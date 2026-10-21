#include "cs2_gc/case_opening.h"
#include <algorithm>
#include <vector>

namespace cs2_gc
{
namespace
{
// Odds by tier position from the bottom; Armory collections can supply fifth/sixth tiers.
std::uint32_t WeightForRank(std::size_t rank, const CaseOdds &odds)
{
    switch (rank)
    {
    case 0: return odds.milSpec;
    case 1: return odds.restricted;
    case 2: return odds.classified;
    case 3: return odds.covert;
    case 4: return odds.fifthTier;
    case 5: return odds.sixthTier;
    default: return 0;
    }
}

// Unbiased value in [0, bound) by rejection sampling.
std::uint64_t Below(const RandomSource &random, std::uint64_t bound)
{
    const std::uint64_t limit = UINT64_MAX - UINT64_MAX % bound;
    for (;;)
    {
        const std::uint64_t value = random();
        if (value < limit)
            return value % bound;
    }
}
}

InventoryItem MakeLootItem(const LootItem &drop, std::uint32_t rarity, const RandomSource &random,
                           std::uint32_t statTrakPerMille)
{
    InventoryItem item;
    item.defIndex = drop.weaponDefIndex;
    item.rarity = rarity;
    switch (drop.kind)
    {
    case LootKind::Skin:
        item.paintKitIndex = drop.paintKitIndex;
        item.wear = drop.wearMin + static_cast<float>(Below(random, 1u << 24)) / static_cast<float>(1u << 24) *
                                       (drop.wearMax - drop.wearMin);
        item.seed = static_cast<std::uint32_t>(Below(random, 1000)) + 1;
        item.statTrak = Below(random, 1000) < statTrakPerMille;
        break;
    case LootKind::Sticker:
        item.stickerKit = drop.stickerKitIndex;
        break;
    case LootKind::Keychain:
        item.keychain = drop.keychainIndex;
        break;
    case LootKind::MusicKit:
        item.musicKit = drop.musicKitIndex;
        item.statTrak = statTrakPerMille == 1000;
        break;
    case LootKind::Plain:
        break;
    }
    return item;
}

std::uint32_t CaseGoldChance(std::uint32_t previousMisses)
{
    return PityChance(previousMisses, 26);
}

std::uint32_t PityChance(std::uint32_t previousMisses, std::uint32_t baseChance, const GameplayConfig &config)
{
    const auto base = std::min(baseChance, 10000u);
    if (!config.pity_enabled || previousMisses + 1 < config.pity_soft_at)
        return base;
    if (previousMisses + 1 >= config.pity_hard_at)
        return 10000;
    return base + (10000 - base) * (previousMisses + 2 - config.pity_soft_at) /
        (config.pity_hard_at - config.pity_soft_at + 1);
}

std::optional<InventoryItem> RollLootList(const Schema &schema, std::string_view lootListName,
                                          const RandomSource &random, const CaseOdds &odds, std::uint32_t excludedRarity)
{
    struct Tier
    {
        std::uint32_t weight;
        std::uint32_t rarity;
        std::vector<LootItem> items;
    };

    // Rank tiers by rarity among the list's own tiers, before any are dropped for lack of items.
    std::vector<LootTier> listed = schema.LootTiers(lootListName);
    std::erase_if(listed, [](const LootTier &tier) { return tier.rarity == 0; });
    std::stable_sort(listed.begin(), listed.end(),
                     [](const LootTier &a, const LootTier &b) { return a.rarity < b.rarity; });

    std::vector<Tier> tiers;
    std::uint64_t totalWeight = 0;
    for (std::size_t rank = 0; rank < listed.size(); ++rank)
    {
        if (excludedRarity && listed[rank].rarity == excludedRarity)
            continue;
        const std::uint32_t weight = WeightForRank(rank, odds);
        Tier resolved{weight, listed[rank].rarity, {}};
        for (const std::string &entry : listed[rank].items)
            if (auto item = schema.ResolveLootItem(entry))
                resolved.items.push_back(std::move(*item));
        if (weight == 0 || resolved.items.empty())
            continue;
        totalWeight += weight;
        tiers.push_back(std::move(resolved));
    }
    if (tiers.empty())
        return std::nullopt;

    std::uint64_t roll = Below(random, totalWeight);
    const Tier *chosen = &tiers.back();
    for (const Tier &tier : tiers)
    {
        if (roll < tier.weight)
        {
            chosen = &tier;
            break;
        }
        roll -= tier.weight;
    }

    const LootItem &drop = chosen->items[Below(random, chosen->items.size())];
    return MakeLootItem(drop, chosen->rarity, random, schema.IsGlove(drop.weaponDefIndex) ? 0 : odds.statTrakPerMille);
}

std::optional<InventoryItem> RollSouvenir(const Schema &schema, const CrateInfo &crate,
                                          const RandomSource &random, const CaseOdds &odds)
{
    if (crate.kind != CrateKind::Souvenir) return std::nullopt;
    auto openingOdds = odds;
    openingOdds.statTrakPerMille = 0;
    openingOdds.fifthTier = 13; openingOdds.sixthTier = 3;
    auto rolled = RollLootList(schema, crate.lootListName, random, openingOdds);
    if (!rolled) return std::nullopt;
    InventoryItem item = *rolled;
    if (!DecorateSouvenir(item,schema,crate,random)) return std::nullopt;
    return item;
}

bool DecorateSouvenir(InventoryItem &item, const Schema &schema, const CrateInfo &crate, const RandomSource &random)
{
    if (crate.kind!=CrateKind::Souvenir || !item.paintKitIndex || schema.IsKnife(item.defIndex) || schema.IsGlove(item.defIndex))
        return false;
    item.stickers.clear();
    item.souvenir = true; item.statTrak = false; item.unusual = false;
    item.tournamentEvent = crate.tournamentEvent;
    // Local packages have no recorded match. Select same-event teams/decals without inventing a match stage.
    auto stickers = schema.SouvenirStickers(crate.tournamentEvent);
    std::vector<SouvenirSticker> logos, teams, signatures;
    for (const auto &sticker : stickers)
        if (sticker.player) signatures.push_back(sticker);
        else if (sticker.team) teams.push_back(sticker);
        else logos.push_back(sticker);
    auto apply = [&](std::uint32_t kit) {
        if (kit && item.stickers.size() < 4)
        { AppliedSticker sticker; sticker.slot = static_cast<std::uint32_t>(item.stickers.size()); sticker.kit = kit; item.stickers.push_back(sticker); }
    };
    if (!logos.empty()) apply(logos[Below(random, logos.size())].kit);
    for (unsigned i = 0; i < 2 && !teams.empty(); ++i)
    {
        const auto selected = teams[Below(random, teams.size())];
        apply(selected.kit);
        (i ? item.tournamentTeam1 : item.tournamentTeam0) = selected.team;
        std::erase_if(teams, [&](const auto &sticker) { return sticker.team == selected.team; });
    }
    const auto map = schema.SouvenirMapSticker(crate.defIndex);
    if (map) apply(map);
    else
    {
        std::erase_if(signatures, [&](const auto &sticker) {
            return sticker.team != item.tournamentTeam0 && sticker.team != item.tournamentTeam1;
        });
        if (!signatures.empty())
        {
            const auto &signature = signatures[Below(random, signatures.size())];
            apply(signature.kit); item.tournamentPlayer = signature.player;
        }
    }
    return true;
}

OpenResult OpenCase(Inventory &inventory, const Schema &schema, std::uint64_t crateId,
                    std::uint64_t keyId, const RandomSource &random, const CaseOdds &odds)
{
    OpenResult result;

    const InventoryItem *crateItem = inventory.Find(crateId);
    const CrateInfo *crate = crateItem ? schema.FindCrate(crateItem->defIndex) : nullptr;
    const bool keyless = crate && (crate->kind == CrateKind::Capsule || crate->kind == CrateKind::GraffitiBox ||
                                   crate->kind == CrateKind::Pins || crate->kind == CrateKind::Souvenir ||
                                   (crate->kind == CrateKind::Case && inventory.Gameplay().free_case_keys && (keyId == 0 || keyId == crateId)));
    if (!crate || (crate->kind != CrateKind::Case && !keyless))
    {
        result.error = OpenError::NoSuchCrate;
        return result;
    }
    if (!keyless)
    {
        const InventoryItem *keyItem = inventory.Find(keyId);
        if (!keyItem)
        {
            result.error = OpenError::NoSuchKey;
            return result;
        }
        if (keyItem->defIndex != crate->keyDefIndex)
        {
            result.error = OpenError::WrongKey;
            return result;
        }
    }

    std::optional<InventoryItem> rolled;
    const auto golds = crate->kind == CrateKind::Case ? schema.CrateGoldOutcomes(crate->defIndex) : std::vector<SkinRef>{};
    if (!golds.empty() && Below(random, 10000) < PityChance(inventory.CasePity(), inventory.Gameplay().case_gold_per_10000, inventory.Gameplay()))
    {
        const auto &gold = golds[Below(random, golds.size())];
        if (const auto loot = schema.SkinAsLootItem(gold.weaponDefIndex, gold.paintKitIndex))
        {
            rolled = MakeLootItem(*loot, 6, random, schema.IsKnife(gold.weaponDefIndex) ? odds.statTrakPerMille : 0);
            rolled->unusual = true;
            // Vanilla knives use Plain loot and need their StatTrak roll separately.
            if (!gold.paintKitIndex && schema.IsKnife(gold.weaponDefIndex))
                rolled->statTrak = Below(random, 1000) < odds.statTrakPerMille;
        }
    }
    else
    {
        auto openingOdds = odds;
        if (crate->kind == CrateKind::Souvenir)
        {
            openingOdds.statTrakPerMille = 0;
            openingOdds.fifthTier = 13; openingOdds.sixthTier = 3;
        }
        else if (crateItem->statTrak || schema.ProducesStatTrak(crate->defIndex)) openingOdds.statTrakPerMille = 1000;
        rolled = crate->kind == CrateKind::Souvenir ? RollSouvenir(schema, *crate, random, openingOdds) :
            RollLootList(schema, crate->lootListName, random, openingOdds);
        // A knife or glove in a case's own loot list (the Black Market and Gauntlet Cases) is a ★ item like any
        // case gold.
        if (rolled && (schema.IsKnife(rolled->defIndex) || schema.IsGlove(rolled->defIndex))) rolled->unusual = true;
    }
    if (!rolled)
    {
        result.error = OpenError::EmptyLootList;
        return result;
    }
    InventoryItem item = *rolled;
    if (!golds.empty())
        inventory.SetCasePity(item.unusual ? 0 : std::min(inventory.CasePity() + 1, 99u));
    item.noStarSale = crateItem->noStarSale;

    // Nothing above mutated the inventory; consume and grant together.
    inventory.Remove(crateId);
    if (!keyless && !inventory.Gameplay().free_case_keys)
        inventory.Remove(keyId);
    item.id = inventory.Add(item);
    result.item = item;
    return result;
}
}

namespace cs2_gc
{
std::optional<std::vector<InventoryItem>> RollMatchDrops(const Schema &schema, const RandomSource &random, const GameplayConfig &config)
{
    if (!config.match_drops_enabled) return std::nullopt;
    std::vector<std::uint32_t> cases, rareCases;
    for (const auto &crate : schema.Crates())
        if (crate.kind == CrateKind::Case && crate.keyDefIndex && !schema.LootTiers(crate.lootListName).empty())
        {
            if (crate.name == "crate_cs2gc_black_market" || crate.name == "crate_cs2gc_gauntlet") {
                if ((crate.name == "crate_cs2gc_black_market" && config.knife_finishes) ||
                    (crate.name == "crate_cs2gc_gauntlet" && config.knife_finishes && config.glove_finishes))
                    rareCases.push_back(crate.defIndex);
            } else cases.push_back(crate.defIndex);
        }
    auto skins = schema.MatchRewardSkins(config.match_weekly_pool_only != 0);
    std::erase_if(skins, [&](const auto &skin) {
        return schema.SkinRarity(skin.weaponDefIndex, skin.paintKitIndex).value_or(0) < config.match_skin_min_rarity;
    });
    if ((config.match_case_percent && cases.empty()) || (config.match_case_percent < 100 && skins.empty()))
        return std::nullopt;
    std::vector<InventoryItem> result;
    for (std::uint32_t i = 0; i < config.match_drop_count; ++i)
    {
        InventoryItem item;
        if (Below(random, 100) < config.match_case_percent)
        {
            const bool rare = !rareCases.empty() && Below(random,10000) < config.reward_rare_case_per_10000;
            const auto &pool=rare?rareCases:cases;
            item.defIndex = pool[Below(random,pool.size())];
        }
        else
        {
            const auto &skin = skins[Below(random, skins.size())];
            const auto loot = schema.SkinAsLootItem(skin.weaponDefIndex, skin.paintKitIndex);
            if (!loot) return std::nullopt;
            item = MakeLootItem(*loot, *schema.SkinRarity(skin.weaponDefIndex, skin.paintKitIndex), random, 0);
        }
        result.push_back(item);
    }
    return result;
}
}
