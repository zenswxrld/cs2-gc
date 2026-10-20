#include "cs2_gc/inventory.h"
#include "cs2_gc/keyvalues.h"
#include <algorithm>
#include <charconv>
#include <cmath>
#include <fstream>
#include <set>
#include <sstream>

namespace cs2_gc
{
std::uint64_t Inventory::Add(InventoryItem item)
{
    item.id = m_nextId++;
    m_items.push_back(item);
    return item.id;
}

bool Inventory::Remove(std::uint64_t id)
{
    const auto it = std::find_if(m_items.begin(), m_items.end(), [id](const InventoryItem &i) { return i.id == id; });
    if (it == m_items.end())
        return false;
    m_items.erase(it);
    return true;
}

const InventoryItem *Inventory::Find(std::uint64_t id) const
{
    const auto it = std::find_if(m_items.begin(), m_items.end(), [id](const InventoryItem &i) { return i.id == id; });
    return it == m_items.end() ? nullptr : &*it;
}

namespace
{
template <typename T>
bool ParseNumber(std::string_view text, T &out)
{
    const auto [end, ec] = std::from_chars(text.data(), text.data() + text.size(), out);
    return ec == std::errc{} && end == text.data() + text.size();
}

std::string FloatText(float value)
{
    char buffer[32];
    const auto result = std::to_chars(buffer, buffer + sizeof(buffer), value);
    return std::string(buffer, result.ptr);
}
}

std::string Inventory::ToText() const
{
    std::ostringstream out;
    out << "\"inventory\"\n{\n\t\"next_id\"\t\"" << m_nextId << "\"\n\t\"items\"\n\t{\n";
    for (const InventoryItem &item : m_items)
    {
        out << "\t\t\"" << item.id << "\"\n\t\t{\n"
            << "\t\t\t\"def_index\"\t\"" << item.defIndex << "\"\n"
            << "\t\t\t\"paint_kit\"\t\"" << item.paintKitIndex << "\"\n"
            << "\t\t\t\"wear\"\t\"" << FloatText(item.wear) << "\"\n"
            << "\t\t\t\"seed\"\t\"" << item.seed << "\"\n"
            << "\t\t\t\"stattrak\"\t\"" << (item.statTrak ? 1 : 0) << "\"\n"
            << "\t\t\t\"rarity\"\t\"" << item.rarity << "\"\n"
            << "\t\t}\n";
    }
    out << "\t}\n}\n";
    return out.str();
}

std::optional<Inventory> Inventory::FromText(std::string_view text)
{
    const auto parsed = ParseKeyValues(text);
    const KvNode *root = parsed ? parsed->Find("inventory") : nullptr;
    const KvNode *items = root ? root->Find("items") : nullptr;
    if (!root || !root->block || !items || !items->block)
        return std::nullopt;

    Inventory inventory;
    if (!ParseNumber(root->Value("next_id"), inventory.m_nextId) || inventory.m_nextId == 0)
        return std::nullopt;

    std::set<std::uint64_t> seen;
    for (const KvNode &entry : items->children)
    {
        InventoryItem item;
        std::uint32_t statTrak = 0;
        if (!entry.block || !ParseNumber(entry.key, item.id) || item.id == 0 || item.id >= inventory.m_nextId ||
            !seen.insert(item.id).second || !ParseNumber(entry.Value("def_index"), item.defIndex) ||
            item.defIndex == 0 || !ParseNumber(entry.Value("paint_kit"), item.paintKitIndex) ||
            !ParseNumber(entry.Value("wear"), item.wear) || !std::isfinite(item.wear) || item.wear < 0.0f ||
            item.wear > 1.0f || !ParseNumber(entry.Value("seed"), item.seed) || item.seed > 1000 ||
            !ParseNumber(entry.Value("stattrak"), statTrak) || statTrak > 1)
            return std::nullopt;
        // Optional so files written before the field existed still load.
        if (entry.Find("rarity") && (!ParseNumber(entry.Value("rarity"), item.rarity) || item.rarity > 99))
            return std::nullopt;
        item.statTrak = statTrak == 1;
        inventory.m_items.push_back(item);
    }
    return inventory;
}

bool Inventory::Save(const std::filesystem::path &path) const
{
    std::filesystem::path temp = path;
    temp += ".tmp";
    {
        std::ofstream file(temp, std::ios::binary | std::ios::trunc);
        const std::string text = ToText();
        file.write(text.data(), static_cast<std::streamsize>(text.size()));
        file.flush();
        if (!file)
        {
            std::error_code ignored;
            std::filesystem::remove(temp, ignored);
            return false;
        }
    }
    std::error_code error;
    std::filesystem::rename(temp, path, error); // replaces an existing file
    if (error)
    {
        std::filesystem::remove(temp, error);
        return false;
    }
    return true;
}

std::optional<Inventory> Inventory::Load(const std::filesystem::path &path)
{
    std::ifstream file(path, std::ios::binary);
    if (!file)
        return std::nullopt;
    std::ostringstream buffer;
    buffer << file.rdbuf();
    return FromText(buffer.str());
}
}
