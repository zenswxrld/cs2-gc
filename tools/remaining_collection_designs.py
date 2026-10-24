"""The remaining 28 gun pools: explicit themes, premium donors and authored labels."""
# Shared source vocabularies describe geometry/materials, not just colours.
POOLS = {
 'heat': 'aa_flames am_electric_red am_jorm_orange am_copper_flecks am_bronze_sparkle am_m4a1-s_alloy_orange am_nuclear_pattern4_famas am_gold_brick am_crystallized am_carbon_fiber am_diamond_plate am_oval_hex hy_gelpen_dark hy_hades hy_red_hex hy_ducts_yellow hy_nuclear_hotorange hye_firework_patches hye_firework_patches_famas sp_mag7_firebitten sp_dapple sp_engine_dirty sp_hazard_bravo sp_nukestripe_orange sp_nukestripe_maroon sp_mesh_forest_fire so_orange_accents so_keycolors so_greyblue',
 'ice': 'am_jorm_blue am_crystallized_silver am_crystallized_blue am_knots_silver am_m4a1s_bluesmoke am_ossify_blue hy_blizzard hy_arctic hy_arctic_contrast hy_forest_winter hy_ocean_bravo hy_varicamo_blue hye_car_wrap4 hye_car_wrap_3 hye_m249_car_wrap_3 hye_mp5_car_wrap4 soe_blue_and_chrome soe_blue_famas soo_mac10_blueberry sp_mesh_glacier sp_mesh_arctic_contrast sp_elites_winter_raider sp_spray_waves_bravo so_whiteout so_whiteout_riptide so_stormfront an_silver aq_blued',
 'water': 'am_jorm_blue am_jorm_green am_ossify_blue am_ossify_blue_p2000_bravo am_seastorm am_seastorm_blood am_seastorm_shojo am_p250_beaded_paint am_mac10_oceani am_mag7_caustic am_mag7_malform am_tec_9_sea_salt am_p250_sputnik am_ump45_electrowave am_zebra_dark hy_ocean_bravo hy_p2000_oceani hy_reef hy_seaside_bravo hy_water_crest hye_topo hye_coral hye_pink_coral sp_galil_wave sp_negev_lionfish sp_spray_water sp_spray_waves_bravo sp_tape_dots_waves so_aqua so_aqua_stmarc so_stormfront aq_leviathan',
 'space': 'am_aqua_flecks am_copper_flecks am_crystallized am_crystallized_blue am_crystallized_dark am_crystallized_silver am_lightning_awp am_numbers_magenta aa_spacerace_orange aa_glock_18_urban_moon_fever aa_ump45_moonrise_sunset hy_zodiac1 hy_zodiac2 hy_hive hy_geometric_steps_pearl hy_cloud_camo soe_pink_pearl soe_purple soe_blue_and_chrome soe_bw_the_end_awp sp_star_bravo sp_spacerace_blue spe_lightning so_night so_space_marine an_silver',
 'prism': 'am_stained_glass am_geometric_steps am_murano_violet am_aug_jumble am_fuschia am_czv2_mf hy_geometric_steps_pearl hy_geometric_steps_green hy_geometric_steps_yellow hy_icosahedron hy_crumple_bravo hy_crumple_dark_bravo hy_kimono_diamonds hy_kimono_diamonds_orange hy_kimono_diamonds_red hy_ali_tile_bravo hy_canals_tile hy_murano_blue hy_murano_orange ht_peaks_rainbow ht_shapes_xm1014 ht_facet_p2000 soo_polysoup_m4a4 soe_ddpat_swirl_bw train_shapes_01 brutalist_architecture aa_vertigogeo_neon sp_kimono_diamonds',
 'stone': 'am_crystallized am_crystallized_blue am_crystallized_dark am_crystallized_dark_green am_crystallized_green am_crystallized_silver am_mac10_malachite am_jade am_crumple am_crumple_bravo am_geometric_steps hy_granite hy_craquelure hy_crumple_bravo hy_crumple_dark_bravo hy_canals_tile hy_ancient_tiles_peach hy_ruins_red hy_veneto_tan soe_yellow_swirl soo_g3sg1_tomato sp_ancient_bright sp_desert_skulls sp_desert_skulls_dawn so_ceramic so_ceramic_negev so_rune_stone brutalist_architecture',
 'fortress': 'am_chainmail am_diamond_plate am_oval_hex am_metals am_negev_glory am_awp_glory am_carbon_fiber am_carbon_fiber_cz75 am_ddpatdense_silver am_ddpatdense_peacock am_army_shine am_metal_inlay ht_metal_edges ht_white_edges hy_blueprint_aqua hy_blueprint_red hy_blueprint_white hy_blueprint_bluered hy_ducts_yellow hy_ducts_grey hy_varicamo_urban hy_red_hex hy_bluehex hye_chrome_ripple so_night so_stormfront sp_asgard_wall sp_mesh_safetyblack sp_hazard_bravo an_gunmetal_bravo aq_blued aq_steel',
 'wood': 'am_bamboo_jungle am_ancient_warm am_ancient_wine am_jade hy_dry_wood hy_ak47lam hy_ak47lam_blue hy_ak47lam_bw hy_ak47lam_green hy_wood_grain_camo_red hy_bamboo_jungle hy_bamboo_jungle_black hy_bamboo_jungle_ink hy_bamboo_stmarc hy_drywood_green hy_forest_boreal hye_green_forest soo_branches sp_dry_wood sp_twigs sp_twigs_beach sp_moro_carving_burnt sp_moro_carving_lightblue sp_moro_carving_yellow sp_moro_textile_green_vine sp_moro_textile_purple_yellow sp_leaves sp_short_tape so_greyblue so_caramel',
 'predator': 'am_tigers_blue am_tigers_brown am_lizard_red am_scorpion_p2000 am_slither_p90 am_nova_sand am_black_panther hy_tiger hy_p250_tiger hy_redtiger hy_tigers_tan hy_v_tiger hy_lizard_skin hy_snakeskin hy_snakeskin_red hy_hunter_blaze_orange hy_hunter_modern hy_nerodia hye_animal_print_lc hye_test_animal_print_45 hye_tiger2 hye_pink_tiger soe_snakeskin sp_zebracam sp_zebracam_blue sp_zebracam_bw sp_zebracam_red sp_snake sp_mesh_python sp_mesh_slashes sp_spray_desert_sage ht_blur_camo_mp5sd',
 'arcane': 'am_jorm_blue am_jorm_green am_jorm_orange am_knots_brown am_knots_silver am_ancient_warm am_ancient_wine am_metal_inlay am_ren_dark am_ren_red am_veneto2 am_veneto_red hy_ancient_tiles_peach hy_authority_purple hy_mayan_dreams_bravo hy_ruins_red hy_hades hy_veneto_purple hy_veneto_tan hy_zodiac1 hy_zodiac2 hy_vines hye_batik_eyes hye_paisley_desat hye_paisley_warm scar_sirocco mac10_arabesque_gold sp_knots_blue sp_labyrinth sp_labyrinth2 sp_labyrinth3 sp_ancient_bright sp_mirage_flowers_tan so_rune_stone',
 'tech': 'am_numbers_magenta am_intelligence_magenta am_intelligence_orange am_intelligence_grey am_famas_dots am_circuitboard_aqua am_circuitboard_green am_circuitboard_orange am_circuitboard_silver am_czv2_mf aa_vertigogeo_neon aa_wiring aa_wiring_yellow aa_engine_performance ht_white_edges ht_abstract_wind hy_vertigogeo hy_vertigoillusion hy_vertigoillusion_yellow hy_vertigospray hy_vertigospray_blue hy_numbers_green hy_technowar_rwb hy_blueprint_aqua hy_blueprint_red hy_red_hex hye_spyglitch_green_m4a1s hye_abstract_knot hye_abstract_knot_m4 hye_green_camo sp_lime_hex sp_technowar_red so_keycolors',
 'ceremony': 'am_awp_glory am_negev_glory am_metals am_p2000_imperial_red am_bronze_sparkle am_scales_bravo am_authority_brown am_numbers_bronze am_metal_inlay am_ren_dark am_ren_red am_veneto2 am_veneto_red hy_authority_purple hy_veneto_purple hy_veneto_tan hy_ren_orange hye_ak47_nouveau hye_paisley_desat mac10_arabesque_gold scar_sirocco soe_blue_and_gold spe_scarf_print sp_asgard_wall am_knots_brown am_knots_silver so_orca so_indigo_and_grey aq_brass aq_copper',
 'air': 'hy_feathers_aug hy_p250_crackshot hy_usaf_round hye_yellow_usaf hye_geobirds hye_geobirds_sunrise hy_icarus hy_hive hy_zodiac3 hy_cloud_camo hy_aug_torn_orange hy_xm1014_fractal_blue hye_abstract_knot hye_abstract_knot_m4 soe_blue_and_chrome spe_missile spe_lightning sp_nova_wind_dispersal sp_spray_waves_bravo sp_tape_dots_waves hy_arctic_contrast hy_varicamo_blue am_p250_sputnik am_ump45_electrowave so_aqua so_stormfront an_titanium30v',
}
PREMIUM = {
 'heat':'am_jorm_orange am_electric_red am_copper_flecks am_m4a1-s_alloy_orange am_nuclear_pattern4_famas am_bronze_sparkle aa_flames',
 'ice':'am_jorm_blue am_m4a1s_bluesmoke am_crystallized_silver am_crystallized_blue am_knots_silver am_ossify_blue soe_blue_and_chrome',
 'water':'am_jorm_blue am_jorm_green am_p250_beaded_paint am_seastorm am_ossify_blue am_mac10_oceani',
 'space':'am_aqua_flecks am_copper_flecks am_numbers_magenta am_lightning_awp hy_geometric_steps_pearl hy_hive soe_pink_pearl soe_purple',
 'prism':'am_stained_glass hy_geometric_steps_pearl am_geometric_steps am_murano_violet am_fuschia soo_polysoup_m4a4',
 'stone':'am_jade am_crystallized_green am_crystallized_dark am_crystallized_blue am_mac10_malachite am_crumple_bravo am_geometric_steps',
 'fortress':'am_metals am_negev_glory am_awp_glory am_chainmail am_diamond_plate am_metal_inlay am_ddpatdense_peacock ht_white_edges',
 'wood':'am_bamboo_jungle am_ancient_warm am_ancient_wine am_jade hy_ak47lam_green hy_dry_wood',
 'predator':'am_tigers_blue am_tigers_brown am_lizard_red am_slither_p90 am_scorpion_p2000 hy_tiger hy_p250_tiger',
 'arcane':'am_jorm_blue am_jorm_green am_jorm_orange am_ancient_warm am_ancient_wine am_knots_silver am_metal_inlay am_veneto2',
 'tech':'am_numbers_magenta am_intelligence_magenta am_intelligence_orange am_famas_dots aa_vertigogeo_neon ht_white_edges hye_spyglitch_green_m4a1s',
 'ceremony':'am_awp_glory am_negev_glory am_metals am_p2000_imperial_red am_bronze_sparkle am_scales_bravo am_veneto2 soe_blue_and_gold',
 'air':'hy_icarus hy_hive hye_abstract_knot hye_abstract_knot_m4 am_p250_sputnik am_ump45_electrowave soe_blue_and_chrome',
}
# icon, source theme, chase weapon, fixed accents, independently rolled premium palette.
SPECS = (
 ('ashfall','heat','ak47',('Crimson','Amber','Ember','Violet'),('Crimson','Amber','Cobalt','Violet','Emerald','Teal')),
 ('aurora','ice','sg556',('Teal','Violet','Glacier','Cobalt'),('Violet','Teal','Emerald','Magenta','Amber','Cobalt')),
 ('brimstone','heat','deagle',('Crimson','Amber','Inferno','Ember'),('Amber','Violet','Emerald','Cobalt','Crimson','Teal')),
 ('cascade','water','fiveseven',('Azure','Teal','Glacier','Cobalt'),('Cobalt','Teal','Violet','Coral','Emerald','Amber')),
 ('cinder','heat','m4a1_silencer',('Ember','Amber','Crimson','Violet'),('Violet','Cobalt','Crimson','Amber','Teal','Emerald')),
 ('eclipse','space','awp',('Midnight','Violet','Royal','Cobalt'),('Violet','Teal','Magenta','Cobalt','Emerald','Amber')),
 ('halcyon','water','usp_silencer',('Azure','Glacier','Teal','Rose'),('Teal','Violet','Rose','Emerald','Cobalt','Amber')),
 ('kaleido','prism','m4a1',('Vapor','Lime','Candy','Royal'),('Violet','Teal','Emerald','Magenta','Amber','Cobalt')),
 ('monsoon','water','sg556',('Cobalt','Teal','Midnight','Glacier'),('Violet','Coral','Teal','Emerald','Amber','Cobalt')),
 ('nebula','space','m4a1_silencer',('Violet','Magenta','Midnight','Cobalt'),('Magenta','Teal','Violet','Emerald','Amber','Cobalt')),
 ('solstice','ceremony','m4a1',('Amber','Ember','Sunrise','Rose'),('Amber','Violet','Cobalt','Emerald','Crimson','Teal')),
 ('zephyr','air','famas',('Teal','Glacier','Azure','Amber'),('Teal','Violet','Amber','Cobalt','Emerald','Magenta')),
 ('tidewater','water','glock',('Teal','Ocean','Glacier','Emerald'),('Emerald','Violet','Coral','Teal','Amber','Cobalt')),
 ('obelisk','stone','m4a1',('Midnight','Cobalt','Royal','Violet'),('Cobalt','Amber','Violet','Emerald','Teal','Magenta')),
 ('zenith','air','awp',('Cobalt','Glacier','Amber','Azure'),('Violet','Amber','Teal','Cobalt','Emerald','Magenta')),
 ('rampart','fortress','ak47',('Cobalt','Crimson','Amber','Midnight'),('Crimson','Cobalt','Amber','Violet','Emerald','Teal')),
 ('ironclad','fortress','negev',('Cobalt','Glacier','Midnight','Amber'),('Cobalt','Amber','Violet','Emerald','Crimson','Teal')),
 ('marauder','predator','ak47',('Crimson','Ember','Amber','Forest'),('Crimson','Violet','Cobalt','Amber','Emerald','Teal')),
 ('nightwatch','tech','m4a1_silencer',('Midnight','Violet','Cobalt','Teal'),('Violet','Teal','Amber','Emerald','Cobalt','Magenta')),
 ('outrider','predator','sg556',('Amber','Forest','Ember','Teal'),('Amber','Violet','Cobalt','Emerald','Crimson','Teal')),
 ('quarry','stone','deagle',('Amber','Emerald','Cobalt','Glacier'),('Emerald','Cobalt','Violet','Amber','Teal','Magenta')),
 ('redoubt','fortress','m4a1',('Crimson','Cobalt','Midnight','Amber'),('Crimson','Cobalt','Amber','Violet','Teal','Emerald')),
 ('talisman','arcane','p250',('Magenta','Emerald','Amber','Royal'),('Magenta','Emerald','Cobalt','Amber','Violet','Teal')),
 ('undertow','water','mac10',('Teal','Midnight','Cobalt','Emerald'),('Teal','Violet','Coral','Emerald','Amber','Cobalt')),
 ('cipher','tech','glock',('Teal','Emerald','Cobalt','Midnight'),('Emerald','Cobalt','Violet','Amber','Teal','Magenta')),
 ('driftwood','wood','aug',('Amber','Teal','Forest','Coral'),('Amber','Teal','Violet','Cobalt','Emerald','Magenta')),
 ('insignia','ceremony','famas',('Amber','Royal','Crimson','Cobalt'),('Amber','Cobalt','Violet','Crimson','Emerald','Teal')),
 ('warden','fortress','xm1014',('Cobalt','Amber','Midnight','Crimson'),('Cobalt','Amber','Violet','Crimson','Emerald','Teal')),
)

def designs():
    from next_collection_lineups import OLDER_NAMES
    extra={
      'cipher':'Root Access|Encrypted Halo|Ghost Protocol|Circuit Trace|Code Prism|Signal Lock|Packet Grid|Zero Day|Wireframe|Checksum|Cold Boot|Port Mark|Data Dust|Relay|Binary Ink|Static',
      'driftwood':'Weathered Crown|Sea Lacquer|Saltwood|Coastal Grain|Tidal Rings|Bleached Timber|Old Varnish|Shoreline|Woodcut|Jetty|Grain Mark|Tide Worn|Barkline|Beach Ash|Salt Stain|Splinter',
      'insignia':'High Command|Ceremonial Guard|Royal Standard|Rank Crest|Honour Guard|Laurel Steel|Regimental|Ensign|Service Mark|Bannerline|Dress Plate|Old Medal|Field Rank|Brass Mark|Unit Stripe|Parade',
      'warden':'Lockdown|Restricted Access|Iron Authority|Security Glass|Guard Shift|Barred Crest|Keyway|Warning Line|Steel Gate|Perimeter|Cold Cell|Latch|Checkpoint|Watch Detail|Gridlock|Duty Mark'}
    result={}
    for icon,group,weapon,palette,family_palette in SPECS:
        result[icon]={'revision':2 if icon in ('outrider','rampart','quarry') else 1,'weapon':'weapon_'+weapon,'palette':palette,
          'family_palette':family_palette,'full_family_palette':True,'motifs':(), 'allow':tuple(dict.fromkeys(POOLS[group].split()+['am_carbon_fiber','am_oval_hex','an_silver','aq_blued','so_whiteout_riptide','so_night'])),
          'premium':tuple(PREMIUM[group].split()),'native_chase':False,
          'modes':{'ancient':('family',),'legendary':('family','fixed'),
                   'mythical':('fixed',)*3,'rare':('fixed',)*4,'uncommon':('fixed',)*3+('transfer',)*3},
          'names':tuple((OLDER_NAMES.get(icon) or extra[icon]).split('|')),
          'theme_group':group}
    result['outrider'].update(weapon='weapon_aug',
      chase={'donor':'am_jade','weapon':'weapon_aug','label':'Trailbreaker','required':True})
    result['quarry'].update(weapon='weapon_deagle',
      chase={'donor':'am_crystallized_blue','weapon':'weapon_deagle','label':'Bedrock','required':True})
    result['rampart'].update(weapon='weapon_m4a1_silencer',
      chase={'donor':'am_metals','weapon':'weapon_m4a1_silencer','label':'Iron Bastion','required':True})
    return result
