#include "cs2_gc/armory.h"
#include <string_view>

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
                              const CaseOdds &odds)
{
    Result result;
    if (request.campaignId != m_campaignId)
    {
        result.status = Status::WrongCampaign;
        return result;
    }
    const ArmoryRedeemable *goods = m_schema.FindRedeemable(request.campaignId, request.redeemId);
    if (!goods)
    {
        result.status = Status::UnknownGoods;
        return result;
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
    if (goods->itemName.starts_with(LootListPrefix))
        item = RollLootList(m_schema, std::string_view(goods->itemName).substr(LootListPrefix.size()), random, odds);
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
    result.item = inventory.AddItem(*item);
    return result;
}
}
