#include "cs2_gc/proxy_support.h"
#include <charconv>
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
