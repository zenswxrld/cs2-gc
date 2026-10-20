#include "cs2_gc/gc_endpoint.h"
#include "cs2_gc/econ_item.h"
#include "cs2_gc/gc_msg_ids.h"

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
    for (const ReplayRule &rule : ReplayRules)
    {
        if (!store->Find(rule.reply))
            continue;
        SetHandler(rule.request, [store, reply = rule.reply](const FrameView &, LocalGameCoordinator &gc) {
            gc.Reply(reply, *store->Find(reply));
        });
    }
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
            std::vector<std::uint8_t> patched;
            std::span<const std::uint8_t> body = *welcome;
            if (m_itemProvider || m_dropRecordedItems)
            {
                const auto items = m_itemProvider ? m_itemProvider(m_config.owner.id)
                                                  : std::vector<std::vector<std::uint8_t>>{};
                if (!items.empty() || m_dropRecordedItems)
                {
                    if (auto result = AppendItemsToWelcome(*welcome, items, m_dropRecordedItems))
                    {
                        patched = std::move(*result);
                        body = patched;
                    }
                    else
                        ++m_patchFailures;
                }
            }
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
