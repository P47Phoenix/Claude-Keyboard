#!/usr/bin/env python3
"""Cycle 9 B3 helper: copy each schematic symbol's `Description`
property into the corresponding PCB footprint, in-place.

KiCad 10's parity DRC flags `footprint_symbol_field_mismatch` for any
field that exists on both sides with different content. Cycles 1-8's
generate.py emits a richly-described `Description` property on
schematic symbols (e.g. "RGB DIN series resistor") but writes
`(property "Description" "")` on PCB footprints. We sync them in
place so the parity check resolves.

Usage:
  distrobox enter kicad -- python3 autoroute/sync_descriptions.py \
      <board.kicad_pcb> <schematic.kicad_sch>
"""
from __future__ import annotations

import re
import sys


def load_sch_descriptions(sch_path: str) -> dict:
    """Return {ref: description} from the schematic.

    Each symbol block in the .kicad_sch contains a `Reference`
    property and a `Description` property. We walk the file as
    text to avoid pulling in S-expression libraries.
    """
    with open(sch_path, "r") as f:
        contents = f.read()

    # Each symbol instance starts with `\t(symbol\n\t\t(lib_id ...)`
    # at indent level 1. Walk by scanning. Collect Reference +
    # Description pairs per block.
    sym_starts = [m.start() for m in re.finditer(r'\n\t\(symbol\n', contents)]
    refs_to_desc = {}
    for s in sym_starts:
        # Find matching close of this symbol block.
        depth = 0
        i = s + 1  # skip leading newline
        # Find first '(' at indent 1 -- the (symbol open paren.
        while i < len(contents) and contents[i] != "(":
            i += 1
        start_paren = i
        depth = 0
        while i < len(contents):
            ch = contents[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    i += 1
                    break
            i += 1
        block = contents[start_paren:i]
        ref_m = re.search(r'\(property "Reference" "([^"]+)"', block)
        desc_m = re.search(r'\(property "Description" "([^"]*)"', block)
        if ref_m and desc_m:
            refs_to_desc[ref_m.group(1)] = desc_m.group(1)
    return refs_to_desc


def main(board_path: str, sch_path: str) -> int:
    descs = load_sch_descriptions(sch_path)

    with open(board_path, "r") as f:
        contents = f.read()

    out_parts = []
    cursor = 0
    total_updated = 0
    while True:
        m = re.search(r'\(footprint "([^"]+)"', contents[cursor:])
        if not m:
            out_parts.append(contents[cursor:])
            break
        fp_start_rel = m.start()
        fp_start = cursor + fp_start_rel
        out_parts.append(contents[cursor:fp_start])
        depth = 0
        i = fp_start
        while i < len(contents):
            ch = contents[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    i += 1
                    break
            i += 1
        fp_block = contents[fp_start:i]

        ref_m = re.search(r'\(property "Reference" "([^"]+)"', fp_block)
        ref = ref_m.group(1) if ref_m else ""
        desc = descs.get(ref, "")

        if desc:
            # Replace the empty Description value if present.
            new_block, n = re.subn(
                r'(\(property "Description" )""',
                lambda mm: f'{mm.group(1)}"{desc}"',
                fp_block, count=1,
            )
            if n > 0:
                fp_block = new_block
                total_updated += 1

        out_parts.append(fp_block)
        cursor = i

    if total_updated == 0:
        print("No Description fields updated.")
        return 0

    new_contents = "".join(out_parts)
    with open(board_path, "w") as f:
        f.write(new_contents)
    print(f"Updated Description on {total_updated} footprints in {board_path}.")
    return total_updated


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    rc = main(sys.argv[1], sys.argv[2])
    sys.exit(0 if rc >= 0 else 1)
