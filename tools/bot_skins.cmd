@echo off
cd /d "%~dp0"
echo Bot skins: installs Metamod:Source, CounterStrikeSharp and the BotRandomizer plugin (downloaded from their
echo official release pages) with popular loadouts. Close CS2 first.
echo.
echo   1 = install / update     2 = remove     3 = status
set /p choice=Choose 1, 2 or 3: 
if "%choice%"=="1" python bot_skins.py install
if "%choice%"=="2" python bot_skins.py uninstall
if "%choice%"=="3" python bot_skins.py status
echo.
echo Press any key to close.
pause >nul
