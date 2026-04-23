#!/usr/bin/env python3
"""Cycle 11 Iter 31: move under-size silk reference text off F.SilkS.

SW_PWR1 and TH1 have their Reference fields on F.SilkS with 0.8 mm
text; DRC rule requires >= 1.0 mm on silkscreen. Moving to F.Fab keeps
the text on the fabrication drawing but drops it from the silk
artwork, so the manufactured board no longer triggers the silk text
height rule.
"""
from __future__ import annotations

import pathlib
import re

PCB = pathlib.Path(
    "/var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/pcb/claude-code-pad.kicad_pcb"
)


def main() -> int:
    text = PCB.read_text()
    changed = 0
    for ref in ("SW_PWR1", "TH1"):
        pattern = re.compile(
            r'(\(property "Reference" "' + re.escape(ref) + r'"\s*\n'
            r'\s*\(at [^)]+\)\s*\n'
            r'\s*\(layer ")F\.SilkS(")'
        )
        new = pattern.sub(r"\1F.Fab\2", text)
        if new != text:
            text = new
            changed += 1
    PCB.write_text(text)
    print(f"moved references to F.Fab: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
