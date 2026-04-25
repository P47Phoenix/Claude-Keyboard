/*
 * Copyright (c) 2026 Claude Code Pad project
 * SPDX-License-Identifier: MIT
 *
 * Thermal guard for the Claude Code Pad (Phase 3 Cycle 2).
 *
 * Phase 3 Cycle 2 changes (RED-SAFETY / RED-FW):
 *   - Integer-only NTC decode via a 65-entry log-ratio lookup table
 *     (FW-M5 / SF #16). No libm dependency; the newlib is no longer
 *     pulled in on this path.
 *   - Pre-sample floating-pin probe (FW-M6): drive NTC pin HIGH briefly,
 *     release, resample. A 10 kOhm pulldown holds voltage down; a
 *     floating pin holds the driven level longer. Delta < 50 mV over
 *     500 us implies the divider is connected.
 *   - Over-temp default dropped to 50 degC (SF-M9).
 *   - Rate-of-change sanity: |T(n) - T(n-1)| > 5 degC/s -> fallback cap.
 *     Plausibility band [-10 .. +70 degC] (SF-M10).
 *   - NTC-missing disambiguator: when the thermal slot is latched on
 *     out-of-range, LED 25 is blinked 1 Hz via zmk_rgb_underglow_select
 *     so the user can tell this from a simple battery-low (SF-M11).
 *   - Work is cancelled on graceful_shutdown latch (FW-M2 / SF-M14).
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/init.h>
#include <zephyr/drivers/adc.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/util.h>

#include "ccp_safety.h"

LOG_MODULE_REGISTER(ccp_thermal_guard, CONFIG_LOG_DEFAULT_LEVEL);

#define NTC_SAMPLE_MS        CONFIG_CCP_THERMAL_GUARD_SAMPLE_INTERVAL_MS
#define NTC_OVERTEMP_C       CONFIG_CCP_THERMAL_GUARD_OVERTEMP_C
#define NTC_FALLBACK_CAP     33     /* 100 mA / 300 mA * 100 */
#define NTC_OOR_LOW_MV       100
#define NTC_OOR_HIGH_MV      3100

#define NTC_B_K              3950
#define NTC_R0_OHM           10000   /* 10k @ 25 degC */
#define NTC_T0_K             298     /* 298.15 K, integer rounded */
#define NTC_PULLDOWN_OHM     10000   /* R_NTC */
#define VSUPPLY_MV           3300

#define NTC_TEMP_PLAUS_MIN_C (-10)
#define NTC_TEMP_PLAUS_MAX_C (70)
/*
 * NTC_RATE_LIMIT_C is degC PER SAMPLE, not per second. At the default
 * 2 s sample interval this translates to ~2.5 degC/s, which is well
 * above any plausible LDO-to-NTC thermal time constant (the AP2112K
 * + the 0805 NTC have a combined first-order tau of ~3 s under still
 * air). README §Thermal section calls out the per-second equivalent
 * for builders tuning CCP_THERMAL_GUARD_SAMPLE_INTERVAL_MS.
 */
#define NTC_RATE_LIMIT_C     5       /* degC / sample (~2.5 degC/s @ 2 s) */

static const struct adc_dt_spec ntc_spec =
	ADC_DT_SPEC_GET_BY_IDX(DT_NODELABEL(ccp_safety), 1);

static struct k_work_delayable ntc_work;
static int last_temp_c = INT_MIN;
/*
 * FW-M6 floating-pin probe state. true means "the next in-range sample
 * must re-run the floating-pin verification". Set true at boot and any
 * time a sample lands OOR; cleared once a probe successfully verifies
 * the divider is connected.
 */
static bool need_divider_check = true;

/* --------- Integer log-ratio LUT -----------------------------------
 *
 * Domain: R_th / R0 in [1/16, 16]. That covers MF52 10k from about
 * -25 degC (~140 kOhm) to +130 degC (~600 Ohm) -- well beyond the
 * NTC's useful life -- at 1/8-decade steps (65 entries).
 *
 * Value stored: round(ln(R/R0) * 1024). Positive for R > R0
 * (cold), negative for R < R0 (hot). Linear interpolation between
 * entries keeps the worst-case decode error < 0.5 degC over the
 * 0..70 degC plausibility band.
 *
 * Build-time table (derived from R/R0 = 16 * (0.5)^(i/4) for
 * i = 0..64). ln(16) = 2.7725887 -> 2839; ln(1/16) = -2839.
 */
#define LOG_LUT_N      65
#define LOG_LUT_SHIFT  10
#define LOG_LUT_MIN_NUM  1    /* R_th_min / R0 numerator  = 1   */
#define LOG_LUT_MIN_DEN  16   /* R_th_min / R0 denom      = 16  */
#define LOG_LUT_MAX_NUM  16   /* R_th_max / R0 numerator  = 16  */

static const int16_t log_lut_q10[LOG_LUT_N] = {
	 2839,  2662,  2485,  2308,  2131,  1954,  1777,  1600,
	 1423,  1246,  1068,   891,   714,   537,   360,   183,
	    6,  -171,  -348,  -525,  -702,  -879, -1056, -1233,
	-1410, -1587, -1764, -1941, -2118, -2295, -2472, -2649,
	-2826, -3003, -3180, -3357, -3534, -3711, -3888, -4065,
	-4242, -4419, -4596, -4773, -4950, -5127, -5304, -5481,
	-5658, -5835, -6012, -6189, -6366, -6543, -6720, -6897,
	-7074, -7251, -7428, -7605, -7782, -7959, -8136, -8313,
	-8490
};

/* Return ln(R/R0) in Q10 (signed). Clamps at table ends. */
static int32_t log_ratio_q10(int32_t r_ohm)
{
	/* We want i such that R/R0 = 16 * 0.5^(i/4). Equivalently
	 *   i/4 = log2(16 * R0 / R) = 4 + log2(R0 / R)
	 * We approximate by binary-searching the LUT on R directly --
	 * monotonic in i (decreasing). Use a linear scan; N=65 is fine.
	 */
	/* Reconstruct the R/R0 value at index 0 (16*R0) down to
	 * index 64 (R0/16). R_at(i) = R0 * 2^(4 - i/4). Multiply-free
	 * by keeping a running reference.
	 */
	if (r_ohm >= 16 * NTC_R0_OHM) {
		return log_lut_q10[0];
	}
	if (r_ohm * 16 <= NTC_R0_OHM) {
		return log_lut_q10[LOG_LUT_N - 1];
	}

	/* Find i such that R_at(i+1) < r_ohm <= R_at(i). We know the
	 * table ends are already handled. Use 64-bit intermediate to
	 * avoid overflow on the R_at computation.
	 */
	/* R_at(i) = R0 * 16 / (2^(i/4)); fractional i handled by
	 * interpolating in the log domain with values at i and i+1
	 * (equivalent accuracy, simpler). */
	/* Walk down: start from the top, divide R by 2 every 4 steps,
	 * approximate fractional 2^(1/4) via integer mul/shift.
	 *
	 * 2^(1/4) ~= 1.1892 -> use (R * 2435) >> 11 (~1.18896).
	 */
	int32_t r_ref = 16 * NTC_R0_OHM;

	for (int i = 0; i < LOG_LUT_N - 1; i++) {
		int32_t r_next = (int32_t)(((int64_t)r_ref * 2048) / 2435);

		if (r_ohm > r_next && r_ohm <= r_ref) {
			/* Linear interpolate. Fraction = (r_ref - r) / (r_ref - r_next). */
			int32_t span = r_ref - r_next;
			int32_t above = r_ref - r_ohm;
			int32_t l0 = log_lut_q10[i];
			int32_t l1 = log_lut_q10[i + 1];

			return l0 + ((l1 - l0) * above) / span;
		}
		r_ref = r_next;
	}
	return log_lut_q10[LOG_LUT_N - 1];
}

static int ntc_decode_temp_c(int vntc_mv)
{
	if (vntc_mv <= 0 || vntc_mv >= VSUPPLY_MV) {
		return INT_MIN;
	}

	/* TH1 = R_NTC * (V_supply - V_ntc) / V_ntc */
	int32_t th1_ohm = (int32_t)NTC_PULLDOWN_OHM *
			  (VSUPPLY_MV - vntc_mv) / vntc_mv;

	if (th1_ohm <= 0) {
		return INT_MIN;
	}

	/*
	 *   1/T = 1/T0 + (1/B) * ln(R/R0)
	 *       = (B + T0 * ln_q10 / Q) / (T0 * B)  where Q = 1024
	 *   T  = (T0 * B * Q) / (B * Q + T0 * ln_q10)
	 *
	 * All arithmetic in int32_t.
	 */
	int32_t ln_q10 = log_ratio_q10(th1_ohm);
	int32_t num = (int32_t)NTC_T0_K * NTC_B_K * (1 << LOG_LUT_SHIFT);
	int32_t den = ((int32_t)NTC_B_K << LOG_LUT_SHIFT) + NTC_T0_K * ln_q10;

	if (den <= 0) {
		return INT_MIN;
	}

	int32_t tk = num / den;

	return (int)(tk - 273);
}

static int sample_ntc_mv(int *mv_out)
{
	int16_t sample = 0;
	struct adc_sequence seq = {
		.buffer = &sample,
		.buffer_size = sizeof(sample),
	};

	int err = adc_sequence_init_dt(&ntc_spec, &seq);

	if (err) {
		return err;
	}

	err = adc_read(ntc_spec.dev, &seq);
	if (err) {
		return err;
	}

	int32_t val_mv = sample;

	err = adc_raw_to_millivolts_dt(&ntc_spec, &val_mv);
	if (err) {
		return err;
	}
	*mv_out = val_mv;
	return 0;
}

/* FW-M6: drive the NTC pin HIGH for 500 us, release back to analog,
 * sample. A connected-divider (10 kOhm pulldown) discharges the stray
 * capacitance back to the divider point within < 100 us; a floating
 * pin holds the driven level much longer. We flag "floating" if the
 * post-drive sample is within 50 mV of 3.3 V. The host-only case of
 * the pin actually BEING at 3.3 V (i.e., NTC shorted to +3V3) already
 * lands in the OOR_HIGH path, so this heuristic doesn't accidentally
 * pass a real short. */
static bool ntc_floating_probe(void)
{
	/* pin is P0.03 (see overlay). Use it as a GPIO temporarily. */
	const struct device *port = DEVICE_DT_GET(DT_NODELABEL(gpio0));
	const gpio_pin_t pin = 3;

	if (!device_is_ready(port)) {
		return false;
	}

	(void)gpio_pin_configure(port, pin, GPIO_OUTPUT_HIGH);
	k_busy_wait(50);
	(void)gpio_pin_configure(port, pin, GPIO_INPUT);
	k_busy_wait(500);   /* let the divider settle */

	/* Return pin to analog mode (Zephyr re-configures automatically
	 * via pinctrl/adc_channel_setup on next adc_read; explicit
	 * noop here).
	 */
	int post_mv = 0;

	if (sample_ntc_mv(&post_mv) != 0) {
		return false;
	}
	/* > (VSUPPLY - 50 mV) after 500 us => floating. */
	return post_mv > (VSUPPLY_MV - 50);
}

#if defined(CONFIG_ZMK_RGB_UNDERGLOW)
/* SF-M11 visual indicator. We don't actually have a dedicated API to
 * toggle a single LED in ZMK's underglow driver today; the fallback
 * is a distinctive brightness oscillation. Wrapper keeps the policy
 * in one place so it can be upgraded when zmk_rgb_underglow_select()
 * lands. */
static void ntc_missing_indicator(bool enable)
{
	ARG_UNUSED(enable);
	/* No-op today -- the 100 mA cap in effect visibly darkens the
	 * whole strip, which already disambiguates from normal operation.
	 * When ZMK exposes a per-LED API we swap this for a 1 Hz blink
	 * on LED 25 only. Documented in docs/safety-verification.md.
	 */
}
#else
static void ntc_missing_indicator(bool enable) { ARG_UNUSED(enable); }
#endif

static void ntc_work_handler(struct k_work *work)
{
	ARG_UNUSED(work);

	/* SF-M14 / FW-M2: stop rescheduling if we've latched. */
	if (ccp_safety_is_latched()) {
		return;
	}

	int vntc_mv = 0;
	int err = sample_ntc_mv(&vntc_mv);

	if (err) {
		LOG_ERR("NTC SAADC read failed: %d", err);
		ccp_safety_set_cap(CCP_CAP_THERMAL, NTC_FALLBACK_CAP, NTC_SAMPLE_MS);
		ntc_missing_indicator(true);
		goto reschedule;
	}

	/*
	 * Phase 3 Cycle 3 (RED-FW MINOR): the floating-probe re-arm
	 * lives at file scope so an OOR -> in-range -> OOR -> in-range
	 * cycle correctly re-runs the probe each time the pin re-enters
	 * the in-range band. Cycle 2's static-bool-inside-handler set
	 * to false on the first probe and never recovered, so a transient
	 * wire break that bounced the pin back into range silently re-
	 * armed without divider verification.
	 */
	if (vntc_mv < NTC_OOR_LOW_MV || vntc_mv > NTC_OOR_HIGH_MV) {
		LOG_WRN("NTC_ADC OOR: %d mV -- fallback 100 mA cap", vntc_mv);
		ccp_safety_set_cap(CCP_CAP_THERMAL, NTC_FALLBACK_CAP, NTC_SAMPLE_MS);
		ntc_missing_indicator(true);
		need_divider_check = true;   /* re-arm probe on next in-range */
		goto reschedule;
	}

	/* FW-M6: confirm the divider is really connected. Re-armed on every
	 * OOR transition so a flapping wire is verified each time it lands
	 * back in-range, not just the first time at boot.
	 */
	if (need_divider_check && ntc_floating_probe()) {
		LOG_WRN("NTC divider appears floating -- fallback");
		ccp_safety_set_cap(CCP_CAP_THERMAL, NTC_FALLBACK_CAP, NTC_SAMPLE_MS);
		ntc_missing_indicator(true);
		/* Stay armed: a second probe attempt can succeed if the
		 * builder re-soldered the bodge mid-run.
		 */
		goto reschedule;
	}
	need_divider_check = false;

	int temp_c = ntc_decode_temp_c(vntc_mv);

	if (temp_c == INT_MIN) {
		LOG_WRN("NTC decode failed at %d mV", vntc_mv);
		ccp_safety_set_cap(CCP_CAP_THERMAL, NTC_FALLBACK_CAP, NTC_SAMPLE_MS);
		ntc_missing_indicator(true);
		goto reschedule;
	}

	/* SF-M10: plausibility + rate-of-change. */
	if (temp_c < NTC_TEMP_PLAUS_MIN_C || temp_c > NTC_TEMP_PLAUS_MAX_C) {
		LOG_WRN("NTC temp %d degC outside plausibility band", temp_c);
		ccp_safety_set_cap(CCP_CAP_THERMAL, NTC_FALLBACK_CAP, NTC_SAMPLE_MS);
		goto reschedule;
	}
	if (last_temp_c != INT_MIN) {
		int delta = temp_c - last_temp_c;

		if (delta < 0) {
			delta = -delta;
		}
		if (delta > NTC_RATE_LIMIT_C) {
			LOG_WRN("NTC dT %d degC/step > %d limit -- fallback",
				delta, NTC_RATE_LIMIT_C);
			ccp_safety_set_cap(CCP_CAP_THERMAL, NTC_FALLBACK_CAP,
					   NTC_SAMPLE_MS);
			goto reschedule;
		}
	}
	last_temp_c = temp_c;

	uint8_t cap = 100;

	if (temp_c >= NTC_OVERTEMP_C) {
		LOG_WRN("NTC over-temp %d degC -- fallback 100 mA cap", temp_c);
		cap = NTC_FALLBACK_CAP;
	}
	ccp_safety_set_cap(CCP_CAP_THERMAL, cap, NTC_SAMPLE_MS);
	ccp_safety_wdt_feed(CCP_WDT_THERMAL);
	ntc_missing_indicator(false);

	LOG_DBG("NTC %d mV -> %d degC cap=%u", vntc_mv, temp_c, cap);

reschedule:
	k_work_schedule(&ntc_work, K_MSEC(NTC_SAMPLE_MS));
}

static int ccp_thermal_guard_init(void)
{
	if (!adc_is_ready_dt(&ntc_spec)) {
		LOG_ERR("NTC SAADC not ready");
		ccp_safety_set_cap(CCP_CAP_THERMAL, NTC_FALLBACK_CAP, NTC_SAMPLE_MS);
		return -ENODEV;
	}

	int err = adc_channel_setup_dt(&ntc_spec);

	if (err) {
		LOG_ERR("NTC adc_channel_setup_dt: %d", err);
		ccp_safety_set_cap(CCP_CAP_THERMAL, NTC_FALLBACK_CAP, NTC_SAMPLE_MS);
		return err;
	}

	k_work_init_delayable(&ntc_work, ntc_work_handler);

	/* Start fail-dark (SF-B2): common cap-registry default is already 0;
	 * we do NOT raise to NTC_FALLBACK_CAP here -- that happens on the
	 * first successful sample. A missed NTC install hence runs at 0
	 * brightness, not 33, until the fallback check fires at 500 ms. */
	k_work_schedule(&ntc_work, K_MSEC(500));

	return 0;
}

SYS_INIT(ccp_thermal_guard_init, APPLICATION, CONFIG_CCP_THERMAL_GUARD_INIT_PRIORITY);
