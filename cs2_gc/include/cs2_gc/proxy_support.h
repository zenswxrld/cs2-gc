#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <string_view>

namespace cs2_gc
{
// True when the command line has `argument` as a whole token (ASCII case-insensitive).
// Tokens are separated by whitespace; double quotes group text, as on Windows.
bool CommandLineHasArgument(std::string_view commandLine, std::string_view argument);

// Settings for the proxy, read from a small key=value file. Every value is optional,
// '#' starts a comment, and an unknown key or malformed value rejects the whole file
// so a typo cannot silently run with defaults.
struct ProxyConfig
{
    std::uint64_t steamId{};          // steam_id: SteamID64 used as the cache owner
    std::uint32_t welcomeVersion{};   // welcome_version
    std::uint32_t ownerType{1};       // owner_type: SO owner type for the steam id
    std::uint64_t cacheVersion{1};    // cache_version
};

std::optional<ProxyConfig> ParseProxyConfig(std::string_view text);
}
