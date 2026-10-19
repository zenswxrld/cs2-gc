#pragma once

#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace cs2_gc
{
enum class ArmoryCategory { Cases, Capsules, Souvenirs, Agents, MusicKits, Other };

struct ArmoryGood
{
    std::uint32_t defIndex{};
    std::string name;
    ArmoryCategory category{};
    std::uint32_t starPrice{};
    std::uint32_t keyDefIndex{}; // zero when not needed; resolved from the CS2 schema
};

struct ArmoryQuery
{
    std::optional<ArmoryCategory> category;
    std::string search;
    std::size_t page{}; // zero-based
    std::size_t pageSize{12};
};

struct ArmoryPage
{
    std::vector<ArmoryGood> goods;
    std::size_t totalGoods{};
    std::size_t page{};
    std::size_t pageCount{};
    bool HasPrevious() const { return page > 0; }
    bool HasNext() const { return pageCount > 0 && page < pageCount - 1; }
};

// One schema-derived catalogue shared by all pages. Pagination is a view,
// never a different inventory or currency balance. Purchasing is not wired yet.
class ArmoryCatalog
{
public:
    explicit ArmoryCatalog(std::vector<ArmoryGood> goods);
    ArmoryPage Query(const ArmoryQuery &query) const;
    const ArmoryGood *Find(std::uint32_t defIndex) const;

private:
    std::vector<ArmoryGood> m_goods;
};
}
