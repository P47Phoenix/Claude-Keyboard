# Claude Keyboard

A 25-key macropad companion for Claude Code terminal sessions — the **Claude Code Pad**. Dedicated hardware for firing CLI shortcuts (accept, reject, allow, arrow keys, commit/PR macros, plan/model cycle) with per-key RGB, a rotary encoder, a 2U stabilized Enter, and RFID artisan keycap support.

Wireless multi-host via BLE on a Seeed XIAO nRF52840; firmware runs [ZMK](https://zmk.dev).

## Status

| Phase | Scope | State |
|---|---|---|
| 1 | PCB design (schematic, layout, routing, gerbers, BOM, CPL) | **Closed** (7 review cycles, 29 BLOCKERs resolved); post-closure GUI-DRC cleanup Cycle 8 in progress |
| 2 | 3D-printed case + bottom plate (CadQuery, PETG) | Not started |
| 3 | Firmware (ZMK on nRF52840) | Not started; hard requirements captured in `claude-code-pad/firmware/zmk/README.md` |
| 4 | TinyML callouts | **Retired** — dropped with OLED in Cycle 1 arbitration |
| 5 | RFID figurine keycap base | Not started |
| 6 | Integration review | Not started |

## Hardware highlights

- **MCU:** Seeed XIAO nRF52840 (direct-solder castellations). BLE 5.x multi-host. Retired the initial XIAO ESP32-S3 + TinyML/OLED path in favour of a simpler, better-supported stack.
- **Keyswitches:** 24× 1U + 1× 2U Enter, Kailh MX hot-swap (Keebio `MX_Only_HS`), 19.05 mm pitch, Cherry plate-mount 2U stabilizer (slotted housing holes per community canonical footprint).
- **RGB:** 25× SK6812MINI-E reverse-mount, one per key, serpentine chain. Firmware-capped at 300 mA peak per IEC 62368-1 Annex Q.
- **Encoder:** EC11 with metal shaft grounded through plated mounting lugs; ESD TVS on all three encoder signals.
- **NFC:** PN532 header for RFID artisan figurine personality switching (Phase 5).
- **Power:** 1S LiPo via JST-PH with **mandatory cell-level protection PCB** (approved cells from Adafruit/SparkFun — see `docs/build-guide.md`). On-board DMG3415U-7 P-FET reverse-polarity, 500 mA PTC, SPDT slide switch. Charging via the XIAO's USB-C + on-module charger.
- **Safety:** NTC cell-temperature monitor, 5× ESD9L3.3 TVS on exposed I²C + encoder, firmware LED cap + VBAT undervoltage cutoff (3.70 V LEDs-on / 3.50 V LEDs-off).
- **Board:** 120 × 132 mm, 2-layer FR4, HASL lead-free, black soldermask. Freerouting-autorouted (1095 segments, 148 GND stitching vias, antenna keepout inviolate).

## Repository layout

```
claude-code-pad/
├── pcb/                           # Phase 1 deliverables
│   ├── claude-code-pad.kicad_pro|sch|pcb
│   ├── gerbers/                   # 10 layers + drill + job file (fab-ready)
│   ├── bom.csv / cpl.csv          # JLCPCB format
│   ├── DESIGN-NOTES.md            # design rationale + cycle history + pinout verification
│   └── _gen/                      # generator + autoroute pipeline
│       ├── generate.py            # schematic + placement source of truth
│       └── autoroute/             # export_dsn + freerouting + import_ses + widen_power + stitch_gnd
├── firmware/
│   ├── zmk/                       # Phase 3 primary (nRF52840 + ZMK)
│   │   └── README.md              # Hard Requirements for FW-1
│   └── qmk/                       # alternate path (RP2040)
├── case/                          # Phase 2 (MECH-1, CadQuery)
├── figurines/                     # Phase 5 (RFID artisan keycap)
└── docs/
    ├── build-guide.md             # MANDATORY battery requirements + assembly
    └── review-log.md              # Adversarial review paper trail
```

## Orchestration

Design work is done by **persona sub-agents** dispatched via Claude's Agent tool, not by the main thread:

- **Designers** (ECE-1 for PCB, MECH-1 for case, FW-1 for firmware) produce deliverables.
- **Adversarial reviewers** (RED-DFM, RED-SAFETY, RED-COST, RED-MECH, RED-FW) critique in parallel.
- Primary designer iterates until BLOCKER/MAJOR findings clear.
- Every cycle is logged in `claude-code-pad/docs/review-log.md`.

Full orchestration spec: `/var/home/meconnelly/Downloads/claude-code-pad-orchestrated-prompt.md` (authoritative for personas, phases, and reviewers).

## Tooling

This repo targets a **Bazzite** (immutable Fedora atomic) workstation. Package management notes and KiCad / Freerouting / Distrobox conventions are in [`CLAUDE.md`](./CLAUDE.md).

- **KiCad 10.0.1** as a Flatpak (`org.kicad.KiCad`) for GUI + authoritative file reads.
- **KiCad 9.0.8** in a `kicad` distrobox (Podman-backed Fedora 43 toolbox) for kicad-cli automation + the KiCad MCP server (`lamaalrajih/kicad-mcp`, auto-loaded via `.mcp.json`).
- **Freerouting 2.1.0** (Java 21) in the same distrobox for headless autorouting.
- **CadQuery / OpenSCAD** (Phase 2) — user-space Python, no Bazzite layering needed.

### Quick commands

```bash
# DRC via kicad-cli (flatpak, matches GUI rule set)
flatpak run --command=kicad-cli org.kicad.KiCad pcb drc \
  --output /tmp/drc.rpt pcb/claude-code-pad.kicad_pcb

# Open the PCB in the GUI
flatpak run --command=pcbnew org.kicad.KiCad pcb/claude-code-pad.kicad_pcb

# Re-run Freerouting (from distrobox)
distrobox enter kicad -- python3 pcb/_gen/autoroute/export_dsn.py pcb/claude-code-pad.kicad_pcb
distrobox enter kicad -- java -jar ~/.local/share/freerouting/freerouting.jar \
  -de /tmp/claude-code-pad.dsn -do /tmp/claude-code-pad.ses
distrobox enter kicad -- python3 pcb/_gen/autoroute/import_ses.py pcb/claude-code-pad.kicad_pcb
```

## Getting involved

If you want to build one:

1. Read [`claude-code-pad/docs/build-guide.md`](claude-code-pad/docs/build-guide.md) first — especially the **mandatory battery requirements** section.
2. Order the PCB from JLCPCB using `claude-code-pad/pcb/gerbers/` and `claude-code-pad/pcb/cpl.csv`.
3. Source the cells from the approved vendor list in the build guide. **Do not substitute a raw LiPo** — the board relies on cell-level protection PCM.
4. Wait for Phase 2 (case STL) and Phase 3 (ZMK firmware) before assembling a complete unit.

## License

TBD.
