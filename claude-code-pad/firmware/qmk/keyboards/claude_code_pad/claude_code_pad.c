/*
 * Claude Code Pad (RP2040 alternate)
 * SPDX-License-Identifier: MIT
 *
 * Minimal core boilerplate. Encoder rotate = up/down, click = Enter.
 */

#include "quantum.h"

#ifdef ENCODER_ENABLE
bool encoder_update_kb(uint8_t index, bool clockwise) {
    if (!encoder_update_user(index, clockwise)) {
        return false;
    }
    tap_code(clockwise ? KC_DOWN : KC_UP);
    return true;
}
#endif
