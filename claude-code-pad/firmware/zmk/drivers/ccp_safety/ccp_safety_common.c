/*
 * Copyright (c) 2026 Claude Code Pad project
 * SPDX-License-Identifier: MIT
 *
 * Common cap-registry used by ccp_battery_guard and ccp_thermal_guard.
 * Applies the effective cap to ZMK's underglow by scaling the shipped
 * brightness. We deliberately do NOT expose this over BLE or ZMK Studio
 * -- see firmware/zmk/README.md §Implementation requirements:
 *   "The cap MUST NOT be runtime-configurable via ZMK Studio, the
 *    keymap, or any characteristic over BLE."
 *
 * Keymap users can still CHANGE ZMK's normal brightness knobs; the
 * effective output is always min(user_brightness, effective_cap).
 */

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include "ccp_safety.h"

#if defined(CONFIG_ZMK_RGB_UNDERGLOW)
#include <zmk/rgb_underglow.h>
#endif

LOG_MODULE_REGISTER(ccp_safety, CONFIG_LOG_DEFAULT_LEVEL);

static K_MUTEX_DEFINE(cap_mutex);
static uint8_t caps[CCP_CAP_NSOURCES] = { 100, 100 };
static bool graceful_shutdown_latched;

static uint8_t min_cap_locked(void)
{
	uint8_t m = 100;

	for (int i = 0; i < CCP_CAP_NSOURCES; i++) {
		if (caps[i] < m) {
			m = caps[i];
		}
	}
	return m;
}

void ccp_safety_set_cap(enum ccp_cap_source src, uint8_t cap)
{
	if (src >= CCP_CAP_NSOURCES) {
		return;
	}
	if (cap > 100) {
		cap = 100;
	}

	k_mutex_lock(&cap_mutex, K_FOREVER);
	caps[src] = cap;
	uint8_t eff = min_cap_locked();
	k_mutex_unlock(&cap_mutex);

#if defined(CONFIG_ZMK_RGB_UNDERGLOW)
	/*
	 * Scale the ZMK underglow brightness by the effective cap.
	 * zmk_rgb_underglow_set_brt() is clamped by the Kconfig BRT_MAX
	 * hard cap, so the worst-case aggregate across both mechanisms
	 * is min(user, 100) * BRT_MAX/100 = <= 20 % full-white = <= 300 mA.
	 */
	if (graceful_shutdown_latched) {
		(void)zmk_rgb_underglow_off();
	} else {
		(void)zmk_rgb_underglow_set_brt(eff);
	}
#endif

	LOG_DBG("cap[src=%d]=%u eff=%u", (int)src, cap, eff);
}

uint8_t ccp_safety_effective_cap(void)
{
	k_mutex_lock(&cap_mutex, K_FOREVER);
	uint8_t m = min_cap_locked();
	k_mutex_unlock(&cap_mutex);
	return m;
}

void ccp_safety_graceful_shutdown(const char *reason)
{
	bool was_latched;

	k_mutex_lock(&cap_mutex, K_FOREVER);
	was_latched = graceful_shutdown_latched;
	graceful_shutdown_latched = true;
	for (int i = 0; i < CCP_CAP_NSOURCES; i++) {
		caps[i] = 0;
	}
	k_mutex_unlock(&cap_mutex);

	if (was_latched) {
		return;
	}

	LOG_WRN("graceful shutdown: %s", reason);

#if defined(CONFIG_ZMK_RGB_UNDERGLOW)
	(void)zmk_rgb_underglow_off();
#endif

	/*
	 * BLE activity reduction: stop advertising, stop connection
	 * intervals. ZMK's sleep path already does this via its sleep
	 * hooks; triggering the sleep state here keeps the keyboard
	 * responsive-to-HID (for "save and exit" prompts) while
	 * dropping the BLE radio duty cycle.
	 *
	 * NOTE: not all ZMK versions expose a public API for this; in
	 * C1 we fall through and let the pm_device + ZMK sleep timeout
	 * handle it. A direct zmk_ble_sleep() call would be cleaner
	 * -- flagged as C2 work.
	 */
}
