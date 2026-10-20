#pragma once

#include "cs2_gc/protobuf_dump.h"
#include <cstdint>
#include <span>
#include <string>

namespace cs2_gc
{
// Compact description of the shared-object messages (Welcome, Create, Update, Destroy,
// CacheSubscribed, UpdateMultiple): which object type IDs they carry, how many objects, and
// one dumped sample of each type. Inventory-sized messages stay readable in a log this way.
// Returns an empty string for any other message ID, or when the body cannot be decoded.
std::string SummarizeSoMessage(std::uint32_t messageId, std::span<const std::uint8_t> body,
                               const DumpOptions &options);
}
