# Claude Code Pad -- QMK alternate (RP2040 Pro Micro)

**Status:** Phase 3 Cycle 1 skeleton. Not production-validated.
ZMK on XIAO nRF52840 is the primary firmware.

This subtree exists so RED-FW has a reviewable escape hatch if ZMK turns
out to be the wrong framework (BLE stack quirks, Zephyr version drift,
nRF52840 power-management bugs). The target MCU is an **RP2040 Pro
Micro** (e.g. Sparkfun Pro Micro RP2040 or SparkFun-clone compatibles)
paired with the same PCB via a pin-compatible daughter board (the Pro
Micro footprint matches the XIAO castellations in spirit but needs a
solder-in adapter because pitch and orientation differ).

## Porting notes

- QMK is **USB-only**; no BLE. If BLE is required, stay on ZMK.
- RP2040 has 26 user GPIOs vs nRF52840's 48; all 25 matrix nets + the
  encoder still fit, with 0 spare for NFC. The PN532 header would lose
  its I2C line on the alt firmware (phase 5 work).
- SK6812 driven via PIO state machine (`ws2812_pio` library). 300 mA
  cap is enforced in `rgb_matrix_config` with a brightness limit of
  `RGB_MATRIX_MAXIMUM_BRIGHTNESS 50` (50/255 * 25 LEDs * 60 mA = 294 mA).
- VBAT monitoring / cell cutoff are **not implemented** in this
  alternate; users running QMK on a battery-powered build accept that
  loss. Most Pro Micro RP2040 builds are USB-bus-powered.

## Wiring delta vs XIAO PCB

You will need an adapter PCB or hand-wired jumpers between the Pro
Micro footprint and the XIAO pads:

| Pro Micro pin | Signal       | XIAO equivalent  |
|---------------|--------------|------------------|
| GP0           | COL0         | D0 (P0.02)       |
| GP1           | COL1         | D10 (P1.15)      |
| GP2           | COL2         | D2 (P0.28)       |
| GP3           | COL3         | D3 (P0.29)       |
| GP4           | COL4         | D6 (P1.11)       |
| GP5           | ROW0         | D7 (P1.12)       |
| GP6           | ROW1         | D8 (P1.13)       |
| GP7           | ROW2         | D9 (P1.14)       |
| GP8           | ROW3         | BP slot 4        |
| GP9           | ROW4         | BP slot 6        |
| GP10          | ENC_A        | BP slot 0        |
| GP11          | ENC_B        | BP slot 1        |
| GP12          | ENC_SW       | BP slot 2        |
| GP13          | RGB_DIN      | BP slot 3        |
| GP14          | SDA          | D4 (P0.04)       |
| GP15          | SCL          | D5 (P0.05)       |
| GP26 / ADC0   | NTC_ADC      | D1 (P0.03)       |

VBAT_ADC (BP slot 5) is intentionally unmapped.

## Build

```bash
qmk compile -kb claude_code_pad -km default
qmk flash    -kb claude_code_pad -km default   # press RP2040 BOOTSEL
```

Not CI'd. RED-FW review scope.
