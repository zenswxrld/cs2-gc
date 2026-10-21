#include "cs2_gc/item_sales.h"
#include <algorithm>
#include <cmath>
namespace cs2_gc {
std::uint32_t ItemSaleValue(const Schema &schema, const GameplayConfig &c, const InventoryItem &item)
{
    if (!c.item_sales_enabled || item.noStarSale || item.storedIn || item.casketCount || item.terminalRemaining || item.purchasePrice || item.expiration)
        return 0;
    for (const auto &crate:schema.Crates())
        if (crate.keyDefIndex && crate.keyDefIndex==item.defIndex) return 5;
    const auto name = schema.ItemName(item.defIndex);
    if (name.empty() || name.starts_with("coupon")) return 0;
    const auto share = [](std::uint32_t price, std::uint32_t percent) {
        return price && percent ? static_cast<std::uint32_t>(std::max<std::uint64_t>(1, std::uint64_t{price} * percent / 100)) : 0u;
    };
    const std::uint32_t prices[] = {0, c.sell_consumer, c.sell_industrial, c.sell_mil_spec,
                                   c.sell_restricted, c.sell_classified, c.sell_covert};
    const auto rarity = item.rarity ? item.rarity : schema.ItemRarity(item.defIndex);
    const auto base = rarity < std::size(prices) ? prices[rarity] : 0;
    if (item.keychain)
    {
        const std::uint32_t charms[] = {0,0,0,std::min(c.sell_charm_mil_spec,2u),c.sell_charm_restricted,
                                        c.sell_charm_classified,c.sell_charm_covert};
        return rarity<std::size(charms)?charms[rarity]:0;
    }
    if (item.stickerKit) return share(base, c.sell_sticker_percent);
    if (name == "musickit") return c.sell_music_kit;
    const auto agents = schema.AgentDefinitions();
    if (std::find(agents.begin(), agents.end(), item.defIndex) != agents.end()) return share(c.armory_agent_price, c.sell_agent_percent);
    if (const auto crate = schema.FindCrate(item.defIndex))
    {
        if (crate->kind == CrateKind::Terminal) return 0;
        return share(crate->kind == CrateKind::Case ? 2u : 1u, c.sell_container_percent);
    }
    if (!name.starts_with("weapon_") && !schema.IsGlove(item.defIndex)) return 0;
    auto value = item.unusual || schema.IsKnife(item.defIndex) || schema.IsGlove(item.defIndex) ?
        (item.paintKitIndex || item.unusual ? c.sell_knife_glove : 0u) : (item.paintKitIndex ? base : 0u);
    if (value && c.sell_wear_enabled && item.paintKitIndex)
    {
        if (!std::isfinite(item.wear) || item.wear<0 || item.wear>1) return 0;
        const auto percent = item.wear<.07f?c.sell_wear_fn:item.wear<.15f?c.sell_wear_mw:
            item.wear<.38f?c.sell_wear_ft:item.wear<.45f?c.sell_wear_ww:c.sell_wear_bs;
        value=share(value,percent);
    }
    // A guaranteed fixed Armory skin must never immediately resell above its purchase price.
    for (const auto &good:schema.ArmoryRedeemables())
    {
        constexpr std::string_view prefix="lootlist:";
        if (good.rotationSlot!="limited" || !good.itemName.starts_with(prefix)) continue;
        std::vector<LootItem> outcomes;
        for(const auto &tier:schema.LootTiers(good.itemName.substr(prefix.size())))
            for(const auto &entry:tier.items)
                if(auto loot=schema.ResolveLootItem(entry))outcomes.push_back(*loot);
        if(outcomes.size()==1 && outcomes[0].weaponDefIndex==item.defIndex && outcomes[0].paintKitIndex==item.paintKitIndex)
            value=std::min(value,good.points?good.points-1:0u);
    }
    return value;
}
}
