#include "cs2_gc/replay.h"
#include <charconv>
#include <fstream>
#include <iterator>
#include <string>
#include <system_error>

namespace cs2_gc
{
namespace
{
bool ParseId(const std::string &name, std::uint32_t &id)
{
    constexpr std::string_view suffix = ".bin";
    if (name.size() <= suffix.size() || name.size() > 10 + suffix.size() ||
        name.compare(name.size() - suffix.size(), suffix.size(), suffix) != 0)
        return false;
    const char *begin = name.data();
    const char *end = name.data() + name.size() - suffix.size();
    const auto [stop, ec] = std::from_chars(begin, end, id);
    return ec == std::errc{} && stop == end && id != 0;
}
}

ReplayStore ReplayStore::LoadDirectory(const std::filesystem::path &directory)
{
    ReplayStore store;
    std::error_code error;
    for (std::filesystem::directory_iterator it(directory, error), end; !error && it != end; it.increment(error))
    {
        if (store.m_bodies.size() >= MaxFiles)
            break;
        std::uint32_t id = 0;
        if (!it->is_regular_file(error) || !ParseId(it->path().filename().string(), id))
            continue;
        const std::uintmax_t size = it->file_size(error);
        if (error || size > MaxBodyBytes)
        {
            error.clear();
            continue;
        }
        std::ifstream file(it->path(), std::ios::binary);
        std::vector<std::uint8_t> body((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
        if (file.bad() || body.size() != size)
            continue;
        store.m_bodies[id] = std::move(body);
    }
    return store;
}

bool ReplayStore::SaveIfMissing(const std::filesystem::path &directory, std::uint32_t id,
                                std::span<const std::uint8_t> body)
{
    if (id == 0 || body.size() > MaxBodyBytes)
        return false;
    std::error_code error;
    std::filesystem::create_directories(directory, error);
    if (error)
        return false;

    const std::filesystem::path target = directory / (std::to_string(id) + ".bin");
    if (std::filesystem::exists(target, error))
        return false;
    std::size_t files = 0;
    for (std::filesystem::directory_iterator it(directory, error), end; !error && it != end; it.increment(error))
        ++files;
    if (files >= MaxFiles)
        return false;

    std::filesystem::path temp = target;
    temp += ".tmp";
    {
        std::ofstream file(temp, std::ios::binary | std::ios::trunc);
        file.write(reinterpret_cast<const char *>(body.data()), static_cast<std::streamsize>(body.size()));
        file.flush();
        if (!file)
        {
            std::filesystem::remove(temp, error);
            return false;
        }
    }
    std::filesystem::rename(temp, target, error);
    if (error)
    {
        std::filesystem::remove(temp, error);
        return false;
    }
    return true;
}

void ReplayStore::Set(std::uint32_t id, std::vector<std::uint8_t> body)
{
    m_bodies[id] = std::move(body);
}

const std::vector<std::uint8_t> *ReplayStore::Find(std::uint32_t id) const
{
    const auto it = m_bodies.find(id);
    return it == m_bodies.end() ? nullptr : &it->second;
}
}
