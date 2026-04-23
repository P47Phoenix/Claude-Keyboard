# Claude Code Pad — Case parameters

All parameters live at the top of `claude-code-pad.py`. Tweak and re-run
to regenerate the STL / STEP outputs. Dimensions in millimetres.

## Shrinkage compensation (Cycle 2)

| Parameter             | Default                | Purpose                                                              |
| --------------------- | ---------------------- | -------------------------------------------------------------------- |
| `SHRINK_COMPENSATION` | 0.005                  | Factor by which every INNER cutout is upscaled so the cooled part lands on nominal. 0.5 % is a K2-Plus / PETG baseline — **calibrate per-printer / per-filament**. |
| `COUPON_SHRINK_STEPS` | `[0.003, 0.005, 0.007]` | Three row-wise shrink values baked into `test-coupon.stl` so a single print reveals which value clips MX switches cleanly. |

The compensation is applied via `_shrink(nominal)` to: MX cutouts, 2U
stab slots + wire holes, the encoder knob hole, M3 clearance holes in
the plate, the USB-C slot, the slide-switch window, and the heat-set
insert pilot holes. It is **not** applied to outer shells or wall
thicknesses (outer walls shrink inward — scaling the shell up would
make the case oversized). See `README.md` §Print calibration for the
coupon-driven calibration procedure.

## Board constants (read from PCB Edge.Cuts, aux origin = 100, 100)

| Parameter          | Default | Purpose                                                       |
| ------------------ | ------- | ------------------------------------------------------------- |
| `BOARD_W`          | 120.0   | PCB east-west extent.                                         |
| `BOARD_H`          | 132.0   | PCB north-south extent.                                       |
| `BOARD_THICKNESS`  | 1.6     | FR4 thickness. Drives placeholder height and assembly Z.      |
| `BOARD_CORNER_R`   | 3.0     | PCB corner fillet radius.                                     |
| `USBC_NOTCH_X`     | 54.0    | West edge of the USB-C notch in the north PCB edge (local X). |
| `USBC_NOTCH_W`     | 12.0    | Width of the USB-C notch.                                     |

## Key grid (5 × 5, MX hotswap + 2U Enter at row 4 col 4)

| Parameter              | Default                                  | Purpose                                           |
| ---------------------- | ---------------------------------------- | ------------------------------------------------- |
| `KEY_PITCH`            | 19.05                                    | Standard 1U MX pitch.                             |
| `KEY_CUTOUT`           | 14.0                                     | MX switch plate cutout nominal (before shrinkage). |
| `COL_X`                | `[19.4, 38.45, 57.5, 76.55, 95.6]`       | Column centres (board-local X).                   |
| `ROW_Y`                | `[39.525, 58.575, 77.625, 96.675, 115.725]` | Row centres.                                   |
| `ENTER_KEY_CENTRE`     | `(105.125, 115.725)`                     | 2U Enter centre (col 4 + 0.5U east offset).        |
| `STAB_OFFSET`          | 11.9                                     | Cherry 2U stab slot offset (c-to-c, E or W of key). |
| `STAB_SLOT_W`          | 3.97                                     | Stab slot width (E-W).                            |
| `STAB_SLOT_H`          | 6.65                                     | Stab slot height (N-S).                           |
| `STAB_WIRE_HOLE_D`     | 3.05                                     | Wire relief hole diameter.                        |
| `STAB_WIRE_OFFSET_N`   | 2.3                                      | Wire hole offset N of key centre.                 |

## Peripheral feature positions (board-local coords)

| Parameter              | Default           | Purpose                                                    |
| ---------------------- | ----------------- | ---------------------------------------------------------- |
| `ENCODER_CENTRE`       | `(108.0, 19.0)`   | EC11 rotary-encoder centre (PCB footprint).                |
| `ENCODER_KNOB_D`       | 10.0              | Knob access hole Ø in top plate.                           |
| `XIAO_CENTRE`          | `(60.0, 19.0)`    | U1 centre (XIAO module).                                   |
| `SWITCH_CENTRE`        | `(33.0, 19.0)`    | SPDT slide switch (SW_PWR1) centre.                        |
| `JST_CENTRE`           | `(8.0, 19.0)`     | J_BAT1 JST-PH centre (cable exits -X).                     |
| `NTC_CENTRE`           | `(10.0, 24.0)`    | TH1 NTC thermistor centre (needs thermal window).          |
| `SWITCH_WINDOW_W`      | 8.0               | North-wall slide-switch access window width.               |
| `SWITCH_WINDOW_H`      | 4.0               | Same, height.                                              |
| `USBC_SLOT_W`          | 14.0              | North-wall USB-C plug-body clearance width.                |
| `USBC_SLOT_H`          | 10.0              | Same, height (clears host-side plug boot).                 |

## Mounting holes (board-local)

| Parameter     | Default                                                       |
| ------------- | ------------------------------------------------------------- |
| `MOUNT_HOLES` | `[(3.5, 27), (116.5, 27), (5.0, 128), (115.0, 128)]` — matches PCB H1..H4. |

## Antenna keepout (XIAO nRF52840)

| Parameter                    | Default         | Purpose                                                                  |
| ---------------------------- | --------------- | ------------------------------------------------------------------------ |
| `ANTENNA_KEEPOUT_CENTRE`     | `(60.0, 19.0)`  | Keepout patch centre (board-local).                                      |
| `ANTENNA_KEEPOUT_W`          | 25.0            | Keepout E-W extent.                                                      |
| `ANTENNA_KEEPOUT_H`          | 10.3            | Keepout N-S extent.                                                      |
| `ANTENNA_KEEPOUT_CLEARANCE`  | 5.0             | No metal / heat-set inserts within this ring around the keepout rect.    |

Bosses whose centres fall inside `keepout + clearance` are printed with a
2.8 mm pilot hole for direct self-tap into PETG (no metal insert).

With the current PCB, the keepout envelope (incl. 5 mm clearance) spans
case-frame X = 42.5..77.5, Y = 8.85..29.15. The 4 mounting bosses sit at
case (5.90, 29.40), (118.90, 29.40), (7.40, 130.40), (117.40, 130.40) —
**all four are outside the envelope in X**, so all four use heat-set
inserts. No boss demotion is needed at this PCB revision. If ECE-1 moves
H1 or H2 inward in a future revision, `build_bottom_case()` will
auto-demote them to self-tap.

## Battery bay (Adafruit #1578 — 500 mAh LiPo, 50 × 34 × 7 mm)

| Parameter            | Default          | Purpose                                                 |
| -------------------- | ---------------- | ------------------------------------------------------- |
| `BATT_BAY_W`         | 54.0             | Cell + 2 mm clearance per side (E-W).                   |
| `BATT_BAY_H`         | 38.0             | Same, N-S.                                              |
| `BATT_BAY_DEPTH`     | 9.0              | Cell + 2 mm vertical clearance.                         |
| `BATT_BAY_CENTRE`    | `(30.0, 75.0)`   | Bay centre in board-local frame (inboard of JST side).  |

## Safety features

| Parameter          | Default        | Purpose                                                                  |
| ------------------ | -------------- | ------------------------------------------------------------------------ |
| `VENT_SLOT_W`      | 10.0           | Floor vent slot width.                                                   |
| `VENT_SLOT_H`      | 3.0            | Floor vent slot height.                                                  |
| `VENT_SLOTS`       | 2 × `(X, Y)`   | Positions of thermal egress slots in the battery-bay floor.              |
| `DIVIDER_SLOT_T`   | 1.8            | Groove width for the 1.6 mm FR-4 divider (slide fit).                    |
| `DIVIDER_HEIGHT`   | = `BATT_BAY_DEPTH` | Divider spans full bay depth.                                        |
| `JST_EXIT_W`       | 2.5            | Width of the JST-PH cable pinch-slot in the divider.                     |
| `JST_EXIT_H`       | 4.0            | Height of same.                                                          |

Strain-relief post: 2 mm Ø cylinder inside the bay, 2.5 mm east and
2.0 mm south of the cable exit — the JST-PH cable wraps once around it so
a tug doesn't transmit force to the PCB JST solder joints.

## Wall / plate / mating geometry

| Parameter                  | Default | Purpose                                                                           |
| -------------------------- | ------- | --------------------------------------------------------------------------------- |
| `PLATE_THICKNESS`          | 1.5     | MX switch spec (required for clip engagement).                                    |
| `TOP_WALL_THICKNESS`       | 2.0     | Top-case sidewall / lip thickness.                                                |
| `TOP_LIP_DEPTH`            | 2.5     | How far the top lip drops into the bottom case for alignment.                     |
| `TOP_LIP_CLEARANCE`        | 0.3     | Slip-fit gap between top lip outside and bottom wall inside.                      |
| `BOTTOM_WALL_THICKNESS`    | 2.0     | Bottom-case sidewall thickness.                                                   |
| `BOTTOM_FLOOR_THICKNESS`   | 2.0     | Bottom-case floor thickness.                                                      |
| `PCB_TRAY_STANDOFF`        | 3.0     | PCB bottom sits 3 mm above floor (room for B.Cu parts and LED apertures).        |
| `PLATE_TO_PCB_GAP`         | 5.0     | MX switch lower housing extends 5 mm below plate.                                 |
| `BOTTOM_INTERIOR_HEIGHT`   | derived | `max(standoff + pcb + plate_gap, batt_bay_depth + 1)` — whichever is taller.     |
| `BOTTOM_WALL_TOP_Z`        | derived | Mating-plane Z (top of bottom wall = bottom of top plate).                       |

## Heat-set insert bosses

| Parameter       | Default | Purpose                                                                 |
| --------------- | ------- | ----------------------------------------------------------------------- |
| `INSERT_DIA`    | 4.0     | Pilot Ø for M3 brass heat-set insert (CNC Kitchen IUB-M3-L4 nominal, pre-shrinkage). Shrink-compensated at cut time. |
| `INSERT_DEPTH`  | 4.2     | Pilot depth = IUB-M3-L4 length (4.0 mm) + 0.2 mm float so the insert never hard-stops on the pilot floor. |
| `BOSS_OD`       | 8.0     | Boss outer Ø (**2.0 mm** wall around insert, Cycle-2 uprating of the 1.45 mm Cycle-1 wall — PETG fractures at 1.45 mm with knurl-induced hoop stress). |
| `BOSS_HEIGHT`   | 6.7     | `INSERT_DEPTH + 2.5` — 2.5 mm solid PETG floor under the insert.        |

Matching screw: **M3 × 6 mm** (plate 1.5 + lip 2.5 landed = ~4 mm of
clamped material ahead of the insert, so M3 × 8 over-inserts and
bottoms in the insert's blind end).

## Case outer geometry + feet

| Parameter              | Default | Purpose                                                                   |
| ---------------------- | ------- | ------------------------------------------------------------------------- |
| `CASE_FIT_CLEARANCE`   | 0.4     | PCB-to-wall clearance per side.                                           |
| `CASE_OUTER_W`         | derived | `BOARD_W + 2*(BOTTOM_WALL + CASE_FIT_CLEARANCE)` ≈ 124.8 mm.              |
| `CASE_OUTER_H`         | derived | Same idiom for height ≈ 136.8 mm.                                         |
| `CASE_OUTER_R`         | 4.0     | Outer corner fillet.                                                      |
| `FOOT_D`               | 10.0    | Rubber-foot recess Ø on underside.                                        |
| `FOOT_DEPTH`           | 1.0     | Recess depth.                                                             |
| `FOOT_INSET`           | 8.0     | Recess centre inset from case corner.                                     |

## Tuning tips

- **MX switch too tight:** bump `KEY_CUTOUT` from 14.0 → 14.10.
- **Top lip won't seat:** bump `TOP_LIP_CLEARANCE` from 0.3 → 0.5.
- **Screw won't bite insert:** re-flow the insert (see `README.md` §
  post-processing) before changing `INSERT_DIA`.
- **Battery won't fit:** `BATT_BAY_W/H/DEPTH` are already +2 mm per axis;
  only bump if switching to a larger cell.
- **Antenna failing RF range:** confirm `ANTENNA_KEEPOUT_CENTRE` matches
  your PCB's XIAO position and `ANTENNA_KEEPOUT_CLEARANCE` ≥ 5.0 mm.
