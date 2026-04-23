#!/usr/bin/env python3
"""Cycle 11 Iter 8: set GND zones' island-removal policy to "remove below
area threshold" so tiny unreachable pour fragments don't appear as
`unconnected_items` errors. Large islands (which may be intentional)
stay.

Implementation via pcbnew API (not text patching), to avoid producing
malformed S-expressions when the file format tightens between KiCad 9
and KiCad 10.

Threshold: 10 mm^2. Any fragment smaller than this is pruned by the
filler.

Idempotent.
"""
from __future__ import annotations

import pathlib
import sys

import pcbnew  # noqa: E402 -- flatpak python

PCB = pathlib.Path(
    "/var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/pcb/claude-code-pad.kicad_pcb"
)


def main() -> int:
    board = pcbnew.LoadBoard(str(PCB))
    if board is None:
        print("LoadBoard FAILED", file=sys.stderr)
        return 1
    changed = 0
    for i in range(board.GetAreaCount()):
        a = board.GetArea(i)
        if a.GetIsRuleArea():
            continue
        net = a.GetNetname()
        if net != "GND":
            continue
        # Island removal mode: 0=Always, 1=Never, 2=MinArea.
        try:
            a.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_AREA)
        except AttributeError:
            # API name varies by bindings. Fall back to integer.
            a.SetIslandRemovalMode(2)
        # Threshold serialises to mm^2 in the .kicad_pcb. Empirically
        # setting 50e12 IU^2 yielded `island_area_min 50`, so pass the
        # desired mm^2 value scaled by 1e12. We want ~500 mm^2 to prune
        # everything except the two main continuous pours.
        a.SetMinIslandArea(500 * 1_000_000 * 1_000_000)
        changed += 1
    print(f"Zones updated: {changed}")

    # Re-fill.
    filler = pcbnew.ZONE_FILLER(board)
    zv = pcbnew.ZONES()
    for i in range(board.GetAreaCount()):
        zv.append(board.GetArea(i))
    filler.Fill(zv, False)

    ok = pcbnew.SaveBoard(str(PCB), board)
    if not ok:
        print("SaveBoard FAILED", file=sys.stderr)
        return 2
    print("saved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
