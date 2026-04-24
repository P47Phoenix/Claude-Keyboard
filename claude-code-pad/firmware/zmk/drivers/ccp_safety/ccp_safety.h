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
 *
 * Phase 3 Cycle 2 additions:
 *   - Fail-dark init (caps start at 0, each guard raises its own slot
 *     only after the first valid sample -- SF-B2).
 *   - Per-source TTL (if a guard stops posting samples, its slot decays
 *     to 0 after 2 * expected_sample_interval -- SF-M1).
 *   - Latch-aware set_cap (once graceful_shutdown has latched, further
 *     ccp_safety_set_cap() calls are no-ops -- SF-M2).
 *   - Watchdog channel feed points so battery + thermal guard both have
 *     to pet the WDT for the system to stay alive (SF-B1).
 */

#ifndef CCP_SAFETY_H_
#define CCP_SAFETY_H_

#include <stdbool.h>
#include <stdint.h>

enum ccp_cap_source {
	CCP_CAP_BATTERY,   /* battery-guard derate 3.90 V .. 3.80 V */
	CCP_CAP_THERMAL,   /* thermal fallback when NTC out-of-range */
	CCP_CAP_NSOURCES,
};

/*
 * Register / update a brightness cap. 0..100, where 100 means "no
 * additional cap beyond Kconfig BRT_MAX". Safe to call from the
 * guard's k_work handler; internally takes a mutex.
 *
 * sample_interval_ms is used to compute a TTL -- if the registry does
 * not see another call on the same source within 2 * sample_interval_ms,
 * the slot is treated as 0 (fail-dark). Pass 0 to disable TTL for a
 * given source (only used for the graceful_shutdown broadcast).
 *
 * If graceful_shutdown has already latched, this call is a no-op and
 * returns without touching the slot.
 */
void ccp_safety_set_cap(enum ccp_cap_source src, uint8_t cap_0_100,
			uint32_t sample_interval_ms);

/*
 * Effective cap (minimum across all registered sources, taking TTL
 * expiry into account -- an expired slot reads as 0).
 */
uint8_t ccp_safety_effective_cap(void);

/*
 * Trigger the graceful shutdown path (disable all LEDs, disconnect BLE,
 * stop advertising, BAS -> 0, log warning). Called by the battery guard
 * on cutoff or broken-wire detection, by the thermal guard only via the
 * same external API. Idempotent.
 */
void ccp_safety_graceful_shutdown(const char *reason);

/*
 * True if graceful_shutdown has ever latched. Exposed so the thermal
 * guard can stop rescheduling its k_work after latch (SF-M14).
 */
bool ccp_safety_is_latched(void);

/*
 * Watchdog feed points. The battery and thermal guards each own one
 * "pet" flag; the system WDT is only fed by an aggregator thread when
 * BOTH have petted within the WDT window. If either guard stops
 * running the MCU resets and the RGB init-safe hook re-runs (SF-B1).
 */
enum ccp_wdt_source {
	CCP_WDT_BATTERY,
	CCP_WDT_THERMAL,
	CCP_WDT_NSOURCES,
};

void ccp_safety_wdt_feed(enum ccp_wdt_source src);

#endif /* CCP_SAFETY_H_ */
