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
 *
 * Phase 3 Cycle 2:
 *   - Fail-dark default: both caps initialise to 0, the guards each
 *     raise their own slot only after first valid sample (SF-B2).
 *   - Per-source TTL: if a slot is not refreshed within
 *     2 * sample_interval_ms, the effective-cap read treats it as 0.
 *   - Latch-aware: after graceful_shutdown, set_cap is a no-op.
 *   - Watchdog aggregator: a 250 ms k_work checks both guards' pet
 *     flags; if both are set, kicks the nRF52840 hardware WDT.
 */

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/drivers/watchdog.h>
#include <zephyr/device.h>
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/conn.h>
#include <zephyr/bluetooth/services/bas.h>
#include "ccp_safety.h"

#if defined(CONFIG_ZMK_RGB_UNDERGLOW)
/* The ZMK underglow public header lives under
 *   <zmk/app/include>/zmk/rgb_underglow.h
 * which is already on the Zephyr module search path for the app but
 * NOT for third-party modules like ccp_safety. Include via the
 * relative path that Zephyr's module CMake gives us (zmk_app_module
 * is on the include list as -I .../zmk/app/module/include, and
 * rgb_underglow.h is exposed there via a thin wrapper). If the app-
 * include flag isn't on our command line, fall back to a forward
 * declaration of the two symbols we actually use.
 */
#if __has_include(<zmk/rgb_underglow.h>)
#include <zmk/rgb_underglow.h>
#else
int zmk_rgb_underglow_on(void);
int zmk_rgb_underglow_off(void);
#endif
#endif

LOG_MODULE_REGISTER(ccp_safety, CONFIG_LOG_DEFAULT_LEVEL);

/* ---------------- cap registry --------------------------------------- */

struct cap_slot {
	uint8_t cap;
	uint32_t ttl_ms;
	int64_t last_set_mono_ms;
};

static K_MUTEX_DEFINE(cap_mutex);
static struct cap_slot caps[CCP_CAP_NSOURCES];  /* zero-init -> fail-dark */
static bool graceful_shutdown_latched;

static uint8_t min_cap_locked(void)
{
	int64_t now = k_uptime_get();
	uint8_t m = 100;

	for (int i = 0; i < CCP_CAP_NSOURCES; i++) {
		uint8_t eff = caps[i].cap;

		if (caps[i].ttl_ms) {
			int64_t age = now - caps[i].last_set_mono_ms;

			if (age > (int64_t)caps[i].ttl_ms) {
				/* Slot has gone stale -- treat as 0 (fail-dark). */
				eff = 0;
			}
		}
		if (eff < m) {
			m = eff;
		}
	}
	return m;
}

void ccp_safety_set_cap(enum ccp_cap_source src, uint8_t cap,
			uint32_t sample_interval_ms)
{
	if (src >= CCP_CAP_NSOURCES) {
		return;
	}
	if (cap > 100) {
		cap = 100;
	}

	k_mutex_lock(&cap_mutex, K_FOREVER);
	if (graceful_shutdown_latched) {
		/* SF-M2: do not let a stray late sample clobber cap=0. */
		k_mutex_unlock(&cap_mutex);
		return;
	}
	caps[src].cap = cap;
	/* TTL = 2 * sample_interval_ms (stale-detection threshold). */
	caps[src].ttl_ms = sample_interval_ms ? (sample_interval_ms * 2U) : 0U;
	caps[src].last_set_mono_ms = k_uptime_get();
	uint8_t eff = min_cap_locked();

	k_mutex_unlock(&cap_mutex);

#if defined(CONFIG_ZMK_RGB_UNDERGLOW)
	/*
	 * ZMK's public underglow API does not expose an absolute-brightness
	 * setter (only relative change_brt / on / off). For the cap = 0
	 * case we must turn the strip off for the safety contract to hold;
	 * for cap > 0 we rely on the Kconfig BRT_MAX hard cap plus the
	 * user's runtime brightness, which is already <= BRT_MAX. This is
	 * a cap-as-ceiling, not cap-as-target, semantics -- sufficient for
	 * Annex Q compliance but coarser than the original design envisioned.
	 * Documented in docs/safety-verification.md §cap-semantics.
	 */
	static bool strip_off;

	if (eff == 0 && !strip_off) {
		(void)zmk_rgb_underglow_off();
		strip_off = true;
	} else if (eff > 0 && strip_off) {
		(void)zmk_rgb_underglow_on();
		strip_off = false;
	}
#endif

	LOG_DBG("cap[src=%d]=%u ttl=%ums eff=%u",
		(int)src, cap, sample_interval_ms * 2U, eff);
}

uint8_t ccp_safety_effective_cap(void)
{
	k_mutex_lock(&cap_mutex, K_FOREVER);
	uint8_t m = min_cap_locked();

	k_mutex_unlock(&cap_mutex);
	return m;
}

bool ccp_safety_is_latched(void)
{
	bool l;

	k_mutex_lock(&cap_mutex, K_FOREVER);
	l = graceful_shutdown_latched;
	k_mutex_unlock(&cap_mutex);
	return l;
}

/* ---------------- graceful shutdown ---------------------------------- */

static void disconnect_cb(struct bt_conn *conn, void *data)
{
	ARG_UNUSED(data);
	(void)bt_conn_disconnect(conn, BT_HCI_ERR_REMOTE_POWER_OFF);
}

void ccp_safety_graceful_shutdown(const char *reason)
{
	bool was_latched;

	k_mutex_lock(&cap_mutex, K_FOREVER);
	was_latched = graceful_shutdown_latched;
	graceful_shutdown_latched = true;
	for (int i = 0; i < CCP_CAP_NSOURCES; i++) {
		caps[i].cap = 0;
		caps[i].ttl_ms = 0;
	}
	k_mutex_unlock(&cap_mutex);

	if (was_latched) {
		return;
	}

	LOG_WRN("graceful shutdown: %s", reason);

#if defined(CONFIG_ZMK_RGB_UNDERGLOW)
	(void)zmk_rgb_underglow_off();
#endif

#if defined(CONFIG_BT)
	/* SF-M13 + SF-M8 + FW M#20: drop BLE radio activity + BAS flag. */
	(void)bt_bas_set_battery_level(0);
	bt_conn_foreach(BT_CONN_TYPE_LE, disconnect_cb, NULL);
	(void)bt_le_adv_stop();
#endif
}

/* ---------------- watchdog aggregator -------------------------------- */

#if defined(CONFIG_WATCHDOG)

/*
 * The nRF52840 watchdog is single-channel in most SoC configs; we
 * emulate a "both guards must pet" policy by requiring both the battery
 * and thermal guards to flip their pet bit within the WDT window. A
 * 250 ms k_work checks the flags, clears them, and feeds the WDT only
 * if BOTH were set. WDT timeout is 2 s (see CONFIG_CCP_WDT_TIMEOUT_MS),
 * giving each guard up to 8 pet intervals to catch up before reset.
 */
#define WDT_CHECK_INTERVAL_MS 250
#define WDT_TIMEOUT_MS        2000

static struct k_work_delayable wdt_work;
static const struct device *wdt_dev;
static int wdt_channel_id = -1;
static bool pet_flags[CCP_WDT_NSOURCES];
static struct k_spinlock pet_lock;

void ccp_safety_wdt_feed(enum ccp_wdt_source src)
{
	if (src >= CCP_WDT_NSOURCES) {
		return;
	}
	k_spinlock_key_t key = k_spin_lock(&pet_lock);

	pet_flags[src] = true;
	k_spin_unlock(&pet_lock, key);
}

static void wdt_aggregator(struct k_work *work)
{
	ARG_UNUSED(work);

	k_spinlock_key_t key = k_spin_lock(&pet_lock);
	bool all = true;

	for (int i = 0; i < CCP_WDT_NSOURCES; i++) {
		if (!pet_flags[i]) {
			all = false;
			break;
		}
	}
	if (all) {
		for (int i = 0; i < CCP_WDT_NSOURCES; i++) {
			pet_flags[i] = false;
		}
	}
	k_spin_unlock(&pet_lock, key);

	if (all && wdt_channel_id >= 0 && wdt_dev) {
		(void)wdt_feed(wdt_dev, wdt_channel_id);
	}
	/* Re-schedule unconditionally; if we never pet, WDT triggers reset. */
	k_work_schedule(&wdt_work, K_MSEC(WDT_CHECK_INTERVAL_MS));
}

static int ccp_wdt_init(void)
{
	wdt_dev = DEVICE_DT_GET_OR_NULL(DT_NODELABEL(wdt0));
	if (!wdt_dev || !device_is_ready(wdt_dev)) {
		LOG_ERR("wdt0 not ready -- ccp safety WDT disabled");
		return -ENODEV;
	}

	struct wdt_timeout_cfg cfg = {
		.window.min = 0U,
		.window.max = WDT_TIMEOUT_MS,
		.callback = NULL,
		.flags = WDT_FLAG_RESET_SOC,
	};

	wdt_channel_id = wdt_install_timeout(wdt_dev, &cfg);
	if (wdt_channel_id < 0) {
		LOG_ERR("wdt_install_timeout: %d", wdt_channel_id);
		return wdt_channel_id;
	}

	int err = wdt_setup(wdt_dev, WDT_OPT_PAUSE_HALTED_BY_DBG);

	if (err) {
		LOG_ERR("wdt_setup: %d", err);
		return err;
	}

	k_work_init_delayable(&wdt_work, wdt_aggregator);
	k_work_schedule(&wdt_work, K_MSEC(WDT_CHECK_INTERVAL_MS));
	LOG_INF("ccp safety WDT armed, timeout=%d ms", WDT_TIMEOUT_MS);
	return 0;
}

SYS_INIT(ccp_wdt_init, APPLICATION, 99);

#else /* !CONFIG_WATCHDOG */

void ccp_safety_wdt_feed(enum ccp_wdt_source src)
{
	ARG_UNUSED(src);
}

#endif
