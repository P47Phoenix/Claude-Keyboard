#!/usr/bin/env python3
"""Cycle 9 B3 fix: stamp the `LCSC` property on every PCB footprint
in-place from `bom.csv`.

Problem: every schematic symbol carries an `LCSC` property (the LCSC
part number). The PCB footprints, written by `generate.py` cycles 1-8,
did not include this property. KiCad 10's schematic-parity DRC flags
`footprint_symbol_field_mismatch: Missing symbol field 'LCSC' in
footprint` for every part.

Fix (surgical, no routing loss): walk the PCB, look up each footprint
reference's LCSC code in `bom.csv` (which lists comma-separated refs
per row), and inject a `(property "LCSC" "...")` block immediately
after the `Description` property of each footprint that doesn't
already carry it.

Usage:
  distrobox enter kicad -- python3 autoroute/add_lcsc_property.py \
      <board.kicad_pcb> <bom.csv>
"""
from __future__ import annotations

import csv
import os
import re
import sys
import uuid


# Same deterministic UUID namespace as generate.py.
NS = uuid.UUID("a7c0de00-0000-0000-0000-000000000000")


def U(tag: str) -> str:
    return str(uuid.uuid5(NS, tag))


def load_bom(bom_path: str) -> dict:
    """Return {ref: lcsc_code} from bom.csv."""
    refs_to_lcsc = {}
    with open(bom_path, newline="") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            lcsc = (row.get("LCSC Part #") or row.get("LCSC") or "").strip()
            if not lcsc:
                continue
            refs = (row.get("Designator") or "").split(",")
            for r in refs:
                r = r.strip()
                if r:
                    refs_to_lcsc[r] = lcsc
    return refs_to_lcsc


def main(board_path: str, bom_path: str) -> int:
    bom = load_bom(bom_path)
    if not bom:
        print(f"No LCSC entries in {bom_path}.", file=sys.stderr)
        return 0

    with open(board_path, "r") as f:
        contents = f.read()

    out_parts = []
    cursor = 0
    total_added = 0
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

        lcsc = bom.get(ref, "")
        if lcsc and 'property "LCSC"' not in fp_block:
            # Find the Description property closing paren, insert
            # an LCSC property right after it (before any other
            # property / pad / fp_line). Description is one of the
            # standard properties emitted by generate.py.
            desc_m = re.search(
                r'(\(property "Description"[\s\S]*?(?:^|\n)\t\t\))',
                fp_block, re.MULTILINE,
            )
            if desc_m:
                insertion_point = desc_m.end()
                lcsc_prop = (
                    f'\n\t\t(property "LCSC" "{lcsc}"\n'
                    f'\t\t\t(at 0 0 0)\n'
                    f'\t\t\t(layer "F.Fab")\n'
                    f'\t\t\t(hide yes)\n'
                    f'\t\t\t(uuid "{U(f"lc_{ref}")}")\n'
                    f'\t\t\t(effects (font (size 1 1) (thickness 0.15)))\n'
                    f'\t\t)'
                )
                fp_block = (fp_block[:insertion_point]
                            + lcsc_prop
                            + fp_block[insertion_point:])
                total_added += 1
                print(f"  {ref}: added LCSC '{lcsc}'")
            else:
                # Fallback: insert just before the (attr ...) block.
                attr_m = re.search(r'\n\t\t\(attr', fp_block)
                if attr_m:
                    insertion_point = attr_m.start()
                    lcsc_prop = (
                        f'\n\t\t(property "LCSC" "{lcsc}"\n'
                        f'\t\t\t(at 0 0 0)\n'
                        f'\t\t\t(layer "F.Fab")\n'
                        f'\t\t\t(hide yes)\n'
                        f'\t\t\t(uuid "{U(f"lc_{ref}")}")\n'
                        f'\t\t\t(effects (font (size 1 1) (thickness 0.15)))\n'
                        f'\t\t)'
                    )
                    fp_block = (fp_block[:insertion_point]
                                + lcsc_prop
                                + fp_block[insertion_point:])
                    total_added += 1
                    print(f"  {ref}: added LCSC '{lcsc}' (fallback)")
                else:
                    print(f"  {ref}: SKIPPED -- no insertion point found")

        out_parts.append(fp_block)
        cursor = i

    if total_added == 0:
        print("No LCSC properties added.")
        return 0

    new_contents = "".join(out_parts)
    with open(board_path, "w") as f:
        f.write(new_contents)
    print(f"Added LCSC property to {total_added} footprints in {board_path}.")
    return total_added


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    rc = main(sys.argv[1], sys.argv[2])
    sys.exit(0 if rc >= 0 else 1)
