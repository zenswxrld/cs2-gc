#include "cs2_gc/protobuf.h"

namespace cs2_gc
{
namespace
{
bool ReadVarint(std::span<const std::uint8_t> data, std::size_t &pos, std::uint64_t &out)
{
    out = 0;
    for (unsigned shift = 0; shift < 70; shift += 7)
    {
        if (pos >= data.size())
            return false;
        const std::uint8_t byte = data[pos++];
        if (shift == 63 && byte > 1)
            return false; // would overflow 64 bits
        out |= std::uint64_t{static_cast<std::uint8_t>(byte & 0x7F)} << shift;
        if (!(byte & 0x80))
            return true;
    }
    return false;
}

bool ReadFixed(std::span<const std::uint8_t> data, std::size_t &pos, unsigned bytes, std::uint64_t &out)
{
    if (data.size() - pos < bytes)
        return false;
    out = 0;
    for (unsigned i = 0; i < bytes; ++i)
        out |= std::uint64_t{data[pos + i]} << (8 * i);
    pos += bytes;
    return true;
}
}

bool PbReader::Next(PbField &field)
{
    field = {};
    if (m_failed || m_pos >= m_data.size())
        return false;

    std::uint64_t tag = 0;
    bool ok = ReadVarint(m_data, m_pos, tag) && (tag >> 3) != 0 && (tag >> 3) <= 0x1FFFFFFF;
    if (ok)
    {
        field.number = static_cast<std::uint32_t>(tag >> 3);
        field.wire = static_cast<std::uint32_t>(tag & 7);
        switch (field.wire)
        {
        case 0: ok = ReadVarint(m_data, m_pos, field.value); break;
        case 1: ok = ReadFixed(m_data, m_pos, 8, field.value); break;
        case 5: ok = ReadFixed(m_data, m_pos, 4, field.value); break;
        case 2:
        {
            std::uint64_t length = 0;
            ok = ReadVarint(m_data, m_pos, length) && length <= m_data.size() - m_pos;
            if (ok)
            {
                field.bytes = m_data.subspan(m_pos, static_cast<std::size_t>(length));
                m_pos += static_cast<std::size_t>(length);
            }
            break;
        }
        default: ok = false; break;
        }
    }
    if (!ok)
    {
        m_failed = true;
        field = {};
    }
    return ok;
}

void PbWriter::RawVarint(std::uint64_t value)
{
    while (value >= 0x80)
    {
        m_bytes.push_back(static_cast<std::uint8_t>(value | 0x80));
        value >>= 7;
    }
    m_bytes.push_back(static_cast<std::uint8_t>(value));
}

void PbWriter::Tag(std::uint32_t number, std::uint32_t wire)
{
    RawVarint((std::uint64_t{number} << 3) | wire);
}

void PbWriter::Varint(std::uint32_t number, std::uint64_t value)
{
    Tag(number, 0);
    RawVarint(value);
}

void PbWriter::Fixed64(std::uint32_t number, std::uint64_t value)
{
    Tag(number, 1);
    for (unsigned shift = 0; shift < 64; shift += 8)
        m_bytes.push_back(static_cast<std::uint8_t>(value >> shift));
}

void PbWriter::Fixed32(std::uint32_t number, std::uint32_t value)
{
    Tag(number, 5);
    for (unsigned shift = 0; shift < 32; shift += 8)
        m_bytes.push_back(static_cast<std::uint8_t>(value >> shift));
}

void PbWriter::Bytes(std::uint32_t number, std::span<const std::uint8_t> bytes)
{
    Tag(number, 2);
    RawVarint(bytes.size());
    m_bytes.insert(m_bytes.end(), bytes.begin(), bytes.end());
}

void PbWriter::String(std::uint32_t number, std::string_view text)
{
    Bytes(number, {reinterpret_cast<const std::uint8_t *>(text.data()), text.size()});
}
}
