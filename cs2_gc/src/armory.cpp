#include "cs2_gc/armory.h"
#include <string_view>
#include <algorithm>
#include <ctime>

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
    if (isHowl || (config.armory_rotation_enabled && config.armory_rotation_enforce))
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
    if (isHowl)
    {
        if (const auto howl = m_schema.ResolveLootItem(HowlEntry))
            item = MakeLootItem(*howl, m_schema.SkinRarity(howl->weaponDefIndex, howl->paintKitIndex).value_or(0), random, 0);
    }
    else if (goods->itemName.starts_with(LootListPrefix))
    {
        CaseOdds collectionOdds = odds;
        collectionOdds.statTrakPerMille = 0;
        item = RollLootList(m_schema, std::string_view(goods->itemName).substr(LootListPrefix.size()), random, collectionOdds);
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
    if (howl) all.push_back(&*howl);
    std::sort(all.begin(), all.end(), [](const auto *a, const auto *b) { return a->itemName < b->itemName; });
    Rotation result;
    if (all.empty()) return result;
    if (!config.armory_rotation_enabled)
    {
        for (const auto *good : all) result.redeemIds.push_back(good->redeemId);
        return result;
    }
    const auto interval = config.armory_rotation_seconds;
    const auto cycle = unixSeconds / interval;
    result.endsAt = unixSeconds - unixSeconds % interval + interval;
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
    offer.itemName = HowlEntry;
    offer.redeemId = Crc32(HowlEntry);
    offer.points = config.armory_howl_star_price;
    return offer;
}
}
