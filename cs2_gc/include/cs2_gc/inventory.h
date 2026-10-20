#pragma once

#include <cstdint>
#include <filesystem>
#include <optional>
#include <string>
#include <string_view>
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

    // KeyValues text, so the file stays hand-editable. FromText is strict: any
    // malformed, duplicate or out-of-range entry rejects the whole file rather
    // than loading a partial inventory.
    std::string ToText() const;
    static std::optional<Inventory> FromText(std::string_view text);

    // Writes to a temporary file in the same directory, then renames over the target,
    // so a crash mid-save never leaves a truncated inventory.
    bool Save(const std::filesystem::path &path) const;
    static std::optional<Inventory> Load(const std::filesystem::path &path);

private:
    std::vector<InventoryItem> m_items;
    std::uint64_t m_nextId{1};
};
}
