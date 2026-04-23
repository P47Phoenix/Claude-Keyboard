#!/usr/bin/env python3
"""Cycle 11 Iter 17: per-pad GND stitcher for orphan LED/CL pads.

For every GND pad that currently lands on a B.Cu island that is NOT
the main B.Cu pour, drop a stitching via right next to the pad so the
pad connects directly to the F.Cu main pour.

Constraints:
  * Via size 0.6 mm diameter / 0.3 mm drill (same netclass default).
  * Via centre must be at least 0.2 mm from any non-GND track/pad on
    either layer (DRC netclass clearance is 0.15 mm; 0.2 gives 0.05 mm
    slack).
  * Via centre must be inside the F.Cu main pour (so the via's F.Cu
    copper actually touches it).
  * Try candidate offsets in a small square around the pad
    (dx, dy in {-0.8, -0.4, 0, +0.4, +0.8} mm) and pick the first one
    that passes.
  * If no candidate works for a pad, log it and leave for waiver.

Idempotent: skips pads that already have a GND via within 0.5 mm.
"""
from __future__ import annotations

import pathlib
import sys

import pcbnew

PCB = pathlib.Path(
    "/var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/pcb/claude-code-pad.kicad_pcb"
)


def mm_to_iu(v): return pcbnew.FromMM(v)
def iu_to_mm(v): return pcbnew.ToMM(v)


def find_main_pour(b, layer):
    best_sps = None
    best_area = 0
    for i in range(b.GetAreaCount()):
        a = b.GetArea(i)
        if a.GetIsRuleArea() or a.GetNetname() != "GND":
            continue
        if a.GetLayer() != layer:
            continue
        poly = a.GetFilledPolysList(layer)
        for j in range(poly.OutlineCount()):
            ol = poly.COutline(j)
            pts = [(ol.CPoint(k).x, ol.CPoint(k).y)
                   for k in range(ol.PointCount())]
            area = 0.0
            for k in range(len(pts)):
                x1, y1 = pts[k]
                x2, y2 = pts[(k + 1) % len(pts)]
                area += (x1 * y2 - x2 * y1)
            area = abs(area) / 2.0
            if area > best_area:
                best_area = area
                sps = pcbnew.SHAPE_POLY_SET()
                sps.NewOutline()
                for x, y in pts:
                    sps.Append(x, y)
                best_sps = sps
    return best_sps, best_area


def nongnd_shapes(b):
    shp_f = []
    shp_b = []
    for trk in b.GetTracks():
        if trk.GetNetname() == "GND":
            continue
        if isinstance(trk, pcbnew.PCB_VIA):
            if trk.IsOnLayer(pcbnew.F_Cu):
                shp_f.append(trk.GetEffectiveShape())
            if trk.IsOnLayer(pcbnew.B_Cu):
                shp_b.append(trk.GetEffectiveShape())
        else:
            layer = trk.GetLayer()
            if layer == pcbnew.F_Cu:
                shp_f.append(trk.GetEffectiveShape())
            elif layer == pcbnew.B_Cu:
                shp_b.append(trk.GetEffectiveShape())
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() == "GND":
                continue
            if pad.IsOnLayer(pcbnew.F_Cu):
                shp_f.append(pad.GetEffectiveShape(pcbnew.F_Cu))
            if pad.IsOnLayer(pcbnew.B_Cu):
                shp_b.append(pad.GetEffectiveShape(pcbnew.B_Cu))
    return shp_f, shp_b


def main() -> int:
    b = pcbnew.LoadBoard(str(PCB))
    if b is None:
        raise SystemExit("LoadBoard failed")

    fcu_main, fcu_area = find_main_pour(b, pcbnew.F_Cu)
    bcu_main, bcu_area = find_main_pour(b, pcbnew.B_Cu)
    print(f"F.Cu main pour: {fcu_area/1e12:.1f} mm^2")
    print(f"B.Cu main pour: {bcu_area/1e12:.1f} mm^2")

    shp_f, shp_b = nongnd_shapes(b)

    # Collect Edge.Cuts segments for board-edge clearance.
    edge_shapes = []
    for drawing in b.GetDrawings():
        try:
            if drawing.GetLayer() == pcbnew.Edge_Cuts:
                edge_shapes.append(drawing.GetEffectiveShape())
        except Exception:
            pass
    # Also LED Edge.Cuts apertures are per-footprint (fp_line on Edge.Cuts).
    for fp in b.GetFootprints():
        for item in fp.GraphicalItems():
            try:
                if item.GetLayer() == pcbnew.Edge_Cuts:
                    edge_shapes.append(item.GetEffectiveShape())
            except Exception:
                pass

    edge_clearance_iu = mm_to_iu(0.15)  # 0.1 min + slack

    def edge_collision(p):
        v = pcbnew.VECTOR2I(p[0], p[1])
        for shp in edge_shapes:
            try:
                if shp.Collide(v, edge_clearance_iu + mm_to_iu(0.3)):
                    return True
            except Exception:
                pass
        return False

    # Collect hole geometry for hole-to-hole clearance.
    pth_holes = []
    for trk in b.GetTracks():
        if isinstance(trk, pcbnew.PCB_VIA):
            pos = trk.GetPosition()
            pth_holes.append((pos.x, pos.y, trk.GetDrillValue()))
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            if pad.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH,
                                      pcbnew.PAD_ATTRIB_NPTH):
                pos = pad.GetPosition()
                pth_holes.append((pos.x, pos.y, pad.GetDrillSize().x))

    via_copper_half_iu = mm_to_iu(0.3)
    via_drill_half_iu = mm_to_iu(0.15)
    # netclass min_clearance is 0.2 mm; leave 0.05 mm slack.
    copper_clearance_iu = mm_to_iu(0.25)
    hole_clearance_iu = mm_to_iu(0.27)   # 0.25 min + slack

    def collision(p, layer_shapes):
        v = pcbnew.VECTOR2I(p[0], p[1])
        for shp in layer_shapes:
            try:
                if shp.Collide(v, via_copper_half_iu + copper_clearance_iu):
                    return True
            except Exception:
                pass
        return False

    def hole_collision(p):
        for hx, hy, hdrill in pth_holes:
            dx = p[0] - hx
            dy = p[1] - hy
            min_center = via_drill_half_iu + hdrill // 2 + hole_clearance_iu
            if dx * dx + dy * dy < min_center * min_center:
                return True
        return False

    # Existing GND vias for idempotency.
    existing_gnd_vias = []
    for trk in b.GetTracks():
        if isinstance(trk, pcbnew.PCB_VIA) and trk.GetNetname() == "GND":
            pos = trk.GetPosition()
            existing_gnd_vias.append((pos.x, pos.y))

    def already_stitched(pad_pos):
        for vx, vy in existing_gnd_vias:
            if (vx - pad_pos[0]) ** 2 + (vy - pad_pos[1]) ** 2 < mm_to_iu(0.5) ** 2:
                return True
        return False

    added = 0
    skipped_no_candidate = []
    skipped_already = 0

    # Walk every GND pad that's NOT in the F.Cu main pour at its
    # location, and is on B.Cu.
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        for pad in fp.Pads():
            if pad.GetNetname() != "GND":
                continue
            # PTH / NPTH GND pads are already physical through-holes; they
            # connect to both layers by construction. Skip -- no via
            # needed. (If the pour can't reach them, that's a pour
            # problem, not a stitching one.)
            if pad.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH,
                                      pcbnew.PAD_ATTRIB_NPTH):
                continue
            pos = pad.GetPosition()
            pad_pos = (pos.x, pos.y)
            v = pcbnew.VECTOR2I(*pad_pos)
            if fcu_main.Contains(v):
                continue  # pad's location is under F.Cu main pour; fine.
            if already_stitched(pad_pos):
                skipped_already += 1
                continue
            # Try nearby offsets.
            ok_p = None
            for dx_mm in (0, -0.6, 0.6, -1.0, 1.0, -1.4, 1.4):
                for dy_mm in (0, -0.6, 0.6, -1.0, 1.0, -1.4, 1.4):
                    p = (pad_pos[0] + mm_to_iu(dx_mm),
                         pad_pos[1] + mm_to_iu(dy_mm))
                    pv = pcbnew.VECTOR2I(p[0], p[1])
                    if not fcu_main.Contains(pv):
                        continue
                    if collision(p, shp_f) or collision(p, shp_b):
                        continue
                    if hole_collision(p):
                        continue
                    if edge_collision(p):
                        continue
                    ok_p = p
                    break
                if ok_p:
                    break
            if ok_p is None:
                skipped_no_candidate.append(f"{ref}.{pad.GetNumber()}")
                continue
            # Add the via.
            via = pcbnew.PCB_VIA(b)
            via.SetPosition(pcbnew.VECTOR2I(*ok_p))
            via.SetWidth(mm_to_iu(0.6))
            via.SetDrill(mm_to_iu(0.3))
            via.SetNetCode(pad.GetNetCode())
            via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            b.Add(via)
            existing_gnd_vias.append(ok_p)
            # Also add a short B.Cu track from pad centre to via centre
            # so the B.Cu island is physically connected to the via.
            trk = pcbnew.PCB_TRACK(b)
            trk.SetStart(pcbnew.VECTOR2I(*pad_pos))
            trk.SetEnd(pcbnew.VECTOR2I(*ok_p))
            trk.SetWidth(mm_to_iu(0.2))
            trk.SetLayer(pcbnew.B_Cu)
            trk.SetNetCode(pad.GetNetCode())
            b.Add(trk)
            added += 1
    print(f"Stitches added: {added}")
    print(f"Already-stitched pads skipped: {skipped_already}")
    print(f"Pads with no safe candidate: {len(skipped_no_candidate)}")
    for s in skipped_no_candidate:
        print(f"  - {s}")

    # Refill. Don't UnFill first -- that seems to cause the filler to
    # ignore zone connect_pads clearance in some edge cases.
    filler = pcbnew.ZONE_FILLER(b)
    zv = pcbnew.ZONES()
    for i in range(b.GetAreaCount()):
        zv.append(b.GetArea(i))
    filler.Fill(zv, False)

    pcbnew.SaveBoard(str(PCB), b)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
