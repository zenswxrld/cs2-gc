@echo off
cd /d "%~dp0"
echo Close CS2 before continuing. This adds 20 Gauntlet Cases and backs up your inventory.
pause
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 "%~dp0grant_custom_cases.py" --gauntlet 20
) else (
  python "%~dp0grant_custom_cases.py" --gauntlet 20
)
pause
