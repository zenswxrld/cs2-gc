#pragma once

#include <cstdint>
#include <functional>
#include <string>

namespace cs2_gc
{
struct ViewmodelRange
{
    std::uint32_t offsetPercent{250}; // viewmodel_offset_x/y/z limits x2.5; 100 leaves them alone
    std::uint32_t fovMin{40}, fovMax{90}; // viewmodel_fov limits (stock 60..68)
};

// Widens the viewmodel convar limits like OfflineCS's viewmodel_range, on a background thread once client.dll has
// registered them. Every value is checked against the inspected client build first; anything unexpected
// changes nothing and is reported through `log`.
void StartViewmodelRange(ViewmodelRange range, std::function<void(const std::string &)> log);
}
