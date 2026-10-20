#pragma once

#include <cstddef>
#include <cstdint>
#include <span>
#include <string_view>
#include <vector>

namespace cs2_gc
{
struct PbField
{
    std::uint32_t number{};
    std::uint32_t wire{};                    // 0 varint, 1 fixed64, 2 length-delimited, 5 fixed32
    std::uint64_t value{};                   // varint / fixed32 / fixed64 payload
    std::span<const std::uint8_t> bytes;     // length-delimited payload, views the source
};

// Bounds-checked reader. Unknown fields are returned to the caller to skip; groups and
// other unsupported wire types, bad varints and overruns set Failed().
class PbReader
{
public:
    explicit PbReader(std::span<const std::uint8_t> data) : m_data(data) {}
    bool Next(PbField &field); // false at the clean end or on error
    bool Failed() const { return m_failed; }

private:
    std::span<const std::uint8_t> m_data;
    std::size_t m_pos{};
    bool m_failed{};
};

class PbWriter
{
public:
    void Varint(std::uint32_t number, std::uint64_t value);
    void Fixed64(std::uint32_t number, std::uint64_t value);
    void Fixed32(std::uint32_t number, std::uint32_t value);
    void Bytes(std::uint32_t number, std::span<const std::uint8_t> bytes);
    void String(std::uint32_t number, std::string_view text);
    void Message(std::uint32_t number, const PbWriter &nested) { Bytes(number, nested.m_bytes); }
    const std::vector<std::uint8_t> &bytes() const { return m_bytes; }

private:
    void Tag(std::uint32_t number, std::uint32_t wire);
    void RawVarint(std::uint64_t value);
    std::vector<std::uint8_t> m_bytes;
};
}
