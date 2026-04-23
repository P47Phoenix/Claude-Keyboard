#!/usr/bin/env python3
"""Cycle 11 Iter 31b: resolve R_GREV1 pad 2 starved-thermal.

The zone requires min 2 thermal spokes; R_GREV1 pad 2 only gets 1 because
of tight local geometry. Override the pad's zone connection to 'solid'
(zone_connect 2 = SOLID) so no thermal bridge is required for this pad.
Solid connection is electrically better (lower resistance) and eliminates
the starved-thermal check for this pad.
"""
from __future__ import annotations

import pathlib
import re

PCB = pathlib.Path(
    "/var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/pcb/claude-code-pad.kicad_pcb"
)


def main() -> int:
    text = PCB.read_text()
    # Find R_GREV1 footprint, then its pad 2.
    idx = text.find('(property "Reference" "R_GREV1"')
    if idx < 0:
        print("R_GREV1 not found")
        return 1
    fp_start = text.rfind("(footprint", 0, idx)
    depth = 0
    k = fp_start
    while k < len(text):
        c = text[k]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                k += 1
                break
        k += 1
    fp_end = k
    fp = text[fp_start:fp_end]

    # Inject (zone_connect 2) into pad 2 just before closing paren.
    new_fp = re.sub(
        r'(\(pad "2" smd rect\s*\n'
        r'\s*\(at [^)]+\)\s*\n'
        r'\s*\(size [^)]+\)\s*\n'
        r'\s*\(layers[^)]+\)\s*\n'
        r'\s*\(net [^)]+\)\s*\n)',
        r"\1\t\t\t(zone_connect 2)\n",
        fp,
        count=1,
    )
    if new_fp == fp:
        print("no pad 2 pattern match")
        return 1
    text = text[:fp_start] + new_fp + text[fp_end:]
    PCB.write_text(text)
    print("R_GREV1 pad 2: zone_connect 2 (solid) added")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
