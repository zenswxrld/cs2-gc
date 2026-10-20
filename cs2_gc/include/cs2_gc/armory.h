#pragma once

#include "cs2_gc/case_opening.h"
#include "cs2_gc/gc_handshake.h"
#include "cs2_gc/live_inventory.h"
#include "cs2_gc/schema.h"
#include <cstdint>
#include <vector>

namespace cs2_gc
{
// A local stand-in for the Armory: a credit balance and the goods the schema lists for a campaign.
// A redeem request is checked against the schema (known goods, matching cost, enough credits) and
// then either fully applied or not at all. Nothing is real: no Steam item is created and no
// account is touched.
class Armory
{
public:
    Armory(const Schema &schema, std::uint32_t campaignId, std::uint32_t credits);

    std::uint32_t Balance() const { return m_balance; }
    std::uint32_t CampaignId() const { return m_campaignId; }

    enum class Status
    {
        Ok,
        WrongCampaign,
        UnknownGoods,
        CostMismatch,    // the client's cost is not the schema's
        NotEnoughCredits,
        NothingToGrant,  // the goods resolve to no item
    };

    struct Result
    {
        Status status{Status::Ok};
        InventoryItem item; // the granted item, already added to `inventory`, on success
    };

    Result Redeem(const RedeemRequest &request, LiveInventory &inventory, const RandomSource &random,
                  const CaseOdds &odds = {});

private:
    const Schema &m_schema;
    std::uint32_t m_campaignId;
    std::uint32_t m_balance;
};
}
