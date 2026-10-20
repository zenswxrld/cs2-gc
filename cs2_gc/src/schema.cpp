#include "cs2_gc/schema.h"
#include <charconv>
#include <unordered_set>

namespace cs2_gc
{
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
            else if (section.key == "revolving_loot_lists" && !entry.block)
                revolving[entry.key] = &entry;
        }
    }

    ItemMap itemsByIndex;
    for (const KvNode *item : itemNodes)
        itemsByIndex[item->key] = item;

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
    return schema;
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
}
