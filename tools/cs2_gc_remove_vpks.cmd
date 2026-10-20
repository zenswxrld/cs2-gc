@echo off
rem Deletes the override VPKs from every game\cs2_gc_* folder (they are rebuilt the next time the helper runs).
rem Run this FIRST if CS2 will not start. Your loose files and settings are left alone.
cd /d "%~dp0"
for /d %%D in ("..\..\cs2_gc_*") do (
  del /q "%%D\pak01_dir.vpk" "%%D\pak01_000.vpk" 2>nul
)
if exist vpk.signatures.cs2_gc_backup copy /y vpk.signatures.cs2_gc_backup vpk.signatures >nul
echo Done (vpk.signatures restored from its backup if one existed). Start CS2 again.
pause
