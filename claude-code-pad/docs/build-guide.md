# Claude Code Pad - Build Guide

**Phase 1 Cycle 4 scaffolding.** FW-1 and MECH-1 will flesh this out in
Phases 2 and 3 with photos, keycap install, case assembly, firmware
flashing, and the rear-pad jumper wiring diagram. This stub exists to
document the safety-critical sections that the hardware depends on.

---

## Battery requirements (MANDATORY)

**READ BEFORE PLUGGING IN A BATTERY.** This board does NOT contain
an on-board cell-level protection circuit. Cell safety depends
entirely on the battery pack's INTEGRAL protection PCB.

### Approved cells

Only single-cell 3.7 V LiPo packs with integral protection PCB
(DW01A + FS8205A class) and JST-SH 2-pin pigtail are approved.

| Capacity | Form factor | LCSC P/N (approved) | Notes |
|----------|-------------|---------------------|-------|
| 400 mAh  | 402535      | **C5290961**        | Fits case bay, ~4 hr charge at 100 mA |
| 600 mAh  | 603040      | **C5290967**        | Bay must accommodate 6 mm depth, ~6 hr charge |
| 1000 mAh | 104050      | Alt -- any 1S + PCM + JST-SH pigtail | Max bay size, ~10 hr charge |

**RAW / UNPROTECTED cells are FORBIDDEN -- fire risk.**

If substituting, confirm the listing shows a protection PCB in the
product photo AND a JST-SH 2-pin 1 mm pigtail (RED = +, BLACK = -).
"Bare tab" / raw-cell listings are not approved.

### JST-SH polarity

```
  J_BAT (PCB view from F.Cu / keycap side):

         +-----+
         | 1 2 |    1 mm pitch
         +-----+
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
`pcb/DESIGN-NOTES.md §Battery requirements (MANDATORY)`.

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

## Hand-solder checklist (Cycle 4)

PCBA handles all SMD parts EXCEPT these DNP items:

| Ref | Part | Package | Notes |
|-----|------|---------|-------|
| U1  | XIAO nRF52840 | Module, castellations | Direct-solder the 14 front castellations to the board. Leave BAT+/BAT- back-pads for wire jumpers (see below). |
| SW_PWR | SS-12D00G4 | SPDT THT 2.54mm | See above. |
| EC1 | EC11 rotary encoder | THT, 15 mm vertical, H20 shaft | Orient per silkscreen. Back-pads 1-3 need wire jumpers to J_XIAO_BP slots 1-3 (ENC_A, ENC_B, ENC_SW). |
| J_NFC | PN532 NFC 4-pin header | 1x04 pin header 2.54 mm | Only populate if adding the PN532 breakout accessory. |
| TH1 | MF52A2 10k NTC | Axial THT, 6.3 mm body | Install with the body resting on the PCB between J_BAT and SW_PWR. Measures battery temperature. If NOT installed, firmware falls back to 100 mA LED peak cap (see `firmware/zmk/README.md §NTC fallback`). |

### Rear-pad jumper wires (7 wires, Cycle 4)

The XIAO nRF52840 has 14 front castellations (all consumed) and 6
back-side GPIO pads that are not exposed by direct-solder. A 7-pad
SMD cluster `J_XIAO_BP` sits <5 mm south of the MCU. Run short wires
(28-30 AWG, 5-8 mm long) from each J_XIAO_BP slot to the matching
XIAO back-side pad:

| Slot | J_XIAO_BP signal | XIAO back-side pad (suggested) |
|------|------------------|-------------------------------|
| 1    | ENC_A            | P1.15 (bottom-left quadrant)   |
| 2    | ENC_B            | P1.14                          |
| 3    | ENC_SW           | P1.13                          |
| 4    | ROW3             | P1.12                          |
| 5    | ROW4             | P1.10                          |
| 6    | RGB_DIN_MCU      | P0.13 (PWM-capable, fast)      |
| 7    | VBAT_ADC         | P1.11 (AIN7 -- SAADC capable)  |

FW-1 will provide the final authoritative pin assignment in Phase 3
with a ZMK overlay file. Always verify against the ZMK overlay before
soldering.

---

## Firmware flashing (Phase 3 placeholder)

Stub. FW-1 to populate with:

- UF2 bootloader entry (double-tap RESET on XIAO).
- ZMK build path (`west build -b nice_nano_v2` with Claude-Code-Pad
  shield overlay).
- Keymap customisation via ZMK Studio.
- Battery cutoff verification procedure (measure VBAT_ADC ADC raw
  and confirm firmware enters deep sleep at VBAT <= 3.70 V).

---

## Case assembly (Phase 2 placeholder)

Stub. MECH-1 to populate with:

- FDM print settings for Creality K2 Plus (layer height, infill,
  material).
- Top-plate / bottom-case screw sequence (4x M3 self-tapping or
  M3 heat-set inserts).
- Keycap install order (row-by-row, bottom to top).
- 2U Enter stabiliser clip-in procedure.
- Battery bay cable routing (keep JST-SH pigtail clear of the
  slide switch actuator travel).
- RFID figurine slot alignment (Phase 5).

---

## Appendix A: known gaps (Cycle 4 hardware)

These PCB-side gaps require builder action and/or Cycle 5 fixes:

- **4 RGB chain row-transitions unrouted** (RGB_D6, RGB_D11,
  RGB_D16, RGB_D21). If you ordered boards from Cycle 4 gerbers,
  these connections are MISSING and the RGB chain will stop at
  LED5, LED10, LED15, LED20 respectively. Workaround: hand-solder
  4 bodge wires on the back of the PCB, each from LED(5n)-DOUT to
  LED(5n+1)-DIN.
- **Encoder (ENC_A/B/SW) unrouted**. Use the J_XIAO_BP rear-pad
  jumper wiring above.

Cycle 5 (next PCB revision) will route these in the KiCad GUI;
fab-ready gerbers labelled "Rev D" will not require the bodge
wires.
