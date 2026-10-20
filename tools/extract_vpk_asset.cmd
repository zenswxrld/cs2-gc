@echo off
cd /d "%~dp0"
python extract_vpk_asset.py panorama/scripts/popups/popup_offers_laptop.vts_c panorama/scripts/popups/popup_offers_laptop_interface.vts_c
echo.
echo Send the files in the cs2_gc_extracted folder (zip it). Press any key to close.
pause >nul
