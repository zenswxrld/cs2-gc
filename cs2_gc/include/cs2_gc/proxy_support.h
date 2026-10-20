#pragma once

#include <cstdint>
#include <optional>
#include <span>
#include <string>
#include <string_view>

namespace cs2_gc
{
// True when the command line has `argument` as a whole token (ASCII case-insensitive).
// Tokens are separated by whitespace; double quotes group text, as on Windows.
bool CommandLineHasArgument(std::string_view commandLine, std::string_view argument);

// Decodes the Steamworks flat-API wrapper `mov rax,[rcx]; jmp [rax+N]` and returns the
// vtable byte offset N. Anything else (including unaligned or implausible offsets) is
// rejected, so a changed code shape disables the hook instead of patching a wrong slot.
std::optional<std::uint32_t> DecodeVtableThunkOffset(std::span<const std::uint8_t> code);

// Settings for the proxy, read from a small key=value file. Every value is optional,
// '#' starts a comment, and an unknown key or malformed value rejects the whole file
// so a typo cannot silently run with defaults.
enum class ProxyMode
{
    Local,   // answer the game from the in-process GC
    Capture, // pass everything to Valve's real GC and only record the traffic
};

struct ProxyConfig
{
    ProxyMode mode{ProxyMode::Local}; // mode: local | capture
    bool hideRealItems{true};         // real_items: hide (a fresh inventory, the default) | keep
    std::uint64_t steamId{};          // steam_id: SteamID64 used as the cache owner
    std::uint32_t welcomeVersion{};   // welcome_version
    std::uint32_t ownerType{1};       // owner_type: SO owner type for the steam id
    std::uint64_t cacheVersion{1};    // cache_version
};

std::optional<ProxyConfig> ParseProxyConfig(std::string_view text);
}
