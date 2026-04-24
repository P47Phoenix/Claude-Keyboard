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
  the USB-C aperture (the sacrificial bridge handles that). Turn supports
  OFF inside the MX cutouts — they're through features, no overhang.
- **Expected print time:** ≈ 6–7 h (Cycle 2: plate 2.0 mm, larger corner R).
- **Expected filament:** ≈ 35–45 g.

### Bottom case

- **Orientation:** CAVITY UP (open side facing +Z in slicer).
- **Why:** Lets the battery-bay walls, boss tops, and strain-relief post all
  print upwards from the floor without support. The outer bottom surface is
  the build plate, so the rubber-foot recesses come out sharp and flat.
- **Layer height:** 0.2 mm.
- **Infill:** 30 % gyroid. Bottom shell doesn't take keypress load.
- **Walls:** 3 perimeters at 0.4 mm.
- **Supports:** OFF. All overhangs are ≤ 45°; the vent holes (Ø 3 mm)
  and divider grooves are self-bridging at 2 mm floor thickness.
- **Bed adhesion (K2 Plus):** **brim 5 mm, 85 °C bed, 235 °C hotend**
  for first-layer grip. A 6 mm case corner radius (Cycle 2) helps avoid
  the corner-lift failure mode; the brim covers the residual risk.
- **Expected print time:** ≈ 9–11 h (Cycle 2 geometry).
- **Expected filament:** ≈ 55–65 g.

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

1. Chuck an M3 heat-set insert (CNC-Kitchen IUB-M3-L4 or equivalent, 4.0 mm
   knurl Ø, L = 4.0 mm) onto a soldering iron tip rated for inserts.
2. Set iron to **240 °C** (PETG flow temp — above glass transition but
   below decomposition; aim for a 3–5 s press, not a 10 s press).
3. Seat the insert into each boss pilot (BOSS_OD 8 mm, pilot Ø 4.0 mm nominal,
   INSERT_DEPTH 4.2 mm). Press straight DOWN under the insert's own weight
   + a light 1–2 N assist — DO NOT lean. Stop when the insert flange is
   flush with the boss top.
4. **Torque guidance:** no torque applied during insertion — hand-press only.
   After the insert cools, the M3 screw pull-out strength is ≈ 4 N·m in
   PETG; budget screw torque ≤ 0.8 N·m (snug + 1/8 turn).
5. Withdraw the iron cleanly (straight up, don't wiggle); let the boss
   cool for 30 s.
6. Check thread by running an M3 screw in by hand — it should turn in
   smoothly with no cross-thread.

**Pilot hole is shrinkage-compensated:** the CAD authors the hole at
`INSERT_DIA * (1 + SHRINK_COMPENSATION)` so the cooled pilot lands at
4.0 mm. If the insert goes in too loose (spinning with light torque),
step `SHRINK_COMPENSATION` down 0.001 and reprint; if it refuses to
start, step up 0.001.

**Exception:** bosses within the antenna keepout envelope (5 mm around the
25 × 10.3 mm XIAO antenna patch) are printed as 2.8 mm pilot holes for
direct self-tap, **no metal insert** — metal within 5 mm of the nRF52840
antenna detunes the RF match. See `PARAMS.md` §Antenna keepout.

### NTC thermal path

Cycle 2 replaces the Cycle 1 through-hole window above TH1 with a
**0.4 mm PETG membrane** (one print layer). The membrane is formed by
an under-side pocket in the case floor that leaves 0.4 mm of material
sandwiched between the bay interior (cell side) and the NTC (PCB side).

**Why not a through-hole?** IEC 62368-1 Annex Q treats a direct cell-to-
PCB opening as an ignition path — thermal-runaway flame jets and
ejected debris would reach the MCU. The 0.4 mm membrane preserves the
barrier while adding only 3–5 s of thermal lag, which the TP4056
charger IC's thermal shutdown and the firmware's 2 s NTC sampling loop
both absorb.

**Alternative geometry (builder preference):** if the membrane doesn't
print reliably (thin-floor curl, visible bed texture pulls through),
swap to a full through-hole plus a Kapton-tape + thermal-grease pad
bonded to the PCB. To print that variant, temporarily change the NTC
cut in `build_bottom_case()` to a through extrusion from Z = −floor to
Z = 0. The Kapton pad + thermal grease gives similar thermal coupling
without the membrane's slower first-response.

### FR-4 divider (required for fire-safety rating)

Cut a 1.6 mm FR-4 sheet to **53.9 × 9.0 mm**. Cycle 2 upgrades the slot
to **3-edge retention**: grooves run along the bay's north, east, and
west walls, each 1.8 mm wide × `DIVIDER_HEIGHT` (= `BATT_BAY_DEPTH`) tall.
The card slides in from above, then bottoms on the bay floor; north,
east, and west edges sit in the grooves so the divider can't pop out
under cell swell.

**Install order matters:** the divider must be placed **before** the
top case is closed. Once the screws are home the bay is a closed box
and the divider cannot be inserted. See "Assembly sequence" below.

If you cannot source FR-4, a printed PETG divider passes the structural
requirement but NOT the UL-94-V0 flammability requirement — do not ship
a PETG-divider unit.

### Rubber feet

Apply 4× self-adhesive bumpers into the corner recesses on the case
underside. Cycle 2 default is **3M SJ-5018 (12.7 mm × 1 mm)** — the
larger footprint grips desktops better and the 1 mm height matches the
printed recess depth exactly. The Cycle 1 footprint for **3M SJ-5003
(10 mm × 1 mm)** is still supported: set `FOOT_D = 10.0` and
`FOOT_INSET = 8.0` in `claude-code-pad.py` before rebuilding the STL.

### Screws

4× **M3 × 6 mm** countersunk or pan-head machine screws. Thread into
the heat-set inserts from the top case side. Stack consumes ≈ plate
(1.8) + lip landing (2.5) = **4.3 mm** ahead of the insert; M3 × 6
leaves **1.7 mm** of thread engagement inside the IUB-M3-L4 (4 mm
long) — the remainder is spare. **Do not use M3 × 8** — it bottoms
in the insert's blind end before the head lands, so the joint clamps
on the screw point rather than the head.

(Cycle 3 updated the stack math after PLATE_THICKNESS moved 2.0 → 1.8
to sit within Cherry MX plate spec. Clamp stack went 4.0 → 4.3 mm;
thread engagement went 2.0 → 1.7 mm -- still ≥ one full M3 pitch
(0.5 mm) of engagement and well inside the insert body.)

Hand-tighten: snug + 1/8 turn (≤ 0.8 N·m).

## Assembly sequence

1. Press 4× M3 heat-set inserts into bottom-case bosses (see above).
2. **Slide the FR-4 divider** into the 3-edge (N + E + W) battery-bay
   slots. The divider MUST go in now — once the case is closed the
   bay is a box and you can't reach the grooves.
3. Place LiPo cell in bay, route JST-PH cable through strain-relief
   gate (two-wall slot). The cable does not wrap around a post — it
   passes straight through the gate.
4. Plug JST-PH into J_BAT1 on the PCB.
5. Lower the PCB onto the bosses / mid-edge standoffs. Check that TH1
   sits directly over the NTC thermal membrane (0.4 mm PETG layer —
   deliberate, not a hole) in the bay floor.
6. Clip MX switches into the top-case plate (already installed in the
   top STL). Slide Cherry 2U stab into the Enter position; clip the
   wire.
7. Drop the top case onto the bottom case — the 0.5 mm lead-in
   chamfers let the 0.4 mm slip-fit lip land without snagging. MX
   switch pins should pass through the PCB hot-swap sockets.
8. Fasten 4× M3 × 6 mm screws (see §Screws — do NOT use M3 × 8).
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
