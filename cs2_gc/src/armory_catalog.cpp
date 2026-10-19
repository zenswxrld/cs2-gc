#include "cs2_gc/armory_catalog.h"
#include <algorithm>
#include <stdexcept>
#include <string_view>
#include <unordered_set>

namespace cs2_gc
{
namespace
{
std::string FoldAscii(std::string_view text)
{
    std::string result{text};
    for (auto &ch : result)
        if (ch >= 'A' && ch <= 'Z')
            ch = static_cast<char>(ch + ('a' - 'A'));
    return result;
}
}

ArmoryCatalog::ArmoryCatalog(std::vector<ArmoryGood> goods) : m_goods{std::move(goods)}
{
    std::unordered_set<std::uint32_t> ids;
    for (const auto &good : m_goods)
    {
        const auto category = static_cast<unsigned>(good.category);
        if (!good.defIndex || good.name.empty() || !ids.insert(good.defIndex).second
            || category > static_cast<unsigned>(ArmoryCategory::Other))
            throw std::invalid_argument("Armory goods need a unique nonzero def index, name and category");
    }
}

const ArmoryGood *ArmoryCatalog::Find(std::uint32_t defIndex) const
{
    const auto found = std::find_if(m_goods.begin(), m_goods.end(),
        [defIndex](const auto &good) { return good.defIndex == defIndex; });
    return found == m_goods.end() ? nullptr : &*found;
}

ArmoryPage ArmoryCatalog::Query(const ArmoryQuery &query) const
{
    // The UI should return to page zero when category/search changes.
    const auto size = std::clamp<std::size_t>(query.pageSize, 1, 60);
    const auto search = FoldAscii(query.search);
    std::vector<const ArmoryGood *> matches;
    for (const auto &good : m_goods)
    {
        if (query.category && good.category != *query.category)
            continue;
        if (!search.empty() && FoldAscii(good.name).find(search) == std::string::npos)
            continue;
        matches.push_back(&good);
    }
    ArmoryPage result;
    result.totalGoods = matches.size();
    result.pageCount = matches.size() / size + (matches.size() % size != 0);
    if (!result.pageCount)
        return result;
    result.page = std::min(query.page, result.pageCount - 1);
    const auto start = result.page * size;
    const auto count = std::min(size, matches.size() - start);
    for (std::size_t i = 0; i < count; ++i)
        result.goods.push_back(*matches[start + i]);
    return result;
}
}
