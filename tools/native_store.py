"""Prepare missing terminal Store entries without changing recorded replies.

The native laptop calls StoreItemPurchase(definition(container_id)). An outdated
price sheet cannot resolve newer definitions and may never send PurchaseInit.
Keep all original response fields, prices/currencies and existing store entries.
"""
from pathlib import Path
import struct
import zlib
import price_sheet as sheet


def terminal_names(source):
    sections = sheet.items_game.collect(sheet.items_game.parse(source))
    found = []
    for _, node in sections.get('items', {}).items():
        if not isinstance(node, list): continue
        values = sheet.items_game.as_dict(node)
        attributes = values.get('attributes')
        if not isinstance(attributes, list): continue
        flag = sheet.items_game.as_dict(attributes).get('volatile container')
        if isinstance(flag, list) and sheet.items_game.as_dict(flag).get('value') == '1':
            name = values.get('name')
            if isinstance(name, str): found.append(name)
    if not found: raise ValueError('No explicit volatile terminal definitions in supplied schema')
    return found


def patch(body, source):
    _, _, container = sheet.read_message(body)
    raw = sheet.decompress(container)
    tree = sheet.decode_kv(raw)
    if sheet.encode_kv(tree) != raw: raise ValueError('Store sheet cannot be edited losslessly')
    entries = sheet.section(tree, 'store', 'entries')
    template = next((name for name, values in entries if isinstance(values, list) and
                     isinstance(dict(values).get('prices'), list) and dict(values)['prices']), None)
    if template is None: raise ValueError('Store sheet has no validated price template')
    added = sheet.add_entries(tree, terminal_names(source), template)
    if not added: return body, 0
    changed = sheet.encode_kv(tree)
    replacements = {4: (5, struct.pack('<I', zlib.crc32(changed))), 8: (2, sheet.compress(changed))}
    output = bytearray()
    for number, wire, value in sheet.read_fields(body):
        if number in replacements: wire, value = replacements.pop(number)
        output.extend(sheet.write_field(number, wire, value))
    for number, (wire, value) in replacements.items(): output.extend(sheet.write_field(number, wire, value))
    if sheet.decode_kv(sheet.decompress(sheet.read_message(output)[2])) != tree:
        raise ValueError('Rebuilt Store sheet failed validation')
    return bytes(output), added


def prepare(directory, config):
    directory = Path(directory)
    target = directory / 'cs2_gc_store_2501.bin'
    if not config['terminals_enabled']:
        if target.exists(): target.unlink()
        return 'disabled'
    original = directory / 'cs2_gc_replay/2501.bin'
    source = directory / 'items_game.txt'
    if not original.is_file() or not source.is_file(): return 'unavailable: replay/2501.bin or original schema missing'
    result, count = patch(original.read_bytes(), source.read_text(encoding='utf-8-sig'))
    if not target.exists() or target.read_bytes() != result:
        temporary = target.with_name(target.name + '.tmp')
        temporary.write_bytes(result); temporary.replace(target)
    return f'ready: {count} missing terminal Store definitions added; original replay unchanged'
