#pragma once

#include "cs2_gc/case_opening.h"
#include "cs2_gc/gc_handshake.h"
#include "cs2_gc/inventory.h"
#include <cstdint>
#include <filesystem>
#include <optional>
#include <vector>

namespace cs2_gc
{
// The inventory as the game sees it during a session: the items plus which item is in which loadout
// slot. Slots are kept in memory only.
class LiveInventory
{
public:
    explicit LiveInventory(Inventory inventory);

    const Inventory &Items() const { return m_inventory; }

    // Adds an item to the inventory and returns it with its new id (the game sees it as
    // CustomItemIdBase + id).
    InventoryItem AddItem(InventoryItem item);

    // Writes the items to a file in the inventory's own text format; false if that failed.
    bool Save(const std::filesystem::path &path) const { return m_inventory.Save(path); }

    // Removes one of our items; false if the id is not one.
    bool RemoveItem(std::uint64_t itemId);

    // The item definition for an item id the game may equip: one of ours, or a built-in default
    // item (ids of the form 0xF000000000000000 | definition). Nothing for any other id.
    std::optional<std::uint32_t> DefinitionOf(std::uint64_t itemId) const;

    // The equip-slot objects (encoded CSOEconEquipSlot) for the current state, for a Welcome.
    std::vector<std::vector<std::uint8_t>> EncodedSlots(std::uint32_t accountId) const;

    // Applies an equip request. All items are checked first; if any is unknown nothing changes and
    // the result is empty. Otherwise it returns the changed slots encoded as CSOEconEquipSlot.
    std::optional<std::vector<std::vector<std::uint8_t>>> Adjust(const AdjustEquipSlots &request,
                                                                 std::uint32_t accountId);

    struct StickerApplied
    {
        InventoryItem item;                // the weapon with the sticker on it
        std::uint32_t position{};          // its backpack position, as a Welcome would give it
        InventoryItem consumed;            // the sticker (or charm) item, now removed
        bool charm{};                      // a charm was attached, not a sticker
    };

    // Applies a sticker item to a weapon slot, or a charm item to a weapon. All checks come first: both
    // ids must be ours, the first a sticker or charm item, the second not a sticker, charm or graffiti,
    // and the slot (0-4) free (a weapon takes one charm).
    // On failure nothing changes.
    std::optional<StickerApplied> ApplySticker(const ApplyStickerRequest &request);

    struct Opened
    {
        InventoryItem item;                  // the new item
        InventoryItem crate;                 // the container, now removed
        std::optional<InventoryItem> key;    // the key, now removed (cases only)
    };

    // Opens one of our containers with one of our keys (ids as the game sees them; key 0 for
    // capsules). Nothing changes on failure.
    std::optional<Opened> Open(const Schema &schema, std::uint64_t crateItemId, std::uint64_t keyItemId,
                               const RandomSource &random);

    // Sets (or, with an empty name, clears) the custom name of one of our items; the updated item
    // and its backpack position, or nothing if the id is not ours.
    struct Renamed
    {
        InventoryItem item;
        std::uint32_t position{};
    };
    std::optional<Renamed> Rename(std::uint64_t itemId, const std::string &name);

    enum class StorageResult { Ok, Invalid, Full };
    struct StorageChange
    {
        StorageResult result{StorageResult::Invalid};
        InventoryItem item;               // the item moved
        InventoryItem casket;             // the storage unit, with its new count
        std::uint32_t itemPosition{};
        std::uint32_t casketPosition{};
    };

    // Puts one of our items into one of our storage units, or takes it out again (a unit holds
    // MaxStorageUnitItems). Both ids as the game sees them. Invalid leaves everything unchanged.
    StorageChange StoreItem(std::uint64_t casketItemId, std::uint64_t itemId, std::uint32_t now);
    StorageChange TakeItem(std::uint64_t casketItemId, std::uint64_t itemId, std::uint32_t now);

    struct Scraped
    {
        InventoryItem item;        // the weapon after the scrape
        std::uint32_t position{};
        bool removed{};            // the sticker wore away completely
    };

    // Scrapes the sticker in one slot of one of our items: its wear rises by a ninth, and past 1 it is
    // removed. Nothing if the item is not ours or has no sticker in that slot.
    std::optional<Scraped> ScrapeSticker(std::uint64_t itemId, std::uint32_t slot);

    struct Sealed
    {
        InventoryItem charm;    // the new charm: the slab with the sticker in it
        InventoryItem sticker;  // consumed
        InventoryItem slab;     // consumed
    };

    // Seals a sticker in a Sticker Slab: both items go and one charm of the slab's keychain, holding the
    // sticker, takes their place. Nothing changes unless the first id is one of our stickers and the
    // second one of our slabs (an item the schema gives `can_wrap_sticker`).
    std::optional<Sealed> SealSticker(const Schema &schema, std::uint64_t stickerItemId, std::uint64_t slabItemId);

private:
    std::uint32_t PositionOf(std::uint64_t ourId) const;
    struct Slot
    {
        std::uint32_t classId{};
        std::uint32_t slotId{};
        std::uint64_t itemId{};
        std::uint32_t itemDefinition{};
    };

    Inventory m_inventory;
    std::vector<Slot> m_slots;
};
}
