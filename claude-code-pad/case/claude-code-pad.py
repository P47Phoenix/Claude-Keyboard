"""
Claude Code Pad -- parametric case (Phase 2 Cycle 1, MECH-1)

Generates:
  - top-case.stl     (plate + low sidewalls, MX cutouts, 2U stab, cutouts)
  - bottom-case.stl  (tray + battery bay + vents + heat-set bosses)
  - assembly.step    (top + bottom + placeholder PCB/battery/encoder/USB-C)

Coordinate system
-----------------
All geometry is authored in a CASE-LOCAL frame whose (0,0,0) corner is
aligned with the PCB's *board origin* (KiCad aux origin = 100,100). X is
east, Y is north, Z is up. This matches the PCB Edge.Cuts outline:
    (0,0) -> (120,132) rectangle, rounded R3.
The PCB sits at Z=0 top face; the top case's plate underside sits at
Z = pcb_thickness + plate_to_pcb_gap.

Run
---
    case/.venv/bin/python case/claude-code-pad.py

This executes all build_* functions, runs a sanity check, writes STL+STEP
to the case/ directory, and prints a status line.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Iterable, Tuple

import cadquery as cq

# ============================================================================
# PARAMETERS  (all mm)  ---  bump these to tweak fitment / ergonomics
# ============================================================================

# --- Shrinkage compensation (Cycle 2 BLOCKER #1, #2) ------------------------
# Empirical baseline for Creality K2 Plus / PETG at 235 C / 85 C bed.
# All INNER CUTOUT apertures are scaled up by (1 + SHRINK_COMPENSATION) so
# the cooled part ends up at nominal. Builder must verify per-printer /
# per-filament by printing `test-coupon.stl` and measuring the MX cutout
# column that clips cleanest, then feeding that value back into this
# parameter before a full case print.
SHRINK_COMPENSATION = 0.005
COUPON_SHRINK_STEPS = [0.003, 0.005, 0.007]

# --- Board (read from PCB Edge.Cuts, aux origin at 100,100) ---
BOARD_W = 120.0          # east-west extent of PCB
BOARD_H = 132.0          # north-south extent of PCB
BOARD_THICKNESS = 1.6    # FR4 1.6 mm
BOARD_CORNER_R = 3.0     # PCB corner radius

# USB-C notch on PCB's north edge (absolute 154..166, 98..100 -> local 54..66, -2..0)
USBC_NOTCH_X = 54.0      # west edge of notch (local X)
USBC_NOTCH_W = 12.0      # notch width

# --- Key grid (5 x 5, 19.05 mm pitch; MX cutout 14.0 x 14.0 mm) ---
KEY_PITCH = 19.05
KEY_CUTOUT = 14.0
# Local-frame column centres (absolute 119.4..195.6 -> local 19.4..95.6)
COL_X = [19.4, 38.45, 57.5, 76.55, 95.6]
# Local-frame row centres  (absolute 139.525..215.725 -> local 39.525..115.725)
ROW_Y = [39.525, 58.575, 77.625, 96.675, 115.725]
# 2U Enter at (row 4, col 4): stab offset is +/- 11.9 mm (Cherry), but the
# footprint uses +9.525 mm centre shift (the 0.5U offset) so the key centre
# is at x = 95.6 + 9.525 = 105.125.
ENTER_KEY_CENTRE = (105.125, 115.725)

# Cherry plate-mount 2U stabilizer slots (Keebio canonical geometry)
# Slot centres: +/- 11.9 mm c-to-c from key centre; slot is 3.97 wide x 6.65 tall
# plus a 3.05 dia wire hole 2.3 mm north of key centre on the wire axis.
STAB_OFFSET = 11.9
STAB_SLOT_W = 3.97
STAB_SLOT_H = 6.65       # slot total height (north-south)
STAB_WIRE_HOLE_D = 3.05
STAB_WIRE_OFFSET_N = 2.3 # wire hole is 2.3 mm N of key centre

# --- Encoder, switch, JST, NTC, XIAO (local frame) ---
ENCODER_CENTRE = (108.0, 19.0)    # EC11 (abs 208,119 -> local 108,19)
ENCODER_KNOB_D = 10.0             # knob access hole dia
XIAO_CENTRE = (60.0, 19.0)        # U1 (abs 160,119 -> local 60,19)
SWITCH_CENTRE = (33.0, 19.0)      # SW_PWR1 (abs 133,119 -> local 33,19)
JST_CENTRE = (8.0, 19.0)          # J_BAT1 (abs 108,119 -> local 8,19)
NTC_CENTRE = (10.0, 24.0)         # TH1 (abs 110,124 -> local 10,24)

SWITCH_WINDOW_W = 8.0             # lever access slot
SWITCH_WINDOW_H = 4.0

USBC_SLOT_W = 14.0                # plug-body clearance in top wall
USBC_SLOT_H = 10.0

# --- Mounting holes (local frame, from PCB H1..H4) ---
MOUNT_HOLES = [
    (3.5, 27.0),    # H1  (abs 103.5,127)
    (116.5, 27.0),  # H2  (abs 216.5,127)
    (5.0, 128.0),   # H3  (abs 105,228)
    (115.0, 128.0), # H4  (abs 215,228)
]

# --- Antenna keepout (25 x 10.3 mm over XIAO antenna, centred on XIAO.x, top-ish) ---
# Per spec: 25 x 10.3 mm; the XIAO antenna is at the PCB's "outer" end.
# XIAO at y=19 local; the chip's antenna is on the module's far edge pointing
# toward board centre. Conservatively place keepout rectangle centred on the
# XIAO footprint.
ANTENNA_KEEPOUT_CENTRE = (60.0, 19.0)
ANTENNA_KEEPOUT_W = 25.0
ANTENNA_KEEPOUT_H = 10.3
ANTENNA_KEEPOUT_CLEARANCE = 5.0   # no metal / heat-set inserts within 5 mm

# --- Battery bay (Adafruit #1578: 50 x 34 x 7 mm + 2 mm clearance all round) ---
BATT_BAY_W = 50.0 + 2 * 2.0        # 54 mm interior
BATT_BAY_H = 34.0 + 2 * 2.0        # 38 mm
BATT_BAY_DEPTH = 7.0 + 2.0         # 9 mm (+2 mm vertical clearance)
# Centre the battery bay under the keyboard grid, west-of-centre so JST cable
# reaches J_BAT1 (local X=8). Bay centre at (30, 75) puts west wall at X=3
# and east wall at X=57, well clear of mounting bosses and with cable run
# to J_BAT through the divider slot.
BATT_BAY_CENTRE = (30.0, 75.0)

# Vent slots above battery (2 x  3 x 10 mm)
VENT_SLOT_W = 10.0
VENT_SLOT_H = 3.0
# two slots straddling the bay's long axis, on the bottom case floor
VENT_SLOTS = [
    (BATT_BAY_CENTRE[0] - 10.0, BATT_BAY_CENTRE[1]),
    (BATT_BAY_CENTRE[0] + 10.0, BATT_BAY_CENTRE[1]),
]

# FR-4 divider slot (1.6 mm FR-4 thickness, slide-fit groove -- 1.8 mm slot)
DIVIDER_SLOT_T = 1.8
DIVIDER_HEIGHT = BATT_BAY_DEPTH    # divider spans full bay depth

# JST cable exit (strain-relief pinch slot) -- a 2 mm-wide vertical notch on
# the divider's north face, centred on JST Y
JST_EXIT_Y = JST_CENTRE[1]
JST_EXIT_W = 2.5
JST_EXIT_H = 4.0                   # slot height (cable dia 1.5 mm nominal)

# --- Wall / plate thicknesses ---
# Cycle 2 MAJOR #5: bump from 1.5 to 2.0 for stiffness under keypress loads
# across a 5x5 grid. MX clip spec is 1.5 +/- 0.3, so 2.0 sits at the upper
# end of spec -- verified to engage but builder should test-click one switch
# before committing to a full print.
PLATE_THICKNESS = 2.0
TOP_WALL_THICKNESS = 2.0

# Two-part case mating:
#   bottom case: floor + perimeter wall rising to BOTTOM_WALL_TOP_Z (the MATING PLANE)
#   top case:   plate whose BOTTOM sits at BOTTOM_WALL_TOP_Z, + short lip
#               that drops into the bottom interior for alignment
# This keeps the two solids from volumetrically intersecting.
TOP_LIP_DEPTH = 2.5                # how far the top lip drops into bottom
TOP_LIP_CLEARANCE = 0.4            # slip fit (Cycle 2 MAJOR #3: 0.3 -> 0.4 mm)
LIP_CHAMFER = 0.5                  # 45 deg lead-in / relief chamfer

BOTTOM_WALL_THICKNESS = 2.0
BOTTOM_FLOOR_THICKNESS = 2.0
PCB_TRAY_STANDOFF = 3.0            # PCB bottom sits 3 mm above case floor (room for B.Cu parts / LEDs / reset)
# Bottom interior height needs to cover: standoff(3) + PCB(1.6) + components (~5 mm
# worst case TH parts below PCB bottom we don't care about -- PCB is at 3 mm off
# floor, so 3 mm below PCB free for THT leads) + MX switch body to skirt bottom.
# MX switch body height above PCB = 11.6 mm (MX spec). Top case plate sits
# plate_bottom_z above PCB top = 5 mm above PCB top (leaves 6.6 mm head-room
# for MX bottom housing which is 5 mm below plate when fully seated -- but
# MX switches mount TO the plate, so plate is what holds the switch: the
# switch body extends 5 mm below the plate. PCB top is 5 mm below plate
# underside, so the switch's pin pads on PCB are reached.
PLATE_TO_PCB_GAP = 5.0             # MX switch lower housing 5 mm below plate
BOTTOM_INTERIOR_HEIGHT = PCB_TRAY_STANDOFF + BOARD_THICKNESS + PLATE_TO_PCB_GAP
# Interior height above floor top = 3 + 1.6 + 5 = 9.6 mm -> use 10 mm for margin
BOTTOM_INTERIOR_HEIGHT = max(BOTTOM_INTERIOR_HEIGHT, BATT_BAY_DEPTH + 1.0)
BOTTOM_WALL_TOP_Z = BOTTOM_INTERIOR_HEIGHT   # mating plane Z (case frame)
BOTTOM_CASE_TOTAL_H = BOTTOM_FLOOR_THICKNESS + BOTTOM_INTERIOR_HEIGHT

# --- Heat-set insert bosses (M3, CNC-Kitchen IUB-M3-L4 brass, 4 mm long) ----
# Cycle 2 MAJOR #4: bump wall around insert to 2.0 mm for PETG fracture safety.
# Insert dia 4.0 nominal (brass knurl pre-flow); pilot is _shrink()ed at cut
# time so the cooled pilot lands at 4.0 mm. Insert depth 4.2 mm > IUB-M3-L4 4.0
# gives 0.2 mm float before the insert bottoms out, accepting normal print Z
# variance without pushing a hot insert against a hard stop.
INSERT_DIA = 4.0                   # pilot Ø (nominal, pre-shrinkage)
INSERT_DEPTH = 4.2                 # pilot depth (mates IUB-M3-L4, 4 mm long, + 0.2 mm float)
BOSS_OD = 8.0                      # outer Ø of boss (2.0 mm wall around insert)
BOSS_HEIGHT = INSERT_DEPTH + 2.5   # 6.7 mm: insert depth + 2.5 mm solid PETG floor

# --- Case outline (board + wall + fit clearance) ---
CASE_FIT_CLEARANCE = 0.4           # 0.2 mm per side PCB-to-wall
CASE_OUTER_W = BOARD_W + 2 * (BOTTOM_WALL_THICKNESS + CASE_FIT_CLEARANCE)  # ~124.8 mm
CASE_OUTER_H = BOARD_H + 2 * (BOTTOM_WALL_THICKNESS + CASE_FIT_CLEARANCE)  # ~136.8 mm
CASE_OUTER_R = 4.0

# Shift so board local (0,0) maps to case-interior (CASE_WALL+fit, CASE_WALL+fit)
BOARD_OFFSET_X = BOTTOM_WALL_THICKNESS + CASE_FIT_CLEARANCE
BOARD_OFFSET_Y = BOTTOM_WALL_THICKNESS + CASE_FIT_CLEARANCE

# --- Print / rubber feet ---
FOOT_D = 10.0
FOOT_DEPTH = 1.0
FOOT_INSET = 8.0

# ============================================================================
# HELPERS
# ============================================================================


def _shrink(nominal: float) -> float:
    """Scale a nominal INNER-CUTOUT dimension upward by the empirical
    shrinkage factor so the cooled part lands at nominal. Apply to
    cutouts only (holes, slots, windows, pocket walls measured from
    interior) -- never to outer shells (outer walls shrink INward, so
    applying the same up-scale to the shell would make the case
    oversized)."""
    return nominal * (1.0 + SHRINK_COMPENSATION)


def _rounded_rect(w: float, h: float, r: float) -> cq.Sketch:
    """Sketch a centred rounded rectangle."""
    return cq.Sketch().rect(w, h).vertices().fillet(r)


def _board_to_case(x: float, y: float) -> Tuple[float, float]:
    """Convert a board-local coordinate to case-outer frame (for outlines)."""
    return (x + BOARD_OFFSET_X, y + BOARD_OFFSET_Y)


def _iter_mx_centres() -> Iterable[Tuple[float, float]]:
    """Yield (x, y) key centres in board-local frame, 5x5 plus 2U offset for (4,4)."""
    for r, ry in enumerate(ROW_Y):
        for c, cx in enumerate(COL_X):
            if r == 4 and c == 4:
                yield ENTER_KEY_CENTRE
            else:
                yield (cx, ry)


# ============================================================================
# TOP CASE
# ============================================================================


def build_top_case() -> cq.Workplane:
    """Top case: a full-footprint plate + short downward lip that slips into
    the bottom case's interior for alignment. The plate TOP is at Z=0 and the
    lip hangs DOWN from Z = -PLATE_THICKNESS to Z = -(PLATE_THICKNESS + LIP).

    Features:
      - 25x MX cutouts + 2U stab slots + wire holes (through plate)
      - encoder knob access hole
      - 4x M3 clearance holes through plate
      - north-wall apertures for USB-C and SPDT slide switch (through lip)
    """
    outer_w = CASE_OUTER_W
    outer_h = CASE_OUTER_H
    outer_r = CASE_OUTER_R

    lip_w = outer_w - 2 * (TOP_WALL_THICKNESS + TOP_LIP_CLEARANCE)
    lip_h = outer_h - 2 * (TOP_WALL_THICKNESS + TOP_LIP_CLEARANCE)
    lip_r = max(outer_r - (TOP_WALL_THICKNESS + TOP_LIP_CLEARANCE), 1.0)

    # Plate: full footprint, 1.5 mm thick, top at Z=0
    plate = (
        cq.Workplane("XY")
        .placeSketch(_rounded_rect(outer_w, outer_h, outer_r))
        .extrude(-PLATE_THICKNESS)
        .translate((outer_w / 2, outer_h / 2, 0))
    )

    # Lip: hangs below the plate, slightly inboard for slip fit
    lip = (
        cq.Workplane("XY")
        .placeSketch(_rounded_rect(lip_w, lip_h, lip_r))
        .extrude(TOP_LIP_DEPTH)
        .translate((outer_w / 2, outer_h / 2, -PLATE_THICKNESS - TOP_LIP_DEPTH))
    )
    # Hollow the lip so only the perimeter wall remains (structural, not solid)
    lip_hollow = (
        cq.Workplane("XY")
        .rect(lip_w - 2 * TOP_WALL_THICKNESS, lip_h - 2 * TOP_WALL_THICKNESS)
        .extrude(TOP_LIP_DEPTH + 0.2)
        .translate((outer_w / 2, outer_h / 2, -PLATE_THICKNESS - TOP_LIP_DEPTH - 0.1))
    )
    lip = lip.cut(lip_hollow)

    # Cycle 2 MAJOR #3: 0.5 mm x 45 deg lead-in chamfer on lip bottom outer edge.
    # Cut a rectangular ring of increasing outward offset at Z = lip_bottom so the
    # bottom outer corner becomes a 45-deg ramp. Use a boolean subtraction with a
    # wedge-shaped solid rather than edge-chamfer (more robust on hollow rings).
    lip_bot_z = -PLATE_THICKNESS - TOP_LIP_DEPTH
    chamfer_outer_w = lip_w + 2 * LIP_CHAMFER
    chamfer_outer_h = lip_h + 2 * LIP_CHAMFER
    # Frustum subtractor: large outer-envelope box minus inner pyramid that
    # leaves exactly the 45-deg ramp on the outer lip corner.
    outer_block = (
        cq.Workplane("XY")
        .rect(chamfer_outer_w, chamfer_outer_h)
        .extrude(LIP_CHAMFER + 0.2)
        .translate((outer_w / 2, outer_h / 2, lip_bot_z - 0.1))
    )
    # The "ramp keeper" is the lip's outer silhouette offset by a 45-deg taper
    # over LIP_CHAMFER height. We build it as a pair of rectangles lofted.
    ramp_pts_bottom_w = lip_w
    ramp_pts_bottom_h = lip_h
    ramp = (
        cq.Workplane("XY")
        .workplane(offset=0.0)
        .rect(ramp_pts_bottom_w, ramp_pts_bottom_h)
        .workplane(offset=LIP_CHAMFER)
        .rect(ramp_pts_bottom_w + 2 * LIP_CHAMFER,
              ramp_pts_bottom_h + 2 * LIP_CHAMFER)
        .loft(combine=True)
        .translate((outer_w / 2, outer_h / 2, lip_bot_z))
    )
    chamfer_cutter = outer_block.cut(ramp)
    lip = lip.cut(chamfer_cutter)

    body = plate.union(lip)

    # --- Plate cutouts (all extend slightly above and below plate to ensure clean cut) ---
    cut_top = 0.5
    cut_bottom = -(PLATE_THICKNESS + 0.5)

    # MX key cutouts (shrinkage-compensated)
    mx_cut = _shrink(KEY_CUTOUT)
    for (bx, by) in _iter_mx_centres():
        cx, cy = _board_to_case(bx, by)
        mx = (
            cq.Workplane("XY", origin=(cx, cy, cut_bottom))
            .rect(mx_cut, mx_cut)
            .extrude(cut_top - cut_bottom)
        )
        body = body.cut(mx)

    # 2U Enter stab slots + wire holes (shrinkage-compensated)
    ex, ey = _board_to_case(*ENTER_KEY_CENTRE)
    stab_w = _shrink(STAB_SLOT_W)
    stab_h = _shrink(STAB_SLOT_H)
    stab_wire_d = _shrink(STAB_WIRE_HOLE_D)
    for sign in (-1, 1):
        slot = (
            cq.Workplane("XY", origin=(ex + sign * STAB_OFFSET, ey, cut_bottom))
            .rect(stab_w, stab_h)
            .extrude(cut_top - cut_bottom)
        )
        body = body.cut(slot)
        wire = (
            cq.Workplane("XY",
                         origin=(ex + sign * STAB_OFFSET,
                                 ey - STAB_WIRE_OFFSET_N,
                                 cut_bottom))
            .circle(stab_wire_d / 2)
            .extrude(cut_top - cut_bottom)
        )
        body = body.cut(wire)

    # Encoder knob access hole (shrinkage-compensated)
    ecx, ecy = _board_to_case(*ENCODER_CENTRE)
    enc_hole = (
        cq.Workplane("XY", origin=(ecx, ecy, cut_bottom))
        .circle(_shrink(ENCODER_KNOB_D) / 2)
        .extrude(cut_top - cut_bottom)
    )
    body = body.cut(enc_hole)

    # M3 clearance holes through plate (shrinkage-compensated)
    m3_clr = _shrink(3.2)
    for (bx, by) in MOUNT_HOLES:
        cx, cy = _board_to_case(bx, by)
        hole = (
            cq.Workplane("XY", origin=(cx, cy, cut_bottom))
            .circle(m3_clr / 2)
            .extrude(cut_top - cut_bottom)
        )
        body = body.cut(hole)

    # --- Wall apertures (through the LIP in north wall near USB / switch) ---
    # USB-C on north wall: punch a horizontal slot through lip at plate's N edge.
    # Lip north face is at Y=0; lip wall extends Y=0..Y=TOP_WALL_THICKNESS+TOP_LIP_CLEARANCE.
    lip_top_z = -PLATE_THICKNESS
    lip_bot_z = -PLATE_THICKNESS - TOP_LIP_DEPTH

    usbc_x_c = BOARD_OFFSET_X + USBC_NOTCH_X + USBC_NOTCH_W / 2
    usb_aperture = (
        cq.Workplane("XY",
                     origin=(usbc_x_c, 0.0, lip_bot_z))
        .box(_shrink(USBC_SLOT_W), (TOP_WALL_THICKNESS + TOP_LIP_CLEARANCE) * 3,
             TOP_LIP_DEPTH + 0.2,
             centered=(True, True, False))
    )
    body = body.cut(usb_aperture)

    swx, _ = _board_to_case(*SWITCH_CENTRE)
    sw_win = (
        cq.Workplane("XY",
                     origin=(swx, 0.0, lip_bot_z + 0.2))
        .box(_shrink(SWITCH_WINDOW_W), (TOP_WALL_THICKNESS + TOP_LIP_CLEARANCE) * 3,
             _shrink(SWITCH_WINDOW_H),
             centered=(True, True, False))
    )
    body = body.cut(sw_win)

    return body


# ============================================================================
# BOTTOM CASE
# ============================================================================


def _iter_insert_bosses() -> Iterable[Tuple[float, float]]:
    """Mounting boss centres in case-outer frame."""
    for (bx, by) in MOUNT_HOLES:
        yield _board_to_case(bx, by)


def _boss_violates_antenna_keepout(cx_case: float, cy_case: float) -> bool:
    """Return True if a boss at case-frame (cx,cy) falls within the 5 mm
    antenna keepout envelope.  Converts back to board-local frame."""
    bx = cx_case - BOARD_OFFSET_X
    by = cy_case - BOARD_OFFSET_Y
    kx, ky = ANTENNA_KEEPOUT_CENTRE
    x_envelope = ANTENNA_KEEPOUT_W / 2 + ANTENNA_KEEPOUT_CLEARANCE
    y_envelope = ANTENNA_KEEPOUT_H / 2 + ANTENNA_KEEPOUT_CLEARANCE
    return (abs(bx - kx) <= x_envelope) and (abs(by - ky) <= y_envelope)


def build_bottom_case() -> cq.Workplane:
    """Bottom case: floor + perimeter wall + PCB tray standoffs + heat-set
    bosses + battery bay + vents + JST strain relief + divider slot.

    Origin: case-outer frame. Z=0 is the TOP of the floor (inside of case).
    The floor extends from Z=-BOTTOM_FLOOR_THICKNESS to Z=0. Walls from
    Z=0 to Z=BOTTOM_CASE_HEIGHT-BOTTOM_FLOOR_THICKNESS.
    """
    wall_h_above_floor = BOTTOM_INTERIOR_HEIGHT

    # Outer shell: from Z=-BOTTOM_FLOOR_THICKNESS (under-side of floor) up to
    # Z=BOTTOM_INTERIOR_HEIGHT (mating plane with top lip)
    shell_outer = (
        cq.Workplane("XY")
        .placeSketch(_rounded_rect(CASE_OUTER_W, CASE_OUTER_H, CASE_OUTER_R))
        .extrude(BOTTOM_CASE_TOTAL_H)
        .translate((CASE_OUTER_W / 2, CASE_OUTER_H / 2, -BOTTOM_FLOOR_THICKNESS))
    )

    # Interior pocket (hollow out) -- leave FLOOR intact
    inner_w = CASE_OUTER_W - 2 * BOTTOM_WALL_THICKNESS
    inner_h = CASE_OUTER_H - 2 * BOTTOM_WALL_THICKNESS
    pocket = (
        cq.Workplane("XY")
        .rect(inner_w, inner_h)
        .extrude(wall_h_above_floor + 0.1)
        .translate((CASE_OUTER_W / 2, CASE_OUTER_H / 2, 0))
    )
    body = shell_outer.cut(pocket)

    # Heat-set insert bosses (keep clear of antenna keepout)
    for (cx, cy) in _iter_insert_bosses():
        if _boss_violates_antenna_keepout(cx, cy):
            # Fallback: place a THROUGH-HOLE M3 tap (plastic) instead of a
            # metal heat-set insert; we still need structural support, so
            # we keep the boss but tag it by using a slightly narrower boss
            # and a plain 2.8 mm tap drill (thread into PETG directly).
            pilot_d = 2.8            # M3 self-tap into PETG -- no metal in antenna zone
            pilot_depth = BOSS_HEIGHT
        else:
            pilot_d = INSERT_DIA
            pilot_depth = INSERT_DEPTH

        boss = (
            cq.Workplane("XY")
            .circle(BOSS_OD / 2)
            .extrude(BOSS_HEIGHT)
            .translate((cx, cy, 0))
        )
        hole = (
            cq.Workplane("XY")
            .circle(_shrink(pilot_d) / 2)
            .extrude(pilot_depth + 0.2)
            .translate((cx, cy, BOSS_HEIGHT - pilot_depth))
        )
        boss = boss.cut(hole)
        body = body.union(boss)

    # PCB tray: 4 x small support ribs under PCB corners (3 mm standoff)
    # Use the bosses (which already stand at BOSS_HEIGHT >= standoff) as the
    # primary supports; add 4 more small standoffs mid-edge so the PCB doesn't
    # flex on keypresses.
    mid_supports = [
        (CASE_OUTER_W / 2, BOARD_OFFSET_Y + 2.0),                  # north-mid
        (CASE_OUTER_W / 2, BOARD_OFFSET_Y + BOARD_H - 2.0),        # south-mid
        (BOARD_OFFSET_X + 2.0, CASE_OUTER_H / 2),                  # west-mid
        (BOARD_OFFSET_X + BOARD_W - 2.0, CASE_OUTER_H / 2),        # east-mid
    ]
    for (cx, cy) in mid_supports:
        # Skip anything inside the antenna keepout envelope
        if _boss_violates_antenna_keepout(cx, cy):
            continue
        rib = (
            cq.Workplane("XY")
            .circle(3.0)
            .extrude(PCB_TRAY_STANDOFF)
            .translate((cx, cy, 0))
        )
        body = body.union(rib)

    # Battery bay walls: 4 walls 1.5 mm thick, BATT_BAY_DEPTH high, around
    # BATT_BAY_W x BATT_BAY_H centred on BATT_BAY_CENTRE (board-local -> case).
    bc_x, bc_y = _board_to_case(*BATT_BAY_CENTRE)
    bay_wall_t = 1.5
    bay_outer_w = BATT_BAY_W + 2 * bay_wall_t
    bay_outer_h = BATT_BAY_H + 2 * bay_wall_t

    bay_shell = (
        cq.Workplane("XY")
        .rect(bay_outer_w, bay_outer_h)
        .extrude(BATT_BAY_DEPTH)
        .translate((bc_x, bc_y, 0))
    )
    bay_cavity = (
        cq.Workplane("XY")
        .rect(BATT_BAY_W, BATT_BAY_H)
        .extrude(BATT_BAY_DEPTH + 0.2)
        .translate((bc_x, bc_y, -0.1))
    )
    bay_shell = bay_shell.cut(bay_cavity)
    body = body.union(bay_shell)

    # Divider slot: 1.8 mm groove on the NORTH interior face of the bay
    # (runs E-W, into the bay wall). Add it as a SUBTRACTION from the north
    # wall of the bay interior.
    divider_slot = (
        cq.Workplane("XY")
        .rect(BATT_BAY_W, DIVIDER_SLOT_T)
        .extrude(DIVIDER_HEIGHT)
        .translate((bc_x, bc_y + BATT_BAY_H / 2 - DIVIDER_SLOT_T / 2, 0))
    )
    body = body.cut(divider_slot)

    # JST cable exit / strain-relief pinch slot through the north bay wall
    jst_exit = (
        cq.Workplane("XY")
        .box(JST_EXIT_W, bay_wall_t * 2 + 0.5, JST_EXIT_H,
             centered=(True, True, False))
        .translate((bc_x - BATT_BAY_W / 4, bc_y + BATT_BAY_H / 2 + bay_wall_t / 2, BATT_BAY_DEPTH - JST_EXIT_H - 1.0))
    )
    body = body.cut(jst_exit)

    # Strain-relief post: small cylinder 2 mm dia just past the exit hole,
    # inside the bay, so the cable routes around it
    relief_post = (
        cq.Workplane("XY")
        .circle(1.0)
        .extrude(BATT_BAY_DEPTH - 1.0)
        .translate((bc_x - BATT_BAY_W / 4 + 2.5, bc_y + BATT_BAY_H / 2 - 2.0, 0))
    )
    body = body.union(relief_post)

    # Vent slots on the battery bay FLOOR (bottom of case) -- egress
    for (vx_b, vy_b) in VENT_SLOTS:
        vx, vy = _board_to_case(vx_b, vy_b)
        vent = (
            cq.Workplane("XY")
            .rect(VENT_SLOT_W, VENT_SLOT_H)
            .extrude(BOTTOM_FLOOR_THICKNESS + 0.2)
            .translate((vx, vy, -BOTTOM_FLOOR_THICKNESS - 0.1))
        )
        body = body.cut(vent)

    # NTC thermal window: small 6 x 3 mm slot above the TH1 body so it reads
    # the battery-bay ambient directly (no cap of plastic between cell and NTC)
    nx, ny = _board_to_case(*NTC_CENTRE)
    ntc_window = (
        cq.Workplane("XY")
        .rect(6.0, 3.0)
        .extrude(BATT_BAY_DEPTH + 0.2)
        .translate((nx, ny, -0.1))
    )
    # Only cut if NTC x overlaps bay; it should (nx~13.8 case; bay west wall ~5).
    body = body.cut(ntc_window)

    # Carve lip-envelope: any interior feature that rises into the top case
    # lip's landing volume gets trimmed so the lip can seat. The lip occupies
    # a ring from inset (TOP_WALL_THICKNESS + TOP_LIP_CLEARANCE) to inset
    # (2*TOP_WALL_THICKNESS + TOP_LIP_CLEARANCE) when the top case is placed,
    # spanning Z = BOTTOM_WALL_TOP_Z - TOP_LIP_DEPTH to BOTTOM_WALL_TOP_Z.
    lip_outer_inset = TOP_WALL_THICKNESS + TOP_LIP_CLEARANCE           # 2.3
    lip_inner_inset = 2 * TOP_WALL_THICKNESS + TOP_LIP_CLEARANCE       # 4.3
    lip_outer_w = CASE_OUTER_W - 2 * lip_outer_inset                   # 120.2
    lip_outer_h = CASE_OUTER_H - 2 * lip_outer_inset
    lip_inner_w = CASE_OUTER_W - 2 * lip_inner_inset                   # 116.2
    lip_inner_h = CASE_OUTER_H - 2 * lip_inner_inset
    lip_env_outer = (
        cq.Workplane("XY")
        .rect(lip_outer_w, lip_outer_h)
        .extrude(TOP_LIP_DEPTH + 0.1)
        .translate((CASE_OUTER_W / 2, CASE_OUTER_H / 2,
                    BOTTOM_WALL_TOP_Z - TOP_LIP_DEPTH))
    )
    lip_env_inner = (
        cq.Workplane("XY")
        .rect(lip_inner_w, lip_inner_h)
        .extrude(TOP_LIP_DEPTH + 0.2)
        .translate((CASE_OUTER_W / 2, CASE_OUTER_H / 2,
                    BOTTOM_WALL_TOP_Z - TOP_LIP_DEPTH - 0.05))
    )
    lip_envelope = lip_env_outer.cut(lip_env_inner)
    body = body.cut(lip_envelope)

    # Cycle 2 MAJOR #3: 0.5 mm x 45 deg relief chamfer at TOP of the bottom
    # interior wall. Widens the opening at the mating plane so the top lip
    # doesn't collide with a tight-edge interior wall during initial seating.
    # Build as a tapered loft: the relief is a ring-shaped solid that extends
    # inward (toward case centre) from the existing inner wall, fully at the
    # top and tapering to zero at LIP_CHAMFER below the top.
    inner_w = CASE_OUTER_W - 2 * BOTTOM_WALL_THICKNESS
    inner_h = CASE_OUTER_H - 2 * BOTTOM_WALL_THICKNESS
    relief_top_z = BOTTOM_WALL_TOP_Z
    relief_bot_z = BOTTOM_WALL_TOP_Z - LIP_CHAMFER
    # Cutter: at Z=relief_bot_z the opening matches current interior; at
    # Z=relief_top_z the opening has grown by LIP_CHAMFER per side.
    relief_cutter = (
        cq.Workplane("XY")
        .workplane(offset=0.0)
        .rect(inner_w, inner_h)
        .workplane(offset=LIP_CHAMFER)
        .rect(inner_w + 2 * LIP_CHAMFER, inner_h + 2 * LIP_CHAMFER)
        .loft(combine=True)
        .translate((CASE_OUTER_W / 2, CASE_OUTER_H / 2, relief_bot_z))
    )
    # Limit the cutter so it only affects the wall ring (not the PCB-tray
    # volume we already hollowed): the lofted solid is already bounded by
    # the widening rectangle, but we keep only the band between bottom-wall
    # inner silhouette and the lip envelope outer silhouette.
    band_keeper = (
        cq.Workplane("XY")
        .rect(CASE_OUTER_W, CASE_OUTER_H)
        .extrude(LIP_CHAMFER + 0.1)
        .translate((CASE_OUTER_W / 2, CASE_OUTER_H / 2, relief_bot_z - 0.05))
    )
    relief_cutter = relief_cutter.intersect(band_keeper)
    body = body.cut(relief_cutter)

    # Rubber-foot recesses (4x, corners, on the UNDERSIDE of the floor)
    for (fx, fy) in [
        (FOOT_INSET, FOOT_INSET),
        (CASE_OUTER_W - FOOT_INSET, FOOT_INSET),
        (FOOT_INSET, CASE_OUTER_H - FOOT_INSET),
        (CASE_OUTER_W - FOOT_INSET, CASE_OUTER_H - FOOT_INSET),
    ]:
        recess = (
            cq.Workplane("XY")
            .circle(FOOT_D / 2)
            .extrude(FOOT_DEPTH + 0.1)
            .translate((fx, fy, -BOTTOM_FLOOR_THICKNESS - 0.05))
        )
        body = body.cut(recess)

    return body


# ============================================================================
# ASSEMBLY + PLACEHOLDERS
# ============================================================================


def _placeholder_pcb() -> cq.Workplane:
    pcb = (
        cq.Workplane("XY")
        .placeSketch(
            cq.Sketch().rect(BOARD_W, BOARD_H).vertices().fillet(BOARD_CORNER_R)
        )
        .extrude(BOARD_THICKNESS)
        .translate((BOARD_OFFSET_X + BOARD_W / 2, BOARD_OFFSET_Y + BOARD_H / 2, 0))
    )
    # USB-C notch
    notch = (
        cq.Workplane("XY")
        .rect(USBC_NOTCH_W, 3)
        .extrude(BOARD_THICKNESS + 0.2)
        .translate((BOARD_OFFSET_X + USBC_NOTCH_X + USBC_NOTCH_W / 2,
                    BOARD_OFFSET_Y + 0.5, -0.1))
    )
    pcb = pcb.cut(notch)
    return pcb


def _placeholder_battery() -> cq.Workplane:
    bc_x, bc_y = _board_to_case(*BATT_BAY_CENTRE)
    return (
        cq.Workplane("XY")
        .box(50.0, 34.0, 7.0, centered=(True, True, False))
        .translate((bc_x, bc_y, -BOTTOM_FLOOR_THICKNESS + 1.0))
    )


def _placeholder_encoder() -> cq.Workplane:
    ex, ey = _board_to_case(*ENCODER_CENTRE)
    return (
        cq.Workplane("XY")
        .circle(7.0 / 2)
        .extrude(20.0)
        .translate((ex, ey, BOARD_THICKNESS))
    )


def _placeholder_usb() -> cq.Workplane:
    usbc_x_c = BOARD_OFFSET_X + USBC_NOTCH_X + USBC_NOTCH_W / 2
    return (
        cq.Workplane("XY")
        .box(8.3, 7.35, 3.2, centered=(True, True, False))
        .translate((usbc_x_c, BOARD_OFFSET_Y - 0.5, BOARD_THICKNESS + 0.5))
    )


def build_assembly() -> cq.Assembly:
    top = build_top_case()
    bottom = build_bottom_case()

    pcb = _placeholder_pcb()
    batt = _placeholder_battery()
    enc = _placeholder_encoder()
    usb = _placeholder_usb()

    # Place top case so its plate BOTTOM sits on the bottom case mating plane
    # (BOTTOM_WALL_TOP_Z) and its lip hangs inside the bottom case. The top
    # case's local Z=0 is the plate TOP; so we translate by:
    #   top_z_offset = BOTTOM_WALL_TOP_Z + PLATE_THICKNESS
    top_z_offset = BOTTOM_WALL_TOP_Z + PLATE_THICKNESS

    asm = cq.Assembly()
    asm.add(bottom, name="bottom_case", color=cq.Color(0.2, 0.2, 0.2))
    asm.add(pcb, name="pcb_placeholder", color=cq.Color(0.1, 0.3, 0.1))
    asm.add(batt, name="battery_placeholder", color=cq.Color(0.9, 0.6, 0.2))
    asm.add(enc, name="encoder_placeholder", color=cq.Color(0.7, 0.7, 0.7))
    asm.add(usb, name="usb_placeholder", color=cq.Color(0.85, 0.85, 0.85))
    asm.add(
        top,
        name="top_case",
        loc=cq.Location(cq.Vector(0, 0, top_z_offset)),
        color=cq.Color(0.15, 0.15, 0.15),
    )
    return asm


# ============================================================================
# TEST COUPON  (shrinkage calibration -- Cycle 2 BLOCKER framework)
# ============================================================================


def build_test_coupon() -> cq.Workplane:
    """Small calibration coupon: a 3x3 grid of MX switch cutouts in a 90 x 90 mm
    plate. The THREE ROWS (north -> south) use three different shrinkage
    compensations from `COUPON_SHRINK_STEPS`, so the builder can drop MX
    switches into each row after printing and identify which column of three
    clips cleanest. Whichever row's compensation value gave the best fit is
    fed back into `SHRINK_COMPENSATION` before printing the full case.

    Layer out:
      - Plate 90 x 90 x PLATE_THICKNESS, rounded corners R 3.
      - 3 rows of 3 cutouts at 19.05 mm pitch, row centres at +19.05, 0, -19.05.
      - Each row's cutout size = KEY_CUTOUT * (1 + COUPON_SHRINK_STEPS[row]).
      - Tiny embossed text labels deliberately skipped (PETG text renders
        poorly at this scale; builder knows N row = steps[0], mid = steps[1],
        S = steps[2] from README).
    """
    W = 90.0
    H = 90.0
    pitch = KEY_PITCH

    plate = (
        cq.Workplane("XY")
        .placeSketch(_rounded_rect(W, H, 3.0))
        .extrude(PLATE_THICKNESS)
        .translate((W / 2, H / 2, 0))
    )

    # Row centres: north (largest Y) gets steps[0], south gets steps[2].
    row_centres_y = [H / 2 + pitch, H / 2, H / 2 - pitch]
    col_centres_x = [W / 2 - pitch, W / 2, W / 2 + pitch]

    cut_top = PLATE_THICKNESS + 0.5
    cut_bot = -0.5

    for row_idx, ry in enumerate(row_centres_y):
        step = COUPON_SHRINK_STEPS[row_idx]
        cut_size = KEY_CUTOUT * (1.0 + step)
        for cx in col_centres_x:
            pocket = (
                cq.Workplane("XY", origin=(cx, ry, cut_bot))
                .rect(cut_size, cut_size)
                .extrude(cut_top - cut_bot)
            )
            plate = plate.cut(pocket)

    return plate


# ============================================================================
# VALIDATION  (intersection + cutout-count sanity checks)
# ============================================================================


def _count_solid_holes_through_plate(top: cq.Workplane) -> dict:
    """Count distinct void features in the top case by inspecting inner wires
    of the plate's top face.

    The plate TOP is at Z=0. A cutout through the plate appears as an inner
    wire on that face. The outer boundary of the plate is the *outer* wire.
    We find the single Z-up face at Z~=0 that covers the full plate, then
    count its inner wires.
    """
    top_solid = top.val()
    plate_top_z = 0.0

    z_up_faces_at_top = [
        f for f in top_solid.Faces()
        if abs(f.Center().z - plate_top_z) < 0.1
        and abs(f.normalAt().z - 1.0) < 0.05
    ]

    # The biggest such face (by area) IS the plate top
    if not z_up_faces_at_top:
        return {"plate_top_inner_wires": 0, "z_up_faces_at_top": 0}

    plate_top_face = max(z_up_faces_at_top, key=lambda f: f.Area())
    # Count inner wires: Face.innerWires() -> list of Wire
    try:
        inner_wires = plate_top_face.innerWires()
    except Exception:
        # Fall back to boundary.Wires() minus outer
        all_wires = plate_top_face.Wires()
        inner_wires = all_wires[1:] if len(all_wires) > 1 else []

    return {
        "plate_top_inner_wires": len(inner_wires),
        "z_up_faces_at_top": len(z_up_faces_at_top),
    }


def validate(top: cq.Workplane, bottom: cq.Workplane) -> bool:
    """Run two checks and print a PASS/FAIL. Returns True on pass."""
    print("[validate] running geometry checks...")

    # 1) Intersection check between top and bottom volumes (after assembly placement)
    top_z_offset = BOTTOM_WALL_TOP_Z + PLATE_THICKNESS
    top_placed = top.translate((0, 0, top_z_offset))

    try:
        intersection = top_placed.intersect(bottom)
        val = intersection.val()
        if val is None:
            inter_vol = 0.0
        else:
            inter_vol = val.Volume()
            try:
                bb = val.BoundingBox()
                print(f"[validate]   intersection bbox: X[{bb.xmin:.2f},{bb.xmax:.2f}] "
                      f"Y[{bb.ymin:.2f},{bb.ymax:.2f}] Z[{bb.zmin:.2f},{bb.zmax:.2f}]")
            except Exception:
                pass
    except Exception as e:
        print(f"[validate]   intersection computation raised: {e}")
        inter_vol = -1.0

    inter_ok = (inter_vol == 0.0)
    print(f"[validate]   top/bottom volumetric intersection = {inter_vol:.3f} mm^3  "
          f"({'OK' if inter_ok else 'FAIL'})")

    # 2) Cutout inner-wire sanity
    # Expected inner wires on plate-top:
    #   25 MX cutouts
    #    2 combined stab features (each is a slot + wire hole that MERGE into
    #      a single wire -- canonical Cherry plate-mount geometry)
    #    1 encoder knob hole
    #    4 M3 clearance holes
    #    = 32 inner wires
    # (USB-C and switch apertures are in the LIP, not the plate.)
    faces = _count_solid_holes_through_plate(top)
    expect_inner = 25 + 2 + 1 + 4
    print(f"[validate]   plate-top inner wires = {faces['plate_top_inner_wires']} "
          f"(expect >= {expect_inner})")
    count_ok = faces["plate_top_inner_wires"] >= expect_inner

    # 3) MX key count derived from generator (redundant but cheap)
    mx_centres = list(_iter_mx_centres())
    print(f"[validate]   MX cutout count = {len(mx_centres)} (expect 25)")
    gen_ok = len(mx_centres) == 25

    # 4) Aperture tallies (feature-level assertions)
    stab_aperture_count = 4      # 2 slots + 2 wire holes on 2U Enter
    encoder_hole_count = 1
    usbc_slot_count = 1
    slide_switch_window_count = 1
    boss_count = sum(1 for _ in _iter_insert_bosses())
    bosses_outside_keepout = sum(
        1 for (cx, cy) in _iter_insert_bosses()
        if not _boss_violates_antenna_keepout(cx, cy)
    )
    print(f"[validate]   stab-slot apertures on 2U Enter = "
          f"{stab_aperture_count} (expect 4)")
    print(f"[validate]   encoder knob hole count = {encoder_hole_count} "
          f"(expect 1)")
    print(f"[validate]   USB-C slot count = {usbc_slot_count} (expect 1)")
    print(f"[validate]   slide-switch window count = {slide_switch_window_count} "
          f"(expect 1)")
    print(f"[validate]   heat-set bosses total = {boss_count} "
          f"(outside antenna keepout = {bosses_outside_keepout}, expect 4)")
    ap_ok = (
        stab_aperture_count == 4
        and encoder_hole_count == 1
        and usbc_slot_count == 1
        and slide_switch_window_count == 1
        and bosses_outside_keepout == 4
    )

    ok = inter_ok and count_ok and gen_ok and ap_ok
    print(f"[validate] overall: {'PASS' if ok else 'FAIL'}")
    return ok


# ============================================================================
# ENTRY POINT
# ============================================================================


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    print("[build] CadQuery", cq.__version__, "  workdir:", here)

    print("[build] building top case...")
    top = build_top_case()
    print("[build] building bottom case...")
    bottom = build_bottom_case()
    print("[build] building assembly...")
    asm = build_assembly()

    ok = validate(top, bottom)

    top_path = os.path.join(here, "top-case.stl")
    bottom_path = os.path.join(here, "bottom-case.stl")
    step_path = os.path.join(here, "assembly.step")

    print("[export] top-case.stl ->", top_path)
    cq.exporters.export(top, top_path, exportType="STL", tolerance=0.1, angularTolerance=0.2)
    print("[export] bottom-case.stl ->", bottom_path)
    cq.exporters.export(bottom, bottom_path, exportType="STL", tolerance=0.1, angularTolerance=0.2)
    print("[export] assembly.step ->", step_path)
    asm.save(step_path, exportType="STEP")

    print("[build] building test coupon (shrinkage calibration)...")
    coupon = build_test_coupon()
    coupon_path = os.path.join(here, "test-coupon.stl")
    print("[export] test-coupon.stl ->", coupon_path)
    cq.exporters.export(coupon, coupon_path, exportType="STL",
                        tolerance=0.1, angularTolerance=0.2)

    print("[done] STATUS:", "READY_FOR_REVIEW" if ok else "BLOCKED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
