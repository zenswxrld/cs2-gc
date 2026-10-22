#pragma once
#include "cs2_gc/progression.h"
#include "cs2_gc/gameplay_config.h"

#include <cstdint>
#include <filesystem>
#include <optional>
#include <string>
#include <string_view>
#include <vector>
#include <map>

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
    bool noStarSale{}; // free Store charm; preserved through attaching/detaching
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
    bool unusual{}; // rare special knife/gloves, including StatTrak knives
    std::optional<std::uint32_t> terminalRemaining;
    std::uint32_t expiration{};
    std::optional<std::uint32_t> purchasePrice;
    bool ownerCertificate{}; // accepted terminal offer: shows the Original Owner Certificate (purchaser account id)
    std::uint32_t musicKit{}; // music id attribute (166)
    bool souvenir{};
    std::uint32_t tournamentEvent{}, tournamentTeam0{}, tournamentTeam1{}, tournamentPlayer{};
    bool statTrakFromContract{}; // preserve intentional local mixed-contract variants across startup repair
    bool noStarSale{}; // free Store grants and derivatives cannot mint stars; terminal offers exempt
};

struct CarePackage
{
    std::uint32_t generation{};
    std::vector<InventoryItem> offers;
};

// The last claimed package, kept on show (claimed / not chosen) until the next one arrives, like Valve's store.
struct ClaimedCareSlot { std::uint32_t defIndex{}, paintKitIndex{}; std::uint64_t ownedId{}; }; // ownedId 0: not chosen
struct ClaimedCarePackage { std::uint32_t generation{}; std::vector<ClaimedCareSlot> slots; };

struct LoadoutSlot
{
    std::uint32_t classId{}, slotId{};
    std::uint64_t itemId{};
    std::uint32_t itemDefinition{};
};

// Local inventory and loadout, persisted together.
class Inventory
{
public:
    const GameplayConfig &Gameplay() const { return m_gameplay; }
    void SetGameplay(const GameplayConfig &config);
    std::vector<std::uint32_t> DisplayXpTracks() const;
    std::uint64_t Add(InventoryItem item); // assigns and returns a fresh id
    bool Remove(std::uint64_t id);
    const InventoryItem *Find(std::uint64_t id) const;
    InventoryItem *Find(std::uint64_t id);
    const std::vector<InventoryItem> &Items() const { return m_items; }
    const std::vector<LoadoutSlot> &Loadout() const { return m_loadout; }
    std::vector<LoadoutSlot> &Loadout() { return m_loadout; }

    // The Armory passes the player has activated: one XP value each, saved with the items.
    const std::vector<std::uint32_t> &XpTracks() const { return m_xpTracks; }
    std::vector<std::uint32_t> &XpTracks() { return m_xpTracks; }
    std::optional<std::uint32_t> ArmoryCredits() const { return m_armoryCredits; }
    void SetArmoryCredits(std::uint32_t credits) { m_armoryCredits = credits; }
    bool ApplyConsoleStars(std::uint64_t cumulative);
    // Stars paid by mission steps: the rewards helper's cumulative total, so a step never pays twice.
    bool ApplyMissionStars(std::uint64_t cumulative);
    const LocalProgress &Progress() const { return m_progress; }
    bool ApplyEarnedXp(std::uint64_t cumulativeXp);
    std::uint64_t MatchRewardTotal() const { return m_matchRewardTotal; }
    void MarkMatchRewarded() { ++m_matchRewardTotal; }
    std::uint32_t LevelRewardTotal() const { return m_levelRewardTotal; }
    void MarkLevelRewarded() { ++m_levelRewardTotal; }
    std::uint32_t CasePity() const { return m_casePity; }
    void SetCasePity(std::uint32_t failures) { m_casePity = failures; }
    std::uint32_t TerminalPity(std::uint32_t defIndex) const
    {
        const auto found = m_terminalPity.find(defIndex);
        return found == m_terminalPity.end() ? 0 : found->second;
    }
    void SetTerminalPity(std::uint32_t defIndex, std::uint32_t failures) { m_terminalPity[defIndex] = failures; }
    std::uint32_t ArmoryPity(const std::string &collection) const
    {
        const auto found = m_armoryPity.find(collection);
        return found == m_armoryPity.end() ? 0 : found->second;
    }
    void SetArmoryPity(const std::string &collection, std::uint32_t failures) { m_armoryPity[collection] = failures; }

    const std::vector<CarePackage> &CarePackages() const { return m_carePackages; }
    const std::optional<ClaimedCarePackage> &LastClaimedCarePackage() const { return m_lastClaimedCare; }
    bool QueueCarePackage(std::vector<InventoryItem> offers);
    std::optional<std::vector<InventoryItem>> ClaimCarePackage(std::uint32_t generation,
                                                             const std::vector<std::uint64_t> &ids);

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
    GameplayConfig m_gameplay{BalancedDefaults()};
    std::uint32_t m_trackXpPerStar{400};
    std::vector<InventoryItem> m_items;
    std::vector<LoadoutSlot> m_loadout;
    std::vector<std::uint32_t> m_xpTracks;
    std::optional<std::uint32_t> m_armoryCredits;
    LocalProgress m_progress;
    std::uint64_t m_matchRewardTotal{};
    std::uint64_t m_consoleStarTotal{};
    std::uint64_t m_missionStarTotal{};
    std::uint32_t m_levelRewardTotal{}; // profile levels already rewarded, excluding starting level 1
    std::uint32_t m_casePity{};
    std::map<std::uint32_t, std::uint32_t> m_terminalPity;
    std::map<std::string, std::uint32_t> m_armoryPity;
    std::vector<CarePackage> m_carePackages;
    std::uint32_t m_lastCareGeneration{};
    std::optional<ClaimedCarePackage> m_lastClaimedCare;
    std::uint64_t m_nextId{1};
};
}
