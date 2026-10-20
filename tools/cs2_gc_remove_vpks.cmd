@echo off
rem Deletes the override VPKs from every game\cs2_gc_* folder (they are rebuilt the next time the helper runs).
rem Run this FIRST if CS2 will not start. Your loose files and settings are left alone.
cd /d "%~dp0"
for /d %%D in ("..\..\cs2_gc_*") do (
  del /q "%%D\pak01_dir.vpk" "%%D\pak01_000.vpk" 2>nul
)
echo Done. Start CS2 again.
pause
