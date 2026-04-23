#!/usr/bin/env python3
"""Cycle 11 Iter 5: silk_edge_clearance cleanup.

Problem: every matrix diode's single B.Silkscreen segment (cathode
indicator at local x=-3.1) sits within 0.1 mm of the adjacent LED's
Edge.Cuts aperture, because diodes are laid out 4 mm east of the LED
and the LED's 3.4 mm aperture extends back toward the diode silk.

Fix: drop the B.Silkscreen cathode bar on the diode footprint. The
B.Fab layer rectangle is retained (+ printed outline on assembly
drawing), but no silk appears on the manufactured board adjacent to
the LED aperture. The diode orientation is determinable from the
pad/body shape (pad 1 = cathode, smaller) and the reference
designator positioned on B.Fab.

Applied to:
  * pcb/claude-code-pad.pretty/D_SOD-123.kicad_mod
  * every D_SOD-123 instance in pcb/claude-code-pad.kicad_pcb
  * pcb/_gen/generate.py fp_diode() (comment only; next regen will
    already skip silk because library is authoritative)

Idempotent.
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path("/var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/pcb")
PCB = ROOT / "claude-code-pad.kicad_pcb"
PRETTY = ROOT / "claude-code-pad.pretty"
DIODE = PRETTY / "D_SOD-123.kicad_mod"


def strip_silk(body: str, layer_variants: tuple[str, ...]) -> str:
    """Drop every (fp_line ...) whose (layer "...") is in layer_variants."""
    out = []
    i = 0
    while i < len(body):
        j = body.find("(fp_line", i)
        if j < 0:
            out.append(body[i:])
            break
        depth = 0
        k = j
        while k < len(body):
            c = body[k]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    k += 1
                    break
            k += 1
        block = body[j:k]
        if any(f'(layer "{L}")' in block for L in layer_variants):
            out.append(body[i:j])
            nl = k
            while nl < len(body) and body[nl] in "\t\n ":
                nl += 1
            i = nl
        else:
            out.append(body[i:k])
            i = k
    return "".join(out)


def main() -> None:
    # 1. Library file.
    text = DIODE.read_text()
    new = strip_silk(text, ("F.SilkS", "B.SilkS", "F.Silkscreen", "B.Silkscreen"))
    if new != text:
        DIODE.write_text(new)
        print("lib patched: D_SOD-123")

    # 2. PCB instances. Only touch D_SOD-123 blocks.
    pcb = PCB.read_text()
    out = []
    i = 0
    patched = 0
    while i < len(pcb):
        m = re.search(r'\(footprint "claude-code-pad:D_SOD-123"', pcb[i:])
        if not m:
            out.append(pcb[i:])
            break
        start = i + m.start()
        out.append(pcb[i:start])
        depth = 0
        j = start
        while j < len(pcb):
            c = pcb[j]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        body = pcb[start:j]
        body = strip_silk(body, ("F.SilkS", "B.SilkS", "F.Silkscreen", "B.Silkscreen"))
        out.append(body)
        patched += 1
        i = j
    new_pcb = "".join(out)
    if new_pcb != pcb:
        PCB.write_text(new_pcb)
        print(f"PCB: patched {patched} D_SOD-123 instances")


if __name__ == "__main__":
    main()
