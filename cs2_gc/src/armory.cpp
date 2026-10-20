#include "cs2_gc/armory.h"
#include <string_view>
#include <algorithm>
#include <ctime>
#include <map>

namespace cs2_gc
{
namespace
{
constexpr std::string_view LootListPrefix = "lootlist:";
}

Armory::Armory(const Schema &schema, std::uint32_t campaignId, std::uint32_t credits)
    : m_schema(schema), m_campaignId(campaignId), m_balance(credits)
{
}

Armory::Result Armory::Redeem(const RedeemRequest &request, LiveInventory &inventory, const RandomSource &random,
                              const CaseOdds &odds, std::optional<std::uint64_t> unixSeconds)
{
    Result result;
    if (request.campaignId != m_campaignId)
    {
        result.status = Status::WrongCampaign;
        return result;
    }
    const auto localHowl = HowlOffer(inventory.Items().Gameplay());
    const bool isHowl = localHowl && request.redeemId == localHowl->redeemId;
    const ArmoryRedeemable *goods = isHowl ? &*localHowl : m_schema.FindRedeemable(request.campaignId, request.redeemId);
    if (!goods)
    {
        result.status = Status::UnknownGoods;
        return result;
    }
    const auto &config = inventory.Items().Gameplay();
    if (isHowl || (config.armory_rotation_enabled && (config.armory_rotation_enforce || !goods->rotationSlot.empty())))
    {
        const auto rotation = RotationAt(unixSeconds.value_or(static_cast<std::uint64_t>(std::time(nullptr))), config);
        if (std::find(rotation.redeemIds.begin(), rotation.redeemIds.end(), request.redeemId) == rotation.redeemIds.end())
        {
            result.status = Status::NotInRotation;
            return result;
        }
    }
    if (request.expectedCost != goods->points)
    {
        result.status = Status::CostMismatch;
        return result;
    }
    if (m_balance < goods->points)
    {
        result.status = Status::NotEnoughCredits;
        return result;
    }

    // Everything that can fail happens before anything changes.
    std::optional<InventoryItem> item;
    std::optional<std::string> rolledCollection;
    bool topReward = false;
    if (isHowl)
    {
        if (const auto howl = m_schema.ResolveLootItem(HowlEntry))
            item = MakeLootItem(*howl, m_schema.SkinRarity(howl->weaponDefIndex, howl->paintKitIndex).value_or(0), random, 0);
    }
    else if (goods->rotationSlot == "limited" && goods->itemName.starts_with(LootListPrefix))
    {
        std::vector<LootItem> fixed;
        for (const auto &tier : m_schema.LootTiers(goods->itemName.substr(LootListPrefix.size())))
            for (const auto &entry : tier.items)
                if (auto resolved = m_schema.ResolveLootItem(entry)) fixed.push_back(*resolved);
        if (fixed.size() == 1 && fixed.front().kind == LootKind::Skin)
            if (auto rarity = m_schema.SkinRarity(fixed.front().weaponDefIndex, fixed.front().paintKitIndex))
                item = MakeLootItem(fixed.front(), *rarity, random, 0);
    }
    else if (goods->itemName.starts_with(LootListPrefix))
    {
        CaseOdds collectionOdds = odds;
        collectionOdds.statTrakPerMille = 0;
        collectionOdds.fifthTier = 13;
        collectionOdds.sixthTier = 3;
        const std::string name = goods->itemName.substr(LootListPrefix.size());
        auto tiers = m_schema.LootTiers(name);
        std::erase_if(tiers, [](const auto &tier) { return tier.rarity == 0; });
        std::stable_sort(tiers.begin(), tiers.end(), [](const auto &a, const auto &b) { return a.rarity < b.rarity; });
        const std::uint32_t weights[] = {collectionOdds.milSpec, collectionOdds.restricted, collectionOdds.classified,
                                        collectionOdds.covert, collectionOdds.fifthTier, collectionOdds.sixthTier};
        std::uint64_t total = 0, topWeight = 0;
        std::uint32_t highest = 0;
        std::vector<LootItem> top;
        bool lower = false;
        for (std::size_t index = 0; index < tiers.size() && index < std::size(weights); ++index)
        {
            std::vector<LootItem> resolved;
            for (const auto &entry : tiers[index].items)
                if (auto outcome = m_schema.ResolveLootItem(entry)) resolved.push_back(*outcome);
            if (resolved.empty() || !weights[index]) continue;
            total += weights[index];
            if (tiers[index].rarity > highest)
            {
                lower = highest != 0;
                highest = tiers[index].rarity; top = std::move(resolved); topWeight = weights[index];
            }
            else if (tiers[index].rarity == highest)
            {
                top.insert(top.end(), resolved.begin(), resolved.end()); topWeight += weights[index];
            }
        }
        if (total && !top.empty())
        {
            auto pity = config;
            pity.pity_enabled = config.armory_pity_enabled;
            pity.pity_soft_at = config.armory_pity_soft_at; pity.pity_hard_at = config.armory_pity_hard_at;
            const auto base = std::max(config.armory_top_per_10000, static_cast<std::uint32_t>(topWeight * 10000 / total));
            const auto chance = lower ? PityChance(inventory.Items().ArmoryPity(name), base, pity) : 10000u;
            const auto below = [&](std::uint64_t bound) {
                const auto limit = UINT64_MAX - UINT64_MAX % bound;
                for (;;) { const auto value = random(); if (value < limit) return value % bound; }
            };
            if (below(10000) < chance)
            {
                item = MakeLootItem(top[below(top.size())], highest, random, 0);
                topReward = true;
            }
            else item = RollLootList(m_schema, name, random, collectionOdds, highest);
            rolledCollection = name;
        }
    }
    else if (const auto definition = m_schema.ItemDefIndex(goods->itemName))
    {
        InventoryItem plain;
        plain.defIndex = *definition;
        plain.rarity = m_schema.ItemRarity(*definition);
        item = plain;
    }
    if (!item)
    {
        result.status = Status::NothingToGrant;
        return result;
    }

    m_balance -= goods->points;
    inventory.SetArmoryCredits(m_balance);
    result.item = inventory.AddItem(*item);
    if (rolledCollection)
        inventory.SetArmoryPity(*rolledCollection, topReward ? 0u : std::min(inventory.Items().ArmoryPity(*rolledCollection) + 1, 99u));
    return result;
}
}

namespace cs2_gc
{
Armory::Rotation Armory::RotationAt(std::uint64_t unixSeconds, const GameplayConfig &config) const
{
    std::vector<const ArmoryRedeemable *> all;
    for (const auto &good : m_schema.ArmoryRedeemables())
        if (good.campaignId == m_campaignId) all.push_back(&good);
    const auto howl = HowlOffer(config);
    if (howl && !m_schema.FindRedeemable(m_campaignId, howl->redeemId)) all.push_back(&*howl);
    std::sort(all.begin(), all.end(), [](const auto *a, const auto *b) { return a->itemName < b->itemName; });
    Rotation result;
    if (all.empty()) return result;
    if (!config.armory_rotation_enabled)
    {
        for (const auto *good : all) result.redeemIds.push_back(good->redeemId);
        return result;
    }
    const auto interval = config.armory_rotation_seconds;
    const auto cycle = unixSeconds / interval + m_rotationOffset;
    result.endsAt = unixSeconds - unixSeconds % interval + interval;
    // Native category slots rotate independently. A large capsule catalogue cannot
    // crowd charms or cases out of their designated slots.
    std::map<std::string, std::vector<const ArmoryRedeemable *>> slots;
    for (const auto *good : all)
        if (!good->rotationSlot.empty()) slots[good->rotationSlot].push_back(good);
    if (!slots.empty())
    {
        for (const auto &[slot, entries] : slots)
            result.redeemIds.push_back(entries[cycle % entries.size()]->redeemId);
        return result;
    }
    const auto count = std::min<std::size_t>(config.armory_rotation_slots, all.size());
    const auto start = ((cycle % all.size()) * count) % all.size();
    for (std::size_t i = 0; i < count; ++i)
        result.redeemIds.push_back(all[(start + i) % all.size()]->redeemId);
    return result;
}
}

namespace cs2_gc
{
std::optional<ArmoryRedeemable> Armory::HowlOffer(const GameplayConfig &config) const
{
    if (!config.armory_rotation_enabled || !config.armory_howl_enabled) return std::nullopt;
    const auto item = m_schema.ResolveLootItem(HowlEntry);
    if (!item || item->kind != LootKind::Skin || m_schema.SkinRarity(item->weaponDefIndex, item->paintKitIndex) != 7)
        return std::nullopt;
    ArmoryRedeemable offer;
    offer.campaignId = m_campaignId;
    // The generated native tile uses the existing single-item Howl loot list.
    const auto native = m_schema.FindRedeemable(m_campaignId, Crc32("lootlist:removed_items"));
    offer.itemName = native ? native->itemName : std::string{HowlEntry};
    offer.redeemId = Crc32(offer.itemName);
    offer.points = config.armory_howl_star_price;
    return offer;
}
}
