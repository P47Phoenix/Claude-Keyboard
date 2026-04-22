# Claude Code Pad - Build Guide

**Phase 1 Cycle 5 scaffolding.** FW-1 and MECH-1 will flesh this out in
Phases 2 and 3 with photos, keycap install, case assembly, firmware
flashing, and the rear-pad jumper wiring diagram. This stub exists to
document the safety-critical sections that the hardware depends on.

---

## Battery requirements (MANDATORY)

**READ BEFORE PLUGGING IN A BATTERY.** This board does NOT contain
an on-board cell-level protection circuit. Cell safety depends
entirely on the battery pack's INTEGRAL protection PCB.

### Approved cells (Cycle 5 re-sourced + URL-verified)

Only single-cell 3.7 V LiPo packs with integral protection PCB
(DW01A + FS8205A class) and **JST-PH 2.0 mm** 2-pin pigtail are
approved. Each URL below was WebFetched during Cycle 5 and
returned HTTP 200.

| Source | Link | Capacity | Dimensions (mm) | PCM? | JST |
|--------|------|---------:|----------------:|------|-----|
| Adafruit | [#1578](https://www.adafruit.com/product/1578)   | 500 mAh | 29 x 36 x 4.75 | yes | PH |
| Adafruit | [#3898](https://www.adafruit.com/product/3898)   | 400 mAh | ~36 x 17 x 7.8 | yes | PH |
| Adafruit | [#328](https://www.adafruit.com/product/328)     | 2500 mAh | 50 x 60 x 7.3 | yes | PH |
| SparkFun | [PRT-13851](https://www.sparkfun.com/products/13851) | 400 mAh | 26.5 x 36.9 x 5 | yes | PH |
| Adafruit | [#1317](https://www.adafruit.com/product/1317)   | 150 mAh | 19.75 x 26.02 x 3.8 | yes | PH |

> **Cycle 4 warning:** the SKUs C5290961 and C5290967 that appeared
> in older versions of this file were hallucinated. Both return 404
> on lcsc.com. **Do not attempt to source them.** LCSC does not
> stock a trivially-findable generic protected 1S LiPo cell with
> JST-PH pigtail; use one of the Adafruit or SparkFun SKUs above.

**RAW / UNPROTECTED cells are FORBIDDEN -- fire risk.**

If substituting, confirm the listing shows a protection PCB in the
product photo AND a JST-PH 2.0 mm 2-pin pigtail (RED = +, BLACK = -).
"Bare tab" / raw-cell listings are not approved.

### JST-PH polarity

The PCB `J_BAT` footprint has **F.SilkS "+" and "-" glyphs**
immediately north of each pad (Cycle 5 fix, C5-M3):

```
   J_BAT (PCB view from F.Cu / keycap side):

         + -             silkscreen glyphs
         |=|             body
         +---+
         | 1 2 |         2.0 mm pitch
         +-----+         side-entry SMD
          |   |
         [+] [-]         pin 1 = cell +  (VBAT_CELL)
                         pin 2 = cell -  (GND)

  Most pigtails ship with RED = +, BLACK = -.
  Match the RED wire to the silkscreen "+" marker next to pin 1.
```

If you connect the battery reversed, Q_REV (P-FET) body-diode
blocks the reverse current BUT the cell slowly drains through the
zener clamp. Unplug and re-wire within 1 minute.

### Why the PCM is mandatory (short version)

The board has a 500 mA PTC (F1). The PTC trips in ~100 ms at 4 A.
If a raw cell is plugged in and a short develops downstream, the
PTC takes ~100 ms to trip. In that 100 ms, an unprotected cell
dumps ~1.4 J of energy at ~4 A, raising cell temperature by
>60 degC. That crosses the thermal-runaway threshold for LiPo
chemistry and produces a **vent-with-flame** event.

A cell-integrated PCM trips in <10 ms at 4 A -- faster than the
PTC can sustain the fault, prevents the vent. **Use cells with PCM.**

Full math and cell-substitution rules in
`pcb/DESIGN-NOTES.md §Cycle 5 §Verified procurement table` and
`§Battery requirements (MANDATORY)`.

---

## Power switch (SW_PWR) installation

SW_PWR is an SS-12D00G4 SPDT slide switch, THT with 2.54 mm pitch
three-pin + 2 mounting lugs. **Not placed by JLCPCB PCBA -- you
hand-solder it.**

**Do not jumper across the switch footprint.** SW_PWR is the
primary way to power the pad down without unplugging the battery.
If the switch is absent or jumpered, the only way to turn the pad
off is to unplug J_BAT (inconvenient and wears out the JST connector).

- With SW_PWR installed and in the **OFF** position: VBAT rail is
  disconnected from the XIAO BAT+ pad; firmware powers down cleanly
  within 1 ms.
- With SW_PWR absent or jumpered: pad runs whenever a charged
  battery is plugged in; only undervolt cutoff (firmware 3.50 V)
  or USB-C unplugged state prevents drain.

### Installation steps

1. Solder SW_PWR to the PCB (3 pins TH + 2 mounting lugs).
2. Verify correct slide direction: the switch actuator should slide
   east (toward the keys) when moving to ON. Silkscreen shows
   ON / OFF markings.
3. Do NOT bridge the footprint with a wire jumper unless you
   understand the firmware 3.50 V cutoff will be the only protection
   against cell over-discharge during long storage.

---

## Hand-solder checklist (Cycle 5)

PCBA handles all SMD parts EXCEPT these DNP items:

| Ref | Part | Package | Notes |
|-----|------|---------|-------|
| U1  | XIAO nRF52840 | Module, castellations | Direct-solder the 14 front castellations to the board. Leave BAT+/BAT- back-pads for wire jumpers (see below). |
| SW_PWR | SS-12D00G4 | SPDT THT 2.54mm | See above. |
| EC1 | EC11 rotary encoder | THT, 15 mm vertical, H20 shaft | Orient per silkscreen. Back-pads 1-3 need wire jumpers to J_XIAO_BP slots 0-2 (ENC_A, ENC_B, ENC_SW). |
| J_NFC | PN532 NFC 4-pin header | 1x04 pin header 2.54 mm | Only populate if adding the PN532 breakout accessory. |
| TH1 | MF52A2 10k NTC | Axial THT, 6.3 mm body | Install with the body resting on the PCB between J_BAT and SW_PWR. Measures battery temperature. If NOT installed, firmware falls back to 100 mA LED peak cap (see `firmware/zmk/README.md §NTC fallback`). |

---

## Appendix A: Cycle 6 rear-bodge wiring (minimal)

Cycle 5 stripped 37 signal routes to bypass a routing failure and
required 35-37 hand-soldered bodge wires. **Cycle 6 replaced the
generative-Python router with Freerouting 2.1.0 and retains every
signal on the PCB.** All 83 nets are machine-routed with 533 traces,
1052 segments, 104 vias, `shorting_items = 0`, `tracks_crossing = 0`,
`hole_clearance = 0`.

The **single residual bodge** is a pour-connectivity fix, not a signal
route:

### The 1 bodge: LED GND pad-to-pour bridge

On one LED (position varies by Freerouting run, typically LED2 / LED12
/ LED14 / LED22) the GND pad (pad 3) sits on a narrow B.Cu peninsula
between the Edge.Cuts light aperture and a nearby signal trace; the
GND pour fails to reach it. All other 24 LEDs have their GND pad 3
connected via the pour.

Assembly-time rule:
1. Open the routed board in the KiCad 10 flatpak: `flatpak run org.kicad.KiCad`.
2. Tools -> Refill All Zones (`B`).
3. Inspect the ratsnest. If any LED pad `3 [GND]` still has an airwire:
4. Add a <2 mm B.Cu trace from that pad to the nearest piece of GND
   pour copper (use the main pour on B.Cu, typically visible
   immediately east or south of the LED body). 28-30 AWG wire-wrap
   wire soldered on the rear works too.

**Not applicable:**

- No antenna-adjacent bodges. (Cycle 5 had ~20; Cycle 6 has zero.
  XIAO nRF52840 modular FCC/IC cert path is preserved.)
- No I²C bodges. SDA/SCL are B.Cu-routed from the MCU pin-8/9
  castellations to J_NFC pins 3/4 with TVS diodes in line.
- No decap-to-MCU bodges. C1/C2/C3/C4 all autorouted.
- No RGB-chain bodges. DIN/DOUT hops 1 -> 2 -> ... -> 25 are all
  machine-routed in the spec serpentine order.
- No ROW3/ROW4 jumper-cluster bodges. Freerouting's path uses the
  rear-pad slot pads but closes the loop in copper, not wire.

### Firmware-optional DNP wires (unchanged from Cycle 5)

These are assembly choices, not PCB fixes -- skip if you don't
populate the optional part:

- **NFC breakout (PN532 on J_NFC)**: J_NFC is DNP; SDA/SCL/3V3/GND
  pins are through-hole and user-solderable. No bodging needed -- the
  board copper is continuous.
- **NTC thermistor (TH1)**: NTC_ADC routes to rear-pad slot 7; if TH1
  is not populated, firmware NTC-fallback disables the 300 mA LED
  derate and caps to 100 mA.
- **Encoder (EC1)**: ENC_A / ENC_B / ENC_SW go from EC1 pins to
  rear-pad slots 0/1/2. EC1 is PTH but physically optional.

### XIAO back-side GPIO mapping (unchanged)

The rear-pad jumper cluster `J_XIAO_BP` routes 7 signals to
user-solderable XIAO back-side pads:

| Slot | Signal      | Suggested XIAO back-side pad |
|------|-------------|------------------------------|
| 0    | ENC_A       | P1.15                        |
| 1    | ENC_B       | P1.14                        |
| 2    | ENC_SW      | P1.13                        |
| 3    | RGB_DIN_MCU | P0.13 (PWM-capable)          |
| 4    | ROW3        | P1.12                        |
| 5    | VBAT_ADC    | P1.11 (AIN7, SAADC-capable)  |
| 6    | ROW4        | P1.10                        |

These 7 wires are **board-to-MCU-side solder joints** (the XIAO is
direct-soldered via castellations; back-pad GPIOs aren't castellated
and need wires from the pad cluster to the MCU underside pads). Not
counted as "bodges" -- this is the standard XIAO mounting method.
FW-1's ZMK overlay honours these assignments.

---

## Firmware flashing (Phase 3 placeholder)

Stub. FW-1 to populate with:

- UF2 bootloader entry (double-tap RESET on XIAO).
- ZMK build path (`west build -b seeeduino_xiao_nrf52840` with
  Claude-Code-Pad shield overlay).
- Keymap customisation via ZMK Studio.
- Battery cutoff verification procedure (measure VBAT_ADC ADC raw
  and confirm firmware enters deep sleep at VBAT <= 3.70 V).
- Broken-wire VBAT_ADC test (disconnect the slot-5 bodge wire,
  verify firmware enters graceful-shutdown state within 8 samples).

---

## Case assembly (Phase 2 placeholder)

Stub. MECH-1 to populate with:

- FDM print settings for Creality K2 Plus (layer height, infill,
  material).
- Top-plate / bottom-case screw sequence (4x M3 self-tapping or
  M3 heat-set inserts).
- Keycap install order (row-by-row, bottom to top).
- 2U Enter stabiliser clip-in procedure.
- Battery bay cable routing (**JST-PH 2.0 mm** -- updated from
  Cycle 4's 1.0 mm pitch spec; MECH-1 must cross-check the battery
  pocket cable clearance).
- Charging rate note: the XIAO nRF52840 module's on-board charge
  pump defaults to ~100 mA charge rate. **Do not modify the XIAO
  module's R_PROG charge-programming resistor** -- the 100 mA
  default is the documented safe limit for the approved cell list.
- RFID figurine slot alignment (Phase 5).
