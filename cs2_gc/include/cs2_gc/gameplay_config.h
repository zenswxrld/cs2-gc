#pragma once
#include <cstdint>
#include <optional>
#include <string_view>

namespace cs2_gc
{
// Runtime policy only: inventory balances/counters remain in the saved inventory.
struct GameplayConfig
{
    std::uint32_t rewards_auto_start{1};
    std::uint32_t xp_enabled{1}, stars_enabled{1};
    std::uint32_t armory_xp_per_star{400};
    std::uint32_t kill_xp{5}, headshot_xp{3}, mvp_xp{25}, match_complete_xp{600};
    std::uint32_t match_drops_enabled{1}, match_drop_count{3}, match_case_percent{50}, match_skin_min_rarity{3};
    std::uint32_t mixed_stattrak_tradeups{1};
    std::uint32_t pity_enabled{1}, pity_soft_at{10}, pity_hard_at{100};
    std::uint32_t case_gold_per_10000{26}, terminal_top_per_10000{64};
    std::uint32_t terminals_enabled{1}, terminal_default_offers{5}, terminal_lifetime_days{7};
    std::uint32_t terminal_helper_enabled{1};
    std::uint32_t armory_rotation_enabled{1}, armory_rotation_seconds{900}, armory_rotation_slots{6};
    // Local Premier model is owned by the GSI bridge until native UI/server integration is verified.
    std::uint32_t premier_enabled{1}, premier_placement_wins{10}, premier_start_rating{1000};
    std::uint32_t premier_scoreboard{1}, premier_bot_badges{1};
    std::uint32_t level_drops_enabled{1}, level_drop_count{3};
    std::uint32_t skip_container_confirmation{1};
    std::uint32_t hide_rent_button{1};
    std::uint32_t armory_pity_enabled{1}, armory_pity_soft_at{10}, armory_pity_hard_at{100};
    std::uint32_t armory_top_per_10000{64};
    std::uint32_t premier_win_rating{300}, premier_loss_rating{100}, premier_max_rating{35000};
    std::uint32_t armory_howl_enabled{1}, armory_howl_star_price{40};
    std::uint32_t armory_rotation_enforce{0}; // enable after matching Panorama override is mounted
};
std::optional<GameplayConfig> ParseGameplayConfig(std::string_view text);
}
