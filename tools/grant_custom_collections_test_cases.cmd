@echo off
cd /d "%~dp0"
echo Close CS2 before continuing. This adds 20 Custom Collections Test Cases (rolls the 40 custom collections like a real case) and backs up your inventory.
pause
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 "%~dp0grant_custom_cases.py" --gauntlet 0 --collections-test 20
) else (
  python "%~dp0grant_custom_cases.py" --gauntlet 0 --collections-test 20
)
pause
