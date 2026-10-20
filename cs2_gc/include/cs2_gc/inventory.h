#pragma once

#include <cstdint>
#include <filesystem>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace cs2_gc
{
// A sticker applied to a weapon slot (0-4), as the game's apply screen placed it.
struct AppliedSticker
{
    std::uint32_t slot{};
    std::uint32_t kit{};
    float wear{};
    float scale{};    // zero when the client left it unset
    float rotation{};
    float offsetX{};
    float offsetY{};
};

inline constexpr std::uint32_t StickerSlotCount = 5;

// A charm attached to a weapon (one per weapon), with the offsets the apply screen placed it at.
struct AppliedKeychain
{
    std::uint32_t kit{};
    float offsetX{};
    float offsetY{};
    float offsetZ{};
    std::uint32_t slabSticker{}; // for a sealed Sticker Slab: the sticker kit inside it
};

inline constexpr std::size_t MaxXpTracks = 5; // the Armory page has room for five passes

struct InventoryItem
{
    std::uint64_t id{};
    std::uint32_t defIndex{};
    std::uint32_t paintKitIndex{}; // zero for items without a finish
    float wear{};
    std::uint32_t seed{};
    bool statTrak{};
    std::uint32_t rarity{}; // rarities value from the schema; zero leaves it to the client
    std::uint32_t stickerKit{}; // for a sticker (or graffiti) item: the sticker kit index; zero otherwise
    std::uint32_t keychain{};   // for a charm item: the keychain index; zero otherwise
    std::uint32_t slabSticker{};          // for a charm that is a sealed Sticker Slab: the sticker kit inside
    std::uint64_t storedIn{};             // our id of the storage unit this item is in; zero when loose
    std::uint32_t casketCount{};          // for a storage unit: how many items are in it
    std::uint32_t casketModified{};       // for a storage unit: unix time of its last change
    std::string customName;               // set with a name tag; empty when none
    std::vector<AppliedSticker> stickers;
    std::optional<AppliedKeychain> charm; // the charm attached to this weapon, if any // stickers applied to this item, one per slot
};

// Local, in-memory inventory. Persistence and client sync are not wired yet.
class Inventory
{
public:
    std::uint64_t Add(InventoryItem item); // assigns and returns a fresh id
    bool Remove(std::uint64_t id);
    const InventoryItem *Find(std::uint64_t id) const;
    InventoryItem *Find(std::uint64_t id);
    const std::vector<InventoryItem> &Items() const { return m_items; }

    // The Armory passes the player has activated: one XP value each, saved with the items.
    const std::vector<std::uint32_t> &XpTracks() const { return m_xpTracks; }
    std::vector<std::uint32_t> &XpTracks() { return m_xpTracks; }

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
    std::vector<std::uint32_t> m_xpTracks;
    std::uint64_t m_nextId{1};
};
}
