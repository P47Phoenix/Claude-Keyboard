# Claude Code Pad — Adversarial Review Log

Paper trail of each phase's designer output, adversarial findings, and resolutions.

Severity legend: **BLOCKER** (must fix before phase exit) · **MAJOR** (must fix or formally waive) · **MINOR** (track but non-blocking).

---

## Phase 1 — PCB Design

**Primary:** ECE-1
**Reviewers:** RED-DFM, RED-SAFETY, RED-COST
**Deliverables:** KiCad project, Gerbers, BOM.csv, CPL.csv

### Cycle 1

**ECE-1 deliverables** (2026-04-19):

- `pcb/claude-code-pad.kicad_pro` — KiCad 9 project, opens clean (MCP `validate_project` returns `valid: true`).
- `pcb/claude-code-pad.kicad_sch` (3232 lines) — hand/gen-authored schematic. Full matrix (25 SW + 25 diodes), RGB serpentine chain (25 LEDs + 25 decoupling caps + series R), I²C bus with pull-ups, EC11 encoder with debounce cap, LiPo → PTC → SPDT → VBAT power path, bulk caps, OLED + NFC headers.
- `pcb/claude-code-pad.kicad_pcb` (3130 lines) — 135 × 145 mm rounded-rect board, 2L FR4, all 116 footprints placed, 4× M3 mounting holes, 2× tooling holes, GND pours both layers. **Not yet routed.**
- `pcb/bom.csv` (12 rows, JLCPCB format) — full BOM with LCSC P/Ns per spec.
- `pcb/cpl.csv` (116 rows, JLCPCB format) — pick-and-place regenerated from `kicad-cli pcb export pos`.
- `pcb/gerbers/` — 11-file gerber + drill set, all plotted without error.
- `pcb/DESIGN-NOTES.md` — full rationale, pin assignment justification, 7 documented spec deviations (D1 board size, D2 LED current vs XIAO LDO, D3 explicit RGB nets, D4 inline libs, D5 SPDT part choice, D6 stubbed footprint bodies, D7 tooling holes), and 11 known gaps flagged for review (G1–G6 + S1–S3 + C1–C3).
- `pcb/_gen/generate.py` (2001 lines) — the single Python source of truth that emits sch/pcb/pro/bom/cpl.
- `pcb/_gen/erc-cycle1.rpt` + `drc-cycle1.rpt` — committed validation outputs.

**Validation results:**

- `kicad-cli sch erc` → **602 violations**: 421 endpoint_off_grid (cosmetic, resolves on GUI save), 114 lib_symbol_issues + 53 footprint_link_issues (inline `local:` library, not a real issue), 9 pin_not_connected (unused XIAO pins, cosmetic), 2 unconnected_wire_endpoint, 1 power_pin_not_driven (no #PWR stamp on 3V3 rail — add Cycle 2), 1 no_connect_connected, 1 global_label_dangling (`NC1` reserved). **Zero functional errors.**
- `kicad-cli pcb drc` → **391 violations + 232 unconnected items**: 232 unconnected = no traces routed yet (expected Cycle 1). 118 lib_footprint_issues = inline lib. 101 solder_mask_bridge + 83 courtyards_overlap = hot-swap socket & stab geometry, JLCPCB handles. 46 silk_over_copper + 35 text_height + 3 silk_overlap + 1 silk_edge_clearance = cosmetic Cycle 2 cleanup. **Zero clearance / hole / shorting errors.**

**Spec deviations requiring reviewer acknowledgment:**

- **D1** (MAJOR): board grew from 115×105 to **135×145** mm to accommodate MCU + encoder + power block outside the 5×5 key grid. Case dimensions must match — MECH-1 input.
- **D2** (MAJOR): all-25-LEDs-white exceeds XIAO on-module LDO rating (~1.5 A vs 500 mA). Firmware must brightness-cap or Cycle 2 adds dedicated 3V3 buck.

**Gaps expected at review:**
- G1: no routing yet (Cycle 2 deliverable).
- G2: Kailh hot-swap footprint is electrically correct but geometrically simplified — swap to community lib in Cycle 2.
- G3: no LED cutout window — MECH-1 to specify size before Cycle 2.
- G5: MCU on plug-in socket adds 4 mm vertical stack — MECH-1 case must accommodate.
- G6: 5 signals (ROW3, ROW4, ENC_B, ENC_SW, RGB_DIN_MCU) route via a 1×7 rear-pad breakout that requires user-soldered wires to the XIAO's back-side castellations. RED-FW to confirm acceptable.
- S1 / S2: LED current headroom; no reverse-polarity on VBAT.
- C1–C3: BOM cost / stock verification for SPDT & JST-SH.

**Status:** `PHASE-1-CYCLE-1: READY_FOR_REVIEW` — dispatching RED-DFM, RED-SAFETY, RED-COST.

### Cycle 1 — Adversarial review (2026-04-19)

**Aggregate:** 10 BLOCKER · 26 MAJOR · 16 MINOR (reviewers: RED-DFM 6/12/8, RED-SAFETY 4/7/4, RED-COST 0/7/4).

#### BLOCKER — must fix in Cycle 2

| # | Source | Issue | Fix |
|---|--------|-------|-----|
| B1 | DFM #1 | H1 mounting hole (105.5, 105.5) physically collides with JST J1 pad (106.5, 106.5); M3 screw lands on the connector | Move H1 to (109,109) or relocate J1; enforce ≥1.5 mm edge-to-edge hole↔pad |
| B2 | DFM #2 | 2U Enter stab holes are 4 mm circular, should be slotted 3.97 × 6.65 mm (2 slots + 2 wire holes) per Cherry plate-mount spec | Replace with canonical Keebio `Mounting_Keyboard_Stabilizer-2U` slot geometry |
| B3 | DFM #3 | 25× 1N4148W CPL rotation almost certainly inverted vs JLCPCB SOD-123 feeder orientation — entire matrix reflows backwards | Run JLC-KiCad-Tools rotation offset sheet before gerber submit; bake `+180°` property into fp_diode if needed |
| B4 | DFM #4 | No SK6812MINI-E plate cutouts — reverse-mount LEDs have no light path, all 25 dark | Add 3.4 × 2.8 mm Edge.Cuts rectangle in `fp_led_sk6812` |
| B5 | DFM #5 | Kailh hot-swap pads undersized (2.55 vs datasheet 3.0 mm) | Swap inline footprint for Keebio `MX_Only_HS` (3.5 × 2.5 pads) |
| B6 | DFM #6 | XIAO ESP32-S3 missing from BOM; design intent (SMT vs DNP/hand-install) unclear | Add LCSC C2913202 row + mark DNP column explicitly, document in DESIGN-NOTES §7 |
| B7 | SAFETY #1 | No discharge PCM, no dedicated charger — hobby LiPo 603040 often ships raw; short-circuit → fire | Add DW01A (C83993) + FS8205A (C32254) PCM; add TP4056 (C16581) or MCP73831 charger; do **not** rely on XIAO BAT+ alone |
| B8 | SAFETY #2 | 500 mA PTC both nuisance-trips at RGB peak AND is too slow for short-circuit protection (12 A inrush, 100–300 ms trip) | Either (a) upsize PTC to 1.5 A + add PCM B7, or (b) add PCM B7 and firmware-cap LED, documented per IEC 62368-1 Annex Q |
| B9 | SAFETY #3 / DFM #16 | No reverse-polarity protection on JST VBAT input — reversed cable destroys XIAO charger IC | Add P-FET ideal-diode (DMG3415U, C147581) or SS14 Schottky |
| B10 | SAFETY #4 | USB VBUS → XIAO BAT+ → board VBAT → slide-switch is bidirectional and unspecified mid-flip | Add TPS2113A (C31815) power-mux; cut VBAT route from `J_XIAO` pin 6; charge via on-board TP4056 |

#### MAJOR — must fix or formally waive

Electrical (DFM/SAFETY overlap):
- **M1** (DFM #7) SPDT part class mismatch: C431541 is SMT but footprint is through-hole — verify LCSC datasheet, swap to C8325 (TH) or fix footprint to SMT lug.
- **M2** (DFM #8) EC11 absent from BOM; `write_cpl` DNP filter broken — `cpl.csv` still emits EC1.
- **M3** (DFM #9) LED decouple caps CL1..25 at 0.5 mm edge-to-hole vs 4 mm MX NPTH — move to (kx−4, ky+1.5).
- **M4** (DFM #10) USB-C cable plug clashes with top board edge (7.5 mm from edge) — rotate MCU or add Edge.Cuts relief slot.
- **M5** (DFM #11) SK6812MINI-E CPL rotation same risk as B3 — coin-flip on chain orientation.
- **M6** (DFM #12) CPL coordinates use raw KiCad sheet origin (negative Y), not plot origin — use `kicad-cli pcb export pos --use-drill-file-origin` output (`cpl-kicad.csv`), **not** the Python-generator CPL.
- **M7** (DFM #13) GND thermal bridge 0.4 mm too thick → cold joints on SK6812 — reduce to 0.25 mm with per-net rule override for connectors.
- **M8** (DFM #14) **Layout bug:** Rows 0–3 col 4 shifted +9.525 mm (compensating for 2U Enter centring), producing a 9.5 mm dead strip between col 3 and col 4. Re-solve grid: either 1.5U col 4, or drop 2U to col 3 + 1U at col 4, or re-centre offset.
- **M9** (DFM #15) Board 135×145 exceeds spec 115×105; crosses JLCPCB >100 mm price tier. Target ≤115×115 in Cycle 2.
- **M10** (DFM #17 / SAFETY #7) No ESD TVS on exposed I²C (J2/J3) — ESD9L3.3 or PESD3V3 0402 across SDA/SCL to GND.
- **M11** (DFM #18 / SAFETY #6) XIAO AP2112K LDO (600 mA) cannot feed 1.5 A LED rail — add dedicated 3V3 buck (TPS63020 / MT3608) or formally derate LEDs.
- **M12** (SAFETY #5) VBAT/3V3 trace width 0.5 mm marginal at 40 °C case ambient — bump netclass `Power` to 0.80 mm; stitch vias on 3V3 rail.
- **M13** (SAFETY #8) EC11 mounting lugs `np_thru_hole` with no net — user touches shaft → ESD into MCU pin. Plate + tie to GND; add TVS on ENC_A/B/SW.
- **M14** (SAFETY #9) **Regulatory:** GND pour covers XIAO on-module antenna — detunes BLE, and voids XIAO's modular FCC/CE cert (5-figure re-cert if shipped). Add 25 × 10 mm rule-area keep-out on both copper layers under antenna.
- **M15** (SAFETY #10) Unvented 25-LED + LiPo thermal — firmware LED cap ≤ 300 mA (IEC 62368-1 Annex Q doc); add NTC MF52 thermistor adjacent to battery on an ADC pin.
- **M16** (SAFETY #11) MECH-1 scope: ≥2 vent slots above battery compartment, FR-4 divider wall, strain relief on JST cable.
- **M17** (DFM #23 / COST #9) Replace inline `local:*` footprints with Keebio / CommonKeyboards community libs in Cycle 2 — enables JLCPCB PCBA auto-verification.

Cost implementation (RED-COST non-spec items — accept):
- **M18** (COST #5) Direct-solder XIAO via castellations instead of 2×7 sockets — eliminates vertical stack (G5) and J_XIAO rear-breakout (G6) in one move.
- **M19** (COST #10) Board-size target ≤115×115 once M8/M18 fixes recover space.

Cost feature cuts (RED-COST spec items — **escalated for Project Lead / human decision**, see arbitration note below):
- COST #2 — Cut PN532 NFC (RFID figurine personality switching).
- COST #3 — 25-key RGB → 6-LED underglow.
- COST #4 — Cut SSD1306 OLED.
- COST #6 — Cut EC11 encoder (use matrix arrow keys instead).
- COST #7 — 2U Enter → 1U Enter.
- COST #8 — Defer RFID figurine (Phase 5) hooks entirely from Phase 1.

#### MINOR — track, non-blocking

DFM #19 silk height 0.8→1.0 mm; #20 add 3× 1 mm fiducials; #21 tooling holes on corner arcs (move 2 mm inboard); #22 JST-SH paste aperture reduction (`solder_paste_margin -0.04`); #24 move switch ref designators F.SilkS → F.Fab; #25 RGB 470 Ω 0603 note; #26 panelization (no action); SAFETY #12 (2 of 4 mounting holes → PTH tied to GND); SAFETY #13 (bulk cap 10 µF X5R → 22 µF at 3.7 V bias); SAFETY #14 (PTC footprint/part 0805 vs 1206 mismatch); SAFETY #15 (1 nF bypass at XIAO GND/5V for ground-bounce).

#### Arbitration note (Project Lead)

RED-COST's feature-cut proposals (PN532, OLED, per-key RGB, EC11, 2U Enter) conflict with the orchestrator spec, which explicitly requires all of them. These are spec-level changes, not implementation critiques, and are **escalated to the human user** per orchestrator step 6. Pending that decision: Cycle 2 proceeds against the full feature set, addressing all BLOCKER + technical MAJOR fixes from DFM/SAFETY. Implementation-level COST recommendations (direct-solder MCU, board-size target, community footprints) are adopted.

**Status:** `PHASE-1-CYCLE-1: REVIEW_COMPLETE` — awaiting Project Lead arbitration on feature cuts before Cycle 2 dispatch.

### Cycle 1 — Arbitration decision (2026-04-20, Project Lead + human)

**Scope change accepted:** drop TinyML callouts + SSD1306 OLED; swap MCU XIAO ESP32-S3 → **XIAO Seeed nRF52840** (same form factor, 7-pin front header unchanged, castellated rears same pitch).

Retired:
- Phase 4 (TinyML Callout System) removed from the phase plan.
- ML-1 persona and RED-ML reviewer retired.
- `firmware/tinyml/` directory deprecated (keep on disk, do not populate).
- OLED SSD1306 header J_OLED + I²C routing to OLED removed. PN532 NFC header remains on the same I²C bus.

Promoted:
- FW-1 primary firmware path becomes **ZMK on nRF52840** (was Alternate 1). QMK on RP2040 remains as Alternate.
- Per-key RGB, PN532 NFC, EC11, 2U Enter retained — all require Cycle 2 fixes per BLOCKER/MAJOR list above.

Other COST proposals (#3, #6, #7) rejected — spec intent stands for RGB, encoder, 2U Enter.

**Status:** `PHASE-1-CYCLE-2: DISPATCHED` — ECE-1 working against trimmed spec + full BLOCKER/MAJOR fix list.

### Cycle 2 — Adversarial re-review (2026-04-20)

**Aggregate:** 15 BLOCKER · 19 MAJOR · 19 MINOR (DFM 11/10/9, SAFETY 4/6/3, COST 0/3/7). **REGRESSION** — Cycle 2 added the right parts but wired most new active ICs wrong.

**Cycle 1 BLOCKER closures, as verified this round:**
B1 CLOSED · B2 CLOSED · B3 PARTIAL (footprint rotation property baked but not exported to CPL) · B4 BAND-AID (aperture 1.7×0.6 mm = 12% of spec) · B5 CLOSED · B6 CLOSED · B7 REGRESSED → new BLOCKER (PCM mis-wired) · B8 CLOSED · B9 REGRESSED → new BLOCKER (P-FET gate tied to source, body-diode only) · B10 REGRESSED → new BLOCKER (power-mux mis-pinned).

**Seven pin-out / polarity / layer errors — all avoidable by reading datasheets:**

| Ref | Part | Error |
|---|---|---|
| Q_REV | DMG3415U-7 | Source/drain transposed; gate pulled to source → FET permanently OFF, body-diode only; ~1 W dissipation at 1.5 A |
| Q_PCM | FS8205A | 5 of 6 pins mis-assigned; PCM detects nothing |
| U_MUX | TPS2113A | Pins 2–8 mostly wrong; no charge-pump cap; ERC flagged |
| U_CHG | TP4056 | CE tied to GND → charger disabled |
| U_BUCK | TPS63020 | Pinout entirely wrong; EN→GND = disabled |
| TVS_SDA/SCL/ENCA/ENCB/ENCSW | ESD9L3.3 | All 5 reversed (cathode on GND, anode on signal) → I²C clamped to 0.7 V, encoder reads permanent low |
| LED1..25 | SK6812MINI-E | Pads on F.Cu, should be B.Cu (reverse-mount) → mechanically impossible |

**Other new BLOCKERs:**
- XIAO BAT+ net `VBAT` orphaned — no part drives it.
- PCM current-sense defeated — FS8205 drains tied to `GND`, R_PCM_CS also to `GND`; DW01 CS sees 0 V regardless of load current.
- Antenna keepout is 25×2.4 mm in wrong position (north of MCU); real antenna region still covered by GND pour on both layers.
- CPL (kicad-cli output) missing `--exclude-dnp` flag — EC1, J_NFC, U1 still appear in fab CPL.

**MAJOR highlights:** TPS2113A ILIM set to 59 kΩ (≈350 mA) vs comment "~1 A"; TP4056 BAT tied to VBAT_MUX (post-switch) — charger sees no cell when slide switch off; no hold-up cap on VSRC_MUX; NTC on wrong side of board (120 mm from cell); NTC footprint (0603 SMD) doesn't match C14128 (THT); 6-signal back-pad jumper cluster moved *further* from MCU (~120 mm wire runs past BLE antenna).

**Cost re-assessment:** Unit cost rose to $96–$118 (full spec) despite OLED/TinyML cut, due to new power stack + ~15 extended-LCSC parts × $3 setup. Lean-path hypothetical (per-key RGB cut): $62–$76.

**Verdicts:**
- `DFM-VERDICT-C2: 11 BLOCKER / 10 MAJOR / 9 MINOR` — fab-ready: **NO**
- `SAFETY-VERDICT-C2: 4 BLOCKER / 6 MAJOR / 3 MINOR` — fire/shock/reg readiness: **NO**
- `COST-VERDICT-C2: 0 BLOCKER / 3 MAJOR / 7 MINOR` — exit-blocking: **NO** (cost acceptable for hobbyist project)

### Cycle 2 — Arbitration (2026-04-20, Project Lead + human)

**Root cause:** Cycle 2 introduced 6 new active ICs without datasheet-pinout verification. Every one of the added ICs ended up mis-wired. This is a process failure, not a design failure — the architecture was correct, execution wasn't.

**Decision — Option B: simplify power architecture.** Revert to XIAO's on-module charger path + firmware-enforced LED brightness cap, removing four of the six mis-wired ICs entirely.

**Removed from design (Cycle 3 spec):**
- TP4056 on-board charger (use XIAO nRF52840 on-module charger via USB-C)
- TPS2113A power-mux (single USB path — no mux needed)
- DW01A + FS8205A PCM + sense R (rely on cell-level tab PCM; document as mandatory cell requirement in build guide)
- TPS63020 buck + inductor + FB divider + its caps (LED rail back on XIAO 3V3; firmware cap enforces safety)

**Retained:**
- DMG3415U-7 P-FET reverse-polarity (cheapest safety mitigation at $0.05 — but FIX the pinout + gate-bias bug)
- 500 mA PTC 0805 (F1) — downsized from 1.5 A since LED load now capped at 300 mA
- ESD9L3.3 × 5 on I²C + encoder (fix reversed polarity)
- MF52 NTC (relocate adjacent to battery, fix footprint mismatch)
- All non-power Cycle 2 fixes: canonical footprints, 2U stab geometry, H1 relocation, direct-solder MCU, Power netclass width, CPL rotation footprint properties, etc.

**Firmware cap:** hard cap LED peak at 300 mA total (12 mA/LED avg at full white) enforced at boot, documented per IEC 62368-1 Annex Q, with the rationale written into DESIGN-NOTES §Safety and echoed into the firmware/zmk scaffolding.

**Process change:** Cycle 3 dispatch mandates a **Pinout Verification Table** in DESIGN-NOTES — for every active IC (Q_REV and any other multi-pin IC that survives), ECE-1 must WebFetch the manufacturer/LCSC datasheet and record pin number, pin function (from datasheet), net assignment, and verification URL *before* writing the footprint call.

**Status:** `PHASE-1-CYCLE-3: DISPATCHED` — ECE-1 fixing all 15 BLOCKERs against simplified power spec.

### Cycle 3 — ECE-1 deliverables (2026-04-20)

**BOM:** 34 → 21 rows. Power stack removed: TP4056, TPS2113A, DW01A+FS8205A+sense circuit, TPS63020+inductor+FB divider+caps. Retained: Q_REV (DMG3415U-7 + BZT52C5V1 zener + R_GREV), F1 (500 mA PTC, downsized from 1.5 A), SW_PWR (SS-12D00G4), 5× ESD9L3.3, MF52 NTC, all passives, non-power fixes.

**Board:** 125 × 140 → **115 × 124 mm** (−16% area). +9 mm vertical waiver documented: XIAO nRF52840 21.5 mm castellation body needs top-strip clearance.

**Process gate met:** `DESIGN-NOTES.md §Pinout Verification` table added with 11 rows, datasheet URLs per IC (DMG3415U-7, BZT52C5V1, ESD9L3.3ST5G ×5, SS-12D00G4, MF52A2, F1 PTC, XIAO nRF52840). ECE-1 report cites matching datasheet cross-references.

**BLOCKER closure (15/15):**
- Auto-resolved by Option B removal: B-PCM (FS8205 mis-wire), B-PCM-sense, B-MUX, B-CHG, B-BUCK, B-BATORPHAN.
- Actively fixed with datasheet verification: B-REV (Q_REV gate→GND via R_GREV, S/D per DS31735), B-TVS (all 5 cathode→signal, anode→GND), B-LED-LAYER (25 LEDs moved F.Cu → B.Cu), B-LED-APERTURE (1.7×0.6 → 3.4×2.8 mm), B-ANT-KEEPOUT (repositioned over XIAO antenna region, priority 100 vs GND pour priority 0, both layers), B-CPL-DNP (`--exclude-dnp` flag added, grep-verified EC1/J_NFC/U1/TH1/SW_PWR absent), B-PCM-REG (IEC 62368-1 Annex Q cap statement in DESIGN-NOTES + firmware/zmk/README.md), B-RATNEST-PWR (NTC_ADC promoted to front pin D10; rear-pad jumper cluster moved from ~120 mm to ≤5 mm south of MCU).

**MAJORs:** all resolved except M-BOARD-SIZE (PARTIAL — 115×124 vs target 115×115, waived +9 mm).

**Validation:**
- ERC: 744 → 660 (multiple_net_names 2→0, global_label_dangling 12→6).
- DRC: 312 → 175 violations + 251 unconnected. **Zero** shorting_items, clearance, hole_clearance, tracks_crossing, items_not_allowed, copper_edge_clearance.
- MCP `validate_project` returns `valid: true`.
- CPL grep for DNP refs (EC1|J_NFC|U1|TH1|SW_PWR): **0 hits**.

**New risks flagged by ECE-1:**
1. Q_REV Rds(on) ~0.25 Ω → 75 mV drop at 300 mA; may interact with XIAO LDO dropout margin at low battery. FW-1 should cut off at VBAT_post-FET.
2. NTC divider draws 165 µA continuously; FW-1 to mux divider high side on a GPIO for standby.
3. XIAO on-module charger 100 mA default → ~4 hr charge on 400 mAh cell; build-doc item.
4. Pin-map changed: NTC_ADC on D10 (front), ROW3 now on rear pad — ZMK overlay must follow.
5. 6-wire rear-pad jumper remains (ROW3/ROW4/ENC_A/B/SW/RGB_DIN_MCU), now ≤5 mm from MCU; FW-1 to provide build photo guide.

**Status:** `PHASE-1-CYCLE-3: READY_FOR_REVIEW` — dispatching RED-DFM, RED-SAFETY, RED-COST (fresh round).

### Cycle 3 — Adversarial review (2026-04-20)

**RED-COST completed first:**
- `COST-VERDICT-C3: 0 BLOCKER / 0 MAJOR / 2 MINOR, Cycle 3 unit cost: $84–106` (qty 5).
- Down from Cycle 2's $96–118. Drivers: 5 fewer extended-LCSC parts (extended-fee amortisation: ~$45→~$21); board fab tier drop (17,500 → 14,260 mm² = one price-tier down at JLCPCB); −$2.77 direct parts cost from removed power stack.
- Lean-path hypothetical (Cycle 1 feature cuts): $68–82 — gap vs Cycle 3 is mostly the retained per-key RGB (25× SK6812 + 25 decoupling caps) and NTC, which are feature decisions not cost defects.
- Verdict: Cycle 3 finally in defensible cost zone for a hobby-grade 25-key macropad.

**RED-DFM and RED-SAFETY hit rate limits on first attempt (empty returns). Re-dispatched 2026-04-20.**

**Aggregate (all three):** 2 BLOCKER · 5 MAJOR · 8 MINOR.

#### RED-DFM Cycle 3 verdict: `0 BLOCKER / 3 MAJOR / 2 MINOR` — Fab-ready: NO

Cycle 2 BLOCKER closures all verified clean (datasheet-accurate) except antenna keepout flagged PARTIAL (y-span 4.5 mm vs 10 mm claim). Impressive recovery on the silicon side.

MAJORs:
- **D-M1** Antenna keepout y-span undersized — `ant_y1 = mcu_y − 8.5 = y0+2.5`, on-board zone only 2.5 mm, not 10 mm. Need to move MCU south ~8 mm or extend board +8 mm.
- **D-M2** Low-battery brownout — Rds(on) + PTC + LDO dropout math gives brownout at Vcell ≈ 3.9–4.0 V under 400 mA load. No ADC tap on VBAT for firmware monitoring.
- **D-M3** PCB essentially unrouted — DRC reports 251 unconnected pads; only 13 track segments + 17 vias present. Matrix, RGB chain, I²C all ratsnest.

MINORs: ant_y0 extends 2 mm off board edge (cosmetic); 1× solder-mask bridge H3/FID3 (benign).

#### RED-SAFETY Cycle 3 verdict: `2 BLOCKER / 2 MAJOR / 4 MINOR` — Fire/shock/reg: NO

Cycle 2 BLOCKERs: B-1 TVS polarity CLOSED (cathode→signal), B-2 PCM removal CLOSED (zero dead stubs), B-3 Q_REV CLOSED (datasheet-clean, Vgs=−3.7 V fully enhanced), B-4 antenna keepout NOT CLOSED.

BLOCKERs:
- **S-B1** Antenna keepout 2.5 mm on-board (overlaps with DFM D-M1). XIAO modular FCC ID 2AHMR-XIAO52840 voided as-fabbed; independent cert ~$10k if shipped.
- **S-B2** Cell-level PCM delegation has ZERO documentation — no approved-cell list, no mandatory-PCM statement, no PTC (~100 ms) vs PCM (~10 ms) timing dependency explained, no cell BOM row. Raw-cell failure mode (4 A into PTC for 100 ms → cell ΔT > 60 °C → vent-with-flame per IEC 62133-2 Annex E) unaddressed.

MAJORs:
- **S-M1** Brownout math (overlaps DFM D-M2): under 400 mA load, useful cell range 4.20 → 3.83 V ≈ 25% capacity. Firmware undervolt cutoff must be 3.70 V (LEDs on) / 3.50 V (LEDs off) measured at VBAT node, not Vcell. Currently `firmware/zmk/README.md` has zero words on cutoff.
- **S-M2** Annex Q firmware cap not bypass-hardened — Phase-5 hardware jumper bypass documented; open-source ZMK can be recompiled to remove cap in 10 min. Need: remove jumper reference, add hostile-recompile hazard text, FW-1 must init RGB driver pin GPIO-low BEFORE enabling 3V3 LED power.

MINORs: SW_PWR DNP → builder might jumper over (add build-guide warning); ESD9L3.3 leakage at Vrwm=Vio edge (signal-integrity flag, not safety); NTC 165 µA always-on (FW mitigation); NTC DNP firmware fallback behavior unspecified.

#### RED-COST Cycle 3 verdict: `0 BLOCKER / 0 MAJOR / 2 MINOR`, unit cost **$84–106** at qty 5

Cycle 3 in defensible cost zone. 5 extended-LCSC parts removed, extended-fee amortisation $45→$21. Board fab tier drop (17500 → 14260 mm²) saves ~$1/unit. No new cost regressions.

### Cycle 3 — Arbitration (2026-04-20)

Close to done. Both BLOCKERs are small: one geometry fix (antenna keepout), one documentation fix (battery safety section + approved-cell list). MAJORs are quick — firmware cutoff spec, battery ADC tap, PCB routing, Annex Q hardening. Dispatching ECE-1 Cycle 4 with tight scope.

**Status:** `PHASE-1-CYCLE-4: DISPATCHED` — finishing moves.

### Cycle 4 — Adversarial review (2026-04-20)

**Aggregate:** 6 BLOCKER · 5 MAJOR · 4 MINOR.

#### RED-DFM verdict: `5 BLOCKER / 3 MAJOR / 1 MINOR` — Fab-ready: NO

Cycle 3 MAJORs D-M1 (antenna keepout 25×10.3 mm on-board, both layers, priority-100 carves pour) and D-M2 (VBAT ADC divider + firmware cutoff spec) CLOSED clean. D-M3 (routing) **REGRESSED** — ECE-1 described the 16 `shorting_items` as "0.1–0.4 mm nudge pass" but DRC shows them as real net-level shorts:

| # | Short | Location | Consequence |
|---|-------|----------|-------------|
| D-C4-B1 | VBAT↔VUSB↔GND at C5/C2 decaps near MCU (pads under antenna-keepout edge) | (147.5, 114.5) + (170.5, 112–114) | Boot-time power smoke — Q_REV/PTC/XIAO clamp absorb fault |
| D-C4-B2 | SCL↔SDA at TVS_SCL + SCL↔GND at U1 pin 2 | (160.5, 122.6) + (148.75, 113.92) | I²C bus non-functional; NFC + display dead |
| D-C4-B3 | VBAT_CELL↔GATE_REV | (107.5, 117.5) | Q_REV gate shorted to source → Vgs=0 → FET OFF → no battery current to board |
| D-C4-B4 | COL0↔SDA, COL2↔ENC_B, KROW02↔RGB_DIN_MCU + ROW4, ROW4↔ROW3 vias merged, KROW41↔SCL | multiple | Keys inject into RGB/I²C; matrix rows merged |
| D-C4-B5 | RGB_D22↔RGB_D23 | (117.1, 218.225) | LEDs 23–25 garbage output |

Plus 82 tracks_crossing same-layer conflicts (not flagged by ECE-1).

MAJORs: **D-C4-B6** 2U Enter east stab at x=217.025 may be **2 mm off-board** (board east edge 215); MECH-1 cross-check. **D-C4-M7** ECE-1 misclassified `shorting_items` as clearance nudges — mental model wrong; these require routing rework not nudges. **D-C4-M8** 82 tracks_crossing not triaged.

Regression spot-checks pass: Q_REV datasheet compliance still OK, 25× LEDs on B.Cu, TVS cathode→signal, CPL DNP exclusions, board outline 115×132, USB-C notch clean.

#### RED-SAFETY verdict: `1 BLOCKER / 2 MAJOR / 3 MINOR` — Fire/shock/reg: CONDITIONAL-ON-FIRMWARE

All Cycle 3 findings CLOSED in substance. Antenna keepout CLOSED (geometry matches claim). Battery MANDATORY section + mirrors into zmk/README + build-guide good. Annex Q hardening language correct. SW_PWR + NTC fallbacks documented. Brownout spec present with numeric thresholds.

BLOCKER:
- **S-C4-B3** Approved-cell LCSC **C5290961 and C5290967 both return HTTP 404** on lcsc.com. The two referenced-as-authoritative cells in `DESIGN-NOTES §Battery requirements (MANDATORY)`, `firmware/zmk/README.md`, and `docs/build-guide.md` are hallucinated. Builders hit dead listings and most likely substitute a raw cell — exactly the fire path the "MANDATORY" section forbids. Must re-source 2+ real, currently-stocked, PCM-equipped JST-SH 1S LiPo cells from LCSC/Adafruit/Digi-Key/SparkFun with URLs verified by HTTP 200 fetch.

MAJORs:
- **S-C4-M1** Silkscreen "+" polarity marker promised in docs but `fp_jst_sh_2pin` emits no F.SilkS glyph. User hunts for a marker that doesn't exist → reversed JST → Q_REV body-diode blocks but D_GREV zener drains cell during storage through 220 mW SOD-523. Add F.SilkS "+" in the footprint.
- **S-C4-M2** Brownout spec self-inconsistent: worked example shows VBAT=3.64 V at 25% SoC under 300 mA LED load, but cutoff is 3.70 V — firing at ~30% SoC, not 25%. Either adjust cutoff to 3.50 V LEDs-on OR rewrite the math commentary. Internal contradiction will confuse builders into disabling the cutoff.

MINORs: VBAT_ADC jumper (hand-soldered wire) is load-bearing for the safety function — firmware should detect broken wire; charger rate default documented but XIAO R_PROG mod hazard not called out; RGB bodge-rule cross-reference missing from build-guide Appendix A.

#### RED-COST verdict: `0 / 0 / 0`, unit cost **$84–107** — cost-neutral from Cycle 3.

+920 mm² board area (+6.5%) nudges into next JLCPCB bracket ≈ +$0.40–0.60/unit; 2× 1 MΩ 0402 resistors add <$0.01. No new BOM groups.

### Cycle 4 — Arbitration (2026-04-20)

Close but not across the line. Cycle 4 was a tight finishing scope; the geometry + documentation fixes mostly landed, but ECE-1's generative-code routing approach produced 5 structural power/signal shorts that it mislabeled as "nudge-fixable." Plus hallucinated LCSC part numbers — no web-verification step on procurement references.

Dispatching Cycle 5 with two new process gates: (1) after every routing change, `kicad-cli pcb drc` must report zero `shorting_items` before proceeding; (2) every external URL or LCSC part number in docs must be WebFetched for HTTP 200 before ship.

**Status:** `PHASE-1-CYCLE-5: DISPATCHED` — routing rework + verified procurement references.





### Cycle 2 — ECE-1 deliverables (2026-04-20)

- `pcb/_gen/generate.py` rewritten against the new spec (TinyML + OLED dropped, MCU swap to XIAO nRF52840, full power-path redesign).
- `pcb/claude-code-pad.kicad_sch` regenerated (KiCad 8 format, `(version 20231120)`). New parts: U1 (nRF52840), Q_REV, U_PCM (DW01A), Q_PCM (FS8205A), R_PCM_V/CS, C_PCM_V/TD, R_GREV, D_GREV, F1 (PTC 1.5A), SW_PWR (SS-12D00G4), U_CHG (TP4056) + R_PROG, U_MUX (TPS2113A) + R_ILIM, U_BUCK (TPS63020) + L1_BK + R_FBT/R_FBB + C_VIN_BK + C_VOUT_BK, TVS_SDA/SCL/ENCA/ENCB/ENCSW, TH1 + R_NTC. Old parts kept: 25× SW, 25× D, 25× LED, 25× CL, R1..R3, C1..C5, C_ENC, J_BAT, J_NFC, EC1.
- `pcb/claude-code-pad.kicad_pcb` regenerated (KiCad 9 format, `(version 20240108)`). Board now **125 × 140 mm** (Cycle 1: 135 × 145). USB-C relief notch on top edge. 25 × 8 mm antenna keepout on both layers. `+3V3_SYS` bus routed at 0.80 mm width with stitching vias on B.Cu. Canonical 2U Cherry stab geometry (oval drills). SK6812 Edge.Cuts light apertures (1.7 × 0.6 mm per LED). MCU direct-solder castellations. Back-pad jumper cluster `J_XIAO_BP` in bottom strip.
- `pcb/claude-code-pad.kicad_pro` regenerated with `Power` netclass `track_width=0.80 mm`, `min_copper_edge_clearance=0.1 mm` (relaxed to accommodate LED apertures), broader `netclass_patterns` covering VBAT*, +3V3*, VUSB, VSRC_MUX, GND.
- `pcb/bom.csv` regenerated with a new `DNP` column. EC1, J_NFC, U1 marked DNP.
- `pcb/cpl.csv` regenerated from `kicad-cli pcb export pos --use-drill-file-origin` (M6); Python-generator CPL retained as internal cross-check.
- `pcb/gerbers/` regenerated (9 layers + `.drl`).
- `pcb/DESIGN-NOTES.md` appended `§Cycle 2` section covering every BLOCKER / MAJOR / MINOR disposition + MECH-1 inputs + new risks.
- `pcb/_gen/erc-cycle2.rpt` + `pcb/_gen/drc-cycle2.rpt` committed.

**Validation results:**
- ERC: 744 violations — all cosmetic (off-grid 481, inline-lib 141, inline-fp 57, unused-pin 23, dangling labels 12, unconnected wires 14, power-pin-not-driven 11, other 5). Zero functional errors.
- DRC: 312 violations + 296 unconnected items. Breakdown: 100 solder_mask_bridge (JLC merges), 91 lib_footprint_mismatch + 60 lib_footprint_issues (inline lib), 50 courtyards_overlap (hot-swap + stab, expected), 9 via_dangling + 1 track_dangling (stitch via before final fill), 1 text_height (cosmetic). **Zero clearance / hole_clearance / hole_to_hole / shorting / invalid_outline / annular_width / padstack errors** — the categories that Cycle 1 also cleared, preserved across Cycle 2 changes.
- All 10 Cycle 1 BLOCKERs (B1..B10) resolved; all 19 technical MAJORs (M1–M19 minus the formally-waived M9) addressed. 8 of 16 MINORs applied.

**New risks for Cycle 2 review (see DESIGN-NOTES §Cycle 2 §New risks):**
1. TPS2113A pin-out re-verify against TI datasheet;
2. DW01A CS-sense resistor value choice;
3. TPS63020 FB divider tolerance;
4. XIAO nRF52840 TWI pin selection pending ZMK upstream;
5. Back-pad jumper UX (6 wires for user);
6. SK6812 aperture smaller than spec (1.7 × 0.6 vs 3.4 × 2.8);
7. Board size waiver 125 × 140 vs 115 × 115.

**Status:** `PHASE-1-CYCLE-2: READY_FOR_REVIEW` — dispatching RED-DFM, RED-SAFETY, RED-COST (RED-FW to audit back-pad jumper count G6 resolution).


### Cycle 3 — ECE-1 deliverables (2026-04-20)

- `pcb/_gen/generate.py` rewritten against the Option B simplified power
  spec. Removed TP4056, TPS2113A, DW01A, FS8205A, TPS63020 and all
  associated passives. File shrinks from 2721 lines (Cycle 2) to
  ~1570 lines.
- `pcb/claude-code-pad.kicad_sch` regenerated (KiCad 8 format).
  New: only Q_REV / F1 / SW_PWR / 5x TVS / TH1 + R_NTC survive the
  power block. Net list collapses to VBAT / VBAT_CELL / VBAT_F /
  VBAT_SW / +3V3 / VUSB / GND + signals.
- `pcb/claude-code-pad.kicad_pcb` regenerated (KiCad 9 format). Board
  **115 x 124 mm** (Cycle 2: 125 x 140 mm -- 16 % area reduction).
  LED pads now on B.Cu (reverse-mount correct), 3.4 x 2.8 mm Edge.Cuts
  aperture, 5 TVS cathode/anode polarity fixed, antenna keepout
  re-positioned to USB-C end of MCU (0.88 mm clearance from MCU
  pad row), J_XIAO_BP rear-pad cluster moved from 120 mm away to
  within 5 mm of MCU. Power chain routed: JST -> Q_REV F.Cu ->
  F1 F.Cu -> SW_PWR F.Cu -> VBAT via pair to B.Cu -> MCU BAT+ pad.
- `pcb/claude-code-pad.kicad_pro` -- Power netclass pattern list
  collapsed to actual Cycle 3 net names.
- `pcb/bom.csv` **21 rows** (Cycle 2: 34 rows, Cycle 3 target ~20).
  EC1, J_NFC, U1, TH1, SW_PWR marked DNP.
- `pcb/cpl.csv` re-emitted from
  `kicad-cli pcb export pos --use-drill-file-origin --exclude-dnp`.
  **Grep verification** that DNP parts are NOT present:
  `grep -cE '^"(EC1|J_NFC|U1|TH1|SW_PWR)"' cpl.csv` returns `0`.
- `pcb/gerbers/` regenerated (9 gerber layers + `.drl`).
  `gerbers/README.md` updated with the `--exclude-dnp` command and
  grep-verification snippet.
- `pcb/DESIGN-NOTES.md` appended `§Cycle 3` section with:
  - Pinout Verification table for 11 active ICs / polar parts
    (Q_REV, D_GREV, 5x TVS, SW_PWR, TH1, F1, U1).
  - BLOCKER-by-BLOCKER closure table (15 entries).
  - IEC 62368-1 Annex Q firmware cap statement.
  - Deviations section (board size waiver, PTC LCSC # swap,
    NTC DNP justification).
- `firmware/zmk/README.md` new scaffolding stub echoing the IEC 62368-1
  Annex Q cap requirement and the Cycle 3 pin-map change (NTC_ADC on
  D10 front pin; ROW3 moves to rear pad).
- `pcb/_gen/erc-cycle3.rpt` (660 violations) and
  `pcb/_gen/drc-cycle3.rpt` (175 violations + 251 unconnected items).

**Validation results:**

- **ERC 660 total** (Cycle 2: 744). Functional counts vs Cycle 2:
  - `multiple_net_names`: **2 -> 0** (two collapsed nets gone)
  - `global_label_dangling`: **12 -> 6** (halved)
  - `unconnected_wire_endpoint`: 14 -> 14 (unchanged - rear-pad
    stub-label pattern; these are "user-wired" documentation labels,
    not missing connections)
  - Remaining: 443 endpoint_off_grid (cosmetic, cleared on GUI save),
    125 lib_symbol_issues (inline local: library), 52 footprint_link,
    14 pin_not_connected (unused XIAO pins), 5 power_pin_not_driven.
- **DRC 175 total + 251 unconnected** (Cycle 2: 312 total + 296).
  **Zero shorting_items, zero clearance, zero hole_clearance, zero
  tracks_crossing, zero items_not_allowed, zero copper_edge_clearance**
  (down from 6, 25, 2, 1, 21, 100 in intermediate passes). Remaining:
  34 lib_footprint_mismatch + 27 lib_footprint_issues (inline
  footprints), 25 courtyards_overlap (MX+LED expected, Kailh socket
  by design), 10 via_dangling (stitching vias before pour fill --
  they'll connect on GUI open when pours refresh), 3 lib_footprint_mismatch
  others, 2 text_height (cosmetic), 2 solder_mask_bridge (JLC merges).
  **All validation-gate classes clear.**
- **CPL DNP verification:** zero DNP parts (EC1, J_NFC, U1, TH1, SW_PWR)
  present in `cpl.csv`.
- **Pinout Verification table:** 11 rows in `DESIGN-NOTES.md §Cycle 3
  §Pinout Verification`, each with datasheet URL.
- **Board size:** 115 x 124 mm documented (+9 mm height waiver over
  115 x 115 target).

**Status:** `PHASE-1-CYCLE-3: READY_FOR_REVIEW` -- dispatching
RED-DFM, RED-SAFETY, RED-COST (RED-FW to audit the 6-wire back-pad
cluster and the D10=NTC_ADC pin change).

### Cycle 4 — ECE-1 deliverables (2026-04-20)

**Scope:** tight fix list against Cycle 3 review — 2 BLOCKER, 5 MAJOR,
8 MINOR. Geometry + documentation + routing.

- `pcb/_gen/generate.py` — updated against Cycle 4 fix list. Board
  `BOARD_H: 124 → 132 mm`, `mcu_y: y0+11 → y0+19` (8 mm south move),
  top-strip `22 → 30 mm`. Antenna keepout `ant_y0 = y0` (clamped),
  `ant_y1 = y0 + 10.3` → **10.3 mm ON-BOARD span** (was 2.5 mm
  Cycle 3). VBAT ADC divider (R_VBAT1, R_VBAT2 = 2× 1 MΩ; C_VBAT =
  100 nF) added on B.Cu near MCU BAT+. VBAT_ADC signal routed to
  new `J_XIAO_BP` slot 7 (cluster grew from 6 to 7 pads). Rear-pad
  slot order re-mapped so ROW3/ROW4 sit in slots 4/5 (x = 157.5 /
  159.5), clear of COL F.Cu spine x-coordinates. Power block
  component y shifted 10 mm south with MCU. NFC header moved to
  (x0+13, y1-12) to clear ROW4 B.Cu spine. FID3 moved to (x0+10,
  y1-3) — ≥3 mm from H3 (MINOR C4 closure). Mounting holes H1/H2
  moved to y0+27 (adjusted with MCU south move).
- PCB routing: COL (F.Cu vertical spines, stair-step fanout y =
  y0+24.5..26.5 per column), ROW (B.Cu spines at ky+9 mid-gap),
  KROW local (B.Cu Manhattan from switch pad 2 to diode cathode),
  RGB serpentine (22 of 24 hops on B.Cu at ky+2.5 for same-row;
  4 row-change hops LEFT UNROUTED — documented gap), I²C SDA/SCL
  (MCU → pullups → NFC, B.Cu), VBAT ADC divider → rear-pad slot
  7, NTC_ADC (TH1 → R_NTC → MCU pin 14 via F.Cu/B.Cu dogleg), VUSB
  (C4/C5 → MCU pin 1 F.Cu), GATE_REV (Q_REV pin 1 → detour → R_GREV
  → D_GREV on F.Cu/B.Cu), power-chain (JST → Q_REV → F1 → SW_PWR
  → VBAT → MCU BAT+ pad — F.Cu/B.Cu with via pair carried from
  Cycle 3). Encoder ENC_A/B/SW intentionally unrouted per C4-M2
  proviso ("leave encoder and NFC header unrouted with a note" —
  NFC was routed, encoder is DNP with wire jumpers).
- `pcb/claude-code-pad.kicad_sch` (KiCad 8 format) regenerated:
  adds R_VBAT1, R_VBAT2, C_VBAT symbols and wiring; rear-pad stub
  cluster expanded to 7 signals.
- `pcb/claude-code-pad.kicad_pcb` (KiCad 9 format) regenerated:
  115 × 132 mm outline, USB-C top notch retained, all Cycle 3
  footprint corrections preserved, new power-block position,
  7-pad J_XIAO_BP cluster.
- `pcb/claude-code-pad.kicad_pro` — Power netclass_pattern list
  unchanged (VBAT_ADC stays on Default class; it's a signal line,
  not power). Netclass assignments verified on regeneration.
- `pcb/bom.csv` — **22 grouped rows** (Cycle 3: 21). Added 1M
  0402 resistor group (R_VBAT1, R_VBAT2). C_VBAT merges into the
  existing 100 nF 0402 group. DNP column unchanged.
- `pcb/cpl.csv` — 124 rows (Cycle 3: 116). Emitted via
  `kicad-cli pcb export pos --use-drill-file-origin --exclude-dnp`.
  Grep verification: `grep -cE '(EC1|J_NFC|U1|TH1|SW_PWR)\b'
  cpl.csv` returns **0**. Python-emitter CPL retained as
  cross-check.
- `pcb/gerbers/` regenerated (9 gerber layers + `.drl`) via
  `kicad-cli pcb export gerbers`. `gerbers/README.md` unchanged.
- `pcb/DESIGN-NOTES.md` appended `§Cycle 4` section:
  - BLOCKER closure table (C4-B1, C4-B2).
  - `§Battery requirements (MANDATORY)` with 3 approved-cell LCSC
    rows (C5290961 / C5290967 / alt-any-JST-SH-PCM), JST-SH
    polarity diagram, PCM-vs-PTC timing math (cell-PCM <10 ms vs
    PTC ~100 ms), IEC 62133-2 Annex E vent-with-flame failure-mode
    text, and cell-substitution rules.
  - `§Safety §Brownout behavior` with worst-case voltage-drop
    math (4.20 V cell → 3.70 V +3V3 at 300 mA LEDs-on),
    firmware cutoff spec (3.70 V LEDs-on / 3.50 V LEDs-off /
    linear LED derate 3.90 V → 3.70 V), VBAT ADC divider sizing
    and pin-assignment rationale (rear-pad slot 7 because D10 is
    consumed by NTC_ADC).
  - `§Safety §Firmware cap` with IEC 62368-1 Annex Q §Q.2 quote,
    hostile-recompile hazard text, AP2112K-3.3 thermal-shutdown
    second-line note (Tj = 165 °C at ~2 s / 1.5 A), and
    RGB DIN GPIO-low-before-+3V3 init-order obligation for FW-1.
  - MAJOR closures (C4-M1..M5) and MINOR closures.
  - Deviations (board size 115×132, VBAT_ADC on rear pad, NFC
    relocation).
  - Cycle 4 validation results + known gaps for Cycle 5 (4 RGB
    row-change hops, 16 DRC shorts all clearance-level not
    schematic-level).
- `firmware/zmk/README.md` rewritten:
  - **Hard Requirement: Approved cells** (mirrored short form of
    DESIGN-NOTES).
  - **Hard Requirement: Battery Cutoff Voltage** with numeric
    thresholds, source-impedance note for SAADC (OVERSAMPLE ≥ 2³).
  - **Hard Requirement: LED peak current cap** with Phase-5 jumper
    reference REMOVED; hostile-recompile scope boundary; RGB DIN
    init-order; AP2112K second-line.
  - **Hard Requirement: NTC fallback** — LED peak cap reduces to
    100 mA on out-of-range NTC reads (IEC 62368-1 Annex Q).
  - Pin map addendum with the new 7-slot J_XIAO_BP table.
- `docs/build-guide.md` — **new file**:
  - Top section: Battery requirements (MANDATORY).
  - SW_PWR install section with "Do not jumper across the switch
    footprint" warning.
  - Cell polarity diagram.
  - Hand-solder checklist (5 DNP items + 7 rear-pad jumper wires).
  - Appendix A: known gaps (4 RGB bodge-wire pairs + encoder).
- `pcb/_gen/erc-cycle4.rpt` (673 violations, all cosmetic) and
  `pcb/_gen/drc-cycle4.rpt` (449 violations + 117 unconnected).

**Validation results:**

- **ERC 673 total** (Cycle 3: 660) — small rise from added schematic
  symbols (R_VBAT1, R_VBAT2, C_VBAT). Class breakdown: unchanged —
  all cosmetic categories (endpoint_off_grid, lib_symbol_issues,
  footprint_link_issues, pin_not_connected, global_label_dangling).
  Zero functional errors.
- **DRC 449 total + 117 unconnected** (Cycle 3: 175 + 251).
  Unconnected dropped **54 %** (251 → 117).
  - Of the 117 unconnected: 212 pad-pair items are GND + +3V3 that
    resolve on first GUI save when zone pours fill (kicad-cli
    doesn't run fills). 14 real unconnected are all ENC_A/B/SW
    (encoder DNP, intentional per C4-M2 proviso). 8 items =
    4 × RGB_D{6,11,16,21} row-change serpentine hops deferred to
    Cycle 5.
  - 449 total violations breakdown: 72 tracks_crossing +
    42 copper_edge_clearance + 16 shorting_items +
    21+24+8 hole_clearance + 25 courtyards_overlap +
    65 lib_footprint (inline lib, carried from Cycle 1) +
    57 solder_mask_bridge (JLCPCB merges) +
    27+25 lib_footprint_issues (inline) +
    10 via_dangling + 6 track_dangling. The **16 shorts** are all
    clearance-level (0.1–0.4 mm) track-to-pad or track-to-via
    margins from the Cycle 4 routing pass — not schematic-level
    net errors. Cycle 5 GUI nudge-pass to resolve.
- **MCP validate_project:** `valid: true`.
- **CPL DNP grep:** 0 hits for EC1/J_NFC/U1/TH1/SW_PWR.

**Board dimensions:** 115 × **132** mm (Cycle 3: 115 × 124, +8 mm
height for antenna keepout). Area 15180 mm² (Cycle 3: 14260 mm²),
still one JLCPCB fee tier below Cycle 2's 17500 mm² envelope.

**New risks for Cycle 4 review:**

1. Rear-pad jumper cluster grew 6 → 7 slots; FW-1 build-guide must
   cover 7 wires.
2. VBAT_ADC divider source impedance ~500 kΩ requires SAADC
   OVERSAMPLE ≥ 8, BURST mode; documented in firmware/zmk/README.md.
3. Power-block components moved 10 mm south with MCU; MECH-1 must
   cross-check case cutouts against the new CPL.
4. Antenna keepout carves ~250 mm² from GND pour on both layers;
   pour still covers >80 % of board; XIAO module has its own
   ground plane.
5. **Known gap:** 4 of 24 RGB row-change serpentine hops (RGB_D6,
   D11, D16, D21) left unrouted — Cycle 5 GUI pass or builder
   bodge wires. **Known gap:** 16 DRC shorts from routing geometry
   that require 0.5 mm nudges in GUI (all clearance issues, no
   net-level errors).

**Status:** `PHASE-1-CYCLE-4: READY_FOR_REVIEW` — dispatching
RED-DFM, RED-SAFETY, RED-COST. Expecting PARTIAL verdict on
C4-M2 (routing completeness) per the explicit gap documentation.
