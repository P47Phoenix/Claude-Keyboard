#!/usr/bin/env python3
"""Cycle 9 B1: EC1 pin-map verification stub (the actual fix lives in
generate.py).

The PCB-side EC1 footprint pad-to-net map was already correct (per the
canonical Alps EC11E pinout, datasheet
https://www.lcsc.com/datasheet/C255515.pdf). The bug was on the
SCHEMATIC side: `generate.py`'s EC11 `sym_def` placed the encoder
pins with lib-Y-up coordinates, but the wire/global-label emitter
treated the same coordinates as sheet-Y-down. Net result: KiCad
resolved ENC_A onto pad 3 (B), ENC_B onto pad 1 (A), ENC_SW onto pad
5 (GND), and GND onto pad 4 (SW).

The Cycle 9 fix in `generate.py`:
  1. Inverts the Y signs on EC11 pins 1, 3, 4, 5 in the sym_def so
     the symbol pin sheet positions align with the wire emitter.
  2. Adds two new symbol pins `MP1` and `MP2` (both tied to GND) so
     the PCB's mounting-lug pads (also `MP1` / `MP2`) have schematic
     counterparts. This closes the two
     `[net_conflict]: No corresponding pin found in schematic`
     warnings on the EC1 lugs.
  3. Generalises `sch_symbol`'s pin emitter to accept alphanumeric
     pin numbers (so `MP1` / `MP2` work).

After re-running `python3 _gen/generate.py` the schematic netlist
shows EC1 pin 1 -> ENC_A, pin 2 -> GND, pin 3 -> ENC_B, pin 4 ->
ENC_SW, pin 5 -> GND, pin MP1 -> GND, pin MP2 -> GND.

The PCB-side footprint (`fp_ec11`) was untouched -- its existing
pad-net assignments are correct and the routed traces are preserved.

This script verifies the fix took effect; it makes no changes.

Usage:
  python3 autoroute/fix_ec11_pinmap.py <schematic.kicad_sch>
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


EXPECTED = {
    "1":   "ENC_A",
    "2":   "GND",
    "3":   "ENC_B",
    "4":   "ENC_SW",
    "5":   "GND",
    "MP1": "GND",
    "MP2": "GND",
}


def main(sch_path: str) -> int:
    # Use kicad-cli to extract the netlist as XML. The flatpak
    # kicad-cli has filesystem=home access only -- write the temp XML
    # under $HOME, not /tmp.
    import os
    out_dir = os.path.expanduser("~/.cache/cycle9-ec11-check")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "netlist.xml")
    cmd = [
        "flatpak", "run", "--command=kicad-cli", "org.kicad.KiCad",
        "sch", "export", "netlist",
        "--output", out_path,
        "--format", "kicadxml",
        sch_path,
    ]
    subprocess.run(cmd, check=False, capture_output=True)

    root = ET.parse(out_path).getroot()
    actual = {}
    for net in root.findall(".//net"):
        for node in net.findall("node"):
            if node.get("ref") == "EC1":
                actual[node.get("pin")] = net.get("name")

    print("EC1 pin -> net (actual vs expected):")
    bad = 0
    for pin, want in EXPECTED.items():
        got = actual.get(pin, "<missing>")
        ok = "OK" if got == want else "MISMATCH"
        print(f"  pin {pin:3s} : {got:20s} (expected {want}) {ok}")
        if got != want:
            bad += 1
    if bad:
        print(f"FAIL: {bad} EC1 pins do not match expected pinout.")
        return 1
    print("PASS: all EC1 pins match the canonical Alps EC11E pinout.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
