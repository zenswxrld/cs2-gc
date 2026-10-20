#include "cs2_gc/gc_summary.h"
#include "cs2_gc/gc_handshake.h"
#include "cs2_gc/gc_msg_ids.h"
#include "cs2_gc/protobuf.h"
#include <map>
#include <set>
#include <string>

namespace cs2_gc
{
namespace
{
constexpr std::size_t SampleBytes = 3 * 1024;
constexpr std::size_t MaxTypes = 64;

constexpr std::size_t MaxSamplesPerType = 6;

struct TypeStats
{
    std::size_t count{};
    std::size_t bytes{};
    // One sample per distinct shape (which fields are present, and which attribute definitions
    // an item carries), so a log shows a skin, a case, a sticker... and not only the first object.
    std::vector<std::vector<std::uint8_t>> samples;
    std::set<std::string> shapes;
};

using Stats = std::map<std::int32_t, TypeStats>;

std::string Shape(const std::vector<std::uint8_t> &data)
{
    std::string shape;
    PbReader reader(data);
    PbField f;
    std::set<std::uint32_t> attributes;
    std::set<std::uint32_t> fields;
    while (reader.Next(f))
    {
        fields.insert(f.number);
        if (f.number == 12 && f.wire == 2)
        {
            PbReader inner(f.bytes);
            PbField g;
            while (inner.Next(g))
                if (g.number == 1 && g.wire == 0)
                    attributes.insert(static_cast<std::uint32_t>(g.value));
        }
    }
    for (std::uint32_t n : fields)
        shape += std::to_string(n) + ",";
    shape += "|";
    for (std::uint32_t n : attributes)
        shape += std::to_string(n) + ",";
    return shape;
}

void Add(Stats &stats, std::int32_t typeId, const std::vector<std::uint8_t> &data)
{
    if (stats.size() >= MaxTypes && !stats.contains(typeId))
        return;
    TypeStats &entry = stats[typeId];
    ++entry.count;
    entry.bytes += data.size();
    if (entry.samples.size() < MaxSamplesPerType && entry.shapes.insert(Shape(data)).second)
        entry.samples.push_back(data);
}

std::string Indent(const std::string &dump, const char *prefix)
{
    std::string out;
    for (std::size_t start = 0; start < dump.size();)
    {
        const std::size_t end = dump.find('\n', start);
        out += prefix + dump.substr(start, end == std::string::npos ? end : end - start + 1);
        if (end == std::string::npos)
        {
            out += '\n';
            break;
        }
        start = end + 1;
    }
    return out;
}

std::string Render(const char *what, const Stats &stats, const DumpOptions &options)
{
    std::string out = std::string("  summary (") + what + "):\n";
    DumpOptions sample = options;
    sample.maxBytes = SampleBytes;
    for (const auto &[typeId, entry] : stats)
    {
        out += "    object type_id=" + std::to_string(typeId) + " count=" + std::to_string(entry.count) +
               " bytes=" + std::to_string(entry.bytes) + "\n";
        int number = 0;
        for (const auto &data : entry.samples)
        {
            out += "      sample " + std::to_string(++number) + " (" + std::to_string(data.size()) + " bytes):\n";
            const std::string dump = DumpProtobuf(data, sample);
            out += dump.empty() ? "        <empty>\n" : Indent(dump, "        ");
        }
    }
    return out;
}
}

std::string SummarizeSoMessage(std::uint32_t messageId, std::span<const std::uint8_t> body,
                               const DumpOptions &options)
{
    namespace m = gc_msg;
    Stats stats;
    const char *what = nullptr;

    if (messageId == m::EGCBaseClientMsg::k_EMsgGCClientWelcome)
    {
        const auto welcome = DecodeClientWelcome(body);
        if (!welcome)
            return {};
        what = "welcome caches";
        for (const SoCacheSubscribed &cache : welcome->outOfDateCaches)
            for (const SoObjectType &type : cache.types)
            {
                if (type.objects.empty())
                    stats.try_emplace(type.typeId);
                for (const auto &object : type.objects)
                    Add(stats, type.typeId, object);
            }
        std::string out = Render(what, stats, options);
        out += "    caches: out of date=" + std::to_string(welcome->outOfDateCaches.size()) + "\n";

        // Everything except the caches (version, game data, location, currency, ...), which the
        // cache summary above does not show.
        PbWriter others;
        bool redactedLocation = false;
        PbReader reader(body);
        PbField f;
        while (reader.Next(f))
        {
            if (f.number == 3)
                continue;
            if (f.number == 5) // location: coarse coordinates and country from the GC's geolocation
            {
                redactedLocation = true;
                continue;
            }
            switch (f.wire)
            {
            case 0: others.Varint(f.number, f.value); break;
            case 1: others.Fixed64(f.number, f.value); break;
            case 5: others.Fixed32(f.number, static_cast<std::uint32_t>(f.value)); break;
            default: others.Bytes(f.number, f.bytes); break;
            }
        }
        DumpOptions otherOptions = options;
        otherOptions.maxBytes = 8 * 1024;
        const std::string dump = DumpProtobuf(others.bytes(), otherOptions);
        out += "  other welcome fields:\n";
        out += dump.empty() && !redactedLocation ? std::string("    <none>\n") : Indent(dump, "    ");
        if (redactedLocation)
            out += "    5: <location redacted>\n";
        return out;
    }
    if (messageId == m::ESOMsg::k_ESOMsg_CacheSubscribed)
    {
        const auto cache = DecodeSoCacheSubscribed(body);
        if (!cache)
            return {};
        for (const SoObjectType &type : cache->types)
        {
            if (type.objects.empty())
                stats.try_emplace(type.typeId);
            for (const auto &object : type.objects)
                Add(stats, type.typeId, object);
        }
        return Render("cache subscribed", stats, options);
    }
    if (messageId == m::ESOMsg::k_ESOMsg_Create || messageId == m::ESOMsg::k_ESOMsg_Update ||
        messageId == m::ESOMsg::k_ESOMsg_Destroy)
    {
        const auto object = DecodeSoSingleObject(body);
        if (!object)
            return {};
        Add(stats, object->typeId, object->data);
        return Render("single object", stats, options);
    }
    if (messageId == m::ESOMsg::k_ESOMsg_UpdateMultiple)
    {
        const auto objects = DecodeSoMultipleObjects(body);
        if (!objects)
            return {};
        for (const auto &object : objects->objects)
            Add(stats, object.typeId, object.data);
        return Render("update multiple", stats, options);
    }
    return {};
}
}
