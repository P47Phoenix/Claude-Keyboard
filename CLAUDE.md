# Claude-Keyboard — Project Notes for Claude

## What this repo is

The "Claude Code Pad" — a 25-key macropad companion for Claude Code terminal sessions. Features: TinyML callouts, OLED, per-key RGB (SK6812MINI-E reverse-mount), hot-swap MX, EC11 rotary encoder, 2U stabilized Enter, RFID artisan keycap figurines.

Source of truth for the full design spec and workflow: `/var/home/meconnelly/Downloads/claude-code-pad-orchestrated-prompt.md`. Project work lives under `claude-code-pad/`.

## Orchestration model

Work is done by **persona sub-agents** dispatched via the Agent tool, not by the main thread. Each phase runs:

1. Primary persona produces deliverables (e.g., ECE-1 for PCB, MECH-1 for case, FW-1 for firmware, ML-1 for TinyML).
2. Adversarial reviewers (RED-DFM, RED-SAFETY, RED-MECH, RED-FW, RED-ML, RED-COST) critique in parallel.
3. Primary persona iterates until BLOCKER/MAJOR issues clear.
4. Cycle is logged in `claude-code-pad/docs/review-log.md`.

The main thread is **Project Lead**: orchestrate, integrate, arbitrate — do not do specialist work directly.

## Host OS: Bazzite (immutable Fedora atomic)

Package management is **not** traditional `dnf install`. Options in order of preference for this repo:

- **Flatpak** — for GUI apps (KiCad is here already).
- **Distrobox** — mutable Fedora containers for dev tooling that needs dnf packages or Python bindings unavailable on the host. Command: `distrobox create -n <name> -i fedora-toolbox:41`, then `distrobox enter <name>`. Installed and ready (v1.8.2.4).
- **Homebrew** — user-space packages (already on PATH at `/home/linuxbrew/.linuxbrew/bin`).
- **`rpm-ostree install <pkg>`** — last resort, layers onto the immutable base, **requires reboot**. Uninstall is `rpm-ostree remove <pkg>` + reboot. Avoid unless no alternative.
- **`uv` / `pipx`** — user-space Python, works normally.

Never run `sudo dnf install` — it will fail or silently no-op on the atomic base.

## KiCad

**Installed as Flatpak:** `org.kicad.KiCad` 10.0.1 (plus Footprints, Packages3D, Symbols, Templates library flatpaks).

**`kicad-cli` is NOT on PATH.** Invoke via:
```bash
flatpak run --command=kicad-cli org.kicad.KiCad <subcommand> [args...]
```

Subcommands: `fp` (footprints), `jobset`, `pcb` (plot gerbers, drill, DRC, pos), `sch` (ERC, export netlist, export BOM), `sym`.

**Filesystem access:** the flatpak has `filesystems=home`, so it can read/write anywhere under `$HOME` — including this repo. No portal dance needed.

**Launching the GUI:** `flatpak run org.kicad.KiCad` opens the KiCad project manager. `flatpak run --command=pcbnew org.kicad.KiCad` / `eeschema` etc. open the individual tools.

### Common non-interactive tasks

```bash
# ERC on schematic
flatpak run --command=kicad-cli org.kicad.KiCad sch erc --output erc.rpt claude-code-pad.kicad_sch

# DRC on board
flatpak run --command=kicad-cli org.kicad.KiCad pcb drc --output drc.rpt claude-code-pad.kicad_pcb

# Plot gerbers (JLCPCB settings)
flatpak run --command=kicad-cli org.kicad.KiCad pcb export gerbers \
  --output gerbers/ \
  --layers "F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts" \
  --use-drill-file-origin \
  claude-code-pad.kicad_pcb

# Drill files (Excellon, 2:4 metric)
flatpak run --command=kicad-cli org.kicad.KiCad pcb export drill \
  --output gerbers/ --format excellon --drill-origin plot \
  --excellon-units mm --excellon-zeros-format decimal \
  claude-code-pad.kicad_pcb

# Position file (CPL) for JLCPCB
flatpak run --command=kicad-cli org.kicad.KiCad pcb export pos \
  --output cpl.csv --format csv --units mm --side both --use-drill-file-origin \
  claude-code-pad.kicad_pcb

# BOM export
flatpak run --command=kicad-cli org.kicad.KiCad sch export bom \
  --output bom.csv claude-code-pad.kicad_sch
```

### KiCad MCP

Installed: `lamaalrajih/kicad-mcp` (v0.1.0) running inside the `kicad` distrobox (Podman-backed Fedora 43 toolbox).

- MCP source: `~/.local/share/kicad-mcp/` (shared $HOME, visible host and container)
- Entry point inside container: `~/.local/share/kicad-mcp/.venv/bin/kicad-mcp`
- Registered in project `.mcp.json` at repo root — Claude Code auto-loads it when working in this directory
- Transport: stdio via `distrobox enter kicad -- <entrypoint>`
- The server shells out to `kicad-cli` (container-native KiCad 9.0.8) for plot/validate rather than importing `pcbnew`

**Restart the Claude Code session** after first clone so the MCP is picked up.

### KiCad version skew — important

- Host flatpak: **KiCad 10.0.1** (GUI, authoritative for opening finished work)
- Distrobox container: **KiCad 9.0.8** (what the MCP and its kicad-cli use)

KiCad 9 can read 9-format files but **not** 10-format. Hand-author schematic / PCB S-expressions targeting KiCad 9 format (or 8 — 9 reads 8 fine) so the MCP can validate them. When ECE-1 produces files, stick to the 9.0 `(version ...)` header. The host flatpak 10 will upgrade the files on first GUI save — do that only after the MCP has validated the design.

If this becomes annoying, `rpm-ostree install kicad` would layer KiCad 10 onto the host for a matched version (requires reboot).

### Container management

```bash
distrobox list                     # show containers
distrobox enter kicad              # interactive shell
distrobox enter kicad -- <cmd>     # one-shot command
distrobox stop kicad               # stop
distrobox rm kicad                 # delete (also removes MCP's venv state)
```

## FreeCAD / CAD tooling (Phase 2 + 5)

**Not installed, intentionally.** MECH-1 uses CadQuery (parametric Python, `pip install cadquery`) or OpenSCAD. Both run headless and export STEP + STL directly.

FreeCAD and a FreeCAD MCP server would only be needed for interactive visual inspection of the assembly — not required by the current spec. Skip unless RED-MECH explicitly requests it. Slicing for the Creality K2 Plus is a separate tool (Creality Print / OrcaSlicer) outside the Claude Code workflow.

## Project directory

```
claude-code-pad/
├── pcb/                       # ECE-1 deliverables — KiCad project, gerbers, BOM, CPL
│   └── gerbers/
├── firmware/
│   ├── esp-idf/               # FW-1 primary (XIAO ESP32-S3)
│   ├── zmk/                   # FW-1 alt (nice!nano v2)
│   ├── qmk/                   # FW-1 alt (RP2040 Pro Micro)
│   └── tinyml/
│       ├── training/
│       ├── corpus/
│       └── model/
├── case/                      # MECH-1 deliverables — CadQuery/OpenSCAD source, STL, STEP
├── figurines/
│   └── mad-dog/
└── docs/
    └── review-log.md          # Adversarial review paper trail
```

## Hardware constants (do not drift)

- Board: ~115 × 105 mm, 2-layer FR4 1.6 mm, black soldermask, HASL lead-free.
- Key pitch 19.05 mm, MX cutout 14.0 mm, 2U Cherry plate-mount stabs (23.8 mm c-to-c, 6.65 × 12.3 mm slots).
- MCU: XIAO ESP32-S3 on socketed 2×7 female headers.
- Pin map, BOM, and RGB chain order: see the orchestrated-prompt source file — it is authoritative. Do not restate pin tables elsewhere in the repo; link to the spec.

## Working conventions

- Sub-agents must stay in persona and produce files, not narrate.
- Every adversarial review cycle gets logged in `docs/review-log.md` with severity tags (BLOCKER/MAJOR/MINOR).
- Don't create speculative files or README stubs — only what a phase deliverable requires.
- When in doubt between flatpak and a native dnf KiCad, stick with flatpak (already installed, library packs already present).
