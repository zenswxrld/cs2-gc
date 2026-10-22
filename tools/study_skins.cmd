@echo off
cd /d "%~dp0"
echo Reading every gun finish (read-only, takes a minute)...
python study_skins.py
echo.
echo Send cs2_gc_skin_study.zip from this folder. Press any key to close.
pause >nul
