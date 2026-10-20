@echo off
rem Turns the VPK overrides OFF for good: deletes the VPKs and stops the helper writing them.
rem To turn them back on, delete cs2_gc_no_vpk.txt from this folder.
cd /d "%~dp0"
echo disabled> cs2_gc_no_vpk.txt
for /d %%D in ("..\..\cs2_gc_*") do (
  del /q "%%D\pak01_dir.vpk" "%%D\pak01_000.vpk" 2>nul
)
echo Done. Start CS2 again.
pause
