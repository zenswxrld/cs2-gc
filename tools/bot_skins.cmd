@echo off
cd /d "%~dp0"
echo Bot plugins: installs CS2-Bot-Improver (better aim, grenades, movement, AI, buying, skins) with Metamod:Source
echo and CounterStrikeSharp from their official pages. Bot skill follows your Premier rating. Close CS2 first.
echo.
echo   1 = install / update     2 = remove     3 = status
set /p choice=Choose 1, 2 or 3: 
if "%choice%"=="1" python bot_skins.py install
if "%choice%"=="2" python bot_skins.py uninstall
if "%choice%"=="3" python bot_skins.py status
echo.
echo Press any key to close.
pause >nul
