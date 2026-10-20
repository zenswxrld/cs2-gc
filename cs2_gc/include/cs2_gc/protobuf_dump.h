#pragma once

#include <cstddef>
#include <cstdint>
#include <span>
#include <string>

namespace cs2_gc
{
// Schema-less, human-readable dump of a protobuf message for diagnostics. Length-delimited
// fields are shown as nested messages, text or hex, chosen heuristically, so the output is
// a guide and not a decoding. Any value shaped like a SteamID64 is redacted so logs can be
// shared. The result is bounded by maxBytes and ends with a marker if it was cut off.
std::string DumpProtobuf(std::span<const std::uint8_t> bytes, std::size_t maxBytes = 64 * 1024);

// "ab cd ef ..." of at most maxBytes bytes, with a trailing count when truncated.
std::string HexPreview(std::span<const std::uint8_t> bytes, std::size_t maxBytes = 64);
}
