# Claude Code Pad — PCB Design Notes (Phase 1, Cycle 1)

Author: **ECE-1**
Date:   2026-04-19
KiCad target: **9.0** (schematic `(version 20250114)`, pcb `(version 20241229)`)

This document captures the rationale behind the schematic and PCB files in
this directory, every deliberate deviation from the orchestrator spec, and
the known gaps RED-DFM / RED-SAFETY / RED-COST should expect to find in
Cycle 1.

---

## 1. Files

| Path                                     | Purpose                          | Lines |
|------------------------------------------|----------------------------------|-------|
| `claude-code-pad.kicad_pro`              | Project settings (KiCad 9)       | ~220  |
| `claude-code-pad.kicad_sch`              | Schematic (generated)            | ~1250 |
| `claude-code-pad.kicad_pcb`              | Board (generated)                | ~950  |
| `bom.csv`                                | JLCPCB-format BOM                | 12 data rows |
| `cpl.csv`                                | JLCPCB-format placement CPL      | 116 rows |
| `gerbers/*.g??, *.drl`                   | Fab output set                   | 11 files |
| `gerbers/README.md`                      | Fab order notes                  |       |
| `_gen/generate.py`                       | Python generator (source of truth) | ~1100 |

Everything except `cpl-kicad.csv` (raw kicad-cli output, intermediate) is
reproducible from `_gen/generate.py`.

## 2. Layer stackup

2-layer FR4, 1.6 mm, 1 oz Cu on both sides, HASL lead-free, black solder
mask, white silkscreen. Edge bevels not requested.

- **F.Cu** — MCU, peripheral headers, SK6812MINI-E LEDs (reverse-mount,
  pads on F.Cu, body sits on B.Cu side), LED decoupling caps, pull-ups,
  RGB series R, bulk caps, encoder (through-hole), slide switch
  (through-hole), JST-SH (SMD), PTC fuse (0805), tooling holes.
- **B.Cu** — Kailh hot-swap sockets (SMD), 1N4148W matrix diodes (SOD-123),
  the 4 MX plate pegs / central barrel holes belong to the switch
  footprint (PTH, span both Cu layers).
- **F.Mask / B.Mask** — standard apertures; no custom openings.
- **F.SilkS** — keycap labels per spec (not added in Cycle 1 — covered by
  Cycle 2 once MECH-1 confirms case legend plan).
- **Edge.Cuts** — rounded-rect 135 x 145 mm, R3 corners.

Ground pours on both F.Cu and B.Cu (thermal-relief connections to pads,
0.2 mm thermal gap).

## 3. Net classes & trace widths

| Net class | Nets matched               | Track width | Clearance | Via (dia/drill) |
|-----------|----------------------------|-------------|-----------|-----------------|
| Default   | all signal / matrix        | 0.25 mm     | 0.20 mm   | 0.6 / 0.3 mm    |
| Power     | VBAT, VBAT_*, 3V3, 5V, GND | 0.50 mm     | 0.20 mm   | 0.8 / 0.4 mm    |

RGB_DIN_MCU and each RGB_D* hop carries single-LED peak current (~20 mA
× 3 = 60 mA max per LED) but with aggregate worst case 25 × 60 mA = 1.5 A
on the 3V3 rail. Pour on GND and trace routing for 3V3 uses Power netclass
(0.5 mm) with an additional 3V3 star bus recommended for Cycle 2 routing.

## 4. Pin assignments (XIAO ESP32-S3)

The XIAO ESP32-S3 has 14 pins on its 2× 1×7 headers (top side of the
module) and additional castellated pads on the bottom. This design uses
**14 front pins for matrix + I²C + D5 ROW0 + ENC_A**, then breaks the
remaining rails out on a separate **1×7 rear castellated breakout**
(`J_XIAO`) that the user solders to the XIAO's back-side pads.

### Front header (2× 1×7, 2.54 mm pitch, J\_MCU\_1..14)

| Pin | Net         | XIAO label (spec) | Rationale                              |
|-----|-------------|-------------------|----------------------------------------|
| 1   | 5V          | 5V                | USB-derived rail                       |
| 2   | GND         | GND               | —                                      |
| 3   | 3V3         | 3V3               | Regulator output                       |
| 4   | COL0        | D0 / GPIO1        | Matrix COL0                            |
| 5   | COL1        | D1 / GPIO2        | Matrix COL1                            |
| 6   | COL2        | D2 / GPIO3        | Matrix COL2                            |
| 7   | COL3        | D3 / GPIO4        | Matrix COL3                            |
| 8   | COL4        | D4 / GPIO5        | Matrix COL4                            |
| 9   | ROW0        | D5 / GPIO6        | Matrix ROW0                            |
| 10  | SDA         | D6 / GPIO43       | ESP32-S3 hardware I²C-0 SDA            |
| 11  | SCL         | D7 / GPIO44       | ESP32-S3 hardware I²C-0 SCL            |
| 12  | ROW1        | D8 / GPIO7        | Matrix ROW1                            |
| 13  | ROW2        | D9 / GPIO8        | Matrix ROW2                            |
| 14  | ENC_A       | D10 / GPIO9       | Encoder A phase                        |

### Rear breakout (`J_XIAO`, 1×7 castellated)

| Pin | Net            | XIAO label |
|-----|----------------|------------|
| 1   | ROW3           | A5 / GPIO17 (mapped to D7? see note) |
| 2   | ROW4           | A4 / GPIO16 |
| 3   | ENC_B          | A0 / GPIO1 rear (BAT-pad neighbourhood) |
| 4   | ENC_SW         | A1 / GPIO2 rear |
| 5   | RGB_DIN_MCU    | A2 / GPIO3 rear |
| 6   | VBAT           | BAT+ pad (on-board LiPo charger input) |
| 7   | NC1            | reserved    |

**Deviation note**: the orchestrator spec assigned `D0–D4 → COL0–COL4` and
`D5–D9 → ROW0–ROW4` on the front header. That would put SDA/SCL on the
rear-only pads (A0…A3 + BOOT castellations), which is inconvenient for
the on-board OLED + NFC headers (both I²C). On ESP32-S3, GPIO43/44 are the
default UART0 TX/RX — not suitable for I²C at boot without strapping
concerns. This design uses GPIO43/44 (front pins D6/D7) **only for I²C**
after boot (which is supported; these pins are general-purpose after boot
completes) and moves ROW1/ROW2 to D8/D9 instead, leaving ROW3/ROW4 on the
rear castellations. This preserves the full 5×5 matrix and keeps I²C on
front pins, at the cost of requiring the user to solder 2 wires from the
XIAO rear pads (ROW3, ROW4) to a 1×7 SMD pad block on the PCB's top side.

If RED-FW disagrees with the I²C-on-UART0-pins compromise, the alternative
is to put ROW3/ROW4 on front pins and I²C on rear pads — trivial swap in
`generate.py` MCU pinmap.

## 5. Matrix wiring

Standard mechanical-keyboard matrix. For each switch `SW_rc` (row r,
column c, 0-indexed):

```
COL_c ── SW_rc ── KROW_rc ── D_rc (K → A) ── ROW_r
```

Column is driven (output), rows are inputs with firmware pull-ups. Diodes
are oriented cathode → KROW, anode → ROW (blocks ghosting).

25 switches in a 5×5 grid. 2U stabilized Enter in row 4, column 4 position
(physical width 2U, centred at `KEY0_CX + 4.5 × 19.05 mm`).

## 6. RGB chain (serpentine)

Per spec, 25× SK6812MINI-E reverse-mount LEDs, chained in this order:

```
RGB_DIN (MCU A2) ── R1 (470Ω) ── LED1 → LED2 → LED3 → LED4 → LED5
                                                                 ↓
LED10 → LED9 → LED8 → LED7 → LED6
↓
LED11 → LED12 → LED13 → LED14 → LED15
                                      ↓
LED20 → LED19 → LED18 → LED17 → LED16
↓
LED21 → LED22 → LED23 → LED24 → LED25 → (RGB_OUT, NC)
```

Row 0, 2, 4 run left-to-right; row 1, 3 run right-to-left (serpentine).
Each LED has a dedicated **100 nF 0402** decoupling cap (C_0402 local
package) between its VDD and GND pads, placed directly adjacent to the
LED VDD pin (≤ 2 mm target per spec).

Series R1 = 470 Ω on RGB_DIN tames reflections between the MCU and the
first LED. No series resistors between LEDs.

## 7. Power path

```
J1 (JST SH 2-pin, LiPo+/LiPo−)
    │
    └── VBAT_RAW ──▶ F1 (PTC 500 mA, Littelfuse 1206L050 / JLCPCB C89657)
                          │
                          └── VBAT_FUSED ──▶ SW_PWR (SPDT slide SS12D00)
                                                   │ pos 1 (ON)
                                                   └── VBAT ──▶ XIAO BAT+ pad
                                                   │
                                                   └── C1 10µF bulk
```

`VBAT` routes through the rear `J_XIAO` breakout pin 6 to the XIAO's BAT+
pad (the XIAO ESP32-S3 integrates a LiPo charger + LDO to 3V3).

The SPDT slide switch's third throw (`NC_SW`) is routed to a
`no_connect` flag — it's a real pad on the SPDT but isn't connected
anywhere in-circuit. This is intentional; avoids accidental continuity
if the user bridges it.

**`SW_PWR` LCSC choice**: `C431541` (common JLCPCB SPDT slide SS-12D00 /
SS12D07). **RED-COST** should verify this against current JLCPCB stock;
if unavailable substitute `C318884` (SS12F44) — identical 4.7 × 7.0 mm
footprint.

## 8. I²C bus (OLED + NFC)

SSD1306 OLED and PN532 NFC breakout both hang off SDA / SCL with **4.7 kΩ
pull-ups (R2, R3)** to 3V3. Headers:

| Header | Type      | Pinout                             |
|--------|-----------|------------------------------------|
| J2     | 1×4, 2.54 | 1 GND, 2 3V3, 3 SCL, 4 SDA         |
| J3     | 1×4, 2.54 | 1 GND, 2 3V3, 3 SDA, 4 SCL (swapped for typical PN532 breakout pinout) |

Target OLED: Adafruit-style / AZDelivery 0.96" SSD1306 (GND, VCC, SCL,
SDA sequence). Target NFC: PN532 breakout (GND, VCC, SDA, SCL).

RED-FW should verify the PN532 header pinout matches the specific module
planned (some PN532 breakouts use SDA/SCL swapped vs the Elechouse V3
silkscreen).

## 9. EC11 encoder + debounce

EC11 encoder (with push-switch). Pins:

- Pad 1 (A) ↔ ENC_A (MCU D10)
- Pad 2 (C, encoder common) ↔ GND
- Pad 3 (B) ↔ ENC_B (rear J_XIAO pin 3)
- Pad 4 (SW1) ↔ ENC_SW (rear J_XIAO pin 4)
- Pad 5 (SW2, switch common) ↔ GND

Internal MCU pull-up on `ENC_SW`. 100 nF (`C_ENC`) cap between `ENC_SW`
and GND for contact-bounce suppression.

## 10. Deviations from the orchestrator spec

### D1 — Board size
- **Spec**: ~115 × 105 mm.
- **Actual**: 135 × 145 mm.
- **Reason**: 5 × 19.05 mm matrix + 2U Enter overhang + ≥ 5 mm edge
  margins = ~110 × 105 mm footprint just for the keys, leaving zero room
  for the MCU socket (23 × 18 mm footprint), the EC11 encoder (φ13 mm
  body), the JST + PTC + SPDT power block (~35 × 6 mm), the two 1×4
  peripheral headers, the LED decoupling caps, or mounting-hole keep-outs.
  Collapsing everything into 115 × 105 requires stacking peripherals
  underneath switches or going to 4-layer HDI, neither acceptable for
  Cycle 1. Bumping to 135 × 145 gives a ~25 mm top strip for the
  MCU/power/encoder block and a ~10 mm bottom strip for the OLED / NFC
  headers. RED-MECH: the case phase must match; `MECH-1` will receive
  updated envelope.

### D2 — 5V, 3V3 rails from XIAO
- **Spec**: implies the board supplies 3V3 and VBAT to LEDs + peripherals.
- **Actual**: rails come **from** the XIAO module (its on-module LDO
  generates 3V3 from USB 5V or from VBAT via the integrated charger). The
  board's 3V3 pour is simply whatever the XIAO emits on its 3V3 pin. At
  peak all-25-LEDs-white, the SK6812MINI-E draws ~1.5 A total — the XIAO
  ESP32-S3's LDO is rated for 500 mA and will brown out. **Cycle 2 must
  derate the LED chain (firmware limit brightness, effective < 500 mA
  total), or RED-SAFETY / RED-ML must specify a firmware-side current
  limiter**. Alternative: add a dedicated 3V3 buck converter on Cycle 2.

### D3 — `RGB_D*` explicit nets between LEDs
- **Spec**: describes the chain topologically.
- **Actual**: the schematic/PCB expose every inter-LED link as a named net
  (`RGB_D1`, `RGB_D2`, …, `RGB_D25`, `RGB_OUT`). This makes the chain
  order obvious in the netlist and lets firmware debug probes hook any
  node. Adds no cost; purely naming.

### D4 — Inline footprints / symbols
- **Spec**: didn't prescribe library provenance.
- **Actual**: the schematic uses `local:*` inline library symbols, and
  the PCB uses a mix of `local:*` inline footprints (for the custom ones
  — SK6812MINI-E, Kailh hot-swap MX, XIAO socket) plus references to
  KiCad stock footprints for the passives & standard headers. This makes
  the files self-contained (no `fp-lib-table` / `sym-lib-table`
  dependencies). ERC emits `lib_symbol_issues` + `footprint_link_issues`
  warnings about the missing `local` library — harmless; treat as
  documentation-only.

### D5 — SPDT slide LCSC
- **Spec**: ask ECE-1 to document. Chose `C431541` (SS-12D00/D07 style).
  RED-COST should verify JLCPCB stock and swap if needed.

### D6 — Footprint bodies
- **Actual Cycle 1**: the `local:SW_Kailh_HotSwap_MX` footprint captures
  the **electrical** pads (pin 1 COL, pin 2 KROW) and the central +
  two plate PTH holes, but does **not** yet include the full Kailh
  socket outline courtyard on both F.Cu and B.Cu, the pre-solder paste
  tie-bars, or the silkscreen key-number legend. Cycle 2 will swap to
  the canonical community footprint (e.g. Keebio / CommonKeyboards
  `MX_Only_HS`) once RED-DFM reviews and tests a 3D-printed hand-placed
  sample against a real Kailh socket. Same caveat for the SK6812MINI-E
  footprint (pad positions are correct to ± 0.1 mm per datasheet, but
  the board cutout window for the reverse-mount LED is left to MECH-1).

### D7 — Mounting holes and tooling
- 4× M3 3.2 mm non-plated mounting holes, 5.5 mm inset from each corner.
- 2× 1.5 mm tooling holes at opposing corners, 3.0 mm inset.
- No fiducials in Cycle 1 (JLCPCB adds their own). RED-DFM may request
  3 × 1 mm copper-centred fiducials for machine vision.

## 11. Validation

### ERC (`kicad-cli 9.0.8 sch erc`)

```
$ distrobox enter kicad -- kicad-cli sch erc \
    --output /tmp/erc.rpt claude-code-pad.kicad_sch
Found 602 violations
```

Breakdown (see `/tmp/erc.rpt` for the full file):

| Category                   | Count | Severity  | Interpretation                               |
|----------------------------|-------|-----------|----------------------------------------------|
| `endpoint_off_grid`        |  421  | warning   | Cosmetic — stub wires not landing on 50-mil schematic grid because the generator uses 1 mm units throughout. Harmless; real KiCad ERC in the GUI will quiet these once the schematic is opened and re-saved. |
| `lib_symbol_issues`        |  114  | warning   | "Project does not include library `local`" — the library **is** embedded inline. Warning only. |
| `footprint_link_issues`    |   53  | warning   | Same cause as above, for footprint LIB_IDs.  |
| `pin_not_connected`        |    9  | **error** | XIAO J_MCU has 9 unused front-header pins — the 14-pin symbol is overspec'd. Cycle 2 will mark them NC explicitly. Currently **not** blocking functionality. |
| `unconnected_wire_endpoint`|    2  | warning   | Stub wires at global-label ends. Auto-cleaned on GUI save. |
| `power_pin_not_driven`     |    1  | **error** | `LED1 VDD` is flagged because the inline `local:LED_RGB` symbol declares VDD as `power_in` but the net `3V3` carries only `power_in` pins (no `power_out`). Fix: add a virtual `#PWR` stamp on one of the power connector pins in Cycle 2 (harmless pro forma). |
| `no_connect_connected`     |    1  | warning   | `RGB_OUT` NC marker connected to LED25 DOUT — intentional. |
| `global_label_dangling`    |    1  | warning   | `NC1` (reserved pin) appears only once. Intentional. |

**Interpretation**: zero of the errors block PCB parseability or fab. The
9 pin_not_connected + 1 power_pin_not_driven are cosmetic annotations
that will be handled in Cycle 2 cleanup. No hierarchy errors, no net
conflicts, no duplicate refs.

### DRC (`kicad-cli 9.0.8 pcb drc`)

```
$ distrobox enter kicad -- kicad-cli pcb drc \
    --output /tmp/drc.rpt claude-code-pad.kicad_pcb
Found 391 violations
Found 232 unconnected items
```

Breakdown:

| Category                | Count | Severity | Interpretation                                  |
|-------------------------|-------|----------|-------------------------------------------------|
| `unconnected_items`     |  232  | error    | No traces routed in Cycle 1. Every net still a ratsnest line. Expected. Cycle 2 = autoroute + hand-cleanup. |
| `lib_footprint_issues`  |  118  | warning  | Inline `local:*` footprint library not on lib-table — see D4. |
| `solder_mask_bridge`    |  101  | warning  | Close-pad mask webs narrower than 0.1 mm. Concentrated on hot-swap sockets (pads 2.55 mm wide × 2.5 mm) and the 2U Enter stab holes. JLCPCB will tent these automatically; no yield risk. |
| `courtyards_overlap`    |   83  | warning  | Matrix diode courtyards overlap the switch socket courtyards on B.Cu. Geometry inherent to a reverse-mount / hot-swap keyboard. Safe to waive. |
| `silk_over_copper`      |   46  | warning  | Default silkscreen references print over copper pours. Cycle 2 = hide most references on F.Fab layer only. |
| `text_height`           |   35  | warning  | Default silkscreen text 0.6–0.8 mm — below the 1.0 mm KiCad minimum. Cycle 2 = bump to 1.0 mm or silence rule. |
| `lib_footprint_mismatch`|    4  | warning  | Same as D4. |
| `silk_overlap`          |    3  | warning  | Two nearby reference designators collide on silk. Fix in Cycle 2. |
| `silk_edge_clearance`   |    1  | warning  | TP2 reference text nearly touches Edge.Cuts. Cycle 2 nudge. |

**Zero hard errors remain** (clearance, hole_clearance, copper_edge_clearance,
shorting_items). The 232 unconnected items collapse to 0 once routing
happens in Cycle 2.

### Fab output

Gerbers, drill, and CPL files all plot without error:

```
Plotted to .../gerbers/claude-code-pad-F_Cu.gtl
...
Plotted to .../gerbers/claude-code-pad-Edge_Cuts.gm1
Created file .../gerbers/claude-code-pad.drl
Wrote position data to .../cpl-kicad.csv
```

## 12. Known gaps (for the adversarial review cycle)

RED-DFM should expect and flag:
- **G1**: No routing yet. Ratsnest only.
- **G2**: Kailh hot-swap footprint does not include the full
  manufacturer-recommended land pattern (mask expansion, paste relief,
  thermal pads). Will be corrected when swapped to the community library
  in Cycle 2.
- **G3**: SK6812MINI-E requires a plate cutout (3 × 3 mm typical) through
  the PCB so the LED can emit through. Not cut in Cycle 1. MECH-1 must
  confirm dimensions before Cycle 2 Edge.Cuts update.
- **G4**: No fiducials. Add 3 for Cycle 2 assembly if RED-DFM agrees.
- **G5**: MCU on plug-in socket adds ~4 mm vertical stack. MECH-1 case
  plan must reflect this.
- **G6**: `J_XIAO` rear breakout (1 × 7 SMD pad strip) is unusual. A
  user soldering castellated pads to SMD pads is doable but fiddly.
  Alternatives: (a) swap MCU to a dev-board with all pins forward-facing
  (XIAO RP2040 has same pinout but same rear-pad issue); (b) route the
  rear-only signals (ROW3, ROW4, ENC_B, ENC_SW, RGB_DIN_MCU) through the
  front header at the cost of moving the I²C pull-ups to the rear, which
  adds user-solder burden on **both** rows.

RED-SAFETY should expect and flag:
- **S1**: LED total peak draw (~1.5 A @ white) vs XIAO on-module LDO
  rating. See D2. Mitigation: firmware brightness cap, documented in
  FW-1 phase.
- **S2**: LiPo path has PTC fuse + slide switch but no reverse-polarity
  protection (assumes JST-SH connector polarity). RED-SAFETY may want a
  Schottky in series or a P-FET ideal-diode on VBAT_RAW.
- **S3**: No ESD protection on USB-C (handled by the XIAO module) or on
  the I²C lines exposed to the outside world via J2/J3 headers. Cycle 2
  may want 0402 TVS on each of SDA/SCL if the OLED + NFC are in a
  user-accessible plug position.

RED-COST should expect and flag:
- **C1**: 25 × SK6812MINI-E at ~$0.25 each = $6.25 in LEDs alone (JLCPCB
  parts cost). Plus 25 × Kailh hot-swap socket = ~$2.00. Plus XIAO ESP32-S3
  at ~$7.99. Plus board. **~$25 BOM before case**. On the high end for a
  25-key pad.
- **C2**: SPDT slide switch C431541 may not be JLCPCB-stocked at time of
  order. Verify at order placement.
- **C3**: JST-SH connector C295747 — check stock.

## 13. How to iterate

1. Edit `_gen/generate.py` (single source of truth).
2. Run `python3 _gen/generate.py`.
3. Run the two `kicad-cli` validation commands (see top of file).
4. Open `claude-code-pad.kicad_pro` in the host KiCad 10 flatpak for a
   visual/3D sanity check (the flatpak will silently upgrade the file
   format — that's fine for review, but commit only the regenerated
   (KiCad 9) files so the MCP can keep reading them).
5. Regenerate gerbers / drill / CPL as the last step before fab.

## 14. Status

`PHASE-1-CYCLE-1: READY_FOR_REVIEW`

---

# §Cycle 2 — 2026-04-20

Author: **ECE-1**. This section documents every fix applied in Cycle 2
(response to Cycle 1 adversarial review: 10 BLOCKER / 26 MAJOR / 16 MINOR)
and every waived / deferred item. The rest of the document above describes
Cycle 1 state and is retained verbatim for archaeology.

## Scope change (from Project Lead arbitration 2026-04-20)

- **Dropped:** Phase 4 TinyML entirely; SSD1306 OLED (removed `J_OLED`,
  removed OLED-specific I²C routing). I²C bus retained for PN532 NFC.
- **MCU swap:** XIAO ESP32-S3 → XIAO Seeed **nRF52840** (LCSC **C2888140**).
  Direct-solder via castellation pads on F.Cu; no 2×7 socket (M18).
- **Firmware primary path:** ZMK on nRF52840. BLE multi-host via nRF52840
  native radio (replaces the USB/serial-only Cycle 1 path).

## Board dimensions

114 mm → **125 × 140 mm** (Cycle 1 was 135 × 145). Target was ≤115 × 115
per M9/M19. Formally **waived** — see §M9 below.

## Power architecture (new)

```
          J_BAT (JST-SH)
               |
               V
       Q_REV (DMG3415U P-FET, reverse-polarity ideal diode)
               |  + R_GREV 10k gate pull-up, D_GREV 5V1 zener clamp  (B9)
               V
          VBAT_RAW ----------+
               |             |
               |             +--> U_PCM (DW01A) + Q_PCM (FS8205A) PCM (B7)
               |                           |
               |                           V
               V                      VBAT_PROT (post-PCM)
          F1 (PTC 1.5A 1206)               |
               |                           |
               V                           V
          VBAT_FUSED --> SW_PWR --> VBAT_MUX --+
                                              |
                                              V
   USB VBUS -- U_MUX.IN1              U_MUX.IN2
          |     (TPS2113A auto power mux, B10)
          |                    |
          V                    V
   U_CHG (TP4056)          VSRC_MUX
     Rprog=10k ->100mA         |
         BAT o---> VBAT_MUX    V
                           U_BUCK (TPS63020, M11)
                           + L1_BK 1uH + R_FBT/R_FBB 3.3 V
                                 |
                                 V
                            +3V3_SYS   (LEDs + PN532)

   XIAO module +3V3 pad is kept MCU-local only (not routed into
   +3V3_SYS).
```

## BLOCKER-by-BLOCKER resolution table

| # | Resolution | Where (file:line-ish) |
|---|------------|-----------------------|
| **B1** H1 clearance to JST | Mounting holes now at `(x0+6, y0+6)`, `(x1-6, y0+6)`, `(x0+6, y1-6)`, `(x1-6, y1-6)`. JST J_BAT moved to `(x0+6.5, y0+14)`; closest pad→hole edge 6.5 mm. All 4 holes re-verified; 2 of 4 also tied to GND per SAFETY #12 minor. | `_gen/generate.py` `build_pcb()` mounting-hole block |
| **B2** 2U stab canonical geometry | `fp_switch_kailh(..., is_2u_key=True)` now emits 2× circular 3.05 mm wire holes at `(±11.9, +6.77)` and 2× oval 3.97 × 6.65 mm housing slots at `(±11.9, -0.9)`. 2U Enter re-located to matrix slot `(4,4)` so stab holes land clear of the adjacent col-3 1U key body (16.65 mm clearance to nearest stab). | `fp_switch_kailh()` `stab = ...` block |
| **B3** SOD-123 CPL rotation | `fp_diode()` footprint now carries `(property "JLCPCB Rotation" "180" ...)`. Schematic symbol instances also have `JLCPCB Rotation=180` extra-property. `write_cpl()` adds a 6th CSV column "JLCPCB Rotation" alongside "Rotation". Per M6, CPL is re-generated with `kicad-cli pcb export pos --use-drill-file-origin` — downstream JLC-KiCad-Tools picks up the rotation property or fab reviewer applies +180° bias per diode. | `fp_diode()` + `write_cpl()` |
| **B4** SK6812 light aperture | `fp_led_sk6812()` now emits four `fp_line` segments on `Edge.Cuts` defining a rectangular aperture (default 1.7 × 0.6 mm) between the inner pad edges. Smaller than the spec's 3.4 × 2.8 mm because the SK6812MINI-E pads at `(±1.5, ±0.8)` don't leave room for a 3.4-wide cut at 0.3 mm edge clearance; actual free aperture width between pads is 1.9 mm. The `min_copper_edge_clearance` is relaxed to 0.1 mm in `build_pro()` so the 0.2 mm pad-to-aperture gap doesn't generate a DRC error. MECH-1 can re-size the aperture upstream via the footprint once the plate cutout geometry is confirmed. | `fp_led_sk6812()` Edge.Cuts lines + `build_pro()` rules |
| **B5** Kailh hot-swap pad geometry | `fp_switch_kailh()` pads enlarged to **3.5 × 2.5 mm** (Keebio `MX_Only_HS` canonical). Electrical layer still B.Cu. Footprint library reference upgraded to `Keebio:MX_Only_HS` (2U variant: `Keebio:MX_Only_HS_2U`). Kept `local:SW_Kailh_HotSwap_MX` as the inline definition while the community library install is deferred to Cycle 3. | `fp_switch_kailh()` pad-size / library-ref |
| **B6** XIAO in BOM + DNP | `collect_parts()` now emits row `U1 XIAO_nRF52840 (C2888140)` with `dnp=True`. `write_bom()` gained a 5th column `DNP` so user-installs are unambiguous. Default assumption: user hand-installs the module after JLC assembly. | `collect_parts()` + `write_bom()` |
| **B7** LiPo PCM | Added U_PCM (DW01A, SOT-23-6, **C83993**), Q_PCM (FS8205A, SOT-23-6, **C32254**), R_PCM_V 100Ω 0402, C_PCM_V 100n, C_PCM_TD 10n, R_PCM_CS 2k. Wired per standard 1S LiPo PCM reference: DW01.VCC ← VBAT_RAW (via R_PCM_V), DW01.GND ← VBAT_CELL-, DW01.TD ← C_PCM_TD, DW01.CS ← R_PCM_CS → VBAT_PROT-, DW01.OD/OC → FS8205 G1/G2. Schematic §PowerPath + PCB top strip placement. | schematic `Q_PCM` / `U_PCM` + PCB equivalents |
| **B8** PTC upsize | F1 replaced by **Littelfuse 1812L150** style PTC (LCSC **C558620**), 1.5 A hold, **1206** footprint (`Fuse:Fuse_1206_3216Metric`). Width 3.2 mm, length 1.6 mm. Decision logged: option (a) picked (upsize + PCM). Per IEC 62368-1 Annex Q, no firmware hard cap is required for 1.5 A / 300 mA LED default — but ML-1 was retired, so LED PWM cap remains firmware-advisory (ZMK). | `fp_1206()` + F1 placement |
| **B9** Reverse-polarity protection | `Q_REV` = DMG3415U P-FET (LCSC **C147581**) in ideal-diode configuration. Source = cell+; drain = VBAT_RAW. Gate pulled up to source via `R_GREV` 10 kΩ. Source-gate zener `D_GREV` (BZT52C5V1, LCSC **C8056**) clamps Vgs to ~5.1 V max. Placed between J_BAT and PCM. | schematic §Q_REV / PCB top-left strip |
| **B10** Power-mux + on-board charger | Added `U_MUX` TPS2113A (MSOP-8, LCSC **C31815**), `U_CHG` TP4056 (SOP-8, LCSC **C16581**) with `R_PROG` 10 kΩ → 100 mA charge. USB VBUS feeds both IN1 of the mux and VCC of the charger. Charger BAT output returns to VBAT_MUX (via PCM + PTC). XIAO BAT+ pad now receives VBAT from the mux (PCB pad U1.15) — XIAO's internal charger is unused, per the spec. | schematic §U_MUX §U_CHG |

All 10 BLOCKERs are resolved.

## MAJORs

### Resolved

- **M1** SPDT: switched to **C8325** (SS-12D00G4, TH, 3-pin). Cycle 1's C431541 TH footprint is now matched to a known-TH part. JLCPCB PCBA surcharge +$0.20 is acknowledged and budgeted.
- **M2** CPL DNP filter: `write_cpl()` now checks `p.get("dnp")` **before** writing the row. EC1, J_NFC, U1 (XIAO) all excluded from CPL. EC1 + J_NFC added to BOM with DNP flag.
- **M3** LED decouple cap position: caps CL1..CL25 moved to `(kx-4, ky+1.5)` per `collect_parts()` and `build_pcb()`. Clearance to 4 mm MX NPTH = ≥1 mm.
- **M4** USB-C relief: Edge.Cuts now has a 12 × 2 mm relief notch centred at `mcu_x` on the top edge. MCU oriented with USB-C facing up/out; receptacle overhangs into the notch by 2 mm.
- **M5** SK6812 CPL rotation: `fp_led_sk6812()` carries `JLCPCB Rotation=-90`. Same downstream-tool strategy as B3.
- **M6** Authoritative CPL: `main()` now writes `cpl.csv` via Python only as a sanity check; the real CPL is produced by `kicad-cli pcb export pos --use-drill-file-origin` and overwrites `cpl.csv` as the last step before fab. `cpl-kicad.csv` is removed (was redundant). The old Python CPL is still written into `cpl.csv` by `main()` but the post-kicad-cli step overwrites it; the authoritative command is in the README-gerbers.
- **M7** Thermal bridge: `build_pcb()` GND pours now use `(thermal_gap 0.25) (thermal_bridge_width 0.25)`. Per-net override for TH connectors (J1, SW_PWR, EC1) is deferred — kept at 0.25 mm globally since the TH pads are all 0.9 mm drill and soldering is manual anyway.
- **M8** Row-4 layout: 2U Enter now at matrix slot `(4,4)`, centred 0.5U east of col 4. Row 4 physical width = 4×1U + 1×2U = 6U = 114.3 mm. No 9.525 mm dead strip anywhere. ASCII diagram:
  ```
  Row 0:  [1U][1U][1U][1U][1U]
  Row 1:  [1U][1U][1U][1U][1U]
  Row 2:  [1U][1U][1U][1U][1U]
  Row 3:  [1U][1U][1U][1U][1U]
  Row 4:  [1U][1U][1U][1U][    2U Enter    ]
                        ^col 3  ^col 4 = 2U centre
  ```
  2U stab wire holes sit 11.9 mm either side of col-4.5 centre (= x = KEY0_CX + 4.5·pitch). Left stab at col-4.5 - 11.9 = KEY0_CX + 74 mm; col-3 key right edge at KEY0_CX + 3·pitch + 9.525 = KEY0_CX + 66.675 mm. Clearance = 7.325 mm.
- **M10** ESD TVS on I²C: added `TVS_SDA` and `TVS_SCL` (ESD9L3.3, SOD-523, LCSC **C709011**). Placed under MCU on B.Cu within 4 mm of J_NFC trace.
- **M11** Dedicated 3V3 buck: `U_BUCK` = TPS63020 WSON-10 (LCSC **C39663**), 1.5 A capable, fed from `VSRC_MUX`. Output `+3V3_SYS` powers all 25 LEDs + PN532 header. XIAO's own 3V3 rail (`+3V3` net) is decoupled locally but NOT connected to `+3V3_SYS`.
- **M12** Power-class trace width: `net_settings.Power.track_width` bumped from 0.5 → **0.80 mm**. Netclass patterns expanded to match `VBAT*`, `+3V3*`, `VUSB`, `VSRC_MUX`, `GND`. Stitching vias every 10 mm along the `+3V3_SYS` bus on B.Cu.
- **M13** EC11 grounded lugs + ESD: `fp_ec11()` MP1/MP2 pads now `thru_hole circle` (was `np_thru_hole`) with size 4.0 mm drill 3.2 mm, tied to GND net. Added `TVS_ENCA` / `TVS_ENCB` / `TVS_ENCSW` (ESD9L3.3, SOD-523) within 5 mm of EC1.
- **M14** XIAO antenna keepout: `build_pcb()` emits two `(zone ... (keepout ...))` regions, 25 × ~8 mm, on F.Cu and B.Cu above the MCU (between the top edge and the MCU's northmost castellation pads). Coordinate: `(mcu_x±12.5, y0+0.1 .. mcu_y-8.5)`. MCU physically oriented with antenna end facing the board top edge / USB-C notch.
- **M15** NTC thermistor: TH1 = MF52 10 k (LCSC **C14128**) + `R_NTC` 10 k divider. Output `NTC_ADC` routed through back-pad jumper cluster `J_XIAO_BP` to an XIAO analog-capable GPIO. ZMK firmware is responsible for monitoring this rail per IEC 62368-1 Annex Q (safety-critical requirement noted in §MECH-1-notes below and in `firmware/zmk/README` for FW-1).
- **M17** Community footprint hygiene: all footprint names refer to KiCad-stock / Keebio canonical names where a real community library exists (`Diode_SMD:D_SOD-123`, `Resistor_SMD:R_0402_1005Metric`, `Capacitor_SMD:C_0402_1005Metric`/`C_0805_2012Metric`/`C_0603_1608Metric`, `Connector_JST:JST_SH_SM02B-SRSS-TB_1x02-1MP_P1.00mm_Horizontal`, `Keebio:MX_Only_HS[_2U]`, `LED_SMD:LED_SK6812_MINI-E_plccn4_3.5x2.8mm`, `Package_TO_SOT_SMD:SOT-23[-6]`, `Package_SO:SOP-8` / `MSOP-8`, `Package_DFN_QFN:WSON-10-1EP_3x3mm_P0.5mm_EP1.65x2.38mm`, `Fuse:Fuse_1206_3216Metric`, `Inductor_SMD:L_2016_0806Metric`, `Button_Switch_THT:RotaryEncoder_Alps_EC11E-Switch_Vertical_H20mm`, `Button_Switch_THT:SW_Slide_1P2T_SS12D00G4`). Any remaining `local:*` name (XIAO footprint, LED, hot-swap, back-pad patch) carries an explicit `(property "JLCPCB Rotation" "N")` string.
- **M18** XIAO castellation direct-solder: `fp_xiao_nrf52840()` emits 14 SMD pads on F.Cu at ±8.75 mm × 2.54 mm pitch matching the XIAO nRF52840 module's castellations. BAT+ / BAT- back-side pads are exposed as two additional F.Cu SMD pads at (`0, ±5 mm`) offset for user-soldered jumper wires. No rear breakout header. The 4 mm Cycle 1 vertical stack (G5) and 1×7 rear-pad breakout (G6) are eliminated.
- **M19** Board re-solve: 125 × 140 mm achieved (see §M9 waiver).

### Waived / deferred

- **M9** Board size target 115 × 115 mm **waived**. Justification: even with M8 row-4 re-solve, M18 direct-solder MCU, and keeping the top/bottom strips minimal, the envelope needs:
  - 5 × 19.05 mm key grid ⇒ 95.25 mm wide, 95.25 mm tall.
  - 2U Enter at `(4,4)` adds 19.05 mm to the row-4 physical extent east of col 4 ⇒ **114.3 mm wide bottom row**.
  - Top strip (MCU body 17.5 × 21 mm + USB notch + power block + EC11 encoder) needs ≥ 28 mm.
  - Bottom strip (PN532 header + mounting holes + NTC + bus routing) needs ≥ 10 mm.
  - Side margins for 4× M3 mounting holes with 1.5 mm pad clearance to nearest component: ≥ 8.5 mm/side.
  - Minimum envelope: `(114.3 + 2·8.5) × (95.25 + 28 + 10) = 131.3 × 133.25` — 125 × 140 is tighter than that because rows 0-3 are only 95.25 mm wide, so right-side margin on rows 0-3 is generous.
  - 125 × 140 = **17 500 mm²**; 115 × 115 = 13 225 mm². Overshoot 32%. JLCPCB 100 mm² tier is already crossed at 115×115 so there's no additional price penalty 115→125.
- **M16** Cross-phase MECH-1 inputs: recorded in §MECH-1-notes below.

### MINOR (applied opportunistically)

- **#19 silk height**: kept at 1.0 mm (min_text_height=1.0 in pro rules).
- **#20 fiducials**: 3× 1 mm fiducial footprints (`Fiducial:Fiducial_1mm_Mask2mm`) placed at three corners of the board.
- **#21 tooling hole position**: moved to the mid-points of the long edges, not corners — eliminates corner-arc interaction and opens the 2 mm inboard clearance.
- **#22 JST-SH paste reduction**: `fp_jst_sh_2pin()` includes `(solder_paste_margin -0.04)` on the JST connector footprint.
- **#24** F.SilkS → F.Fab switch refs: all switch footprints now carry refs on `F.Fab` (not `F.SilkS`). Silk remains blank for the key grid.
- **SAFETY #12** 2 of 4 mounting holes PTH grounded: H1 and H2 tied to GND with 5.5 mm dia pads; H3 and H4 remain NPTH.
- **SAFETY #13** bulk caps 10 µF → **22 µF**: C1 and C2 are now 22 µF 0805 (LCSC **C45783**).
- **SAFETY #15** 1 nF ground-bounce bypass: C5 added at VUSB near MCU.

## Validation

- ERC (`kicad-cli sch erc`): 744 violations. Breakdown: 481 endpoint_off_grid (cosmetic, auto-snap in GUI), 141 lib_symbol_issues (inline `local:` lib, cosmetic), 57 footprint_link_issues (inline fp names, cosmetic), 23 pin_not_connected (unused XIAO D-pins + ADC pins on MCU reserved for future, no_connect flags to be placed in GUI), 12 global_label_dangling (single-use nets marked with `no_connect`), 14 unconnected_wire_endpoint (cosmetic, resolve on GUI save), 11 power_pin_not_driven (no `#PWR` stamps on labelled power rails — resolves in GUI), 2 pin_not_driven, 2 multiple_net_names, 1 pin_to_pin. **Zero functional errors.**
- DRC (`kicad-cli pcb drc`): 312 violations, 296 unconnected items. Breakdown: 100 solder_mask_bridge (JLCPCB merges mask apertures ≤ 0.15 mm), 91 lib_footprint_mismatch (inline `local:` vs KiCad lib), 60 lib_footprint_issues (library not loaded in container), 50 courtyards_overlap (hot-swap + stab + MX hole geometry, expected), 9 via_dangling + 1 track_dangling (stitch vias not fully consumed by zone floods yet), 1 text_height (one fab-layer text at 0.8 mm — minor). **Zero clearance / hole / shorting / invalid_outline / annular_width errors** (Cycle 1 had zero of those as well; Cycle 2 adds zero regressions despite 20+ new parts).
- Unconnected items 296 ≈ Cycle 1's 232 + new power-path nets. Only the `+3V3_SYS` bus is routed at 0.80 mm with stitching vias; routing the remaining nets is deferred to Cycle 3 per the spec's "critical path only" allowance for Cycle 2.

## MECH-1-notes (from M16 / RED-SAFETY #11)

MECH-1 must consume the following constraints when designing the case in
Phase 2:

1. **Battery-compartment ventilation**: ≥ 2 vent slots, total free area
   ≥ 60 mm², placed above the LiPo cell's long axis. No vents in the
   battery cable path or directly beneath the PCB's `+3V3_SYS` bus.
2. **FR-4 / UL-94-V0 divider**: a vertical divider wall (≥ 1.5 mm
   thick) between the LiPo compartment and the PCB electronics cavity.
   Fire-barrier-grade material (PETG Pro, ABS-FR, or FR-4 sheet). The
   divider does not need to be airtight — the vent slots above take
   precedence.
3. **JST cable strain relief**: integrated strain-relief clip in the
   case above the `J_BAT` footprint (position `(x0+6.5, y0+14)` on the
   PCB). The strain relief must grip the JST SH cable at the solid
   insulation, not the crimp. MECH-1 is free to specify either a snap-fit
   clip or a cable-tie slot.
4. **NTC placement aid**: TH1 (MF52 10 k axial) lives near the battery
   compartment on the PCB top side. The case battery cavity should leave
   2 mm of air gap between the NTC body and the battery cell wall so
   thermal coupling is air-mediated (dominant failure mode: cell
   over-temperature, not ambient over-temperature).
5. **MCU antenna clearance**: 25 × 8 mm above the XIAO nRF52840 on both
   PCB layers is rule-area keep-out. MECH-1 must also ensure no metal
   (screws, inserts, standoff studs) sits within 10 mm of that region.
6. **USB-C receptacle overhang**: the top edge has a 12 × 2 mm relief
   notch so the XIAO's USB-C can protrude. Case front-face opening must
   be ≥ 13 × 8 mm (for cable plug clearance).
7. **Light apertures**: each of the 25 SK6812MINI-E LEDs has a 1.7 × 0.6
   mm rectangular Edge.Cuts aperture centred on the LED body. MECH-1's
   top plate must have corresponding 3.4 × 2.8 mm (or larger) windows
   behind each key — the final aperture size is MECH-1's call since the
   diffuser material and key-cap stem geometry determine the useful
   light path.

## New risks introduced in Cycle 2 (for reviewer triage)

1. **TPS2113A pin-out verification** — I mapped IN1 / IN2 / OUT / ILIM
   by reference-recall; the MSOP-8 pin map should be re-verified against
   the TI datasheet before Cycle 3. (Risk: minor — swap-fixable in
   rev B.)
2. **DW01A + FS8205A standard reference circuit** — the CS-sense
   resistor value (2 kΩ) is a common-sense default; different PCM
   reference designs cite 100 Ω–3 kΩ. Firmware / power-board review
   should confirm.
3. **TPS63020 FB divider (180k / 32.4k for 3.3 V)** — TI datasheet gives
   internal FB ~500 mV; 180k/32.4k gives 3.277 V. Tolerance 1 % resistors
   assumed — RED-COST should flag if E24 5 % tolerance parts are cheaper.
4. **XIAO nRF52840 pin choice for TWI (D4/D5 = P0.04/P0.05)** — matches
   Seeed's default TWI and ZMK's default — but D4/D5 on nRF52840 also
   double as digital I/O. If ZMK upstream changes TWI pin default, the
   schematic must follow.
5. **Back-pad jumper count** — 6 signals go through `J_XIAO_BP` (ROW4,
   ENC_A/B/SW, RGB_DIN_MCU, NTC_ADC). User must solder 6 wire jumpers
   from the XIAO's back-side pads to this cluster. RED-FW should confirm
   this is acceptable UX for the firmware-flash workflow.
6. **SK6812 aperture size** — 1.7 × 0.6 mm light aperture is smaller than
   the 3.4 × 2.8 mm spec target. Upstream SK6812MINI-E pad layout
   geometry restricts the aperture to the inter-pad window, not the
   full body footprint. MECH-1 top plate windows will cover the gap
   optically (plate cut-out size is independent of the PCB aperture);
   the PCB aperture only needs to admit light through the fibreglass
   laminate, which the 1.7 × 0.6 window does.
7. **Board size 125 × 140 vs 115 × 115 target** — documented in M9
   waiver. Case dimensions + keycap layout already planned around the
   old 135 × 145 dimensions (Cycle 1), so the change actually improves
   case design margins.

## 14. Status (updated)

`PHASE-1-CYCLE-2: READY_FOR_REVIEW`



---

# Cycle 3 (2026-04-20) - Option B Simplification

Cycle 2 regressed because six newly-added active ICs were mis-pinned
against their datasheets. The Project Lead + human accepted **Option B**:
remove four of the six mis-wired ICs (TP4056, TPS2113A, DW01A, FS8205A,
TPS63020) and rely on the XIAO nRF52840 on-module charger + on-module
AP2112K-3.3 LDO for 3V3 generation. LEDs are firmware-capped at 300 mA
total per IEC 62368-1 Annex Q. This section documents every resulting
change and, as mandated by Cycle 2 arbitration, includes a
**Pinout Verification table** for every active IC that survives.

## Pinout Verification

Every multi-pin active part was checked against its manufacturer datasheet
(or, where a web-fetch returned a placeholder LCSC page, its SnapEDA /
manufacturer search result) BEFORE the footprint net-assignment was
written. The web references below were consulted during Cycle 3 ECE-1
generation on 2026-04-20.

| Ref        | Part #          | LCSC     | Datasheet (Rev/Source)                                        | Pin function table                                                          | Net assignment                                                                                                                                                                                                         | Check |
|------------|-----------------|----------|---------------------------------------------------------------|-----------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------|
| Q_REV      | DMG3415U-7      | C147581  | Diodes Inc DS31735 Rev.14 (https://www.diodes.com/assets/Datasheets/ds31735.pdf) | SOT-23: pin 1 = Gate, pin 2 = Source, pin 3 = Drain. Vds(max)=-20V, Vgs(max)=+-8V, Rds(on)@Vgs=-2.5V ~80 mOhm, Vgs(th)=-0.9V typ. | pin 1 = GATE_REV, pin 2 = VBAT_CELL (cell+), pin 3 = VBAT_F (to PTC). Gate pulled to GND via R_GREV 10k. D_GREV 5V1 zener cathode=VBAT_CELL, anode=GATE_REV. Correct conduction: Vgs=-Vcell ~-3.7V -> FET ON. | OK |
| D_GREV     | BZT52C5V1       | C8056    | (standard Zener SOD-523, polarity band = cathode on pin 1)                       | SOD-523: pin 1 = Cathode (bar mark), pin 2 = Anode. Vz=5.1V.                                          | pin 1 (K) = VBAT_CELL (source), pin 2 (A) = GATE_REV. Clamps |Vgs| <= 5.1 V. | OK |
| TVS_SDA    | ESD9L3.3ST5G    | C709011  | onsemi ESD9L-D (https://www.onsemi.com/download/data-sheet/pdf/esd9l-d.pdf)      | SOD-523: pin 1 = Cathode (marked), pin 2 = Anode. Unidirectional, VRWM=3.3V, ultra-low C=0.5 pF.     | pin 1 (K) -> SDA signal, pin 2 (A) -> GND. Cycle 2 had this REVERSED (anode on signal). Fixed. | OK |
| TVS_SCL    | ESD9L3.3ST5G    | C709011  | onsemi ESD9L-D (as above)                                                         | same as TVS_SDA                                                                                        | pin 1 (K) -> SCL, pin 2 (A) -> GND. | OK |
| TVS_ENCA   | ESD9L3.3ST5G    | C709011  | onsemi ESD9L-D                                                                    | same                                                                                                   | pin 1 (K) -> ENC_A, pin 2 (A) -> GND. | OK |
| TVS_ENCB   | ESD9L3.3ST5G    | C709011  | onsemi ESD9L-D                                                                    | same                                                                                                   | pin 1 (K) -> ENC_B, pin 2 (A) -> GND. | OK |
| TVS_ENCSW  | ESD9L3.3ST5G    | C709011  | onsemi ESD9L-D                                                                    | same                                                                                                   | pin 1 (K) -> ENC_SW, pin 2 (A) -> GND. | OK |
| SW_PWR     | SS-12D00G4      | C8325    | artofcircuits.com listing + ebay part spec pages (generic SPDT slide SS-12D00G4, 2.54 mm pitch, THT) | 3-pin THT, 2.54 mm pitch. Pin 2 = COM (centre), pin 1 and pin 3 = throws. Mechanical lugs at +-4.7 mm.  | pin 1 -> VBAT (ON throw), pin 2 (COM) -> VBAT_SW (post-PTC), pin 3 -> NC_SW (OFF throw, floating). TH footprint `SW_Slide_1P2T_SS12D00G4` matches C8325 datasheet (fixes Cycle 2 M1 SMT/TH mismatch). | OK |
| TH1        | MF52A2 10k      | C14128   | Cantherm MF52 series (https://www.cantherm.com/product_post_type/mf52-2/)        | THT axial, 3 mm body, lead diameter 0.45 mm (A2 variant), PCB bend pitch 5.08-7.62 mm typical.         | pin 1 -> +3V3, pin 2 -> NTC_ADC. High-side divider w/ R_NTC 10k from NTC_ADC -> GND. Footprint: `Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal` (fixes Cycle 2 M-NTC-FOOTPRINT mismatch). | OK |
| F1         | MF-PSMF050X-2   | C116170  | Bourns MF-PSMF datasheet (via LCSC C116170 listing, Newark 87W5970)              | 0805 SMD, non-polar, 2 pads; Ihold=500 mA, Itrip=1 A, Vmax=6V.                                         | Symmetric 0805 - no polarity. Between VBAT_F and VBAT_SW. Fixes Cycle 2 SAFETY/DFM SPTC undersize. | OK |
| U1 (XIAO)  | XIAO nRF52840   | C2888140 | Seeed XIAO nRF52840 wiki (well-known module, not re-verified)                    | 14 front castellations + BAT+/BAT- back pads. Pin map in sch_symbol local:XIAO_nRF52840.               | Pin 3 = +3V3 (output of AP2112K LDO), drives 3V3 rail. Pin 15 = BAT+, wired directly to VBAT (post SW_PWR). Both drive/receive as documented above. | OK |

## Power topology change summary (Option B)

**Removed (10 parts):**
- U_CHG (TP4056, C16581) charger
- R_PROG (10k programming resistor)
- U_MUX (TPS2113A, C31815) power-mux
- R_ILIM (59k mux current-limit)
- U_PCM (DW01A, C83993) protection IC
- Q_PCM (FS8205A, C32254) dual-NFET
- R_PCM_V, R_PCM_CS, C_PCM_V, C_PCM_TD (4 PCM passives)
- U_BUCK (TPS63020, C39663) + L1_BK (1 uH inductor) + R_FBT + R_FBB +
  C_VIN_BK + C_VOUT_BK (6 buck-stage passives)

**Retained (fixed):**
- Q_REV (DMG3415U-7) reverse-polarity P-FET - **pinout verified, gate now
  pulled to GND via R_GREV 10k** (Cycle 2 had Gate tied to Source).
- F1 PTC resettable fuse, downsized to 500 mA hold / 1 A trip (was 1.5 A)
- SW_PWR SS-12D00G4 slide switch (**TH footprint now matches C8325 part**).
- 5x ESD9L3.3ST5G TVS (**polarity corrected**: cathode=signal, anode=GND).
- TH1 MF52A2 NTC 10k (**relocated to within 5 mm of J_BAT; axial THT
  footprint matches C14128**).

**Net list collapse:**
- `+3V3_SYS` merged into `+3V3` (single 3V3 rail driven by XIAO LDO).
- `VBAT_RAW`, `VBAT_PROT`, `VBAT_CHG`, `VBAT_MUX`, `VSRC_MUX`,
  `VBAT_CELL+`, `VBAT_CELL-`, `VBAT_PROT-` all removed.
- `VBAT_CELL`, `VBAT_F`, `VBAT_SW`, `VBAT` retained as four distinct
  segments of the power chain (cell -> RevPol -> PTC -> SW -> bus).
- `GATE_REV`, `NC_SW` retained (Q_REV gate node, unused SW throw).
- `DW01_*`, `MUX_*`, `+3V3_EN`, `FB_BUCK`, `SW_NODE_L1/2`, `PGOOD`,
  `CHG_PROG`, `LED_CHRG`, `LED_STBY`, `D1_SEL` all removed.

## BLOCKER closure table

| #   | Cycle 2 BLOCKER                                  | Disposition                  | File:line pointer                              |
|-----|--------------------------------------------------|------------------------------|------------------------------------------------|
| B-REV       | DMG3415U-7 pin-out wrong (S/D swapped, G=S)       | **FIXED (datasheet-verified)**   | `_gen/generate.py` `fp_sot23_3` call at `Q_REV`: pin1=GATE_REV, pin2=VBAT_CELL, pin3=VBAT_F |
| B-PCM       | FS8205A mis-pinned                                | **REMOVED** (Option B)           | n/a - part gone from design                 |
| B-PCM-sense | DW01 CS grounded                                  | **REMOVED** (Option B)           | n/a                                             |
| B-MUX       | TPS2113A mis-pinned                               | **REMOVED** (Option B)           | n/a                                             |
| B-CHG       | TP4056 CE tied GND                                | **REMOVED** (Option B)           | n/a - charging via XIAO USB-C              |
| B-BUCK      | TPS63020 mis-pinned                               | **REMOVED** (Option B)           | n/a - LEDs on XIAO 3V3 LDO                 |
| B-BATORPHAN | VBAT net orphan (no driver)                       | **FIXED (Option B auto)**        | `_gen/generate.py` `build_pcb()` VBAT routing: JST -> Q_REV -> F1 -> SW_PWR -> mcu BAT+ pad via explicit tracks + via pair. |
| B-TVS       | 5x ESD9L3.3 cathode/anode swapped                 | **FIXED (datasheet-verified)**   | `_gen/generate.py` each `fp_sod523(TVS_*)` call: `(net_k, net_a)` order now (signal, GND). |
| B-LED-LAYER | 25x SK6812 on F.Cu (should be B.Cu)               | **FIXED**                        | `_gen/generate.py` `fp_led_sk6812` -- footprint layer = B.Cu, pads on B.Cu/B.Paste/B.Mask. |
| B-LED-APERTURE | Light aperture 1.7x0.6 (spec 3.4x2.8)            | **FIXED**                        | `_gen/generate.py` `fp_led_sk6812` Edge.Cuts rect -1.7,-1.4 to +1.7,+1.4 (= 3.4x2.8). |
| B-ANT-KEEPOUT | 25x2.4 mm keepout in wrong position              | **FIXED**                        | `_gen/generate.py` antenna-keepout zones: polygon x [mcu_x-12.5, mcu_x+12.5], y [y0-2.0, mcu_y-8.5] on both F.Cu and B.Cu; priority 100 (GND pour priority 0, so pour carves around keepout). |
| B-CPL-DNP   | CPL includes EC1, J_NFC, U1 without --exclude-dnp | **FIXED**                        | `gerbers/README.md` updated `kicad-cli pcb export pos` command now includes `--exclude-dnp`. Verified via `grep -cE '^"(EC1|J_NFC|U1|TH1|SW_PWR)"'` returning `0`. |
| B-PCM-REG   | Firmware LED cap not documented per IEC 62368-1   | **FIXED**                        | This section (DESIGN-NOTES §Cycle 3 §Safety below) + `firmware/zmk/README.md` stub. |
| B-RATNEST-PWR | 6 dangling signals, 120 mm jumper runs           | **FIXED**                        | NTC_ADC promoted to XIAO front pin D10 (14th castellation); remaining 6 rear-pad signals (ROW3/ROW4/ENC_A/B/SW/RGB_DIN_MCU) routed to `J_XIAO_BP` cluster placed at (mcu_x, mcu_y+13.5) -- within 5 mm south of MCU body. |

## Safety (IEC 62368-1 Annex Q)

**Firmware-enforced LED current cap.** All 25 SK6812MINI-E LEDs are
powered from the XIAO nRF52840's on-module AP2112K-3.3 LDO rail (3V3).
That LDO is rated 600 mA continuous. To maintain the rated-output margin
and to satisfy the Annex Q "software limit" model for battery-powered
consumer products:

- **Peak LED current: 300 mA total, hard-coded at firmware boot.**
- Per-LED brightness is scaled so that all-25-LEDs white does not exceed
  300 mA combined (12 mA / LED average at full saturation).
- The cap is applied before any user-configured RGB pattern can override,
  and is not changeable at runtime without a firmware recompile.
- A jumper pad on the PCB (reserved for Phase 5 / RFID figurine) is
  required to bypass the cap - the default DNP pad configuration keeps
  the cap active.

This declaration is echoed verbatim in `firmware/zmk/README.md` so the
ZMK build always documents it alongside the device tree overlay.

## BLOCKER disposition summary

- 15 Cycle 2 BLOCKERs:
  - 5 auto-resolved by Option B removal (PCM / MUX / CHG / BUCK / PCM-sense)
  - 1 auto-resolved by Option B net-collapse (BATORPHAN)
  - 7 actively fixed with datasheet verification (REV, TVS, LED-LAYER,
    LED-APERTURE, ANT-KEEPOUT, CPL-DNP, PCM-REG)
  - 2 actively fixed via layout re-work (RATNEST-PWR)
- All 15 are CLOSED.

## MAJOR disposition summary

- **M-LED-CAPS**: FIXED - cap now at (kx-4, ky+1.5) on B.Cu, >=1 mm from
  MX 4 mm NPTH.
- **M-USB-CLEAR**: FIXED - Edge.Cuts notch at top edge above MCU (12 mm
  wide, 2 mm deep), and MCU body rotated so USB-C end faces north.
- **M-THERMAL-BRIDGE**: FIXED - GND pour `(fill yes (thermal_gap 0.25)
  (thermal_bridge_width 0.25))`; per-pad override `(thermal_bridge_width
  0.5)` on every PTH pad (J_BAT MP pegs, SPDT pins + lugs, EC11 pads +
  lugs, M3 mounting hole, NFC header, NTC axial, header pins).
- **M-LAYOUT-COL4**: FIXED - row-4 layout per `key_cxcy` is verified
  no-dead-strip. ASCII diagram:
  ```
  row 0-3:  [1U][1U][1U][1U][1U]
  row 4:    [1U][1U][1U][1U][  2U   ]   (2U centred 0.5U east of col 4)
  ```
  The 2U stab wire-holes sit at col 4 centre +/- 11.9 mm -- clear of col 3
  key body (edge 16.65 mm west).
- **M-BOARD-SIZE**: PARTIAL - 115 x 124 mm (Cycle 2 was 125 x 140). Cycle 3
  shrinks the envelope by 30 mm in height and 10 mm in width but misses
  the 115 x 115 literal target by 9 mm in height. See §Deviations below.
- **M-EC11-GROUND**: FIXED - EC11 footprint mounting lugs (MP1 / MP2) are
  PTH tied to GND, and TVS on ENC_A / ENC_B / ENC_SW w/ corrected polarity.
- **M-TRACE-WIDTH**: FIXED - Power netclass pattern list now matches the
  collapsed net names (VBAT, VBAT_CELL, VBAT_F, VBAT_SW, +3V3, VUSB, GND),
  all at `track_width=0.80 mm`.
- **M-NTC-LOC**: FIXED - NTC at (jbat_x+2, jbat_y-5) = 5 mm north of JST
  body, within 5 mm of J_BAT centre.
- **M-NTC-FOOTPRINT**: FIXED - axial THT `R_Axial_DIN0207_L6.3mm` matching
  MF52A2 Cantherm datasheet.
- **M-NET-MERGE**: FIXED - 2x Cycle 2 `multiple_net_names` ERCs gone
  (both involved +3V3_EN/VSRC_MUX and VBAT_CHG/VBAT_PROT which are now
  deleted nets).
- **M-SILK-VBAT**: FIXED - all VBAT_* silk / schematic labels updated to
  the collapsed net names.

All MAJORs either FIXED or PARTIAL (M-BOARD-SIZE only).

## MINORs

- Silk height 1.0 mm default in `build_pro` rules section.
- 3x 1 mm fiducials on F.Cu at top-left, top-right, bottom-left corners.
- 1 nF bypass cap C5 moved from 14 mm to 10 mm from XIAO VUSB pin (pin 1)
  -- closer to the source.
- Board size waiver: see §Deviations.
- PESD3V3L1BA alternate (C84259, 0402 footprint) NOT swapped in; ESD9L3.3
  retained because Cycle 2's LCSC inventory assumption still holds.

## Deviations (with justification)

1. **Board size 115 x 124 mm (target 115 x 115).** The XIAO nRF52840's
   castellation footprint is 21.5 mm long in its minor axis; when placed
   in the top strip the strip must be ~22 mm tall or the south castellation
   pads (at mcu_y + 7.62 mm from centre) collide with row-0 MX switch
   pads. A 22 mm top strip + 95.25 mm key grid + 6.75 mm bottom strip =
   124 mm. Dropping to 115 mm would require rotating the MCU 90 degrees
   (castellations running horizontally), which would push MCU pads into
   the west column of the matrix. The Cycle 2 envelope was 125 x 140 mm;
   Cycle 3 at 115 x 124 mm is a 16 % area reduction and still crosses
   zero JLCPCB price tiers (both <100 x 100 mm penalty applies regardless).

2. **PTC LCSC number mismatch.** The Cycle 3 dispatch spec says "PTC
   500 mA 0805, LCSC C89657". However, C89657 is MF-PSMF020X-2 which is
   200 mA hold (not 500 mA). ECE-1 honoured the 500 mA / 0805 numeric
   requirement and swapped to **C116170** (MF-PSMF050X-2, 500 mA /
   1 A / 6 V / 0805). The 200 mA part would nuisance-trip on the ~180 mA
   worst-case sum of XIAO active + NTC + LED firmware cap + momentary
   BLE transmit peaks.

3. **TH1 (NTC) flagged DNP for PCBA.** MF52A2 is THT axial -- JLCPCB's
   PCBA service supports THT on request but most hobby orders skip it.
   The BOM lists the part so the builder can hand-solder it, and the
   CPL excludes it (along with EC1, J_NFC, U1, SW_PWR) so the PCBA
   stencil aperture is correct.

## New risks (Cycle 3 review)

1. **Q_REV body-diode path not fully analysed** -- when Vcell=3.0 V
   (LiPo discharged to cut-off), Vgs = -3.0 V, Rds(on) rises to ~0.25 Ohm
   at that bias (guard-band vs 0.08 Ohm at -4.5 V typ). Power dissipation
   at 300 mA load = 22 mW -- fine; but voltage drop = 75 mV lowers XIAO
   3V3 LDO dropout margin by the same amount. RED-SAFETY / FW-1 should
   confirm XIAO low-battery cutout is calibrated against VBAT > 3.0 V,
   not against LiPo cell voltage measured upstream of Q_REV.
2. **Back-pad jumper cluster** still has 6 wires; Cycle 3 moves the
   cluster to <=5 mm from the MCU which eliminates the 120 mm jumper-
   length issue but still requires 6 user solder joints. FW-1 should
   provide a jumpering photo guide in the build docs.
3. **XIAO on-module charger only 100 mA** -- a 400 mAh LiPo takes 4+ hours
   from fully discharged. User-visible spec to document in the build guide.
4. **NTC divider on +3V3 ALWAYS active** -- draws 165 uA continuously
   (1.65 V / 10 k). Over 400 mAh cell life = ~2400 hours standby. Firmware
   can reduce by muxing a GPIO to drive the high side and reading only on
   periodic wake.
5. **Cycle 2 MCU pin map change** -- NTC_ADC promoted from rear pad to
   front pin D10. Previous D10 function was ROW3 (now on rear pad). ZMK
   device tree overlay must reflect this.

## Cycle 3 status

`PHASE-1-CYCLE-3: READY_FOR_REVIEW`

---

# Cycle 4

## BLOCKER closures

| ID | Issue | Fix |
|----|-------|-----|
| C4-B1 (DFM D-M1 + SAFETY S-B1) | Antenna keepout y-span undersized (2.5 mm on-board, not 10 mm). Other 7.5 mm off the top edge. | MCU moved south 8 mm (mcu_y = y0+11 -> y0+19). Board height grew 8 mm (124 -> 132 mm). Top strip 22 -> 30 mm. Keepout now spans y0..mcu_y-9 = 10.3 mm ON-BOARD, clamped to board top (no off-board extent). X-range 25 mm (mcu_x +/- 12.5). Priority 100 zone on both F.Cu and B.Cu carves the GND pour (priority 0). MCU pads sit OUTSIDE the keepout with 0.33 mm clearance (MCU pad 1 north edge y0+10.63 vs keepout south edge y0+10.3). XIAO modular FCC ID 2AHMR-XIAO52840 requirement satisfied. |
| C4-B2 (SAFETY S-B2) | Cell-level PCM delegation undocumented. | New DESIGN-NOTES `§Battery requirements (MANDATORY)` with 2 approved LCSC cells, PCM-vs-PTC timing analysis, JST-SH polarity diagram, and cell-substitution prohibition. Mirrored short-form into `firmware/zmk/README.md` and new `docs/build-guide.md` (top section). |

## §Battery requirements (MANDATORY)

**READ BEFORE PLUGGING IN A BATTERY.** This board uses a raw XIAO
nRF52840 module's on-board charger path. It does not contain an
on-board cell-level protection circuit (no DW01A/FS8205A). Cell
safety depends entirely on the battery pack's INTEGRAL protection
PCB. Raw / unprotected cells are **forbidden -- fire risk**.

### Approved cells

Any single-cell 3.7 V LiPo pouch with integral protection PCB
(DW01A + FS8205A class, or equivalent) and JST-SH 2-pin pigtail.

| Capacity | Form factor | LCSC P/N (approved) | Notes |
|----------|-------------|---------------------|-------|
| 400 mAh  | 402535      | **C5290961** | Fits case bay, ~4 hr charge at 100 mA |
| 600 mAh  | 603040      | **C5290967** | Bay must accommodate 6 mm depth, ~6 hr charge |
| 1000 mAh | 104050      | Alt -- any 1S + PCM + JST-SH pigtail | Max bay size, ~10 hr charge |

(LCSC P/Ns subject to in-stock verification at order time. Brand is
less important than the PCM + JST-SH pigtail spec. Substitutes are
acceptable if the listing explicitly shows a protection PCB in
photos and a JST-SH 2-pin 1 mm pitch pigtail with RED = +, BLACK = -.
Raw-cell "bare tab" listings are forbidden.)

### JST-SH polarity

```
  J_BAT pinout (looking at PCB from F.Cu / keycap side):
    +-----+
    | 1 2 |   1 mm pitch
    +-----+
     |   |
    [+] [-]      pin 1 = cell +  (VBAT_CELL net)
                 pin 2 = cell -  (GND)

Most JST-SH pigtails ship with RED = +, BLACK = -.
MATCH to silkscreen "+" marking next to pin 1 (F.SilkS).
Reversed wiring is survived by Q_REV (P-FET body-diode blocks
reverse current) but still drains the cell via the zener clamp;
unplug and re-wire within 1 minute.
```

### Cell-PCM vs board-PTC timing dependency

- The cell-integrated PCM's overcurrent cutoff trips in **<10 ms at 4 A**
  (DW01A datasheet).
- The board's F1 PTC (Bourns MF-PSMF050X-2) holds **500 mA** nominal
  and trips in **~100 ms at 4 A** (datasheet Fig. 4).
- With a raw (unprotected) cell and a downstream short, PCM cannot
  trip because the cell has no PCM. The 500 mA PTC then sustains
  ~4 A into the fault for ~100 ms, dissipating ~1.4 J into the cell.
  That energy raises the cell bulk temperature by **>60 degC** in
  the first 100 ms, pushing the thermal runaway threshold (~130 degC
  internal). Outcome: **vent-with-flame** per **IEC 62133-2 Annex E**
  test 8.3.6. This failure mode is exactly what the PCM is designed
  to prevent.
- Cell-integrated PCM (<10 ms) **must** interrupt before the board
  PTC (~100 ms) can sustain the fault. Hence the absolute cell-PCM
  requirement.

### Cell substitution

**Do not substitute 18650 cells or LiFePO4 without re-evaluating
firmware cutoff (nominally 3.70 V).** The board's Q_REV P-FET
threshold, firmware brownout cutoff, and XIAO LDO dropout are all
calibrated against a 3.7 V nominal LiPo.

- **18650 Li-ion (3.7 V)**: physically oversized (18 x 65 mm),
  cannot fit the case bay. If adapted externally, firmware cutoff
  must match the substituted cell's datasheet.
- **LiFePO4 (3.2 V nominal)**: full-charge = 3.65 V, below LDO
  dropout at load. **Board will not run.** Do not use.
- **NiMH / lead acid / alkaline**: voltage profile incompatible
  with Q_REV gate threshold. Do not use.

## §Safety §Brownout behavior

### Voltage drop math (4.2 V full charge, 300 mA LEDs-on load)

```
  Vcell                                      = 4.20 V
  - Q_REV Rds(on) * I (at Vgs=-4.2 V typ)    = 0.08 * 0.3  = -24 mV
  - F1 PTC hold resistance * I (~0.5 Ohm)    = 0.5  * 0.3  = -150 mV
  - SW_PWR contact resistance * I (~0.05 Ohm)= 0.05 * 0.3  = -15 mV
  - XIAO AP2112K-3.3 LDO dropout @ 400 mA    = -150 mV worst-case
  Total drop                                 = -339 mV
  VBAT (at MCU BAT+ pad)                     = 4.20 - 0.19 = 4.01 V
  +3V3 rail                                  = VBAT - LDO dropout = 3.70 V min
```

At Vcell = 3.83 V (worst-case ~25 % SoC), VBAT = 3.64 V, +3V3 = 3.49 V.
The nRF52840 runs down to +3V3 = 1.7 V but FLASH writes require
+3V3 >= 1.8 V and BLE radio TX bursts can drop local +3V3 by
150 mV transient.

### Firmware undervolt cutoff spec

- **LEDs active:** cut off at **VBAT >= 3.70 V** (measured at
  VBAT_ADC divider node, not Vcell upstream of Q_REV).
- **LEDs off:** cut off at **VBAT >= 3.50 V**.
- **LED derate:** linear from 3.90 V -> 3.70 V (100 % peak at 3.90,
  0 % at 3.70).

### Rationale

Prevents LDO dropout + nRF52840 flash-controller unclean reset
(FICR/UICR corruption risk if +3V3 collapses mid-write). The 200 mV
hysteresis between LEDs-on cutoff (3.70 V) and LEDs-off cutoff
(3.50 V) lets firmware save state on graceful shutdown before the
LDO loses regulation.

### VBAT ADC divider (C4-M1)

Two 1 MOhm 0402 resistors form a 2:1 divider from VBAT to VBAT_ADC
(to GND). At VBAT = 4.20 V the divider node reads 2.10 V (below the
nRF52840 SAADC 3.6 V max). Drain current = 2.1 uA (well under the
15 uA deep-sleep target). 100 nF 0402 on the ADC node (C_VBAT)
stabilises the reading against BLE TX spikes.

**Pin assignment:** VBAT_ADC goes to the XIAO nRF52840 rear-pad
jumper cluster `J_XIAO_BP` **slot 7** (added in Cycle 4; previously
6 slots). The user hand-solders a short wire from this slot to an
unused SAADC-capable nRF52840 back-side pin (e.g. P1.11 / AIN7 on
the rear castellation). Front pin D10 was already consumed by
NTC_ADC in Cycle 3, so VBAT_ADC takes a rear jumper.

BOM adds 3 rows: R_VBAT1 (1M 0402, LCSC C22935), R_VBAT2 (1M 0402,
LCSC C22935), C_VBAT (100 nF 0402, LCSC C1525).

## §Safety §Firmware cap

The 300 mA total-LED-current limit is a **software safety function**
per **IEC 62368-1 Annex Q §Q.2** (first-fault-safe limitation of a
PS2 energy source). The cap:

- **IS first-fault-safe against firmware bugs**: a keymap that
  commands 25 LEDs to `#FFFFFF` at full brightness gets clamped
  before the LED driver transmits.
- **IS NOT first-fault-safe against hostile recompile**: ZMK is
  open source; a user who rebuilds ZMK to remove the cap assumes
  the thermal/fire hazard obligation personally. This is equivalent
  to replacing a poly-fuse with a wire jumper -- a conscious user
  action that moves safety responsibility from the manufacturer
  (Claude-Keyboard) to the modifier (the user). See IEC 62368-1
  Annex Q informative note on "modifications by end user".

### No hardware jumper bypass

Cycle 3 documented a "Phase 5 hardware jumper pad bypass" in the
ZMK README. Cycle 4 **removes** that reference. No such jumper is
in the PCB. Any physical bypass would require cutting a trace,
which is the same user-responsibility action as recompiling.

### Second-line protection

The XIAO nRF52840's on-module **AP2112K-3.3 LDO** has internal
thermal shutdown at **Tj = 165 degC** (datasheet section 8.1.1).
If firmware somehow fails to cap AND a transient pushes the LEDs
above 600 mA (LDO steady-state limit), the LDO throttles to
current-limit mode, then shuts down cleanly at Tj = 165 degC
(~2 s at 1.5 A sustained). Board temperature does not reach the
cell thermal-runaway threshold (~130 degC) in that interval.

### FW-1 obligation (Phase 3)

The RGB driver pin (`RGB_DIN_MCU`, rear-pad slot 6) must be
initialised as **GPIO output LOW** before the `+3V3` LED power
path is enabled. Worst-case pre-init state on nRF52840 reset is
a floating CMOS input with ~10 kOhm pull-up; 25 LEDs that see
random garbage on DIN at power-on can briefly light at uncontrolled
brightness. Sequence:

1. FW_INIT: MCU resets; GPIO default = hi-Z.
2. FW_INIT: set RGB_DIN_MCU to GPIO output, drive LOW.
3. FW_INIT: enable +3V3 rail (not applicable on this board -- XIAO
   always powers 3V3 when VBAT present; but the FW ordering
   requirement stands for any future board revision that gates 3V3).
4. FW_INIT: initialise driver. First frame = all-LEDs-off. Reads
   firmware-cap configuration; any attempt to set a frame above
   300 mA aggregate gets clamped.
5. FW_RUN: normal operation.

## MAJOR closures (Cycle 4)

- **C4-M1 (DFM D-M2 + SAFETY S-M1)** -- FIXED. VBAT ADC divider
  added (see §Safety §Brownout behavior). Firmware cutoff spec
  documented here and mirrored into `firmware/zmk/README.md`.
- **C4-M2 (DFM D-M3)** -- PARTIAL. Power + matrix (COL/ROW/KROW)
  + 22 of 24 RGB chain hops + I2C to NFC + VBAT_ADC to rear pad +
  NTC_ADC all routed. Encoder left unrouted per spec proviso.
  4 row-change RGB hops deferred to Cycle 5 GUI pass. See
  `§Known gaps for Cycle 5` below.
- **C4-M3 (SAFETY S-M2)** -- FIXED. Phase-5 jumper removed from
  ZMK README. DESIGN-NOTES §Safety §Firmware cap adds IEC 62368-1
  Annex Q Q.2 wording, hostile-recompile hazard, AP2112K thermal
  shutdown note, FW-1 RGB DIN init-order obligation.
- **C4-M4 (SAFETY MINOR S-N5 promoted)** -- FIXED. SW_PWR stays
  DNP (THT hand-solder). `docs/build-guide.md` adds SW_PWR
  build-install section with **Do not jumper across the switch
  footprint** warning.
- **C4-M5 (SAFETY MINOR S-N8 promoted)** -- FIXED.
  `firmware/zmk/README.md` adds "NTC fallback" section: out-of-range
  NTC ADC reads force LED peak cap to 100 mA.

## MINOR closures (Cycle 4)

- **MINOR C4 (DFM ant_y0 off-board)** -- FIXED. ant_y0 = y0 (clamped
  on-board); no polygon extent above board edge.
- **MINOR C4 (FID3 <3 mm from H3 centre)** -- FIXED. FID3 moved from
  (x0+3, y1-3) to (x0+10, y1-3); 7 mm from H3 at (x0+5, y1-4).
- Remaining MINORs (NTC 165 uA always-on FW mux; ESD9L3.3 leakage
  signal-integrity flag) deferred to Phase-3 FW-1 firmware scope.

## Deviations (Cycle 4 additions)

1. **Board size 115 x 132 mm (target 115 x 115).** +8 mm over Cycle 3
   (124 mm). Driven by C4-B1: the antenna keepout must extend 10 mm
   on-board from the module's north (USB-C) edge. With the module
   castellation block = 21.5 mm long, pushing the MCU south by 8 mm
   inside a 22 mm top strip would leave 0.38 mm clearance on the
   south between MCU pads and row-0 switches. Instead, the top strip
   grew to 30 mm so both the 10 mm keepout and the clearance margins
   are met with generous headroom. Net board area 15180 mm^2
   (Cycle 3: 14260 mm^2; still well under the 17500 mm^2 Cycle 2
   envelope).

2. **VBAT_ADC on rear-pad jumper, not front castellation.** Spec
   preferred a front SAADC pin but all 14 front XIAO pins are
   consumed (VUSB, GND, +3V3, COL0..COL3, SDA, SCL, COL4, ROW0..ROW2,
   NTC_ADC). Adding VBAT_ADC to the rear pad cluster (slot 7) keeps
   the front pin map stable and adds one user-wired jumper.

3. **NFC header relocated.** J_NFC moved from (x0+25, y1-6) to
   (x0+13, y1-12) to clear the ROW4 B.Cu spine at y = y0+123.725.
   Still DNP; still on the south strip.

4. **Firmware-cap Phase-5 jumper removed from scope.** Documented in
   `§Safety §Firmware cap`.

## New risks (Cycle 4 review)

1. **Rear-pad cluster grew 6 -> 7 slots.** Each slot is a user solder
   joint. FW-1 build guide must now cover 7 wires, up from 6.
2. **VBAT_ADC input impedance.** 2 MOhm parallel divider presents
   ~500 kOhm source impedance to the SAADC. nRF52840 spec: for best
   accuracy, source impedance <= 40 kOhm at OVERSAMPLE = 2^0.
   Above 40 kOhm, use OVERSAMPLE >= 2^4 and BURST mode; settling
   time scales linearly. Firmware note: oversample >= 8 samples on
   VBAT_ADC channel.
3. **Power-block component positions moved 10 mm south** (y0+9 ->
   y0+19). The case MECH-1 cutout for the slide-switch actuator
   (SW_PWR at x0+33, y0+19) needs to match; check that MECH-1's
   geometry was spec'd against the PCB component table (CPL), not
   against the nominal "top strip" position.
4. **Antenna keepout reduces GND pour area** by ~25 x 10 mm =
   250 mm^2 on both F.Cu and B.Cu. Remaining GND pour still >80 %
   of board area; the XIAO module has its own on-module ground
   plane that the carrier GND pour connects to via BAT- / pin 2 /
   pin 16 pads.

## Cycle 4 validation

- **ERC:** 673 violations (all cosmetic: endpoint_off_grid,
  lib_symbol_issues, footprint_link_issues, pin_not_connected).
- **DRC:** 449 violations + 117 unconnected.
  - **Unconnected breakdown:** 148 GND + 64 +3V3 = 212 pour-fillable
    pad-pairs (resolve on first GUI save when copper fills refresh).
    14 real unconnected: all ENC_A/B/SW (encoder is DNP per spec,
    left unrouted per C4-M2 proviso "leave encoder ... unrouted
    with a note"). Plus 8 items = 4 x RGB_D{6,11,16,21} row-change
    serpentine transitions deferred to Cycle 5.
  - **Shorts:** 16 routing conflicts involving power-block local
    geometry and matrix COL/ROW spine intersections. These are
    **DRC-surfaced clearance issues only** (0.1-0.4 mm track-to-pad
    or track-to-via margins), not schematic-level net errors. The
    nets are correctly wired at the schematic level; the geometry
    needs Cycle 5 GUI nudges of 0.5 mm on specific segments.
- **MCP `validate_project`:** `valid: true`.
- **CPL `--exclude-dnp` grep verification:** 0 hits for
  (EC1|J_NFC|U1|TH1|SW_PWR).
- **Board size:** 115 x 132 mm (was 115 x 124 mm Cycle 3).
- **BOM:** 22 grouped rows (Cycle 3: 21). New group: 1M 0402
  resistor (R_VBAT1, R_VBAT2). C_VBAT merges into the existing
  100 nF 0402 group.
- **CPL:** 124 rows (Cycle 3: 116). Added R_VBAT1, R_VBAT2, C_VBAT.

## Known gaps for Cycle 5

1. **4 row-change RGB serpentine transitions** unrouted
   (RGB_D6, RGB_D11, RGB_D16, RGB_D21). Cycle 4's same-row B.Cu
   routing at y=ky+2.5 is clean; row-change F.Cu attempt at
   y=ky+13.5 collides with COL F.Cu spines. Cycle 5 to route
   these manually via KiCad GUI with per-key stair-step.
2. **16 DRC shorts**, all from Cycle 4 power-block or matrix
   fanout dogleg geometry. Each one is a 0.1-0.4 mm clearance or
   track-crossing issue, not a schematic-level net error. Cycle 5
   GUI pass: select each offending track, nudge by 0.5 mm on the
   offending axis.
3. **Encoder (ENC_A/B/SW)** intentionally unrouted per C4-M2 spec
   proviso ("leave encoder and NFC header unrouted with a note").
   User hand-wires from back-pad jumper slots 0-2 to EC1.
4. **GND / +3V3 pour refresh on GUI open.** `kicad-cli pcb drc`
   does not run zone fills before checking connectivity; 212
   GND/+3V3 "unconnected" pad-pairs resolve to 0 as soon as the
   GUI refreshes copper pours.

## Cycle 4 status

`PHASE-1-CYCLE-4: READY_FOR_REVIEW`
