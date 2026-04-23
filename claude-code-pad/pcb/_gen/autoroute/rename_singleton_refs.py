#!/usr/bin/env python3
"""Cycle 10: rename 14 singleton references to canonical `_1` suffix form.

Context
-------
KiCad's standard annotation policy assigns every component (including
single-instance ones) a numeric suffix. ECE-1's Cycle 1..9 schematic
emitter produced bare names (e.g. `C_ENC`, `J_BAT`, `TVS_SDA`) for
singleton parts. The KiCad 10 GUI auto-annotates these on open and
reports them as `missing_footprint <ref>1` (14 entries) until the
files are updated on disk.

Cycle 10 fix (surgical, in place):
  * Every `(property "Reference" "<name>")` -> "<name>1"
  * Every `(reference "<name>")` inside schematic `(path ...)` forms
    -> `(reference "<name>1")`
  * `bom.csv` + `cpl.csv` designator columns updated to match.

UUIDs are preserved verbatim. Freerouting output (1095 segments + 250
vias) is untouched. The generator (`generate.py`) is updated in a
second edit pass so future regenerations emit the suffixed refs
directly.

Usage
-----
    python3 autoroute/rename_singleton_refs.py <pcb_dir>

Idempotent: a ref already ending in a digit is skipped. Re-running is
safe (no `_11` / `_12` cascade).
"""
from __future__ import annotations
import re
import sys
from pathlib import Path


# Definitive rename map -- enumerated from DRC.rpt [missing_footprint]
# rows + grep of the schematic for unsuffixed instance Reference
# properties. Mechanical-only footprints (H1-4, FID1-3, TP1-2,
# J_XIAO_BP, TH1) already carry numeric suffixes or are PCB-only
# mechanical items that will stay in the `extra_footprint` residual
# list until Rev-B promotes them to schematic symbols.
SINGLETONS: tuple[str, ...] = (
    "C_ENC",
    "C_VBAT",
    "D_GREV",
    "J_BAT",
    "J_NFC",
    "Q_REV",
    "R_GREV",
    "R_NTC",
    "SW_PWR",
    "TVS_ENCA",
    "TVS_ENCB",
    "TVS_ENCSW",
    "TVS_SCL",
    "TVS_SDA",
)


def rename_text(text: str, names: tuple[str, ...]) -> tuple[str, int]:
    """Return (new_text, total_replacements) for both:
       (property "Reference" "<name>")
       (reference "<name>")
    """
    total = 0
    for n in names:
        # (property "Reference" "<name>")  -- used in .kicad_sch AND .kicad_pcb
        pat1 = re.compile(r'\(property\s+"Reference"\s+"' + re.escape(n) + r'"')
        new1 = '(property "Reference" "' + n + '1"'
        text, k1 = pat1.subn(new1, text)

        # (reference "<name>")  -- used inside schematic (path ...) forms
        pat2 = re.compile(r'\(reference\s+"' + re.escape(n) + r'"\)')
        new2 = '(reference "' + n + '1")'
        text, k2 = pat2.subn(new2, text)

        total += k1 + k2
        print(f"  {n:12s} -> {n+'1':13s}  ({k1} property + {k2} path = {k1+k2})")
    return text, total


def rename_csv_designators(text: str, names: tuple[str, ...]) -> tuple[str, int]:
    """Rename bare <name> designators in BOM/CPL CSV cells.

    Matches only whole-word occurrences (bounded by `,` or `"` on
    both sides) so we never touch substring matches (e.g. "J_BATT").
    """
    total = 0
    for n in names:
        # Bounded by non-word chars [",] on both sides.
        pat = re.compile(r'(?P<pre>[,"])' + re.escape(n) + r'(?P<post>[,"])')
        rep = lambda m, nn=n: m.group("pre") + nn + "1" + m.group("post")
        text, k = pat.subn(rep, text)
        total += k
    return text, total


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: rename_singleton_refs.py <pcb_dir>", file=sys.stderr)
        return 2
    pcb_dir = Path(sys.argv[1]).resolve()

    sch_p = pcb_dir / "claude-code-pad.kicad_sch"
    pcb_p = pcb_dir / "claude-code-pad.kicad_pcb"
    bom_p = pcb_dir / "bom.csv"
    cpl_p = pcb_dir / "cpl.csv"

    for p in (sch_p, pcb_p, bom_p, cpl_p):
        if not p.is_file():
            print(f"missing: {p}", file=sys.stderr)
            return 2

    print(f"[schematic] {sch_p}")
    sch_txt = sch_p.read_text()
    sch_new, n_sch = rename_text(sch_txt, SINGLETONS)
    sch_p.write_text(sch_new)
    print(f"  total: {n_sch} replacements")

    print(f"[pcb] {pcb_p}")
    pcb_txt = pcb_p.read_text()
    pcb_new, n_pcb = rename_text(pcb_txt, SINGLETONS)
    pcb_p.write_text(pcb_new)
    print(f"  total: {n_pcb} replacements")

    print(f"[bom] {bom_p}")
    bom_txt = bom_p.read_text()
    bom_new, n_bom = rename_csv_designators(bom_txt, SINGLETONS)
    bom_p.write_text(bom_new)
    print(f"  total: {n_bom} replacements")

    print(f"[cpl] {cpl_p}")
    cpl_txt = cpl_p.read_text()
    cpl_new, n_cpl = rename_csv_designators(cpl_txt, SINGLETONS)
    cpl_p.write_text(cpl_new)
    print(f"  total: {n_cpl} replacements")

    # Sanity: expected 14 property + 14 path = 28 in schematic; 14
    # property + 0 path = 14 in PCB.
    ok = (n_sch == 28) and (n_pcb == 14)
    print()
    print(f"schematic: {n_sch}  (expected 28)")
    print(f"pcb:       {n_pcb}  (expected 14)")
    print(f"bom:       {n_bom}  (expected 14)")
    print(f"cpl:       {n_cpl}  (expected 14)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
