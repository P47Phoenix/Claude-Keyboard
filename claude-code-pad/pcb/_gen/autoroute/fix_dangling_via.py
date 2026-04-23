#!/usr/bin/env python3
"""Cycle 11 Iter 30: remove the orphan ENC_A via.

Cycle 4 Freerouting output dropped a via at (158.4250, 129.4250) for
ENC_A that does not connect to anything on either layer. Delete it.

Idempotent.
"""
from __future__ import annotations

import pathlib

import pcbnew

PCB = pathlib.Path(
    "/var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/pcb/claude-code-pad.kicad_pcb"
)


def main() -> int:
    b = pcbnew.LoadBoard(str(PCB))
    target = (pcbnew.FromMM(158.425), pcbnew.FromMM(129.425))
    tol = pcbnew.FromMM(0.005)
    to_delete = []
    for trk in b.GetTracks():
        if not isinstance(trk, pcbnew.PCB_VIA):
            continue
        p = trk.GetPosition()
        if abs(p.x - target[0]) < tol and abs(p.y - target[1]) < tol:
            to_delete.append(trk)
    for v in to_delete:
        b.Remove(v)
    print(f"removed {len(to_delete)} vias at target")
    pcbnew.SaveBoard(str(PCB), b)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
