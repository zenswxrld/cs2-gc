#include "cs2_gc/econ_item.h"
#include "cs2_gc/protobuf.h"
#include <bit>
#include <array>
#include <cstring>

namespace cs2_gc
{
namespace
{
constexpr std::uint64_t ItemTypeId = 1; // SO object type of CSOEconItem, as seen in the capture

std::array<std::uint8_t, 4> LittleEndian(std::uint32_t value)
{
    return {static_cast<std::uint8_t>(value), static_cast<std::uint8_t>(value >> 8),
            static_cast<std::uint8_t>(value >> 16), static_cast<std::uint8_t>(value >> 24)};
}

void AddFloatAttribute(PbWriter &item, std::uint32_t defIndex, float value)
{
    PbWriter attribute;
    attribute.Varint(1, defIndex);
    attribute.Bytes(3, LittleEndian(std::bit_cast<std::uint32_t>(value)));
    item.Message(12, attribute);
}

void Reemit(PbWriter &out, const PbField &f)
{
    switch (f.wire)
    {
    case 0: out.Varint(f.number, f.value); break;
    case 1: out.Fixed64(f.number, f.value); break;
    case 5: out.Fixed32(f.number, static_cast<std::uint32_t>(f.value)); break;
    default: out.Bytes(f.number, f.bytes); break;
    }
}

// CMsgSOCacheSubscribed.SubscribedType, with `items` appended when it is the item type (and its
// existing objects removed first when dropExisting).
std::optional<std::vector<std::uint8_t>> PatchSubscribedType(std::span<const std::uint8_t> type,
    std::span<const std::vector<std::uint8_t>> items, bool dropExisting, bool &isItemType)
{
    isItemType = false;
    {
        // The type ID decides how every other field is treated, so read it first.
        PbReader scan(type);
        PbField f;
        while (scan.Next(f))
            if (f.number == 1 && f.wire == 0 && f.value == ItemTypeId)
                isItemType = true;
        if (scan.Failed())
            return std::nullopt;
    }
    PbWriter out;
    PbReader reader(type);
    PbField f;
    while (reader.Next(f))
    {
        if (isItemType && dropExisting && f.number == 2)
            continue;
        Reemit(out, f);
    }
    if (reader.Failed())
        return std::nullopt;
    if (isItemType)
        for (const auto &item : items)
            out.Bytes(2, item);
    return out.bytes();
}

std::optional<std::vector<std::uint8_t>> PatchCache(std::span<const std::uint8_t> cache,
    std::span<const std::vector<std::uint8_t>> items, bool dropExisting)
{
    PbWriter out;
    PbReader reader(cache);
    PbField f;
    bool patched = false;
    while (reader.Next(f))
    {
        if (f.number == 2 && f.wire == 2)
        {
            bool isItemType = false;
            auto type = PatchSubscribedType(f.bytes, items, dropExisting, isItemType);
            if (!type)
                return std::nullopt;
            patched |= isItemType;
            out.Bytes(2, *type);
        }
        else
            Reemit(out, f);
    }
    if (reader.Failed())
        return std::nullopt;
    if (!patched)
    {
        PbWriter type;
        type.Varint(1, ItemTypeId);
        for (const auto &item : items)
            type.Bytes(2, item);
        out.Message(2, type);
    }
    return out.bytes();
}
}

std::vector<std::uint8_t> BuildEconItem(const InventoryItem &item, std::uint32_t accountId,
                                        std::uint64_t itemId, std::uint32_t inventoryPosition)
{
    PbWriter out;
    out.Varint(1, itemId);
    out.Varint(2, accountId);
    out.Varint(3, inventoryPosition);
    out.Varint(4, item.defIndex);
    out.Varint(7, QualityUnique);
    if (item.paintKitIndex)
    {
        AddFloatAttribute(out, AttributePaintIndex, static_cast<float>(item.paintKitIndex));
        AddFloatAttribute(out, AttributePaintSeed, static_cast<float>(item.seed));
        AddFloatAttribute(out, AttributePaintWear, item.wear);
    }
    if (item.rarity)
        out.Varint(19, item.rarity);
    return out.bytes();
}

std::optional<std::vector<std::uint8_t>> AppendItemsToWelcome(
    std::span<const std::uint8_t> welcome, std::span<const std::vector<std::uint8_t>> items, bool dropExisting)
{
    PbWriter out;
    PbReader reader(welcome);
    PbField f;
    bool patched = false;
    while (reader.Next(f))
    {
        if (f.number == 3 && f.wire == 2 && !patched)
        {
            auto cache = PatchCache(f.bytes, items, dropExisting);
            if (!cache)
                return std::nullopt;
            out.Bytes(3, *cache);
            patched = true;
        }
        else
            Reemit(out, f);
    }
    if (reader.Failed() || !patched)
        return std::nullopt;
    return out.bytes();
}
}
