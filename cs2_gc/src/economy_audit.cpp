#include "cs2_gc/economy_audit.h"
#include "cs2_gc/item_sales.h"
#include <algorithm>
#include <array>
#include <map>
#include <set>
#include <tuple>

namespace cs2_gc
{
namespace
{
using Distribution = std::vector<std::pair<double, double>>; // (probability, stars)
constexpr std::string_view LootListPrefix = "lootlist:";
constexpr std::array<float, 6> WearEdges{0.0f, .07f, .15f, .38f, .45f, 1.0f};

double Mean(const Distribution &d)
{
    double sum = 0;
    for (const auto &[p, v] : d) sum += p * v;
    return sum;
}

double Best(const Distribution &d)
{
    double best = 0;
    for (const auto &[p, v] : d) if (p > 0) best = std::max(best, v);
    return best;
}

void Append(Distribution &out, const Distribution &in, double weight)
{
    for (const auto &[p, v] : in) out.emplace_back(p * weight, v);
}

// ItemSaleValue is exact but slow (it scans agents and fixed rows); results only depend on these fields and the wear band.
class Seller
{
public:
    Seller(const Schema &schema, const GameplayConfig &config) : m_schema(schema), m_config(config) {}
    double operator()(const InventoryItem &item)
    {
        std::size_t band = 0;
        while (band < 4 && item.wear >= WearEdges[band + 1]) ++band;
        const auto key = std::make_tuple(item.defIndex, item.paintKitIndex, item.stickerKit, item.keychain, item.musicKit,
                                         item.rarity, item.unusual, item.paintKitIndex ? band : 0u);
        const auto found = m_cache.find(key);
        if (found != m_cache.end()) return found->second;
        return m_cache[key] = ItemSaleValue(m_schema, m_config, item);
    }
private:
    const Schema &m_schema;
    const GameplayConfig &m_config;
    std::map<std::tuple<std::uint32_t, std::uint32_t, std::uint32_t, std::uint32_t, std::uint32_t, std::uint32_t, bool, std::size_t>, double> m_cache;
};

// One rolled loot entry: wear is uniform in the finish's range, and sale value only depends on its wear band.
Distribution ItemOutcomes(Seller &sell, const LootItem &loot,
                          std::uint32_t rarity, bool unusual)
{
    InventoryItem item;
    item.defIndex = loot.weaponDefIndex;
    item.rarity = rarity;
    item.unusual = unusual;
    switch (loot.kind)
    {
    case LootKind::Skin: item.paintKitIndex = loot.paintKitIndex; break;
    case LootKind::Sticker: item.stickerKit = loot.stickerKitIndex; break;
    case LootKind::Keychain: item.keychain = loot.keychainIndex; break;
    case LootKind::MusicKit: item.musicKit = loot.musicKitIndex; break;
    case LootKind::Plain: break;
    }
    Distribution out;
    const float low = std::clamp(loot.wearMin, 0.0f, 1.0f), high = std::clamp(loot.wearMax, low, 1.0f);
    if (!item.paintKitIndex || high <= low)
    {
        item.wear = item.paintKitIndex ? low : 0.0f;
        out.emplace_back(1.0, sell(item));
        return out;
    }
    for (std::size_t band = 0; band + 1 < WearEdges.size(); ++band)
    {
        const float from = std::max(low, WearEdges[band]), to = std::min(high, WearEdges[band + 1]);
        if (to <= from) continue;
        item.wear = (from + to) / 2;
        out.emplace_back((to - from) / (high - low), sell(item));
    }
    return out;
}

Distribution Uniform(const Schema &schema, Seller &sell, const std::vector<LootItem> &items,
                     std::uint32_t rarity, bool unusual)
{
    Distribution out;
    for (const auto &item : items)
        Append(out, ItemOutcomes(sell, item, rarity, unusual || schema.IsKnife(item.weaponDefIndex) ||
                                 schema.IsGlove(item.weaponDefIndex)), 1.0 / static_cast<double>(items.size()));
    return out;
}

std::uint32_t RankWeight(std::size_t rank, const CaseOdds &odds)
{
    const std::uint32_t weights[] = {odds.milSpec, odds.restricted, odds.classified, odds.covert, odds.fifthTier, odds.sixthTier};
    return rank < std::size(weights) ? weights[rank] : 0;
}

template <typename Keep>
std::vector<LootItem> Resolve(const Schema &schema, const LootTier &tier, Keep keep)
{
    std::vector<LootItem> out;
    for (const auto &entry : tier.items)
        if (auto item = schema.ResolveLootItem(entry))
            if (keep(*item)) out.push_back(*item);
    return out;
}

// RollLootList's exact tier odds (ranks by rarity among the listed tiers; empty/zero-weight tiers renormalised).
template <typename Keep>
Distribution RollOutcomes(const Schema &schema, Seller &sell, std::string_view list, const CaseOdds &odds,
                          std::uint32_t excluded, Keep keep, bool unusual = false)
{
    auto tiers = schema.LootTiers(list);
    std::erase_if(tiers, [](const LootTier &tier) { return tier.rarity == 0; });
    std::stable_sort(tiers.begin(), tiers.end(), [](const auto &a, const auto &b) { return a.rarity < b.rarity; });
    std::vector<std::pair<double, Distribution>> parts;
    double total = 0;
    for (std::size_t rank = 0; rank < tiers.size(); ++rank)
    {
        if (excluded && tiers[rank].rarity == excluded) continue;
        const auto weight = RankWeight(rank, odds);
        const auto items = Resolve(schema, tiers[rank], [](const LootItem &) { return true; });
        if (!weight || items.empty()) continue;
        // A roll that lands on an item `keep` rejects grants nothing and charges nothing (Black Market).
        std::vector<LootItem> kept;
        for (const auto &item : items) if (keep(item)) kept.push_back(item);
        const double share = static_cast<double>(kept.size()) / static_cast<double>(items.size());
        total += weight * share;
        if (!kept.empty()) parts.emplace_back(weight * share, Uniform(schema, sell, kept, tiers[rank].rarity, unusual));
    }
    Distribution out;
    for (const auto &[weight, outcomes] : parts) Append(out, outcomes, weight / total);
    return out;
}

Distribution Distinct(Distribution d)
{
    std::map<double, double> merged;
    for (const auto &[p, v] : d) merged[v] += p;
    Distribution out;
    for (const auto &[v, p] : merged) out.emplace_back(p, v);
    return out;
}

// The best of `count` independent offers.
Distribution MaxOf(const Distribution &single, std::uint32_t count)
{
    const auto merged = Distinct(single);
    Distribution out;
    double below = 0;
    for (const auto &[p, v] : merged)
    {
        double lower = 1, upper = 1;
        for (std::uint32_t i = 0; i < count; ++i) { lower *= below; upper *= below + p; }
        out.emplace_back(upper - lower, v);
        below += p;
    }
    return out;
}

bool AnySkin(const LootItem &) { return true; }

EconomyPath Path(std::string name, std::string kind, double cost, const Distribution &d)
{
    EconomyPath path{std::move(name), std::move(kind), cost, Mean(d), Best(d), false};
    return path;
}
}

std::vector<EconomyPath> AuditEconomy(const Schema &schema, const GameplayConfig &config, const CaseOdds &odds)
{
    std::vector<EconomyPath> paths;
    Seller sell(schema, config);
    // Weapon cases: sold unopened, or opened (free key) with the shared gold pity.
    const auto openCase = [&](const CrateInfo &crate) {
        auto caseOdds = odds;
        if (schema.ProducesStatTrak(crate.defIndex)) caseOdds.statTrakPerMille = 1000;
        Distribution d;
        const auto golds = schema.CrateGoldOutcomes(crate.defIndex);
        const double gold = golds.empty() ? 0.0 : PityRate(config.case_gold_per_10000, config);
        if (gold > 0)
        {
            std::vector<LootItem> items;
            for (const auto &skin : golds)
                if (auto loot = schema.SkinAsLootItem(skin.weaponDefIndex, skin.paintKitIndex)) items.push_back(*loot);
            if (!items.empty()) Append(d, Uniform(schema, sell, items, 6, true), gold);
        }
        Append(d, RollOutcomes(schema, sell, crate.lootListName, caseOdds, 0, AnySkin), 1.0 - gold);
        return d;
    };
    for (const auto &good : schema.ArmoryRedeemables())
    {
        const double cost = good.points;
        const auto definition = schema.ItemDefIndex(good.itemName);
        const auto *crate = definition ? schema.FindCrate(*definition) : nullptr;
        const std::string list = good.itemName.starts_with(LootListPrefix) ? good.itemName.substr(LootListPrefix.size()) : std::string{};
        Distribution d;
        bool deterministic = false;
        if (good.rotationSlot == "agent")
        {
            InventoryItem agent;
            const auto agents = schema.AgentDefinitions();
            if (agents.empty()) continue;
            for (const auto definitionIndex : agents)
            {
                agent.defIndex = definitionIndex;
                agent.rarity = schema.ItemRarity(definitionIndex);
                d.emplace_back(1.0 / agents.size(), sell(agent));
            }
        }
        else if (good.itemName == "crate_cs2gc_black_market" || good.itemName == "crate_cs2gc_gauntlet")
        {
            if (!crate) continue;
            const bool gloves = good.itemName == "crate_cs2gc_gauntlet";
            d = RollOutcomes(schema, sell, crate->lootListName, odds, 0, [&](const LootItem &item) {
                return gloves ? schema.IsGlove(item.weaponDefIndex) : schema.IsKnife(item.weaponDefIndex);
            }, true);
        }
        else if (good.rotationSlot == "limited" && !list.empty())
        {
            std::vector<LootItem> fixed;
            for (const auto &tier : schema.LootTiers(list))
                for (auto &item : Resolve(schema, tier, AnySkin)) fixed.push_back(item);
            if (fixed.size() != 1 || fixed.front().kind != LootKind::Skin) continue;
            const auto rarity = schema.SkinRarity(fixed.front().weaponDefIndex, fixed.front().paintKitIndex);
            if (!rarity) continue;
            d = ItemOutcomes(sell, fixed.front(), *rarity, false);
            deterministic = true;
        }
        else if (!list.empty() || good.rotationSlot == "souvenir")
        {
            CaseOdds collection = odds;
            collection.statTrakPerMille = 0; collection.fifthTier = 13; collection.sixthTier = 3;
            const auto *souvenir = good.rotationSlot == "souvenir" ? crate : nullptr;
            if (good.rotationSlot == "souvenir" && !souvenir) continue;
            const std::string name = souvenir ? souvenir->lootListName : list;
            const auto keep = [&](const LootItem &item) {
                return !souvenir || (item.kind == LootKind::Skin && !schema.IsKnife(item.weaponDefIndex) && !schema.IsGlove(item.weaponDefIndex));
            };
            auto tiers = schema.LootTiers(name);
            std::erase_if(tiers, [](const auto &tier) { return tier.rarity == 0; });
            std::stable_sort(tiers.begin(), tiers.end(), [](const auto &a, const auto &b) { return a.rarity < b.rarity; });
            std::uint64_t total = 0, topWeight = 0;
            std::uint32_t highest = 0;
            std::vector<LootItem> top;
            bool lower = false;
            for (std::size_t rank = 0; rank < tiers.size() && rank < 6; ++rank)
            {
                auto items = Resolve(schema, tiers[rank], keep);
                const auto weight = RankWeight(rank, collection);
                if (items.empty() || !weight) continue;
                total += weight;
                if (tiers[rank].rarity > highest)
                {
                    lower = highest != 0;
                    highest = tiers[rank].rarity; top = std::move(items); topWeight = weight;
                }
                else if (tiers[rank].rarity == highest)
                {
                    top.insert(top.end(), items.begin(), items.end()); topWeight += weight;
                }
            }
            if (!total || top.empty()) continue;
            auto pity = config;
            pity.pity_enabled = config.armory_pity_enabled;
            pity.pity_soft_at = config.armory_pity_soft_at; pity.pity_hard_at = config.armory_pity_hard_at;
            const auto base = std::max(config.armory_top_per_10000, static_cast<std::uint32_t>(topWeight * 10000 / total));
            const double hit = lower ? PityRate(base, pity) : 1.0;
            Append(d, Uniform(schema, sell, top, highest, false), hit);
            if (hit < 1) Append(d, RollOutcomes(schema, sell, name, collection, highest, keep), 1.0 - hit);
            deterministic = top.size() == 1 && !lower;
        }
        else if (good.rotationSlot == "capsule" && crate && !crate->lootListName.empty())
        {
            auto capsule = odds;
            capsule.statTrakPerMille = 0;
            d = RollOutcomes(schema, sell, crate->lootListName, capsule, 0, AnySkin);
        }
        else if (crate && crate->kind == CrateKind::Case)
        {
            // An Armory case stays a crate: sell it as it is, or open it with the free key.
            InventoryItem plain;
            plain.defIndex = crate->defIndex;
            plain.rarity = schema.ItemRarity(crate->defIndex);
            paths.push_back(Path("sell:" + good.itemName, "case-sell", cost, {{1.0, double(sell(plain))}}));
            paths.back().deterministic = true;
            if (config.free_case_keys)
                paths.push_back(Path("open:" + good.itemName, "case-open", cost, openCase(*crate)));
            continue;
        }
        else if (crate && crate->kind == CrateKind::Terminal)
        {
            if (!config.terminals_enabled) continue;
            const auto golds = schema.CrateGoldOutcomes(crate->defIndex);
            std::uint32_t highest = 0;
            std::vector<LootItem> top;
            bool lowerTier = false;
            for (const auto &tier : schema.LootTiers(crate->lootListName))
            {
                if (!tier.rarity || tier.rarity > 6) continue;
                for (const auto &item : Resolve(schema, tier, AnySkin))
                {
                    if (tier.rarity > highest) { lowerTier = highest != 0; highest = tier.rarity; top.clear(); }
                    if (tier.rarity == highest) top.push_back(item); else lowerTier = true;
                }
            }
            const double hit = golds.empty() && !lowerTier ? 1.0 :
                PityRate(golds.empty() ? config.terminal_top_per_10000 : config.case_gold_per_10000, config);
            Distribution offer;
            if (!golds.empty())
            {
                std::vector<LootItem> items;
                for (const auto &skin : golds)
                    if (auto loot = schema.SkinAsLootItem(skin.weaponDefIndex, skin.paintKitIndex)) items.push_back(*loot);
                Append(offer, Uniform(schema, sell, items, 6, true), hit);
            }
            else Append(offer, Uniform(schema, sell, top, highest, false), hit);
            auto terminalOdds = odds;
            terminalOdds.statTrakPerMille = 0;
            if (hit < 1) Append(offer, RollOutcomes(schema, sell, crate->lootListName, terminalOdds, golds.empty() ? highest : 0, AnySkin), 1 - hit);
            // The player keeps the best of the offers; accepting one is free.
            d = MaxOf(offer, config.terminal_default_offers);
        }
        else if (definition)
        {
            InventoryItem plain;
            plain.defIndex = *definition;
            plain.rarity = schema.ItemRarity(*definition);
            d.emplace_back(1.0, sell(plain));
            deterministic = true;
        }
        if (d.empty()) continue;
        paths.push_back(Path(good.itemName, good.rotationSlot, cost, d));
        paths.back().deterministic = deterministic;
    }

    // Trade-ups: ten skins of one rarity (five Covert) from one collection, at any mix of wear bands, against
    // the average sale value of the result. Input wear is chosen to make the inputs as cheap as possible.
    for (const auto &collection : schema.TradeUpCollectionNames())
    {
        std::map<std::uint32_t, std::vector<LootItem>> byRarity;
        for (const auto &skin : schema.TradeUpCollectionSkins(collection))
            if (auto rarity = schema.SkinRarity(skin.weaponDefIndex, skin.paintKitIndex); rarity && *rarity <= 6)
                if (auto loot = schema.SkinAsLootItem(skin.weaponDefIndex, skin.paintKitIndex)) byRarity[*rarity].push_back(*loot);
        for (const auto &[rarity, inputs] : byRarity)
        {
            std::vector<LootItem> outputs;
            if (rarity == 6)
            {
                for (const auto &skin : schema.GoldOutcomes(collection, false))
                    if (auto loot = schema.SkinAsLootItem(skin.weaponDefIndex, skin.paintKitIndex)) outputs.push_back(*loot);
            }
            else if (auto next = byRarity.find(rarity + 1); next != byRarity.end()) outputs = next->second;
            if (outputs.empty()) continue;
            const std::uint32_t count = rarity == 6 ? 5 : 10;
            // Cheapest input per wear band, where some input finish can have that wear.
            std::array<double, 5> price{}, from{}, to{};
            std::array<bool, 5> possible{};
            for (std::size_t band = 0; band < 5; ++band)
                for (const auto &input : inputs)
                {
                    const float low = std::max(input.wearMin, WearEdges[band]), high = std::min(input.wearMax, WearEdges[band + 1]);
                    if (high <= low) continue;
                    InventoryItem item;
                    item.defIndex = input.weaponDefIndex; item.paintKitIndex = input.paintKitIndex;
                    item.rarity = rarity; item.wear = (low + high) / 2;
                    const double value = sell(item);
                    price[band] = possible[band] ? std::min(price[band], value) : value;
                    from[band] = possible[band] ? std::min<double>(from[band], low) : low;
                    to[band] = possible[band] ? std::max<double>(to[band], high) : high;
                    possible[band] = true;
                }
            // Each output's sale value in each wear band.
            std::vector<std::array<double, 5>> outputValue(outputs.size());
            for (std::size_t index = 0; index < outputs.size(); ++index)
                for (std::size_t band = 0; band < 5; ++band)
                {
                    InventoryItem item;
                    item.defIndex = outputs[index].weaponDefIndex; item.paintKitIndex = outputs[index].paintKitIndex;
                    item.rarity = rarity == 6 ? 6 : rarity + 1; item.unusual = rarity == 6;
                    item.wear = item.paintKitIndex ? (WearEdges[band] + WearEdges[band + 1]) / 2 : 0.0f;
                    outputValue[index][band] = sell(item);
                }
            // Every split of the inputs across wear bands; its average wear can be anywhere in the split's range.
            struct Split { double cost, low, high; };
            std::vector<Split> splits;
            std::array<std::uint32_t, 5> split{};
            const auto add = [&] {
                Split entry{0, 0, 0};
                for (std::size_t band = 0; band < 5; ++band)
                {
                    if (split[band] && !possible[band]) return;
                    entry.cost += split[band] * price[band];
                    entry.low += split[band] * from[band];
                    entry.high += split[band] * to[band];
                }
                entry.low /= count; entry.high /= count;
                splits.push_back(entry);
            };
            for (split[0] = 0; split[0] <= count; ++split[0])
                for (split[1] = 0; split[0] + split[1] <= count; ++split[1])
                    for (split[2] = 0; split[0] + split[1] + split[2] <= count; ++split[2])
                        for (split[3] = 0; split[0] + split[1] + split[2] + split[3] <= count; ++split[3])
                        {
                            split[4] = count - split[0] - split[1] - split[2] - split[3];
                            add();
                        }
            EconomyPath worst{"tradeup:" + collection + ":" + std::to_string(rarity), "tradeup", 0, 0, 0, false};
            double worstRatio = -1;
            for (int step = 0; step <= 400; ++step)
            {
                const double average = step / 400.0;
                double cost = -1;
                for (const auto &entry : splits)
                    if (entry.low <= average && average <= entry.high && (cost < 0 || entry.cost < cost)) cost = entry.cost;
                if (cost < 0) continue;
                double expected = 0, best = 0;
                for (std::size_t index = 0; index < outputs.size(); ++index)
                {
                    const auto &output = outputs[index];
                    const double wear = output.paintKitIndex ? std::clamp(output.wearMin + average * (output.wearMax - output.wearMin), 0.0, 1.0) : 0.0;
                    std::size_t band = 0;
                    while (band < 4 && wear >= WearEdges[band + 1]) ++band;
                    expected += outputValue[index][band] / outputs.size();
                    best = std::max(best, outputValue[index][band]);
                }
                const double ratio = cost > 0 ? expected / cost : (expected > 0 ? 1e9 : 0);
                if (ratio > worstRatio) { worstRatio = ratio; worst.cost = cost; worst.expected = expected; worst.best = best; }
            }
            if (worstRatio >= 0) paths.push_back(worst);
        }
    }
    return paths;
}
}
