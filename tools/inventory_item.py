"""Print a ready-to-paste cs2_gc_inventory.txt entry for a weapon skin, looked up in items_game.txt.

Read-only. Given the weapon and finish names used by the game (for example weapon_ak47 and
cu_ak47_asiimov) it finds the definition and finish indices and works out the rarity the game
shows (finish rarity + the weapon's base rarity - 1, capped at Covert). Uses Python 3.9+ only.
"""
import argparse
from pathlib import Path
import re
import sys

TOKEN = re.compile(r'"((?:[^"\\]|\\.)*)"|([{}])|//[^\n]*')
COVERT = 6


def parse(text):
    """items_game.txt as nested lists of (key, value) pairs; repeated keys are kept."""
    root = []
    stack = [root]
    pending = None
    for match in TOKEN.finditer(text):
        string, brace = match.group(1), match.group(2)
        if string is None and not brace:
            continue
        if brace == "{":
            if pending is None:
                raise ValueError("block without a key")
            node = []
            stack[-1].append((pending, node))
            stack.append(node)
            pending = None
        elif brace == "}":
            if len(stack) == 1 or pending is not None:
                raise ValueError("unbalanced braces")
            stack.pop()
        elif pending is None:
            pending = string
        else:
            stack[-1].append((pending, string))
            pending = None
    if len(stack) != 1 or pending is not None:
        raise ValueError("unterminated block")
    return root


def as_dict(node):
    return {key: value for key, value in node}


def collect(root):
    top = as_dict(root).get("items_game")
    if not isinstance(top, list):
        raise ValueError("no items_game section")
    sections = {}
    for key, value in top:  # items_game.txt repeats whole sections; merge them
        if isinstance(value, list):
            merged = sections.setdefault(key, {})
            for inner_key, inner_value in value:
                merged[inner_key] = inner_value
    return sections


def base_rarity(item, prefabs, depth=0):
    values = as_dict(item)
    if "item_rarity" in values:
        return values["item_rarity"]
    if depth > 8:
        return None
    for name in values.get("prefab", "").split():
        if name in prefabs:
            found = base_rarity(prefabs[name], prefabs, depth + 1)
            if found:
                return found
    return None


def find_entry(sections, weapon, kit):
    items = {as_dict(v).get("name"): (k, v) for k, v in sections.get("items", {}).items() if isinstance(v, list)}
    kits = {as_dict(v).get("name"): (k, v) for k, v in sections.get("paint_kits", {}).items() if isinstance(v, list)}
    if weapon not in items:
        raise ValueError(f"No weapon named {weapon!r} in the schema")
    if kit not in kits:
        raise ValueError(f"No finish named {kit!r} in the schema")
    rarities = {k: int(as_dict(v)["value"]) for k, v in sections.get("rarities", {}).items() if isinstance(v, list)}
    def_index, item = items[weapon]
    kit_index, kit_node = kits[kit]
    kit_rarity = rarities.get(sections.get("paint_kits_rarity", {}).get(kit))
    weapon_rarity = rarities.get(base_rarity(item, sections.get("prefabs", {})))
    if not kit_rarity or not weapon_rarity:
        raise ValueError("The schema does not give both a finish rarity and a weapon rarity")
    kit_values = as_dict(kit_node)
    return {
        "def_index": int(def_index),
        "paint_kit": int(kit_index),
        "rarity": kit_rarity if kit_rarity > COVERT else min(kit_rarity + weapon_rarity - 1, COVERT),
        "wear_min": float(kit_values.get("wear_remap_min", "0")),
        "wear_max": float(kit_values.get("wear_remap_max", "1")),
    }


def render(entry, item_id, wear, seed):
    if not entry["wear_min"] <= wear <= entry["wear_max"]:
        raise ValueError(f"wear must be between {entry['wear_min']} and {entry['wear_max']} for this finish")
    if not 1 <= seed <= 1000:
        raise ValueError("seed must be between 1 and 1000")
    return (f'\t\t"{item_id}"\n\t\t{{\n'
            f'\t\t\t"def_index"\t"{entry["def_index"]}"\n'
            f'\t\t\t"paint_kit"\t"{entry["paint_kit"]}"\n'
            f'\t\t\t"wear"\t"{wear:g}"\n'
            f'\t\t\t"seed"\t"{seed}"\n'
            f'\t\t\t"stattrak"\t"0"\n'
            f'\t\t\t"rarity"\t"{entry["rarity"]}"\n'
            f'\t\t}}\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("items_game", type=Path, help="items_game.txt extracted from the game")
    parser.add_argument("weapon", help="weapon name, e.g. weapon_ak47")
    parser.add_argument("finish", help="finish name, e.g. cu_ak47_asiimov")
    parser.add_argument("--id", type=int, default=1, help="item id inside the inventory file (default 1)")
    parser.add_argument("--wear", type=float, help="wear 0-1 (default: the middle of the finish's range)")
    parser.add_argument("--seed", type=int, default=1, help="pattern seed 1-1000 (default 1)")
    args = parser.parse_args(argv)
    try:
        sections = collect(parse(args.items_game.read_text(encoding="utf-8-sig", errors="replace")))
        entry = find_entry(sections, args.weapon, args.finish)
        wear = args.wear if args.wear is not None else round((entry["wear_min"] + entry["wear_max"]) / 2, 3)
        sys.stdout.write(render(entry, args.id, wear, args.seed))
        print(f"// next_id must be greater than {args.id}", file=sys.stderr)
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(f"Failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
