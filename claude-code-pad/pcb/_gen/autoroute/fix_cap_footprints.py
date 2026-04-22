#!/usr/bin/env python3
"""Cycle 9 B2 fix: correct 0402 capacitor LIB_IDs in-place.

Problem: `generate.py` emitted every 0402 (both R and C) using
`Resistor_SMD:R_0402_1005Metric`. Pad geometry is identical for both
families so the board works, but KiCad 10's schematic-parity DRC
flags `footprint_symbol_mismatch` on every 0402 capacitor because the
schematic symbol's Footprint property targets
`Capacitor_SMD:C_0402_1005Metric`.

Fix (surgical, no routing loss): walk every footprint on the PCB and
for each reference whose expected family is Capacitor (CL1..CL25, C3,
C4, C_ENC, C_ENC1, C_VBAT, C_VBAT1 -- `C`-prefixed refs on the
R_0402_1005Metric body), rewrite the footprint library id to
`Capacitor_SMD:C_0402_1005Metric`. 0805 caps (C1/C2) and 0603 caps
are already on the correct library; SPS / SOD / SOT / LED / MX /
encoder footprints are untouched.

Usage:
  distrobox enter kicad -- python3 autoroute/fix_cap_footprints.py <board.kicad_pcb>
"""
from __future__ import annotations

import os
import re
import sys


# Map from OLD footprint LIB_ID to NEW footprint LIB_ID. Keyed by
# (lib_id, ref_filter_regex).
# Every reference that matches ref_filter AND currently uses the OLD
# LIB_ID is rewritten to NEW.
REWRITES = [
    {
        "old": "Resistor_SMD:R_0402_1005Metric",
        "new": "Capacitor_SMD:C_0402_1005Metric",
        # Ref starts with 'C' (but NOT 'COL' / 'COMMENT' / reserved) --
        # i.e. capacitor references. The board convention is CL* for
        # the LED-local caps, Cn for bulk / decoupling, C_* for the
        # encoder/VBAT debounce caps. No current refs beginning with
        # 'C' are non-capacitors, so the bare prefix is sufficient.
        "ref_regex": re.compile(r"^C(L\d+|_[A-Z0-9]+1?|\d+)$"),
    },
]


def main(board_path: str) -> int:
    # We edit the .kicad_pcb as text; using pcbnew.Board here risks
    # an unrelated serialisation round-trip that can disturb the
    # Freerouting-produced track geometry (empirically observed in
    # cycle 8). Text editing is safer and targeted.
    with open(board_path, "r") as f:
        contents = f.read()

    # Split into footprint blocks. A footprint block begins with
    # `\t(footprint "..."\n` and ends at the matching closing `\t)`.
    # We parse by scanning paren depth from the `(footprint` opening.
    out_parts = []
    cursor = 0
    total_rewrites = 0
    while True:
        m = re.search(r'\(footprint "([^"]+)"', contents[cursor:])
        if not m:
            out_parts.append(contents[cursor:])
            break
        fp_start_rel = m.start()
        fp_start = cursor + fp_start_rel
        old_lib = m.group(1)
        out_parts.append(contents[cursor:fp_start])

        # Find matching close paren for this footprint.
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
        # Pull the Reference out of the block.
        ref_m = re.search(r'\(property "Reference" "([^"]+)"', fp_block)
        ref = ref_m.group(1) if ref_m else ""

        new_lib = None
        for rule in REWRITES:
            if old_lib == rule["old"] and rule["ref_regex"].match(ref):
                new_lib = rule["new"]
                break

        if new_lib is not None:
            # Rewrite only the lib_id in the opening `(footprint "OLD"`.
            fp_block = fp_block.replace(
                f'(footprint "{old_lib}"',
                f'(footprint "{new_lib}"',
                1,
            )
            total_rewrites += 1
            print(f"  {ref}: {old_lib} -> {new_lib}")

        out_parts.append(fp_block)
        cursor = i

    new_contents = "".join(out_parts)
    if total_rewrites == 0:
        print("No footprints matched the rewrite rules.")
        return 0

    with open(board_path, "w") as f:
        f.write(new_contents)
    print(f"Rewrote {total_rewrites} footprint LIB_IDs in {board_path}.")
    return total_rewrites


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    rc = main(sys.argv[1])
    sys.exit(0 if rc >= 0 else 1)
