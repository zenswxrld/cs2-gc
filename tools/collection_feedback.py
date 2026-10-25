"""Explicit client-review repairs; leave every other source's treatment unchanged."""
# Native paint alpha is material data on these sources. Opt into RGB processing
# across that mask and coordinate their art, without touching normal/wear inputs.
MODES={
 'cu_mac10_redhot':5, 'cu_mag7_redhot':5,
 'gs_m4a1s_snakebite_gold':5,
 'glock_ghost_protocol_red':5, 'soe_iridescent_purple':5,
 'cu_glock_eyecontact':5, 'cu_ak_neon_rider':5,
 'awp_printstream':8, 'cu_m4a1_howling':5,
 'cu_awp_viper':5, 'cu_ak-47_phantom_disruptor':5,
 'gsch_axia_glock':5, 'gs_ak47_empress':9,
}

def bindings(kit,primary):
    if kit=='glock_ghost_protocol_red':return (primary,'g_tOverlay')
    if kit=='gsch_axia_glock':return (primary,'g_tCaseHardeningColorRamp')
    return (primary,)
