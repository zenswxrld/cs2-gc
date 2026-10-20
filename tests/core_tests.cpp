#include "cs2_gc/armory_catalog.h"
#include "cs2_gc/message_queue.h"
#include "cs2_gc/progression.h"
#include "cs2_gc/schema.h"
#include <array>
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
        return 0;
    }
    catch (const std::exception &error)
    {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
}
