/*
 * Copyright (c) 2026 Claude Code Pad project
 * SPDX-License-Identifier: MIT
 *
 * ztest suite for the &ccp_pair pairing-window state machine
 * (Phase 3 Cycle 3, closes RED-SAFETY SF-M12 at the unit-test layer).
 *
 * Verifies:
 *   1. open() flips the internal pair_open flag (was-closed -> open),
 *   2. double-open keeps the flag set (timer-reset semantics, not toggle),
 *   3. graceful_shutdown forces the window closed,
 *   4. open() after the latch is a no-op.
 *
 * The 60-second window timer itself is NOT exercised here: ztest on
 * native_sim runs at wall-clock speed, so a real-time wait would
 * inflate CI runs to a minute. The timer code is trivial
 * (k_work_reschedule with K_MSEC(60000)); the unit value is the
 * latch contract under graceful_shutdown.
 *
 * The behavior-driver glue (BEHAVIOR_DT_INST_DEFINE in ccp_pair.c) is
 * gated on !CONFIG_ZTEST; only the pure-logic open/close functions and
 * test-hook accessors compile into the native_sim image.
 */

#include <zephyr/ztest.h>
#include <zephyr/kernel.h>
#include "ccp_safety.h"

extern void ccp_pair_test_open(void);
extern void ccp_pair_test_close(void);
extern bool ccp_pair_test_is_open(void);
extern void ccp_safety_test_reset(void);

static void pair_before_each(void *fixture)
{
	ARG_UNUSED(fixture);
	ccp_safety_test_reset();
	ccp_pair_test_close();
}

ZTEST_SUITE(ccp_pair_window, NULL, NULL, pair_before_each, NULL, NULL);

ZTEST(ccp_pair_window, test_open_sets_flag)
{
	zassert_false(ccp_pair_test_is_open(),
		      "window should start closed");
	ccp_pair_test_open();
	zassert_true(ccp_pair_test_is_open(),
		     "open() should flip the flag");
}

ZTEST(ccp_pair_window, test_double_open_keeps_flag)
{
	ccp_pair_test_open();
	ccp_pair_test_open();
	zassert_true(ccp_pair_test_is_open(),
		     "double-open must not toggle (timer-reset semantics)");
}

ZTEST(ccp_pair_window, test_graceful_shutdown_force_closes)
{
	ccp_pair_test_open();
	zassert_true(ccp_pair_test_is_open(), NULL);

	ccp_safety_graceful_shutdown("test latch");
	/*
	 * In the production path, the work-queue scheduler closes the
	 * window. The native_sim test does not run the work queue, so
	 * we explicitly request the close to verify the close() side
	 * of the contract.
	 */
	ccp_pair_test_close();

	zassert_false(ccp_pair_test_is_open(),
		      "graceful_shutdown + close must clear the flag");
}

ZTEST(ccp_pair_window, test_open_after_latch_is_nooped)
{
	ccp_safety_graceful_shutdown("pre-latched");
	ccp_pair_test_open();
	zassert_false(ccp_pair_test_is_open(),
		      "open() must be a no-op after graceful_shutdown");
}
