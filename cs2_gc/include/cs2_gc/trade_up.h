#pragma once

#include "cs2_gc/case_opening.h"
#include "cs2_gc/inventory.h"
#include "cs2_gc/schema.h"
#include <cstdint>
#include <vector>

namespace cs2_gc
{
enum class TradeUpError
{
    None,
    WrongCount,      // not ten standard skins, or five Covert skins
    UnknownItem,     // an id that is not an item, a repeat, or a loose one inside a storage unit
    NotASkin,        // knives, gloves, tools and the like cannot be traded up
    MixedRarity,     // the skins are not all of one rarity
    TopRarity,       // unsupported input rarity
    MixedStatTrak,   // StatTrak and normal skins cannot be mixed
    NoCollection,    // a skin the schema places in no collection
    NoOutcome,       // none of the collections has a skin of the next rarity
};

const char *TradeUpErrorText(TradeUpError error);

struct TradeUpResult
{
    TradeUpError error{TradeUpError::None};
    InventoryItem item;                    // the new skin, already added to the inventory on success
    std::vector<InventoryItem> consumed;   // the ten inputs, already removed on success
};

// A trade-up contract: ten skins of one rarity become one skin of the next rarity; five Covert
// skins become a knife/gloves from GoldOutcomes (StatTrak permits knives only). Outcomes come from the
// collections of the skins provided. Each collection is picked in proportion to how many of the ten
// it supplied, then a skin of the next rarity in it is picked evenly. The new skin's wear is the
// average of the inputs' wear placed in the new finish's own range, and it is StatTrak only if all ten
// were. Collections are the schema's `item_sets`, so the Armory collections that only exist in CS2
// count as much as the older ones. Atomic: everything is checked and rolled before anything changes.
TradeUpResult TradeUp(Inventory &inventory, const Schema &schema, const std::vector<std::uint64_t> &itemIds,
                      const RandomSource &random);

constexpr std::size_t TradeUpItemCount = 10;
}
