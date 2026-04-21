# Claude Code Pad - ZMK firmware scaffolding

**Phase 1 Cycle 4 placeholder.** ECE-1 owns the PCB through Phase 1;
FW-1 will populate this directory with the full ZMK device tree overlay
and keymap in Phase 3. This stub exists to document the Hard Requirements
that the hardware design depends on.

---

## Hard Requirement: Approved cells

**DO NOT plug in a raw / unprotected LiPo cell. Fire risk.**

Only single-cell 3.7 V LiPo packs with INTEGRAL protection PCB
(DW01A + FS8205A class) and JST-SH 2-pin pigtail are approved.
Approved LCSC part numbers (subject to in-stock verification):

- **C5290961** -- 400 mAh 402535 LiPo + PCM + JST-SH
- **C5290967** -- 600 mAh 603040 LiPo + PCM + JST-SH

Full list, polarity diagram, PCM-vs-PTC timing analysis, and cell
substitution rules live in `pcb/DESIGN-NOTES.md` **§Battery
requirements (MANDATORY)**. The short version:

- Cell-integrated PCM trips at <10 ms @ 4 A (DW01A spec).
- Board F1 PTC trips at ~100 ms @ 4 A (500 mA hold).
- Raw cell through 500 mA PTC into a 4 A fault sustains for ~100 ms;
  cell dT > 60 degC -> vent-with-flame per IEC 62133-2 Annex E.
  The cell PCM is what prevents this.

---

## Hard Requirement: Battery Cutoff Voltage

Firmware **must** implement undervolt cutoff measured at the VBAT_ADC
divider (NOT at Vcell upstream of Q_REV):

| LED state       | Cutoff VBAT |
|-----------------|-------------|
| LEDs active     | **3.70 V**  |
| LEDs off        | **3.50 V**  |
| LED peak derate | linear 3.90 V -> 3.70 V (100 % -> 0 %) |

**Rationale:** prevents XIAO AP2112K-3.3 LDO dropout and nRF52840
flash-controller unclean reset (FICR/UICR corruption risk if +3V3
collapses mid-write). The 200 mV hysteresis between 3.70 V and
3.50 V lets firmware save state on graceful shutdown before the
LDO loses regulation.

**Measurement:** VBAT_ADC = VBAT / 2 (2x 1 MOhm resistor divider,
100 nF ADC anti-alias cap). Source impedance ~500 kOhm -- firmware
must use nRF52840 SAADC **OVERSAMPLE >= 2^3** (8 samples) and
BURST mode when reading VBAT_ADC.

**Pin:** VBAT_ADC is on XIAO back-side rear-pad jumper slot 7
(NEW in Cycle 4 -- see pin map below). User solder-wires from
J_XIAO_BP slot 7 to an unused SAADC-capable back-side pin
(e.g. P1.11 / AIN7).

Full math and derivation in `pcb/DESIGN-NOTES.md §Safety §Brownout
behavior`.

---

## Hard Requirement: LED peak current cap

Firmware **must** cap total RGB LED peak current at **300 mA**.

This is per **IEC 62368-1 Annex Q §Q.2** (first-fault-safe limit
of a PS2 energy source). The XIAO nRF52840 module's on-board
AP2112K-3.3 LDO drives all 25 SK6812MINI-E LEDs; the LDO is rated
600 mA steady-state. Running 25 LEDs at full white nominal would
draw ~1.5 A and either trigger the LDO thermal shutdown (good) or
eventually fail open-drain (bad). Our PCB design has NO redundant
3V3 regulator; the 300 mA cap is the primary safety enforcement.

### Implementation requirements

- The cap MUST be applied at `driver_init()` time, before any user
  RGB effect can load.
- The cap MUST NOT be runtime-configurable via ZMK Studio, the
  keymap, or any characteristic over BLE.
- The per-LED PWM value is scaled such that the sum across all 25
  LEDs at any instant is <=300 mA (worst case = ~12 mA/LED at full
  white; colour-mixed animations may run higher per-LED but stay
  within the 300 mA aggregate via the driver's dithered-power model).

### Scope boundary (hostile recompile)

This cap is first-fault-safe against firmware **bugs**, not against
a deliberate recompile. Users who rebuild ZMK to remove the cap
assume the thermal/fire hazard obligation personally. See
`pcb/DESIGN-NOTES.md §Safety §Firmware cap` for the IEC 62368-1
Annex Q language.

**No hardware jumper bypass exists on this board.** (Cycle 3
documented a "Phase-5 hardware jumper" for future use; Cycle 4
removes that reference -- no such pad is on the PCB.)

### RGB driver init order (FW-1 obligation)

Before enabling the `+3V3` LED power path, firmware **must** drive
the `RGB_DIN_MCU` pin as GPIO output LOW. Worst-case pre-init
nRF52840 GPIO state is floating CMOS input with ~10 kOhm pull-up;
25 LEDs seeing random data on DIN at power-on could briefly light
at uncontrolled brightness. Sequence:

1. MCU reset -> GPIO default hi-Z.
2. Set `RGB_DIN_MCU` as GPIO output, drive LOW.
3. Enable +3V3 rail (on this board it's always on when VBAT is
   present; requirement still stands for future board revisions).
4. Initialise WS2812 driver with first frame = all-LEDs-off;
   apply 300 mA firmware cap to every subsequent frame.
5. Enter normal operation.

### Second-line protection

If firmware cap fails AND a transient demands >600 mA, the XIAO
AP2112K-3.3 LDO's thermal shutdown (Tj = 165 degC, ~2 s at 1.5 A)
catches it. Board temperature does not reach the cell thermal
runaway threshold (~130 degC) within that interval.

---

## Hard Requirement: NTC fallback

If the NTC ADC channel (NTC_ADC, XIAO pin D10 / P0.03) reads
**out-of-range** (floating input -- typical when TH1 is not
hand-installed, or a wire break on the axial thermistor), firmware
**must**:

- Reduce the LED peak cap from 300 mA to **100 mA** until a valid
  temperature reading resumes.

Behavior documented to satisfy **IEC 62368-1 Annex Q** fallback
requirements for a degraded thermal-sensing subsystem. "Out of
range" = ADC reads either < 0.1 V (short-to-GND / wire break) or
> 3.1 V (short-to-+3V3).

---

## Pin map (Cycle 4)

See `pcb/DESIGN-NOTES.md` for the canonical pin-to-net mapping.
Cycle 4 changes vs Cycle 3:

- `VBAT_ADC` is a **new** signal on `J_XIAO_BP` rear-pad **slot 7**
  (cluster grew from 6 pads to 7). ZMK device-tree SAADC bindings
  must add this channel. Firmware connects the slot via user-solder
  wire to an unused XIAO nRF52840 back-side SAADC-capable pin
  (P1.11 / AIN7 recommended).
- Rear-pad cluster slot numbering re-ordered so ROW3/ROW4 don't
  align with COL F.Cu spine x-coordinates. New mapping:

| Slot | x (mm) | Signal    |
|------|--------|-----------|
| 1    | 151.5  | ENC_A     |
| 2    | 153.5  | ENC_B     |
| 3    | 155.5  | ENC_SW    |
| 4    | 157.5  | ROW3      |
| 5    | 159.5  | ROW4      |
| 6    | 161.5  | RGB_DIN_MCU |
| 7    | 163.5  | VBAT_ADC  |

Other Cycle 3 changes still apply:

- `NTC_ADC` on D10 / P0.03 (front pin 14). Unchanged.
- 6 (now 7) rear-side signals require user-wire jumpers to the
  corresponding XIAO back-side GPIOs. See `docs/build-guide.md`
  for the photo guide.
