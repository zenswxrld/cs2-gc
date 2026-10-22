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
#include "viewmodel_range.h"
#include "cs2_gc/client_fingerprint.h"
#include "cs2_gc/econ_item.h"
#include "cs2_gc/gc_endpoint.h"
#include "cs2_gc/gc_msg_ids.h"
#include "cs2_gc/gc_summary.h"
#include "cs2_gc/protobuf_dump.h"
#include "cs2_gc/protobuf.h"
#include "cs2_gc/proxy_support.h"
#include "cs2_gc/replay.h"

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#undef SendMessage // windows.h renames it; our methods keep their SDK names

#include <atomic>
#include <chrono>
#include <charconv>
#include <vector>
#include <filesystem>
#include <fstream>
#include <functional>
#include <memory>
#include <algorithm>
#include <map>
#include <random>
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

std::recursive_mutex g_localGcMutex; // client and listen server share one inventory
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
        std::lock_guard lock(g_localGcMutex);
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
    void EnableNativeStore(const std::filesystem::path &path, const ReplayStore &replay)
    {
        const auto id = gc_msg::EGCItemMsg::k_EMsgGCStoreGetUserDataResponse;
        const auto *recorded = replay.Find(id);
        if (!recorded) return;
        m_gc.SetHandler(gc_msg::EGCItemMsg::k_EMsgGCStoreGetUserData,
            [path, fallback = *recorded, id](const FrameView &frame, LocalGameCoordinator &gc) {
                std::vector<std::uint8_t> body;
                std::error_code error;
                const auto size = std::filesystem::file_size(path, error);
                if (!error && size <= MaxMessageBytes)
                {
                    std::ifstream input(path, std::ios::binary);
                    body.assign(std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>());
                    if (input.bad() || body.size() != size) body.clear();
                }
                bool hasSheet = false;
                PbReader reader(body); PbField field;
                while (reader.Next(field))
                    if (field.number == 8 && field.wire == 2 && field.bytes.size() >= 17 &&
                        std::memcmp(field.bytes.data(), "LZMA", 4) == 0) hasSheet = true;
                if (reader.Failed() || !hasSheet) body = fallback;
                gc.Reply(id, body, ReplyHeaderFor(frame));
            });
    }
    void SetItemProvider(LocalGameCoordinator::ItemProvider provider) { m_gc.SetItemProvider(std::move(provider)); }
    void SetDropRecordedItems(bool drop) { m_gc.SetDropRecordedItems(drop); }
    void SetArmoryCredits(std::optional<std::uint32_t> credits) { m_gc.SetArmoryCredits(credits); }
    void EnableLocalPremier(const LocalPremier &rank) { m_gc.EnableLocalPremier(rank); }
    void EnableProgression(std::filesystem::path rewardPath, std::function<void()> afterReward)
    {
        m_rewardPath = std::move(rewardPath);
        m_afterReward = std::move(afterReward);
        m_log.Write("progression: gameplay rewards use the local bridge (automatic startup controlled by rewards_auto_start)");
    }
    void PollProgression()
    {
        std::lock_guard inventoryLock(g_localGcMutex);
        std::lock_guard lock(m_rewardMutex);
        const auto now = std::chrono::steady_clock::now();
        if (m_rewardPath.empty() || now < m_nextRewardPoll)
            return;
        m_nextRewardPoll = now + std::chrono::seconds(1);
        std::ifstream input(m_rewardPath);
        std::string text;
        std::getline(input, text);
        std::uint64_t total = 0;
        const auto [end, error] = std::from_chars(text.data(), text.data() + text.size(), total);
        if (input && error == std::errc{} && end == text.data() + text.size())
            m_gc.ApplyEarnedXp(total, m_afterReward);
        {
            std::ifstream matches(m_rewardPath.parent_path() / "cs2_gc_matches.txt");
            std::string count;
            std::getline(matches, count);
            std::uint64_t completed = 0;
            const auto [last, ec] = std::from_chars(count.data(), count.data() + count.size(), completed);
            if (matches && ec == std::errc{} && last == count.data() + count.size())
                m_gc.ApplyMatchRewards(completed, m_afterReward);
        }
        PollTradeUpRequest();
        PollTerminalRequest();
        PollCareClaims();
        PollCarePackageRequest();
#ifdef CS2_GC_DEBUG_TOOLS
        {
            std::ifstream control(m_rewardPath.parent_path() / "cs2_gc_console.txt");
            std::uint64_t pid = 0, stars = 0, offset = 0; std::string extra;
            if ((control >> pid >> stars >> offset) && !(control >> extra) && control.eof() &&
                pid == GetCurrentProcessId() && offset <= 1000000)
                m_gc.ApplyConsoleControl(stars, static_cast<std::uint32_t>(offset), m_afterReward);
        }
#endif
        m_gc.ApplyLevelRewards(m_afterReward);
        {
            std::ifstream premier(m_rewardPath.parent_path() / "cs2_gc_premier.txt");
            std::uint64_t rating = 0, wins = 0, placements = 0;
            std::string extra;
            if ((premier >> rating >> wins >> placements) && !(premier >> extra) && premier.eof() &&
                rating <= 99999 && wins <= UINT32_MAX && placements >= 1 && placements <= 100)
                m_gc.SetLocalPremier({static_cast<std::uint32_t>(rating), static_cast<std::uint32_t>(wins),
                                      static_cast<std::uint32_t>(placements)});
        }
    }
    // Care-package claims (build 31): the native claim and Armory calls refuse to send local claims (build 28-30
    // logs), so the patched page prints the claim and this reads lines appended to csgo/console.log (-condebug)
    // since launch. The GC still validates the package generation and the three choices.
    void PollCareClaims()
    {
        const auto path = m_rewardPath.parent_path().parent_path().parent_path() / "csgo" / "console.log";
        std::error_code error;
        const auto size = std::filesystem::file_size(path, error);
        if (error) return;
        if (!m_consoleOffset || size < *m_consoleOffset) { m_consoleOffset = size; return; } // launch or new file
        if (size == *m_consoleOffset) return;
        std::ifstream log(path, std::ios::binary);
        log.seekg(static_cast<std::streamoff>(*m_consoleOffset));
        std::string text(static_cast<std::size_t>(std::min<std::uintmax_t>(size - *m_consoleOffset, 1u << 20)), '\0');
        log.read(text.data(), static_cast<std::streamsize>(text.size()));
        text.resize(static_cast<std::size_t>(log.gcount()));
        const auto complete = text.rfind('\n');
        if (complete == std::string::npos) { if (text.size() == (1u << 20)) *m_consoleOffset += text.size(); return; }
        text.resize(complete + 1);
        *m_consoleOffset += text.size();
        for (const auto &claim : ParseCareConsoleClaims(text))
            if (m_gc.ClaimCareFromConsole(claim.generation, claim.tokens, m_afterReward)) m_log.Write("care package: console claim granted");
    }
    void EnableLiveInventory(std::shared_ptr<LiveInventory> inventory, std::function<void()> afterChange)
    {
        m_gc.EnableLiveInventory(std::move(inventory), std::move(afterChange));
    }
    void EnableServerInventory(std::shared_ptr<LiveInventory> inventory) { m_gc.EnableServerInventory(std::move(inventory)); }
    void RefreshServerInventory()
    {
        std::lock_guard lock(g_localGcMutex);
        m_gc.RefreshServerInventory();
    }
    void EnableStorePurchaseFailure() { m_gc.EnableStorePurchaseFailure(); }
    void EnableStorePurchases(std::shared_ptr<LiveInventory> inventory, std::function<bool(std::uint32_t)> canSell,
                              std::function<void()> afterGrant)
    {
        m_gc.EnableStorePurchases(std::move(inventory), std::move(canSell), std::move(afterGrant));
    }
    std::optional<std::uint64_t> TakePendingAuthorization() { return m_gc.TakePendingAuthorization(); }
    void EnableContainers(std::shared_ptr<LiveInventory> inventory, std::shared_ptr<const Schema> schema,
                          RandomSource random, std::function<void()> afterChange)
    {
        m_gc.EnableContainers(std::move(inventory), std::move(schema), std::move(random), std::move(afterChange));
    }
    void EnableArmory(std::shared_ptr<Armory> armory, std::shared_ptr<LiveInventory> inventory, RandomSource random,
                      std::function<void()> afterGrant)
    {
        m_gc.EnableArmory(std::move(armory), std::move(inventory), std::move(random), std::move(afterGrant));
    }

    GCResult RetrieveMessage(std::uint32_t *type, void *destination, std::uint32_t capacity,
                             std::uint32_t *size) override
    {
        const GCResult result = m_gc.RetrieveMessage(type, destination, capacity, size);
        if (result == GCResult::OK && type && size && destination)
            LogFrame(m_log, "<< GC->GAME", *type, {static_cast<const std::uint8_t *>(destination), *size});
        return result;
    }

private:
    void PollCarePackageRequest()
    {
        const auto dir = m_rewardPath.parent_path();
        const auto pending = dir / "cs2_gc_care_request.txt";
        const auto processing = dir / "cs2_gc_care_processing.txt";
        std::error_code ec;
        // Recover an interrupted request too; generation checks make replay harmless.
        if (!std::filesystem::exists(processing,ec)) {
            if (!std::filesystem::exists(pending,ec)) return;
            std::filesystem::rename(pending,processing,ec);
            if (ec) return;
        }
        std::ifstream input(processing);
        std::string line((std::istreambuf_iterator<char>(input)),std::istreambuf_iterator<char>());
        input.close();
        if (!line.empty() && line.back() == '\n') line.pop_back();
        const auto request = DecodeLocalCareRequest(line);
        std::ifstream boot(dir / "cs2_gc_console_boot.txt");
        std::string nonce,extra;
        const bool session = bool(boot >> nonce) && !(boot >> extra);
        const bool accepted = request && session && request->processId == GetCurrentProcessId() &&
            request->nonce == nonce && m_gc.ClaimLocalCarePackage(request->generation,request->mask,m_afterReward);
        m_log.Write(accepted ? "care helper: three selected rewards granted and saved" :
                               "care helper: request rejected; no rewards granted");
        std::filesystem::remove(processing,ec);
    }
    void PollTerminalRequest()
    {
        const auto dir = m_rewardPath.parent_path();
        const auto pending = dir / "cs2_gc_terminal_request.txt";
        const auto processing = dir / "cs2_gc_terminal_processing.txt";
        std::error_code ec;
        if (std::filesystem::exists(processing, ec) || !std::filesystem::exists(pending, ec)) return;
        std::filesystem::rename(pending, processing, ec);
        if (ec) return;
        std::ifstream input(processing);
        std::string line; std::getline(input, line); input.close();
        // Reuse the strict token/ID decoder; repeat one ID only to share the transport shape.
        const auto request = DecodeLocalTradeUpRequest(line);
        bool valid = request && request->itemIds.size() == 5;
        if (valid)
            for (const auto id : request->itemIds) valid = valid && id == request->itemIds.front();
        const bool accepted = valid && m_gc.AcceptLocalTerminal(request->itemIds.front(), m_afterReward);
        if (request)
        {
            const auto temporary = dir / "cs2_gc_terminal_result.txt.tmp";
            std::ofstream output(temporary);
            output << request->token << "\n" << (accepted ? "success" : "rejected; check cs2_gc_log.txt") << "\n";
            output.close();
            std::filesystem::remove(dir / "cs2_gc_terminal_result.txt", ec);
            std::filesystem::rename(temporary, dir / "cs2_gc_terminal_result.txt", ec);
        }
        std::filesystem::remove(processing, ec);
    }
    void PollTradeUpRequest()
    {
        const auto directory = m_rewardPath.parent_path();
        const auto pending = directory / "cs2_gc_tradeup_request.txt";
        const auto processing = directory / "cs2_gc_tradeup_processing.txt";
        std::error_code ec;
        if (std::filesystem::exists(processing, ec) || !std::filesystem::exists(pending, ec))
            return;
        std::filesystem::rename(pending, processing, ec);
        if (ec)
            return;
        std::ifstream input(processing);
        std::string line;
        std::getline(input, line);
        input.close();
        const auto request = DecodeLocalTradeUpRequest(line);
        if (request)
        {
            PbWriter body;
            body.Varint(1, 1);
            for (const auto id : request->itemIds)
                body.Varint(2, id);
            std::vector<std::uint8_t> frame;
            WriteProtobufFrame(gc_msg::EGCItemMsg::k_EMsgGCCraft, {}, body.bytes(), frame);
            const auto ignored = m_gc.IgnoredMessages();
            const auto result = SendMessage(gc_msg::EGCItemMsg::k_EMsgGCCraft | ProtobufMask, frame.data(),
                                             static_cast<std::uint32_t>(frame.size()));
            const bool success = result == GCResult::OK && ignored == m_gc.IgnoredMessages();
            const auto temporary = directory / "cs2_gc_tradeup_result.tmp";
            std::ofstream output(temporary, std::ios::trunc);
            output << request->token << '\n' << (success ? "success" : "rejected; check cs2_gc_log.txt") << '\n';
            output.close();
            if (output)
                std::filesystem::rename(temporary, directory / "cs2_gc_tradeup_result.txt", ec);
        }
        else
            m_log.Write("local trade-up helper: invalid request; nothing consumed");
        std::filesystem::remove(processing, ec);
    }
    LocalGameCoordinator m_gc;
    std::filesystem::path m_rewardPath;
    std::optional<std::uintmax_t> m_consoleOffset; // console.log bytes already read (care claims)
    std::function<void()> m_afterReward;
    std::chrono::steady_clock::time_point m_nextRewardPoll{};
    std::mutex m_rewardMutex;
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
    ProxyCoordinator *serverCoordinator{};
    ProxyMode mode{ProxyMode::Local};
    bool autoRewards{};
    HANDLE rewardsProcess{};
    unsigned rewardsLaunchAttempts{};
    std::chrono::steady_clock::time_point nextRewardsLaunch{};
    using FindFn = void *(__cdecl *)(int, const char *);
    using CreateFn = void *(__cdecl *)(const char *);
    FindFn realFind{};
    FindFn realFindServer{};
    CreateFn realCreate{};
    void (__cdecl *realRegister)(void *, int){};
    void (__cdecl *realUnregister)(void *){};
    void (__cdecl *realRunCallbacks)(){};
    void (__cdecl *realServerRunCallbacks)(){};
    int (__cdecl *realServerPipe)(){};
    int (__cdecl *realGetUser)(){};
    std::uint64_t (__cdecl *realGetSteamId)(void *){};
    std::optional<std::uint32_t> genericSlotOffset; // from the real DLL's own flat-API thunk
};

// Called from the normal game callback loop, never DllMain/loader initialization.
void StartRewardsIfNeeded(State &state)
{
    if (!state.autoRewards)
        return;
    static std::mutex launchMutex;
    std::lock_guard lock(launchMutex);
    const auto now = std::chrono::steady_clock::now();
    if (now < state.nextRewardsLaunch)
        return;
    state.nextRewardsLaunch = now + std::chrono::seconds(10);
    if (state.rewardsProcess)
    {
        if (WaitForSingleObject(state.rewardsProcess, 0) == WAIT_TIMEOUT)
            return;
        DWORD code = 1;
        GetExitCodeProcess(state.rewardsProcess, &code);
        CloseHandle(state.rewardsProcess);
        state.rewardsProcess = nullptr;
        if (code == 0)
        {
            state.autoRewards = false; // another helper already holds the directory lock
            state.log->Write("rewards: launcher finished; an existing helper may already be running");
            return;
        }
        state.log->Write("rewards: helper exited with code " + std::to_string(code) +
                         "; see cs2_gc_rewards.log (Python 3 is required)");
    }
    if (state.rewardsLaunchAttempts >= 3)
    {
        state.autoRewards = false;
        state.log->Write("rewards: stopped retrying; check cs2_gc_rewards.log or run start_rewards.cmd to diagnose");
        return;
    }
    ++state.rewardsLaunchAttempts;
    const auto script = std::filesystem::path(state.directory) / L"gsi_rewards.py";
    const auto cfg = (std::filesystem::path(state.directory) / L".." / L".." / L"csgo" / L"cfg").lexically_normal();
    if (!std::filesystem::exists(script) || !std::filesystem::is_directory(cfg))
    {
        state.autoRewards = false;
        state.log->Write("rewards: missing bundled helper or game/csgo/cfg; extract the complete test ZIP beside the DLL");
        return;
    }
    struct Candidate { const wchar_t *name; bool launcher; };
    const Candidate candidates[] = {{L"pyw.exe", true}, {L"pythonw.exe", false},
                                    {L"py.exe", true}, {L"python.exe", false}};
    for (const auto &candidate : candidates)
    {
        wchar_t found[32768];
        const auto length = SearchPathW(nullptr, candidate.name, nullptr, 32768, found, nullptr);
        if (!length || length >= 32768)
            continue;
        std::wstring command = QuoteWindowsArgument(found);
        if (candidate.launcher) command += L" -3";
        command += L" " + QuoteWindowsArgument(script.wstring()) +
                   L" --proxy-dir " + QuoteWindowsArgument(state.directory) +
                   L" --cfg-dir " + QuoteWindowsArgument(cfg.wstring()) +
                   L" --parent-pid " + std::to_wstring(GetCurrentProcessId()) +
                   L" --log-file " + QuoteWindowsArgument((std::filesystem::path(state.directory) / L"cs2_gc_rewards.log").wstring());
#ifdef CS2_GC_DEBUG_TOOLS
        command += L" --debug-console";
#endif
        STARTUPINFOW startup{};
        startup.cb = sizeof(startup);
        startup.dwFlags = STARTF_USESHOWWINDOW;
        startup.wShowWindow = SW_HIDE;
        PROCESS_INFORMATION child{};
        if (!CreateProcessW(found, command.data(), nullptr, nullptr, FALSE, CREATE_NO_WINDOW,
                            nullptr, state.directory.c_str(), &startup, &child))
            continue;
        CloseHandle(child.hThread);
        state.rewardsProcess = child.hProcess;
        state.log->Write("rewards: background helper launched; exits with CS2. Diagnostics: cs2_gc_rewards.log");
        return;
    }
    state.autoRewards = false;
    state.log->Write("rewards: Python 3 not found; install Python 3 with its launcher or PATH option, then restart CS2");
}

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
        return state.serverCoordinator && state.realServerPipe && pipe == state.realServerPipe()
                   ? state.serverCoordinator : state.coordinator;

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
            s.realFindServer = reinterpret_cast<State::FindFn>(GetProcAddress(real, "SteamInternal_FindOrCreateGameServerInterface"));
            s.realCreate = reinterpret_cast<State::CreateFn>(GetProcAddress(real, "SteamInternal_CreateInterface"));
            s.realRegister = reinterpret_cast<decltype(s.realRegister)>(GetProcAddress(real, "SteamAPI_RegisterCallback"));
            s.realUnregister = reinterpret_cast<decltype(s.realUnregister)>(GetProcAddress(real, "SteamAPI_UnregisterCallback"));
            s.realRunCallbacks = reinterpret_cast<decltype(s.realRunCallbacks)>(GetProcAddress(real, "SteamAPI_RunCallbacks"));
            s.realServerRunCallbacks = reinterpret_cast<decltype(s.realServerRunCallbacks)>(GetProcAddress(real, "SteamGameServer_RunCallbacks"));
            s.realServerPipe = reinterpret_cast<decltype(s.realServerPipe)>(GetProcAddress(real, "SteamGameServer_GetHSteamPipe"));
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
        endpoint.diagnostic = [log = s.log](std::string_view message) { log->Write(std::string{message}); };
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
            s.serverCoordinator = new ProxyCoordinator(endpoint, *s.log, provider);
            s.coordinator = new ProxyCoordinator(endpoint, *s.log, std::move(provider));
            auto replay = std::make_shared<ReplayStore>(
                ReplayStore::LoadDirectory(std::filesystem::path(s.directory + L"cs2_gc_replay")));
            if (replay->Size())
            {
                s.coordinator->EnableReplay(replay);
                s.coordinator->SetDropRecordedItems(proxy.hideRealItems);
                if (proxy.armoryCredits)
                {
                    s.coordinator->SetArmoryCredits(proxy.armoryCredits);
                    s.log->Write("armory: the credits balance is set to " + std::to_string(*proxy.armoryCredits) +
                                 " in the welcome (armory_credits)");
                }
                s.log->Write(proxy.hideRealItems ? "inventory: fresh. The items in the recording are removed; only "
                                                   "cs2_gc_inventory.txt items appear (real_items = keep to change)"
                                                 : "inventory: the recorded items are kept (real_items = keep)");
                s.log->Write("replay: " + std::to_string(replay->Size()) + " recorded message bodies loaded from "
                             "cs2_gc_replay; they belong to the account they were captured from");
            }
            else
                s.log->Write("replay: no recordings in cs2_gc_replay, using the synthetic welcome");
            s.coordinator->EnableNativeStore(std::filesystem::path(s.directory + L"cs2_gc_store_2501.bin"), *replay);

            // One live inventory serves the welcome, equipping and the Armory. It starts from
            // cs2_gc_inventory.txt (same text format the core saves in, so it can be edited by hand).
            const std::filesystem::path inventoryPath(s.directory + L"cs2_gc_inventory.txt");
            std::optional<Inventory> loaded = std::filesystem::exists(inventoryPath) ? Inventory::Load(inventoryPath)
                                                                                     : std::optional<Inventory>(Inventory{});
            const bool inventoryFileUsable = loaded.has_value();
            if (!loaded)
            {
                // Never saved over later: it may be a hand-edited file with a mistake in it.
                s.log->Write("custom inventory: cs2_gc_inventory.txt is invalid, starting empty and not saving over it");
                loaded = Inventory{};
            }
            std::ifstream gameplayFile(std::filesystem::path(s.directory + L"cs2_gc_gameplay.cfg"));
            if (gameplayFile)
            {
                std::ostringstream contents; contents << gameplayFile.rdbuf();
                if (const auto gameplay = ParseGameplayConfig(contents.str()))
                {
                    loaded->SetGameplay(*gameplay);
                    s.log->Write("gameplay: cs2_gc_gameplay.cfg loaded (restart game/helper after edits)");
                }
                else
                    s.log->Write("ERROR: cs2_gc_gameplay.cfg invalid; using documented default gameplay settings");
            }
            else s.log->Write("gameplay: no cs2_gc_gameplay.cfg; using documented defaults");
            s.autoRewards = loaded->Gameplay().rewards_auto_start != 0;
            {
                const auto &gameplay = loaded->Gameplay();
                Logger *rangeLog = s.log;
                StartViewmodelRange({gameplay.viewmodel_range_percent, gameplay.viewmodel_fov_min, gameplay.viewmodel_fov_max},
                                    [rangeLog](const std::string &message) { rangeLog->Write(message); });
            }
            if (loaded->Gameplay().premier_enabled)
                s.coordinator->EnableLocalPremier({loaded->Gameplay().premier_start_rating, 0,
                                                   loaded->Gameplay().premier_placement_wins});
            auto live = std::make_shared<LiveInventory>(std::move(*loaded));
            s.serverCoordinator->EnableServerInventory(live);
            Logger *saveLog = s.log;
            s.coordinator->EnableProgression(std::filesystem::path(s.directory + L"cs2_gc_rewards.txt"),
                [live, inventoryPath, inventoryFileUsable, saveLog] {
                    if (inventoryFileUsable && !live->Save(inventoryPath))
                        saveLog->Write("could not save cs2_gc_inventory.txt");
                });
            s.coordinator->EnableLiveInventory(live, [live, inventoryPath, inventoryFileUsable, saveLog] {
                if (inventoryFileUsable && !live->Save(inventoryPath))
                    saveLog->Write("could not save cs2_gc_inventory.txt");
            });
            s.coordinator->EnableStorePurchaseFailure();

            if (replay->Size())
            {
                // Read at each Hello, so items granted during the session are in a reconnect's welcome.
                s.coordinator->SetItemProvider([live](std::uint64_t steamId) {
                    std::vector<std::vector<std::uint8_t>> encoded;
                    std::uint32_t position = ItemPositionBase;
                    for (const InventoryItem &item : live->Items().Items())
                        encoded.push_back(BuildEconItem(item, static_cast<std::uint32_t>(steamId & 0xFFFFFFFFull),
                                                        CustomItemIdBase + item.id, position++));
                    return encoded;
                });
                s.log->Write("custom inventory: " + std::to_string(live->Items().Items().size()) +
                             " item(s) from cs2_gc_inventory.txt will be added to the welcome");
            }
            else if (!live->Items().Items().empty())
                s.log->Write("custom inventory: needs a recorded welcome (cs2_gc_replay) to add items to; "
                             "no custom items added");

            // The Armory is built from the game's own schema, so it needs items_game.txt next to the DLL.
            const std::filesystem::path schemaPath(s.directory + L"items_game.txt");
            if (!std::filesystem::exists(schemaPath))
                s.log->Write("armory: items_game.txt not found next to steam_api64.dll; Armory purchases stay "
                             "unanswered (extract it from the game, see README)");
            else
            {
                std::ifstream schemaFile(schemaPath, std::ios::binary);
                std::ostringstream schemaText;
                schemaText << schemaFile.rdbuf();
                std::string schemaSource = schemaText.str();
                // The bridge prepares a reversible native catalogue for the next
                // launch. Validate both files against its stamp before accepting
                // it, so native shop indexes and local redeem identities agree.
                const auto nativeDir = schemaPath.parent_path().parent_path().parent_path() / L"cs2_gc_native";
                std::ifstream stampFile(nativeDir / L"cs2_gc_schema_stamp.txt");
                std::string marker; std::uint64_t originalCrc = 0, outputCrc = 0;
                if (stampFile >> marker >> originalCrc >> outputCrc && marker == "CS2_GC_NATIVE_V1" &&
                    originalCrc == Crc32(schemaSource))
                {
                    std::ifstream nativeFile(nativeDir / L"scripts/items/items_game.txt", std::ios::binary);
                    const std::string nativeSource((std::istreambuf_iterator<char>(nativeFile)), {});
                    std::ifstream gameinfo(nativeDir.parent_path() / L"csgo/gameinfo.gi");
                    const std::string mounts((std::istreambuf_iterator<char>(gameinfo)), {});
                    if (!nativeSource.empty() && outputCrc == Crc32(nativeSource) &&
                        mounts.find("Game\tcs2_gc_native // cs2_gc native tradeups") != std::string::npos)
                    {
                        schemaSource = nativeSource;
                        s.log->Write("armory: validated mounted native catalogue loaded");
                    }
                }
                auto parsed = Schema::Load(schemaSource);
                if (!parsed)
                    s.log->Write("armory: items_game.txt could not be read; Armory purchases stay unanswered");
                else
                {
                    Schema *schema = new Schema(std::move(*parsed)); // lives as long as the process
                    std::ifstream goldFile(std::filesystem::path(s.directory + L"gold_pools.txt"), std::ios::binary);
                    const std::string goldText((std::istreambuf_iterator<char>(goldFile)), {});
                    s.log->Write(schema->LoadGoldPools(goldText) ? "gold trade-ups: validated gold_pools.txt loaded"
                                                               : "gold trade-ups: gold_pools.txt missing or incompatible with items_game.txt");
                    {
                        std::ifstream familyFile(std::filesystem::path(s.directory + L"cs2_gc_skin_families.txt"), std::ios::binary);
                        const std::string familyText((std::istreambuf_iterator<char>(familyFile)), {});
                        if (!familyText.empty())
                            s.log->Write(schema->LoadSkinFamilies(familyText) ? "custom collections: colour families loaded"
                                                                              : "custom collections: cs2_gc_skin_families.txt invalid; families off");
                    }
                    if (const std::size_t repaired = live->RepairCollectionStatTrak(*schema))
                    {
                        s.log->Write("inventory: cleared invalid StatTrak flags on " + std::to_string(repaired) +
                                     " glove(s) or collection skin(s) from earlier rolls");
                        if (inventoryFileUsable && !live->Save(inventoryPath))
                            s.log->Write("could not save cs2_gc_inventory.txt");
                    }
                    if (const auto keys = live->EnsureCaseKeys(*schema); !keys.empty())
                    {
                        s.log->Write("inventory: added " + std::to_string(keys.size()) +
                                     " free case key(s) (free_case_keys = 1; keys are never used up)");
                        if (inventoryFileUsable && !live->Save(inventoryPath)) s.log->Write("could not save cs2_gc_inventory.txt");
                    }
                    // Store purchases are free and local: any item the schema defines can be bought, so the
                    // Store's own price sheet decides what is offered. The game checks the Armory pass etc. itself.
                    if (const std::size_t repaired = live->RepairStoreCoupons(*schema))
                    {
                        s.log->Write("inventory: replaced " + std::to_string(repaired) + " guaranteed Store envelopes with their items");
                        if (inventoryFileUsable && !live->Save(inventoryPath)) s.log->Write("could not save cs2_gc_inventory.txt");
                    }
                    if (const std::size_t repaired = live->RepairSlabs(*schema))
                    {
                        s.log->Write("inventory: removed stickers or charms from " + std::to_string(repaired) +
                                     " Sticker Slab item(s), written there by an earlier build");
                        if (inventoryFileUsable && !live->Save(inventoryPath))
                            s.log->Write("could not save cs2_gc_inventory.txt");
                    }
                    s.coordinator->EnableStorePurchases(
                        live, [schema](std::uint32_t defIndex) {
                            if (!schema->HasItem(defIndex)) return false;
                            const auto *crate = schema->FindCrate(defIndex);
                            if (crate && crate->kind == CrateKind::Case) return false;
                            for (const auto contents : schema->CouponContents(defIndex))
                                if (const auto *nested = schema->FindCrate(contents); nested && nested->kind == CrateKind::Case)
                                    return false;
                            return true;
                        },
                        [live, inventoryPath, inventoryFileUsable, saveLog] {
                            if (inventoryFileUsable && !live->Save(inventoryPath))
                                saveLog->Write("could not save cs2_gc_inventory.txt");
                        });
                    std::random_device containerDevice;
                    auto containerEngine = std::make_shared<std::mt19937_64>((std::uint64_t{containerDevice()} << 32) |
                                                                              containerDevice());
                    s.coordinator->EnableContainers(
                        live, std::shared_ptr<const Schema>(schema, [](const Schema *) {}),
                        [containerEngine] { return (*containerEngine)(); },
                        [live, inventoryPath, inventoryFileUsable, saveLog] {
                            if (inventoryFileUsable && !live->Save(inventoryPath))
                                saveLog->Write("could not save cs2_gc_inventory.txt");
                        });
                    s.log->Write("containers: cases (with their key), sticker capsules and graffiti boxes open "
                                 "locally; naming items works. Music kit boxes and souvenir packages are not handled");
                    s.log->Write("store: purchases are granted locally and free (needs the Store price sheet to list "
                                 "the item); saved to cs2_gc_inventory.txt");
                    std::uint32_t campaign = 0;
                    for (const ArmoryRedeemable &goods : schema->ArmoryRedeemables())
                        campaign = (std::max)(campaign, goods.campaignId);
                    if (!campaign)
                        s.log->Write("armory: items_game.txt lists no Armory goods; purchases stay unanswered");
                    else
                    {
                        const auto credits = live->Items().ArmoryCredits().value_or(proxy.armoryCredits.value_or(0));
                        auto armory = std::make_shared<Armory>(*schema, campaign, credits);
                        live->SetArmoryCredits(credits);
                        s.coordinator->SetArmoryCredits(credits);
                        if (inventoryFileUsable && !live->Save(inventoryPath))
                            s.log->Write("could not save cs2_gc_inventory.txt");
                        std::random_device device;
                        auto engine = std::make_shared<std::mt19937_64>((std::uint64_t{device()} << 32) | device());
                        Logger *log = s.log;
                        s.coordinator->EnableArmory(armory, live, [engine] { return (*engine)(); },
                                                    [live, inventoryPath, inventoryFileUsable, log] {
                                                        if (inventoryFileUsable && !live->Save(inventoryPath))
                                                            log->Write("could not save cs2_gc_inventory.txt");
                                                    });
                        s.log->Write("armory: " + std::to_string(schema->ArmoryRedeemables().size()) + " goods loaded "
                                     "from items_game.txt (campaign " + std::to_string(campaign) + "), " +
                                     std::to_string(armory->Balance()) + " credits (saved balance; config seeds a new inventory). Purchases are "
                                     "granted locally and saved to cs2_gc_inventory.txt");
                    }
                }
            }
            s.log->Write("cs2_gc diagnostic proxy active (-insecure), mode=local. Targets Steam build " +
                         std::string(TargetSteamBuildId) + "; the GC is local and nothing is sent to Valve.");
        }
        else
            s.log->Write("cs2_gc diagnostic proxy active (-insecure), mode=capture. Valve's real GC is used "
                         "unchanged; traffic is only recorded. Targets Steam build " +
                         std::string(TargetSteamBuildId) + ".");
        s.log->Write("test build: claude-20261022-33");
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
constexpr int MicroTxnAuthorizationId = 152; // k_iSteamUserCallbacks + 52
constexpr std::uint32_t CounterStrikeAppId = 730;
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
    return id == GcMessageAvailableId || id == GcMessageFailedId || id == MicroTxnAuthorizationId;
}

// MicroTxnAuthorizationResponse_t as the game reads it (8-byte packing on 64-bit Windows).
struct MicroTxnAuthorizationResponse
{
    std::uint32_t appId;
    std::uint64_t orderId;
    std::uint8_t authorized;
};
static_assert(sizeof(MicroTxnAuthorizationResponse) == 24);

void DeliverMicroTxnAuthorization(State &state, std::uint64_t orderId)
{
    std::vector<CallbackObject *> targets;
    {
        std::lock_guard lock(g_callbackMutex);
        for (const RegisteredCallback &entry : g_callbacks)
            if (entry.id == MicroTxnAuthorizationId)
                targets.push_back(entry.object);
    }
    if (targets.empty())
        state.log->Write("purchase: the game has not registered for MicroTxnAuthorizationResponse_t; "
                         "the authorisation was not delivered");
    for (CallbackObject *object : targets)
    {
        const auto sizeFn = reinterpret_cast<int(__cdecl *)(void *)>(object->vtable[SizeSlot]);
        if (sizeFn(object) != static_cast<int>(sizeof(MicroTxnAuthorizationResponse)))
        {
            state.log->Write("callback object does not look like MicroTxnAuthorizationResponse_t; not delivering");
            continue;
        }
        MicroTxnAuthorizationResponse response{CounterStrikeAppId, orderId, 1};
        state.log->Write("delivering MicroTxnAuthorizationResponse_t for the purchase");
        reinterpret_cast<void(__cdecl *)(void *, void *)>(object->vtable[RunSlot])(object, &response);
    }
}

void DeliverGcMessageAvailable(State &state, std::uint32_t size, bool server = false)
{
    std::vector<CallbackObject *> targets;
    {
        std::lock_guard lock(g_callbackMutex);
        for (const RegisteredCallback &entry : g_callbacks)
            if (entry.id == GcMessageAvailableId && !!(entry.object->flags & CallbackFlagGameServer) == server)
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
        if (!(object->flags & CallbackFlagGameServer) || id != MicroTxnAuthorizationId)
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
    if (state.active && state.coordinator && state.mode == ProxyMode::Local)
    {
        StartRewardsIfNeeded(state);
        state.coordinator->PollProgression();
    }
    std::uint32_t size = 0;
    if (state.active && state.coordinator && state.coordinator->IsMessageAvailable(&size))
        DeliverGcMessageAvailable(state, size);

    // The authorisation follows the Init reply by a moment, so the game has stored the transaction id
    // its Finalize will use (the CS:GO fork waits 150 ms too).
    static std::optional<std::pair<std::uint64_t, std::chrono::steady_clock::time_point>> due;
    if (state.active && state.coordinator)
    {
        if (!due)
            if (const auto order = state.coordinator->TakePendingAuthorization())
                due = {*order, std::chrono::steady_clock::now() + std::chrono::milliseconds(150)};
        if (due && std::chrono::steady_clock::now() >= due->second)
        {
            const std::uint64_t order = due->first;
            due.reset();
            DeliverMicroTxnAuthorization(state, order);
        }
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

extern "C" __declspec(dllexport) void __cdecl SteamGameServer_RunCallbacks()
{
    State &state = Init();
    if (state.realServerRunCallbacks)
        state.realServerRunCallbacks();
    if (state.active && state.mode == ProxyMode::Local && state.serverCoordinator)
    {
        state.serverCoordinator->RefreshServerInventory();
        std::uint32_t size = 0;
        if (state.serverCoordinator->IsMessageAvailable(&size))
            DeliverGcMessageAvailable(state, size, true);
    }
}

extern "C" __declspec(dllexport) void *__cdecl SteamInternal_FindOrCreateGameServerInterface(int user, const char *version)
{
    State &state = Init();
    if (state.active && state.mode == ProxyMode::Local && version && std::string_view(version) == GcInterfaceName)
        return state.serverCoordinator;
    return state.realFindServer ? state.realFindServer(user, version) : nullptr;
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
