"""Generate root-level save shortcuts; paths follow the portable game folder."""
def files():
    result={}
    for action,title in (('backup','Back Up Progress'),('restore','Restore Progress')):
        text='@echo off\r\ncd /d "%~dp0.."\r\n"game\\bin\\win64\\cs2_gc_python\\python.exe" -B "game\\bin\\win64\\progress_saves.py" '+action+' --proxy-dir "game\\bin\\win64"\r\necho.\r\npause\r\n'
        result['CS2 GC Saves/'+title+'.cmd']=text.encode()
    result['CS2 GC Saves/READ ME.txt']=('Close CS2 and its rewards helper before using these shortcuts.\r\n'
        'Back Up Progress saves inventory, loadout, XP, rank, stars, mission progress, reward counters and finish mappings together.\r\n'
        'Copy a complete Progress-*.zip into this folder in another version, then use Restore Progress.\r\n'
        'Restore keeps a Before-Restore backup automatically. It never copies old DLLs or generated game assets.\r\n'
        'These are private saves: they contain your local profile. Keep them locally.\r\n').encode()
    result['CS2 GC Settings/Edit Rewards.cmd']=('@echo off\r\ncd /d "%~dp0.."\r\n'
        '"game\\bin\\win64\\cs2_gc_python\\python.exe" -B "game\\bin\\win64\\settings_editor.py"\r\n').encode()
    result['CS2 GC Settings/Edit Settings.cmd']=('@echo off\r\ncd /d "%~dp0.."\r\n'
        '"game\\bin\\win64\\cs2_gc_python\\python.exe" -B "game\\bin\\win64\\settings_editor.py" --all\r\n').encode()
    return result

def install(root):
    from pathlib import Path
    root=Path(root)
    for name,data in files().items():
        target=root/name
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():
            with target.open('xb') as output:output.write(data)
