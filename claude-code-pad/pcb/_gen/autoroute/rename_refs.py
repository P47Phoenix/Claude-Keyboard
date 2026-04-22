#!/usr/bin/env python3
"""Cycle 9 B4: PCB reference renamer (no-op for Cycle 9).

The Cycle 9 brief asked ECE-1 to rename PCB footprint references with
schematic-side `_1` suffix drift -- specifically C_ENC -> C_ENC1,
C_VBAT -> C_VBAT1, D_GREV -> D_GREV1.

After parity-DRC was actually run with the Cycle 9 flags, the only
ref drift turned out to be the `C5` (1 nF USB ground-bounce bypass)
that was retired from the PCB in Cycle 5 but lingered in the
schematic emitter -- fixed in `generate.py` (removed from the
MCU-local decap list). No additional `missing_footprint` /
`extra_footprint` from `_1` suffix drift was reported (Cycle 8's UUID
linkage already resolved most ref-drift signals before they reached
the parity check).

The 10 residual `extra_footprint` warnings are all mechanical-only
footprints (FID1-3, H1-4, J_XIAO_BP, TP1-2) carried forward as known
Cycle 8 residuals. Rev-B will add them as schematic symbols.

This script enumerates the empty rename list and exits successfully,
and is retained so the file referenced by the Cycle 9 deliverables
list exists. To do an actual rename run, populate the RENAMES dict
below and re-run.

Usage:
  python3 autoroute/rename_refs.py <board.kicad_pcb>
"""
from __future__ import annotations

import re
import sys


# Empty for Cycle 9. Format: {old_ref: new_ref}.
RENAMES: dict = {}


def main(board_path: str) -> int:
    if not RENAMES:
        print("RENAMES is empty; nothing to do (Cycle 9 had no ref drift).")
        return 0

    with open(board_path, "r") as f:
        contents = f.read()

    out = []
    cursor = 0
    n = 0
    while True:
        m = re.search(r'\(footprint "[^"]+"', contents[cursor:])
        if not m:
            out.append(contents[cursor:])
            break
        fp_start = cursor + m.start()
        out.append(contents[cursor:fp_start])
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
        block = contents[fp_start:i]
        ref_m = re.search(r'\(property "Reference" "([^"]+)"', block)
        if ref_m:
            old = ref_m.group(1)
            new = RENAMES.get(old)
            if new:
                block = re.sub(
                    r'(\(property "Reference" )"' + re.escape(old) + '"',
                    rf'\1"{new}"', block, count=1,
                )
                n += 1
                print(f"  {old} -> {new}")
        out.append(block)
        cursor = i

    if n == 0:
        print("No matching references found.")
        return 0
    with open(board_path, "w") as f:
        f.write("".join(out))
    print(f"Renamed {n} references in {board_path}.")
    return n


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
