@echo off
cd /d "%~dp0"
echo Manual diagnostic mode. Normally CS2 starts rewards in the background automatically.
if not exist "..\..\csgo\cfg" (
  echo Put this helper beside steam_api64.dll in game\bin\win64 first.
  pause
  exit /b 1
)
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 "%~dp0gsi_rewards.py" --proxy-dir "%~dp0." --cfg-dir "%~dp0..\..\csgo\cfg"
) else (
  python "%~dp0gsi_rewards.py" --proxy-dir "%~dp0." --cfg-dir "%~dp0..\..\csgo\cfg"
)
pause
