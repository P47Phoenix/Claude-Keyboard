# Copyright (c) 2026 Claude Code Pad project
# SPDX-License-Identifier: MIT

zephyr_library_named(ccp_safety)
zephyr_library_sources_ifdef(CONFIG_CCP_RGB_INIT_SAFE ccp_rgb_init_safe.c)
zephyr_library_sources(ccp_safety_common.c)
zephyr_library_sources_ifdef(CONFIG_CCP_BATTERY_GUARD ccp_battery_guard.c)
zephyr_library_sources_ifdef(CONFIG_CCP_THERMAL_GUARD ccp_thermal_guard.c)
zephyr_library_include_directories(.)
