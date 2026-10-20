#include "cs2_gc/econ_item.h"
#include "cs2_gc/protobuf.h"
#include <bit>
#include <functional>
#include <array>
#include <cstring>

namespace cs2_gc
{
namespace
{

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

void AddIntegerAttribute(PbWriter &item, std::uint32_t defIndex, std::uint32_t value)
{
    PbWriter attribute;
    attribute.Varint(1, defIndex);
    attribute.Bytes(3, LittleEndian(value));
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
std::optional<std::vector<std::uint8_t>> PatchSubscribedType(std::span<const std::uint8_t> type, std::uint64_t typeId,
    std::span<const std::vector<std::uint8_t>> items, bool dropExisting, bool &isItemType)
{
    isItemType = false;
    {
        // The type ID decides how every other field is treated, so read it first.
        PbReader scan(type);
        PbField f;
        while (scan.Next(f))
            if (f.number == 1 && f.wire == 0 && f.value == typeId)
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

std::optional<std::vector<std::uint8_t>> PatchCache(std::span<const std::uint8_t> cache, std::uint64_t typeId,
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
            auto type = PatchSubscribedType(f.bytes, typeId, items, dropExisting, isItemType);
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
        type.Varint(1, typeId);
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
    out.Varint(7, item.expiration ? 14 : item.unusual ? 3 : item.statTrak ? QualityStrange : QualityUnique);
    if (item.terminalRemaining)
        AddIntegerAttribute(out, 169, *item.terminalRemaining);
    if (item.expiration)
        AddIntegerAttribute(out, 183, item.expiration);
    if (item.purchasePrice)
        AddIntegerAttribute(out, 316, *item.purchasePrice);
    if (item.statTrak)
    {
        AddIntegerAttribute(out, AttributeKillEater, 0);
        AddIntegerAttribute(out, AttributeKillEaterScoreType, 0);
    }
    if (item.paintKitIndex)
    {
        AddFloatAttribute(out, AttributePaintIndex, static_cast<float>(item.paintKitIndex));
        AddFloatAttribute(out, AttributePaintSeed, static_cast<float>(item.seed));
        AddFloatAttribute(out, AttributePaintWear, item.wear);
    }
    if (item.stickerKit)
        AddIntegerAttribute(out, AttributeStickerKit, item.stickerKit);
    if (item.keychain)
        AddIntegerAttribute(out, AttributeKeychain, item.keychain);
    if (item.slabSticker)
        AddIntegerAttribute(out, AttributeKeychainSticker, item.slabSticker);
    for (const AppliedSticker &sticker : item.stickers)
    {
        const std::uint32_t base = AttributeStickerSlotBase + 4 * sticker.slot;
        const std::uint32_t offset = AttributeStickerOffsetBase + 2 * sticker.slot;
        AddIntegerAttribute(out, base, sticker.kit);
        if (sticker.wear != 0.0f)
            AddFloatAttribute(out, base + 1, sticker.wear);
        if (sticker.scale != 0.0f)
            AddFloatAttribute(out, base + 2, sticker.scale);
        if (sticker.rotation != 0.0f)
            AddFloatAttribute(out, base + 3, sticker.rotation);
        if (sticker.offsetX != 0.0f)
            AddFloatAttribute(out, offset, sticker.offsetX);
        if (sticker.offsetY != 0.0f)
            AddFloatAttribute(out, offset + 1, sticker.offsetY);
    }
    if (item.defIndex == DefinitionStorageUnit)
    {
        AddIntegerAttribute(out, AttributeCasketItemsCount, item.casketCount);
        AddIntegerAttribute(out, AttributeCasketModificationDate,
                            item.casketModified ? item.casketModified : 1700000000u);
    }
    if (item.storedIn)
    {
        const std::uint64_t casketId = CustomItemIdBase + item.storedIn;
        AddIntegerAttribute(out, AttributeCasketIdLow, static_cast<std::uint32_t>(casketId & 0xFFFFFFFFull));
        AddIntegerAttribute(out, AttributeCasketIdHigh, static_cast<std::uint32_t>(casketId >> 32));
    }
    if (item.charm)
    {
        AddIntegerAttribute(out, AttributeKeychain, item.charm->kit);
        if (item.charm->offsetX != 0.0f)
            AddFloatAttribute(out, AttributeKeychainOffsetBase, item.charm->offsetX);
        if (item.charm->offsetY != 0.0f)
            AddFloatAttribute(out, AttributeKeychainOffsetBase + 1, item.charm->offsetY);
        if (item.charm->offsetZ != 0.0f)
            AddFloatAttribute(out, AttributeKeychainOffsetBase + 2, item.charm->offsetZ);
        if (item.charm->slabSticker)
            AddIntegerAttribute(out, AttributeKeychainSticker, item.charm->slabSticker);
    }
    if (!item.customName.empty())
    {
        // A string attribute's value_bytes hold a serialized CAttribute_String (value = field 1).
        PbWriter text;
        text.String(1, item.customName);
        PbWriter attribute;
        attribute.Varint(1, AttributeCustomName);
        attribute.Bytes(3, text.bytes());
        out.Message(12, attribute);
    }
    if (item.rarity)
        out.Varint(19, item.rarity);
    return out.bytes();
}

std::vector<std::uint8_t> EncodeEquipSlot(std::uint32_t accountId, std::uint32_t classId, std::uint32_t slotId,
                                          std::uint64_t itemId, std::uint32_t itemDefinition)
{
    PbWriter out;
    out.Varint(1, accountId);
    out.Varint(2, classId);
    out.Varint(3, slotId);
    out.Varint(4, itemId);
    out.Varint(5, itemDefinition);
    return out.bytes();
}

std::optional<std::vector<std::uint8_t>> AppendItemsToWelcome(
    std::span<const std::uint8_t> welcome, std::span<const std::vector<std::uint8_t>> items, bool dropExisting)
{
    return AppendObjectsToWelcome(welcome, ItemTypeId, items, dropExisting);
}

std::optional<std::vector<std::uint8_t>> AppendObjectsToWelcome(
    std::span<const std::uint8_t> welcome, std::uint64_t typeId,
    std::span<const std::vector<std::uint8_t>> objects, bool dropExisting)
{
    std::span<const std::vector<std::uint8_t>> items = objects;
    PbWriter out;
    PbReader reader(welcome);
    PbField f;
    bool patched = false;
    while (reader.Next(f))
    {
        if (f.number == 3 && f.wire == 2 && !patched)
        {
            auto cache = PatchCache(f.bytes, typeId, items, dropExisting);
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

namespace cs2_gc
{
namespace
{
using ObjectRewrite = std::function<std::optional<std::vector<std::uint8_t>>(std::span<const std::uint8_t>)>;

// Rewrites every object of one SO type in the first cache of a Welcome; all else is copied.
std::optional<std::vector<std::uint8_t>> RewriteObjects(std::span<const std::uint8_t> welcome,
                                                        std::uint64_t typeId, const ObjectRewrite &rewrite)
{
    PbWriter out;
    PbReader reader(welcome);
    PbField f;
    bool sawCache = false;
    while (reader.Next(f))
    {
        if (f.number != 3 || f.wire != 2 || sawCache)
        {
            Reemit(out, f);
            continue;
        }
        sawCache = true;
        PbWriter cacheOut;
        PbReader cacheReader(f.bytes);
        PbField c;
        while (cacheReader.Next(c))
        {
            if (c.number != 2 || c.wire != 2)
            {
                Reemit(cacheOut, c);
                continue;
            }
            bool matches = false;
            {
                PbReader scan(c.bytes);
                PbField t;
                while (scan.Next(t))
                    if (t.number == 1 && t.wire == 0 && t.value == typeId)
                        matches = true;
                if (scan.Failed())
                    return std::nullopt;
            }
            PbWriter typeOut;
            PbReader typeReader(c.bytes);
            PbField t;
            while (typeReader.Next(t))
            {
                if (matches && t.number == 2 && t.wire == 2)
                {
                    auto changed = rewrite(t.bytes);
                    if (!changed)
                        return std::nullopt;
                    typeOut.Bytes(2, *changed);
                }
                else
                    Reemit(typeOut, t);
            }
            if (typeReader.Failed())
                return std::nullopt;
            cacheOut.Bytes(2, typeOut.bytes());
        }
        if (cacheReader.Failed())
            return std::nullopt;
        out.Bytes(3, cacheOut.bytes());
    }
    if (reader.Failed() || !sawCache)
        return std::nullopt;
    return out.bytes();
}
}

std::optional<std::vector<std::uint8_t>> WithXpShopBalance(std::span<const std::uint8_t> object, std::uint32_t balance)
{
    PbWriter out;
    PbReader reader(object);
    PbField f;
    bool replaced = false;
    while (reader.Next(f))
    {
        if (f.number == 2 && f.wire == 0)
        {
            out.Varint(2, balance);
            replaced = true;
        }
        else
            Reemit(out, f);
    }
    if (reader.Failed())
        return std::nullopt;
    if (!replaced)
        out.Varint(2, balance);
    return out.bytes();
}

std::optional<std::vector<std::uint8_t>> WithXpShopTrack(std::span<const std::uint8_t> object, std::uint32_t xp)
{
    PbWriter out;
    PbReader reader(object);
    PbField f;
    while (reader.Next(f))
        Reemit(out, f);
    if (reader.Failed())
        return std::nullopt;
    out.Varint(3, xp);
    return out.bytes();
}

std::optional<std::vector<std::uint8_t>> WithXpShopTracks(std::span<const std::uint8_t> object,
                                                          std::span<const std::uint32_t> tracks)
{
    PbWriter out;
    PbReader reader(object);
    PbField f;
    while (reader.Next(f))
        if (!(f.number == 3 && f.wire == 0))
            Reemit(out, f);
    if (reader.Failed())
        return std::nullopt;
    for (const std::uint32_t xp : tracks)
        out.Varint(3, xp);
    return out.bytes();
}

std::vector<std::vector<std::uint8_t>> ExtractObjects(std::span<const std::uint8_t> welcome, std::uint64_t typeId)
{
    std::vector<std::vector<std::uint8_t>> found;
    const auto result = RewriteObjects(welcome, typeId, [&found](std::span<const std::uint8_t> object) {
        found.emplace_back(object.begin(), object.end());
        return std::optional<std::vector<std::uint8_t>>{std::vector<std::uint8_t>(object.begin(), object.end())};
    });
    if (!result)
        found.clear();
    return found;
}

std::optional<std::vector<std::uint8_t>> SetArmoryBalance(std::span<const std::uint8_t> welcome,
                                                          std::uint32_t balance)
{
    return RewriteObjects(welcome, XpShopTypeId, [balance](std::span<const std::uint8_t> object) {
        return WithXpShopBalance(object, balance);
    });
}
}
