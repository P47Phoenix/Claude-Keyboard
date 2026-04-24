/*
 * Copyright (c) 2026 Claude Code Pad project
 * SPDX-License-Identifier: MIT
 *
 * Battery guard for the Claude Code Pad (Phase 3 Cycle 2).
 *
 * Semantics (RED-SAFETY C1 -> C2):
 *   1. Linear LED derate 4.00 V -> 3.80 V (100 % -> 0 %)
 *      ("leds_cut" latches once the derate curve hits 0 at 3.80 V;
 *      LEDs remain off until cell_mv >= 3.80 + 100 mV hysteresis.)
 *   2. Graceful shutdown (hard latch) at cell_mv <= 3.50 V, OR at
 *      broken-wire detection, OR at a physical out-of-range band
 *      [< 2800 mV OR > 4400 mV] (SF-M7: catches open-divider-resistor).
 *   3. Broken-wire detection requires TWO consecutive 8-sample windows
 *      to trigger (SF-M5), so transient cell-sag under a full-current
 *      LED burst does not falsely latch.
 *   4. SAADC sample cadence is 250 ms (SF-B3) + burst/oversample set
 *      in DT. A stale slot decays to 0 within 500 ms.
 *   5. Every successful sample pets the WDT_BATTERY flag (SF-B1). If
 *      this guard hangs the MCU resets within ~2 s.
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/init.h>
#include <zephyr/drivers/adc.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/util.h>
#include <string.h>

#include "ccp_safety.h"

LOG_MODULE_REGISTER(ccp_battery_guard, CONFIG_LOG_DEFAULT_LEVEL);

#define VBAT_SAMPLE_MS  CONFIG_CCP_BATTERY_GUARD_SAMPLE_INTERVAL_MS

/* Thresholds in millivolts at the cell (NOT at the ADC). */
#define CUTOFF_LEDS_ON_MV   3800
#define CUTOFF_LEDS_OFF_MV  3500
#define DERATE_TOP_MV       4000
#define DERATE_BOT_MV       3800
#define HYSTERESIS_MV       100

/* SF-M7 physical-range sanity band. A cell that reads < 2.8 V is dead
 * and should never have been plugged in; > 4.4 V is unphysical and
 * indicates the 1:2 divider has one open resistor so the ADC sees
 * raw cell voltage -- either way, graceful shutdown is the correct
 * response.
 */
#define VBAT_PHYS_MIN_MV    2800
#define VBAT_PHYS_MAX_MV    4400

/* Broken-wire detection window (SF-M5: require two consecutive windows
 * before latching). */
#define VBAT_WINDOW         8
#define VARIANCE_LIMIT_MV   100
#define STEP_LIMIT_MV       300

static const struct adc_dt_spec vbat_spec =
	ADC_DT_SPEC_GET_BY_IDX(DT_NODELABEL(ccp_safety), 0);

/* FW-M3: BUILD_ASSERT the DT node is our compat, not a generic
 * voltage-divider compat (would do its own scaling). */
BUILD_ASSERT(DT_NODE_HAS_COMPAT(DT_NODELABEL(ccp_safety),
				claude_code_pad_ccp_safety),
	     "ccp_safety DT node must carry the claude-code-pad,ccp-safety "
	     "compatible (so vbat_spec gain/ref are the raw SAADC values).");

static struct k_work_delayable vbat_work;
static int16_t window[VBAT_WINDOW];
static uint8_t window_len;
static uint8_t consecutive_bad_windows;
static bool leds_cut;

static int sample_vbat_mv(int *cell_mv_out)
{
	int16_t sample = 0;
	struct adc_sequence seq = {
		.buffer = &sample,
		.buffer_size = sizeof(sample),
	};

	int err = adc_sequence_init_dt(&vbat_spec, &seq);

	if (err) {
		return err;
	}

	err = adc_read(vbat_spec.dev, &seq);
	if (err) {
		return err;
	}

	int32_t val_mv = sample;

	/* FW-M3: de-divide AFTER adc_raw_to_millivolts_dt has had a chance
	 * to reject an invalid raw sample. */
	err = adc_raw_to_millivolts_dt(&vbat_spec, &val_mv);
	if (err) {
		return err;
	}

	*cell_mv_out = val_mv * 2;
	return 0;
}

/* Returns true if the latest window fails variance/step sanity. */
static bool window_suspect(int latest_mv)
{
	if (window_len < VBAT_WINDOW) {
		window[window_len++] = latest_mv;
		return false;
	}
	memmove(window, window + 1, sizeof(window[0]) * (VBAT_WINDOW - 1));
	window[VBAT_WINDOW - 1] = latest_mv;

	int32_t sum = 0;

	for (int i = 0; i < VBAT_WINDOW; i++) {
		sum += window[i];
	}
	int32_t mean = sum / VBAT_WINDOW;

	int32_t max_abs_resid = 0;

	for (int i = 0; i < VBAT_WINDOW; i++) {
		int32_t d = window[i] - mean;

		if (d < 0) {
			d = -d;
		}
		if (d > max_abs_resid) {
			max_abs_resid = d;
		}
	}
	if (max_abs_resid > VARIANCE_LIMIT_MV) {
		LOG_WRN("VBAT max-abs-residual %d mV > limit %d mV",
			max_abs_resid, VARIANCE_LIMIT_MV);
		return true;
	}

	for (int i = 1; i < VBAT_WINDOW; i++) {
		int32_t step = window[i] - window[i - 1];

		if (step < 0) {
			step = -step;
		}
		if (step > STEP_LIMIT_MV) {
			LOG_WRN("VBAT step %d mV > limit %d mV",
				step, STEP_LIMIT_MV);
			return true;
		}
	}
	return false;
}

static void vbat_work_handler(struct k_work *work)
{
	ARG_UNUSED(work);

	if (ccp_safety_is_latched()) {
		/* Nothing to do -- just reschedule to keep the WDT happy
		 * until the aggregator decides to reset.
		 */
		return;
	}

	int cell_mv = 0;
	int err = sample_vbat_mv(&cell_mv);

	if (err) {
		LOG_ERR("VBAT SAADC read failed: %d", err);
		goto reschedule;
	}

	/* SF-M7: physical-range sanity check. Fires graceful_shutdown
	 * independent of the broken-wire window. */
	if (cell_mv < VBAT_PHYS_MIN_MV || cell_mv > VBAT_PHYS_MAX_MV) {
		LOG_WRN("VBAT %d mV outside physical band [%d, %d]",
			cell_mv, VBAT_PHYS_MIN_MV, VBAT_PHYS_MAX_MV);
		ccp_safety_graceful_shutdown("VBAT out of physical range");
		return;
	}

	if (window_suspect(cell_mv)) {
		consecutive_bad_windows++;
		if (consecutive_bad_windows >= 2) {
			ccp_safety_graceful_shutdown("VBAT_ADC broken wire");
			return;
		}
	} else {
		consecutive_bad_windows = 0;
	}

	/* SF-M6: two-tier cutoff. Only the 3.50 V trip is a graceful
	 * shutdown; 3.80 V just latches leds_cut (via the derate curve). */
	if (cell_mv <= CUTOFF_LEDS_OFF_MV) {
		ccp_safety_graceful_shutdown("VBAT <= 3.50 V");
		return;
	}

	/* Compute linear derate 4.00 V -> 3.80 V -> 0 .. 100 cap. */
	uint8_t cap_0_100;

	if (cell_mv >= DERATE_TOP_MV) {
		cap_0_100 = 100;
	} else if (cell_mv <= DERATE_BOT_MV) {
		cap_0_100 = 0;
	} else {
		int span = DERATE_TOP_MV - DERATE_BOT_MV;     /* 200 */
		int above = cell_mv - DERATE_BOT_MV;

		cap_0_100 = (uint8_t)((above * 100) / span);
	}

	/* Hysteresis: latch leds_cut ON when cap hits 0; release only when
	 * cell_mv >= DERATE_BOT_MV + HYSTERESIS_MV = 3.90 V. */
	if (cap_0_100 == 0) {
		leds_cut = true;
	} else if (leds_cut && cell_mv >= (DERATE_BOT_MV + HYSTERESIS_MV)) {
		leds_cut = false;
	}

	if (leds_cut) {
		cap_0_100 = 0;
	}

	ccp_safety_set_cap(CCP_CAP_BATTERY, cap_0_100, VBAT_SAMPLE_MS);
	ccp_safety_wdt_feed(CCP_WDT_BATTERY);

	LOG_DBG("VBAT=%d mV cap=%u leds_cut=%d", cell_mv, cap_0_100, leds_cut);

reschedule:
	k_work_schedule(&vbat_work, K_MSEC(VBAT_SAMPLE_MS));
}

static int ccp_battery_guard_init(void)
{
	if (!adc_is_ready_dt(&vbat_spec)) {
		LOG_ERR("VBAT SAADC not ready");
		return -ENODEV;
	}

	int err = adc_channel_setup_dt(&vbat_spec);

	if (err) {
		LOG_ERR("VBAT adc_channel_setup_dt: %d", err);
		return err;
	}

	k_work_init_delayable(&vbat_work, vbat_work_handler);

	/* First sample at 250 ms lets the cell settle after Q_REV turns on. */
	k_work_schedule(&vbat_work, K_MSEC(250));

	return 0;
}

SYS_INIT(ccp_battery_guard_init, APPLICATION, CONFIG_CCP_BATTERY_GUARD_INIT_PRIORITY);
