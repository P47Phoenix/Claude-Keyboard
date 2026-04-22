# Claude Code Pad - ZMK firmware scaffolding

**Phase 1 Cycle 5 placeholder.** ECE-1 owns the PCB through Phase 1;
FW-1 will populate this directory with the full ZMK device tree overlay
and keymap in Phase 3. This stub exists to document the Hard Requirements
that the hardware design depends on.

---

## Hard Requirement: Approved cells

**DO NOT plug in a raw / unprotected LiPo cell. Fire risk.**

Only single-cell 3.7 V LiPo packs with INTEGRAL protection PCB
(DW01A + FS8205A class) and **JST-PH 2.0 mm** 2-pin pigtail are
approved. Cycle 5 migrated `J_BAT` to JST-PH (up from a 1.0 mm pitch
spec in earlier cycles) because the protected-1S-LiPo ecosystem
(Adafruit, SparkFun, Pimoroni) uses JST-PH; 1.0 mm pitch cells with
integrated PCMs are not routinely stocked.

**Cycle 4 carried two hallucinated LCSC SKUs (C5290961, C5290967).**
Both return HTTP 404. **Do not attempt to source those part numbers.**
Cycle 5 replaces them with the following HTTP-200-verified SKUs:

| Source | Link | Capacity | PCM? | JST |
|--------|------|---------:|------|-----|
| Adafruit | [#1578](https://www.adafruit.com/product/1578)   | 500 mAh  | yes | PH |
| Adafruit | [#3898](https://www.adafruit.com/product/3898)   | 400 mAh  | yes | PH |
| Adafruit | [#328](https://www.adafruit.com/product/328)     | 2500 mAh | yes | PH |
| SparkFun | [PRT-13851](https://www.sparkfun.com/products/13851) | 400 mAh | yes | PH |
| Adafruit | [#1317](https://www.adafruit.com/product/1317)   | 150 mAh  | yes | PH |

Full polarity diagram, PCM-vs-PTC timing analysis, and cell
substitution rules live in `pcb/DESIGN-NOTES.md §Battery
requirements (MANDATORY)` and `§Cycle 5 §Verified procurement table`.
Short version:

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

**Rationale (C5-M4 reconciled):** cutoff fires near **30-35 % SoC**
to preserve LDO dropout headroom for the AP2112K 3V3 LDO. This is
intentional -- the useful cell range is the top 65-70 % of nominal
capacity. A cell at 3.70 V under 300 mA LED load sits at ~3.60 V at
the VBAT node (100 mV Rds(on) + PTC drop) and feeds the LDO with
~0.30 V of dropout headroom, well above the 0.25 V AP2112K minimum.
The 200 mV hysteresis between 3.70 V (LEDs-on) and 3.50 V (LEDs-off)
lets firmware save state on graceful shutdown before the LDO loses
regulation.

(Cycle 4 claimed "cutoff fires at ~25 % SoC"; that math was
inconsistent with the 3.70 V trip point. Cycle 5 retracts that
figure.)

**Measurement:** VBAT_ADC = VBAT / 2 (2x 1 MOhm resistor divider,
100 nF ADC anti-alias cap). Source impedance ~500 kOhm -- firmware
must use nRF52840 SAADC **OVERSAMPLE >= 2^3** (8 samples) and
BURST mode when reading VBAT_ADC.

**Pin:** VBAT_ADC is on XIAO back-side rear-pad jumper **slot 5**
(patch_x+4, Cycle 5 slot reassignment). User solder-wires from
`J_XIAO_BP` slot 5 to an unused SAADC-capable XIAO back-side pin
(P1.11 / AIN7 recommended).

---

## Hard Requirement: VBAT_ADC integrity (broken-wire detection) [C5-M5]

The VBAT_ADC cut-off above is the graceful-shutdown tripwire. Because
the ADC line is a **hand-soldered jumper wire** from the rear-pad
slot to a back-side GPIO, a broken wire leaves the ADC floating and
reads garbage -- firmware would never trip the cut-off and the cell
would be over-discharged to cell-damage levels.

Firmware **must** detect a broken VBAT_ADC jumper and fail safe:

- Sample VBAT_ADC eight consecutive times at the normal sampling
  cadence (SAADC OVERSAMPLE>=2^3, BURST mode).
- Compute **variance** over the 8 samples. If variance > 100 mV,
  the wire is likely broken (floating input picks up 50/60 Hz hum
  and noise).
- Compute **instantaneous step** between each sample pair. If any
  step exceeds +/- 0.3 V, the wire is likely broken (a real cell
  cannot change voltage that fast under 300 mA load).
- If EITHER condition triggers, enter the **SAME** graceful-shutdown
  path as the 3.50 V undervoltage cutoff: disable all LEDs, log
  warning, advertise "critical battery / sensor fault" BLE state,
  and reduce BLE activity to minimum.

This fail-safe cannot be disabled at runtime.

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
removed that reference -- no such pad is on the PCB.)

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

## Pin map (Cycle 5)

See `pcb/DESIGN-NOTES.md §Cycle 5 §Routing topology summary` for the
canonical pin-to-net mapping. Cycle 5 rear-pad slot reassignment:

| Slot | Signal      |
|------|-------------|
| 0    | ENC_A       |
| 1    | ENC_B       |
| 2    | ENC_SW      |
| 3    | RGB_DIN_MCU |
| 4    | ROW3        |
| 5    | VBAT_ADC    |
| 6    | ROW4        |

Slot 0 sits at x=patch_x-6=158, slot 6 at x=patch_x+6=170 with
patch_x=mcu_x+4=164 on a 115x132 mm board (mcu_x=160.0 after Cycle-5
width bump 115->120 mm).

### Cycle 5 builder-bodge wires (required for full functionality)

Cycle 5 stripped the following from the PCB to guarantee zero
`shorting_items`. All 35 are rear-side bodge wires the builder
must hand-solder during assembly. Priority order:

1. **RGB chain (25 wires)** -- LED DOUT(n) to DIN(n+1) along the
   serpentine order 1-2-3-4-5-10-9-8-7-6-11-12-13-14-15-20-19-18-17-16-21-22-23-24-25,
   plus MCU `RGB_DIN_MCU` (via R1) to LED1 DIN.
2. **Decap caps (4 wires)** -- C1/C3 pad 1 to MCU pin 3 (+3V3);
   C4 pad 1 to MCU pin 1 (VUSB); C2 pad 1 to MCU BAT+ pad.
3. **I2C bus (2 wires)** -- MCU pin 8 (SDA) to J_NFC pin 3;
   MCU pin 9 (SCL) to J_NFC pin 4.
4. **ROW3/4 (2 wires)** -- rear-pad slot 4 to ROW3 B.Cu spine east
   end (x=198.6, y=205.675); rear-pad slot 6 to ROW4 B.Cu spine east
   end (x=204.15, y=224.725).
5. **NTC_ADC (1 wire)** -- R_NTC pin 1 to MCU pin 14 (P0.03/AIN1).
6. **Encoder (3 wires)** -- EC1 A/B/SW to rear-pad slots 0/1/2.

Full photo guide in `docs/build-guide.md §Appendix A`.
