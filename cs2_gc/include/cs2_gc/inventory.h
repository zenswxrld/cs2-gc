#pragma once

#include <cstdint>
#include <optional>
#include <vector>

namespace cs2_gc
{
struct InventoryItem
{
    std::uint64_t id{};
    std::uint32_t defIndex{};
    std::uint32_t paintKitIndex{}; // zero for items without a finish
    float wear{};
    std::uint32_t seed{};
    bool statTrak{};
};

// Local, in-memory inventory. Persistence and client sync are not wired yet.
class Inventory
{
public:
    std::uint64_t Add(InventoryItem item); // assigns and returns a fresh id
    bool Remove(std::uint64_t id);
    const InventoryItem *Find(std::uint64_t id) const;
    const std::vector<InventoryItem> &Items() const { return m_items; }

private:
    std::vector<InventoryItem> m_items;
    std::uint64_t m_nextId{1};
};
}
