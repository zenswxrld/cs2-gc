#pragma once

#include "cs2_gc/inventory.h"
#include <cstdint>
#include <optional>
#include <span>
#include <vector>

namespace cs2_gc
{
// Item attribute definition indices, read from the target build's items_game.txt
// (build 25947352): "set item texture prefab", "... seed", "... wear". The first two are stored
// as the float of the integer value, the wear as a float.
inline constexpr std::uint32_t AttributePaintIndex = 6;
inline constexpr std::uint32_t AttributePaintSeed = 7;
inline constexpr std::uint32_t AttributePaintWear = 8;

// Quality "unique" from the same schema; the real item in the capture used it too.
inline constexpr std::uint32_t QualityUnique = 4;

// Encodes a CSOEconItem (base_gcmessages.proto of the target client) for a plain paint-kit
// weapon. StatTrak is not encoded yet. `inventoryPosition` is the backpack slot.
std::vector<std::uint8_t> BuildEconItem(const InventoryItem &item, std::uint32_t accountId,
                                        std::uint64_t itemId, std::uint32_t inventoryPosition);

// Returns the Welcome with `items` added to the item (type 1) objects of its first cache, or
// nothing when the Welcome is malformed or has no cache. Every other byte-level field of the
// Welcome and of the cache is carried over unchanged and in order. A cache with no item type
// gets one.
// With dropExisting, the item objects the Welcome already carries are removed first, so the
// result holds only `items` (a fresh inventory). Other object types are never touched.
std::optional<std::vector<std::uint8_t>> AppendItemsToWelcome(
    std::span<const std::uint8_t> welcome, std::span<const std::vector<std::uint8_t>> items,
    bool dropExisting = false);
}
