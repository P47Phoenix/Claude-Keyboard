#!/usr/bin/env python3
"""Cycle 11 Iter 14: relax GND zone min_thickness and connect_pads clearance
so the filler produces a more continuous pour across crowded local
geometry.

Current: min_thickness 0.2 mm, connect_pads clearance 0.2 mm.
New:     min_thickness 0.15 mm (== board min_clearance), connect_pads 0.15.

0.15 mm is JLCPCB basic-tier minimum trace/clearance; we already set
board `min_clearance` to 0.15 in Cycle 8. The zone must not violate its
host board clearance anyway, so reducing the zone's own minimum to match
just lets the filler thread more copper through tight cuts.

Re-fills the zones so the updated geometry appears on disk.

Idempotent.
"""
from __future__ import annotations

import pathlib

import pcbnew  # flatpak python

PCB = pathlib.Path(
    "/var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/pcb/claude-code-pad.kicad_pcb"
)


def main() -> int:
    b = pcbnew.LoadBoard(str(PCB))
    if b is None:
        raise SystemExit("LoadBoard failed")
    touched = 0
    for i in range(b.GetAreaCount()):
        a = b.GetArea(i)
        if a.GetIsRuleArea() or a.GetNetname() != "GND":
            continue
        # Relax zone min_thickness from 0.2 -> 0.15 mm. (Allows pour to
        # thread tighter slivers; net-to-net clearance is unaffected.)
        a.SetMinThickness(pcbnew.FromMM(0.15))
        # Leave LocalClearance untouched -- netclass default 0.2 mm
        # govers zone-to-other-net spacing and must not be weakened.
        # Also enable AREA mode with a huge threshold (10000 mm^2) so
        # every island smaller than that is pruned at fill time. The
        # main pour (~9100 mm^2 B.Cu, ~12000 mm^2 F.Cu) is the only
        # thing above that; any orphan islands disappear.
        a.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_AREA)
        # min_island_area: KiCad 10 serialises to mm^2 stored in a 32-bit
        # int divided by 1e6 (so max ~2147 mm^2). 2000 mm^2 still beats
        # every fragment except the two main pours (9100 B, 12000 F).
        a.SetMinIslandArea(2000 * 1_000_000 * 1_000_000)
        a.UnFill()
        touched += 1
    print(f"zones relaxed: {touched}")

    filler = pcbnew.ZONE_FILLER(b)
    zv = pcbnew.ZONES()
    for i in range(b.GetAreaCount()):
        zv.append(b.GetArea(i))
    filler.Fill(zv, False)

    pcbnew.SaveBoard(str(PCB), b)

    # Report new outline counts.
    b = pcbnew.LoadBoard(str(PCB))
    for i in range(b.GetAreaCount()):
        a = b.GetArea(i)
        if a.GetIsRuleArea() or a.GetNetname() != "GND":
            continue
        poly = a.GetFilledPolysList(a.GetLayer())
        print(f'{b.GetLayerName(a.GetLayer())}: outline_count={poly.OutlineCount()}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
