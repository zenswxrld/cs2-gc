@echo off
cd /d "%~dp0"
echo Close CS2 before continuing. This adds 20 Custom Skins Test Case 2s (the rest of the guns, Twilight Galaxy, Gold Brick, Blue Phosphor) and backs up your inventory.
pause
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 "%~dp0grant_custom_cases.py" --gauntlet 0 --custom-skins-test2 20
) else (
  python "%~dp0grant_custom_cases.py" --gauntlet 0 --custom-skins-test2 20
)
pause
