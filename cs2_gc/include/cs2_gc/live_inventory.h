#pragma once

#include "cs2_gc/case_opening.h"
#include "cs2_gc/gc_handshake.h"
#include "cs2_gc/trade_up.h"
#include "cs2_gc/inventory.h"
#include <cstdint>
#include <filesystem>
#include <optional>
#include <vector>

namespace cs2_gc
{
// The inventory as the game sees it during a session: the items plus which item is in which loadout
// slot. Slots save with the inventory and are restored for client/server welcomes.
class LiveInventory
{
public:
    explicit LiveInventory(Inventory inventory);

    const Inventory &Items() const { return m_inventory; }
    std::vector<std::vector<std::uint8_t>> EncodedServerItems(std::uint32_t accountId) const;
    struct TerminalChange
    {
        InventoryItem terminal;
        std::optional<InventoryItem> offer;
        std::vector<InventoryItem> removed;
        bool unsealed{};
        bool exhausted{};
    };
    std::optional<TerminalChange> AdvanceTerminal(const Schema &schema, const OpenCrateRequest &request,
                                                const RandomSource &random, std::uint32_t now);
    std::optional<InventoryItem> TerminalOffer(const Schema &schema, std::uint64_t gameId) const;
    std::optional<TerminalChange> AcceptTerminal(const Schema &schema, std::uint64_t gameId);
    void SetArmoryCredits(std::uint32_t credits) { m_inventory.SetArmoryCredits(credits); }
    bool ApplyConsoleStars(std::uint64_t cumulative) { return m_inventory.ApplyConsoleStars(cumulative); }
    void SetArmoryPity(const std::string &collection, std::uint32_t misses) { m_inventory.SetArmoryPity(collection, misses); }
    std::optional<std::vector<InventoryItem>> GrantMatchRewards(const Schema &schema, std::uint64_t completed,
                                                               const RandomSource &random)
    {
        if (completed <= m_inventory.MatchRewardTotal()) return std::nullopt;
        if (!m_inventory.Gameplay().match_drops_enabled)
        {
            m_inventory.MarkMatchRewarded();
            return std::vector<InventoryItem>{};
        }
        auto config = m_inventory.Gameplay();
        if (config.care_packages_enabled) config.match_drop_count = 4;
        auto drops = RollMatchDrops(schema, random, config);
        if (!drops) return std::nullopt;
        if (config.care_packages_enabled)
        {
            if (!m_inventory.QueueCarePackage(*drops)) return std::nullopt;
            m_inventory.MarkMatchRewarded(); return std::vector<InventoryItem>{};
        }
        for (auto &item : *drops) item = AddItem(item);
        m_inventory.MarkMatchRewarded();
        return drops;
    }
    std::optional<std::vector<InventoryItem>> ClaimCarePackage(std::uint32_t generation, const std::vector<std::uint64_t> &ids)
    { return m_inventory.ClaimCarePackage(generation,ids); }
    bool ApplyEarnedXp(std::uint64_t cumulativeXp) { return m_inventory.ApplyEarnedXp(cumulativeXp); }
    std::optional<std::vector<InventoryItem>> GrantLevelRewards(const Schema &schema, const RandomSource &random)
    {
        if (m_inventory.LevelRewardTotal() >= m_inventory.Progress().level - 1) return std::nullopt;
        if (!m_inventory.Gameplay().level_drops_enabled)
        {
            m_inventory.MarkLevelRewarded();
            return std::vector<InventoryItem>{};
        }
        auto config = m_inventory.Gameplay();
        config.match_drops_enabled = 1; // level rewards are independent of the match-drop switch
        config.match_drop_count = config.care_packages_enabled ? 4u : config.level_drop_count;
        auto drops = RollMatchDrops(schema, random, config);
        if (!drops) return std::nullopt;
        if (config.care_packages_enabled)
        {
            if (!m_inventory.QueueCarePackage(*drops)) return std::nullopt;
            m_inventory.MarkLevelRewarded(); return std::vector<InventoryItem>{};
        }
        for (auto &item : *drops) item = AddItem(item);
        m_inventory.MarkLevelRewarded();
        return drops;
    }

    // Activates one more Armory Pass, starting at `xp`; false when MaxXpTracks are already active.
    bool AddXpTrack(std::uint32_t xp);

    // Adds an item to the inventory and returns it with its new id (the game sees it as
    // CustomItemIdBase + id).
    InventoryItem AddItem(InventoryItem item);
    // free_case_keys: one matching key for every keyed case type owned. Returns the keys added.
    std::vector<InventoryItem> EnsureCaseKeys(const Schema &schema);

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
        bool created{};                    // the item is new: a built-in weapon that became an inventory item
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

    struct Detached
    {
        InventoryItem weapon;     // the weapon without its charm
        std::uint32_t position{};
        InventoryItem charm;      // the charm, now a loose item again
    };

    // Takes the charm off one of our weapons and returns it to the inventory as an item of its own. Nothing
    // if the item is not ours or carries no charm.
    std::optional<Detached> DetachCharm(std::uint64_t weaponItemId);

    // A trade-up contract over ten of our items (ids as the game sees them). Nothing changes on failure.
    TradeUpResult TradeUp(const Schema &schema, const std::vector<std::uint64_t> &gameItemIds,
                          const RandomSource &random);

    struct Scraped
    {
        InventoryItem item;        // the weapon after the scrape
        std::uint32_t position{};
        bool removed{};            // the sticker wore away completely
    };

    // Scrapes the sticker in one slot of one of our items. With a target (the level chosen on the scrape
    // slider) its wear goes to that level, never down, and a target of 1 or more removes it; without one
    // the wear rises by a ninth and past 1 the sticker is removed. Nothing if the item is not ours or has
    // no sticker in that slot.
    std::optional<Scraped> ScrapeSticker(std::uint64_t itemId, std::uint32_t slot,
                                         std::optional<float> target = std::nullopt);

    // Strips stickers and charms from Sticker Slabs. An earlier build wrote a sticker onto a slab item
    // (as if it were a weapon), saved it, and the game crashed on it. Returns how many items were repaired.
    std::size_t RepairStoreCoupons(const Schema &schema);
    std::size_t RepairSlabs(const Schema &schema);

    // Earlier Armory rolls incorrectly assigned hidden StatTrak to collection-only finishes.
    // Also clears invalid glove StatTrak, preserving ids, finishes, wear and equipped slots.
    // Valid case/mixed-contract weapon StatTrak remains unchanged.
    std::size_t RepairCollectionStatTrak(const Schema &schema);

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
    Inventory m_inventory;
};
}
