#include "cs2_gc/live_inventory.h"
#include "cs2_gc/econ_item.h"
#include <ctime>

namespace cs2_gc
{
std::optional<InventoryItem> LiveInventory::TerminalOffer(const Schema &schema, std::uint64_t gameId) const
{
    if (gameId <= CustomItemIdBase)
        return std::nullopt;
    const auto *terminal = m_inventory.Find(gameId - CustomItemIdBase);
    const auto *crate = terminal ? schema.FindCrate(terminal->defIndex) : nullptr;
    if (!crate || crate->kind != CrateKind::Terminal || !terminal->terminalRemaining ||
        terminal->expiration <= static_cast<std::uint32_t>(std::time(nullptr)))
        return std::nullopt;
    for (const auto &item : m_inventory.Items())
        if (item.storedIn == terminal->id && item.purchasePrice)
            return item;
    return std::nullopt;
}

std::optional<LiveInventory::TerminalChange> LiveInventory::AdvanceTerminal(
    const Schema &schema, const OpenCrateRequest &request, const RandomSource &random, std::uint32_t now)
{
    if (request.crateItemId <= CustomItemIdBase)
        return std::nullopt;
    auto *terminal = m_inventory.Find(request.crateItemId - CustomItemIdBase);
    const auto *crate = terminal ? schema.FindCrate(terminal->defIndex) : nullptr;
    if (!crate || crate->kind != CrateKind::Terminal || terminal->storedIn)
        return std::nullopt;
    TerminalChange change;
    if (!request.pointsRemaining)
    {
        if (!terminal->expiration)
            terminal->expiration = now + 7 * 24 * 60 * 60; // local offer lifetime
        if (terminal->expiration <= now)
            return std::nullopt;
        change.terminal = *terminal;
        change.unsealed = true;
        return change;
    }
    if (!terminal->expiration || terminal->expiration <= now ||
        *request.pointsRemaining != terminal->terminalRemaining.value_or(0))
        return std::nullopt;
    const bool exhausted = terminal->terminalRemaining && *terminal->terminalRemaining == 0;
    const auto limit = request.volatileLimit ? request.volatileLimit : 5u;
    if (limit > 100)
        return std::nullopt;
    std::optional<InventoryItem> offer;
    if (!exhausted)
    {
        CaseOdds odds;
        odds.statTrakPerMille = 0;
        offer = RollLootList(schema, crate->lootListName, random, odds);
        if (!offer)
            return std::nullopt;
    }
    change.terminal = *terminal;
    for (const auto &item : m_inventory.Items())
        if (item.storedIn == terminal->id)
            change.removed.push_back(item);
    for (const auto &item : change.removed)
        m_inventory.Remove(item.id);
    // Erasing a prior offer may move the vector: never keep item pointers across mutations.
    terminal = m_inventory.Find(change.terminal.id);
    if (exhausted)
    {
        change.exhausted = true;
        m_inventory.Remove(change.terminal.id);
        return change;
    }
    terminal->terminalRemaining = terminal->terminalRemaining ? *terminal->terminalRemaining - 1 : limit - 1;
    change.terminal = *terminal;
    offer->storedIn = terminal->id;
    offer->purchasePrice = 0; // this GC's Store is free/local, including terminal offers
    change.offer = AddItem(*offer);
    return change;
}

std::optional<LiveInventory::TerminalChange> LiveInventory::AcceptTerminal(const Schema &schema, std::uint64_t gameId)
{
    const auto offer = TerminalOffer(schema, gameId);
    if (!offer)
        return std::nullopt;
    TerminalChange change;
    change.terminal = *m_inventory.Find(gameId - CustomItemIdBase);
    m_inventory.Remove(change.terminal.id);
    auto *item = m_inventory.Find(offer->id);
    item->storedIn = 0;
    item->purchasePrice.reset();
    change.offer = *item;
    return change;
}
}
