ENCODER_ENABLE = yes
ENCODER_MAP_ENABLE = yes
RGB_MATRIX_ENABLE = yes
RGB_MATRIX_DRIVER = ws2812
WS2812_DRIVER = vendor
NKRO_ENABLE = yes
EXTRAKEY_ENABLE = yes
MOUSEKEY_ENABLE = yes
BOOTMAGIC_ENABLE = yes

# Phase 3 Cycle 2 (RED-FW MINOR #21-22):
#   VIA_ENABLE=yes lets users re-map the 11 macro keys + BT-layer
#   bindings from VIA's web UI instead of recompiling; RAW_ENABLE=yes
#   is a VIA prerequisite. ENCODER_MAP_ENABLE above (was ENCODER_ENABLE
#   only in Cycle 1) lets us give the encoder push a real keycode
#   (KC_ENT by default) in the encoder_map.c the QMK keymap ships.
VIA_ENABLE = yes
RAW_ENABLE = yes
