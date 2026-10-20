#pragma once

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

    // The item definition for an item id the game may equip: one of ours, or a built-in default
    // item (ids of the form 0xF000000000000000 | definition). Nothing for any other id.
    std::optional<std::uint32_t> DefinitionOf(std::uint64_t itemId) const;

    // The equip-slot objects (encoded CSOEconEquipSlot) for the current state, for a Welcome.
    std::vector<std::vector<std::uint8_t>> EncodedSlots(std::uint32_t accountId) const;

    // Applies an equip request. All items are checked first; if any is unknown nothing changes and
    // the result is empty. Otherwise it returns the changed slots encoded as CSOEconEquipSlot.
    std::optional<std::vector<std::vector<std::uint8_t>>> Adjust(const AdjustEquipSlots &request,
                                                                 std::uint32_t accountId);

private:
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
