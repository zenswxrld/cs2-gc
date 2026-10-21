@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 "%~dp0extract_finish_materials.py"
) else (
  python "%~dp0extract_finish_materials.py"
)
echo.
echo Send the files in the cs2_gc_extracted folder (zip it). Press any key to close.
pause >nul
