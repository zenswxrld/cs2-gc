"""Read-only Windows CS2 build fingerprints. Uses Python 3.9+ standard library."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys


MODULES = (
    "game/bin/win64/cs2.exe",
    "game/bin/win64/engine2.dll",
    "game/bin/win64/tier0.dll",
    "game/bin/win64/steam_api64.dll",
    "game/csgo/bin/win64/client.dll",
    "game/csgo/bin/win64/server.dll",
)


def pe_info(path):
    """Read architecture and COFF timestamp without loading executable code."""
    with path.open("rb") as source:
        dos = source.read(64)
        if len(dos) < 64 or dos[:2] != b"MZ":
            raise ValueError("Not a PE executable")
        offset = struct.unpack_from("<I", dos, 0x3C)[0]
        if offset < 64 or offset > path.stat().st_size - 26:
            raise ValueError("Invalid PE header offset")
        source.seek(offset)
        header = source.read(26)
        if len(header) != 26 or header[:4] != b"PE\0\0":
            raise ValueError("Invalid PE signature")
        machine, sections, timestamp = struct.unpack_from("<HHI", header, 4)
        optional_size = struct.unpack_from("<H", header, 20)[0]
        magic = struct.unpack_from("<H", header, 24)[0]
        if not sections or optional_size < 2 or offset + 24 + optional_size > path.stat().st_size:
            raise ValueError("Truncated or invalid PE optional header")
        return {"machine": hex(machine), "pe_magic": hex(magic),
                "x64": machine == 0x8664 and magic == 0x20B,
                "coff_timestamp": timestamp}


def file_record(root, relative):
    path = root / relative
    result = {"path": relative, "present": path.is_file()}
    if not result["present"]:
        return result
    try:
        before = path.stat()
        result["bytes"] = before.st_size
        result.update(pe_info(path))
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("File changed during inspection; wait for Steam to finish updating")
        result["sha256"] = digest.hexdigest()
    except (OSError, ValueError, struct.error) as error:
        result["error"] = str(error)
    return result


def inspect(root):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError("Game directory does not exist")
    modules = [file_record(root, relative) for relative in MODULES]
    result = {
        "format_version": 1,
        "target": "cs2-windows-x64",
        "runtime_compatibility": "unverified",
        "modules": modules,
        "steam_inf": {},
        "armory_integration": "pending client script inspection",
    }
    steam_inf = root / "game/csgo/steam.inf"
    if steam_inf.is_file():
        # Only record build identifiers, never account data or arbitrary file text.
        for line in steam_inf.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() in {"ClientVersion", "ServerVersion", "PatchVersion", "ProductName", "appID"}:
                result["steam_inf"][key.strip()] = value.strip()
    manifest = root.parent.parent / "appmanifest_730.acf"
    if manifest.is_file():
        match = re.search(r'"buildid"\s+"(\d+)"', manifest.read_text(encoding="utf-8", errors="replace"))
        if match:
            result["steam_build_id"] = match.group(1)
    result["layout_complete"] = all(module["present"] and module.get("x64")
                                    and not module.get("error") for module in modules)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game_root", type=Path,
                        help='Steam game directory containing the "game" folder')
    parser.add_argument("--out", type=Path, help="Optional JSON destination outside the game directory")
    args = parser.parse_args(argv)
    try:
        if args.out and args.out.resolve().is_relative_to(args.game_root.resolve()):
            raise ValueError("Choose an output path outside the game directory")
        report = inspect(args.game_root)
        text = json.dumps(report, indent=2) + "\n"
        if args.out:
            # Refuse to replace an existing report without the user's choosing a new name.
            with args.out.open("x", encoding="utf-8") as destination:
                destination.write(text)
            print("Saved build report. CS2 runtime compatibility is still unverified.")
        else:
            print(text, end="")
        return 0 if report["layout_complete"] else 2
    except (OSError, ValueError) as error:
        print(f"Inspection failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
