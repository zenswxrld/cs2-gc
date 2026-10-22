"""Eligible Weekly/Armory donors, selected from the user's actual schema.

Weapon-specific artwork stays on its source weapon. No guessed material paths.
"""
from dataclasses import dataclass
import re
from inventory_item import collect, parse, as_dict
from armory_rotation_catalog import ARMORY_COLLECTIONS

REQUIRED = {
    'Crimson Foil': ('gsch_sport_ump45', 'weapon_ump45'),
    'Rainbow Spoon': ('aq_titanium_rainbow_galilar', 'weapon_galilar'),
}
# Generic transfers require both an eligible style and a generic material name.
# Custom/anodized artwork (7/9/10) remains on its original weapon.
GENERIC_STYLES = {'1', '2', '3', '4', '5', '6', '8'}
AFFINITIES = {
    'forged': ('metal','copper','foil','steel','forge','bronze','flame','titanium'),
    'phantom_blade': ('ghost','iridescent','titanium','ripple','abstract','glitch','smoke'),
    'harbor': ('blue','sea','arctic','water','wave','cloud','teal','navy'),
    'mosaic': ('poly','facet','shape','geometric','mosaic','paisley','mandala','halftone'),
    'kestrel': ('bird','wing','geobirds','usaf','air','tiger','feather'),
    'juggernaut': ('metal','steel','plate','camo','carbon','titanium','defense'),
    'lodestar': ('star','constellation','iridescent','peaks','ripple','sky','galaxy'),
    'fathom': ('blue','coral','flow','water','sea','teal','ripple','topo'),
    'cipher': ('binary','glitch','tech','circuit','perimeter','autoexec','hex','grid'),
    'driftwood': ('wood','grain','branches','palm','forest','jungle','knot','thicket'),
    'insignia': ('gold','copper','foil','mandala','paisley','ribbon','stencil'),
    'warden': ('perimeter','defense','steel','site','grid','hex','urban','camo'),
}

@dataclass(frozen=True)
class Donor:
    name: str
    material: str
    style: str
    weapons: tuple
    collections: tuple
    generic: bool


def catalog(schema, kits, kit_path):
    import native_finishes as finishes
    found = {}
    for collection, node in collect(parse(schema)).get('item_sets', {}).items():
        if collection not in ARMORY_COLLECTIONS and not collection.startswith('set_timed_drops_'):
            continue
        if not isinstance(node, list):
            continue
        for entry, _ in as_dict(node).get('items', []):
            match = re.fullmatch(r'\[([^\]]+)\](weapon_[a-z0-9_]+)', entry)
            if match and match[1] in kits:
                row = found.setdefault(match[1], [set(),set()])
                row[0].add(match[2]); row[1].add(collection)
    rows = {}
    for name, (weapons, collections) in sorted(found.items()):
        values = kits[name][1]
        generic = (values.get('style') in GENERIC_STYLES
                   and not any(word in name for word in finishes.WEAPON_WORDS))
        rows[name] = Donor(name, kit_path(name,values).replace('\\','/').lower(),
            values.get('style',''), tuple(sorted(weapons)), tuple(sorted(collections)), generic)
    return rows


def previous_materials(entries, kits, kit_path):
    bases = sorted(kits,key=lambda n:(-len(n),n))
    used = set()
    for entry in entries:
        kit = entry.split(']')[0].lstrip('[')
        base = next((n for n in bases if n==kit or '_'+n+'_' in '_'+kit+'_'),None)
        if base:
            used.add(kit_path(base,kits[base][1]).replace('\\','/').lower())
    return used


def candidates(rows, icon, weapon, used, counts, seen, limit=2):
    words = AFFINITIES.get(icon,tuple(icon.split('_')))
    def score(row):
        text = row.name.replace('_',' ')
        fit = sum(1 for word in words if word in text)
        return (-fit, counts.get(row.material,0), row.name)
    return sorted((row for row in rows.values()
        if (row.generic or weapon in row.weapons) and row.material not in used
        and row.material not in seen and counts.get(row.material,0)<limit), key=score)
