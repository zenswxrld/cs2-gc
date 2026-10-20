#include "cs2_gc/armory_catalog.h"
#include "cs2_gc/case_opening.h"
#include "cs2_gc/client_fingerprint.h"
#include "cs2_gc/gc_endpoint.h"
#include "cs2_gc/gc_msg_ids.h"
#include "cs2_gc/protobuf.h"
#include "cs2_gc/protobuf_dump.h"
#include "cs2_gc/proxy_support.h"
#include "cs2_gc/message_queue.h"
#include "cs2_gc/progression.h"
#include "cs2_gc/schema.h"
#include <array>
#include <filesystem>
#include <fstream>
#include <cmath>
#include <atomic>
#include <iostream>
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

void Armory()
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
              !has(redacted, "123456789") && has(redacted, "<steamid redacted>"), "steam ids redacted");

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

    const auto config = ParseProxyConfig("# comment\n steam_id = 76561198000000000 \nwelcome_version=3 # trailing\r\nowner_type=1\ncache_version=9\n");
    Check(config && config->steamId == 76561198000000000ull && config->welcomeVersion == 3 && config->ownerType == 1 &&
              config->cacheVersion == 9, "config values");
    const auto defaults = ParseProxyConfig("");
    Check(defaults && defaults->steamId == 0 && defaults->ownerType == 1 && defaults->cacheVersion == 1, "defaults");
    for (const char *bad : {"steam_id=abc", "steam_id=", "steam_id=12x", "steam_id=-1", "welcome_version=4294967296",
                            "owner_type=99999999999", "steamid=1", "nonsense", "=5", "steam_id=1 2"})
        Check(!ParseProxyConfig(bad), bad);
}

int main()
{
    try
    {
        Frames(); std::cout << "PASS protocol framing and malformed input\n";
        Queues(); std::cout << "PASS bounded Steam-style message queue\n";
        Progression(); std::cout << "PASS XP and star reward rules\n";
        Armory(); std::cout << "PASS Armory categories, search and pagination\n";
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
        return 0;
    }
    catch (const std::exception &error)
    {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
}
