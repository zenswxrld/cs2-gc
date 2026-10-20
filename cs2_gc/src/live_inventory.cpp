#include "cs2_gc/live_inventory.h"
#include "cs2_gc/econ_item.h"

namespace cs2_gc
{
LiveInventory::LiveInventory(Inventory inventory)
    : m_inventory(std::move(inventory))
{
}

InventoryItem LiveInventory::AddItem(InventoryItem item)
{
    item.id = m_inventory.Add(item);
    return item;
}

std::optional<std::uint32_t> LiveInventory::DefinitionOf(std::uint64_t itemId) const
{
    if ((itemId >> 60) == 0xF)
    {
        const std::uint32_t definition = static_cast<std::uint32_t>(itemId & 0xFFFFFFFFull);
        return definition ? std::optional<std::uint32_t>{definition} : std::nullopt;
    }
    if (itemId <= CustomItemIdBase)
        return std::nullopt;
    const InventoryItem *item = m_inventory.Find(itemId - CustomItemIdBase);
    return item ? std::optional<std::uint32_t>{item->defIndex} : std::nullopt;
}

std::vector<std::vector<std::uint8_t>> LiveInventory::EncodedSlots(std::uint32_t accountId) const
{
    std::vector<std::vector<std::uint8_t>> out;
    for (const Slot &slot : m_slots)
        if (slot.itemId)
            out.push_back(EncodeEquipSlot(accountId, slot.classId, slot.slotId, slot.itemId, slot.itemDefinition));
    return out;
}

std::optional<std::vector<std::vector<std::uint8_t>>> LiveInventory::Adjust(const AdjustEquipSlots &request,
                                                                            std::uint32_t accountId)
{
    for (const EquipSlotChange &change : request.slots)
        if (change.itemId && !DefinitionOf(change.itemId))
            return std::nullopt;

    std::vector<std::vector<std::uint8_t>> changed;
    for (const EquipSlotChange &change : request.slots)
    {
        const std::uint32_t definition = change.itemId ? *DefinitionOf(change.itemId) : 0;
        Slot *slot = nullptr;
        for (Slot &candidate : m_slots)
            if (candidate.classId == change.classId && candidate.slotId == change.slotId)
                slot = &candidate;
        if (!slot)
        {
            m_slots.push_back({change.classId, change.slotId, 0, 0});
            slot = &m_slots.back();
        }
        slot->itemId = change.itemId;
        slot->itemDefinition = definition;
        changed.push_back(EncodeEquipSlot(accountId, change.classId, change.slotId, change.itemId, definition));
    }
    return changed;
}
}
