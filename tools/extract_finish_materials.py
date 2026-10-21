"""Copy finishes' composite materials AND the materials they name out of the installed pak01 (read-only), so
their colour and effect parameters (metal flake, pearl, iridescence) can be inspected.

Usage (from game\\bin\\win64):  python extract_finish_materials.py weapons/paints/timed_drops/soe_teal_glitter.vcompmat
Writes into a cs2_gc_extracted folder next to this script.
"""
from pathlib import Path
import sys

import kv3
from native_finishes import Source

DEFAULT = ('weapons/paints/timed_drops/soe_teal_glitter.vcompmat', 'weapons/paints/timed_drops/soe_pink_pearl.vcompmat',
           'weapons/paints/timed_drops/soe_iridescent_purple.vcompmat',
           'weapons/paints/timed_drops/soe_metallic_green_2.vcompmat',
           'weapons/paints/set_graphic_design/cu_glitter_deagle.vcompmat')


def materials(node, found):
    """Every string in the composite document that names a .vmat."""
    if isinstance(node.value, list):
        for child in node.value:
            materials(child[1] if isinstance(child, tuple) else child, found)
    elif isinstance(node.value, str) and node.value.endswith('.vmat'):
        found.add(node.value)
    return found


def main(names):
    game = Path(__file__).resolve().parent.parent.parent
    out = Path(__file__).resolve().parent / 'cs2_gc_extracted'
    source = Source(vpk=game / 'csgo' / 'pak01_dir.vpk')
    for name in names:
        data = source.read(name + '_c')
        if data is None: print(name, '-> not found'); continue
        wanted = {name + '_c': data}
        _, blocks = kv3.read_resource(data)
        _, root = kv3.read_kv3(dict(blocks)['DATA'])
        for material in sorted(materials(root, set())):
            found = source.read(material + '_c')
            if found is not None: wanted[material + '_c'] = found
            else: print('  missing', material)
        for path, content in wanted.items():
            target = out / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            print('wrote', target, len(content), 'bytes')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:] or DEFAULT))
