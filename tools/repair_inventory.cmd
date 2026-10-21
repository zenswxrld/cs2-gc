@echo off
cd /d "%~dp0"
echo Close CS2 before continuing. This repairs cs2_gc_inventory.txt after the 26c case grant (backs it up first).
pause
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 "%~dp0grant_custom_cases.py" --gauntlet 0
) else (
  python "%~dp0grant_custom_cases.py" --gauntlet 0
)
pause
