// Stand-in steam_api64.dll for diagnostics. Every export is forwarded to the original
// library (renamed steam_api64_real.dll, see tools/make_proxy_def.py) except two:
//  - SteamInternal_FindOrCreateUserInterface hands the game a local GC for
//    "SteamGameCoordinator001".
//  - SteamInternal_CreateInterface returns the real ISteamClient, with its
//    GetISteamGenericInterface vtable entry redirected so the same name resolves to the
//    local GC when the game asks through the client object.
//  - SteamAPI_RegisterCallback / UnregisterCallback / RunCallbacks take over the two GC
//    callbacks, so the game is told (GCMessageAvailable_t) when the local GC has a message
//    for it. Without that callback the game does not pick replies up.
// Every interface name the game requests is logged, plus the GC messages it sends.
//
// Two modes (cs2_gc.cfg, "mode"). local, the default, answers the game from the in-process GC.
// capture hands the game Valve's real GC unchanged and only records the traffic in both
// directions, with the local account's identifiers redacted; it is for learning what the real
// GC sends. Neither mode does anything without -insecure.
//
// It only activates when the game was launched with -insecure; otherwise every call goes to
// the real library untouched and nothing is written. Windows x64 only.
#include "cs2_gc/client_fingerprint.h"
#include "cs2_gc/gc_endpoint.h"
#include "cs2_gc/gc_msg_ids.h"
#include "cs2_gc/gc_summary.h"
#include "cs2_gc/protobuf_dump.h"
#include "cs2_gc/proxy_support.h"
#include "cs2_gc/replay.h"

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#undef SendMessage // windows.h renames it; our methods keep their SDK names

#include <atomic>
#include <chrono>
#include <vector>
#include <filesystem>
#include <fstream>
#include <functional>
#include <memory>
#include <map>
#include <cstring>
#include <utility>
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

// The local account's SteamID64 and 32-bit account ID, once known, are redacted from dumps.
std::mutex g_redactMutex;
std::vector<std::uint64_t> g_redact;

void AddRedaction(std::uint64_t steamId)
{
    std::lock_guard lock(g_redactMutex);
    g_redact = {steamId, steamId & 0xFFFFFFFFull};
}

DumpOptions CurrentOptions(std::size_t maxBytes)
{
    DumpOptions options;
    options.maxBytes = maxBytes;
    std::lock_guard lock(g_redactMutex);
    options.redact = g_redact;
    return options;
}

void LogFrame(Logger &log, const char *direction, std::uint32_t type, std::span<const std::uint8_t> bytes)
{
    std::string text = std::string(direction) + " type=" + Describe(type) + " size=" + std::to_string(bytes.size());
    FrameView frame;
    if (ReadProtobufFrame(type, bytes, frame) == FrameError::None)
    {
        // Header and body are dumped through the redacting dumper; raw bytes are never logged.
        const std::string header = DumpProtobuf(frame.header, CurrentOptions(8 * 1024));
        // Inventory-sized shared-object messages are summarised (type IDs, counts, one sample
        // each) instead of dumped whole.
        const std::string summary = SummarizeSoMessage(type & ~ProtobufMask, frame.body, CurrentOptions(64 * 1024));
        const std::string body = summary.empty() ? DumpProtobuf(frame.body, CurrentOptions(48 * 1024))
                                                 : "<" + std::to_string(frame.body.size()) + " bytes; see summary>\n";
        text += "\n  header:\n" + (header.empty() ? "    <empty>\n" : Indent(header));
        text += "  body:\n" + (body.empty() ? "    <empty>\n" : Indent(body));
        text += summary;
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
    // steamIdProvider is asked until it returns a nonzero SteamID64, which then becomes the
    // cache owner. Leave it empty when the config already supplies one.
    ProxyCoordinator(const GcEndpointConfig &config, Logger &log, std::function<std::uint64_t()> steamIdProvider)
        : m_gc(config), m_log(log), m_ownerType(config.owner.type), m_provider(std::move(steamIdProvider))
    {
    }

    GCResult SendMessage(std::uint32_t type, const void *data, std::uint32_t size) override
    {
        if (m_provider)
        {
            if (const std::uint64_t id = m_provider())
            {
                m_gc.SetOwner({m_ownerType, id});
                AddRedaction(id);
                m_provider = nullptr;
                m_log.Write("cache owner taken from the local Steam session (value not logged)");
            }
        }
        if (data && size <= MaxMessageBytes)
            LogFrame(m_log, ">> GAME->GC", type, {static_cast<const std::uint8_t *>(data), size});
        const GCResult result = m_gc.SendMessage(type, data, size);
        if (result != GCResult::OK)
            m_log.Write("   SendMessage rejected, result=" + std::to_string(static_cast<unsigned>(result)));
        return result;
    }

    bool IsMessageAvailable(std::uint32_t *size) override { return m_gc.IsMessageAvailable(size); }

    void EnableReplay(std::shared_ptr<const ReplayStore> store) { m_gc.EnableReplay(std::move(store)); }

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
    std::uint32_t m_ownerType;
    std::function<std::uint64_t()> m_provider;
};

// Wraps Valve's real GC interface: every call is passed straight through and only logged.
class CaptureCoordinator final : public SteamGameCoordinatorInterface
{
public:
    CaptureCoordinator(SteamGameCoordinatorInterface *real, Logger &log, std::function<void()> identity,
                       std::filesystem::path replayDirectory)
        : m_real(real), m_log(log), m_identity(std::move(identity)), m_replayDirectory(std::move(replayDirectory))
    {
    }

    GCResult SendMessage(std::uint32_t type, const void *data, std::uint32_t size) override
    {
        m_identity();
        if (data && size <= MaxMessageBytes)
            LogFrame(m_log, ">> GAME->REAL GC", type, {static_cast<const std::uint8_t *>(data), size});
        return m_real->SendMessage(type, data, size);
    }

    bool IsMessageAvailable(std::uint32_t *size) override { return m_real->IsMessageAvailable(size); }

    GCResult RetrieveMessage(std::uint32_t *type, void *destination, std::uint32_t capacity,
                             std::uint32_t *size) override
    {
        const GCResult result = m_real->RetrieveMessage(type, destination, capacity, size);
        if (result == GCResult::OK && type && size && destination)
        {
            m_identity();
            const std::span<const std::uint8_t> bytes{static_cast<const std::uint8_t *>(destination), *size};
            LogFrame(m_log, "<< REAL GC->GAME", *type, bytes);
            Record(*type, bytes);
        }
        return result;
    }

private:
    // Keeps the first body of each message type so local mode can replay it. The files hold
    // account data and stay on this machine.
    void Record(std::uint32_t type, std::span<const std::uint8_t> bytes)
    {
        FrameView frame;
        if (ReadProtobufFrame(type, bytes, frame) != FrameError::None)
            return;
        const std::uint32_t id = type & ~ProtobufMask;
        if (ReplayStore::SaveIfMissing(m_replayDirectory, id, frame.body))
            m_log.Write("saved a replay recording for message " + std::to_string(id) + " (" +
                        std::to_string(frame.body.size()) + " bytes)");
    }

    SteamGameCoordinatorInterface *m_real;
    Logger &m_log;
    std::function<void()> m_identity;
    std::filesystem::path m_replayDirectory;
};

struct State
{
    bool active{};
    std::wstring directory;
    Logger *log{};
    ProxyCoordinator *coordinator{};
    ProxyMode mode{ProxyMode::Local};
    using FindFn = void *(__cdecl *)(int, const char *);
    using CreateFn = void *(__cdecl *)(const char *);
    FindFn realFind{};
    CreateFn realCreate{};
    void (__cdecl *realRegister)(void *, int){};
    void (__cdecl *realUnregister)(void *){};
    void (__cdecl *realRunCallbacks)(){};
    int (__cdecl *realGetUser)(){};
    std::uint64_t (__cdecl *realGetSteamId)(void *){};
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

// Capture mode: the account identifiers are learned from the local Steam session so they can
// be redacted from everything that is logged.
void ResolveIdentity()
{
    static std::atomic<bool> done{false};
    State &state = Init();
    if (done || !state.realGetUser || !state.realGetSteamId)
        return;
    void *user = state.realFind(state.realGetUser(), "SteamUser023");
    const std::uint64_t id = user ? state.realGetSteamId(user) : 0;
    if (!id)
        return;
    AddRedaction(id);
    done = true;
    state.log->Write("account identifiers read from the local Steam session; they are redacted (not logged)");
}

// Returns what the game should be given for the GC interface. Local mode: the in-process GC.
// Capture mode: a logging wrapper around Valve's real one, which the caller obtained.
void *GcInterfaceFor(State &state, void *realObject)
{
    if (state.mode == ProxyMode::Local)
        return state.coordinator;
    if (!realObject)
        return nullptr;
    static std::mutex mutex;
    static std::map<void *, CaptureCoordinator *> wrappers;
    std::lock_guard lock(mutex);
    CaptureCoordinator *&wrapper = wrappers[realObject];
    if (!wrapper)
    {
        wrapper = new CaptureCoordinator(static_cast<SteamGameCoordinatorInterface *>(realObject), *state.log,
                                         [] { ResolveIdentity(); },
                                         std::filesystem::path(state.directory + L"cs2_gc_replay"));
        state.log->Write("capture: wrapping Valve's real SteamGameCoordinator001");
    }
    return wrapper;
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
    const bool wantsGc = state.active && state.genericSlotOffset && version &&
                         std::string_view(version) == GcInterfaceName;
    if (wantsGc && state.mode == ProxyMode::Local)
        return state.coordinator;

    void **vtable = *reinterpret_cast<void ***>(self);
    void **slot = reinterpret_cast<void **>(reinterpret_cast<char *>(vtable) + *state.genericSlotOffset);
    void *original = nullptr;
    {
        std::lock_guard lock(g_patchMutex);
        const auto it = g_originalGeneric.find(slot);
        original = it == g_originalGeneric.end() ? nullptr : it->second;
    }
    void *result = original ? reinterpret_cast<GenericFn>(original)(self, user, pipe, version) : nullptr;
    return wantsGc ? GcInterfaceFor(state, result) : result;
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
            s.realRegister = reinterpret_cast<decltype(s.realRegister)>(GetProcAddress(real, "SteamAPI_RegisterCallback"));
            s.realUnregister = reinterpret_cast<decltype(s.realUnregister)>(GetProcAddress(real, "SteamAPI_UnregisterCallback"));
            s.realRunCallbacks = reinterpret_cast<decltype(s.realRunCallbacks)>(GetProcAddress(real, "SteamAPI_RunCallbacks"));
            s.realGetUser = reinterpret_cast<decltype(s.realGetUser)>(GetProcAddress(real, "SteamAPI_GetHSteamUser"));
            s.realGetSteamId = reinterpret_cast<decltype(s.realGetSteamId)>(GetProcAddress(real, "SteamAPI_ISteamUser_GetSteamID"));
            // The flat-API wrapper is `mov rax,[rcx]; jmp [rax+N]`; N is the vtable offset we need.
            if (const auto *thunk = reinterpret_cast<const std::uint8_t *>(
                    GetProcAddress(real, "SteamAPI_ISteamClient_GetISteamGenericInterface")))
                s.genericSlotOffset = DecodeVtableThunkOffset({thunk, 16});
        }

        s.active = s.realFind && s.realCreate && s.realRegister && s.realUnregister && s.realRunCallbacks &&
                   CommandLineHasArgument(Narrow(GetCommandLineW()), "-insecure");
        if (!s.active)
            return s;

        s.log = new Logger(std::filesystem::path(s.directory + L"cs2_gc_log.txt"));
        s.log->Write("---- new session ----");
        ProxyConfig proxy;
        // Windows hides known extensions, so "cs2_gc.cfg" is easily saved as "cs2_gc.cfg.txt".
        std::ifstream cfg(std::filesystem::path(s.directory + L"cs2_gc.cfg"), std::ios::binary);
        std::string configName = "cs2_gc.cfg";
        if (!cfg)
        {
            cfg.clear();
            cfg.open(std::filesystem::path(s.directory + L"cs2_gc.cfg.txt"), std::ios::binary);
            configName = "cs2_gc.cfg.txt";
        }
        std::string note = "config: no cs2_gc.cfg next to steam_api64.dll, using defaults";
        if (cfg)
        {
            std::ostringstream text;
            text << cfg.rdbuf();
            if (const auto parsed = ParseProxyConfig(text.str()))
            {
                proxy = *parsed;
                note = "config: " + configName + " loaded";
            }
            else
                note = "config: " + configName + " is invalid, using defaults";
        }
        // A launch option is easier to get right than a file, and takes precedence over it.
        if (CommandLineHasArgument(Narrow(GetCommandLineW()), "-cs2gc_capture"))
        {
            proxy.mode = ProxyMode::Capture;
            note += "; -cs2gc_capture launch option set";
        }

        s.mode = proxy.mode;
        if (proxy.steamId)
            AddRedaction(proxy.steamId);

        GcEndpointConfig endpoint;
        endpoint.welcomeVersion = proxy.welcomeVersion;
        endpoint.owner = {proxy.ownerType, proxy.steamId};
        endpoint.cacheVersion = proxy.cacheVersion;
        std::function<std::uint64_t()> provider;
        if (proxy.steamId == 0 && s.realGetUser && s.realGetSteamId)
        {
            // Looked up when called: this lambda runs while the state is still being built,
            // and the local is moved into its final home afterwards.
            provider = []() -> std::uint64_t {
                State &self = Init();
                void *user = self.realFind(self.realGetUser(), "SteamUser023");
                return user ? self.realGetSteamId(user) : 0;
            };
        }
        if (s.mode == ProxyMode::Local)
        {
            s.coordinator = new ProxyCoordinator(endpoint, *s.log, std::move(provider));
            auto replay = std::make_shared<ReplayStore>(
                ReplayStore::LoadDirectory(std::filesystem::path(s.directory + L"cs2_gc_replay")));
            if (replay->Size())
            {
                s.coordinator->EnableReplay(replay);
                s.log->Write("replay: " + std::to_string(replay->Size()) + " recorded message bodies loaded from "
                             "cs2_gc_replay; they belong to the account they were captured from");
            }
            else
                s.log->Write("replay: no recordings in cs2_gc_replay, using the synthetic welcome");
            s.log->Write("cs2_gc diagnostic proxy active (-insecure), mode=local. Targets Steam build " +
                         std::string(TargetSteamBuildId) + "; the GC is local and nothing is sent to Valve.");
        }
        else
            s.log->Write("cs2_gc diagnostic proxy active (-insecure), mode=capture. Valve's real GC is used "
                         "unchanged; traffic is only recorded. Targets Steam build " +
                         std::string(TargetSteamBuildId) + ".");
        s.log->Write(s.genericSlotOffset ? "ISteamClient hook slot decoded from the real library"
                                         : "could not decode GetISteamGenericInterface from the real library; "
                                           "only interface requests will be logged");
        s.log->Write(note + "; welcome values are unverified guesses. Logs redact SteamID-shaped values and the "
                            "local account's identifiers, but review before sharing.");
        return s;
    }();
    return state;
}

// ---------------------------------------------------------------------------------------
// GC callbacks. The game registers CCallbackBase objects with Steam. For the two GC callback
// IDs the proxy keeps them itself and invokes them from SteamAPI_RunCallbacks, on the game's
// own thread, the way Steam would.
//
// The game is built with MSVC, which lays overloaded virtual functions out in reverse
// declaration order. CCallbackBase declares Run(void*), Run(void*, bool, uint64) and
// GetCallbackSizeBytes(), so the vtable is [Run(void*, bool, uint64), Run(void*), Size].
// This file is compiled with a different ABI, so the slots are called explicitly instead of
// through a C++ virtual call.
constexpr int GcMessageAvailableId = 1701; // k_iSteamGameCoordinatorCallbacks + 1
constexpr int GcMessageFailedId = 1702;    // + 2
constexpr std::size_t RunSlot = 1;
constexpr std::size_t SizeSlot = 2;
constexpr std::uint8_t CallbackFlagRegistered = 0x01;
constexpr std::uint8_t CallbackFlagGameServer = 0x02;

struct CallbackObject
{
    void **vtable;
    std::uint8_t flags;
};

struct RegisteredCallback
{
    int id;
    CallbackObject *object;
};

std::mutex g_callbackMutex;
std::vector<RegisteredCallback> g_callbacks;

bool IsGcCallback(int id)
{
    return id == GcMessageAvailableId || id == GcMessageFailedId;
}

void DeliverGcMessageAvailable(State &state, std::uint32_t size)
{
    std::vector<CallbackObject *> targets;
    {
        std::lock_guard lock(g_callbackMutex);
        for (const RegisteredCallback &entry : g_callbacks)
            if (entry.id == GcMessageAvailableId)
                targets.push_back(entry.object);
    }

    static int delivered = 0;
    for (CallbackObject *object : targets)
    {
        // Sanity-check the vtable assumption before calling into the game's object:
        // GCMessageAvailable_t is a single uint32.
        const auto sizeFn = reinterpret_cast<int(__cdecl *)(void *)>(object->vtable[SizeSlot]);
        if (sizeFn(object) != static_cast<int>(sizeof(std::uint32_t)))
        {
            static bool warned = false;
            if (!std::exchange(warned, true))
                state.log->Write("callback object does not look like GCMessageAvailable_t; not delivering");
            continue;
        }
        if (delivered < 10)
        {
            ++delivered;
            state.log->Write("delivering GCMessageAvailable_t (message size " + std::to_string(size) + ")");
        }
        reinterpret_cast<void(__cdecl *)(void *, void *)>(object->vtable[RunSlot])(object, &size);
    }
}
}

extern "C" __declspec(dllexport) void __cdecl SteamAPI_RegisterCallback(void *callback, int id)
{
    State &state = Init();
    if (state.active && state.mode == ProxyMode::Local && callback && IsGcCallback(id))
    {
        auto *object = static_cast<CallbackObject *>(callback);
        if (!(object->flags & CallbackFlagGameServer))
        {
            {
                std::lock_guard lock(g_callbackMutex);
                g_callbacks.push_back({id, object});
            }
            object->flags |= CallbackFlagRegistered;
            state.log->Write("took over callback registration for id " + std::to_string(id));
            return;
        }
    }
    if (state.realRegister)
        state.realRegister(callback, id);
}

extern "C" __declspec(dllexport) void __cdecl SteamAPI_UnregisterCallback(void *callback)
{
    State &state = Init();
    if (state.active && callback)
    {
        bool ours = false;
        {
            std::lock_guard lock(g_callbackMutex);
            for (auto it = g_callbacks.begin(); it != g_callbacks.end();)
            {
                if (it->object == callback)
                {
                    ours = true;
                    it = g_callbacks.erase(it);
                }
                else
                    ++it;
            }
        }
        if (ours)
        {
            static_cast<CallbackObject *>(callback)->flags &= static_cast<std::uint8_t>(~CallbackFlagRegistered);
            return;
        }
    }
    if (state.realUnregister)
        state.realUnregister(callback);
}

extern "C" __declspec(dllexport) void __cdecl SteamAPI_RunCallbacks()
{
    State &state = Init();
    if (state.realRunCallbacks)
        state.realRunCallbacks();
    std::uint32_t size = 0;
    if (state.active && state.coordinator && state.coordinator->IsMessageAvailable(&size))
        DeliverGcMessageAvailable(state, size);
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
    {
        if (state.mode == ProxyMode::Local)
            return state.coordinator;
        return GcInterfaceFor(state, state.realFind(user, version));
    }
    return state.realFind(user, version);
}

BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, LPVOID)
{
    if (reason == DLL_PROCESS_ATTACH)
        DisableThreadLibraryCalls(module); // all setup is lazy; nothing runs under the loader lock
    return TRUE;
}
