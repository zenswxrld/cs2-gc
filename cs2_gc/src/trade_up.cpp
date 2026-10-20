#include "cs2_gc/trade_up.h"
#include <algorithm>
#include <map>
#include <set>

namespace cs2_gc
{
namespace
{
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

constexpr std::uint32_t Covert = 6;
}

const char *TradeUpErrorText(TradeUpError error)
{
    switch (error)
    {
    case TradeUpError::None: return "success";
    case TradeUpError::WrongCount: return "expected ten skins, or five Covert skins";
    case TradeUpError::UnknownItem: return "unknown, duplicate or stored item";
    case TradeUpError::NotASkin: return "missing weapon finish or rarity";
    case TradeUpError::MixedRarity: return "mixed skin rarities";
    case TradeUpError::TopRarity: return "unsupported input rarity";
    case TradeUpError::MixedStatTrak: return "mixed StatTrak and normal skins";
    case TradeUpError::NoCollection: return "skin has no collection in items_game.txt";
    case TradeUpError::NoOutcome: return "collection has no supported next-rarity outcome";
    }
    return "unknown error";
}

TradeUpResult TradeUp(Inventory &inventory, const Schema &schema, const std::vector<std::uint64_t> &itemIds,
                      const RandomSource &random)
{
    TradeUpResult result;
    const auto fail = [&result](TradeUpError error) {
        result.error = error;
        return result;
    };
    if (itemIds.size() != TradeUpItemCount && itemIds.size() != 5)
        return fail(TradeUpError::WrongCount);

    std::set<std::uint64_t> seen;
    std::vector<const InventoryItem *> inputs;
    for (const std::uint64_t id : itemIds)
    {
        const InventoryItem *item = inventory.Find(id);
        if (!item || item->storedIn || !seen.insert(id).second)
            return fail(TradeUpError::UnknownItem);
        inputs.push_back(item);
    }

    std::uint32_t rarity = 0;
    float totalWear = 0.0f;
    std::map<std::string, std::uint32_t> supplied; // collection -> how many of the ten it supplies
    for (const InventoryItem *item : inputs)
    {
        if (item->paintKitIndex == 0)
            return fail(TradeUpError::NotASkin);
        const auto skinRarity = schema.SkinRarity(item->defIndex, item->paintKitIndex);
        if (!skinRarity)
            return fail(TradeUpError::NotASkin);
        if (rarity == 0)
            rarity = *skinRarity;
        else if (*skinRarity != rarity)
            return fail(TradeUpError::MixedRarity);
        if (item->statTrak != inputs.front()->statTrak)
            return fail(TradeUpError::MixedStatTrak);
        const auto collections = schema.CollectionsOf(item->defIndex, item->paintKitIndex);
        if (collections.empty())
            return fail(TradeUpError::NoCollection);
        ++supplied[collections.front()];
        totalWear += item->wear;
    }
    if ((rarity == Covert && itemIds.size() != 5) || (rarity != Covert && itemIds.size() != TradeUpItemCount))
        return fail(TradeUpError::WrongCount);
    if (rarity > Covert)
        return fail(TradeUpError::TopRarity);

    // For every collection that supplied inputs, its skins of the next rarity.
    struct Pool
    {
        std::uint32_t weight;
        std::vector<SkinRef> skins;
    };
    std::vector<Pool> pools;
    std::uint64_t totalWeight = 0;
    for (const auto &[collection, count] : supplied)
    {
        Pool pool{count, {}};
        if (rarity == Covert)
            pool.skins = schema.GoldOutcomes(collection, inputs.front()->statTrak);
        else
            for (const SkinRef &skin : schema.CollectionSkins(collection))
                if (schema.SkinRarity(skin.weaponDefIndex, skin.paintKitIndex) == rarity + 1)
                    pool.skins.push_back(skin);
        if (pool.skins.empty())
            return fail(TradeUpError::NoOutcome);
        totalWeight += pool.weight;
        pools.push_back(std::move(pool));
    }
    if (pools.empty())
        return fail(TradeUpError::NoOutcome);

    std::uint64_t roll = Below(random, totalWeight);
    const Pool *chosen = &pools.back();
    for (const Pool &pool : pools)
    {
        if (roll < pool.weight)
        {
            chosen = &pool;
            break;
        }
        roll -= pool.weight;
    }
    const SkinRef &outcome = chosen->skins[Below(random, chosen->skins.size())];
    const auto minted = schema.SkinAsLootItem(outcome.weaponDefIndex, outcome.paintKitIndex);
    if (!minted)
        return fail(TradeUpError::NoOutcome);

    InventoryItem item;
    item.defIndex = outcome.weaponDefIndex;
    item.paintKitIndex = outcome.paintKitIndex;
    item.rarity = rarity == Covert ? Covert : rarity + 1;
    item.statTrak = inputs.front()->statTrak;
    item.unusual = rarity == Covert;
    item.seed = static_cast<std::uint32_t>(Below(random, 1000)) + 1;
    const float average = totalWear / static_cast<float>(itemIds.size());
    item.wear = outcome.paintKitIndex ? std::clamp(minted->wearMin + average * (minted->wearMax - minted->wearMin), 0.0f, 1.0f) : 0.0f;

    // Nothing above changed the inventory; consume and grant together.
    for (const InventoryItem *input : inputs)
        result.consumed.push_back(*input);
    for (const std::uint64_t id : itemIds)
        inventory.Remove(id);
    item.id = inventory.Add(item);
    result.item = item;
    return result;
}
}
