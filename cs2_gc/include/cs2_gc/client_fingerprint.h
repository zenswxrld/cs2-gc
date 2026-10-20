#pragma once

#include <string_view>

namespace cs2_gc
{
// The one CS2 build the protocol constants were derived from. Hashes are of the files
// the user supplied; no game binaries are stored in this repository.
inline constexpr std::string_view TargetSteamBuildId = "25947352";
inline constexpr std::string_view TargetClientDllSha256 =
    "659940c1db362ed981d1df10637cec8c2a3d99409b77fc3b73e435e4649e36b0";
inline constexpr std::string_view TargetEngine2DllSha256 =
    "6456df18d8f954394024c2c07da8c848df15a5ace74ce7390d78970ceb39ee21";
inline constexpr std::string_view TargetSteamApiDllSha256 =
    "2a785780af426dfc5c809087d100db8d4ff41a1e1a2956ad5473689e77e3c863";
}
