#include "cs2_gc/armory.h"
#include "cs2_gc/armory_catalog.h"
#include "cs2_gc/case_opening.h"
#include "cs2_gc/econ_item.h"
#include "cs2_gc/client_fingerprint.h"
#include "cs2_gc/gc_endpoint.h"
#include "cs2_gc/gc_msg_ids.h"
#include "cs2_gc/gc_summary.h"
#include "cs2_gc/live_inventory.h"
#include "cs2_gc/protobuf.h"
#include "cs2_gc/protobuf_dump.h"
#include "cs2_gc/replay.h"
#include "cs2_gc/proxy_support.h"
#include "cs2_gc/message_queue.h"
#include "cs2_gc/progression.h"
#include "cs2_gc/schema.h"
#include "cs2_gc/item_sales.h"
#include <array>
#include <filesystem>
#include <fstream>
#include <cmath>
#include <atomic>
#include <cstring>
#include <iostream>
#include <map>
#include <set>
#include <limits>
#include <random>
#include <stdexcept>
#include <thread>

using namespace cs2_gc;

void Check(bool condition, const char *message)
{
    if (!condition)
        throw std::runtime_error(message);
}

Message Packet(std::uint32_t type = 4004, std::uint8_t body = 7)
{
    Message packet{type | ProtobufMask, {}};
    const std::array<std::uint8_t, 1> payload{body};
    Check(WriteProtobufFrame(type, {}, payload, packet.bytes) == FrameError::None, "packet encode");
    return packet;
}

void Frames()
{
    std::vector<std::uint8_t> bytes;
    const std::array<std::uint8_t, 2> header{0x50, 1};
    const std::array<std::uint8_t, 3> body{8, 2, 0};
    Check(WriteProtobufFrame(4004, header, body, bytes) == FrameError::None, "encode");
    Check(bytes[0] == 0xA4 && bytes[1] == 0x0F && bytes[3] == 0x80, "little endian type");
    FrameView frame;
    Check(ReadProtobufFrame(4004 | ProtobufMask, bytes, frame) == FrameError::None, "decode");
    Check(frame.header.size() == 2 && frame.body.size() == 3 && frame.body[1] == 2, "payload preserved");
    Check(WriteProtobufFrame(frame.type, frame.header, frame.body, bytes) == FrameError::None, "aliased input");
    for (std::size_t size = 0; size < 8; ++size)
        Check(ReadProtobufFrame(4004 | ProtobufMask, std::span{bytes}.first(size), frame)
            == FrameError::Truncated, "truncated prefix");
    Check(ReadProtobufFrame(4005 | ProtobufMask, bytes, frame) == FrameError::TypeMismatch, "type mismatch");
    bytes[4] = 255;
    Check(ReadProtobufFrame(4004 | ProtobufMask, bytes, frame) == FrameError::InvalidHeaderLength, "bad header length");
    Check(frame.header.empty() && frame.body.empty(), "failure resets views");
    bytes = {0, 0, 0, 0x80, 0, 0, 0, 0};
    Check(ReadProtobufFrame(ProtobufMask, bytes, frame) == FrameError::InvalidType, "zero type");
    bytes[3] = 0;
    Check(ReadProtobufFrame(0, bytes, frame) == FrameError::NotProtobuf, "legacy frame rejected");
    std::vector<std::uint8_t> huge(MaxMessageBytes + 1);
    Check(ReadProtobufFrame(1, huge, frame) == FrameError::TooLarge, "oversized read");
    Check(WriteProtobufFrame(1, {}, huge, bytes) == FrameError::TooLarge, "oversized write");
    Check(WriteProtobufFrame(0, {}, {}, bytes) == FrameError::InvalidType, "zero write type");
    std::mt19937 random{123};
    for (int i = 0; i < 20000; ++i)
    {
        bytes.resize(random() % 128);
        for (auto &byte : bytes)
            byte = static_cast<std::uint8_t>(random());
        (void)ReadProtobufFrame(random(), bytes, frame);
    }
}

void Queues()
{
    MessageQueue queue{18, 2};
    Check(queue.Push(Packet()), "push");
    Check(queue.Push(Packet(4005)), "second push");
    Check(!queue.Push(Packet()), "bounded queue");
    std::uint32_t type = 1, size = 1;
    Check(queue.IsMessageAvailable(&size) && size == 9, "peek size");
    std::array<std::uint8_t, 16> buffer{};
    Check(queue.RetrieveMessage(&type, buffer.data(), 8, &size) == GCResult::BufferTooSmall, "small buffer");
    Check(size == 9 && type == 0, "required size on small buffer");
    Check(queue.RetrieveMessage(&type, nullptr, 16, &size) == GCResult::InvalidMessage, "null destination");
    Check(queue.RetrieveMessage(&type, buffer.data(), 16, &size) == GCResult::OK
        && type == (4004 | ProtobufMask), "failed retrieves retain first message");
    Check(queue.Push(Packet()), "capacity reclaimed");
    queue.Clear();
    Check(!queue.IsMessageAvailable(&size) && size == 0, "clear");
    Check(queue.RetrieveMessage(&type, buffer.data(), 16, &size) == GCResult::NoMessage && type == 0, "empty retrieve");
    Check(!queue.IsMessageAvailable(nullptr), "null size");
    Check(queue.RetrieveMessage(nullptr, buffer.data(), 16, &size) == GCResult::InvalidMessage, "null type");
    Check(!queue.Push({1, {1, 2}}), "malformed message");
    MessageQueue tiny{8, 1};
    Check(!tiny.Push(Packet()), "byte budget");

    MessageQueue concurrent;
    std::array<std::thread, 4> producers;
    std::atomic<bool> success{true};
    for (auto &thread : producers)
        thread = std::thread{[&] { for (int i = 0; i < 250; ++i) if (!concurrent.Push(Packet())) success = false; }};
    for (auto &thread : producers)
        thread.join();
    int received = 0;
    while (concurrent.RetrieveMessage(&type, buffer.data(), 16, &size) == GCResult::OK)
        ++received;
    Check(success && received == 1000, "concurrent producers lose no messages");
}

void Progression()
{
    Profile profile;
    RewardConfig config;
    ApplyReward(profile, RewardEvent::Kill, config);
    ApplyReward(profile, RewardEvent::Headshot, config);
    Check(profile.xp == 8 && profile.stars == 5, "headshot bonus is additive");
    profile.xp = 4990;
    const auto change = ApplyReward(profile, RewardEvent::MVP, config);
    Check(change.levelsGained == 1 && profile.level == 2 && profile.xp == 15, "level rollover");
    config.matchComplete.xp = 15000;
    Check(ApplyReward(profile, RewardEvent::MatchComplete, config).levelsGained == 3 && profile.xp == 15,
        "multiple levels");
    profile = {39, 4999, 0};
    ApplyReward(profile, RewardEvent::Kill, config);
    Check(profile.level == 40 && profile.xp == 0, "level cap");
    ApplyReward(profile, RewardEvent::MatchComplete, config);
    Check(profile.level == 40 && profile.xp == 0 && profile.stars == 51, "stars continue at level cap");
    profile.stars = std::numeric_limits<std::uint64_t>::max() - 1;
    Check(ApplyReward(profile, RewardEvent::MatchComplete, config).starsAdded == 1, "no currency overflow");
    config.xpEnabled = false;
    config.starsEnabled = false;
    profile = {};
    ApplyReward(profile, RewardEvent::Kill, config);
    Check(profile.level == 1 && profile.xp == 0 && profile.stars == 0, "disabled rewards");
    config.xpEnabled = true;
    config.xpPerLevel = 0;
    ApplyReward(profile, RewardEvent::Kill, config);
    Check(profile.level == 6, "zero level threshold is normalized");
}

void ArmoryCatalogueTest()
{
    std::vector<ArmoryGood> goods;
    // Synthetic IDs; these fixtures are not an item catalogue to install.
    for (std::uint32_t i = 1; i <= 25; ++i)
        goods.push_back({i, "Case " + std::to_string(i), ArmoryCategory::Cases, 10, 100});
    goods.push_back({50, "Random Agent", ArmoryCategory::Agents, 50, 0});
    ArmoryCatalog catalog{goods};
    ArmoryQuery query;
    auto page = catalog.Query(query);
    Check(page.pageCount == 3 && page.totalGoods == 26 && page.goods.size() == 12, "catalog pages");
    Check(!page.HasPrevious() && page.HasNext(), "first page navigation");
    query.page = std::numeric_limits<std::size_t>::max();
    page = catalog.Query(query);
    Check(page.page == 2 && page.goods.size() == 2 && !page.HasNext() && page.HasPrevious(), "last page clamping");
    query.category = ArmoryCategory::Agents;
    page = catalog.Query(query);
    Check(page.page == 0 && page.goods.size() == 1 && page.goods[0].defIndex == 50, "category filter");
    query.category.reset();
    query.search = "CASE 2";
    page = catalog.Query(query);
    Check(page.totalGoods == 7 && page.goods[0].defIndex == 2, "search before paging");
    query.search = "unknown";
    page = catalog.Query(query);
    Check(page.pageCount == 0 && !page.HasNext() && !page.HasPrevious(), "empty search");
    Check(catalog.Find(1) && catalog.Find(1)->keyDefIndex == 100 && !catalog.Find(999), "authoritative item lookup");
    query = {};
    query.pageSize = 0;
    Check(catalog.Query(query).goods.size() == 1, "minimum page size");
    query.pageSize = std::numeric_limits<std::size_t>::max();
    Check(catalog.Query(query).goods.size() == 26, "maximum page size");
    goods.push_back(goods[0]);
    bool rejected = false;
    try { ArmoryCatalog duplicate{goods}; } catch (const std::invalid_argument &) { rejected = true; }
    Check(rejected, "duplicate catalogue IDs rejected");
}


// Synthetic fixture shaped like items_game.txt; not real game data.
constexpr const char *SchemaFixture = R"("items_game"
{
    "prefabs"
    {
        "weapon_case_base" { "item_name" "#Base_Crate" }
        "weapon_case" { "prefab" "weapon_case_base" "associated_item" "900" }
        "weapon_case_souvenirpkg" { "prefab" "weapon_case_base" }
        "sticker_capsule" { "prefab" "weapon_case_base" }
    }
    "items"
    {
        "900" { "name" "a_key" }
        "901" // comment
        {
            "name" "case_one" "item_name" "#Case_One" "prefab" "weapon_case"
            "attributes" { "set supply crate series" { "attribute_class" "supply_crate_series" "value" "5" } }
        }
        "902"
        {
            "name" "keyless" "item_name" "#Case_Two" "prefab" "weapon_case"
            "associated_items" { "903" "1" }
            "attributes" { "set supply crate series" { "value" "6" } }
        }
        "910"
        {
            "name" "souvenir" "prefab" "weapon_case_souvenirpkg"
            "attributes" { "set supply crate series" { "value" "7" } }
        }
        "906" { "name" "capsule" "prefab" "sticker_capsule" "attributes" { "set supply crate series" { "value" "9" } } }
        "911" { "name" "no_series" "prefab" "weapon_case" }
    }
    "items" { "905" { "name" "late" "prefab" "weapon_case" "attributes" { "set supply crate series" { "value" "8" } } } }
    "revolving_loot_lists" { "5" "case_one_lootlist" "6" "case_two_lootlist" }
    "client_loot_lists"
    {
        "case_one_lootlist" { "case_one_rare" "1" "case_one_mythical" "1" "set_unusual_missing" "1" }
        "case_one_rare" { "[kit_a]weapon_ak47" "1" "[kit_b]weapon_awp" "1" }
        "case_one_mythical" { "[kit_c]weapon_m4a1" "1" }
        "case_two_lootlist" { "case_two_lootlist" "1" }
    }
})";

void KeyValuesParsing()
{
    auto root = ParseKeyValues("\xEF\xBB\xBF" "\"a\" { \"k\" \"v\\\"q\" \"k\" \"w\" \"n\" { } } // tail");
    Check(root && root->Find("a") && root->Find("a")->Value("k") == "v\"q", "escaped value, first duplicate wins");
    Check(root->Find("a")->children.size() == 3 && root->Find("a")->Find("n")->block, "duplicates kept");
    Check(!ParseKeyValues("\"a\" {"), "unterminated block");
    Check(!ParseKeyValues("\"a\" }"), "stray close");
    Check(!ParseKeyValues("\"a\" \"b"), "unterminated string");
    Check(!ParseKeyValues("{ }"), "block without key");
    Check(!ParseKeyValues("\"a\""), "key without value");
    Check(!ParseKeyValues("bare"), "unquoted token");
    std::string deep;
    for (int i = 0; i < 200; ++i) deep += "\"k\" {";
    Check(!ParseKeyValues(deep), "depth limit");
}

void SchemaCrates()
{
    Check(!Schema::Load("\"other\" { }"), "needs items_game root");
    const auto schema = Schema::Load(SchemaFixture);
    Check(schema.has_value(), "fixture loads");
    Check(schema->Crates().size() == 5, "souvenir packages included, seriesless items excluded, repeated sections merged");
    const CrateInfo *one = schema->FindCrate(901);
    Check(one && one->keyDefIndex == 900 && one->series == 5 && one->nameToken == "Case_One", "prefab key and token");
    Check(one->lootListName == "case_one_lootlist", "series resolves loot list");
    const CrateInfo *two = schema->FindCrate(902);
    Check(two && two->keyDefIndex == 903, "associated_items key");
    Check(one->kind == CrateKind::Case && schema->FindCrate(906)->kind == CrateKind::Capsule, "kind from prefab chain");
    Check(schema->FindCrate(905)->kind == CrateKind::Case, "prefab-inherited key makes a case");
    Check(schema->FindCrate(905) && schema->FindCrate(910)->kind == CrateKind::Souvenir && !schema->FindCrate(1), "lookup");

    const auto tiers = schema->LootTiers("case_one_lootlist");
    Check(tiers.size() == 2 && tiers[0].name == "case_one_rare" && tiers[0].items.size() == 2, "tiers flattened");
    Check(tiers[1].items.front() == "[kit_c]weapon_m4a1", "entries unexpanded");
    Check(schema->LootTiers("case_two_lootlist").empty(), "cycle cut off");
    Check(schema->LootTiers("missing").empty(), "unknown list");
}

constexpr const char *OpeningFixture = R"("items_game"
{
    "rarities" { "rare" { "value" "3" } "mythical" { "value" "4" } "legendary" { "value" "5" } "ancient" { "value" "6" } }
    "prefabs"
    {
        "weapon_case_base" { }
        "weapon_case" { "prefab" "weapon_case_base" "associated_item" "50" }
    }
    "items"
    {
        "50" { "name" "key" }
        "51" { "name" "other_key" }
        "60" { "name" "the_case" "prefab" "weapon_case"
               "attributes" { "set supply crate series" { "value" "1" } } }
        "7" { "name" "weapon_ak47" }
        "9" { "name" "weapon_awp" }
    }
    "paint_kits"
    {
        "100" { "name" "kit_a" "wear_remap_min" "0.10" "wear_remap_max" "0.20" }
        "101" { "name" "kit_b" "wear_remap_min" "0.00" "wear_remap_max" "1.00" }
        "102" { "name" "kit_bad" "wear_remap_min" "0.90" "wear_remap_max" "0.10" }
    }
    "revolving_loot_lists" { "1" "lootlist" }
    "client_loot_lists"
    {
        "lootlist" { "box_rare" "1" "box_mythical" "1" "box_legendary" "1" "box_ancient" "1" }
        "box_rare" { "[kit_a]weapon_ak47" "1" "[kit_b]weapon_awp" "1" "[kit_missing]weapon_awp" "1" }
        "box_mythical" { "[kit_b]weapon_ak47" "1" }
        "box_legendary" { "[kit_bad]weapon_ak47" "1" }
        "box_ancient" { "[kit_a]weapon_awp" "1" }
    }
})";

void CaseOpening()
{
    const auto schema = Schema::Load(OpeningFixture);
    Check(schema.has_value(), "opening fixture loads");
    Check(schema->ResolveLootItem("[kit_a]weapon_ak47").has_value(), "resolves");
    Check(!schema->ResolveLootItem("[kit_missing]weapon_awp") && !schema->ResolveLootItem("[kit_a]weapon_nope") &&
              !schema->ResolveLootItem("kit_a") && !schema->ResolveLootItem("[kit_bad]weapon_ak47"),
          "unresolvable entries rejected");
    const auto tiers = schema->LootTiers("lootlist");
    Check(tiers.size() == 4 && tiers[0].rarity == 3 && tiers[3].rarity == 6, "tier rarity from suffix");

    std::mt19937_64 engine(12345);
    const RandomSource random = [&] { return engine(); };
    const std::array<std::uint32_t, 4> expected{7992, 1598, 320, 64};

    // Failures leave the inventory untouched.
    Inventory inventory;
    const auto crate = inventory.Add({0, 60});
    const auto key = inventory.Add({0, 50});
    const auto wrong = inventory.Add({0, 51});
    const auto notCrate = inventory.Add({0, 7});
    Check(OpenCase(inventory, *schema, 999, key, random).error == OpenError::NoSuchCrate, "unknown crate");
    Check(OpenCase(inventory, *schema, notCrate, key, random).error == OpenError::NoSuchCrate, "not a crate");
    Check(OpenCase(inventory, *schema, crate, 999, random).error == OpenError::NoSuchKey, "unknown key");
    Check(OpenCase(inventory, *schema, crate, wrong, random).error == OpenError::WrongKey, "wrong key");
    Check(inventory.Items().size() == 4, "failed opens change nothing");
    {
        // free_case_keys (default): one key per case type is added and opening never uses it up.
        LiveInventory live(Inventory{});
        live.AddItem({0, 60});
        live.AddItem({0, 60});
        const auto keys = live.EnsureCaseKeys(*schema);
        Check(keys.empty() && live.EnsureCaseKeys(*schema).empty(),
              "free opening does not create inventory keys");
        Inventory inv;
        const auto c = inv.Add({0, 60});
        const auto k = inv.Add({0, 50});
        Check(OpenCase(inv, *schema, c, k, random).error == OpenError::None && !inv.Find(c) && inv.Find(k),
              "free_case_keys: the case is opened and the key is kept");
    }

    // Statistical check on many opens, each with a fresh crate and key.
    std::array<int, 4> counts{};
    int statTrak = 0;
    constexpr int Opens = 40000;
    for (int i = 0; i < Opens; ++i)
    {
        Inventory inv;
        GameplayConfig paidKeys;
        paidKeys.free_case_keys = 0;
        inv.SetGameplay(paidKeys);
        const auto c = inv.Add({0, 60});
        const auto k = inv.Add({0, 50});
        const OpenResult result = OpenCase(inv, *schema, c, k, random);
        Check(result.error == OpenError::None, "open succeeds");
        Check(inv.Items().size() == 1 && !inv.Find(c) && !inv.Find(k) && inv.Find(result.item.id), "crate and key consumed, item granted");
        const InventoryItem &item = result.item;
        Check(item.seed >= 1 && item.seed <= 1000 && item.wear >= 0.0f && item.wear <= 1.0f, "seed and wear range");
        if (item.defIndex == 7 && item.paintKitIndex == 100)
        {
            ++counts[0];
            Check(item.wear >= 0.10f && item.wear <= 0.20f, "wear within kit range");
        }
        else if (item.paintKitIndex == 101 && item.defIndex == 9)
            ++counts[0];
        else if (item.defIndex == 7 && item.paintKitIndex == 101)
            ++counts[1];
        else if (item.defIndex == 9 && item.paintKitIndex == 100)
            ++counts[3];
        else
            Check(false, "item not from the loot list");
        statTrak += item.statTrak;
    }
    // The legendary tier only holds an invalid kit, so it is skipped and the others renormalise.
    const double total = expected[0] + expected[1] + expected[3];
    const double tolerance = 0.015;
    Check(std::abs(counts[0] / double(Opens) - expected[0] / total) < tolerance, "mil-spec odds");
    Check(std::abs(counts[1] / double(Opens) - expected[1] / total) < tolerance, "restricted odds");
    Check(std::abs(counts[3] / double(Opens) - expected[3] / total) < tolerance, "covert odds");
    Check(std::abs(statTrak / double(Opens) - 0.1) < tolerance, "StatTrak rate");

    // A case whose loot list resolves to nothing fails cleanly without consuming anything.
    const auto empty = Schema::Load(R"("items_game"
    {
        "rarities" { "rare" { "value" "3" } }
        "prefabs" { "weapon_case_base" { } "weapon_case" { "prefab" "weapon_case_base" "associated_item" "50" } }
        "items" { "50" { "name" "k" } "60" { "prefab" "weapon_case" "name" "c"
                  "attributes" { "set supply crate series" { "value" "1" } } } }
        "revolving_loot_lists" { "1" "ll" }
        "client_loot_lists" { "ll" { "x_rare" "1" } "x_rare" { "[nokit]weapon_none" "1" } }
    })");
    Inventory inv;
    const auto c = inv.Add({0, 60});
    const auto k = inv.Add({0, 50});
    Check(empty.has_value() && empty->FindCrate(60), "empty fixture loads");
    Check(OpenCase(inv, *empty, c, k, random).error == OpenError::EmptyLootList && inv.Items().size() == 2,
          "nothing consumed");
}

void InventoryPersistence()
{
    Inventory inventory;
    inventory.Add({0, 7, 100, 0.123456789f, 42, true});
    const auto doomed = inventory.Add({0, 9, 0, 0.0f, 1, false});
    inventory.Add({0, 4001, 0, 1.0f, 1000, false});
    inventory.Remove(doomed); // ids must not be reused after a removal

    const auto restored = Inventory::FromText(inventory.ToText());
    Check(restored && restored->Items().size() == 2, "round trip count");
    Check(restored->Items()[0].wear == inventory.Items()[0].wear && restored->Items()[0].statTrak &&
              restored->Items()[0].seed == 42 && restored->Items()[1].defIndex == 4001, "round trip fields exact");
    Inventory next = *restored;
    Check(next.Add({0, 1, 0, 0.0f, 1, false}) == 4, "id counter survives, removed ids not reused");

    // Strict rejection: nothing partial is ever loaded.
    const auto bad = [&](const char *replace, const char *with) {
        std::string text = inventory.ToText();
        const std::size_t at = text.find(replace);
        Check(at != std::string::npos, "test mutation applies");
        text.replace(at, std::string_view(replace).size(), with);
        return Inventory::FromText(text).has_value();
    };
    Check(!bad("\"wear\"\t\"0.12345679\"", "\"wear\"\t\"1.5\""), "wear above 1");
    Check(!bad("\"wear\"\t\"0.12345679\"", "\"wear\"\t\"nan\""), "nan wear");
    Check(!bad("\"seed\"\t\"42\"", "\"seed\"\t\"1001\""), "seed above 1000");
    Check(!bad("\"stattrak\"\t\"1\"", "\"stattrak\"\t\"2\""), "stattrak flag");
    Check(!bad("\"def_index\"\t\"7\"", "\"def_index\"\t\"0\""), "zero def index");
    Check(!bad("\"def_index\"\t\"7\"", "\"def_index\"\t\"7x\""), "trailing junk");
    Check(!bad("\"3\"\n", "\"1\"\n"), "duplicate id");
    Check(!bad("\"next_id\"\t\"4\"", "\"next_id\"\t\"3\""), "id at or above next_id");
    Check(!Inventory::FromText("\"inventory\" { }") && !Inventory::FromText("") && !Inventory::FromText("\"inventory\" {"),
          "missing sections and truncation");
    Check(Inventory::FromText(Inventory{}.ToText()).has_value(), "empty inventory round trips");

    const auto dir = std::filesystem::temp_directory_path() / "cs2_gc_inventory_test";
    std::filesystem::create_directories(dir);
    const auto file = dir / "inventory.txt";
    std::filesystem::remove(file);
    Check(!Inventory::Load(file), "missing file");
    Check(inventory.Save(file) && !std::filesystem::exists(dir / "inventory.txt.tmp"), "save, no temp left");
    Check(Inventory::Load(file) && Inventory::Load(file)->Items().size() == 2, "load from disk");
    Check(next.Save(file) && Inventory::Load(file)->Items().size() == 3, "overwrite existing");
    Check(!inventory.Save(dir / "no_such_dir" / "inventory.txt"), "unwritable path reports failure");
    std::ofstream(file, std::ios::trunc) << "\"inventory\" { \"next_id\" \"2\" ";
    Check(!Inventory::Load(file), "corrupt file rejected");
    std::filesystem::remove_all(dir);
}

void GcMessageIds()
{
    // Values extracted from the target client's embedded descriptors; they must stay
    // consistent with the wire tests above, which already use 4004 for the welcome.
    namespace m = cs2_gc::gc_msg;
    Check(m::EGCBaseClientMsg::k_EMsgGCClientWelcome == 4004 && m::EGCBaseClientMsg::k_EMsgGCClientHello == 4006,
          "hello and welcome");
    Check(m::ESOMsg::k_ESOMsg_Create == 21 && m::ESOMsg::k_ESOMsg_CacheSubscribed == 24, "SO cache messages");
    Check(m::EGCItemMsg::k_EMsgGCOpenCrate == 2534, "this build opens cases with OpenCrate");
    Check(m::GCConnectionStatus::GCConnectionStatus_HAVE_SESSION == 0, "connection status");
    Check(std::string_view(m::MessageName(4006)) == "EGCBaseClientMsg::k_EMsgGCClientHello" && !m::MessageName(1), "name lookup");
    Check(TargetSteamBuildId == "25947352" && TargetClientDllSha256.size() == 64 &&
              TargetEngine2DllSha256.size() == 64 && TargetSteamApiDllSha256.size() == 64,
          "fingerprint record");
}

std::vector<std::uint8_t> Bytes(std::initializer_list<int> values)
{
    std::vector<std::uint8_t> out;
    for (int v : values)
        out.push_back(static_cast<std::uint8_t>(v));
    return out;
}

void ProtobufWire()
{
    // Canonical vectors from the protobuf encoding documentation.
    PbWriter w;
    w.Varint(1, 150);
    Check(w.bytes() == Bytes({0x08, 0x96, 0x01}), "varint vector");
    PbWriter s;
    s.String(2, "testing");
    Check(s.bytes() == Bytes({0x12, 0x07, 't', 'e', 's', 't', 'i', 'n', 'g'}), "string vector");
    PbWriter fixed;
    fixed.Fixed64(3, 0x0102030405060708ull);
    fixed.Fixed32(4, 0x0A0B0C0Du);
    Check(fixed.bytes() == Bytes({0x19, 8, 7, 6, 5, 4, 3, 2, 1, 0x25, 0x0D, 0x0C, 0x0B, 0x0A}), "fixed vectors");

    PbReader reader(fixed.bytes());
    PbField f;
    Check(reader.Next(f) && f.number == 3 && f.wire == 1 && f.value == 0x0102030405060708ull, "fixed64 read");
    Check(reader.Next(f) && f.number == 4 && f.wire == 5 && f.value == 0x0A0B0C0Du, "fixed32 read");
    Check(!reader.Next(f) && !reader.Failed(), "clean end");

    PbWriter big;
    big.Varint(1, UINT64_MAX);
    PbReader bigReader(big.bytes());
    Check(bigReader.Next(f) && f.value == UINT64_MAX, "max varint");

    const auto fails = [](std::vector<std::uint8_t> bytes) {
        PbReader r(bytes);
        PbField field;
        while (r.Next(field)) {}
        return r.Failed();
    };
    Check(fails(Bytes({0x08})), "missing varint");
    Check(fails(Bytes({0x08, 0x80})), "truncated varint");
    Check(fails(Bytes({0x08, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x02})), "varint overflows 64 bits");
    Check(fails(Bytes({0x08, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x01})), "varint too long");
    Check(fails(Bytes({0x00, 0x01})), "field number zero");
    Check(fails(Bytes({0x12, 0x05, 1, 2})), "length overruns");
    Check(fails(Bytes({0x12, 0xFF, 0xFF, 0xFF, 0xFF, 0x0F})), "huge length");
    Check(fails(Bytes({0x0B})) && fails(Bytes({0x0C})) && fails(Bytes({0x0E})), "group and invalid wire types");
    Check(fails(Bytes({0x19, 1, 2, 3})) && fails(Bytes({0x25, 1})), "short fixed");
    Check(!fails({}), "empty message is valid");

    // No prefix of a valid message may crash the reader.
    PbWriter nested;
    nested.Varint(1, 300);
    nested.Message(2, w);
    nested.Fixed64(3, 7);
    for (std::size_t n = 0; n <= nested.bytes().size(); ++n)
        fails(std::vector<std::uint8_t>(nested.bytes().begin(), nested.bytes().begin() + n));
}

void HandshakeCodec()
{
    ClientHello hello;
    hello.version = 7;
    hello.haveVersions.push_back({{1, 76561190000000001ull}, 42});
    hello.clientSessionNeed = 9;
    hello.clientLauncher = 3;
    hello.steamLauncher = 2;
    const auto decoded = DecodeClientHello(EncodeClientHello(hello));
    Check(decoded && *decoded->version == 7 && decoded->haveVersions.size() == 1 &&
              decoded->haveVersions[0].owner.id == 76561190000000001ull && decoded->haveVersions[0].version == 42 &&
              *decoded->clientSessionNeed == 9 && *decoded->clientLauncher == 3 && *decoded->steamLauncher == 2,
          "hello round trip");
    const auto empty = DecodeClientHello({});
    Check(empty && !empty->version && empty->haveVersions.empty(), "empty hello");

    PbWriter unknown;
    unknown.Varint(99, 1);
    unknown.Varint(1, 5);
    Check(DecodeClientHello(unknown.bytes()) && *DecodeClientHello(unknown.bytes())->version == 5, "unknown fields skipped");
    PbWriter oversized;
    oversized.Varint(1, 0x100000000ull);
    Check(!DecodeClientHello(oversized.bytes()), "oversized uint32 rejected");
    PbWriter wrongWire;
    wrongWire.Fixed64(1, 5);
    Check(!DecodeClientHello(wrongWire.bytes()), "wrong wire type rejected");
    Check(!DecodeClientHello(Bytes({0x08})), "truncated hello rejected");

    ClientWelcome welcome;
    welcome.version = 11;
    welcome.outOfDateCaches.push_back({{1, 99}, 5, {{-1, {{1, 2, 3}, {}}}, {1, {}}}});
    const auto bytes = EncodeClientWelcome(welcome);
    const auto back = DecodeClientWelcome(bytes);
    Check(back && back->version == 11 && back->outOfDateCaches.size() == 1, "welcome round trip");
    const SoCacheSubscribed &cache = back->outOfDateCaches[0];
    Check(cache.owner.id == 99 && cache.version == 5 && cache.types.size() == 2 && cache.types[0].typeId == -1 &&
              cache.types[0].objects.size() == 2 && cache.types[0].objects[0] == Bytes({1, 2, 3}) &&
              cache.types[0].objects[1].empty() && cache.types[1].typeId == 1,
          "cache contents, negative type id, empty object");
    // Known encoding: version=11, one cache {types:[], version fixed64=5, owner{type 1,id 99}}.
    ClientWelcome minimal;
    minimal.version = 11;
    minimal.outOfDateCaches.push_back({{1, 99}, 5, {}});
    Check(EncodeClientWelcome(minimal) ==
              Bytes({0x08, 0x0B, 0x1A, 0x0F, 0x19, 5, 0, 0, 0, 0, 0, 0, 0, 0x22, 0x04, 0x08, 0x01, 0x10, 0x63}),
          "welcome wire layout");
    for (std::size_t n = 0; n < bytes.size(); ++n)
        DecodeClientWelcome(std::span(bytes).first(n)); // must not crash on any prefix
}

void Endpoint()
{
    GcEndpointConfig config;
    config.welcomeVersion = 5;
    config.owner = {1, 1234};
    config.cacheVersion = 77;
    config.cacheTypes = {{1, {{9, 9}}}};
    LocalGameCoordinator gc(config);

    const auto send = [&](std::uint32_t type, const std::vector<std::uint8_t> &body) {
        std::vector<std::uint8_t> frame;
        Check(WriteProtobufFrame(type, {}, body, frame) == FrameError::None, "frame");
        return gc.SendMessage(type | ProtobufMask, frame.data(), static_cast<std::uint32_t>(frame.size()));
    };

    std::uint32_t size = 123;
    Check(!gc.IsMessageAvailable(&size) && size == 0, "nothing before hello");

    ClientHello hello;
    hello.version = 1;
    Check(send(gc_msg::EGCBaseClientMsg::k_EMsgGCClientHello, EncodeClientHello(hello)) == GCResult::OK, "hello accepted");
    Check(gc.IsMessageAvailable(&size) && size > 8, "welcome queued");

    std::uint32_t type = 0, got = 0;
    std::vector<std::uint8_t> small(4);
    Check(gc.RetrieveMessage(&type, small.data(), 4, &got) == GCResult::BufferTooSmall && got == size,
          "buffer too small reports size");
    std::vector<std::uint8_t> buffer(size);
    Check(gc.RetrieveMessage(&type, buffer.data(), size, &got) == GCResult::OK && got == size, "retrieve");
    Check(type == (gc_msg::EGCBaseClientMsg::k_EMsgGCClientWelcome | ProtobufMask), "welcome type carries the protobuf flag");
    FrameView frame;
    Check(ReadProtobufFrame(type, buffer, frame) == FrameError::None, "welcome frame");
    const auto welcome = DecodeClientWelcome(frame.body);
    Check(welcome && welcome->version == 5 && welcome->outOfDateCaches.size() == 1, "welcome content");
    Check(welcome->outOfDateCaches[0].owner.id == 1234 && welcome->outOfDateCaches[0].version == 77 &&
              welcome->outOfDateCaches[0].types.size() == 1 && welcome->outOfDateCaches[0].types[0].objects.size() == 1,
          "welcome carries configured cache");
    Check(!gc.IsMessageAvailable(&size), "queue drained");

    // Bad input never produces a reply and never mutates state beyond the counter.
    Check(send(gc_msg::EGCBaseClientMsg::k_EMsgGCClientHello, Bytes({0x08})) == GCResult::OK && !gc.IsMessageAvailable(&size) &&
              gc.IgnoredMessages() == 1, "malformed hello gets no welcome");
    Check(gc.SendMessage(5, nullptr, 0) == GCResult::InvalidMessage, "empty non-protobuf");
    Check(gc.SendMessage(4006 | ProtobufMask, nullptr, 8) == GCResult::InvalidMessage, "null with size");
    std::vector<std::uint8_t> raw;
    WriteProtobufFrame(4006, {}, {}, raw);
    Check(gc.SendMessage(4007 | ProtobufMask, raw.data(), static_cast<std::uint32_t>(raw.size())) == GCResult::InvalidMessage,
          "type mismatch");
    Check(gc.SendMessage(4006, raw.data(), static_cast<std::uint32_t>(raw.size())) == GCResult::InvalidMessage, "missing flag");
    Check(gc.SendMessage(4006 | ProtobufMask, raw.data(), 3) == GCResult::InvalidMessage, "truncated frame");
    Check(!gc.IsMessageAvailable(&size), "rejected messages queue nothing");

    // Unknown types are accepted, counted and unanswered; custom handlers can reply.
    Check(send(9999, {}) == GCResult::OK && gc.IgnoredMessages() == 2, "unknown message ignored");
    gc.SetHandler(9999, [](const FrameView &, LocalGameCoordinator &g) { g.Reply(9998, Bytes({1, 2})); });
    Check(send(9999, {}) == GCResult::OK && gc.IsMessageAvailable(&size), "custom handler replies");
    gc.RetrieveMessage(&type, buffer.data(), static_cast<std::uint32_t>(buffer.size()), &got);
    Check(type == (9998 | ProtobufMask) && got == 10, "custom reply framing");
    Check(!gc.Reply(0, {}), "invalid reply type rejected");

    // A later hello uses the owner set after construction.
    gc.SetOwner({1, 4321});
    Check(send(gc_msg::EGCBaseClientMsg::k_EMsgGCClientHello, EncodeClientHello(hello)) == GCResult::OK &&
              gc.IsMessageAvailable(&size), "second hello answered");
    std::vector<std::uint8_t> second(size);
    gc.RetrieveMessage(&type, second.data(), size, &got);
    FrameView secondFrame;
    Check(ReadProtobufFrame(type, second, secondFrame) == FrameError::None &&
              DecodeClientWelcome(secondFrame.body)->outOfDateCaches[0].owner.id == 4321, "owner updated");
}

void ProtobufDump()
{
    const auto has = [](const std::string &text, const char *part) { return text.find(part) != std::string::npos; };

    PbWriter inner;
    inner.Varint(1, 7);
    inner.String(2, "hello");
    PbWriter w;
    w.Varint(1, 150);
    w.Message(2, inner);
    w.Bytes(3, Bytes({0x00, 0xFF, 0x80}));
    w.Fixed64(4, 5);
    w.Fixed32(5, 9);
    w.Bytes(6, {});
    const std::string text = DumpProtobuf(w.bytes());
    Check(has(text, "1: varint 150\n") && has(text, "2: message {\n  1: varint 7\n  2: text \"hello\"\n}\n"), "nested and text");
    Check(has(text, "3: bytes[3] 00 ff 80") && has(text, "4: fixed64 0x0000000000000005") &&
              has(text, "5: fixed32 0x00000009") && has(text, "6: bytes[0]"), "scalars and bytes");

    // SteamID64-shaped values never appear in the output, in any wire type.
    constexpr std::uint64_t Id = 0x0110000100000000ull + 123456789;
    PbWriter ids;
    ids.Fixed64(1, Id);
    ids.Varint(2, Id);
    PbWriter nestedId;
    nestedId.Fixed64(1, Id);
    ids.Message(3, nestedId);
    const std::string redacted = DumpProtobuf(ids.bytes());
    Check(!has(redacted, "0110000") && !has(redacted, std::to_string(Id).c_str()) &&
              !has(redacted, "123456789") && has(redacted, "<id redacted>"), "steam ids redacted");

    PbWriter textId;
    textId.String(1, "id=76561198012345678");
    Check(!has(DumpProtobuf(textId.bytes()), "7656119") && has(DumpProtobuf(textId.bytes()), "<steamid redacted>"),
          "decimal steam id text redacted");
    Check(has(DumpProtobuf(Bytes({0x08})), "<malformed protobuf"), "malformed input is reported, not crashed on");
    Check(DumpProtobuf({}).empty(), "empty message");

    // Deep nesting and huge inputs stay bounded.
    std::vector<std::uint8_t> deep = Bytes({0x08, 0x01});
    for (int i = 0; i < 50; ++i)
    {
        PbWriter layer;
        layer.Bytes(1, deep);
        deep = layer.bytes();
    }
    Check(!DumpProtobuf(deep).empty(), "deep nesting bounded");
    PbWriter many;
    for (int i = 0; i < 5000; ++i)
        many.Varint(1, i);
    const std::string capped = DumpProtobuf(many.bytes(), 1000);
    Check(capped.size() < 1100 && has(capped, "<output truncated>"), "output capped");

    Check(HexPreview(Bytes({1, 0xAB})) == "01 ab" && has(HexPreview(std::vector<std::uint8_t>(100, 1), 4), "(100 bytes)"),
          "hex preview");
}

void ProxySupport()
{
    Check(QuoteWindowsArgument(L"") == L"\"\"" &&
          QuoteWindowsArgument(L"C:\\Program Files\\CS2\\") == L"\"C:\\Program Files\\CS2\\\\\"" &&
          QuoteWindowsArgument(L"a\"b") == L"\"a\\\"b\"", "background command safely quotes spaces, trailing slashes and quotes");
    Check(ParseGameplayConfig("rewards_auto_start=0")->rewards_auto_start == 0 &&
          !ParseGameplayConfig("rewards_auto_start=2"), "automatic rewards setting accepts only a boolean");
    Check(CommandLineHasArgument("cs2.exe -insecure", "-insecure"), "flag present");
    Check(CommandLineHasArgument("\"C:\\Program Files\\cs2.exe\" -novid -INSECURE +map de_dust2", "-insecure"), "case-insensitive, quoted path");
    Check(CommandLineHasArgument("cs2.exe\t-insecure\r\n", "-insecure"), "tab and newline separators");
    Check(!CommandLineHasArgument("cs2.exe", "-insecure") && !CommandLineHasArgument("", "-insecure"), "flag absent");
    Check(!CommandLineHasArgument("cs2.exe -insecure2", "-insecure") && !CommandLineHasArgument("cs2.exe --insecure", "-insecure") &&
              !CommandLineHasArgument("cs2.exe -notinsecure", "-insecure"), "whole token only");
    Check(!CommandLineHasArgument("cs2.exe \"-insecure foo\"", "-insecure"), "quoted text is one token");
    Check(!CommandLineHasArgument("C:\\games\\-insecure\\cs2.exe -novid", "-insecure"), "path text is not a flag");

    // Real thunks read from the target steam_api64.dll (SteamAPI_ISteamClient_*).
    const auto thunk = [](std::initializer_list<int> bytes) { return DecodeVtableThunkOffset(Bytes(bytes)); };
    Check(thunk({0x48, 0x8b, 0x01, 0x48, 0xff, 0x60, 0x60, 0xcc, 0xcc}) == 0x60u, "GetISteamGenericInterface disp8");
    Check(thunk({0x48, 0x8b, 0x01, 0x48, 0xff, 0x20, 0xcc, 0xcc, 0xcc}) == 0u, "slot zero");
    Check(thunk({0x48, 0x8b, 0x01, 0x48, 0xff, 0xa0, 0x10, 0x01, 0x00, 0x00}) == 0x110u, "disp32");
    Check(!thunk({0x48, 0x8b, 0x01, 0x48, 0xff, 0x60, 0xf8, 0xcc}) && !thunk({0x48, 0x8b, 0x01, 0x48, 0xff, 0x60, 0x61, 0xcc}) &&
              !thunk({0x48, 0x8b, 0x01, 0x48, 0xff, 0xa0, 0x00, 0x00, 0x10, 0x00}) &&
              !thunk({0x48, 0x8b, 0x01, 0x48, 0xff, 0xa0, 0x10, 0x01}) && !thunk({0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90}) &&
              !thunk({0x48, 0x8b, 0x01, 0x48, 0xff, 0xe0, 0x00}) && !thunk({}) && !thunk({0x48, 0x8b, 0x01}),
          "unrecognised, negative, unaligned, huge or short thunks rejected");

    const auto config = ParseProxyConfig("# comment\n steam_id = 76561198000000000 \nwelcome_version=3 # trailing\r\nowner_type=1\ncache_version=9\n");
    Check(config && config->steamId == 76561198000000000ull && config->welcomeVersion == 3 && config->ownerType == 1 &&
              config->cacheVersion == 9, "config values");
    Check(ParseProxyConfig("mode = capture")->mode == ProxyMode::Capture && ParseProxyConfig("mode=local")->mode == ProxyMode::Local &&
              ParseProxyConfig("")->mode == ProxyMode::Local && !ParseProxyConfig("mode=Capture") && !ParseProxyConfig("mode=") &&
              !ParseProxyConfig("mode=capture extra"), "mode setting is strict");
    Check(ParseProxyConfig("")->hideRealItems && ParseProxyConfig("real_items = hide")->hideRealItems &&
              !ParseProxyConfig("real_items=keep")->hideRealItems && !ParseProxyConfig("real_items=yes") && !ParseProxyConfig("real_items="),
          "real_items setting: fresh inventory by default, strict values");
    Check(ParseProxyConfig("armory_credits = 25")->armoryCredits == 25u && !ParseProxyConfig("")->armoryCredits &&
              ParseProxyConfig("armory_credits=0")->armoryCredits == 0u && !ParseProxyConfig("armory_credits=-1") &&
              !ParseProxyConfig("armory_credits=1000001") && !ParseProxyConfig("armory_credits=x"), "armory_credits setting");
    const auto defaults = ParseProxyConfig("");
    Check(defaults && defaults->steamId == 0 && defaults->ownerType == 1 && defaults->cacheVersion == 1, "defaults");
    for (const char *bad : {"steam_id=abc", "steam_id=", "steam_id=12x", "steam_id=-1", "welcome_version=4294967296",
                            "owner_type=99999999999", "steamid=1", "nonsense", "=5", "steam_id=1 2"})
        Check(!ParseProxyConfig(bad), bad);
}

void SoSummaries()
{
    const auto has = [](const std::string &text, const char *part) { return text.find(part) != std::string::npos; };

    // Extra redaction of the local account's values, without touching small counters.
    PbWriter account;
    account.Varint(1, 123456789);
    account.Fixed32(2, 123456789);
    account.Fixed64(3, 123456789);
    account.Varint(4, 12345);
    DumpOptions options;
    options.redact = {123456789, 12345};
    const std::string dump = DumpProtobuf(account.bytes(), options);
    Check(!has(dump, "123456789") && !has(dump, "0x075bcd15") && has(dump, "4: varint 12345"), "account values redacted, small values kept");
    Check(has(DumpProtobuf(account.bytes()), "1: varint 123456789"), "no redaction without options");

    // Object messages round trip through the decoders.
    PbWriter owner;
    owner.Varint(1, 1);
    owner.Varint(2, 99);
    PbWriter single;
    single.Varint(2, 7);
    single.Bytes(3, Bytes({1, 2, 3}));
    single.Fixed64(4, 5);
    single.Message(5, owner);
    const auto decodedSingle = DecodeSoSingleObject(single.bytes());
    Check(decodedSingle && decodedSingle->typeId == 7 && decodedSingle->data == Bytes({1, 2, 3}) && decodedSingle->version == 5 &&
              decodedSingle->owner.id == 99, "single object decode");
    PbWriter objectA, objectB, multi;
    objectA.Varint(1, 1);
    objectA.Bytes(2, Bytes({9}));
    objectB.Varint(1, 2);
    objectB.Bytes(2, Bytes({8, 8}));
    multi.Message(2, objectA);
    multi.Message(2, objectB);
    multi.Fixed64(3, 6);
    multi.Message(6, owner);
    const auto decodedMulti = DecodeSoMultipleObjects(multi.bytes());
    Check(decodedMulti && decodedMulti->objects.size() == 2 && decodedMulti->objects[1].data == Bytes({8, 8}) &&
              decodedMulti->owner.type == 1, "multiple objects decode");
    Check(!DecodeSoSingleObject(Bytes({0x10})) && !DecodeSoMultipleObjects(Bytes({0x12, 0x05, 1})), "malformed object messages rejected");
    PbWriter wrongWire;
    wrongWire.Varint(3, 1);
    Check(!DecodeSoSingleObject(wrongWire.bytes()), "wrong wire type rejected");

    // A welcome with 3 items and 1 persona object summarises to counts and one sample each.
    PbWriter item;
    item.Varint(1, 4242);
    item.Varint(2, 123456789); // the local account id inside an object
    ClientWelcome welcome;
    welcome.outOfDateCaches.push_back({{1, 76561190000000000ull + 123456789}, 3,
                                       {{1, {item.bytes(), item.bytes(), item.bytes()}}, {2, {Bytes({0x08, 0x01})}}}});
    DumpOptions secret;
    secret.redact = {123456789};
    const std::string summary = SummarizeSoMessage(gc_msg::EGCBaseClientMsg::k_EMsgGCClientWelcome, EncodeClientWelcome(welcome), secret);
    Check(has(summary, "object type_id=1 count=3") && has(summary, "object type_id=2 count=1") && has(summary, "1: varint 4242"),
          "welcome summary counts and samples");
    Check(!has(summary, "123456789") && has(summary, "<id redacted>"), "summary redacts account values inside objects");

    const std::string update = SummarizeSoMessage(gc_msg::ESOMsg::k_ESOMsg_UpdateMultiple, multi.bytes(), secret);
    Check(has(update, "type_id=1 count=1") && has(update, "type_id=2 count=1"), "update multiple summary");
    Check(has(SummarizeSoMessage(gc_msg::ESOMsg::k_ESOMsg_Update, single.bytes(), secret), "type_id=7"), "single object summary");
    Check(SummarizeSoMessage(9999, single.bytes(), secret).empty() && SummarizeSoMessage(gc_msg::ESOMsg::k_ESOMsg_Update, Bytes({0x10}), secret).empty(),
          "unrelated or undecodable messages produce no summary");
}

void Replay()
{
    const auto dir = std::filesystem::temp_directory_path() / "cs2_gc_replay_test";
    std::filesystem::remove_all(dir);

    Check(ReplayStore::LoadDirectory(dir).Size() == 0, "missing directory loads empty");
    Check(ReplayStore::SaveIfMissing(dir, 4004, Bytes({1, 2, 3})), "first save");
    Check(!ReplayStore::SaveIfMissing(dir, 4004, Bytes({9, 9})), "an existing recording is never replaced");
    Check(ReplayStore::SaveIfMissing(dir, 9194, Bytes({})), "empty body is a valid recording");
    Check(!ReplayStore::SaveIfMissing(dir, 0, Bytes({1})) &&
              !ReplayStore::SaveIfMissing(dir, 5, std::vector<std::uint8_t>(ReplayStore::MaxBodyBytes + 1)), "bad id and oversize body refused");
    Check(!std::filesystem::exists(dir / "4004.bin.tmp"), "no temporary file left behind");

    // Hand-made junk next to real recordings is ignored.
    std::ofstream(dir / "notes.txt") << "x";
    std::ofstream(dir / "abc.bin") << "x";
    std::ofstream(dir / "12x.bin") << "x";
    std::ofstream(dir / "4294967296.bin") << "x";
    std::ofstream(dir / "0.bin") << "x";
    std::ofstream(dir / ".bin") << "x";
    const ReplayStore loaded = ReplayStore::LoadDirectory(dir);
    Check(loaded.Size() == 2 && *loaded.Find(4004) == Bytes({1, 2, 3}) && loaded.Find(9194)->empty() && !loaded.Find(1), "load ignores junk");

    // The number of recordings is bounded.
    std::filesystem::remove_all(dir);
    for (std::uint32_t id = 1; id <= ReplayStore::MaxFiles; ++id)
        Check(ReplayStore::SaveIfMissing(dir, id, Bytes({1})), "fill to the limit");
    Check(!ReplayStore::SaveIfMissing(dir, 1000, Bytes({1})) && ReplayStore::LoadDirectory(dir).Size() == ReplayStore::MaxFiles, "recording count capped");
    std::filesystem::remove_all(dir);

    // Endpoint behaviour with recordings.
    namespace m = gc_msg;
    auto store = std::make_shared<ReplayStore>();
    store->Set(m::EGCBaseClientMsg::k_EMsgGCClientWelcome, Bytes({0x08, 0x2A}));
    store->Set(m::ECsgoGCMsg::k_EMsgGCCStrike15_v2_GC2ClientGlobalStats, Bytes({0x70, 0x01}));
    store->Set(m::ECsgoGCMsg::k_EMsgGCCStrike15_v2_ClientGCRankUpdate, Bytes({0x0A, 0x00}));
    store->Set(m::ECsgoGCMsg::k_EMsgGCCStrike15_v2_RecurringMissionSchema, Bytes({0x0A, 0x01, 0x77}));

    LocalGameCoordinator gc(GcEndpointConfig{});
    gc.EnableReplay(store);
    const auto send = [&](std::uint32_t type, const std::vector<std::uint8_t> &body) {
        std::vector<std::uint8_t> frame;
        WriteProtobufFrame(type, {}, body, frame);
        return gc.SendMessage(type | ProtobufMask, frame.data(), static_cast<std::uint32_t>(frame.size()));
    };
    const auto next = [&](std::uint32_t &type) {
        std::uint32_t size = 0;
        std::vector<std::uint8_t> out;
        if (!gc.IsMessageAvailable(&size))
            return out;
        std::vector<std::uint8_t> buffer(size);
        std::uint32_t got = 0;
        gc.RetrieveMessage(&type, buffer.data(), size, &got);
        FrameView frame;
        ReadProtobufFrame(type, buffer, frame);
        return std::vector<std::uint8_t>(frame.body.begin(), frame.body.end());
    };

    ClientHello hello;
    hello.version = 1;
    Check(send(m::EGCBaseClientMsg::k_EMsgGCClientHello, EncodeClientHello(hello)) == GCResult::OK, "hello");
    std::uint32_t type = 0;
    Check(next(type) == Bytes({0x08, 0x2A}) && type == (m::EGCBaseClientMsg::k_EMsgGCClientWelcome | ProtobufMask), "recorded welcome replayed verbatim");
    Check(next(type) == Bytes({0x70, 0x01}) && type == (m::ECsgoGCMsg::k_EMsgGCCStrike15_v2_GC2ClientGlobalStats | ProtobufMask), "post-welcome stats");
    Check(next(type) == Bytes({0x0A, 0x00}) && type == (m::ECsgoGCMsg::k_EMsgGCCStrike15_v2_ClientGCRankUpdate | ProtobufMask), "post-welcome rank update");
    std::uint32_t size = 0;
    Check(!gc.IsMessageAvailable(&size), "nothing else queued");

    Check(send(m::ECsgoGCMsg::k_EMsgGCCStrike15_v2_RequestRecurringMissionSchedule, {}) == GCResult::OK &&
              next(type) == Bytes({0x0A, 0x01, 0x77}) &&
              type == (m::ECsgoGCMsg::k_EMsgGCCStrike15_v2_RecurringMissionSchema | ProtobufMask), "recorded reply to a request");
    Check(send(m::ECsgoGCMsg::k_EMsgGCCStrike15_v2_ClientGCRankUpdate, {}) == GCResult::OK && next(type) == Bytes({0x0A, 0x00}),
          "rank request answered");
    // No recording for the store pair, so that request stays ignored, as before replay existed.
    const std::size_t ignoredBefore = gc.IgnoredMessages();
    Check(send(m::EGCItemMsg::k_EMsgGCStoreGetUserData, {}) == GCResult::OK && !gc.IsMessageAvailable(&size) &&
              gc.IgnoredMessages() == ignoredBefore + 1, "request without a recorded reply is unchanged");

    // Without a recorded welcome the synthetic one is still used and nothing extra is sent.
    LocalGameCoordinator plain(GcEndpointConfig{});
    plain.EnableReplay(std::make_shared<ReplayStore>());
    std::vector<std::uint8_t> frame;
    WriteProtobufFrame(m::EGCBaseClientMsg::k_EMsgGCClientHello, {}, EncodeClientHello(hello), frame);
    plain.SendMessage(m::EGCBaseClientMsg::k_EMsgGCClientHello | ProtobufMask, frame.data(), static_cast<std::uint32_t>(frame.size()));
    std::uint32_t plainType = 0, plainSize = 0, plainGot = 0;
    Check(plain.IsMessageAvailable(&plainSize), "synthetic welcome still sent");
    std::vector<std::uint8_t> plainBuffer(plainSize);
    plain.RetrieveMessage(&plainType, plainBuffer.data(), plainSize, &plainGot);
    FrameView plainFrame;
    ReadProtobufFrame(plainType, plainBuffer, plainFrame);
    Check(DecodeClientWelcome(plainFrame.body) && !plain.IsMessageAvailable(&plainSize), "synthetic welcome decodes, nothing follows");
    plain.EnableReplay(nullptr); // clearing is allowed
}

void WelcomeOtherFields()
{
    const auto has = [](const std::string &text, const char *part) { return text.find(part) != std::string::npos; };
    PbWriter gameData;
    gameData.Varint(5, 77);
    PbWriter welcomeBody;
    welcomeBody.Varint(1, 3);
    welcomeBody.Bytes(2, gameData.bytes());
    PbWriter cacheOwner;
    cacheOwner.Varint(1, 1);
    cacheOwner.Varint(2, 555);
    PbWriter cache;
    cache.Fixed64(3, 9);
    cache.Message(4, cacheOwner);
    welcomeBody.Message(3, cache);
    welcomeBody.String(10, "https://example.invalid/balance");
    const std::string summary = SummarizeSoMessage(gc_msg::EGCBaseClientMsg::k_EMsgGCClientWelcome, welcomeBody.bytes(), DumpOptions{});
    Check(has(summary, "other welcome fields:") && has(summary, "1: varint 3") && has(summary, "5: varint 77") &&
              has(summary, "10: text \"https://example.invalid/balance\""), "non-cache welcome fields are shown");
    Check(!has(summary, "3: message"), "the cache itself is not repeated in the other fields");
}

// Reads a CSOEconItem back into its parts, independently of the encoder.
struct DecodedItem
{
    std::uint64_t id{};
    std::uint32_t account{}, inventory{}, defIndex{}, quality{}, rarity{};
    std::map<std::uint32_t, std::uint32_t> floatBits; // attribute def index -> value_bytes as LE uint32
    bool ok{true};
};

DecodedItem DecodeItem(const std::vector<std::uint8_t> &bytes)
{
    DecodedItem item;
    PbReader reader(bytes);
    PbField f;
    while (reader.Next(f))
    {
        switch (f.number)
        {
        case 1: item.id = f.value; break;
        case 2: item.account = static_cast<std::uint32_t>(f.value); break;
        case 3: item.inventory = static_cast<std::uint32_t>(f.value); break;
        case 4: item.defIndex = static_cast<std::uint32_t>(f.value); break;
        case 7: item.quality = static_cast<std::uint32_t>(f.value); break;
        case 19: item.rarity = static_cast<std::uint32_t>(f.value); break;
        case 12:
        {
            PbReader inner(f.bytes);
            PbField g;
            std::uint32_t def = 0;
            while (inner.Next(g))
            {
                if (g.number == 1)
                    def = static_cast<std::uint32_t>(g.value);
                else if (g.number == 3 && g.bytes.size() == 4)
                    item.floatBits[def] = std::uint32_t{g.bytes[0]} | (std::uint32_t{g.bytes[1]} << 8) |
                                          (std::uint32_t{g.bytes[2]} << 16) | (std::uint32_t{g.bytes[3]} << 24);
                else
                    item.ok = false;
            }
            break;
        }
        default: item.ok = false; break;
        }
    }
    item.ok = item.ok && !reader.Failed();
    return item;
}

float AsFloat(std::uint32_t bits)
{
    float value;
    std::memcpy(&value, &bits, sizeof value);
    return value;
}

void EconItems()
{
    InventoryItem skin{0, 7, 282, 0.15f, 661, false, 4};
    const auto bytes = BuildEconItem(skin, 123456, 1000000000005ull, 1002);
    const DecodedItem item = DecodeItem(bytes);
    Check(item.ok && item.id == 1000000000005ull && item.account == 123456 && item.inventory == 1002 && item.defIndex == 7 &&
              item.quality == QualityUnique && item.rarity == 4, "item fields");
    Check(AsFloat(item.floatBits.at(AttributePaintIndex)) == 282.0f && AsFloat(item.floatBits.at(AttributePaintSeed)) == 661.0f &&
              AsFloat(item.floatBits.at(AttributePaintWear)) == 0.15f && item.floatBits.size() == 3, "paint attributes are floats");
    skin.statTrak = true;
    const auto tracked = DecodeItem(BuildEconItem(skin, 1, 2, 3));
    Check(tracked.ok && tracked.quality == QualityStrange && tracked.floatBits.at(AttributeKillEater) == 0 &&
              tracked.floatBits.at(AttributeKillEaterScoreType) == 0,
          "StatTrak skins advertise their quality and integer counter attributes to the client");
    InventoryItem plain{0, 4001, 0, 0.0f, 1, false, 0};
    const DecodedItem noPaint = DecodeItem(BuildEconItem(plain, 1, 2, 3));
    Check(noPaint.ok && noPaint.floatBits.empty() && noPaint.rarity == 0, "no paint attributes or rarity for a plain item");

    // Welcome patching: every other field survives, in order, and only the item type grows.
    PbWriter owner;
    owner.Varint(1, 1);
    owner.Varint(2, 99);
    const auto existing = Bytes({0x08, 0x01});
    PbWriter itemType;
    itemType.Varint(1, 1);
    itemType.Bytes(2, existing);
    PbWriter otherType;
    otherType.Varint(1, 7);
    otherType.Bytes(2, Bytes({0x08, 0x05}));
    PbWriter cache;
    cache.Message(2, otherType);
    cache.Message(2, itemType);
    cache.Fixed64(3, 77);
    cache.Message(4, owner);
    cache.Varint(15, 12345); // unknown to the patcher; must survive
    PbWriter welcome;
    welcome.Varint(1, 0);
    welcome.Bytes(2, Bytes({0x28, 0x03})); // game data
    welcome.Message(3, cache);
    welcome.String(11, "XX");

    const std::vector<std::vector<std::uint8_t>> extra{bytes, BuildEconItem(plain, 1, 2, 3)};
    const auto patched = AppendItemsToWelcome(welcome.bytes(), extra);
    Check(patched.has_value(), "welcome patched");
    const auto decoded = DecodeClientWelcome(*patched);
    Check(decoded && decoded->version == 0 && decoded->outOfDateCaches.size() == 1, "patched welcome decodes");
    const SoCacheSubscribed &patchedCache = decoded->outOfDateCaches[0];
    Check(patchedCache.types.size() == 2 && patchedCache.types[0].typeId == 7 && patchedCache.types[0].objects.size() == 1, "other type untouched");
    Check(patchedCache.types[1].typeId == 1 && patchedCache.types[1].objects.size() == 3 && patchedCache.types[1].objects[0] == existing &&
              patchedCache.types[1].objects[1] == bytes, "items appended after the existing ones");
    Check(patchedCache.owner.id == 99 && patchedCache.version == 77, "owner and version preserved");

    // Byte-level: removing the appended items must give back the original bytes exactly.
    const auto unpatched = AppendItemsToWelcome(welcome.bytes(), {});
    Check(unpatched && *unpatched == welcome.bytes(), "patching with no items reproduces the welcome byte for byte");
    PbReader fieldReader(*patched);
    PbField field;
    std::vector<std::uint32_t> order;
    while (fieldReader.Next(field))
        order.push_back(field.number);
    Check(order == std::vector<std::uint32_t>({1, 2, 3, 11}), "top-level field order preserved");

    // A cache without an item type gets one; malformed or cache-less welcomes are refused.
    PbWriter bareCache;
    bareCache.Fixed64(3, 1);
    bareCache.Message(4, owner);
    PbWriter bareWelcome;
    bareWelcome.Message(3, bareCache);
    const auto created = DecodeClientWelcome(*AppendItemsToWelcome(bareWelcome.bytes(), extra));
    Check(created && created->outOfDateCaches[0].types.size() == 1 && created->outOfDateCaches[0].types[0].typeId == 1 &&
              created->outOfDateCaches[0].types[0].objects.size() == 2, "item type created when missing");
    PbWriter noCache;
    noCache.Varint(1, 5);
    Check(!AppendItemsToWelcome(noCache.bytes(), extra) && !AppendItemsToWelcome(Bytes({0x1A, 0x09, 1}), extra) &&
              !AppendItemsToWelcome(Bytes({0x08}), extra), "no cache, truncated or malformed welcome refused");
    for (std::size_t n = 0; n < welcome.bytes().size(); ++n)
        AppendItemsToWelcome(std::span(welcome.bytes()).first(n), extra); // never crashes on a prefix

    // The endpoint applies the provider to a replayed welcome, and survives a bad recording.
    auto store = std::make_shared<ReplayStore>();
    store->Set(gc_msg::EGCBaseClientMsg::k_EMsgGCClientWelcome, welcome.bytes());
    GcEndpointConfig config;
    config.owner = {1, 99};
    LocalGameCoordinator gc(config);
    gc.EnableReplay(store);
    std::uint64_t askedFor = 0;
    gc.SetItemProvider([&](std::uint64_t steamId) {
        askedFor = steamId;
        return extra;
    });
    ClientHello hello;
    std::vector<std::uint8_t> frame;
    WriteProtobufFrame(gc_msg::EGCBaseClientMsg::k_EMsgGCClientHello, {}, EncodeClientHello(hello), frame);
    gc.SendMessage(gc_msg::EGCBaseClientMsg::k_EMsgGCClientHello | ProtobufMask, frame.data(), static_cast<std::uint32_t>(frame.size()));
    std::uint32_t size = 0, type = 0, got = 0;
    Check(gc.IsMessageAvailable(&size), "welcome queued");
    std::vector<std::uint8_t> out(size);
    gc.RetrieveMessage(&type, out.data(), size, &got);
    FrameView outFrame;
    ReadProtobufFrame(type, out, outFrame);
    const auto sent = DecodeClientWelcome(outFrame.body);
    Check(askedFor == 99 && sent && sent->outOfDateCaches[0].types[1].objects.size() == 3, "endpoint added the provided items");

    auto broken = std::make_shared<ReplayStore>();
    broken->Set(gc_msg::EGCBaseClientMsg::k_EMsgGCClientWelcome, Bytes({0x08, 0x01})); // valid protobuf, no cache
    LocalGameCoordinator gc2(config);
    gc2.EnableReplay(broken);
    gc2.SetItemProvider([&](std::uint64_t) { return extra; });
    gc2.SendMessage(gc_msg::EGCBaseClientMsg::k_EMsgGCClientHello | ProtobufMask, frame.data(), static_cast<std::uint32_t>(frame.size()));
    Check(gc2.PatchFailures() == 1 && gc2.IsMessageAvailable(&size), "unpatchable welcome is sent as recorded and counted");
}

void InventoryRarity()
{
    Inventory inventory;
    inventory.Add({0, 7, 282, 0.15f, 661, false, 4});
    const auto back = Inventory::FromText(inventory.ToText());
    Check(back && back->Items()[0].rarity == 4, "rarity round trip");
    // Files written before the field existed still load, with rarity zero.
    std::string text = inventory.ToText();
    const std::size_t at = text.find("\t\t\t\"rarity\"");
    text.erase(at, text.find('\n', at) - at + 1);
    const auto old = Inventory::FromText(text);
    Check(old && old->Items()[0].rarity == 0, "older files without rarity load");
    text = inventory.ToText();
    text.replace(text.find("\"rarity\"\t\"4\""), 12, "\"rarity\"\t\"100\"");
    Check(!Inventory::FromText(text), "out of range rarity rejected");
}

void SummaryDiversityAndLocation()
{
    const auto has = [](const std::string &text, const char *part) { return text.find(part) != std::string::npos; };
    // Items of different shape each get a sample; identical shapes share one.
    const auto skin = BuildEconItem({0, 7, 282, 0.15f, 661, false, 4}, 1, 11, 1);
    const auto skin2 = BuildEconItem({0, 9, 801, 0.30f, 5, false, 5}, 1, 12, 2);
    const auto crate = BuildEconItem({0, 4001, 0, 0.0f, 1, false, 0}, 1, 13, 3);
    SoCacheSubscribed cache;
    cache.owner = {1, 9};
    cache.types.push_back({1, {skin, skin2, crate}});
    PbWriter locationInner;
    locationInner.Fixed32(1, 0xc217418b);
    locationInner.Fixed32(2, 0x4310f692);
    locationInner.String(3, "AU");
    ClientWelcome welcome;
    welcome.outOfDateCaches.push_back(cache);
    auto raw = EncodeClientWelcome(welcome);
    PbWriter withLocation;
    withLocation.Varint(1, 0);
    withLocation.Message(5, locationInner);
    withLocation.Varint(7, 1792458960);
    std::vector<std::uint8_t> combined = raw;
    combined.insert(combined.end(), withLocation.bytes().begin(), withLocation.bytes().end());
    const std::string summary = SummarizeSoMessage(gc_msg::EGCBaseClientMsg::k_EMsgGCClientWelcome, combined, DumpOptions{});
    Check(has(summary, "object type_id=1 count=3") && has(summary, "sample 1") && has(summary, "sample 2"), "distinct shapes sampled");
    Check(!has(summary, "sample 3"), "same-shaped items share a sample"); // the two skins have the same shape
    Check(has(summary, "other welcome fields") && has(summary, "5: <location redacted>") && !has(summary, "0xc217418b") &&
              !has(summary, "\"AU\"") && has(summary, "7: varint 1792458960"), "location redacted, other fields kept");
}

void SkinRarityAndFreshInventory()
{
    // Synthetic schema: rarities, a weapon base rarity through a prefab, and finish rarities.
    const auto schema = Schema::Load(R"("items_game"
    {
        "rarities" { "common" { "value" "1" } "uncommon" { "value" "2" } "mythical" { "value" "4" }
                     "legendary" { "value" "5" } "ancient" { "value" "6" } }
        "prefabs" { "rifle" { "item_rarity" "uncommon" } "smg" { "item_rarity" "common" } }
        "items" { "7" { "name" "weapon_rifle" "prefab" "rifle" } "34" { "name" "weapon_smg" "prefab" "smg" }
                  "99" { "name" "weapon_bare" } }
        "paint_kits" { "10" { "name" "k_mythical" } "11" { "name" "k_legendary" } "12" { "name" "k_ancient" }
                       "13" { "name" "k_unrated" } }
        "paint_kits_rarity" { "k_mythical" "mythical" "k_legendary" "legendary" "k_ancient" "ancient" }
    })");
    Check(schema.has_value(), "rarity fixture loads");
    Check(schema->SkinRarity(7, 10) == 5u && schema->SkinRarity(7, 11) == 6u, "finish + weapon - 1");
    Check(schema->SkinRarity(7, 12) == 6u, "capped at Covert");
    Check(schema->SkinRarity(34, 10) == 4u, "a common-base weapon keeps the finish rarity");
    Check(!schema->SkinRarity(99, 10) && !schema->SkinRarity(7, 13) && !schema->SkinRarity(7, 999) && !schema->SkinRarity(123, 10),
          "missing weapon rarity, finish rarity, finish or weapon gives nothing");

    // A fresh inventory: the item objects of the recording are removed, everything else stays.
    PbWriter owner;
    owner.Varint(1, 1);
    owner.Varint(2, 99);
    PbWriter itemType;
    itemType.Varint(1, 1);
    itemType.Bytes(2, Bytes({0x08, 0x01}));
    itemType.Bytes(2, Bytes({0x08, 0x02}));
    PbWriter otherType;
    otherType.Varint(1, 7);
    otherType.Bytes(2, Bytes({0x08, 0x05}));
    PbWriter cache;
    cache.Message(2, itemType);
    cache.Message(2, otherType);
    cache.Fixed64(3, 77);
    cache.Message(4, owner);
    PbWriter welcome;
    welcome.Varint(1, 0);
    welcome.Message(3, cache);
    welcome.String(11, "XX");

    const std::vector<std::vector<std::uint8_t>> mine{BuildEconItem({0, 7, 282, 0.15f, 661, false, 5}, 1, 1000000000001ull, 1000)};
    const auto fresh = AppendItemsToWelcome(welcome.bytes(), mine, true);
    const auto decoded = fresh ? DecodeClientWelcome(*fresh) : std::nullopt;
    Check(decoded && decoded->outOfDateCaches[0].types.size() == 2, "both object types kept");
    const auto &types = decoded->outOfDateCaches[0].types;
    Check(types[0].typeId == 1 && types[0].objects.size() == 1 && types[0].objects[0] == mine[0], "only our item remains");
    Check(types[1].typeId == 7 && types[1].objects.size() == 1, "other object types untouched");
    Check(decoded->outOfDateCaches[0].owner.id == 99 && decoded->outOfDateCaches[0].version == 77, "owner and version preserved");

    const auto empty = AppendItemsToWelcome(welcome.bytes(), {}, true);
    const auto emptyDecoded = DecodeClientWelcome(*empty);
    Check(emptyDecoded && emptyDecoded->outOfDateCaches[0].types[0].typeId == 1 && emptyDecoded->outOfDateCaches[0].types[0].objects.empty(),
          "no custom items still gives an empty item list");
    const auto keep = AppendItemsToWelcome(welcome.bytes(), mine, false);
    Check(DecodeClientWelcome(*keep)->outOfDateCaches[0].types[0].objects.size() == 3, "keeping the recording adds to it");

    // Through the endpoint: with the drop flag and no provider the recorded items are removed.
    auto store = std::make_shared<ReplayStore>();
    store->Set(gc_msg::EGCBaseClientMsg::k_EMsgGCClientWelcome, welcome.bytes());
    GcEndpointConfig config;
    config.owner = {1, 99};
    LocalGameCoordinator gc(config);
    gc.EnableReplay(store);
    gc.SetDropRecordedItems(true);
    ClientHello hello;
    std::vector<std::uint8_t> frame;
    WriteProtobufFrame(gc_msg::EGCBaseClientMsg::k_EMsgGCClientHello, {}, EncodeClientHello(hello), frame);
    gc.SendMessage(gc_msg::EGCBaseClientMsg::k_EMsgGCClientHello | ProtobufMask, frame.data(), static_cast<std::uint32_t>(frame.size()));
    std::uint32_t size = 0, type = 0, got = 0;
    Check(gc.IsMessageAvailable(&size), "welcome queued");
    std::vector<std::uint8_t> out(size);
    gc.RetrieveMessage(&type, out.data(), size, &got);
    FrameView outFrame;
    ReadProtobufFrame(type, out, outFrame);
    const auto sent = DecodeClientWelcome(outFrame.body);
    Check(sent && sent->outOfDateCaches[0].types[0].objects.empty() && sent->outOfDateCaches[0].types[1].objects.size() == 1 &&
              gc.PatchFailures() == 0, "endpoint sends a fresh inventory");
}

void ArmoryBalance()
{
    // Synthetic XpShop-shaped object: generation time, balance 0, two track ids.
    PbWriter shop;
    shop.Varint(1, 1781273308);
    shop.Varint(2, 0);
    shop.Varint(3, 1361);
    shop.Varint(3, 1362);
    PbWriter shopNoBalance;
    shopNoBalance.Varint(1, 5);
    shopNoBalance.Varint(3, 7);
    PbWriter shopType;
    shopType.Varint(1, XpShopTypeId);
    shopType.Bytes(2, shop.bytes());
    shopType.Bytes(2, shopNoBalance.bytes());
    PbWriter otherType;
    otherType.Varint(1, 4);
    otherType.Bytes(2, Bytes({0x10, 0x07})); // field 2 = 7 here must NOT be changed
    PbWriter owner;
    owner.Varint(1, 1);
    owner.Varint(2, 99);
    PbWriter cache;
    cache.Message(2, otherType);
    cache.Message(2, shopType);
    cache.Fixed64(3, 5);
    cache.Message(4, owner);
    PbWriter welcome;
    welcome.Varint(1, 0);
    welcome.Message(3, cache);
    welcome.String(11, "XX");

    const auto result = SetArmoryBalance(welcome.bytes(), 25);
    const auto decoded = result ? DecodeClientWelcome(*result) : std::nullopt;
    Check(decoded && decoded->outOfDateCaches[0].types.size() == 2, "types preserved");
    const auto &types = decoded->outOfDateCaches[0].types;
    Check(types[0].typeId == 4 && types[0].objects[0] == Bytes({0x10, 0x07}), "other types untouched, even with a field 2");

    const auto object = [&](std::size_t i) {
        std::map<std::uint32_t, std::vector<std::uint64_t>> fields;
        PbReader reader(types[1].objects[i]);
        PbField f;
        while (reader.Next(f))
            fields[f.number].push_back(f.value);
        return fields;
    };
    const auto first = object(0);
    Check(first.at(2) == std::vector<std::uint64_t>{25} && first.at(1) == std::vector<std::uint64_t>{1781273308} &&
              first.at(3) == (std::vector<std::uint64_t>{1361, 1362}), "balance set, other fields and repeated tracks kept");
    const auto second = object(1);
    Check(second.at(2) == std::vector<std::uint64_t>{25} && second.at(1) == std::vector<std::uint64_t>{5}, "missing balance is added");
    Check(decoded->outOfDateCaches[0].owner.id == 99 && decoded->outOfDateCaches[0].version == 5, "owner and version preserved");

    // A welcome without that object type comes back byte for byte; bad input is refused.
    PbWriter plainCache;
    plainCache.Message(2, otherType);
    plainCache.Message(4, owner);
    PbWriter plain;
    plain.Message(3, plainCache);
    Check(SetArmoryBalance(plain.bytes(), 9) == plain.bytes(), "no XpShop object: unchanged");
    PbWriter noCache;
    noCache.Varint(1, 1);
    Check(!SetArmoryBalance(noCache.bytes(), 1) && !SetArmoryBalance(Bytes({0x1A, 0x05, 1}), 1) && !SetArmoryBalance(Bytes({0x08}), 1),
          "no cache or malformed input refused");
    for (std::size_t n = 0; n < welcome.bytes().size(); ++n)
        SetArmoryBalance(std::span(welcome.bytes()).first(n), 3);

    // Through the endpoint, together with the fresh-inventory patch.
    auto store = std::make_shared<ReplayStore>();
    store->Set(gc_msg::EGCBaseClientMsg::k_EMsgGCClientWelcome, welcome.bytes());
    GcEndpointConfig config;
    config.owner = {1, 99};
    LocalGameCoordinator gc(config);
    gc.EnableReplay(store);
    gc.SetDropRecordedItems(true);
    gc.SetArmoryCredits(12);
    ClientHello hello;
    std::vector<std::uint8_t> frame;
    WriteProtobufFrame(gc_msg::EGCBaseClientMsg::k_EMsgGCClientHello, {}, EncodeClientHello(hello), frame);
    gc.SendMessage(gc_msg::EGCBaseClientMsg::k_EMsgGCClientHello | ProtobufMask, frame.data(), static_cast<std::uint32_t>(frame.size()));
    std::uint32_t size = 0, type = 0, got = 0;
    Check(gc.IsMessageAvailable(&size), "welcome queued");
    std::vector<std::uint8_t> out(size);
    gc.RetrieveMessage(&type, out.data(), size, &got);
    FrameView outFrame;
    ReadProtobufFrame(type, out, outFrame);
    const auto sent = DecodeClientWelcome(outFrame.body);
    // types: the two that were there, the created (empty) item type, and the created loadout-slot type
    Check(sent && gc.PatchFailures() == 0 && sent->outOfDateCaches[0].types.size() == 4, "both patches applied without failures");
    // The drop patch created an (empty) item type; the XpShop balance carries the credits.
    bool found = false;
    for (const auto &t : sent->outOfDateCaches[0].types)
        if (t.typeId == static_cast<std::int32_t>(XpShopTypeId))
        {
            PbReader reader(t.objects[0]);
            PbField f;
            while (reader.Next(f))
                found |= f.number == 2 && f.value == 12;
        }
    Check(found, "endpoint sends the configured balance");
}

void LoadoutAndPurchases()
{
    namespace m = gc_msg;
    Inventory inventory;
    inventory.Add({0, 7, 282, 0.15f, 661, false, 5}); // id 1 -> CustomItemIdBase + 1
    const std::uint64_t mine = CustomItemIdBase + 1;
    const std::uint64_t defaultAk = 0xF000000000000007ull;
    LiveInventory live(inventory);

    Check(live.DefinitionOf(mine) == 7u && live.DefinitionOf(defaultAk) == 7u, "own and default items resolve");
    Check(!live.DefinitionOf(CustomItemIdBase + 2) && !live.DefinitionOf(CustomItemIdBase) && !live.DefinitionOf(12345) &&
              !live.DefinitionOf(0xF000000000000000ull), "unknown ids do not");

    AdjustEquipSlots request;
    request.slots = {{2, 14, mine}, {3, 14, defaultAk}};
    request.changeNum = 1;
    const auto changed = live.Adjust(request, 555);
    Check(changed && changed->size() == 2, "equip applied");
    const auto slotFields = [](const std::vector<std::uint8_t> &bytes) {
        std::map<std::uint32_t, std::uint64_t> fields;
        PbReader reader(bytes);
        PbField f;
        while (reader.Next(f))
            fields[f.number] = f.value;
        return fields;
    };
    const auto first = slotFields((*changed)[0]);
    Check(first.at(1) == 555 && first.at(2) == 2 && first.at(3) == 14 && first.at(4) == mine && first.at(5) == 7, "equip slot object");
    Check(live.EncodedSlots(555).size() == 2, "slots remembered");
    const auto equippedSave = Inventory::FromText(live.Items().ToText());
    Check(equippedSave && LiveInventory(*equippedSave).EncodedSlots(555) == live.EncodedSlots(555),
          "team-specific custom and default loadout slots survive a full inventory reload");
    auto removedEquipped = *equippedSave;
    Check(removedEquipped.Remove(1) && removedEquipped.Loadout().size() == 1 &&
              removedEquipped.Loadout()[0].itemId == defaultAk && Inventory::FromText(removedEquipped.ToText()),
          "consuming an equipped custom item removes its saved slot while preserving base weapons");

    // One unknown item rejects the whole request, and nothing changes.
    AdjustEquipSlots bad;
    bad.slots = {{2, 15, mine}, {2, 16, 99999}};
    Check(!live.Adjust(bad, 555) && live.EncodedSlots(555).size() == 2, "unknown item: nothing changes");
    // Clearing a slot empties it; it drops out of the welcome slots.
    AdjustEquipSlots clear;
    clear.slots = {{2, 14, 0}};
    const auto cleared = live.Adjust(clear, 555);
    Check(cleared && slotFields((*cleared)[0]).at(4) == 0 && slotFields((*cleared)[0]).at(5) == 0 && live.EncodedSlots(555).size() == 1,
          "cleared slot");
    const auto clearedSave = Inventory::FromText(live.Items().ToText());
    Check(clearedSave && LiveInventory(*clearedSave).EncodedSlots(555) == live.EncodedSlots(555), "unequipping also survives restart");

    // Message codecs.
    PbWriter slotMsg;
    slotMsg.Varint(1, 2);
    slotMsg.Varint(2, 14);
    slotMsg.Varint(3, mine);
    PbWriter body;
    body.Message(1, slotMsg);
    body.Varint(2, 1);
    const auto decoded = DecodeAdjustEquipSlots(body.bytes());
    Check(decoded && decoded->slots.size() == 1 && decoded->slots[0].itemId == mine && decoded->changeNum == 1, "equip request decode");
    PbWriter wrongWire;
    wrongWire.Fixed64(1, 3);
    Check(!DecodeAdjustEquipSlots(wrongWire.bytes()) && !DecodeAdjustEquipSlots(Bytes({0x0A, 0x09, 1})), "malformed equip request rejected");
    SoMultipleObjects update;
    update.objects.push_back({3, Bytes({1, 2})});
    update.version = 9;
    update.owner = {1, 77};
    const auto roundTrip = DecodeSoMultipleObjects(EncodeSoMultipleObjects(update));
    Check(roundTrip && roundTrip->objects.size() == 1 && roundTrip->objects[0].typeId == 3 && roundTrip->version == 9 && roundTrip->owner.id == 77,
          "SO update round trip");

    // The job id of a request comes back as the target of the reply.
    PbWriter jobHeader;
    jobHeader.Fixed64(10, 8);
    FrameView withJob;
    withJob.header = jobHeader.bytes();
    const auto echoed = ReplyHeaderFor(withJob); // kept alive: the reader only views it
    PbReader headerReader(echoed);
    PbField hf;
    Check(headerReader.Next(hf) && hf.number == 11 && hf.wire == 1 && hf.value == 8, "job id echoed as target");
    Check(ReplyHeaderFor(FrameView{}).empty(), "no job id, no header");

    // Endpoint: equipping answers with an update, and a fresh welcome carries the live slots.
    PbWriter owner;
    owner.Varint(1, 1);
    owner.Varint(2, 555);
    PbWriter equipType;
    equipType.Varint(1, EquipSlotTypeId);
    equipType.Bytes(2, EncodeEquipSlot(555, 2, 14, 777, 7)); // recorded slot for a recorded item
    PbWriter cache;
    cache.Message(2, equipType);
    cache.Fixed64(3, 40);
    cache.Message(4, owner);
    PbWriter welcome;
    welcome.Varint(1, 0);
    welcome.Message(3, cache);
    auto store = std::make_shared<ReplayStore>();
    store->Set(m::EGCBaseClientMsg::k_EMsgGCClientWelcome, welcome.bytes());

    GcEndpointConfig config;
    config.owner = {1, 555};
    LocalGameCoordinator gc(config);
    gc.EnableReplay(store);
    gc.SetDropRecordedItems(true);
    auto liveForEndpoint = std::make_shared<LiveInventory>(inventory);
    int equipSaves = 0;
    gc.EnableLiveInventory(liveForEndpoint, [&] { ++equipSaves; });
    gc.EnableStorePurchaseFailure();

    const auto send = [&](std::uint32_t type, const std::vector<std::uint8_t> &payload, const std::vector<std::uint8_t> &header = {}) {
        std::vector<std::uint8_t> frame;
        WriteProtobufFrame(type, header, payload, frame);
        return gc.SendMessage(type | ProtobufMask, frame.data(), static_cast<std::uint32_t>(frame.size()));
    };
    struct Out { std::uint32_t type{}; std::vector<std::uint8_t> header, body; bool any{}; };
    const auto next = [&]() {
        Out out;
        std::uint32_t size = 0, got = 0;
        if (!gc.IsMessageAvailable(&size))
            return out;
        std::vector<std::uint8_t> buffer(size);
        gc.RetrieveMessage(&out.type, buffer.data(), size, &got);
        FrameView frame;
        ReadProtobufFrame(out.type, buffer, frame);
        out.header.assign(frame.header.begin(), frame.header.end());
        out.body.assign(frame.body.begin(), frame.body.end());
        out.any = true;
        return out;
    };

    ClientHello hello;
    send(m::EGCBaseClientMsg::k_EMsgGCClientHello, EncodeClientHello(hello));
    const auto slotObjects = [](const std::optional<ClientWelcome> &w) -> const std::vector<std::vector<std::uint8_t>> * {
        if (w)
            for (const auto &type : w->outOfDateCaches[0].types)
                if (type.typeId == static_cast<std::int32_t>(EquipSlotTypeId))
                    return &type.objects;
        return nullptr;
    };
    const Out w1 = next();
    const auto w1Decoded = DecodeClientWelcome(w1.body);
    Check(slotObjects(w1Decoded) && slotObjects(w1Decoded)->empty(), "fresh welcome: recorded slots removed, none equipped yet");

    send(m::EGCItemMsg::k_EMsgGCAdjustEquipSlotsManual, body.bytes());
    const Out u = next();
    Check(equipSaves == 1 && Inventory::FromText(liveForEndpoint->Items().ToText())->Loadout().size() == 1,
          "native equip request invokes the save callback and persists its slot");
    const auto updateOut = DecodeSoMultipleObjects(u.body);
    Check(u.any && u.type == (m::ESOMsg::k_ESOMsg_UpdateMultiple | ProtobufMask) && updateOut && updateOut->objects.size() == 1 &&
              updateOut->objects[0].typeId == 3 && updateOut->owner.id == 555 && updateOut->version == 41, "equip answered with an SO update, version past the recorded one");
    PbWriter second;
    second.Message(1, slotMsg);
    send(m::EGCItemMsg::k_EMsgGCAdjustEquipSlotsManual, second.bytes());
    Check(next().any && true, "another equip answered");
    PbWriter unknownSlot;
    PbWriter unknownMsg;
    unknownMsg.Varint(1, 2);
    unknownMsg.Varint(2, 14);
    unknownMsg.Varint(3, 424242);
    unknownSlot.Message(1, unknownMsg);
    const std::size_t ignoredBefore = gc.IgnoredMessages();
    send(m::EGCItemMsg::k_EMsgGCAdjustEquipSlotsManual, unknownSlot.bytes());
    Check(!next().any && gc.IgnoredMessages() == ignoredBefore + 1, "equip of an unknown item is ignored");

    send(m::EGCBaseClientMsg::k_EMsgGCClientHello, EncodeClientHello(hello));
    const Out w2 = next();
    const auto w2Decoded = DecodeClientWelcome(w2.body);
    Check(slotObjects(w2Decoded) && slotObjects(w2Decoded)->size() == 1, "a reconnect's welcome carries the equipped slot");

    // A purchase fails cleanly, with the job id echoed so the game can match the reply.
    PbWriter purchase;
    purchase.Varint(3, 21);
    send(m::EGCItemMsg::k_EMsgGCStorePurchaseInit, purchase.bytes(), jobHeader.bytes());
    const Out r = next();
    PbReader resultReader(r.body);
    PbField rf;
    Check(r.any && r.type == (m::EGCItemMsg::k_EMsgGCStorePurchaseInitResponse | ProtobufMask) && resultReader.Next(rf) && rf.number == 1 && rf.value == 2,
          "purchase refused with result 2");
    PbReader echoReader(r.header);
    PbField ef;
    Check(echoReader.Next(ef) && ef.number == 11 && ef.value == 8, "refusal carries the request's job id");
    Check(gc.PatchFailures() == 0, "no patch failures");
}

constexpr const char *ArmoryFixture = R"("items_game"
{
    "rarities" { "common" { "value" "1" } "uncommon" { "value" "2" } "rare" { "value" "3" } "mythical" { "value" "4" }
                 "legendary" { "value" "5" } "ancient" { "value" "6" } }
    "prefabs"
    {
        "weapon_case_base" { }
        "weapon_case" { "prefab" "weapon_case_base" "associated_item" "50" }
        "rifle" { "item_rarity" "uncommon" }
        "sticker_capsule" { "prefab" "weapon_case_base" }
    }
    "items"
    {
        "50" { "name" "the_key" }
        "60" { "name" "the_case" "prefab" "weapon_case" "attributes" { "set supply crate series" { "value" "1" } } }
        "61" { "name" "crate_sticker_pack_test_capsule" "prefab" "sticker_capsule" "attributes" { "set supply crate series" { "value" "2" } } }
        "7" { "name" "weapon_rifle" "prefab" "rifle" }
        "1209" { "name" "sticker" }
        "1355" { "name" "keychain" }
    }
    "paint_kits" { "10" { "name" "k_a" } "11" { "name" "k_b" } }
    "sticker_kits" { "300" { "name" "stk_a" } "301" { "name" "stk_b" } }
    "keychain_definitions" { "17" { "name" "kc_a" } }
    "client_loot_lists"
    {
        "set_test" { "set_test_uncommon" "1" "set_test_rare" "1" }
        "set_test_uncommon" { "[k_a]weapon_rifle" "1" }
        "set_test_rare" { "[k_b]weapon_rifle" "1" }
        "stickers_test" { "stickers_test_rare" "1" }
        "stickers_test_rare" { "[stk_a]sticker" "1" "[stk_b]sticker" "1" }
        "kc_test" { "kc_test_rare" "1" }
        "kc_test_rare" { "[kc_a]keychain" "1" }
    }
    "revolving_loot_lists" { "2" "stickers_test" }
    "seasonaloperations"
    {
        "11"
        {
            "redeemable_goods" "xpshop"
            "operational_point_redeemable" { "points" "4" "item_name" "lootlist:set_test" }
            "operational_point_redeemable" { "points" "2" "item_name" "the_case" }
            "operational_point_redeemable" { "points" "1" "item_name" "lootlist:stickers_test" }
            "operational_point_redeemable" { "points" "3" "item_name" "lootlist:kc_test" }
            "operational_point_redeemable" { "points" "5" "item_name" "lootlist:missing_list" }
            "operational_point_redeemable" { "points" "1" "item_name" "crate_sticker_pack_test_capsule" "local_rotation_slot" "capsule" }
            "operational_point_redeemable" { "item_name" "no_points_given" }
        }
        "12" { "redeemable_goods" "credits" "operational_point_redeemable" { "points" "1" "item_name" "ignored" } }
    }
})";

void ArmoryRedeems()
{
    Check(Crc32("123456789") == 0xCBF43926u && Crc32("") == 0u, "CRC32 check value");
    Check(Crc32("lootlist:set_overpass_2024") == 2917110498u && Crc32("lootlist:keychain_pack_kc_weapon_01_lootlist") == 2218434721u,
          "CRC32 reproduces the redeem ids captured from the game");

    const auto schema = Schema::Load(ArmoryFixture);
    Check(schema.has_value(), "armory fixture loads");
    Check(schema->ArmoryRedeemables().size() == 6, "six usable tiles; the one without points and the credits campaign are skipped");
    const auto *collection = schema->FindRedeemable(11, Crc32("lootlist:set_test"));
    Check(collection && collection->points == 4 && collection->shopIndex == 0, "collection tile");
    const auto *theCase = schema->FindRedeemable(11, Crc32("the_case"));
    Check(theCase && theCase->points == 2 && theCase->shopIndex == 1, "case tile");
    Check(!schema->FindRedeemable(12, Crc32("ignored")) && !schema->FindRedeemable(11, 12345) && !schema->FindRedeemable(10, Crc32("the_case")),
          "unknown campaign or id");
    Check(schema->ItemRarity(7) == 2 && schema->ItemRarity(60) == 0 && schema->ItemRarity(999) == 0, "item rarity from the prefab chain");

    const auto sticker = schema->ResolveLootItem("[stk_a]sticker");
    const auto charm = schema->ResolveLootItem("[kc_a]keychain");
    const auto skin = schema->ResolveLootItem("[k_a]weapon_rifle");
    Check(sticker && sticker->kind == LootKind::Sticker && sticker->weaponDefIndex == 1209 && sticker->stickerKitIndex == 300 &&
              charm && charm->kind == LootKind::Keychain && charm->weaponDefIndex == 1355 && charm->keychainIndex == 17 &&
              skin && skin->kind == LootKind::Skin && skin->paintKitIndex == 10, "skins, stickers and charms resolve");
    Check(!schema->ResolveLootItem("[nope]sticker") && !schema->ResolveLootItem("[nope]keychain"), "unknown sticker or charm rejected");

    std::mt19937_64 engine(99);
    const RandomSource random = [&] { return engine(); };
    const auto request = [&](const char *name, std::uint32_t cost, std::uint32_t campaign = 11) {
        return RedeemRequest{campaign, Crc32(name), 100, cost};
    };

    // A collection: skins by tier position, uncommon being the lowest tier.
    Inventory inventory;
    LiveInventory live(inventory);
    Armory armory(*schema, 11, 50);
    const auto first = armory.Redeem(request("lootlist:set_test", 4), live, random);
    Check(first.status == Armory::Status::Ok && first.item.defIndex == 7 && first.item.id == 1 &&
              (first.item.paintKitIndex == 10 || first.item.paintKitIndex == 11) && first.item.seed >= 1 && armory.Balance() == 46 &&
              live.Items().Items().size() == 1, "collection redeem grants a skin and costs 4");
    Check(first.item.rarity == (first.item.paintKitIndex == 10 ? 2u : 3u), "the item carries its tier's rarity");
    {
        Armory forced(*schema, 11, 4);
        LiveInventory fresh(Inventory{});
        CaseOdds odds;
        odds.statTrakPerMille = 1000;
        const auto drop = forced.Redeem(request("lootlist:set_test", 4), fresh, [] { return 0ull; }, odds);
        Check(drop.status == Armory::Status::Ok && !drop.item.statTrak,
              "Armory collection rolls never mint hidden StatTrak even with forced case odds");
        const auto restored = Inventory::FromText(fresh.Items().ToText());
        Check(restored && restored->ArmoryCredits() == 0u, "spending the last stars persists a real zero balance");
        LiveInventory restarted(*restored);
        Armory resumed(*schema, 11, restarted.Items().ArmoryCredits().value_or(30));
        Check(resumed.Redeem(request("lootlist:set_test", 4), restarted, random).status == Armory::Status::NotEnoughCredits &&
                  resumed.Balance() == 0 && restarted.Items().Items().size() == 1,
              "a relaunch cannot restore the configured seed balance or repeat an unaffordable purchase");
        const auto partial = Inventory::FromText(live.Items().ToText());
        Check(partial && partial->ArmoryCredits() == 46u, "remaining stars persist alongside the purchased item");
        Check(!Inventory{}.ArmoryCredits(), "old inventories without stars still allow the configured seed balance");
        for (const char *value : {"-1", "4294967296", "bad"})
            Check(!Inventory::FromText(std::string{"\"inventory\" { \"next_id\" \"1\" \"armory_credits\" \""} +
                                      value + "\" \"items\" { } }"), "invalid star balances reject the save");
    }

    const auto caseRedeem = armory.Redeem(request("the_case", 2), live, random);
    Check(caseRedeem.status == Armory::Status::Ok && caseRedeem.item.defIndex == 60 && caseRedeem.item.paintKitIndex == 0 &&
              armory.Balance() == 44, "a plain item name grants that item");
    const auto stickerRedeem = armory.Redeem(request("lootlist:stickers_test", 1), live, random);
    Check(stickerRedeem.status == Armory::Status::Ok && stickerRedeem.item.defIndex == 1209 &&
              (stickerRedeem.item.stickerKit == 300 || stickerRedeem.item.stickerKit == 301) && stickerRedeem.item.rarity == 3, "sticker pack");
    const auto charmRedeem = armory.Redeem(request("lootlist:kc_test", 3), live, random);
    Check(charmRedeem.status == Armory::Status::Ok && charmRedeem.item.defIndex == 1355 && charmRedeem.item.keychain == 17, "charm pack");
    Check(armory.Balance() == 40 && live.Items().Items().size() == 4, "balance and inventory after four redeems");
    {
        Armory capsules(*schema, 11, 1);
        LiveInventory fresh(Inventory{});
        const auto opened = capsules.Redeem(request("crate_sticker_pack_test_capsule", 1), fresh, random);
        Check(opened.status == Armory::Status::Ok && opened.item.defIndex == 1209 &&
                  (opened.item.stickerKit == 300 || opened.item.stickerKit == 301) && fresh.Items().Items().size() == 1,
              "a capsule purchase grants one sticker from that capsule, not the capsule");
    }

    {
        const auto custom = Schema::Load(R"("items_game" {
          "rarities" { "ancient" { "value" "6" } }
          "prefabs" { "weapon_case_base" {} "weapon_case" { "prefab" "weapon_case_base" "associated_item" "50" }
            "hands_paintable" {} }
          "items" { "50" { "name" "key" }
            "500" { "name" "weapon_bayonet" "item_class" "weapon_knife" }
            "5030" { "name" "gloves_test" "prefab" "hands_paintable" }
            "60" { "name" "crate_cs2gc_black_market" "prefab" "weapon_case" "attributes" { "set supply crate series" { "value" "1" } } }
            "61" { "name" "crate_cs2gc_gauntlet" "prefab" "weapon_case" "attributes" { "set supply crate series" { "value" "2" } } } }
          "paint_kits" { "10" { "name" "knife_finish" } "11" { "name" "glove_finish" } }
          "paint_kits_rarity" { "knife_finish" "ancient" "glove_finish" "ancient" }
          "client_loot_lists" { "knives" { "knives_ancient" "1" } "knives_ancient" { "[knife_finish]weapon_bayonet" "1" }
            "gloves" { "gloves_ancient" "1" } "gloves_ancient" { "[glove_finish]gloves_test" "1" } }
          "revolving_loot_lists" { "1" "knives" "2" "gloves" }
          "seasonaloperations" { "11" { "redeemable_goods" "xpshop"
            "operational_point_redeemable" { "item_name" "crate_cs2gc_black_market" "points" "100" "local_rotation_slot" "limited" }
            "operational_point_redeemable" { "item_name" "crate_cs2gc_gauntlet" "points" "100" "local_rotation_slot" "limited" } } }
        })");
        Check(custom.has_value(), "direct custom Armory fixture loads");
        LiveInventory owned(Inventory{});
        Armory shop(*custom,11,200);
        CaseOdds forced; forced.statTrakPerMille = 1000;
        for (const char *name : {"crate_cs2gc_black_market", "crate_cs2gc_gauntlet"})
        {
            const bool glove = std::string_view(name) == "crate_cs2gc_gauntlet";
            const auto grant = shop.Redeem(request(name,100),owned,[] { return 0ull; },forced);
            Check(grant.status == Armory::Status::Ok && grant.item.defIndex == (glove ? 5030u : 500u) &&
                      grant.item.paintKitIndex == (glove ? 11u : 10u) && grant.item.unusual && grant.item.ownerCertificate &&
                      grant.item.statTrak == !glove,
                  "custom Armory purchase directly grants its own finished gold; gloves never StatTrak");
        }
        Check(shop.Balance() == 0 && owned.Items().Items().size() == 2,
              "two purchases charge exactly twice and create no cases or keys");
        const auto saved = Inventory::FromText(owned.Items().ToText());
        Check(saved && saved->Items().size() == 2 && saved->ArmoryCredits() == 0u,
              "direct custom rewards and spent stars survive reload");
        Check(shop.Redeem(request("crate_cs2gc_gauntlet",100),owned,random).status == Armory::Status::NotEnoughCredits &&
                  owned.Items().Items().size() == 2, "insufficient stars cannot mint another direct gold");
        Inventory oldCases;
        const auto oldCase = oldCases.Add({0,61});
        const auto oldOpen = OpenCase(oldCases,*custom,oldCase,0,[] { return 0ull; },forced);
        Check(oldOpen.error == OpenError::None && oldOpen.item.defIndex == 5030 && !oldOpen.item.statTrak,
              "previously owned Gauntlet cases still open normally");
    }

    // Every failure leaves the balance and the inventory exactly as they were.
    const auto unchanged = [&](Armory::Status want, const RedeemRequest &r, const char *what) {
        const auto before = live.Items().Items().size();
        const auto balance = armory.Balance();
        const auto result = armory.Redeem(r, live, random);
        Check(result.status == want && live.Items().Items().size() == before && armory.Balance() == balance, what);
    };
    unchanged(Armory::Status::WrongCampaign, request("the_case", 2, 12), "wrong campaign");
    unchanged(Armory::Status::UnknownGoods, RedeemRequest{11, 4242, 40, 2}, "unknown goods");
    unchanged(Armory::Status::CostMismatch, request("the_case", 1), "the client's cost differs from the schema's");
    unchanged(Armory::Status::NothingToGrant, request("lootlist:missing_list", 5), "a loot list that does not exist");
    Armory poor(*schema, 11, 1);
    const auto tooDear = poor.Redeem(request("lootlist:set_test", 4), live, random);
    Check(tooDear.status == Armory::Status::NotEnoughCredits && poor.Balance() == 1 && live.Items().Items().size() == 4, "not enough credits");

    // Odds follow tier position: the lowest tier of a collection is the common one.
    Armory rich(*schema, 11, 1000000);
    int uncommon = 0;
    constexpr int Rolls = 20000;
    LiveInventory scratch{Inventory{}};
    GameplayConfig baseOdds;
    baseOdds.armory_pity_enabled = 0; baseOdds.armory_top_per_10000 = 0;
    Inventory baseInventory; baseInventory.SetGameplay(baseOdds);
    scratch = LiveInventory(baseInventory);
    for (int i = 0; i < Rolls; ++i)
        uncommon += rich.Redeem(request("lootlist:set_test", 4), scratch, random).item.paintKitIndex == 10;
    Check(std::abs(uncommon / double(Rolls) - 7992.0 / (7992 + 1598)) < 0.015, "collection odds: lowest tier is the common one");
    Inventory pityInventory;
    pityInventory.SetArmoryPity("set_test", 99);
    pityInventory.SetArmoryPity("unrelated_collection", 7);
    LiveInventory pityLive(pityInventory);
    Armory pityArmory(*schema, 11, 8);
    auto guaranteed = pityArmory.Redeem(request("lootlist:set_test", 4), pityLive, [] { return 9999ull; });
    Check(guaranteed.status == Armory::Status::Ok && guaranteed.item.paintKitIndex == 11 &&
              pityLive.Items().ArmoryPity("set_test") == 0 && pityLive.Items().ArmoryPity("unrelated_collection") == 7,
          "100th Armory collection roll guarantees its highest tier and resets only its own saved counter");
    const auto failedBefore = pityLive.Items().ToText();
    const auto failed = pityArmory.Redeem(request("lootlist:set_test", 5), pityLive, [] { return 9999ull; });
    Check(failed.status == Armory::Status::CostMismatch && failedBefore == pityLive.Items().ToText(),
          "failed Armory buys do not consume stars or advance collection pity");
    const auto miss = pityArmory.Redeem(request("lootlist:set_test", 4), pityLive, [] { return 9999ull; });
    const auto savedPity = Inventory::FromText(pityLive.Items().ToText());
    Check(miss.status == Armory::Status::Ok && savedPity && savedPity->ArmoryPity("set_test") == 1 &&
              savedPity->ArmoryPity("unrelated_collection") == 7, "Armory pity survives restart independently for each collection");
}

void ArmoryEndpoint()
{
    namespace m = gc_msg;
    const auto schema = Schema::Load(ArmoryFixture);
    Check(schema.has_value(), "fixture loads");

    // A recorded welcome whose pass object has generation time 5, balance 10 and one track.
    PbWriter pass;
    pass.Varint(1, 5);
    pass.Varint(2, 10);
    pass.Varint(3, 77);
    PbWriter passType;
    passType.Varint(1, XpShopTypeId);
    passType.Bytes(2, pass.bytes());
    PbWriter owner;
    owner.Varint(1, 1);
    owner.Varint(2, 555);
    PbWriter cache;
    cache.Message(2, passType);
    cache.Fixed64(3, 100);
    cache.Message(4, owner);
    PbWriter welcome;
    welcome.Varint(1, 0);
    welcome.Message(3, cache);
    auto store = std::make_shared<ReplayStore>();
    store->Set(m::EGCBaseClientMsg::k_EMsgGCClientWelcome, welcome.bytes());

    GcEndpointConfig config;
    config.owner = {1, 555};
    LocalGameCoordinator gc(config);
    gc.EnableReplay(store);
    auto live = std::make_shared<LiveInventory>(Inventory{});
    auto armory = std::make_shared<Armory>(*schema, 11, 10);
    std::mt19937_64 engine(7);
    int grants = 0;
    gc.EnableArmory(armory, live, [&] { return engine(); }, [&] { ++grants; });

    const auto send = [&](std::uint32_t type, const std::vector<std::uint8_t> &payload) {
        std::vector<std::uint8_t> frame;
        WriteProtobufFrame(type, {}, payload, frame);
        return gc.SendMessage(type | ProtobufMask, frame.data(), static_cast<std::uint32_t>(frame.size()));
    };
    struct Out { std::uint32_t type{}; std::vector<std::uint8_t> body; bool any{}; };
    const auto next = [&]() {
        Out out;
        std::uint32_t size = 0, got = 0;
        if (!gc.IsMessageAvailable(&size))
            return out;
        std::vector<std::uint8_t> buffer(size);
        gc.RetrieveMessage(&out.type, buffer.data(), size, &got);
        FrameView frame;
        ReadProtobufFrame(out.type, buffer, frame);
        out.body.assign(frame.body.begin(), frame.body.end());
        out.any = true;
        return out;
    };
    const auto redeem = [&](const char *name, std::uint32_t cost, std::uint32_t balance = 10) {
        PbWriter body;
        body.Varint(1, 11);
        body.Varint(2, Crc32(name));
        body.Varint(3, balance);
        body.Varint(4, cost);
        return send(m::ECsgoGCMsg::k_EMsgGCCStrike15_v2_ClientRedeemMissionReward, body.bytes());
    };

    // The same message as the real client sends decodes to what the handler sees.
    PbWriter probe;
    probe.Varint(1, 11);
    probe.Varint(2, 2917110498u);
    probe.Varint(3, 25);
    probe.Varint(4, 4);
    const auto decoded = DecodeRedeemRequest(probe.bytes());
    Check(decoded && decoded->campaignId == 11 && decoded->redeemId == 2917110498u && decoded->redeemableBalance == 25 &&
              decoded->expectedCost == 4, "redeem request decode");
    Check(!DecodeRedeemRequest(Bytes({0x08})) && !DecodeRedeemRequest(Bytes({0x10, 0x80, 0x80, 0x80, 0x80, 0x10})), "malformed or oversized request rejected");

    // A valid redeem: the item is created as a new unacknowledged one, then the pass balance changes.
    Check(redeem("the_case", 2) == GCResult::OK, "redeem accepted");
    const Out created = next();
    const auto createdObject = DecodeSoSingleObject(created.body);
    Check(created.any && created.type == (m::ESOMsg::k_ESOMsg_Create | ProtobufMask) && createdObject && createdObject->typeId == 1 &&
              createdObject->owner.id == 555, "an item is created");
    const DecodedItem item = DecodeItem(createdObject->data);
    Check(item.ok && item.defIndex == 60 && item.account == 555 && item.id == CustomItemIdBase + 1 &&
              item.inventory == (InventoryUnacknowledgedBit | PickupXpShopRedeem), "a new, unacknowledged Armory item");
    const Out updated = next();
    const auto updatedObject = DecodeSoSingleObject(updated.body);
    Check(updated.any && updated.type == (m::ESOMsg::k_ESOMsg_Update | ProtobufMask) && updatedObject &&
              updatedObject->typeId == static_cast<std::int32_t>(XpShopTypeId), "the pass object is updated");
    std::map<std::uint32_t, std::vector<std::uint64_t>> fields;
    {
        PbReader reader(updatedObject->data);
        PbField f;
        while (reader.Next(f))
            fields[f.number].push_back(f.value);
    }
    Check(fields.at(2) == std::vector<std::uint64_t>{8} && fields.at(1) == std::vector<std::uint64_t>{5} &&
              !fields.count(3), "balance 10 - 2 = 8, other fields kept, the recorded account's pass dropped");
    Check(createdObject->version > 100 && updatedObject->version == createdObject->version + 1, "object versions move on");
    Check(grants == 1 && live->Items().Items().size() == 1 && armory->Balance() == 8 && !next().any, "one grant, balance 8, nothing else sent");

    // Bad requests send nothing, change nothing and do not call the grant hook.
    redeem("the_case", 9);   // a cost that is not the schema's
    redeem("not a tile", 2); // goods the schema does not list
    Check(!next().any && armory->Balance() == 8 && grants == 1, "rejected requests change nothing and send nothing");
    redeem("lootlist:set_test", 4); // 8 -> 4
    Check(next().any && next().any && armory->Balance() == 4, "a later valid redeem still works");
    redeem("lootlist:set_test", 4); // 4 -> 0
    Check(next().any && next().any && armory->Balance() == 0 && grants == 3, "credits can be spent to zero");
    const std::size_t ignoredBefore = gc.IgnoredMessages();
    redeem("the_case", 2); // credits are 0
    Check(!next().any && gc.IgnoredMessages() == ignoredBefore + 1 && armory->Balance() == 0, "no credits left: ignored");
    send(m::ECsgoGCMsg::k_EMsgGCCStrike15_v2_ClientRedeemMissionReward, Bytes({0x08}));
    Check(!next().any, "malformed request ignored");

    // A reconnect's welcome shows the live balance.
    ClientHello hello;
    send(m::EGCBaseClientMsg::k_EMsgGCClientHello, EncodeClientHello(hello));
    const Out w = next();
    const auto passObjects = ExtractObjects(w.body, XpShopTypeId);
    Check(passObjects.size() == 1, "the welcome carries the pass object");
    PbReader passReader(passObjects[0]);
    PbField pf;
    std::uint64_t balance = 99;
    while (passReader.Next(pf))
        if (pf.number == 2)
            balance = pf.value;
    Check(balance == 0, "a reconnect's welcome shows the live balance");
}

void StickerApplication()
{
    namespace m = gc_msg;
    Inventory inventory;
    InventoryItem weapon;
    weapon.defIndex = 7;
    weapon.paintKitIndex = 282;
    weapon.wear = 0.1f;
    weapon.seed = 5;
    inventory.Add(weapon);
    InventoryItem sticker;
    sticker.defIndex = DefinitionSticker;
    sticker.stickerKit = 77;
    inventory.Add(sticker);
    const std::uint64_t weaponId = CustomItemIdBase + 1, stickerId = CustomItemIdBase + 2;

    PbWriter body;
    body.Varint(1, stickerId);
    body.Varint(2, weaponId);
    body.Varint(3, 3);
    body.Fixed32(6, std::bit_cast<std::uint32_t>(15.0f));
    body.Fixed32(8, std::bit_cast<std::uint32_t>(0.25f));
    const auto request = DecodeApplyStickerRequest(body.bytes());
    Check(request && request->stickerItemId == stickerId && request->targetItemId == weaponId && request->slot == 3 &&
              request->rotation == 15.0f && request->offsetX == 0.25f && request->scale == 0.0f,
          "apply-sticker request decodes");
    PbWriter wrongWire;
    wrongWire.Varint(6, 1);
    Check(!DecodeApplyStickerRequest(wrongWire.bytes()) && !DecodeApplyStickerRequest(Bytes({0x0A, 0x09, 1})),
          "malformed apply-sticker request rejected");

    auto live = std::make_shared<LiveInventory>(inventory);
    ApplyStickerRequest bad = *request;
    bad.slot = 5;
    Check(!live->ApplySticker(bad), "slot past the last is refused");
    bad = *request;
    bad.stickerItemId = weaponId;
    Check(!live->ApplySticker(bad), "a non-sticker item cannot be applied");
    bad = *request;
    bad.targetItemId = 4242;
    Check(!live->ApplySticker(bad) && live->Items().Items().size() == 2, "unknown target refused, nothing changed");

    GcEndpointConfig config;
    config.owner = {1, 555};
    LocalGameCoordinator gc(config);
    int saves = 0;
    gc.EnableLiveInventory(live, [&saves] { ++saves; });
    std::vector<std::uint8_t> frame;
    WriteProtobufFrame(m::EGCItemMsg::k_EMsgGCApplySticker, {}, body.bytes(), frame);
    gc.SendMessage(m::EGCItemMsg::k_EMsgGCApplySticker | ProtobufMask, frame.data(), static_cast<std::uint32_t>(frame.size()));
    const auto read = [&]() -> std::optional<std::pair<std::uint32_t, SoSingleObject>> {
        std::uint32_t size = 0, got = 0, type = 0;
        if (!gc.IsMessageAvailable(&size))
            return std::nullopt;
        std::vector<std::uint8_t> buffer(size);
        gc.RetrieveMessage(&type, buffer.data(), size, &got);
        FrameView view;
        ReadProtobufFrame(type, buffer, view);
        auto object = DecodeSoSingleObject(view.body);
        if (!object)
            return std::nullopt;
        return std::make_pair(type & ~ProtobufMask, *object);
    };
    const auto destroyed = read();
    const auto updated = read();
    Check(updated && updated->first == m::ESOMsg::k_ESOMsg_Update && updated->second.typeId == 1, "item updated");
    Check(destroyed && destroyed->first == m::ESOMsg::k_ESOMsg_Destroy && destroyed->second.typeId == 1,
          "sticker item destroyed");
    {
        // Then the notification the apply screen waits for: request 1086 (apply sticker), the weapon's id.
        std::uint32_t size = 0, got = 0, type = 0;
        Check(gc.IsMessageAvailable(&size), "a notification follows");
        std::vector<std::uint8_t> buffer(size);
        gc.RetrieveMessage(&type, buffer.data(), size, &got);
        FrameView view;
        ReadProtobufFrame(type, buffer, view);
        std::uint64_t item = 0, request = 0;
        PbReader reader(view.body);
        PbField f;
        while (reader.Next(f))
            (f.number == 1 ? item : request) = f.value;
        Check((type & ~ProtobufMask) == m::EGCItemMsg::k_EMsgGCItemCustomizationNotification && request == 1086 &&
                  item == weaponId,
              "apply-sticker notification names the weapon");
    }
    Check(saves == 1 && live->Items().Items().size() == 1, "inventory saved, sticker item consumed");
    const InventoryItem &applied = live->Items().Items()[0];
    Check(applied.stickers.size() == 1 && applied.stickers[0].slot == 3 && applied.stickers[0].kit == 77 &&
              applied.stickers[0].rotation == 15.0f,
          "sticker recorded on the weapon");

    // The attributes the game reads: slot 3 id is 125, rotation 128, offset x 284.
    const auto encoded = BuildEconItem(applied, 555, weaponId, ItemPositionBase);
    const auto has = [&](std::uint32_t attribute) {
        PbReader reader(encoded);
        PbField f;
        while (reader.Next(f))
            if (f.number == 12 && f.wire == 2)
            {
                PbReader inner(f.bytes);
                PbField g;
                while (inner.Next(g))
                    if (g.number == 1 && g.value == attribute)
                        return true;
            }
        return false;
    };
    Check(has(125) && has(128) && has(284) && !has(126) && !has(127), "sticker attributes encoded for slot 3");
    Check(updated && updated->second.data == encoded, "the update carries the item with its sticker");

    Check(!live->ApplySticker(*request), "a sticker cannot be applied twice");
    const auto restored = Inventory::FromText(live->Items().ToText());
    Check(restored && restored->Items().size() == 1 && restored->Items()[0].stickers.size() == 1 &&
              restored->Items()[0].stickers[0].offsetX == 0.25f,
          "applied stickers survive a save and load");
    Check(!Inventory::FromText("\"inventory\" { \"next_id\" \"2\" \"items\" { \"1\" { \"def_index\" \"7\" \"paint_kit\" \"0\" "
                               "\"wear\" \"0\" \"seed\" \"0\" \"stattrak\" \"0\" \"sticker_0\" \"0 0 0 0 0 0\" } } }"),
          "a sticker with no kit is rejected on load");
}

void StorePurchases()
{
    namespace m = gc_msg;
    auto live = std::make_shared<LiveInventory>(Inventory{});
    GcEndpointConfig config;
    config.owner = {1, 555};
    LocalGameCoordinator gc(config);
    int saves = 0;
    gc.EnableStorePurchases(live, [](std::uint32_t def) { return def == 4001 || def == 1203; }, [&saves] { ++saves; });

    struct Out { std::uint32_t type{}; std::vector<std::uint8_t> header, body; };
    const auto read = [&]() -> std::optional<Out> {
        std::uint32_t size = 0, got = 0;
        if (!gc.IsMessageAvailable(&size))
            return std::nullopt;
        Out out;
        std::vector<std::uint8_t> buffer(size);
        gc.RetrieveMessage(&out.type, buffer.data(), size, &got);
        FrameView view;
        ReadProtobufFrame(out.type, buffer, view);
        out.type &= ~ProtobufMask;
        out.header.assign(view.header.begin(), view.header.end());
        out.body.assign(view.body.begin(), view.body.end());
        return out;
    };
    const auto send = [&](std::uint32_t type, const PbWriter &body, std::uint64_t job) {
        PbWriter header;
        header.Fixed64(10, job);
        std::vector<std::uint8_t> frame;
        WriteProtobufFrame(type, header.bytes(), body.bytes(), frame);
        gc.SendMessage(type | ProtobufMask, frame.data(), static_cast<std::uint32_t>(frame.size()));
    };
    const auto init = [](std::initializer_list<std::pair<std::uint32_t, std::uint32_t>> lines) {
        PbWriter body;
        body.Varint(3, 21);
        for (const auto &[def, quantity] : lines)
        {
            PbWriter line;
            line.Varint(1, def);
            line.Varint(2, quantity);
            line.Varint(3, 140);
            body.Message(4, line);
        }
        return body;
    };
    const auto result = [](const Out &out) {
        PbReader reader(out.body);
        PbField f;
        std::uint64_t value = 0;
        while (reader.Next(f))
            if (f.number == 1)
                value = f.value;
        return value;
    };

    // Refused: an item the schema does not sell, a zero quantity, an empty cart.
    for (const auto &bad : {init({{9999, 1}}), init({{4001, 0}}), init({})})
    {
        send(m::EGCItemMsg::k_EMsgGCStorePurchaseInit, bad, 9);
        const auto reply = read();
        Check(reply && reply->type == m::EGCItemMsg::k_EMsgGCStorePurchaseInitResponse && result(*reply) == 2,
              "an invalid purchase is refused");
        Check(!gc.TakePendingAuthorization(), "a refused purchase authorises nothing");
    }

    send(m::EGCItemMsg::k_EMsgGCStorePurchaseInit, init({{4001, 2}, {1203, 1}}), 7);
    const auto accepted = read();
    std::uint64_t txn = 0;
    if (accepted)
    {
        PbReader reader(accepted->body);
        PbField f;
        while (reader.Next(f))
            if (f.number == 2)
                txn = f.value;
    }
    Check(accepted && result(*accepted) == 1 && txn != 0, "a valid purchase is accepted with a transaction id");
    Check(accepted && !accepted->header.empty(), "the job id is echoed");
    Check(gc.TakePendingAuthorization() == txn && !gc.TakePendingAuthorization(), "the authorisation is due once");

    // A second purchase while one is open is refused.
    send(m::EGCItemMsg::k_EMsgGCStorePurchaseInit, init({{4001, 1}}), 8);
    const auto second = read();
    Check(second && result(*second) == 2, "only one transaction at a time");

    PbWriter wrong;
    wrong.Varint(1, txn + 1);
    send(m::EGCItemMsg::k_EMsgGCStorePurchaseFinalize, wrong, 10);
    const auto refused = read();
    Check(refused && result(*refused) == 2 && live->Items().Items().empty() && saves == 0,
          "finalize with the wrong transaction id grants nothing");

    PbWriter finalize;
    finalize.Varint(1, txn);
    send(m::EGCItemMsg::k_EMsgGCStorePurchaseFinalize, finalize, 11);
    int creates = 0;
    std::optional<Out> response;
    while (const auto out = read())
    {
        if (out->type == m::ESOMsg::k_ESOMsg_Create)
        {
            ++creates;
            const auto object = DecodeSoSingleObject(out->body);
            PbReader reader(object ? std::span<const std::uint8_t>(object->data) : std::span<const std::uint8_t>{});
            PbField f;
            std::uint64_t inventory = 0;
            while (reader.Next(f))
                if (f.number == 3)
                    inventory = f.value;
            Check(inventory == (InventoryUnacknowledgedBit | PickupPurchased), "bought items arrive unacknowledged as purchases");
        }
        else if (out->type == m::EGCItemMsg::k_EMsgGCStorePurchaseFinalizeResponse)
            response = out;
    }
    Check(creates == 3 && live->Items().Items().size() == 3 && saves == 1, "three items created and saved");
    std::vector<std::uint64_t> ids;
    if (response)
    {
        PbReader reader(response->body);
        PbField f;
        while (reader.Next(f))
            if (f.number == 2)
                ids.push_back(f.value);
    }
    Check(response && result(*response) == 1 && ids.size() == 3 && ids[0] == CustomItemIdBase + 1,
          "finalize answers with the new item ids");

    send(m::EGCItemMsg::k_EMsgGCStorePurchaseFinalize, finalize, 12);
    const auto again = read();
    Check(again && result(*again) == 2 && live->Items().Items().size() == 3, "a transaction finalizes once");

    send(m::EGCItemMsg::k_EMsgGCStorePurchaseInit, init({{4001, 1}}), 13);
    const auto third = read();
    PbWriter cancel;
    cancel.Varint(1, third ? [&] { PbReader r(third->body); PbField f; std::uint64_t t = 0; while (r.Next(f)) if (f.number == 2) t = f.value; return t; }() : 0);
    send(m::EGCItemMsg::k_EMsgGCStorePurchaseCancel, cancel, 14);
    const auto cancelled = read();
    Check(cancelled && cancelled->type == m::EGCItemMsg::k_EMsgGCStorePurchaseCancelResponse &&
              !gc.TakePendingAuthorization(),
          "cancel drops the transaction");
    send(m::EGCItemMsg::k_EMsgGCStorePurchaseInit, init({{4001, 1}}), 15);
    const auto fresh = read();
    Check(fresh && result(*fresh) == 1, "a new purchase can start after a cancel");
}

void ArmoryPassActivation()
{
    namespace m = gc_msg;
    const auto schema = Schema::Load(ArmoryFixture);
    PbWriter pass;
    pass.Varint(1, 5);
    pass.Varint(2, 10);
    pass.Varint(3, 77);
    PbWriter passType;
    passType.Varint(1, XpShopTypeId);
    passType.Bytes(2, pass.bytes());
    PbWriter owner;
    owner.Varint(1, 1);
    owner.Varint(2, 555);
    PbWriter cache;
    cache.Message(2, passType);
    cache.Fixed64(3, 100);
    cache.Message(4, owner);
    PbWriter welcome;
    welcome.Varint(1, 0);
    welcome.Message(3, cache);
    auto store = std::make_shared<ReplayStore>();
    store->Set(m::EGCBaseClientMsg::k_EMsgGCClientWelcome, welcome.bytes());

    Inventory inventory;
    InventoryItem ticket;
    ticket.defIndex = DefinitionArmoryPass;
    inventory.Add(ticket);
    InventoryItem other;
    other.defIndex = 7;
    inventory.Add(other);

    GcEndpointConfig config;
    config.owner = {1, 555};
    LocalGameCoordinator gc(config);
    gc.EnableReplay(store);
    auto live = std::make_shared<LiveInventory>(inventory);
    auto armory = std::make_shared<Armory>(*schema, 11, 30);
    std::mt19937_64 engine(7);
    int saves = 0;
    gc.EnableArmory(armory, live, [&] { return engine(); }, [&] { ++saves; });

    const auto use = [&](std::uint64_t itemId) {
        PbWriter body;
        body.Varint(1, itemId);
        std::vector<std::uint8_t> frame;
        WriteProtobufFrame(m::EGCItemMsg::k_EMsgGCUseItemRequest, {}, body.bytes(), frame);
        gc.SendMessage(m::EGCItemMsg::k_EMsgGCUseItemRequest | ProtobufMask, frame.data(), static_cast<std::uint32_t>(frame.size()));
    };
    struct Out { std::uint32_t type{}; std::vector<std::uint8_t> body; bool any{}; };
    const auto next = [&]() {
        Out out;
        std::uint32_t size = 0, got = 0;
        if (!gc.IsMessageAvailable(&size))
            return out;
        std::vector<std::uint8_t> buffer(size);
        gc.RetrieveMessage(&out.type, buffer.data(), size, &got);
        FrameView frame;
        ReadProtobufFrame(out.type, buffer, frame);
        out.body.assign(frame.body.begin(), frame.body.end());
        out.type &= ~ProtobufMask;
        out.any = true;
        return out;
    };
    const auto tracks = [](std::span<const std::uint8_t> object) {
        std::vector<std::uint64_t> values;
        PbReader reader(object);
        PbField f;
        while (reader.Next(f))
            if (f.number == 3)
                values.push_back(f.value);
        return values;
    };

    use(CustomItemIdBase + 2); // not a pass
    use(0xF000000000000000ull | DefinitionArmoryPass); // a built-in default is not one of ours
    use(424242);
    Check(!next().any && live->Items().Items().size() == 2 && saves == 0, "anything but one of our passes is ignored");

    use(CustomItemIdBase + 1);
    const Out updated = next();
    const Out destroyed = next();
    const auto pass1 = DecodeSoSingleObject(updated.body);
    Check(updated.type == m::ESOMsg::k_ESOMsg_Update && pass1 && pass1->typeId == static_cast<std::int32_t>(XpShopTypeId) &&
              tracks(pass1->data) == std::vector<std::uint64_t>({1}), "activating adds a pass at 1 XP; the recorded account's passes are not carried over");
    Check(destroyed.type == m::ESOMsg::k_ESOMsg_Destroy && live->Items().Items().size() == 1 && saves == 1,
          "the ticket is consumed and the inventory saved");
    const Out passNotice = next();
    std::uint64_t noticeRequest = 0;
    {
        PbReader reader(passNotice.body);
        PbField f;
        while (reader.Next(f))
            if (f.number == 2)
                noticeRequest = f.value;
    }
    Check(passNotice.type == m::EGCItemMsg::k_EMsgGCItemCustomizationNotification && noticeRequest == 9221,
          "activation sends the XpShopUseTicket notification");
    use(CustomItemIdBase + 1);
    Check(!next().any, "a ticket activates once");

    ClientHello hello;
    std::vector<std::uint8_t> frame;
    WriteProtobufFrame(m::EGCBaseClientMsg::k_EMsgGCClientHello, {}, EncodeClientHello(hello), frame);
    gc.SendMessage(m::EGCBaseClientMsg::k_EMsgGCClientHello | ProtobufMask, frame.data(), static_cast<std::uint32_t>(frame.size()));
    const Out w = next();
    const auto objects = ExtractObjects(w.body, XpShopTypeId);
    Check(objects.size() == 1 && tracks(objects[0]) == std::vector<std::uint64_t>({1}),
          "a reconnect's welcome keeps the activated pass");
    PbReader reader(objects.empty() ? std::span<const std::uint8_t>{} : std::span<const std::uint8_t>(objects[0]));
    PbField f;
    std::uint64_t balance = 0;
    while (reader.Next(f))
        if (f.number == 2)
            balance = f.value;
    Check(balance == 30, "and shows the configured credits, not the recorded ones");
}

void ContainersAndNaming()
{
    namespace m = gc_msg;
    const auto schema = Schema::Load(ArmoryFixture);
    Check(schema.has_value(), "fixture loads");
    const auto shared = std::shared_ptr<const Schema>(&*schema, [](const Schema *) {});

    Inventory inventory;
    InventoryItem crate;
    crate.defIndex = 60; // "the_case" in the fixture
    inventory.Add(crate);
    InventoryItem wrongKey;
    wrongKey.defIndex = 7;
    inventory.Add(wrongKey);
    auto live = std::make_shared<LiveInventory>(inventory);

    GcEndpointConfig config;
    config.owner = {1, 555};
    LocalGameCoordinator gc(config);
    std::mt19937_64 engine(3);
    int saves = 0;
    gc.EnableContainers(live, shared, [&] { return engine(); }, [&saves] { ++saves; });

    const auto send = [&](std::uint32_t type, const PbWriter &body) {
        std::vector<std::uint8_t> frame;
        WriteProtobufFrame(type, {}, body.bytes(), frame);
        gc.SendMessage(type | ProtobufMask, frame.data(), static_cast<std::uint32_t>(frame.size()));
    };
    struct Out { std::uint32_t type{}; std::vector<std::uint8_t> body; };
    const auto read = [&]() -> std::optional<Out> {
        std::uint32_t size = 0, got = 0;
        if (!gc.IsMessageAvailable(&size))
            return std::nullopt;
        Out out;
        std::vector<std::uint8_t> buffer(size);
        gc.RetrieveMessage(&out.type, buffer.data(), size, &got);
        FrameView view;
        ReadProtobufFrame(out.type, buffer, view);
        out.type &= ~ProtobufMask;
        out.body.assign(view.body.begin(), view.body.end());
        return out;
    };
    const auto open = [&](std::uint64_t key, std::uint64_t crateId) {
        PbWriter body;
        body.Varint(1, key);
        body.Varint(2, crateId);
        send(m::EGCItemMsg::k_EMsgGCOpenCrate, body);
    };

    const std::size_t ignored = gc.IgnoredMessages();
    open(0, CustomItemIdBase + 1);                    // a case with no key
    open(CustomItemIdBase + 2, CustomItemIdBase + 1); // the wrong key
    open(0, 424242);                                  // not ours
    Check(!read() && gc.IgnoredMessages() == ignored + 3 && live->Items().Items().size() == 2 && saves == 0,
          "bad open requests change nothing");
    PbWriter malformed;
    malformed.Varint(1, 5); // no container
    send(m::EGCItemMsg::k_EMsgGCOpenCrate, malformed);
    Check(!read(), "an open request without a container is ignored");

    // A name sticks to an item, and the game is told.
    PbWriter name;
    name.Varint(1, 0);
    name.Varint(2, CustomItemIdBase + 2);
    name.String(4, "Stuff");
    send(m::EGCItemMsg::k_EMsgGCNameItem, name);
    const auto update = read();
    const auto notice = read();
    Check(update && update->type == m::ESOMsg::k_ESOMsg_Update && notice &&
              notice->type == m::EGCItemMsg::k_EMsgGCItemCustomizationNotification && saves == 1,
          "naming updates the item and notifies");
    const auto named = Inventory::FromText(live->Items().ToText());
    Check(named && named->Items().size() == 2 && named->Items()[1].customName == "Stuff", "the name is saved");
    const auto econ = BuildEconItem(named->Items()[1], 555, CustomItemIdBase + 2, ItemPositionBase);
    bool hasName = false;
    {
        PbReader reader(econ);
        PbField f;
        while (reader.Next(f))
            if (f.number == 12 && f.wire == 2)
            {
                PbReader inner(f.bytes);
                PbField g;
                while (inner.Next(g))
                    if (g.number == 1 && g.value == AttributeCustomName)
                        hasName = true;
            }
    }
    Check(hasName, "the custom name attribute is encoded");
    PbWriter bad;
    bad.Varint(2, CustomItemIdBase + 2);
    bad.String(4, "a\"b");
    send(m::EGCItemMsg::k_EMsgGCNameItem, bad);
    Check(!read() && live->Items().Items()[1].customName == "Stuff", "a name with a quote is refused");
}

void CharmsAndCoupons()
{
    namespace m = gc_msg;
    Inventory inventory;
    InventoryItem weapon;
    weapon.defIndex = 7;
    weapon.paintKitIndex = 282;
    inventory.Add(weapon);
    InventoryItem charm;
    charm.defIndex = DefinitionKeychain;
    charm.keychain = 33;
    inventory.Add(charm);
    InventoryItem second;
    second.defIndex = DefinitionKeychain;
    second.keychain = 34;
    inventory.Add(second);
    auto live = std::make_shared<LiveInventory>(inventory);
    GcEndpointConfig config;
    config.owner = {1, 555};
    LocalGameCoordinator gc(config);
    int saves = 0;
    gc.EnableLiveInventory(live, [&saves] { ++saves; });

    PbWriter body;
    body.Varint(1, CustomItemIdBase + 2);
    body.Varint(2, CustomItemIdBase + 1);
    body.Fixed32(8, std::bit_cast<std::uint32_t>(9.5f));
    body.Fixed32(9, std::bit_cast<std::uint32_t>(0.5f));
    body.Fixed32(10, std::bit_cast<std::uint32_t>(4.25f));
    const auto request = DecodeApplyStickerRequest(body.bytes());
    Check(request && request->offsetZ == 4.25f, "the third offset decodes");
    std::vector<std::uint8_t> frame;
    WriteProtobufFrame(m::EGCItemMsg::k_EMsgGCApplySticker, {}, body.bytes(), frame);
    gc.SendMessage(m::EGCItemMsg::k_EMsgGCApplySticker | ProtobufMask, frame.data(), static_cast<std::uint32_t>(frame.size()));
    std::vector<std::uint32_t> types;
    std::uint64_t notifyRequest = 0;
    std::uint32_t size = 0;
    while (gc.IsMessageAvailable(&size))
    {
        std::uint32_t got = 0, type = 0;
        std::vector<std::uint8_t> buffer(size);
        gc.RetrieveMessage(&type, buffer.data(), size, &got);
        types.push_back(type & ~ProtobufMask);
        if ((type & ~ProtobufMask) == m::EGCItemMsg::k_EMsgGCItemCustomizationNotification)
        {
            FrameView view;
            ReadProtobufFrame(type, buffer, view);
            PbReader reader(view.body);
            PbField f;
            while (reader.Next(f))
                if (f.number == 2)
                    notifyRequest = f.value;
        }
    }
    Check(types.size() == 3 && types[0] == m::ESOMsg::k_ESOMsg_Destroy && types[1] == m::ESOMsg::k_ESOMsg_Update &&
              notifyRequest == 1091,
          "a charm is applied with the ApplyKeychain notification");
    const InventoryItem &applied = live->Items().Items()[0];
    Check(applied.charm && applied.charm->kit == 33 && applied.charm->offsetZ == 4.25f && applied.stickers.empty() &&
              saves == 1 && live->Items().Items().size() == 2,
          "the charm sits on the weapon and the charm item is consumed");
    const auto encoded = BuildEconItem(applied, 555, CustomItemIdBase + 1, ItemPositionBase);
    std::set<std::uint64_t> attributes;
    {
        PbReader reader(encoded);
        PbField f;
        while (reader.Next(f))
            if (f.number == 12 && f.wire == 2)
            {
                PbReader inner(f.bytes);
                PbField g;
                while (inner.Next(g))
                    if (g.number == 1)
                        attributes.insert(g.value);
            }
    }
    Check(attributes.count(299) && attributes.count(300) && attributes.count(301) && attributes.count(302),
          "charm id and offsets are encoded");
    const auto restored = Inventory::FromText(live->Items().ToText());
    Check(restored && restored->Items()[0].charm && restored->Items()[0].charm->offsetX == 9.5f,
          "an attached charm survives a save and load");

    // The built-in Remove Keychain Tool takes the charm off again: the weapon is updated, the charm is a
    // loose item and the game is told (RemoveKeychain, 1092).
    {
        PbWriter detach;
        detach.Varint(1, 0xF000000000000000ull | DefinitionRemoveKeychainTool);
        detach.Varint(2, CustomItemIdBase + 1);
        std::vector<std::uint8_t> detachFrame;
        WriteProtobufFrame(m::EGCItemMsg::k_EMsgGCApplySticker, {}, detach.bytes(), detachFrame);
        gc.SendMessage(m::EGCItemMsg::k_EMsgGCApplySticker | ProtobufMask, detachFrame.data(),
                       static_cast<std::uint32_t>(detachFrame.size()));
        std::vector<std::uint32_t> kinds;
        std::uint64_t request = 0;
        std::uint32_t pending = 0;
        while (gc.IsMessageAvailable(&pending))
        {
            std::uint32_t got = 0, type = 0;
            std::vector<std::uint8_t> buffer(pending);
            gc.RetrieveMessage(&type, buffer.data(), pending, &got);
            kinds.push_back(type & ~ProtobufMask);
            if ((type & ~ProtobufMask) == m::EGCItemMsg::k_EMsgGCItemCustomizationNotification)
            {
                FrameView view;
                ReadProtobufFrame(type, buffer, view);
                PbReader reader(view.body);
                PbField f;
                while (reader.Next(f))
                    if (f.number == 2)
                        request = f.value;
            }
        }
        Check(kinds.size() == 3 && kinds[0] == m::ESOMsg::k_ESOMsg_Create && kinds[1] == m::ESOMsg::k_ESOMsg_Update &&
                  request == 1092,
              "removing a charm creates the charm item, updates the weapon and sends RemoveKeychain");
        Check(!live->Items().Items()[0].charm && live->Items().Items().size() == 3 &&
                  live->Items().Items()[2].defIndex == DefinitionKeychain && live->Items().Items()[2].keychain == 33,
              "the charm is back in the inventory");
        gc.SendMessage(m::EGCItemMsg::k_EMsgGCApplySticker | ProtobufMask, detachFrame.data(),
                       static_cast<std::uint32_t>(detachFrame.size()));
        Check(!gc.IsMessageAvailable(&pending), "a weapon without a charm has nothing to remove");
        // Put the charm item back on the weapon for the checks that follow.
        PbWriter again2;
        again2.Varint(1, CustomItemIdBase + 4);
        again2.Varint(2, CustomItemIdBase + 1);
        WriteProtobufFrame(m::EGCItemMsg::k_EMsgGCApplySticker, {}, again2.bytes(), detachFrame);
        gc.SendMessage(m::EGCItemMsg::k_EMsgGCApplySticker | ProtobufMask, detachFrame.data(),
                       static_cast<std::uint32_t>(detachFrame.size()));
        while (gc.IsMessageAvailable(&pending))
        {
            std::uint32_t got = 0, type = 0;
            std::vector<std::uint8_t> buffer(pending);
            gc.RetrieveMessage(&type, buffer.data(), pending, &got);
        }
    }

    PbWriter again;
    again.Varint(1, CustomItemIdBase + 3);
    again.Varint(2, CustomItemIdBase + 1);
    WriteProtobufFrame(m::EGCItemMsg::k_EMsgGCApplySticker, {}, again.bytes(), frame);
    gc.SendMessage(m::EGCItemMsg::k_EMsgGCApplySticker | ProtobufMask, frame.data(), static_cast<std::uint32_t>(frame.size()));
    Check(!gc.IsMessageAvailable(&size) && live->Items().Items().size() == 2, "a weapon takes one charm");
}

void StorageUnits()
{
    namespace m = gc_msg;
    const auto schema = Schema::Load(ArmoryFixture);
    const auto shared = std::shared_ptr<const Schema>(&*schema, [](const Schema *) {});
    Inventory inventory;
    InventoryItem unit;
    unit.defIndex = DefinitionStorageUnit;
    inventory.Add(unit);
    InventoryItem skin;
    skin.defIndex = 7;
    skin.paintKitIndex = 282;
    inventory.Add(skin);
    InventoryItem unit2;
    unit2.defIndex = DefinitionStorageUnit;
    inventory.Add(unit2);
    auto live = std::make_shared<LiveInventory>(inventory);
    GcEndpointConfig config;
    config.owner = {1, 555};
    LocalGameCoordinator gc(config);
    std::mt19937_64 engine(1);
    int saves = 0;
    gc.EnableContainers(live, shared, [&] { return engine(); }, [&saves] { ++saves; });

    struct Out { std::uint32_t type{}; std::vector<std::uint8_t> body; };
    const auto drain = [&]() {
        std::vector<Out> out;
        std::uint32_t size = 0;
        while (gc.IsMessageAvailable(&size))
        {
            std::uint32_t got = 0, type = 0;
            std::vector<std::uint8_t> buffer(size);
            gc.RetrieveMessage(&type, buffer.data(), size, &got);
            FrameView view;
            ReadProtobufFrame(type, buffer, view);
            out.push_back({type & ~ProtobufMask, std::vector<std::uint8_t>(view.body.begin(), view.body.end())});
        }
        return out;
    };
    const auto send = [&](std::uint32_t type, std::uint64_t casket, std::uint64_t item) {
        PbWriter body;
        body.Varint(1, casket);
        if (item)
            body.Varint(2, item);
        std::vector<std::uint8_t> frame;
        WriteProtobufFrame(type, {}, body.bytes(), frame);
        gc.SendMessage(type | ProtobufMask, frame.data(), static_cast<std::uint32_t>(frame.size()));
    };
    const auto notificationRequest = [](const Out &out) {
        std::uint64_t request = 0;
        PbReader reader(out.body);
        PbField f;
        while (reader.Next(f))
            if (f.number == 2)
                request = f.value;
        return request;
    };
    const auto attributes = [](std::span<const std::uint8_t> econ) {
        std::map<std::uint64_t, std::uint32_t> found;
        PbReader reader(econ);
        PbField f;
        while (reader.Next(f))
            if (f.number == 12 && f.wire == 2)
            {
                PbReader inner(f.bytes);
                PbField g;
                std::uint64_t id = 0;
                std::uint32_t value = 0;
                while (inner.Next(g))
                {
                    if (g.number == 1)
                        id = g.value;
                    if (g.number == 3 && g.bytes.size() == 4)
                        value = g.bytes[0] | g.bytes[1] << 8 | g.bytes[2] << 16 | static_cast<std::uint32_t>(g.bytes[3]) << 24;
                }
                found[id] = value;
            }
        return found;
    };
    const std::uint64_t unitId = CustomItemIdBase + 1, skinId = CustomItemIdBase + 2, unit2Id = CustomItemIdBase + 3;

    // The unit always carries a count and a date, even when empty.
    const auto emptyUnit = attributes(BuildEconItem(live->Items().Items()[0], 555, unitId, ItemPositionBase));
    Check(emptyUnit.count(AttributeCasketItemsCount) && emptyUnit.at(AttributeCasketItemsCount) == 0 &&
              emptyUnit.count(AttributeCasketModificationDate),
          "an empty unit has a count and a date");

    send(m::EGCItemMsg::k_EMsgGCCasketItemAdd, unitId, skinId);
    const auto added = drain();
    Check(added.size() == 3 && added[0].type == m::ESOMsg::k_ESOMsg_Update && added[1].type == m::ESOMsg::k_ESOMsg_Update &&
              added[2].type == m::EGCItemMsg::k_EMsgGCItemCustomizationNotification &&
              notificationRequest(added[2]) == 1013,
          "a deposit updates the item and the unit, then notifies");
    const auto skinObject = DecodeSoSingleObject(added[0].body);
    const auto unitObject = DecodeSoSingleObject(added[1].body);
    const auto stored = attributes(skinObject->data);
    Check(stored.at(AttributeCasketIdLow) == static_cast<std::uint32_t>(unitId & 0xFFFFFFFFull) &&
              stored.at(AttributeCasketIdHigh) == static_cast<std::uint32_t>(unitId >> 32),
          "the stored item names its unit in two attributes");
    Check(attributes(unitObject->data).at(AttributeCasketItemsCount) == 1 && saves == 1, "the unit now counts one item");

    send(m::EGCItemMsg::k_EMsgGCCasketItemLoadContents, unitId, 0);
    const auto contents = drain();
    Check(contents.size() == 1 && notificationRequest(contents[0]) == 1012, "loading contents notifies");

    send(m::EGCItemMsg::k_EMsgGCCasketItemAdd, unit2Id, skinId); // already stored
    send(m::EGCItemMsg::k_EMsgGCCasketItemAdd, unitId, unit2Id);  // a unit inside a unit
    send(m::EGCItemMsg::k_EMsgGCCasketItemAdd, skinId, unitId);   // not a unit
    send(m::EGCItemMsg::k_EMsgGCCasketItemAdd, unitId, 424242);   // not ours
    send(m::EGCItemMsg::k_EMsgGCCasketItemExtract, unit2Id, skinId); // out of the wrong unit
    Check(drain().empty() && saves == 1, "invalid storage requests change nothing");

    const auto restored = Inventory::FromText(live->Items().ToText());
    Check(restored && restored->Items()[1].storedIn == 1 && restored->Items()[0].casketCount == 1,
          "contents survive a save and load");

    send(m::EGCItemMsg::k_EMsgGCCasketItemExtract, unitId, skinId);
    const auto removed = drain();
    Check(removed.size() == 3 && notificationRequest(removed[2]) == 1014 && saves == 2, "extracting notifies");
    const auto loose = attributes(DecodeSoSingleObject(removed[0].body)->data);
    Check(!loose.count(AttributeCasketIdLow) && live->Items().Items()[0].casketCount == 0, "the item is loose again");

    // Capacity: a unit holds MaxStorageUnitItems.
    Inventory crowded;
    crowded.Add(unit);
    for (std::uint32_t i = 0; i < MaxStorageUnitItems + 1; ++i)
        crowded.Add(skin);
    LiveInventory full(crowded);
    std::uint32_t okCount = 0;
    LiveInventory::StorageResult last{};
    for (std::uint32_t i = 0; i < MaxStorageUnitItems + 1; ++i)
    {
        last = full.StoreItem(CustomItemIdBase + 1, CustomItemIdBase + 2 + i, 1).result;
        okCount += last == LiveInventory::StorageResult::Ok;
    }
    Check(okCount == MaxStorageUnitItems && last == LiveInventory::StorageResult::Full, "a unit holds 1000 items");
}

constexpr const char *SlabFixture = R"("items_game"
{
    "items"
    {
        "1209" { "name" "sticker" }
        "1355" { "name" "keychain" }
        "7" { "name" "weapon_rifle" }
        "4000" { "name" "sticker_display_case" "attributes" { "display case keychain id" "37" }
                 "capabilities" { "can_wrap_sticker" "1" } }
        "20001" { "name" "coupon - stk_a" "loot_list_name" "coupon loot list - stk_a" }
        "20144" { "name" "coupon - crate_xray_p250" "loot_list_name" "coupon loot list - crate_xray_p250" }
        "20149" { "name" "coupon - crate_patch_pack01" "loot_list_name" "coupon loot list - crate_patch_pack01" }
        "4668" { "name" "crate_xray_p250" }
        "4610" { "name" "crate_patch_pack01" }
    }
    "sticker_kits" { "300" { "name" "stk_a" } }
    "keychain_definitions" { "37" { "name" "kc_sticker_display_case" } }
    "client_loot_lists"
    {
        "coupon loot list - stk_a" { "public_list_contents" "1" "[stk_a]sticker" "1" }
        "coupon loot list - crate_xray_p250" { "public_list_contents" "1" "crate_xray_p250" "1" }
        "coupon loot list - crate_patch_pack01" { "public_list_contents" "1" "crate_patch_pack01" "1" }
    }
})";

void SlabsScrapesAndCoupons()
{
    namespace m = gc_msg;
    const auto schema = Schema::Load(SlabFixture);
    Check(schema.has_value(), "slab fixture loads");
    Check(schema->SlabKeychainIndex(4000) == 37u && !schema->SlabKeychainIndex(7) && !schema->SlabKeychainIndex(1209),
          "only the slab names a display-case keychain");
    Check(schema->CouponEntries(20001) == std::vector<std::string>{"[stk_a]sticker"} && schema->CouponEntries(7).empty(),
          "coupon entries are read from the schema");
    const auto shared = std::shared_ptr<const Schema>(&*schema, [](const Schema *) {});

    Inventory inventory;
    InventoryItem weapon;
    weapon.defIndex = 7;
    weapon.paintKitIndex = 282;
    AppliedSticker onWeapon;
    onWeapon.slot = 3;
    onWeapon.kit = 300;
    onWeapon.wear = 0.5f;
    weapon.stickers.push_back(onWeapon);
    inventory.Add(weapon);
    InventoryItem sticker;
    sticker.defIndex = DefinitionSticker;
    sticker.stickerKit = 300;
    inventory.Add(sticker);
    InventoryItem slab;
    slab.defIndex = 4000;
    inventory.Add(slab);
    auto live = std::make_shared<LiveInventory>(inventory);

    GcEndpointConfig config;
    config.owner = {1, 555};
    LocalGameCoordinator gc(config);
    int saves = 0;
    std::mt19937_64 engine(1);
    gc.EnableLiveInventory(live, [&saves] { ++saves; });
    gc.EnableContainers(live, shared, [&] { return engine(); }, [&saves] { ++saves; });
    gc.EnableStorePurchases(live, [&](std::uint32_t def) { return schema->HasItem(def); }, [&saves] { ++saves; });

    struct Out { std::uint32_t type{}; std::vector<std::uint8_t> body; };
    const auto drain = [&]() {
        std::vector<Out> out;
        std::uint32_t size = 0;
        while (gc.IsMessageAvailable(&size))
        {
            std::uint32_t got = 0, type = 0;
            std::vector<std::uint8_t> buffer(size);
            gc.RetrieveMessage(&type, buffer.data(), size, &got);
            FrameView view;
            ReadProtobufFrame(type, buffer, view);
            out.push_back({type & ~ProtobufMask, std::vector<std::uint8_t>(view.body.begin(), view.body.end())});
        }
        return out;
    };
    const auto request = [&](std::uint32_t type, const PbWriter &body) {
        std::vector<std::uint8_t> frame;
        WriteProtobufFrame(type, {}, body.bytes(), frame);
        gc.SendMessage(type | ProtobufMask, frame.data(), static_cast<std::uint32_t>(frame.size()));
    };
    const auto noticeRequest = [](const Out &out) {
        std::uint64_t value = 0;
        PbReader reader(out.body);
        PbField f;
        while (reader.Next(f))
            if (f.number == 2)
                value = f.value;
        return value;
    };
    const std::uint64_t weaponId = CustomItemIdBase + 1, stickerId = CustomItemIdBase + 2, slabId = CustomItemIdBase + 3;

    // Scrapes: each adds a ninth of wear; past 1 the sticker goes and the game is told.
    PbWriter scrape;
    scrape.Varint(2, weaponId);
    scrape.Varint(3, 3);
    request(m::EGCItemMsg::k_EMsgGCApplySticker, scrape);
    auto out = drain();
    Check(out.size() == 1 && out[0].type == m::ESOMsg::k_ESOMsg_Update &&
              std::abs(live->Items().Items()[0].stickers[0].wear - (0.5f + 1.0f / 9.0f)) < 1e-5f,
          "a scrape raises the wear and sends one update");
    for (int i = 0; i < 4; ++i)
        request(m::EGCItemMsg::k_EMsgGCApplySticker, scrape);
    out = drain();
    Check(out.size() == 5 && live->Items().Items()[0].stickers.empty() &&
              out.back().type == m::EGCItemMsg::k_EMsgGCItemCustomizationNotification && noticeRequest(out.back()) == 1053,
          "the last scrape removes the sticker and sends RemoveSticker");
    request(m::EGCItemMsg::k_EMsgGCApplySticker, scrape);
    Check(drain().empty(), "nothing is left to scrape");

    // With a slider target the wear goes to that level; the end of the slider removes the sticker.
    {
        Inventory slider;
        InventoryItem armed;
        armed.defIndex = 7;
        AppliedSticker onSlot;
        onSlot.slot = 1;
        onSlot.kit = 300;
        onSlot.wear = 0.2f;
        armed.stickers.push_back(onSlot);
        slider.Add(armed);
        LiveInventory sliderLive(slider);
        const auto partway = sliderLive.ScrapeSticker(CustomItemIdBase + 1, 1, 0.6f);
        Check(partway && !partway->removed && std::abs(sliderLive.Items().Items()[0].stickers[0].wear - 0.6f) < 1e-6f,
              "a target sets the wear to that level");
        const auto lower = sliderLive.ScrapeSticker(CustomItemIdBase + 1, 1, 0.3f);
        Check(lower && std::abs(sliderLive.Items().Items()[0].stickers[0].wear - 0.6f) < 1e-6f,
              "scraping never lowers the wear");
        const auto gone = sliderLive.ScrapeSticker(CustomItemIdBase + 1, 1, 1.0f);
        Check(gone && gone->removed && sliderLive.Items().Items()[0].stickers.empty(), "a target of 1 removes the sticker");
        PbWriter body;
        body.Varint(2, weaponId);
        body.Varint(3, 3);
        body.Fixed32(5, std::bit_cast<std::uint32_t>(1.0f));
        body.Fixed32(11, std::bit_cast<std::uint32_t>(1.0f));
        const auto decoded = DecodeApplyStickerRequest(body.bytes());
        Check(decoded && decoded->wearTarget && *decoded->wearTarget == 1.0f, "the wear target decodes");
    }

    // Sealing a sticker in a slab: both go, one charm of keychain 37 holding the sticker comes.
    PbWriter seal;
    seal.Varint(1, stickerId);
    seal.Varint(2, slabId);
    request(m::EGCItemMsg::k_EMsgGCApplySticker, seal);
    out = drain();
    Check(out.size() == 4 && out[0].type == m::ESOMsg::k_ESOMsg_Destroy && out[1].type == m::ESOMsg::k_ESOMsg_Destroy &&
              out[2].type == m::ESOMsg::k_ESOMsg_Create && out[3].type == m::EGCItemMsg::k_EMsgGCItemCustomizationNotification &&
              noticeRequest(out[3]) == 1055,
          "sealing destroys sticker and slab, creates a charm and sends EncapsulateSticker");
    Check(live->Items().Items().size() == 2 && live->Items().Items()[1].defIndex == DefinitionKeychain &&
              live->Items().Items()[1].keychain == 37 && live->Items().Items()[1].slabSticker == 300,
          "the charm is keychain 37 with the sticker kit inside");
    const auto sealedRoundTrip = Inventory::FromText(live->Items().ToText());
    Check(sealedRoundTrip && sealedRoundTrip->Items()[1].slabSticker == 300, "a sealed slab survives a save and load");

    // Attaching the sealed slab to a weapon carries the sticker along.
    PbWriter attach;
    attach.Varint(1, CustomItemIdBase + 4);
    attach.Varint(2, weaponId);
    attach.Fixed32(8, std::bit_cast<std::uint32_t>(1.0f));
    request(m::EGCItemMsg::k_EMsgGCApplySticker, attach);
    drain();
    Check(live->Items().Items()[0].charm && live->Items().Items()[0].charm->kit == 37 &&
              live->Items().Items()[0].charm->slabSticker == 300,
          "an attached slab keeps its sticker");

    // Buying grants the guaranteed sticker/package itself, without a coupon envelope or opening the package.
    for (const std::uint32_t def : {20001u, 20144u, 20149u})
    {
        PbWriter line;
        line.Varint(1, def);
        line.Varint(2, 1);
        PbWriter init;
        init.Varint(3, 21);
        init.Message(4, line);
        request(m::EGCItemMsg::k_EMsgGCStorePurchaseInit, init);
        const auto reply = drain();
        std::uint64_t txn = 0;
        PbReader reader(reply.at(0).body);
        PbField f;
        while (reader.Next(f))
            if (f.number == 2)
                txn = f.value;
        PbWriter finalize;
        finalize.Varint(1, txn);
        request(m::EGCItemMsg::k_EMsgGCStorePurchaseFinalize, finalize);
        drain();
    }
    // A slab that an earlier build wrote a sticker onto is repaired; a weapon's stickers are not touched.
    {
        Inventory bad;
        InventoryItem brokenSlab;
        brokenSlab.defIndex = 4000;
        AppliedSticker wrong;
        wrong.slot = 0;
        wrong.kit = 9456;
        brokenSlab.stickers.push_back(wrong);
        bad.Add(brokenSlab);
        InventoryItem armed;
        armed.defIndex = 7;
        armed.stickers.push_back(wrong);
        bad.Add(armed);
        LiveInventory repairable(bad);
        Check(repairable.RepairSlabs(*schema) == 1 && repairable.Items().Items()[0].stickers.empty() &&
                  repairable.Items().Items()[1].stickers.size() == 1 && repairable.RepairSlabs(*schema) == 0,
              "a slab with a sticker written on it is repaired, a weapon is left alone");
    }
    // Something that is not a sticker can never be applied to a slab, and nothing is written onto the slab.
    {
        const std::size_t before = live->Items().Items().size();
        InventoryItem freshSlab;
        freshSlab.defIndex = 4000;
        const InventoryItem added = live->AddItem(freshSlab);
        PbWriter bogus;
        bogus.Varint(1, weaponId);
        bogus.Varint(2, CustomItemIdBase + added.id);
        request(m::EGCItemMsg::k_EMsgGCApplySticker, bogus);
        Check(drain().empty() && live->Items().Items().size() == before + 1 &&
                  live->Items().Find(added.id)->stickers.empty(),
              "a failed seal leaves the slab untouched");
        live->RemoveItem(CustomItemIdBase + added.id);
    }
    const auto &items = live->Items().Items();
    Check(items.size() == 4 && items[1].defIndex == DefinitionSticker && items[1].stickerKit == 300 &&
              items[2].defIndex == 4668 && items[3].defIndex == 4610,
          "single-item coupons grant the sticker, X-Ray P250 package and patch pack directly");
}

void ArmoryPassCapAndPersistence()
{
    namespace m = gc_msg;
    const auto schema = Schema::Load(ArmoryFixture);
    PbWriter pass;
    pass.Varint(1, 5);
    pass.Varint(2, 10);
    pass.Varint(3, 1361);
    pass.Varint(3, 1361);
    PbWriter passType;
    passType.Varint(1, XpShopTypeId);
    passType.Bytes(2, pass.bytes());
    PbWriter owner;
    owner.Varint(1, 1);
    owner.Varint(2, 555);
    PbWriter cache;
    cache.Message(2, passType);
    cache.Fixed64(3, 100);
    cache.Message(4, owner);
    PbWriter welcome;
    welcome.Varint(1, 0);
    welcome.Message(3, cache);
    auto store = std::make_shared<ReplayStore>();
    store->Set(m::EGCBaseClientMsg::k_EMsgGCClientWelcome, welcome.bytes());

    Inventory inventory;
    for (int i = 0; i < 7; ++i)
    {
        InventoryItem ticket;
        ticket.defIndex = DefinitionArmoryPass;
        inventory.Add(ticket);
    }
    auto live = std::make_shared<LiveInventory>(inventory);
    GcEndpointConfig config;
    config.owner = {1, 555};
    LocalGameCoordinator gc(config);
    gc.EnableReplay(store);
    auto armory = std::make_shared<Armory>(*schema, 11, 30);
    std::mt19937_64 engine(1);
    gc.EnableArmory(armory, live, [&] { return engine(); }, [] {});

    const auto use = [&](std::uint64_t id) {
        PbWriter body;
        body.Varint(1, id);
        std::vector<std::uint8_t> frame;
        WriteProtobufFrame(m::EGCItemMsg::k_EMsgGCUseItemRequest, {}, body.bytes(), frame);
        gc.SendMessage(m::EGCItemMsg::k_EMsgGCUseItemRequest | ProtobufMask, frame.data(), static_cast<std::uint32_t>(frame.size()));
        std::uint32_t size = 0;
        int sent = 0;
        while (gc.IsMessageAvailable(&size))
        {
            std::uint32_t got = 0, type = 0;
            std::vector<std::uint8_t> buffer(size);
            gc.RetrieveMessage(&type, buffer.data(), size, &got);
            ++sent;
        }
        return sent;
    };
    for (int i = 1; i <= 5; ++i)
        Check(use(CustomItemIdBase + i) == 3, "a pass activates (update, destroy, notification)");
    Check(use(CustomItemIdBase + 6) == 0 && live->Items().XpTracks().size() == 5 && live->Items().Items().size() == 2,
          "a sixth pass is refused and its ticket is kept");

    const auto restored = Inventory::FromText(live->Items().ToText());
    Check(restored && restored->XpTracks() == std::vector<std::uint32_t>(5, 1u), "the passes are saved with the inventory");
    Check(!Inventory::FromText("\"inventory\" { \"next_id\" \"1\" \"xp_tracks\" \"0\" \"items\" { } }") &&
              !Inventory::FromText("\"inventory\" { \"next_id\" \"1\" \"xp_tracks\" \"1 1 1 1 1 1\" \"items\" { } }"),
          "a zero-XP or sixth pass in the file is rejected");
}

constexpr const char *TradeUpFixture = R"("items_game"
{
    "rarities" { "common" { "value" "1" } "uncommon" { "value" "2" } "rare" { "value" "3" } "mythical" { "value" "4" }
                 "legendary" { "value" "5" } "ancient" { "value" "6" } }
    "prefabs" { "rifle" { "item_rarity" "common" } "weapon_case_base" { } }
    "items"
    {
        "7" { "name" "weapon_rifle" "prefab" "rifle" }
        "1209" { "name" "sticker" }
        "1355" { "name" "keychain" }
        "49" { "name" "weapon_c4" "prefab" "rifle" }
        "300" { "name" "stk" }
        "60" { "name" "test_case" "prefab" "weapon_case_base" "associated_item" "50"
                 "attributes" { "set supply crate series" { "value" "1" } } }
    }
    "sticker_kits" { "300" { "name" "stk_a" } }
    "keychain_definitions" { "17" { "name" "kc_a" } }
    "paint_kits"
    {
        "10" { "name" "k_a" "wear_remap_min" "0.0" "wear_remap_max" "0.5" }
        "11" { "name" "k_b" "wear_remap_min" "0.0" "wear_remap_max" "0.5" }
        "12" { "name" "k_c" "wear_remap_min" "0.1" "wear_remap_max" "0.8" }
        "13" { "name" "k_d" "wear_remap_min" "0.0" "wear_remap_max" "1.0" }
    }
    "paint_kits_rarity" { "k_a" "rare" "k_b" "rare" "k_c" "mythical" "k_d" "mythical" }
    "revolving_loot_lists" { "1" "case_rare" }
    "client_loot_lists" { "case_rare" { "[k_a]weapon_rifle" "1" "[k_c]weapon_rifle" "1" } }
    "item_sets"
    {
        "set_one" { "items" { "[k_a]weapon_rifle" "1" "[k_c]weapon_rifle" "1" } }
        "set_two" { "items" { "[k_b]weapon_rifle" "1" "[k_d]weapon_rifle" "1" } }
    }
})";

void TradeUps()
{
    namespace m = gc_msg;
    const auto schema = Schema::Load(TradeUpFixture);
    Check(schema.has_value() && schema->CollectionCount() == 2, "two collections load from item_sets");
    Check(schema->CollectionsOf(7, 10) == std::vector<std::string>{"set_one"} && schema->CollectionsOf(7, 99).empty() &&
              schema->CollectionSkins("set_two").size() == 2,
          "a skin knows its collections");
    std::mt19937_64 engine(11);
    const RandomSource random = [&] { return engine(); };

    const auto skin = [](std::uint32_t kit, float wear, bool statTrak = false) {
        InventoryItem item;
        item.defIndex = 7;
        item.paintKitIndex = kit;
        item.wear = wear;
        item.statTrak = statTrak;
        return item;
    };
    const auto fill = [&](Inventory &inventory, std::uint32_t kit, int count, float wear, bool statTrak = false) {
        std::vector<std::uint64_t> ids;
        for (int i = 0; i < count; ++i)
            ids.push_back(inventory.Add(skin(kit, wear, statTrak)));
        return ids;
    };

    {
        Inventory freeInputs;
        auto freeIds=fill(freeInputs,10,10,.2f);
        freeInputs.Find(freeIds[0])->noStarSale=true;
        const auto freeOutput=TradeUp(freeInputs,*schema,freeIds,[]{return 0ull;});
        Check(freeOutput.error==TradeUpError::None && freeOutput.item.noStarSale,
            "free Store inputs cannot be laundered through trade-ups into star income");
    }

    // Ten rare skins of one collection become the collection's one mythical skin, with the wear mapped.
    Inventory inventory;
    auto ids = fill(inventory, 10, 10, 0.4f);
    const auto traded = TradeUp(inventory, *schema, ids, random);
    Check(traded.error == TradeUpError::None && traded.item.paintKitIndex == 12 && traded.item.rarity == 4 &&
              traded.consumed.size() == 10 && inventory.Items().size() == 1 && inventory.Items()[0].id == traded.item.id,
          "ten skins become one of the next rarity");
    Check(std::abs(traded.item.wear - (0.1f + 0.4f * 0.7f)) < 1e-5f && traded.item.seed >= 1 && traded.item.seed <= 1000,
          "the average wear is mapped into the new finish's range");

    {
        Inventory souvenirs;
        std::vector<std::uint64_t> souvenirIds;
        for (unsigned i=0;i<10;++i)
        {
            auto input=skin(i<6?10:11,.4f);
            input.souvenir=true; input.tournamentEvent=i<6?25:24;
            input.tournamentTeam0=10; input.tournamentTeam1=20; input.tournamentPlayer=123;
            input.stickers.push_back({0,300});
            souvenirIds.push_back(souvenirs.Add(input));
        }
        const auto before=souvenirs.ToText();
        auto disabled=ParseGameplayConfig("souvenir_tradeups=0\n");
        Check(disabled.has_value(),"souvenir trade-up option parses");
        souvenirs.SetGameplay(*disabled);
        Check(TradeUp(souvenirs,*schema,souvenirIds,[]{return 0ull;}).error==TradeUpError::SouvenirDisabled &&
                  souvenirs.ToText()==before,"disabled souvenir contracts preserve every input");
        souvenirs.SetGameplay(GameplayConfig{});
        const auto output=TradeUp(souvenirs,*schema,souvenirIds,[]{return 0ull;});
        Check(output.error==TradeUpError::None && output.item.souvenir && !output.item.statTrak &&
                  !output.item.unusual && output.item.paintKitIndex==12 && output.item.rarity==4 &&
                  output.item.tournamentEvent==25 && output.item.tournamentTeam0==10 &&
                  output.item.tournamentTeam1==20 && output.item.tournamentPlayer==123 &&
                  output.item.stickers.empty() && output.consumed.size()==10 && souvenirs.Items().size()==1,
              "souvenir contract uses the winning collection and its provenance without copying applied stickers");
        Check(std::abs(output.item.wear-(.1f+.4f*.7f))<1e-5f,"souvenir wear uses normal contract mapping");
        const auto wire=DecodeItem(BuildEconItem(output.item,42,CustomItemIdBase+output.item.id,1));
        Check(wire.ok && wire.quality==QualityTournament && wire.floatBits.at(137)==25 &&
                  !wire.floatBits.contains(AttributeKillEater),"contract serializes native Souvenir quality");
        const auto saved=Inventory::FromText(souvenirs.ToText());
        Check(saved && saved->Items()[0].souvenir && saved->Items()[0].tournamentEvent==25,
              "souvenir contract output persists");
        for (const bool badTracked : {false,true})
        {
            Inventory mixed;std::vector<std::uint64_t> mixedIds;
            for (unsigned i=0;i<10;++i)
            {
                auto input=skin(10,.1f);input.souvenir=badTracked || i!=9;
                input.statTrak=badTracked && i==9;
                mixedIds.push_back(mixed.Add(input));
            }
            const auto unchanged=mixed.ToText();
            Check(TradeUp(mixed,*schema,mixedIds,[]{return 0ull;}).error==TradeUpError::MixedSouvenir &&
                      mixed.ToText()==unchanged,"mixed quality or invalid Souvenir StatTrak refuses atomically");
        }
    }

    // StatTrak probability follows the fraction of tracked inputs.
    Inventory st;
    auto stIds = fill(st, 10, 10, 0.1f, true);
    Check(TradeUp(st, *schema, stIds, random).item.statTrak, "ten StatTrak skins give a StatTrak skin");
    for (unsigned tracked = 0; tracked <= 10; ++tracked) {
        unsigned hits = 0;
        for (unsigned roll = 0; roll < 10; ++roll) {
            Inventory mixed;
            std::vector<std::uint64_t> ids;
            for (unsigned i = 0; i < 10; ++i)
                ids.push_back(mixed.Add(skin(10, .1f, i < tracked)));
            const auto result = TradeUp(mixed, *schema, ids, [roll] { return std::uint64_t{roll}; });
            Check(result.error == TradeUpError::None && result.consumed.size() == 10 && mixed.Items().size() == 1,
                  "every mix of normal and StatTrak inputs completes atomically");
            hits += result.item.statTrak;
        }
        Check(hits == tracked, "StatTrak chance exactly follows the input fraction, including zero and all");
    }

    // Hidden StatTrak on collection-only Armory skins previously made visually normal contracts fail.
    Inventory damaged;
    auto repairedIds = fill(damaged, 11, 9, 0.2f);
    repairedIds.push_back(damaged.Add(skin(11, 0.2f, true)));
    LiveInventory repaired(damaged);
    Check(schema->CanBeStatTrak(7, 10) && !schema->CanBeStatTrak(7, 11) &&
              repaired.RepairCollectionStatTrak(*schema) == 1 && repaired.RepairCollectionStatTrak(*schema) == 0,
          "only impossible collection StatTrak flags are cleared, once");
    std::vector<std::uint64_t> repairedGameIds;
    for (auto id : repairedIds)
        repairedGameIds.push_back(CustomItemIdBase + id);
    Check(repaired.TradeUp(*schema, repairedGameIds, random).error == TradeUpError::None,
          "the repaired mixed-flag contract consumes ten skins and grants its outcome");
    Inventory valid;
    valid.Add(skin(10, 0.2f, true));
    valid.Add(skin(999, 0.2f, true));
    LiveInventory preserved(valid);
    Check(preserved.RepairCollectionStatTrak(*schema) == 0 && preserved.Items().Items()[0].statTrak &&
              preserved.Items().Items()[1].statTrak, "valid case StatTrak and unknown finishes are preserved");

    // A mix of two collections lands in either, weighted by how many each supplied.
    int fromOne = 0, fromTwo = 0;
    for (int round = 0; round < 400; ++round)
    {
        Inventory mixed;
        auto mixIds = fill(mixed, 10, 7, 0.2f);   // set_one, rare
        auto twoIds = fill(mixed, 11, 3, 0.2f);   // set_two, rare
        mixIds.insert(mixIds.end(), twoIds.begin(), twoIds.end());
        const auto r = TradeUp(mixed, *schema, mixIds, random);
        Check(r.error == TradeUpError::None, "a mixed-collection contract works");
        (r.item.paintKitIndex == 12 ? fromOne : fromTwo) += 1;
    }
    Check(fromOne > 240 && fromOne < 320 && fromOne + fromTwo == 400, "outcomes follow the 7 to 3 split");
    // (set_one's mythical skin is kit 12, set_two's is kit 13.)

    // Refusals leave everything as it was.
    Inventory bad;
    auto nine = fill(bad, 10, 9, 0.1f);
    Check(TradeUp(bad, *schema, nine, random).error == TradeUpError::WrongCount, "nine items are refused");
    auto repeated = nine;
    repeated.push_back(nine[0]);
    Check(TradeUp(bad, *schema, repeated, random).error == TradeUpError::UnknownItem, "a repeated item is refused");
    auto tenth = nine;
    tenth.push_back(bad.Add(skin(12, 0.1f))); // mythical among rare
    Check(TradeUp(bad, *schema, tenth, random).error == TradeUpError::MixedRarity, "mixed rarities are refused");
    Inventory top;
    auto topIds = fill(top, 12, 10, 0.1f); // mythical, and its collection has nothing legendary above it
    Check(TradeUp(top, *schema, topIds, random).error == TradeUpError::NoOutcome && top.Items().size() == 10,
          "a collection with nothing above is refused");
    Inventory plain;
    auto plainIds = fill(plain, 0, 10, 0.0f);
    Check(TradeUp(plain, *schema, plainIds, random).error == TradeUpError::NotASkin, "items without a finish are refused");
    Check(bad.Items().size() == 10, "failed contracts removed nothing");

    // Over the endpoint: ten destroys, a create, then the old-style struct response.
    auto live = std::make_shared<LiveInventory>(Inventory{});
    std::vector<std::uint64_t> gameIds;
    for (int i = 0; i < 10; ++i)
        gameIds.push_back(CustomItemIdBase + live->AddItem(skin(10, 0.4f)).id);
    GcEndpointConfig config;
    config.owner = {1, 555};
    std::string diagnostic;
    config.diagnostic = [&](std::string_view message) { diagnostic = message; };
    LocalGameCoordinator gc(config);
    int saves = 0;
    const auto shared = std::shared_ptr<const Schema>(&*schema, [](const Schema *) {});
    gc.EnableContainers(live, shared, random, [&saves] { ++saves; });
    PbWriter craft;
    craft.Varint(1, 1);
    for (const auto id : gameIds)
        craft.Varint(2, id);
    std::vector<std::uint8_t> frame;
    WriteProtobufFrame(m::EGCItemMsg::k_EMsgGCCraft, {}, craft.bytes(), frame);
    gc.SendMessage(m::EGCItemMsg::k_EMsgGCCraft | ProtobufMask, frame.data(), static_cast<std::uint32_t>(frame.size()));
    std::vector<std::uint32_t> kinds;
    std::vector<std::uint8_t> structReply;
    std::uint32_t size = 0;
    while (gc.IsMessageAvailable(&size))
    {
        std::uint32_t got = 0, type = 0;
        std::vector<std::uint8_t> buffer(size);
        gc.RetrieveMessage(&type, buffer.data(), size, &got);
        kinds.push_back(type);
        if (type == m::EGCItemMsg::k_EMsgGCCraftResponse)
            structReply = buffer;
    }
    Check(kinds.size() == 12 && kinds[0] == (m::ESOMsg::k_ESOMsg_Destroy | ProtobufMask) &&
              kinds[10] == (m::ESOMsg::k_ESOMsg_Create | ProtobufMask) && kinds[11] == m::EGCItemMsg::k_EMsgGCCraftResponse,
          "ten destroys, one create, then the struct response (no protobuf bit)");
    Check(structReply.size() == 34 + 2 + 4 + 2 + 8 && structReply[0] == (m::EGCItemMsg::k_EMsgGCCraftResponse & 0xFF) &&
              structReply[1] == (m::EGCItemMsg::k_EMsgGCCraftResponse >> 8) && structReply[16] == 1 && structReply[17] == 0 &&
              structReply[34] == 1 && structReply[36] == 0 && structReply[40] == 1,
          "the response carries recipe 1, result OK and one item");
    Check(live->Items().Items().size() == 1 && saves == 1, "the contract is saved");

    // The shared native recipe must work even when the first selected item is StatTrak.
    for (const bool trackedFirst : {false, true})
    {
        auto mixedLive = std::make_shared<LiveInventory>(Inventory{});
        PbWriter mixedCraft;
        mixedCraft.Varint(1, 0); // An existing normal recipe; zero is a valid ID.
        for (int i = 0; i < 10; ++i)
        {
            const bool tracked = trackedFirst ? i < 3 : i >= 7;
            mixedCraft.Varint(2, CustomItemIdBase + mixedLive->AddItem(skin(10, .2f, tracked)).id);
        }
        LocalGameCoordinator mixedGc(config);
        int mixedSaves = 0;
        mixedGc.EnableContainers(mixedLive, shared, [] { return std::uint64_t{0}; }, [&] { ++mixedSaves; });
        WriteProtobufFrame(m::EGCItemMsg::k_EMsgGCCraft, {}, mixedCraft.bytes(), frame);
        mixedGc.SendMessage(m::EGCItemMsg::k_EMsgGCCraft | ProtobufMask, frame.data(),
                            static_cast<std::uint32_t>(frame.size()));
        Check(mixedLive->Items().Items().size() == 1 && mixedSaves == 1 &&
                  mixedLive->Items().Items()[0].statTrak && mixedLive->Items().Items()[0].statTrakFromContract,
              "normal native recipe accepts either first-item variant and retains the mixed StatTrak roll");
        std::vector<std::uint8_t> reply;
        while (mixedGc.IsMessageAvailable(&size))
        {
            std::uint32_t got = 0, type = 0;
            std::vector<std::uint8_t> buffer(size);
            mixedGc.RetrieveMessage(&type, buffer.data(), size, &got);
            if (type == m::EGCItemMsg::k_EMsgGCCraftResponse) reply = buffer;
        }
        Check(reply.size() == 50 && reply[34] == 0 && reply[35] == 0 && reply[36] == 0 && reply[40] == 1,
              "shared recipe zero receives a successful native Craft response with its original recipe ID");
    }

    // A refused contract still gets a (failed) struct response and changes nothing.
    PbWriter shortCraft;
    shortCraft.Varint(1, 1);
    shortCraft.Varint(2, CustomItemIdBase + 1);
    WriteProtobufFrame(m::EGCItemMsg::k_EMsgGCCraft, {}, shortCraft.bytes(), frame);
    gc.SendMessage(m::EGCItemMsg::k_EMsgGCCraft | ProtobufMask, frame.data(), static_cast<std::uint32_t>(frame.size()));
    std::uint32_t failedType = 0, failedSize = 0;
    std::vector<std::uint8_t> failed;
    if (gc.IsMessageAvailable(&failedSize))
    {
        std::uint32_t got = 0;
        failed.resize(failedSize);
        gc.RetrieveMessage(&failedType, failed.data(), failedSize, &got);
    }
    Check(failedType == m::EGCItemMsg::k_EMsgGCCraftResponse && failed.size() == 34 + 2 + 4 + 2 && failed[36] == 4,
          "a refused contract answers Invalid");
    Check(diagnostic == "trade-up: expected ten skins, or five Covert skins", "a rejection logs its actual reason without item or account IDs");

    // A built-in weapon (the C4) takes a charm: the request names the base definition, and the weapon becomes
    // an inventory item.
    Inventory fresh;
    InventoryItem charm;
    charm.defIndex = DefinitionKeychain;
    charm.keychain = 17;
    fresh.Add(charm);
    InventoryItem sticker;
    sticker.defIndex = DefinitionSticker;
    sticker.stickerKit = 300;
    fresh.Add(sticker);
    LiveInventory baseLive(fresh);
    ApplyStickerRequest onBomb;
    onBomb.stickerItemId = CustomItemIdBase + 1;
    onBomb.baseItemDefIndex = 49;
    onBomb.offsetX = 1.5f;
    const auto bombCharm = baseLive.ApplySticker(onBomb);
    Check(bombCharm && bombCharm->created && bombCharm->item.defIndex == 49 && bombCharm->item.charm &&
              bombCharm->item.charm->kit == 17 && baseLive.Items().Items().size() == 2 &&
              baseLive.Items().Items()[1].defIndex == 49,
          "a charm on a built-in weapon creates the weapon item");
    ApplyStickerRequest stickerBomb;
    stickerBomb.stickerItemId = CustomItemIdBase + 2;
    stickerBomb.baseItemDefIndex = 49;
    stickerBomb.slot = 2;
    const auto bombSticker = baseLive.ApplySticker(stickerBomb);
    Check(bombSticker && bombSticker->created && bombSticker->item.stickers.size() == 1 &&
              bombSticker->item.stickers[0].slot == 2 && baseLive.Items().Items().size() == 2,
          "a sticker on a built-in weapon does too");
    ApplyStickerRequest nothing;
    nothing.stickerItemId = CustomItemIdBase + 99;
    nothing.baseItemDefIndex = 49;
    Check(!baseLive.ApplySticker(nothing) && baseLive.Items().Items().size() == 2,
          "an unknown sticker creates nothing");
}

void SavedProgressionAndServerItems()
{
    Inventory inventory;
    Check(inventory.Progress().level == 1 && inventory.Progress().xp == 0 && inventory.Progress().rewardTotal == 0,
          "new local profiles start at level 1, zero XP");
    inventory.SetArmoryCredits(30);
    inventory.XpTracks() = {1, 1};
    Check(inventory.ApplyEarnedXp(399) && inventory.ArmoryCredits() == 32 && inventory.XpTracks()[0] == 400,
          "one XP stream advances both passes and awards one star per pass");
    Check(!inventory.ApplyEarnedXp(399) && !inventory.ApplyEarnedXp(100) && inventory.ArmoryCredits() == 32,
          "duplicate or older bridge totals never pay twice");
    auto restored = Inventory::FromText(inventory.ToText());
    Check(restored && !restored->ApplyEarnedXp(399) && restored->Progress().xp == 399,
          "the reward checkpoint and rank survive relaunch together");
    restored->ApplyEarnedXp(5001);
    Check(restored->Progress().level == 2 && restored->Progress().xp == 1, "profile levels roll over at 5000 XP");
    restored->ApplyEarnedXp(1000000);
    Check(restored->Progress().level == 40 && restored->Progress().xp == 0 && restored->ArmoryCredits() == 110 &&
              restored->XpTracks() == std::vector<std::uint32_t>({16000, 16000}),
          "passes stop at 40 stars each and profile stops at level 40");
    LiveInventory finished(*restored);
    Check(finished.AddXpTrack(1) && finished.Items().XpTracks() == std::vector<std::uint32_t>{1},
          "completed passes can be replaced by a newly activated pass");
    PbWriter recordedProfile;
    recordedProfile.Varint(1, 555);
    recordedProfile.Varint(17, 38);
    recordedProfile.Varint(18, 327680768);
    const auto patched = WithLocalProfile(recordedProfile.bytes(), LocalProgress{});
    PbReader reader(*patched);
    PbField field;
    std::map<std::uint32_t, std::uint64_t> values;
    while (reader.Next(field)) values[field.number] = field.value;
    Check(values[1] == 555 && values[17] == 1 && values[18] == 327680000,
          "recorded account rank is replaced by level 1 and native zero XP while other fields survive");

    Inventory loadout;
    InventoryItem skin;
    skin.defIndex = 7;
    skin.paintKitIndex = 282;
    skin.rarity = 6;
    const auto id = loadout.Add(skin);
    auto live = std::make_shared<LiveInventory>(loadout);
    AdjustEquipSlots equip;
    equip.slots.push_back({2, 15, CustomItemIdBase + id});
    Check(live->Adjust(equip, 555).has_value(), "server fixture equips a custom AK");
    const auto items = live->EncodedServerItems(555);
    Check(items.size() == 1, "only equipped items enter the bot server cache");
    PbReader econ(items[0]);
    bool equipped = false;
    while (econ.Next(field))
        if (field.number == 18) {
            PbReader slot(field.bytes);
            PbField inner;
            std::vector<std::uint64_t> pair;
            while (slot.Next(inner)) pair.push_back(inner.value);
            equipped = pair == std::vector<std::uint64_t>{2, 15};
        }
    Check(equipped, "server CSOEconItem carries its team and slot in equipped_state");
    GcEndpointConfig config;
    config.owner = {1, 555};
    LocalGameCoordinator server(config);
    server.EnableServerInventory(live);
    PbWriter hello;
    hello.Varint(1, 2000933);
    std::vector<std::uint8_t> frame;
    WriteProtobufFrame(gc_msg::EGCBaseClientMsg::k_EMsgGCServerHello, {}, hello.bytes(), frame);
    server.SendMessage(gc_msg::EGCBaseClientMsg::k_EMsgGCServerHello | ProtobufMask, frame.data(), static_cast<std::uint32_t>(frame.size()));
    server.RefreshServerInventory();
    std::vector<std::uint32_t> kinds;
    std::uint32_t size = 0;
    while (server.IsMessageAvailable(&size)) {
        std::uint32_t type = 0, got = 0;
        std::vector<std::uint8_t> bytes(size);
        server.RetrieveMessage(&type, bytes.data(), size, &got);
        kinds.push_back(type & ~ProtobufMask);
    }
    Check(kinds == std::vector<std::uint32_t>{4005, 24}, "bot server receives its own welcome and equipped-item cache");
    server.RefreshServerInventory();
    Check(!server.IsMessageAvailable(&size), "unchanged server inventory is not flooded repeatedly");
}

void GoldTradeUps()
{
    const auto schemaText = R"("items_game" {
        "rarities" { "common" { "value" "1" } "ancient" { "value" "6" } }
        "prefabs" { "rifle" { "item_rarity" "common" } "hands_paintable" { } }
        "items" {
            "7" { "name" "weapon_test" "prefab" "rifle" }
            "500" { "name" "weapon_bayonet" "item_class" "weapon_knife" }
            "5030" { "name" "gloves_test" "prefab" "hands_paintable" }
            "60" { "tags" { "ItemSet" { "tag_value" "set_test" } } }
        }
        "paint_kits" { "10" { "name" "red" } "20" { "name" "gold" "wear_remap_min" "0.1" "wear_remap_max" "0.5" } }
        "paint_kits_rarity" { "red" "ancient" }
        "item_sets" { "set_test" { "items" { "[red]weapon_test" "1" } } }
    })";
    auto schema = Schema::Load(schemaText);
    Check(schema && schema->LoadGoldPools("\"gold_pools\" { \"60\" { \"500:20\" \"1\" \"5030:20\" \"1\" \"500:0\" \"1\" } }"),
          "gold pools validate real definitions and finishes, including vanilla knives");
    Check(schema->GoldOutcomes("set_test", false).size() == 3 && schema->GoldOutcomes("set_test", true).size() == 2,
          "StatTrak gold outcomes exclude gloves");
    Check(!schema->LoadGoldPools("\"gold_pools\" { \"60\" { \"999:20\" \"1\" } }") &&
              schema->GoldOutcomes("set_test", false).size() == 3, "invalid catalogue does not replace working pools");
    for (bool tracked : {false, true}) {
        Inventory inv;
        std::vector<std::uint64_t> ids;
        for (int i = 0; i < 5; ++i) {
            InventoryItem item;
            item.defIndex = 7; item.paintKitIndex = 10; item.wear = .5f; item.statTrak = tracked;
            ids.push_back(inv.Add(item));
        }
        const auto result = TradeUp(inv, *schema, ids, [] { return 0ull; });
        Check(result.error == TradeUpError::None && result.item.defIndex == 500 && result.item.unusual &&
                  result.item.statTrak == tracked && inv.Items().size() == 1 && result.consumed.size() == 5 &&
                  std::abs(result.item.wear - .3f) < 1e-5f,
              "five Covert skins become a correctly flagged gold with five-input average wear");
        Check(Inventory::FromText(inv.ToText())->Items()[0].unusual, "gold quality survives saving");
    }
    for (unsigned tracked = 1; tracked < 5; ++tracked) {
        unsigned hits = 0;
        for (unsigned roll = 0; roll < 5; ++roll) {
            Inventory mixed;
            std::vector<std::uint64_t> ids;
            for (unsigned i = 0; i < 5; ++i) {
                InventoryItem item;
                item.defIndex = 7; item.paintKitIndex = 10; item.wear = .5f; item.statTrak = i < tracked;
                ids.push_back(mixed.Add(item));
            }
            const auto result = TradeUp(mixed, *schema, ids, [roll] { return std::uint64_t{roll}; });
            Check(result.error == TradeUpError::None && result.item.unusual && mixed.Items().size() == 1 &&
                      (!result.item.statTrak || schema->IsKnife(result.item.defIndex)),
                  "mixed Covert contracts complete and never put StatTrak on gloves");
            hits += result.item.statTrak;
        }
        Check(hits == tracked, "gold StatTrak chance uses the five-input fraction");
    }

    Check(schema->LoadGoldPools("\"gold_pools\" { \"60\" { \"5030:20\" \"1\" } }"), "glove-only pool loads");
    for (unsigned tracked : {1u, 5u}) {
        Inventory input;
        std::vector<std::uint64_t> ids;
        for (unsigned i = 0; i < 5; ++i) {
            InventoryItem item; item.defIndex = 7; item.paintKitIndex = 10; item.statTrak = i < tracked;
            ids.push_back(input.Add(item));
        }
        const auto old = input.ToText();
        const auto result = TradeUp(input, *schema, ids, [] { return 0ull; });
        Check(tracked == 5 ? (result.error == TradeUpError::NoOutcome && input.ToText() == old) :
                  (result.error == TradeUpError::None && !result.item.statTrak && result.item.defIndex == 5030),
              "glove-only mixed contracts stay normal; all-StatTrak refuses atomically");
    }

}

void Terminals()
{
    const auto schema = Schema::Load(R"("items_game" {
        "rarities" { "rare" { "value" "3" } }
        "prefabs" { "weapon_case_base" { } "weapon_case_selfopening_collection" { "prefab" "weapon_case_base" }
                    "volatile_pricing" { } }
        "items" {
            "5176" { "name" "crate_community_36" "prefab" "volatile_pricing weapon_case_selfopening_collection"
                     "attributes" { "set supply crate series" { "value" "273" } } }
            "7" { "name" "weapon_test" }
        }
        "paint_kits" { "10" { "name" "finish" } }
        "revolving_loot_lists" { "273" "terminal_list" }
        "client_loot_lists" { "terminal_list" { "terminal_rare" "1" } "terminal_rare" { "[finish]weapon_test" "1" } }
    })");
    Check(schema && schema->FindCrate(5176)->kind == CrateKind::Terminal, "volatile collection crate is a terminal");
    const auto shared = std::shared_ptr<const Schema>(&*schema, [](const Schema *) {});
    Inventory inventory;
    GameplayConfig twoOffers;
    twoOffers.terminal_default_offers = 2; // the offer count comes from local config
    inventory.SetGameplay(twoOffers);
    InventoryItem terminal;
    terminal.defIndex = 5176;
    inventory.Add(terminal);
    auto live = std::make_shared<LiveInventory>(inventory);
    GcEndpointConfig config;
    config.owner = {1, 555};
    LocalGameCoordinator gc(config);
    int saves = 0;
    gc.EnableContainers(live, shared, [] { return 0ull; }, [&] { ++saves; });
    gc.EnableStorePurchases(live, [](auto def) { return def == 5176; }, [&] { ++saves; });
    const auto request = [&](std::uint32_t type, const PbWriter &body) {
        std::vector<std::uint8_t> bytes;
        WriteProtobufFrame(type, {}, body.bytes(), bytes);
        gc.SendMessage(type | ProtobufMask, bytes.data(), static_cast<std::uint32_t>(bytes.size()));
    };
    const auto drain = [&] {
        std::vector<std::pair<std::uint32_t, std::vector<std::uint8_t>>> result;
        std::uint32_t size = 0;
        while (gc.IsMessageAvailable(&size)) {
            std::uint32_t type = 0, got = 0;
            std::vector<std::uint8_t> bytes(size);
            gc.RetrieveMessage(&type, bytes.data(), size, &got);
            FrameView frame;
            Check(ReadProtobufFrame(type, bytes, frame) == FrameError::None, "terminal response frame");
            result.push_back({type & ~ProtobufMask, {frame.body.begin(), frame.body.end()}});
        }
        return result;
    };
    PbWriter unseal;
    unseal.Varint(2, CustomItemIdBase + 1);
    request(gc_msg::EGCItemMsg::k_EMsgGCOpenCrate, unseal);
    auto replies = drain();
    Check(replies.size() == 2 && live->Items().Find(1)->expiration && !live->Items().Find(1)->terminalRemaining,
          "unsealing updates the terminal itself, not an ordinary crate roll");
    PbWriter next;
    next.Varint(1, CustomItemIdBase + 1);
    next.Varint(2, CustomItemIdBase + 1);
    next.Varint(4, 0);
    next.Varint(5, 99); // the laptop's "Offer limit" is a price cap and must not change the offer count
    request(gc_msg::EGCItemMsg::k_EMsgGCOpenCrate, next);
    replies = drain();
    auto offer = live->TerminalOffer(*schema, CustomItemIdBase + 1);
    Check(replies.size() == 3 && offer && offer->storedIn == 1 && offer->purchasePrice == 0u &&
              live->Items().Find(1)->terminalRemaining == 1u, "first offer stays inside the terminal until accepted");
    PbWriter loadOffer;
    loadOffer.Varint(2, CustomItemIdBase + 1);
    loadOffer.Varint(4, 1);
    const auto beforeLoad = live->Items().ToText();
    const auto savesBeforeLoad = saves;
    request(gc_msg::EGCItemMsg::k_EMsgGCVolatileItemLoadContents, loadOffer);
    replies = drain();
    Check(replies.size() == 3 && replies[0].first == 22 && replies[1].first == 22 && replies[2].first == 1090 &&
              beforeLoad == live->Items().ToText() && saves == savesBeforeLoad,
          "native 2536 reload sends saved terminal/offer and notification without reroll or save");
    PbWriter staleLoad;
    staleLoad.Varint(2, CustomItemIdBase + 1); staleLoad.Varint(4, 9);
    request(gc_msg::EGCItemMsg::k_EMsgGCVolatileItemLoadContents, staleLoad);
    Check(drain().empty() && beforeLoad == live->Items().ToText(), "stale native terminal reload is refused without mutation");
    request(gc_msg::EGCItemMsg::k_EMsgGCOpenCrate, next);
    Check(drain().empty() && live->TerminalOffer(*schema, CustomItemIdBase + 1)->id == offer->id,
          "repeating a stale offer request cannot reroll it");
    const auto restored = Inventory::FromText(live->Items().ToText());
    Check(restored && restored->Find(1)->terminalRemaining == 1u && restored->Find(offer->id)->storedIn == 1,
          "terminal offer and remaining choices survive a relaunch");
    {
        auto helperLive = std::make_shared<LiveInventory>(*restored);
        LocalGameCoordinator helperGc(config);
        helperGc.EnableContainers(helperLive, shared, [] { return 0ull; }, {});
        int helperSaves = 0;
        Check(helperGc.AcceptLocalTerminal(CustomItemIdBase + 1, [&] { ++helperSaves; }) &&
              !helperGc.AcceptLocalTerminal(CustomItemIdBase + 1, {}) && helperSaves == 1 &&
              helperLive->Items().Items().size() == 1 && !helperLive->Items().Items()[0].storedIn,
              "terminal helper accepts the saved displayed offer once, without native checkout");
    }
    PbWriter decline;
    decline.Varint(2, CustomItemIdBase + 1);
    decline.Varint(4, 1);
    request(gc_msg::EGCItemMsg::k_EMsgGCOpenCrate, decline);
    drain();
    const auto finalOffer = live->TerminalOffer(*schema, CustomItemIdBase + 1);
    Check(finalOffer && finalOffer->id != offer->id && !live->Items().Find(offer->id) &&
              live->Items().Find(1)->terminalRemaining == 0u, "declining destroys the old offer and presents the last one");
    PbWriter line;
    line.Varint(1, 5176); line.Varint(2, 1); line.Varint(5, CustomItemIdBase + 1);
    PbWriter init; init.Message(4, line);
    request(gc_msg::EGCItemMsg::k_EMsgGCStorePurchaseInit, init);
    replies = drain();
    PbReader reader(replies.at(0).second);
    PbField field;
    std::uint64_t transaction = 0;
    while (reader.Next(field)) if (field.number == 2) transaction = field.value;
    PbWriter finalize; finalize.Varint(1, transaction);
    request(gc_msg::EGCItemMsg::k_EMsgGCStorePurchaseFinalize, finalize);
    replies = drain();
    Check(replies.size() == 3 && !live->Items().Find(1) && live->Items().Items().size() == 1 &&
              live->Items().Find(finalOffer->id)->storedIn == 0 && !live->Items().Find(finalOffer->id)->purchasePrice,
          "accepting buys the displayed offer, consumes the terminal and does not reroll or grant another terminal");
    Check(live->Items().Find(finalOffer->id)->ownerCertificate, "an accepted terminal offer carries the Original Owner Certificate");
    request(gc_msg::EGCItemMsg::k_EMsgGCStorePurchaseFinalize, finalize);
    drain();
    Check(live->Items().Items().size() == 1 && saves == 4, "repeated finalize cannot duplicate a terminal reward");
}

void NativeArmorySlotsAndConsoleStars()
{
    std::string text = R"("items_game" { "items" { )";
    for (unsigned i = 0; i < 12; ++i)
        text += "\"" + std::to_string(100 + i) + "\" { \"name\" \"item_" + std::to_string(i) + "\" } ";
    text += R"(} "seasonaloperations" { "11" { "redeemable_goods" "xpshop" )";
    const std::string slots[] = {"case", "capsule", "charm", "sticker", "collection", "limited"};
    for (unsigned i = 0; i < 12; ++i)
        text += "\"operational_point_redeemable\" { \"item_name\" \"item_" + std::to_string(i) +
            "\" \"points\" \"2\" \"local_rotation_slot\" \"" + slots[i / 2] + "\" } ";
    text += "} } }";
    auto schema = Schema::Load(text);
    Check(schema && schema->ArmoryRedeemables().size() == 12, "generated native catalogue loads every row");
    GameplayConfig config;
    Check(Armory(*schema, 11, 10).RotationAt(0, config).redeemIds.size() == 11,
          "expanded default groups expose multiple goods per category");
    config.armory_case_slots = config.armory_capsule_slots = config.armory_charm_slots =
        config.armory_sticker_slots = config.armory_collection_slots = config.armory_limited_slots = 1;
    Armory armory(*schema, 11, 10);
    const auto first = armory.RotationAt(0, config), next = armory.RotationAt(900, config);
    Check(first.redeemIds.size() == 6 && next.redeemIds.size() == 6, "every category has its own active slot");
    for (const auto id : first.redeemIds)
        Check(std::find(next.redeemIds.begin(), next.redeemIds.end(), id) == next.redeemIds.end(), "each pool advances");
    armory.SetRotationOffset(1);
    Check(armory.RotationAt(0, config).redeemIds == next.redeemIds, "console force rotation advances all pools");
    auto strict = config; strict.armory_rotation_enforce = 1;
    Inventory saved; saved.SetArmoryCredits(10); saved.SetGameplay(strict);
    LiveInventory live(saved);
    RedeemRequest request; request.campaignId = 11; request.expectedCost = 2; request.redeemId = first.redeemIds[0];
    Check(armory.Redeem(request, live, [] { return 0ull; }, {}, 0).status == Armory::Status::NotInRotation &&
          live.Items().Items().empty() && armory.Balance() == 10, "with armory_rotation_enforce a stale slot rejects without spending");
    {
        // Default: the page's rotation is trusted (the GC may not see its offset), so the same purchase succeeds.
        Inventory relaxed; relaxed.SetArmoryCredits(10); relaxed.SetGameplay(config);
        LiveInventory trusting(relaxed);
        Armory other(*schema, 11, 10);
        other.SetRotationOffset(1);
        Check(other.Redeem(request, trusting, [] { return 0ull; }, {}, 0).status != Armory::Status::NotInRotation,
              "by default a tile from another rotation offset is not refused");
    }
    Check(saved.ApplyConsoleStars(100) && saved.ArmoryCredits() == 110, "test stars add to balance");
    auto restored = Inventory::FromText(saved.ToText());
    Check(restored && !restored->ApplyConsoleStars(100) && !restored->ApplyConsoleStars(99) &&
          restored->ArmoryCredits() == 110 && restored->ApplyConsoleStars(1100) && restored->ArmoryCredits() == 1110,
          "console cursor survives restart and cannot grant the same stars twice");
}

void HowlAndArmoryRotation()
{
    auto schema = Schema::Load(R"("items_game" {
      "rarities" { "common" { "value" "1" } "rare" { "value" "3" } "immortal" { "value" "7" } }
      "items" { "7" { "name" "weapon_m4a1" "item_rarity" "common" } }
      "paint_kits" { "309" { "name" "cu_m4a1_howling" "wear_remap_max" "0.4" } "10" { "name" "blue" } }
      "paint_kits_rarity" { "cu_m4a1_howling" "immortal" "blue" "rare" }
      "client_loot_lists" { "test_rare" { "[blue]weapon_m4a1" "1" } }
      "seasonaloperations" { "11" { "redeemable_goods" "xpshop"
        "operational_point_redeemable" { "item_name" "lootlist:test_rare" "points" "4" } } }
    })");
    Check(schema && schema->SkinRarity(7, 309) == 7, "Howl keeps its real Contraband rarity");
    GameplayConfig config; config.armory_rotation_slots = 1;
    Armory armory(*schema, 11, 500);
    const auto howl = armory.HowlOffer(config);
    Check(howl && howl->points == 250 && armory.RotationAt(0, config).redeemIds == std::vector<std::uint32_t>{howl->redeemId} &&
          armory.RotationAt(0, config).endsAt == 900 && armory.RotationAt(899, config).endsAt == 900 &&
          armory.RotationAt(900, config).redeemIds.front() != howl->redeemId &&
          armory.RotationAt(1800, config).redeemIds.front() == howl->redeemId,
          "Howl rotates in and out on 15-minute boundaries and returns");
    auto strict = config; strict.armory_rotation_enforce = 1;  // the default trusts the page's rotation
    Inventory saved; saved.SetGameplay(strict); saved.SetArmoryCredits(500);
    LiveInventory inventory(saved);
    RedeemRequest request; request.campaignId = 11; request.redeemId = howl->redeemId; request.expectedCost = 250;
    const auto before = inventory.Items().ToText();
    Check(armory.Redeem(request, inventory, [] { return 0ull; }, {}, 900).status == Armory::Status::NotInRotation &&
          inventory.Items().ToText() == before && armory.Balance() == 500, "expired Howl offer cannot spend stars");
    const auto bought = armory.Redeem(request, inventory, [] { return 0ull; }, {}, 0);
    Check(bought.status == Armory::Status::Ok && bought.item.paintKitIndex == 309 && bought.item.rarity == 7 &&
          !bought.item.statTrak && bought.item.ownerCertificate && bought.item.wear <= .4f && armory.Balance() == 250 && inventory.Items().ArmoryCredits() == 250u,
          "active Howl offer grants the existing skin and spends the configured stars");
    config.armory_howl_enabled = 0;
    Check(!armory.HowlOffer(config) && armory.RotationAt(0, config).redeemIds.size() == 1, "Howl can be disabled");
    Inventory contract; std::vector<std::uint64_t> ids;
    for (int i = 0; i < 5; ++i) ids.push_back(contract.Add(bought.item));
    const auto old = contract.ToText();
    Check(TradeUp(contract, *schema, ids, [] { return 0ull; }).error != TradeUpError::None && contract.ToText() == old,
          "Howl cannot be consumed as a Covert contract input");
}

void ConfiguredRewardsAndPity()
{
    Check(CaseGoldChance(0) == 26 && CaseGoldChance(8) == 26 && CaseGoldChance(9) == 135 &&
          CaseGoldChance(99) == 10000, "case pity starts on 10 and guarantees 100");
    for (unsigned n = 1; n <= 99; ++n)
        Check(CaseGoldChance(n) >= CaseGoldChance(n - 1), "pity chance is monotonic");
    auto settings = ParseGameplayConfig("armory_xp_per_star=200\nmatch_drop_count=4\npity_soft_at=5\npity_hard_at=20\n");
    Check(settings && settings->match_drop_count == 4 && PityChance(19, 26, *settings) == 10000 &&
          PityChance(3, 26, *settings) == 26 && PityChance(4, 26, *settings) > 26, "config changes real reward and pity rules");
    for (auto bad : {"unknown=1", "pity_soft_at=99\npity_hard_at=20", "stars_enabled=2", "match_skin_min_rarity=2",
                     "match_drop_count=0", "kill_xp=1\nkill_xp=2", "armory_rotation_seconds=0"})
        Check(!ParseGameplayConfig(bad), "invalid config is rejected atomically");
    Inventory progression;
    progression.XpTracks().push_back(201);
    progression.SetGameplay(*settings);
    Check(progression.XpTracks()[0] == 100 && progression.DisplayXpTracks()[0] == 200, "changing pass XP preserves pass fraction in native UI units");
    progression.ApplyEarnedXp(100);
    Check(progression.ArmoryCredits() == 1u && progression.DisplayXpTracks()[0] == 400 && progression.Progress().xp == 100,
          "configured pass XP awards a star and native display matches");
    auto reloadedProgress = Inventory::FromText(progression.ToText());
    Check(reloadedProgress && reloadedProgress->DisplayXpTracks()[0] == 400, "pass XP unit survives relaunch");
    settings->stars_enabled = 0; settings->xp_enabled = 0;
    progression.SetGameplay(*settings); progression.ApplyEarnedXp(300);
    Check(progression.Progress().xp == 100 && progression.ArmoryCredits() == 1u, "profile and star switches consume cursor without paying");

    auto schema = Schema::Load(R"("items_game" {
      "rarities" { "common" { "value" "1" } "rare" { "value" "3" } "ancient" { "value" "6" } }
      "prefabs" { "rifle" { "item_rarity" "common" } "hands_paintable" { }
        "weapon_case_base" { } "weapon_case" { "prefab" "weapon_case_base" "associated_item" "50" }
        "volatile_pricing" { } "weapon_case_selfopening_collection" { "prefab" "weapon_case_base" } }
      "items" {
        "7" { "name" "weapon_test" "prefab" "rifle" }
        "50" { "name" "key" } "51" { "name" "wrong_key" }
        "500" { "name" "weapon_bayonet" "item_class" "weapon_knife" }
        "5030" { "name" "gloves_test" "prefab" "hands_paintable" }
        "60" { "name" "case_test" "prefab" "weapon_case" "tags" { "ItemSet" { "tag_value" "set_test" } }
          "attributes" { "set supply crate series" { "value" "1" } } }
        "5176" { "name" "terminal_test" "prefab" "volatile_pricing weapon_case_selfopening_collection"
          "attributes" { "set supply crate series" { "value" "1" } } }
        "5181" { "name" "terminal_gold" "prefab" "volatile_pricing weapon_case_selfopening_collection"
          "tags" { "ItemSet" { "tag_value" "set_test" } }
          "attributes" { "set supply crate series" { "value" "1" } } }
        "61" { "name" "case_gloves" "prefab" "weapon_case" "attributes" { "set supply crate series" { "value" "2" } } }
      }
      "paint_kits" { "10" { "name" "blue" } "11" { "name" "red" } "20" { "name" "gold" } }
      "paint_kits_rarity" { "blue" "rare" "red" "ancient" "gold" "ancient" }
      "item_sets" { "set_timed_drops_test" { "items" { "[blue]weapon_test" "1" "[red]weapon_test" "1" } } }
      "revolving_loot_lists" { "1" "rewards" "2" "gloves_only" }
      "client_loot_lists" { "rewards" { "rewards_rare" "1" "rewards_ancient" "1" } "gloves_only" { "gloves_only_ancient" "1" }
        "gloves_only_ancient" { "[gold]gloves_test" "1" }
        "rewards_rare" { "[blue]weapon_test" "1" } "rewards_ancient" { "[red]weapon_test" "1" } }
    })");
    Check(schema && schema->LoadGoldPools("\"gold_pools\" { \"60\" { \"5030:20\" \"1\" } }"), "pity fixture validated");
    Inventory inv;
    inv.SetCasePity(99); inv.SetTerminalPity(5176, 99); inv.SetTerminalPity(5181, 99);
    const auto crate = inv.Add({0, 60}), key = inv.Add({0, 50}), wrong = inv.Add({0, 51});
    Check(OpenCase(inv, *schema, crate, wrong, [] { return 9999ull; }).error == OpenError::WrongKey && inv.CasePity() == 99,
          "bad opens do not advance pity");
    auto restored = Inventory::FromText(inv.ToText());
    Check(restored && restored->CasePity() == 99 && restored->TerminalPity(5176) == 99 && restored->TerminalPity(5181) == 99,
          "separate case and terminal pity counters persist");
    const auto gold = OpenCase(*restored, *schema, crate, key, [] { return 9999ull; });
    Check(gold.error == OpenError::None && gold.item.unusual && gold.item.defIndex == 5030 && !gold.item.statTrak && restored->CasePity() == 0,
          "100th eligible case guarantees real gold and resets without StatTrak gloves");
    {
        Inventory gloveInventory;
        const auto gloveCase = gloveInventory.Add({0, 61}), gloveKey = gloveInventory.Add({0, 50});
        const auto glove = OpenCase(gloveInventory, *schema, gloveCase, gloveKey, [] { return 0ull; });
        Check(glove.error == OpenError::None && glove.item.defIndex == 5030 && glove.item.unusual && !glove.item.statTrak,
              "a glove in a case's own loot list (the Gauntlet Case) is a gold item");
    }
    for (auto def : {5176u, 5181u}) restored->Add({0, def});
    LiveInventory terminals(*restored);
    const auto terminalId = [&](auto def) {
        for (const auto &item : terminals.Items().Items()) if (item.defIndex == def) return CustomItemIdBase + item.id;
        return std::uint64_t{0};
    };
    for (auto def : {5176u, 5181u}) {
        OpenCrateRequest request;
        request.crateItemId = terminalId(def);
        Check(terminals.AdvanceTerminal(*schema, request, [] { return 9999ull; }, 100).has_value(), "terminal unseals");
        Check(terminals.Items().TerminalPity(def) == 99, "unseal does not count as an offer");
        request.pointsRemaining = 0;
        const auto offer = terminals.AdvanceTerminal(*schema, request, [] { return 9999ull; }, 100);
        Check(offer && offer->offer && offer->offer->rarity == 6 && terminals.Items().TerminalPity(def) == 0 &&
              (def != 5181 || (offer->offer->unusual && !offer->offer->statTrak)), "100th terminal offer guarantees its top reward");
        const auto before = terminals.Items().ToText();
        Check(!terminals.AdvanceTerminal(*schema, request, [] { return 0ull; }, 100) && before == terminals.Items().ToText(),
              "stale terminal request cannot advance pity or change offer");
    }
    Check(terminals.Items().CasePity() == 0, "terminal pity does not touch case pity");
    std::mt19937_64 engine(951);
    std::size_t caseDrops = 0, skinDrops = 0;
    for (unsigned n = 0; n < 1000; ++n) {
        const auto drops = RollMatchDrops(*schema, [&] { return engine(); });
        Check(drops && drops->size() == 3, "every completed match produces exactly three drops");
        for (const auto &drop : *drops) {
            if (!drop.paintKitIndex) { ++caseDrops; Check(drop.defIndex == 60 || drop.defIndex == 61, "only keyed cases in case reward pool"); }
            else { ++skinDrops; Check(drop.rarity >= 3 && drop.rarity <= 6 && !drop.unusual && !drop.statTrak, "weapon rewards blue and above, no golds"); }
        }
    }
    Check(caseDrops > 1400 && caseDrops < 1600 && caseDrops + skinDrops == 3000, "independent case/weapon split is 50 percent");
    Inventory direct; GameplayConfig directConfig; directConfig.care_packages_enabled=0; direct.SetGameplay(directConfig);
    LiveInventory rewards(direct);
    Check(rewards.GrantMatchRewards(*schema, 1, [&] { return engine(); })->size() == 3 &&
          !rewards.GrantMatchRewards(*schema, 1, [&] { return engine(); }), "duplicate completion grants nothing");
    auto savedRewards = Inventory::FromText(rewards.Items().ToText());
    Check(savedRewards && savedRewards->MatchRewardTotal() == 1, "completion cursor and three items save together");
    LocalGameCoordinator endpoint({});
    auto live = std::make_shared<LiveInventory>(direct);
    auto shared = std::shared_ptr<const Schema>(&*schema, [](const Schema *) {});
    endpoint.EnableContainers(live, shared, [&] { return engine(); }, {});
    int saves = 0;
    Check(endpoint.ApplyMatchRewards(1, [&] { ++saves; }) && !endpoint.ApplyMatchRewards(1, {}), "endpoint grants a completion once");
    std::vector<std::uint32_t> types;
    std::uint32_t size = 0;
    while (endpoint.IsMessageAvailable(&size)) {
        std::vector<std::uint8_t> bytes(size); std::uint32_t type = 0, got = 0;
        endpoint.RetrieveMessage(&type, bytes.data(), size, &got); types.push_back(type & ~ProtobufMask);
    }
    // A dropped case also brings its free key (free_case_keys), created after the drop notifications.
    const bool droppedCase = std::any_of(live->Items().Items().begin(), live->Items().Items().end(),
                                         [](const InventoryItem &item) { return item.defIndex == 60; });
    auto expectedTypes = std::vector<std::uint32_t>{21, 9137, 21, 9137, 21, 9137};
    (void)droppedCase; // Free openings no longer generate a matching key.
    Check(types == expectedTypes && saves == 1, "native match drop notifications follow each created item and save once");
    Inventory levelInventory;
    GameplayConfig levelConfig;
    levelConfig.match_drops_enabled = 0;
    levelConfig.care_packages_enabled = 0;
    levelInventory.SetGameplay(levelConfig);
    LiveInventory levels(levelInventory);
    Check(!levels.GrantLevelRewards(*schema, [&] { return engine(); }), "starting level 1 has no free level reward");
    levels.ApplyEarnedXp(2 * ProfileLevelXp);
    Check(levels.Items().Progress().level == 3 && levels.GrantLevelRewards(*schema, [&] { return engine(); })->size() == 3,
          "level 2 grants three rewards even with match drops disabled");
    auto pending = Inventory::FromText(levels.Items().ToText());
    Check(pending && pending->LevelRewardTotal() == 1, "level reward cursor persists alongside its granted items");
    pending->SetGameplay(levelConfig);
    LiveInventory resumed(*pending);
    Check(resumed.GrantLevelRewards(*schema, [&] { return engine(); })->size() == 3 &&
              !resumed.GrantLevelRewards(*schema, [&] { return engine(); }) && resumed.Items().Items().size() == 6,
          "a second earned level survives restart and pays once without any weekly timer");
    resumed.ApplyEarnedXp(2 * ProfileLevelXp);
    Check(!resumed.GrantLevelRewards(*schema, [&] { return engine(); }), "replaying XP does not duplicate level drops");
    const std::string token(32, 'a');
    Check(DecodeLocalTradeUpRequest(token + " 1 2 3 4 5").has_value() &&
          !DecodeLocalTradeUpRequest(token + " 1 2 3 4") && !DecodeLocalTradeUpRequest(token + " 1 2 3 4 5 ") &&
          !DecodeLocalTradeUpRequest(token + " 1 2 3 4 18446744073709551616"), "helper request count, trailing data and overflow validated");
}

void NativePremier()
{
    const auto fields = [](std::span<const std::uint8_t> body) {
        std::map<std::uint32_t, std::uint64_t> result;
        PbReader reader(body); PbField field;
        while (reader.Next(field)) if (field.wire == 0) result[field.number] = field.value;
        Check(!reader.Failed(), "Premier protobuf parses");
        return result;
    };
    for (const auto wins : {0u, 1u, 9u, 10u})
    {
        const auto rank = fields(EncodePremierRank({4000, wins, 10}, 555));
        Check(rank.at(1) == 555 && rank.at(2) == (wins >= 10 ? 4000 : 0) && rank.at(3) == wins && rank.at(6) == 11,
              "native Premier type11 publishes exact placement wins while hiding rating until ten wins");
    }
    PbWriter wingman; wingman.Varint(2, 5); wingman.Varint(6, 7);
    PbWriter stale; stale.Bytes(1, EncodePremierRank({9000, 99, 10}, 999)); stale.Message(1, wingman); stale.Varint(30, 42);
    const auto changed = WithPremierRankUpdate(stale.bytes(), {1300, 1, 10}, 555);
    Check(changed.has_value(), "recorded rank update patches");
    PbReader reader(*changed); PbField field;
    int premierCount = 0, wingmanCount = 0;
    while (reader.Next(field)) if (field.number == 1) {
        const auto rank = fields(field.bytes);
        if (rank.at(6) == 11) { ++premierCount; Check(rank.at(3) == 1 && rank.at(2) == 0 && rank.at(1) == 555, "recorded Premier replaced"); }
        if (rank.at(6) == 7) ++wingmanCount;
    }
    Check(premierCount == 1 && wingmanCount == 1, "other native rank types retained without duplicate Premier entries");
    PbWriter oldProfile; oldProfile.Bytes(20, EncodePremierRank({9000, 99, 10}, 999)); oldProfile.Message(20, wingman);
    const LocalPremier current{1300, 1, 10};
    const auto profile = WithLocalProfile(oldProfile.bytes(), {}, &current, 555);
    Check(profile.has_value(), "welcome/profile placement count patches");
    PbReader profileReader(*profile); premierCount = 0;
    while (profileReader.Next(field)) if (field.number == 20) {
        const auto rank = fields(field.bytes);
        if (rank.at(6) == 11) { ++premierCount; Check(rank.at(3) == 1, "XP profile update cannot restore stale placement wins"); }
    }
    Check(premierCount == 1, "one local Premier ranking in profile");
    GcEndpointConfig config; config.owner = {1, 555};
    LocalGameCoordinator gc(config);
    gc.EnableLocalPremier({1000, 0, 10});
    Check(gc.SetLocalPremier(current) && !gc.SetLocalPremier(current) && !gc.SetLocalPremier({100000, 1, 10}),
          "native rank cache updates only on valid changes");
    std::uint32_t size = 0, type = 0, got = 0;
    Check(gc.IsMessageAvailable(&size), "saved placement change queues a native rank event");
    std::vector<std::uint8_t> bytes(size); gc.RetrieveMessage(&type, bytes.data(), size, &got);
    Check((type & ~ProtobufMask) == gc_msg::ECsgoGCMsg::k_EMsgGCCStrike15_v2_ClientGCRankUpdate,
          "native rank event uses the captured 9194 message");
}

void WeeklyPoolAndItemSales()
{
    auto schema = Schema::Load(R"("items_game" {
      "rarities" { "common" { "value" "1" } "rare" { "value" "3" } "ancient" { "value" "6" } }
      "prefabs" { "weapon_case_base" {} "weapon_case" { "prefab" "weapon_case_base" "associated_item" "50" }
        "operator" { "flexible_loadout_category" "customplayer" "item_quality" "unique" "model_player" "official.vmdl" } }
      "items" { "7" { "name" "weapon_test" "item_rarity" "common" } "8" { "name" "weapon_knife_test" "item_class" "weapon_knife" }
        "50" { "name" "key" } "60" { "name" "crate_test" "prefab" "weapon_case"
          "attributes" { "set supply crate series" { "value" "1" } } }
        "100" { "name" "customplayer_test" "prefab" "operator" }
        "1209" { "name" "sticker" } "1355" { "name" "keychain" } "1201" { "name" "coupon_test" } }
      "paint_kits" { "10" { "name" "weekly_blue" } "11" { "name" "case_blue" } "12" { "name" "weekly_grey" } }
      "paint_kits_rarity" { "weekly_blue" "rare" "case_blue" "rare" "weekly_grey" "common" }
      "item_sets" { "set_timed_drops_test" { "items" { "[weekly_blue]weapon_test" "1" "[weekly_grey]weapon_test" "1" } }
        "set_case_test" { "items" { "[case_blue]weapon_test" "1" } } }
      "client_loot_lists" { "case_list" { "[case_blue]weapon_test" "1" } }
      "revolving_loot_lists" { "1" "case_list" }
      "seasonaloperations" { "11" { "redeemable_goods" "xpshop"
        "operational_point_redeemable" { "item_name" "lootlist:case_list" "points" "4" "local_rotation_slot" "limited" } } }
    })");
    Check(schema && schema->AgentDefinitions() == std::vector<std::uint32_t>{100}, "only official eligible agents resolve");
    const auto weekly = schema->MatchRewardSkins();
    Check(weekly.size() == 1 && weekly[0].paintKitIndex == 10 && schema->MatchRewardSkins(false).size() == 2,
          "weekly-only pool excludes case collections and below-blue weekly finishes");
    GameplayConfig config;
    config.match_case_percent = 0;
    for (unsigned i = 0; i < 20; ++i) {
        const auto drops = RollMatchDrops(*schema, [i] { return std::uint64_t{i}; }, config);
        Check(drops && drops->size() == 3 && (*drops)[0].paintKitIndex == 10,
              "all-weapon rewards draw from the non-case weekly pool");
    }
    InventoryItem skin; skin.defIndex = 7; skin.paintKitIndex = 10; skin.rarity = 3; skin.wear=.2f;
    Check(ItemSaleValue(*schema, config, skin) == 5, "OfflineCS blue sale price");
    auto freeSkin=skin;freeSkin.noStarSale=true;
    Check(ItemSaleValue(*schema,config,freeSkin)==0,"free Store items cannot create star income");
    Inventory freeSaved;freeSkin.charm=AppliedKeychain{1,0,0,0,0,true};
    const auto freeId=freeSaved.Add(freeSkin);
    const auto freeRestored=Inventory::FromText(freeSaved.ToText());
    Check(freeRestored && freeRestored->Find(freeId)->noStarSale && freeRestored->Find(freeId)->charm->noStarSale,
        "free origin and attached charm origin persist across restart");
    const auto freeWire=DecodeItem(BuildEconItem(freeSkin,42,CustomItemIdBase+freeId,1));
    Check(freeWire.floatBits.at(2)==1,"native cannot-trade attribute hides star sale for free Store items");
    skin.wear=.01f;const auto fn=ItemSaleValue(*schema,config,skin);
    skin.wear=.10f;const auto mw=ItemSaleValue(*schema,config,skin);
    skin.wear=.4f;const auto ww=ItemSaleValue(*schema,config,skin);
    skin.wear=.7f;const auto bs=ItemSaleValue(*schema,config,skin);
    Check(fn==6 && mw==5 && ww==4 && bs==3,"wear-adjusted sale prices retain integer stars and exterior ordering");
    skin.wear=.2f;
    auto limited=skin;limited.paintKitIndex=11;limited.wear=.01f;
    Check(ItemSaleValue(*schema,config,limited)==3,"guaranteed fixed skin resale stays below its purchase cost");
    InventoryItem charm;charm.defIndex=1355;charm.keychain=1;charm.rarity=3;
    Check(ItemSaleValue(*schema,config,charm)==1,"blue charm sells for one star rather than a skin-derived price");
    auto inflated=config;inflated.sell_charm_mil_spec=999;
    Check(ItemSaleValue(*schema,inflated,charm)==2,"blue charm config cannot exceed its three-star purchase price");
    charm.rarity=6;Check(ItemSaleValue(*schema,config,charm)==25,"rare charms may sell for more than their random purchase cost");
    skin.statTrak = true;
    Check(ItemSaleValue(*schema, config, skin) == 5, "StatTrak has the same OfflineCS base sale value");
    InventoryItem agent; agent.defIndex = 100;
    Check(ItemSaleValue(*schema, config, agent) == 25, "agent buyback uses half of configured price");
    InventoryItem sticker; sticker.defIndex = 1209; sticker.stickerKit = 1; sticker.rarity = 6;
    Check(ItemSaleValue(*schema, config, sticker) == 25, "sticker buyback uses half of rarity price");
    InventoryItem crate; crate.defIndex = 60;
    Check(ItemSaleValue(*schema, config, crate) == 1, "containers use percentage with minimum one star");
    InventoryItem knife = skin; knife.defIndex = 8;
    Check(ItemSaleValue(*schema, config, knife) == 72, "knife and glove sale price default (72)");
    skin.storedIn = 8;
    Check(ItemSaleValue(*schema, config, skin) == 0, "stored items cannot be sold separately");
    skin.storedIn = 0;
    Inventory saved; saved.SetArmoryCredits(7); saved.SetGameplay(config);
    const auto id = saved.Add(skin);
    saved.Loadout().push_back({2, 15, CustomItemIdBase + id, 7});
    auto live = std::make_shared<LiveInventory>(saved);
    auto shared = std::shared_ptr<const Schema>(&*schema, [](const Schema *) {});
    LocalGameCoordinator endpoint({}); int saves = 0;
    endpoint.EnableContainers(live, shared, [] { return 0ull; }, [&] { ++saves; });
    const auto send = [&](const PbWriter &body) {
        std::vector<std::uint8_t> bytes;
        WriteProtobufFrame(gc_msg::EGCItemMsg::k_EMsgGCDelete, {}, body.bytes(), bytes);
        endpoint.SendMessage(gc_msg::EGCItemMsg::k_EMsgGCDelete | ProtobufMask, bytes.data(), bytes.size());
    };
    PbWriter malformed; malformed.Varint(1, CustomItemIdBase + id); malformed.Varint(2, 50);
    send(malformed);
    Check(live->Items().Find(id) && live->Items().ArmoryCredits() == 7 && saves == 0, "malformed sale cannot remove or pay");
    PbWriter sale; sale.Varint(1, CustomItemIdBase + id);
    send(sale); send(sale);
    Check(!live->Items().Find(id) && live->Items().Loadout().empty() && live->Items().ArmoryCredits() == 12 && saves == 1,
          "native sale removes item and loadout, credits once and saves atomically");
    auto restored = Inventory::FromText(live->Items().ToText());
    Check(restored && restored->ArmoryCredits() == 12 && restored->Items().empty(), "sale balance and inventory survive restart");
    const auto overflowItem = live->AddItem(skin);
    live->SetArmoryCredits(UINT32_MAX);
    PbWriter overflow; overflow.Varint(1, CustomItemIdBase + overflowItem.id); send(overflow);
    Check(live->Items().Find(overflowItem.id) && saves == 1, "overflow sale retains item");
}

void MusicKitsAndCouponMigration()
{
    auto schema = Schema::Load(R"("items_game" {
      "rarities" { "rare" { "value" "3" } }
      "prefabs" { "weapon_case_base" {} "musickit_prefab" { "item_rarity" "rare" } }
      "items" { "1314" { "name" "musickit" "prefab" "musickit_prefab" }
        "88" { "name" "musickit_fixed" "prefab" "musickit_prefab" "attributes" { "music id" "42" } }
        "1209" { "name" "sticker" "item_rarity" "rare" }
        "20037" { "name" "coupon - sticker" "loot_list_name" "coupon loot list sticker" }
        "20038" { "name" "coupon - music" "loot_list_name" "coupon loot list music" "will_produce_stattrak" "1" }
        "60" { "name" "crate_musickit_test_capsule" "prefab" "weapon_case_base"
          "attributes" { "set supply crate series" { "value" "1" } } }
        "61" { "name" "crate_musickit_test_stattrak_capsule" "prefab" "weapon_case_base"
          "attributes" { "set supply crate series" { "value" "2" } } } }
      "music_definitions" { "42" { "name" "test_music" } }
      "sticker_kits" { "260" { "name" "test_sticker" } }
      "client_loot_lists" {
        "music_flat" { "[test_music]musickit" "1" }
        "music_stattrak" { "will_produce_stattrak" "1" "music_flat" "1" }
        "coupon loot list music" { "public_list_contents" "1" "[test_music]musickit" "1" }
        "coupon loot list sticker" { "public_list_contents" "1" "[test_sticker]sticker" "1" } }
      "revolving_loot_lists" { "1" "music_flat" "2" "music_stattrak" }
    })");
    Check(schema.has_value(), "music schema loads");
    Inventory saved;
    const auto normal = saved.Add({0,60}), tracked = saved.Add({0,61});
    const auto opened = OpenCase(saved,*schema,normal,0,[]{return 0ull;});
    Check(opened.error == OpenError::None && opened.item.musicKit == 42 && !opened.item.statTrak,
          "keyless flat music list grants a playable kit with its music id");
    const auto stat = OpenCase(saved,*schema,tracked,0,[]{return 0ull;});
    Check(stat.error == OpenError::None && stat.item.musicKit == 42 && stat.item.statTrak,
          "StatTrak music capsules guarantee StatTrak rather than a weapon roll");
    saved.Add({0,20037}); saved.Add({0,20038});
    const auto fixedKit = saved.Add({0,88});
    LiveInventory live(saved);
    Check(live.RepairStoreCoupons(*schema) == 3 && live.RepairStoreCoupons(*schema) == 0,
          "existing guaranteed envelopes convert once without granting duplicates");
    bool sticker = false, music = false;
    for (const auto &item : live.Items().Items()) {
        sticker |= item.stickerKit == 260;
        music |= item.musicKit == 42 && item.statTrak;
    }
    Check(sticker && music && live.Items().Find(fixedKit)->musicKit == 42, "converted offers include stickers, StatTrak music and fixed music definitions");
    const auto restored = Inventory::FromText(live.Items().ToText());
    Check(restored && restored->Find(stat.item.id)->musicKit == 42 && restored->Find(stat.item.id)->statTrak,
          "music id and StatTrak survive a save and restart");
    // Build owns the payload for the duration of parsing.
    const auto encoded = BuildEconItem(stat.item,555,CustomItemIdBase+stat.item.id,1000);
    PbReader reader(encoded); PbField field; bool musicAttribute = false;
    while (reader.Next(field)) if (field.number == 12 && field.wire == 2) {
        PbReader inner(field.bytes); PbField attribute;
        while(inner.Next(attribute)) if(attribute.number == 1 && attribute.value == 166) musicAttribute = true;
    }
    Check(musicAttribute,"native econ item carries the schema music id attribute");
}

void ArmoryTerminals()
{
    auto schema = Schema::Load(R"("items_game" {
      "prefabs" { "weapon_case_base" {} "volatile_pricing" {}
        "weapon_case_selfopening_collection" { "prefab" "weapon_case_base" } }
      "items" {
        "77" { "name" "crate_terminal_a" "prefab" "volatile_pricing weapon_case_selfopening_collection"
          "attributes" { "set supply crate series" { "value" "1" } } }
        "78" { "name" "crate_terminal_b" "prefab" "volatile_pricing weapon_case_selfopening_collection"
          "attributes" { "set supply crate series" { "value" "2" } } } }
      "seasonaloperations" { "11" { "redeemable_goods" "xpshop"
        "operational_point_redeemable" { "item_name" "crate_terminal_a" "points" "2" "local_rotation_slot" "terminal" }
        "operational_point_redeemable" { "item_name" "crate_terminal_b" "points" "2" "local_rotation_slot" "terminal" } } }
    })");
    Check(schema && schema->FindCrate(77)->kind == CrateKind::Terminal,"Armory fixture uses real terminal definitions");
    GameplayConfig config; Armory shop(*schema,11,10);
    const auto first=shop.RotationAt(0,config), next=shop.RotationAt(900,config);
    Check(first.redeemIds.size()==1 && next.redeemIds.size()==1 && first.redeemIds!=next.redeemIds,
          "dedicated terminal slot rotates independently");
    Inventory saved; saved.SetGameplay(config); saved.SetArmoryCredits(10); LiveInventory live(saved);
    RedeemRequest request; request.campaignId=11;request.expectedCost=2;request.redeemId=first.redeemIds[0];
    const auto bought=shop.Redeem(request,live,[]{return 0ull;},{},0);
    Check(bought.status==Armory::Status::Ok && bought.item.defIndex==77 && !bought.item.expiration &&
          !bought.item.terminalRemaining && live.Items().ArmoryCredits()==8,
          "two stars buy an unopened terminal rather than an offer or weapon");
    OpenCrateRequest open; open.crateItemId=CustomItemIdBase+bought.item.id;
    Check(live.AdvanceTerminal(*schema,open,[]{return 0ull;},100).has_value(),
          "Armory terminal follows the existing native unseal path");
    config.terminals_enabled=0;
    Check(shop.RotationAt(0,config).redeemIds.empty(),"disabled terminals disappear from Armory rotation");
}

void SouvenirPackagesAndHandwraps()
{
    const auto schema = Schema::Load(R"("items_game" {
      "prefabs" {
        "weapon_case_base" {} "weapon_case_souvenirpkg" { "prefab" "weapon_case_base" }
        "event_package" { "prefab" "weapon_case_souvenirpkg" "attributes" { "tournament event id" { "value" "25" } } }
        "hands_paintable" {} }
      "rarities" { "common" { "value" "1" } "rare" { "value" "3" } "ancient" { "value" "6" } }
      "items" {
        "7" { "name" "weapon_test" "item_rarity" "rare" }
        "5032" { "name" "leather_handwraps" "prefab" "hands_paintable" }
        "60" { "name" "crate_test2025_promo_de_test" "prefab" "event_package"
          "attributes" { "set supply crate series" { "value" "1" } } }
        "61" { "name" "crate_empty" "prefab" "event_package"
          "attributes" { "set supply crate series" { "value" "2" } } }
        "62" { "name" "crate_signature_promo_unknown" "prefab" "event_package"
          "attributes" { "set supply crate series" { "value" "1" } } } }
      "paint_kits" { "10" { "name" "blue" "wear_remap_min" "0.1" "wear_remap_max" "0.2" } }
      "paint_kits_rarity" { "blue" "common" }
      "item_sets" { "set_test" { "items" { "[blue]weapon_test" "1" } } }
      "sticker_kits" {
        "1" { "name" "event_org_gold" "tournament_event_id" "25" "tournament_team_id" "0" }
        "2" { "name" "event_a_gold" "tournament_event_id" "25" "tournament_team_id" "10" }
        "3" { "name" "event_b_gold" "tournament_event_id" "25" "tournament_team_id" "20" }
        "4" { "name" "event_a_signature_gold" "tournament_event_id" "25" "tournament_team_id" "10" "tournament_player_id" "123" }
        "5" { "name" "de_test_gold" }
        "6" { "name" "another_event_gold" "tournament_event_id" "24" "tournament_team_id" "30" }
        "7" { "name" "event_a_paper" "tournament_event_id" "25" "tournament_team_id" "10" } }
      "revolving_loot_lists" { "1" "souvenir_loot" "2" "missing" }
      "client_loot_lists" { "souvenir_loot" { "set_test_common" "1" "match_highlight_reel_keychain" "kc_test" }
        "set_test_common" { "[blue]weapon_test" "1" } }
      "seasonaloperations" { "11" { "redeemable_goods" "xpshop"
        "operational_point_redeemable" { "item_name" "crate_test2025_promo_de_test" "points" "5" "local_rotation_slot" "souvenir" }
        "operational_point_redeemable" { "item_name" "crate_signature_promo_unknown" "points" "5" "local_rotation_slot" "souvenir" } } }
    })");
    Check(schema && schema->FindCrate(60)->kind == CrateKind::Souvenir && schema->FindCrate(60)->keyDefIndex == 0 &&
          schema->FindCrate(60)->tournamentEvent == 25, "souvenir series and inherited event coexist");
    {
        auto pitySchemaText=std::string(R"("items_game" {
          "rarities" { "rare" { "value" "3" } "ancient" { "value" "6" } }
          "prefabs" { "weapon_case_souvenirpkg" { "prefab" "weapon_case_base" } "weapon_case_base" {} }
          "items" { "7" { "name" "weapon_test" } "60" { "name" "crate_promo_test" "prefab" "weapon_case_souvenirpkg"
            "attributes" { "set supply crate series" { "value" "1" } "tournament event id" { "value" "25" } } } }
          "paint_kits" { "10" { "name" "blue" } "11" { "name" "red" } }
          "paint_kits_rarity" { "blue" "rare" "red" "ancient" }
          "revolving_loot_lists" { "1" "pool" }
          "client_loot_lists" { "pool" { "pool_rare" "1" "pool_ancient" "1" } "pool_rare" { "[blue]weapon_test" "1" } "pool_ancient" { "[red]weapon_test" "1" } }
          "seasonaloperations" { "11" { "redeemable_goods" "xpshop" "operational_point_redeemable" {
            "item_name" "crate_promo_test" "points" "5" "local_rotation_slot" "souvenir" } } }
        })");
        auto pitySchema=Schema::Load(pitySchemaText);
        Check(pitySchema.has_value(),"two-tier souvenir fixture loads");
        Inventory inv;inv.SetArmoryCredits(10);inv.SetArmoryPity("souvenir:pool",99);inv.SetArmoryPity("unrelated",7);inv.SetCasePity(12);
        LiveInventory pityLive(inv);Armory pityShop(*pitySchema,11,10);
        auto forced=pityShop.Redeem({11,Crc32("crate_promo_test"),10,5},pityLive,[]{return 9999ull;});
        Check(forced.status==Armory::Status::Ok && forced.item.paintKitIndex==11 && forced.item.souvenir &&
            !forced.item.statTrak && pityLive.Items().ArmoryPity("souvenir:pool")==0 &&
            pityLive.Items().ArmoryPity("unrelated")==7 && pityLive.Items().CasePity()==12 && pityShop.Balance()==5,
            "100th souvenir roll guarantees its top tier, preserves quality and only resets its own pity");
        auto config=inv.Gameplay();config.armory_pity_enabled=0;inv.SetGameplay(config);
        LiveInventory off(inv);Armory offShop(*pitySchema,11,10);
        auto ordinary=offShop.Redeem({11,Crc32("crate_promo_test"),10,5},off,[]{return 9999ull;});
        Check(ordinary.status==Armory::Status::Ok && ordinary.item.paintKitIndex==10,
            "disabling souvenir pity returns to the ordinary tier roll");
    }
    Inventory inventory; inventory.SetArmoryCredits(15); inventory.SetCasePity(44);
    LiveInventory live(inventory); Armory shop(*schema,11,15);
    GameplayConfig config; config.armory_rotation_enforce=1;
    Check(shop.RotationAt(0,config).redeemIds != shop.RotationAt(900,config).redeemIds,
          "souvenir packages rotate independently");
    auto offer = shop.Redeem({11,Crc32("crate_test2025_promo_de_test"),15,5},live,[]{return 0ull;});
    Check(offer.status == Armory::Status::Ok && offer.item.defIndex == 7 && offer.item.souvenir &&
          offer.item.tournamentEvent == 25 && shop.Balance() == 10 && live.Items().Items().size() == 1,
          "Armory grants exactly one souvenir weapon directly for its cost, without a package");
    Check(offer.item.stickers.size() == 4 && offer.item.stickers.back().kit == 5 &&
          live.Items().CasePity() == 44, "direct souvenir purchase keeps decals and does not affect case pity");
    const auto packageId = live.AddItem({0,60}).id;
    const auto result = live.Open(*schema,CustomItemIdBase+packageId,0,[]{return 0ull;});
    Check(result && result->item.souvenir && !result->item.statTrak && !result->item.unusual &&
          result->item.paintKitIndex == 10 && result->item.wear >= .1f && result->item.wear <= .2f &&
          result->item.stickers.size() == 4 && result->item.stickers.back().kit == 5 &&
          result->item.tournamentTeam0 == 10 && result->item.tournamentTeam1 == 20 &&
          live.Items().CasePity() == 44 && !live.Items().Find(packageId),
          "previously owned souvenir packages still open keylessly with correct decals");
    const auto wire = DecodeItem(BuildEconItem(result->item,42,CustomItemIdBase+result->item.id,1));
    Check(wire.ok && wire.quality == QualityTournament && wire.floatBits.at(137)==25 && wire.floatBits.at(139)==10 &&
          wire.floatBits.at(140)==20 && !wire.floatBits.contains(AttributeKillEater),
          "native Souvenir quality and tournament attributes without StatTrak counter");
    auto restored = Inventory::FromText(live.Items().ToText());
    Check(restored && restored->Items()[0].souvenir && restored->Items()[0].tournamentEvent == 25 &&
          restored->Items()[0].stickers.size() == 4, "souvenir quality, provenance and stickers survive save/reload");
    const auto signatureCase = restored->Add({0,62});
    const auto signature = OpenCase(*restored,*schema,signatureCase,0,[]{return 0ull;});
    Check(signature.error == OpenError::None && signature.item.stickers.back().kit == 4 &&
          signature.item.tournamentPlayer==123, "mapless package uses a signature from one of its same-event teams");
    const auto empty = restored->Add({0,61});
    Check(OpenCase(*restored,*schema,empty,0,[]{return 0ull;}).error == OpenError::EmptyLootList && restored->Find(empty),
          "missing souvenir loot never consumes a package");
    std::vector<std::uint64_t> inputs;
    for (unsigned i=0; i<10; ++i) inputs.push_back(restored->Add(result->item));
    const auto before=restored->Items().size();
    Check(TradeUp(*restored,*schema,inputs,[]{return 0ull;}).error == TradeUpError::NoOutcome &&
          restored->Items().size()==before,"souvenir collection without a higher-tier outcome is not consumed");
    InventoryItem wraps; wraps.defIndex=5032; wraps.paintKitIndex=10; wraps.statTrak=true;
    wraps.statTrakFromContract=true; wraps.unusual=true; wraps.wear=.15f; wraps.seed=17;
    const auto wrapId=restored->Add(wraps);
    restored->Loadout().push_back({2,41,CustomItemIdBase+wrapId,5032});
    LiveInventory repaired(*restored);
    Check(repaired.RepairCollectionStatTrak(*schema)==1 && repaired.RepairCollectionStatTrak(*schema)==0,
          "invalid custom glove StatTrak repairs once even without collection metadata");
    const auto *fixed=repaired.Items().Find(wrapId);
    Check(fixed && !fixed->statTrak && !fixed->statTrakFromContract && fixed->wear==.15f && fixed->seed==17 &&
          fixed->paintKitIndex==10 && repaired.Items().Loadout().size()==1 &&
          ItemSaleValue(*schema,config,*fixed)==config.sell_knife_glove,
          "hand wraps keep id/finish/wear/loadout and use the configured glove sale price");
    auto saleLive=std::make_shared<LiveInventory>(repaired.Items());
    saleLive->SetArmoryCredits(8);
    auto sharedSchema=std::shared_ptr<const Schema>(&*schema,[](const Schema *){});
    LocalGameCoordinator coordinator({}); int saves=0;
    coordinator.EnableContainers(saleLive,sharedSchema,[]{return 0ull;},[&]{++saves;});
    PbWriter sale; sale.Varint(1,CustomItemIdBase+wrapId); std::vector<std::uint8_t> bytes;
    WriteProtobufFrame(gc_msg::EGCItemMsg::k_EMsgGCDelete,{},sale.bytes(),bytes);
    for (int i=0; i<2; ++i) coordinator.SendMessage(gc_msg::EGCItemMsg::k_EMsgGCDelete|ProtobufMask,bytes.data(),bytes.size());
    Check(!saleLive->Items().Find(wrapId) && saleLive->Items().Loadout().empty() &&
          saleLive->Items().ArmoryCredits()==80 && saves==1,"native handwrap sale pays once and removes the equipped item");

}

void NativeCarePackages()
{
    const auto schema=Schema::Load(R"("items_game" {
      "prefabs" { "weapon_case_base" {} "weapon_case" { "prefab" "weapon_case_base" "associated_item" "50" } }
      "rarities" { "common" { "value" "1" } "rare" { "value" "3" } }
      "items" { "7" { "name" "weapon_test" "item_rarity" "rare" }
        "50" { "name" "the_key" }
        "60" { "name" "crate_normal" "prefab" "weapon_case" "attributes" { "set supply crate series" { "value" "1" } } }
        "61" { "name" "crate_cs2gc_black_market" "prefab" "weapon_case" "attributes" { "set supply crate series" { "value" "1" } } }
        "62" { "name" "crate_cs2gc_gauntlet" "prefab" "weapon_case" "attributes" { "set supply crate series" { "value" "1" } } }
        "63" { "name" "crate_cs2gc_dead_hand_test" "prefab" "weapon_case" "attributes" { "set supply crate series" { "value" "1" } } } }
      "paint_kits" { "10" { "name" "blue" } }
      "paint_kits_rarity" { "blue" "common" }
      "item_sets" { "set_timed_drops_test" { "items" { "[blue]weapon_test" "1" } } }
      "client_loot_lists" { "crate_list" { "crate_list_rare" "1" } "crate_list_rare" { "[blue]weapon_test" "1" } }
      "revolving_loot_lists" { "1" "crate_list" }
    })");
    Check(schema.has_value(),"care package fixture loads");
    GameplayConfig config;config.match_case_percent=100;
    {
        std::mt19937_64 engine(77);bool testCase=false;
        for (int n=0;n<500;++n)
            if (const auto drops=RollMatchDrops(*schema,[&]{return engine();},config))
                for (const auto &drop:*drops) testCase|=drop.defIndex==63;
        Check(!testCase,"the grant-only Dead Hand Test Case never drops");
    }
    Inventory saved;saved.SetGameplay(config);
    LiveInventory live(saved);
    Check(live.GrantMatchRewards(*schema,1,[]{return 500ull;}).has_value() && live.Items().Items().empty() &&
          live.Items().CarePackages().size()==1 && live.Items().CarePackages()[0].offers.size()==4,
          "a match reserves four offers, granting no automatic inventory items");
    Check(!live.GrantMatchRewards(*schema,1,[]{return 0ull;}),"same match cannot reroll a saved package");
    auto restored=Inventory::FromText(live.Items().ToText());
    Check(restored && restored->CarePackages().size()==1 && restored->Items().empty(),"pending choices survive restart");
    const auto package=restored->CarePackages().front();
    std::vector<std::uint64_t> chosen{package.offers[0].id,package.offers[1].id,package.offers[2].id};
    Check(!restored->ClaimCarePackage(package.generation,{chosen[0],chosen[0],chosen[1]}) &&
          !restored->ClaimCarePackage(package.generation,{chosen[0],chosen[1]}) &&
          !restored->ClaimCarePackage(package.generation+1,chosen) &&
          !restored->ClaimCarePackage(package.generation,{chosen[0],chosen[1],999999}),
          "duplicate, partial, stale and foreign claims fail atomically");
    auto claimed=restored->ClaimCarePackage(package.generation,chosen);
    Check(claimed && claimed->size()==3 && restored->Items().size()==3 && restored->CarePackages().empty() &&
          !restored->Find(package.offers[3].id) && !restored->ClaimCarePackage(package.generation,chosen),
          "three chosen ids become owned exactly once; fourth is discarded");
    restored=Inventory::FromText(restored->ToText());
    Check(restored && restored->Items().size()==3 && restored->CarePackages().empty(),"claimed state persists without regrant");
    LiveInventory levels(*restored);levels.ApplyEarnedXp(2*ProfileLevelXp);
    Check(levels.GrantLevelRewards(*schema,[]{return 700ull;}).has_value() &&
          levels.GrantLevelRewards(*schema,[]{return 900ull;}).has_value() &&
          !levels.GrantLevelRewards(*schema,[]{return 0ull;}) && levels.Items().CarePackages().size()==2,
          "each earned profile level queues its own choice package with no weekly timer");
    auto afterLevels=Inventory::FromText(levels.Items().ToText());
    Check(afterLevels && afterLevels->CarePackages()[0].generation < afterLevels->CarePackages()[1].generation,
          "multiple pending packages retain order and distinct generations");
    Check(!afterLevels->ClaimCarePackage(afterLevels->CarePackages()[1].generation,
          {afterLevels->CarePackages()[1].offers[0].id,afterLevels->CarePackages()[1].offers[1].id,
           afterLevels->CarePackages()[1].offers[2].id}),"later queue entries cannot be claimed out of order");
    auto shared=std::shared_ptr<const Schema>(&*schema,[](const Schema*){});
    auto endpointInventory=std::make_shared<LiveInventory>(saved);LocalGameCoordinator endpoint({});int saves=0;
    endpoint.EnableContainers(endpointInventory,shared,[]{return 500ull;},[&]{++saves;});
    Check(endpoint.ApplyMatchRewards(1,[&]{++saves;}),"native choice package queues through the coordinator");
    bool personal=false,oldDrop=false,unsafePreview=false;std::vector<std::uint64_t> choiceTokens;std::uint32_t size=0;
    while(endpoint.IsMessageAvailable(&size)) {
        std::vector<std::uint8_t> bytes(size);std::uint32_t type=0,got=0;endpoint.RetrieveMessage(&type,bytes.data(),size,&got);
        oldDrop|=(type&~ProtobufMask)==gc_msg::ECsgoGCMsg::k_EMsgGCCStrike15_v2_MatchEndRewardDropsNotification;
        FrameView frame;ReadProtobufFrame(type,bytes,frame);
        if((type&~ProtobufMask)==gc_msg::ESOMsg::k_ESOMsg_Create) {
            const auto object=DecodeSoSingleObject(frame.body);
            if(object && object->typeId==1)unsafePreview=true;
            if(object && object->typeId==4) {
                personal=true;PbReader store(object->data);PbField field;
                while(store.Next(field))if(field.number==3 && field.wire==0)choiceTokens.push_back(field.value);
            }
        }
    }
    Check(personal && !oldDrop && !unsafePreview && saves==1 && choiceTokens.size()==4 &&
          std::set<std::uint64_t>(choiceTokens.begin(),choiceTokens.end()).size()==4,
          "match end publishes only choice descriptors, no preview econ items or end-match drops");
    {
        const auto disk=Inventory::FromText(endpointInventory->Items().ToText());
        Check(disk.has_value(),"queued package reloads for reconnect");
        auto resumed=std::make_shared<LiveInventory>(*disk);LocalGameCoordinator reconnect({});
        reconnect.EnableContainers(resumed,shared,[]{return 1ull;},{});
        PbWriter hello;std::vector<std::uint8_t> wire;
        WriteProtobufFrame(gc_msg::EGCBaseClientMsg::k_EMsgGCClientHello,{},hello.bytes(),wire);
        reconnect.SendMessage(gc_msg::EGCBaseClientMsg::k_EMsgGCClientHello|ProtobufMask,wire.data(),wire.size());
        std::uint32_t available=0;bool storeFound=false;unsigned previewCount=0;
        while(reconnect.IsMessageAvailable(&available)) {
            std::vector<std::uint8_t> message(available);std::uint32_t type=0,got=0;
            reconnect.RetrieveMessage(&type,message.data(),available,&got);
            if((type&~ProtobufMask)!=gc_msg::EGCBaseClientMsg::k_EMsgGCClientWelcome)continue;
            FrameView frame;ReadProtobufFrame(type,message,frame);const auto welcome=DecodeClientWelcome(frame.body);
            Check(welcome.has_value(),"reconnected welcome decodes");
            for(const auto &cache:welcome->outOfDateCaches)for(const auto &object:cache.types) {
                if(object.typeId==4)storeFound=object.objects.size()==1;
                if(object.typeId==1)previewCount+=static_cast<unsigned>(object.objects.size());
            }
        }
        Check(storeFound && previewCount==0 && resumed->Items().Items().empty(),
              "reconnect restores choice descriptors without recreating the crashing unowned econ previews");
    }
    const auto &offer=endpointInventory->Items().CarePackages().front();
    PbWriter request;request.Varint(1,offer.generation);request.Varint(2,0);
    for(unsigned i=0;i<3;++i)request.Varint(3,choiceTokens[i]);
    std::vector<std::uint8_t> body;WriteProtobufFrame(9219,{},request.bytes(),body);
    endpoint.SendMessage(9219|ProtobufMask,body.data(),body.size());
    endpoint.SendMessage(9219|ProtobufMask,body.data(),body.size());
    Check(endpointInventory->Items().Items().size()==3 && endpointInventory->Items().CarePackages().empty() && saves==2,
          "native StoreRedeemFreeRewards path pays three once and saves before notification");
    Inventory opens;const auto crate=opens.Add({0,60});
    Check(OpenCase(opens,*schema,crate,0,[]{return 0ull;}).error==OpenError::None && opens.Items().size()==1,
          "free case opens with no key object");
    const auto selfTool=opens.Add({0,60});
    Check(OpenCase(opens,*schema,selfTool,selfTool,[]{return 0ull;}).error==OpenError::None,
          "native keyless UseTool(case,case) opens without treating the case as a wrong key");
    InventoryItem key;key.defIndex=50;
    Check(ItemSaleValue(*schema,config,key)==5,"leftover keys sell for five stars");
    config.reward_rare_case_per_10000=10000;
    const auto rare=RollMatchDrops(*schema,[]{return 0ull;},config);
    Check(rare && (*rare)[0].defIndex==61,"custom cases use the configurable rare-case channel");
    Check(RollMatchDrops(*schema,[]{return 1ull;},config)->front().defIndex==62,
          "Gauntlet shares the rare channel with Black Market");
    config.knife_finishes=0;
    const auto normal=RollMatchDrops(*schema,[]{return 0ull;},config);
    Check(normal && (*normal)[0].defIndex==60,"disabled custom finishes never enter rare drop choices");
    config.knife_finishes=1;config.reward_rare_case_per_10000=0;
    Check(RollMatchDrops(*schema,[]{return 0ull;},config)->front().defIndex==60,
          "custom cases are excluded from the ordinary case pool");
}

int main()
{
    try
    {
        NativeCarePackages(); std::cout << "PASS native three-of-four care packages, keyless cases and rare rewards\n";
        SouvenirPackagesAndHandwraps(); std::cout << "PASS souvenir packages, glove repair and handwrap sales\n";
        ArmoryTerminals(); std::cout << "PASS terminal Armory offers\n";
        MusicKitsAndCouponMigration(); std::cout << "PASS music kits and coupon migration\n";
        WeeklyPoolAndItemSales(); std::cout << "PASS weekly pool and native item sales\n";
        NativeArmorySlotsAndConsoleStars(); std::cout << "PASS native Armory slots and console stars\n";
        NativePremier(); std::cout << "PASS native Premier placement/rating cache\n";
        HowlAndArmoryRotation(); std::cout << "PASS limited Howl and Armory rotation policy\n";
        ConfiguredRewardsAndPity(); std::cout << "PASS configured match rewards, pity and local transport\n";
        ArmoryPassCapAndPersistence(); std::cout << "PASS armory pass cap and persistence\n";
        SavedProgressionAndServerItems(); std::cout << "PASS saved ranks, pass XP and bot-server cache\n";
        Terminals(); std::cout << "PASS terminal offers, decline and purchase\n";
        GoldTradeUps(); std::cout << "PASS five-Covert gold contracts\n";
        TradeUps(); std::cout << "PASS trade-ups and built-in weapons\n";
        SlabsScrapesAndCoupons(); std::cout << "PASS slabs, scrapes and coupons\n";
        StorageUnits(); std::cout << "PASS storage units\n";
        CharmsAndCoupons(); std::cout << "PASS charms\n";
        ContainersAndNaming(); std::cout << "PASS containers and naming\n";
        ArmoryPassActivation(); std::cout << "PASS armory pass activation\n";
        StorePurchases(); std::cout << "PASS store purchases\n";
        StickerApplication(); std::cout << "PASS sticker application\n";
        Frames(); std::cout << "PASS protocol framing and malformed input\n";
        Queues(); std::cout << "PASS bounded Steam-style message queue\n";
        Progression(); std::cout << "PASS XP and star reward rules\n";
        ArmoryCatalogueTest(); std::cout << "PASS Armory categories, search and pagination\n";
        KeyValuesParsing(); std::cout << "PASS KeyValues parser and malformed input\n";
        SchemaCrates(); std::cout << "PASS schema crates, keys and loot tiers\n";
        CaseOpening(); std::cout << "PASS case opening odds and atomic consumption\n";
        InventoryPersistence(); std::cout << "PASS inventory persistence and strict loading\n";
        GcMessageIds(); std::cout << "PASS extracted GC message IDs and build fingerprint\n";
        ProtobufWire(); std::cout << "PASS protobuf reader and writer\n";
        HandshakeCodec(); std::cout << "PASS handshake message codecs\n";
        Endpoint(); std::cout << "PASS local game coordinator hello/welcome\n";
        ProtobufDump(); std::cout << "PASS protobuf dump and SteamID redaction\n";
        ProxySupport(); std::cout << "PASS launch guard and proxy config parsing\n";
        SoSummaries(); std::cout << "PASS object message decoders, summaries and account redaction\n";
        Replay(); std::cout << "PASS replay store and recorded-reply endpoint\n";
        WelcomeOtherFields(); std::cout << "PASS welcome summary shows non-cache fields\n";
        EconItems(); std::cout << "PASS econ item encoding and welcome patching\n";
        InventoryRarity(); std::cout << "PASS inventory rarity\n";
        SummaryDiversityAndLocation(); std::cout << "PASS summary samples and location redaction\n";
        SkinRarityAndFreshInventory(); std::cout << "PASS skin rarity and fresh inventory\n";
        ArmoryBalance(); std::cout << "PASS armory balance patch\n";
        LoadoutAndPurchases(); std::cout << "PASS loadout equipping, purchase refusal and job id echo\n";
        ArmoryRedeems(); std::cout << "PASS armory redeems from the schema\n";
        ArmoryEndpoint(); std::cout << "PASS armory over the endpoint\n";
        return 0;
    }
    catch (const std::exception &error)
    {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
}
