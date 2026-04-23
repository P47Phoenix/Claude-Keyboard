#!/usr/bin/env python3
"""Cycle 11 Iter 2b: split MountingHole_3.2mm_M3 into two library footprints
so grounded (H1/H2) and non-grounded (H3/H4) resolve without
lib_footprint_mismatch.

New footprints:
  claude-code-pad:MountingHole_3.2mm_M3           (grounded, pad 1 thru_hole)
  claude-code-pad:MountingHole_3.2mm_M3_NPTH      (no pad net, np_thru_hole)

H3 + H4 get rewritten to reference the NPTH variant.

Also: Fiducial_1mm_Mask2mm has three instances but the DRC flagged a
mismatch for FID1/FID2/FID3 too -- same mechanism. Check Fiducial parity
and split if needed.
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path("/var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/pcb")
PCB = ROOT / "claude-code-pad.kicad_pcb"
PRETTY = ROOT / "claude-code-pad.pretty"

NPTH_MOD = """(footprint "MountingHole_3.2mm_M3_NPTH"
\t(layer "F.Cu")
\t(descr "Mounting hole 3.2mm for M3 (non-plated)")
\t(property "Reference" "REF**"
\t\t(at 0 -4 0)
\t\t(layer "F.Fab")
\t\t(effects (font (size 1 1) (thickness 0.15)))
\t)
\t(property "Value" "M3"
\t\t(at 0 4 0)
\t\t(layer "F.Fab")
\t\t(hide yes)
\t\t(effects (font (size 1 1) (thickness 0.15)))
\t)
\t(property "Datasheet" "" (at 0 0 0) (layer "F.Fab") (hide yes) (effects (font (size 1.27 1.27) (thickness 0.15))))
\t(property "Description" "" (at 0 0 0) (layer "F.Fab") (hide yes) (effects (font (size 1.27 1.27) (thickness 0.15))))
\t(property "Footprint" "" (at 0 0 0) (layer "F.Fab") (hide yes) (effects (font (size 1.27 1.27) (thickness 0.15))))
\t(attr exclude_from_pos_files exclude_from_bom allow_missing_courtyard)
\t(duplicate_pad_numbers_are_jumpers no)
\t(pad "" np_thru_hole circle
\t\t(at 0 0)
\t\t(size 3.2 3.2)
\t\t(drill 3.2)
\t\t(layers "*.Cu" "*.Mask")
\t\t(remove_unused_layers no)
\t)
)
"""


def split_mounting_hole() -> None:
    # Write the NPTH library module.
    (PRETTY / "MountingHole_3.2mm_M3_NPTH.kicad_mod").write_text(NPTH_MOD)

    # Rewrite PCB so any H3/H4 footprints (np_thru_hole) point at NPTH variant.
    text = PCB.read_text()
    # Find all claude-code-pad:MountingHole_3.2mm_M3 blocks and patch those
    # containing np_thru_hole.
    pattern = re.compile(
        r'\(footprint "claude-code-pad:MountingHole_3.2mm_M3"\s*\n(?:(?!\n\t\(footprint ).)*?\n\t\)',
        re.DOTALL,
    )
    def fix(m: re.Match) -> str:
        body = m.group(0)
        if "np_thru_hole" in body:
            return body.replace(
                'claude-code-pad:MountingHole_3.2mm_M3"',
                'claude-code-pad:MountingHole_3.2mm_M3_NPTH"',
                1,
            )
        return body

    new = pattern.sub(fix, text)
    if new != text:
        PCB.write_text(new)
        print("PCB: H3/H4 (np_thru_hole) rewritten to MountingHole_3.2mm_M3_NPTH")
    else:
        print("PCB: no NPTH mounting-hole footprint matched the regex")


if __name__ == "__main__":
    split_mounting_hole()
