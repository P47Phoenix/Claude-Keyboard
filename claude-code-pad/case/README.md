# Claude Code Pad — Case (Phase 2 Cycle 1)

Parametric CadQuery source for the Claude Code Pad enclosure. Two parts:
top case (MX switch plate + skirt/lip) and bottom case (PCB tray + battery
bay + heat-set insert bosses).

All dimensions are in millimetres. Geometry is authored in a case-local
frame whose (0, 0, 0) corner maps to the PCB's KiCad aux origin at
(100, 100). PCB top face sits at Z = 0; case outer-frame Z = 0 is the top
surface of the bottom-case FLOOR, i.e. the interior of the bottom shell.

## Files

| File                  | Purpose                                                                                           |
| --------------------- | ------------------------------------------------------------------------------------------------- |
| `claude-code-pad.py`  | Parametric CadQuery source. Run directly to build all artefacts.                                  |
| `top-case.stl`        | Print-ready top plate (1.5 mm) + 2.5 mm slip-fit lip, with MX cutouts, 2U stab, USB-C, encoder.    |
| `bottom-case.stl`     | Print-ready bottom tray — 2 mm walls/floor, 4× M3 heat-set bosses, battery bay, vents, feet.       |
| `assembly.step`       | Full STEP assembly: top + bottom + placeholder PCB/battery/encoder/USB-C for Fusion 360 checking. |
| `test-coupon.stl`     | 90 × 90 mm shrinkage-calibration coupon — 3 × 3 MX cutouts at 3 different compensation values.    |
| `PARAMS.md`           | Table of all exposed CadQuery parameters with defaults and what they control.                     |

## Build

```bash
case/.venv/bin/python case/claude-code-pad.py
```

This executes `build_top_case()`, `build_bottom_case()`, and
`build_assembly()`, runs the validation gate (volumetric intersection +
plate-top inner-wire count + MX-centre count), exports the three outputs,
and prints `STATUS: READY_FOR_REVIEW` on success.

Typical run takes ≈ 30 s on a modern laptop.

## Print orientation (Creality K2 Plus, PETG)

### Top case

- **Orientation:** PLATE FACE DOWN on bed (Z- points UP in slicer).
- **Why:** Puts the MX-switch clip surface in free-air for the cleanest
  14.0 mm square tolerance — no support scars on the plate top where the
  keycap edges pass.
- **Layer height:** 0.16 mm (tighter fit on MX clips).
- **Infill:** 60 % gyroid. Plate is structural; any less and keypresses flex
  the skirt.
- **Walls:** 4 perimeters at 0.4 mm nozzle (wall shells 1.6 mm; allows 2.0 mm
  sidewall to still be solid perimeter).
- **Supports:** tree supports on the down-facing keycap pockets; none inside
  the USB-C aperture (bridge it). Turn supports OFF inside the MX cutouts —
  they're through features, no overhang.
- **Expected print time:** ≈ 5–6 h.
- **Expected filament:** ≈ 45 g.

### Bottom case

- **Orientation:** CAVITY UP (open side facing +Z in slicer).
- **Why:** Lets the battery-bay walls, boss tops, and strain-relief post all
  print upwards from the floor without support. The outer bottom surface is
  the build plate, so the rubber-foot recesses come out sharp and flat.
- **Layer height:** 0.2 mm.
- **Infill:** 30 % gyroid. Bottom shell doesn't take keypress load.
- **Walls:** 3 perimeters at 0.4 mm.
- **Supports:** OFF. All overhangs are ≤ 45°; the battery-bay divider slot
  and vent slots are bridgeable at 2 mm floor thickness.
- **Expected print time:** ≈ 7–8 h.
- **Expected filament:** ≈ 90 g.

### PETG shrinkage policy

Cycle 2 introduces a true compensation framework instead of the Cycle 1
"manually bump the nominal if switches are sloppy" hack.

`SHRINK_COMPENSATION` (default **0.005**) is applied via `_shrink()` to
every inner aperture: MX cutouts, 2U stab slots + wire holes, encoder
knob hole, M3 clearance holes, USB-C slot, slide-switch window, and the
heat-set insert pilot holes. The 0.005 (0.5 %) default is an empirical
K2 Plus / PETG baseline — **calibrate for your own printer and filament
before printing the full case.**

### Print calibration (test coupon)

`case/test-coupon.stl` is a small 90 × 90 × 1.5 mm plate with a 3 × 3
grid of MX-switch cutouts. The three **rows** each use a different
compensation from `COUPON_SHRINK_STEPS = [0.003, 0.005, 0.007]`:

- **North row (top of print)** — 0.3 % compensation (14.042 mm authored)
- **Middle row**              — 0.5 % compensation (14.070 mm authored) — **default**
- **South row (bottom)**      — 0.7 % compensation (14.098 mm authored)

Procedure:

1. Print `test-coupon.stl` flat on the bed with identical slicer settings
   to the real case (PETG, 0.16 mm layer height, 60 % infill, 235 °C
   hotend, 85 °C bed, brim on).
2. Drop an MX switch into each cell.
3. Identify the row whose switches clip with a firm click but slide in
   without forcing. Columns are identical within a row — you're judging
   rows, not columns.
4. If middle row is best: leave `SHRINK_COMPENSATION = 0.005`. If north:
   drop to 0.003. If south: raise to 0.007.
5. Re-run `case/.venv/bin/python case/claude-code-pad.py` to regenerate
   STLs with the calibrated value, then print the real case.

If none of the three rows is acceptable (e.g. all too loose or all too
tight), bracket with new `COUPON_SHRINK_STEPS` values and repeat — e.g.
`[0.008, 0.010, 0.012]` if the 0.7 % row was still sloppy.

## Post-processing

### Heat-set insert procedure (bottom case, 4× M3 brass inserts)

1. Chuck an M3 heat-set insert (CNC-Kitchen IUB-M3-L4 or equivalent, 4.1 mm
   pilot dia, L = 4.0 mm) onto a soldering iron tip rated for inserts.
2. Set iron to **240 °C**.
3. Seat the insert into each boss pilot (BOSS_OD 7 mm, pilot 4.1 mm,
   INSERT_DEPTH 5 mm). Press DOWN until the insert's flange is flush with
   the boss top. **Do not push past flush** — PETG flows and you'll bury the
   insert.
4. Withdraw the iron; let the insert cool for 30 s before disturbing.
5. Check thread by running an M3 screw in by hand — it should turn in
   smoothly with no cross-thread.

**Exception:** bosses within the antenna keepout envelope (5 mm around the
25 × 10.3 mm XIAO antenna patch) are printed as 2.8 mm pilot holes for
direct self-tap, **no metal insert** — metal within 5 mm of the nRF52840
antenna detunes the RF match. See `PARAMS.md` §Antenna keepout.

### FR-4 divider (optional but recommended)

Cut a 1.6 mm FR-4 sheet to 53.9 × 9.0 mm. Slide into the 1.8 mm slot on
the north wall of the battery bay (groove runs E-W). This fire-isolates
the cell from the PCB electronics per IEC 62133 guidance. If you cannot
source FR-4, a printed PETG divider will pass structural requirement but
NOT the UL-94-V0 flammability requirement.

### Rubber feet

Apply 4× 10 mm Ø × 1 mm self-adhesive bumpers into the corner recesses on
the case underside. 3M Bumpon SJ-5003 or generic equivalent.

### Screws

4× M3 × 8 mm countersunk or pan-head machine screws. Thread into the heat-
set inserts from the top case side. Hand-tighten + 1/8 turn.

## Assembly sequence

1. Press 4× M3 heat-set inserts into bottom-case bosses (see above).
2. Slide FR-4 divider into battery-bay slot.
3. Place LiPo cell in bay, route JST-PH cable through strain-relief slot
   (cable wraps around the relief post once, exits through divider pinch).
4. Plug JST-PH into J_BAT1 on the PCB.
5. Lower the PCB onto the bosses / mid-edge standoffs. Check that TH1 sits
   directly over the NTC thermal window in the bay floor.
6. Clip MX switches into the top-case plate (already installed in the top
   STL). Slide Cherry 2U stab into the Enter position; clip the wire.
7. Drop the top case onto the bottom case — the lip slips into the bottom
   interior with a 0.3 mm slip fit. MX switch pins should pass through the
   PCB hot-swap sockets.
8. Fasten 4× M3 screws.
9. Press keycaps. Connect USB-C. Power on.

## Known gaps / review targets

The following are deliberately left for RED-MECH and RED-COST to probe in
Cycle 2:

- Print-in-place OLED cutout: not yet included. Depends on OLED
  placement in firmware BOM which isn't pinned.
- Snap-fit latches: currently the case relies on 4× M3 screws for
  closure. A no-screw snap-fit variant is an option.
- 3M double-sided tape pads for the battery in the bay: called out in
  assembly but no recess is printed.
- RFID artisan-keycap figurine dock: Phase 5 deliverable, out of scope.

See `/var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/docs/review-log.md`
for the full review workflow.
