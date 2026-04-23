#!/usr/bin/env python3
"""Cycle 11 Iter 46: remove the 7 pre-existing informational J_XIAO_BP
global labels that my mechanical-symbol patch (Iter 38) supersedes.

Pre-existing labels at (60, 30..66) were placed by Cycle 9 generate.py
to document "net X -> XIAO back pad (user-wired)" with associated
text annotations. With the new J_XIAO_BP mechanical schematic symbol
in place (Cycle 11 Iter 38) carrying the same net labels at its pins,
the old informational labels are now duplicates that ERC flags as
dangling.

Delete the 7 global_labels and their accompanying text annotations.
"""
from __future__ import annotations

import pathlib
import re

SCH = pathlib.Path(
    "/var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/pcb/claude-code-pad.kicad_sch"
)


def main() -> int:
    text = SCH.read_text()
    # Remove each of the 7 global_label entries at their specific coords.
    # Use a regex that matches both the global_label and the nearby text.
    targets = [
        ("ROW3", "60", "30"),
        ("ROW4", "60", "36"),
        ("ENC_A", "60", "42"),
        ("ENC_B", "60", "48"),
        ("ENC_SW", "60", "54"),
        ("RGB_DIN_MCU", "60", "60"),
        ("VBAT_ADC", "60", "66"),
    ]
    removed = 0
    for name, x, y in targets:
        pattern = re.compile(
            r'\t\(global_label "' + re.escape(name) + r'" \(shape input\) \(at '
            + re.escape(x) + r' ' + re.escape(y) + r' 0\)[^\n]+\n'
            r'\t\(text "' + re.escape(name) + r' -> XIAO back pad[^"]*"[^\n]+\n'
        )
        new = pattern.sub("", text)
        if new != text:
            text = new
            removed += 1
    SCH.write_text(text)
    print(f"removed {removed} dangling informational labels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
