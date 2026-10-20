#include "cs2_gc/live_inventory.h"
#include "cs2_gc/econ_item.h"
#include <algorithm>

namespace cs2_gc
{
LiveInventory::LiveInventory(Inventory inventory)
    : m_inventory(std::move(inventory))
{
}

InventoryItem LiveInventory::AddItem(InventoryItem item)
{
    item.id = m_inventory.Add(item);
    return item;
}

bool LiveInventory::RemoveItem(std::uint64_t itemId)
{
    return itemId > CustomItemIdBase && m_inventory.Remove(itemId - CustomItemIdBase);
}

std::optional<std::uint32_t> LiveInventory::DefinitionOf(std::uint64_t itemId) const
{
    if ((itemId >> 60) == 0xF)
    {
        const std::uint32_t definition = static_cast<std::uint32_t>(itemId & 0xFFFFFFFFull);
        return definition ? std::optional<std::uint32_t>{definition} : std::nullopt;
    }
    if (itemId <= CustomItemIdBase)
        return std::nullopt;
    const InventoryItem *item = m_inventory.Find(itemId - CustomItemIdBase);
    return item ? std::optional<std::uint32_t>{item->defIndex} : std::nullopt;
}

std::optional<LiveInventory::Scraped> LiveInventory::ScrapeSticker(std::uint64_t itemId, std::uint32_t slot)
{
    if (itemId <= CustomItemIdBase)
        return std::nullopt;
    InventoryItem *item = m_inventory.Find(itemId - CustomItemIdBase);
    if (!item)
        return std::nullopt;
    const auto sticker = std::find_if(item->stickers.begin(), item->stickers.end(),
                                      [slot](const AppliedSticker &s) { return s.slot == slot; });
    if (sticker == item->stickers.end())
        return std::nullopt;
    Scraped scraped;
    sticker->wear += 1.0f / 9.0f;
    if (sticker->wear > 1.0f)
    {
        item->stickers.erase(sticker);
        scraped.removed = true;
    }
    scraped.item = *item;
    scraped.position = PositionOf(item->id);
    return scraped;
}

std::optional<LiveInventory::Sealed> LiveInventory::SealSticker(const Schema &schema, std::uint64_t stickerItemId,
                                                                std::uint64_t slabItemId)
{
    if (stickerItemId <= CustomItemIdBase || slabItemId <= CustomItemIdBase || stickerItemId == slabItemId)
        return std::nullopt;
    const InventoryItem *sticker = m_inventory.Find(stickerItemId - CustomItemIdBase);
    const InventoryItem *slab = m_inventory.Find(slabItemId - CustomItemIdBase);
    if (!sticker || !slab || sticker->defIndex != DefinitionSticker || sticker->stickerKit == 0)
        return std::nullopt;
    const auto keychain = schema.SlabKeychainIndex(slab->defIndex);
    if (!keychain)
        return std::nullopt;

    Sealed sealed;
    sealed.sticker = *sticker;
    sealed.slab = *slab;
    sealed.charm.defIndex = DefinitionKeychain;
    sealed.charm.keychain = *keychain;
    sealed.charm.slabSticker = sticker->stickerKit;
    sealed.charm.rarity = schema.ItemRarity(slab->defIndex);
    m_inventory.Remove(sealed.sticker.id);
    m_inventory.Remove(sealed.slab.id);
    sealed.charm.id = m_inventory.Add(sealed.charm);
    return sealed;
}

std::uint32_t LiveInventory::PositionOf(std::uint64_t ourId) const
{
    std::uint32_t index = 0;
    for (const InventoryItem &item : m_inventory.Items())
    {
        if (item.id == ourId)
            break;
        ++index;
    }
    return ItemPositionBase + index;
}

LiveInventory::StorageChange LiveInventory::StoreItem(std::uint64_t casketItemId, std::uint64_t itemId,
                                                      std::uint32_t now)
{
    StorageChange change;
    if (casketItemId <= CustomItemIdBase || itemId <= CustomItemIdBase || casketItemId == itemId)
        return change;
    InventoryItem *casket = m_inventory.Find(casketItemId - CustomItemIdBase);
    InventoryItem *item = m_inventory.Find(itemId - CustomItemIdBase);
    if (!casket || !item || casket->defIndex != DefinitionStorageUnit || item->defIndex == DefinitionStorageUnit ||
        item->storedIn != 0)
        return change;
    if (casket->casketCount >= MaxStorageUnitItems)
    {
        change.result = StorageResult::Full;
        change.casket = *casket;
        return change;
    }
    item->storedIn = casket->id;
    ++casket->casketCount;
    casket->casketModified = now;
    change.result = StorageResult::Ok;
    change.item = *item;
    change.casket = *casket;
    change.itemPosition = PositionOf(item->id);
    change.casketPosition = PositionOf(casket->id);
    return change;
}

LiveInventory::StorageChange LiveInventory::TakeItem(std::uint64_t casketItemId, std::uint64_t itemId,
                                                     std::uint32_t now)
{
    StorageChange change;
    if (casketItemId <= CustomItemIdBase || itemId <= CustomItemIdBase)
        return change;
    InventoryItem *casket = m_inventory.Find(casketItemId - CustomItemIdBase);
    InventoryItem *item = m_inventory.Find(itemId - CustomItemIdBase);
    if (!casket || !item || casket->defIndex != DefinitionStorageUnit || item->storedIn != casket->id ||
        casket->casketCount == 0)
        return change;
    item->storedIn = 0;
    --casket->casketCount;
    casket->casketModified = now;
    change.result = StorageResult::Ok;
    change.item = *item;
    change.casket = *casket;
    change.itemPosition = PositionOf(item->id);
    change.casketPosition = PositionOf(casket->id);
    return change;
}

std::optional<LiveInventory::Opened> LiveInventory::Open(const Schema &schema, std::uint64_t crateItemId,
                                                         std::uint64_t keyItemId, const RandomSource &random)
{
    if (crateItemId <= CustomItemIdBase)
        return std::nullopt;
    const InventoryItem *crate = m_inventory.Find(crateItemId - CustomItemIdBase);
    if (!crate)
        return std::nullopt;
    Opened opened;
    opened.crate = *crate;
    // A coupon opens into the container it stands for. No key, one item.
    if (const auto contents = schema.CouponContents(crate->defIndex); !contents.empty())
    {
        InventoryItem item;
        item.defIndex = contents[random() % contents.size()];
        item.rarity = schema.ItemRarity(item.defIndex);
        m_inventory.Remove(crate->id);
        item.id = m_inventory.Add(item);
        opened.item = item;
        return opened;
    }
    if (keyItemId > CustomItemIdBase)
        if (const InventoryItem *key = m_inventory.Find(keyItemId - CustomItemIdBase))
            opened.key = *key;
    const OpenResult result = OpenCase(m_inventory, schema, crateItemId - CustomItemIdBase,
                                       keyItemId > CustomItemIdBase ? keyItemId - CustomItemIdBase : 0, random);
    if (result.error != OpenError::None)
        return std::nullopt;
    opened.item = result.item;
    // Only a case consumes its key.
    const CrateInfo *info = schema.FindCrate(opened.crate.defIndex);
    if (!info || info->kind != CrateKind::Case)
        opened.key.reset();
    return opened;
}

std::optional<LiveInventory::Renamed> LiveInventory::Rename(std::uint64_t itemId, const std::string &name)
{
    if (itemId <= CustomItemIdBase || name.size() > 40)
        return std::nullopt;
    for (const char c : name)
        if (c == '"' || c == '\\' || static_cast<unsigned char>(c) < 0x20)
            return std::nullopt;
    InventoryItem *item = m_inventory.Find(itemId - CustomItemIdBase);
    if (!item)
        return std::nullopt;
    item->customName = name;
    std::uint32_t index = 0;
    for (const InventoryItem &candidate : m_inventory.Items())
    {
        if (candidate.id == item->id)
            break;
        ++index;
    }
    return Renamed{*item, ItemPositionBase + index};
}

std::optional<LiveInventory::StickerApplied> LiveInventory::ApplySticker(const ApplyStickerRequest &request)
{
    if (request.stickerItemId <= CustomItemIdBase || request.targetItemId <= CustomItemIdBase ||
        request.stickerItemId == request.targetItemId)
        return std::nullopt;
    const InventoryItem *sticker = m_inventory.Find(request.stickerItemId - CustomItemIdBase);
    InventoryItem *target = m_inventory.Find(request.targetItemId - CustomItemIdBase);
    if (!sticker || !target || target->defIndex == DefinitionSticker || target->defIndex == DefinitionKeychain ||
        target->stickerKit || target->keychain)
        return std::nullopt;

    // The same request attaches a charm: the item is a charm tool and the floats are its x, y, z offsets.
    const bool charm = sticker->defIndex == DefinitionKeychain && sticker->keychain != 0;
    if (charm)
    {
        if (target->charm)
            return std::nullopt;
        target->charm = AppliedKeychain{sticker->keychain, request.offsetX, request.offsetY, request.offsetZ,
                                        sticker->slabSticker};
    }
    else
    {
        if (sticker->defIndex != DefinitionSticker || sticker->stickerKit == 0 || request.slot >= StickerSlotCount)
            return std::nullopt;
        for (const AppliedSticker &existing : target->stickers)
            if (existing.slot == request.slot)
                return std::nullopt;
        AppliedSticker applied;
        applied.slot = request.slot;
        applied.kit = sticker->stickerKit;
        applied.wear = request.wear;
        applied.scale = request.scale;
        applied.rotation = request.rotation;
        applied.offsetX = request.offsetX;
        applied.offsetY = request.offsetY;
        target->stickers.push_back(applied);
    }

    StickerApplied result;
    result.charm = charm;
    result.consumed = *sticker;
    m_inventory.Remove(sticker->id);
    result.item = *m_inventory.Find(request.targetItemId - CustomItemIdBase);
    std::uint32_t index = 0;
    for (const InventoryItem &item : m_inventory.Items())
    {
        if (item.id == result.item.id)
            break;
        ++index;
    }
    result.position = ItemPositionBase + index;
    return result;
}

std::vector<std::vector<std::uint8_t>> LiveInventory::EncodedSlots(std::uint32_t accountId) const
{
    std::vector<std::vector<std::uint8_t>> out;
    for (const Slot &slot : m_slots)
        if (slot.itemId)
            out.push_back(EncodeEquipSlot(accountId, slot.classId, slot.slotId, slot.itemId, slot.itemDefinition));
    return out;
}

std::optional<std::vector<std::vector<std::uint8_t>>> LiveInventory::Adjust(const AdjustEquipSlots &request,
                                                                            std::uint32_t accountId)
{
    for (const EquipSlotChange &change : request.slots)
        if (change.itemId && !DefinitionOf(change.itemId))
            return std::nullopt;

    std::vector<std::vector<std::uint8_t>> changed;
    for (const EquipSlotChange &change : request.slots)
    {
        const std::uint32_t definition = change.itemId ? *DefinitionOf(change.itemId) : 0;
        Slot *slot = nullptr;
        for (Slot &candidate : m_slots)
            if (candidate.classId == change.classId && candidate.slotId == change.slotId)
                slot = &candidate;
        if (!slot)
        {
            m_slots.push_back({change.classId, change.slotId, 0, 0});
            slot = &m_slots.back();
        }
        slot->itemId = change.itemId;
        slot->itemDefinition = definition;
        changed.push_back(EncodeEquipSlot(accountId, change.classId, change.slotId, change.itemId, definition));
    }
    return changed;
}
}
