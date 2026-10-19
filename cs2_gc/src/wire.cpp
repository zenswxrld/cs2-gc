#include "cs2_gc/wire.h"
#include <utility>

namespace cs2_gc
{
namespace
{
std::uint32_t Read32(std::span<const std::uint8_t> bytes)
{
    return std::uint32_t{bytes[0]} | (std::uint32_t{bytes[1]} << 8)
        | (std::uint32_t{bytes[2]} << 16) | (std::uint32_t{bytes[3]} << 24);
}

void Append32(std::vector<std::uint8_t> &bytes, std::uint32_t value)
{
    for (unsigned shift = 0; shift < 32; shift += 8)
        bytes.push_back(static_cast<std::uint8_t>(value >> shift));
}
}

FrameError ReadProtobufFrame(std::uint32_t apiType, std::span<const std::uint8_t> bytes,
    FrameView &frame)
{
    frame = {};
    if (bytes.size() > MaxMessageBytes)
        return FrameError::TooLarge;
    if (bytes.size() < 8)
        return FrameError::Truncated;
    const auto type = Read32(bytes);
    if (!(type & ProtobufMask))
        return FrameError::NotProtobuf;
    if (!(type & ~ProtobufMask))
        return FrameError::InvalidType;
    if (apiType != type)
        return FrameError::TypeMismatch;
    const auto headerLength = Read32(bytes.subspan(4));
    if (headerLength > bytes.size() - 8)
        return FrameError::InvalidHeaderLength;
    frame = {type, bytes.subspan(8, headerLength), bytes.subspan(8 + headerLength)};
    return FrameError::None;
}

FrameError WriteProtobufFrame(std::uint32_t type, std::span<const std::uint8_t> header,
    std::span<const std::uint8_t> body, std::vector<std::uint8_t> &bytes)
{
    // Assemble separately so input spans may refer to the previous output.
    if (!(type & ~ProtobufMask))
        return FrameError::InvalidType;
    if (header.size() > MaxMessageBytes - 8 || body.size() > MaxMessageBytes - 8 - header.size())
        return FrameError::TooLarge;
    std::vector<std::uint8_t> result;
    result.reserve(8 + header.size() + body.size());
    Append32(result, type | ProtobufMask);
    Append32(result, static_cast<std::uint32_t>(header.size()));
    result.insert(result.end(), header.begin(), header.end());
    result.insert(result.end(), body.begin(), body.end());
    bytes = std::move(result);
    return FrameError::None;
}
}
