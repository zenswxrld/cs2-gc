#pragma once

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <map>
#include <span>
#include <vector>

namespace cs2_gc
{
// Message bodies recorded from a real GC session, one file per message ID ("<id>.bin" holding
// the protobuf body only). They contain account data, so they live next to the DLL on the
// user's machine and must never be committed or shared.
class ReplayStore
{
public:
    static constexpr std::size_t MaxBodyBytes = 1024 * 1024;
    static constexpr std::size_t MaxFiles = 64;

    // Loads "<decimal id>.bin" files. Anything else, unreadable files and oversize bodies are
    // skipped; at most MaxFiles are read.
    static ReplayStore LoadDirectory(const std::filesystem::path &directory);

    // Writes "<id>.bin" through a temporary file, but never replaces an existing recording, so
    // the first message of each type wins. False if it already exists, is too large, the
    // directory already holds MaxFiles recordings, or writing fails.
    static bool SaveIfMissing(const std::filesystem::path &directory, std::uint32_t id,
                              std::span<const std::uint8_t> body);

    void Set(std::uint32_t id, std::vector<std::uint8_t> body);
    const std::vector<std::uint8_t> *Find(std::uint32_t id) const;
    std::size_t Size() const { return m_bodies.size(); }

private:
    std::map<std::uint32_t, std::vector<std::uint8_t>> m_bodies;
};
}
