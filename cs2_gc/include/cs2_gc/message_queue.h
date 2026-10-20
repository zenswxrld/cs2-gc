#pragma once

#include "cs2_gc/wire.h"
#include <deque>
#include <mutex>

namespace cs2_gc
{
// Numeric results mirror the SDK's EGCResults; no game interface is hooked yet.
enum class GCResult : std::uint32_t
{
    OK = 0,
    NoMessage = 1,
    BufferTooSmall = 2,
    NotLoggedOn = 3,
    InvalidMessage = 4
};

struct Message
{
    std::uint32_t type{};
    std::vector<std::uint8_t> bytes;
};

class MessageQueue
{
public:
    explicit MessageQueue(std::size_t byteLimit = 32 * 1024 * 1024, std::size_t messageLimit = 4096);
    bool Push(Message message);
    // A message in the old struct form: no protobuf bit, and the bytes start with the same type. The size and
    // count limits are the same as for Push.
    bool PushStruct(Message message);
    bool IsMessageAvailable(std::uint32_t *size) const;
    GCResult RetrieveMessage(std::uint32_t *type, void *destination, std::uint32_t capacity,
        std::uint32_t *size);
    void Clear();

private:
    const std::size_t m_byteLimit;
    const std::size_t m_messageLimit;
    mutable std::mutex m_mutex;
    std::deque<Message> m_messages;
    std::size_t m_bytes{};
};
}
