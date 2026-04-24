/*
 * Copyright (c) 2026 Claude Code Pad project
 * SPDX-License-Identifier: MIT
 *
 * ztest suite for the ccp_safety cap registry and graceful-shutdown
 * latch. Verifies the SF-B2 (fail-dark default), SF-M1 (TTL),
 * SF-M2 (set_cap no-op after latch) and FW-M3 (latch clears all slots)
 * contracts without needing a real nRF52840 board.
 *
 * Run via `west twister -T firmware/zmk/tests` on native_sim.
 */

#include <zephyr/ztest.h>
#include <zephyr/kernel.h>
#include "ccp_safety.h"

/*
 * Stubs for the three external subsystems ccp_safety_common.c calls
 * into. Having the test-suite own them keeps the production code
 * free of #ifdef CONFIG_ZTEST branches.
 */
int zmk_rgb_underglow_on(void) { return 0; }
int zmk_rgb_underglow_off(void) { return 0; }

#if defined(CONFIG_BT)
/* Bluetooth is OFF via prj.conf -- no stubs needed. */
#endif

extern void ccp_safety_test_reset(void);

static void before_each(void *fixture)
{
	ARG_UNUSED(fixture);
	ccp_safety_test_reset();
}

ZTEST_SUITE(ccp_safety_cap_registry, NULL, NULL, before_each, NULL, NULL);

ZTEST(ccp_safety_cap_registry, test_fail_dark_default)
{
	/* Fresh-boot default: nothing has called set_cap. Expect 0. */
	zassert_equal(ccp_safety_effective_cap(), 0,
		      "caps should default to 0 (fail-dark)");
}

ZTEST(ccp_safety_cap_registry, test_min_is_effective)
{
	ccp_safety_set_cap(CCP_CAP_BATTERY, 100, 1000);
	ccp_safety_set_cap(CCP_CAP_THERMAL, 33, 1000);

	zassert_equal(ccp_safety_effective_cap(), 33,
		      "effective cap should be min of sources");
}

ZTEST(ccp_safety_cap_registry, test_ttl_decays_to_zero)
{
	ccp_safety_set_cap(CCP_CAP_BATTERY, 100, 100);
	ccp_safety_set_cap(CCP_CAP_THERMAL, 100, 100);

	zassert_equal(ccp_safety_effective_cap(), 100,
		      "fresh slots should read their posted value");

	/* TTL is 2 * sample_interval_ms = 200 ms. Sleep 300 ms. */
	k_msleep(300);

	zassert_equal(ccp_safety_effective_cap(), 0,
		      "stale slots should decay to 0 within 2*interval");
}

ZTEST(ccp_safety_cap_registry, test_latch_is_nooping)
{
	/* Raise both slots so min_cap reads 100 -- otherwise the
	 * fail-dark default on the un-posted slot masks the test. */
	ccp_safety_set_cap(CCP_CAP_BATTERY, 100, 1000);
	ccp_safety_set_cap(CCP_CAP_THERMAL, 100, 1000);
	zassert_equal(ccp_safety_effective_cap(), 100, "baseline");

	ccp_safety_graceful_shutdown("test trigger");

	zassert_true(ccp_safety_is_latched(),
		     "graceful_shutdown should set the latch");
	zassert_equal(ccp_safety_effective_cap(), 0,
		      "latch should force effective cap to 0");

	/* A late set_cap must not resurrect the cap. */
	ccp_safety_set_cap(CCP_CAP_BATTERY, 100, 1000);
	ccp_safety_set_cap(CCP_CAP_THERMAL, 100, 1000);
	zassert_equal(ccp_safety_effective_cap(), 0,
		      "post-latch set_cap must be a no-op (SF-M2)");
}

ZTEST(ccp_safety_cap_registry, test_idempotent_graceful_shutdown)
{
	ccp_safety_graceful_shutdown("first");
	zassert_true(ccp_safety_is_latched(), NULL);
	ccp_safety_graceful_shutdown("second");   /* must not hang */
	zassert_true(ccp_safety_is_latched(), NULL);
}

ZTEST(ccp_safety_cap_registry, test_cap_clamp_to_100)
{
	ccp_safety_set_cap(CCP_CAP_BATTERY, 200, 1000);
	/* Internal clamp caps at 100; effective cap is min(100, other).
	 * With other slot fail-dark 0, eff is 0 -- we just assert the
	 * internal clamp didn't overflow some storage path. */
	ccp_safety_set_cap(CCP_CAP_THERMAL, 200, 1000);
	zassert_equal(ccp_safety_effective_cap(), 100, NULL);
}
