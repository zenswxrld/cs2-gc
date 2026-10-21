#include "cs2_gc/trade_up.h"
#include <algorithm>
#include <map>
#include <set>
#include <charconv>

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

std::optional<LocalTradeUpRequest> DecodeLocalTradeUpRequest(std::string_view text)
{
    if (text.size() > 512)
        return std::nullopt;
    const auto split = text.find(' ');
    if (split != 32 || text.substr(0, split).find_first_not_of("0123456789abcdef") != std::string_view::npos)
        return std::nullopt;
    LocalTradeUpRequest request;
    request.token = text.substr(0, split);
    text.remove_prefix(split + 1);
    while (!text.empty())
    {
        const auto end = text.find(' ');
        const auto word = text.substr(0, end);
        std::uint64_t id = 0;
        const auto [last, ec] = std::from_chars(word.data(), word.data() + word.size(), id);
        if (ec != std::errc{} || last != word.data() + word.size() || !id || request.itemIds.size() == 10)
            return std::nullopt;
        request.itemIds.push_back(id);
        if (end == std::string_view::npos)
            break;
        text.remove_prefix(end + 1);
        if (text.empty())
            return std::nullopt;
    }
    if (request.itemIds.size() != 5 && request.itemIds.size() != 10)
        return std::nullopt;
    return request;
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
    case TradeUpError::MixedSouvenir: return "Souvenir contracts require only Souvenir weapons without StatTrak";
    case TradeUpError::SouvenirDisabled: return "local Souvenir contracts are disabled";
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
    std::uint32_t statTrakCount = 0;
    std::uint32_t souvenirCount = 0;
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
        statTrakCount += item->statTrak;
        souvenirCount += item->souvenir;
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
    if (souvenirCount)
    {
        if (!inventory.Gameplay().souvenir_tradeups) return fail(TradeUpError::SouvenirDisabled);
        if (souvenirCount != itemIds.size() || statTrakCount) return fail(TradeUpError::MixedSouvenir);
        if (rarity == Covert) return fail(TradeUpError::NoOutcome);
    }
    // Exact input fraction, with no random draw at the 0% and 100% endpoints.
    if (!inventory.Gameplay().mixed_stattrak_tradeups && statTrakCount && statTrakCount != itemIds.size())
        return fail(TradeUpError::MixedStatTrak);
    bool outputStatTrak = statTrakCount == itemIds.size() ||
                          (statTrakCount && Below(random, itemIds.size()) < statTrakCount);

    // For every collection that supplied inputs, its skins of the next rarity.
    struct Pool
    {
        std::uint32_t weight;
        std::vector<SkinRef> skins;
        std::string collection;
    };
    std::vector<Pool> pools;
    std::uint64_t totalWeight = 0;
    for (const auto &[collection, count] : supplied)
    {
        Pool pool{count, {}, collection};
        if (rarity == Covert)
            pool.skins = schema.GoldOutcomes(collection, false);
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

    if (rarity == Covert && outputStatTrak)
    {
        auto knifePools = pools;
        std::uint64_t knifeWeight = 0;
        for (auto &pool : knifePools)
        {
            std::erase_if(pool.skins, [&schema](const SkinRef &skin) { return !schema.IsKnife(skin.weaponDefIndex); });
            if (!pool.skins.empty())
                knifeWeight += pool.weight;
        }
        std::erase_if(knifePools, [](const Pool &pool) { return pool.skins.empty(); });
        if (knifePools.empty())
        {
            if (statTrakCount == itemIds.size())
                return fail(TradeUpError::NoOutcome);
            outputStatTrak = false; // mixed glove-only inputs have no possible StatTrak output
        }
        else
        {
            pools = std::move(knifePools);
            totalWeight = knifeWeight;
        }
    }

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
    item.statTrak = outputStatTrak;
    item.statTrakFromContract = outputStatTrak;
    item.unusual = rarity == Covert;
    item.noStarSale = std::any_of(inputs.begin(), inputs.end(), [](const auto *input) { return input->noStarSale; });
    if (souvenirCount)
    {
        std::vector<const InventoryItem *> donors;
        for (const auto *input : inputs)
            if (schema.CollectionsOf(input->defIndex,input->paintKitIndex).front() == chosen->collection)
                donors.push_back(input);
        const auto *donor = donors[Below(random,donors.size())];
        item.souvenir = true;
        item.tournamentEvent = donor->tournamentEvent;
        item.tournamentTeam0 = donor->tournamentTeam0;
        item.tournamentTeam1 = donor->tournamentTeam1;
        item.tournamentPlayer = donor->tournamentPlayer;
    }
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
