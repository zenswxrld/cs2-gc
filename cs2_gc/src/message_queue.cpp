#include "cs2_gc/message_queue.h"
#include <cstring>

namespace cs2_gc
{
MessageQueue::MessageQueue(std::size_t byteLimit, std::size_t messageLimit)
    : m_byteLimit{byteLimit}, m_messageLimit{messageLimit}
{
}

bool MessageQueue::Push(Message message)
{
    FrameView frame;
    if (ReadProtobufFrame(message.type, message.bytes, frame) != FrameError::None)
        return false;
    const std::lock_guard lock{m_mutex};
    if (m_messages.size() >= m_messageLimit || message.bytes.size() > m_byteLimit - m_bytes)
        return false;
    const auto size = message.bytes.size();
    m_messages.push_back(std::move(message));
    m_bytes += size;
    return true;
}

bool MessageQueue::PushStruct(Message message)
{
    if (message.bytes.size() < 4 || message.bytes.size() > MaxMessageBytes || (message.type & ProtobufMask) ||
        message.type == 0)
        return false;
    const std::uint32_t embedded = std::uint32_t{message.bytes[0]} | (std::uint32_t{message.bytes[1]} << 8) |
                                   (std::uint32_t{message.bytes[2]} << 16) | (std::uint32_t{message.bytes[3]} << 24);
    if (embedded != message.type)
        return false;
    const std::lock_guard lock{m_mutex};
    if (m_messages.size() >= m_messageLimit || message.bytes.size() > m_byteLimit - m_bytes)
        return false;
    const auto size = message.bytes.size();
    m_messages.push_back(std::move(message));
    m_bytes += size;
    return true;
}

bool MessageQueue::IsMessageAvailable(std::uint32_t *size) const
{
    if (!size)
        return false;
    const std::lock_guard lock{m_mutex};
    *size = m_messages.empty() ? 0 : static_cast<std::uint32_t>(m_messages.front().bytes.size());
    return !m_messages.empty();
}

GCResult MessageQueue::RetrieveMessage(std::uint32_t *type, void *destination,
    std::uint32_t capacity, std::uint32_t *size)
{
    if (type)
        *type = 0;
    if (size)
        *size = 0;
    if (!type || !size)
        return GCResult::InvalidMessage;
    const std::lock_guard lock{m_mutex};
    if (m_messages.empty())
        return GCResult::NoMessage;
    const auto &message = m_messages.front();
    *size = static_cast<std::uint32_t>(message.bytes.size());
    if (capacity < message.bytes.size())
        return GCResult::BufferTooSmall;
    if (!destination)
        return GCResult::InvalidMessage;
    *type = message.type;
    std::memcpy(destination, message.bytes.data(), message.bytes.size());
    m_bytes -= message.bytes.size();
    m_messages.pop_front();
    return GCResult::OK;
}

void MessageQueue::Clear()
{
    const std::lock_guard lock{m_mutex};
    m_messages.clear();
    m_bytes = 0;
}
}
