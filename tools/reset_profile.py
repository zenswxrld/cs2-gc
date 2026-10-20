"""Reset the local profile. Run with CS2 and the helper closed.

  progress  level/XP, Premier rank, match count and reward cursors only; items, loadout and stars are kept
  all       everything above plus the inventory (a completely fresh profile)

Files are moved into a dated backup folder beside this script, never deleted. Level/XP live in the inventory's
"progression" block and are re-derived from cs2_gc_gsi_state.json (cumulative XP, Premier, matches), so both are reset.
"""
from pathlib import Path
import re
import shutil
import sys
import time

STATE = ['cs2_gc_gsi_state.json', 'cs2_gc_rewards.txt', 'cs2_gc_matches.txt', 'cs2_gc_premier.txt',
         'cs2_gc_console.txt', 'cs2_gc_console_boot.txt']
INVENTORY = 'cs2_gc_inventory.txt'
PROGRESSION = re.compile(r'^([ \t]*)"progression"[ \t]*\{[^}\n]*\}[ \t]*$', re.M)
LEVEL_REWARDS = re.compile(r'^[ \t]*"level_reward_total"[ \t]*"\d+"[ \t]*\r?\n', re.M)


def reset_inventory_progress(text):
    if len(PROGRESSION.findall(text)) > 1:
        raise ValueError('Inventory has more than one progression block; leaving it unchanged')
    text = PROGRESSION.sub(lambda m: m.group(1) + '"progression" { "level" "1" "xp" "0" "reward_total" "0" }', text)
    return LEVEL_REWARDS.sub('', text)


def reset(directory, mode):
    directory = Path(directory)
    if mode not in ('progress', 'all'):
        raise ValueError('mode must be progress or all')
    backup = directory / time.strftime('cs2_gc_profile_backup_%Y%m%d_%H%M%S')
    backup.mkdir()
    moved = []
    for name in STATE + ([INVENTORY] if mode == 'all' else []):
        if (directory / name).exists():
            shutil.move(str(directory / name), str(backup / name)); moved.append(name)
    inventory = directory / INVENTORY
    if mode == 'progress' and inventory.exists():
        original = inventory.read_text(encoding='utf-8')
        shutil.copy2(inventory, backup / INVENTORY)
        updated = reset_inventory_progress(original)
        if updated != original:
            temporary = inventory.with_name(inventory.name + '.tmp')
            temporary.write_text(updated, encoding='utf-8', newline='')
            temporary.replace(inventory)
    return backup, moved


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'progress'
    try:
        backup, moved = reset(Path(__file__).resolve().parent, mode)
    except (OSError, ValueError) as error:
        print('Reset failed: ' + str(error)); raise SystemExit(1)
    print('Reset (' + mode + ') done. Backup: ' + backup.name + ' (' + (', '.join(moved) or 'nothing moved') + ')')
