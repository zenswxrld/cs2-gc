#include "cs2_gc/protobuf_dump.h"
#include "cs2_gc/protobuf.h"
#include <cstdio>
#include <string_view>

namespace cs2_gc
{
namespace
{
constexpr int MaxDepth = 6;
constexpr std::size_t MaxFields = 4096;

// Individual SteamID64s are 0x0110000100000000 plus the account number.
bool LooksLikeSteamId(std::uint64_t value)
{
    return (value >> 32) == 0x01100001u;
}

bool ParsesCleanly(std::span<const std::uint8_t> bytes)
{
    PbReader reader(bytes);
    PbField field;
    std::size_t count = 0;
    while (reader.Next(field))
        if (++count > MaxFields)
            return false;
    return !reader.Failed() && count > 0;
}

bool Printable(std::span<const std::uint8_t> bytes)
{
    for (std::uint8_t b : bytes)
        if (b < 0x20 || b > 0x7E)
            return false;
    return true;
}

// SteamID64 written out as decimal text always starts with these digits.
bool ContainsSteamIdText(std::span<const std::uint8_t> bytes)
{
    constexpr std::string_view marker = "7656119";
    return std::string_view(reinterpret_cast<const char *>(bytes.data()), bytes.size()).find(marker) !=
           std::string_view::npos;
}

struct Dumper
{
    std::string out;
    std::size_t limit;
    bool truncated{};

    bool Room(std::size_t more)
    {
        if (out.size() + more > limit)
            truncated = true;
        return !truncated;
    }

    void Line(int depth, const std::string &text)
    {
        if (Room(depth * 2 + text.size() + 1))
            out.append(static_cast<std::size_t>(depth) * 2, ' '), out += text, out += '\n';
    }

    void Message(std::span<const std::uint8_t> bytes, int depth)
    {
        PbReader reader(bytes);
        PbField f;
        while (!truncated && reader.Next(f))
        {
            const std::string name = std::to_string(f.number) + ": ";
            char buffer[64];
            switch (f.wire)
            {
            case 0:
                Line(depth, name + (LooksLikeSteamId(f.value) ? "varint <steamid redacted>"
                                                              : "varint " + std::to_string(f.value)));
                break;
            case 1:
                std::snprintf(buffer, sizeof buffer, "0x%016llx", static_cast<unsigned long long>(f.value));
                Line(depth, name + (LooksLikeSteamId(f.value) ? "fixed64 <steamid redacted>"
                                                              : std::string("fixed64 ") + buffer));
                break;
            case 5:
                std::snprintf(buffer, sizeof buffer, "0x%08x", static_cast<unsigned>(f.value));
                Line(depth, name + "fixed32 " + buffer);
                break;
            default:
                if (f.bytes.empty())
                    Line(depth, name + "bytes[0]");
                else if (depth < MaxDepth && ParsesCleanly(f.bytes))
                {
                    Line(depth, name + "message {");
                    Message(f.bytes, depth + 1);
                    Line(depth, "}");
                }
                else if (ContainsSteamIdText(f.bytes))
                    Line(depth, name + "text <steamid redacted>");
                else if (Printable(f.bytes))
                    Line(depth, name + "text \"" + std::string(f.bytes.begin(), f.bytes.end()) + "\"");
                else
                    Line(depth, name + "bytes[" + std::to_string(f.bytes.size()) + "] " + HexPreview(f.bytes, 32));
            }
        }
        if (reader.Failed())
            Line(depth, "<malformed protobuf: stopped here>");
    }
};
}

std::string DumpProtobuf(std::span<const std::uint8_t> bytes, std::size_t maxBytes)
{
    Dumper dumper{{}, maxBytes, false};
    dumper.Message(bytes, 0);
    if (dumper.truncated)
        dumper.out += "<output truncated>\n";
    return dumper.out;
}

std::string HexPreview(std::span<const std::uint8_t> bytes, std::size_t maxBytes)
{
    std::string text;
    const std::size_t shown = bytes.size() < maxBytes ? bytes.size() : maxBytes;
    for (std::size_t i = 0; i < shown; ++i)
    {
        char buffer[4];
        std::snprintf(buffer, sizeof buffer, "%02x", bytes[i]);
        if (i)
            text += ' ';
        text += buffer;
    }
    if (shown < bytes.size())
        text += " ... (" + std::to_string(bytes.size()) + " bytes)";
    return text;
}
}
