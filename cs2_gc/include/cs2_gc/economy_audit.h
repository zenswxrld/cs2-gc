#pragma once
#include "cs2_gc/case_opening.h"
#include "cs2_gc/gameplay_config.h"
#include "cs2_gc/schema.h"
#include <string>
#include <vector>

namespace cs2_gc
{
// Deterministic star-economy audit: every way stars become items and back again, valued with the same
// odds, pity and ItemSaleValue rules the GC uses (no random sampling). Pity is taken at its long-run rate
// for a player who keeps buying the same row (or opening cases).
struct EconomyPath
{
    std::string name;      // Armory item name, "open:<case>", "sell:<case>" or "tradeup:<collection>:<rarity>"
    std::string kind;      // Armory slot, or "case-open", "case-sell", "tradeup"
    double cost{};         // stars paid; for a trade-up, the cheapest sale value of its inputs at that wear
    double expected{};     // average stars back by selling the result
    double best{};         // most stars any single result sells for
    bool deterministic{};  // exactly one possible item (wear and pattern aside)
    // A path gains stars when its average return reaches its cost, or a single fixed item can sell for it.
    bool Loop() const { return cost > 0 && (expected >= cost || (deterministic && best >= cost)); }
};

std::vector<EconomyPath> AuditEconomy(const Schema &schema, const GameplayConfig &config, const CaseOdds &odds = {});
}
