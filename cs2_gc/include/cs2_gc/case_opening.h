#pragma once

#include "cs2_gc/inventory.h"
#include "cs2_gc/schema.h"
#include <cstdint>
#include <functional>

namespace cs2_gc
{
using RandomSource = std::function<std::uint64_t()>; // uniform 64-bit values

enum class OpenError
{
    None,
    NoSuchCrate,   // crate item missing, or not a keyed weapon case
    NoSuchKey,     // key missing from the inventory
    WrongKey,      // key is not the crate's key
    EmptyLootList, // schema gave nothing resolvable to drop
};

struct OpenResult
{
    OpenError error{OpenError::None};
    InventoryItem item; // the new item, already added to the inventory on success
};

// Drop odds in parts per 10000, by rarity value. Rarity 99 (the rare special
// tier) is left out because its loot lists are not resolved yet; the remaining
// tiers are renormalised.
struct CaseOdds
{
    std::uint32_t milSpec{7992}, restricted{1598}, classified{320}, covert{64};
    std::uint32_t statTrakPerMille{100};
};

// Atomic: the crate and key are consumed and the item added together, or the
// inventory is left unchanged. All rolling happens before any mutation.
OpenResult OpenCase(Inventory &inventory, const Schema &schema, std::uint64_t crateId,
                    std::uint64_t keyId, const RandomSource &random, const CaseOdds &odds = {});
}
