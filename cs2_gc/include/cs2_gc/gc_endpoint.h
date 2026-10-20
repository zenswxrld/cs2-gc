#pragma once

#include "cs2_gc/gc_handshake.h"
#include "cs2_gc/message_queue.h"
#include "cs2_gc/replay.h"
#include <atomic>
#include <functional>
#include <memory>
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
    void SetHandler(std::uint32_t type, Handler handler); // plain ID; replaces any earlier one
    void SetOwner(const SoOwner &owner);                  // used by later welcomes

    // Answers from recorded real-GC bodies. A recorded Welcome replaces the synthetic one and
    // is followed by the other messages the real GC sent unprompted after it; a request that
    // the capture showed being answered gets the recorded reply. Message types with no
    // recording are left exactly as they were. The recorded bodies belong to one account.
    void EnableReplay(std::shared_ptr<const ReplayStore> store);

    std::size_t IgnoredMessages() const { return m_ignored; }

private:
    void OnClientHello(const FrameView &frame);

    GcEndpointConfig m_config;
    std::shared_ptr<const ReplayStore> m_replay;
    MessageQueue m_toGame;
    std::mutex m_mutex;
    std::unordered_map<std::uint32_t, Handler> m_handlers;
    std::atomic<std::size_t> m_ignored{0};
};
}
