# Claude Code Pad - ZMK firmware

**Phase 3 Cycle 1 (FW-1).** The Hard Requirements below are the
hardware-design contract that this firmware implements. Every clause
is traceable to a specific IEC / regulatory rule; see the review log
for the full chain of custody.

Phase 3 C1 added: shield tree under `boards/shields/claude_code_pad/`,
safety drivers under `drivers/ccp_safety/`, builder wire guide in
`BODGE-MAP.md`, and QMK alternate scaffold one level up in
`../qmk/`.

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
divider (NOT at Vcell upstream of Q_REV). Phase 3 Cycle 2
(RED-SAFETY SF-M4 / SF-M6) separates the LED-derate tripwire from
the graceful-shutdown tripwire:

| LED state       | Cutoff / derate VBAT |
|-----------------|----------------------|
| LED peak derate | linear **4.00 V -> 3.80 V** (100 % -> 0 %) |
| LEDs latch off  | at **3.80 V** (end of the derate ramp) |
| LEDs re-enable  | at **3.90 V** (100 mV hysteresis above latch) |
| Graceful shutdown | at **3.50 V** (LEDs already off) |

**Rationale (Cycle 2 revision):** in Cycle 1 the derate curve's
lower bound (3.70 V) was also the graceful-shutdown threshold, so
3.70 V fired `graceful_shutdown()` on the first sample and the
two-tier design never got to activate. Cycle 2 raises the derate
band to 4.00 -> 3.80 V so the LED-off latch has real separation
from the BLE-disconnect latch at 3.50 V. A cell at 3.80 V under
zero-LED load sits at ~3.75 V at the VBAT node and still feeds the
AP2112K LDO with ~0.45 V of dropout headroom; graceful shutdown
at 3.50 V therefore has 300 mV of headroom for "save and reconnect"
HID events after the LEDs have been cut.

**Measurement:** VBAT_ADC = VBAT / 2 (2x 1 MOhm resistor divider,
100 nF ADC anti-alias cap). Source impedance ~500 kOhm -- firmware
must use nRF52840 SAADC **OVERSAMPLE >= 2^3** (8 samples) and
BURST mode when reading VBAT_ADC.

**Pin:** VBAT_ADC is on XIAO back-side rear-pad jumper **slot 5**
(patch_x+4, Cycle 5 slot reassignment). User solder-wires from
`J_XIAO_BP` slot 5 to **P0.31 / AIN7** on the XIAO's back-side
castellation. (Cycle 1 of this README said "P1.11 / AIN7" -- FW-B2
correction: on the nRF52840, P1.x pins are NOT SAADC-capable. AIN7
lives on P0.31. Verified against
nRF52840 product specification v1.7 §6.17 Analog input pin
assignments: AIN0..7 correspond to P0.02/.03/.04/.05/.28/.29/.30/.31.
All other P1 pins are digital-only.)

---

## Hard Requirement: VBAT_ADC integrity (broken-wire detection) [C5-M5]

The VBAT_ADC cut-off above is the graceful-shutdown tripwire. Because
the ADC line is a **hand-soldered jumper wire** from the rear-pad
slot to a back-side GPIO, a broken wire leaves the ADC floating and
reads garbage -- firmware would never trip the cut-off and the cell
would be over-discharged to cell-damage levels.

Firmware **must** detect a broken VBAT_ADC jumper and fail safe:

- Sample VBAT_ADC at 250 ms cadence (SAADC OVERSAMPLE>=2^3, BURST
  mode). Cycle 2 dropped this from 10 s per RED-SAFETY SF-B3; nRF52840
  brownout at 1.7 V plus up to 400 mV LDO ESR sag can traverse the
  cutoff band faster than a 10 s window.
- Compute **max-abs-residual** (max of |sample[i] - mean|) over a
  rolling 8-sample window. If > 100 mV, the window is suspect
  (floating input picks up 50/60 Hz hum and noise).
- Compute **instantaneous step** between each sample pair. If any
  step exceeds +/- 0.3 V, the window is suspect (a real cell cannot
  change voltage that fast under 300 mA load).
- **Cycle 2 SF-M5:** require TWO consecutive suspect windows before
  latching graceful_shutdown. A single window of cell-sag under an
  RGB transient no longer false-latches.
- **Cycle 2 SF-M7:** physical-range sanity band. If cell_mv < 2800 OR
  cell_mv > 4400, latch graceful_shutdown immediately (catches
  open-divider-resistor: one of the 1 MOhm legs failing open would
  put ~3.3 V on the ADC pin and the de-divided reading would exceed
  4.4 V).
- When EITHER the broken-wire latch or the physical-range band trips,
  enter the **SAME** graceful-shutdown path as the 3.50 V
  undervoltage cutoff: disable all LEDs, BAS -> 0, disconnect BLE,
  stop advertising, log warning.

This fail-safe cannot be disabled at runtime.

**User-recoverable safety clear (SF-M5):** holding Fn + the top-
right key through a RESET boot re-runs `bt_settings_clear_default()`
and resets the `graceful_shutdown_latched` flag. This is a debug
escape hatch for builders who have confirmed the bodge is sound but
need to clear an earlier latch event from flash.

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

If the NTC ADC channel (NTC_ADC, XIAO pin D1 / P0.03 -- P1.15 was
the original Cycle 5 landing, moved in firmware Cycle 1 because
P1.x is not SAADC-capable) reads **out-of-range** (floating input
-- typical when TH1 is not hand-installed, or a wire break on the
axial thermistor), firmware **must**:

- Reduce the LED peak cap from 300 mA to **100 mA** until a valid
  temperature reading resumes.

Behavior documented to satisfy **IEC 62368-1 Annex Q** fallback
requirements for a degraded thermal-sensing subsystem. "Out of
range" = ADC reads either < 0.1 V (short-to-GND / wire break) or
> 3.1 V (short-to-+3V3).

**Cycle 2 over-temperature threshold (SF-M9):** firmware caps LEDs
at 100 mA when the decoded NTC temperature exceeds **50 degC**
(dropped from 60 degC). The NTC on this revision is co-located with
the LDO, not the cell; the NTC-to-cell-surface correlation is not
yet bench-validated, and a 10 degC cushion keeps the cell well
below the 60 degC IEC 62133-2 onset threshold even under worst-case
correlation error. Rev-B relocates the NTC to a cell-contact
position.

**Cycle 2 rate-of-change sanity (SF-M10):** a decoded temperature
delta > 5 degC/sample OR a temperature outside the [-10 .. +70 degC]
plausibility band forces the 100 mA fallback regardless of the
absolute reading. Catches a partially-shorted divider that reads
in-range but with nonsense physics.

**Cycle 2 floating-pin probe (FW-M6):** on the first in-range
reading after any out-of-range sample, firmware briefly drives the
NTC pin HIGH, releases, and re-samples. A connected divider
discharges the stray capacitance within < 100 us; a floating pin
holds the driven level. A post-release sample within 50 mV of 3.3 V
=> floating pin => 100 mA fallback. Does NOT accidentally flag a
real NTC-shorted-to-+3V3 because that case already lands in the
out-of-range path before the probe runs.

**Cycle 2 NTC decode (FW-M5):** integer-only, 65-entry log-ratio
LUT. `log()` / newlib dependency no longer on the critical path;
worst-case decode error < 0.5 degC over the 0..70 degC plausibility
band.

---

## Hard Requirement: BLE security (Phase 3 Cycle 2, SF-B4)

Cycle 1 silently shipped legacy "just works" pairing while this
README claimed passkey authentication. Cycle 2 corrects both the
code and the documentation.

**Posture (as-shipped Cycle 2):**

| Setting                        | Value | Purpose                              |
|--------------------------------|-------|--------------------------------------|
| `BT_SMP_SC_PAIR_ONLY`          | y     | LE Secure Connections (ECDH) only    |
| `BT_SMP_ENFORCE_MITM`          | y     | Authenticated pairing required       |
| `BT_BONDABLE`                  | n     | New bonds only in pairing-mode window|
| `BT_CTLR_TX_PWR_PLUS_4`        | y     | +4 dBm (PCB antenna tuned for this)  |

**What this means without a display or keypad on the device:**

The Claude Code Pad today has no OLED (Phase 1 Cycle 1 cut it for
cost) and no dedicated 10-key passkey entry. With `ENFORCE_MITM=y`,
pairing will only succeed via hosts that implement:

1. **LE Secure Connections with Numeric Comparison.** Modern
   macOS / iOS / Android / Windows 10+ all support this for BLE
   peripherals that have no I/O capability -- the host shows a
   6-digit number and the user presses "yes/no" on the host side.
   No keypad on the peripheral required.
2. **BLE OOB (Out Of Band) pairing.** Not applicable for this
   build.

Hosts that try to fall back to legacy "Just Works" (no user
confirmation, no MITM resistance) will have pairing rejected by
the peripheral's SMP layer. This is the intended behaviour. A
drive-by attacker cannot silently bond; an attacker who owns the
host already has HID access and BLE MITM is moot.

**Pairing-mode window (SF-M12, keymap glue deferred to Cycle 3):**
`BT_BONDABLE=n` means new bonds are rejected outside an explicit
pairing-mode window. Firmware flips `bt_set_bondable(true)` for
60 s when the user holds Fn + BT0 for 3 s. The keymap binding for
this is a Cycle 3 deliverable.

**Phase 5 upgrade path:** when the PN532 NFC reader + the RGB LEDs
are available for passkey-display use, the firmware will implement
colour-coded 6-digit passkey display via LEDs 0..5 and switch to
`NoInputNoOutput -> DisplayOnly` IO-capabilities advertising.
Documented in `docs/safety-verification.md §BLE MITM test plan`.

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

---

## Phase 3 C1 addendum: NTC_ADC pin move

Cycle 5 landed NTC_ADC on MCU pin 14 (D10 / P1.15). P1.15 is **not**
SAADC-capable on the nRF52840; firmware Cycle 1 moves NTC_ADC to MCU
pin 5 (D1 / P0.03 / AIN1) and shifts COL1 from D1 to D10. See
`BODGE-MAP.md` for the bodge-wire delta.

---

## Building

### Prerequisites

- Python 3.10+, `west`, Zephyr SDK (toolchain). Quick install:
  ```bash
  pipx install west
  # or:  brew install west
  wget https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v0.17.0/zephyr-sdk-0.17.0_linux-x86_64.tar.xz
  tar xf zephyr-sdk-0.17.0_linux-x86_64.tar.xz -C ~
  cd ~/zephyr-sdk-0.17.0 && ./setup.sh
  ```
- ZMK pulls the Zephyr tree itself via `west update`.

### Clone + init

```bash
mkdir -p ~/zmk-ccp && cd ~/zmk-ccp
git clone https://github.com/<you>/Claude-Keyboard src/ccp
west init -l src/ccp/claude-code-pad/firmware/zmk/config
west update
west zephyr-export
pip install -r zephyr/scripts/requirements-base.txt
```

### Build

```bash
cd ~/zmk-ccp
west build -s zmk/app -b xiao_ble/nrf52840 \
    -- -DSHIELD=claude_code_pad \
       -DZMK_EXTRA_MODULES="$PWD/src/ccp/claude-code-pad/firmware/zmk"
```

Note: the Zephyr 4.1+ board name is `xiao_ble/nrf52840`. Upstream
Zephyr renamed the old `seeeduino_xiao_ble` board to `xiao_ble` as
part of the HWMv2 migration; the `/nrf52840` qualifier is required
in v4.1 because the XIAO "Sense" variant (which carries an IMU)
shares the same board tree.

Output UF2: `build/zephyr/zmk.uf2`.

A pre-built reference UF2 lives at `firmware/zmk/build-artifacts/zmk.uf2`
(checked into the repo for the current Cycle 2 commit). Use it for
quick smoke tests before standing up a local toolchain; the paired
`firmware/zmk/build-artifacts/build.log` is the full `west build`
log from the same build.

### Flash (UF2 bootloader)

1. Double-tap the RESET button on the XIAO nRF52840. It enumerates as
   `XIAO-BOOT` USB mass storage.
2. Copy `build/zephyr/zmk.uf2` to that drive.
3. The board reboots and enumerates as `Claude Code Pad` (USB HID +
   BLE).

### First-boot checklist

Observe the ZMK log over USB CDC (CONFIG_ZMK_USB_LOGGING=y in a debug
build) or over RTT:

```
[INF] ccp_rgb_init_safe: RGB_DIN_MCU pre-driven LOW
[INF] zmk_rgb_underglow: inited
[INF] ccp_battery_guard: VBAT=<mV> cap=<n> leds_cut=0
[INF] ccp_thermal_guard: NTC <mV> -> <degC> cap=100
```

If the thermal guard reports `cap=33` persistently, the NTC bodge is
missing or the thermistor is not installed -- the 100 mA fallback cap
is in effect and **this is intentional**. See `BODGE-MAP.md` to fix.

### Troubleshooting

- **"board seeeduino_xiao_ble not found"** -- the west manifest did
  not pull the Zephyr tree containing the Seeed XIAO BLE definition.
  Run `west update` again; verify `~/zmk-ccp/zephyr/boards/arm/
  seeeduino_xiao_ble/` exists.
- **"shield claude_code_pad not found"** -- `ZMK_EXTRA_MODULES` is not
  pointing at the firmware/zmk directory of your checkout, or the
  path contains spaces and is not quoted.
- **BLE won't pair, or pairs then drops immediately** -- clear the
  pairing table: tap the BT layer (C2 work adds a dedicated binding;
  for now re-flash after deleting `/lfs1/settings/bt` via the ZMK
  studio tool) then re-pair. On Linux hosts, delete the bond on the
  host side too (`bluetoothctl remove <mac>`).
- **All 25 LEDs flash bright-white on boot** -- the pre-init GPIO
  hook failed; the LEDs saw garbage on DIN. Verify in the log that
  `[INF] ccp_rgb_init_safe: RGB_DIN_MCU pre-driven LOW` appeared
  before any RGB driver line. If absent, rebuild with a clean cache.

### Validation gate for local / CI builds

```bash
# ERC-equivalent: Kconfig sanity
west build -t menuconfig   # should open clean, no unresolved symbols
# Static analysis (if installed)
west build -t clang-analyzer
```
