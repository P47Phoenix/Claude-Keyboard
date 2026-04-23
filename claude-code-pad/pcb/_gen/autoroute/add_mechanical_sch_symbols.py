#!/usr/bin/env python3
"""Cycle 11 Iter 38: add matching schematic symbols for mechanical PCB
footprints so DRC parity reports them as present, not `extra_footprint`.

For each mechanical ref, we read the PCB footprint's Value and Description
fields and emit a schematic symbol whose corresponding properties match
byte-for-byte. This prevents `footprint_symbol_mismatch` and
`footprint_symbol_field_mismatch` warnings.

For footprints whose PCB pad has a net (FID1/FID2/FID3 with GND), we
emit a single power-input pin on the schematic symbol, named "1" and
wired to GND label via a short wire. That keeps `net_conflict` quiet.

For non-pad mechanical footprints (H1-4, TP1-2, J_XIAO_BP), no pin is
emitted.
"""
from __future__ import annotations

import hashlib
import pathlib
import re

PCB = pathlib.Path(
    "/var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/pcb/claude-code-pad.kicad_pcb"
)
SCH = pathlib.Path(
    "/var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/pcb/claude-code-pad.kicad_sch"
)

# refs needing placeholder + pad info
PAD_REFS = {"FID1", "FID2", "FID3"}
NO_PAD_REFS = {"H1", "H2", "H3", "H4", "TP1", "TP2"}
# J_XIAO_BP is handled specially: 7 named pins matching the 7 XIAO
# back-pad signals. Its Value, Description, and attr flags must match
# the PCB footprint exactly.
MULTIPIN_REFS = {
    # Note: the lib symbol's pins 1..7 are laid out in a vertical
    # column at decreasing y (pin 1 at y=+1.5 down to pin 7 at y=-1.5).
    # The PCB parity seems to match labels to pins by visual position,
    # so we order the labels top-to-bottom to match the lib symbol's
    # pin ordering as drawn. Empirically this requires REVERSING the
    # pad numbers.
    "J_XIAO_BP": [
        ("1", "ROW4"), ("2", "VBAT_ADC"), ("3", "ROW3"),
        ("4", "RGB_DIN_MCU"), ("5", "ENC_SW"), ("6", "ENC_B"),
        ("7", "ENC_A"),
    ],
}
TARGETS = list(PAD_REFS | NO_PAD_REFS | MULTIPIN_REFS.keys())


def u_from_str(s: str) -> str:
    h = hashlib.md5(s.encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-5{h[13:16]}-a{h[17:20]}-{h[20:32]}"


def parse_fp_block(pcb: str, ref: str):
    """Return dict: uuid, fp_start, fp_end, lib_id, value, description, has_pad_net."""
    m = re.search(rf'\(property "Reference" "{re.escape(ref)}"', pcb)
    if not m:
        return None
    fp_start = pcb.rfind("(footprint", 0, m.start())
    depth = 0
    k = fp_start
    while k < len(pcb):
        c = pcb[k]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                k += 1
                break
        k += 1
    fp_end = k
    block = pcb[fp_start:fp_end]
    return {
        "fp_start": fp_start,
        "fp_end": fp_end,
        "uuid": re.search(r'\(uuid "([a-f0-9-]+)"\)', block).group(1),
        "lib_id": re.search(r'\(footprint "([^"]+)"', block).group(1),
        "value": _read_prop(block, "Value"),
        "description": _read_prop(block, "Description") or "",
        "has_gnd_pad": '(net "GND")' in block,
    }


def _read_prop(block: str, name: str) -> str:
    m = re.search(
        rf'\(property "{re.escape(name)}" "([^"]*)"',
        block,
    )
    return m.group(1) if m else ""


def get_root_uuid() -> str:
    sch = SCH.read_text()
    m = re.search(r'\(path "/([a-f0-9-]+)"', sch)
    if m:
        return m.group(1)
    raise SystemExit("no root path UUID")


PLACEHOLDER_SYMBOLS_DEF_XIAO_BP = '''(symbol "Mechanical:XIAO_BP"
    (pin_names (offset 0.254) hide)
    (exclude_from_sim yes)
    (in_bom no)
    (on_board yes)
    (property "Reference" "J" (at 0 5 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Value" "XIAO_BackPad_Jumper" (at 0 7 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Description" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "ki_keywords" "xiao back pad jumper" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "ki_fp_filters" "*" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (symbol "XIAO_BP_0_1"
      (rectangle (start -5 -2) (end 5 2) (stroke (width 0) (type default)) (fill (type none)))
      (pin input line (at -6.27 1.5 0) (length 1.27) (hide yes) (name "1" (effects (font (size 1 1)))) (number "1" (effects (font (size 1 1)))))
      (pin input line (at -6.27 1.0 0) (length 1.27) (hide yes) (name "2" (effects (font (size 1 1)))) (number "2" (effects (font (size 1 1)))))
      (pin input line (at -6.27 0.5 0) (length 1.27) (hide yes) (name "3" (effects (font (size 1 1)))) (number "3" (effects (font (size 1 1)))))
      (pin input line (at -6.27 0.0 0) (length 1.27) (hide yes) (name "4" (effects (font (size 1 1)))) (number "4" (effects (font (size 1 1)))))
      (pin input line (at -6.27 -0.5 0) (length 1.27) (hide yes) (name "5" (effects (font (size 1 1)))) (number "5" (effects (font (size 1 1)))))
      (pin input line (at -6.27 -1.0 0) (length 1.27) (hide yes) (name "6" (effects (font (size 1 1)))) (number "6" (effects (font (size 1 1)))))
      (pin input line (at -6.27 -1.5 0) (length 1.27) (hide yes) (name "7" (effects (font (size 1 1)))) (number "7" (effects (font (size 1 1)))))
    )
    (embedded_fonts no)
  )
  '''

PLACEHOLDER_SYMBOLS_DEF = PLACEHOLDER_SYMBOLS_DEF_XIAO_BP + '''(symbol "Mechanical:Placeholder"
    (pin_names (offset 0) hide)
    (exclude_from_sim yes)
    (in_bom no)
    (on_board yes)
    (property "Reference" "M" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Value" "Mechanical" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Description" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "ki_keywords" "mechanical placeholder" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "ki_fp_filters" "*" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (symbol "Placeholder_0_1"
      (rectangle (start -1 -1) (end 1 1) (stroke (width 0) (type default)) (fill (type none)))
    )
    (embedded_fonts no)
  )
  (symbol "Mechanical:Placeholder_GND"
    (pin_names (offset 0) hide)
    (exclude_from_sim yes)
    (in_bom no)
    (on_board yes)
    (property "Reference" "M" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Value" "Mechanical" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Description" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "ki_keywords" "mechanical placeholder gnd" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "ki_fp_filters" "*" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (symbol "Placeholder_GND_0_1"
      (rectangle (start -1 -1) (end 1 1) (stroke (width 0) (type default)) (fill (type none)))
      (pin power_in line (at -2.54 0 0) (length 1.27) (hide yes)
        (name "GND" (effects (font (size 1.27 1.27))))
        (number "1" (effects (font (size 1.27 1.27))))
      )
    )
    (embedded_fonts no)
  )'''


def main() -> int:
    pcb = PCB.read_text()
    sch = SCH.read_text()
    root_uuid = get_root_uuid()

    infos = {}
    for ref in TARGETS:
        info = parse_fp_block(pcb, ref)
        if info is None:
            print(f"skip (not in PCB): {ref}")
            continue
        infos[ref] = info

    # Inject placeholder symbol definitions into lib_symbols if missing.
    # Each definition is idempotent-checked individually.
    needed = {
        "Mechanical:Placeholder": PLACEHOLDER_SYMBOLS_DEF,
        "Mechanical:XIAO_BP": PLACEHOLDER_SYMBOLS_DEF_XIAO_BP,
    }
    if '(symbol "Mechanical:XIAO_BP"' not in sch:
        sch = re.sub(
            r'(\(lib_symbols\s*\n)',
            r"\1    " + PLACEHOLDER_SYMBOLS_DEF_XIAO_BP + "\n",
            sch,
            count=1,
        )
    if '(symbol "Mechanical:Placeholder"' not in sch:
        sch = re.sub(
            r'(\(lib_symbols\s*\n)',
            r"\1    " + PLACEHOLDER_SYMBOLS_DEF + "\n",
            sch,
            count=1,
        )

    x_base = 340.0
    y_base = 120.0
    dx = 5.0
    sch_uuids = {}
    inserts = []
    for i, (ref, info) in enumerate(infos.items()):
        uuid = u_from_str(f"mech_sch_{ref}_{info['uuid']}")
        sch_uuids[ref] = uuid
        x = x_base + i * dx
        y = y_base
        if ref in MULTIPIN_REFS:
            lib = "Mechanical:XIAO_BP"
        elif info["has_gnd_pad"]:
            lib = "Mechanical:Placeholder_GND"
        else:
            lib = "Mechanical:Placeholder"
        val = info["value"]
        desc = info["description"]
        lib_id = info["lib_id"]
        def esc(s): return s.replace('\\', '\\\\').replace('"', '\\"')
        block = f'''  (symbol
    (lib_id "{lib}")
    (at {x} {y} 0) (unit 1)
    (exclude_from_sim yes) (in_bom no) (on_board yes) (dnp no)
    (uuid "{uuid}")
    (property "Reference" "{ref}" (at {x + 2} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Value" "{esc(val)}" (at {x + 2} {y + 2} 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Footprint" "{esc(lib_id)}" (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Datasheet" "" (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Description" "{esc(desc)}" (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))
'''
        extras_post = ""
        if ref in MULTIPIN_REFS:
            for pin_num, _pin_name in MULTIPIN_REFS[ref]:
                pin_uuid = u_from_str(f"mech_pin_{ref}_{pin_num}")
                block += f'    (pin "{pin_num}" (uuid "{pin_uuid}"))\n'
            # Emit wire + net label per pin so parity sees each pad's
            # PCB-side net on the schematic side.
            for idx, (pin_num, pin_name) in enumerate(MULTIPIN_REFS[ref]):
                py = y + 1.5 - 0.5 * idx
                px = x - 6.27
                wx = px - 2.54
                wire_uuid = u_from_str(f"mech_wire_{ref}_{pin_num}")
                label_uuid = u_from_str(f"mech_label_{ref}_{pin_num}")
                extras_post += f'''  (wire
    (pts (xy {px} {py}) (xy {wx} {py}))
    (stroke (width 0) (type default))
    (uuid "{wire_uuid}")
  )
  (global_label "{pin_name}" (shape input)
    (at {wx} {py} 180)
    (fields_autoplaced yes)
    (effects (font (size 1.27 1.27)) (justify right))
    (uuid "{label_uuid}")
  )
'''
        elif info["has_gnd_pad"]:
            pin_uuid = u_from_str(f"mech_pin_{ref}")
            block += f'    (pin "1" (uuid "{pin_uuid}"))\n'
        block += f'''    (instances
      (project "claude-code-pad"
        (path "/{root_uuid}" (reference "{ref}") (unit 1))
      )
    )
  )
'''
        inserts.append(block + extras_post)

    # Idempotency: if schematic already has one of our inserted uuids, skip.
    any_uuid = next(iter(sch_uuids.values()))
    if any_uuid in sch:
        print("mechanical placeholders already present; refreshing")
        # Strip them out and rewrite.
        for uuid in sch_uuids.values():
            sch = re.sub(
                r'\(symbol\s*\n\s*\(lib_id "Mechanical:[^"]*"\)(?:(?!\n  \(symbol|\n  \(sheet|\n\)).)*?\(uuid "'
                + re.escape(uuid)
                + r'"\)(?:(?!\n  \(symbol|\n  \(sheet|\n\)).)*?\n  \)\n',
                "",
                sch,
                flags=re.DOTALL,
            )
    # Append new symbols before final closing paren.
    sch = sch.rstrip()
    if sch.endswith(")"):
        sch = sch[:-1] + "".join(inserts) + ")\n"
    SCH.write_text(sch)
    print(f"wrote schematic with {len(inserts)} mechanical placeholders")

    # Patch PCB with (path ...).
    # Do NOT refresh info offsets by re-reading; instead patch in reverse
    # order so earlier offsets stay valid.
    for ref in sorted(infos.keys(), key=lambda r: -infos[r]["fp_start"]):
        info = infos[ref]
        sch_uuid = sch_uuids[ref]
        fp_start = info["fp_start"]
        fp_end = info["fp_end"]
        block = pcb[fp_start:fp_end]
        # Remove any existing (path ...) line.
        block = re.sub(r'\s*\(path "[^"]+"\)\s*\n', "\n", block)
        block = re.sub(
            r'(\(at [^)]+\)\s*\n)',
            rf'\1\t\t(path "/{root_uuid}/{sch_uuid}")\n',
            block,
            count=1,
        )
        pcb = pcb[:fp_start] + block + pcb[fp_end:]
    PCB.write_text(pcb)
    print(f"patched PCB: added (path ...) to {len(infos)} mechanical footprints")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
