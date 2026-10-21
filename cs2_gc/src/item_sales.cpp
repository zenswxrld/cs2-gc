#include "cs2_gc/item_sales.h"
#include <algorithm>
namespace cs2_gc {
std::uint32_t ItemSaleValue(const Schema &schema, const GameplayConfig &c, const InventoryItem &item)
{
    if (!c.item_sales_enabled || item.storedIn || item.casketCount || item.terminalRemaining || item.purchasePrice || item.expiration)
        return 0;
    const auto name = schema.ItemName(item.defIndex);
    if (name.empty() || name.starts_with("coupon")) return 0;
    const auto share = [](std::uint32_t price, std::uint32_t percent) {
        return price && percent ? static_cast<std::uint32_t>(std::max<std::uint64_t>(1, std::uint64_t{price} * percent / 100)) : 0u;
    };
    const std::uint32_t prices[] = {0, c.sell_consumer, c.sell_industrial, c.sell_mil_spec,
                                   c.sell_restricted, c.sell_classified, c.sell_covert};
    const auto rarity = item.rarity ? item.rarity : schema.ItemRarity(item.defIndex);
    const auto base = rarity < std::size(prices) ? prices[rarity] : 0;
    if (item.stickerKit || item.keychain) return share(base, c.sell_sticker_percent);
    if (name == "musickit") return c.sell_music_kit;
    const auto agents = schema.AgentDefinitions();
    if (std::find(agents.begin(), agents.end(), item.defIndex) != agents.end()) return share(c.armory_agent_price, c.sell_agent_percent);
    if (const auto crate = schema.FindCrate(item.defIndex))
    {
        if (crate->kind == CrateKind::Terminal) return 0;
        return share(crate->kind == CrateKind::Case ? 2u : 1u, c.sell_container_percent);
    }
    if (!name.starts_with("weapon_") && name.find("glove") == std::string::npos) return 0;
    if (item.unusual || schema.IsKnife(item.defIndex) || name.find("glove") != std::string::npos)
        return item.paintKitIndex || item.unusual ? c.sell_knife_glove : 0;
    return item.paintKitIndex ? base : 0;
}
}
