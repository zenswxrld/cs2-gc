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
inline constexpr std::uint32_t AttributeKillEater = 80;
inline constexpr std::uint32_t AttributeKillEaterScoreType = 81;

// Sticker (and graffiti) kit id, and charm id. The sticker attribute is what the capture's graffiti
// item carries; the sticker and charm items themselves are tools (definitions 1209 and 1355).
inline constexpr std::uint32_t AttributeStickerKit = 113;   // "sticker slot 0 id"
inline constexpr std::uint32_t AttributeKeychain = 299;     // "keychain slot 0 id"
// Applied stickers, per slot 0-4 (items_game.txt): id, wear, scale and rotation at 113 + 4 * slot
// (+0..+3, the id stored as an integer), offset x and y at 278 + 2 * slot (+0, +1).
inline constexpr std::uint32_t AttributeStickerSlotBase = 113;
inline constexpr std::uint32_t AttributeStickerOffsetBase = 278;
// An attached charm: id 299 (an integer), offsets x, y, z at 300, 301, 302 (floats).
inline constexpr std::uint32_t AttributeKeychainOffsetBase = 300;
// "keychain slot 0 sticker": the sticker kit inside a sealed Sticker Slab charm.
inline constexpr std::uint32_t AttributeKeychainSticker = 321;
// Storage units: the unit (definition 1201) carries an item count (270) and a modification date (271);
// an item inside one carries the unit's id as two integers, low half at 272 and high half at 273.
inline constexpr std::uint32_t DefinitionStorageUnit = 1201;
inline constexpr std::uint32_t AttributeCasketItemsCount = 270;
inline constexpr std::uint32_t AttributeCasketModificationDate = 271;
inline constexpr std::uint32_t AttributeCasketIdLow = 272;
inline constexpr std::uint32_t AttributeCasketIdHigh = 273;
inline constexpr std::uint32_t MaxStorageUnitItems = 1000;
inline constexpr std::uint32_t AttributeCustomName = 111; // "custom name attr", a string
inline constexpr std::uint32_t DefinitionSticker = 1209;
inline constexpr std::uint32_t DefinitionKeychain = 1355;

// A new item the player has not yet acknowledged has this bit set in its `inventory` field, with
// the way it arrived in the low bits. The values follow the order of the client's pickup-method
// names (found_in_crate is 5, ..., ad 21, rental 22, xpshopredeem 23, purchasedvolatile 24);
// 23 is derived from that order and still has to be confirmed in the game.
inline constexpr std::uint32_t InventoryUnacknowledgedBit = 1u << 30;
inline constexpr std::uint32_t PickupCrafted = 2; // a trade-up contract's result
inline constexpr std::uint32_t PickupPurchased = 4;
inline constexpr std::uint32_t PickupFoundInCrate = 5;
inline constexpr std::uint32_t PickupXpShopRedeem = 23;

// Quality "unique" from the same schema; the real item in the capture used it too.
inline constexpr std::uint32_t QualityUnique = 4;
inline constexpr std::uint32_t QualityStrange = 9;
inline constexpr std::uint32_t QualityTournament = 12; // installed schema quality: tournament (Souvenir)

// Encodes a CSOEconItem (base_gcmessages.proto of the target client) for a plain paint-kit
// weapon. StatTrak is not encoded yet. `inventoryPosition` is the backpack slot.
std::vector<std::uint8_t> BuildEconItem(const InventoryItem &item, std::uint32_t accountId,
                                        std::uint64_t itemId, std::uint32_t inventoryPosition);

// Returns the Welcome with `items` added to the item (type 1) objects of its first cache, or
// nothing when the Welcome is malformed or has no cache. Every other byte-level field of the
// Welcome and of the cache is carried over unchanged and in order. A cache with no item type
// gets one.
// SO object type seen in the capture of build 25947352 whose shape is CSOAccountXpShop: field 1
// generation time, 2 redeemable balance (the Armory Credits Balance) and 3 `xp_tracks`, one entry
// per activated Armory Pass holding that pass's XP (the page shows XP / XP-per-star stars; the
// capture has two passes of 1361 XP). Confirmed in the game for the balance (credits 30 -> 26).
inline constexpr std::uint64_t XpShopTypeId = 6;

// The raw objects of one SO type in the first cache of a Welcome. Empty if there are none or the
// Welcome is malformed.
std::vector<std::vector<std::uint8_t>> ExtractObjects(std::span<const std::uint8_t> welcome, std::uint64_t typeId);

// One XpShop object with its redeemable balance (field 2) set, every other field kept; the balance
// is added when the object has none. Nothing if the object is malformed.
std::optional<std::vector<std::uint8_t>> WithXpShopBalance(std::span<const std::uint8_t> object, std::uint32_t balance);

// The pass object with one more entry in `xp_tracks` (field 3): a pass the player has activated, with
// the XP it starts with. Each entry is one pass; the Armory page shows its XP in stars. Nothing if the
// object is malformed.
std::optional<std::vector<std::uint8_t>> WithXpShopTrack(std::span<const std::uint8_t> object, std::uint32_t xp);

// The pass object with its `xp_tracks` (field 3) replaced by exactly these entries, every other field kept.
// The Armory page only draws a pass whose XP is non-zero. Nothing if the object is malformed.
std::optional<std::vector<std::uint8_t>> WithXpShopTracks(std::span<const std::uint8_t> object,
                                                          std::span<const std::uint32_t> tracks);

// The item definition of the Armory Pass ticket (`XpShopTicket1`, tool type xp_shop_ticket): bought in
// the Store, then used from the Armory page, which sends a use-item request.
inline constexpr std::uint32_t DefinitionArmoryPass = 1354;

// The built-in "Remove Keychain Tool" (the Charm Detachments entry in the inventory). The game uses it with
// the ApplySticker message: the "sticker" is its default item id (0xF000000000000000 | 65) and the item is
// the weapon to take the charm off.
inline constexpr std::uint32_t DefinitionRemoveKeychainTool = 65;

// Returns the Welcome with the redeemable balance of every XpShop object set to `balance`. All
// other fields, objects and types are carried over unchanged. Nothing when the Welcome is
// malformed or has no cache; a Welcome with no XpShop object is returned unchanged.
std::optional<std::vector<std::uint8_t>> SetArmoryBalance(std::span<const std::uint8_t> welcome,
                                                          std::uint32_t balance);

// SO object type of CSOEconItem, as seen in the capture.
inline constexpr std::uint64_t ItemTypeId = 1;
// Earlier supplied welcome capture: type 4, generation_time(1), balance(2), four repeated item ids(3).
inline constexpr std::uint64_t PersonalStoreTypeId = 4;

// Backpack position of the first of our items in a Welcome (clear of the account's own slots); the
// rest follow in inventory order.
inline constexpr std::uint32_t ItemPositionBase = 1000;

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
