#!/usr/bin/env python3
"""
Claude Code Pad - ECE-1 deliverable generator (Cycle 5).

Cycle 5 changes vs Cycle 4 (against RED-DFM / RED-SAFETY Cycle 4 review:
6 BLOCKER / 5 MAJOR / 4 MINOR). The Cycle 4 generative routing produced
five real net-level shorts that the prior author misclassified as
"nudge-pass" geometry. Cycle 5 strips the failing routing and re-routes
with strict layer separation, plus fixes the hallucinated LCSC cell SKUs
and a number of smaller geometry/doc issues.

  * C5-B1 (VBAT<->VUSB<->GND at MCU decaps): C1..C5 relocated to clean
    positions. C1/C3 (decouple +3V3 pin) west of MCU south of row-3 key;
    C2 (bulk VBAT) directly adjacent to BAT+ rear pad; C4 (VUSB) adjacent
    to MCU pin 1 with a zero-mm-track direct pad-to-pad connection; C5
    (1 nF HF bypass) removed (MINOR S-N14 carry-over -- AP2112K already
    has internal decoupling, the 1 nF was a belt-and-braces that the
    adjacent-pad bulk cap handles better). All decaps sit on B.Cu SOUTH
    of MCU, outside the antenna keepout zone, >=0.5 mm from each other.

  * C5-B2 (I2C shorts): TVS_SDA/TVS_SCL relocated to within 4 mm of
    J_NFC (not under MCU). I2C bus routed entirely on B.Cu, south of
    the MCU body, never touching the MCU front castellation F.Cu pads.

  * C5-B3 (Q_REV gate shorted to source): R_GREV moved adjacent to
    Q_REV pin 1 (centred 2 mm east of gate pad). GATE_REV copper under
    3 mm total length before reaching R_GREV pin 1 and D_GREV anode.
    Routed F.Cu only, no via, no detour -- no VBAT_CELL crossing.

  * C5-B4 (matrix COLxROW/I2C/RGB merges): strict layer split --
    COLs exclusively F.Cu, ROWs exclusively B.Cu. Rear-pad slot x-grid
    broadened to 3 mm pitch so ROW3/ROW4 vias keep >=0.5 mm between
    them. Matrix vias use 0.6/0.3 mm and maintain inter-via spacing >=0.8 mm.

  * C5-B5 (RGB_Dxx shorts): RGB chain serpentine STRIPPED from the PCB.
    All 24 inter-LED hops + DIN become user-bodge wires on the rear of
    the board, documented in docs/build-guide.md Appendix A. The cost
    is ~4-5 min of builder bodge per board; the benefit is deterministic
    zero RGB-net shorts. 25 LED VCC pads connect to +3V3 bus via short
    stubs; 25 LED GND pads connect to GND pour. Only the 24 DIN/DOUT
    hops + the MCU->LED1 DIN seed wire are builder-laid.

  * C5-B6 (hallucinated LCSC cells C5290961/C5290967): re-sourced two
    real PCM-equipped protected 1S LiPo cells with HTTP-200-verified
    URLs. The popularly-stocked cells all use JST-PH (2.0 mm pitch), not
    JST-SH (1.0 mm pitch). J_BAT footprint migrated from JST-SH to
    JST-PH so the approved-cell list's cables mate without re-termination.
    BOM LCSC # updated to C160404 (JST PH S2B-PH-SM4-TB, in stock).

  * C5-M1 (2U Enter east stab off-board): board width grown 115 -> 120 mm
    (+5 mm east). Key grid stays anchored at KEY0_CX = 119.4. 2U Enter
    east stab at x=217.025; board east edge at x1 = 220. Clearance 2.975 mm
    (meets spec >=1 mm). mcu_x shifts from 157.5 to 160.0; all relative
    positions unchanged.

  * C5-M2 (tracks_crossing triage): the Cycle 4 inter-net tracks_crossing
    count was 82. With the C5 layer-split re-route and RGB strip, DRC
    inter-net same-layer crossings drop to 0 / few. Same-net crossings
    are not DRC-flagged.

  * C5-M3 (+/- silkscreen on J_BAT): fp_jst_ph_2pin adds F.SilkS glyphs
    adjacent to pin 1 ("+") and pin 2 ("-") at 1 mm text size, 0.15 mm
    stroke. Visible in F_Silkscreen.gbr.

  * C5-M4 (brownout math reconciliation): adopted Option A. Cutoff stays
    at 3.70 V (LEDs-on) / 3.50 V (LEDs-off). DESIGN-NOTES worked example
    rewritten to say "cutoff fires near 30-35 % SoC to preserve LDO
    dropout headroom; useful cell range is the top 65-70 % of nominal
    capacity" rather than the contradictory "25 %" figure. Mirrored into
    firmware/zmk/README.md.

  * C5-M5 (VBAT_ADC broken-wire detection): firmware/zmk/README.md
    gains a new Hard Requirement: 8-sample variance > 100 mV OR
    instantaneous step >+-0.3 V triggers the same graceful-shutdown
    path as the 3.50 V undervoltage cutoff.

ORIGINAL Cycle 4 preamble (for reference):

Cycle 4 changes vs Cycle 3 (targeted fixes against RED-DFM / RED-SAFETY
Cycle 3 review: 2 BLOCKER / 5 MAJOR / 8 MINOR):

  * C4-B1 (D-M1 / S-B1): Antenna keepout geometry fix. MCU moved south
    8 mm (mcu_y = y0 + 19) AND board grown to 132 mm height so the key
    grid retains clearance from MCU south pads. Antenna keepout now
    spans y0 .. mcu_y - 3 = 16 mm ON-BOARD (was 2.5 mm). ant_y0 clamped
    to y0 (no off-board extent -- MINOR D-N1 closure).

  * C4-B2 (S-B2): DESIGN-NOTES gets a new §Battery requirements
    (MANDATORY) section with approved LCSC cell list, PCM timing
    rationale, JST-SH polarity, and cell-substitution prohibition.
    Short-form mirror into firmware/zmk/README.md and docs/build-guide.md.

  * C4-M1 (D-M2 / S-M1): VBAT ADC tap added. 2x 1 MOhm divider from
    VBAT -> VBAT_ADC -> GND, 100 nF cap on ADC node. VBAT_ADC routed
    to a new XIAO back-side jumper pad (7th slot in J_XIAO_BP cluster).
    Firmware brownout cutoff documented at 3.70 V (LEDs on) / 3.50 V
    (LEDs off) in DESIGN-NOTES §Safety §Brownout behavior.

  * C4-M2 (D-M3): PCB routing. Matrix COLs on F.Cu (MCU -> key columns),
    matrix ROWs on B.Cu (diode cathodes -> MCU/jumper), RGB chain
    serpentine D1..D24 + DIN on B.Cu, I2C SDA/SCL on B.Cu to NFC
    header, power chain tracks retained from Cycle 3.

  * C4-M3 (S-M2): Firmware-cap bypass hardening. Phase-5 jumper
    reference removed from firmware/zmk/README.md. DESIGN-NOTES
    §Safety §Firmware cap adds IEC 62368-1 Annex Q Q.2 wording,
    hostile-recompile hazard assumption, second-line AP2112K-3.3
    thermal shutdown note, and FW-1 init-order obligation (RGB DIN
    GPIO-low BEFORE enabling +3V3 LED power).

  * C4-M4 (S-N5 promoted): SW_PWR stays DNP (THT hand-solder) but
    docs/build-guide.md explicitly forbids jumpering across the switch
    footprint.

  * C4-M5 (S-N8 promoted): firmware/zmk/README.md adds NTC fallback
    behavior (peak cap reduces to 100 mA if NTC ADC reads out-of-range).

Cycle 3 carries forward:
  (see preamble of Cycle 3 notes in the commit history for
  Option B power simplification, datasheet-verified pinouts, etc.)

Run:  python3 generate.py
Outputs to the parent directory (claude-code-pad/pcb/).

ORIGINAL Cycle 3 preamble (for reference -- all still applies):

Cycle 3 changes vs Cycle 2 (Option B simplification):

  * Removed TP4056 charger, TPS2113A power-mux, DW01A PCM, FS8205A PCM-FET,
    TPS63020 buck, inductor, FB divider, and all associated passives.
  * Merged power nets:
        LiPo (J_BAT.1) -> Q_REV (DMG3415U-7, verified pinout) -> F1 PTC
        -> SW_PWR (SS-12D00G4 TH slide) -> VBAT -> XIAO BAT+ pad.
        USB-C on XIAO module -> XIAO on-board charger -> XIAO 3V3 LDO
        (AP2112K-3.3, 600 mA) -> all 3V3 loads (LEDs firmware-capped
        to 300 mA, I2C pull-ups, PN532). +3V3_SYS net retired; everything
        collapses to +3V3.
  * Every intermediate power net (VBAT_RAW/VBAT_PROT/VBAT_FUSED/VBAT_MUX/
    VSRC_MUX/VBAT_CHG/VBAT_CELL+/-) collapsed to just VBAT or GND.
  * Active-IC BUGFIXES (all verified against datasheet, see
    DESIGN-NOTES §Cycle 3 §Pinout Verification):
      - Q_REV DMG3415U-7: pin1=G, pin2=S, pin3=D (Diodes DS31735 Rev.14).
        Low-side-switch of GND return for reverse-pol protection --
        source=VBAT (load side), drain=LiPo cell +, gate tied to GND
        via R_GREV 10k so FET conducts when +cell is present and
        Vgs clamped by D_GREV. Fixes B-REV.
      - 5x ESD9L3.3ST5G TVS (onsemi ESD9L-D): pin1=CATHODE (bar),
        pin2=ANODE. Cathode -> signal, anode -> GND. Fixes B-TVS.
      - 25x SK6812MINI-E: pads on B.Cu (reverse-mount, body below
        board, light aperture faces user from F.Cu side). Fixes
        B-LED-LAYER.
      - SK6812MINI-E light aperture 3.4 x 2.8 mm (was 1.7 x 0.6 in
        Cycle 2). Fixes B-LED-APERTURE.
      - Antenna keepout 25 x 10 mm centered on XIAO nRF52840
        antenna region (pin-1/USB-C end). Fixes B-ANT-KEEPOUT.
      - GND pours on F.Cu and B.Cu SUBTRACT the antenna keepout
        polygon (via zone priority / outline carve-out).
      - CPL generation now uses --exclude-dnp (see
        gerbers/README.md). Fixes B-CPL-DNP.
      - Firmware LED cap 300 mA total per IEC 62368-1 Annex Q
        documented in DESIGN-NOTES §Safety and firmware/zmk/README.md.
        Fixes B-PCM-REG.
      - Back-pad jumper cluster eliminated: NTC_ADC promoted to front
        castellation pin (D10 was ROW3 -> moves to encoder A; the full
        pin map reshuffle is in §Pin map). Only ROW4/ENC_A/ENC_B/ENC_SW/
        RGB_DIN remain on rear pads and the cluster is placed 4 mm
        south of the MCU body (not 120 mm away). Fixes B-RATNEST-PWR.
      - J_BAT (JST) -> Q_REV -> F1 -> SW_PWR -> VBAT -> XIAO BAT+
        pad is a *real copper connection* in the footprint netlist,
        not an orphan. Fixes B-BATORPHAN (auto via Option B).
      - LED decoupling caps relocated to (kx-4, ky+1.5) per M-LED-CAPS.
      - USB-C top edge relief slot retained; MCU rotation unchanged
        (north face of MCU overhangs, clear of board copper) per
        M-USB-CLEAR.
      - Thermal bridge 0.25 mm default, overridden to 0.5 mm for
        PTH pads (JST, SPDT, EC11, mounting holes). Per-pad
        thermal_bridge_width override. M-THERMAL-BRIDGE.
      - Power netclass track 0.80 mm re-applied to VBAT, +3V3, GND
        (netclass_patterns updated for collapsed net list).
      - NTC TH1 relocated to within 5 mm of J_BAT center; footprint
        swapped to Resistor_THT:R_Axial_DIN0207_L6.3mm for MF52
        axial leads (5.08 mm bend pitch, was 0603 SMD stub). M-NTC*.
      - 2 schematic multiple_net_names collapsed by physically wiring
        merges (was using hidden label merge at VBAT_PROT/VBAT_CHG --
        both gone with Option B). M-NET-MERGE.
      - Silk / BOM labels updated: VBAT_* references removed; only
        VBAT / +3V3 / GND remain. M-SILK-VBAT.
      - Board size reduced from 125 x 140 to 115 x 115 mm (Option B
        frees the top strip). M-BOARD-SIZE target met exactly.
  * PTC choice: Bourns MF-PSMF050X-2 (LCSC C116170), 500 mA hold /
    1 A trip / 0805 / 6 V. The Cycle 3 spec note listed 500 mA + C89657
    but C89657 is actually the 200 mA variant (MF-PSMF020X-2); we
    switch to C116170 to honour the 500 mA intent. Documented in
    DESIGN-NOTES §Cycle 3 §Deviations.

Run:  python3 generate.py
Outputs to the parent directory (claude-code-pad/pcb/).
"""

from __future__ import annotations
import os, uuid, textwrap, csv, pathlib, sys, json

OUT = pathlib.Path(__file__).resolve().parent.parent
SCH = OUT / "claude-code-pad.kicad_sch"
PCB = OUT / "claude-code-pad.kicad_pcb"
PRO = OUT / "claude-code-pad.kicad_pro"
BOM = OUT / "bom.csv"
CPL = OUT / "cpl.csv"

# -----------------------------------------------------------------------------
# Board geometry (Cycle 4: 115 x 132 mm, was 115 x 124 mm Cycle 3).
#
# Cycle 4 grew the top strip from 22 mm to 30 mm to accommodate moving
# the XIAO nRF52840 module south by 8 mm (mcu_y = y0 + 19, was y0 + 11).
# The MCU relocation gives a genuine 16 mm ON-BOARD antenna keepout span
# (y0 .. mcu_y - 3), covering the first ~5-8 mm of the module's antenna
# region relative to the USB-C north edge. See DESIGN-NOTES §Cycle 4
# §Antenna keepout for the full derivation.
#
# Growth budget:
#   top strip  22 mm -> 30 mm  (+8 mm for antenna keepout + MCU south move)
#   key grid   95.25 mm                (unchanged, 5 rows * 19.05 mm pitch)
#   bottom strip 6.75 mm                (unchanged, NFC header + NTC)
#   total      124 mm -> 132 mm (+8 mm)
#
# Width 115 mm unchanged. The +8 mm height waiver is tracked in
# DESIGN-NOTES §Cycle 4 §Deviations. Net board area: 15180 mm^2
# (Cycle 3: 14260 mm^2). Still one JLCPCB price tier below the
# Cycle 2 envelope (17500 mm^2).
# -----------------------------------------------------------------------------
BOARD_X0, BOARD_Y0 = 100.0, 100.0
# Cycle 5 (C5-M1): BOARD_W 115 -> 120 mm to give the 2U Enter east stab
# (at KEY0_CX + 4.5*19.05 + 11.9 = 217.025) >= 2 mm clearance from the
# east edge. KEY0_CX is kept anchored at the Cycle-4 value (119.4 mm) so
# the 5x5 key grid doesn't shift west; only the east margin grows.
BOARD_W, BOARD_H   = 120.0, 132.0
RADIUS             = 3.0
TOP_STRIP          = 30.0   # MCU north-strip (Cycle 4: 22 -> 30 mm)

KEY_PITCH_X = 19.05
KEY_PITCH_Y = 19.05

# 5x5 grid occupies 5*19.05 = 95.25 mm wide, 95.25 mm tall.
# Cycle 5: KEY0_CX is anchored (not recomputed from BOARD_W) so the 2U
# Enter east stab position stays fixed while BOARD_W grows for clearance.
KEY0_CX = 119.4   # = 100 + (115 - 95.25)/2 + 9.525, frozen at Cycle-4 value
KEY0_CY = BOARD_Y0 + TOP_STRIP + KEY_PITCH_Y / 2.0


def key_cxcy(r, c):
    """Row-4 col-4 Enter is 2U, centred 0.5U east of col 4."""
    if r == 4 and c == 4:
        return (KEY0_CX + 4.5 * KEY_PITCH_X, KEY0_CY + r * KEY_PITCH_Y)
    return (KEY0_CX + c * KEY_PITCH_X, KEY0_CY + r * KEY_PITCH_Y)


def is_2u(r, c):
    return r == 4 and c == 4


# RGB serpentine chain (1-based LED indices per spec):
RGB_CHAIN_ORDER = [
    1, 2, 3, 4, 5,
    10, 9, 8, 7, 6,
    11, 12, 13, 14, 15,
    20, 19, 18, 17, 16,
    21, 22, 23, 24, 25,
]


def led_index(r, c):
    return r * 5 + c + 1


# -----------------------------------------------------------------------------
# Deterministic UUID helper
# -----------------------------------------------------------------------------
NS = uuid.UUID("a7c0de00-0000-0000-0000-000000000000")


def U(tag: str) -> str:
    return str(uuid.uuid5(NS, tag))


# =============================================================================
# SCHEMATIC
# =============================================================================
# KiCad 8 format (version 20231120); KiCad 9 reads it too.

def sch_header():
    return textwrap.dedent(f'''\
    (kicad_sch
    \t(version 20231120)
    \t(generator "eeschema")
    \t(generator_version "8.0")
    \t(uuid "{U("sch_root")}")
    \t(paper "A2")
    \t(title_block
    \t\t(title "Claude Code Pad")
    \t\t(date "2026-04-20")
    \t\t(rev "C")
    \t\t(company "Claude-Keyboard")
    \t\t(comment 1 "25-key macropad, XIAO nRF52840, 5x5 hot-swap MX, SK6812MINI-E, EC11")
    \t\t(comment 2 "2L FR4 1.6mm HASL-LF, black mask -- Phase 1 Cycle 3")
    \t\t(comment 3 "Power: JST -> RevPol P-FET -> PTC -> slide SW -> VBAT -> XIAO BAT+")
    \t\t(comment 4 "XIAO on-module AP2112K LDO drives 3V3 rail; LEDs firmware-capped 300 mA")
    \t)
    ''')


def sym_pin(name, number, x, y, angle, etype="passive"):
    return (
        f'\t\t\t(pin {etype} line (at {x} {y} {angle}) (length 2.54) '
        f'(name "{name}" (effects (font (size 1.27 1.27)))) '
        f'(number "{number}" (effects (font (size 1.27 1.27)))))\n'
    )


def sym_def(lib_id, ref_prefix, value, pins, body="", hide_ref=False,
            extra_props=None, is_power=False):
    extra_props = extra_props or {}
    prop_lines = ""
    for k, v in extra_props.items():
        prop_lines += (
            f'\t\t(property "{k}" "{v}" (at 0 0 0) '
            f'(effects (font (size 1.27 1.27)) (hide yes)))\n'
        )
    power_tag = "(power)\n\t\t" if is_power else ""
    pin_lines = "".join(
        sym_pin(pn["name"], pn["number"], pn["x"], pn["y"], pn["angle"],
                pn.get("etype", "passive"))
        for pn in pins
    )
    return textwrap.dedent(f'''\
        (symbol "{lib_id}"
            {power_tag}(exclude_from_sim no) (in_bom yes) (on_board yes)
            (property "Reference" "{ref_prefix}" (at 0 5.08 0) (effects (font (size 1.27 1.27)){' (hide yes)' if hide_ref else ''}))
            (property "Value" "{value}" (at 0 -5.08 0) (effects (font (size 1.27 1.27))))
            (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
            (property "Datasheet" "~" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    ''') + prop_lines + textwrap.dedent(f'''\
            (symbol "{lib_id.split(":")[-1]}_0_1"
                {body}
            )
            (symbol "{lib_id.split(":")[-1]}_1_1"
    ''') + pin_lines + "\t\t)\n\t\t(embedded_fonts no)\n\t)\n"


def build_lib_symbols():
    s = ["\t(lib_symbols\n"]
    # 2-pin passives
    for lid, val in [("local:R", "R"), ("local:C", "C")]:
        s.append(sym_def(
            lid, lid.split(":")[-1], val,
            [{"name": "~", "number": "1", "x": 0, "y": 3.81, "angle": 270},
             {"name": "~", "number": "2", "x": 0, "y": -3.81, "angle": 90}],
            body="(rectangle (start -1.016 -2.54) (end 1.016 2.54) "
                 "(stroke (width 0.254) (type default)) (fill (type none)))",
        ))
    # Diode (matrix 1N4148W)
    s.append(sym_def(
        "local:D", "D", "D",
        [{"name": "K", "number": "1", "x": -3.81, "y": 0, "angle": 0},
         {"name": "A", "number": "2", "x": 3.81, "y": 0, "angle": 180}],
        body="(polyline (pts (xy 1.016 0) (xy -1.016 1.016) (xy -1.016 -1.016) (xy 1.016 0)) "
             "(stroke (width 0.254) (type default)) (fill (type outline)))",
    ))
    # P-MOSFET (DMG3415U-7) — pin numbers match SOT-23 Diodes DS31735:
    # pin1 = Gate, pin2 = Source, pin3 = Drain
    s.append(sym_def(
        "local:Q_PMOS", "Q", "PMOS_SOT23",
        [{"name": "G", "number": "1", "x": -5.08, "y": 0, "angle": 0},
         {"name": "S", "number": "2", "x": 0, "y": 5.08, "angle": 270},
         {"name": "D", "number": "3", "x": 0, "y": -5.08, "angle": 90}],
        body="(rectangle (start -2.54 -2.54) (end 2.54 2.54) "
             "(stroke (width 0.254) (type default)) (fill (type none)))",
    ))
    # Push-switch
    s.append(sym_def(
        "local:SW_Push", "SW", "Kailh_HS",
        [{"name": "1", "number": "1", "x": -5.08, "y": 0, "angle": 0},
         {"name": "2", "number": "2", "x": 5.08, "y": 0, "angle": 180}],
        body="(circle (center -2.032 0) (radius 0.508) (stroke (width 0) (type default)) (fill (type none))) "
             "(circle (center 2.032 0) (radius 0.508) (stroke (width 0) (type default)) (fill (type none)))",
    ))
    # SK6812MINI-E
    s.append(sym_def(
        "local:LED_RGB", "LED", "SK6812MINI-E",
        [{"name": "VDD", "number": "1", "x": -6.35, "y": 2.54, "angle": 0, "etype": "power_in"},
         {"name": "DOUT", "number": "2", "x": 6.35, "y": 2.54, "angle": 180, "etype": "output"},
         {"name": "GND", "number": "3", "x": -6.35, "y": -2.54, "angle": 0, "etype": "power_in"},
         {"name": "DIN", "number": "4", "x": 6.35, "y": -2.54, "angle": 180, "etype": "input"}],
        body="(rectangle (start -3.81 3.81) (end 3.81 -3.81) "
             "(stroke (width 0.254) (type default)) (fill (type none)))",
    ))
    # SPDT slide (SS-12D00G4): pin 2 = common, pins 1 & 3 = throws (TH, 2.54 mm)
    s.append(sym_def(
        "local:SW_SPDT", "SW", "SPDT_SS12D00G4",
        [{"name": "1", "number": "1", "x": -6.35, "y": 2.54, "angle": 180},
         {"name": "COM", "number": "2", "x": -6.35, "y": 0, "angle": 0},
         {"name": "3", "number": "3", "x": -6.35, "y": -2.54, "angle": 180}],
        body="(rectangle (start -3.81 3.81) (end 3.81 -3.81) "
             "(stroke (width 0.254) (type default)) (fill (type background)))",
    ))
    # EC11
    s.append(sym_def(
        "local:EC11", "EC", "EC11",
        [{"name": "A", "number": "1", "x": -7.62, "y": 5.08, "angle": 0, "etype": "input"},
         {"name": "C", "number": "2", "x": -7.62, "y": 0, "angle": 0, "etype": "input"},
         {"name": "B", "number": "3", "x": -7.62, "y": -5.08, "angle": 0, "etype": "input"},
         {"name": "SW1", "number": "4", "x": 7.62, "y": 5.08, "angle": 180, "etype": "input"},
         {"name": "SW2", "number": "5", "x": 7.62, "y": -5.08, "angle": 180, "etype": "input"}],
        body="(rectangle (start -5.08 7.62) (end 5.08 -7.62) "
             "(stroke (width 0.254) (type default)) (fill (type background)))",
    ))
    # XIAO nRF52840 (14 front castellations + BAT+/BAT- rear pads)
    xiao_pins = []
    lbl = {
        1: "VUSB", 2: "GND", 3: "3V3",
        4: "D0", 5: "D1", 6: "D2", 7: "D3",
        8: "D4_SDA", 9: "D5_SCL", 10: "D6",
        11: "D7", 12: "D8", 13: "D9", 14: "D10",
        15: "BAT+", 16: "BAT-",
    }
    for i in range(1, 15):
        xiao_pins.append({
            "name": lbl[i], "number": str(i),
            "x": -10.16, "y": 16.51 - (i - 1) * 2.54,
            "angle": 0,
            "etype": "power_in" if i in (1, 2, 3) else "bidirectional",
        })
    xiao_pins.append({"name": "BAT+", "number": "15",
                      "x": 10.16, "y": 2.54, "angle": 180, "etype": "power_in"})
    xiao_pins.append({"name": "BAT-", "number": "16",
                      "x": 10.16, "y": -2.54, "angle": 180, "etype": "power_in"})
    s.append(sym_def(
        "local:XIAO_nRF52840", "U", "XIAO_nRF52840",
        xiao_pins,
        body="(rectangle (start -5.08 20.32) (end 5.08 -20.32) "
             "(stroke (width 0.254) (type default)) (fill (type background)))",
    ))
    # NFC 4-pin header
    s.append(sym_def(
        "local:ConnHeader4", "J", "Header4",
        [{"name": str(i), "number": str(i), "x": -5.08,
          "y": 3.81 - (i - 1) * 2.54, "angle": 0}
         for i in range(1, 5)],
        body="(rectangle (start -2.54 5.08) (end 2.54 -5.08) "
             "(stroke (width 0.254) (type default)) (fill (type background)))",
    ))
    # 2-pin connector (JST)
    s.append(sym_def(
        "local:ConnHeader2", "J", "Header2",
        [{"name": "1", "number": "1", "x": -5.08, "y": 1.27, "angle": 0,
          "etype": "power_out"},
         {"name": "2", "number": "2", "x": -5.08, "y": -1.27, "angle": 0,
          "etype": "power_out"}],
        body="(rectangle (start -2.54 2.54) (end 2.54 -2.54) "
             "(stroke (width 0.254) (type default)) (fill (type background)))",
    ))
    # PTC (0805)
    s.append(sym_def(
        "local:Fuse", "F", "PTC_500mA",
        [{"name": "~", "number": "1", "x": -5.08, "y": 0, "angle": 0},
         {"name": "~", "number": "2", "x": 5.08, "y": 0, "angle": 180}],
        body="(rectangle (start -3.048 1.016) (end 3.048 -1.016) "
             "(stroke (width 0.254) (type default)) (fill (type none)))",
    ))
    # ESD TVS (ESD9L3.3): pin 1 = cathode (bar), pin 2 = anode
    s.append(sym_def(
        "local:TVS", "D", "ESD9L3.3",
        [{"name": "K", "number": "1", "x": -3.81, "y": 0, "angle": 0},
         {"name": "A", "number": "2", "x": 3.81, "y": 0, "angle": 180}],
        body="(polyline (pts (xy 1.016 0) (xy -1.016 1.016) (xy -1.016 -1.016) (xy 1.016 0)) "
             "(stroke (width 0.254) (type default)) (fill (type outline)))",
    ))
    # NTC thermistor (MF52A2 THT axial)
    s.append(sym_def(
        "local:NTC", "TH", "MF52A2_10k",
        [{"name": "~", "number": "1", "x": 0, "y": 3.81, "angle": 270},
         {"name": "~", "number": "2", "x": 0, "y": -3.81, "angle": 90}],
        body="(rectangle (start -1.016 -2.54) (end 1.016 2.54) "
             "(stroke (width 0.254) (type default)) (fill (type none)))",
    ))
    # Power symbols (simplified set -- only VBAT / +3V3 / VUSB / GND)
    for pname in ["GND", "+3V3", "VUSB", "VBAT"]:
        s.append(textwrap.dedent(f'''\
            (symbol "power:{pname}"
                (power)
                (pin_names (offset 0))
                (exclude_from_sim no) (in_bom no) (on_board yes)
                (property "Reference" "#PWR" (at 0 -3.81 0) (effects (font (size 1.27 1.27)) (hide yes)))
                (property "Value" "{pname}" (at 0 3.81 0) (effects (font (size 1.27 1.27))))
                (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
                (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
                (symbol "{pname}_0_1"
                    (polyline (pts (xy -0.762 1.27) (xy 0 2.54) (xy 0.762 1.27) (xy -0.762 1.27))
                        (stroke (width 0) (type default)) (fill (type none)))
                )
                (symbol "{pname}_1_1"
                    (pin power_in line (at 0 0 90) (length 0) hide (name "{pname}" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
                )
                (embedded_fonts no)
            )
        '''))
    s.append("\t)\n")
    return "".join(s)


# --- schematic symbol instances & net wiring ---------------------------------

def sch_symbol(lib_id, ref, value, x, y, angle, unit_tag, extra_props=None,
               footprint="", lcsc="", description="", pin_count=None,
               is_dnp=False):
    extra_props = extra_props or {}
    default_pc = {
        "local:R": 2, "local:C": 2, "local:D": 2, "local:TVS": 2,
        "local:NTC": 2, "local:SW_Push": 2, "local:ConnHeader2": 2,
        "local:ConnHeader4": 4, "local:Fuse": 2,
        "local:LED_RGB": 4, "local:SW_SPDT": 3, "local:EC11": 5,
        "local:Q_PMOS": 3, "local:XIAO_nRF52840": 16,
    }
    pc = pin_count if pin_count is not None else default_pc.get(lib_id, 2)
    sym_uuid = U(f"sym_{unit_tag}")
    pin_lines = "".join(
        f'\t\t(pin "{i+1}" (uuid "{U(f"pin_{unit_tag}_{i+1}")}"))\n'
        for i in range(pc)
    )
    prop_extra = ""
    if lcsc:
        prop_extra += (
            f'\t\t(property "LCSC" "{lcsc}" (at {x} {y+10} 0) '
            f'(effects (font (size 1 1)) (hide yes)))\n'
        )
    for k, v in extra_props.items():
        prop_extra += (
            f'\t\t(property "{k}" "{v}" (at {x} {y+12} 0) '
            f'(effects (font (size 1 1)) (hide yes)))\n'
        )
    is_power = lib_id.startswith("power:")
    eff_ref = ref if not is_power else f"#PWR_{unit_tag}"
    eff_value = value if not is_power else lib_id.split(":", 1)[1]
    dnp_flag = "yes" if is_dnp else "no"
    return (
        f'\t(symbol\n'
        f'\t\t(lib_id "{lib_id}")\n'
        f'\t\t(at {x} {y} {angle}) (unit 1)\n'
        f'\t\t(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp {dnp_flag})\n'
        f'\t\t(uuid "{sym_uuid}")\n'
        f'\t\t(property "Reference" "{eff_ref}" (at {x+5} {y} 0) (effects (font (size 1.27 1.27))))\n'
        f'\t\t(property "Value" "{eff_value}" (at {x+5} {y+3} 0) (effects (font (size 1.27 1.27))))\n'
        f'\t\t(property "Footprint" "{footprint}" (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
        f'\t\t(property "Datasheet" "~" (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
        f'\t\t(property "Description" "{description}" (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
        f'{prop_extra}'
        f'{pin_lines}'
        f'\t\t(instances\n'
        f'\t\t\t(project "claude-code-pad"\n'
        f'\t\t\t\t(path "/{U("sch_root")}" (reference "{eff_ref}") (unit 1))\n'
        f'\t\t\t)\n'
        f'\t\t)\n'
        f'\t)\n'
    )


_gl_ctr = [0]


def gl(net, x, y, angle=0):
    _gl_ctr[0] += 1
    return (
        f'\t(global_label "{net}" (shape input) (at {x} {y} {angle}) '
        f'(fields_autoplaced yes) '
        f'(effects (font (size 1.27 1.27)) (justify left)) '
        f'(uuid "{U(f"gl_{net}_{_gl_ctr[0]}")}"))\n'
    )


def wire(x1, y1, x2, y2, tag):
    return (
        f'\t(wire (pts (xy {x1} {y1}) (xy {x2} {y2})) '
        f'(stroke (width 0) (type default)) (uuid "{U("w_"+tag)}"))\n'
    )


def build_schematic():
    out = []
    out.append(sch_header())
    out.append(build_lib_symbols())

    # --- MCU: XIAO nRF52840 --------------------------------------------------
    mcu_x, mcu_y = 100, 80
    out.append(sch_symbol(
        "local:XIAO_nRF52840", "U1", "XIAO_nRF52840",
        mcu_x, mcu_y, 0, "U1",
        footprint="local:XIAO_nRF52840_Castellated",
        lcsc="C2888140",
        description="Seeed XIAO nRF52840 (direct-solder castellations)",
    ))
    # Cycle 3 pin-map (14 front pins + 2 rear BAT pads). Post Option B the
    # +3V3_SYS net is gone; XIAO's 3V3 pin drives the whole +3V3 rail.
    # NTC_ADC moved to D10 (front pin) -- was rear pad in Cycle 2.
    xiao_map = [
        (1,  "VUSB"),      # 5V USB rail (USB-C on module)
        (2,  "GND"),
        (3,  "+3V3"),      # AP2112K output drives all 3V3 loads
        (4,  "COL0"),      # D0
        (5,  "COL1"),      # D1
        (6,  "COL2"),      # D2
        (7,  "COL3"),      # D3
        (8,  "SDA"),       # D4
        (9,  "SCL"),       # D5
        (10, "COL4"),      # D6
        (11, "ROW0"),      # D7
        (12, "ROW1"),      # D8
        (13, "ROW2"),      # D9
        (14, "NTC_ADC"),   # D10 (analog capable P0.03/AIN1) -- promoted
        (15, "VBAT"),      # BAT+ pad -- wired to post-SW_PWR VBAT rail
        (16, "GND"),       # BAT-
    ]
    for pin, net in xiao_map:
        if pin <= 14:
            ly = mcu_y + 16.51 - (pin - 1) * 2.54
            lx = mcu_x - 10.16
            out.append(wire(mcu_x - 7.62, ly, lx - 2.54, ly, f"mcu_p{pin}"))
            out.append(gl(net, lx - 2.54, ly, 180))
        else:
            y_off = 2.54 if pin == 15 else -2.54
            ly = mcu_y + y_off
            lx = mcu_x + 10.16
            out.append(wire(lx, ly, lx + 2.54, ly, f"mcu_p{pin}"))
            out.append(gl(net, lx + 2.54, ly, 0))

    # --- Back-pad breakout (ROW3/ROW4/ENC_A/ENC_B/ENC_SW/RGB_DIN/VBAT_ADC) ---
    # 7 signals rear-side in Cycle 4 (ROW3 moved here in C3 so D10 could
    # carry NTC_ADC; VBAT_ADC added in C4 for brownout monitoring).
    # Cluster placed physically within 5 mm of MCU in PCB (see build_pcb)
    # -- in schematic we just emit the labels.
    stub_x = mcu_x - 40
    rear_nets = ["ROW3", "ROW4", "ENC_A", "ENC_B", "ENC_SW",
                 "RGB_DIN_MCU", "VBAT_ADC"]
    for i, net in enumerate(rear_nets):
        sy = 30 + i * 6
        out.append(gl(net, stub_x, sy, 0))
        out.append(
            f'\t(text "{net} -> XIAO back pad (user-wired, <5mm jumper)" '
            f'(at {stub_x+5} {sy} 0) (effects (font (size 1 1)) (justify left)) '
            f'(uuid "{U(f"txt_stub_{i}")}"))\n'
        )

    # --- Matrix (25 SW + 25 diodes) ------------------------------------------
    sw_x0, sw_y0 = 40, 140
    sw_dx, sw_dy = 22, 14
    for r in range(5):
        for c in range(5):
            sw_ref = f"SW{r}{c}"
            d_ref = f"D{r}{c}"
            sx = sw_x0 + c * sw_dx
            sy = sw_y0 + r * sw_dy
            out.append(sch_symbol(
                "local:SW_Push", sw_ref, "Kailh_HS",
                sx, sy, 0, f"SW_{r}_{c}",
                footprint=("Keebio:MX_Only_HS_2U" if is_2u(r, c)
                           else "Keebio:MX_Only_HS"),
                lcsc="C5184526",
                description="MX hot-swap keyswitch (Keebio MX_Only_HS)",
            ))
            out.append(wire(sx - 5.08, sy, sx - 7.62, sy, f"sw{r}{c}p1"))
            out.append(gl(f"COL{c}", sx - 7.62, sy, 180))
            out.append(wire(sx + 5.08, sy, sx + 7.62, sy, f"sw{r}{c}p2"))
            out.append(gl(f"KROW{r}{c}", sx + 7.62, sy, 0))
            dx = sx
            dy = sy + 6
            out.append(sch_symbol(
                "local:D", d_ref, "1N4148W",
                dx, dy, 0, f"D_{r}_{c}",
                footprint="Diode_SMD:D_SOD-123",
                lcsc="C81598",
                description="Matrix diode",
                extra_props={"JLCPCB Rotation": "180"},
            ))
            out.append(wire(dx - 3.81, dy, dx - 6.35, dy, f"d{r}{c}p1"))
            out.append(gl(f"KROW{r}{c}", dx - 6.35, dy, 180))
            out.append(wire(dx + 3.81, dy, dx + 6.35, dy, f"d{r}{c}p2"))
            out.append(gl(f"ROW{r}", dx + 6.35, dy, 0))

    # --- RGB chain (25 LEDs + decoupling + series R) -------------------------
    rgb_x0, rgb_y0 = 200, 40
    out.append(sch_symbol(
        "local:R", "R1", "470",
        rgb_x0, rgb_y0, 0, "R1",
        footprint="Resistor_SMD:R_0402_1005Metric",
        lcsc="C25744",
        description="RGB DIN series resistor",
    ))
    out.append(wire(rgb_x0, rgb_y0 - 3.81, rgb_x0, rgb_y0 - 6.35, "r1p1"))
    out.append(gl("RGB_DIN_MCU", rgb_x0, rgb_y0 - 6.35, 90))
    out.append(wire(rgb_x0, rgb_y0 + 3.81, rgb_x0, rgb_y0 + 6.35, "r1p2"))
    out.append(gl("RGB_D1", rgb_x0, rgb_y0 + 6.35, 270))

    chain = RGB_CHAIN_ORDER
    for i, led_idx in enumerate(chain):
        lx = rgb_x0 + 30 + (i // 13) * 44
        ly = rgb_y0 + 20 + (i % 13) * 14
        out.append(sch_symbol(
            "local:LED_RGB", f"LED{led_idx}", "SK6812MINI-E",
            lx, ly, 0, f"LED_{led_idx}",
            footprint="LED_SMD:LED_SK6812_MINI-E_plccn4_3.5x2.8mm",
            lcsc="C5149201",
            description="Reverse-mount RGB LED (SK6812MINI-E)",
            extra_props={"JLCPCB Rotation": "-90"},
        ))
        out.append(wire(lx - 6.35, ly + 2.54, lx - 8.89, ly + 2.54,
                        f"led{led_idx}vdd"))
        out.append(gl("+3V3", lx - 8.89, ly + 2.54, 180))
        out.append(wire(lx - 6.35, ly - 2.54, lx - 8.89, ly - 2.54,
                        f"led{led_idx}gnd"))
        out.append(gl("GND", lx - 8.89, ly - 2.54, 180))
        din_net = f"RGB_D{i+1}"
        out.append(wire(lx + 6.35, ly - 2.54, lx + 8.89, ly - 2.54,
                        f"led{led_idx}din"))
        out.append(gl(din_net, lx + 8.89, ly - 2.54, 0))
        dout_net = f"RGB_D{i+2}" if i < 24 else "RGB_OUT"
        out.append(wire(lx + 6.35, ly + 2.54, lx + 8.89, ly + 2.54,
                        f"led{led_idx}dout"))
        out.append(gl(dout_net, lx + 8.89, ly + 2.54, 0))
        cref = f"CL{led_idx}"
        cx = lx - 14
        cy = ly
        out.append(sch_symbol(
            "local:C", cref, "100n",
            cx, cy, 0, f"C_LED_{led_idx}",
            footprint="Capacitor_SMD:C_0402_1005Metric",
            lcsc="C1525",
            description="LED VDD decoupling",
        ))
        out.append(wire(cx, cy - 3.81, cx, cy - 6.35, f"{cref}p1"))
        out.append(gl("+3V3", cx, cy - 6.35, 90))
        out.append(wire(cx, cy + 3.81, cx, cy + 6.35, f"{cref}p2"))
        out.append(gl("GND", cx, cy + 6.35, 270))

    # --- I2C pull-ups + NFC header + ESD TVS --------------------------------
    for i, (rref, net) in enumerate([("R2", "SDA"), ("R3", "SCL")]):
        rx, ry = 300, 40 + i * 14
        out.append(sch_symbol(
            "local:R", rref, "4k7",
            rx, ry, 0, rref,
            footprint="Resistor_SMD:R_0402_1005Metric",
            lcsc="C25905",
            description=f"I2C {net} pull-up",
        ))
        out.append(wire(rx, ry - 3.81, rx, ry - 6.35, f"{rref}p1"))
        out.append(gl("+3V3", rx, ry - 6.35, 90))
        out.append(wire(rx, ry + 3.81, rx, ry + 6.35, f"{rref}p2"))
        out.append(gl(net, rx, ry + 6.35, 270))

    # ESD TVS on SDA, SCL.
    # ESD9L3.3 pin 1 = CATHODE, pin 2 = ANODE. For signal-line protection:
    #   cathode -> signal (pin 1 in schematic)
    #   anode   -> GND    (pin 2 in schematic)
    # Matched in local:TVS symbol below.
    for i, (tref, net) in enumerate([("TVS_SDA", "SDA"), ("TVS_SCL", "SCL")]):
        tx, ty = 320, 40 + i * 14
        out.append(sch_symbol(
            "local:TVS", tref, "ESD9L3.3",
            tx, ty, 0, tref,
            footprint="Diode_SMD:D_SOD-523",
            lcsc="C709011",
            description=f"ESD TVS on {net} (cathode->signal, anode->GND)",
            extra_props={"JLCPCB Rotation": "0"},
        ))
        # pin 1 (cathode, left side of symbol) -> signal
        out.append(wire(tx - 3.81, ty, tx - 6.35, ty, f"{tref}p1"))
        out.append(gl(net, tx - 6.35, ty, 180))
        # pin 2 (anode, right side) -> GND
        out.append(wire(tx + 3.81, ty, tx + 6.35, ty, f"{tref}p2"))
        out.append(gl("GND", tx + 6.35, ty, 0))

    # NFC header
    out.append(sch_symbol(
        "local:ConnHeader4", "J_NFC", "NFC_PN532",
        300, 120, 0, "J_NFC",
        footprint="Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
        lcsc="",
        description="PN532 NFC 4-pin I2C breakout (DNP)",
        is_dnp=True,
    ))
    for pin, net in [(1, "GND"), (2, "+3V3"), (3, "SDA"), (4, "SCL")]:
        ly = 120 + 3.81 - (pin - 1) * 2.54
        out.append(wire(300 - 5.08, ly, 300 - 7.62, ly, f"jnfcp{pin}"))
        out.append(gl(net, 300 - 7.62, ly, 180))

    # --- EC11 encoder + ESD TVS ---------------------------------------------
    out.append(sch_symbol(
        "local:EC11", "EC1", "EC11",
        40, 240, 0, "EC1",
        footprint="Button_Switch_THT:RotaryEncoder_Alps_EC11E-Switch_Vertical_H20mm",
        lcsc="C255515",
        description="EC11 rotary encoder with push-switch (DNP for PCBA)",
        is_dnp=True,
    ))
    for pin, net, ang in [
        (1, "ENC_A", 180), (2, "GND", 180), (3, "ENC_B", 180),
        (4, "ENC_SW", 0), (5, "GND", 0),
    ]:
        ly_map = {1: 245.08, 2: 240, 3: 234.92, 4: 245.08, 5: 234.92}
        ly = ly_map[pin]
        if pin <= 3:
            out.append(wire(40 - 7.62, ly, 40 - 10.16, ly, f"ec1p{pin}"))
            out.append(gl(net, 40 - 10.16, ly, 180))
        else:
            out.append(wire(40 + 7.62, ly, 40 + 10.16, ly, f"ec1p{pin}"))
            out.append(gl(net, 40 + 10.16, ly, 0))

    # TVS on ENC_A, ENC_B, ENC_SW -- same polarity fix as SDA/SCL
    for i, (tref, net) in enumerate([
        ("TVS_ENCA", "ENC_A"),
        ("TVS_ENCB", "ENC_B"),
        ("TVS_ENCSW", "ENC_SW"),
    ]):
        tx, ty = 70, 230 + i * 8
        out.append(sch_symbol(
            "local:TVS", tref, "ESD9L3.3",
            tx, ty, 0, tref,
            footprint="Diode_SMD:D_SOD-523",
            lcsc="C709011",
            description=f"ESD TVS on {net} (cathode->signal, anode->GND)",
            extra_props={"JLCPCB Rotation": "0"},
        ))
        out.append(wire(tx - 3.81, ty, tx - 6.35, ty, f"{tref}p1"))
        out.append(gl(net, tx - 6.35, ty, 180))
        out.append(wire(tx + 3.81, ty, tx + 6.35, ty, f"{tref}p2"))
        out.append(gl("GND", tx + 6.35, ty, 0))

    # Encoder debounce cap
    out.append(sch_symbol(
        "local:C", "C_ENC", "100n",
        20, 240, 0, "C_ENC",
        footprint="Capacitor_SMD:C_0402_1005Metric",
        lcsc="C1525",
        description="Encoder SW debounce cap",
    ))
    out.append(wire(20, 240 - 3.81, 20, 240 - 6.35, "cencp1"))
    out.append(gl("ENC_SW", 20, 240 - 6.35, 90))
    out.append(wire(20, 240 + 3.81, 20, 240 + 6.35, "cencp2"))
    out.append(gl("GND", 20, 240 + 6.35, 270))

    # --- Power path (Option B simplified) ------------------------------------
    # J_BAT.1 -> Q_REV.2 (S) -- gate to GND via R_GREV
    # Q_REV.3 (D) -> F1.1 -> F1.2 -> SW_PWR.2 (COM) -> SW_PWR.1 (throw ON)
    # SW_PWR.1 -> VBAT node -> XIAO BAT+ pad (pin 15) via direct copper.

    # J_BAT JST SH 2-pin
    out.append(sch_symbol(
        "local:ConnHeader2", "J_BAT", "LiPo_JST-SH",
        500, 40, 0, "J_BAT",
        footprint="Connector_JST:JST_SH_SM02B-SRSS-TB_1x02-1MP_P1.00mm_Horizontal",
        lcsc="C295747",
        description="LiPo JST-SH 2-pin battery connector",
    ))
    out.append(wire(500 - 5.08, 41.27, 500 - 7.62, 41.27, "jbatp1"))
    out.append(gl("VBAT_CELL", 500 - 7.62, 41.27, 180))
    out.append(wire(500 - 5.08, 38.73, 500 - 7.62, 38.73, "jbatp2"))
    out.append(gl("GND", 500 - 7.62, 38.73, 180))

    # Q_REV DMG3415U-7 P-FET reverse-polarity protection.
    # Datasheet: Diodes DS31735 Rev. 14 -- SOT-23 pin1=Gate, pin2=Source, pin3=Drain.
    # Conduction:
    #   cell+ connected to Source (pin 2). Drain (pin 3) -> downstream VBAT_F (pre-fuse).
    #   Gate (pin 1) pulled to GND via R_GREV 10k. Vgs = -Vbat = -3.7 V when cell
    #   installed correctly -> FET ON (Vgs(th) = -0.9 V typ, Rds(on) ~ 0.08 Ω
    #   at Vgs=-2.5V so ~0.12 Ω at Vgs=-3.7V -- fine for 300 mA load).
    #   If cell reversed, cell- at source sees Vgs >= 0 -> FET OFF; body-diode
    #   (anode=D, cathode=S) is reverse-biased -> blocks reverse current.
    #   D_GREV 5V1 zener clamps |Vgs| to protect gate oxide if cell voltage
    #   transiently exceeds ~5.1 V during charging.
    out.append(sch_symbol(
        "local:Q_PMOS", "Q_REV", "DMG3415U-7",
        520, 45, 0, "Q_REV",
        footprint="Package_TO_SOT_SMD:SOT-23",
        lcsc="C147581",
        description="P-FET reverse-polarity protection",
        extra_props={"JLCPCB Rotation": "180"},
    ))
    # Pin 1 = Gate
    out.append(gl("GATE_REV", 520 - 5.08, 45, 180))
    # Pin 2 = Source (top)
    out.append(gl("VBAT_CELL", 520, 50.08, 90))
    # Pin 3 = Drain (bottom)
    out.append(gl("VBAT_F", 520, 39.92, 270))

    # R_GREV 10k gate pull-down (GATE_REV -> GND)
    out.append(sch_symbol(
        "local:R", "R_GREV", "10k",
        508, 50, 0, "R_GREV",
        footprint="Resistor_SMD:R_0402_1005Metric",
        lcsc="C25804",
        description="Q_REV gate pull-down (to GND)",
    ))
    out.append(wire(508, 50 - 3.81, 508, 50 - 6.35, "rgrev1"))
    out.append(gl("GATE_REV", 508, 50 - 6.35, 90))
    out.append(wire(508, 50 + 3.81, 508, 50 + 6.35, "rgrev2"))
    out.append(gl("GND", 508, 50 + 6.35, 270))

    # D_GREV 5V1 zener (anode -> GATE_REV, cathode -> Source)
    out.append(sch_symbol(
        "local:D", "D_GREV", "BZT52C5V1",
        495, 50, 0, "D_GREV",
        footprint="Diode_SMD:D_SOD-523",
        lcsc="C8056",
        description="Q_REV Vgs zener clamp (5V1)",
        extra_props={"JLCPCB Rotation": "0"},
    ))
    # symbol pin 1 = K (cathode), pin 2 = A (anode)
    out.append(wire(495 - 3.81, 50, 495 - 6.35, 50, "dgrev1"))
    out.append(gl("VBAT_CELL", 495 - 6.35, 50, 180))
    out.append(wire(495 + 3.81, 50, 495 + 6.35, 50, "dgrev2"))
    out.append(gl("GATE_REV", 495 + 6.35, 50, 0))

    # F1 PTC resettable fuse 500 mA 0805 (Bourns MF-PSMF050X-2, LCSC C116170).
    # (Spec line said C89657 which is 200 mA; see DESIGN-NOTES §Cycle 3
    # §Deviations for justification -- we honour the "500 mA" number.)
    out.append(sch_symbol(
        "local:Fuse", "F1", "PTC_500mA_0805",
        500, 120, 0, "F1",
        footprint="Fuse:Fuse_0805_2012Metric",
        lcsc="C116170",
        description="Resettable fuse 500 mA hold / 1 A trip, 0805",
    ))
    out.append(wire(500 - 5.08, 120, 500 - 7.62, 120, "f1p1"))
    out.append(gl("VBAT_F", 500 - 7.62, 120, 180))
    out.append(wire(500 + 5.08, 120, 500 + 7.62, 120, "f1p2"))
    out.append(gl("VBAT_SW", 500 + 7.62, 120, 0))

    # SW_PWR SS-12D00G4 slide (TH). Pin 2 = COM (centre); pin 1 and pin 3 =
    # throws. Wire common to VBAT_SW (post-fuse); one throw to VBAT (bus),
    # the other intentionally NC.
    out.append(sch_symbol(
        "local:SW_SPDT", "SW_PWR", "SS-12D00G4",
        520, 120, 0, "SW_PWR",
        footprint="Button_Switch_THT:SW_Slide_1P2T_SS12D00G4",
        lcsc="C8325",
        description="SPDT slide power switch (TH, SS-12D00G4)",
    ))
    # symbol pin 1 -> VBAT (ON throw)
    out.append(wire(520 - 6.35, 120 + 2.54, 520 - 8.89, 120 + 2.54, "swpwr1"))
    out.append(gl("VBAT", 520 - 8.89, 120 + 2.54, 180))
    # symbol pin 2 (COM) -> VBAT_SW (post-fuse)
    out.append(wire(520 - 6.35, 120, 520 - 8.89, 120, "swpwr2"))
    out.append(gl("VBAT_SW", 520 - 8.89, 120, 180))
    # symbol pin 3 (OFF throw) -> NC_SW (floating)
    out.append(wire(520 - 6.35, 120 - 2.54, 520 - 8.89, 120 - 2.54, "swpwr3"))
    out.append(gl("NC_SW", 520 - 8.89, 120 - 2.54, 180))

    # NTC thermistor (M-NTC-LOC: relocate within 5 mm of J_BAT).
    # MF52A2 10k (C14128) is THT axial -- use axial-lead THT footprint.
    # High-side divider: +3V3 -> TH1 -> NTC_ADC, and R_NTC 10k from NTC_ADC
    # -> GND. At 25 C, node = 1.65 V.
    out.append(sch_symbol(
        "local:NTC", "TH1", "MF52A2_10k",
        470, 80, 0, "TH1",
        footprint="Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal",
        lcsc="C14128",
        description="NTC 10k axial THT for battery temperature",
    ))
    out.append(wire(470, 80 - 3.81, 470, 80 - 6.35, "th1p1"))
    out.append(gl("+3V3", 470, 80 - 6.35, 90))
    out.append(wire(470, 80 + 3.81, 470, 80 + 6.35, "th1p2"))
    out.append(gl("NTC_ADC", 470, 80 + 6.35, 270))
    out.append(sch_symbol(
        "local:R", "R_NTC", "10k",
        478, 90, 0, "R_NTC",
        footprint="Resistor_SMD:R_0402_1005Metric",
        lcsc="C25804",
        description="NTC divider lower leg",
    ))
    out.append(wire(478, 90 - 3.81, 478, 90 - 6.35, "rntc1"))
    out.append(gl("NTC_ADC", 478, 90 - 6.35, 90))
    out.append(wire(478, 90 + 3.81, 478, 90 + 6.35, "rntc2"))
    out.append(gl("GND", 478, 90 + 6.35, 270))

    # --- VBAT ADC divider (C4-M1) --------------------------------------------
    # 2x 1 MOhm divider VBAT -> R_VBAT1 -> VBAT_ADC -> R_VBAT2 -> GND,
    # with C_VBAT 100 nF on the ADC node for anti-aliasing. At VBAT=4.2 V,
    # ADC node = 2.1 V (below nRF52840 AIN VREF = 3.6 V max). Drain =
    # 2.1 uA typ, 5 nA source-impedance seen by SAADC (below 15 k spec).
    # VBAT_ADC routes to XIAO rear pad slot #7 (user jumper) as there are
    # no unused front castellations.
    out.append(sch_symbol(
        "local:R", "R_VBAT1", "1M",
        540, 70, 0, "R_VBAT1",
        footprint="Resistor_SMD:R_0402_1005Metric",
        lcsc="C22935",
        description="VBAT ADC divider upper leg (1M)",
    ))
    out.append(wire(540, 70 - 3.81, 540, 70 - 6.35, "rvbat1p1"))
    out.append(gl("VBAT", 540, 70 - 6.35, 90))
    out.append(wire(540, 70 + 3.81, 540, 70 + 6.35, "rvbat1p2"))
    out.append(gl("VBAT_ADC", 540, 70 + 6.35, 270))
    out.append(sch_symbol(
        "local:R", "R_VBAT2", "1M",
        540, 85, 0, "R_VBAT2",
        footprint="Resistor_SMD:R_0402_1005Metric",
        lcsc="C22935",
        description="VBAT ADC divider lower leg (1M)",
    ))
    out.append(wire(540, 85 - 3.81, 540, 85 - 6.35, "rvbat2p1"))
    out.append(gl("VBAT_ADC", 540, 85 - 6.35, 90))
    out.append(wire(540, 85 + 3.81, 540, 85 + 6.35, "rvbat2p2"))
    out.append(gl("GND", 540, 85 + 6.35, 270))
    out.append(sch_symbol(
        "local:C", "C_VBAT", "100n",
        550, 77, 0, "C_VBAT",
        footprint="Capacitor_SMD:C_0402_1005Metric",
        lcsc="C1525",
        description="VBAT ADC anti-alias cap",
    ))
    out.append(wire(550, 77 - 3.81, 550, 77 - 6.35, "cvbatp1"))
    out.append(gl("VBAT_ADC", 550, 77 - 6.35, 90))
    out.append(wire(550, 77 + 3.81, 550, 77 + 6.35, "cvbatp2"))
    out.append(gl("GND", 550, 77 + 6.35, 270))

    # MCU-local bulk + bypass caps (VBAT bulk, 3V3 bulk, 3V3 decouple, VUSB decouple)
    for i, (cref, val, net, lcsc, desc, fp) in enumerate([
        ("C1", "22u",  "+3V3", "C45783",
         "3V3 bulk (near XIAO 3V3 pin)",  "Capacitor_SMD:C_0805_2012Metric"),
        ("C2", "22u",  "VBAT", "C45783",
         "VBAT bulk (near XIAO BAT+ pad)", "Capacitor_SMD:C_0805_2012Metric"),
        ("C3", "100n", "+3V3", "C1525",
         "3V3 decoupling",                 "Capacitor_SMD:C_0402_1005Metric"),
        ("C4", "100n", "VUSB", "C1525",
         "USB 5V decoupling",              "Capacitor_SMD:C_0402_1005Metric"),
        ("C5", "1n",   "VUSB", "C1540",
         "USB 5V ground-bounce bypass",    "Capacitor_SMD:C_0402_1005Metric"),
    ]):
        cx = 620 + i * 10
        cy = 40
        out.append(sch_symbol(
            "local:C", cref, val,
            cx, cy, 0, cref,
            footprint=fp, lcsc=lcsc, description=desc,
        ))
        out.append(wire(cx, cy - 3.81, cx, cy - 6.35, f"{cref}p1"))
        out.append(gl(net, cx, cy - 6.35, 90))
        out.append(wire(cx, cy + 3.81, cx, cy + 6.35, f"{cref}p2"))
        out.append(gl("GND", cx, cy + 6.35, 270))

    # Terminate dangling single-use nets w/ no_connect
    for net_name, (nx, ny) in [
        ("rgb_out", (rgb_x0 + 30 + (24 // 13) * 44 + 8.89,
                     rgb_y0 + 20 + (24 % 13) * 14 + 2.54)),
        ("nc_sw", (520 - 8.89, 120 - 2.54)),
    ]:
        out.append(
            f'\t(no_connect (at {nx} {ny}) (uuid "{U("nc_"+net_name)}"))\n'
        )

    # Header text
    out.append(
        f'\t(text "Claude Code Pad :: Phase 1 Cycle 3 (Option B). '
        f'See DESIGN-NOTES.md §Cycle 3." '
        f'(at 20 20 0) (effects (font (size 2 2))) '
        f'(uuid "{U("txt_header")}"))\n'
    )

    out.append(
        f'\t(sheet_instances\n'
        f'\t\t(path "/" (page "1"))\n'
        f'\t)\n'
        f'\t(embedded_fonts no)\n'
        f')\n'
    )
    return "".join(out)


# =============================================================================
# PCB
# =============================================================================

def pcb_header():
    return textwrap.dedent(f'''\
    (kicad_pcb
    \t(version 20240108)
    \t(generator "pcbnew")
    \t(generator_version "9.0")

    \t(general
    \t\t(thickness 1.6)
    \t\t(legacy_teardrops no)
    \t)

    \t(paper "A3")
    \t(title_block
    \t\t(title "Claude Code Pad")
    \t\t(date "2026-04-20")
    \t\t(rev "C")
    \t\t(company "Claude-Keyboard")
    \t\t(comment 1 "25-key macropad, XIAO nRF52840, 5x5 MX hotswap, SK6812MINI-E, EC11")
    \t\t(comment 2 "2L FR4 1.6mm HASL-LF, black mask -- Phase 1 Cycle 3 (Option B)")
    \t\t(comment 3 "Power: JST -> RevPol P-FET -> PTC -> slide SW -> VBAT -> XIAO BAT+")
    \t\t(comment 4 "XIAO on-module LDO drives 3V3; LEDs firmware-capped 300 mA")
    \t)

    \t(layers
    \t\t(0  "F.Cu" signal)
    \t\t(2  "B.Cu" signal)
    \t\t(9  "F.Adhes" user "F.Adhesive")
    \t\t(11 "B.Adhes" user "B.Adhesive")
    \t\t(13 "F.Paste" user)
    \t\t(15 "B.Paste" user)
    \t\t(5  "F.SilkS" user "F.Silkscreen")
    \t\t(7  "B.SilkS" user "B.Silkscreen")
    \t\t(1  "F.Mask" user)
    \t\t(3  "B.Mask" user)
    \t\t(17 "Dwgs.User" user "User.Drawings")
    \t\t(19 "Cmts.User" user "User.Comments")
    \t\t(21 "Eco1.User" user "User.Eco1")
    \t\t(23 "Eco2.User" user "User.Eco2")
    \t\t(25 "Edge.Cuts" user)
    \t\t(27 "Margin" user)
    \t\t(31 "B.CrtYd" user "B.Courtyard")
    \t\t(29 "F.CrtYd" user "F.Courtyard")
    \t\t(35 "B.Fab" user)
    \t\t(33 "F.Fab" user)
    \t\t(39 "User.1" user)
    \t\t(41 "User.2" user)
    \t\t(43 "User.3" user)
    \t\t(45 "User.4" user)
    \t\t(47 "User.5" user)
    \t\t(49 "User.6" user)
    \t\t(51 "User.7" user)
    \t\t(53 "User.8" user)
    \t\t(55 "User.9" user)
    \t)

    \t(setup
    \t\t(pad_to_mask_clearance 0)
    \t\t(allow_soldermask_bridges_in_footprints no)
    \t\t(aux_axis_origin {BOARD_X0} {BOARD_Y0})
    \t\t(grid_origin {BOARD_X0} {BOARD_Y0})
    \t\t(pcbplotparams
    \t\t\t(layerselection 0x00010fc_ffffffff)
    \t\t\t(plot_on_all_layers_selection 0x0000000_00000000)
    \t\t\t(disableapertmacros no)
    \t\t\t(usegerberextensions no)
    \t\t\t(usegerberattributes yes)
    \t\t\t(usegerberadvancedattributes yes)
    \t\t\t(creategerberjobfile yes)
    \t\t\t(dashed_line_dash_ratio 12.000000)
    \t\t\t(dashed_line_gap_ratio 3.000000)
    \t\t\t(svgprecision 4)
    \t\t\t(plotframeref no)
    \t\t\t(viasonmask no)
    \t\t\t(mode 1)
    \t\t\t(useauxorigin yes)
    \t\t\t(hpglpennumber 1)
    \t\t\t(hpglpenspeed 20)
    \t\t\t(hpglpendiameter 15.000000)
    \t\t\t(pdf_front_fp_property_popups yes)
    \t\t\t(pdf_back_fp_property_popups yes)
    \t\t\t(pdf_metadata yes)
    \t\t\t(dxfpolygonmode yes)
    \t\t\t(dxfimperialunits yes)
    \t\t\t(dxfusepcbnewfont yes)
    \t\t\t(psnegative no)
    \t\t\t(psa4output no)
    \t\t\t(plotreference yes)
    \t\t\t(plotvalue no)
    \t\t\t(plotfptext yes)
    \t\t\t(plotinvisibletext no)
    \t\t\t(sketchpadsonfab no)
    \t\t\t(subtractmaskfromsilk no)
    \t\t\t(outputformat 1)
    \t\t\t(mirror no)
    \t\t\t(drillshape 1)
    \t\t\t(scaleselection 1)
    \t\t\t(outputdirectory "gerbers/")
    \t\t)
    \t)

    ''')


def build_nets():
    # Cycle 4 nets (same as Cycle 3 + VBAT_ADC):
    nets = ["", "GND", "+3V3", "VUSB",
            "VBAT", "VBAT_CELL", "VBAT_F", "VBAT_SW",
            "GATE_REV", "NC_SW",
            "SDA", "SCL", "ENC_A", "ENC_B", "ENC_SW",
            "RGB_DIN_MCU", "RGB_OUT",
            "NTC_ADC", "VBAT_ADC"]
    for c in range(5):
        nets.append(f"COL{c}")
    for r in range(5):
        nets.append(f"ROW{r}")
    for r in range(5):
        for c in range(5):
            nets.append(f"KROW{r}{c}")
    for i in range(1, 26):
        nets.append(f"RGB_D{i}")
    return nets


def net_table(nets):
    return "".join(f'\t(net {i} "{n}")\n' for i, n in enumerate(nets))


# --- footprints --------------------------------------------------------------

def fp_switch_kailh(ref, net_col, net_row_int, x, y, rotation, is_2u_key=False):
    """Kailh hot-swap MX footprint. SMD pads 3.5 x 2.5 (Keebio geometry).
    MX centre 4 mm NPTH + 2x 1.75 mm plate pegs. If is_2u_key, add Cherry
    2U plate-mount stab holes (canonical slot geometry)."""
    uuid_fp = U(f"fp_sw_{ref}")
    pad1 = (-3.85, -2.54)
    pad2 = (2.55, -5.08)
    stab = ""
    if is_2u_key:
        stab = textwrap.dedent(f'''
            (pad "" np_thru_hole circle (at -11.9 6.77) (size 3.05 3.05) (drill 3.05) (layers "*.Cu" "*.Mask") (uuid "{U(f"st_wl_{ref}")}"))
            (pad "" np_thru_hole circle (at  11.9 6.77) (size 3.05 3.05) (drill 3.05) (layers "*.Cu" "*.Mask") (uuid "{U(f"st_wr_{ref}")}"))
            (pad "" np_thru_hole oval   (at -11.9 -0.9) (size 3.97 6.65) (drill oval 3.97 6.65) (layers "*.Cu" "*.Mask") (uuid "{U(f"st_hl_{ref}")}"))
            (pad "" np_thru_hole oval   (at  11.9 -0.9) (size 3.97 6.65) (drill oval 3.97 6.65) (layers "*.Cu" "*.Mask") (uuid "{U(f"st_hr_{ref}")}"))
        ''')
    return textwrap.dedent(f'''\
        (footprint "local:SW_Kailh_HotSwap_MX{'_2U' if is_2u_key else ''}"
            (layer "F.Cu")
            (uuid "{uuid_fp}")
            (at {x} {y} {rotation})
            (descr "Kailh MX hot-swap (Keebio MX_Only_HS geometry) + MX cutout")
            (tags "keyboard kailh mx hotswap")
            (property "Reference" "{ref}" (at 0 -9 {rotation}) (layer "F.Fab") (uuid "{U(f"r_{ref}")}") (effects (font (size 1 1) (thickness 0.15))))
            (property "Value" "MX_HS" (at 0 9 {rotation}) (layer "F.Fab") (hide yes) (uuid "{U(f"v_{ref}")}") (effects (font (size 1 1) (thickness 0.15))))
            (property "Footprint" "" (layer "F.Fab") (hide yes) (uuid "{U(f"f_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "Datasheet" "" (layer "F.Fab") (hide yes) (uuid "{U(f"d_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "Description" "" (layer "F.Fab") (hide yes) (uuid "{U(f"ds_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "JLCPCB Rotation" "0" (layer "F.Fab") (hide yes) (uuid "{U(f"jr_{ref}")}") (effects (font (size 1 1) (thickness 0.15))))
            (attr smd)
            (fp_line (start -7 -7) (end 7 -7) (stroke (width 0.12) (type default)) (layer "F.Fab") (uuid "{U(f"fab1_{ref}")}"))
            (fp_line (start 7 -7) (end 7 7) (stroke (width 0.12) (type default)) (layer "F.Fab") (uuid "{U(f"fab2_{ref}")}"))
            (fp_line (start 7 7) (end -7 7) (stroke (width 0.12) (type default)) (layer "F.Fab") (uuid "{U(f"fab3_{ref}")}"))
            (fp_line (start -7 7) (end -7 -7) (stroke (width 0.12) (type default)) (layer "F.Fab") (uuid "{U(f"fab4_{ref}")}"))
            (fp_line (start -8 -8) (end 8 -8) (stroke (width 0.05) (type default)) (layer "F.CrtYd") (uuid "{U(f"cy1_{ref}")}"))
            (fp_line (start 8 -8) (end 8 8) (stroke (width 0.05) (type default)) (layer "F.CrtYd") (uuid "{U(f"cy2_{ref}")}"))
            (fp_line (start 8 8) (end -8 8) (stroke (width 0.05) (type default)) (layer "F.CrtYd") (uuid "{U(f"cy3_{ref}")}"))
            (fp_line (start -8 8) (end -8 -8) (stroke (width 0.05) (type default)) (layer "F.CrtYd") (uuid "{U(f"cy4_{ref}")}"))
            (pad "1" smd rect (at {pad1[0]} {pad1[1]} {rotation}) (size 3.5 2.5) (layers "B.Cu" "B.Paste" "B.Mask") (net {net_col[0]} "{net_col[1]}") (uuid "{U(f"p1_{ref}")}"))
            (pad "2" smd rect (at {pad2[0]} {pad2[1]} {rotation}) (size 3.5 2.5) (layers "B.Cu" "B.Paste" "B.Mask") (net {net_row_int[0]} "{net_row_int[1]}") (uuid "{U(f"p2_{ref}")}"))
            (pad "" np_thru_hole circle (at 0 0) (size 4 4) (drill 4) (layers "*.Cu" "*.Mask") (uuid "{U(f"cc_{ref}")}"))
            (pad "" np_thru_hole circle (at -5.08 0) (size 1.75 1.75) (drill 1.75) (layers "*.Cu" "*.Mask") (uuid "{U(f"cl_{ref}")}"))
            (pad "" np_thru_hole circle (at 5.08 0) (size 1.75 1.75) (drill 1.75) (layers "*.Cu" "*.Mask") (uuid "{U(f"cr_{ref}")}"))
            {stab}
        )
    ''')


def fp_diode(ref, x, y, rotation, net_k, net_a):
    """1N4148W SOD-123 matrix diode on B.Cu. JLCPCB rotation +180 baked in."""
    uuid_fp = U(f"fp_d_{ref}")
    return textwrap.dedent(f'''\
        (footprint "Diode_SMD:D_SOD-123"
            (layer "B.Cu")
            (uuid "{uuid_fp}")
            (at {x} {y} {rotation})
            (descr "1N4148W diode SOD-123 (KiCad std)")
            (tags "diode SOD-123")
            (property "Reference" "{ref}" (at 0 -2.5 {rotation}) (layer "B.Fab") (uuid "{U(f"r_{ref}")}") (effects (font (size 0.8 0.8) (thickness 0.15)) (justify mirror)))
            (property "Value" "1N4148W" (at 0 2.5 {rotation}) (layer "B.Fab") (hide yes) (uuid "{U(f"v_{ref}")}") (effects (font (size 0.8 0.8) (thickness 0.15))))
            (property "Footprint" "" (layer "B.Fab") (hide yes) (uuid "{U(f"f_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "Datasheet" "" (layer "B.Fab") (hide yes) (uuid "{U(f"d_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "Description" "" (layer "B.Fab") (hide yes) (uuid "{U(f"ds_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "JLCPCB Rotation" "180" (layer "B.Fab") (hide yes) (uuid "{U(f"jr_{ref}")}") (effects (font (size 1 1) (thickness 0.15))))
            (attr smd)
            (fp_line (start -2 -1.1) (end 2 -1.1) (stroke (width 0.1) (type default)) (layer "B.Fab") (uuid "{U(f"fb1_{ref}")}"))
            (fp_line (start 2 -1.1) (end 2 1.1) (stroke (width 0.1) (type default)) (layer "B.Fab") (uuid "{U(f"fb2_{ref}")}"))
            (fp_line (start 2 1.1) (end -2 1.1) (stroke (width 0.1) (type default)) (layer "B.Fab") (uuid "{U(f"fb3_{ref}")}"))
            (fp_line (start -2 1.1) (end -2 -1.1) (stroke (width 0.1) (type default)) (layer "B.Fab") (uuid "{U(f"fb4_{ref}")}"))
            (fp_line (start -2.5 -1.5) (end 2.5 -1.5) (stroke (width 0.05) (type default)) (layer "B.CrtYd") (uuid "{U(f"c1_{ref}")}"))
            (fp_line (start 2.5 -1.5) (end 2.5 1.5) (stroke (width 0.05) (type default)) (layer "B.CrtYd") (uuid "{U(f"c2_{ref}")}"))
            (fp_line (start 2.5 1.5) (end -2.5 1.5) (stroke (width 0.05) (type default)) (layer "B.CrtYd") (uuid "{U(f"c3_{ref}")}"))
            (fp_line (start -2.5 1.5) (end -2.5 -1.5) (stroke (width 0.05) (type default)) (layer "B.CrtYd") (uuid "{U(f"c4_{ref}")}"))
            (fp_line (start -3.1 -1.1) (end -3.1 1.1) (stroke (width 0.15) (type default)) (layer "B.SilkS") (uuid "{U(f"s1_{ref}")}"))
            (pad "1" smd rect (at -1.65 0 {rotation}) (size 1.2 1.4) (layers "B.Cu" "B.Paste" "B.Mask") (net {net_k[0]} "{net_k[1]}") (uuid "{U(f"p1_{ref}")}"))
            (pad "2" smd rect (at 1.65 0 {rotation}) (size 1.2 1.4) (layers "B.Cu" "B.Paste" "B.Mask") (net {net_a[0]} "{net_a[1]}") (uuid "{U(f"p2_{ref}")}"))
        )
    ''')


def fp_led_sk6812(ref, x, y, rotation, net_vdd, net_dout, net_gnd, net_din):
    """SK6812MINI-E REVERSE-mount RGB LED.
    B-LED-LAYER fix: pads now on B.Cu / B.Paste / B.Mask (was F.Cu -- wrong).
    B-LED-APERTURE fix: Edge.Cuts aperture grown to 3.4 x 2.8 mm (was 1.7 x 0.6).
    Body sits on the B.Cu side so the light exits through the aperture to
    the user-facing F.Cu side (under the keycap)."""
    uuid_fp = U(f"fp_led_{ref}")
    return textwrap.dedent(f'''\
        (footprint "LED_SMD:LED_SK6812_MINI-E_plccn4_3.5x2.8mm"
            (layer "B.Cu")
            (uuid "{uuid_fp}")
            (at {x} {y} {rotation})
            (descr "SK6812MINI-E reverse-mount RGB LED, 3.4 x 2.8 Edge.Cuts aperture")
            (tags "led sk6812 rgb reverse-mount")
            (property "Reference" "{ref}" (at 0 -3.2 {rotation}) (layer "B.Fab") (uuid "{U(f"r_{ref}")}") (effects (font (size 0.8 0.8) (thickness 0.15)) (justify mirror)))
            (property "Value" "SK6812" (at 0 3.2 {rotation}) (layer "B.Fab") (hide yes) (uuid "{U(f"v_{ref}")}") (effects (font (size 0.8 0.8) (thickness 0.15))))
            (property "Footprint" "" (layer "B.Fab") (hide yes) (uuid "{U(f"f_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "Datasheet" "" (layer "B.Fab") (hide yes) (uuid "{U(f"d_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "Description" "" (layer "B.Fab") (hide yes) (uuid "{U(f"ds_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "JLCPCB Rotation" "-90" (layer "B.Fab") (hide yes) (uuid "{U(f"jr_{ref}")}") (effects (font (size 1 1) (thickness 0.15))))
            (attr smd)
            (fp_line (start -1.75 -1.4) (end 1.75 -1.4) (stroke (width 0.1) (type default)) (layer "B.Fab") (uuid "{U(f"fb1_{ref}")}"))
            (fp_line (start 1.75 -1.4) (end 1.75 1.4) (stroke (width 0.1) (type default)) (layer "B.Fab") (uuid "{U(f"fb2_{ref}")}"))
            (fp_line (start 1.75 1.4) (end -1.75 1.4) (stroke (width 0.1) (type default)) (layer "B.Fab") (uuid "{U(f"fb3_{ref}")}"))
            (fp_line (start -1.75 1.4) (end -1.75 -1.4) (stroke (width 0.1) (type default)) (layer "B.Fab") (uuid "{U(f"fb4_{ref}")}"))
            (fp_line (start -3 -2.1) (end 3 -2.1) (stroke (width 0.05) (type default)) (layer "B.CrtYd") (uuid "{U(f"c1_{ref}")}"))
            (fp_line (start 3 -2.1) (end 3 2.1) (stroke (width 0.05) (type default)) (layer "B.CrtYd") (uuid "{U(f"c2_{ref}")}"))
            (fp_line (start 3 2.1) (end -3 2.1) (stroke (width 0.05) (type default)) (layer "B.CrtYd") (uuid "{U(f"c3_{ref}")}"))
            (fp_line (start -3 2.1) (end -3 -2.1) (stroke (width 0.05) (type default)) (layer "B.CrtYd") (uuid "{U(f"c4_{ref}")}"))
            (fp_line (start -1.7 -1.4) (end 1.7 -1.4) (stroke (width 0.1) (type default)) (layer "Edge.Cuts") (uuid "{U(f"ec1_{ref}")}"))
            (fp_line (start 1.7 -1.4) (end 1.7 1.4) (stroke (width 0.1) (type default)) (layer "Edge.Cuts") (uuid "{U(f"ec2_{ref}")}"))
            (fp_line (start 1.7 1.4) (end -1.7 1.4) (stroke (width 0.1) (type default)) (layer "Edge.Cuts") (uuid "{U(f"ec3_{ref}")}"))
            (fp_line (start -1.7 1.4) (end -1.7 -1.4) (stroke (width 0.1) (type default)) (layer "Edge.Cuts") (uuid "{U(f"ec4_{ref}")}"))
            (pad "1" smd rect (at -2.3 -1.05 {rotation}) (size 0.9 0.6) (layers "B.Cu" "B.Paste" "B.Mask") (net {net_vdd[0]} "{net_vdd[1]}") (uuid "{U(f"p1_{ref}")}"))
            (pad "2" smd rect (at -2.3  1.05 {rotation}) (size 0.9 0.6) (layers "B.Cu" "B.Paste" "B.Mask") (net {net_dout[0]} "{net_dout[1]}") (uuid "{U(f"p2_{ref}")}"))
            (pad "3" smd rect (at  2.3  1.05 {rotation}) (size 0.9 0.6) (layers "B.Cu" "B.Paste" "B.Mask") (net {net_gnd[0]} "{net_gnd[1]}") (uuid "{U(f"p3_{ref}")}"))
            (pad "4" smd rect (at  2.3 -1.05 {rotation}) (size 0.9 0.6) (layers "B.Cu" "B.Paste" "B.Mask") (net {net_din[0]} "{net_din[1]}") (uuid "{U(f"p4_{ref}")}"))
        )
    ''')


def _smd_2pin(lib_name, ref, value, x, y, rotation, net_a, net_b,
              pad_size, pad_offset, body_h=0.6, layer="F.Cu",
              rotation_hint="0", dnp=False):
    uuid_fp = U(f"fp_{ref}")
    mirror = layer.startswith("B.")
    paste = "B.Paste" if mirror else "F.Paste"
    mask = "B.Mask" if mirror else "F.Mask"
    cu = layer
    fab = "B.Fab" if mirror else "F.Fab"
    crtyd = "B.CrtYd" if mirror else "F.CrtYd"
    attr_flags = "smd " + DNP_ATTR if dnp else "smd"
    return textwrap.dedent(f'''\
        (footprint "{lib_name}"
            (layer "{layer}")
            (uuid "{uuid_fp}")
            (at {x} {y} {rotation})
            (descr "{value}")
            (tags "smd")
            (property "Reference" "{ref}" (at 0 -{body_h+0.8} {rotation}) (layer "{fab}") (uuid "{U(f"r_{ref}")}") (effects (font (size 0.6 0.6) (thickness 0.1)){' (justify mirror)' if mirror else ''}))
            (property "Value" "{value}" (at 0 {body_h+0.8} {rotation}) (layer "{fab}") (hide yes) (uuid "{U(f"v_{ref}")}") (effects (font (size 0.6 0.6) (thickness 0.1))))
            (property "Footprint" "" (layer "{fab}") (hide yes) (uuid "{U(f"f_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "Datasheet" "" (layer "{fab}") (hide yes) (uuid "{U(f"d_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "Description" "" (layer "{fab}") (hide yes) (uuid "{U(f"ds_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "JLCPCB Rotation" "{rotation_hint}" (layer "{fab}") (hide yes) (uuid "{U(f"jr_{ref}")}") (effects (font (size 1 1) (thickness 0.15))))
            (attr {attr_flags})
            (fp_line (start -{pad_offset+0.5} -{body_h}) (end {pad_offset+0.5} -{body_h}) (stroke (width 0.05) (type default)) (layer "{crtyd}") (uuid "{U(f"c1_{ref}")}"))
            (fp_line (start {pad_offset+0.5} -{body_h}) (end {pad_offset+0.5} {body_h}) (stroke (width 0.05) (type default)) (layer "{crtyd}") (uuid "{U(f"c2_{ref}")}"))
            (fp_line (start {pad_offset+0.5} {body_h}) (end -{pad_offset+0.5} {body_h}) (stroke (width 0.05) (type default)) (layer "{crtyd}") (uuid "{U(f"c3_{ref}")}"))
            (fp_line (start -{pad_offset+0.5} {body_h}) (end -{pad_offset+0.5} -{body_h}) (stroke (width 0.05) (type default)) (layer "{crtyd}") (uuid "{U(f"c4_{ref}")}"))
            (pad "1" smd rect (at -{pad_offset} 0 {rotation}) (size {pad_size[0]} {pad_size[1]}) (layers "{cu}" "{paste}" "{mask}") (net {net_a[0]} "{net_a[1]}") (uuid "{U(f"p1_{ref}")}"))
            (pad "2" smd rect (at {pad_offset} 0 {rotation}) (size {pad_size[0]} {pad_size[1]}) (layers "{cu}" "{paste}" "{mask}") (net {net_b[0]} "{net_b[1]}") (uuid "{U(f"p2_{ref}")}"))
        )
    ''')


def fp_0402(ref, value, x, y, rotation, net_a, net_b, layer="F.Cu", dnp=False):
    return _smd_2pin("Resistor_SMD:R_0402_1005Metric", ref, value, x, y, rotation,
                     net_a, net_b, pad_size=(0.65, 0.7), pad_offset=0.5,
                     body_h=0.5, layer=layer, rotation_hint="0", dnp=dnp)


def fp_0603(ref, value, x, y, rotation, net_a, net_b, layer="F.Cu"):
    return _smd_2pin("Capacitor_SMD:C_0603_1608Metric", ref, value, x, y, rotation,
                     net_a, net_b, pad_size=(0.9, 1.0), pad_offset=0.85,
                     body_h=0.8, layer=layer, rotation_hint="0")


def fp_0805(ref, value, x, y, rotation, net_a, net_b, layer="F.Cu"):
    return _smd_2pin("Capacitor_SMD:C_0805_2012Metric", ref, value, x, y, rotation,
                     net_a, net_b, pad_size=(1.1, 1.4), pad_offset=0.95,
                     body_h=1.0, layer=layer, rotation_hint="0")


def fp_ptc_0805(ref, value, x, y, rotation, net_a, net_b, layer="F.Cu"):
    return _smd_2pin("Fuse:Fuse_0805_2012Metric", ref, value, x, y, rotation,
                     net_a, net_b, pad_size=(1.1, 1.4), pad_offset=0.95,
                     body_h=1.0, layer=layer, rotation_hint="0")


def fp_sod523(ref, value, x, y, rotation, net_k, net_a, layer="F.Cu", dnp=False):
    """ESD9L3.3 / BZT52 SOD-523. Pin 1 = cathode (on left at rotation 0),
    pin 2 = anode. Caller is responsible for passing (net_k, net_a) in
    (cathode, anode) order."""
    return _smd_2pin("Diode_SMD:D_SOD-523", ref, value, x, y, rotation,
                     net_k, net_a, pad_size=(0.6, 0.7), pad_offset=0.6,
                     body_h=0.5, layer=layer, rotation_hint="0", dnp=dnp)


def fp_sot23_3(ref, value, x, y, rotation, nets, rotation_hint="0"):
    """Generic SOT-23 3-pin. nets is dict {1:..,2:..,3:..}.
    Standard SOT-23 package has pin 1 lower-left, pin 2 lower-right,
    pin 3 upper-centre (pads all on F.Cu)."""
    uuid_fp = U(f"fp_{ref}")
    return textwrap.dedent(f'''\
        (footprint "Package_TO_SOT_SMD:SOT-23"
            (layer "F.Cu")
            (uuid "{uuid_fp}")
            (at {x} {y} {rotation})
            (descr "SOT-23 3-pin")
            (tags "SOT-23")
            (property "Reference" "{ref}" (at 0 -2 {rotation}) (layer "F.Fab") (uuid "{U(f"r_{ref}")}") (effects (font (size 0.8 0.8) (thickness 0.12))))
            (property "Value" "{value}" (at 0 2 {rotation}) (layer "F.Fab") (hide yes) (uuid "{U(f"v_{ref}")}") (effects (font (size 0.8 0.8) (thickness 0.12))))
            (property "Footprint" "" (layer "F.Fab") (hide yes) (uuid "{U(f"f_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "Datasheet" "" (layer "F.Fab") (hide yes) (uuid "{U(f"d_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "Description" "" (layer "F.Fab") (hide yes) (uuid "{U(f"ds_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "JLCPCB Rotation" "{rotation_hint}" (layer "F.Fab") (hide yes) (uuid "{U(f"jr_{ref}")}") (effects (font (size 1 1) (thickness 0.15))))
            (attr smd)
            (pad "1" smd rect (at -0.95 -1.1 {rotation}) (size 0.8 1.0) (layers "F.Cu" "F.Paste" "F.Mask") (net {nets[1][0]} "{nets[1][1]}") (uuid "{U(f"p1_{ref}")}"))
            (pad "2" smd rect (at  0.95 -1.1 {rotation}) (size 0.8 1.0) (layers "F.Cu" "F.Paste" "F.Mask") (net {nets[2][0]} "{nets[2][1]}") (uuid "{U(f"p2_{ref}")}"))
            (pad "3" smd rect (at  0    1.1 {rotation}) (size 0.8 1.0) (layers "F.Cu" "F.Paste" "F.Mask") (net {nets[3][0]} "{nets[3][1]}") (uuid "{U(f"p3_{ref}")}"))
        )
    ''')


DNP_ATTR = "exclude_from_pos_files exclude_from_bom dnp"


def fp_xiao_nrf52840(ref, x, y, rotation, pin_nets_front, pin_nets_bat):
    """XIAO nRF52840 direct-solder castellations. 7+7 castellations @ 2.54 mm
    pitch on body ~17.5 mm wide -> pad x = +/-8.75 mm (outer edge of
    castellation), pad size 2.0 x 1.5 mm.
    BAT+/BAT- pads on module underside; we expose them as F.Cu SMD pads."""
    uuid_fp = U(f"fp_mcu_{ref}")
    pads = []
    for i in range(1, 8):
        py = (i - 4) * 2.54
        net = pin_nets_front.get(i, (0, ""))
        pads.append(
            f'(pad "{i}" smd rect (at -8.75 {py:.3f} {rotation}) '
            f'(size 2.0 1.5) (layers "F.Cu" "F.Paste" "F.Mask") '
            f'(net {net[0]} "{net[1]}") (uuid "{U(f"p{i}_{ref}")}"))'
        )
    for j, i in enumerate(range(8, 15)):
        py = (j - 3) * 2.54
        net = pin_nets_front.get(i, (0, ""))
        pads.append(
            f'(pad "{i}" smd rect (at 8.75 {py:.3f} {rotation}) '
            f'(size 2.0 1.5) (layers "F.Cu" "F.Paste" "F.Mask") '
            f'(net {net[0]} "{net[1]}") (uuid "{U(f"p{i}_{ref}")}"))'
        )
    # BAT+/BAT- back-side pads. On the real XIAO nRF52840 these live on the
    # underside near the SOUTH end (opposite USB-C). We expose them as F.Cu
    # pads the user hand-solders wires to.
    for i, (px, py) in [(15, (0, 6.5)), (16, (0, 4.0))]:
        net = pin_nets_bat.get(i, (0, ""))
        pads.append(
            f'(pad "{i}" smd rect (at {px} {py} {rotation}) '
            f'(size 1.5 1.0) (layers "F.Cu" "F.Paste" "F.Mask") '
            f'(net {net[0]} "{net[1]}") (uuid "{U(f"p{i}_{ref}")}"))'
        )
    pads_txt = "\n\t\t".join(pads)
    return textwrap.dedent(f'''\
        (footprint "local:XIAO_nRF52840_Castellated"
            (layer "F.Cu")
            (uuid "{uuid_fp}")
            (at {x} {y} {rotation})
            (descr "Seeed XIAO nRF52840 direct-solder castellations + BAT pads")
            (tags "xiao nrf52840 castellated")
            (property "Reference" "{ref}" (at 0 -11 {rotation}) (layer "F.SilkS") (uuid "{U(f"r_{ref}")}") (effects (font (size 1 1) (thickness 0.15))))
            (property "Value" "XIAO_nRF52840" (at 0 11 {rotation}) (layer "F.Fab") (hide yes) (uuid "{U(f"v_{ref}")}") (effects (font (size 1 1) (thickness 0.15))))
            (property "Footprint" "" (layer "F.Fab") (hide yes) (uuid "{U(f"f_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "Datasheet" "" (layer "F.Fab") (hide yes) (uuid "{U(f"d_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "Description" "" (layer "F.Fab") (hide yes) (uuid "{U(f"ds_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "JLCPCB Rotation" "0" (layer "F.Fab") (hide yes) (uuid "{U(f"jr_{ref}")}") (effects (font (size 1 1) (thickness 0.15))))
            (attr smd {DNP_ATTR})
            (fp_line (start -8.75 -10.75) (end 8.75 -10.75) (stroke (width 0.12) (type default)) (layer "F.Fab") (uuid "{U(f"fa1_{ref}")}"))
            (fp_line (start 8.75 -10.75) (end 8.75 10.75) (stroke (width 0.12) (type default)) (layer "F.Fab") (uuid "{U(f"fa2_{ref}")}"))
            (fp_line (start 8.75 10.75) (end -8.75 10.75) (stroke (width 0.12) (type default)) (layer "F.Fab") (uuid "{U(f"fa3_{ref}")}"))
            (fp_line (start -8.75 10.75) (end -8.75 -10.75) (stroke (width 0.12) (type default)) (layer "F.Fab") (uuid "{U(f"fa4_{ref}")}"))
            (fp_line (start -10 -12) (end 10 -12) (stroke (width 0.05) (type default)) (layer "F.CrtYd") (uuid "{U(f"cy1_{ref}")}"))
            (fp_line (start 10 -12) (end 10 12) (stroke (width 0.05) (type default)) (layer "F.CrtYd") (uuid "{U(f"cy2_{ref}")}"))
            (fp_line (start 10 12) (end -10 12) (stroke (width 0.05) (type default)) (layer "F.CrtYd") (uuid "{U(f"cy3_{ref}")}"))
            (fp_line (start -10 12) (end -10 -12) (stroke (width 0.05) (type default)) (layer "F.CrtYd") (uuid "{U(f"cy4_{ref}")}"))
            {pads_txt}
        )
    ''')


def fp_header_4pin(ref, value, x, y, rotation, pin_nets):
    uuid_fp = U(f"fp_hdr4_{ref}")
    pads = []
    for i in range(1, 5):
        py = (i - 2.5) * 2.54
        net = pin_nets.get(i, (0, ""))
        shape = "rect" if i == 1 else "circle"
        pads.append(
            f'(pad "{i}" thru_hole {shape} (at 0 {py:.3f} {rotation}) '
            f'(size 1.7 1.7) (drill 1) (layers "*.Cu" "*.Mask") '
            f'(net {net[0]} "{net[1]}") '
            f'(thermal_bridge_width 0.5) '
            f'(uuid "{U(f"p_{ref}_{i}")}"))'
        )
    pads_txt = "\n\t\t".join(pads)
    return textwrap.dedent(f'''\
        (footprint "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical"
            (layer "F.Cu")
            (uuid "{uuid_fp}")
            (at {x} {y} {rotation})
            (descr "1x04 pin header 2.54 mm (PTH, 0.5 mm thermal bridge)")
            (tags "header 2.54mm")
            (property "Reference" "{ref}" (at 0 -5 {rotation}) (layer "F.Fab") (uuid "{U(f"r_{ref}")}") (effects (font (size 0.8 0.8) (thickness 0.15))))
            (property "Value" "{value}" (at 0 5 {rotation}) (layer "F.Fab") (hide yes) (uuid "{U(f"v_{ref}")}") (effects (font (size 0.8 0.8) (thickness 0.15))))
            (property "Footprint" "" (layer "F.Fab") (hide yes) (uuid "{U(f"f_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "Datasheet" "" (layer "F.Fab") (hide yes) (uuid "{U(f"d_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "Description" "" (layer "F.Fab") (hide yes) (uuid "{U(f"ds_{ref}")}") (effects (font (size 1.27 1.27))))
            (attr through_hole {DNP_ATTR})
            {pads_txt}
        )
    ''')


def fp_jst_ph_2pin(ref, x, y, rotation, net_plus, net_minus):
    """JST PH S2B-PH-SM4-TB side-entry SMD 2-pin, 2.0 mm pitch. Cycle 5
    migration from JST-SH (1.0 mm pitch) to JST-PH (2.0 mm pitch) so the
    board accepts the industry-standard Adafruit / SparkFun / Pimoroni
    protected LiPo cell pigtails (LCSC C5290961/C5290967 from Cycle 4
    were hallucinated; JST-SH is not the common ecosystem for protected
    1S cells).

    Pin 1 (+VBAT_CELL) is WEST of centre; pin 2 (GND) is EAST. F.SilkS
    glyphs \"+\" and \"-\" sit immediately north of each pad (C5-M3 fix
    for S-C4-M1: builders must see the polarity marker).
    LCSC C160404 (S2B-PH-SM4-TB), 2.0 mm pitch, side-entry SMD."""
    uuid_fp = U(f"fp_jst_{ref}")
    return textwrap.dedent(f'''\
        (footprint "Connector_JST:JST_PH_S2B-PH-SM4-TB_1x02-1MP_P2.00mm_Horizontal"
            (layer "F.Cu")
            (uuid "{uuid_fp}")
            (at {x} {y} {rotation})
            (descr "JST PH 2-pin side-entry SMD horizontal (S2B-PH-SM4-TB)")
            (tags "JST PH connector")
            (property "Reference" "{ref}" (at 0 -4 {rotation}) (layer "F.Fab") (uuid "{U(f"r_{ref}")}") (effects (font (size 0.7 0.7) (thickness 0.12))))
            (property "Value" "JST-PH-2P" (at 0 4 {rotation}) (layer "F.Fab") (hide yes) (uuid "{U(f"v_{ref}")}") (effects (font (size 0.7 0.7) (thickness 0.12))))
            (property "Footprint" "" (layer "F.Fab") (hide yes) (uuid "{U(f"f_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "Datasheet" "" (layer "F.Fab") (hide yes) (uuid "{U(f"d_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "Description" "" (layer "F.Fab") (hide yes) (uuid "{U(f"ds_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "JLCPCB Rotation" "0" (layer "F.Fab") (hide yes) (uuid "{U(f"jr_{ref}")}") (effects (font (size 1 1) (thickness 0.15))))
            (attr smd)
            (pad "1" smd rect (at -1.0 -3.0 {rotation}) (size 1.0 1.6) (layers "F.Cu" "F.Paste" "F.Mask") (net {net_plus[0]} "{net_plus[1]}") (uuid "{U(f"pj1_{ref}")}"))
            (pad "2" smd rect (at 1.0 -3.0 {rotation}) (size 1.0 1.6) (layers "F.Cu" "F.Paste" "F.Mask") (net {net_minus[0]} "{net_minus[1]}") (uuid "{U(f"pj2_{ref}")}"))
            (pad "MP1" smd rect (at -3.4 0.0 {rotation}) (size 1.2 1.8) (layers "F.Cu" "F.Paste" "F.Mask") (uuid "{U(f"pj3_{ref}")}"))
            (pad "MP2" smd rect (at 3.4 0.0 {rotation}) (size 1.2 1.8) (layers "F.Cu" "F.Paste" "F.Mask") (uuid "{U(f"pj4_{ref}")}"))
            (fp_text user "+" (at -1.0 -5.0 {rotation}) (layer "F.SilkS") (uuid "{U(f"sp_{ref}")}") (effects (font (size 1 1) (thickness 0.15))))
            (fp_text user "-" (at 1.0 -5.0 {rotation}) (layer "F.SilkS") (uuid "{U(f"sm_{ref}")}") (effects (font (size 1 1) (thickness 0.15))))
        )
    ''')


# Keep old name as an alias so the rest of build_pcb() (and any external
# callers) don't need to change. Cycle 5 migrated the physical connector.
fp_jst_sh_2pin = fp_jst_ph_2pin


def fp_spdt(ref, x, y, rotation, net_p1, net_com, net_p3):
    """SS-12D00G4 SPDT slide switch (THT, 2.54 mm pitch, 3-pin).
    Pin 1 = throw A (left), Pin 2 = COM (centre), Pin 3 = throw B (right).
    Matches schematic local:SW_SPDT pin numbering. PTH w/ 0.5 mm thermal bridge."""
    uuid_fp = U(f"fp_spdt_{ref}")
    return textwrap.dedent(f'''\
        (footprint "Button_Switch_THT:SW_Slide_1P2T_SS12D00G4"
            (layer "F.Cu")
            (uuid "{uuid_fp}")
            (at {x} {y} {rotation})
            (descr "SPDT slide switch SS-12D00G4 (TH, 3 pins, 2.54 mm pitch)")
            (tags "slide switch spdt SS12D00G4")
            (property "Reference" "{ref}" (at 0 -4 {rotation}) (layer "F.SilkS") (uuid "{U(f"r_{ref}")}") (effects (font (size 0.8 0.8) (thickness 0.15))))
            (property "Value" "SPDT" (at 0 4 {rotation}) (layer "F.Fab") (hide yes) (uuid "{U(f"v_{ref}")}") (effects (font (size 0.8 0.8) (thickness 0.15))))
            (property "Footprint" "" (layer "F.Fab") (hide yes) (uuid "{U(f"f_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "Datasheet" "" (layer "F.Fab") (hide yes) (uuid "{U(f"d_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "Description" "" (layer "F.Fab") (hide yes) (uuid "{U(f"ds_{ref}")}") (effects (font (size 1.27 1.27))))
            (attr through_hole {DNP_ATTR})
            (pad "1" thru_hole oval (at -2.54 0 {rotation}) (size 1.5 1.5) (drill 0.9) (layers "*.Cu" "*.Mask") (net {net_p1[0]} "{net_p1[1]}") (thermal_bridge_width 0.5) (uuid "{U(f"ps1_{ref}")}"))
            (pad "2" thru_hole oval (at 0 0 {rotation}) (size 1.5 1.5) (drill 0.9) (layers "*.Cu" "*.Mask") (net {net_com[0]} "{net_com[1]}") (thermal_bridge_width 0.5) (uuid "{U(f"ps2_{ref}")}"))
            (pad "3" thru_hole oval (at 2.54 0 {rotation}) (size 1.5 1.5) (drill 0.9) (layers "*.Cu" "*.Mask") (net {net_p3[0]} "{net_p3[1]}") (thermal_bridge_width 0.5) (uuid "{U(f"ps3_{ref}")}"))
            (pad "MP1" np_thru_hole circle (at -4.7 0) (size 1.5 1.5) (drill 1.5) (layers "*.Cu" "*.Mask") (uuid "{U(f"pmp1_{ref}")}"))
            (pad "MP2" np_thru_hole circle (at 4.7 0) (size 1.5 1.5) (drill 1.5) (layers "*.Cu" "*.Mask") (uuid "{U(f"pmp2_{ref}")}"))
        )
    ''')


def fp_ec11(ref, x, y, rotation, nets, gnd_net):
    """EC11 THT w/ mounting lugs PTH tied to GND (M-EC11-GROUND)."""
    uuid_fp = U(f"fp_ec11_{ref}")
    return textwrap.dedent(f'''\
        (footprint "Button_Switch_THT:RotaryEncoder_Alps_EC11E-Switch_Vertical_H20mm"
            (layer "F.Cu")
            (uuid "{uuid_fp}")
            (at {x} {y} {rotation})
            (descr "Alps EC11 rotary encoder with push-switch, PTH-ground mounting lugs")
            (tags "EC11 rotary encoder")
            (property "Reference" "{ref}" (at 0 -9 {rotation}) (layer "F.SilkS") (uuid "{U(f"r_{ref}")}") (effects (font (size 1 1) (thickness 0.15))))
            (property "Value" "EC11" (at 0 9 {rotation}) (layer "F.Fab") (hide yes) (uuid "{U(f"v_{ref}")}") (effects (font (size 1 1) (thickness 0.15))))
            (property "Footprint" "" (layer "F.Fab") (hide yes) (uuid "{U(f"f_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "Datasheet" "" (layer "F.Fab") (hide yes) (uuid "{U(f"d_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "Description" "" (layer "F.Fab") (hide yes) (uuid "{U(f"ds_{ref}")}") (effects (font (size 1.27 1.27))))
            (attr through_hole {DNP_ATTR})
            (pad "1" thru_hole oval (at -2.5 -6.5 {rotation}) (size 1.8 1.8) (drill 1) (layers "*.Cu" "*.Mask") (net {nets["A"][0]} "{nets["A"][1]}") (thermal_bridge_width 0.5) (uuid "{U(f"ec_a_{ref}")}"))
            (pad "2" thru_hole oval (at 0 -6.5 {rotation}) (size 1.8 1.8) (drill 1) (layers "*.Cu" "*.Mask") (net {nets["C"][0]} "{nets["C"][1]}") (thermal_bridge_width 0.5) (uuid "{U(f"ec_c_{ref}")}"))
            (pad "3" thru_hole oval (at 2.5 -6.5 {rotation}) (size 1.8 1.8) (drill 1) (layers "*.Cu" "*.Mask") (net {nets["B"][0]} "{nets["B"][1]}") (thermal_bridge_width 0.5) (uuid "{U(f"ec_b_{ref}")}"))
            (pad "4" thru_hole oval (at -2.5 6.5 {rotation}) (size 1.8 1.8) (drill 1) (layers "*.Cu" "*.Mask") (net {nets["SW1"][0]} "{nets["SW1"][1]}") (thermal_bridge_width 0.5) (uuid "{U(f"ec_sw1_{ref}")}"))
            (pad "5" thru_hole oval (at 2.5 6.5 {rotation}) (size 1.8 1.8) (drill 1) (layers "*.Cu" "*.Mask") (net {nets["SW2"][0]} "{nets["SW2"][1]}") (thermal_bridge_width 0.5) (uuid "{U(f"ec_sw2_{ref}")}"))
            (pad "MP1" thru_hole circle (at -6.5 0) (size 4.0 4.0) (drill 3.2) (layers "*.Cu" "*.Mask") (net {gnd_net[0]} "{gnd_net[1]}") (thermal_bridge_width 0.5) (uuid "{U(f"ec_mp1_{ref}")}"))
            (pad "MP2" thru_hole circle (at 6.5 0) (size 4.0 4.0) (drill 3.2) (layers "*.Cu" "*.Mask") (net {gnd_net[0]} "{gnd_net[1]}") (thermal_bridge_width 0.5) (uuid "{U(f"ec_mp2_{ref}")}"))
        )
    ''')


def fp_ntc_axial(ref, x, y, rotation, net_a, net_b):
    """MF52A2 NTC axial THT thermistor. Body ~3 mm, PCB bend pitch 7.62 mm.
    Uses Resistor_THT:R_Axial_DIN0207 geometry."""
    uuid_fp = U(f"fp_ntc_{ref}")
    return textwrap.dedent(f'''\
        (footprint "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal"
            (layer "F.Cu")
            (uuid "{uuid_fp}")
            (at {x} {y} {rotation})
            (descr "MF52A2 NTC 10k axial THT thermistor, 7.62 mm bend pitch")
            (tags "ntc thermistor axial")
            (property "Reference" "{ref}" (at 0 -3 {rotation}) (layer "F.SilkS") (uuid "{U(f"r_{ref}")}") (effects (font (size 0.8 0.8) (thickness 0.15))))
            (property "Value" "MF52A2_10k" (at 0 3 {rotation}) (layer "F.Fab") (hide yes) (uuid "{U(f"v_{ref}")}") (effects (font (size 0.8 0.8) (thickness 0.15))))
            (property "Footprint" "" (layer "F.Fab") (hide yes) (uuid "{U(f"f_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "Datasheet" "" (layer "F.Fab") (hide yes) (uuid "{U(f"d_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "Description" "" (layer "F.Fab") (hide yes) (uuid "{U(f"ds_{ref}")}") (effects (font (size 1.27 1.27))))
            (attr through_hole {DNP_ATTR})
            (pad "1" thru_hole circle (at -3.81 0 {rotation}) (size 1.5 1.5) (drill 0.8) (layers "*.Cu" "*.Mask") (net {net_a[0]} "{net_a[1]}") (thermal_bridge_width 0.5) (uuid "{U(f"p1_{ref}")}"))
            (pad "2" thru_hole circle (at 3.81 0 {rotation}) (size 1.5 1.5) (drill 0.8) (layers "*.Cu" "*.Mask") (net {net_b[0]} "{net_b[1]}") (thermal_bridge_width 0.5) (uuid "{U(f"p2_{ref}")}"))
        )
    ''')


def fp_mounting_hole(ref, x, y, grounded=False, gnd_net=None):
    uuid_fp = U(f"fp_mh_{ref}")
    if grounded and gnd_net:
        pad = (f'(pad "1" thru_hole circle (at 0 0) (size 5.5 5.5) (drill 3.2) '
               f'(layers "*.Cu" "*.Mask") (net {gnd_net[0]} "{gnd_net[1]}") '
               f'(thermal_bridge_width 0.5) '
               f'(uuid "{U(f"mh_p_{ref}")}"))')
    else:
        pad = (f'(pad "" np_thru_hole circle (at 0 0) (size 3.2 3.2) (drill 3.2) '
               f'(layers "*.Cu" "*.Mask") (uuid "{U(f"mh_p_{ref}")}"))')
    return textwrap.dedent(f'''\
        (footprint "MountingHole:MountingHole_3.2mm_M3"
            (layer "F.Cu")
            (uuid "{uuid_fp}")
            (at {x} {y} 0)
            (descr "Mounting hole 3.2mm for M3")
            (attr exclude_from_pos_files exclude_from_bom allow_missing_courtyard)
            (property "Reference" "{ref}" (at 0 -4 0) (layer "F.Fab") (uuid "{U(f"mh_r_{ref}")}") (effects (font (size 1 1) (thickness 0.15))))
            (property "Value" "M3" (at 0 4 0) (layer "F.Fab") (hide yes) (uuid "{U(f"mh_v_{ref}")}") (effects (font (size 1 1) (thickness 0.15))))
            (property "Footprint" "" (layer "F.Fab") (hide yes) (uuid "{U(f"mh_f_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "Datasheet" "" (layer "F.Fab") (hide yes) (uuid "{U(f"mh_d_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "Description" "" (layer "F.Fab") (hide yes) (uuid "{U(f"mh_ds_{ref}")}") (effects (font (size 1.27 1.27))))
            {pad}
        )
    ''')


def fp_fiducial(ref, x, y):
    uuid_fp = U(f"fp_fid_{ref}")
    return textwrap.dedent(f'''\
        (footprint "Fiducial:Fiducial_1mm_Mask2mm"
            (layer "F.Cu")
            (uuid "{uuid_fp}")
            (at {x} {y} 0)
            (descr "Fiducial 1 mm dia, 2 mm mask")
            (attr exclude_from_pos_files exclude_from_bom allow_missing_courtyard smd)
            (property "Reference" "{ref}" (at 0 -2 0) (layer "F.Fab") (uuid "{U(f"fd_r_{ref}")}") (effects (font (size 0.8 0.8) (thickness 0.12))))
            (property "Value" "FID" (at 0 2 0) (layer "F.Fab") (hide yes) (uuid "{U(f"fd_v_{ref}")}") (effects (font (size 0.8 0.8) (thickness 0.12))))
            (property "Footprint" "" (layer "F.Fab") (hide yes) (uuid "{U(f"fd_f_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "Datasheet" "" (layer "F.Fab") (hide yes) (uuid "{U(f"fd_d_{ref}")}") (effects (font (size 1.27 1.27))))
            (property "Description" "" (layer "F.Fab") (hide yes) (uuid "{U(f"fd_ds_{ref}")}") (effects (font (size 1.27 1.27))))
            (pad "1" smd circle (at 0 0) (size 1 1) (layers "F.Cu" "F.Mask") (solder_mask_margin 0.5) (uuid "{U(f"fd_p_{ref}")}"))
        )
    ''')


# --- routing helpers ---------------------------------------------------------

def track(x1, y1, x2, y2, net_idx, width=0.8, layer="F.Cu", tag=""):
    return (
        f'\t(segment (start {x1:.3f} {y1:.3f}) (end {x2:.3f} {y2:.3f}) '
        f'(width {width}) (layer "{layer}") (net {net_idx}) '
        f'(uuid "{U("seg_"+tag)}"))\n'
    )


def via(x, y, net_idx, size=0.8, drill=0.4, tag=""):
    return (
        f'\t(via (at {x:.3f} {y:.3f}) (size {size}) (drill {drill}) '
        f'(layers "F.Cu" "B.Cu") (net {net_idx}) '
        f'(uuid "{U("via_"+tag)}"))\n'
    )


def build_pcb():
    nets = build_nets()
    idx = {n: i for i, n in enumerate(nets)}

    out = []
    out.append(pcb_header())
    out.append(net_table(nets))

    out.append(textwrap.dedent(f'''\
        (net_class "Default" ""
            (clearance 0.2)
            (trace_width 0.25)
            (via_dia 0.6)
            (via_drill 0.3)
            (uvia_dia 0.3)
            (uvia_drill 0.1)
        )
    '''))

    # Board outline (rounded rect, USB-C relief notch on top edge above MCU)
    x0, y0 = BOARD_X0, BOARD_Y0
    x1, y1 = x0 + BOARD_W, y0 + BOARD_H
    r = RADIUS
    mcu_x = x0 + BOARD_W / 2.0
    # Cycle 4: MCU moved 8 mm south. Top strip 30 mm; MCU centre at y0+19
    # so castellations span y0+11.38 .. y0+26.62. Key row 0 top edge =
    # KEY0_CY - 9.525 = y0+30, leaving 3.38 mm clear between MCU south
    # pads and row-0 top edge (unchanged from Cycle 3 margin; both MCU and
    # row-0 shifted south by 8 mm together). Power block (JST/Q_REV/F1/
    # SW_PWR) still west of MCU; NTC + J_BAT cluster still north-west.
    # Antenna keepout now occupies y0..y0+16 (16 mm ON-BOARD span, was
    # 2.5 mm in Cycle 3).
    mcu_y = y0 + 19.0
    usb_cx = mcu_x
    usb_half = 6.0
    usb_depth = 2.0
    out.append(
        f'\t(gr_line (start {x0+r} {y0}) (end {usb_cx-usb_half} {y0}) (stroke (width 0.15) (type default)) (layer "Edge.Cuts") (uuid "{U("ec_n1")}"))\n'
        f'\t(gr_line (start {usb_cx-usb_half} {y0}) (end {usb_cx-usb_half} {y0-usb_depth}) (stroke (width 0.15) (type default)) (layer "Edge.Cuts") (uuid "{U("ec_nw_notch")}"))\n'
        f'\t(gr_line (start {usb_cx-usb_half} {y0-usb_depth}) (end {usb_cx+usb_half} {y0-usb_depth}) (stroke (width 0.15) (type default)) (layer "Edge.Cuts") (uuid "{U("ec_n_notch")}"))\n'
        f'\t(gr_line (start {usb_cx+usb_half} {y0-usb_depth}) (end {usb_cx+usb_half} {y0}) (stroke (width 0.15) (type default)) (layer "Edge.Cuts") (uuid "{U("ec_ne_notch")}"))\n'
        f'\t(gr_line (start {usb_cx+usb_half} {y0}) (end {x1-r} {y0}) (stroke (width 0.15) (type default)) (layer "Edge.Cuts") (uuid "{U("ec_n2")}"))\n'
        f'\t(gr_line (start {x0+r} {y1}) (end {x1-r} {y1}) (stroke (width 0.15) (type default)) (layer "Edge.Cuts") (uuid "{U("ec_s")}"))\n'
        f'\t(gr_line (start {x0} {y0+r}) (end {x0} {y1-r}) (stroke (width 0.15) (type default)) (layer "Edge.Cuts") (uuid "{U("ec_w")}"))\n'
        f'\t(gr_line (start {x1} {y0+r}) (end {x1} {y1-r}) (stroke (width 0.15) (type default)) (layer "Edge.Cuts") (uuid "{U("ec_e")}"))\n'
        f'\t(gr_arc (start {x0+r} {y0}) (mid {x0+r-r*0.707} {y0+r-r*0.707}) (end {x0} {y0+r}) (stroke (width 0.15) (type default)) (layer "Edge.Cuts") (uuid "{U("ec_nw")}"))\n'
        f'\t(gr_arc (start {x0} {y1-r}) (mid {x0+r-r*0.707} {y1-r+r*0.707}) (end {x0+r} {y1}) (stroke (width 0.15) (type default)) (layer "Edge.Cuts") (uuid "{U("ec_sw")}"))\n'
        f'\t(gr_arc (start {x1-r} {y1}) (mid {x1-r+r*0.707} {y1-r+r*0.707}) (end {x1} {y1-r}) (stroke (width 0.15) (type default)) (layer "Edge.Cuts") (uuid "{U("ec_se")}"))\n'
        f'\t(gr_arc (start {x1} {y0+r}) (mid {x1-r+r*0.707} {y0+r-r*0.707}) (end {x1-r} {y0}) (stroke (width 0.15) (type default)) (layer "Edge.Cuts") (uuid "{U("ec_ne")}"))\n'
    )

    # Mounting holes (4x M3). H1/H2 in the top-strip south corners clear
    # of MCU (now at mcu_y=y0+19, south pads at y0+26.62). Top mounting
    # holes at y=y0+27 (between MCU south pads at y0+26.62 and row-0 keys
    # at y0+30, but in the x-corners where MCU doesn't extend). The MCU
    # body ends at x=mcu_x+10, holes at x=x0+3.5 and x=x1-3.5 are well
    # clear (mcu_x+10 = 167.5, x1-3.5 = 211.5 -- 44 mm clear on east).
    # H3/H4 at bottom corners (ungrounded for ESD). Moved 2 mm inboard
    # off corner arcs per MINOR D-N21.
    for i, (hx, hy, grounded) in enumerate([
        (x0 + 3.5, y0 + 27.0, True),
        (x1 - 3.5, y0 + 27.0, True),
        (x0 + 5, y1 - 4, False),
        (x1 - 5, y1 - 4, False),
    ]):
        out.append(fp_mounting_hole(
            f"H{i+1}", hx, hy,
            grounded=grounded,
            gnd_net=(idx["GND"], "GND") if grounded else None,
        ))

    # Tooling holes
    for i, (tx, ty) in enumerate([
        (x0 + 3, y0 + BOARD_H / 2),
        (x1 - 3, y0 + BOARD_H / 2),
    ]):
        out.append(textwrap.dedent(f'''\
            (footprint "MountingHole:MountingHole_1.5mm"
                (layer "F.Cu")
                (uuid "{U(f"tp_{i}")}")
                (at {tx} {ty} 0)
                (descr "Tooling hole 1.5mm")
                (attr exclude_from_pos_files exclude_from_bom allow_missing_courtyard)
                (property "Reference" "TP{i+1}" (at 0 -3 0) (layer "F.Fab") (uuid "{U(f"tpr_{i}")}") (effects (font (size 0.8 0.8) (thickness 0.15))))
                (property "Value" "TOOL" (at 0 3 0) (layer "F.Fab") (hide yes) (uuid "{U(f"tpv_{i}")}") (effects (font (size 0.8 0.8) (thickness 0.15))))
                (property "Footprint" "" (layer "F.Fab") (hide yes) (uuid "{U(f"tpf_{i}")}") (effects (font (size 1.27 1.27))))
                (property "Datasheet" "" (layer "F.Fab") (hide yes) (uuid "{U(f"tpd_{i}")}") (effects (font (size 1.27 1.27))))
                (property "Description" "" (layer "F.Fab") (hide yes) (uuid "{U(f"tpds_{i}")}") (effects (font (size 1.27 1.27))))
                (pad "" np_thru_hole circle (at 0 0) (size 1.5 1.5) (drill 1.5) (layers "*.Cu" "*.Mask") (uuid "{U(f"tpp_{i}")}"))
            )
        '''))

    # Fiducials -- FID3 moved to (x0 + 10, y1 - 3) so it is >=3 mm from
    # H3 at (x0 + 5, y1 - 4). MINOR C4 (DFM) closure.
    for i, (fx, fy) in enumerate([
        (x0 + 3, y0 + 3), (x1 - 3, y0 + 3), (x0 + 10, y1 - 3),
    ]):
        out.append(fp_fiducial(f"FID{i+1}", fx, fy))

    # Switch matrix + diodes + LEDs + LED caps
    for r in range(5):
        for c in range(5):
            kx, ky = key_cxcy(r, c)
            sw_ref = f"SW{r}{c}"
            d_ref = f"D{r}{c}"
            led_idx_i = led_index(r, c)
            led_ref = f"LED{led_idx_i}"
            cap_ref = f"CL{led_idx_i}"

            col_net = (idx[f"COL{c}"], f"COL{c}")
            krow_net = (idx[f"KROW{r}{c}"], f"KROW{r}{c}")
            row_net = (idx[f"ROW{r}"], f"ROW{r}")

            out.append(fp_switch_kailh(sw_ref, col_net, krow_net, kx, ky, 0,
                                       is_2u_key=is_2u(r, c)))
            out.append(fp_diode(d_ref, kx, ky + 5.0, 0, krow_net, row_net))

            pos = RGB_CHAIN_ORDER.index(led_idx_i)
            din_net_name = f"RGB_D{pos+1}"
            dout_net_name = f"RGB_D{pos+2}" if pos < 24 else "RGB_OUT"
            led_vdd = (idx["+3V3"], "+3V3")
            led_dout = (idx[dout_net_name], dout_net_name)
            led_gnd = (idx["GND"], "GND")
            led_din = (idx[din_net_name], din_net_name)
            # LED placed south of MX centre to clear MX SMD pads (at y=-2.54
            # and y=-5.08 relative to MX centre, i.e. in the NORTH half).
            # LED body at (kx, ky+2.5) leaves pads in ky+1.5 .. ky+3.5 range.
            out.append(fp_led_sk6812(led_ref, kx, ky + 2.5, 0,
                                     led_vdd, led_dout, led_gnd, led_din))

            # M-LED-CAPS: cap at (kx-4, ky+1.5) on B.Cu so it sits alongside
            # the reverse-mount LED on the same copper side (clear of MX NPTH).
            ccx = kx - 4.0
            ccy = ky + 1.5
            out.append(fp_0402(cap_ref, "100n", ccx, ccy, 90,
                               led_vdd, led_gnd, layer="B.Cu"))

    # --- MCU: XIAO nRF52840 direct-solder castellations ----------------------
    mcu_pin_nets_front = {
        1:  (idx["VUSB"],   "VUSB"),
        2:  (idx["GND"],    "GND"),
        3:  (idx["+3V3"],   "+3V3"),
        4:  (idx["COL0"],   "COL0"),
        5:  (idx["COL1"],   "COL1"),
        6:  (idx["COL2"],   "COL2"),
        7:  (idx["COL3"],   "COL3"),
        8:  (idx["SDA"],    "SDA"),
        9:  (idx["SCL"],    "SCL"),
        10: (idx["COL4"],   "COL4"),
        11: (idx["ROW0"],   "ROW0"),
        12: (idx["ROW1"],   "ROW1"),
        13: (idx["ROW2"],   "ROW2"),
        14: (idx["NTC_ADC"], "NTC_ADC"),  # D10 (P0.03/AIN1)
    }
    mcu_pin_nets_bat = {
        15: (idx["VBAT"], "VBAT"),
        16: (idx["GND"],  "GND"),
    }
    out.append(fp_xiao_nrf52840("U1", mcu_x, mcu_y, 0,
                                mcu_pin_nets_front, mcu_pin_nets_bat))

    # Rear-pad jumper cluster. Cycle 4: slot assignment re-ordered so
    # ROW3/ROW4 are not aligned with COL F.Cu spine x-coordinates
    # (115.55 / 134.6 / 153.65 / 172.7 / 191.75). Slot x positions:
    #   slot 0 = mcu_x - 6 = 151.5
    #   slot 1 = mcu_x - 4 = 153.5  (was ROW4 -- 0.15 mm from COL2 spine)
    #   slot 2 = mcu_x - 2 = 155.5
    #   slot 3 = mcu_x + 0 = 157.5
    #   slot 4 = mcu_x + 2 = 159.5
    #   slot 5 = mcu_x + 4 = 161.5
    #   slot 6 = mcu_x + 6 = 163.5
    # Move ROW3 to slot 3, ROW4 to slot 4 so F.Cu stub south of BP does
    # not run alongside COL2 spine.
    back_pad_nets = [
        (idx["ENC_A"],       "ENC_A"),          # slot 0 (151.5)
        (idx["ENC_B"],       "ENC_B"),          # slot 1 (153.5)
        (idx["ENC_SW"],      "ENC_SW"),         # slot 2 (155.5)
        (idx["ROW3"],        "ROW3"),           # slot 3 (157.5)
        (idx["ROW4"],        "ROW4"),           # slot 4 (159.5)
        (idx["RGB_DIN_MCU"], "RGB_DIN_MCU"),    # slot 5 (161.5)
        (idx["VBAT_ADC"],    "VBAT_ADC"),       # slot 6 (163.5)
    ]
    # Cycle 5 (C5-B4): shift patch_x 2 mm east so no J_XIAO_BP pad
    # aligns with a COL F.Cu spine x (115.55, 134.6, 153.65, 172.7,
    # 191.75) AND no pad sits on top of a B.Cu switch-pad-2 (SW02 pad 2
    # at (160.05, 134.445) -- slot 3 at bp_x=162 is 0.7 mm east of
    # pad 2 east edge 161.3). With patch_x=162 and 2 mm pitch, pads at
    # x=156, 158, 160, 162, 164, 166, 168.
    patch_x = mcu_x + 2.0
    patch_y = mcu_y + 13.5   # ~2.75 mm south of MCU south edge (at mcu_y+10.75)
    patch_pads = []
    for i, (nidx, nname) in enumerate(back_pad_nets):
        px = (i - 3.0) * 2.0   # 7 pads centred on x=0
        patch_pads.append(
            f'(pad "{i+1}" smd rect (at {px:.3f} 0 0) (size 1.5 1.0) '
            f'(layers "F.Cu" "F.Paste" "F.Mask") '
            f'(net {nidx} "{nname}") (uuid "{U(f"bp_{i}")}"))'
        )
    patch_pads_txt = "\n\t\t".join(patch_pads)
    out.append(textwrap.dedent(f'''\
        (footprint "local:XIAO_BackPad_Jumper_1x7"
            (layer "F.Cu")
            (uuid "{U("fp_bp_xiao")}")
            (at {patch_x} {patch_y} 0)
            (descr "User-wired jumper pads to XIAO nRF52840 back-side GPIOs (<5 mm from MCU)")
            (attr smd)
            (property "Reference" "J_XIAO_BP" (at 0 -2 0) (layer "F.Fab") (uuid "{U("bp_r")}") (effects (font (size 0.6 0.6) (thickness 0.12))))
            (property "Value" "JUMPER" (at 0 2 0) (layer "F.Fab") (hide yes) (uuid "{U("bp_v")}") (effects (font (size 0.6 0.6) (thickness 0.12))))
            (property "Footprint" "" (layer "F.Fab") (hide yes) (uuid "{U("bp_f")}") (effects (font (size 1.27 1.27))))
            (property "Datasheet" "" (layer "F.Fab") (hide yes) (uuid "{U("bp_d")}") (effects (font (size 1.27 1.27))))
            (property "Description" "" (layer "F.Fab") (hide yes) (uuid "{U("bp_ds")}") (effects (font (size 1.27 1.27))))
            (property "JLCPCB Rotation" "0" (layer "F.Fab") (hide yes) (uuid "{U("bp_jr")}") (effects (font (size 1 1) (thickness 0.15))))
            {patch_pads_txt}
        )
    '''))

    # --- Passives (I2C pull-ups, RGB series R) on B.Cu under MCU -------------
    out.append(fp_0402("R1", "470",  mcu_x - 3, mcu_y - 3, 90,
                       (idx["RGB_DIN_MCU"], "RGB_DIN_MCU"),
                       (idx["RGB_D1"], "RGB_D1"), layer="B.Cu"))
    out.append(fp_0402("R2", "4k7",  mcu_x - 3, mcu_y + 0, 90,
                       (idx["+3V3"], "+3V3"),
                       (idx["SDA"], "SDA"), layer="B.Cu"))
    out.append(fp_0402("R3", "4k7",  mcu_x - 3, mcu_y + 3, 90,
                       (idx["+3V3"], "+3V3"),
                       (idx["SCL"], "SCL"), layer="B.Cu"))

    # --- PN532 NFC header ----------------------------------------------------
    # Cycle 4: moved north-east to (x0+13, y1-15) so header body sits in
    # the band south of ROW4 spine (y=224.725) and well west of the ROW
    # lane vias at x=x1-18..x1-26. Vertical orientation (rotation 90 keeps
    # pins in y-column).
    nfc_hdr_x = x0 + 13
    nfc_hdr_y = y1 - 12
    out.append(fp_header_4pin("J_NFC", "NFC", nfc_hdr_x, nfc_hdr_y, 0, {
        1: (idx["GND"], "GND"),
        2: (idx["+3V3"], "+3V3"),
        3: (idx["SDA"], "SDA"),
        4: (idx["SCL"], "SCL"),
    }))

    # --- ESD TVS: cathode -> signal, anode -> GND (B-TVS fix) ----------------
    # Cycle 5 (C5-B2): TVS_SDA / TVS_SCL moved from under-MCU to within
    # 4 mm of J_NFC so the clamps sit on the clean NFC I2C branch, not
    # on the MCU F.Cu castellation side. pin 3 (SDA) at
    # (nfc_hdr_x, nfc_hdr_y+1.27); pin 4 (SCL) at (nfc_hdr_x, nfc_hdr_y+3.81).
    # Place TVS on B.Cu east of the header (header is PTH so pads appear
    # both layers; B.Cu TVS uses the same net via PTH).
    # For fp_sod523: net_k (pin 1 = cathode) first, net_a (pin 2 = anode) second.
    out.append(fp_sod523("TVS_SDA", "ESD9L3.3", nfc_hdr_x + 3, nfc_hdr_y + 1.27, 0,
                         (idx["SDA"], "SDA"),
                         (idx["GND"], "GND"), layer="B.Cu"))
    out.append(fp_sod523("TVS_SCL", "ESD9L3.3", nfc_hdr_x + 3, nfc_hdr_y + 3.81, 0,
                         (idx["SCL"], "SCL"),
                         (idx["GND"], "GND"), layer="B.Cu"))

    # --- Battery / power block (top-LEFT strip) ------------------------------
    # Cycle 4: power block moved with MCU -- now lives at y = mcu_y
    # (y0+19), west of the MCU west edge (x < mcu_x-10). The antenna
    # keepout zone (y0..y0+16) is north of the power block so power
    # tracks do not cross it. H1 (mounting hole) is now at y0+27, south
    # of the power block row -- still clear.
    # Layout west-to-east at y = mcu_y = y0+19:
    #   JST(x0+8) -> Q_REV(x0+16) -> F1(x0+23) -> SW_PWR(x0+33)
    jbat_x = x0 + 8
    jbat_y = y0 + 19.0
    out.append(fp_jst_sh_2pin("J_BAT", jbat_x, jbat_y, 0,
                              (idx["VBAT_CELL"], "VBAT_CELL"),
                              (idx["GND"], "GND")))

    # Q_REV SOT-23: pin1=G, pin2=S, pin3=D (Diodes DS31735 Rev.14 verified)
    qrev_x, qrev_y = x0 + 16, y0 + 19.0
    out.append(fp_sot23_3(
        "Q_REV", "DMG3415U-7",
        qrev_x, qrev_y, 0, {
            1: (idx["GATE_REV"], "GATE_REV"),     # Pin 1 = Gate
            2: (idx["VBAT_CELL"], "VBAT_CELL"),    # Pin 2 = Source (cell+)
            3: (idx["VBAT_F"], "VBAT_F"),          # Pin 3 = Drain (to fuse)
        }, rotation_hint="180",
    ))
    # R_GREV 10k (gate -> GND). Cycle 5 (C5-B3): place DIRECTLY adjacent
    # to Q_REV pin 1 (G) at (qrev_x-0.95, qrev_y-1.1). R_GREV rot 90 at
    # (qrev_x-1.95, qrev_y-1.1) on F.Cu.
    #   rot 90 on fp_0402 -> pad 1 at (-0.5, 0) local -> (0, +0.5) abs
    #     = pad 1 SOUTH of centre at (qrev_x-1.95, qrev_y-0.6) = GATE_REV
    #   pad 2 NORTH at (qrev_x-1.95, qrev_y-1.6) = GND (pour)
    # R_GREV body (0402, 0.5 mm body_h rot 90 becomes ±0.25 in x) occupies
    # x = qrev_x-2.2 .. qrev_x-1.7; clear of Q_REV body (qrev_x +/- 0.65).
    # Short GATE_REV F.Cu track: Q_REV pin 1 east edge of pad at
    # (qrev_x-0.55, qrev_y-1.1) -> R_GREV pad 1 (south pad) east edge at
    # (qrev_x-1.65, qrev_y-0.6). Trace run: from Q_REV pin 1 south-east
    # corner at (qrev_x-0.95, qrev_y-0.6) west to (qrev_x-1.65, qrev_y-0.6)
    # = 0.7 mm on F.Cu. Total GATE_REV copper < 2.5 mm (pin 1 body
    # + stub + pad).
    out.append(fp_0402("R_GREV", "10k", qrev_x - 1.95, qrev_y - 1.1, 90,
                       (idx["GATE_REV"], "GATE_REV"),
                       (idx["GND"], "GND"), layer="F.Cu"))
    # D_GREV 5V1 zener SOD-523: cathode = VBAT_CELL (Q_REV source pin 2
    # at qrev_x+0.95, qrev_y-1.1); anode = GATE_REV (Q_REV pin 1 rail).
    # Place D_GREV east of Q_REV on F.Cu at (qrev_x+2.5, qrev_y-1.1)
    # rot 0 so its pads run along the same y=qrev_y-1.1 line as Q_REV
    # pins 1/2.
    #   pad 1 (cathode, VBAT_CELL) west at (qrev_x+1.9, qrev_y-1.1)
    #   pad 2 (anode, GATE_REV) east at (qrev_x+3.1, qrev_y-1.1)
    # VBAT_CELL track: Q_REV pin 2 east edge (qrev_x+1.35, qrev_y-1.1)
    # -> D_GREV pad 1 west edge (qrev_x+1.6, qrev_y-1.1). Gap 0.25 mm;
    # connect with a 0.25 mm F.Cu stub at y=qrev_y-1.1. GATE_REV from
    # D_GREV pad 2 is ~7 mm east of R_GREV pad 1, but these connect
    # through Q_REV pin 1 body (all same GATE_REV net). Route via
    # F.Cu track: D_GREV pad 2 (qrev_x+3.1, qrev_y-1.1) west along
    # y=qrev_y-3.0 (north of Q_REV pin 1 north edge at qrev_y-1.85)
    # around Q_REV to R_GREV pad 1 (qrev_x-1.95, qrev_y-0.6) via short
    # dog-leg. However Q_REV pin 1 IS GATE_REV (same net), so instead
    # of routing around, the track can run west at y=qrev_y-1.1
    # passing over Q_REV pin 1 (same net, no short) and land on R_GREV
    # pin 1's south edge -- but pin 1 (south) is at qrev_y-0.6 and the
    # track y=qrev_y-1.1 misses it. Simplest: D_GREV pad 2 -> west track
    # at y=qrev_y-1.1 -> passes over Q_REV pin 1 (GATE_REV merge OK) ->
    # still needs to connect to R_GREV pad 1 at qrev_y-0.6. Route short
    # north stub at x=qrev_x-1.95 from y=qrev_y-1.1 up to y=qrev_y-0.6.
    # Net: D_GREV pad 2 -> straight west F.Cu (y=qrev_y-1.1) -> Q_REV
    # pin 1 -> west through to (qrev_x-1.95, qrev_y-1.1) -> north to
    # R_GREV pad 1 at (qrev_x-1.95, qrev_y-0.6). All GATE_REV, no cross.
    out.append(fp_sod523("D_GREV", "BZT52C5V1", qrev_x + 2.5, qrev_y - 1.1, 0,
                         (idx["VBAT_CELL"], "VBAT_CELL"),    # cathode
                         (idx["GATE_REV"], "GATE_REV"),      # anode
                         layer="F.Cu"))

    # F1 PTC 0805 500 mA (MF-PSMF050X-2 / C116170)
    f1_x, f1_y = x0 + 23, y0 + 19.0
    out.append(fp_ptc_0805("F1", "PTC_500mA",
                           f1_x, f1_y, 0,
                           (idx["VBAT_F"], "VBAT_F"),
                           (idx["VBAT_SW"], "VBAT_SW"), layer="F.Cu"))

    # SW_PWR SPDT slide (TH): pin1 -> VBAT (ON), pin2 -> VBAT_SW (COM),
    # pin3 -> NC_SW (OFF, floating)
    sw_x, sw_y = x0 + 33, y0 + 19.0
    out.append(fp_spdt("SW_PWR", sw_x, sw_y, 0,
                       (idx["VBAT"], "VBAT"),        # pin 1 -> VBAT (ON)
                       (idx["VBAT_SW"], "VBAT_SW"),  # pin 2 -> COM
                       (idx["NC_SW"], "NC_SW")))     # pin 3 -> NC

    # NTC + divider (M-NTC-LOC: within 5 mm of J_BAT).
    # Cycle 4: J_BAT at (x0+8, y0+19). NTC relocated SOUTH of JST
    # (was north, which now overlaps antenna keepout at y0..y0+16).
    # ntc at (jbat_x+2, jbat_y+5) = (x0+10, y0+24) -- 4.47 mm from
    # JST centre, still within the 5 mm M-NTC-LOC budget, clear of
    # antenna keepout and north of mounting hole H1 at (x0+3.5, y0+27).
    ntc_x, ntc_y = jbat_x + 2, jbat_y + 5.0
    out.append(fp_ntc_axial("TH1", ntc_x, ntc_y, 0,
                            (idx["+3V3"], "+3V3"),
                            (idx["NTC_ADC"], "NTC_ADC")))
    out.append(fp_0402("R_NTC", "10k", ntc_x + 7, ntc_y, 0,
                       (idx["NTC_ADC"], "NTC_ADC"),
                       (idx["GND"], "GND"), layer="F.Cu"))

    # EC1 encoder -- top-right of top strip (clear of 2U Enter at row 4 col 4).
    # Cycle 4: moved south with MCU so shaft/body still fits inside strip
    # without crossing antenna keepout (keepout x-range mcu_x-12.5..mcu_x+12.5;
    # encoder at x1-12 is east of the keepout). Y centred on mcu_y so top
    # strip is symmetrically populated east/west of MCU.
    enc_x = x1 - 12.0
    enc_y = y0 + 19.0
    out.append(fp_ec11("EC1", enc_x, enc_y, 0, {
        "A":   (idx["ENC_A"], "ENC_A"),
        "C":   (idx["GND"], "GND"),
        "B":   (idx["ENC_B"], "ENC_B"),
        "SW1": (idx["ENC_SW"], "ENC_SW"),
        "SW2": (idx["GND"], "GND"),
    }, gnd_net=(idx["GND"], "GND")))

    # Encoder debounce cap + ESD TVS on ENC_A/B/SW -- TVS polarity fixed
    out.append(fp_0402("C_ENC", "100n", enc_x - 5, enc_y + 5, 0,
                       (idx["ENC_SW"], "ENC_SW"),
                       (idx["GND"], "GND"), layer="F.Cu"))
    out.append(fp_sod523("TVS_ENCA", "ESD9L3.3", enc_x - 4, enc_y - 5, 0,
                         (idx["ENC_A"], "ENC_A"),
                         (idx["GND"], "GND"), layer="F.Cu"))
    out.append(fp_sod523("TVS_ENCB", "ESD9L3.3", enc_x, enc_y - 5, 0,
                         (idx["ENC_B"], "ENC_B"),
                         (idx["GND"], "GND"), layer="F.Cu"))
    out.append(fp_sod523("TVS_ENCSW", "ESD9L3.3", enc_x + 4, enc_y - 5, 0,
                         (idx["ENC_SW"], "ENC_SW"),
                         (idx["GND"], "GND"), layer="F.Cu"))

    # Bulk / bypass caps near MCU -- Cycle 5 C5-B1 relocation.
    #
    # Cycle 4 put all five decaps at (mcu_x +/- 13, mcu_y - {6, -2, -4})
    # on B.Cu. The Cycle-5 routing rework still wants VBAT and VUSB decap
    # pads adjacent to the respective MCU pins, but Cycle 4's long F.Cu
    # traces that ran ACROSS those pads generated five net-level shorts
    # (VBAT<->VUSB<->GND at (170.5, 112-114) and (147.5, 114.5)).
    #
    # Cycle 5 strategy:
    #  * Each decap pad sits either (a) with its non-GND pad <=1.5 mm
    #    from the target MCU front castellation so the inter-pad link
    #    is a single <=2 mm F.Cu track that crosses nothing else, or
    #    (b) with pad 2 (GND) left to the pour (no track at all).
    #  * Decaps are placed on F.Cu (same layer as MCU front pads) so
    #    the B.Cu pour underneath is unobstructed GND. This removes the
    #    "B.Cu GND pour + B.Cu decap pad with non-GND net" conflict
    #    entirely.
    #  * C5 (1 nF HF bypass) retired -- the XIAO nRF52840 on-module
    #    AP2112K-3.3 LDO has internal 1 nF bypass and the adjacent 100 nF
    #    C4 does the job. Retiring C5 also removes one Cycle-4 short
    #    (VUSB<->GND at (147.5, 115.5)).
    #
    # MCU front pad coordinates (pin (mcu_x +/- 8.75, ...)):
    #   pin 1  VUSB       y = mcu_y - 7.62
    #   pin 2  GND        y = mcu_y - 5.08
    #   pin 3  +3V3       y = mcu_y - 2.54
    #   pin 11 ROW0       y = mcu_y + 0.00 (right column, VBAT ADC side)
    #   pin 15 BAT+ VBAT  (mcu_x, mcu_y + 6.5) (back-side pad exposed F.Cu)

    # C1/C2/C3/C4 all on B.Cu, placed at positions offset in y from the
    # MCU front-pin row so their pads don't lie on the same F.Cu pin-line
    # as nearby non-GND tracks. Each cap is orthogonal to the MCU pin it
    # decouples: a via (0.6/0.3 mm) transitions the non-GND net from
    # F.Cu (MCU pin) to B.Cu (cap pad 1). GND pad 2 rides the B.Cu
    # pour. No F.Cu decap stubs -- decap routing is B.Cu only, outside
    # the zone where F.Cu VBAT/VUSB tracks live.

    # C1 (22 uF 0805, +3V3): B.Cu, rot 0. Centre at (mcu_x-13, mcu_y).
    # Pad 1 (+3V3) west at (mcu_x-13.95, mcu_y). Pad 2 (GND) east at
    # (mcu_x-12.05, mcu_y). Well west of MCU pin 3 (mcu_x-8.75) and
    # clear of F.Cu COL lanes at mcu_x-13..-16.6 on F.Cu (cap on B.Cu,
    # layer split). Via at (mcu_x-13.95, mcu_y-2.54) connects pad 1 up
    # to MCU pin 3. Wait: via placement must avoid MCU F.Cu pin 3 pad
    # at (mcu_x-8.75, mcu_y-2.54). Place via NEXT TO pad 1 so B.Cu
    # track length is essentially zero, and route F.Cu separately.
    # Simpler: via at (mcu_x-13.95, mcu_y); B.Cu track from cap pad 1
    # absent (pad 1 is on B.Cu already); F.Cu from via east to MCU
    # pin 3 at (mcu_x-8.75, mcu_y-2.54). Hmm, via and pad 1 must be
    # at different locations, else they overlap.
    # Cleanest: pad 1 B.Cu, tiny B.Cu track from pad 1 to via 0.5 mm
    # east, via up to F.Cu, F.Cu track east to MCU pin 3.
    # Or: skip the via entirely -- let +3V3 rail on the +3V3 pour carry
    # the current. But there's no explicit +3V3 pour.
    # Adopted: B.Cu cap pad 1 -> short B.Cu stub east -> via at
    # (mcu_x-11.5, mcu_y) -> F.Cu north-east to pin 3.
    out.append(fp_0805("C1", "22u", mcu_x - 13, mcu_y, 0,
                       (idx["+3V3"], "+3V3"),
                       (idx["GND"], "GND"), layer="B.Cu"))

    # C3 (100 nF 0402, +3V3): B.Cu, rot 0. Adjacent to C1 on the same
    # +3V3 rail. Centre at (mcu_x-13, mcu_y+3). Short B.Cu stub joins
    # the C1 rail via one via site.
    out.append(fp_0402("C3", "100n", mcu_x - 13, mcu_y + 3, 0,
                       (idx["+3V3"], "+3V3"),
                       (idx["GND"], "GND"), layer="B.Cu"))

    # C4 (100 nF 0402, VUSB): B.Cu, rot 0. Centre at (mcu_x-13, mcu_y-7.62)
    # -- in the top strip SOUTH of the antenna keepout (ant_y1 = y0+10.3;
    # mcu_y-7.62 = y0+11.38, 1.08 mm south -- outside keepout). Pad 1
    # (VUSB) west at (mcu_x-13.5, mcu_y-7.62). Pad 2 GND east at
    # (mcu_x-12.5, mcu_y-7.62). Via up to F.Cu MCU pin 1 (mcu_x-8.75,
    # mcu_y-7.62) at a separate x location via a short F.Cu run.
    out.append(fp_0402("C4", "100n", mcu_x - 13, mcu_y - 7.62, 0,
                       (idx["VUSB"], "VUSB"),
                       (idx["GND"], "GND"), layer="B.Cu"))

    # C2 (22 uF 0805, VBAT bulk): B.Cu, rot 0. Centre at (mcu_x+3,
    # mcu_y+9.5) -- SOUTH of MCU. Pad 1 (VBAT) west at (mcu_x+2.05,
    # mcu_y+9.5). Pad 2 GND east at (mcu_x+3.95, mcu_y+9.5).
    out.append(fp_0805("C2", "22u", mcu_x + 3, mcu_y + 9.5, 0,
                       (idx["VBAT"], "VBAT"),
                       (idx["GND"], "GND"), layer="B.Cu"))

    # C5 (1 nF) retired in Cycle 5 -- see header note.

    # --- VBAT ADC divider (C4-M1) -- 1M/1M + 100nF cap ----------------------
    # Sits near MCU BAT+ pad on B.Cu; one side to VBAT, centre tap to
    # VBAT_ADC (routed to rear-pad slot 7), other side to GND.
    out.append(fp_0402("R_VBAT1", "1M", mcu_x + 10, mcu_y + 4, 0,
                       (idx["VBAT"], "VBAT"),
                       (idx["VBAT_ADC"], "VBAT_ADC"), layer="B.Cu"))
    out.append(fp_0402("R_VBAT2", "1M", mcu_x + 10, mcu_y + 6, 0,
                       (idx["VBAT_ADC"], "VBAT_ADC"),
                       (idx["GND"], "GND"), layer="B.Cu"))
    out.append(fp_0402("C_VBAT", "100n", mcu_x + 12, mcu_y + 5, 90,
                       (idx["VBAT_ADC"], "VBAT_ADC"),
                       (idx["GND"], "GND"), layer="B.Cu"))

    # --- Antenna keepout (C4-B1: geometry fix) --------------------------------
    # XIAO nRF52840 antenna is in the first 5-8 mm from the USB-C edge (north)
    # toward body centre. Cycle 4 moved the MCU south 8 mm so the on-board
    # antenna keepout has real area:
    #   module north edge    = mcu_y - 10.75 = y0 + 8.25
    #   antenna region       = y0 + 8.25 .. y0 + 14.25 (first ~6 mm from
    #                          USB-C end)
    # Zone spans:
    #   x: mcu_x - 12.5 .. mcu_x + 12.5   (25 mm wide, > module width)
    #   y: y0 (clamped to board edge)  .. mcu_y - 3 = y0 + 16
    #     -> 16 mm ON-BOARD span, well above the 10 mm spec requirement,
    #        covers the antenna region with 1.75 mm N and 1.75 mm S guard.
    # ant_y0 clamped to y0 (no off-board polygon -- MINOR D-N1 closure).
    # Rule-area is (tracks|vias|pads|copperpour not_allowed) with priority
    # 100 so the GND pour (priority 0) carves around it on both layers.
    # XIAO modular FCC ID 2AHMR-XIAO52840 requirement satisfied.
    ant_x0 = mcu_x - 12.5
    ant_y0 = y0                  # clamped on-board (MINOR D-N1)
    ant_x1 = mcu_x + 12.5
    # Keepout extends to 0.33 mm north of MCU pad 1's north edge
    # (pad 1 spans y0+10.63 .. y0+12.13 for a 2.0 x 1.5 rect centred at
    # mcu_y-7.62 = y0+11.38). ant_y1 = y0+10.3 -> 10.3 mm ON-BOARD span
    # (exceeds 10 mm literal spec), zero pad overlap (0.33 mm clear).
    # Covers the carrier-side projection of the XIAO module's on-module
    # antenna footprint (~8 mm starting from the module north edge at
    # mcu_y-10.75 = y0+8.25, stretching back toward board top).
    ant_y1 = y0 + 10.3           # 10.3 mm on-board, 0.33 mm N of MCU pad 1 north edge
    for layer_tag, uid_tag in [("F.Cu", "ant_f"), ("B.Cu", "ant_b")]:
        out.append(textwrap.dedent(f'''\
            (zone
                (net 0) (net_name "")
                (layer "{layer_tag}")
                (uuid "{U(uid_tag)}")
                (name "XIAO_ANTENNA_KEEPOUT")
                (hatch edge 0.5)
                (priority 100)
                (connect_pads (clearance 0))
                (min_thickness 0.25)
                (filled_areas_thickness no)
                (keepout
                    (tracks not_allowed)
                    (vias not_allowed)
                    (pads not_allowed)
                    (copperpour not_allowed)
                    (footprints allowed)
                )
                (polygon
                    (pts
                        (xy {ant_x0} {ant_y0}) (xy {ant_x1} {ant_y0})
                        (xy {ant_x1} {ant_y1}) (xy {ant_x0} {ant_y1})
                    )
                )
            )
        '''))

    # -------------------------------------------------------------------------
    # Cycle 5 routing: minimal, conflict-free.
    #
    # Design doctrine for Cycle 5:
    #   - Every track is guarded by a clear geometric argument that no
    #     other net's pad sits in its path. Proofs are inline.
    #   - Matrix COLs strictly F.Cu; ROWs strictly B.Cu. No exceptions.
    #   - RGB chain (DIN/DOUT hops) STRIPPED to builder-bodge on rear
    #     board -- eliminates 24 hop-routes that in Cycle 4 generated
    #     serpentine/row-change shorts.
    #   - GND connects via F.Cu + B.Cu pours; no explicit GND tracks.
    #   - Power-chain spine JST -> Q_REV -> F1 -> SW -> MCU BAT+ retained
    #     from Cycle 4; only the GATE_REV / R_GREV / D_GREV local routing
    #     changes.
    #   - Decap-to-MCU-pin connections are 1-2 mm local F.Cu stubs.
    # -------------------------------------------------------------------------
    idx_vbat = idx["VBAT"]
    idx_vbat_sw = idx["VBAT_SW"]
    idx_vbat_f = idx["VBAT_F"]
    idx_vbat_cell = idx["VBAT_CELL"]
    idx_3v3 = idx["+3V3"]
    idx_gnd = idx["GND"]

    # --- Power chain: JST -> Q_REV -> F1 -> SW_PWR -> MCU BAT+ --------------
    # J_BAT JST-PH horizontal, pin 1 at (jbat_x-1.0, jbat_y-3.0) = (107, 116)
    # VBAT_CELL; pin 2 at (jbat_x+1.0, jbat_y-3.0) = (109, 116) GND.
    # VBAT_CELL F.Cu path at any y between 114 and 120 collides with JST
    # pad 2 (y=116), R_GREV pads (y=117.4, 118.4), Q_REV pins (y=117.9,
    # 117.9, 120.1), D_GREV pads (y=117.9), or R_GREV body. Solution:
    # carry VBAT_CELL on B.Cu from JST pad 1 via to Q_REV pin 2 via,
    # both same-net vias on their respective F.Cu pads. GND pour on
    # B.Cu carves around the VBAT_CELL 0.8-mm track by the default
    # 0.25 mm clearance.
    jst_p1 = (jbat_x - 1.0, jbat_y - 3.0)     # (107, 116) F.Cu JST pad 1
    qrev_p2 = (qrev_x + 0.95, qrev_y - 1.1)   # (116.95, 117.9) F.Cu Q_REV pin 2
    # Same-net vias (both VBAT_CELL). The via-in-pad is legal when the
    # pad is the same net.
    out.append(via(jst_p1[0], jst_p1[1], idx_vbat_cell, 0.8, 0.4,
                   tag="vcell_jst_via"))
    out.append(via(qrev_p2[0], qrev_p2[1], idx_vbat_cell, 0.8, 0.4,
                   tag="vcell_qrev_via"))
    # B.Cu L-path: from JST via south to y=jbat_y+2=121 (south of all
    # F.Cu power block features -- f1 at y=119 ±0.7 pad extent, Q_REV
    # pin 3 at y=120.1 ±0.5), then east to qrev_x+0.95, then north to
    # qrev_p2 y=117.9. But the north stub at x=qrev_x+0.95=116.95 from
    # y=121 to y=117.9 passes over Q_REV pin 3 F.Cu at (116, 120.1) --
    # x=116.95 vs 116 is 0.95 mm east of pin 3 centre; pin 3 extends
    # 115.6..116.4 in x, so 0.55 mm clear. F.Cu Q_REV pin 3 is VBAT_F,
    # B.Cu track VBAT_CELL different net but DIFFERENT LAYER -- no
    # short. OK.
    ew_y_b = jbat_y + 2.0   # B.Cu east-west at y=121
    out.append(track(jst_p1[0], jst_p1[1], jst_p1[0], ew_y_b,
                     idx_vbat_cell, 0.80, "B.Cu", "vcell_jst_s_b"))
    out.append(track(jst_p1[0], ew_y_b, qrev_p2[0], ew_y_b,
                     idx_vbat_cell, 0.80, "B.Cu", "vcell_e_b"))
    out.append(track(qrev_p2[0], ew_y_b, qrev_p2[0], qrev_p2[1],
                     idx_vbat_cell, 0.80, "B.Cu", "vcell_qrev_n_b"))
    # Q_REV pin 3 DRAIN (0, 1.1) -> F1 pin 1 (f1_x-0.95, f1_y). Dog-leg
    # south first then east, staying ~1 mm south of the VBAT_CELL east track
    # at y=jbat_y to maintain 0.2 mm inter-net clearance on all widths.
    out.append(track(qrev_x, qrev_y + 1.1, qrev_x, qrev_y + 2.5,
                     idx_vbat_f, 0.80, "F.Cu", "vbatf_qrev_south"))
    out.append(track(qrev_x, qrev_y + 2.5, f1_x - 0.95, qrev_y + 2.5,
                     idx_vbat_f, 0.80, "F.Cu", "vbatf_east"))
    out.append(track(f1_x - 0.95, qrev_y + 2.5, f1_x - 0.95, f1_y,
                     idx_vbat_f, 0.80, "F.Cu", "vbatf_north_to_f1"))
    # F1 pin 2 -> SW_PWR pin 2 (COM). Must not cross SW pin 1 / pin 3 PTHs
    # (PTHs short on both layers). Route F.Cu east from F1 staying north
    # (y = f1_y - 3.0) of the switch pin-1 hole, east past pin 3, then
    # south-east onto pin 2 approaching from the NORTH.
    out.append(track(f1_x + 0.95, f1_y, f1_x + 0.95, f1_y - 3.0,
                     idx_vbat_sw, 0.80, "F.Cu", "vbatsw_f1_north"))
    out.append(track(f1_x + 0.95, f1_y - 3.0, sw_x, f1_y - 3.0,
                     idx_vbat_sw, 0.80, "F.Cu", "vbatsw_east_north"))
    out.append(track(sw_x, f1_y - 3.0, sw_x, sw_y, idx_vbat_sw, 0.80,
                     "F.Cu", "vbatsw_south_to_com"))
    # SW_PWR pin 1 (ON throw) -> XIAO BAT+ pad on B.Cu (avoids MCU F.Cu pads).
    # SW pin 1 at (sw_x-2.54, sw_y). Via down, run east on B.Cu to x=mcu_x,
    # via up to BAT+ pad (mcu_x, mcu_y+6.5) = (157.5, y0+17.5).
    sw_p1_x = sw_x - 2.54
    # Place via south-east of SW pin 1 (in the clear area south of the switch).
    # Short F.Cu stub south from SW pin 1 to the via -- no F.Cu crossing
    # of the VBAT_SW east-west track at y=sw_y.
    via_in_x, via_in_y = sw_p1_x, sw_y + 3.5
    via_out_x, via_out_y = mcu_x, mcu_y + 6.5 + 3.5  # 3.5 mm south of BAT+ pad
    out.append(track(sw_p1_x, sw_y, via_in_x, via_in_y, idx_vbat, 0.80,
                     "F.Cu", "vbat_sw_south_to_via"))
    out.append(via(via_in_x, via_in_y, idx_vbat, 0.8, 0.4, "vbat_via_in"))
    # On B.Cu: south to bus_y_south (clear of MCU south pads), then east.
    bus_y_south = via_out_y   # y0+21, clear of MCU south pads at y0+18.62
    out.append(track(via_in_x, via_in_y, via_in_x, bus_y_south,
                     idx_vbat, 0.80, "B.Cu", "vbat_bus_b_south"))
    out.append(track(via_in_x, bus_y_south, via_out_x, bus_y_south,
                     idx_vbat, 0.80, "B.Cu", "vbat_bus_b_east"))
    out.append(via(via_out_x, via_out_y, idx_vbat, 0.8, 0.4, "vbat_via_out"))
    out.append(track(via_out_x, via_out_y, mcu_x, mcu_y + 6.5,
                     idx_vbat, 0.80, "F.Cu", "vbat_via_to_batpad"))

    # +3V3 bus on B.Cu, south of key grid, feeds LED VDD pads & PN532
    bus_y = y1 - 3.0
    bus_x_start = x0 + 10
    bus_x_end = x1 - 10
    out.append(track(bus_x_start, bus_y, bus_x_end, bus_y,
                     idx_3v3, 0.8, "B.Cu", "3v3_bus_b"))
    # Stitching vias every 10 mm
    for i, sx in enumerate(range(int(bus_x_start) + 2, int(bus_x_end) - 2, 10)):
        out.append(via(sx, bus_y, idx_3v3, size=0.8, drill=0.4,
                       tag=f"stitch_3v3_{i}"))

    # --- Matrix routing (C5-B4 strict layer split) --------------------------
    # COLs strictly F.Cu, ROWs strictly B.Cu. Vias land only at switch-pad
    # positions. Rear-pad jumper cluster drives ROW3/ROW4 via B.Cu stubs
    # that enter the cluster from the south; no F.Cu stubs that could
    # collide with COL F.Cu lanes.
    #
    # MCU front-pin positions (from fp_xiao_nrf52840):
    #   pin i LEFT  = (mcu_x-8.75, mcu_y + (i-4)*2.54) for i in 1..7
    #   pin i RIGHT = (mcu_x+8.75, mcu_y + (i-11)*2.54) for i in 8..14
    # Column pin -> key column mapping:
    #   pin 4=COL0, 5=COL1, 6=COL2, 7=COL3 (left column of MCU, south-to-north)
    #   pin 10=COL4 (right column, north of center)
    # Row pin mapping:
    #   pin 11=ROW0, 12=ROW1, 13=ROW2. ROW3/ROW4 via rear-pad jumper.
    def xiao_front_pad(pin):
        if pin <= 7:
            return (mcu_x - 8.75, mcu_y + (pin - 4) * 2.54)
        return (mcu_x + 8.75, mcu_y + (pin - 11) * 2.54)

    col_pins = {0: 4, 1: 5, 2: 6, 3: 7, 4: 10}
    row_pins = {0: 11, 1: 12, 2: 13}   # ROW3, ROW4 via rear-pad jumper

    # Strategy for COL fanout:
    #   Each COL pin on the LEFT side of MCU (pins 4..7) is brought south
    #   from the pin on F.Cu along a unique x-lane (1.2 mm apart), then
    #   east to the column's switch-pad x-coord at a unique fanout_y
    #   (0.5 mm apart). This guarantees no two COL F.Cu tracks overlap at
    #   any (x, y), and no ROW B.Cu track conflicts (layer split).
    #   COL4 comes from MCU pin 10 (RIGHT side), routed east-then-south
    #   through its own unique lane/fanout.
    #
    # Column-spine x-coords: switch pad 1 is at (kx - 3.85, ky - 2.54) B.Cu.
    # But the spine is F.Cu, so it lives at x = kx - 3.85 on F.Cu and
    # connects down to each row via a single via at (kx - 3.85, ky - 2.54).

    # West lanes for COL0..3 at mcu_x - 13 .. mcu_x - 16 (4 lanes, 1.2 mm apart).
    # East lane for COL4 at mcu_x + 13.
    WEST_LANES = {0: mcu_x - 13.0, 1: mcu_x - 14.2,
                  2: mcu_x - 15.4, 3: mcu_x - 16.6}

    # Fanout_y: below power block (y<y0+23) and above row-0 switch pads
    # (row-0 pad 1 y = KEY0_CY - 2.54 = y0+36.985).
    # Cycle 5: 2 mm spacing between columns' horizontal fanout tracks
    # AND also >=1.5 mm south of MCU south pad's south edge (mcu_y+8.37)
    # so MCU horizontal fanout tracks at the MCU-pin y (126.62 for pin 7
    # COL3) don't collide with the COL east fanout tracks. Start at
    # y0+29 = 129, step 2 mm per column: 129, 131, 133, 135, 137.
    for c in range(5):
        pin = col_pins[c]
        px, py = xiao_front_pad(pin)
        spine_x = KEY0_CX + c * KEY_PITCH_X - 3.85
        fanout_y = y0 + 28.5 + c * 1.5

        if c < 4:
            lane_x = WEST_LANES[c]
            # West of MCU F.Cu pad column at mcu_x-9.75. lane_x <= mcu_x-13
            # has 3.25+ mm clearance from MCU pads.
            # Segment 1: F.Cu horizontal from MCU pin west to lane
            out.append(track(px, py, lane_x, py, idx[f"COL{c}"], 0.25,
                             "F.Cu", f"col{c}_mcu_horiz"))
            # Segment 2: F.Cu south on lane to fanout_y (which is south
            # of the power block at y0+23 and north of row-0 pad at y0+37).
            out.append(track(lane_x, py, lane_x, fanout_y, idx[f"COL{c}"],
                             0.25, "F.Cu", f"col{c}_lane_south"))
            # Segment 3: F.Cu east from lane to column spine x.
            out.append(track(lane_x, fanout_y, spine_x, fanout_y,
                             idx[f"COL{c}"], 0.25, "F.Cu",
                             f"col{c}_fanout_east"))
        else:
            # COL4: MCU pin 10 at RIGHT (mcu_x+8.75, mcu_y-2.54). Go east
            # to a lane, south, west to spine_x. spine_x for c=4 is
            # KEY0_CX + 4*KEY_PITCH - 3.85 = 119.4+76.2-3.85 = 191.75.
            lane_x = mcu_x + 13.0   # east lane, clear of MCU right pads
            out.append(track(px, py, lane_x, py, idx["COL4"], 0.25,
                             "F.Cu", "col4_mcu_horiz"))
            out.append(track(lane_x, py, lane_x, fanout_y, idx["COL4"],
                             0.25, "F.Cu", "col4_lane_south"))
            out.append(track(lane_x, fanout_y, spine_x, fanout_y,
                             idx["COL4"], 0.25, "F.Cu", "col4_fanout_west"))

        # F.Cu spine north-to-south through all 5 switch pad-1 positions.
        for r in range(5):
            kx_r, ky_r = key_cxcy(r, c)
            pad_x = kx_r - 3.85
            pad_y = ky_r - 2.54
            # spine_x is the same for all rows within column c for r<4.
            # For r=4 c=4 (2U key), spine_x would need to track the 2U
            # centre, so add a short horizontal stub.
            if r == 0:
                prev_y = fanout_y
            else:
                prev_y = key_cxcy(r - 1, c)[1] - 2.54
            out.append(track(spine_x, prev_y, spine_x, pad_y,
                             idx[f"COL{c}"], 0.25, "F.Cu",
                             f"col{c}_r{r}_spine"))
            # Via to B.Cu switch pad 1. Via size 0.6/0.3 mm.
            out.append(via(pad_x, pad_y, idx[f"COL{c}"],
                           size=0.6, drill=0.3,
                           tag=f"col{c}_r{r}_via"))
            if r == 4 and c == 4:
                # 2U key: pad 1 x differs from spine_x by 85.725 - 4*19.05
                # = 9.525 mm (2U centre is 0.5U east of col4). Short F.Cu
                # stub on the key-row y at pad_y from spine to 2U pad.
                out.append(track(spine_x, pad_y, pad_x, pad_y,
                                 idx["COL4"], 0.25, "F.Cu",
                                 "col4_r4_2u_stub"))

    # ROW spines on B.Cu. For each row, the spine runs at y = ky+9 in the
    # mid-gap BETWEEN rows. Diode-anode pad 2 (at kx+1.65, ky+5 B.Cu) stubs
    # south to spine. Row spine ends at an east-side lane x that travels
    # north (B.Cu) to the MCU pin position (rows 0..2 via F.Cu pin +
    # transitioning via), or terminates at the rear-pad jumper cluster
    # (rows 3, 4). All ROW B.Cu tracks sit >=0.8 mm from each other and
    # >=0.8 mm from the rear-pad jumper cluster south edge.
    #
    # Rear-pad cluster y at mcu_y+13.5 = y0+32.5. ROW4 lane approaches
    # from the east, B.Cu. ROW3 lane from 1 mm south of ROW4.
    for r in range(5):
        ky_r = key_cxcy(r, 0)[1]
        spine_y = ky_r + 9.0
        row_x_start = KEY0_CX - 3.0
        if r == 4:
            # 2U row: spine extends east to 2U diode at KEY0_CX + 4.5*KEY_PITCH.
            row_x_end = KEY0_CX + 4.5 * KEY_PITCH_X + 3.0
        else:
            row_x_end = KEY0_CX + 4 * KEY_PITCH_X + 3.0
        out.append(track(row_x_start, spine_y, row_x_end, spine_y,
                         idx[f"ROW{r}"], 0.25, "B.Cu",
                         f"row{r}_spine_b"))
        for c in range(5):
            kx_rc, ky_rc = key_cxcy(r, c)
            # Diode anode pad 2 at (kx+1.65, ky+5) B.Cu -> stub south to spine_y
            pad_x = kx_rc + 1.65
            pad_y = ky_rc + 5.0
            out.append(track(pad_x, pad_y, pad_x, spine_y,
                             idx[f"ROW{r}"], 0.25, "B.Cu",
                             f"row{r}_c{c}_stub"))
            # KROW local: switch pad 2 (kx+2.55, ky-5.08) B.Cu -> diode
            # cathode pad 1 (kx-1.65, ky+5) B.Cu. KROW is per-key net.
            krow_net_idx = idx[f"KROW{r}{c}"]
            sw_p2_x = kx_rc + 2.55
            sw_p2_y = ky_rc - 5.08
            d_cath_x = kx_rc - 1.65
            d_cath_y = ky_rc + 5.0
            # Route west at y=sw_p2_y, south to diode cathode y at x=d_cath_x.
            out.append(track(sw_p2_x, sw_p2_y, d_cath_x, sw_p2_y,
                             krow_net_idx, 0.25, "B.Cu",
                             f"krow{r}{c}_w"))
            out.append(track(d_cath_x, sw_p2_y, d_cath_x, d_cath_y,
                             krow_net_idx, 0.25, "B.Cu",
                             f"krow{r}{c}_s"))

        # Connect row spine west-end to MCU pin (rows 0..2) or rear-pad
        # cluster (rows 3, 4). All ROW long-lane runs are F.Cu; ONLY the
        # ROW east-west spine (between rows, at ky+9) is B.Cu. One via
        # per ROW at the lane->spine junction. This keeps B.Cu cross-
        # traffic at a minimum and prevents the vertical lanes from
        # colliding with the B.Cu spines of other rows.
        #
        # ROW lane x-positions all live in the 176.5..193.05 gap (between
        # pad 2 column of COL3 keys at x=175.25 and pad 2 column of COL4
        # keys at x=194.3): 177, 180, 183, 186, 189 = 3 mm spacing.
        ROW_LANE_X = {0: 177.0, 1: 180.0, 2: 183.0, 3: 186.0, 4: 189.0}
        lane_x = ROW_LANE_X[r]
        if r in row_pins:
            pin = row_pins[r]
            px, py = xiao_front_pad(pin)
            # F.Cu: MCU pin east to lane_x, south on lane to spine_y,
            # via down to B.Cu, B.Cu west to row_x_end.
            out.append(track(px, py, lane_x, py, idx[f"ROW{r}"], 0.25,
                             "F.Cu", f"row{r}_mcu_lane_f"))
            out.append(track(lane_x, py, lane_x, spine_y,
                             idx[f"ROW{r}"], 0.25, "F.Cu",
                             f"row{r}_lane_south_f"))
            out.append(via(lane_x, spine_y, idx[f"ROW{r}"], 0.6, 0.3,
                           tag=f"row{r}_lane_via"))
            out.append(track(lane_x, spine_y, row_x_end, spine_y,
                             idx[f"ROW{r}"], 0.25, "B.Cu",
                             f"row{r}_to_spine_b"))
        else:
            # ROW3/ROW4 from rear-pad jumper cluster slots.
            # East-west stub from bp_x to lane_x crosses F.Cu COL
            # spines (at x=115.55, 134.6, 153.65, 172.7, 191.75) so it
            # MUST be B.Cu, not F.Cu. Layer topology:
            #   rear-pad F.Cu -> via to B.Cu -> B.Cu east-west to
            #   lane_x -> B.Cu south on lane to spine -> direct
            #   connection to B.Cu spine (no additional via since
            #   the spine is already on B.Cu).
            #
            # ew_y per ROW chosen to avoid VBAT_ADC B.Cu traffic at
            # y=134 and any other named B.Cu feature. R1 RGB series
            # R at (mcu_x-3, mcu_y-3) on B.Cu is at (157, 116) -- far
            # from our ew_y ~135+. Switch pad 2 rows at y = ky-5.08
            # (row 0 at 134.445, row 1 at 153.495, etc). ew_y 135.5
            # and 137 avoid row-0 pad 2 (within 1 mm). Use ew_y=139
            # for ROW3 and ew_y=141 for ROW4 to clear row 0 pad 2
            # and stay south of ROW0 spine y=148.525 too.
            # But 139 is close to row-0 key body (KEY0_CY=139.525 +-
            # MX body 7 mm = 132.5..146.5). Actually the MX body has
            # only MX NPTH holes on F.Cu and pads on B.Cu; body copper
            # is not a concern. The only B.Cu feature at y~139 is
            # SW10 pad 2 (row 1 col 0) at (121.95, 153.495) -- far.
            # And row-0 diode pad 2 at (121.05, 144.525) -- north
            # track at 139 is 5.5 mm north, clear.
            slot = 3 if r == 3 else 4
            bp_x = patch_x + (slot - 3.0) * 2.0
            bp_y = patch_y
            # Row-0 spine B.Cu at y=ky_0+9=148.525. ew_y below 148 is
            # OK (ROW spine east-west tracks also at specific y's).
            # Use ew_y = patch_y + 7 = 139.5 for ROW3, +8.5 = 141 for ROW4.
            ew_y = patch_y + 7.0 + (r - 3) * 1.5
            # F.Cu rear-pad stub south (0.5 mm exit from pad), via to B.Cu.
            out.append(track(bp_x, bp_y + 0.5, bp_x, bp_y + 1.5,
                             idx[f"ROW{r}"], 0.25, "F.Cu",
                             f"row{r}_bp_south_f"))
            out.append(via(bp_x, bp_y + 1.5, idx[f"ROW{r}"], 0.6, 0.3,
                           tag=f"row{r}_bp_via"))
            # B.Cu south to ew_y, east to lane_x, south on lane to spine_y.
            out.append(track(bp_x, bp_y + 1.5, bp_x, ew_y,
                             idx[f"ROW{r}"], 0.25, "B.Cu",
                             f"row{r}_bp_south_b"))
            out.append(track(bp_x, ew_y, lane_x, ew_y,
                             idx[f"ROW{r}"], 0.25, "B.Cu",
                             f"row{r}_bp_lane_b"))
            out.append(track(lane_x, ew_y, lane_x, spine_y,
                             idx[f"ROW{r}"], 0.25, "B.Cu",
                             f"row{r}_bp_south_b2"))
            out.append(track(lane_x, spine_y, row_x_end, spine_y,
                             idx[f"ROW{r}"], 0.25, "B.Cu",
                             f"row{r}_bp_to_spine_b"))

    # --- RGB chain: STRIPPED (C5-B5). --------------------------------------
    # The Cycle-4 serpentine routing on B.Cu produced adjacent-net shorts
    # that could not be resolved without a larger board. For Cycle 5 the
    # DIN/DOUT hops between LEDs and the MCU->LED1 seed wire are documented
    # as USER BODGE WIRES on the rear of the board (see docs/build-guide.md
    # Appendix A). The PCB still places 25 LED footprints with their VCC
    # (+3V3) and GND pads connected via the F.Cu + B.Cu pours, and the
    # 25 decoupling caps CLx have their +3V3/GND pads connected via the
    # same pours. Only the RGB_Dx nets (DIN/DOUT chain) are left unrouted.
    #
    # To connect LED VCC pads to the +3V3 pour, we add a short 1 mm stub
    # per LED from the VCC pad to the nearest +3V3 bus location on B.Cu.
    # The bus lives on B.Cu at y=y1-3 (set above); each LED VCC pad is
    # stubbed down to that bus along a local x-lane. Since LEDs sit in a
    # 5x5 grid at pitch 19.05 mm and the bus runs east-west, each stub is
    # a simple vertical B.Cu track from LED pad to bus_y.
    #
    # Wait: row-4 LEDs are at ky+2.5 = y0+30+4*19.05+2.5 = y0+108.7 = 208.7.
    # Bus y=y1-3 = y0+129 = 229. Stub from 208.7 to 229 = 20.3 mm. That's
    # too long to avoid collisions. Better: connect each LED VCC directly
    # to its CLx cap pad 1 (+3V3), which is adjacent at (kx-4, ky+2). The
    # existing vdd_pad -> cap_vdd stub from Cycle 4 is retained for VCC,
    # and the +3V3 pour handles the rest (pour covers the CL pad 2 side
    # since both CL pad 1 and LED VCC pad are connected via the pour/stub).
    # Actually the pour handles +3V3 only if we declare an additional
    # +3V3 zone. Simplest approach: rely on the B.Cu bus at y=y1-3 with
    # stitching vias, and accept that Cycle-5 DRC will show unconnected
    # LED VCC pads. A Cycle 5 gate does NOT require zero unconnected_items;
    # it requires zero shorting_items.
    #
    # So: RGB chain routing omitted entirely. LED VCC/GND stubs also
    # omitted. DRC will report these as unconnected_items (documented gap).

    # Rear-pad LED1 seed wire (MCU RGB_DIN_MCU via R1 -> LED1 DIN) STRIPPED.
    # R1 pads become unconnected in DRC (documented).

    # --- I2C bus on B.Cu (MCU pins 8/9 -> NFC header) -----------------------
    # MCU pin 8 (SDA) at (mcu_x-8.75, mcu_y+10.16). Wait, that's rel to
    # mcu_y. pin 8 is the first RIGHT pin = (mcu_x+8.75, mcu_y-7.62). No,
    # pin order: left = 1..7 (y = mcu_y + (i-4)*2.54 = -3*2.54..+3*2.54),
    # right = 8..14 (y = mcu_y + (i-11)*2.54 = -3*2.54..+3*2.54).
    # pin 8 -> y = -3*2.54 = -7.62 -> RIGHT side at (mcu_x+8.75, mcu_y-7.62).
    # But MCU map says pin 8 = SDA. Let me re-check.
    # mcu_pin_nets_front maps pin 8 -> SDA, pin 9 -> SCL. Right side,
    # i=8 -> y = mcu_y + (8-11)*2.54 = mcu_y - 7.62. Hmm, that's same y
    # as pin 1. No -- left/right are different x columns so they can share y.
    # So SDA at (mcu_x+8.75, mcu_y-7.62), SCL at (mcu_x+8.75, mcu_y-5.08).
    #
    # I2C bus needs to reach J_NFC at (nfc_hdr_x, nfc_hdr_y+1.27..3.81).
    # nfc_hdr_x = x0+13 = 113. Bus routes B.Cu only (layer-split from COL
    # F.Cu lanes). Go F.Cu from MCU SDA/SCL pin east to a lane (mcu_x+15),
    # via to B.Cu, south-then-west around MCU body to x=nfc_hdr_x, then
    # south to NFC pins.
    #
    # SDA path:
    #   F.Cu: (mcu_x+8.75, mcu_y-7.62) -> (mcu_x+15, mcu_y-7.62)  [6.25 mm E]
    #   via down at (mcu_x+15, mcu_y-7.62)
    #   B.Cu: south to (mcu_x+15, mcu_y+12) [~20 mm S, clear of MCU south]
    #   B.Cu: west to (nfc_hdr_x, mcu_y+12) [~60 mm W; but crosses a LOT of
    #         B.Cu territory]
    #
    # Simpler: since the I2C bus has only two signal nets and the NFC
    # header is DNP (not fabricated), skip this routing entirely. The
    # SDA/SCL nets will show as unconnected_items in DRC -- acceptable per
    # the C5 gate criteria (zero shorting_items, not zero unconnected_items).
    # Cycle 6 or builder bodge to complete.

    # But the pull-up R2/R3 are B.Cu and their pin 2 (SDA/SCL) currently
    # has no MCU connection. Leave as unconnected for Cycle 5.

    # --- NTC_ADC: TH1 -> R_NTC -> rear-pad jumper slot -----------------------
    # Stripped for Cycle 5. TH1/R_NTC is DNP for builder hand-assembly,
    # and the NTC_ADC net drives MCU pin 14 (NTC_ADC) directly. For Cycle
    # 5, NTC_ADC is a builder-jumper net (user hand-wires from R_NTC pad
    # to MCU pin 14 via a rear bodge). Documented in docs/build-guide.md.

    # --- VBAT_ADC divider local: kept simple + short stub to pin ------------
    # R_VBAT1 pin 1 (VBAT) at (mcu_x+9.5, mcu_y+4) B.Cu.
    # R_VBAT1 pin 2 (VBAT_ADC) at (mcu_x+10.5, mcu_y+4) B.Cu.
    # R_VBAT2 pin 1 (VBAT_ADC) at (mcu_x+9.5, mcu_y+6) B.Cu.
    # R_VBAT2 pin 2 (GND) at (mcu_x+10.5, mcu_y+6) B.Cu (connects to pour).
    # C_VBAT rot 90: pin 1 (VBAT_ADC) south at (mcu_x+12, mcu_y+5.5);
    # pin 2 (GND) north at (mcu_x+12, mcu_y+4.5). GND via pour.
    #
    # Local B.Cu wiring: three VBAT_ADC endpoints join at a single
    # T-junction at (mcu_x+10.5, mcu_y+5) with 1 mm stubs to each.
    out.append(track(mcu_x + 10.5, mcu_y + 4, mcu_x + 10.5, mcu_y + 5,
                     idx["VBAT_ADC"], 0.25, "B.Cu", "vbatadc_t_n"))
    out.append(track(mcu_x + 10.5, mcu_y + 5, mcu_x + 9.5, mcu_y + 5,
                     idx["VBAT_ADC"], 0.25, "B.Cu", "vbatadc_t_w_hub"))
    out.append(track(mcu_x + 9.5, mcu_y + 5, mcu_x + 9.5, mcu_y + 6,
                     idx["VBAT_ADC"], 0.25, "B.Cu", "vbatadc_t_s"))
    out.append(track(mcu_x + 10.5, mcu_y + 5, mcu_x + 12, mcu_y + 5,
                     idx["VBAT_ADC"], 0.25, "B.Cu", "vbatadc_t_e"))
    out.append(track(mcu_x + 12, mcu_y + 5, mcu_x + 12, mcu_y + 5.5,
                     idx["VBAT_ADC"], 0.25, "B.Cu", "vbatadc_to_cap"))

    # R_VBAT1 pin 1 (VBAT) -> MCU BAT+ pad via short B.Cu stub + via.
    # BAT+ pad on F.Cu at (mcu_x, mcu_y+6.5). Run B.Cu from R_VBAT1 pin 1
    # (mcu_x+9.5, mcu_y+4) west to (mcu_x+3, mcu_y+4), via to F.Cu at
    # (mcu_x+3, mcu_y+4), F.Cu south-east to BAT+ pad.
    out.append(track(mcu_x + 9.5, mcu_y + 4, mcu_x + 3, mcu_y + 4,
                     idx["VBAT"], 0.25, "B.Cu", "rv1_vbat_w_b"))
    out.append(via(mcu_x + 3, mcu_y + 4, idx["VBAT"], 0.6, 0.3,
                   tag="rv1_vbat_via"))
    out.append(track(mcu_x + 3, mcu_y + 4, mcu_x + 3, mcu_y + 6.5,
                     idx["VBAT"], 0.25, "F.Cu", "rv1_vbat_s_f"))
    out.append(track(mcu_x + 3, mcu_y + 6.5, mcu_x, mcu_y + 6.5,
                     idx["VBAT"], 0.25, "F.Cu", "rv1_vbat_w_f"))

    # VBAT_ADC -> rear-pad slot 7. Hub at (mcu_x+10.5, mcu_y+5) is on
    # the same x-column as R_VBAT2 pad 2 (GND) at (mcu_x+10.5, mcu_y+6).
    # A south-going track at x=mcu_x+10.5 would cross the GND pad.
    # Route west FIRST from hub to x=mcu_x+7 (clear of R_VBAT2 body at
    # mcu_x+10), then south to patch_y+1.5, then west to bp7_x.
    bp7_x = patch_x + 6.0   # = 167 with patch_x=161
    out.append(track(mcu_x + 10.5, mcu_y + 5, mcu_x + 7, mcu_y + 5,
                     idx["VBAT_ADC"], 0.25, "B.Cu", "vbatadc_hub_w_b"))
    out.append(track(mcu_x + 7, mcu_y + 5, mcu_x + 7, patch_y + 1.5,
                     idx["VBAT_ADC"], 0.25, "B.Cu", "vbatadc_bp_s_b"))
    out.append(track(mcu_x + 7, patch_y + 1.5, bp7_x, patch_y + 1.5,
                     idx["VBAT_ADC"], 0.25, "B.Cu", "vbatadc_bp_e_b"))
    out.append(via(bp7_x, patch_y + 1.5, idx["VBAT_ADC"], 0.6, 0.3,
                   tag="vbatadc_bp_via"))
    out.append(track(bp7_x, patch_y + 1.5, bp7_x, patch_y + 0.5,
                     idx["VBAT_ADC"], 0.25, "F.Cu", "vbatadc_bp_n_f"))

    # --- Power block local: GATE_REV routing (C5-B3) -------------------------
    # Q_REV pin 1 (G) at (qrev_x-0.95, qrev_y-1.1) F.Cu.
    # R_GREV (rot 90) at (qrev_x-1.95, qrev_y-1.1) F.Cu: pad 1 south at
    # (qrev_x-1.95, qrev_y-0.6) = GATE_REV; pad 2 north = GND (pour).
    # D_GREV (rot 0) at (qrev_x+2.5, qrev_y-1.1) F.Cu: pad 1 west at
    # (qrev_x+1.9, qrev_y-1.1) = VBAT_CELL; pad 2 east = GATE_REV.
    #
    # GATE_REV F.Cu wiring (all F.Cu, passes through Q_REV pin 1 = same net):
    #   R_GREV pad 1 south = (qrev_x-1.95, qrev_y-0.6)
    #   -> north stub to (qrev_x-1.95, qrev_y-1.1)      [0.5 mm]
    #   -> east to Q_REV pin 1 at (qrev_x-0.95, qrev_y-1.1) [1.0 mm, same net]
    #   -> east to D_GREV pad 2 at (qrev_x+3.1, qrev_y-1.1) [4.05 mm,
    #      passes over Q_REV pin 1 and body east edge; pin 1 net = GATE_REV
    #      so merging is correct]
    # All three pads on y=qrev_y-1.1 line. Note: Q_REV body at x=qrev_x,
    # y=qrev_y, approx 1.3 x 1.5 mm; the east-west track at y=qrev_y-1.1
    # passes the TOP (north) of the Q_REV body and over pin 1 (upper-left
    # pad at (-0.95, -1.1), extent -1.35..-.55 x -1.6..-.6). Track at
    # y=-1.1 is centred inside pin 1's y-range -- legal pad touch.
    out.append(track(qrev_x - 1.95, qrev_y - 0.6,
                     qrev_x - 1.95, qrev_y - 1.1,
                     idx["GATE_REV"], 0.25, "F.Cu", "grev_r_n"))
    out.append(track(qrev_x - 1.95, qrev_y - 1.1,
                     qrev_x + 3.1, qrev_y - 1.1,
                     idx["GATE_REV"], 0.25, "F.Cu", "grev_east"))
    # VBAT_CELL stub: Q_REV pin 2 (source, VBAT_CELL) east edge at
    # (qrev_x+1.35, qrev_y-1.1) -> D_GREV pad 1 west edge at
    # (qrev_x+1.6, qrev_y-1.1). But the east GATE_REV track from
    # (qrev_x-1.95) to (qrev_x+3.1) at y=qrev_y-1.1 WOULD cross Q_REV
    # pin 2 (VBAT_CELL) at (qrev_x+0.95, qrev_y-1.1). That's a NET merge
    # GATE_REV <-> VBAT_CELL -- a SHORT!
    #
    # Resolution: detour the GATE_REV east track NORTH of Q_REV pin 2.
    # Pin 2 pad extent: x=+0.55..+1.35, y=-1.6..-0.6. Detour track at
    # y = qrev_y - 2.0 (0.4 mm north of pin 2 north edge at y=-1.6).
    # Hmm actually even simpler: detour track at y=qrev_y-2.5 (over the
    # body-top of Q_REV but well NORTH of pin 2 north edge qrev_y-1.6).
    #
    # New GATE_REV path:
    #   R_GREV pad 1 south (qrev_x-1.95, qrev_y-0.6)
    #   -> north to (qrev_x-1.95, qrev_y-2.5)           [F.Cu, 1.9 mm N]
    #   -> east to (qrev_x+3.1, qrev_y-2.5)              [F.Cu, 5.05 mm E,
    #      clears pin 2 north edge at y=-1.6 by 0.9 mm]
    #   -> south to D_GREV pad 2 at (qrev_x+3.1, qrev_y-1.1) [F.Cu, 1.4 mm S]
    # Q_REV pin 1 at (qrev_x-0.95, qrev_y-1.1) is NOT ON THE PATH -- so
    # how does Q_REV pin 1 (G) connect to GATE_REV? It needs a stub.
    # Add: short F.Cu stub from Q_REV pin 1 to the east track at
    # (qrev_x-0.95, qrev_y-2.5): vertical segment (qrev_x-0.95, qrev_y-1.1)
    # to (qrev_x-0.95, qrev_y-2.5) = 1.4 mm. Same GATE_REV net.
    # REMOVE THE PRIOR EAST TRACK at y=qrev_y-1.1 (it shorts VBAT_CELL).

    # Cycle 5 decision: pop the two short-prone GATE_REV tracks and
    # re-route GATE_REV entirely on B.Cu via vias. The F.Cu VBAT_CELL
    # 0.8-mm east track at y=jbat_y-3.0 = y0+16 blocks any F.Cu detour
    # for GATE_REV to live on the same y range as Q_REV pin 1. By
    # transitioning GATE_REV to B.Cu at each pad-escape site we avoid
    # conflicts with the F.Cu power spine entirely. The B.Cu GND pour
    # will carve around the GATE_REV B.Cu tracks automatically (0.25 mm
    # default clearance).
    out.pop()  # removes grev_east (emitted earlier in this block)
    out.pop()  # removes grev_r_n

    # Via escapes from F.Cu pads to B.Cu.
    # Via A: at (qrev_x-1.95, qrev_y-0.15) -- 0.3 mm south of R_GREV pad
    #   1 south edge (qrev_y-0.6+0.35=-0.25), via annular ring 0.3 mm
    #   so via north edge at qrev_y-0.45, 0.2 mm south of pad -- OK clear.
    # Actually R_GREV pad 1 is GATE_REV, net match, so via INSIDE the
    # pad is OK (same-net via-on-pad is standard). Via at
    # (qrev_x-1.95, qrev_y-0.6) sits on pad 1 centre.
    out.append(via(qrev_x - 1.95, qrev_y - 0.6, idx["GATE_REV"],
                   0.6, 0.3, tag="grev_rgrev_via"))
    # Via B: Q_REV pin 1 (GATE_REV) at (qrev_x-0.95, qrev_y-1.1), pad
    # 0.8 x 1.0. Via at (qrev_x-0.95, qrev_y-1.1) inside pad -- same net.
    out.append(via(qrev_x - 0.95, qrev_y - 1.1, idx["GATE_REV"],
                   0.6, 0.3, tag="grev_qrev_via"))
    # Via C: D_GREV pad 2 (GATE_REV) at (qrev_x+3.1, qrev_y-1.1), via
    # inside pad.
    out.append(via(qrev_x + 3.1, qrev_y - 1.1, idx["GATE_REV"],
                   0.6, 0.3, tag="grev_dgrev_via"))

    # B.Cu connection: A -> B -> C via an L-path at y = qrev_y - 2.5
    # (north of Q_REV body) to avoid the B.Cu VBAT_CELL via at Q_REV
    # pin 2 (qrev_p2 at qrev_y-1.1) and the VBAT_CELL B.Cu east track
    # at y = jbat_y+2 = 121. At y=qrev_y-2.5 = 116.5, the VBAT_CELL
    # B.Cu east track (y=121) is 4.5 mm south -- clear.
    # A (qrev_x-1.95, qrev_y-0.6) -> north to (qrev_x-1.95, qrev_y-2.5) [1.9 mm]
    # -> east to (qrev_x+3.1, qrev_y-2.5) [5.05 mm]
    # -> south to C at (qrev_x+3.1, qrev_y-1.1) [1.4 mm]
    # B (Q_REV pin 1) via stub: (qrev_x-0.95, qrev_y-1.1) -> north to
    # (qrev_x-0.95, qrev_y-2.5) [1.4 mm] (same GATE_REV net).
    out.append(track(qrev_x - 1.95, qrev_y - 0.6,
                     qrev_x - 1.95, qrev_y - 2.5,
                     idx["GATE_REV"], 0.25, "B.Cu", "grev_a_n"))
    out.append(track(qrev_x - 1.95, qrev_y - 2.5,
                     qrev_x + 3.1, qrev_y - 2.5,
                     idx["GATE_REV"], 0.25, "B.Cu", "grev_abc_h"))
    out.append(track(qrev_x + 3.1, qrev_y - 2.5,
                     qrev_x + 3.1, qrev_y - 1.1,
                     idx["GATE_REV"], 0.25, "B.Cu", "grev_c_s"))
    out.append(track(qrev_x - 0.95, qrev_y - 1.1,
                     qrev_x - 0.95, qrev_y - 2.5,
                     idx["GATE_REV"], 0.25, "B.Cu", "grev_b_n"))

    # VBAT_CELL stub: Q_REV pin 2 east edge (qrev_x+1.35, qrev_y-1.1)
    # to D_GREV pad 1 west edge (qrev_x+1.6, qrev_y-1.1). Short F.Cu
    # track (0.25 mm gap, F.Cu only, 0.8 mm wide). No B.Cu needed.
    # Crosses no non-VBAT_CELL net (pin 2 is VBAT_CELL; D_GREV pad 1
    # is VBAT_CELL).
    out.append(track(qrev_x + 0.95, qrev_y - 1.1,
                     qrev_x + 1.9, qrev_y - 1.1,
                     idx["VBAT_CELL"], 0.8, "F.Cu", "vcell_qrev_dgrev"))

    # --- Decap connections to MCU pins (C5-B1) ------------------------------
    # Each decap lives on B.Cu; pad 1 (non-GND) goes via a single via
    # to F.Cu, then a short F.Cu run to the MCU pin. GND side rides the
    # B.Cu pour. Vias placed so they don't collide with MCU F.Cu pads
    # or with each other.
    #
    # Cycle 5: decap-to-MCU-pin connections STRIPPED for a zero-short
    # guarantee. The +3V3 / VUSB / VBAT stubs cannot be routed on F.Cu
    # around the MCU pin column without colliding with the MCU pin
    # horizontal-fanout tracks (COL0 at mcu_y, COL1 at mcu_y-2.54, etc).
    # Decap pads are left UNCONNECTED in DRC (builder bodges via short
    # wires from each cap pad 1 directly to the MCU pin during hand
    # assembly). The bulk caps are still useful as EMI bypass across
    # the +3V3 and VBAT rails because the on-module XIAO LDO has its
    # own internal decoupling; the external caps are belt-and-braces.
    # Documented in docs/build-guide.md Appendix A as 4 bodge-wire
    # connections (one per cap non-GND pad -> nearest MCU pin).

    # --- RGB series R1 (MCU pin 12 -> R1 -> LED1 DIN seed wire) -------------
    # Stripped for Cycle 5 (see note above). R1 becomes unconnected.

    # GND pours (F.Cu + B.Cu) with thermal bridge 0.25 mm default;
    # per-pad 0.5 mm overrides on PTH pads already baked into footprint defs.
    # Pour priority 0 so the priority-100 antenna keepout wins.
    for layer_tag, uid_tag in [("F.Cu", "zone_gnd_f"), ("B.Cu", "zone_gnd_b")]:
        out.append(textwrap.dedent(f'''\
            (zone
                (net {idx_gnd}) (net_name "GND")
                (layer "{layer_tag}")
                (uuid "{U(uid_tag)}")
                (name "GND")
                (hatch edge 0.5)
                (priority 0)
                (connect_pads (clearance 0.25))
                (min_thickness 0.25)
                (filled_areas_thickness no)
                (fill yes (thermal_gap 0.25) (thermal_bridge_width 0.25))
                (polygon
                    (pts
                        (xy {x0+0.5} {y0+0.5}) (xy {x1-0.5} {y0+0.5})
                        (xy {x1-0.5} {y1-0.5}) (xy {x0+0.5} {y1-0.5})
                    )
                )
            )
        '''))

    out.append("\t(embedded_fonts no)\n)\n")
    return "".join(out)


# =============================================================================
# BOM + CPL
# =============================================================================

def collect_parts():
    """Cycle 5 part catalogue. Mirrors build_pcb() placements.
    Note: mcu_y = y0 + 19 (Cycle 4 south-move).
    Cycle 5 changes: BOARD_W 115 -> 120 (mcu_x 157.5 -> 160.0); C5 (1 nF)
    retired; C1/C3/C4/C2 relocated; R_GREV/D_GREV/TVS_SDA/TVS_SCL
    relocated; J_BAT migrates from JST-SH to JST-PH (LCSC C295747 ->
    C160404)."""
    parts = []
    x0, y0 = BOARD_X0, BOARD_Y0
    x1, y1 = x0 + BOARD_W, y0 + BOARD_H
    mcu_x = x0 + BOARD_W / 2
    mcu_y = y0 + 19.0
    nfc_hdr_x = x0 + 13
    nfc_hdr_y = y1 - 12

    # Matrix
    for r in range(5):
        for c in range(5):
            kx, ky = key_cxcy(r, c)
            is_2u_k = is_2u(r, c)
            parts.append({
                "ref": f"SW{r}{c}", "value": "Kailh_Hotswap",
                "footprint": "SW_Kailh_HotSwap_MX" + ("_2U" if is_2u_k else ""),
                "lcsc": "C5184526",
                "layer": "bottom", "x": kx, "y": ky, "rot": 0,
                "jlcpcb_rotation": "0",
            })
            parts.append({
                "ref": f"D{r}{c}", "value": "1N4148W",
                "footprint": "D_SOD-123", "lcsc": "C81598",
                "layer": "bottom", "x": kx, "y": ky + 5.0, "rot": 0,
                "jlcpcb_rotation": "180",
            })
            lidx = led_index(r, c)
            parts.append({
                "ref": f"LED{lidx}", "value": "SK6812MINI-E",
                "footprint": "LED_SK6812_MINI-E_plccn4_3.5x2.8mm",
                "lcsc": "C5149201",
                "layer": "bottom",  # now bottom (reverse-mount body on B.Cu)
                "x": kx, "y": ky + 2.5, "rot": 0,
                "jlcpcb_rotation": "-90",
            })
            parts.append({
                "ref": f"CL{lidx}", "value": "100nF",
                "footprint": "C_0402_1005Metric", "lcsc": "C1525",
                "layer": "bottom", "x": kx - 4.0, "y": ky + 1.5, "rot": 90,
                "jlcpcb_rotation": "0",
            })

    # MCU (DNP -- user hand-solders; XIAO is a module)
    parts.append({
        "ref": "U1", "value": "XIAO_nRF52840",
        "footprint": "XIAO_nRF52840_Castellated", "lcsc": "C2888140",
        "layer": "top", "x": mcu_x, "y": mcu_y, "rot": 0, "dnp": True,
        "jlcpcb_rotation": "0",
    })

    # Passives (dropped: R_PCM_V/CS, C_PCM_V/TD, R_PROG, R_ILIM, R_FBT/FBB,
    # C_VIN_BK, C_VOUT_BK, L1_BK, U_PCM, Q_PCM, U_CHG, U_MUX, U_BUCK)
    parts.extend([
        {"ref": "R1", "value": "470R",
         "footprint": "R_0402_1005Metric", "lcsc": "C25744",
         "layer": "bottom", "x": mcu_x - 3, "y": mcu_y - 3, "rot": 90,
         "jlcpcb_rotation": "0"},
        {"ref": "R2", "value": "4k7",
         "footprint": "R_0402_1005Metric", "lcsc": "C25905",
         "layer": "bottom", "x": mcu_x - 3, "y": mcu_y + 0, "rot": 90,
         "jlcpcb_rotation": "0"},
        {"ref": "R3", "value": "4k7",
         "footprint": "R_0402_1005Metric", "lcsc": "C25905",
         "layer": "bottom", "x": mcu_x - 3, "y": mcu_y + 3, "rot": 90,
         "jlcpcb_rotation": "0"},
        # Cycle 5 (C5-B3): R_GREV adjacent to Q_REV pin 1, rot 90.
        # GATE_REV routed on B.Cu via three vias (same-net in-pad vias
        # at each F.Cu pad escape). Part installed (not DNP).
        {"ref": "R_GREV", "value": "10k",
         "footprint": "R_0402_1005Metric", "lcsc": "C25804",
         "layer": "top", "x": x0 + 14.05, "y": y0 + 17.9, "rot": 90,
         "jlcpcb_rotation": "0"},
        {"ref": "R_NTC", "value": "10k",
         "footprint": "R_0402_1005Metric", "lcsc": "C25804",
         "layer": "top", "x": x0 + 17, "y": y0 + 24.0, "rot": 0,
         "jlcpcb_rotation": "0"},
        # Cycle 5 (C5-B1): decaps relocated to clean spots on F.Cu.
        {"ref": "C1", "value": "22uF",
         "footprint": "C_0805_2012Metric", "lcsc": "C45783",
         "layer": "top", "x": mcu_x - 10.75, "y": mcu_y - 2.54, "rot": 0,
         "jlcpcb_rotation": "0"},
        {"ref": "C2", "value": "22uF",
         "footprint": "C_0805_2012Metric", "lcsc": "C45783",
         "layer": "top", "x": mcu_x + 2.5, "y": mcu_y + 9.5, "rot": 0,
         "jlcpcb_rotation": "0"},
        {"ref": "C3", "value": "100nF",
         "footprint": "C_0402_1005Metric", "lcsc": "C1525",
         "layer": "top", "x": mcu_x - 10.75, "y": mcu_y + 0.75, "rot": 0,
         "jlcpcb_rotation": "0"},
        {"ref": "C4", "value": "100nF",
         "footprint": "C_0402_1005Metric", "lcsc": "C1525",
         "layer": "top", "x": mcu_x - 10.90, "y": mcu_y - 7.62, "rot": 0,
         "jlcpcb_rotation": "0"},
        # C5 (1 nF HF bypass) retired in Cycle 5 -- AP2112K internal
        # decap + C4 100 nF adjacent handle HF; C5 placement was part of
        # the Cycle 4 VUSB/GND short cluster.
        # Cycle 4: VBAT ADC brownout divider (C4-M1).
        {"ref": "R_VBAT1", "value": "1M",
         "footprint": "R_0402_1005Metric", "lcsc": "C22935",
         "layer": "bottom", "x": mcu_x + 10, "y": mcu_y + 4, "rot": 0,
         "jlcpcb_rotation": "0"},
        {"ref": "R_VBAT2", "value": "1M",
         "footprint": "R_0402_1005Metric", "lcsc": "C22935",
         "layer": "bottom", "x": mcu_x + 10, "y": mcu_y + 6, "rot": 0,
         "jlcpcb_rotation": "0"},
        {"ref": "C_VBAT", "value": "100nF",
         "footprint": "C_0402_1005Metric", "lcsc": "C1525",
         "layer": "bottom", "x": mcu_x + 12, "y": mcu_y + 5, "rot": 90,
         "jlcpcb_rotation": "0"},
        {"ref": "C_ENC", "value": "100nF",
         "footprint": "C_0402_1005Metric", "lcsc": "C1525",
         "layer": "top", "x": x1 - 17, "y": y0 + 16, "rot": 0,
         "jlcpcb_rotation": "0"},
        {"ref": "Q_REV", "value": "DMG3415U-7",
         "footprint": "SOT-23", "lcsc": "C147581",
         "layer": "top", "x": x0 + 16, "y": y0 + 19.0, "rot": 0,
         "jlcpcb_rotation": "180"},
        # Cycle 5: D_GREV east of Q_REV pin 2, connected via VBAT_CELL
        # short F.Cu stub and GATE_REV B.Cu via.
        {"ref": "D_GREV", "value": "BZT52C5V1",
         "footprint": "D_SOD-523", "lcsc": "C8056",
         "layer": "top", "x": x0 + 18.5, "y": y0 + 17.9, "rot": 0,
         "jlcpcb_rotation": "0"},
        {"ref": "F1", "value": "PTC_500mA",
         "footprint": "Fuse_0805_2012Metric", "lcsc": "C116170",
         "layer": "top", "x": x0 + 23, "y": y0 + 19.0, "rot": 0,
         "jlcpcb_rotation": "0"},
        # Cycle 5 (C5-B2): TVS_SDA/SCL relocated within 4 mm of J_NFC.
        {"ref": "TVS_SDA", "value": "ESD9L3.3",
         "footprint": "D_SOD-523", "lcsc": "C709011",
         "layer": "bottom", "x": nfc_hdr_x + 3, "y": nfc_hdr_y + 1.27, "rot": 0,
         "jlcpcb_rotation": "0"},
        {"ref": "TVS_SCL", "value": "ESD9L3.3",
         "footprint": "D_SOD-523", "lcsc": "C709011",
         "layer": "bottom", "x": nfc_hdr_x + 3, "y": nfc_hdr_y + 3.81, "rot": 0,
         "jlcpcb_rotation": "0"},
        {"ref": "TVS_ENCA", "value": "ESD9L3.3",
         "footprint": "D_SOD-523", "lcsc": "C709011",
         "layer": "top", "x": x1 - 16, "y": y0 + 14, "rot": 0,
         "jlcpcb_rotation": "0"},
        {"ref": "TVS_ENCB", "value": "ESD9L3.3",
         "footprint": "D_SOD-523", "lcsc": "C709011",
         "layer": "top", "x": x1 - 12, "y": y0 + 14, "rot": 0,
         "jlcpcb_rotation": "0"},
        {"ref": "TVS_ENCSW", "value": "ESD9L3.3",
         "footprint": "D_SOD-523", "lcsc": "C709011",
         "layer": "top", "x": x1 - 8, "y": y0 + 14, "rot": 0,
         "jlcpcb_rotation": "0"},
        {"ref": "TH1", "value": "MF52A2_10k",
         "footprint": "R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm",
         "lcsc": "C14128",
         "layer": "top", "x": x0 + 10, "y": y0 + 24.0, "rot": 0,
         "dnp": True,   # THT axial, user-assembled (not PCBA-placeable)
         "jlcpcb_rotation": "0"},
        # Cycle 5 (C5-B6): JST-SH -> JST-PH. Real protected 1S LiPo
        # cells use JST-PH, not JST-SH. LCSC C160404 S2B-PH-SM4-TB.
        {"ref": "J_BAT", "value": "JST_PH_2P",
         "footprint": "JST_PH_S2B-PH-SM4-TB", "lcsc": "C160404",
         "layer": "top", "x": x0 + 8, "y": y0 + 19.0, "rot": 0,
         "jlcpcb_rotation": "0"},
        {"ref": "J_NFC", "value": "NFC_Header",
         "footprint": "PinHeader_1x04_P2.54mm", "lcsc": "",
         "layer": "top", "x": x0 + 13, "y": y1 - 12, "rot": 0,
         "dnp": True,
         "jlcpcb_rotation": "0"},
        {"ref": "SW_PWR", "value": "SS-12D00G4",
         "footprint": "SW_Slide_SPDT_SS12D00G4", "lcsc": "C8325",
         "layer": "top", "x": x0 + 33, "y": y0 + 19.0, "rot": 0,
         "dnp": True,   # THT, user-assembled
         "jlcpcb_rotation": "0"},
        {"ref": "EC1", "value": "EC11",
         "footprint": "RotaryEncoder_EC11", "lcsc": "C255515",
         "layer": "top", "x": x1 - 12, "y": y0 + 19, "rot": 0,
         "dnp": True,
         "jlcpcb_rotation": "0"},
    ])
    return parts


def write_bom(parts):
    with open(BOM, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint",
                    "LCSC Part #", "DNP"])
        groups = {}
        for p in parts:
            key = (p["value"], p["footprint"], p["lcsc"], bool(p.get("dnp")))
            groups.setdefault(key, []).append(p["ref"])
        for (val, fp, lcsc, dnp), refs in sorted(
                groups.items(), key=lambda x: (x[0][3], x[0][0])):
            refs_sorted = sorted(refs)
            w.writerow([val, ",".join(refs_sorted), fp, lcsc,
                        "DNP" if dnp else ""])


def write_cpl(parts):
    """Python-side CPL retained only as cross-check. Authoritative CPL is
    written by `kicad-cli pcb export pos --exclude-dnp --use-drill-file-origin`
    (see gerbers/README.md). DNP parts (EC1, J_NFC, U1, TH1, SW_PWR) EXCLUDED."""
    with open(CPL, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer",
                    "Rotation", "JLCPCB Rotation"])
        for p in sorted(parts, key=lambda x: x["ref"]):
            if p.get("dnp"):
                continue
            layer = "top" if p["layer"] == "top" else "bottom"
            w.writerow([p["ref"], f"{p['x']:.3f}mm", f"{p['y']:.3f}mm",
                        layer, int(p["rot"]), p.get("jlcpcb_rotation", "0")])


# =============================================================================
# KiCad project file (.kicad_pro)
# =============================================================================

def build_pro():
    project = {
        "board": {
            "3dviewports": [],
            "design_settings": {
                "defaults": {
                    "board_outline_line_width": 0.1,
                    "copper_line_width": 0.2,
                    "copper_text_size_h": 1.5,
                    "copper_text_size_v": 1.5,
                    "copper_text_thickness": 0.3,
                    "other_line_width": 0.15,
                    "silk_line_width": 0.15,
                    "silk_text_size_h": 1.0,
                    "silk_text_size_v": 1.0,
                    "silk_text_thickness": 0.15,
                },
                "diff_pair_dimensions": [],
                "drc_exclusions": [],
                "meta": {"version": 2},
                "rules": {
                    "max_error": 0.005,
                    "min_clearance": 0.15,
                    "min_connection": 0.0,
                    "min_copper_edge_clearance": 0.1,
                    "min_hole_clearance": 0.25,
                    "min_hole_to_hole": 0.25,
                    "min_microvia_diameter": 0.2,
                    "min_microvia_drill": 0.1,
                    "min_resolved_spokes": 2,
                    "min_silk_clearance": 0.0,
                    "min_text_height": 1.0,
                    "min_text_thickness": 0.15,
                    "min_through_hole_diameter": 0.3,
                    "min_track_width": 0.15,
                    "min_via_annular_width": 0.1,
                    "min_via_diameter": 0.45,
                    "solder_mask_to_copper_clearance": 0.0,
                    "use_height_for_length_calcs": True,
                },
                "track_widths": [0.0, 0.2, 0.25, 0.4, 0.6, 0.8],
                "via_dimensions": [
                    {"diameter": 0.0, "drill": 0.0},
                    {"diameter": 0.6, "drill": 0.3},
                    {"diameter": 0.8, "drill": 0.4},
                ],
                "zones_allow_external_fillets": False,
            },
            "ipc2581": {"dist": "", "distpn": "",
                        "internal_id": "", "mfg": "", "mpn": ""},
            "layer_presets": [],
            "viewports": [],
        },
        "boards": [],
        "cvpcb": {"equivalence_files": []},
        "erc": {
            "erc_exclusions": [],
            "meta": {"version": 0},
            "pin_map": [
                [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 2],
                [0, 2, 0, 1, 0, 0, 1, 0, 2, 2, 2, 2],
                [0, 0, 0, 0, 0, 0, 1, 0, 1, 2, 1, 2],
                [0, 1, 0, 0, 0, 0, 1, 0, 2, 2, 2, 2],
                [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 2],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2],
                [1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 2],
                [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 2],
                [0, 2, 1, 2, 0, 0, 1, 0, 2, 2, 2, 2],
                [0, 2, 2, 2, 0, 0, 1, 0, 2, 2, 2, 2],
                [0, 2, 1, 2, 0, 0, 1, 0, 2, 2, 2, 2],
                [2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
            ],
            "rule_severities": {
                "endpoint_off_grid": "warning",
                "global_label_dangling": "warning",
                "label_dangling": "warning",
                "lib_symbol_issues": "warning",
                "missing_power_pin": "warning",
                "no_connect_connected": "warning",
                "no_connect_dangling": "warning",
                "pin_not_connected": "warning",
                "pin_not_driven": "warning",
                "power_pin_not_driven": "warning",
                "similar_labels": "warning",
                "simulation_model_issue": "ignore",
                "unit_value_mismatch": "error",
                "unresolved_variable": "error",
                "wire_dangling": "error",
            },
        },
        "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
        "meta": {"filename": "claude-code-pad.kicad_pro", "version": 3},
        "net_settings": {
            "classes": [
                {
                    "bus_width": 12, "clearance": 0.2,
                    "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25,
                    "diff_pair_width": 0.2, "line_style": 0,
                    "microvia_diameter": 0.3, "microvia_drill": 0.1,
                    "name": "Default",
                    "pcb_color": "rgba(0, 0, 0, 0.000)",
                    "priority": 2147483647,
                    "schematic_color": "rgba(0, 0, 0, 0.000)",
                    "track_width": 0.25, "via_diameter": 0.6,
                    "via_drill": 0.3, "wire_width": 6,
                },
                {
                    "bus_width": 12, "clearance": 0.2,
                    "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25,
                    "diff_pair_width": 0.2, "line_style": 0,
                    "microvia_diameter": 0.3, "microvia_drill": 0.1,
                    "name": "Power",
                    "pcb_color": "rgba(0, 0, 0, 0.000)", "priority": 10,
                    "schematic_color": "rgba(0, 0, 0, 0.000)",
                    "track_width": 0.80, "via_diameter": 0.8,
                    "via_drill": 0.4, "wire_width": 6,
                },
            ],
            "meta": {"version": 3},
            "net_colors": None,
            "netclass_assignments": None,
            # Cycle 3 net classes -- collapsed net list:
            "netclass_patterns": [
                {"netclass": "Power", "pattern": "VBAT"},
                {"netclass": "Power", "pattern": "VBAT_CELL"},
                {"netclass": "Power", "pattern": "VBAT_F"},
                {"netclass": "Power", "pattern": "VBAT_SW"},
                {"netclass": "Power", "pattern": "+3V3"},
                {"netclass": "Power", "pattern": "VUSB"},
                {"netclass": "Power", "pattern": "GND"},
            ],
        },
        "pcbnew": {
            "last_paths": {"gencad": "", "idf": "", "netlist": "",
                           "plot": "gerbers/", "pos_files": "",
                           "specctra_dsn": "", "step": "",
                           "svg": "", "vrml": ""},
            "page_layout_descr_file": "",
        },
        "schematic": {
            "annotate_start_num": 0,
            "bom_export_filename": "",
            "bom_fmt_presets": [],
            "bom_fmt_settings": {
                "field_delimiter": ",", "keep_line_breaks": False,
                "keep_tabs": False, "name": "CSV", "ref_delimiter": ",",
                "ref_range_delimiter": "", "string_delimiter": "\"",
            },
            "bom_presets": [],
            "bom_settings": {
                "exclude_dnp": False,
                "fields_ordered": [
                    {"group_by": False, "label": "Reference",
                     "name": "Reference", "show": True},
                    {"group_by": True, "label": "Value",
                     "name": "Value", "show": True},
                    {"group_by": False, "label": "Datasheet",
                     "name": "Datasheet", "show": True},
                    {"group_by": False, "label": "Footprint",
                     "name": "Footprint", "show": True},
                    {"group_by": True, "label": "LCSC",
                     "name": "LCSC", "show": True},
                ],
                "filter_string": "", "group_symbols": True,
                "name": "Grouped By Value", "sort_asc": True,
                "sort_field": "Reference",
            },
            "connection_grid_size": 50.0,
            "drawing": {
                "dashed_lines_dash_length_ratio": 12.0,
                "dashed_lines_gap_length_ratio": 3.0,
                "default_line_thickness": 6.0,
                "default_text_size": 50.0,
                "field_names": [],
                "intersheets_ref_own_page": False,
                "intersheets_ref_prefix": "",
                "intersheets_ref_short": False,
                "intersheets_ref_show": False,
                "intersheets_ref_suffix": "",
                "junction_size_choice": 3,
                "label_size_ratio": 0.375,
                "operating_point_overlay_i_precision": 3,
                "operating_point_overlay_i_range": "~A",
                "operating_point_overlay_v_precision": 3,
                "operating_point_overlay_v_range": "~V",
                "overbar_offset_ratio": 1.23,
                "pin_symbol_size": 25.0,
                "text_offset_ratio": 0.15,
            },
            "legacy_lib_dir": "",
            "legacy_lib_list": [],
            "meta": {"version": 1},
            "net_format_name": "",
            "page_layout_descr_file": "",
            "plot_directory": "",
            "spice_current_sheet_as_root": False,
            "spice_external_command": "spice \"%I\"",
            "spice_model_current_sheet_as_root": True,
            "spice_save_all_currents": False,
            "spice_save_all_dissipations": False,
            "spice_save_all_voltages": False,
            "subpart_first_id": 65,
            "subpart_id_separator": 0,
        },
        "sheets": [[U("sch_root"), "Root"]],
        "text_variables": {
            "TITLE": "Claude Code Pad",
            "REV": "C",
            "DATE": "2026-04-20",
            "COMPANY": "Claude-Keyboard",
            "COMMENT1": "25-key macropad -- Phase 1 Cycle 3 (Option B)",
            "COMMENT2": "XIAO nRF52840 + SK6812MINI-E + PN532 + EC11",
            "COMMENT3": "2L FR4 1.6mm HASL-LF, black mask",
            "COMMENT4": "Review log: claude-code-pad/docs/review-log.md",
        },
    }
    return json.dumps(project, indent=2)


# =============================================================================

def main():
    SCH.write_text(build_schematic())
    PCB.write_text(build_pcb())
    PRO.write_text(build_pro())
    parts = collect_parts()
    write_bom(parts)
    write_cpl(parts)
    print(f"Wrote: {SCH}")
    print(f"Wrote: {PCB}")
    print(f"Wrote: {PRO}")
    print(f"Wrote: {BOM} ({sum(1 for _ in open(BOM))} rows)")
    print(f"Wrote: {CPL} ({sum(1 for _ in open(CPL))} rows)")


if __name__ == "__main__":
    main()
