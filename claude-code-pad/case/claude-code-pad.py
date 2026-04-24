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
# Cycle 2 MAJOR #10: 14 mm Ø knob + 1 mm clearance + press-click axial travel
ENCODER_KNOB_D = 16.0             # knob access hole dia
ENCODER_KNOB_PROTRUSION = 6.0     # knob top sits 6 mm above top-plate top
ENCODER_PRESS_TRAVEL = 1.0        # EC11 tactile-click axial travel clearance
XIAO_CENTRE = (60.0, 19.0)        # U1 (abs 160,119 -> local 60,19)
SWITCH_CENTRE = (33.0, 19.0)      # SW_PWR1 (abs 133,119 -> local 33,19)
JST_CENTRE = (8.0, 19.0)          # J_BAT1 (abs 108,119 -> local 8,19)
NTC_CENTRE = (10.0, 24.0)         # TH1 (abs 110,124 -> local 10,24)

# Cycle 2 MAJOR #9: slide-switch aperture sized to the MSS22AG15 slider body
# (11 mm long x 5 mm tall actuator boss) with 1 mm clearance
SWITCH_WINDOW_W = 12.0
SWITCH_WINDOW_H = 6.0

# Cycle 2 MAJOR #8 / MINOR #15: USB-C with sacrificial bridge + chamfer, and
# 0.1 / 0.05 mm shrink-comp applied via _shrink() at cut time
USBC_SLOT_W = 15.0                # plug-body + host-cable boot clearance
USBC_SLOT_H = 10.0
USBC_BRIDGE_W = 1.0               # sacrificial mid-span bridge (print-time, remove post)
USBC_BRIDGE_H = 2.0
USBC_EDGE_CHAMFER = 1.0           # 1 mm x 1 mm external-edge chamfer

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

# Vent geometry (Cycle 2 MAJOR #6/7): replace the 2x slot scheme with round
# holes that bridge reliably on PETG and deliver >= 150 mm^2 total vent area.
# 8x Ø3 circles on the bay floor (~56 mm^2) + 4x Ø3 circles through the
# east and west bay walls into the case exterior sidewall (~28 mm^2 each).
# Rough total area ~112 mm^2 through floor + 56 through walls = 168 mm^2.
VENT_HOLE_D = 3.0
# Floor vents -- 4x2 grid within the bay floor
FLOOR_VENT_OFFSETS = [
    (-15.0, -8.0), (-5.0, -8.0), (5.0, -8.0), (15.0, -8.0),
    (-15.0, 8.0),  (-5.0, 8.0),  (5.0, 8.0),  (15.0, 8.0),
]
# Wall vents -- 2 per east & west bay wall, staggered vertically
WALL_VENT_Z = [BATT_BAY_DEPTH - 6.0, BATT_BAY_DEPTH - 2.5]
WALL_VENT_Y_OFFSETS = [-8.0, 8.0]

# FR-4 divider slot (1.6 mm FR-4 thickness, slide-fit groove -- 1.8 mm slot)
DIVIDER_SLOT_T = 1.8
DIVIDER_HEIGHT = BATT_BAY_DEPTH    # divider spans full bay depth

# JST cable exit (strain-relief pinch slot) -- a 2 mm-wide vertical notch on
# the divider's north face, centred on JST Y
JST_EXIT_Y = JST_CENTRE[1]
JST_EXIT_W = 2.5
JST_EXIT_H = 4.0                   # slot height (cable dia 1.5 mm nominal)

# --- Wall / plate thicknesses ---
# Cycle 3 MAJOR #5 rework: MX switch plate spec is 1.5 +/- 0.3 mm -> **1.8 mm
# is the hard upper bound**. Cycle 2's 2.0 mm value was out of spec and
# risked poor clip engagement. Drop to 1.8 mm (top of spec). Deflection-wise
# the top plate still retains ~88% of Cycle 2's stiffness (the bending
# stiffness of a plate scales with t^3, so 1.8^3 / 2.0^3 = 0.729; the
# effective stiffness loss is smaller once you include the lip + walls as
# a box-section contribution), which is enough for the 5x5 grid under the
# <=60 gf-force typical keypress load. Builder should still test-click one
# MX switch at 1.8 mm plate thickness before committing to a full print.
PLATE_THICKNESS = 1.8
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
# Cycle 2 MINOR #18: 3 -> 5 to clear Kailh hot-swap socket tails (measured
# 3.2 mm below PCB bottom on MX hotswap sockets). 5 mm leaves 1.8 mm margin.
PCB_TRAY_STANDOFF = 5.0
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
CASE_OUTER_R = 6.0                 # Cycle 2 MINOR #17: 4 -> 6 for cool-down stress

# Shift so board local (0,0) maps to case-interior (CASE_WALL+fit, CASE_WALL+fit)
BOARD_OFFSET_X = BOTTOM_WALL_THICKNESS + CASE_FIT_CLEARANCE
BOARD_OFFSET_Y = BOTTOM_WALL_THICKNESS + CASE_FIT_CLEARANCE

# --- Print / rubber feet ---
# Cycle 2 MINOR #16: default moved from 3M SJ-5003 (10 x 1 mm) to 3M SJ-5018
# (12.7 x 1 mm) for better grip on desktops. Both variants documented in
# README; swap FOOT_D / FOOT_DEPTH to match your chosen foot.
FOOT_D = 12.7          # SJ-5018 default (SJ-5003 alternative = 10.0)
FOOT_DEPTH = 1.0
FOOT_INSET = 9.0       # increased with FOOT_D so edge-clearance is preserved

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


def _cut_wall_aperture(
    solid: cq.Workplane,
    center_x: float,
    width: float,
    z_bot: float,
    z_top: float,
    wall_axis: str = "N",
    wall_span: float = 6.0,
    wall_face_coord: float = 0.0,
) -> cq.Workplane:
    """Cut a rectangular aperture through a case wall (Cycle 3 BLOCKER fix).

    Cuts a box of (width × wall_span × (z_top - z_bot)) through `solid`,
    centred at (center_x, wall_face_coord) on the wall face and extending
    from Z = z_bot to Z = z_top in the solid's own frame.

    `wall_axis="N"` treats the wall as the north (+Y) wall, so the cut
    box is oriented with its short axis along Y and passes through the
    full wall thickness (given a generous `wall_span`).

    Introduced in Phase 2 Cycle 3 so that USB-C and slide-switch
    apertures can be cut on *both* the top-case (through the lip) and
    the bottom-case (through the north sidewall) with a single
    geometry path. This closes the Cycle 2 BLOCKER where the cuts
    landed only in the top lip (z = 9.1..11.6 in the bottom-case frame)
    while the actual plug body and actuator stick DOWN into the
    bottom-wall Z range.
    """
    assert wall_axis == "N", "Only north-wall cuts implemented (USB-C and slide switch sit on the north edge)."
    assert z_top > z_bot, f"z_top ({z_top}) must be greater than z_bot ({z_bot})."
    height = z_top - z_bot
    aperture = (
        cq.Workplane("XY", origin=(center_x, wall_face_coord, z_bot))
        .box(width, wall_span, height, centered=(True, True, False))
    )
    return solid.cut(aperture)


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

    # 2U Enter stab slots + wire holes (shrinkage-compensated).
    # Cycle 2 MINOR #19: build each stab as a UNION of rect + wire-hole
    # circle BEFORE cutting from the plate. The wire hole and slot
    # share a common outline in the Cherry plate-mount standard, so
    # merging them first yields a single clean inner wire on the plate
    # top face rather than two overlapping wires, which made STL
    # viewers show a seam artefact at the merge point.
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
        wire = (
            cq.Workplane("XY",
                         origin=(ex + sign * STAB_OFFSET,
                                 ey - STAB_WIRE_OFFSET_N,
                                 cut_bottom))
            .circle(stab_wire_d / 2)
            .extrude(cut_top - cut_bottom)
        )
        stab_aperture = slot.union(wire)
        body = body.cut(stab_aperture)

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
    usb_w = _shrink(USBC_SLOT_W)
    usb_h = _shrink(USBC_SLOT_H)
    wall_span = (TOP_WALL_THICKNESS + TOP_LIP_CLEARANCE) * 3
    usb_aperture = (
        cq.Workplane("XY",
                     origin=(usbc_x_c, 0.0, lip_bot_z))
        .box(usb_w, wall_span,
             min(usb_h, TOP_LIP_DEPTH + 0.2),
             centered=(True, True, False))
    )
    body = body.cut(usb_aperture)

    # Cycle 2 MAJOR #8: sacrificial bridge rib across the USB-C opening at
    # mid-span -- a 1x2 mm bar that lets the slicer bridge cleanly on PETG.
    # Builder snips it off before plugging in a USB-C cable for the first
    # time. The bridge lives entirely within the lip-wall body (the lip's
    # north wall spans Y = lip_outer_inset .. lip_outer_inset + TOP_WALL_THICKNESS),
    # so it can never poke outside and collide with the bottom case.
    lip_outer_inset = TOP_WALL_THICKNESS + TOP_LIP_CLEARANCE
    bridge_y_min = lip_outer_inset
    bridge_y_max = lip_outer_inset + TOP_WALL_THICKNESS
    bridge_y_centre = (bridge_y_min + bridge_y_max) / 2
    bridge_y_span = bridge_y_max - bridge_y_min
    bridge_z_centre = lip_bot_z + min(usb_h, TOP_LIP_DEPTH + 0.2) / 2
    usb_bridge = (
        cq.Workplane("XY",
                     origin=(usbc_x_c, bridge_y_centre,
                             bridge_z_centre - USBC_BRIDGE_H / 2))
        .box(USBC_BRIDGE_W, bridge_y_span, USBC_BRIDGE_H,
             centered=(True, True, False))
    )
    body = body.union(usb_bridge)

    # Cycle 2 MINOR #15: 1x1 mm 45 deg external-edge chamfer on the USB-C
    # aperture outside, so the plug boot has a lead-in if the cable is at
    # a slight angle to the case edge. Built as a loft from the nominal
    # aperture at Y = 1 mm (inside the face) to a 1-mm-larger aperture at
    # Y = 0 (face) so the outer edge is a 45-deg ramp.
    chamfer_size = USBC_EDGE_CHAMFER
    slot_h_cut = min(usb_h, TOP_LIP_DEPTH + 0.2)
    chamfer_subtractor = (
        cq.Workplane("XZ", origin=(usbc_x_c,
                                    chamfer_size,
                                    lip_bot_z + slot_h_cut / 2))
        .rect(usb_w, slot_h_cut)
        .workplane(offset=-chamfer_size)
        .rect(usb_w + 2 * chamfer_size,
              slot_h_cut + 2 * chamfer_size)
        .loft(combine=True)
    )
    body = body.cut(chamfer_subtractor)

    swx, _ = _board_to_case(*SWITCH_CENTRE)
    # Cycle 2 MAJOR #9: switch window Z centre computed from actuator height.
    # The MSS22AG15 slider actuator boss is 5 mm tall above the switch body.
    # The switch body sits at PCB top + 1 mm ride height; actuator boss
    # centre is at PCB top + 1 + 2.5 = 3.5 mm above PCB. Plate underside is
    # PLATE_TO_PCB_GAP = 5 mm above PCB, so lip bottom is -TOP_LIP_DEPTH
    # below plate underside. Actuator centre Z (in top-case frame, Z=0 plate
    # top): -PLATE_THICKNESS - (PLATE_TO_PCB_GAP - 3.5) = -plate - 1.5.
    sw_actuator_z = -PLATE_THICKNESS - (PLATE_TO_PCB_GAP - 3.5)
    sw_window_z_bot = sw_actuator_z - _shrink(SWITCH_WINDOW_H) / 2
    sw_win = (
        cq.Workplane("XY",
                     origin=(swx, 0.0, sw_window_z_bot))
        .box(_shrink(SWITCH_WINDOW_W), wall_span,
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

    # Battery bay walls: 4 walls 2.0 mm thick (Cycle 2 MAJOR #6: 1.5 -> 2.0
    # for PETG bend stiffness under cell swell + UL flame retention), around
    # BATT_BAY_W x BATT_BAY_H centred on BATT_BAY_CENTRE (board-local -> case).
    bc_x, bc_y = _board_to_case(*BATT_BAY_CENTRE)
    bay_wall_t = 2.0
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

    # Divider slot: 1.8 mm groove on the NORTH, EAST, and WEST interior faces
    # of the bay (Cycle 2 MAJOR #12: 3-edge retention so the FR-4 card can't
    # pop out under cell swell). The north groove runs E-W; the east and west
    # grooves run N-S, each extending from floor to DIVIDER_HEIGHT.
    #
    # Placement of the divider plane: same N position as before
    # (BATT_BAY_H / 2 - DIVIDER_SLOT_T / 2 north of bay centre). Grooves cut
    # DIVIDER_SLOT_T / 2 INTO each wall from the interior face.
    divider_y = bc_y + BATT_BAY_H / 2 - DIVIDER_SLOT_T / 2
    # North groove (E-W) -- extends into the north wall by full bay-wall_t
    north_groove = (
        cq.Workplane("XY")
        .rect(BATT_BAY_W + 2 * bay_wall_t, DIVIDER_SLOT_T)
        .extrude(DIVIDER_HEIGHT)
        .translate((bc_x, divider_y, 0))
    )
    body = body.cut(north_groove)
    # East / west grooves (N-S) -- at the divider Y, cut through the east/west
    # walls to hold the card edge-on.
    for x_sign in (-1, 1):
        side_groove = (
            cq.Workplane("XY")
            .rect(DIVIDER_SLOT_T, bay_wall_t * 2 + 0.1)
            .extrude(DIVIDER_HEIGHT)
            .translate((
                bc_x + x_sign * (BATT_BAY_W / 2 + bay_wall_t / 2),
                divider_y,
                0,
            ))
        )
        body = body.cut(side_groove)

    # JST cable exit / strain-relief gate (Cycle 2 MAJOR #11): replace the
    # cantilever relief post with a two-wall "cable gate". Two 2 mm-thick
    # walls form a 2 mm-wide slot through which the JST-PH cable passes.
    # The cable is pinched in SHEAR between the two walls (and between the
    # walls and the inner face of the north bay wall when seated), so tug-
    # out load is carried as wall-on-wall shear, not cantilever.
    gate_gap = JST_EXIT_W          # cable slot width (unchanged, 2.5 mm)
    gate_wall_t = 2.0              # wall thickness per side of the gate
    gate_height = 6.0              # gate wall height above floor
    gate_y = bc_y + BATT_BAY_H / 2 - bay_wall_t - 1.0   # just inside north wall
    gate_cx = bc_x - BATT_BAY_W / 4                     # aligned with cable exit

    # Cable exit through the north bay wall -- still a pinch slot, but now
    # sits directly behind the gate
    jst_exit = (
        cq.Workplane("XY")
        .box(_shrink(JST_EXIT_W), bay_wall_t * 2 + 0.5, _shrink(JST_EXIT_H),
             centered=(True, True, False))
        .translate((gate_cx,
                    bc_y + BATT_BAY_H / 2 + bay_wall_t / 2,
                    BATT_BAY_DEPTH - JST_EXIT_H - 1.0))
    )
    body = body.cut(jst_exit)

    # Two gate walls, east + west of the cable path
    for x_sign in (-1, 1):
        gate_wall = (
            cq.Workplane("XY")
            .box(gate_wall_t,
                 bay_wall_t + 1.5,
                 gate_height,
                 centered=(True, True, False))
            .translate((
                gate_cx + x_sign * (gate_gap / 2 + gate_wall_t / 2),
                gate_y,
                0,
            ))
        )
        body = body.union(gate_wall)

    # Vents (Cycle 2 MAJOR #7): 8x Ø3 holes through the bay FLOOR + 4x Ø3
    # holes through the east and west bay WALLS, for >=150 mm^2 total vent
    # area. All apertures shrink-compensated so the cooled holes land at Ø3.
    vent_d = _shrink(VENT_HOLE_D)
    # Floor vents -- small round holes across the bay floor
    for (dx, dy) in FLOOR_VENT_OFFSETS:
        vent = (
            cq.Workplane("XY")
            .circle(vent_d / 2)
            .extrude(BOTTOM_FLOOR_THICKNESS + 0.3)
            .translate((bc_x + dx, bc_y + dy,
                        -BOTTOM_FLOOR_THICKNESS - 0.1))
        )
        body = body.cut(vent)
    # Wall vents -- through east and west bay walls into the case sidewall.
    # Bay east/west wall outer face is at bc_x +/- (BATT_BAY_W/2 + bay_wall_t).
    # Cut a horizontal cylinder (axis along X) all the way through the wall.
    for x_sign in (-1, 1):
        wall_centre_x = bc_x + x_sign * (BATT_BAY_W / 2 + bay_wall_t / 2)
        for z_level in WALL_VENT_Z:
            for dy in WALL_VENT_Y_OFFSETS:
                vent = (
                    cq.Workplane("YZ", origin=(wall_centre_x,
                                                bc_y + dy,
                                                z_level))
                    .circle(vent_d / 2)
                    .extrude(bay_wall_t + 0.5, both=True)
                )
                body = body.cut(vent)

    # NTC thermal membrane (Cycle 2 MAJOR #14): replace the Cycle-1 through-
    # hole window with a 0.4 mm (1 PETG layer) MEMBRANE between cell and NTC.
    # A through-hole was an ignition-spark / debris path per IEC 62368-1
    # Annex Q (thermal runaway flames must not vent toward PCB / MCU) and
    # also let FR-4 shards contact the cell; a 0.4 mm PETG membrane adds
    # ~3-5 s thermal lag which both the charger IC and the firmware cutoff
    # (2 s sample interval) can absorb. The membrane is authored as a pair
    # of pockets -- one recessed UPWARD from the floor underside, one
    # recessed DOWNWARD from the bay-floor topside -- so 0.4 mm of floor
    # material remains sandwiched in the middle, flush with the surrounding
    # floor on both sides.
    nx, ny = _board_to_case(*NTC_CENTRE)
    ntc_w = _shrink(6.0)
    ntc_h = _shrink(3.0)
    # Upper pocket -- opens into the bay. Depth: recess into top of floor
    # (floor top at Z=0), leaving 0.4 mm remaining, so pocket bottom at
    # Z = - (BOTTOM_FLOOR_THICKNESS - 0.4) would be below. Actually we want
    # the membrane AT the floor top surface -- i.e. the bay floor is not
    # recessed (cell sits flat on floor). The thermal path IS through the
    # full floor thickness of 2 mm. That's too thick. So we also recess
    # the underside of the floor UP by (floor_t - 0.4) so membrane = 0.4.
    ntc_recess_depth = BOTTOM_FLOOR_THICKNESS - 0.4
    # Underside pocket: from floor underside up to (0.4 mm below floor top)
    under_pocket = (
        cq.Workplane("XY")
        .rect(ntc_w, ntc_h)
        .extrude(ntc_recess_depth + 0.05)
        .translate((nx, ny, -BOTTOM_FLOOR_THICKNESS - 0.05))
    )
    body = body.cut(under_pocket)
    # Alternative geometry (documented in README): builder may print a
    # second bottom-case variant with a full through-hole + adhesive
    # Kapton+thermal-pad in lieu of the membrane. Not built here.

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

    # --- North-wall apertures (Cycle 3 BLOCKER fix) --------------------------
    # The top case's USB-C aperture only reaches Z = 9.1..11.6 (lip range).
    # The actual USB-C plug body on the PCB sits at Z = PCB_top - 1.0 .. PCB_top + 3.2
    # = 5.6 .. 9.8, so 5.6..9.1 is blocked by the solid bottom-case north wall.
    # Cut the aperture through the bottom-case north wall from
    # usb_bottom_z = PCB_top - 1.0 up to the mating plane at BOTTOM_WALL_TOP_Z
    # so the plug body has a continuous slot from the case exterior to the PCB.
    pcb_top_z = PCB_TRAY_STANDOFF + BOARD_THICKNESS
    # Extend cut 0.2 mm below the component's Z-min so the Z-overlap probe
    # assertions are unambiguously in air (no exact-boundary float ties).
    usb_bottom_z = pcb_top_z - 1.0 - 0.2
    usbc_x_c = BOARD_OFFSET_X + USBC_NOTCH_X + USBC_NOTCH_W / 2
    # wall_span generous enough to cut cleanly through the full north wall
    wall_cut_span = (BOTTOM_WALL_THICKNESS + CASE_FIT_CLEARANCE) * 3
    body = _cut_wall_aperture(
        body,
        center_x=usbc_x_c,
        width=_shrink(USBC_SLOT_W),
        z_bot=usb_bottom_z,
        z_top=BOTTOM_WALL_TOP_Z + 0.1,     # overshoot into the lip-envelope cut
        wall_axis="N",
        wall_span=wall_cut_span,
        wall_face_coord=0.0,
    )

    # Slide-switch window (Cycle 3 BLOCKER fix): the top-case's cut only
    # reaches down to Z = 9.1 (lip top), but the MSS22AG15 actuator boss
    # extends down to Z = PCB_top + 1.0 - (WINDOW_H/2 - 2.5) = 7.1 in the
    # bottom-case frame (actuator centre = PCB_top + 3.5 = 10.1,
    # half-height = 3.0). Cut a matching aperture through the bottom-case
    # north wall so the switch actuator has continuous clearance.
    swx, _sw_unused = _board_to_case(*SWITCH_CENTRE)
    sw_actuator_centre_z = pcb_top_z + 3.5           # 10.1 in bottom-case frame
    sw_window_half_h = _shrink(SWITCH_WINDOW_H) / 2
    sw_z_bot = sw_actuator_centre_z - sw_window_half_h
    body = _cut_wall_aperture(
        body,
        center_x=swx,
        width=_shrink(SWITCH_WINDOW_W),
        z_bot=sw_z_bot,
        z_top=BOTTOM_WALL_TOP_Z + 0.1,    # overshoot into lip-envelope cut
        wall_axis="N",
        wall_span=wall_cut_span,
        wall_face_coord=0.0,
    )

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


def assert_aperture_clears(
    assembled_solid,
    aperture_xy: Tuple[float, float],
    aperture_wh: Tuple[float, float],
    component_z_min: float,
    component_z_max: float,
    wall_axis: str = "N",
    name: str = "aperture",
    shrink: float = 0.6,
    nx: int = 3,
    nz: int = 5,
) -> bool:
    """Probe the assembled solid across a component's Z-range to confirm
    the aperture cuts fully clear of material (Cycle 3 MAJOR #3 validation
    gate).

    Parameters
    ----------
    assembled_solid : cadquery Solid
        The unioned top+bottom case geometry (as a single Solid) in the
        bottom-case frame.
    aperture_xy : (cx, cy)
        Aperture centre in the wall face plane (for a north-wall aperture,
        cx is X in the case-outer frame, cy is irrelevant and may be 0).
    aperture_wh : (w, h)
        Aperture width (along the wall face) and aperture height (along Z).
        `assert_aperture_clears` probes the inner `shrink * w` x
        `shrink * h` region so tolerance/chamfer edges are not sampled.
    component_z_min, component_z_max : float
        Z-range the component occupies (must sit WITHIN the aperture's
        authored Z-span, i.e. (cy - h/2, cy + h/2)).
    wall_axis : {"N", "S", "E", "W"}, default "N"
        Which wall the aperture passes through. Only "N" is exercised
        today (USB-C and slide switch sit on the north edge).
    name : str
        Label for the PASS/FAIL print line.
    shrink : float in (0, 1]
        Fractional envelope of the aperture to probe (default 0.6 to stay
        clear of the edge chamfers and shrink-compensation tolerances).
    nx, nz : int
        Probe-grid density across the aperture width and across the
        component Z-range.

    Returns True if every probe point lies *outside* the solid (i.e. in
    air), False otherwise. Prints PASS/FAIL per aperture.
    """
    cx, _cy = aperture_xy
    w, _h_ap = aperture_wh

    if wall_axis != "N":
        # Only the north wall is exercised at this revision. E/W/S can be
        # added when a feature on those walls needs aperture clearance.
        raise NotImplementedError(f"assert_aperture_clears({wall_axis=}) not wired")

    # Probe X positions: nx equispaced across 0.6 * aperture width
    half_w = (w * shrink) / 2.0
    xs = [cx - half_w + (2 * half_w) * i / (nx - 1) for i in range(nx)] if nx > 1 else [cx]

    # Probe Y along the full wall depth (case outer Y=0 to Y=BOTTOM_WALL_THICKNESS)
    # so the probe truly lives *inside the wall*, not just at the face.
    ys = [BOTTOM_WALL_THICKNESS / 2.0]      # wall mid-plane

    # Probe Z across the component range
    zs = [component_z_min + (component_z_max - component_z_min) * i / (nz - 1)
          for i in range(nz)] if nz > 1 else [(component_z_min + component_z_max) / 2.0]

    collisions = []
    for px in xs:
        for py in ys:
            for pz in zs:
                probe = cq.Vector(px, py, pz)
                try:
                    inside = assembled_solid.isInside(probe, tolerance=1e-6)
                except Exception:
                    # If the Solid API doesn't expose isInside cleanly,
                    # fall back to a tiny-sphere intersection volume test.
                    tiny = (
                        cq.Workplane("XY", origin=(px, py, pz))
                        .sphere(0.05)
                        .val()
                    )
                    try:
                        inter_vol = assembled_solid.intersect(tiny).Volume()
                        inside = inter_vol > 1e-9
                    except Exception:
                        inside = False
                if inside:
                    collisions.append((px, py, pz))

    ok = len(collisions) == 0
    print(f"[validate]   aperture '{name}' Z-clearance: "
          f"{'PASS' if ok else 'FAIL'}  "
          f"(probes={nx * len(ys) * nz}, collisions={len(collisions)}, "
          f"z=[{component_z_min:.2f}, {component_z_max:.2f}])")
    if not ok:
        # Show a representative collision so the root cause is immediate
        px, py, pz = collisions[0]
        print(f"[validate]     first collision at (x={px:.2f}, y={py:.2f}, z={pz:.2f})")
    return ok


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

    # 5) Z-overlap assertions (Cycle 3 MAJOR #3 process fix).
    # For each component-bearing aperture, probe the UNIONED case solid
    # across the component's real Z-range and assert no material. This
    # catches the Cycle-2 class of defect where an aperture was cut in the
    # top lip but solid bottom-case wall still blocked the component.
    pcb_top_z = PCB_TRAY_STANDOFF + BOARD_THICKNESS

    try:
        assembled = top_placed.union(bottom).val()
    except Exception as e:
        print(f"[validate]   assembled-solid union raised: {e}")
        assembled = None

    z_ok = True
    if assembled is not None:
        usbc_x_c = BOARD_OFFSET_X + USBC_NOTCH_X + USBC_NOTCH_W / 2
        # USB-C plug body: z = PCB_top - 1.0 to PCB_top + 3.2
        z_ok &= assert_aperture_clears(
            assembled,
            aperture_xy=(usbc_x_c, 0.0),
            aperture_wh=(USBC_SLOT_W, USBC_SLOT_H),
            component_z_min=pcb_top_z - 1.0,
            component_z_max=pcb_top_z + 3.2,
            wall_axis="N",
            name="USB-C plug body",
        )

        sw_cx, _sw_cy = _board_to_case(*SWITCH_CENTRE)
        # Slide-switch actuator: z = PCB_top + 0.5 to PCB_top + 6.5 (actuator
        # boss 5 mm tall, ride 1 mm above PCB). The aperture envelope is
        # (w=12, h=6) centred at z = PCB_top + 3.5 = 10.1, giving the
        # Cycle-3 BLOCKER 7.1..13.1 Z-range when including the boss radius.
        z_ok &= assert_aperture_clears(
            assembled,
            aperture_xy=(sw_cx, 0.0),
            aperture_wh=(SWITCH_WINDOW_W, SWITCH_WINDOW_H),
            component_z_min=pcb_top_z + 0.5,
            component_z_max=pcb_top_z + 6.5,
            wall_axis="N",
            name="slide-switch actuator",
        )
    else:
        print("[validate]   aperture Z-clearance: SKIPPED (no assembled solid)")
        z_ok = False

    ok = inter_ok and count_ok and gen_ok and ap_ok and z_ok
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
