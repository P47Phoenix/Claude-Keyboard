# Copyright (c) 2026 Claude Code Pad project
# SPDX-License-Identifier: MIT

zephyr_library_named(ccp_safety)
zephyr_library_sources_ifdef(CONFIG_CCP_RGB_INIT_SAFE ccp_rgb_init_safe.c)
zephyr_library_sources(ccp_safety_common.c)
zephyr_library_sources_ifdef(CONFIG_CCP_BATTERY_GUARD ccp_battery_guard.c)
zephyr_library_sources_ifdef(CONFIG_CCP_THERMAL_GUARD ccp_thermal_guard.c)
zephyr_library_include_directories(.)

# ccp_pair.c uses ZMK's behavior driver API (drivers/behavior.h, zmk/behavior.h),
# which lives under zmk/app/include/ -- a path the ZMK app target sees but
# module-side libraries do not. The upstream pattern (used by ZMK's own
# test-behaviors at zmk/app/module/test-behaviors/CMakeLists.txt) is to
# attach the source to the `app` target via target_sources. We do the same
# here so &ccp_pair links into ZMK's behavior dispatch table just like a
# first-party behavior would.
if(CONFIG_CCP_PAIR_BEHAVIOR)
  target_sources(app PRIVATE ${CMAKE_CURRENT_LIST_DIR}/ccp_pair.c)
  target_include_directories(app PRIVATE ${CMAKE_CURRENT_LIST_DIR})
endif()
