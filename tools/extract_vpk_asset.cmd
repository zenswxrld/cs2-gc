@echo off
cd /d "%~dp0"
python extract_vpk_asset.py panorama/scripts/endofmatch.vts_c panorama/scripts/endofmatch-rank.vts_c panorama/scripts/endofmatch-skillgroup.vts_c panorama/scripts/endofmatch-win.vts_c panorama/layout/endofmatch.vxml_c panorama/layout/endofmatch-rank.vxml_c panorama/layout/endofmatch-skillgroup.vxml_c
echo.
echo Send the files in the cs2_gc_extracted folder (zip it). Press any key to close.
pause >nul
