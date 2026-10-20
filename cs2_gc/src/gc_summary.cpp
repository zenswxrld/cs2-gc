#include "cs2_gc/gc_summary.h"
#include "cs2_gc/gc_handshake.h"
#include "cs2_gc/gc_msg_ids.h"
#include "cs2_gc/protobuf.h"
#include <map>

namespace cs2_gc
{
namespace
{
constexpr std::size_t SampleBytes = 3 * 1024;
constexpr std::size_t MaxTypes = 64;

struct TypeStats
{
    std::size_t count{};
    std::size_t bytes{};
    std::vector<std::uint8_t> sample;
};

using Stats = std::map<std::int32_t, TypeStats>;

void Add(Stats &stats, std::int32_t typeId, const std::vector<std::uint8_t> &data)
{
    if (stats.size() >= MaxTypes && !stats.contains(typeId))
        return;
    TypeStats &entry = stats[typeId];
    if (entry.count++ == 0)
        entry.sample = data;
    entry.bytes += data.size();
}

std::string Render(const char *what, const Stats &stats, const DumpOptions &options)
{
    std::string out = std::string("  summary (") + what + "):\n";
    DumpOptions sample = options;
    sample.maxBytes = SampleBytes;
    for (const auto &[typeId, entry] : stats)
    {
        out += "    object type_id=" + std::to_string(typeId) + " count=" + std::to_string(entry.count) +
               " bytes=" + std::to_string(entry.bytes) + "\n      first object:\n";
        const std::string dump = DumpProtobuf(entry.sample, sample);
        out += dump.empty() ? "        <empty>\n" : "";
        for (std::size_t start = 0; start < dump.size();)
        {
            const std::size_t end = dump.find('\n', start);
            out += "        " + dump.substr(start, end == std::string::npos ? end : end - start + 1);
            if (end == std::string::npos)
            {
                out += '\n';
                break;
            }
            start = end + 1;
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
        PbReader reader(body);
        PbField f;
        while (reader.Next(f))
        {
            if (f.number == 3)
                continue;
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
        for (std::size_t start = 0; start < dump.size();)
        {
            const std::size_t end = dump.find('\n', start);
            out += "    " + dump.substr(start, end == std::string::npos ? end : end - start + 1);
            if (end == std::string::npos)
            {
                out += '\n';
                break;
            }
            start = end + 1;
        }
        if (dump.empty())
            out += "    <none>\n";
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
