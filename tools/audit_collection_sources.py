"""Read public tracked schema metadata in CI; no game binaries or local installs."""
import json
import re
import urllib.request
from pathlib import Path
from inventory_item import collect, parse, as_dict
from native_finishes import titles_from, kit_path

REVISION = "6ac247908a83c309b37314fd097c47dc78103746"
ROOT = "https://raw.githubusercontent.com/SteamTracking/GameTracking-CS2/" + REVISION + "/game/csgo/pak01_dir/"

def read(path):
    request = urllib.request.Request(ROOT + path, headers={"User-Agent": "cs2-gc-source-audit"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read().decode("utf-8-sig")

def main():
    schema = read("scripts/items/items_game.txt")
    english = read("resource/csgo_english.txt")
    sections = collect(parse(schema))
    kits = {as_dict(v)["name"]: (k, as_dict(v)) for k,v in sections["paint_kits"].items()
            if isinstance(v,list) and "name" in as_dict(v)}
    titles = titles_from(english,kits)
    configured = set()
    for filename in ("native_skins.py", "next_collection_lineups.py"):
        text = (Path(__file__).parent / filename).read_text(encoding="utf-8")
        configured.update(re.findall(r"['\"]((?:am|aa|an|aq|hy|so|sp|soe)_[a-z0-9_]+)['\"]", text))
    rows = []
    for set_name, value in sections.get("item_sets", {}).items():
        if not isinstance(value, list):
            continue
        info = as_dict(value)
        items = info.get("items", [])
        if not isinstance(items, list):
            continue
        for entry, _ in items:
            match = re.fullmatch(r"\[([^\]]+)\](weapon_[a-z0-9_]+)", entry)
            if not match or match[1] not in kits:
                continue
            name, weapon = match.groups()
            index, values = kits[name]
            rows.append(dict(collection=set_name, donor=name, title=titles.get(name,""),
                weapon=weapon, index=index, style=values.get("style"),
                material=kit_path(name,values), configured_before=name in configured))
    report = dict(revision=REVISION, rows=rows)
    out = Path("source-audit")
    out.mkdir(exist_ok=True)
    (out / "donors.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    for row in rows:
        print("DONOR " + json.dumps(row,ensure_ascii=True))
    for name, (index, values) in kits.items():
        title = titles.get(name,"")
        if title in ("Rainbow Spoon", "Crimson Foil"):
            print("REQUIRED " + json.dumps(dict(donor=name,index=index,title=title,values=values)))

if __name__ == "__main__":
    main()
