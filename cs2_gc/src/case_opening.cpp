#include "cs2_gc/case_opening.h"
#include <algorithm>
#include <vector>

namespace cs2_gc
{
namespace
{
// Odds by tier position from the bottom: 0 -> milSpec, ... 3 -> covert; anything beyond has none.
std::uint32_t WeightForRank(std::size_t rank, const CaseOdds &odds)
{
    switch (rank)
    {
    case 0: return odds.milSpec;
    case 1: return odds.restricted;
    case 2: return odds.classified;
    case 3: return odds.covert;
    default: return 0;
    }
}

// Unbiased value in [0, bound) by rejection sampling.
std::uint64_t Below(const RandomSource &random, std::uint64_t bound)
{
    const std::uint64_t limit = UINT64_MAX - UINT64_MAX % bound;
    for (;;)
    {
        const std::uint64_t value = random();
        if (value < limit)
            return value % bound;
    }
}
}

std::optional<InventoryItem> RollLootList(const Schema &schema, std::string_view lootListName,
                                          const RandomSource &random, const CaseOdds &odds)
{
    struct Tier
    {
        std::uint32_t weight;
        std::uint32_t rarity;
        std::vector<LootItem> items;
    };

    // Rank tiers by rarity among the list's own tiers, before any are dropped for lack of items.
    std::vector<LootTier> listed = schema.LootTiers(lootListName);
    std::erase_if(listed, [](const LootTier &tier) { return tier.rarity == 0; });
    std::stable_sort(listed.begin(), listed.end(),
                     [](const LootTier &a, const LootTier &b) { return a.rarity < b.rarity; });

    std::vector<Tier> tiers;
    std::uint64_t totalWeight = 0;
    for (std::size_t rank = 0; rank < listed.size(); ++rank)
    {
        const std::uint32_t weight = WeightForRank(rank, odds);
        Tier resolved{weight, listed[rank].rarity, {}};
        for (const std::string &entry : listed[rank].items)
            if (auto item = schema.ResolveLootItem(entry))
                resolved.items.push_back(std::move(*item));
        if (weight == 0 || resolved.items.empty())
            continue;
        totalWeight += weight;
        tiers.push_back(std::move(resolved));
    }
    if (tiers.empty())
        return std::nullopt;

    std::uint64_t roll = Below(random, totalWeight);
    const Tier *chosen = &tiers.back();
    for (const Tier &tier : tiers)
    {
        if (roll < tier.weight)
        {
            chosen = &tier;
            break;
        }
        roll -= tier.weight;
    }

    const LootItem &drop = chosen->items[Below(random, chosen->items.size())];
    InventoryItem item;
    item.defIndex = drop.weaponDefIndex;
    item.rarity = chosen->rarity;
    switch (drop.kind)
    {
    case LootKind::Skin:
        item.paintKitIndex = drop.paintKitIndex;
        item.wear = drop.wearMin + static_cast<float>(Below(random, 1u << 24)) / static_cast<float>(1u << 24) *
                                       (drop.wearMax - drop.wearMin);
        item.seed = static_cast<std::uint32_t>(Below(random, 1000)) + 1;
        item.statTrak = Below(random, 1000) < odds.statTrakPerMille;
        break;
    case LootKind::Sticker:
        item.stickerKit = drop.stickerKitIndex;
        break;
    case LootKind::Keychain:
        item.keychain = drop.keychainIndex;
        break;
    }
    return item;
}

OpenResult OpenCase(Inventory &inventory, const Schema &schema, std::uint64_t crateId,
                    std::uint64_t keyId, const RandomSource &random, const CaseOdds &odds)
{
    OpenResult result;

    const InventoryItem *crateItem = inventory.Find(crateId);
    const CrateInfo *crate = crateItem ? schema.FindCrate(crateItem->defIndex) : nullptr;
    if (!crate || crate->kind != CrateKind::Case)
    {
        result.error = OpenError::NoSuchCrate;
        return result;
    }
    const InventoryItem *keyItem = inventory.Find(keyId);
    if (!keyItem)
    {
        result.error = OpenError::NoSuchKey;
        return result;
    }
    if (keyItem->defIndex != crate->keyDefIndex)
    {
        result.error = OpenError::WrongKey;
        return result;
    }

    auto rolled = RollLootList(schema, crate->lootListName, random, odds);
    if (!rolled)
    {
        result.error = OpenError::EmptyLootList;
        return result;
    }
    InventoryItem item = *rolled;

    // Nothing above mutated the inventory; consume and grant together.
    inventory.Remove(crateId);
    inventory.Remove(keyId);
    item.id = inventory.Add(item);
    result.item = item;
    return result;
}
}
