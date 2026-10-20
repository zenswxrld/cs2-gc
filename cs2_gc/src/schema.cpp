#include "cs2_gc/schema.h"
#include <algorithm>
#include <charconv>
#include <unordered_set>

namespace cs2_gc
{
std::uint32_t Crc32(std::string_view text)
{
    std::uint32_t crc = 0xFFFFFFFFu;
    for (const char c : text)
    {
        crc ^= static_cast<std::uint8_t>(c);
        for (int bit = 0; bit < 8; ++bit)
            crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
    }
    return ~crc;
}

namespace
{
using ItemMap = std::unordered_map<std::string, const KvNode *>;

bool ParseU32(std::string_view text, std::uint32_t &out)
{
    const auto [end, ec] = std::from_chars(text.data(), text.data() + text.size(), out);
    return ec == std::errc{} && end == text.data() + text.size();
}

// Properties inherit through "prefab" (space separated, later names win over earlier).
const KvNode *Resolve(const KvNode &item, std::string_view property, const ItemMap &prefabs, int depth = 0)
{
    if (const KvNode *own = item.Find(property))
        return own;
    if (depth > 8)
        return nullptr;
    std::string_view list = item.Value("prefab");
    std::vector<std::string_view> names;
    while (!list.empty())
    {
        const std::size_t space = list.find(' ');
        if (space != 0)
            names.push_back(list.substr(0, space));
        if (space == std::string_view::npos)
            break;
        list.remove_prefix(space + 1);
    }
    for (auto it = names.rbegin(); it != names.rend(); ++it)
    {
        const auto prefab = prefabs.find(std::string{*it});
        if (prefab == prefabs.end())
            continue;
        if (const KvNode *found = Resolve(*prefab->second, property, prefabs, depth + 1))
            return found;
    }
    return nullptr;
}

bool HasPrefab(const KvNode &item, std::string_view wanted, const ItemMap &prefabs, int depth = 0)
{
    if (depth > 8)
        return false;
    std::string_view list = item.Value("prefab");
    while (!list.empty())
    {
        const std::size_t space = list.find(' ');
        const std::string_view name = list.substr(0, space);
        if (name == wanted)
            return true;
        const auto prefab = prefabs.find(std::string{name});
        if (!name.empty() && prefab != prefabs.end() && HasPrefab(*prefab->second, wanted, prefabs, depth + 1))
            return true;
        if (space == std::string_view::npos)
            break;
        list.remove_prefix(space + 1);
    }
    return false;
}

bool ChainContains(const KvNode &item, std::string_view fragment, const ItemMap &prefabs, int depth = 0)
{
    if (depth > 8)
        return false;
    std::string_view list = item.Value("prefab");
    while (!list.empty())
    {
        const std::size_t space = list.find(' ');
        const std::string_view name = list.substr(0, space);
        if (name.find(fragment) != std::string_view::npos)
            return true;
        const auto prefab = prefabs.find(std::string{name});
        if (!name.empty() && prefab != prefabs.end() && ChainContains(*prefab->second, fragment, prefabs, depth + 1))
            return true;
        if (space == std::string_view::npos)
            break;
        list.remove_prefix(space + 1);
    }
    return false;
}

CrateKind Classify(const KvNode &item, std::uint32_t keyDefIndex, const ItemMap &prefabs)
{
    if (ChainContains(item, "_capsule", prefabs))
        return CrateKind::Capsule;
    if (ChainContains(item, "graffiti_box", prefabs))
        return CrateKind::GraffitiBox;
    if (keyDefIndex == 0 && item.Value("name").starts_with("crate_pins_"))
        return CrateKind::Pins;
    return keyDefIndex != 0 ? CrateKind::Case : CrateKind::Other;
}

std::string_view ResolveValue(const KvNode &item, std::string_view property, const ItemMap &prefabs)
{
    const KvNode *node = Resolve(item, property, prefabs);
    return node && !node->block ? std::string_view{node->value} : std::string_view{};
}

std::uint32_t CrateSeries(const KvNode &item, const ItemMap &prefabs)
{
    const KvNode *attributes = Resolve(item, "attributes", prefabs);
    if (!attributes)
        return 0;
    const KvNode *series = attributes->Find("set supply crate series");
    std::uint32_t value = 0;
    if (!series || !ParseU32(series->Value("value"), value))
        return 0;
    return value;
}

std::uint32_t KeyDefIndex(const KvNode &item, const ItemMap &prefabs)
{
    std::uint32_t key = 0;
    if (const KvNode *associated = Resolve(item, "associated_items", prefabs))
    {
        if (!associated->children.empty() && ParseU32(associated->children.front().key, key))
            return key;
    }
    if (ParseU32(ResolveValue(item, "associated_item", prefabs), key))
        return key;
    return 0;
}
}

std::optional<Schema> Schema::Load(std::string_view itemsGameText)
{
    auto parsed = ParseKeyValues(itemsGameText);
    if (!parsed)
        return std::nullopt;
    if (!parsed->Find("items_game"))
        return std::nullopt;

    Schema schema;
    schema.m_root = std::move(*parsed);
    const KvNode &root = *schema.m_root.Find("items_game");

    ItemMap prefabs;
    std::vector<const KvNode *> itemNodes;
    std::unordered_map<std::string, const KvNode *> revolving;
    for (const KvNode &section : root.children)
    {
        if (!section.block)
            continue;
        for (const KvNode &entry : section.children)
        {
            if (section.key == "prefabs")
                prefabs[entry.key] = &entry;
            else if (section.key == "items" && entry.block)
                itemNodes.push_back(&entry);
            else if (section.key == "client_loot_lists" && entry.block)
                schema.m_lootLists[entry.key] = &entry;
            else if (section.key == "item_sets" && entry.block)
                schema.m_itemSets.push_back(&entry);
            else if (section.key == "revolving_loot_lists" && !entry.block)
                revolving[entry.key] = &entry;
            else if (section.key == "paint_kits" && entry.block)
            {
                schema.m_paintKits[std::string{entry.Value("name")}] = &entry;
                std::uint32_t index = 0;
                if (ParseU32(entry.key, index))
                    schema.m_paintKitNames[index] = std::string{entry.Value("name")};
            }
            else if (section.key == "paint_kits_rarity" && !entry.block)
                schema.m_paintKitRarity[entry.key] = entry.value;
            else if (section.key == "sticker_kits" && entry.block)
            {
                std::uint32_t index = 0;
                if (ParseU32(entry.key, index) && !entry.Value("name").empty())
                    schema.m_stickerKits.try_emplace(std::string{entry.Value("name")}, index);
            }
            else if (section.key == "keychain_definitions" && entry.block)
            {
                std::uint32_t index = 0;
                if (ParseU32(entry.key, index) && !entry.Value("name").empty())
                    schema.m_keychains.try_emplace(std::string{entry.Value("name")}, index);
            }
            else if (section.key == "seasonaloperations" && entry.block && entry.Value("redeemable_goods") == "xpshop")
            {
                std::uint32_t campaign = 0;
                if (ParseU32(entry.key, campaign))
                {
                    std::uint32_t shopIndex = 0;
                    for (const KvNode &good : entry.children)
                    {
                        if (good.key != "operational_point_redeemable" || !good.block)
                            continue;
                        ArmoryRedeemable armory;
                        armory.campaignId = campaign;
                        armory.shopIndex = shopIndex++;
                        armory.itemName = good.Value("item_name");
                        if (!ParseU32(good.Value("points"), armory.points) || armory.itemName.empty())
                            continue; // an unusable tile still occupies its position in the game's list
                        armory.redeemId = Crc32(armory.itemName);
                        schema.m_armoryRedeemables.push_back(std::move(armory));
                    }
                }
            }
            else if (section.key == "rarities" && entry.block)
            {
                std::uint32_t value = 0;
                if (ParseU32(entry.Value("value"), value))
                    schema.m_rarities[entry.key] = value;
            }
        }
    }

    schema.m_prefabs = prefabs;
    for (const KvNode *item : itemNodes)
    {
        std::uint32_t defIndex = 0;
        if (ParseU32(item->key, defIndex))
        {
            schema.m_itemsByIndex[defIndex] = item;
            if (!item->Value("name").empty())
                schema.m_itemsByName[std::string{item->Value("name")}] = defIndex;
        }
    }

    for (const KvNode *item : itemNodes)
    {
        std::uint32_t defIndex = 0;
        if (!ParseU32(item->key, defIndex) || !HasPrefab(*item, "weapon_case_base", prefabs) ||
            HasPrefab(*item, "weapon_case_souvenirpkg", prefabs))
            continue;
        const std::uint32_t series = CrateSeries(*item, prefabs);
        if (series == 0)
            continue;

        CrateInfo crate;
        crate.defIndex = defIndex;
        crate.name = item->Value("name");
        std::string_view token = ResolveValue(*item, "item_name", prefabs);
        if (token.starts_with('#'))
            token.remove_prefix(1);
        crate.nameToken = token;
        crate.series = series;
        crate.keyDefIndex = KeyDefIndex(*item, prefabs);
        crate.kind = Classify(*item, crate.keyDefIndex, prefabs);
        const auto list = revolving.find(std::to_string(series));
        if (list != revolving.end())
            crate.lootListName = list->second->value;
        schema.m_crateIndex[defIndex] = schema.m_crates.size();
        schema.m_crates.push_back(std::move(crate));
    }

    // Index the collections once everything they refer to is known. Only "[finish]weapon" entries that resolve
    // to a skin count; stickers, charms, music kits and the like are not trade-up material.
    for (const auto &[name, definition] : schema.m_itemsByName)
        schema.m_weaponNames.emplace(definition, name);
    for (const KvNode *set : schema.m_itemSets)
    {
        const KvNode *items = set->Find("items");
        if (!items || !items->block)
            continue;
        std::vector<SkinRef> &skins = schema.m_collectionSkins[set->key];
        for (const KvNode &entry : items->children)
        {
            const auto skin = schema.ResolveLootItem(entry.key);
            if (!skin || skin->kind != LootKind::Skin)
                continue;
            skins.push_back({skin->weaponDefIndex, skin->paintKitIndex});
            schema.m_skinCollections[(std::uint64_t{skin->weaponDefIndex} << 32) | skin->paintKitIndex].push_back(set->key);
        }
    }
    for (auto &[key, names] : schema.m_skinCollections)
    {
        std::sort(names.begin(), names.end());
        names.erase(std::unique(names.begin(), names.end()), names.end());
    }
    return schema;
}

std::vector<std::string> Schema::CollectionsOf(std::uint32_t weaponDefIndex, std::uint32_t paintKitIndex) const
{
    const auto found = m_skinCollections.find((std::uint64_t{weaponDefIndex} << 32) | paintKitIndex);
    return found == m_skinCollections.end() ? std::vector<std::string>{} : found->second;
}

const std::vector<SkinRef> &Schema::CollectionSkins(const std::string &collection) const
{
    static const std::vector<SkinRef> none;
    const auto found = m_collectionSkins.find(collection);
    return found == m_collectionSkins.end() ? none : found->second;
}

std::optional<LootItem> Schema::SkinAsLootItem(std::uint32_t weaponDefIndex, std::uint32_t paintKitIndex) const
{
    const auto weapon = m_weaponNames.find(weaponDefIndex);
    const auto kit = m_paintKitNames.find(paintKitIndex);
    if (weapon == m_weaponNames.end() || kit == m_paintKitNames.end())
        return std::nullopt;
    auto item = ResolveLootItem("[" + kit->second + "]" + weapon->second);
    return item && item->kind == LootKind::Skin ? item : std::nullopt;
}

const CrateInfo *Schema::FindCrate(std::uint32_t defIndex) const
{
    const auto it = m_crateIndex.find(defIndex);
    return it == m_crateIndex.end() ? nullptr : &m_crates[it->second];
}

std::vector<LootTier> Schema::LootTiers(std::string_view lootListName) const
{
    std::vector<LootTier> tiers;
    std::unordered_set<std::string> visiting;

    struct Walker
    {
        const Schema &schema;
        std::vector<LootTier> &tiers;
        std::unordered_set<std::string> &visiting;

        void Visit(const std::string &name, int depth)
        {
            const auto it = schema.m_lootLists.find(name);
            if (it == schema.m_lootLists.end() || depth > 8 || !visiting.insert(name).second)
                return;
            const KvNode &list = *it->second;
            bool leaf = true;
            for (const KvNode &child : list.children)
                if (!child.block && schema.m_lootLists.contains(child.key))
                    leaf = false;
            if (leaf)
            {
                LootTier tier;
                tier.name = name;
                const std::size_t underscore = name.rfind('_');
                if (underscore != std::string::npos)
                {
                    const auto rarity = schema.m_rarities.find(name.substr(underscore + 1));
                    if (rarity != schema.m_rarities.end())
                        tier.rarity = rarity->second;
                }
                for (const KvNode &child : list.children)
                    if (!child.block)
                        tier.items.push_back(child.key);
                tiers.push_back(std::move(tier));
            }
            else
            {
                for (const KvNode &child : list.children)
                    if (!child.block)
                        Visit(child.key, depth + 1);
            }
            visiting.erase(name);
        }
    };

    Walker{*this, tiers, visiting}.Visit(std::string{lootListName}, 0);
    return tiers;
}

const ArmoryRedeemable *Schema::FindRedeemable(std::uint32_t campaignId, std::uint32_t redeemId) const
{
    for (const ArmoryRedeemable &good : m_armoryRedeemables)
        if (good.campaignId == campaignId && good.redeemId == redeemId)
            return &good;
    return nullptr;
}

std::uint32_t Schema::ItemRarity(std::uint32_t defIndex) const
{
    const auto item = m_itemsByIndex.find(defIndex);
    if (item == m_itemsByIndex.end())
        return 0;
    const auto rarity = m_rarities.find(std::string{ResolveValue(*item->second, "item_rarity", m_prefabs)});
    return rarity == m_rarities.end() ? 0 : rarity->second;
}

std::vector<std::string> Schema::CouponEntries(std::uint32_t defIndex) const
{
    std::vector<std::string> entries;
    const auto item = m_itemsByIndex.find(defIndex);
    if (item == m_itemsByIndex.end())
        return entries;
    const std::string_view listName = item->second->Value("loot_list_name");
    if (!listName.starts_with("coupon loot list"))
        return entries;
    const auto list = m_lootLists.find(std::string{listName});
    if (list == m_lootLists.end())
        return entries;
    for (const KvNode &entry : list->second->children)
        if (!entry.block && entry.key != "public_list_contents")
            entries.push_back(entry.key);
    return entries;
}

std::vector<std::uint32_t> Schema::CouponContents(std::uint32_t defIndex) const
{
    std::vector<std::uint32_t> contents;
    for (const std::string &entry : CouponEntries(defIndex))
        if (const auto definition = ItemDefIndex(entry))
            contents.push_back(*definition);
    return contents;
}

std::optional<std::uint32_t> Schema::SlabKeychainIndex(std::uint32_t defIndex) const
{
    const auto item = m_itemsByIndex.find(defIndex);
    if (item == m_itemsByIndex.end())
        return std::nullopt;
    const KvNode *capabilities = item->second->Find("capabilities");
    const KvNode *attributes = item->second->Find("attributes");
    if (!capabilities || !attributes || capabilities->Value("can_wrap_sticker") != "1")
        return std::nullopt;
    std::uint32_t keychain = 0;
    if (!ParseU32(attributes->Value("display case keychain id"), keychain) || keychain == 0)
        return std::nullopt;
    return keychain;
}

std::optional<std::uint32_t> Schema::ItemDefIndex(std::string_view name) const
{
    const auto it = m_itemsByName.find(std::string{name});
    return it == m_itemsByName.end() ? std::nullopt : std::optional<std::uint32_t>{it->second};
}

std::optional<LootItem> Schema::ResolveLootItem(std::string_view entry) const
{
    if (!entry.starts_with('['))
    {
        // A plain item name, as the collectible pin capsules list them.
        const auto plain = m_itemsByName.find(std::string{entry});
        if (plain == m_itemsByName.end())
            return std::nullopt;
        LootItem item;
        item.kind = LootKind::Plain;
        item.weaponDefIndex = plain->second;
        return item;
    }
    const std::size_t close = entry.find(']');
    if (close == std::string_view::npos)
        return std::nullopt;

    LootItem item;
    item.paintKitName = entry.substr(1, close - 1);
    item.weaponClass = entry.substr(close + 1);

    const auto weapon = m_itemsByName.find(item.weaponClass);
    if (weapon == m_itemsByName.end())
        return std::nullopt;
    item.weaponDefIndex = weapon->second;

    if (item.weaponClass == "sticker")
    {
        const auto kit = m_stickerKits.find(item.paintKitName);
        if (kit == m_stickerKits.end())
            return std::nullopt;
        item.kind = LootKind::Sticker;
        item.stickerKitIndex = kit->second;
        return item;
    }
    if (item.weaponClass == "keychain")
    {
        const auto charm = m_keychains.find(item.paintKitName);
        if (charm == m_keychains.end())
            return std::nullopt;
        item.kind = LootKind::Keychain;
        item.keychainIndex = charm->second;
        return item;
    }

    const auto kit = m_paintKits.find(item.paintKitName);
    if (kit == m_paintKits.end() || !ParseU32(kit->second->key, item.paintKitIndex))
        return std::nullopt;

    const auto parseWear = [&](std::string_view name, float &out) {
        const std::string_view text = kit->second->Value(name);
        float value = 0.0f;
        const auto [end, ec] = std::from_chars(text.data(), text.data() + text.size(), value);
        if (ec == std::errc{} && end == text.data() + text.size())
            out = value;
    };
    parseWear("wear_remap_min", item.wearMin);
    parseWear("wear_remap_max", item.wearMax);
    if (item.wearMin > item.wearMax || item.wearMin < 0.0f || item.wearMax > 1.0f)
        return std::nullopt;
    return item;
}

std::optional<std::uint32_t> Schema::SkinRarity(std::uint32_t weaponDefIndex, std::uint32_t paintKitIndex) const
{
    const auto weapon = m_itemsByIndex.find(weaponDefIndex);
    const auto kitName = m_paintKitNames.find(paintKitIndex);
    if (weapon == m_itemsByIndex.end() || kitName == m_paintKitNames.end())
        return std::nullopt;
    const auto kitRarity = m_paintKitRarity.find(kitName->second);
    if (kitRarity == m_paintKitRarity.end())
        return std::nullopt;
    const auto kit = m_rarities.find(kitRarity->second);
    const auto base = m_rarities.find(std::string{ResolveValue(*weapon->second, "item_rarity", m_prefabs)});
    if (kit == m_rarities.end() || base == m_rarities.end() || kit->second == 0 || base->second == 0)
        return std::nullopt;
    constexpr std::uint32_t Covert = 6;
    const std::uint32_t combined = kit->second + base->second - 1;
    return combined > Covert ? Covert : combined;
}
}
