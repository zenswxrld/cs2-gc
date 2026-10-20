#include "cs2_gc/keyvalues.h"

namespace cs2_gc
{
const KvNode *KvNode::Find(std::string_view name) const
{
    for (const KvNode &child : children)
        if (child.key == name)
            return &child;
    return nullptr;
}

std::string_view KvNode::Value(std::string_view name, std::string_view fallback) const
{
    const KvNode *child = Find(name);
    return child && !child->block ? std::string_view{child->value} : fallback;
}

namespace
{
constexpr std::size_t MaxDepth = 64;

struct Lexer
{
    std::string_view text;
    std::size_t pos{};

    // kind: 0 end, 1 string, 2 '{', 3 '}', -1 error
    int Next(std::string &out)
    {
        for (;;)
        {
            while (pos < text.size() && (text[pos] == ' ' || text[pos] == '\t' || text[pos] == '\r' || text[pos] == '\n'))
                ++pos;
            if (pos + 1 < text.size() && text[pos] == '/' && text[pos + 1] == '/')
            {
                while (pos < text.size() && text[pos] != '\n')
                    ++pos;
                continue;
            }
            break;
        }
        if (pos >= text.size())
            return 0;
        const char c = text[pos];
        if (c == '{')
            return ++pos, 2;
        if (c == '}')
            return ++pos, 3;
        if (c != '"')
            return -1;
        ++pos;
        out.clear();
        while (pos < text.size() && text[pos] != '"')
        {
            if (text[pos] == '\\' && pos + 1 < text.size())
            {
                const char e = text[pos + 1];
                out.push_back(e == 'n' ? '\n' : e == 't' ? '\t' : e);
                pos += 2;
            }
            else
                out.push_back(text[pos++]);
        }
        if (pos >= text.size())
            return -1;
        ++pos;
        return 1;
    }
};
}

std::optional<KvNode> ParseKeyValues(std::string_view text)
{
    if (text.starts_with("\xEF\xBB\xBF"))
        text.remove_prefix(3);

    Lexer lexer{text};
    KvNode root;
    root.block = true;
    std::vector<KvNode *> stack{&root};
    std::string token;
    std::optional<std::string> pendingKey;

    for (;;)
    {
        const int kind = lexer.Next(token);
        if (kind < 0)
            return std::nullopt;
        if (kind == 0)
            break;

        KvNode &parent = *stack.back();
        if (kind == 1)
        {
            if (!pendingKey)
            {
                pendingKey = token;
                continue;
            }
            KvNode node;
            node.key = std::move(*pendingKey);
            node.value = token;
            parent.children.push_back(std::move(node));
            pendingKey.reset();
        }
        else if (kind == 2)
        {
            if (!pendingKey || stack.size() >= MaxDepth)
                return std::nullopt;
            KvNode node;
            node.key = std::move(*pendingKey);
            node.block = true;
            parent.children.push_back(std::move(node));
            stack.push_back(&parent.children.back());
            pendingKey.reset();
        }
        else
        {
            if (pendingKey || stack.size() == 1)
                return std::nullopt;
            stack.pop_back();
        }
    }

    if (pendingKey || stack.size() != 1)
        return std::nullopt;
    return root;
}
}
