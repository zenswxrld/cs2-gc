#include "cs2_gc/gc_handshake.h"
#include "cs2_gc/protobuf.h"
#include <limits>

namespace cs2_gc
{
namespace
{
bool U32(const PbField &f, std::uint32_t &out)
{
    // protobuf truncates oversized varints for 32-bit fields; reject instead of guessing
    if (f.wire != 0 || f.value > std::numeric_limits<std::uint32_t>::max())
        return false;
    out = static_cast<std::uint32_t>(f.value);
    return true;
}

bool I32(const PbField &f, std::int32_t &out)
{
    // int32 is a sign-extended 64-bit varint; anything else is out of range
    if (f.wire != 0)
        return false;
    const auto value = static_cast<std::int64_t>(f.value);
    if (value < std::numeric_limits<std::int32_t>::min() || value > std::numeric_limits<std::int32_t>::max())
        return false;
    out = static_cast<std::int32_t>(value);
    return true;
}

bool Fixed64(const PbField &f, std::uint64_t &out)
{
    if (f.wire != 1)
        return false;
    out = f.value;
    return true;
}

bool DecodeOwner(std::span<const std::uint8_t> body, SoOwner &owner)
{
    owner = {};
    PbReader reader(body);
    PbField f;
    while (reader.Next(f))
    {
        if (f.number == 1 && !U32(f, owner.type))
            return false;
        if (f.number == 2)
        {
            if (f.wire != 0)
                return false;
            owner.id = f.value;
        }
    }
    return !reader.Failed();
}

bool DecodeHaveVersion(std::span<const std::uint8_t> body, SoCacheVersion &out)
{
    out = {};
    PbReader reader(body);
    PbField f;
    while (reader.Next(f))
    {
        if (f.number == 1 && (f.wire != 2 || !DecodeOwner(f.bytes, out.owner)))
            return false;
        if (f.number == 2 && !Fixed64(f, out.version))
            return false;
    }
    return !reader.Failed();
}

PbWriter OwnerWriter(const SoOwner &owner)
{
    PbWriter w;
    w.Varint(1, owner.type);
    w.Varint(2, owner.id);
    return w;
}
}

std::optional<ClientHello> DecodeClientHello(std::span<const std::uint8_t> body)
{
    ClientHello hello;
    PbReader reader(body);
    PbField f;
    while (reader.Next(f))
    {
        std::uint32_t value = 0;
        switch (f.number)
        {
        case 1: if (!U32(f, value)) return std::nullopt; hello.version = value; break;
        case 2:
        {
            SoCacheVersion version;
            if (f.wire != 2 || !DecodeHaveVersion(f.bytes, version))
                return std::nullopt;
            hello.haveVersions.push_back(version);
            break;
        }
        case 3: if (!U32(f, value)) return std::nullopt; hello.clientSessionNeed = value; break;
        case 4: if (!U32(f, value)) return std::nullopt; hello.clientLauncher = value; break;
        case 9: if (!U32(f, value)) return std::nullopt; hello.steamLauncher = value; break;
        default: break;
        }
    }
    if (reader.Failed())
        return std::nullopt;
    return hello;
}

std::optional<SoCacheSubscribed> DecodeSoCacheSubscribed(std::span<const std::uint8_t> body)
{
    SoCacheSubscribed cache;
    PbReader reader(body);
    PbField f;
    while (reader.Next(f))
    {
        if (f.number == 2)
        {
            if (f.wire != 2)
                return std::nullopt;
            SoObjectType type;
            PbReader inner(f.bytes);
            PbField g;
            while (inner.Next(g))
            {
                if (g.number == 1 && !I32(g, type.typeId))
                    return std::nullopt;
                if (g.number == 2)
                {
                    if (g.wire != 2)
                        return std::nullopt;
                    type.objects.emplace_back(g.bytes.begin(), g.bytes.end());
                }
            }
            if (inner.Failed())
                return std::nullopt;
            cache.types.push_back(std::move(type));
        }
        else if (f.number == 3 && !Fixed64(f, cache.version))
            return std::nullopt;
        else if (f.number == 4 && (f.wire != 2 || !DecodeOwner(f.bytes, cache.owner)))
            return std::nullopt;
    }
    if (reader.Failed())
        return std::nullopt;
    return cache;
}

std::optional<ClientWelcome> DecodeClientWelcome(std::span<const std::uint8_t> body)
{
    ClientWelcome welcome;
    PbReader reader(body);
    PbField f;
    while (reader.Next(f))
    {
        if (f.number == 1 && !U32(f, welcome.version))
            return std::nullopt;
        if (f.number == 3)
        {
            auto cache = f.wire == 2 ? DecodeSoCacheSubscribed(f.bytes) : std::nullopt;
            if (!cache)
                return std::nullopt;
            welcome.outOfDateCaches.push_back(std::move(*cache));
        }
    }
    if (reader.Failed())
        return std::nullopt;
    return welcome;
}

std::optional<SoSingleObject> DecodeSoSingleObject(std::span<const std::uint8_t> body)
{
    SoSingleObject object;
    PbReader reader(body);
    PbField f;
    while (reader.Next(f))
    {
        if (f.number == 2 && !I32(f, object.typeId))
            return std::nullopt;
        if (f.number == 3)
        {
            if (f.wire != 2)
                return std::nullopt;
            object.data.assign(f.bytes.begin(), f.bytes.end());
        }
        if (f.number == 4 && !Fixed64(f, object.version))
            return std::nullopt;
        if (f.number == 5 && (f.wire != 2 || !DecodeOwner(f.bytes, object.owner)))
            return std::nullopt;
    }
    if (reader.Failed())
        return std::nullopt;
    return object;
}

std::optional<SoMultipleObjects> DecodeSoMultipleObjects(std::span<const std::uint8_t> body)
{
    SoMultipleObjects result;
    PbReader reader(body);
    PbField f;
    while (reader.Next(f))
    {
        if (f.number == 2)
        {
            if (f.wire != 2)
                return std::nullopt;
            SoMultipleObjects::Object object;
            PbReader inner(f.bytes);
            PbField g;
            while (inner.Next(g))
            {
                if (g.number == 1 && !I32(g, object.typeId))
                    return std::nullopt;
                if (g.number == 2)
                {
                    if (g.wire != 2)
                        return std::nullopt;
                    object.data.assign(g.bytes.begin(), g.bytes.end());
                }
            }
            if (inner.Failed())
                return std::nullopt;
            result.objects.push_back(std::move(object));
        }
        else if (f.number == 3 && !Fixed64(f, result.version))
            return std::nullopt;
        else if (f.number == 6 && (f.wire != 2 || !DecodeOwner(f.bytes, result.owner)))
            return std::nullopt;
    }
    if (reader.Failed())
        return std::nullopt;
    return result;
}

std::vector<std::uint8_t> EncodeSoCacheSubscribed(const SoCacheSubscribed &cache)
{
    PbWriter w;
    for (const SoObjectType &type : cache.types)
    {
        PbWriter t;
        t.Varint(1, static_cast<std::uint64_t>(static_cast<std::int64_t>(type.typeId)));
        for (const auto &object : type.objects)
            t.Bytes(2, object);
        w.Message(2, t);
    }
    w.Fixed64(3, cache.version);
    w.Message(4, OwnerWriter(cache.owner));
    return w.bytes();
}

std::vector<std::uint8_t> EncodeClientWelcome(const ClientWelcome &welcome)
{
    PbWriter w;
    w.Varint(1, welcome.version);
    for (const SoCacheSubscribed &cache : welcome.outOfDateCaches)
        w.Bytes(3, EncodeSoCacheSubscribed(cache));
    return w.bytes();
}

std::vector<std::uint8_t> EncodeClientHello(const ClientHello &hello)
{
    PbWriter w;
    if (hello.version)
        w.Varint(1, *hello.version);
    for (const SoCacheVersion &have : hello.haveVersions)
    {
        PbWriter h;
        h.Message(1, OwnerWriter(have.owner));
        h.Fixed64(2, have.version);
        w.Message(2, h);
    }
    if (hello.clientSessionNeed)
        w.Varint(3, *hello.clientSessionNeed);
    if (hello.clientLauncher)
        w.Varint(4, *hello.clientLauncher);
    if (hello.steamLauncher)
        w.Varint(9, *hello.steamLauncher);
    return w.bytes();
}
}
