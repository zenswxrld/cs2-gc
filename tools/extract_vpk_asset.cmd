@echo off
cd /d "%~dp0"
python extract_vpk_asset.py gloves/paints/volatile_02/glove_driver_brocade_phoenix_red.vcompmat_c gloves/paints/sporty_purple.vcompmat_c gloves/paints/specialist_fade.vcompmat_c gloves/paints/slick_red.vcompmat_c gloves/paints/_shared_paint_generic.vcompmat_c
echo.
echo Send the files in the cs2_gc_extracted folder (zip it). Press any key to close.
pause >nul
