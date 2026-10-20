@echo off
rem Resets the local profile. Old files are moved into a dated backup folder, not deleted.
cd /d "%~dp0"
tasklist /fi "imagename eq cs2.exe" | find /i "cs2.exe" >nul
if %errorlevel% equ 0 (
  echo CS2 is still running. Close CS2 completely, then run this again.
  pause
  exit /b 1
)
echo  1 = Reset level, XP and Premier rank only (keep my items)
echo  2 = Reset everything (fresh inventory too)
choice /c 12 /m "Choose"
rem Read the answer straight away: in a .cmd file a later SET clears ERRORLEVEL.
if errorlevel 2 (set MODE=all) else (set MODE=progress)
where py >nul 2>nul
if %errorlevel% equ 0 (py -3 "%~dp0reset_profile.py" %MODE%) else (python "%~dp0reset_profile.py" %MODE%)
pause
