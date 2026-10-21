#include "viewmodel_range.h"

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

#include <chrono>
#include <cstring>
#include <thread>

namespace cs2_gc
{
namespace
{
// Inspected client.dll (Steam build 25947352): each convar is a static CConVarRef { access index; ConVarData * }
// written by ICvar::RegisterConVar. ConVarData starts { name, default*, min*, max* } (public hl2sdk-cs2 layout),
// and the registration code passes exactly these limits.
struct Target
{
    const char *name;
    std::uintptr_t rva; // the static convar object in client.dll
    float defaultValue, minimum, maximum;
    bool fov;
};
constexpr Target Targets[] = {
    {"viewmodel_offset_x", 0x25328c0, 1.0f, -2.0f, 2.5f, false},
    {"viewmodel_offset_y", 0x25328d0, 1.0f, -2.0f, 2.0f, false},
    {"viewmodel_offset_z", 0x25328e0, -1.0f, -2.0f, 2.0f, false},
    {"viewmodel_fov", 0x256aad0, 60.0f, 60.0f, 68.0f, true},
};

bool Readable(const void *address, std::size_t size)
{
    MEMORY_BASIC_INFORMATION info{};
    if (!address || !VirtualQuery(address, &info, sizeof(info)) || info.State != MEM_COMMIT ||
        (info.Protect & (PAGE_NOACCESS | PAGE_GUARD)))
        return false;
    const auto start = reinterpret_cast<std::uintptr_t>(address);
    return start + size <= reinterpret_cast<std::uintptr_t>(info.BaseAddress) + info.RegionSize;
}

template <typename T> bool Read(const void *address, T &out)
{
    if (!Readable(address, sizeof(T))) return false;
    std::memcpy(&out, address, sizeof(T));
    return true;
}

bool WriteFloat(float *address, float value)
{
    DWORD old = 0;
    if (!VirtualProtect(address, sizeof(float), PAGE_READWRITE, &old)) return false;
    *address = value;
    VirtualProtect(address, sizeof(float), old, &old);
    return true;
}

// One convar: follow the object to its ConVarData, verify name and the default/min/max values, then widen.
std::string Apply(std::uintptr_t base, const Target &target, const ViewmodelRange &range, bool &done)
{
    done = false;
    const char *data = nullptr;
    if (!Read(reinterpret_cast<const void *>(base + target.rva + 8), data) || !data) return {}; // not registered yet
    done = true;
    const char *name = nullptr;
    float *values[3]{};
    if (!Read(data, name) || !Readable(name, std::strlen(target.name) + 1) || std::strcmp(name, target.name) != 0)
        return std::string(target.name) + ": not the inspected client layout, left unchanged";
    for (int i = 0; i < 3; ++i)
        if (!Read(data + 8 + i * 8, values[i]) || !Readable(values[i], sizeof(float)))
            return std::string(target.name) + ": no readable default/min/max, left unchanged";
    if (*values[0] != target.defaultValue || *values[1] != target.minimum || *values[2] != target.maximum)
        return std::string(target.name) + ": limits differ from the inspected build, left unchanged";
    const float scale = range.offsetPercent / 100.0f;
    const float minimum = target.fov ? static_cast<float>(range.fovMin) : target.minimum * scale;
    const float maximum = target.fov ? static_cast<float>(range.fovMax) : target.maximum * scale;
    if (!WriteFloat(values[1], minimum) || !WriteFloat(values[2], maximum))
        return std::string(target.name) + ": could not write the limits";
    return std::string(target.name) + " range " + std::to_string(minimum) + " .. " + std::to_string(maximum);
}
} // namespace

void StartViewmodelRange(ViewmodelRange range, std::function<void(const std::string &)> log)
{
    if (range.offsetPercent == 100 && range.fovMin == 60 && range.fovMax == 68) return;
    if (range.offsetPercent < 100 || range.offsetPercent > 1000 || range.fovMin > range.fovMax || range.fovMin < 1 ||
        range.fovMax > 179)
    {
        log("viewmodel range: settings out of bounds, left unchanged");
        return;
    }
    std::thread([range, log] {
        bool pending[std::size(Targets)];
        std::fill(std::begin(pending), std::end(pending), true);
        for (int attempt = 0; attempt < 600; ++attempt) // up to five minutes for client.dll to load and register
        {
            const auto base = reinterpret_cast<std::uintptr_t>(GetModuleHandleW(L"client.dll"));
            bool remaining = false;
            for (std::size_t i = 0; i < std::size(Targets); ++i)
            {
                if (!pending[i]) continue;
                bool done = false;
                const auto message = base ? Apply(base, Targets[i], range, done) : std::string{};
                if (done) { pending[i] = false; log("viewmodel range: " + message); }
                else remaining = true;
            }
            if (!remaining) return;
            std::this_thread::sleep_for(std::chrono::milliseconds(500));
        }
        log("viewmodel range: client.dll convars never registered, left unchanged");
    }).detach();
}
} // namespace cs2_gc
#else
namespace cs2_gc
{
void StartViewmodelRange(ViewmodelRange, std::function<void(const std::string &)>) {}
}
#endif
