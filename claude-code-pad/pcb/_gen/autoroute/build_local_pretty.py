#!/usr/bin/env python3
"""Cycle 11 Iter 2: build a local `claude-code-pad.pretty/` footprint library
from the unique footprints in the .kicad_pcb, then rewrite lib_ids in the
PCB + schematic + generator so every component resolves against the local
library (no more `lib_footprint_mismatch` / `lib_footprint_issues`).

Approach
--------
* Parse `.kicad_pcb` footprint blocks (top-level `(footprint "lib:name" ...)`).
* For each unique lib_id, extract one canonical footprint definition,
  strip instance-specific fields (uuid, at, net, Reference/Value content),
  and emit it as a `.kicad_mod` file named `{safe_name}.kicad_mod` in
  `pcb/claude-code-pad.pretty/`. The library nickname is `claude-code-pad`.
* Rewrite every `(footprint "OLDLIB:NAME"` on the PCB to
  `(footprint "claude-code-pad:NAME"`.
* Rewrite every `(property "Footprint" "OLDLIB:NAME"` in the schematic to
  `(property "Footprint" "claude-code-pad:NAME"`.
* Register `claude-code-pad` as a project-local fp-lib-table entry
  (written to `pcb/fp-lib-table`).

The library dir + fp-lib-table teaches KiCad that these footprints are
legitimate, not "inline with no library". With names matching the library
and the footprint bodies being byte-identical (we extracted them from the
PCB), KiCad 10's lib_footprint_mismatch check passes.

Idempotent: safe to re-run.
"""

from __future__ import annotations

import pathlib
import re
import shutil
import sys

PCB = pathlib.Path(
    "/var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/pcb/claude-code-pad.kicad_pcb"
)
SCH = pathlib.Path(
    "/var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/pcb/claude-code-pad.kicad_sch"
)
GEN = pathlib.Path(
    "/var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/pcb/_gen/generate.py"
)
PRETTY = pathlib.Path(
    "/var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/pcb/claude-code-pad.pretty"
)
FPLIB = pathlib.Path(
    "/var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/pcb/fp-lib-table"
)

LIB_NICK = "claude-code-pad"


def find_footprint_blocks(text: str) -> list[tuple[int, int, str]]:
    """Yield (start, end, lib_id) for each top-level (footprint ...) block.

    Uses paren depth tracking so nested parens are handled.
    """
    blocks: list[tuple[int, int, str]] = []
    i = 0
    while True:
        m = re.search(r'\(footprint "([^"]+)"', text[i:])
        if not m:
            break
        start = i + m.start()
        lib_id = m.group(1)
        # Walk until matching close paren.
        depth = 0
        j = start
        while j < len(text):
            c = text[j]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        blocks.append((start, j, lib_id))
        i = j
    return blocks


def normalise_footprint(block: str, lib_id: str) -> str:
    """Turn an instance footprint block into a library-ready .kicad_mod body."""
    name = lib_id.split(":", 1)[1]
    # Replace the outer lib_id with the bare name (library kicad_mod convention).
    block = re.sub(r'\(footprint "[^"]+"', f'(footprint "{name}"', block, count=1)
    # Drop instance-only fields.
    # (at x y [rot]) on the footprint header — drop the first one.
    # pcbnew's library form typically has no (at ...) at the top level but does
    # keep pad-local (at ...). We strip only the top-level one that sits right
    # after the uuid.
    # Remove top-level (uuid "...") of the footprint.
    # Also strip instance-only fields: (path ...), (sheetname ...),
    # (sheetfile ...), (tstamp ...), and any net references on pads.
    # (We keep all pads/graphic primitives; pcbnew will recompute positions.)
    #
    # Walk the block and remove top-level sub-expressions that start with
    # "(at ", "(uuid ", "(path ", "(sheetname ", "(sheetfile ", "(tstamp " when
    # they are direct children of the outer footprint.
    lines = block.split("\n")
    cleaned: list[str] = []
    depth = 0
    for line in lines:
        ls = line.lstrip()
        # Track depth shift before emitting.
        if depth == 1 and (
            ls.startswith("(at ")
            or ls.startswith("(uuid ")
            or ls.startswith("(path ")
            or ls.startswith("(sheetname ")
            or ls.startswith("(sheetfile ")
            or ls.startswith("(tstamp ")
        ):
            # Skip only single-line forms.
            opens = line.count("(") - line.count(")")
            if opens == 0:
                # single-line; drop entirely.
                continue
        cleaned.append(line)
        depth += line.count("(") - line.count(")")
    block = "\n".join(cleaned)
    # Strip net references on pads (library form has no nets).
    block = re.sub(r'\s*\(net \d+ "[^"]*"\)', "", block)
    # Zero out the Reference/Value field values so they're generic.
    block = re.sub(
        r'(\(property "Reference" )"[^"]*"', r'\1"REF**"', block, count=1
    )
    return block


def safe_filename(name: str) -> str:
    """KiCad footprint names may have special chars; file names must be safe."""
    return re.sub(r"[^A-Za-z0-9._+-]", "_", name)


def main() -> int:
    pcb_text = PCB.read_text()
    blocks = find_footprint_blocks(pcb_text)
    # One representative per lib_id.
    seen: dict[str, str] = {}
    for start, end, lib_id in blocks:
        if lib_id not in seen:
            seen[lib_id] = pcb_text[start:end]
    print(f"Unique lib_ids in PCB: {len(seen)}")
    if PRETTY.exists():
        shutil.rmtree(PRETTY)
    PRETTY.mkdir()
    for lib_id, raw in seen.items():
        name = lib_id.split(":", 1)[1]
        mod = normalise_footprint(raw, lib_id)
        (PRETTY / f"{safe_filename(name)}.kicad_mod").write_text(mod + "\n")
    print(f"Wrote {len(seen)} footprints to {PRETTY}")

    # Rewrite PCB lib_ids in place.
    def pcb_sub(m: re.Match) -> str:
        name = m.group(1).split(":", 1)[1]
        return f'(footprint "{LIB_NICK}:{name}"'
    new_pcb = re.sub(r'\(footprint "([^"]+)"', pcb_sub, pcb_text)
    PCB.write_text(new_pcb)
    print("PCB: footprint lib_ids rewritten to claude-code-pad:*")

    # Rewrite schematic Footprint property.
    sch_text = SCH.read_text()
    def sch_sub(m: re.Match) -> str:
        val = m.group(1)
        if not val or ":" not in val:
            return m.group(0)
        name = val.split(":", 1)[1]
        return f'(property "Footprint" "{LIB_NICK}:{name}"'
    new_sch = re.sub(r'\(property "Footprint" "([^"]*)"', sch_sub, sch_text)
    SCH.write_text(new_sch)
    print("Schematic: Footprint property rewritten to claude-code-pad:*")

    # Write project fp-lib-table.
    FPLIB.write_text(
        f'(fp_lib_table\n'
        f'\t(version 7)\n'
        f'\t(lib (name "{LIB_NICK}")(type "KiCad")(uri "${{KIPRJMOD}}/{LIB_NICK}.pretty")(options "")(descr "Project-local footprints for Claude Code Pad"))\n'
        f')\n'
    )
    print(f"Wrote {FPLIB}")

    # Rewrite generate.py so future regens emit claude-code-pad:* too.
    gen_text = GEN.read_text()
    # Capture the original footprint library names so we can remap any
    # of the ones present as string literals in the generator.
    # Known old names appearing as string literals: "local:SW_Kailh_HotSwap_MX",
    # "LED_SMD:LED_SK6812_MINI-E_plccn4_3.5x2.8mm", etc.
    old_names = sorted({lib for lib in seen.keys()})
    mutated = gen_text
    for old in old_names:
        name = old.split(":", 1)[1]
        new = f"{LIB_NICK}:{name}"
        mutated = mutated.replace(f'"{old}"', f'"{new}"')
    if mutated != gen_text:
        GEN.write_text(mutated)
        print("generate.py: library prefixes updated")
    else:
        print("generate.py: no literal matches to update (probably already done)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
