@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 "%~dp0terminal_purchase.py"
) else (
  python "%~dp0terminal_purchase.py"
)
pause
