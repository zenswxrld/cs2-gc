#include "cs2_gc/item_sales.h"
#include <algorithm>
#include <cmath>
#include <map>
#include <vector>
#include "cs2_gc/case_opening.h"
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
    if (item.stickerKit)
    {
        const std::uint32_t stickers[] = {0, 0, 0, c.sell_sticker_mil_spec, c.sell_sticker_restricted, c.sell_sticker_classified, c.sell_sticker_covert};
        return rarity < std::size(stickers) ? std::min(stickers[rarity], base * c.sell_sticker_percent / 100) : 0;
    }
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

namespace cs2_gc
{
namespace
{
// Mirrored by tools/gameplay_config.py balance(); keep the arithmetic (and its order) identical.
constexpr std::uint32_t CaseWeights[] = {7992, 1598, 320, 64};                 // CaseOdds{} by tier rank
constexpr std::uint32_t CollectionWeights[] = {7992, 1598, 320, 64, 13, 3};   // Armory collection/souvenir odds

std::uint64_t Share(std::uint64_t value, std::uint64_t percent)
{
    return value && percent ? std::max<std::uint64_t>(1, value * percent / 100) : 0;
}

struct Wear
{
    bool enabled{};
    std::uint32_t high{100}, low{100}; // highest / lowest non-zero band percent
    std::uint64_t Out(std::uint64_t v) const { return enabled ? Share(v, high) : v; }
    std::uint64_t In(std::uint64_t v) const { return enabled ? Share(v, low) : v; }
};

// Average over ranks 0..count-1 of a loot list (rank weights `weights`); the top rank is pity-boosted to `hit`
// when `pity`, as Armory::Redeem rolls the top tier first and the rest without it.
double WindowValue(const std::uint64_t *values, const std::uint32_t *weights, std::size_t count, bool pity, double hit)
{
    double lower = 0, total = 0;
    const std::size_t plain = pity ? count - 1 : count;
    for (std::size_t rank = 0; rank < plain; ++rank)
    {
        lower += static_cast<double>(weights[rank]) * static_cast<double>(values[rank]);
        total += weights[rank];
    }
    lower = total > 0 ? lower / total : 0;
    return pity ? hit * static_cast<double>(values[count - 1]) + (1 - hit) * lower : lower;
}

double ArmoryHitRate(std::size_t count, const GameplayConfig &c)
{
    if (count < 2) return 1.0;
    std::uint64_t total = 0;
    for (std::size_t rank = 0; rank < count; ++rank) total += CollectionWeights[rank];
    auto pity = c;
    pity.pity_enabled = c.armory_pity_enabled;
    pity.pity_soft_at = c.armory_pity_soft_at;
    pity.pity_hard_at = c.armory_pity_hard_at;
    const auto base = std::max<std::uint64_t>(c.armory_top_per_10000, CollectionWeights[count - 1] * 10000 / total);
    return PityRate(static_cast<std::uint32_t>(base), pity);
}

bool Within(double value, std::uint32_t price, const GameplayConfig &c)
{
    return value * 100 <= static_cast<double>(c.sell_max_return_percent) * price;
}

// Best of `count` independent offers.
double BestOf(const std::vector<std::pair<double, std::uint64_t>> &offer, std::uint32_t count)
{
    std::map<std::uint64_t, double> merged;
    for (const auto &[p, v] : offer) merged[v] += p;
    double below = 0, result = 0;
    for (const auto &[v, p] : merged)
    {
        double lower = 1, upper = 1;
        for (std::uint32_t i = 0; i < count; ++i) { lower *= below; upper *= below + p; }
        result += static_cast<double>(v) * (upper - lower);
        below += p;
    }
    return result;
}

// Weapon skins (rarity 1..6) and knives/gloves: cases, terminals, collections and souvenir packages.
// Long-run pity rates, computed once per balance.
struct Rates
{
    double gold{}, terminalTop{}, armory[7]{};
    explicit Rates(const GameplayConfig &c) : gold(PityRate(c.case_gold_per_10000, c)), terminalTop(PityRate(c.terminal_top_per_10000, c))
    {
        for (std::size_t count = 1; count <= 6; ++count) armory[count] = ArmoryHitRate(count, c);
    }
};

bool WeaponsWithin(const std::uint64_t *w, std::uint64_t gold, const GameplayConfig &c, const Wear &wear, const Rates &rates)
{
    std::uint64_t o[7] = {};
    for (int t = 1; t <= 6; ++t) o[t] = wear.Out(w[t]);
    const auto og = wear.Out(gold);
    const double g = rates.gold;
    const std::uint64_t caseValues[] = {o[3], o[4], o[5], o[6]};
    if (!Within(g * static_cast<double>(og) + (1 - g) * WindowValue(caseValues, CaseWeights, 4, false, 0), c.armory_case_price, c))
        return false;
    if (c.terminals_enabled)
    {
        std::vector<std::pair<double, std::uint64_t>> offer{{g, og}};
        for (std::size_t rank = 0; rank < 4; ++rank) offer.emplace_back((1 - g) * CaseWeights[rank] / 9974.0, caseValues[rank]);
        if (!Within(BestOf(offer, c.terminal_default_offers), c.armory_terminal_price, c)) return false;
        const double h = rates.terminalTop;
        offer = {{h, o[6]}};
        for (std::size_t rank = 0; rank < 3; ++rank) offer.emplace_back((1 - h) * CaseWeights[rank] / 9910.0, caseValues[rank]);
        if (!Within(BestOf(offer, c.terminal_default_offers), c.armory_terminal_price, c)) return false;
    }
    // Collections and souvenir packages start at Consumer or Industrial grade and span at least three rarities
    // (installed lists: 1-3, 1-4, 1-5, 1-6, 2-4, 2-6); the top one is pity-boosted.
    for (int first = 1; first <= 2; ++first)
        for (int last = first + 2; last <= 6; ++last)
        {
            const std::size_t count = static_cast<std::size_t>(last - first + 1);
            std::uint64_t values[6] = {};
            for (std::size_t rank = 0; rank < count; ++rank) values[rank] = o[first + static_cast<int>(rank)];
            const double hit = rates.armory[count];
            if (!Within(WindowValue(values, CollectionWeights, count, true, hit), c.armory_souvenir_price, c)) return false;
            if (last == 6 && c.custom_collections) values[count - 1] = std::max(values[count - 1], og); // knife collections
            if (!Within(WindowValue(values, CollectionWeights, count, true, hit), ArmoryCollectionPrice, c)) return false;
        }
    return true;
}

// Largest v <= current whose wear-adjusted best sale stays within `limit` stars.
std::uint64_t CapOut(std::uint64_t current, std::uint64_t limit, const Wear &wear)
{
    if (!current) return 0;
    if (!limit) return 0;
    const std::uint64_t most = wear.enabled ? (wear.high ? ((limit + 1) * 100 - 1) / wear.high : current) : limit;
    return std::min(current, most);
}

// Stickers and charms at the row price. Sticker capsules/packs: every adjacent run of tiers (single tiers below
// the top too: some capsules are all Foil). Charm packs always start at Mil-Spec.
bool TiersWithin(const std::uint64_t *v, std::uint32_t price, int minimumRun, bool singles, const GameplayConfig &c, const Rates &rates)
{
    for (int first = 3; first <= (singles ? 6 : 3); ++first)
        for (int last = first; last <= 6; ++last)
        {
            const std::size_t count = static_cast<std::size_t>(last - first + 1);
            std::uint64_t values[4] = {};
            for (std::size_t rank = 0; rank < count; ++rank) values[rank] = v[first + static_cast<int>(rank)];
            const bool capsule = singles && (count > 1 || last < 6);
            if (capsule && !Within(WindowValue(values, CaseWeights, count, false, 0), price, c)) return false;
            if (static_cast<int>(count) >= minimumRun &&
                !Within(WindowValue(values, CollectionWeights, count, true, rates.armory[count]), price, c)) return false;
        }
    return true;
}

// Lowest tiers lose their resale first; returns the balanced values.
void ReduceTiers(std::uint64_t *v, std::uint32_t price, int minimumRun, bool singles, const GameplayConfig &c, const Rates &rates)
{
    for (int t = 3; t <= 6 && !TiersWithin(v, price, minimumRun, singles, c, rates); ++t)
    {
        std::uint64_t low = 0, high = v[t];
        v[t] = 0;
        if (!TiersWithin(v, price, minimumRun, singles, c, rates)) continue;
        while (low < high)
        {
            const auto middle = low + (high - low + 1) / 2;
            v[t] = middle;
            if (TiersWithin(v, price, minimumRun, singles, c, rates)) low = middle; else high = middle - 1;
        }
        v[t] = low;
    }
}
}

GameplayConfig BalancedDefaults()
{
    static const GameplayConfig defaults = [] { GameplayConfig config; BalanceSales(config); return config; }();
    return defaults;
}

void BalanceSales(GameplayConfig &c)
{
    Wear wear;
    wear.enabled = c.sell_wear_enabled != 0;
    if (wear.enabled)
    {
        const std::uint32_t bands[] = {c.sell_wear_fn, c.sell_wear_mw, c.sell_wear_ft, c.sell_wear_ww, c.sell_wear_bs};
        wear.high = 0; wear.low = 0;
        for (const auto band : bands)
        {
            wear.high = std::max(wear.high, band);
            if (band && (!wear.low || band < wear.low)) wear.low = band;
        }
    }
    const std::uint32_t r = c.sell_max_return_percent;
    const Rates rates(c);
    std::uint32_t *weapons[] = {nullptr, &c.sell_consumer, &c.sell_industrial, &c.sell_mil_spec, &c.sell_restricted,
                                &c.sell_classified, &c.sell_covert};
    // Weapons: one uniform scale keeps the configured shape; positive values keep at least one star so trade-up
    // inputs always have a price, then each tier is capped by the ten (five Covert) inputs it takes to make it.
    std::uint64_t w[7] = {}, gold = 0;
    bool balanced = false;
    for (std::uint64_t scale = 1000; !balanced; --scale)
    {
        for (int t = 1; t <= 6; ++t) w[t] = *weapons[t] ? std::max<std::uint64_t>(1, *weapons[t] * scale / 1000) : 0;
        gold = c.sell_knife_glove ? std::max<std::uint64_t>(1, c.sell_knife_glove * scale / 1000) : 0;
        for (int t = 1; t < 6; ++t)
            if (w[t] && w[t + 1]) w[t + 1] = CapOut(w[t + 1], r * 10 * wear.In(w[t]) / 100, wear);
        if (w[6]) gold = CapOut(gold, r * 5 * wear.In(w[6]) / 100, wear);
        balanced = WeaponsWithin(w, gold, c, wear, rates);
        if (!balanced && scale == 0)
        {
            std::fill(std::begin(w), std::end(w), 0);
            gold = 0;
            balanced = true;
        }
    }
    for (int t = 1; t <= 6; ++t) *weapons[t] = static_cast<std::uint32_t>(w[t]);
    c.sell_knife_glove = static_cast<std::uint32_t>(gold);

    // Stickers: their own table, never above sell_sticker_percent of the weapon value of their rarity.
    std::uint32_t *stickers[] = {nullptr, nullptr, nullptr, &c.sell_sticker_mil_spec, &c.sell_sticker_restricted,
                                 &c.sell_sticker_classified, &c.sell_sticker_covert};
    std::uint64_t s[7] = {};
    for (int t = 3; t <= 6; ++t) s[t] = std::min<std::uint64_t>(*stickers[t], w[t] * c.sell_sticker_percent / 100);
    ReduceTiers(s, ArmoryStickerPrice, 2, true, c, rates);
    for (int t = 3; t <= 6; ++t) *stickers[t] = static_cast<std::uint32_t>(s[t]);

    std::uint64_t charms[7] = {0, 0, 0, std::min(c.sell_charm_mil_spec, 2u), c.sell_charm_restricted, c.sell_charm_classified, c.sell_charm_covert};
    ReduceTiers(charms, ArmoryCharmPrice, 3, false, c, rates);
    c.sell_charm_mil_spec = static_cast<std::uint32_t>(charms[3]); c.sell_charm_restricted = static_cast<std::uint32_t>(charms[4]);
    c.sell_charm_classified = static_cast<std::uint32_t>(charms[5]); c.sell_charm_covert = static_cast<std::uint32_t>(charms[6]);

    // Agents are a fixed price: never more than the return limit of it.
    c.sell_agent_percent = std::min(c.sell_agent_percent, r);
    while (c.sell_agent_percent && Share(c.armory_agent_price, c.sell_agent_percent) * 100 > std::uint64_t{r} * c.armory_agent_price)
        --c.sell_agent_percent;
    // A weapon case bought in the Armory may be sold unopened.
    while (c.sell_container_percent && Share(2, c.sell_container_percent) * 100 > std::uint64_t{r} * c.armory_case_price)
        --c.sell_container_percent;
}
}
