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
    Check(schema->Crates().size() == 4, "souvenir and seriesless items excluded, repeated sections merged");
    const CrateInfo *one = schema->FindCrate(901);
    Check(one && one->keyDefIndex == 900 && one->series == 5 && one->nameToken == "Case_One", "prefab key and token");
    Check(one->lootListName == "case_one_lootlist", "series resolves loot list");
    const CrateInfo *two = schema->FindCrate(902);
    Check(two && two->keyDefIndex == 903, "associated_items key");
    Check(one->kind == CrateKind::Case && schema->FindCrate(906)->kind == CrateKind::Capsule, "kind from prefab chain");
    Check(schema->FindCrate(905)->kind == CrateKind::Case, "prefab-inherited key makes a case");
    Check(schema->FindCrate(905) && !schema->FindCrate(910) && !schema->FindCrate(1), "lookup");

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

    // Statistical check on many opens, each with a fresh crate and key.
    std::array<int, 4> counts{};
    int statTrak = 0;
    constexpr int Opens = 40000;
    for (int i = 0; i < Opens; ++i)
    {
        Inventory inv;
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
    gc.EnableLiveInventory(liveForEndpoint);
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
    }
    "items"
    {
        "50" { "name" "the_key" }
        "60" { "name" "the_case" "prefab" "weapon_case" "attributes" { "set supply crate series" { "value" "1" } } }
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
    Check(schema->ArmoryRedeemables().size() == 5, "five usable tiles; the one without points and the credits campaign are skipped");
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

    const auto caseRedeem = armory.Redeem(request("the_case", 2), live, random);
    Check(caseRedeem.status == Armory::Status::Ok && caseRedeem.item.defIndex == 60 && caseRedeem.item.paintKitIndex == 0 &&
              armory.Balance() == 44, "a plain item name grants that item");
    const auto stickerRedeem = armory.Redeem(request("lootlist:stickers_test", 1), live, random);
    Check(stickerRedeem.status == Armory::Status::Ok && stickerRedeem.item.defIndex == 1209 &&
              (stickerRedeem.item.stickerKit == 300 || stickerRedeem.item.stickerKit == 301) && stickerRedeem.item.rarity == 3, "sticker pack");
    const auto charmRedeem = armory.Redeem(request("lootlist:kc_test", 3), live, random);
    Check(charmRedeem.status == Armory::Status::Ok && charmRedeem.item.defIndex == 1355 && charmRedeem.item.keychain == 17, "charm pack");
    Check(armory.Balance() == 40 && live.Items().Items().size() == 4, "balance and inventory after four redeems");

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
    for (int i = 0; i < Rolls; ++i)
        uncommon += rich.Redeem(request("lootlist:set_test", 4), scratch, random).item.paintKitIndex == 10;
    Check(std::abs(uncommon / double(Rolls) - 7992.0 / (7992 + 1598)) < 0.015, "collection odds: lowest tier is the common one");
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
              fields.at(3) == std::vector<std::uint64_t>{77}, "balance 10 - 2 = 8, other fields kept");
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
              tracks(pass1->data) == std::vector<std::uint64_t>({77, 0}), "activating adds an empty pass, keeps the recorded one");
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
    Check(objects.size() == 1 && tracks(objects[0]) == std::vector<std::uint64_t>({77, 0}),
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
        "20002" { "name" "coupon - a_capsule" "loot_list_name" "coupon loot list - a_capsule" }
    }
    "sticker_kits" { "300" { "name" "stk_a" } }
    "keychain_definitions" { "37" { "name" "kc_sticker_display_case" } }
    "client_loot_lists"
    {
        "coupon loot list - stk_a" { "public_list_contents" "1" "[stk_a]sticker" "1" }
        "coupon loot list - a_capsule" { "public_list_contents" "1" "weapon_rifle" "1" }
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

    // Buying: a coupon for one sticker is the sticker; a coupon for a container stays an envelope.
    for (const std::uint32_t def : {20001u, 20002u})
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
    const auto &items = live->Items().Items();
    Check(items.size() == 3 && items[1].defIndex == DefinitionSticker && items[1].stickerKit == 300 && items[2].defIndex == 20002,
          "a single-sticker coupon grants the sticker, a container coupon stays a coupon");
}

int main()
{
    try
    {
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
