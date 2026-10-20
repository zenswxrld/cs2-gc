#pragma once

#include <cstdint>
#include <optional>
#include <span>
#include <vector>

namespace cs2_gc
{
inline constexpr std::uint32_t ProfileLevelXp = 5000;
inline constexpr std::uint32_t ArmoryStarXp = 400;
inline constexpr std::uint32_t ArmoryPassMaxXp = 40 * ArmoryStarXp;
struct LocalProgress
{
    std::uint32_t level{1};
    std::uint32_t xp{};
    std::uint64_t rewardTotal{}; // cumulative bridge XP already applied, for idempotent delivery
};
struct LocalPremier
{
    std::uint32_t rating{}, wins{}, placementWins{10};
    bool operator==(const LocalPremier &) const = default;
};
// Rank type 11 and these fields are present in the supplied CS2 capture/protobuf.
std::vector<std::uint8_t> EncodePremierRank(const LocalPremier &rank, std::uint32_t accountId, std::int32_t change = 0);
std::optional<std::vector<std::uint8_t>> WithPremierRankUpdate(std::span<const std::uint8_t> body,
                                                            const LocalPremier &rank, std::uint32_t accountId, std::int32_t change = 0);
std::optional<std::vector<std::uint8_t>> WithLocalProfile(std::span<const std::uint8_t> body,
                                                       const LocalProgress &profile,
                                                       const LocalPremier *premier = nullptr, std::uint32_t accountId = 0);
std::optional<std::vector<std::uint8_t>> WithWelcomeProfile(std::span<const std::uint8_t> body,
                                                         const LocalProgress &profile,
                                                         const LocalPremier *premier = nullptr, std::uint32_t accountId = 0);
// The adapter must filter events to the local player. Headshot is an extra
// reward in addition to Kill, matching the CS:GO fork's configuration.
enum class RewardEvent { Kill, Headshot, MVP, Plant, Defuse, MatchComplete };
struct Reward { std::uint32_t xp; std::uint32_t stars; };
struct RewardConfig
{
    bool xpEnabled{true};
    bool starsEnabled{true};
    std::uint32_t xpPerLevel{5000};
    Reward kill{5, 1};
    Reward headshot{3, 4};
    Reward mvp{25, 5};
    Reward plant{25, 3};
    Reward defuse{25, 3};
    Reward matchComplete{600, 50};
};
struct Profile
{
    std::uint32_t level{1};
    std::uint32_t xp{};
    std::uint64_t stars{};
};
struct ProgressChange
{
    std::uint32_t levelsGained{};
    std::uint64_t starsAdded{};
};

// Pure local reward rules ported from Inventory::AddPlayerXp and StarShop::Reward.
// Does not grant real Steam items or publish a GC profile.
ProgressChange ApplyReward(Profile &profile, RewardEvent event, const RewardConfig &config);
}
