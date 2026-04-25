# Copyright (c) 2026 Claude Code Pad project
# SPDX-License-Identifier: MIT

cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(ccp_safety_test)

FILE(GLOB app_sources src/*.c)
target_sources(app PRIVATE ${app_sources})
# Pull in the safety-registry + pair-window source under test. We
# compile them here rather than link against libccp_safety because the
# test bench uses a fake rgb_underglow (no ZMK on the test board) and
# a fake bluetooth subsystem; building the files directly with the
# stubs wired in is simpler than teaching the app build to swap in
# mocks. ccp_pair.c gates its DT/behavior glue on !CONFIG_ZTEST so the
# pure-logic state machine is what compiles into the test image.
target_sources(app PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/../../drivers/ccp_safety/ccp_safety_common.c
  ${CMAKE_CURRENT_SOURCE_DIR}/../../drivers/ccp_safety/ccp_pair.c
)
target_include_directories(app PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/../../drivers/ccp_safety
)
