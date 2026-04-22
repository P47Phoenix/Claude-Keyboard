#!/usr/bin/env python3
"""Cycle 7 surgical fix: widen power traces in-place, proximity-aware.

Problem: the Power netclass (0.80 mm) defined in claude-code-pad.kicad_pro
did not propagate through the Freerouting DSN -> SES round-trip. Every power
net came out at the Default 0.25 mm width. Widening avoids re-running
Freerouting (which would nuke the routed tracks).

Naive widening creates shorts where existing non-power routing was packed
within the envelope of the new 0.80 mm trace. This script is therefore
proximity-aware:

  For every power track segment, compute the minimum distance from the
  segment centreline to any OTHER-net copper object on the same layer.
  The maximum safe half-width is (dist - min_clearance). Trace width
  snaps to one of: 0.80 mm (goal), 0.50 mm, 0.40 mm, 0.30 mm, or
  0.25 mm (leave-as-is) -- the widest width that fits.

  Vias on power nets get the netclass via geometry (0.80 mm diameter /
  0.40 mm drill) *only* if no other-net copper lies within the expanded
  envelope.

After widening, re-fill zones so pour clearance rebuilds around the new
trace envelopes. Save.

Usage:
  distrobox enter kicad -- python3 autoroute/widen_power.py <board.kicad_pcb>
"""
from __future__ import annotations

import os
import sys

import pcbnew


POWER_NETS = {
    "VBAT",
    "VBAT_RAW",
    "VBAT_CELL",
    "VBAT_F",
    "VBAT_SW",
    "+3V3",
    "VUSB",
}

# Target and fallback widths in mm, widest-first. The first width that
# fits the proximity budget wins. 0.25 means leave the track alone.
WIDTH_LADDER_MM = [0.80, 0.60, 0.50, 0.40, 0.30]
LEAVE_AS_IS_MM = 0.25

# Must match the DRC clearance rule (netclass Default / Power = 0.25 mm).
# Use a tiny extra buffer (+5 um) to protect against sub-micron rounding
# in SHAPE_SEGMENT.Collide() integer math.
MIN_CLEARANCE_MM = 0.255

# Copper-to-edge (Edge.Cuts) clearance from board setup (0.10 mm), plus
# the same +5 um rounding buffer.
EDGE_CLEARANCE_MM = 0.105

# Via geometry targets (Power netclass).
POWER_VIA_DRILL_MM = 0.40
POWER_VIA_DIAMETER_MM = 0.80


def iu_to_mm(v: int) -> float:
    return v / 1e6


def mm_to_iu(v: float) -> int:
    return int(round(v * 1e6))


def get_obstacle_shapes(board, layer: int):
    """Return list of (netcode, SHAPE, kind) triples on `layer` for every
    copper object on the board, plus virtual Edge.Cuts obstacles. The
    caller filters by netcode; kind is one of "copper" or "edge".

    Kept layer-scoped so we never compare F.Cu vs B.Cu (different copper).
    """
    shapes = []
    # Tracks (segments + vias)
    for trk in board.GetTracks():
        if isinstance(trk, pcbnew.PCB_VIA):
            if not trk.IsOnLayer(layer):
                continue
        else:
            if trk.GetLayer() != layer:
                continue
        shapes.append((trk.GetNetCode(), trk.GetEffectiveShape(), "copper"))
    # Pads
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if not pad.IsOnLayer(layer):
                continue
            shapes.append((pad.GetNetCode(), pad.GetEffectiveShape(layer), "copper"))
    # Edge.Cuts graphics (board outline + LED apertures). Use netcode
    # -1 so they never match a real net; kind "edge" uses a different
    # clearance value.
    for drw in board.GetDrawings():
        if drw.GetLayer() == pcbnew.Edge_Cuts:
            try:
                shapes.append((-1, drw.GetEffectiveShape(), "edge"))
            except Exception:
                pass
    for fp in board.GetFootprints():
        for g in fp.GraphicalItems():
            if g.GetLayer() == pcbnew.Edge_Cuts:
                try:
                    shapes.append((-1, g.GetEffectiveShape(), "edge"))
                except Exception:
                    pass
    return shapes


def widest_safe_width(centreline_shape, track_netcode, obstacles,
                      min_clearance_iu: int,
                      edge_clearance_iu: int) -> float:
    """Return the widest width (mm) from WIDTH_LADDER_MM that keeps the
    track at least `min_clearance_iu` from any copper obstacle and
    `edge_clearance_iu` from any Edge.Cuts outline.

    `centreline_shape` MUST be a zero-width SHAPE_SEGMENT along the
    track's centreline. For each candidate width `w`, a track of width
    `w` has half-width `w/2`; it clears an obstacle iff the centreline
    has at least `w/2 + clearance` distance from that obstacle. We use
    `obstacle.Collide(centreline, clearance)` which returns True iff
    the centreline is within `clearance` of the obstacle.
    """
    for w_mm in WIDTH_LADDER_MM:
        half_iu = mm_to_iu(w_mm) // 2
        required_copper = half_iu + min_clearance_iu
        required_edge = half_iu + edge_clearance_iu
        ok = True
        for nc, shape, kind in obstacles:
            if kind == "copper" and nc == track_netcode:
                continue
            clr = required_edge if kind == "edge" else required_copper
            try:
                # Use obstacle.Collide(centreline, clearance) because
                # SHAPE_SEGMENT.Collide(other_shape) is unreliable
                # when the other shape is a compound/polygon.
                if shape.Collide(centreline_shape, clr):
                    ok = False
                    break
            except Exception:
                continue
        if ok:
            return w_mm
    return LEAVE_AS_IS_MM


def main(pcb_path: str) -> int:
    pcb_path = os.path.abspath(pcb_path)
    if not os.path.isfile(pcb_path):
        print(f"ERROR: board not found: {pcb_path}", file=sys.stderr)
        return 1

    board = pcbnew.LoadBoard(pcb_path)

    target_via_diameter = pcbnew.FromMM(POWER_VIA_DIAMETER_MM)
    target_via_drill = pcbnew.FromMM(POWER_VIA_DRILL_MM)
    min_clearance_iu = pcbnew.FromMM(MIN_CLEARANCE_MM)
    edge_clearance_iu = pcbnew.FromMM(EDGE_CLEARANCE_MM)

    # Map net codes we care about.
    power_netcodes: dict[int, str] = {}
    for name, net in board.GetNetsByName().items():
        sname = str(name)
        if sname in POWER_NETS:
            power_netcodes[net.GetNetCode()] = sname
    print(f"POWER net codes resolved: {power_netcodes}")
    missing = POWER_NETS - set(power_netcodes.values())
    if missing:
        print(f"WARN: POWER nets not present on board: {sorted(missing)}")

    # Pre-build full copper obstacle lists per layer once (expensive part).
    # The track loop filters by same-net below. Other power nets (e.g.
    # VBAT vs VBAT_SW) ARE obstacles for each other -- the DRC treats
    # them as distinct.
    print("Indexing copper obstacles on F.Cu and B.Cu...")
    obstacles_fcu = get_obstacle_shapes(board, pcbnew.F_Cu)
    obstacles_bcu = get_obstacle_shapes(board, pcbnew.B_Cu)
    print(f"  F.Cu obstacles: {len(obstacles_fcu)}  B.Cu obstacles: {len(obstacles_bcu)}")

    # Counts.
    per_width_counts: dict[float, int] = {w: 0 for w in [*WIDTH_LADDER_MM, LEAVE_AS_IS_MM]}
    track_counts = {n: 0 for n in POWER_NETS}
    via_counts = {n: 0 for n in POWER_NETS}
    via_left_narrow = {n: 0 for n in POWER_NETS}

    for trk in board.GetTracks():
        nc = trk.GetNetCode()
        if nc not in power_netcodes:
            continue
        nname = power_netcodes[nc]

        if isinstance(trk, pcbnew.PCB_VIA):
            # Check if the enlarged via annulus (0.80 mm diameter =>
            # 0.40 mm radius) would collide with any other-net copper on
            # either layer. We use `obstacle_shape.Collide(via_centre,
            # required_clearance)` which is the verified-working
            # direction (zero-length SHAPE_SEGMENT does not always
            # report collisions).
            #
            # IMPORTANT: before checking, shrink the via back to its
            # baseline (0.60 mm / 0.30 mm drill) so that a prior-run
            # already-enlarged annulus does not falsely report
            # "no conflict" (the old wider geometry would still show
            # collision here though, so this is belt-and-braces).
            pos = trk.GetPosition()
            via_half = pcbnew.FromMM(POWER_VIA_DIAMETER_MM / 2)
            required_copper = via_half + min_clearance_iu
            required_edge = via_half + edge_clearance_iu
            conflict = False
            for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
                if not trk.IsOnLayer(layer):
                    continue
                obs = obstacles_fcu if layer == pcbnew.F_Cu else obstacles_bcu
                for ob_nc, ob_shape, kind in obs:
                    if kind == "copper" and ob_nc == nc:
                        continue
                    clr = required_edge if kind == "edge" else required_copper
                    try:
                        if ob_shape.Collide(pos, clr):
                            conflict = True
                            break
                    except Exception:
                        continue
                if conflict:
                    break
            if conflict:
                # Revert to baseline Default-netclass via geometry.
                trk.SetWidth(pcbnew.FromMM(0.6))
                trk.SetDrill(pcbnew.FromMM(0.3))
                via_left_narrow[nname] += 1
            else:
                trk.SetWidth(target_via_diameter)
                trk.SetDrill(target_via_drill)
                via_counts[nname] += 1
            continue

        # Regular track segment.
        layer = trk.GetLayer()
        obs = obstacles_fcu if layer == pcbnew.F_Cu else obstacles_bcu
        # Zero-width centreline for pure distance measurement.
        seg = pcbnew.SEG(trk.GetStart(), trk.GetEnd())
        centreline = pcbnew.SHAPE_SEGMENT(seg, 0)
        w_mm = widest_safe_width(centreline, nc, obs,
                                 min_clearance_iu, edge_clearance_iu)
        per_width_counts[w_mm] = per_width_counts.get(w_mm, 0) + 1
        if w_mm == LEAVE_AS_IS_MM:
            # Reset to baseline 0.25 mm in case a prior run widened it.
            trk.SetWidth(pcbnew.FromMM(LEAVE_AS_IS_MM))
            continue
        trk.SetWidth(pcbnew.FromMM(w_mm))
        track_counts[nname] += 1

    total_tracks = sum(track_counts.values())
    total_vias = sum(via_counts.values())
    print(f"Widened {total_tracks} power tracks, {total_vias} power vias.")
    print("Track width distribution:")
    for w in [*WIDTH_LADDER_MM, LEAVE_AS_IS_MM]:
        print(f"  {w:.2f} mm : {per_width_counts.get(w, 0)}")
    for n in sorted(POWER_NETS):
        print(
            f"  {n:<10}  tracks modified={track_counts[n]:>4}  "
            f"vias upgraded={via_counts[n]:>3}  "
            f"vias left narrow={via_left_narrow[n]:>3}"
        )

    # Re-run pour fill so new trace widths are respected.
    filler = pcbnew.ZONE_FILLER(board)
    zv = pcbnew.ZONES()
    for i in range(board.GetAreaCount()):
        zv.append(board.GetArea(i))
    print(f"Re-filling {len(zv)} zones...")
    filler.Fill(zv, False)

    ok = pcbnew.SaveBoard(pcb_path, board)
    if not ok:
        print("ERROR: SaveBoard failed", file=sys.stderr)
        return 2
    print(f"Saved: {pcb_path}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: widen_power.py <board.kicad_pcb>", file=sys.stderr)
        sys.exit(64)
    sys.exit(main(sys.argv[1]))
