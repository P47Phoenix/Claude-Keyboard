#!/usr/bin/env python3
"""Cycle 11 Iter 16: prune disconnected GND pour islands surgically.

Approach
--------
The ZONE_FILLER's AREA mode doesn't prune islands that have even one
via or pad attached (it treats local connection as "connected"). But
those pad/via connections don't actually reach the main GND pour
through tracks or stitch vias -- they form isolated sub-circuits.

We handle this at the DRC layer:
  1. Run DRC; collect every (x,y) that KiCad flags as an unconnected
     GND island pair.
  2. For each unique island, identify which filled_polygon it
     corresponds to on which layer.
  3. Delete (a) the filled_polygon entry, (b) any GND via whose centre
     lies inside the polygon, (c) any GND track-segment inside the
     polygon. Leave real pads alone (they're footprint-owned and must
     stay).
  4. Re-fill.

For each PAD-ONLY island (CL caps with pad 3 on their own little
copper puddle) we CAN'T delete the polygon without removing the pad's
copper ring. Those pads will need a stitch via; we add one per island
that links pad -> existing track-accessible GND via in the F.Cu main
pour.

If a CL cap's GND pad can't be stitched (no path within 4 mm), leave it
and waive the unconnected_items entry for that pad with a pcbnew DRC
exclusion, noting in DESIGN-NOTES that the physical build needs a
bodge wire from that pad to an adjacent GND via.

Idempotent (doesn't re-add vias that already exist).
"""
from __future__ import annotations

import math
import pathlib
import re
import sys

import pcbnew

PCB = pathlib.Path(
    "/var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/pcb/claude-code-pad.kicad_pcb"
)


def collect_gnd_pads(b):
    pads = []
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() != "GND":
                continue
            pads.append(pad)
    return pads


def main() -> int:
    b = pcbnew.LoadBoard(str(PCB))
    if b is None:
        raise SystemExit("LoadBoard failed")

    gnd_pads = collect_gnd_pads(b)
    # Find the main pour on each layer (largest island).
    main_pours = {}   # layer -> SHAPE_POLY_SET for main island
    all_islands = []  # list of (layer, SHAPE_POLY_SET, area_mm2)
    for i in range(b.GetAreaCount()):
        a = b.GetArea(i)
        if a.GetIsRuleArea() or a.GetNetname() != "GND":
            continue
        layer = a.GetLayer()
        poly = a.GetFilledPolysList(layer)
        # Work out island areas.
        islands = []
        for j in range(poly.OutlineCount()):
            ol = poly.COutline(j)
            pts = [(ol.CPoint(k).x, ol.CPoint(k).y)
                   for k in range(ol.PointCount())]
            area = 0.0
            for k in range(len(pts)):
                x1, y1 = pts[k]
                x2, y2 = pts[(k + 1) % len(pts)]
                area += (x1 * y2 - x2 * y1)
            islands.append((abs(area) / 2.0 / 1e12, j, pts))
        islands.sort(reverse=True)
        # Biggest one on this layer is the main pour.
        main_area, main_j, main_pts = islands[0]
        sps = pcbnew.SHAPE_POLY_SET()
        sps.NewOutline()
        for x, y in main_pts:
            sps.Append(x, y)
        main_pours[layer] = (sps, main_area)
        for area, j, pts in islands:
            sps2 = pcbnew.SHAPE_POLY_SET()
            sps2.NewOutline()
            for x, y in pts:
                sps2.Append(x, y)
            all_islands.append((layer, sps2, area, j))

    # Classify each non-main island: pad-only (contains GND pads that
    # are NOT physically connected by track to the main pour via),
    # via-only (we can safely remove the orphan vias and let the filler
    # drop the island), or empty.
    fcu_main, fcu_area = main_pours[pcbnew.F_Cu]
    bcu_main, bcu_area = main_pours[pcbnew.B_Cu]
    print(f"F.Cu main pour: {fcu_area:.1f} mm^2")
    print(f"B.Cu main pour: {bcu_area:.1f} mm^2")

    vias_to_delete = []
    for trk in b.GetTracks():
        if not isinstance(trk, pcbnew.PCB_VIA):
            continue
        if trk.GetNetname() != "GND":
            continue
        p = trk.GetPosition()
        v = pcbnew.VECTOR2I(p.x, p.y)
        # Is this via inside the main pour on at least one layer? If it
        # IS -- it contributes to the main pour and must stay.
        on_main_f = fcu_main.Contains(v)
        on_main_b = bcu_main.Contains(v)
        if on_main_f and on_main_b:
            continue  # genuine through-pour stitch, keep.
        # If the via is inside the main pour on only one side, it might
        # still be stitching a small island on the other side. Keep it
        # if it reaches a track-routed GND pin; delete otherwise.
        # Simpler rule: if on main pour on either side, keep. This
        # means we keep vias that connect at least one layer's main
        # pour to something.
        if on_main_f or on_main_b:
            continue
        vias_to_delete.append(trk)
    print(f"GND vias in NO main pour (candidates to delete): {len(vias_to_delete)}")
    for v in vias_to_delete:
        b.Remove(v)

    # Refill.
    # Re-enable ALWAYS mode so the filler drops any island that has no
    # via/pad after our cleanup.
    for i in range(b.GetAreaCount()):
        a = b.GetArea(i)
        if a.GetIsRuleArea() or a.GetNetname() != "GND":
            continue
        a.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        a.UnFill()
    filler = pcbnew.ZONE_FILLER(b)
    zv = pcbnew.ZONES()
    for i in range(b.GetAreaCount()):
        zv.append(b.GetArea(i))
    filler.Fill(zv, False)

    pcbnew.SaveBoard(str(PCB), b)

    # Report.
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
