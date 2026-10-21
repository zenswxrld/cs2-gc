#include "cs2_gc/gc_endpoint.h"
#include "cs2_gc/econ_item.h"
#include "cs2_gc/item_sales.h"
#include "cs2_gc/gc_msg_ids.h"
#include "cs2_gc/protobuf.h"
#include <utility>
#include <ctime>
#include <set>
#include <bit>

namespace cs2_gc
{
namespace
{
// CMsgGCItemCustomizationNotification: item_id (1), request (2). The game waits for it to finish
// an unlock, sticker or naming screen. The request values are the client's own
// k_EGCItemCustomizationNotification_* enum, read from its descriptors.
// Local choice descriptors, not econ item IDs. Slot keeps duplicate rewards independently selectable.
// Panorama resolves def/paint through the native GetFauxItemIDFromDefAndPaintIndex API.
constexpr std::uint64_t CareChoiceBase = 3000000000000ull;
std::uint64_t CareChoiceToken(const InventoryItem &item, std::size_t slot)
{
    return CareChoiceBase + (static_cast<std::uint64_t>(slot) << 32) +
        (static_cast<std::uint64_t>(item.paintKitIndex) << 16) + item.defIndex;
}
std::vector<std::uint8_t> EncodeCareStore(const Inventory &inventory)
{
    PbWriter out;
    const auto &queue = inventory.CarePackages();
    if (queue.empty()) { out.Varint(1,0); out.Varint(2,0); }
    else {
        out.Varint(1,queue.front().generation); out.Varint(2,3);
        for (std::size_t slot=0;slot<queue.front().offers.size();++slot)
            out.Varint(3,CareChoiceToken(queue.front().offers[slot],slot));
    }
    return out.bytes();
}
constexpr std::uint32_t NotificationNameItem = 1006;
constexpr std::uint32_t NotificationUnlockCrate = 1007;
constexpr std::uint32_t NotificationApplySticker = 1086;
constexpr std::uint32_t NotificationApplyKeychain = 1091;
constexpr std::uint32_t NotificationRemoveSticker = 1053;
constexpr std::uint32_t NotificationRemoveKeychain = 1092;
constexpr std::uint32_t NotificationEncapsulateSticker = 1055;
constexpr std::uint32_t NotificationCasketTooFull = 1011;
constexpr std::uint32_t NotificationCasketContents = 1012;
constexpr std::uint32_t NotificationCasketAdded = 1013;
constexpr std::uint32_t NotificationCasketRemoved = 1014;
constexpr std::uint32_t NotificationXpShopUseTicket = 9221;

std::vector<std::uint8_t> EncodeCustomizationNotification(std::uint32_t request, std::uint64_t itemId)
{
    PbWriter out;
    out.Varint(1, itemId);
    out.Varint(2, request);
    return out.bytes();
}

// Observed in a capture of the real GC for build 25947352: sent by the GC right after the
// Welcome without being asked.
constexpr std::uint32_t PostWelcome[] = {
    gc_msg::ECsgoGCMsg::k_EMsgGCCStrike15_v2_GC2ClientGlobalStats,
    gc_msg::ECsgoGCMsg::k_EMsgGCCStrike15_v2_ClientGCRankUpdate,
};

struct ReplayRule
{
    std::uint32_t request;
    std::uint32_t reply;
};

// Request/reply pairs from the same capture. The rank update is included because the game
// repeats its request every ten seconds until it gets an answer.
constexpr ReplayRule ReplayRules[] = {
    {gc_msg::ECsgoGCMsg::k_EMsgGCCStrike15_v2_RequestRecurringMissionSchedule,
     gc_msg::ECsgoGCMsg::k_EMsgGCCStrike15_v2_RecurringMissionSchema},
    {gc_msg::EGCItemMsg::k_EMsgGCStoreGetUserData, gc_msg::EGCItemMsg::k_EMsgGCStoreGetUserDataResponse},
    {gc_msg::ECsgoGCMsg::k_EMsgGCCStrike15_v2_GetEventFavorites_Request,
     gc_msg::ECsgoGCMsg::k_EMsgGCCStrike15_v2_GetEventFavorites_Response},
    {gc_msg::ECsgoGCMsg::k_EMsgGCCStrike15_v2_ClientGCRankUpdate,
     gc_msg::ECsgoGCMsg::k_EMsgGCCStrike15_v2_ClientGCRankUpdate},
};
}

void LocalGameCoordinator::EnableReplay(std::shared_ptr<const ReplayStore> store)
{
    {
        std::lock_guard lock(m_mutex);
        m_replay = store;
    }
    if (!store)
        return;
    if (const auto *recorded = store->Find(gc_msg::EGCBaseClientMsg::k_EMsgGCClientWelcome))
        if (const auto welcome = DecodeClientWelcome(*recorded); welcome && !welcome->outOfDateCaches.empty())
            m_soVersion = welcome->outOfDateCaches[0].version;
    for (const ReplayRule &rule : ReplayRules)
    {
        if (!store->Find(rule.reply))
            continue;
        SetHandler(rule.request, [store, reply = rule.reply](const FrameView &, LocalGameCoordinator &gc) {
            gc.Reply(reply, *store->Find(reply));
        });
    }
}

void LocalGameCoordinator::ReplyLocalPremier(std::int32_t change)
{
    if (!m_premier || !m_config.owner.id) return;
    const auto id = gc_msg::ECsgoGCMsg::k_EMsgGCCStrike15_v2_ClientGCRankUpdate;
    std::span<const std::uint8_t> recorded;
    if (m_replay)
        if (const auto *body = m_replay->Find(id)) recorded = *body;
    auto body = WithPremierRankUpdate(recorded, *m_premier, static_cast<std::uint32_t>(m_config.owner.id), change);
    if (!body) body = WithPremierRankUpdate({}, *m_premier, static_cast<std::uint32_t>(m_config.owner.id), change);
    Reply(id, *body);
}

void LocalGameCoordinator::EnableLocalPremier(const LocalPremier &rank)
{
    {
        std::lock_guard lock(m_mutex);
        m_premier = rank;
    }
    SetHandler(gc_msg::ECsgoGCMsg::k_EMsgGCCStrike15_v2_ClientGCRankUpdate,
               [](const FrameView &, LocalGameCoordinator &gc) { gc.ReplyLocalPremier(); });
}

bool LocalGameCoordinator::SetLocalPremier(const LocalPremier &rank)
{
    std::lock_guard lock(m_mutex);
    if (!m_premier || *m_premier == rank || rank.rating > 99999 || rank.placementWins < 1 || rank.placementWins > 100)
        return false;
    const auto old = m_premier->wins >= m_premier->placementWins ? m_premier->rating : 0;
    const auto next = rank.wins >= rank.placementWins ? rank.rating : 0;
    m_premier = rank;
    ReplyLocalPremier(old && next ? static_cast<std::int32_t>(next) - static_cast<std::int32_t>(old) : 0);
    if (m_config.diagnostic) m_config.diagnostic("Premier: local rating/placement update queued for native rank cache");
    return true;
}

void LocalGameCoordinator::EnableServerInventory(std::shared_ptr<LiveInventory> inventory)
{
    m_live = std::move(inventory);
    SetHandler(gc_msg::EGCBaseClientMsg::k_EMsgGCServerHello, [](const FrameView &, LocalGameCoordinator &gc) {
        PbWriter gameData;
        gameData.Varint(18, 1); // a local gscookieid, not a Valve session cookie
        PbWriter welcome;
        welcome.Varint(1, 0);
        welcome.Bytes(2, gameData.bytes());
        welcome.Varint(7, static_cast<std::uint32_t>(std::time(nullptr)));
        gc.Reply(gc_msg::EGCBaseClientMsg::k_EMsgGCServerWelcome, welcome.bytes());
        gc.m_serverReady = true;
        gc.m_serverItems.clear();
        gc.m_serverSlots.clear();
    });
    SetHandler(gc_msg::ECsgoGCMsg::k_EMsgGCCStrike15_v2_Server2GCClientValidate,
               [](const FrameView &, LocalGameCoordinator &gc) { gc.m_serverItems.clear(); gc.m_serverSlots.clear(); });
}

void LocalGameCoordinator::RefreshServerInventory()
{
    std::lock_guard lock(m_mutex);
    if (!m_serverReady || !m_live || !m_config.owner.id)
        return;
    const auto accountId = static_cast<std::uint32_t>(m_config.owner.id);
    auto items = m_live->EncodedServerItems(accountId);
    auto slots = m_live->EncodedSlots(accountId);
    if (items == m_serverItems && slots == m_serverSlots)
        return;
    m_serverItems = items;
    m_serverSlots = slots;
    PbWriter type;
    type.Varint(1, ItemTypeId);
    for (const auto &item : items)
        type.Bytes(2, item);
    PbWriter owner;
    owner.Varint(1, m_config.owner.type);
    owner.Varint(2, m_config.owner.id);
    PbWriter cache;
    cache.Message(2, type);
    // The game server library registers CSOEconEquipSlot (type 3) beside items, as the client does.
    PbWriter slotType;
    slotType.Varint(1, EquipSlotTypeId);
    for (const auto &slot : slots)
        slotType.Bytes(2, slot);
    if (!slots.empty())
        cache.Message(2, slotType);
    cache.Fixed64(3, ++m_soVersion);
    cache.Message(4, owner);
    Reply(gc_msg::ESOMsg::k_ESOMsg_CacheSubscribed, cache.bytes());
}

bool LocalGameCoordinator::ApplyConsoleControl(std::uint64_t cumulativeStars, std::uint32_t rotationOffset,
                                               const std::function<void()> &afterChange)
{
    std::lock_guard lock(m_mutex);
    if (m_armory) m_armory->SetRotationOffset(rotationOffset);
    if (!m_live || !m_live->ApplyConsoleStars(cumulativeStars)) return false;
    const auto credits = m_live->Items().ArmoryCredits().value_or(0);
    m_armoryCredits = credits;
    if (m_armory) m_armory->SetBalance(credits);
    {
        std::lock_guard passLock(m_txnMutex);
        if (auto pass = WithXpShopBalance(m_xpShop, credits))
        {
            m_xpShop = *pass;
            SoSingleObject updated;
            updated.typeId = static_cast<std::int32_t>(XpShopTypeId);
            updated.data = *pass;
            updated.version = ++m_soVersion;
            updated.owner = m_config.owner;
            Reply(gc_msg::ESOMsg::k_ESOMsg_Update, EncodeSoSingleObject(updated));
        }
    }
    if (afterChange) afterChange();
    return true;
}

bool LocalGameCoordinator::ApplyEarnedXp(std::uint64_t cumulativeXp, const std::function<void()> &afterChange)
{
    std::lock_guard lock(m_mutex);
    if (!m_live || !m_live->ApplyEarnedXp(cumulativeXp))
        return false;
    const auto &inventory = m_live->Items();
    if (m_armory)
        m_armory->SetBalance(inventory.ArmoryCredits().value_or(0));
    {
        std::lock_guard passLock(m_txnMutex);
        if (!m_xpShop.empty())
        {
            auto pass = WithXpShopBalance(m_xpShop, inventory.ArmoryCredits().value_or(0));
            if (pass)
                pass = WithXpShopTracks(*pass, inventory.DisplayXpTracks());
            if (pass)
            {
                m_xpShop = *pass;
                SoSingleObject updated;
                updated.typeId = static_cast<std::int32_t>(XpShopTypeId);
                updated.data = *pass;
                updated.version = ++m_soVersion;
                updated.owner = m_config.owner;
                Reply(gc_msg::ESOMsg::k_ESOMsg_Update, EncodeSoSingleObject(updated));
            }
        }
    }
    std::vector<std::uint8_t> base;
    if (m_replay)
        if (const auto *welcome = m_replay->Find(gc_msg::EGCBaseClientMsg::k_EMsgGCClientWelcome))
        {
            PbReader reader(*welcome);
            PbField field;
            while (reader.Next(field))
                if (field.number == 6 && field.wire == 2)
                    base.assign(field.bytes.begin(), field.bytes.end());
        }
    if (const auto profile = WithLocalProfile(base, inventory.Progress(), m_premier ? &*m_premier : nullptr,
                                             static_cast<std::uint32_t>(m_config.owner.id)))
        Reply(gc_msg::ECsgoGCMsg::k_EMsgGCCStrike15_v2_MatchmakingGC2ClientHello, *profile);
    if (m_config.diagnostic)
        m_config.diagnostic("progression: earned XP applied; profile, passes and stars saved");
    if (afterChange)
        afterChange();
    return true;
}

void LocalGameCoordinator::EnableArmory(std::shared_ptr<Armory> armory, std::shared_ptr<LiveInventory> inventory,
                                        RandomSource random, std::function<void()> afterGrant)
{
    {
        std::lock_guard lock(m_mutex);
        m_armory = armory;
    }
    if (!armory || !inventory)
        return;

    // The recorded Armory pass object is the starting point; it is kept as live state so a balance
    // change or an activated pass rewrites only its own field and the rest is carried along.
    if (m_replay)
        if (const auto *welcome = m_replay->Find(gc_msg::EGCBaseClientMsg::k_EMsgGCClientWelcome))
        {
            auto objects = ExtractObjects(*welcome, XpShopTypeId);
            if (!objects.empty())
            {
                // The recorded account's own passes are not ours: start from the ones activated here (none at first).
                auto pass = WithXpShopBalance(objects.front(), armory->Balance());
                if (pass)
                    pass = WithXpShopTracks(*pass, inventory->Items().DisplayXpTracks());
                std::lock_guard lock(m_txnMutex);
                m_xpShop = pass.value_or(std::move(objects.front()));
            }
        }

    SetHandler(gc_msg::ECsgoGCMsg::k_EMsgGCCStrike15_v2_ClientRedeemMissionReward,
               [armory, inventory, random, afterGrant](const FrameView &frame, LocalGameCoordinator &gc) {
                   const auto request = DecodeRedeemRequest(frame.body);
                   if (!request)
                   {
                       ++gc.m_ignored;
                       return;
                   }
                   const auto result = armory->Redeem(*request, *inventory, random);
                   if (result.status != Armory::Status::Ok)
                   {
                       ++gc.m_ignored;
                       if (gc.m_config.diagnostic) gc.m_config.diagnostic("armory rejected: redeem=" + std::to_string(request->redeemId) +
                           " cost=" + std::to_string(request->expectedCost) + " balance=" + std::to_string(armory->Balance()) +
                           " status=" + std::to_string(static_cast<int>(result.status)));
                       return;
                   }

                   const auto accountId = static_cast<std::uint32_t>(gc.m_config.owner.id & 0xFFFFFFFFull);
                   SoSingleObject created;
                   created.typeId = static_cast<std::int32_t>(ItemTypeId);
                   created.data = BuildEconItem(result.item, accountId, CustomItemIdBase + result.item.id,
                                                InventoryUnacknowledgedBit | PickupXpShopRedeem);
                   created.version = ++gc.m_soVersion;
                   created.owner = gc.m_config.owner;
                   gc.Reply(gc_msg::ESOMsg::k_ESOMsg_Create, EncodeSoSingleObject(created));
                   gc.SendMissingCaseKeys();

                   std::optional<std::vector<std::uint8_t>> pass;
                   {
                       std::lock_guard lock(gc.m_txnMutex);
                       if (!gc.m_xpShop.empty())
                           if (auto updatedPass = WithXpShopBalance(gc.m_xpShop, armory->Balance()))
                           {
                               gc.m_xpShop = *updatedPass;
                               pass = std::move(updatedPass);
                           }
                   }
                   if (pass)
                   {
                       SoSingleObject updated;
                       updated.typeId = static_cast<std::int32_t>(XpShopTypeId);
                       updated.data = *pass;
                       updated.version = ++gc.m_soVersion;
                       updated.owner = gc.m_config.owner;
                       gc.Reply(gc_msg::ESOMsg::k_ESOMsg_Update, EncodeSoSingleObject(updated));
                   }
                   if (afterGrant)
                       afterGrant();
               });

    // Activating a bought Armory Pass: the Armory page calls UseTool on the ticket, which sends a
    // use-item request. The ticket is consumed and the account gets one more (empty) pass.
    SetHandler(gc_msg::EGCItemMsg::k_EMsgGCUseItemRequest,
               [inventory, afterGrant](const FrameView &frame, LocalGameCoordinator &gc) {
                   const auto itemId = DecodeUseItemRequest(frame.body);
                   const auto definition = itemId ? inventory->DefinitionOf(*itemId) : std::nullopt;
                   std::optional<std::vector<std::uint8_t>> pass;
                   {
                       std::lock_guard lock(gc.m_txnMutex);
                       // A new pass starts at 1 XP: the page draws a pass only when its XP is non-zero.
                       if (definition == DefinitionArmoryPass && !gc.m_xpShop.empty() && (*itemId >> 60) != 0xF &&
                           inventory->AddXpTrack(1))
                           pass = WithXpShopTracks(gc.m_xpShop, inventory->Items().DisplayXpTracks());
                       if (pass)
                           gc.m_xpShop = *pass;
                   }
                   if (!pass)
                   {
                       ++gc.m_ignored; // not a pass of ours, or no recorded pass object to extend
                       return;
                   }
                   const auto accountId = static_cast<std::uint32_t>(gc.m_config.owner.id & 0xFFFFFFFFull);
                   const InventoryItem *ticket = inventory->Items().Find(*itemId - CustomItemIdBase);
                   SoSingleObject destroyed;
                   destroyed.typeId = static_cast<std::int32_t>(ItemTypeId);
                   destroyed.data = BuildEconItem(*ticket, accountId, *itemId, ItemPositionBase);
                   inventory->RemoveItem(*itemId);

                   SoSingleObject updated;
                   updated.typeId = static_cast<std::int32_t>(XpShopTypeId);
                   updated.data = *pass;
                   updated.version = ++gc.m_soVersion;
                   updated.owner = gc.m_config.owner;
                   gc.Reply(gc_msg::ESOMsg::k_ESOMsg_Update, EncodeSoSingleObject(updated));
                   destroyed.version = ++gc.m_soVersion;
                   destroyed.owner = gc.m_config.owner;
                   gc.Reply(gc_msg::ESOMsg::k_ESOMsg_Destroy, EncodeSoSingleObject(destroyed));
                   gc.Reply(gc_msg::EGCItemMsg::k_EMsgGCItemCustomizationNotification,
                            EncodeCustomizationNotification(NotificationXpShopUseTicket, *itemId));
                   if (afterGrant)
                       afterGrant();
               });
}

std::optional<std::uint64_t> LocalGameCoordinator::TakePendingAuthorization()
{
    std::lock_guard lock(m_txnMutex);
    return std::exchange(m_pendingAuthorization, std::nullopt);
}

void LocalGameCoordinator::EnableStorePurchases(std::shared_ptr<LiveInventory> inventory,
                                                std::function<bool(std::uint32_t)> canSell,
                                                std::function<void()> afterGrant)
{
    constexpr std::uint32_t ResultOk = 1;
    constexpr std::uint32_t ResultFail = 2;
    constexpr std::uint32_t MaxQuantity = 100;

    SetHandler(gc_msg::EGCItemMsg::k_EMsgGCStorePurchaseInit,
               [canSell](const FrameView &frame, LocalGameCoordinator &gc) {
                   const auto request = DecodeStorePurchaseRequest(frame.body);
                   bool valid = request && !request->lines.empty();
                   std::uint64_t total = 0;
                   if (valid)
                       for (const auto &line : request->lines)
                       {
                           total += line.quantity;
                           valid = valid && line.quantity > 0 && total <= MaxQuantity && canSell(line.defIndex);
                       }
                   PbWriter response;
                   {
                       std::lock_guard lock(gc.m_txnMutex);
                       valid = valid && !gc.m_txn;
                       if (valid)
                       {
                           gc.m_txn = Transaction{++gc.m_lastTxnId, request->lines};
                           gc.m_pendingAuthorization = gc.m_txn->id;
                           response.Varint(1, ResultOk);
                           response.Varint(2, gc.m_txn->id);
                           response.String(3, "https://checkout.steampowered.com/checkout/approvetxn/" +
                                                  std::to_string(gc.m_txn->id) + "/?returnurl=steam");
                       }
                   }
                   if (!valid)
                   {
                       ++gc.m_ignored;
                       response.Varint(1, ResultFail);
                   }
                   gc.Reply(gc_msg::EGCItemMsg::k_EMsgGCStorePurchaseInitResponse, response.bytes(),
                            ReplyHeaderFor(frame));
               });

    SetHandler(gc_msg::EGCItemMsg::k_EMsgGCStorePurchaseCancel, [](const FrameView &frame, LocalGameCoordinator &gc) {
        const auto txn = DecodeTxnId(frame.body);
        {
            std::lock_guard lock(gc.m_txnMutex);
            if (txn && gc.m_txn && gc.m_txn->id == *txn)
            {
                gc.m_txn.reset();
                gc.m_pendingAuthorization.reset();
            }
        }
        PbWriter response;
        response.Varint(1, ResultOk);
        gc.Reply(gc_msg::EGCItemMsg::k_EMsgGCStorePurchaseCancelResponse, response.bytes(), ReplyHeaderFor(frame));
    });

    SetHandler(gc_msg::EGCItemMsg::k_EMsgGCStorePurchaseFinalize,
               [inventory, afterGrant](const FrameView &frame, LocalGameCoordinator &gc) {
                   const auto txnId = DecodeTxnId(frame.body);
                   std::optional<Transaction> txn;
                   {
                       std::lock_guard lock(gc.m_txnMutex);
                       if (txnId && gc.m_txn && gc.m_txn->id == *txnId)
                       {
                           txn = std::move(gc.m_txn);
                           gc.m_txn.reset();
                           gc.m_pendingAuthorization.reset();
                       }
                   }
                   PbWriter response;
                   if (!txn)
                   {
                       ++gc.m_ignored;
                       response.Varint(1, ResultFail);
                       gc.Reply(gc_msg::EGCItemMsg::k_EMsgGCStorePurchaseFinalizeResponse, response.bytes(),
                                ReplyHeaderFor(frame));
                       return;
                   }
                   const auto accountId = static_cast<std::uint32_t>(gc.m_config.owner.id & 0xFFFFFFFFull);
                   std::vector<std::uint64_t> itemIds;
                   std::shared_ptr<const Schema> schema;
                   {
                       std::lock_guard lock(gc.m_txnMutex);
                       schema = gc.m_schema;
                   }
                   // The creates go out before the response so the ids in it already resolve in the cache.
                   std::set<std::uint64_t> terminals;
                   for (const auto &line : txn->lines)
                       if (line.supplementalData &&
                           (!schema || line.quantity != 1 || !terminals.insert(line.supplementalData).second ||
                            inventory->DefinitionOf(line.supplementalData) != line.defIndex ||
                            !inventory->TerminalOffer(*schema, line.supplementalData)))
                       {
                           response.Varint(1, ResultFail);
                           gc.Reply(gc_msg::EGCItemMsg::k_EMsgGCStorePurchaseFinalizeResponse, response.bytes(),
                                    ReplyHeaderFor(frame));
                           return;
                       }
                   for (const auto &line : txn->lines)
                       for (std::uint32_t i = 0; i < line.quantity; ++i)
                       {
                           if (line.supplementalData)
                           {
                               const auto acceptedId = gc.AcceptTerminalLocked(line.supplementalData);
                               itemIds.push_back(*acceptedId);
                               continue;
                           }
                           InventoryItem item;
                           item.defIndex = line.defIndex;
                           // Resolve guaranteed offers and fixed music definitions; never roll a container here.
                           if (schema)
                           {
                               const auto entries = schema->CouponEntries(line.defIndex);
                               const auto name = entries.size() == 1 ? entries.front() : schema->ItemName(line.defIndex);
                               if (const auto loot = schema->ResolveLootItem(name); loot && loot->kind != LootKind::Skin)
                                   item = MakeLootItem(*loot, schema->ItemRarity(loot->weaponDefIndex),
                                       [] { return std::uint64_t{0}; }, schema->ProducesStatTrak(line.defIndex) ? 1000 : 0);
                           }
                           if (schema && schema->ProducesStatTrak(line.defIndex)) item.statTrak = true;
                           item = inventory->AddItem(item);
                           SoSingleObject created;
                           created.typeId = static_cast<std::int32_t>(ItemTypeId);
                           created.data = BuildEconItem(item, accountId, CustomItemIdBase + item.id,
                                                        InventoryUnacknowledgedBit | PickupPurchased);
                           created.version = ++gc.m_soVersion;
                           created.owner = gc.m_config.owner;
                           gc.Reply(gc_msg::ESOMsg::k_ESOMsg_Create, EncodeSoSingleObject(created));
                           itemIds.push_back(CustomItemIdBase + item.id);
                       }
                   gc.SendMissingCaseKeys();
                   response.Varint(1, ResultOk);
                   for (const std::uint64_t id : itemIds)
                       response.Varint(2, id);
                   gc.Reply(gc_msg::EGCItemMsg::k_EMsgGCStorePurchaseFinalizeResponse, response.bytes(),
                            ReplyHeaderFor(frame));
                   if (afterGrant)
                       afterGrant();
               });
}

void LocalGameCoordinator::EnableContainers(std::shared_ptr<LiveInventory> inventory,
                                            std::shared_ptr<const Schema> schema, RandomSource random,
                                            std::function<void()> afterChange)
{
    if (!inventory || !schema)
        return;
    {
        std::lock_guard lock(m_txnMutex);
        m_live = inventory;
        m_schema = schema;
        m_rewardRandom = random;
    }
    SetHandler(gc_msg::ECsgoGCMsg::k_EMsgGCCStrike15_v2_ClientRedeemFreeReward,
        [inventory,afterChange](const FrameView &frame, LocalGameCoordinator &gc) {
            PbReader reader(frame.body); PbField field;
            std::optional<std::uint32_t> generation,balance; std::vector<std::uint64_t> ids; bool valid=true;
            while (reader.Next(field)) {
                if (field.number==1 && field.wire==0 && !generation && field.value<=UINT32_MAX) generation=static_cast<std::uint32_t>(field.value);
                else if (field.number==2 && field.wire==0 && !balance && field.value<=UINT32_MAX) balance=static_cast<std::uint32_t>(field.value);
                else if (field.number==3 && field.wire==0 && ids.size()<4 && field.value>=CareChoiceBase && field.value<CareChoiceBase+(4ull<<32))
                    ids.push_back(field.value);
                else if (field.number==3 && field.wire==2) {
                    // proto2 repeated uint64 normally arrives unpacked; accept packed encoding too.
                    std::uint64_t value=0; unsigned shift=0;
                    for (const auto byte : field.bytes) {
                        if (shift>=64 || (shift==63 && byte>1)) {valid=false;break;}
                        value|=std::uint64_t{byte&127u}<<shift;
                        if (byte&128u) shift+=7;
                        else {
                            if (value<CareChoiceBase || value>=CareChoiceBase+(4ull<<32) || ids.size()>=4) {valid=false;break;}
                            ids.push_back(value); value=0;shift=0;
                        }
                    }
                    if (shift) valid=false;
                }
                else valid=false;
            }
            // This proto field is an optional client snapshot, not authority to grant items.
            // Native clients may omit a zero (remaining) balance. Saved generation + exactly three
            // distinct, matching offers remain authoritative regardless of that hint.
            if (!valid || reader.Failed() || !generation || balance.value_or(0)>3 || inventory->Items().CarePackages().empty()) {
                if(gc.m_config.diagnostic)gc.m_config.diagnostic("care claim rejected: invalid frame/queue; choices="+std::to_string(ids.size())+
                    " balance_hint="+std::to_string(balance.value_or(0)));
                ++gc.m_ignored;return;
            }
            const auto &package=inventory->Items().CarePackages().front();
            std::vector<std::uint64_t> selected;
            for (const auto token:ids) {
                const auto slot=static_cast<std::size_t>((token-CareChoiceBase)>>32);
                if (slot>=package.offers.size() || token!=CareChoiceToken(package.offers[slot],slot)) {
                    if(gc.m_config.diagnostic)gc.m_config.diagnostic("care claim rejected: offer descriptor mismatch");
                    ++gc.m_ignored;return;
                }
                selected.push_back(package.offers[slot].id);
            }
            const auto chosen=inventory->ClaimCarePackage(*generation,selected);
            if (!chosen) {
                if(gc.m_config.diagnostic)gc.m_config.diagnostic("care claim rejected: stale generation or duplicate/partial choices");
                ++gc.m_ignored;return;
            }
            // Preview descriptors never enter the econ cache. Only the three chosen owned items are published.
            if (afterChange) afterChange();
            gc.NotifyCarePackage(); gc.NotifyRewardDrops(*chosen);
            PbWriter notification;
            for(const auto &item:*chosen) notification.Varint(1,CustomItemIdBase+item.id);
            notification.Varint(2,gc_msg::ECsgoGCMsg::k_EMsgGCCStrike15_v2_ClientRedeemFreeReward);
            gc.Reply(gc_msg::EGCItemMsg::k_EMsgGCItemCustomizationNotification,notification.bytes());
            if(gc.m_config.diagnostic)gc.m_config.diagnostic("care package: three chosen rewards granted and saved");
        });
    SetHandler(gc_msg::EGCItemMsg::k_EMsgGCDelete,
               [inventory, schema, afterChange](const FrameView &frame, LocalGameCoordinator &gc) {
                   PbReader reader(frame.body); PbField field;
                   std::uint64_t id = 0; bool valid = true;
                   while (reader.Next(field)) {
                       if (field.number == 1 && field.wire == 0 && !id) id = field.value;
                       else valid = false;
                   }
                   const auto *item = id > CustomItemIdBase && id < 2 * CustomItemIdBase ? inventory->Items().Find(id - CustomItemIdBase) : nullptr;
                   const auto value = item && valid && !reader.Failed() ? ItemSaleValue(*schema, inventory->Items().Gameplay(), *item) : 0;
                   const auto balance = inventory->Items().ArmoryCredits().value_or(0);
                   if (!value || value > UINT32_MAX - balance) { ++gc.m_ignored; return; }
                   SoSingleObject removed;
                   removed.typeId = static_cast<std::int32_t>(ItemTypeId);
                   removed.data = BuildEconItem(*item, static_cast<std::uint32_t>(gc.m_config.owner.id), id, ItemPositionBase);
                   if (!inventory->RemoveItem(id)) { ++gc.m_ignored; return; }
                   inventory->SetArmoryCredits(balance + value);
                   gc.m_armoryCredits = balance + value;
                   if (gc.m_armory) gc.m_armory->SetBalance(balance + value);
                   removed.version = ++gc.m_soVersion; removed.owner = gc.m_config.owner;
                   gc.Reply(gc_msg::ESOMsg::k_ESOMsg_Destroy, EncodeSoSingleObject(removed));
                   {
                       std::lock_guard lock(gc.m_txnMutex);
                       if (auto pass = WithXpShopBalance(gc.m_xpShop, balance + value)) {
                           gc.m_xpShop = *pass;
                           SoSingleObject updated; updated.typeId = static_cast<std::int32_t>(XpShopTypeId);
                           updated.data = *pass; updated.version = ++gc.m_soVersion; updated.owner = gc.m_config.owner;
                           gc.Reply(gc_msg::ESOMsg::k_ESOMsg_Update, EncodeSoSingleObject(updated));
                       }
                   }
                   if (afterChange) afterChange();
                   if (gc.m_config.diagnostic) gc.m_config.diagnostic("item sold: +" + std::to_string(value) + " stars; item and balance saved together");
               });
    SetHandler(gc_msg::EGCItemMsg::k_EMsgGCOpenCrate,
               [inventory, schema, random, afterChange](const FrameView &frame, LocalGameCoordinator &gc) {
                   const auto request = DecodeOpenCrateRequest(frame.body);
                   const auto definition = request ? inventory->DefinitionOf(request->crateItemId) : std::nullopt;
                   const auto *crateInfo = definition ? schema->FindCrate(*definition) : nullptr;
                   if (request && crateInfo && crateInfo->kind == CrateKind::Terminal)
                   {
                       const auto change = inventory->AdvanceTerminal(*schema, *request, random,
                                                                       static_cast<std::uint32_t>(std::time(nullptr)));
                       if (!change)
                       {
                           ++gc.m_ignored;
                           return;
                       }
                       const auto send = [&](std::uint32_t type, const InventoryItem &item) {
                           SoSingleObject object;
                           object.typeId = static_cast<std::int32_t>(ItemTypeId);
                           object.data = BuildEconItem(item, static_cast<std::uint32_t>(gc.m_config.owner.id),
                                                      CustomItemIdBase + item.id, ItemPositionBase);
                           object.version = ++gc.m_soVersion;
                           object.owner = gc.m_config.owner;
                           gc.Reply(type, EncodeSoSingleObject(object));
                       };
                       for (const auto &item : change->removed)
                           send(gc_msg::ESOMsg::k_ESOMsg_Destroy, item);
                       send(change->exhausted ? gc_msg::ESOMsg::k_ESOMsg_Destroy : gc_msg::ESOMsg::k_ESOMsg_Update,
                            change->terminal);
                       if (change->offer)
                           send(gc_msg::ESOMsg::k_ESOMsg_Create, *change->offer);
                       gc.Reply(gc_msg::EGCItemMsg::k_EMsgGCItemCustomizationNotification,
                                EncodeCustomizationNotification(change->unsealed ? NotificationUnlockCrate : NotificationCasketContents,
                                                                request->crateItemId));
                       if (afterChange)
                           afterChange();
                       return;
                   }
                   const auto opened = request ? inventory->Open(*schema, request->crateItemId, request->keyItemId, random)
                                               : std::nullopt;
                   if (!opened)
                   {
                       ++gc.m_ignored; // not ours, wrong or missing key, or nothing the schema can roll
                       return;
                   }
                   const auto accountId = static_cast<std::uint32_t>(gc.m_config.owner.id & 0xFFFFFFFFull);
                   const auto destroy = [&](const InventoryItem &item) {
                       SoSingleObject object;
                       object.typeId = static_cast<std::int32_t>(ItemTypeId);
                       object.data = BuildEconItem(item, accountId, CustomItemIdBase + item.id, ItemPositionBase);
                       object.version = ++gc.m_soVersion;
                       object.owner = gc.m_config.owner;
                       gc.Reply(gc_msg::ESOMsg::k_ESOMsg_Destroy, EncodeSoSingleObject(object));
                   };
                   destroy(opened->crate);
                   if (opened->key)
                       destroy(*opened->key);
                   SoSingleObject created;
                   created.typeId = static_cast<std::int32_t>(ItemTypeId);
                   created.data = BuildEconItem(opened->item, accountId, CustomItemIdBase + opened->item.id,
                                                InventoryUnacknowledgedBit | PickupFoundInCrate);
                   created.version = ++gc.m_soVersion;
                   created.owner = gc.m_config.owner;
                   gc.Reply(gc_msg::ESOMsg::k_ESOMsg_Create, EncodeSoSingleObject(created));
                   gc.Reply(gc_msg::EGCItemMsg::k_EMsgGCItemCustomizationNotification,
                            EncodeCustomizationNotification(NotificationUnlockCrate,
                                                            CustomItemIdBase + opened->item.id));
                   if (afterChange)
                       afterChange();
               });

    // Storage units. The items stay in the cache; one inside a unit just carries the unit's id in two
    // attributes and the game shows it there. Every outcome is a notification naming the unit.
    const auto storage = [inventory, afterChange](bool deposit) {
        return [inventory, afterChange, deposit](const FrameView &frame, LocalGameCoordinator &gc) {
            const auto request = DecodeCasketRequest(frame.body);
            if (!request)
            {
                ++gc.m_ignored;
                return;
            }
            const auto now = static_cast<std::uint32_t>(std::time(nullptr));
            const auto change = deposit ? inventory->StoreItem(request->casketItemId, request->itemId, now)
                                        : inventory->TakeItem(request->casketItemId, request->itemId, now);
            if (change.result == LiveInventory::StorageResult::Invalid)
            {
                ++gc.m_ignored;
                return;
            }
            if (change.result == LiveInventory::StorageResult::Full)
            {
                gc.Reply(gc_msg::EGCItemMsg::k_EMsgGCItemCustomizationNotification,
                         EncodeCustomizationNotification(NotificationCasketTooFull, request->casketItemId));
                return;
            }
            const auto accountId = static_cast<std::uint32_t>(gc.m_config.owner.id & 0xFFFFFFFFull);
            for (const auto &[object, position] : {std::pair{&change.item, change.itemPosition},
                                                   std::pair{&change.casket, change.casketPosition}})
            {
                SoSingleObject updated;
                updated.typeId = static_cast<std::int32_t>(ItemTypeId);
                updated.data = BuildEconItem(*object, accountId, CustomItemIdBase + object->id, position);
                updated.version = ++gc.m_soVersion;
                updated.owner = gc.m_config.owner;
                gc.Reply(gc_msg::ESOMsg::k_ESOMsg_Update, EncodeSoSingleObject(updated));
            }
            gc.Reply(gc_msg::EGCItemMsg::k_EMsgGCItemCustomizationNotification,
                     EncodeCustomizationNotification(deposit ? NotificationCasketAdded : NotificationCasketRemoved,
                                                     request->casketItemId));
            if (afterChange)
                afterChange();
        };
    };
    SetHandler(gc_msg::EGCItemMsg::k_EMsgGCCasketItemAdd, storage(true));
    SetHandler(gc_msg::EGCItemMsg::k_EMsgGCCasketItemExtract, storage(false));
    SetHandler(gc_msg::EGCItemMsg::k_EMsgGCCasketItemLoadContents,
               [inventory, schema](const FrameView &frame, LocalGameCoordinator &gc) {
                   const auto request = DecodeCasketRequest(frame.body);
                   const InventoryItem *casket = request && request->casketItemId > CustomItemIdBase
                                                     ? inventory->Items().Find(request->casketItemId - CustomItemIdBase)
                                                     : nullptr;
                   const auto *crate = casket ? schema->FindCrate(casket->defIndex) : nullptr;
                   if (!casket || (casket->defIndex != DefinitionStorageUnit && (!crate || crate->kind != CrateKind::Terminal)))
                   {
                       ++gc.m_ignored;
                       return;
                   }
                   gc.Reply(gc_msg::EGCItemMsg::k_EMsgGCItemCustomizationNotification,
                            EncodeCustomizationNotification(NotificationCasketContents, request->casketItemId));
               });

    // The native laptop now sends 2536 (CMsgOpenCrate-shaped) when reopening an
    // offer. It must receive the current objects and casket_contents notification,
    // without treating this read as a decline or rolling a new offer.
    SetHandler(gc_msg::EGCItemMsg::k_EMsgGCVolatileItemLoadContents,
               [inventory, schema](const FrameView &frame, LocalGameCoordinator &gc) {
                   const auto request = DecodeOpenCrateRequest(frame.body);
                   const auto offer = request ? inventory->TerminalOffer(*schema, request->crateItemId) : std::nullopt;
                   const auto *terminal = offer ? inventory->Items().Find(request->crateItemId - CustomItemIdBase) : nullptr;
                   if (!terminal || !inventory->Items().Gameplay().terminals_enabled ||
                       (request->pointsRemaining && request->pointsRemaining != terminal->terminalRemaining))
                   {
                       ++gc.m_ignored;
                       return;
                   }
                   const auto account = static_cast<std::uint32_t>(gc.m_config.owner.id);
                   for (const auto &item : {*terminal, *offer})
                   {
                       SoSingleObject object;
                       object.typeId = static_cast<std::int32_t>(ItemTypeId);
                       object.owner = gc.m_config.owner;
                       object.version = ++gc.m_soVersion;
                       object.data = BuildEconItem(item, account, CustomItemIdBase + item.id, ItemPositionBase);
                       gc.Reply(gc_msg::ESOMsg::k_ESOMsg_Update, EncodeSoSingleObject(object));
                   }
                   gc.Reply(gc_msg::EGCItemMsg::k_EMsgGCItemCustomizationNotification,
                            EncodeCustomizationNotification(NotificationCasketContents, request->crateItemId));
                   if (gc.m_config.diagnostic) gc.m_config.diagnostic("terminal: native laptop loaded the saved offer without rerolling");
               });

    // Trade-up contracts. The request is a protobuf (recipe, ten item ids); the response is still the old
    // struct: recipe index (int16), result (uint32), item count (uint16), then the new item's id.
    SetHandler(gc_msg::EGCItemMsg::k_EMsgGCCraft,
               [inventory, schema, random, afterChange](const FrameView &frame, LocalGameCoordinator &gc) {
                   constexpr std::uint32_t ResponseOk = 0;
                   constexpr std::uint32_t ResponseInvalid = 4;
                   const auto request = DecodeCraftRequest(frame.body);
                   if (!request)
                   {
                       ++gc.m_ignored;
                       return;
                   }
                   const auto respond = [&gc, &request](std::uint32_t result, std::uint64_t itemId) {
                       std::vector<std::uint8_t> body;
                       const auto put = [&body](std::uint64_t value, int bytes) {
                           for (int i = 0; i < bytes; ++i)
                               body.push_back(static_cast<std::uint8_t>(value >> (8 * i)));
                       };
                       put(request->recipe, 2);
                       put(result, 4);
                       put(itemId ? 1 : 0, 2);
                       if (itemId)
                           put(itemId, 8);
                       gc.ReplyStruct(gc_msg::EGCItemMsg::k_EMsgGCCraftResponse, body);
                   };
                   const TradeUpResult traded = inventory->TradeUp(*schema, request->itemIds, random);
                   if (gc.m_config.diagnostic)
                       gc.m_config.diagnostic(std::string{"trade-up: "} + TradeUpErrorText(traded.error));
                   if (traded.error != TradeUpError::None)
                   {
                       ++gc.m_ignored;
                       respond(ResponseInvalid, 0);
                       return;
                   }
                   const auto accountId = static_cast<std::uint32_t>(gc.m_config.owner.id & 0xFFFFFFFFull);
                   for (const InventoryItem &input : traded.consumed)
                   {
                       SoSingleObject destroyed;
                       destroyed.typeId = static_cast<std::int32_t>(ItemTypeId);
                       destroyed.data = BuildEconItem(input, accountId, CustomItemIdBase + input.id, ItemPositionBase);
                       destroyed.version = ++gc.m_soVersion;
                       destroyed.owner = gc.m_config.owner;
                       gc.Reply(gc_msg::ESOMsg::k_ESOMsg_Destroy, EncodeSoSingleObject(destroyed));
                   }
                   SoSingleObject created;
                   created.typeId = static_cast<std::int32_t>(ItemTypeId);
                   created.data = BuildEconItem(traded.item, accountId, CustomItemIdBase + traded.item.id,
                                                InventoryUnacknowledgedBit | PickupCrafted);
                   created.version = ++gc.m_soVersion;
                   created.owner = gc.m_config.owner;
                   gc.Reply(gc_msg::ESOMsg::k_ESOMsg_Create, EncodeSoSingleObject(created));
                   respond(ResponseOk, CustomItemIdBase + traded.item.id);
                   if (afterChange)
                       afterChange();
               });

    SetHandler(gc_msg::EGCItemMsg::k_EMsgGCNameItem,
               [inventory, afterChange](const FrameView &frame, LocalGameCoordinator &gc) {
                   const auto request = DecodeNameItemRequest(frame.body);
                   const auto renamed = request ? inventory->Rename(request->itemId, request->name) : std::nullopt;
                   if (!renamed)
                   {
                       ++gc.m_ignored;
                       return;
                   }
                   const auto accountId = static_cast<std::uint32_t>(gc.m_config.owner.id & 0xFFFFFFFFull);
                   SoSingleObject updated;
                   updated.typeId = static_cast<std::int32_t>(ItemTypeId);
                   updated.data = BuildEconItem(renamed->item, accountId, CustomItemIdBase + renamed->item.id,
                                                renamed->position);
                   updated.version = ++gc.m_soVersion;
                   updated.owner = gc.m_config.owner;
                   gc.Reply(gc_msg::ESOMsg::k_ESOMsg_Update, EncodeSoSingleObject(updated));
                   gc.Reply(gc_msg::EGCItemMsg::k_EMsgGCItemCustomizationNotification,
                            EncodeCustomizationNotification(NotificationNameItem,
                                                            CustomItemIdBase + renamed->item.id));
                   if (afterChange)
                       afterChange();
               });
}

void LocalGameCoordinator::EnableStorePurchaseFailure()
{
    SetHandler(gc_msg::EGCItemMsg::k_EMsgGCStorePurchaseInit, [](const FrameView &frame, LocalGameCoordinator &gc) {
        PbWriter response;
        response.Varint(1, 2); // result: EResult Fail
        gc.Reply(gc_msg::EGCItemMsg::k_EMsgGCStorePurchaseInitResponse, response.bytes(), ReplyHeaderFor(frame));
    });
}

void LocalGameCoordinator::EnableLiveInventory(std::shared_ptr<LiveInventory> inventory,
                                               std::function<void()> afterChange)
{
    {
        std::lock_guard lock(m_mutex);
        m_live = inventory;
    }
    if (!inventory)
        return;
    SetHandler(gc_msg::EGCItemMsg::k_EMsgGCAdjustEquipSlotsManual,
               [inventory, afterChange](const FrameView &frame, LocalGameCoordinator &gc) {
                   const auto request = DecodeAdjustEquipSlots(frame.body);
                   if (!request)
                   {
                       ++gc.m_ignored;
                       return;
                   }
                   const auto accountId = static_cast<std::uint32_t>(gc.m_config.owner.id & 0xFFFFFFFFull);
                   const auto changed = inventory->Adjust(*request, accountId);
                   if (!changed || changed->empty())
                   {
                       ++gc.m_ignored; // an item we do not know: leave the loadout as it is
                       return;
                   }
                   SoMultipleObjects update;
                   for (const auto &object : *changed)
                       update.objects.push_back({static_cast<std::int32_t>(EquipSlotTypeId), object});
                   update.version = ++gc.m_soVersion;
                   update.owner = gc.m_config.owner;
                   gc.Reply(gc_msg::ESOMsg::k_ESOMsg_UpdateMultiple, EncodeSoMultipleObjects(update));
                   if (afterChange) afterChange();
               });

    SetHandler(gc_msg::EGCItemMsg::k_EMsgGCApplySticker,
               [inventory, afterChange](const FrameView &frame, LocalGameCoordinator &gc) {
                   const auto request = DecodeApplyStickerRequest(frame.body);
                   std::shared_ptr<const Schema> schema;
                   {
                       std::lock_guard lock(gc.m_txnMutex);
                       schema = gc.m_schema;
                   }
                   // The built-in Remove Keychain Tool takes the charm off a weapon and gives it back as an item.
                   if (request && (request->stickerItemId >> 60) == 0xF &&
                       (request->stickerItemId & 0xFFFFFFFFull) == DefinitionRemoveKeychainTool)
                   {
                       const auto detached = inventory->DetachCharm(request->targetItemId);
                       if (!detached)
                       {
                           ++gc.m_ignored;
                           return;
                       }
                       const auto accountId = static_cast<std::uint32_t>(gc.m_config.owner.id & 0xFFFFFFFFull);
                       SoSingleObject created;
                       created.typeId = static_cast<std::int32_t>(ItemTypeId);
                       created.data = BuildEconItem(detached->charm, accountId, CustomItemIdBase + detached->charm.id,
                                                    InventoryUnacknowledgedBit | PickupPurchased);
                       created.version = ++gc.m_soVersion;
                       created.owner = gc.m_config.owner;
                       gc.Reply(gc_msg::ESOMsg::k_ESOMsg_Create, EncodeSoSingleObject(created));
                       SoSingleObject updated;
                       updated.typeId = static_cast<std::int32_t>(ItemTypeId);
                       updated.data = BuildEconItem(detached->weapon, accountId, CustomItemIdBase + detached->weapon.id,
                                                    detached->position);
                       updated.version = ++gc.m_soVersion;
                       updated.owner = gc.m_config.owner;
                       gc.Reply(gc_msg::ESOMsg::k_ESOMsg_Update, EncodeSoSingleObject(updated));
                       gc.Reply(gc_msg::EGCItemMsg::k_EMsgGCItemCustomizationNotification,
                                EncodeCustomizationNotification(NotificationRemoveKeychain,
                                                                CustomItemIdBase + detached->weapon.id));
                       if (afterChange)
                           afterChange();
                       return;
                   }
                   // No sticker item means a scrape of the one in that slot.
                   if (request && request->stickerItemId == 0)
                   {
                       const auto scraped = inventory->ScrapeSticker(request->targetItemId, request->slot, request->wearTarget);
                       if (!scraped)
                       {
                           ++gc.m_ignored;
                           return;
                       }
                       const auto accountId = static_cast<std::uint32_t>(gc.m_config.owner.id & 0xFFFFFFFFull);
                       SoSingleObject updated;
                       updated.typeId = static_cast<std::int32_t>(ItemTypeId);
                       updated.data = BuildEconItem(scraped->item, accountId, CustomItemIdBase + scraped->item.id,
                                                    scraped->position);
                       updated.version = ++gc.m_soVersion;
                       updated.owner = gc.m_config.owner;
                       gc.Reply(gc_msg::ESOMsg::k_ESOMsg_Update, EncodeSoSingleObject(updated));
                       if (scraped->removed)
                           gc.Reply(gc_msg::EGCItemMsg::k_EMsgGCItemCustomizationNotification,
                                    EncodeCustomizationNotification(NotificationRemoveSticker,
                                                                    CustomItemIdBase + scraped->item.id));
                       if (afterChange)
                           afterChange();
                       return;
                   }
                   // The same message seals a sticker in a Sticker Slab: the target is the slab, not a weapon.
                   if (request && schema)
                       if (const auto sealed = inventory->SealSticker(*schema, request->stickerItemId, request->targetItemId))
                       {
                           const auto accountId = static_cast<std::uint32_t>(gc.m_config.owner.id & 0xFFFFFFFFull);
                           const auto destroy = [&](const InventoryItem &item) {
                               SoSingleObject object;
                               object.typeId = static_cast<std::int32_t>(ItemTypeId);
                               object.data = BuildEconItem(item, accountId, CustomItemIdBase + item.id, ItemPositionBase);
                               object.version = ++gc.m_soVersion;
                               object.owner = gc.m_config.owner;
                               gc.Reply(gc_msg::ESOMsg::k_ESOMsg_Destroy, EncodeSoSingleObject(object));
                           };
                           destroy(sealed->sticker);
                           destroy(sealed->slab);
                           SoSingleObject created;
                           created.typeId = static_cast<std::int32_t>(ItemTypeId);
                           created.data = BuildEconItem(sealed->charm, accountId, CustomItemIdBase + sealed->charm.id,
                                                        InventoryUnacknowledgedBit | PickupPurchased);
                           created.version = ++gc.m_soVersion;
                           created.owner = gc.m_config.owner;
                           gc.Reply(gc_msg::ESOMsg::k_ESOMsg_Create, EncodeSoSingleObject(created));
                           gc.Reply(gc_msg::EGCItemMsg::k_EMsgGCItemCustomizationNotification,
                                    EncodeCustomizationNotification(NotificationEncapsulateSticker,
                                                                    CustomItemIdBase + sealed->charm.id));
                           if (afterChange)
                               afterChange();
                           return;
                       }
                   // A built-in weapon the schema does not define cannot become an item.
                   if (request && request->baseItemDefIndex && schema && !schema->HasItem(request->baseItemDefIndex))
                   {
                       ++gc.m_ignored;
                       return;
                   }
                   // A slab is never a weapon: if sealing did not take, change nothing.
                   if (request && schema)
                       if (const auto target = inventory->DefinitionOf(request->targetItemId);
                           target && schema->SlabKeychainIndex(*target))
                       {
                           ++gc.m_ignored;
                           return;
                       }
                   const auto applied = request ? inventory->ApplySticker(*request) : std::nullopt;
                   if (!applied)
                   {
                       ++gc.m_ignored; // not ours, not a sticker, or the slot is taken: change nothing
                       return;
                   }
                   const auto accountId = static_cast<std::uint32_t>(gc.m_config.owner.id & 0xFFFFFFFFull);
                   SoSingleObject destroyed;
                   destroyed.typeId = static_cast<std::int32_t>(ItemTypeId);
                   destroyed.data = BuildEconItem(applied->consumed, accountId,
                                                  CustomItemIdBase + applied->consumed.id, applied->position);
                   destroyed.version = ++gc.m_soVersion;
                   destroyed.owner = gc.m_config.owner;
                   gc.Reply(gc_msg::ESOMsg::k_ESOMsg_Destroy, EncodeSoSingleObject(destroyed));

                   SoSingleObject updated;
                   updated.typeId = static_cast<std::int32_t>(ItemTypeId);
                   updated.data = BuildEconItem(applied->item, accountId, CustomItemIdBase + applied->item.id,
                                                applied->position);
                   updated.version = ++gc.m_soVersion;
                   updated.owner = gc.m_config.owner;
                   // A built-in weapon becomes an inventory item here, so the game is told of a new item.
                   gc.Reply(applied->created ? gc_msg::ESOMsg::k_ESOMsg_Create : gc_msg::ESOMsg::k_ESOMsg_Update,
                            EncodeSoSingleObject(updated));

                   gc.Reply(gc_msg::EGCItemMsg::k_EMsgGCItemCustomizationNotification,
                            EncodeCustomizationNotification(applied->charm ? NotificationApplyKeychain
                                                                            : NotificationApplySticker,
                                                            CustomItemIdBase + applied->item.id));
                   if (afterChange)
                       afterChange();
               });
}

void LocalGameCoordinator::SetArmoryCredits(std::optional<std::uint32_t> credits)
{
    std::lock_guard lock(m_mutex);
    m_armoryCredits = credits;
}

void LocalGameCoordinator::SetDropRecordedItems(bool drop)
{
    std::lock_guard lock(m_mutex);
    m_dropRecordedItems = drop;
}

void LocalGameCoordinator::SetItemProvider(ItemProvider provider)
{
    std::lock_guard lock(m_mutex);
    m_itemProvider = std::move(provider);
}

LocalGameCoordinator::LocalGameCoordinator(GcEndpointConfig config)
    : m_config(std::move(config))
{
    SetHandler(gc_msg::EGCBaseClientMsg::k_EMsgGCClientHello,
               [this](const FrameView &frame, LocalGameCoordinator &) { OnClientHello(frame); });
}

void LocalGameCoordinator::SetHandler(std::uint32_t type, Handler handler)
{
    std::lock_guard lock(m_mutex);
    m_handlers[type] = std::move(handler);
}

void LocalGameCoordinator::SetOwner(const SoOwner &owner)
{
    std::lock_guard lock(m_mutex);
    m_config.owner = owner;
}

std::vector<std::uint8_t> ReplyHeaderFor(const FrameView &request)
{
    PbReader reader(request.header);
    PbField f;
    while (reader.Next(f))
        if (f.number == 10 && f.wire == 1) // CMsgProtoBufHeader.job_id_source
        {
            PbWriter header;
            header.Fixed64(11, f.value); // job_id_target
            return header.bytes();
        }
    return {};
}

bool LocalGameCoordinator::Reply(std::uint32_t type, std::span<const std::uint8_t> body,
                                 std::span<const std::uint8_t> header)
{
    Message message{type | ProtobufMask, {}};
    if (WriteProtobufFrame(type, header, body, message.bytes) != FrameError::None)
        return false;
    return m_toGame.Push(std::move(message));
}

bool LocalGameCoordinator::ReplyStruct(std::uint32_t type, std::span<const std::uint8_t> body)
{
    Message message{type, {}};
    const auto put = [&message](std::uint64_t value, int bytes) {
        for (int i = 0; i < bytes; ++i)
            message.bytes.push_back(static_cast<std::uint8_t>(value >> (8 * i)));
    };
    put(type, 4);
    put(0, 4);
    put(0, 8);
    put(1, 2); // header version
    put(~std::uint64_t{0}, 8); // target job: none
    put(~std::uint64_t{0}, 8); // source job: none
    message.bytes.insert(message.bytes.end(), body.begin(), body.end());
    return m_toGame.PushStruct(std::move(message));
}

bool LocalGameCoordinator::Reply(std::uint32_t type, std::span<const std::uint8_t> body)
{
    Message message{type | ProtobufMask, {}};
    if (WriteProtobufFrame(type, {}, body, message.bytes) != FrameError::None)
        return false;
    return m_toGame.Push(std::move(message));
}

GCResult LocalGameCoordinator::SendMessage(std::uint32_t type, const void *data, std::uint32_t size)
{
    if ((!data && size != 0) || size > MaxMessageBytes)
        return GCResult::InvalidMessage;

    FrameView frame;
    const std::span<const std::uint8_t> bytes(static_cast<const std::uint8_t *>(data), size);
    if (ReadProtobufFrame(type, bytes, frame) != FrameError::None)
        return GCResult::InvalidMessage;

    std::lock_guard lock(m_mutex);
    const auto handler = m_handlers.find(frame.type & ~ProtobufMask);
    if (handler == m_handlers.end())
    {
        ++m_ignored; // accepted but unanswered; the game does not learn that from the result
        return GCResult::OK;
    }
    handler->second(frame, *this);
    return GCResult::OK;
}

void LocalGameCoordinator::OnClientHello(const FrameView &frame)
{
    if (!DecodeClientHello(frame.body))
    {
        ++m_ignored; // malformed hello: no welcome rather than a welcome built from garbage
        return;
    }
    if (m_replay)
    {
        if (const auto *welcome = m_replay->Find(gc_msg::EGCBaseClientMsg::k_EMsgGCClientWelcome))
        {
            std::vector<std::uint8_t> patched = *welcome;
            if (m_live)
                if (auto profile = WithWelcomeProfile(patched, m_live->Items().Progress(), m_premier ? &*m_premier : nullptr,
                                                       static_cast<std::uint32_t>(m_config.owner.id)))
                    patched = std::move(*profile);
            if (m_itemProvider || m_dropRecordedItems)
            {
                const auto items = m_itemProvider ? m_itemProvider(m_config.owner.id)
                                                  : std::vector<std::vector<std::uint8_t>>{};
                if (!items.empty() || m_dropRecordedItems)
                {
                    if (auto result = AppendItemsToWelcome(patched, items, m_dropRecordedItems))
                        patched = std::move(*result);
                    else
                        ++m_patchFailures;
                }
            }
            if (m_dropRecordedItems || m_live)
            {
                // The recorded loadout slots point at the recorded items. When those are gone, the
                // slots are replaced with the live ones (none yet if nothing was equipped).
                const auto accountId = static_cast<std::uint32_t>(m_config.owner.id & 0xFFFFFFFFull);
                const auto slots = m_live ? m_live->EncodedSlots(accountId) : std::vector<std::vector<std::uint8_t>>{};
                if (auto result = AppendObjectsToWelcome(patched, EquipSlotTypeId, slots, m_dropRecordedItems))
                    patched = std::move(*result);
                else
                    ++m_patchFailures;
            }
            if (m_live && m_live->Items().Gameplay().care_packages_enabled) {
                const auto &queue=m_live->Items().CarePackages();
                const std::vector<std::vector<std::uint8_t>> store{EncodeCareStore(m_live->Items())};
                if(auto result=AppendObjectsToWelcome(patched,PersonalStoreTypeId,store,true)) patched=std::move(*result);
                m_sentCareStore=store.front();m_sentCareGeneration=queue.empty()?0:queue.front().generation;
            }
            if (m_armory || m_armoryCredits)
            {
                std::vector<std::uint8_t> livePass;
                {
                    std::lock_guard lock(m_txnMutex);
                    livePass = m_xpShop;
                }
                const std::uint32_t credits = m_armory ? m_armory->Balance() : *m_armoryCredits;
                const std::vector<std::vector<std::uint8_t>> passes{livePass};
                // The live pass object (credits and activated passes) replaces the recorded one.
                auto result = livePass.empty() ? SetArmoryBalance(patched, credits)
                                               : AppendObjectsToWelcome(patched, XpShopTypeId, passes, true);
                if (result)
                    patched = std::move(*result);
                else
                    ++m_patchFailures;
            }
            const std::span<const std::uint8_t> body = patched;
            Reply(gc_msg::EGCBaseClientMsg::k_EMsgGCClientWelcome, body);
            for (std::uint32_t id : PostWelcome)
            {
                if (m_premier && id == gc_msg::ECsgoGCMsg::k_EMsgGCCStrike15_v2_ClientGCRankUpdate)
                {
                    ReplyLocalPremier();
                    continue;
                }
                if (const auto *body = m_replay->Find(id))
                    Reply(id, *body);
            }
            return;
        }
    }

    ClientWelcome welcome;
    welcome.version = m_config.welcomeVersion;
    welcome.outOfDateCaches.push_back({m_config.owner, m_config.cacheVersion, m_config.cacheTypes});
    if (m_live && m_live->Items().Gameplay().care_packages_enabled) {
        auto &types=welcome.outOfDateCaches.front().types;
        types.erase(std::remove_if(types.begin(),types.end(),[](const auto &type){return type.typeId==static_cast<std::int32_t>(PersonalStoreTypeId);}),types.end());
        types.push_back({static_cast<std::int32_t>(PersonalStoreTypeId),{EncodeCareStore(m_live->Items())}});
        const auto &queue=m_live->Items().CarePackages();
        m_sentCareStore=EncodeCareStore(m_live->Items());m_sentCareGeneration=queue.empty()?0:queue.front().generation;
    }
    Reply(gc_msg::EGCBaseClientMsg::k_EMsgGCClientWelcome, EncodeClientWelcome(welcome));
    ReplyLocalPremier();
}
}

namespace cs2_gc
{
std::optional<std::uint64_t> LocalGameCoordinator::AcceptTerminalLocked(std::uint64_t gameId)
{
    if (!m_live || !m_schema) return std::nullopt;
    const auto accepted = m_live->AcceptTerminal(*m_schema, gameId);
    if (!accepted) return std::nullopt;
    const auto account = static_cast<std::uint32_t>(m_config.owner.id);
    SoSingleObject object;
    object.typeId = static_cast<std::int32_t>(ItemTypeId);
    object.owner = m_config.owner;
    object.version = ++m_soVersion;
    object.data = BuildEconItem(accepted->terminal, account, gameId, ItemPositionBase);
    Reply(gc_msg::ESOMsg::k_ESOMsg_Destroy, EncodeSoSingleObject(object));
    object.version = ++m_soVersion;
    const auto id = CustomItemIdBase + accepted->offer->id;
    object.data = BuildEconItem(*accepted->offer, account, id, InventoryUnacknowledgedBit | PickupPurchased);
    Reply(gc_msg::ESOMsg::k_ESOMsg_Update, EncodeSoSingleObject(object));
    return id;
}

bool LocalGameCoordinator::AcceptLocalTerminal(std::uint64_t gameId, const std::function<void()> &afterChange)
{
    std::lock_guard lock(m_mutex);
    if (!m_live || !m_live->Items().Gameplay().terminal_helper_enabled || !AcceptTerminalLocked(gameId)) return false;
    if (afterChange) afterChange();
    if (m_config.diagnostic) m_config.diagnostic("terminal: displayed offer accepted through local helper");
    return true;
}

bool LocalGameCoordinator::ApplyMatchRewards(std::uint64_t completed, const std::function<void()> &afterChange)
{
    std::lock_guard lock(m_mutex);
    if (!m_live || !m_schema || !m_rewardRandom) return false;
    const auto drops = m_live->GrantMatchRewards(*m_schema, completed, m_rewardRandom);
    if (!drops) return false;
    if (afterChange) afterChange();
    if (m_live->Items().Gameplay().care_packages_enabled) NotifyCarePackage();
    else NotifyRewardDrops(*drops);
    if (m_config.diagnostic) m_config.diagnostic("match rewards: " + std::to_string(drops->size()) + " direct drops; care-package queue saved");
    return true;
}

bool LocalGameCoordinator::ApplyLevelRewards(const std::function<void()> &afterChange)
{
    std::lock_guard lock(m_mutex);
    if (!m_live || !m_schema || !m_rewardRandom) return false;
    const auto drops = m_live->GrantLevelRewards(*m_schema, m_rewardRandom);
    if (!drops) return false;
    if (afterChange) afterChange();
    if (m_live->Items().Gameplay().care_packages_enabled) NotifyCarePackage();
    else NotifyRewardDrops(*drops);
    if (m_config.diagnostic) m_config.diagnostic("level rewards: " + std::to_string(drops->size()) + " direct drops; care-package queue saved; no weekly cooldown");
    return true;
}

void LocalGameCoordinator::SendMissingCaseKeys()
{
    std::shared_ptr<const Schema> schema;
    {
        std::lock_guard lock(m_txnMutex);
        schema = m_schema;
    }
    if (!m_live || !schema)
        return;
    const auto account = static_cast<std::uint32_t>(m_config.owner.id & 0xFFFFFFFFull);
    for (const auto &key : m_live->EnsureCaseKeys(*schema))
    {
        SoSingleObject object;
        object.typeId = static_cast<std::int32_t>(ItemTypeId);
        object.data = BuildEconItem(key, account, CustomItemIdBase + key.id, ItemPositionBase);
        object.version = ++m_soVersion;
        object.owner = m_config.owner;
        Reply(gc_msg::ESOMsg::k_ESOMsg_Create, EncodeSoSingleObject(object));
    }
}

void LocalGameCoordinator::NotifyCarePackage()
{
    if (!m_live) return;
    const auto &queue=m_live->Items().CarePackages();
    const auto generation=queue.empty()?0:queue.front().generation;
    if (generation==m_sentCareGeneration && !m_sentCareStore.empty()) return;
    if (!m_sentCareStore.empty()) {
        SoSingleObject removed;removed.typeId=static_cast<std::int32_t>(PersonalStoreTypeId);
        removed.owner=m_config.owner;removed.version=++m_soVersion;removed.data=m_sentCareStore;
        Reply(gc_msg::ESOMsg::k_ESOMsg_Destroy,EncodeSoSingleObject(removed));
    }
    m_sentCareStore=EncodeCareStore(m_live->Items());m_sentCareGeneration=generation;
    SoSingleObject store;store.typeId=static_cast<std::int32_t>(PersonalStoreTypeId);store.owner=m_config.owner;
    store.version=++m_soVersion;store.data=m_sentCareStore;
    Reply(gc_msg::ESOMsg::k_ESOMsg_Create,EncodeSoSingleObject(store));
}

void LocalGameCoordinator::NotifyRewardDrops(const std::vector<InventoryItem> &drops)
{
    const auto account = static_cast<std::uint32_t>(m_config.owner.id);
    for (const auto &item : drops)
    {
        const auto id = CustomItemIdBase + item.id;
        SoSingleObject object;
        object.typeId = static_cast<std::int32_t>(ItemTypeId);
        object.owner = m_config.owner;
        object.version = ++m_soVersion;
        object.data = BuildEconItem(item, account, id, InventoryUnacknowledgedBit);
        Reply(gc_msg::ESOMsg::k_ESOMsg_Create, EncodeSoSingleObject(object));
        if (m_live && m_live->Items().Gameplay().care_packages_enabled) continue;
        // CEconItemPreviewDataBlock and MatchEndRewardDropsNotification from the target protobuf.
        PbWriter preview;
        preview.Varint(1, account); preview.Varint(2, id); preview.Varint(3, item.defIndex);
        preview.Varint(4, item.paintKitIndex); preview.Varint(5, item.rarity); preview.Varint(6, QualityUnique);
        preview.Varint(7, std::bit_cast<std::uint32_t>(item.wear)); preview.Varint(8, item.seed);
        PbWriter notification; notification.Message(6, preview);
        Reply(gc_msg::ECsgoGCMsg::k_EMsgGCCStrike15_v2_MatchEndRewardDropsNotification, notification.bytes());
    }    SendMissingCaseKeys();
}
}
