/*
 * Copyright (c) 2026 Claude Code Pad project
 * SPDX-License-Identifier: MIT
 *
 * Claude Code Pad pairing-window behavior (closes RED-SAFETY SF-M12).
 *
 * BLE security posture (set in claude_code_pad.conf):
 *   CONFIG_BT_BONDABLE=n   -> device rejects new bonds by default
 *   CONFIG_BT_SMP_SC_PAIR_ONLY=y, CONFIG_BT_SMP_ENFORCE_MITM=y
 *
 * ccp_pair is the explicit, time-bounded window during which a host
 * can establish a bond:
 *
 *   on press:
 *     bt_set_bondable(true);
 *     schedule a k_work_delayable to fire after CCP_PAIR_WINDOW_MS;
 *     start the blink work that flashes the strip (or LED 25 once
 *     ZMK exposes a per-LED override) at 1 Hz for the window duration;
 *
 *   on window expiry:
 *     bt_set_bondable(false);
 *     stop the blink work, restore strip to its pre-window state.
 *
 * Re-pressing the chord while the window is open RESETS the timer
 * to a fresh 60 s rather than toggling: the safety contract is that
 * the device must NOT remain bondable indefinitely on accident, and
 * tap-tap must NOT silently cancel a real pairing flow either. If
 * graceful_shutdown latches at any point during the window, the
 * window is force-closed (bondable=false) and the blink is stopped.
 *
 * The keymap binding (boards/shields/claude_code_pad/claude_code_pad.keymap)
 * exposes this as a 3-second hold-tap on the BT layer, position (0,0):
 *
 *     row 0 col 0 = bt0_pair { tap=&bt BT_SEL 0; hold-3s=&ccp_pair }
 *
 * Reaching this binding therefore requires:
 *   1. holding the BT layer access key, AND
 *   2. holding row-0-col-0 for 3 s.
 *
 * That two-step gate is the user-facing equivalent of "Fn+BT0 hold 3 s"
 * called out in firmware/zmk/README.md §BLE security.
 */

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/atomic.h>

#if defined(CONFIG_BT)
#include <zephyr/bluetooth/conn.h>
#endif

#if defined(CONFIG_ZMK_RGB_UNDERGLOW) && __has_include(<zmk/rgb_underglow.h>)
#include <zmk/rgb_underglow.h>
#elif defined(CONFIG_ZMK_RGB_UNDERGLOW)
int zmk_rgb_underglow_on(void);
int zmk_rgb_underglow_off(void);
#endif

#include "ccp_safety.h"

LOG_MODULE_REGISTER(ccp_pair, CONFIG_LOG_DEFAULT_LEVEL);

#define CCP_PAIR_WINDOW_MS    60000
#define CCP_PAIR_BLINK_MS     500     /* 1 Hz on/off */

/* ---- Pure-logic state machine (testable on native_sim) ---------------- */

static struct k_work_delayable pair_window_work;
static struct k_work_delayable pair_blink_work;
static atomic_t pair_open;     /* 1 while the bondable window is open */
static atomic_t blink_state;   /* 0 / 1, toggled each blink tick */
static bool pair_workq_inited;

static void pair_blink_handler(struct k_work *work)
{
	ARG_UNUSED(work);

	if (!atomic_get(&pair_open) || ccp_safety_is_latched()) {
		return;
	}

	atomic_xor(&blink_state, 1);

	/*
	 * SF-M11 today: ZMK's public underglow API has no per-LED override,
	 * so the visible feedback is a strip-wide on/off toggle. When the
	 * upstream zmk_rgb_underglow_select() lands we swap this for a 1 Hz
	 * blue blink on LED 25 only. The behaviour observable by the
	 * builder is "the strip flickers visibly while the pairing window
	 * is open", which is sufficient indication that BLE is bondable.
	 */
#if defined(CONFIG_ZMK_RGB_UNDERGLOW)
	if (atomic_get(&blink_state)) {
		(void)zmk_rgb_underglow_on();
	} else {
		(void)zmk_rgb_underglow_off();
	}
#endif

	k_work_schedule(&pair_blink_work, K_MSEC(CCP_PAIR_BLINK_MS));
}

static void pair_window_close(void)
{
	if (!atomic_cas(&pair_open, 1, 0)) {
		return;
	}

#if defined(CONFIG_BT)
	bt_set_bondable(false);
#endif
	if (pair_workq_inited) {
		(void)k_work_cancel_delayable(&pair_blink_work);
	}

	/*
	 * Restore the strip to its on-state when the window ends so that
	 * a builder who pressed the chord but did not pair is not left
	 * with a dark pad. The cap registry's normal effective-cap path
	 * resumes control on the next guard sample (<= 250 ms).
	 */
#if defined(CONFIG_ZMK_RGB_UNDERGLOW)
	(void)zmk_rgb_underglow_on();
#endif

	LOG_WRN("ccp_pair: pairing window closed -- bondable=false");
}

static void pair_window_handler(struct k_work *work)
{
	ARG_UNUSED(work);
	pair_window_close();
}

static void pair_window_init_once(void)
{
	if (pair_workq_inited) {
		return;
	}
	k_work_init_delayable(&pair_window_work, pair_window_handler);
	k_work_init_delayable(&pair_blink_work, pair_blink_handler);
	pair_workq_inited = true;
}

static void pair_window_open(void)
{
	if (ccp_safety_is_latched()) {
		LOG_WRN("ccp_pair: ignored -- graceful shutdown latched");
		return;
	}
	pair_window_init_once();

	bool was_open = (atomic_set(&pair_open, 1) != 0);

#if defined(CONFIG_BT)
	bt_set_bondable(true);
#endif

	/*
	 * Re-arm the close timer. Repeated presses RESET the 60-second
	 * timer instead of toggling -- see file header for rationale.
	 */
	(void)k_work_reschedule(&pair_window_work, K_MSEC(CCP_PAIR_WINDOW_MS));

	if (!was_open) {
		atomic_set(&blink_state, 0);
		(void)k_work_reschedule(&pair_blink_work, K_MSEC(CCP_PAIR_BLINK_MS));
		LOG_WRN("ccp_pair: pairing window OPEN (%d ms) -- bondable=true",
			CCP_PAIR_WINDOW_MS);
	} else {
		LOG_INF("ccp_pair: pairing window timer reset");
	}
}

#if defined(CONFIG_ZTEST)
/*
 * Test-only access for the native_sim ztest suite. Exposed via local
 * extern decls in tests/ccp_safety/src/test_pair_window.c rather than
 * in ccp_safety.h so the production header stays clean.
 */
void ccp_pair_test_open(void)         { pair_window_open(); }
void ccp_pair_test_close(void)        { pair_window_close(); }
bool ccp_pair_test_is_open(void)      { return atomic_get(&pair_open) != 0; }
#endif

/* ---- Behavior-driver glue (only present on real targets) -------------- */

#if !defined(CONFIG_ZTEST)

#define DT_DRV_COMPAT claude_code_pad_behavior_ccp_pair

#include <zephyr/device.h>
#include <drivers/behavior.h>

#if DT_HAS_COMPAT_STATUS_OKAY(DT_DRV_COMPAT)

static int on_keymap_binding_pressed(struct zmk_behavior_binding *binding,
				     struct zmk_behavior_binding_event event)
{
	ARG_UNUSED(binding);
	ARG_UNUSED(event);
	pair_window_open();
	return 0;
}

static int on_keymap_binding_released(struct zmk_behavior_binding *binding,
				      struct zmk_behavior_binding_event event)
{
	ARG_UNUSED(binding);
	ARG_UNUSED(event);
	return 0;
}

static const struct behavior_driver_api behavior_ccp_pair_driver_api = {
	.binding_pressed = on_keymap_binding_pressed,
	.binding_released = on_keymap_binding_released,
};

static int ccp_pair_init(const struct device *dev)
{
	ARG_UNUSED(dev);
	pair_window_init_once();
	return 0;
}

BEHAVIOR_DT_INST_DEFINE(0, ccp_pair_init, NULL, NULL, NULL, POST_KERNEL,
			CONFIG_KERNEL_INIT_PRIORITY_DEFAULT,
			&behavior_ccp_pair_driver_api);

#endif /* DT_HAS_COMPAT_STATUS_OKAY(DT_DRV_COMPAT) */

#endif /* !CONFIG_ZTEST */
