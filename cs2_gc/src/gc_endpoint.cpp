#include "cs2_gc/gc_endpoint.h"
#include "cs2_gc/econ_item.h"
#include "cs2_gc/gc_msg_ids.h"
#include "cs2_gc/protobuf.h"
#include <utility>
#include <ctime>

namespace cs2_gc
{
namespace
{
// CMsgGCItemCustomizationNotification: item_id (1), request (2). The game waits for it to finish
// an unlock, sticker or naming screen. The request values are the client's own
// k_EGCItemCustomizationNotification_* enum, read from its descriptors.
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
                    pass = WithXpShopTracks(*pass, inventory->Items().XpTracks());
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
                           pass = WithXpShopTracks(gc.m_xpShop, inventory->Items().XpTracks());
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
                   for (const auto &line : txn->lines)
                       for (std::uint32_t i = 0; i < line.quantity; ++i)
                       {
                           InventoryItem item;
                           item.defIndex = line.defIndex;
                           // The Store sells coupons. One for a single sticker or charm is that item; one for a
                           // container (or anything the schema cannot resolve yet) stays an envelope to unlock.
                           if (schema)
                               if (const auto entries = schema->CouponEntries(line.defIndex); entries.size() == 1)
                                   if (const auto loot = schema->ResolveLootItem(entries[0]);
                                       loot && (loot->kind == LootKind::Sticker || loot->kind == LootKind::Keychain))
                                       item = MakeLootItem(*loot, 0, [] { return std::uint64_t{0}; });
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
        m_schema = schema;
    }
    SetHandler(gc_msg::EGCItemMsg::k_EMsgGCOpenCrate,
               [inventory, schema, random, afterChange](const FrameView &frame, LocalGameCoordinator &gc) {
                   const auto request = DecodeOpenCrateRequest(frame.body);
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
               [inventory](const FrameView &frame, LocalGameCoordinator &gc) {
                   const auto request = DecodeCasketRequest(frame.body);
                   const InventoryItem *casket = request && request->casketItemId > CustomItemIdBase
                                                     ? inventory->Items().Find(request->casketItemId - CustomItemIdBase)
                                                     : nullptr;
                   if (!casket || casket->defIndex != DefinitionStorageUnit)
                   {
                       ++gc.m_ignored;
                       return;
                   }
                   gc.Reply(gc_msg::EGCItemMsg::k_EMsgGCItemCustomizationNotification,
                            EncodeCustomizationNotification(NotificationCasketContents, request->casketItemId));
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
               [inventory](const FrameView &frame, LocalGameCoordinator &gc) {
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
                if (const auto *body = m_replay->Find(id))
                    Reply(id, *body);
            return;
        }
    }

    ClientWelcome welcome;
    welcome.version = m_config.welcomeVersion;
    welcome.outOfDateCaches.push_back({m_config.owner, m_config.cacheVersion, m_config.cacheTypes});
    Reply(gc_msg::EGCBaseClientMsg::k_EMsgGCClientWelcome, EncodeClientWelcome(welcome));
}
}
