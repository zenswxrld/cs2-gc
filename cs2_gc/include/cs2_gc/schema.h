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
    std::uint32_t rarity{};          // rarities value from the tier name suffix; zero if unknown
    std::vector<std::string> items;  // "[paintkit]weapon_class" style entries, unexpanded
};

// One resolved "[paintkit]weapon_class" loot entry.
struct LootItem
{
    std::uint32_t weaponDefIndex{};
    std::uint32_t paintKitIndex{};
    std::string weaponClass;
    std::string paintKitName;
    float wearMin{0.0f};
    float wearMax{1.0f};
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

    // Fails (nothing returned) when the entry is not "[kit]class", or the weapon
    // or paint kit is missing from the schema, so nothing is guessed.
    std::optional<LootItem> ResolveLootItem(std::string_view entry) const;

    // Rarity value of a paint-kit weapon as the game shows it: the finish's rarity plus the
    // weapon's base rarity minus one, capped at 6 (Covert). Checked against the target build:
    // AK-47 (base 2) with a rarity-4 finish is Classified (5), with a rarity-5 finish Covert (6).
    // Nothing if the weapon, finish or either rarity is missing from the schema.
    std::optional<std::uint32_t> SkinRarity(std::uint32_t weaponDefIndex, std::uint32_t paintKitIndex) const;

private:
    Schema() = default;

    KvNode m_root;
    std::vector<CrateInfo> m_crates;
    std::unordered_map<std::string, const KvNode *> m_lootLists;
    std::unordered_map<std::uint32_t, std::size_t> m_crateIndex;
    std::unordered_map<std::string, std::uint32_t> m_itemsByName;
    std::unordered_map<std::string, const KvNode *> m_paintKits; // by name; key is the index
    std::unordered_map<std::string, std::uint32_t> m_rarities;
    std::unordered_map<std::string, std::string> m_paintKitRarity;       // kit name -> rarity name
    std::unordered_map<std::uint32_t, std::string> m_paintKitNames;      // kit index -> name
    std::unordered_map<std::uint32_t, const KvNode *> m_itemsByIndex;
    std::unordered_map<std::string, const KvNode *> m_prefabs;
};
}
