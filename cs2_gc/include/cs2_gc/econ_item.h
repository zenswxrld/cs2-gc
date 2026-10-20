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

// Sticker (and graffiti) kit id, and charm id. The sticker attribute is what the capture's graffiti
// item carries; the sticker and charm items themselves are tools (definitions 1209 and 1355).
inline constexpr std::uint32_t AttributeStickerKit = 113;   // "sticker slot 0 id"
inline constexpr std::uint32_t AttributeKeychain = 299;     // "keychain slot 0 id"
inline constexpr std::uint32_t DefinitionSticker = 1209;
inline constexpr std::uint32_t DefinitionKeychain = 1355;

// A new item the player has not yet acknowledged has this bit set in its `inventory` field, with
// the way it arrived in the low bits. The values follow the order of the client's pickup-method
// names (found_in_crate is 5, ..., ad 21, rental 22, xpshopredeem 23, purchasedvolatile 24);
// 23 is derived from that order and still has to be confirmed in the game.
inline constexpr std::uint32_t InventoryUnacknowledgedBit = 1u << 30;
inline constexpr std::uint32_t PickupPurchased = 4;
inline constexpr std::uint32_t PickupFoundInCrate = 5;
inline constexpr std::uint32_t PickupXpShopRedeem = 23;

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
// SO object type seen in the capture of build 25947352 whose shape is CSOAccountXpShop: field 1
// generation time, 2 redeemable balance (the Armory Credits Balance, 0 in the capture) and 3 the
// Armory Pass track ids (two, matching the two passes in the UI). Identified by shape and by the
// balance the UI showed; treat it as unconfirmed until a changed balance shows up in the game.
inline constexpr std::uint64_t XpShopTypeId = 6;

// The raw objects of one SO type in the first cache of a Welcome. Empty if there are none or the
// Welcome is malformed.
std::vector<std::vector<std::uint8_t>> ExtractObjects(std::span<const std::uint8_t> welcome, std::uint64_t typeId);

// One XpShop object with its redeemable balance (field 2) set, every other field kept; the balance
// is added when the object has none. Nothing if the object is malformed.
std::optional<std::vector<std::uint8_t>> WithXpShopBalance(std::span<const std::uint8_t> object, std::uint32_t balance);

// Returns the Welcome with the redeemable balance of every XpShop object set to `balance`. All
// other fields, objects and types are carried over unchanged. Nothing when the Welcome is
// malformed or has no cache; a Welcome with no XpShop object is returned unchanged.
std::optional<std::vector<std::uint8_t>> SetArmoryBalance(std::span<const std::uint8_t> welcome,
                                                          std::uint32_t balance);

// SO object type of CSOEconItem, as seen in the capture.
inline constexpr std::uint64_t ItemTypeId = 1;

// Ids of the items this project creates start here, well clear of an account's own item ids.
inline constexpr std::uint64_t CustomItemIdBase = 1000000000000ull;

// SO object type of CSOEconEquipSlot (account_id, class_id, slot_id, item_id, item_definition): the
// capture's type 3 objects have exactly this shape and the loadout's slots.
inline constexpr std::uint64_t EquipSlotTypeId = 3;

// Encodes a CSOEconEquipSlot. An empty slot has item id and definition zero.
std::vector<std::uint8_t> EncodeEquipSlot(std::uint32_t accountId, std::uint32_t classId, std::uint32_t slotId,
                                          std::uint64_t itemId, std::uint32_t itemDefinition);

// Like AppendItemsToWelcome but for any SO object type: `objects` are added to that type's objects in
// the first cache (the type is created if missing), after removing its existing ones when dropExisting.
std::optional<std::vector<std::uint8_t>> AppendObjectsToWelcome(
    std::span<const std::uint8_t> welcome, std::uint64_t typeId,
    std::span<const std::vector<std::uint8_t>> objects, bool dropExisting);

// With dropExisting, the item objects the Welcome already carries are removed first, so the
// result holds only `items` (a fresh inventory). Other object types are never touched.
std::optional<std::vector<std::uint8_t>> AppendItemsToWelcome(
    std::span<const std::uint8_t> welcome, std::span<const std::vector<std::uint8_t>> items,
    bool dropExisting = false);
}
