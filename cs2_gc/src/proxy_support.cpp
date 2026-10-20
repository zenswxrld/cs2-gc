#include "cs2_gc/proxy_support.h"
#include <algorithm>
#include <charconv>
#include <iterator>
#include <limits>
#include <set>
#include "cs2_gc/gameplay_config.h"

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

std::wstring QuoteWindowsArgument(std::wstring_view argument)
{
    std::wstring out(1, L'"');
    std::size_t slashes = 0;
    for (const auto ch : argument)
    {
        if (ch == L'\\') { ++slashes; continue; }
        out.append(ch == L'"' ? slashes * 2 + 1 : slashes, L'\\');
        slashes = 0;
        out += ch;
    }
    out.append(slashes * 2, L'\\');
    out += L'"';
    return out;
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
        else if (key == "mode")
        {
            if (value == "local")
                config.mode = ProxyMode::Local;
            else if (value == "capture")
                config.mode = ProxyMode::Capture;
            else
                return std::nullopt;
        }
        else if (key == "armory_credits")
        {
            std::uint32_t credits = 0;
            if (!Number(value, credits) || credits > 1000000)
                return std::nullopt;
            config.armoryCredits = credits;
        }
        else if (key == "real_items")
        {
            if (value == "hide")
                config.hideRealItems = true;
            else if (value == "keep")
                config.hideRealItems = false;
            else
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

namespace cs2_gc
{
std::optional<GameplayConfig> ParseGameplayConfig(std::string_view text)
{
    GameplayConfig config;
    std::set<std::string> seen;
    while (!text.empty())
    {
        const auto end = text.find('\n');
        auto line = text.substr(0, end);
        text = end == std::string_view::npos ? std::string_view{} : text.substr(end + 1);
        line = Trim(line.substr(0, line.find('#')));
        if (line.empty()) continue;
        const auto equal = line.find('=');
        if (equal == std::string_view::npos) return std::nullopt;
        const auto key = Trim(line.substr(0, equal)), value = Trim(line.substr(equal + 1));
        if (!seen.insert(std::string(key)).second) return std::nullopt;
        std::uint32_t number = 0;
        if (!Number(value, number)) return std::nullopt;
        std::uint32_t *target = nullptr, minimum = 0, maximum = 1;
#define BOOL_OPTION(name) if (key == #name) target = &config.name; else
#define NUMBER_OPTION(name, low, high) if (key == #name) { target = &config.name; minimum = low; maximum = high; } else
        BOOL_OPTION(rewards_auto_start) BOOL_OPTION(xp_enabled) BOOL_OPTION(stars_enabled) BOOL_OPTION(match_drops_enabled)
        BOOL_OPTION(mixed_stattrak_tradeups) BOOL_OPTION(pity_enabled) BOOL_OPTION(terminals_enabled)
        BOOL_OPTION(terminal_helper_enabled) BOOL_OPTION(armory_rotation_enabled) BOOL_OPTION(armory_rotation_enforce) BOOL_OPTION(premier_enabled) BOOL_OPTION(armory_howl_enabled)
        BOOL_OPTION(premier_scoreboard) BOOL_OPTION(premier_bot_badges)
        BOOL_OPTION(level_drops_enabled) NUMBER_OPTION(level_drop_count, 1, 20)
        BOOL_OPTION(skip_container_confirmation)
        BOOL_OPTION(hide_rent_button)
        BOOL_OPTION(armory_pity_enabled)
        NUMBER_OPTION(armory_pity_soft_at, 2, 99) NUMBER_OPTION(armory_pity_hard_at, 3, 100)
        NUMBER_OPTION(armory_top_per_10000, 0, 10000)
        NUMBER_OPTION(armory_howl_star_price, 1, 1000000)
        NUMBER_OPTION(premier_placement_wins, 1, 100) NUMBER_OPTION(premier_start_rating, 0, 99999)
        NUMBER_OPTION(premier_win_rating, 0, 10000) NUMBER_OPTION(premier_loss_rating, 0, 10000)
        NUMBER_OPTION(premier_max_rating, 1, 99999)
        NUMBER_OPTION(armory_rotation_seconds, 10, 86400) NUMBER_OPTION(armory_rotation_slots, 1, 60)
        NUMBER_OPTION(armory_xp_per_star, 1, 100000)
        NUMBER_OPTION(kill_xp, 0, 1000000) NUMBER_OPTION(headshot_xp, 0, 1000000)
        NUMBER_OPTION(mvp_xp, 0, 1000000) NUMBER_OPTION(match_complete_xp, 0, 1000000)
        NUMBER_OPTION(match_drop_count, 1, 20) NUMBER_OPTION(match_case_percent, 0, 100)
        NUMBER_OPTION(match_skin_min_rarity, 3, 6)
        NUMBER_OPTION(pity_soft_at, 2, 99) NUMBER_OPTION(pity_hard_at, 3, 100)
        NUMBER_OPTION(case_gold_per_10000, 0, 10000) NUMBER_OPTION(terminal_top_per_10000, 0, 10000)
        NUMBER_OPTION(terminal_default_offers, 1, 100) NUMBER_OPTION(terminal_lifetime_days, 1, 365)
        return std::nullopt;
#undef BOOL_OPTION
#undef NUMBER_OPTION
        if (number < minimum || number > maximum) return std::nullopt;
        *target = number;
    }
    if (config.premier_start_rating > config.premier_max_rating) return std::nullopt;
    if (config.armory_pity_soft_at >= config.armory_pity_hard_at) return std::nullopt;
    if (config.pity_soft_at >= config.pity_hard_at) return std::nullopt;
    return config;
}
}
