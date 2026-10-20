#pragma once

#include "cs2_gc/keyvalues.h"
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

namespace cs2_gc
{
enum class CrateKind { Case, Capsule, GraffitiBox, Other };

struct CrateInfo
{
    std::uint32_t defIndex{};
    std::string name;
    std::string nameToken;           // localization token, without the leading '#'
    std::uint32_t series{};          // supply crate series
    std::uint32_t keyDefIndex{};     // zero when the crate opens without a key
    std::string lootListName;        // client_loot_lists entry, resolved via the series
    CrateKind kind{CrateKind::Other}; // from the prefab chain; Case means keyed weapon case
};

struct LootTier
{
    std::string name;                // e.g. crate_community_35_rare
    std::vector<std::string> items;  // "[paintkit]weapon_class" style entries, unexpanded
};

// Read-only view over the target client's items_game.txt. Built from the real
// file at runtime; nothing here is a hand-written item list.
class Schema
{
public:
    Schema(Schema &&) = default;
    Schema &operator=(Schema &&) = default;
    Schema(const Schema &) = delete; // lookup tables point into m_root
    Schema &operator=(const Schema &) = delete;

    static std::optional<Schema> Load(std::string_view itemsGameText);

    // Standard cases only; souvenir packages are not crates here.
    const std::vector<CrateInfo> &Crates() const { return m_crates; }
    const CrateInfo *FindCrate(std::uint32_t defIndex) const;

    // Flattens a loot list into its tiers. Nested lists that are not themselves
    // tiers are expanded; cycles and excessive depth are cut off.
    std::vector<LootTier> LootTiers(std::string_view lootListName) const;

private:
    Schema() = default;

    KvNode m_root;
    std::vector<CrateInfo> m_crates;
    std::unordered_map<std::string, const KvNode *> m_lootLists;
    std::unordered_map<std::uint32_t, std::size_t> m_crateIndex;
};
}
