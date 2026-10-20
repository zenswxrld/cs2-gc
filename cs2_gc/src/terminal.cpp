#include "cs2_gc/live_inventory.h"
#include "cs2_gc/econ_item.h"
#include <ctime>
#include <algorithm>

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
    if (!m_inventory.Gameplay().terminals_enabled || !crate || crate->kind != CrateKind::Terminal || terminal->storedIn)
        return std::nullopt;
    TerminalChange change;
    if (!request.pointsRemaining)
    {
        if (!terminal->expiration)
            terminal->expiration = now + m_inventory.Gameplay().terminal_lifetime_days * 24 * 60 * 60; // local offer lifetime
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
    const auto limit = request.volatileLimit ? request.volatileLimit : m_inventory.Gameplay().terminal_default_offers;
    if (limit > 100)
        return std::nullopt;
    std::optional<InventoryItem> offer;
    const auto terminalDef = terminal->defIndex;
    bool topReward = false;
    if (!exhausted)
    {
        CaseOdds odds;
        odds.statTrakPerMille = 0;
        const auto below = [&](std::uint64_t bound) {
            const auto limitValue = UINT64_MAX - UINT64_MAX % bound;
            for (;;) { const auto value = random(); if (value < limitValue) return value % bound; }
        };
        const auto golds = schema.CrateGoldOutcomes(terminalDef);
        std::uint32_t highest = 0;
        std::vector<LootItem> top;
        bool lowerTier = false;
        for (const auto &tier : schema.LootTiers(crate->lootListName))
        {
            if (!tier.rarity || tier.rarity > 6) continue;
            for (const auto &entry : tier.items)
                if (const auto resolved = schema.ResolveLootItem(entry))
                {
                    if (tier.rarity > highest)
                    {
                        lowerTier = highest != 0;
                        highest = tier.rarity;
                        top.clear();
                    }
                    if (tier.rarity == highest) top.push_back(*resolved);
                    else lowerTier = true;
                }
        }
        const auto chance = golds.empty() && !lowerTier ? 10000u :
            PityChance(m_inventory.TerminalPity(terminalDef), golds.empty() ? m_inventory.Gameplay().terminal_top_per_10000 : m_inventory.Gameplay().case_gold_per_10000, m_inventory.Gameplay());
        if (below(10000) < chance)
        {
            if (!golds.empty())
            {
                const auto &gold = golds[below(golds.size())];
                if (const auto drop = schema.SkinAsLootItem(gold.weaponDefIndex, gold.paintKitIndex))
                {
                    offer = MakeLootItem(*drop, 6, random, 0);
                    offer->unusual = true;
                }
            }
            else if (!top.empty())
                offer = MakeLootItem(top[below(top.size())], highest, random, 0);
            topReward = true;
        }
        else
            offer = RollLootList(schema, crate->lootListName, random, odds, golds.empty() ? highest : 0);
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
    m_inventory.SetTerminalPity(terminalDef, topReward ? 0u : std::min(m_inventory.TerminalPity(terminalDef) + 1, 99u));
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
