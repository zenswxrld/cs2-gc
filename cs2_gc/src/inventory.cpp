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

InventoryItem *Inventory::Find(std::uint64_t id)
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

bool ParseSticker(std::string_view text, AppliedSticker &sticker)
{
    float *floats[] = {&sticker.wear, &sticker.scale, &sticker.rotation, &sticker.offsetX, &sticker.offsetY};
    auto next = [&text]() {
        const auto end = text.find(' ');
        const std::string_view word = text.substr(0, end);
        text = end == std::string_view::npos ? std::string_view{} : text.substr(end + 1);
        return word;
    };
    if (!ParseNumber(next(), sticker.kit) || sticker.kit == 0)
        return false;
    for (float *value : floats)
        if (!ParseNumber(next(), *value) || !std::isfinite(*value))
            return false;
    return text.empty();
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
            << "\t\t\t\"sticker_kit\"\t\"" << item.stickerKit << "\"\n"
            << "\t\t\t\"keychain\"\t\"" << item.keychain << "\"\n";
        if (!item.customName.empty())
            out << "\t\t\t\"custom_name\"\t\"" << item.customName << "\"\n";
        if (item.charm)
            out << "\t\t\t\"charm\"\t\"" << item.charm->kit << ' ' << FloatText(item.charm->offsetX) << ' '
                << FloatText(item.charm->offsetY) << ' ' << FloatText(item.charm->offsetZ) << "\"\n";
        for (const AppliedSticker &sticker : item.stickers)
            out << "\t\t\t\"sticker_" << sticker.slot << "\"\t\"" << sticker.kit << ' ' << FloatText(sticker.wear)
                << ' ' << FloatText(sticker.scale) << ' ' << FloatText(sticker.rotation) << ' '
                << FloatText(sticker.offsetX) << ' ' << FloatText(sticker.offsetY) << "\"\n";
        out << "\t\t}\n";
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
        if ((entry.Find("sticker_kit") && !ParseNumber(entry.Value("sticker_kit"), item.stickerKit)) ||
            (entry.Find("keychain") && !ParseNumber(entry.Value("keychain"), item.keychain)))
            return std::nullopt;
        for (std::uint32_t slot = 0; slot < StickerSlotCount; ++slot)
        {
            const KvNode *node = entry.Find("sticker_" + std::to_string(slot));
            if (!node)
                continue;
            AppliedSticker sticker;
            sticker.slot = slot;
            if (node->block || !ParseSticker(node->value, sticker))
                return std::nullopt;
            item.stickers.push_back(sticker);
        }
        if (const KvNode *charm = entry.Find("charm"))
        {
            AppliedKeychain applied;
            float *offsets[] = {&applied.offsetX, &applied.offsetY, &applied.offsetZ};
            std::string_view text = charm->value;
            auto next = [&text]() {
                const auto end = text.find(' ');
                const std::string_view word = text.substr(0, end);
                text = end == std::string_view::npos ? std::string_view{} : text.substr(end + 1);
                return word;
            };
            bool ok = !charm->block && ParseNumber(next(), applied.kit) && applied.kit != 0;
            for (float *offset : offsets)
                ok = ok && ParseNumber(next(), *offset) && std::isfinite(*offset);
            if (!ok || !text.empty())
                return std::nullopt;
            item.charm = applied;
        }
        if (const KvNode *name = entry.Find("custom_name"))
        {
            if (name->block || name->value.size() > 40 || name->value.find('"') != std::string::npos)
                return std::nullopt;
            item.customName = name->value;
        }
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
