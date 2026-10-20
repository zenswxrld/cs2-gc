"""Read, extend and rebuild the Store's price sheet (message 2501, CMsgStoreGetUserDataResponse).

The price sheet is Valve binary KeyValues inside an "LZMA" container inside field 8 of that message.
`dump` prints what a recorded 2501.bin holds. `add-cases` adds a Store entry for every standard case
and any key that has none, taking prices from an existing entry, puts them in the banner layout (and makes
Valve's "View On Market" case tiles sellable), and writes a new 2501.bin to put in
the cs2_gc_replay folder. Output files are never overwritten. Python 3.9+ standard library only.
"""
import argparse
import importlib.util
import lzma
from pathlib import Path
import struct
import sys
import zlib

END = 0x0B
LZMA_MAGIC = b"LZMA"
DICT_SIZE = 1 << 18  # what the recorded sheet uses

_spec = importlib.util.spec_from_file_location("inventory_item", Path(__file__).with_name("inventory_item.py"))
items_game = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(items_game)


# ---- protobuf: just enough for CMsgStoreGetUserDataResponse ----
def read_varint(data, pos):
    result = shift = 0
    while True:
        if pos >= len(data) or shift > 63:
            raise ValueError("bad varint")
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            return result, pos


def write_varint(value):
    out = bytearray()
    while value >= 0x80:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def read_fields(data):
    fields, pos = [], 0
    while pos < len(data):
        tag, pos = read_varint(data, pos)
        number, wire = tag >> 3, tag & 7
        if wire == 0:
            value, pos = read_varint(data, pos)
        elif wire == 5:
            value, pos = data[pos:pos + 4], pos + 4
        elif wire == 1:
            value, pos = data[pos:pos + 8], pos + 8
        elif wire == 2:
            length, pos = read_varint(data, pos)
            if pos + length > len(data):
                raise ValueError("field overruns the message")
            value, pos = data[pos:pos + length], pos + length
        else:
            raise ValueError("unsupported wire type")
        fields.append((number, wire, value))
    return fields


def write_field(number, wire, value):
    tag = write_varint(number << 3 | wire)
    if wire == 0:
        return tag + write_varint(value)
    if wire in (1, 5):
        return tag + value
    return tag + write_varint(len(value)) + value


# ---- LZMA container: "LZMA", unpacked size, packed size, 5 property bytes, raw stream ----
def decompress(container):
    if container[:4] != LZMA_MAGIC or len(container) < 17:
        raise ValueError("not an LZMA container")
    unpacked, packed = struct.unpack_from("<II", container, 4)
    if 17 + packed > len(container) or unpacked > 64 * 1024 * 1024:
        raise ValueError("container sizes are implausible")
    alone = container[12:17] + struct.pack("<Q", unpacked) + container[17:17 + packed]
    out = lzma.decompress(alone, format=lzma.FORMAT_ALONE)
    if len(out) != unpacked:
        raise ValueError("unpacked size does not match the header")
    return out


def compress(raw):
    filters = [{"id": lzma.FILTER_LZMA1, "dict_size": DICT_SIZE, "lc": 3, "lp": 0, "pb": 2}]
    alone = lzma.compress(raw, format=lzma.FORMAT_ALONE, filters=filters)
    properties, stream = alone[:5], alone[13:]  # drop the 8-byte size; the container carries it
    return LZMA_MAGIC + struct.pack("<II", len(raw), len(stream)) + properties + stream


# ---- binary KeyValues ----
class UInt64(int):
    """A 64-bit KeyValues value, kept distinct from the 32-bit ints so the sheet re-encodes exactly."""


def decode_kv(data):
    pos = 0

    def cstr():
        nonlocal pos
        end = data.index(b"\0", pos)
        text = data[pos:end].decode("utf-8", "replace")
        pos = end + 1
        return text

    def block():
        nonlocal pos
        out = []
        while pos < len(data):
            kind = data[pos]
            pos += 1
            if kind in (END, 0x08):
                return out
            key = cstr()
            if kind == 0:
                out.append((key, block()))
            elif kind == 1:
                out.append((key, cstr()))
            elif kind == 2:
                out.append((key, struct.unpack_from("<i", data, pos)[0]))
                pos += 4
            elif kind == 3:
                out.append((key, struct.unpack_from("<f", data, pos)[0]))
                pos += 4
            elif kind == 7:
                out.append((key, UInt64(struct.unpack_from("<Q", data, pos)[0])))
                pos += 8
            else:
                raise ValueError(f"unknown KeyValues type {kind}")
        return out

    return block()


def encode_kv(tree):
    out = bytearray()

    def block(nodes):
        for key, value in nodes:
            name = key.encode("utf-8") + b"\0"
            if isinstance(value, list):
                out.extend(b"\x00" + name)
                block(value)
                out.append(END)
            elif isinstance(value, str):
                out.extend(b"\x01" + name + value.encode("utf-8") + b"\0")
            elif isinstance(value, float):
                out.extend(b"\x03" + name + struct.pack("<f", value))
            elif isinstance(value, UInt64):
                out.extend(b"\x07" + name + struct.pack("<Q", value))
            else:
                out.extend(b"\x02" + name + struct.pack("<i", value))

    block(tree)
    out.append(END)  # closes the root block
    return bytes(out)


# ---- the sheet ----
def read_message(body):
    result, version, container = 1, None, None
    for number, _, value in read_fields(body):
        if number == 1:
            result = value
        elif number == 4:
            version = value
        elif number == 8:
            container = value
    if container is None:
        raise ValueError("message has no price sheet")
    return result, version, container


def build_message(raw_sheet):
    """CMsgStoreGetUserDataResponse with result 1 and a version derived from the sheet's content."""
    version = struct.pack("<I", zlib.crc32(raw_sheet))
    return (write_field(1, 0, 1) + write_field(4, 5, version) + write_field(8, 2, compress(raw_sheet)))


def load_sheet(path):
    _, _, container = read_message(Path(path).read_bytes())
    raw = decompress(container)
    tree = decode_kv(raw)
    if encode_kv(tree) != raw:
        raise ValueError("this sheet does not round-trip through the decoder; refusing to edit it")
    return tree


def section(tree, *path):
    node = tree
    for name in path:
        node = next((v for k, v in node if k == name and isinstance(v, list)), None)
        if node is None:
            raise ValueError("price sheet has no section " + "/".join(path))
    return node


def find_cases(sections):
    """(case name, key name) for every keyed standard case, from items_game sections."""
    return [(case, key) for case, key, _, _ in find_case_items(sections)]


def find_case_items(sections):
    """(case name, key name, case index, key index) for every keyed standard case."""
    items = {k: v for k, v in sections.get("items", {}).items() if isinstance(v, list)}
    prefabs = sections.get("prefabs", {})

    def chain(node, depth=0):
        names = []
        for name in items_game.as_dict(node).get("prefab", "").split():
            names.append(name)
            if name in prefabs and depth < 8:
                names.extend(chain(prefabs[name], depth + 1))
        return names

    def resolve(node, prop, depth=0):
        values = items_game.as_dict(node)
        if prop in values:
            return values[prop]
        for name in values.get("prefab", "").split():
            if name in prefabs and depth < 8:
                found = resolve(prefabs[name], prop, depth + 1)
                if found:
                    return found
        return None

    cases = []
    for index, node in items.items():
        names = chain(node)
        if "weapon_case_base" not in names or "weapon_case_souvenirpkg" in names:
            continue
        if any("_capsule" in n or "graffiti_box" in n for n in names):
            continue
        attributes = resolve(node, "attributes")
        if not isinstance(attributes, list) or not any(k == "set supply crate series" for k, _ in attributes):
            continue
        associated = resolve(node, "associated_items")
        key_index = associated[0][0] if isinstance(associated, list) and associated else resolve(node, "associated_item")
        key_node = items.get(str(key_index)) if key_index else None
        key_name = items_game.as_dict(key_node).get("name") if key_node else None
        if key_node is None:  # a case that opens without a key is not sold with one
            continue
        cases.append((items_game.as_dict(node).get("name"), key_name, str(index), str(key_index)))
    return cases


def add_entries(tree, wanted, price_from):
    """Append a Store entry for each name in `wanted` that has none; returns how many were added."""
    entries = section(tree, "store", "entries")
    existing = {dict(v).get("item_link") for _, v in entries if isinstance(v, list)}
    template = next((v for k, v in entries if k == price_from and isinstance(v, list)), None)
    if template is None:
        raise ValueError(f"no existing entry named {price_from!r} to take prices from")
    prices = dict(template).get("prices")
    added = 0
    for name in wanted:
        if not name or name in existing:
            continue
        entries.append((name, [("item_link", name), ("category_tags", "Misc"), ("prices", [tuple(p) for p in prices])]))
        existing.add(name)
        added += 1
    return added


def add_banner_entries(tree, indices):
    """Make each item index a plain Store tile; returns (tiles added, Steam Market links turned into sales).

    The Store builds its tabs from the banner layout, keyed by item index. An entry with `market_link`
    is shown on the Market tab as "View On Market" instead of being sold; removing it makes the
    item an ordinary tile, priced from its `entries` row.
    """
    layout = section(tree, "store", "store_banner_layout")
    added = unlinked = 0
    for index in dict.fromkeys(indices):
        entry = next((v for k, v in layout if k == index and isinstance(v, list)), None)
        if entry is None:
            layout.append((index, [("custom_format", "single")]))
            added += 1
        elif any(k == "market_link" for k, _ in entry):
            entry[:] = [(k, v) for k, v in entry if k != "market_link"]
            unlinked += 1
    return added, unlinked


def command_dump(args):
    tree = load_sheet(args.sheet)
    entries = section(tree, "store", "entries")
    print(f"{len(entries)} store entries, {len(section(tree, 'store', 'store_banner_layout'))} banner layouts, "
          f"{len(section(tree, 'store', 'currencies'))} currencies")
    for name, value in entries[: args.limit]:
        print(" ", name, "->", dict(value).get("item_link"))
    return 0


def command_add_cases(args):
    tree = load_sheet(args.sheet)
    sections = items_game.collect(items_game.parse(args.items_game.read_text(encoding="utf-8-sig", errors="replace")))
    items = find_case_items(sections)
    cases = [(case, key) for case, key, _, _ in items]
    wanted = [name for case, key in cases for name in (case, key)]
    added = add_entries(tree, wanted, args.price_from)
    tiles, unlinked = add_banner_entries(tree, [i for _, _, case, key in items for i in (case, key)])
    raw = encode_kv(tree)
    message = build_message(raw)
    verify = decode_kv(decompress(read_message(message)[2]))  # the same steps the game takes
    if verify != tree:
        raise ValueError("the rebuilt sheet does not decode back to what was written")
    with args.out.open("xb") as destination:
        destination.write(message)
    print(f"{len(cases)} cases found; {added} new price entries, {tiles} new Store tiles, {unlinked} Steam Market "
          f"links turned into sales ({len(raw)} bytes before compression). Wrote {args.out}.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    dump = commands.add_parser("dump", help="summarise a recorded 2501.bin")
    dump.add_argument("sheet", type=Path)
    dump.add_argument("--limit", type=int, default=10)
    add = commands.add_parser("add-cases", help="add every case and missing key to the Store")
    add.add_argument("sheet", type=Path, help="recorded 2501.bin")
    add.add_argument("items_game", type=Path, help="items_game.txt extracted from the game")
    add.add_argument("--out", type=Path, required=True, help="new 2501.bin; an existing file is never overwritten")
    add.add_argument("--price-from", default="Weapon Case Key", help="existing entry whose prices the new ones copy")
    args = parser.parse_args(argv)
    try:
        return command_dump(args) if args.command == "dump" else command_add_cases(args)
    except (OSError, ValueError, lzma.LZMAError, struct.error, KeyError) as error:
        print(f"Failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
