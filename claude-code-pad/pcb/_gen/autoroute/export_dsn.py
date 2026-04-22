#!/usr/bin/env python3
"""Export Specctra DSN from a KiCad .kicad_pcb via the pcbnew Python API.

Run inside the `kicad` distrobox so pcbnew 9.0.x is importable:

    distrobox enter kicad -- python3 autoroute/export_dsn.py <pcb> <dsn>
"""
import os
import sys

import pcbnew


def main(pcb_path: str, dsn_path: str) -> int:
    pcb_path = os.path.abspath(pcb_path)
    dsn_path = os.path.abspath(dsn_path)
    if not os.path.isfile(pcb_path):
        print(f"ERROR: PCB not found: {pcb_path}", file=sys.stderr)
        return 1

    board = pcbnew.LoadBoard(pcb_path)
    print(f"Loaded board: {board.GetFileName()}")
    print(f"Nets:        {board.GetNetCount()}")
    print(f"Footprints:  {len(board.GetFootprints())}")
    print(f"Tracks:      {len(board.GetTracks())}")
    print(f"Zones:       {board.GetAreaCount()}")

    ok = pcbnew.ExportSpecctraDSN(board, dsn_path)
    if not ok:
        print("ERROR: ExportSpecctraDSN returned False", file=sys.stderr)
        return 2

    size = os.path.getsize(dsn_path) if os.path.isfile(dsn_path) else 0
    print(f"Wrote DSN: {dsn_path} ({size} bytes)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: export_dsn.py <board.kicad_pcb> <out.dsn>", file=sys.stderr)
        sys.exit(64)
    sys.exit(main(sys.argv[1], sys.argv[2]))
