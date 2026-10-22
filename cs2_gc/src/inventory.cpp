#include "cs2_gc/inventory.h"
#include "cs2_gc/keyvalues.h"
#include "cs2_gc/econ_item.h"
#include <algorithm>
#include <charconv>
#include <cmath>
#include <fstream>
#include <set>
#include <sstream>
#include <limits>
#include <iomanip>
#include <ctime>
#include <functional>

namespace cs2_gc
{
void Inventory::SetGameplay(const GameplayConfig &config)
{
    for (auto &track : m_xpTracks)
        track = std::max(1u, static_cast<std::uint32_t>(std::min<std::uint64_t>(
            std::uint64_t{track} * config.armory_xp_per_star / m_trackXpPerStar,
            std::uint64_t{40} * config.armory_xp_per_star)));
    m_trackXpPerStar = config.armory_xp_per_star;
    m_gameplay = config;
}

std::vector<std::uint32_t> Inventory::DisplayXpTracks() const
{
    std::vector<std::uint32_t> result;
    for (const auto track : m_xpTracks)
        result.push_back(std::max(1u, static_cast<std::uint32_t>(std::min<std::uint64_t>(
            std::uint64_t{track} * ArmoryStarXp / m_trackXpPerStar, ArmoryPassMaxXp))));
    return result;
}

bool Inventory::ApplyEarnedXp(std::uint64_t cumulativeXp)
{
    if (cumulativeXp <= m_progress.rewardTotal)
        return false;
    const auto delta = cumulativeXp - m_progress.rewardTotal;
    m_progress.rewardTotal = cumulativeXp;
    const auto profileDelta = m_gameplay.xp_enabled ? delta : 0;
    const auto needed = std::uint64_t{40 - m_progress.level} * ProfileLevelXp;
    const auto xp = std::uint64_t{m_progress.xp} + std::min(profileDelta, needed);
    m_progress.level += static_cast<std::uint32_t>(std::min<std::uint64_t>(xp / ProfileLevelXp, 40 - m_progress.level));
    m_progress.xp = m_progress.level == 40 ? 0 : static_cast<std::uint32_t>(xp % ProfileLevelXp);
    const auto maxPassXp = 40 * m_trackXpPerStar;
    std::uint64_t stars = m_armoryCredits.value_or(0);
    for (auto &track : m_xpTracks)
    {
        const auto previous = std::min(track, maxPassXp);
        track = previous + static_cast<std::uint32_t>(std::min<std::uint64_t>(m_gameplay.stars_enabled ? delta : 0, maxPassXp - previous));
        stars += track / m_trackXpPerStar - previous / m_trackXpPerStar;
    }
    m_armoryCredits = static_cast<std::uint32_t>(std::min<std::uint64_t>(stars, UINT32_MAX));
    return true;
}

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
    std::erase_if(m_loadout, [id](const LoadoutSlot &slot) {
        return slot.itemId > CustomItemIdBase && (slot.itemId >> 60) != 0xF && slot.itemId - CustomItemIdBase == id;
    });
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
    out << "\"inventory\"\n{\n\t\"next_id\"\t\"" << m_nextId << "\"\n";
    out << "\t\"last_care_generation\" \"" << m_lastCareGeneration << "\"\n";
    if (m_lastClaimedCare)
    {
        // Plain numbers, not item blocks: nothing here has to repeat next_id.
        out << "\t\"care_claimed\" {\n\t\t\"generation\" \"" << m_lastClaimedCare->generation << "\"\n";
        for (std::size_t slot = 0; slot < m_lastClaimedCare->slots.size(); ++slot)
        {
            const auto &entry = m_lastClaimedCare->slots[slot];
            out << "\t\t\"slot" << slot << "\" \"" << entry.defIndex << ' ' << entry.paintKitIndex << ' ' << entry.ownedId << "\"\n";
        }
        out << "\t}\n";
    }
    if (!m_carePackages.empty())
    {
        out << "\t\"care_packages\" {\n";
        for (const auto &package : m_carePackages)
        {
            Inventory preview; preview.m_items = package.offers; preview.m_nextId = m_nextId;
            const auto text = preview.ToText();
            out << "\t\t\"" << package.generation << "\" {\n\"next_id\" \"" << m_nextId << "\"\n"
                << text.substr(text.find("\t\"items\""));
        }
        out << "\t}\n";
    }
    out << "\t\"case_pity\"\t\"" << m_casePity << "\"\n";
    out << "\t\"match_reward_total\" \"" << m_matchRewardTotal << "\"\n";
    out << "\t\"console_star_total\" \"" << m_consoleStarTotal << "\"\n";
    out << "\t\"level_reward_total\" \"" << m_levelRewardTotal << "\"\n";
    out << "\t\"track_xp_per_star\" \"" << m_trackXpPerStar << "\"\n";
    if (!m_terminalPity.empty())
    {
        out << "\t\"terminal_pity\" {\n";
        for (const auto &[definition, failures] : m_terminalPity)
            out << "\t\t\"" << definition << "\" \"" << failures << "\"\n";
        out << "\t}\n";
    }
    if (m_armoryCredits)
        out << "\t\"armory_credits\"\t\"" << *m_armoryCredits << "\"\n";
    if (!m_loadout.empty())
    {
        out << "\t\"loadout\" {\n";
        std::size_t index = 0;
        for (const auto &slot : m_loadout)
            out << "\t\t\"" << index++ << "\" { \"class\" \"" << slot.classId << "\" \"slot\" \"" << slot.slotId
                << "\" \"item_id\" \"" << slot.itemId << "\" \"definition\" \"" << slot.itemDefinition << "\" }\n";
        out << "\t}\n";
    }
    if (!m_armoryPity.empty())
    {
        out << "\t\"armory_pity\" {\n";
        for (const auto &[collection, misses] : m_armoryPity)
            out << "\t\t" << std::quoted(collection) << " \"" << misses << "\"\n";
        out << "\t}\n";
    }
    out << "\t\"progression\" { \"level\" \"" << m_progress.level << "\" \"xp\" \"" << m_progress.xp
        << "\" \"reward_total\" \"" << m_progress.rewardTotal << "\" }\n";
    if (!m_xpTracks.empty())
    {
        out << "\t\"xp_tracks\"\t\"";
        for (std::size_t i = 0; i < m_xpTracks.size(); ++i)
            out << (i ? " " : "") << m_xpTracks[i];
        out << "\"\n";
    }
    out << "\t\"items\"\n\t{\n";
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
            << "\t\t\t\"music_kit\"\t\"" << item.musicKit << "\"\n"
            << "\t\t\t\"keychain\"\t\"" << item.keychain << "\"\n";
        if (!item.customName.empty())
            out << "\t\t\t\"custom_name\"\t\"" << item.customName << "\"\n";
        if (item.souvenir)
            out << "\t\t\t\"souvenir\"\t\"1\"\n";
        if (item.tournamentEvent)
            out << "\t\t\t\"tournament_event\"\t\"" << item.tournamentEvent << "\"\n"
                << "\t\t\t\"tournament_team0\"\t\"" << item.tournamentTeam0 << "\"\n"
                << "\t\t\t\"tournament_team1\"\t\"" << item.tournamentTeam1 << "\"\n"
                << "\t\t\t\"tournament_player\"\t\"" << item.tournamentPlayer << "\"\n";
        if (item.statTrakFromContract)
            out << "\t\t\t\"contract_stattrak\"\t\"1\"\n";
        if (item.noStarSale)
            out << "\t\t\t\"no_star_sale\"\t\"1\"\n";
        if (item.unusual)
            out << "\t\t\t\"unusual\"\t\"1\"\n";
        if (item.terminalRemaining)
            out << "\t\t\t\"terminal_remaining\"\t\"" << *item.terminalRemaining << "\"\n";
        if (item.expiration)
            out << "\t\t\t\"expiration\"\t\"" << item.expiration << "\"\n";
        if (item.purchasePrice)
            out << "\t\t\t\"purchase_price\"\t\"" << *item.purchasePrice << "\"\n";
        if (item.ownerCertificate)
            out << "\t\t\t\"owner_certificate\"\t\"1\"\n";
        if (item.slabSticker)
            out << "\t\t\t\"slab_sticker\"\t\"" << item.slabSticker << "\"\n";
        if (item.storedIn)
            out << "\t\t\t\"stored_in\"\t\"" << item.storedIn << "\"\n";
        if (item.casketCount || item.casketModified)
            out << "\t\t\t\"casket\"\t\"" << item.casketCount << ' ' << item.casketModified << "\"\n";
        if (item.charm)
            out << "\t\t\t\"charm\"\t\"" << item.charm->kit << ' ' << FloatText(item.charm->offsetX) << ' '
                << FloatText(item.charm->offsetY) << ' ' << FloatText(item.charm->offsetZ) << ' '
                << item.charm->slabSticker << ' ' << (item.charm->noStarSale ? 1 : 0) << "\"\n";
        for (const AppliedSticker &sticker : item.stickers)
            out << "\t\t\t\"sticker_" << sticker.slot << "\"\t\"" << sticker.kit << ' ' << FloatText(sticker.wear)
                << ' ' << FloatText(sticker.scale) << ' ' << FloatText(sticker.rotation) << ' '
                << FloatText(sticker.offsetX) << ' ' << FloatText(sticker.offsetY) << "\"\n";
        out << "\t\t}\n";
    }
    out << "\t}\n}\n";
    return out.str();
}

std::optional<Inventory> Inventory::FromText(std::string_view sourceText)
{
    const auto parsed = ParseKeyValues(sourceText);
    const KvNode *root = parsed ? parsed->Find("inventory") : nullptr;
    const KvNode *items = root ? root->Find("items") : nullptr;
    if (!root || !root->block || !items || !items->block)
        return std::nullopt;

    Inventory inventory;
    if (!ParseNumber(root->Value("next_id"), inventory.m_nextId) || inventory.m_nextId == 0)
        return std::nullopt;

    if (const auto *pity = root->Find("case_pity"))
        if (pity->block || !ParseNumber(pity->value, inventory.m_casePity) || inventory.m_casePity > 99)
            return std::nullopt;

    if (const auto *matches = root->Find("match_reward_total"))
        if (matches->block || !ParseNumber(matches->value, inventory.m_matchRewardTotal))
            return std::nullopt;
    if (const auto *stars = root->Find("console_star_total"))
        if (stars->block || !ParseNumber(stars->value, inventory.m_consoleStarTotal))
            return std::nullopt;

    if (const auto *pities = root->Find("terminal_pity"))
    {
        if (!pities->block)
            return std::nullopt;
        for (const auto &entry : pities->children)
        {
            std::uint32_t definition = 0, failures = 0;
            if (entry.block || !ParseNumber(entry.key, definition) || !definition ||
                !ParseNumber(entry.value, failures) || failures > 99 ||
                !inventory.m_terminalPity.emplace(definition, failures).second)
                return std::nullopt;
        }
    }

    if (const auto *pities = root->Find("armory_pity"))
    {
        if (!pities->block) return std::nullopt;
        for (const auto &entry : pities->children)
        {
            std::uint32_t misses = 0;
            if (entry.block || entry.key.empty() || entry.key.size() > 256 ||
                !ParseNumber(entry.value, misses) || misses > 99 ||
                !inventory.m_armoryPity.emplace(entry.key, misses).second) return std::nullopt;
        }
    }
    if (const KvNode *progress = root->Find("progression"))
    {
        if (!progress->block || !ParseNumber(progress->Value("level"), inventory.m_progress.level) ||
            inventory.m_progress.level < 1 || inventory.m_progress.level > 40 ||
            !ParseNumber(progress->Value("xp"), inventory.m_progress.xp) || inventory.m_progress.xp >= ProfileLevelXp ||
            (inventory.m_progress.level == 40 && inventory.m_progress.xp != 0) ||
            !ParseNumber(progress->Value("reward_total"), inventory.m_progress.rewardTotal))
            return std::nullopt;
    }
    // Older saves start tracking from their current level; no invented historical drops.
    inventory.m_levelRewardTotal = inventory.m_progress.level - 1;
    if (const auto *levels = root->Find("level_reward_total"))
        if (levels->block || !ParseNumber(levels->value, inventory.m_levelRewardTotal) ||
            inventory.m_levelRewardTotal >= inventory.m_progress.level)
            return std::nullopt;

    if (const KvNode *credits = root->Find("armory_credits"))
    {
        std::uint32_t value = 0;
        if (credits->block || !ParseNumber(credits->value, value))
            return std::nullopt;
        inventory.m_armoryCredits = value;
    }

    if (const auto *unit = root->Find("track_xp_per_star"))
        if (unit->block || !ParseNumber(unit->value, inventory.m_trackXpPerStar) ||
            !inventory.m_trackXpPerStar || inventory.m_trackXpPerStar > 100000)
            return std::nullopt;
    inventory.m_gameplay.armory_xp_per_star = inventory.m_trackXpPerStar;
    if (const KvNode *tracks = root->Find("xp_tracks"))
    {
        std::string_view text = tracks->value;
        while (!text.empty())
        {
            const auto end = text.find(' ');
            std::uint32_t xp = 0;
            if (tracks->block || inventory.m_xpTracks.size() >= MaxXpTracks ||
                !ParseNumber(text.substr(0, end), xp) || xp == 0 || xp > 100000000u)
                return std::nullopt;
            inventory.m_xpTracks.push_back(xp);
            text = end == std::string_view::npos ? std::string_view{} : text.substr(end + 1);
        }
    }

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
        if (const auto *souvenir = entry.Find("souvenir"))
        {
            if (souvenir->block || souvenir->value != "1" || statTrak) return std::nullopt;
            item.souvenir = true;
        }
        for (const auto &[name, value] : {std::pair{"tournament_event", &item.tournamentEvent},
             std::pair{"tournament_team0", &item.tournamentTeam0}, std::pair{"tournament_team1", &item.tournamentTeam1},
             std::pair{"tournament_player", &item.tournamentPlayer}})
            if (entry.Find(name) && !ParseNumber(entry.Value(name), *value)) return std::nullopt;
        if (const auto *contract = entry.Find("contract_stattrak"))
        {
            if (contract->block || contract->value != "1" || statTrak != 1) return std::nullopt;
            item.statTrakFromContract = true;
        }
        // Optional so files written before the field existed still load.
        if (entry.Find("rarity") && (!ParseNumber(entry.Value("rarity"), item.rarity) || item.rarity > 99))
            return std::nullopt;
        if (entry.Find("music_kit") && !ParseNumber(entry.Value("music_kit"), item.musicKit)) return std::nullopt;
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
        if (const KvNode *slab = entry.Find("slab_sticker"))
        {
            if (slab->block || !ParseNumber(slab->value, item.slabSticker) || item.slabSticker == 0)
                return std::nullopt;
        }
        if (const KvNode *stored = entry.Find("stored_in"))
        {
            if (stored->block || !ParseNumber(stored->value, item.storedIn) || item.storedIn == 0)
                return std::nullopt;
        }
        if (const KvNode *casket = entry.Find("casket"))
        {
            const auto space = casket->value.find(' ');
            if (casket->block || space == std::string::npos ||
                !ParseNumber(std::string_view(casket->value).substr(0, space), item.casketCount) ||
                !ParseNumber(std::string_view(casket->value).substr(space + 1), item.casketModified) ||
                item.casketCount > 1000)
                return std::nullopt;
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
            if (ok && !text.empty()) // the sticker inside a sealed slab; files from before it existed lack it
                ok = ParseNumber(next(), applied.slabSticker);
            if (ok && !text.empty())
            {
                std::uint32_t free = 0;
                ok = ParseNumber(next(), free) && free <= 1 && text.empty();
                applied.noStarSale = free == 1;
            }
            if (!ok)
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
        if (const auto *free = entry.Find("no_star_sale"))
        {
            if (free->block || free->value != "1") return std::nullopt;
            item.noStarSale = true;
        }
        if (entry.Find("expiration") && !ParseNumber(entry.Value("expiration"), item.expiration))
            return std::nullopt;
        for (const auto &[key, target] : {std::pair{"terminal_remaining", &item.terminalRemaining},
                                         std::pair{"purchase_price", &item.purchasePrice}})
            if (const auto *node = entry.Find(key))
            {
                std::uint32_t value = 0;
                if (node->block || !ParseNumber(node->value, value))
                    return std::nullopt;
                *target = value;
            }
        if (const auto *certificate = entry.Find("owner_certificate"))
        {
            if (certificate->block || (certificate->value != "0" && certificate->value != "1"))
                return std::nullopt;
            item.ownerCertificate = certificate->value == "1";
        }
        if (const auto *unusual = entry.Find("unusual"))
        {
            if (unusual->block || unusual->value != "1")
                return std::nullopt;
            item.unusual = true;
        }
        inventory.m_items.push_back(item);
    }
    if (const auto *loadout = root->Find("loadout"))
    {
        if (!loadout->block) return std::nullopt;
        std::set<std::pair<std::uint32_t, std::uint32_t>> slots;
        for (const auto &entry : loadout->children)
        {
            LoadoutSlot slot;
            if (!entry.block || entry.children.size() != 4 ||
                !ParseNumber(entry.Value("class"), slot.classId) || !ParseNumber(entry.Value("slot"), slot.slotId) ||
                !ParseNumber(entry.Value("item_id"), slot.itemId) || !ParseNumber(entry.Value("definition"), slot.itemDefinition) ||
                !slots.emplace(slot.classId, slot.slotId).second) return std::nullopt;
            if (!slot.itemId)
            {
                if (slot.itemDefinition) return std::nullopt;
            }
            else if ((slot.itemId >> 60) == 0xF)
            {
                const auto definition = static_cast<std::uint32_t>(slot.itemId);
                if (!definition || definition != slot.itemDefinition) return std::nullopt;
            }
            else
            {
                const auto *item = slot.itemId > CustomItemIdBase ? inventory.Find(slot.itemId - CustomItemIdBase) : nullptr;
                if (!item || item->defIndex != slot.itemDefinition) return std::nullopt;
            }
            inventory.m_loadout.push_back(slot);
        }
    }
    if (root->Find("last_care_generation") &&
        !ParseNumber(root->Value("last_care_generation"), inventory.m_lastCareGeneration)) return std::nullopt;
    if (const auto *claimed = root->Find("care_claimed"))
    {
        ClaimedCarePackage record;
        if (!claimed->block || !ParseNumber(claimed->Value("generation"), record.generation) || !record.generation ||
            record.generation > inventory.m_lastCareGeneration) return std::nullopt;
        for (std::size_t slot = 0; slot < 4; ++slot)
        {
            std::istringstream fields(std::string(claimed->Value("slot" + std::to_string(slot))));
            ClaimedCareSlot entry; std::string extra;
            if (!(fields >> entry.defIndex >> entry.paintKitIndex >> entry.ownedId) || (fields >> extra)) return std::nullopt;
            record.slots.push_back(entry);
        }
        if (claimed->children.size() != 5) return std::nullopt;
        inventory.m_lastClaimedCare = std::move(record);
    }
    if (const auto *packages = root->Find("care_packages"))
    {
        if (!packages->block || packages->children.size() > 256) return std::nullopt;
        std::uint32_t previous = 0;
        for (const auto &node : packages->children)
        {
            std::uint32_t generation = 0;
            if (!node.block || !ParseNumber(node.key, generation) || !generation || generation <= previous ||
                generation > inventory.m_lastCareGeneration || node.Find("care_packages")) return std::nullopt;
            previous = generation;
            std::ostringstream text;
            std::function<void(const KvNode &)> write = [&](const KvNode &entry) {
                text << std::quoted(entry.key) << ' ';
                if (entry.block) { text << "{\n"; for (const auto &child : entry.children) write(child); text << "}\n"; }
                else text << std::quoted(entry.value) << '\n';
            };
            text << "\"inventory\" {\n";
            for (const auto &entry : node.children) write(entry);
            text << "}\n";
            const auto preview = Inventory::FromText(text.str());
            if (!preview || preview->m_items.size() != 4 || preview->m_nextId != inventory.m_nextId ||
                !preview->m_loadout.empty()) return std::nullopt;
            for (const auto &item : preview->m_items)
                if (!seen.insert(item.id).second || item.storedIn || item.casketCount) return std::nullopt;
            inventory.m_carePackages.push_back({generation, preview->m_items});
        }
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

namespace cs2_gc
{
bool Inventory::ApplyConsoleStars(std::uint64_t cumulative)
{
    if (cumulative <= m_consoleStarTotal) return false;
    const auto delta = cumulative - m_consoleStarTotal;
    const auto balance = static_cast<std::uint64_t>(m_armoryCredits.value_or(0));
    m_armoryCredits = static_cast<std::uint32_t>(balance + std::min<std::uint64_t>(delta, UINT32_MAX - balance));
    m_consoleStarTotal = cumulative;
    return true;
}

bool Inventory::QueueCarePackage(std::vector<InventoryItem> offers)
{
    if (offers.size() != 4 || m_carePackages.size() >= 256 || m_lastCareGeneration == UINT32_MAX) return false;
    const auto now = static_cast<std::uint64_t>(std::time(nullptr));
    const auto generation = std::max(m_lastCareGeneration + 1, static_cast<std::uint32_t>(std::min<std::uint64_t>(now, UINT32_MAX)));
    for (auto &item : offers) { item.id = Add(item); Remove(item.id); }
    m_carePackages.push_back({generation,std::move(offers)});
    m_lastCareGeneration = generation;
    return true;
}

std::optional<std::vector<InventoryItem>> Inventory::ClaimCarePackage(std::uint32_t generation,
                                                                    const std::vector<std::uint64_t> &ids)
{
    if (m_carePackages.empty() || m_carePackages.front().generation != generation || ids.size() != 3) return std::nullopt;
    const auto &offers = m_carePackages.front().offers;
    std::set<std::uint64_t> unique;
    std::vector<InventoryItem> chosen;
    for (const auto id : ids)
    {
        const auto found = std::find_if(offers.begin(),offers.end(),[&](const auto &item){return item.id==id;});
        if (!unique.insert(id).second || found==offers.end()) return std::nullopt;
        chosen.push_back(*found);
    }
    m_items.insert(m_items.end(),chosen.begin(),chosen.end());
    ClaimedCarePackage claimed{generation, {}};
    for (const auto &offer : offers)
        claimed.slots.push_back({offer.defIndex, offer.paintKitIndex, unique.count(offer.id) ? offer.id : 0});
    m_lastClaimedCare = std::move(claimed);
    m_carePackages.erase(m_carePackages.begin());
    return chosen;
}

}
