#include "cs2_gc/gc_endpoint.h"
#include "cs2_gc/econ_item.h"
#include "cs2_gc/gc_msg_ids.h"
#include "cs2_gc/protobuf.h"

namespace cs2_gc
{
namespace
{
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

    // The recorded Armory pass object, kept so a balance change only rewrites its balance field.
    std::vector<std::uint8_t> passObject;
    if (m_replay)
        if (const auto *welcome = m_replay->Find(gc_msg::EGCBaseClientMsg::k_EMsgGCClientWelcome))
        {
            auto objects = ExtractObjects(*welcome, XpShopTypeId);
            if (!objects.empty())
                passObject = std::move(objects.front());
        }

    SetHandler(gc_msg::ECsgoGCMsg::k_EMsgGCCStrike15_v2_ClientRedeemMissionReward,
               [armory, inventory, random, afterGrant, passObject](const FrameView &frame, LocalGameCoordinator &gc) {
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

                   if (const auto pass = WithXpShopBalance(passObject, armory->Balance()))
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
}

void LocalGameCoordinator::EnableStorePurchaseFailure()
{
    SetHandler(gc_msg::EGCItemMsg::k_EMsgGCStorePurchaseInit, [](const FrameView &frame, LocalGameCoordinator &gc) {
        PbWriter response;
        response.Varint(1, 2); // result: EResult Fail
        gc.Reply(gc_msg::EGCItemMsg::k_EMsgGCStorePurchaseInitResponse, response.bytes(), ReplyHeaderFor(frame));
    });
}

void LocalGameCoordinator::EnableLiveInventory(std::shared_ptr<LiveInventory> inventory)
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
                const std::uint32_t credits = m_armory ? m_armory->Balance() : *m_armoryCredits;
                if (auto result = SetArmoryBalance(patched, credits))
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
