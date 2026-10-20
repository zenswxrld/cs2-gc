#include "cs2_gc/inventory.h"
#include <algorithm>

namespace cs2_gc
{
std::uint64_t Inventory::Add(InventoryItem item)
{
    item.id = m_nextId++;
    m_items.push_back(item);
    return item.id;
}

bool Inventory::Remove(std::uint64_t id)
{
    const auto it = std::find_if(m_items.begin(), m_items.end(), [id](const InventoryItem &i) { return i.id == id; });
    if (it == m_items.end())
        return false;
    m_items.erase(it);
    return true;
}

const InventoryItem *Inventory::Find(std::uint64_t id) const
{
    const auto it = std::find_if(m_items.begin(), m_items.end(), [id](const InventoryItem &i) { return i.id == id; });
    return it == m_items.end() ? nullptr : &*it;
}
}
