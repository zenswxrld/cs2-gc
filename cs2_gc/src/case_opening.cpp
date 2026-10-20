#include "cs2_gc/case_opening.h"
#include <vector>

namespace cs2_gc
{
namespace
{
constexpr std::uint32_t RarityMilSpec = 3, RarityRestricted = 4, RarityClassified = 5, RarityCovert = 6;

std::uint32_t WeightFor(std::uint32_t rarity, const CaseOdds &odds)
{
    switch (rarity)
    {
    case RarityMilSpec: return odds.milSpec;
    case RarityRestricted: return odds.restricted;
    case RarityClassified: return odds.classified;
    case RarityCovert: return odds.covert;
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

    struct Tier
    {
        std::uint32_t weight;
        std::vector<LootItem> items;
    };
    std::vector<Tier> tiers;
    std::uint64_t totalWeight = 0;
    for (const LootTier &tier : schema.LootTiers(crate->lootListName))
    {
        const std::uint32_t weight = WeightFor(tier.rarity, odds);
        Tier resolved{weight, {}};
        for (const std::string &entry : tier.items)
            if (auto item = schema.ResolveLootItem(entry))
                resolved.items.push_back(std::move(*item));
        if (weight == 0 || resolved.items.empty())
            continue;
        totalWeight += weight;
        tiers.push_back(std::move(resolved));
    }
    if (tiers.empty())
    {
        result.error = OpenError::EmptyLootList;
        return result;
    }

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
    item.paintKitIndex = drop.paintKitIndex;
    item.rarity = schema.SkinRarity(drop.weaponDefIndex, drop.paintKitIndex).value_or(0);
    item.wear = drop.wearMin + static_cast<float>(Below(random, 1u << 24)) / static_cast<float>(1u << 24) *
                                   (drop.wearMax - drop.wearMin);
    item.seed = static_cast<std::uint32_t>(Below(random, 1000)) + 1;
    item.statTrak = Below(random, 1000) < odds.statTrakPerMille;

    // Nothing above mutated the inventory; consume and grant together.
    inventory.Remove(crateId);
    inventory.Remove(keyId);
    item.id = inventory.Add(item);
    result.item = item;
    return result;
}
}
