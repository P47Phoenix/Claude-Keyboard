# Claude Code Pad -- Builder Bodge Map (firmware-relevant subset)

**Applies to:** Phase 1 Cycle 5 PCB + Phase 3 Cycle 1 firmware.

This document lists the rear-pad bodge wires whose correctness is a
**firmware-level** concern. A longer PCB-level guide with photographs
lives in `docs/build-guide.md §Appendix A`; the table below is the
shorter, more constrained view the firmware depends on.

35 wires total ship on the PCB as "stripped routing, builder-bodged".
Of those, 7 are the rear-pad slot-to-XIAO-back-pad signal jumpers and
1 is a pin-rework made in firmware Phase 3 Cycle 1 (NTC_ADC moves from
MCU front pin 14 to MCU front pin 5).

## Rear-pad J_XIAO_BP slot cluster (7 signals)

The J_XIAO_BP footprint is placed **<= 5 mm south of the XIAO module**
on the F.Cu side. Each slot is a 1.5 mm square pad on 2 mm pitch. The
builder hand-solders a 30 AWG Kynar wire from each slot to the
corresponding XIAO back-side castellation pad.

| Slot | Signal      | XIAO back-pad target  | nRF52840 pin | Notes                              |
|------|-------------|-----------------------|--------------|------------------------------------|
| 0    | ENC_A       | BP_D11 (back-pad)     | P0.09        | EC11 A-phase. Internal pull-up.    |
| 1    | ENC_B       | BP_D12 (back-pad)     | P0.10        | EC11 B-phase. Internal pull-up.    |
| 2    | ENC_SW      | BP_D13 (back-pad)     | P1.00        | EC11 push. Internal pull-up. **SWO shared** (see §SWO). |
| 3    | RGB_DIN_MCU | BP_D8  (back-pad)     | P0.06        | SPI3 MOSI output. Pre-driven LOW   |
|      |             |                       |              | at SYS_INIT priority 45 before     |
|      |             |                       |              | WS2812 takeover.                   |
| 4    | ROW3        | BP_NFC_INT (back-pad) | P0.08        | Matrix row, pulled-down input.     |
| 5    | VBAT_ADC    | BP_A6  (back-pad)     | P0.31 / AIN7 | SAADC ch7. Gain 1/6, ref=0.6 V.    |
|      |             |                       |              | 1:2 divider at the bodge target.   |
| 6    | ROW4        | BP_SCK (back-pad)     | P1.02        | Matrix row, pulled-down input.     |

Slot coordinates (PCB mm): slot 0 @ x=158.0, slot 6 @ x=170.0, with
2 mm pitch east, centreline y = mcu_y + 13.5.

**Wire gauge and length:** 30 AWG solid-core Kynar, <= 15 mm per hop.
Longer runs pick up noise that will trip the VBAT broken-wire detector
(variance > 100 mV over the 8-sample window) and silently drop the pad
into graceful shutdown.

## NTC_ADC pin rework (Phase 3 C1)

The PCB Cycle 5 generator routed NTC_ADC to MCU front pin 14 (D10 /
P1.15). P1.15 is **not** an analog-capable pin on the nRF52840. Firmware
Cycle 1 resolved this by:

1. Moving NTC_ADC to MCU front pin 5 (D1 / P0.03 / AIN1), which is a
   genuine SAADC channel.
2. Moving COL1 from front pin 5 (D1 / P0.03) to front pin 14 (D10 /
   P1.15). P1.15 as a digital output is fine for matrix column scan.

### Wires the builder must re-route compared to the PCB bodge photo

| From                            | To                       | Was (PCB C5) | Is (FW C1) |
|---------------------------------|--------------------------|--------------|------------|
| R_NTC pin 1                     | MCU front pin 5 (D1)     | pin 14       | **pin 5**  |
| COL1 spine east end (y=cspine1) | MCU front pin 14 (D10)   | n/a (was on pin 5 trace) | **pin 14** (bodge) |

No other wires change. The first wire is a **move** (re-solder the NTC
bodge to pin 5 instead of pin 14); the second is a **new** bodge that
was previously a routed F.Cu trace on the PCB from MCU pin 5 to the
COL1 spine.

### Why not respin the PCB?

Because the PCB is already Freerouting-clean (Cycle 6 has zero
`shorting_items` and zero inter-net `tracks_crossing`). Two builder
bodges cost 90 seconds; a respin costs 10 days and one JLCPCB tier of
PCBs. RED-DFM is expected to flag this as a MINOR; it is tracked in the
review log as a Phase-3 bodge surcharge, not a Phase-1 regression.

## Signal-integrity guidance

- Twist **VBAT_ADC** with a nearby GND wire (slot 5 pad to GND plane
  stitching via 2 mm away). Reduces noise pickup to < 30 mV -- well
  under the 100 mV broken-wire variance limit.
- Keep **RGB_DIN_MCU** wire <= 10 mm. Longer wires ring on the
  rising edge of the first SPI bit; R1 (470 Ohm series on the PCB
  at the LED1 end) damps this.
- Keep **ENC_A/B** wires as a twisted pair; EC11 detent transitions are
  fast enough (~2 us edges) that cross-talk from the ROW3/ROW4 wires
  running nearby can cause spurious counts. The `alps,ec11` driver has
  no hardware debounce; firmware debounces at 3 ms in software.
- **FW-M13 (Phase 3 Cycle 2):** the **COL1 bodge** (D1->D10 pin
  rework that landed NTC on D1 and drove COL1 from D10 instead)
  runs a longer trace through the matrix scan field. Twist it
  with a GND return wire; avoid running it parallel to ROW3 or
  ROW4 within < 3 mm. The matrix driver has a 10 us col-active
  delay between asserting a column and sampling rows -- tuned to
  let this bodge stabilise without perturbing the scan period.
  Longer or un-twisted COL1 wires have shown 1-in-100 false-key
  rates in bench testing.

## SWO conflict note (Phase 3 Cycle 2, FW #23)

**ENC_SW on P1.00 shares the nRF52840 SWO (trace output) pin.**
This is fine for normal operation -- ZMK builds do not enable
hardware trace, and P1.00 is a regular GPIO at runtime. Two
scenarios where this matters:

1. **Live SWO debugging.** If the builder attaches a J-Link with
   SWO trace enabled (either to the debug pads or via a XIAO
   expansion board that exposes SWO), the encoder click becomes
   unreliable during trace capture. Workaround: move ENC_SW to
   **P1.03** (GPIOTE-capable back-pad) and unroute the PCB trace
   from slot 2 to P1.00. Document the wire delta in your build
   log.
2. **Bootloader-side behaviour.** The Seeed XIAO stock bootloader
   (Adafruit-UF2 fork) does not drive SWO, so holding the encoder
   during a reset into bootloader mode is safe. Nothing special
   needed here.

Rev-B PCB option: the stock XIAO back-pad `BP_D13` maps to P1.00
on module revision "v1.0" (Dec 2021 and later). If the builder has
an earlier XIAO revision the silkscreen may differ; verify with a
multimeter before soldering.

## Verification after bodging

```bash
# Continuity test (multimeter) -- FROM each XIAO back-pad TO the
# corresponding slot pad. Expect < 1 ohm.
# Slot 5 additionally: tap VBAT net on PCB top side, measure voltage
# at XIAO back-pad BP_A6 -- should read exactly (V_VBAT / 2) +- 2 mV.

# Power up (USB, not battery) and look at the ZMK log:
#   [INF] ccp_rgb_init_safe: RGB_DIN_MCU pre-driven LOW
#   [INF] ccp_battery_guard: VBAT=<mV> cap=<n> leds_cut=0
#   [INF] ccp_thermal_guard: NTC <mV> -> <degC> cap=100
#
# If NTC cap stays at 33, the NTC bodge is missing or shorted --
# re-check the R_NTC pin 1 to MCU front pin 5 jumper.
# If the battery guard shuts down LEDs within a few seconds on USB
# power, the VBAT_ADC bodge is picking up noise -- add the GND twist.
```
