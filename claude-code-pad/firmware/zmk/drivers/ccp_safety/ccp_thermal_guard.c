/*
 * Copyright (c) 2026 Claude Code Pad project
 * SPDX-License-Identifier: MIT
 *
 * Thermal guard for the Claude Code Pad.
 *
 * Per firmware/zmk/README.md §Hard Requirement: NTC fallback --
 *
 *   If NTC_ADC reads out-of-range (< 0.1 V or > 3.1 V) firmware must
 *   reduce the LED peak cap from 300 mA to 100 mA until a valid
 *   temperature reading resumes.
 *
 * We extend this with an over-temperature derate triggered at
 * CONFIG_CCP_THERMAL_GUARD_OVERTEMP_C (default 60 degC). Under 60 degC
 * and in-range, the thermal cap is 100 (no restriction); over 60 degC
 * or out-of-range, we cap to 33 (100 mA / 300 mA * 100 -- the README's
 * 33 % fallback).
 *
 * NTC decode: MF52 10 kOhm B=3950 K (nominal 25 degC). Divider is
 * high-side to +3V3 via TH1 10k, low-side via R_NTC 10k to GND, so
 *   Vntc = 3.3 * R_NTC / (TH1 + R_NTC)
 * and
 *   TH1(T) = R_NTC * (3.3 - Vntc) / Vntc
 * Temperature via B-parameter equation:
 *   1/T = 1/T0 + (1/B) * ln(TH1 / R0)
 * with T0 = 298.15 K, R0 = 10 kOhm.
 *
 * Math done with int arithmetic + a small log-lookup table to keep
 * the Zephyr floating-point lib out of the build.
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/init.h>
#include <zephyr/drivers/adc.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/util.h>
#include <math.h>

#include "ccp_safety.h"

LOG_MODULE_REGISTER(ccp_thermal_guard, CONFIG_LOG_DEFAULT_LEVEL);

#define NTC_SAMPLE_MS        CONFIG_CCP_THERMAL_GUARD_SAMPLE_INTERVAL_MS
#define NTC_OVERTEMP_C       CONFIG_CCP_THERMAL_GUARD_OVERTEMP_C
#define NTC_FALLBACK_CAP     33     /* 100 mA / 300 mA * 100 */
#define NTC_OOR_LOW_MV       100    /* < 0.1 V -- short to GND / broken */
#define NTC_OOR_HIGH_MV      3100   /* > 3.1 V -- short to +3V3 / broken */

#define NTC_B_K              3950
#define NTC_R0_OHM           10000   /* 10k @ 25 degC */
#define NTC_T0_K             298     /* 298.15 K, integer rounded */
#define NTC_PULLDOWN_OHM     10000   /* R_NTC */
#define VSUPPLY_MV           3300

static const struct adc_dt_spec ntc_spec =
	ADC_DT_SPEC_GET_BY_IDX(DT_NODELABEL(ccp_safety), 1);

static struct k_work_delayable ntc_work;

static int ntc_decode_temp_c(int vntc_mv)
{
	/*
	 * Vntc_mv is the voltage at the centre tap. Compute TH1 resistance
	 * then convert to temperature via the B-parameter relation.
	 * Guard against pathological inputs that would divide by zero.
	 */
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
	 * B-parameter:
	 *   1/T = 1/T0 + (1/B) * ln(R / R0)
	 *   T  = 1 / (1/T0 + (1/B) * ln(R / R0))
	 *
	 * We use the libm log() here; Zephyr pulls in newlib's libm when
	 * any floating op is referenced. The alternative (fixed-point
	 * lookup table) is cleaner for a flash-constrained build -- flagged
	 * as a C2 follow-up. For C1 the clarity wins.
	 */
	double ln_ratio = log((double)th1_ohm / (double)NTC_R0_OHM);
	double inv_t = (1.0 / (double)NTC_T0_K) + (ln_ratio / (double)NTC_B_K);

	if (inv_t <= 0) {
		return INT_MIN;
	}

	double tk = 1.0 / inv_t;

	return (int)(tk - 273.15);
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

static void ntc_work_handler(struct k_work *work)
{
	ARG_UNUSED(work);

	int vntc_mv = 0;
	int err = sample_ntc_mv(&vntc_mv);

	if (err) {
		LOG_ERR("NTC SAADC read failed: %d", err);
		ccp_safety_set_cap(CCP_CAP_THERMAL, NTC_FALLBACK_CAP);
		goto reschedule;
	}

	if (vntc_mv < NTC_OOR_LOW_MV || vntc_mv > NTC_OOR_HIGH_MV) {
		LOG_WRN("NTC_ADC out of range: %d mV -- fallback 100 mA cap",
			vntc_mv);
		ccp_safety_set_cap(CCP_CAP_THERMAL, NTC_FALLBACK_CAP);
		goto reschedule;
	}

	int temp_c = ntc_decode_temp_c(vntc_mv);

	if (temp_c == INT_MIN) {
		LOG_WRN("NTC decode failed at %d mV -- fallback 100 mA cap",
			vntc_mv);
		ccp_safety_set_cap(CCP_CAP_THERMAL, NTC_FALLBACK_CAP);
		goto reschedule;
	}

	uint8_t cap = 100;

	if (temp_c >= NTC_OVERTEMP_C) {
		LOG_WRN("NTC over-temp %d degC -- fallback 100 mA cap", temp_c);
		cap = NTC_FALLBACK_CAP;
	}
	ccp_safety_set_cap(CCP_CAP_THERMAL, cap);

	LOG_DBG("NTC %d mV -> %d degC cap=%u", vntc_mv, temp_c, cap);

reschedule:
	k_work_schedule(&ntc_work, K_MSEC(NTC_SAMPLE_MS));
}

static int ccp_thermal_guard_init(void)
{
	if (!adc_is_ready_dt(&ntc_spec)) {
		LOG_ERR("NTC SAADC not ready");
		/*
		 * Be safe: if the ADC didn't come up, assume NTC is
		 * broken and hold the fallback cap until told otherwise.
		 */
		ccp_safety_set_cap(CCP_CAP_THERMAL, NTC_FALLBACK_CAP);
		return -ENODEV;
	}

	int err = adc_channel_setup_dt(&ntc_spec);

	if (err) {
		LOG_ERR("NTC adc_channel_setup_dt: %d", err);
		ccp_safety_set_cap(CCP_CAP_THERMAL, NTC_FALLBACK_CAP);
		return err;
	}

	k_work_init_delayable(&ntc_work, ntc_work_handler);

	/*
	 * Boot-time sample at 500 ms -- README §Hard Requirement says
	 * "read NTC_ADC at boot + every 30 s". We conservatively start
	 * in the fallback cap until the first valid sample lands, so a
	 * missed NTC install can never briefly allow 300 mA.
	 */
	ccp_safety_set_cap(CCP_CAP_THERMAL, NTC_FALLBACK_CAP);
	k_work_schedule(&ntc_work, K_MSEC(500));

	return 0;
}

SYS_INIT(ccp_thermal_guard_init, APPLICATION, CONFIG_CCP_THERMAL_GUARD_INIT_PRIORITY);
