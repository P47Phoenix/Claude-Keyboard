# Gerbers - Claude Code Pad

JLCPCB-ready gerber + drill + CPL set produced by `kicad-cli` 9.0.8 from
`../claude-code-pad.kicad_pcb`.

## Files

| File                                   | Purpose                         |
|----------------------------------------|---------------------------------|
| `claude-code-pad-F_Cu.gtl`             | Top copper                      |
| `claude-code-pad-B_Cu.gbl`             | Bottom copper                   |
| `claude-code-pad-F_Paste.gtp`          | Top paste stencil               |
| `claude-code-pad-B_Paste.gbp`          | Bottom paste stencil            |
| `claude-code-pad-F_Mask.gts`           | Top solder mask                 |
| `claude-code-pad-B_Mask.gbs`           | Bottom solder mask              |
| `claude-code-pad-F_Silkscreen.gto`     | Top silkscreen                  |
| `claude-code-pad-B_Silkscreen.gbo`     | Bottom silkscreen               |
| `claude-code-pad-Edge_Cuts.gm1`        | Board outline + LED apertures   |
| `claude-code-pad.drl`                  | Excellon drill (PTH + NPTH)     |
| `claude-code-pad-job.gbrjob`           | Gerber X2 job file              |

## How to regenerate

Cycle 3: the CPL command now uses `--exclude-dnp` so that EC1, J_NFC, U1,
TH1 and SW_PWR (marked DNP in the BOM) are not listed in the fab CPL.
This closes B-CPL-DNP.

```bash
# Gerbers
distrobox enter kicad -- kicad-cli pcb export gerbers \
  --output /var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/pcb/gerbers/ \
  --layers "F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts" \
  --use-drill-file-origin \
  /var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/pcb/claude-code-pad.kicad_pcb

# Drill
distrobox enter kicad -- kicad-cli pcb export drill \
  --output /var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/pcb/gerbers/ \
  --format excellon --drill-origin plot \
  --excellon-units mm --excellon-zeros-format decimal \
  /var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/pcb/claude-code-pad.kicad_pcb

# Position file (CPL) -- Cycle 3: --exclude-dnp flag added.
distrobox enter kicad -- kicad-cli pcb export pos \
  --output /var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/pcb/cpl.csv \
  --format csv --units mm --side both \
  --use-drill-file-origin \
  --exclude-dnp \
  /var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/pcb/claude-code-pad.kicad_pcb

# Verify DNP exclusion:
grep -cE '^"(EC1|J_NFC|U1|TH1|SW_PWR)"' \
  /var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/pcb/cpl.csv
# Expected output: 0
```

## JLCPCB order settings

- Material: FR4
- Layers: 2
- Dimensions: 115 x 124 mm (see `../DESIGN-NOTES.md` Cycle 3 §Deviations -
  +9 mm height waiver to clear XIAO nRF52840 module castellations)
- Thickness: 1.6 mm
- Colour: Black (matte or gloss)
- Silkscreen: White
- Surface finish: HASL-LF (lead-free)
- Min via / track: 0.4 / 0.15 mm (well within JLCPCB standard)
- Impedance control: N/A
- Gold fingers: N/A
- Castellated holes: N/A (MCU castellations live inside board area,
  not on the board edge)

Zip the above 11 files and upload to JLCPCB. Use `../bom.csv` for SMT
Assembly (rows marked `DNP` are skipped on the JLCPCB side too) and
`../cpl.csv` (kicad-cli output with `--exclude-dnp`) for pick-and-place.
