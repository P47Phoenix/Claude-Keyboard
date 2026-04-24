/*
 * Claude Code Pad QMK default keymap -- SKELETON.
 * SPDX-License-Identifier: MIT
 *
 * C1 scope: starter layout matching the ZMK default with the simple
 * single-key macros (Accept/Reject/Allow/etc.). String macros
 * (SubAgent, Commit Trunk/PR, Test, Build) are stubbed as SEND_STRING
 * calls and ARE NOT FEATURE-COMPLETE.
 */

#include QMK_KEYBOARD_H

enum ccp_keycodes {
    CCP_SUBAGENT = SAFE_RANGE,
    CCP_ESC2,
    CCP_COMMIT_TRUNK,
    CCP_COMMIT_PR,
    CCP_TEST,
    CCP_BUILD,
};

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    if (!record->event.pressed) {
        return true;
    }
    switch (keycode) {
        case CCP_SUBAGENT:
            SEND_STRING(SS_TAP(X_ESC) "use sub agents for this" SS_TAP(X_ENTER));
            return false;
        case CCP_ESC2:
            SEND_STRING(SS_TAP(X_ESC) SS_TAP(X_ESC));
            return false;
        case CCP_COMMIT_TRUNK:
            SEND_STRING("/commit" SS_TAP(X_ENTER));
            return false;
        case CCP_COMMIT_PR:
            SEND_STRING("/pr" SS_TAP(X_ENTER));
            return false;
        case CCP_TEST:
            SEND_STRING("run tests" SS_TAP(X_ENTER));
            return false;
        case CCP_BUILD:
            SEND_STRING("run build" SS_TAP(X_ENTER));
            return false;
    }
    return true;
}

/* y/n/a/A + Enter are tap-dances -- use ACTION_MACRO for simplicity. */
#define CCP_ACCEPT  MT(MOD_LSFT, KC_Y)   /* placeholder; C2 will use real macros */

const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    [0] = LAYOUT_ortho_5x5(
        S(KC_TAB), S(KC_TAB), S(KC_TAB), LALT(KC_P), LCTL(KC_G),
        CCP_SUBAGENT, LALT(KC_T), CCP_ESC2, KC_F13, KC_R,
        KC_Y, KC_N, KC_A, S(KC_A), KC_ESC,
        KC_LEFT, KC_UP, KC_DOWN, KC_RGHT, KC_F14,
        CCP_COMMIT_TRUNK, CCP_COMMIT_PR, CCP_TEST, CCP_BUILD, KC_ENT
    ),
};
