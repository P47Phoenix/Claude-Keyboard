#!/usr/bin/env python3
"""Import a Freerouting Specctra .ses session back into a KiCad .kicad_pcb
and refill zones using the pcbnew Python API.

    distrobox enter kicad -- python3 autoroute/import_ses.py <pcb> <ses>
"""
import os
import sys

import pcbnew


def refill_zones(board: "pcbnew.BOARD") -> None:
    filler = pcbnew.ZONE_FILLER(board)
    zones = [board.GetArea(i) for i in range(board.GetAreaCount())]
    # ZONE_FILLER.Fill takes a vector of zones.
    zv = pcbnew.ZONES()
    for z in zones:
        zv.append(z)
    # The second argument (check_fill) must be False for a one-shot fill.
    filler.Fill(zv, False)


def main(pcb_path: str, ses_path: str) -> int:
    pcb_path = os.path.abspath(pcb_path)
    ses_path = os.path.abspath(ses_path)
    for p in (pcb_path, ses_path):
        if not os.path.isfile(p):
            print(f"ERROR: not found: {p}", file=sys.stderr)
            return 1

    board = pcbnew.LoadBoard(pcb_path)
    print(f"Loaded board: {board.GetFileName()}")
    print(f"Tracks before import: {len(board.GetTracks())}")

    ok = pcbnew.ImportSpecctraSES(board, ses_path)
    if not ok:
        print("ERROR: ImportSpecctraSES returned False", file=sys.stderr)
        return 2

    print(f"Tracks after import:  {len(board.GetTracks())}")

    # Refill GND pours so unconnected GND pads get polygon-filled copper.
    print("Refilling zones...")
    try:
        refill_zones(board)
    except Exception as exc:  # pragma: no cover
        print(f"WARN: zone fill raised {exc!r}; continuing", file=sys.stderr)

    ok = pcbnew.SaveBoard(pcb_path, board)
    if not ok:
        print("ERROR: SaveBoard returned False", file=sys.stderr)
        return 3
    print(f"Saved board: {pcb_path}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: import_ses.py <board.kicad_pcb> <session.ses>", file=sys.stderr)
        sys.exit(64)
    sys.exit(main(sys.argv[1], sys.argv[2]))
