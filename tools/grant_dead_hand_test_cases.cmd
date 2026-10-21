@echo off
cd /d "%~dp0"
echo Close CS2 before continuing. This adds 20 Dead Hand Test Cases (only the new Dead Hand glove recolours) and backs up your inventory.
pause
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 "%~dp0grant_custom_cases.py" --gauntlet 0 --dead-hand-test 20
) else (
  python "%~dp0grant_custom_cases.py" --gauntlet 0 --dead-hand-test 20
)
pause
