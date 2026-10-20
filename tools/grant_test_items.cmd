@echo off
cd /d "%~dp0"
echo Close CS2 before continuing. This adds test items and backs up your inventory.
pause
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 "%~dp0grant_test_items.py"
) else (
  python "%~dp0grant_test_items.py"
)
pause
