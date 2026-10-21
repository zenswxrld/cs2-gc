@echo off
cd /d "%~dp0"
python extract_vpk_asset.py gloves/paints/sporty_purple.vmat_c gloves/paints/specialist_fade.vmat_c gloves/paints/slick_red.vmat_c gloves/paints/sporty_blue_white_webbing.vmat_c items/assets/paintkits/volatile_02/glove_driver_brocade_phoenix_red.vmat_c workshop/paintkits/templates/glove_compositor.vmat_c
echo.
echo Send the files in the cs2_gc_extracted folder (zip it). Press any key to close.
pause >nul
