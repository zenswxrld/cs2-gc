@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 "%~dp0mixed_tradeup.py"
) else (
  python "%~dp0mixed_tradeup.py"
)
pause
