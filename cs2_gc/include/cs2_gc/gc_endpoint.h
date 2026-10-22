#pragma once

#include "cs2_gc/armory.h"
#include "cs2_gc/gc_handshake.h"
#include "cs2_gc/live_inventory.h"
#include "cs2_gc/message_queue.h"
#include "cs2_gc/replay.h"
#include <atomic>
#include <functional>
#include <string_view>
#include <memory>
#include <optional>
#include <mutex>
#include <unordered_map>

namespace cs2_gc
{
// Values the handshake needs but that cannot be derived offline. The caller supplies them;
// nothing here is a verified default for any client.
struct GcEndpointConfig
{
    std::uint32_t welcomeVersion{};
    SoOwner owner;
    std::uint64_t cacheVersion{};
    std::vector<SoObjectType> cacheTypes; // initial subscribed objects, if any
    std::function<void(std::string_view)> diagnostic;
};

// An in-process stand-in for the GC with the same three calls as ISteamGameCoordinator
// (SendMessage / IsMessageAvailable / RetrieveMessage). It is not attached to Steam's
// interface yet. Message types carry the protobuf flag, as the SDK passes them.
class LocalGameCoordinator
{
public:
    // Handlers run inside SendMessage, serialized. They answer through Reply() and must not
    // call SendMessage or SetHandler (the dispatch lock is held).
    using Handler = std::function<void(const FrameView &frame, LocalGameCoordinator &gc)>;

    explicit LocalGameCoordinator(GcEndpointConfig config);

    GCResult SendMessage(std::uint32_t type, const void *data, std::uint32_t size);
    bool IsMessageAvailable(std::uint32_t *size) const { return m_toGame.IsMessageAvailable(size); }
    GCResult RetrieveMessage(std::uint32_t *type, void *destination, std::uint32_t capacity,
                             std::uint32_t *size)
    {
        return m_toGame.RetrieveMessage(type, destination, capacity, size);
    }

    // Queue a protobuf reply for the game. `type` is the plain message ID (no flag).
    bool Reply(std::uint32_t type, std::span<const std::uint8_t> body);
    // A reply in the old struct form (no protobuf): the type without the protobuf bit, the extended header
    // with invalid job ids, then `body`. The trade-up response still uses it.
    bool ReplyStruct(std::uint32_t type, std::span<const std::uint8_t> body);
    // With a header, for replies the game matches to its request (see ReplyHeaderFor).
    bool Reply(std::uint32_t type, std::span<const std::uint8_t> body, std::span<const std::uint8_t> header);
    void SetHandler(std::uint32_t type, Handler handler); // plain ID; replaces any earlier one
    void SetOwner(const SoOwner &owner);                  // used by later welcomes

    // Answers from recorded real-GC bodies. A recorded Welcome replaces the synthetic one and
    // is followed by the other messages the real GC sent unprompted after it; a request that
    // the capture showed being answered gets the recorded reply. Message types with no
    // recording are left exactly as they were. The recorded bodies belong to one account.
    void EnableReplay(std::shared_ptr<const ReplayStore> store);
    // Enable after replay so local Premier overrides the recorded account's rank.
    void EnableLocalPremier(const LocalPremier &rank);
    bool SetLocalPremier(const LocalPremier &rank);
    // Separate bot-server endpoint; never share its queue with the game client's GC.
    void EnableServerInventory(std::shared_ptr<LiveInventory> inventory);
    void RefreshServerInventory();

    // Extra encoded items (CSOEconItem) to add to a replayed Welcome. Called at each Hello with
    // the cache owner's SteamID64. If the recorded Welcome cannot be patched it is sent as
    // recorded and PatchFailures() increases.
    using ItemProvider = std::function<std::vector<std::vector<std::uint8_t>>(std::uint64_t steamId)>;
    void SetItemProvider(ItemProvider provider);
    // Remove the items the recorded Welcome carries, so the inventory starts fresh and holds only
    // what the provider supplies. Other recorded object types are left alone.
    void SetDropRecordedItems(bool drop);
    // Set the Armory credits balance in the replayed Welcome (unset leaves the recording as is).
    void SetArmoryCredits(std::optional<std::uint32_t> credits);

    // Track the loadout: equip requests change the live inventory and the game is told through a
    // shared-object update, and a fresh Welcome carries the current slots in place of the recorded ones.
    // Sticker applications also change the inventory (and are answered by an item update plus the
    // sticker item's removal); `afterChange` runs after each so the caller can save it.
    void EnableLiveInventory(std::shared_ptr<LiveInventory> inventory, std::function<void()> afterChange = {});

    // Opening containers and naming items. A container opened with the right key (capsules need none)
    // is destroyed along with the key, the rolled item is created as found in a crate, and the game is
    // sent the unlock notification it waits for. Naming sets the item's custom name. `afterChange` runs
    // after each so the caller can save.
    void EnableContainers(std::shared_ptr<LiveInventory> inventory, std::shared_ptr<const Schema> schema,
                          RandomSource random, std::function<void()> afterChange);
    // Consume cumulative XP from the local GSI bridge, idempotently, on the game's callback thread.
    bool ApplyEarnedXp(std::uint64_t cumulativeXp, const std::function<void()> &afterChange);
    // Missions rotating with the Armory (native_missions.py / mission_tracker.py). `pool`: repeated {1 index,
    // 2 template blob}; progress is shown as CSOAccountRecurringMission (SO type 16), changes pushed to the client.
    struct MissionProgress { std::uint32_t mission{}, period{}, progress{}; };
    void SetMissions(std::vector<std::uint8_t> pool, std::vector<MissionProgress> progress);
    // The mission of the current Armory rotation (cycle = now / armory_rotation_seconds + Refresh offset). Returns
    // {variant, period} when it changed (the new schema is pushed once the game has asked for missions).
    std::optional<std::pair<std::uint32_t, std::uint32_t>> MissionTick(std::uint64_t unixSeconds);
    // Stars for reached mission steps (the helper's cumulative "stars N" line).
    bool ApplyMissionStars(std::uint64_t cumulativeStars, const std::function<void()> &afterChange);
    // A care-package claim the patched page printed to console.log (build 31): generation + the three choice tokens.
    bool ClaimCareFromConsole(std::uint32_t generation, const std::vector<std::uint64_t> &tokens,
                              const std::function<void()> &afterChange);
    bool ApplyConsoleControl(std::uint64_t cumulativeStars, std::uint32_t rotationOffset,
                             const std::function<void()> &afterChange);
    bool ApplyMatchRewards(std::uint64_t completed, const std::function<void()> &afterChange);
    bool ApplyLevelRewards(const std::function<void()> &afterChange);
    // Local helper fallback when the native terminal checkout sends no purchase request.
    bool AcceptLocalTerminal(std::uint64_t gameId, const std::function<void()> &afterChange);

    // Local UI fallback; the saved front package remains authoritative.
    bool ClaimLocalCarePackage(std::uint32_t generation, std::uint32_t mask,
                               const std::function<void()> &afterChange);

    // Sell items for free. A valid purchase (every line an item `canSell` accepts, a sane quantity)
    // is answered with a transaction id; the proxy then reports the authorisation through the
    // MicroTxnAuthorizationResponse callback (TakePendingAuthorization), the game sends Finalize, and
    // the items are created as new, unacknowledged purchases. Nothing is charged anywhere.
    // `afterGrant` runs after items are added so the caller can save.
    void EnableStorePurchases(std::shared_ptr<LiveInventory> inventory, std::function<bool(std::uint32_t)> canSell,
                              std::function<void()> afterGrant);

    // The transaction whose authorisation callback is due, once; nothing otherwise.
    std::optional<std::uint64_t> TakePendingAuthorization();

    // Answer a store purchase request with a failure instead of leaving it unanswered. Nothing is
    // charged and nothing is granted.
    void EnableStorePurchaseFailure();

    // Answer Armory purchases from the schema: a valid redeem creates the item (shown to the game as a
    // new, unacknowledged one), lowers the credit balance and tells the game about both. The recorded
    // Welcome (if any) provides the Armory pass object that the balance update is built from. The
    // Welcome shows the armory's live balance from then on. Invalid requests are ignored.
    void EnableArmory(std::shared_ptr<Armory> armory, std::shared_ptr<LiveInventory> inventory,
                      RandomSource random, std::function<void()> afterGrant = {});
    std::size_t PatchFailures() const { return m_patchFailures; }

    std::size_t IgnoredMessages() const { return m_ignored; }

private:
    void OnClientHello(const FrameView &frame);
    void ReplyLocalPremier(std::int32_t change = 0); // caller holds m_mutex
    bool CompleteCareClaimLocked(std::shared_ptr<LiveInventory> inventory, std::uint32_t generation,
                                 const std::vector<std::uint64_t> &selected,
                                 const std::function<void()> &afterChange);
    void NotifyCarePackage(); // caller holds m_mutex
    void PublishArmoryCreditsLocked(); // caller holds m_mutex
    std::uint32_t m_sentCareGeneration{};
    std::vector<std::uint8_t> m_sentCareStore;
    std::vector<std::uint8_t> m_missionSchema;
    std::vector<std::vector<std::uint8_t>> m_missionPool;
    std::optional<std::uint64_t> m_missionCycle;
    std::uint32_t m_missionOffset{};
    bool m_missionsRequested{};
    std::optional<std::pair<std::uint32_t, std::uint32_t>> MissionTickLocked(std::uint64_t unixSeconds);
    std::optional<std::vector<MissionProgress>> m_missionProgress;
    std::vector<std::vector<std::uint8_t>> EncodedMissionProgress() const;
    void NotifyRewardDrops(const std::vector<InventoryItem> &drops); // caller holds m_mutex
    void SendMissingCaseKeys(); // free_case_keys: create and send a key for each newly owned case type
    std::optional<std::uint64_t> AcceptTerminalLocked(std::uint64_t gameId);

    GcEndpointConfig m_config;
    std::shared_ptr<const ReplayStore> m_replay;
    MessageQueue m_toGame;
    std::mutex m_mutex;
    std::unordered_map<std::uint32_t, Handler> m_handlers;
    std::atomic<std::size_t> m_ignored{0};
    std::atomic<std::size_t> m_patchFailures{0};
    ItemProvider m_itemProvider;
    bool m_dropRecordedItems{};
    std::optional<std::uint32_t> m_armoryCredits;
    std::optional<LocalPremier> m_premier;
    std::shared_ptr<LiveInventory> m_live;
    std::shared_ptr<Armory> m_armory;
    bool m_serverReady{};
    std::vector<std::vector<std::uint8_t>> m_serverItems;
    std::vector<std::vector<std::uint8_t>> m_serverSlots;
    std::uint64_t m_soVersion{1};

    struct Transaction
    {
        std::uint64_t id{};
        std::vector<StorePurchaseRequest::Line> lines;
    };
    std::mutex m_txnMutex;
    RandomSource m_rewardRandom;
    std::shared_ptr<const Schema> m_schema; // set by EnableContainers; the sticker handler uses it for slabs
    std::vector<std::uint8_t> m_xpShop; // the current Armory pass object (credits and activated passes)
    std::optional<Transaction> m_txn;
    std::optional<std::uint64_t> m_pendingAuthorization;
    std::uint64_t m_lastTxnId{7000000000ull};
};

// The header for a reply to `request`: the job id the request carried, echoed back as the target so
// the game can match the reply to it. Empty when the request has no job id.
std::vector<std::uint8_t> ReplyHeaderFor(const FrameView &request);

// Care-package claim (k_EMsgGCCStrike15_v2_ClientRedeemFreeReward): the unused offer slot an id names,
// either the local choice token from the PersonalStore or the faux id Panorama resolved for the tile.
std::optional<std::size_t> CareChoiceSlot(const CarePackage &package, std::uint64_t id, const std::vector<bool> &used);
struct CareConsoleClaim { std::uint32_t generation{}; std::vector<std::uint64_t> tokens; };
// Claims in newly appended console.log text: "cs2_gc care: claim generation=<n> balance=<n> tokens=<a>,<b>,<c> ...".
std::vector<CareConsoleClaim> ParseCareConsoleClaims(std::string_view text);
}
