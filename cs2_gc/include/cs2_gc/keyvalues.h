#pragma once

#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace cs2_gc
{
// Valve KeyValues text. Keys may repeat (items_game.txt repeats whole sections),
// so children stay an ordered list instead of a map.
struct KvNode
{
    std::string key;
    std::string value;
    std::vector<KvNode> children;
    bool block{};

    const KvNode *Find(std::string_view name) const; // first child
    std::string_view Value(std::string_view name, std::string_view fallback = {}) const;
};

// Returns the synthetic root holding every top-level key, or nothing when the
// text is malformed (unbalanced braces, unterminated string, nesting too deep).
std::optional<KvNode> ParseKeyValues(std::string_view text);
}
