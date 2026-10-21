#pragma once
#include <cstdint>
#include <optional>
#include <string_view>

namespace cs2_gc
{
// Runtime policy only: inventory balances/counters remain in the saved inventory.
struct GameplayConfig
{
    std::uint32_t armory_collection_slots{3};
    std::uint32_t armory_charm_slots{2};
    std::uint32_t free_case_keys{1}, skip_key_selection{1};
    std::uint32_t knife_finishes{1}, glove_finishes{1}, custom_skins_test{1}, custom_collections{0}, custom_cases{1}, glove_panel_variants{1}, black_market_price{100};
    std::uint32_t viewmodel_range_percent{250}, viewmodel_fov_min{40}, viewmodel_fov_max{90}; // wider viewmodel limits // knife recolours + Black Market Case (helper-generated) // keep one never-consumed key for every case type owned
    std::uint32_t armory_sticker_slots{2};
    std::uint32_t armory_case_slots{2};
    std::uint32_t armory_capsule_slots{2};
    std::uint32_t armory_limited_slots{1};
    std::uint32_t armory_agent_slots{1};
    std::uint32_t armory_agent_price{50};
    std::uint32_t reward_rare_case_per_10000{100}; // combined Black Market/Gauntlet chance within case offers
    std::uint32_t custom_collection_drop_percent{15}; // within weapon reward slots; never changes case chance
    std::uint32_t care_packages_enabled{1}; // four reserved offers, claim exactly three
    std::uint32_t bot_hide_tag{1}, hide_mainmenu_promo{1}, offline_mission_launch{1};
    std::uint32_t armory_souvenir_slots{1}, armory_souvenir_price{5};
    std::uint32_t armory_terminal_slots{1};
    std::uint32_t armory_terminal_price{10}, armory_case_price{5};
    std::uint32_t match_weekly_pool_only{1};
    std::uint32_t item_sales_enabled{1};
    std::uint32_t sell_consumer{1};
    std::uint32_t sell_industrial{2};
    std::uint32_t sell_mil_spec{5};
    std::uint32_t sell_restricted{10};
    std::uint32_t sell_classified{25};
    std::uint32_t sell_covert{50};
    std::uint32_t sell_knife_glove{72};
    std::uint32_t sell_sticker_percent{50};
    std::uint32_t sell_charm_mil_spec{1}, sell_charm_restricted{3}, sell_charm_classified{9}, sell_charm_covert{25};
    std::uint32_t sell_wear_enabled{1}, sell_wear_fn{125}, sell_wear_mw{110}, sell_wear_ft{100}, sell_wear_ww{80}, sell_wear_bs{60};
    std::uint32_t sell_music_kit{10};
    std::uint32_t sell_container_percent{30};
    std::uint32_t sell_agent_percent{50};
    std::uint32_t premier_rating_variation{79};
    std::uint32_t premier_bot_spread{1200};
    std::uint32_t end_match_screens{1};
    std::uint32_t end_match_duration{20};
    std::uint32_t match_end_delay{45};
    std::uint32_t rewards_auto_start{1};
    std::uint32_t xp_enabled{1}, stars_enabled{1};
    std::uint32_t armory_xp_per_star{400};
    std::uint32_t kill_xp{5}, headshot_xp{3}, mvp_xp{25}, match_complete_xp{600};
    std::uint32_t match_drops_enabled{1}, match_drop_count{3}, match_case_percent{50}, match_skin_min_rarity{3};
    std::uint32_t mixed_stattrak_tradeups{1};
    std::uint32_t souvenir_tradeups{1};
    std::uint32_t pity_enabled{1}, pity_soft_at{10}, pity_hard_at{100};
    std::uint32_t case_gold_per_10000{26}, terminal_top_per_10000{64};
    std::uint32_t terminals_enabled{1}, terminal_default_offers{5}, terminal_lifetime_days{7};
    std::uint32_t terminal_helper_enabled{1};
    std::uint32_t armory_rotation_enabled{1}, armory_rotation_seconds{900}, armory_rotation_slots{6};
    // Local Premier model is owned by the GSI bridge until native UI/server integration is verified.
    std::uint32_t premier_enabled{1}, premier_placement_wins{10}, premier_start_rating{1000};
    std::uint32_t premier_scoreboard{1}, premier_bot_badges{1};
    std::uint32_t bot_fake_ping{1}, bot_random_names{1}; // native UI/bot profile overrides prepared by the helper
    std::uint32_t level_drops_enabled{1}, level_drop_count{3};
    std::uint32_t skip_container_confirmation{1};
    std::uint32_t hide_rent_button{1};
    std::uint32_t armory_pity_enabled{1}, armory_pity_soft_at{10}, armory_pity_hard_at{100};
    std::uint32_t armory_top_per_10000{64};
    std::uint32_t premier_win_rating{300}, premier_loss_rating{100}, premier_max_rating{35000};
    std::uint32_t premier_bonus_wins{0}; // total extra placement wins the helper grants once; never removed
    std::uint32_t armory_howl_enabled{1}, armory_howl_star_price{250};
    std::uint32_t armory_rotation_enforce{0}; // enable after matching Panorama override is mounted
};
std::optional<GameplayConfig> ParseGameplayConfig(std::string_view text);
}
