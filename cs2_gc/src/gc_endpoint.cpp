#include "cs2_gc/gc_endpoint.h"
#include "cs2_gc/gc_msg_ids.h"

namespace cs2_gc
{
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
    ClientWelcome welcome;
    welcome.version = m_config.welcomeVersion;
    welcome.outOfDateCaches.push_back({m_config.owner, m_config.cacheVersion, m_config.cacheTypes});
    Reply(gc_msg::EGCBaseClientMsg::k_EMsgGCClientWelcome, EncodeClientWelcome(welcome));
}
}
