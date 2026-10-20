// Stand-in steam_api64.dll for diagnostics. Every export is forwarded to the original
// library (renamed steam_api64_real.dll, see tools/make_proxy_def.py) except two:
//  - SteamInternal_FindOrCreateUserInterface hands the game a local GC for
//    "SteamGameCoordinator001".
//  - SteamInternal_CreateInterface returns the real ISteamClient, with its
//    GetISteamGenericInterface vtable entry redirected so the same name resolves to the
//    local GC when the game asks through the client object.
// Every interface name the game requests is logged, plus the GC messages it sends.
//
// It only activates when the game was launched with -insecure; otherwise every call goes to
// the real library untouched and nothing is written. Windows x64 only.
#include "cs2_gc/client_fingerprint.h"
#include "cs2_gc/gc_endpoint.h"
#include "cs2_gc/gc_msg_ids.h"
#include "cs2_gc/protobuf_dump.h"
#include "cs2_gc/proxy_support.h"

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#undef SendMessage // windows.h renames it; our methods keep their SDK names

#include <chrono>
#include <filesystem>
#include <fstream>
#include <map>
#include <cstring>
#include <mutex>
#include <set>
#include <optional>
#include <sstream>
#include <string>
#include <string_view>

using namespace cs2_gc;

namespace
{
constexpr char GcInterfaceName[] = "SteamGameCoordinator001";
constexpr std::uintmax_t MaxLogBytes = 8u * 1024 * 1024;

// Same layout as the SDK's ISteamGameCoordinator: three virtual calls, in this order.
class SteamGameCoordinatorInterface
{
public:
    virtual GCResult SendMessage(std::uint32_t type, const void *data, std::uint32_t size) = 0;
    virtual bool IsMessageAvailable(std::uint32_t *size) = 0;
    virtual GCResult RetrieveMessage(std::uint32_t *type, void *destination, std::uint32_t capacity,
                                     std::uint32_t *size) = 0;
};

std::wstring ModuleDirectory()
{
    HMODULE self = nullptr;
    GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                       reinterpret_cast<LPCWSTR>(&ModuleDirectory), &self);
    wchar_t path[MAX_PATH * 4]{};
    const DWORD length = GetModuleFileNameW(self, path, static_cast<DWORD>(std::size(path)));
    std::wstring directory(path, length);
    const std::size_t slash = directory.find_last_of(L"\\/");
    return slash == std::wstring::npos ? std::wstring{} : directory.substr(0, slash + 1);
}

std::string Narrow(const wchar_t *text)
{
    std::string out;
    for (; *text; ++text)
        out.push_back(*text < 0x80 ? static_cast<char>(*text) : '?');
    return out;
}

class Logger
{
public:
    explicit Logger(const std::filesystem::path &path) : m_file(path, std::ios::app | std::ios::binary) {}

    void Write(const std::string &text)
    {
        std::lock_guard lock(m_mutex);
        if (!m_file || m_stopped)
            return;
        if (m_written + text.size() > MaxLogBytes)
        {
            m_file << "[log size limit reached; logging stopped]\n";
            m_stopped = true;
            return;
        }
        const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - m_start).count();
        std::ostringstream line;
        line << '[' << ms << " ms] " << text << '\n';
        m_file << line.str();
        m_file.flush();
        m_written += line.str().size();
    }

private:
    std::ofstream m_file;
    std::mutex m_mutex;
    std::chrono::steady_clock::time_point m_start{std::chrono::steady_clock::now()};
    std::uintmax_t m_written{};
    bool m_stopped{};
};

std::string Describe(std::uint32_t type)
{
    const std::uint32_t id = type & ~ProtobufMask;
    const char *name = gc_msg::MessageName(id);
    return std::to_string(id) + " (" + (name ? name : "unnamed in this build") + ")" +
           ((type & ProtobufMask) ? "" : " [no protobuf flag]");
}

std::string Indent(const std::string &text)
{
    std::string out = "    ";
    for (std::size_t i = 0; i < text.size(); ++i)
    {
        out += text[i];
        if (text[i] == '\n' && i + 1 < text.size())
            out += "    ";
    }
    return out;
}

void LogFrame(Logger &log, const char *direction, std::uint32_t type, std::span<const std::uint8_t> bytes)
{
    std::string text = std::string(direction) + " type=" + Describe(type) + " size=" + std::to_string(bytes.size());
    FrameView frame;
    if (ReadProtobufFrame(type, bytes, frame) == FrameError::None)
    {
        // Header and body are dumped through the redacting dumper; raw bytes are never logged.
        const std::string header = DumpProtobuf(frame.header, 8 * 1024);
        const std::string body = DumpProtobuf(frame.body, 48 * 1024);
        text += "\n  header:\n" + (header.empty() ? "    <empty>\n" : Indent(header));
        text += "  body:\n" + (body.empty() ? "    <empty>" : Indent(body));
        if (!text.empty() && text.back() == '\n')
            text.pop_back();
    }
    else
        text += " (not a valid protobuf frame; contents not logged)";
    log.Write(text);
}

class ProxyCoordinator final : public SteamGameCoordinatorInterface
{
public:
    ProxyCoordinator(const GcEndpointConfig &config, Logger &log) : m_gc(config), m_log(log) {}

    GCResult SendMessage(std::uint32_t type, const void *data, std::uint32_t size) override
    {
        if (data && size <= MaxMessageBytes)
            LogFrame(m_log, ">> GAME->GC", type, {static_cast<const std::uint8_t *>(data), size});
        const GCResult result = m_gc.SendMessage(type, data, size);
        if (result != GCResult::OK)
            m_log.Write("   SendMessage rejected, result=" + std::to_string(static_cast<unsigned>(result)));
        return result;
    }

    bool IsMessageAvailable(std::uint32_t *size) override { return m_gc.IsMessageAvailable(size); }

    GCResult RetrieveMessage(std::uint32_t *type, void *destination, std::uint32_t capacity,
                             std::uint32_t *size) override
    {
        const GCResult result = m_gc.RetrieveMessage(type, destination, capacity, size);
        if (result == GCResult::OK && type && size && destination)
            LogFrame(m_log, "<< GC->GAME", *type, {static_cast<const std::uint8_t *>(destination), *size});
        return result;
    }

private:
    LocalGameCoordinator m_gc;
    Logger &m_log;
};

struct State
{
    bool active{};
    std::wstring directory;
    Logger *log{};
    ProxyCoordinator *coordinator{};
    using FindFn = void *(__cdecl *)(int, const char *);
    using CreateFn = void *(__cdecl *)(const char *);
    FindFn realFind{};
    CreateFn realCreate{};
    std::optional<std::uint32_t> genericSlotOffset; // from the real DLL's own flat-API thunk
};

State &Init();

// Each distinct requested interface name is logged once, with how it was requested.
void LogInterfaceRequest(const char *how, const char *version)
{
    State &state = Init();
    if (!state.active || !version)
        return;
    static std::mutex mutex;
    static std::set<std::string> seen;
    const std::string entry = std::string(how) + ": " + std::string(version, strnlen(version, 128));
    std::lock_guard lock(mutex);
    if (seen.size() < 256 && seen.insert(entry).second)
        state.log->Write("interface requested via " + entry);
}

// The original GetISteamGenericInterface for each patched vtable, keyed by the slot address.
std::mutex g_patchMutex;
std::map<void **, void *> g_originalGeneric;

void *__cdecl GenericInterfaceHook(void *self, int user, int pipe, const char *version);

using GenericFn = void *(__cdecl *)(void *, int, int, const char *);

void *__cdecl GenericInterfaceHook(void *self, int user, int pipe, const char *version)
{
    State &state = Init();
    LogInterfaceRequest("ISteamClient::GetISteamGenericInterface", version);
    if (state.active && state.genericSlotOffset && version && std::string_view(version) == GcInterfaceName)
        return state.coordinator;

    void **vtable = *reinterpret_cast<void ***>(self);
    void **slot = reinterpret_cast<void **>(reinterpret_cast<char *>(vtable) + *state.genericSlotOffset);
    void *original = nullptr;
    {
        std::lock_guard lock(g_patchMutex);
        const auto it = g_originalGeneric.find(slot);
        original = it == g_originalGeneric.end() ? nullptr : it->second;
    }
    return original ? reinterpret_cast<GenericFn>(original)(self, user, pipe, version) : nullptr;
}

// Redirects one vtable entry of the real ISteamClient object in place. Only done once per
// vtable, and only when the slot offset was decoded from the real library.
void PatchSteamClient(State &state, void *object)
{
    if (!object || !state.genericSlotOffset)
        return;
    void **vtable = *reinterpret_cast<void ***>(object);
    void **slot = reinterpret_cast<void **>(reinterpret_cast<char *>(vtable) + *state.genericSlotOffset);

    std::lock_guard lock(g_patchMutex);
    if (g_originalGeneric.contains(slot) || *slot == reinterpret_cast<void *>(&GenericInterfaceHook))
        return;
    DWORD oldProtect = 0;
    if (!VirtualProtect(slot, sizeof(void *), PAGE_READWRITE, &oldProtect))
    {
        state.log->Write("could not make the ISteamClient vtable writable; GC hook not installed");
        return;
    }
    g_originalGeneric[slot] = *slot;
    *slot = reinterpret_cast<void *>(&GenericInterfaceHook);
    DWORD ignored = 0;
    VirtualProtect(slot, sizeof(void *), oldProtect, &ignored);
    state.log->Write("ISteamClient::GetISteamGenericInterface hook installed at vtable offset 0x" +
                     [&] { std::ostringstream o; o << std::hex << *state.genericSlotOffset; return o.str(); }());
}

State &Init()
{
    static State state = [] {
        State s;
        s.directory = ModuleDirectory();
        const HMODULE real = LoadLibraryW((s.directory + L"steam_api64_real.dll").c_str());
        if (real)
        {
            s.realFind = reinterpret_cast<State::FindFn>(GetProcAddress(real, "SteamInternal_FindOrCreateUserInterface"));
            s.realCreate = reinterpret_cast<State::CreateFn>(GetProcAddress(real, "SteamInternal_CreateInterface"));
            // The flat-API wrapper is `mov rax,[rcx]; jmp [rax+N]`; N is the vtable offset we need.
            if (const auto *thunk = reinterpret_cast<const std::uint8_t *>(
                    GetProcAddress(real, "SteamAPI_ISteamClient_GetISteamGenericInterface")))
                s.genericSlotOffset = DecodeVtableThunkOffset({thunk, 16});
        }

        s.active = s.realFind && s.realCreate && CommandLineHasArgument(Narrow(GetCommandLineW()), "-insecure");
        if (!s.active)
            return s;

        s.log = new Logger(std::filesystem::path(s.directory + L"cs2_gc_log.txt"));
        ProxyConfig proxy;
        std::ifstream cfg(std::filesystem::path(s.directory + L"cs2_gc.cfg"), std::ios::binary);
        std::string note = "config: defaults";
        if (cfg)
        {
            std::ostringstream text;
            text << cfg.rdbuf();
            if (const auto parsed = ParseProxyConfig(text.str()))
            {
                proxy = *parsed;
                note = "config: cs2_gc.cfg loaded";
            }
            else
                note = "config: cs2_gc.cfg is invalid, using defaults";
        }

        GcEndpointConfig endpoint;
        endpoint.welcomeVersion = proxy.welcomeVersion;
        endpoint.owner = {proxy.ownerType, proxy.steamId};
        endpoint.cacheVersion = proxy.cacheVersion;
        s.coordinator = new ProxyCoordinator(endpoint, *s.log);
        s.log->Write("cs2_gc diagnostic proxy active (-insecure). Targets Steam build " +
                     std::string(TargetSteamBuildId) + "; the GC is local and nothing is sent to Valve.");
        s.log->Write(s.genericSlotOffset ? "ISteamClient hook slot decoded from the real library"
                                         : "could not decode GetISteamGenericInterface from the real library; "
                                           "only interface requests will be logged");
        s.log->Write(note + "; welcome values are unverified guesses. Logs redact SteamID-shaped values, "
                            "but review before sharing.");
        return s;
    }();
    return state;
}
}

extern "C" __declspec(dllexport) void *__cdecl SteamInternal_CreateInterface(const char *version)
{
    State &state = Init();
    if (!state.realCreate)
        return nullptr;
    void *result = state.realCreate(version);
    LogInterfaceRequest("SteamInternal_CreateInterface", version);
    if (state.active && result && version && std::string_view(version) == "SteamClient023")
        PatchSteamClient(state, result);
    return result;
}

extern "C" __declspec(dllexport) void *__cdecl SteamInternal_FindOrCreateUserInterface(int user, const char *version)
{
    State &state = Init();
    if (!state.realFind)
        return nullptr;
    LogInterfaceRequest("SteamInternal_FindOrCreateUserInterface", version);
    if (state.active && version && std::string_view(version) == GcInterfaceName)
        return state.coordinator;
    return state.realFind(user, version);
}

BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, LPVOID)
{
    if (reason == DLL_PROCESS_ATTACH)
        DisableThreadLibraryCalls(module); // all setup is lazy; nothing runs under the loader lock
    return TRUE;
}
