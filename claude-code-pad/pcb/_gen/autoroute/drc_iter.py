#!/usr/bin/env python3
"""Cycle 11 iteration driver.

Runs kicad-cli DRC with the same flags Project Lead uses and logs
the categorical breakdown per iteration. Pass an iteration number
to save as drc-iter-N.rpt.

Usage:  python3 drc_iter.py N            -> run + label the report.
        python3 drc_iter.py N diff M     -> compare iter N to iter M counts.
"""

from __future__ import annotations

import collections
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PCB = ROOT / "claude-code-pad.kicad_pcb"
GEN = ROOT / "_gen"
CLI = ["flatpak", "run", "--command=kicad-cli", "org.kicad.KiCad"]


def run_drc(report: pathlib.Path) -> str:
    report.parent.mkdir(parents=True, exist_ok=True)
    cmd = CLI + [
        "pcb", "drc",
        "--schematic-parity", "--severity-all",
        "--output", str(report), str(PCB),
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return out.stdout + out.stderr


def categorise(report: pathlib.Path) -> collections.Counter:
    text = report.read_text(encoding="utf-8", errors="replace")
    return collections.Counter(re.findall(r"\[([a-z_]+)\]", text))


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    n = int(argv[1])
    report = GEN / f"drc-iter-{n}.rpt"
    if len(argv) >= 4 and argv[2] == "diff":
        m = int(argv[3])
        prev = GEN / f"drc-iter-{m}.rpt"
        a = categorise(prev)
        b = categorise(report)
        keys = sorted(set(a) | set(b))
        print(f"{'category':35s} {m:>7} {n:>7}  delta")
        for k in keys:
            da, db = a[k], b[k]
            delta = db - da
            mark = ""
            if delta < 0:
                mark = "  -->"
            elif delta > 0:
                mark = "  !! REGRESSION"
            print(f"{k:35s} {da:>7} {db:>7}  {delta:+d}{mark}")
        return 0
    print(run_drc(report).strip().splitlines()[-3:])
    cats = categorise(report)
    total = sum(cats.values())
    print(f"iter {n}: total={total}")
    for k, v in cats.most_common():
        print(f"  {v:>4}  {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
