@echo off
cd /d "%~dp0"
python extract_vpk_asset.py weapons/paints/legacy/aa_fade.vcompmat_c weapons/paints/legacy/am_doppler_phase1.vcompmat_c weapons/paints/legacy/am_marble_fade.vcompmat_c weapons/paints/legacy/aq_oiled.vcompmat_c weapons/paints/legacy/hy_webs.vcompmat_c materials/models/weapons/customization/paints/vmats/aa_fade.vmat_c panorama/images/econ/default_generated/weapon_bayonet_aa_fade_light_png.vtex_c
echo.
echo Send the files in the cs2_gc_extracted folder (zip it). Press any key to close.
pause >nul
