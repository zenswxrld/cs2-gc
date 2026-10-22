#pragma once

#include "cs2_gc/keyvalues.h"
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace cs2_gc
{
enum class CrateKind { Case, Capsule, GraffitiBox, Pins, Terminal, Souvenir, Other }; // Pins: collectible pin capsules, keyless

struct CrateInfo
{
    std::uint32_t defIndex{};
    std::string name;
    std::string nameToken;           // localization token, without the leading '#'
    std::uint32_t series{};          // supply crate series
    std::uint32_t keyDefIndex{};     // zero when the crate opens without a key
    std::string lootListName;        // client_loot_lists entry, resolved via the series
    std::uint32_t tournamentEvent{}; // installed package event, including inherited attributes
    CrateKind kind{CrateKind::Other}; // from the prefab chain; Case means keyed weapon case
};

struct SouvenirSticker
{
    std::uint32_t kit{}, event{}, team{}, player{};
    bool gold{};
};

struct LootTier
{
    std::string name;                // e.g. crate_community_35_rare
    std::uint32_t rarity{};          // rarities value from the tier name suffix; zero if unknown
    std::vector<std::string> items;  // "[paintkit]weapon_class" style entries, unexpanded
};

enum class LootKind { Skin, Sticker, Keychain, MusicKit, Plain }; // Plain: an item named as it is in the schema

// One resolved "[name]class" loot entry: "[finish]weapon_x" is a skin, "[kit]sticker" a sticker and
// "[charm]keychain" a charm.
struct LootItem
{
    LootKind kind{LootKind::Skin};
    std::uint32_t weaponDefIndex{};  // the item definition (the weapon, or the sticker / charm tool)
    std::uint32_t paintKitIndex{};   // skins
    std::uint32_t stickerKitIndex{}; // stickers
    std::uint32_t musicKitIndex{};
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
    std::string rotationSlot; // generated catalogue: case/capsule/charm/sticker/collection/limited
};

std::uint32_t Crc32(std::string_view text);

// A weapon skin: the weapon's item definition and the finish (paint kit) index.
struct SkinRef
{
    std::uint32_t weaponDefIndex{};
    std::uint32_t paintKitIndex{};
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

    // Installed containers, including keyless souvenir packages.
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

    // Collections (the schema's `item_sets`: cases' contents and the newer Armory collections alike) a skin
    // belongs to, sorted by name. Only weapon skins are indexed.
    std::vector<std::string> CollectionsOf(std::uint32_t weaponDefIndex, std::uint32_t paintKitIndex) const;
    // The skins of one collection, in schema order; empty for an unknown collection.
    const std::vector<SkinRef> &CollectionSkins(const std::string &collection) const;
    std::size_t CollectionCount() const { return m_collectionSkins.size(); }
    std::vector<std::string> CollectionNames() const; // sorted

    // A finish offered by a keyed weapon case can have StatTrak; collection-only drops cannot.
    bool CanBeStatTrak(std::uint32_t weaponDefIndex, std::uint32_t paintKitIndex) const;
    // Supplement server-only rare pools with a versioned catalogue, validating every definition/finish.
    bool LoadGoldPools(std::string_view text);
    std::vector<SkinRef> GoldOutcomes(const std::string &collection, bool statTrak) const;
    std::vector<SkinRef> CrateGoldOutcomes(std::uint32_t defIndex) const;
    bool IsKnife(std::uint32_t defIndex) const;
    bool IsGlove(std::uint32_t defIndex) const;
    // Colour families of the custom collections (cs2_gc_skin_families.txt): a collection lists one family paint
    // kit per gun, and a roll grants one of its variant finishes instead. Unknown finishes are skipped.
    bool LoadSkinFamilies(std::string_view text);
    const std::vector<std::uint32_t> *SkinFamily(std::uint32_t paintKitIndex) const;
    const std::vector<std::string> &DropCollections() const { return m_dropCollections; }
    // Trade-up membership: the official item_sets, else the custom collections (set_cs2gc_case_* loot lists, which
    // can not be item_sets - see LoadSkinFamilies). A colour variant belongs where its family kit is listed.
    std::vector<std::string> TradeUpCollectionsOf(std::uint32_t weaponDefIndex, std::uint32_t paintKitIndex) const;
    const std::vector<SkinRef> &TradeUpCollectionSkins(const std::string &collection) const;
    std::vector<std::string> TradeUpCollectionNames() const; // official then custom, each sorted
    std::vector<SouvenirSticker> SouvenirStickers(std::uint32_t event) const;
    std::uint32_t SouvenirMapSticker(std::uint32_t crateDefinition) const;
    std::vector<SkinRef> MatchRewardSkins(bool weeklyOnly = true) const;
    std::vector<std::uint32_t> AgentDefinitions() const;
    bool ProducesStatTrak(std::uint32_t definition) const;
    std::string ItemName(std::uint32_t definition) const;

    // A skin as a loot entry (finish name and wear range) so a trade-up can mint it. Nothing if the
    // weapon or finish is unknown.
    std::optional<LootItem> SkinAsLootItem(std::uint32_t weaponDefIndex, std::uint32_t paintKitIndex) const;

    // The rarity value of an item definition by its own `item_rarity` (0 when it has none).
    std::uint32_t ItemRarity(std::uint32_t defIndex) const;

    // The raw loot list entries of a Store coupon item ("[kit]sticker", "[kit]musickit", a plain item
    // name, ...); empty when the item is not a coupon.
    std::vector<std::string> CouponEntries(std::uint32_t defIndex) const;

    // What a Store "coupon" item (names like "coupon - crate_xray_p250", with a `loot_list_name`) turns
    // into when opened: the items its coupon loot list names, which are plain items such as a crate.
    // Empty when the item is not a coupon or its list resolves to nothing.
    std::vector<std::uint32_t> CouponContents(std::uint32_t defIndex) const;

    // For a Sticker Slab (an item with the `can_wrap_sticker` capability): the keychain index its
    // attribute "display case keychain id" names. A sealed slab is a charm of that keychain holding a
    // sticker. Nothing for any other item.
    std::optional<std::uint32_t> SlabKeychainIndex(std::uint32_t defIndex) const;

    bool HasItem(std::uint32_t defIndex) const { return m_itemsByIndex.count(defIndex) != 0; }

    // The item definition index for an item name such as "crate_community_35".
    std::optional<std::uint32_t> ItemDefIndex(std::string_view name) const;

    // Rarity value of a paint-kit weapon as the game shows it: the finish's rarity plus the
    // weapon's base rarity minus one, capped at 6 (Covert), except explicit Contraband finish rarity is retained. Checked against the target build:
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
    std::unordered_map<std::uint32_t, std::vector<std::uint32_t>> m_skinFamilies; // family kit -> variant kits
    std::vector<std::string> m_dropCollections; // validated custom collection loot lists, never crate definitions
    std::unordered_map<std::string, std::vector<SkinRef>> m_customCollectionSkins;
    std::unordered_map<std::uint64_t, std::vector<std::string>> m_customSkinCollections; // weapon << 32 | kit
    std::unordered_map<std::string, std::uint32_t> m_rarities;
    std::unordered_map<std::string, std::string> m_paintKitRarity;       // kit name -> rarity name
    std::unordered_map<std::uint32_t, std::string> m_paintKitNames;      // kit index -> name
    std::unordered_map<std::uint32_t, const KvNode *> m_itemsByIndex;
    std::unordered_map<std::string, std::uint32_t> m_stickerKits;   // name -> index
    std::unordered_map<std::string, std::uint32_t> m_musicKits;
    std::unordered_map<std::string, std::uint32_t> m_keychains;     // name -> index
    std::vector<ArmoryRedeemable> m_armoryRedeemables;
    std::unordered_map<std::string, const KvNode *> m_prefabs;
    std::vector<SouvenirSticker> m_souvenirStickers;
    std::vector<const KvNode *> m_itemSets;
    std::unordered_map<std::string, std::vector<SkinRef>> m_collectionSkins;
    std::unordered_map<std::uint64_t, std::vector<std::string>> m_skinCollections; // weapon << 32 | kit
    std::unordered_set<std::uint64_t> m_statTrakSkins;
    std::unordered_map<std::string, std::vector<SkinRef>> m_goldPools;
    std::unordered_map<std::uint32_t, std::string> m_weaponNames;                  // definition -> class name
};
}
