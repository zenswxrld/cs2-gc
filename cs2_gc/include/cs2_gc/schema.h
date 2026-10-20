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

enum class LootKind { Skin, Sticker, Keychain };

// One resolved "[name]class" loot entry: "[finish]weapon_x" is a skin, "[kit]sticker" a sticker and
// "[charm]keychain" a charm.
struct LootItem
{
    LootKind kind{LootKind::Skin};
    std::uint32_t weaponDefIndex{};  // the item definition (the weapon, or the sticker / charm tool)
    std::uint32_t paintKitIndex{};   // skins
    std::uint32_t stickerKitIndex{}; // stickers
    std::uint32_t keychainIndex{};   // charms
    std::string weaponClass;
    std::string paintKitName;
    float wearMin{0.0f};
    float wearMax{1.0f};
};

// One tile of the Armory: a `operational_point_redeemable` of a seasonal operation whose goods are
// "xpshop". The game's redeem request names a goods by redeemId = CRC32(itemName), which matches
// every request captured so far, and a cost equal to `points`.
struct ArmoryRedeemable
{
    std::uint32_t campaignId{};
    std::uint32_t shopIndex{};   // position among the campaign's goods
    std::uint32_t points{};      // cost in Armory credits
    std::string itemName;        // an item name, or "lootlist:<client loot list>"
    std::uint32_t redeemId{};
};

std::uint32_t Crc32(std::string_view text);

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

    // The Armory's goods across all campaigns, in schema order.
    const std::vector<ArmoryRedeemable> &ArmoryRedeemables() const { return m_armoryRedeemables; }
    const ArmoryRedeemable *FindRedeemable(std::uint32_t campaignId, std::uint32_t redeemId) const;

    // The rarity value of an item definition by its own `item_rarity` (0 when it has none).
    std::uint32_t ItemRarity(std::uint32_t defIndex) const;

    // The item definition index for an item name such as "crate_community_35".
    std::optional<std::uint32_t> ItemDefIndex(std::string_view name) const;

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
    std::unordered_map<std::string, std::uint32_t> m_stickerKits;   // name -> index
    std::unordered_map<std::string, std::uint32_t> m_keychains;     // name -> index
    std::vector<ArmoryRedeemable> m_armoryRedeemables;
    std::unordered_map<std::string, const KvNode *> m_prefabs;
};
}
