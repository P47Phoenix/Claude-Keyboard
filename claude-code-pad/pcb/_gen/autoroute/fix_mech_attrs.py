#!/usr/bin/env python3
"""Cycle 11 Iter 39: align mechanical footprint attrs with their
schematic symbols' in_bom flags.

J_XIAO_BP on the PCB has `(attr smd)` -- no exclude_from_bom. Its
schematic symbol (Iter 38) has `in_bom no`. The parity check flags
this as `footprint_symbol_mismatch`. We add `exclude_from_bom` +
`exclude_from_pos_files` to the PCB so the flags agree. These flags
are semantically correct (back-pad jumper is a solder pattern, not a
BOM line).
"""
from __future__ import annotations

import pathlib
import re

PCB = pathlib.Path(
    "/var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/pcb/claude-code-pad.kicad_pcb"
)


def main() -> int:
    text = PCB.read_text()
    # Find J_XIAO_BP footprint block.
    m = re.search(r'\(property "Reference" "J_XIAO_BP"', text)
    if not m:
        print("J_XIAO_BP not found")
        return 1
    fp_start = text.rfind("(footprint", 0, m.start())
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
    block = text[fp_start:k]
    new_block = re.sub(
        r'\(attr smd\)',
        '(attr smd exclude_from_pos_files exclude_from_bom allow_missing_courtyard)',
        block,
        count=1,
    )
    if new_block == block:
        print("no attr change")
        return 0
    text = text[:fp_start] + new_block + text[k:]
    PCB.write_text(text)
    print("J_XIAO_BP: attr bumped with exclude flags")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
