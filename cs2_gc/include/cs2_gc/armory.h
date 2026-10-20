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
    void SetBalance(std::uint32_t credits) { m_balance = credits; }
    std::uint32_t CampaignId() const { return m_campaignId; }

    enum class Status
    {
        Ok,
        WrongCampaign,
        UnknownGoods,
        CostMismatch,    // the client's cost is not the schema's
        NotEnoughCredits,
        NotInRotation,
        NothingToGrant,  // the goods resolve to no item
    };

    struct Result
    {
        Status status{Status::Ok};
        InventoryItem item; // the granted item, already added to `inventory`, on success
    };

    struct Rotation
    {
        std::uint64_t endsAt{};
        std::vector<std::uint32_t> redeemIds;
    };
    // Existing CS2 Howl finish, a local offer identity derived from its schema loot-entry name.
    static constexpr std::string_view HowlEntry = "[cu_m4a1_howling]weapon_m4a1";
    std::optional<ArmoryRedeemable> HowlOffer(const GameplayConfig &config) const;
    Rotation RotationAt(std::uint64_t unixSeconds, const GameplayConfig &config) const;
    Result Redeem(const RedeemRequest &request, LiveInventory &inventory, const RandomSource &random,
                  const CaseOdds &odds = {}, std::optional<std::uint64_t> unixSeconds = std::nullopt);

private:
    const Schema &m_schema;
    std::uint32_t m_campaignId;
    std::uint32_t m_balance;
};
}
