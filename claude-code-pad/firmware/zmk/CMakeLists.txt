# Copyright (c) 2026 Claude Code Pad project
# SPDX-License-Identifier: MIT
#
# Top-level CMakeLists for the Claude Code Pad ZMK module. module.yml
# points `cmake: .` at this file; we delegate to the safety driver
# subdirectory today and leave room for future modules (TinyML
# inference, OLED glue, PN532 figurine stack) to slot in as siblings.

if(CONFIG_CCP_BATTERY_GUARD OR CONFIG_CCP_THERMAL_GUARD OR CONFIG_ZMK_RGB_UNDERGLOW)
  add_subdirectory(drivers/ccp_safety)
endif()
