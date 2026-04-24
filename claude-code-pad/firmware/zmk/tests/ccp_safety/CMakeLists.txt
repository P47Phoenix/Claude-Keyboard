# Copyright (c) 2026 Claude Code Pad project
# SPDX-License-Identifier: MIT

cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(ccp_safety_test)

FILE(GLOB app_sources src/*.c)
target_sources(app PRIVATE ${app_sources})
# Pull in the safety-registry source-under-test. We compile it here
# rather than link against libccp_safety because the test bench uses
# a fake rgb_underglow (no ZMK on the test board) and a fake bluetooth
# subsystem; building the file directly with the stubs wired in is
# simpler than teaching the app build to swap in mocks.
target_sources(app PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/../../drivers/ccp_safety/ccp_safety_common.c
)
target_include_directories(app PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/../../drivers/ccp_safety
)
