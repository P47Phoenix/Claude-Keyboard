#!/usr/bin/env python3
"""Cycle 11 Iter 32 (fixed): tie fiducial pads to GND net.

Bigger mask aperture makes the bridge issue worse, not better. The
bridge error fires when the fiducial's mask opening merges with an
adjacent different-net opening. Easiest resolution: put the fiducials
on the GND net -- then the merged opening is same-net and no bridge
warning. Fiducial copper is a single 1 mm dot; tying to GND is
harmless (it's a vision alignment target, not a signal pad).

Revert footprint name back to Mask2mm (narrow aperture keeps the
fiducial distinct for AOI machines), but mark the pad net = "GND".

Idempotent.
"""
from __future__ import annotations

import pathlib
import re

PCB = pathlib.Path(
    "/var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/pcb/claude-code-pad.kicad_pcb"
)
SCH = pathlib.Path(
    "/var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/pcb/claude-code-pad.kicad_sch"
)
PRETTY = pathlib.Path(
    "/var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/pcb/claude-code-pad.pretty"
)


def main() -> int:
    # Restore lib name and margin (idempotent: tolerates either state).
    new_path = PRETTY / "Fiducial_1mm_Mask3mm.kicad_mod"
    old_path = PRETTY / "Fiducial_1mm_Mask2mm.kicad_mod"
    if new_path.exists() and not old_path.exists():
        text = new_path.read_text()
        text = text.replace('"Fiducial_1mm_Mask3mm"', '"Fiducial_1mm_Mask2mm"', 1)
        text = text.replace("(solder_mask_margin 1.0)",
                            "(solder_mask_margin 0.5)")
        text = text.replace('"Fiducial 1 mm dia, 3 mm mask"',
                            '"Fiducial 1 mm dia, 2 mm mask"')
        old_path.write_text(text)
        new_path.unlink()

    # PCB: revert lib_id and solder_mask_margin; then tie fiducial pad
    # to GND net.
    pcb = PCB.read_text()
    pcb = pcb.replace(
        "claude-code-pad:Fiducial_1mm_Mask3mm",
        "claude-code-pad:Fiducial_1mm_Mask2mm",
    )
    pcb = pcb.replace("(solder_mask_margin 1.0)",
                      "(solder_mask_margin 0.5)")

    # For each FID1/FID2/FID3 footprint, inject (net N "GND") into its
    # pad 1 block.
    # KiCad 10 format: pad has `(net "NET_NAME")`. Inject `(net "GND")`
    # into each fiducial pad block.
    patched = 0
    out = []
    i = 0
    while i < len(pcb):
        idx = pcb.find('(footprint "claude-code-pad:Fiducial_1mm_Mask2mm"', i)
        if idx < 0:
            out.append(pcb[i:])
            break
        depth = 0
        k = idx
        while k < len(pcb):
            c = pcb[k]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    k += 1
                    break
            k += 1
        body = pcb[idx:k]
        if re.search(r'\(pad "1"[^)]*\(net "GND"\)', body, re.DOTALL):
            out.append(pcb[i:k])
        else:
            new_body = re.sub(
                r'(\(pad "1" smd circle\s*\n'
                r'\s*\(at 0 0\)\s*\n'
                r'\s*\(size 1 1\)\s*\n'
                r'\s*\(layers [^)]+\)\s*\n)',
                r'\1\t\t\t(net "GND")\n',
                body,
                count=1,
            )
            if new_body != body:
                patched += 1
            out.append(pcb[i:idx])
            out.append(new_body)
        i = k
    pcb_new = "".join(out)
    PCB.write_text(pcb_new)
    print(f"PCB: tied {patched} fiducial pads to GND net")

    # Schematic: revert Footprint name.
    sch = SCH.read_text()
    sch = sch.replace(
        "claude-code-pad:Fiducial_1mm_Mask3mm",
        "claude-code-pad:Fiducial_1mm_Mask2mm",
    )
    SCH.write_text(sch)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
