#pragma once

#include <cstddef>
#include <cstdint>
#include <span>
#include <vector>

namespace cs2_gc
{
inline constexpr std::uint32_t ProtobufMask = 0x80000000u;
inline constexpr std::size_t MaxMessageBytes = 16 * 1024 * 1024;

enum class FrameError
{
    None,
    TooLarge,
    Truncated,
    NotProtobuf,
    InvalidType,
    TypeMismatch,
    InvalidHeaderLength
};

// Non-owning views: the source bytes must outlive the parsed frame.
// Header/body are opaque protobuf bytes, not a claim of schema compatibility.
struct FrameView
{
    std::uint32_t type{}; // protobuf flag retained, as in ISteamGameCoordinator
    std::span<const std::uint8_t> header;
    std::span<const std::uint8_t> body;
};

FrameError ReadProtobufFrame(std::uint32_t apiType, std::span<const std::uint8_t> bytes,
    FrameView &frame);
FrameError WriteProtobufFrame(std::uint32_t type, std::span<const std::uint8_t> header,
    std::span<const std::uint8_t> body, std::vector<std::uint8_t> &bytes);
}
