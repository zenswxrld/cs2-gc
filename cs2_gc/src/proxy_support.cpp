#include "cs2_gc/proxy_support.h"
#include <algorithm>
#include <charconv>
#include <iterator>
#include <limits>

namespace cs2_gc
{
namespace
{
char Lower(char c)
{
    return c >= 'A' && c <= 'Z' ? static_cast<char>(c - 'A' + 'a') : c;
}

bool EqualsNoCase(std::string_view a, std::string_view b)
{
    if (a.size() != b.size())
        return false;
    for (std::size_t i = 0; i < a.size(); ++i)
        if (Lower(a[i]) != Lower(b[i]))
            return false;
    return true;
}

std::string_view Trim(std::string_view text)
{
    const auto space = [](char c) { return c == ' ' || c == '\t' || c == '\r'; };
    while (!text.empty() && space(text.front()))
        text.remove_prefix(1);
    while (!text.empty() && space(text.back()))
        text.remove_suffix(1);
    return text;
}

template <typename T>
bool Number(std::string_view text, T &out)
{
    T value{};
    const auto [end, ec] = std::from_chars(text.data(), text.data() + text.size(), value);
    if (text.empty() || ec != std::errc{} || end != text.data() + text.size())
        return false;
    out = value;
    return true;
}
}

bool CommandLineHasArgument(std::string_view commandLine, std::string_view argument)
{
    std::string token;
    bool inQuotes = false, inToken = false;
    const auto flush = [&] {
        const bool match = inToken && EqualsNoCase(token, argument);
        token.clear();
        inToken = false;
        return match;
    };
    for (char c : commandLine)
    {
        if (c == '"')
        {
            inQuotes = !inQuotes;
            inToken = true;
        }
        else if (!inQuotes && (c == ' ' || c == '\t' || c == '\r' || c == '\n'))
        {
            if (flush())
                return true;
        }
        else
        {
            token.push_back(c);
            inToken = true;
        }
    }
    return flush();
}

std::optional<std::uint32_t> DecodeVtableThunkOffset(std::span<const std::uint8_t> code)
{
    constexpr std::uint8_t Prologue[] = {0x48, 0x8B, 0x01}; // mov rax, [rcx]
    if (code.size() < 7 || !std::equal(std::begin(Prologue), std::end(Prologue), code.begin()))
        return std::nullopt;
    if (code[3] != 0x48 || code[4] != 0xFF)
        return std::nullopt;

    std::uint32_t offset = 0;
    if (code[5] == 0x20) // jmp [rax]
        offset = 0;
    else if (code[5] == 0x60) // jmp [rax+disp8]
    {
        if (code[6] & 0x80)
            return std::nullopt; // negative displacement is not a vtable slot
        offset = code[6];
    }
    else if (code[5] == 0xA0) // jmp [rax+disp32]
    {
        if (code.size() < 10)
            return std::nullopt;
        offset = std::uint32_t{code[6]} | (std::uint32_t{code[7]} << 8) | (std::uint32_t{code[8]} << 16) |
                 (std::uint32_t{code[9]} << 24);
    }
    else
        return std::nullopt;

    if (offset % 8 != 0 || offset > 0x1000)
        return std::nullopt;
    return offset;
}

std::optional<ProxyConfig> ParseProxyConfig(std::string_view text)
{
    ProxyConfig config;
    while (!text.empty())
    {
        const std::size_t newline = text.find('\n');
        std::string_view line = text.substr(0, newline);
        text = newline == std::string_view::npos ? std::string_view{} : text.substr(newline + 1);
        if (const std::size_t hash = line.find('#'); hash != std::string_view::npos)
            line = line.substr(0, hash);
        line = Trim(line);
        if (line.empty())
            continue;

        const std::size_t equals = line.find('=');
        if (equals == std::string_view::npos)
            return std::nullopt;
        const std::string_view key = Trim(line.substr(0, equals));
        const std::string_view value = Trim(line.substr(equals + 1));
        if (key == "steam_id")
        {
            if (!Number(value, config.steamId))
                return std::nullopt;
        }
        else if (key == "welcome_version")
        {
            if (!Number(value, config.welcomeVersion))
                return std::nullopt;
        }
        else if (key == "owner_type")
        {
            if (!Number(value, config.ownerType))
                return std::nullopt;
        }
        else if (key == "cache_version")
        {
            if (!Number(value, config.cacheVersion))
                return std::nullopt;
        }
        else
            return std::nullopt;
    }
    return config;
}
}
