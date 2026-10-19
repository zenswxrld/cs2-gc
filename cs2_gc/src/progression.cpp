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
