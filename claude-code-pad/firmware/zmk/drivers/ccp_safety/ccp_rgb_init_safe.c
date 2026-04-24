/*
 * Copyright (c) 2026 Claude Code Pad project
 * SPDX-License-Identifier: MIT
 *
 * Pre-RGB-driver init hook: drives RGB_DIN_MCU (back-pad slot 3, P0.06)
 * as GPIO output LOW BEFORE the SPI/WS2812 driver takes over. Satisfies
 * firmware/zmk/README.md §Hard Requirement: LED peak current cap
 * §RGB driver init order (steps 1 and 2).
 *
 * Rationale: worst-case pre-init nRF52840 GPIO state is floating CMOS
 * input with internal ~10 kOhm pull-up; 25 SK6812MINI-E LEDs seeing
 * random data on DIN at power-on could briefly light at uncontrolled
 * brightness, exceeding the 300 mA Annex Q cap.
 *
 * Init priority 45 is BEFORE the SPI3 peripheral (default 50) and the
 * WS2812 driver (default 90). After this hook returns, the SPI
 * subsystem reclaims P0.06 via pinctrl and begins emitting the "all
 * LEDs off" first frame the ZMK RGB driver sends on startup.
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/init.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(ccp_rgb_init_safe, CONFIG_LOG_DEFAULT_LEVEL);

/* P0.06 -- RGB_DIN_MCU back-pad slot 3 */
#define RGB_DIN_PORT  DT_NODELABEL(gpio0)
#define RGB_DIN_PIN   6

static int ccp_rgb_init_safe(void)
{
	const struct device *port = DEVICE_DT_GET(RGB_DIN_PORT);

	if (!device_is_ready(port)) {
		LOG_ERR("gpio0 not ready; cannot pre-drive RGB_DIN_MCU LOW");
		return -ENODEV;
	}

	int ret = gpio_pin_configure(port, RGB_DIN_PIN,
				     GPIO_OUTPUT_INACTIVE);
	if (ret) {
		LOG_ERR("failed to drive RGB_DIN_MCU LOW: %d", ret);
		return ret;
	}

	/*
	 * Hold LOW long enough that (a) any in-flight SK6812MINI latch
	 * (>= 50 us quiet time) completes with all-zeros, and (b) the
	 * +3V3 rail stabilises. 200 us is well above both bounds without
	 * meaningfully delaying boot.
	 */
	k_busy_wait(200);

	LOG_DBG("RGB_DIN_MCU pre-driven LOW");
	return 0;
}

SYS_INIT(ccp_rgb_init_safe, POST_KERNEL, 45);
