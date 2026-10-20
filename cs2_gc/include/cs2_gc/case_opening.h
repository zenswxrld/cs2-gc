#pragma once

#include "cs2_gc/inventory.h"
#include "cs2_gc/schema.h"
#include <cstdint>
#include <functional>
#include <optional>
#include <string_view>

namespace cs2_gc
{
using RandomSource = std::function<std::uint64_t()>; // uniform 64-bit values
// Consecutive eligible case misses: 0.26% initially; linear soft pity on opening 10, hard pity on 100.
std::uint32_t CaseGoldChance(std::uint32_t previousMisses);
std::uint32_t PityChance(std::uint32_t previousMisses, std::uint32_t baseChance, const GameplayConfig &config = {});

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

// The item a resolved loot entry stands for: the skin (with its wear, seed and StatTrak roll), the
// sticker, the charm or the plain item, with the given rarity (zero leaves it to the client).
InventoryItem MakeLootItem(const LootItem &drop, std::uint32_t rarity, const RandomSource &random,
                           std::uint32_t statTrakPerMille = 100);

// Drop odds in parts per 10000, by rarity value. Rarity 99 (the rare special
// tier) is left out because its loot lists are not resolved yet; the remaining
// tiers are renormalised.
struct CaseOdds
{
    std::uint32_t milSpec{7992}, restricted{1598}, classified{320}, covert{64};
    std::uint32_t statTrakPerMille{100};
    std::uint32_t fifthTier{}, sixthTier{}; // Armory collections can contain more tiers than standard cases
};

// Rolls one item from a client loot list (a case's, or an Armory collection, sticker or charm pack's).
// Tiers are ranked by rarity within the list and given the odds in rank order, so a case (rare to
// ancient) and a collection (uncommon to legendary) are treated alike. Tiers with nothing resolvable
// are skipped and the rest renormalised. Nothing when no tier has an item.
std::optional<InventoryItem> RollLootList(const Schema &schema, std::string_view lootListName,
                                          const RandomSource &random, const CaseOdds &odds = {},
                                          std::uint32_t excludedRarity = 0);

// Three independent 50% case / 50% blue-or-better weapon drops; atomic on missing pools.
std::optional<std::vector<InventoryItem>> RollMatchDrops(const Schema &schema, const RandomSource &random,
                                                               const GameplayConfig &config = {});

// Cases need their key; capsules and graffiti boxes open without one (the key id is ignored).
// Atomic: the crate and key are consumed and the item added together, or the
// inventory is left unchanged. All rolling happens before any mutation.
OpenResult OpenCase(Inventory &inventory, const Schema &schema, std::uint64_t crateId,
                    std::uint64_t keyId, const RandomSource &random, const CaseOdds &odds = {});
}
