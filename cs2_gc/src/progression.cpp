#include <bit>
#include "cs2_gc/progression.h"
#include <algorithm>
#include <limits>

namespace cs2_gc
{
ProgressChange ApplyReward(Profile &profile, RewardEvent event, const RewardConfig &config)
{
    Reward reward{};
    switch (event)
    {
    case RewardEvent::Kill: reward = config.kill; break;
    case RewardEvent::Headshot: reward = config.headshot; break;
    case RewardEvent::MVP: reward = config.mvp; break;
    case RewardEvent::Plant: reward = config.plant; break;
    case RewardEvent::Defuse: reward = config.defuse; break;
    case RewardEvent::MatchComplete: reward = config.matchComplete; break;
    default: return {};
    }
    ProgressChange change;
    if (config.starsEnabled)
    {
        change.starsAdded = std::min<std::uint64_t>(reward.stars,
            std::numeric_limits<std::uint64_t>::max() - profile.stars);
        profile.stars += change.starsAdded;
    }
    if (!config.xpEnabled || !reward.xp)
        return change;
    profile.level = std::clamp(profile.level, 1u, 40u);
    if (profile.level == 40)
    {
        profile.xp = 0;
        return change;
    }
    const auto perLevel = std::max(config.xpPerLevel, 1u);
    std::uint64_t xp = std::uint64_t{profile.xp} + reward.xp;
    change.levelsGained = static_cast<std::uint32_t>(std::min<std::uint64_t>(xp / perLevel, 40 - profile.level));
    profile.level += change.levelsGained;
    profile.xp = profile.level == 40 ? 0 : static_cast<std::uint32_t>(xp % perLevel);
    return change;
}
}

// Profile fields are from build 25966348's CMsgGCCStrike15_v2_MatchmakingGC2ClientHello.
// The recorded CS2 welcome also confirms the native XP base (327680000) in game_data2.
#include "cs2_gc/protobuf.h"
namespace cs2_gc
{
namespace
{
void CopyField(PbWriter &out, const PbField &field)
{
    switch (field.wire)
    {
    case 0: out.Varint(field.number, field.value); break;
    case 1: out.Fixed64(field.number, field.value); break;
    case 5: out.Fixed32(field.number, static_cast<std::uint32_t>(field.value)); break;
    default: out.Bytes(field.number, field.bytes); break;
    }
}
}
std::vector<std::uint8_t> EncodePremierRank(const LocalPremier &rank, std::uint32_t accountId, std::int32_t change)
{
    PbWriter out;
    out.Varint(1, accountId);
    out.Varint(2, rank.wins >= rank.placementWins ? rank.rating : 0);
    out.Varint(3, rank.wins);
    out.Fixed32(4, std::bit_cast<std::uint32_t>(static_cast<float>(change)));
    out.Varint(6, 11);
    return out.bytes();
}
std::optional<std::vector<std::uint8_t>> WithPremierRankUpdate(std::span<const std::uint8_t> body,
                                                            const LocalPremier &rank, std::uint32_t accountId, std::int32_t change)
{
    PbWriter out;
    PbReader reader(body);
    PbField field;
    while (reader.Next(field))
    {
        bool premier = false;
        if (field.number == 1 && field.wire == 2)
        {
            PbReader ranking(field.bytes);
            PbField value;
            while (ranking.Next(value))
                if (value.number == 6 && value.wire == 0 && value.value == 11) premier = true;
            if (ranking.Failed()) return std::nullopt;
        }
        if (!premier) CopyField(out, field);
    }
    if (reader.Failed()) return std::nullopt;
    out.Bytes(1, EncodePremierRank(rank, accountId, change));
    return out.bytes();
}
std::optional<std::vector<std::uint8_t>> WithLocalProfile(std::span<const std::uint8_t> body,
                                                       const LocalProgress &profile,
                                                       const LocalPremier *premier, std::uint32_t accountId)
{
    PbWriter out;
    PbReader reader(body);
    PbField field;
    while (reader.Next(field))
    {
        bool oldPremier = false;
        if (premier && field.number == 20 && field.wire == 2)
        {
            PbReader ranking(field.bytes);
            PbField rank;
            while (ranking.Next(rank))
                if (rank.number == 6 && rank.wire == 0 && rank.value == 11) oldPremier = true;
            if (ranking.Failed()) return std::nullopt;
        }
        if (field.number != 17 && field.number != 18 && !oldPremier)
            CopyField(out, field);
    }
    if (reader.Failed())
        return std::nullopt;
    out.Varint(17, profile.level);
    out.Varint(18, 327680000u + profile.xp);
    if (premier) out.Bytes(20, EncodePremierRank(*premier, accountId));
    return out.bytes();
}
std::optional<std::vector<std::uint8_t>> WithWelcomeProfile(std::span<const std::uint8_t> body,
                                                         const LocalProgress &profile,
                                                         const LocalPremier *premier, std::uint32_t accountId)
{
    PbWriter out;
    PbReader reader(body);
    PbField field;
    bool found = false;
    while (reader.Next(field))
    {
        if (field.number == 6 && field.wire == 2)
        {
            const auto patched = WithLocalProfile(field.bytes, profile, premier, accountId);
            if (!patched)
                return std::nullopt;
            out.Bytes(6, *patched);
            found = true;
        }
        else
            CopyField(out, field);
    }
    if (reader.Failed())
        return std::nullopt;
    if (!found)
        out.Bytes(6, *WithLocalProfile({}, profile, premier, accountId));
    return out.bytes();
}
}
