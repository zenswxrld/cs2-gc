@echo off
cd /d "%~dp0"
python extract_vpk_asset.py panorama/scripts/common/item_context_entries.vts_c panorama/scripts/mainmenu_select_item_for_capability.vts_c panorama/scripts/popups/popup_capability_decodable.vts_c panorama/scripts/popups/popup_select_item_for_capability.vts_c
echo.
echo Send the files in the cs2_gc_extracted folder (zip it). Press any key to close.
pause >nul
