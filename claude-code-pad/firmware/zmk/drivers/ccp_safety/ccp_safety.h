/*
 * Copyright (c) 2026 Claude Code Pad project
 * SPDX-License-Identifier: MIT
 *
 * Shared cap-registry for the two project-specific safety guards.
 * Each guard computes a local cap (fraction of max brightness in 0..100)
 * and publishes it here. The effective cap applied to ZMK's underglow
 * driver is always the minimum of the registered caps.
 *
 * Both guards always run simultaneously in release builds; the cap
 * registry lets them compose without coupling.
 */

#ifndef CCP_SAFETY_H_
#define CCP_SAFETY_H_

#include <stdint.h>

enum ccp_cap_source {
	CCP_CAP_BATTERY,   /* battery-guard derate 3.90 V .. 3.70 V */
	CCP_CAP_THERMAL,   /* thermal fallback when NTC out-of-range */
	CCP_CAP_NSOURCES,
};

/*
 * Register / update a brightness cap. 0..100, where 100 means "no
 * additional cap beyond Kconfig BRT_MAX". Safe to call from the
 * guard's k_work handler; internally takes a mutex.
 */
void ccp_safety_set_cap(enum ccp_cap_source src, uint8_t cap_0_100);

/*
 * Effective cap (minimum across all registered sources).
 */
uint8_t ccp_safety_effective_cap(void);

/*
 * Trigger the graceful shutdown path (disable all LEDs, minimum BLE
 * activity, log warning). Called by the battery guard on cutoff or
 * broken-wire detection. Idempotent.
 */
void ccp_safety_graceful_shutdown(const char *reason);

#endif /* CCP_SAFETY_H_ */
