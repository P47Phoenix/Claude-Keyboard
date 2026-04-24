/*
 * Copyright (c) 2026 Claude Code Pad project
 * SPDX-License-Identifier: MIT
 *
 * Battery guard for the Claude Code Pad.
 *
 * Implements all three battery-safety requirements from
 * firmware/zmk/README.md:
 *
 *   1. Undervolt cutoff
 *        LEDs-on  : cut at V_VBAT <= 3.70 V
 *        LEDs-off : cut at V_VBAT <= 3.50 V
 *   2. Linear LED derate 3.90 V -> 3.70 V (100 % -> 0 %)
 *   3. Broken-wire detection
 *        8 consecutive samples, variance > 100 mV OR step > 0.3 V
 *        -> same path as 3.50 V cutoff. Cannot be disabled at runtime.
 *   4. Hysteresis
 *        Re-enable LEDs only when V_VBAT >= (cutoff + 100 mV).
 *
 * SAADC configuration is declared in the overlay (OVERSAMPLE=3 -> 8
 * samples, BURST mode via oversampling directive, internal 0.6 V ref
 * @ gain 1/6). Divider is 2x 1 MOhm so ADC reads V_VBAT / 2.
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/init.h>
#include <zephyr/drivers/adc.h>
#include <zephyr/logging/log.h>
#include <string.h>

#include "ccp_safety.h"

LOG_MODULE_REGISTER(ccp_battery_guard, CONFIG_LOG_DEFAULT_LEVEL);

#define VBAT_SAMPLE_MS  CONFIG_CCP_BATTERY_GUARD_SAMPLE_INTERVAL_MS

/* Thresholds in millivolts at the cell (NOT at the ADC). */
#define CUTOFF_LEDS_ON_MV   3700
#define CUTOFF_LEDS_OFF_MV  3500
#define DERATE_TOP_MV       3900
#define DERATE_BOT_MV       3700
#define HYSTERESIS_MV       100

/* Broken-wire detection window. */
#define VBAT_WINDOW         8
#define VARIANCE_LIMIT_MV   100
#define STEP_LIMIT_MV       300

static const struct adc_dt_spec vbat_spec =
	ADC_DT_SPEC_GET_BY_IDX(DT_NODELABEL(ccp_safety), 0);

static struct k_work_delayable vbat_work;
static int16_t window[VBAT_WINDOW];
static uint8_t window_len;
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

	/*
	 * 12-bit single-ended, ref = 0.6 V, gain = 1/6 -> full-scale
	 * input = 3.6 V. Convert to mV at the ADC pin:
	 *    vadc_mv = sample * 3600 / 4096
	 * Then de-divide (x2) to cell voltage:
	 *    vcell_mv = vadc_mv * 2
	 */
	int32_t val_mv = sample;

	err = adc_raw_to_millivolts_dt(&vbat_spec, &val_mv);
	if (err) {
		return err;
	}

	*cell_mv_out = val_mv * 2;
	return 0;
}

static bool window_broken_wire(int latest_mv)
{
	/* Keep a circular 8-sample window of cell millivolt readings. */
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

	int32_t variance_mv = 0;

	for (int i = 0; i < VBAT_WINDOW; i++) {
		int32_t d = window[i] - mean;

		if (d < 0) {
			d = -d;
		}
		if (d > variance_mv) {
			variance_mv = d;
		}
	}
	if (variance_mv > VARIANCE_LIMIT_MV) {
		LOG_WRN("VBAT variance %d mV > limit %d mV -- broken wire",
			variance_mv, VARIANCE_LIMIT_MV);
		return true;
	}

	for (int i = 1; i < VBAT_WINDOW; i++) {
		int32_t step = window[i] - window[i - 1];

		if (step < 0) {
			step = -step;
		}
		if (step > STEP_LIMIT_MV) {
			LOG_WRN("VBAT step %d mV > limit %d mV -- broken wire",
				step, STEP_LIMIT_MV);
			return true;
		}
	}
	return false;
}

static void vbat_work_handler(struct k_work *work)
{
	ARG_UNUSED(work);

	int cell_mv = 0;
	int err = sample_vbat_mv(&cell_mv);

	if (err) {
		LOG_ERR("VBAT SAADC read failed: %d", err);
		goto reschedule;
	}

	if (window_broken_wire(cell_mv)) {
		ccp_safety_graceful_shutdown("VBAT_ADC broken wire");
		return;   /* latched -- do not reschedule */
	}

	int cutoff_mv = leds_cut ? CUTOFF_LEDS_OFF_MV : CUTOFF_LEDS_ON_MV;

	if (cell_mv <= cutoff_mv) {
		ccp_safety_graceful_shutdown("VBAT undervolt");
		return;
	}

	/* Compute linear derate 3.90 V -> 3.70 V -> 0 .. 100 cap. */
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

	/* Hysteresis: latch leds_cut ON the moment cap hits 0; release
	 * only when cell_mv >= DERATE_BOT_MV + HYSTERESIS_MV.
	 */
	if (cap_0_100 == 0) {
		leds_cut = true;
	} else if (leds_cut && cell_mv >= (DERATE_BOT_MV + HYSTERESIS_MV)) {
		leds_cut = false;
	}

	if (leds_cut) {
		cap_0_100 = 0;
	}

	ccp_safety_set_cap(CCP_CAP_BATTERY, cap_0_100);

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

	/* First sample at 1 s lets the cell settle after Q_REV turns on. */
	k_work_schedule(&vbat_work, K_MSEC(1000));

	return 0;
}

SYS_INIT(ccp_battery_guard_init, APPLICATION, CONFIG_CCP_BATTERY_GUARD_INIT_PRIORITY);
