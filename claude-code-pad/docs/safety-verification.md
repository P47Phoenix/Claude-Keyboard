# Claude Code Pad — safety verification plan

Phase 3 Cycle 2 deliverable (RED-SAFETY SF-B5). IEC 62368-1 Annex Q
§Q.4 requires documented evidence that the safety-relevant firmware
behaviour actually behaves as specified. This file is the contract
for how that evidence is produced.

The plan has three strata:

1. **Unit (`ztest`):** native-sim host testing of the cap registry
   and the graceful-shutdown latch. Runs in CI, no hardware
   required.
2. **Bench (`docs/safety-verification-bench.md` -- separate file,
   filled in as data lands):** real-silicon verification of the
   SAADC, NTC decode, undervolt cutoff, WDT timeout, broken-wire
   detection, and physical-range sanity. Needs a XIAO nRF52840,
   a bench supply (0..4.5 V), and a thermal test chamber or hot-
   air soldering station.
3. **BLE MITM test plan (§BLE below):** demonstrates that an
   attacker without user cooperation cannot complete pairing.

## 1. Unit (`ztest`)

Scope: the cap registry, the TTL decay, the fail-dark default, the
graceful-shutdown latch idempotency, and the "cap cannot be
resurrected after latch" property (SF-M2).

Source: `firmware/zmk/tests/ccp_safety/src/test_cap_registry.c`.

Run:

```bash
cd ~/ccp-build
export PATH=$HOME/.local/bin:$PATH
export ZEPHYR_SDK_INSTALL_DIR=$HOME/zephyr-sdk-0.17.0
export ZEPHYR_BASE=$HOME/ccp-build/zephyr
./zephyr/scripts/twister \
    -T /var/home/meconnelly/Documents/GitHub/Claude-Keyboard/claude-code-pad/firmware/zmk/tests/ccp_safety \
    --platform native_sim/native/64
```

Expected outcome (Cycle 2 baseline):

```
SUITE PASS - 100.00% [ccp_safety_cap_registry]: pass = 6, fail = 0
```

CI hook: not wired yet (this repo has no GitHub Actions at the
time of writing). Tracked as a Cycle 3 follow-up.

## 2. Bench protocol (to run against real hardware)

### 2.1 VBAT undervolt cutoff

Setup:

- XIAO nRF52840 with the Cycle 2 UF2 flashed.
- Bench supply feeding the BAT+ pin via a 1 Ohm current-sense
  resistor. Scope on the RGB_DIN_MCU pin + cell voltage.
- RGB effect set to solid-white full-brightness (limited by the
  Kconfig BRT_MAX=20 hard cap to 300 mA aggregate).

Procedure:

1. Start at V_cell = 4.10 V. Confirm cap=100, LEDs at the expected
   brightness, log shows `VBAT=4100 cap=100 leds_cut=0`.
2. Ramp down at 10 mV/s. Record V_cell at which:
   - derate first bites (log shows cap<100): expected **4.00 V**
   - leds_cut latches (cap=0): expected **3.80 V**
   - graceful_shutdown fires: expected **3.50 V**
3. Verify hysteresis: after leds_cut latches at 3.80 V, ramp V_cell
   back up. LEDs should re-enable only once V_cell >= **3.90 V**.
4. Verify the physical-range band (SF-M7): set V_cell to 2.7 V;
   expect graceful_shutdown with reason "VBAT out of physical range".

Pass criteria: all three thresholds within +/- 20 mV of the nominal
values. Hysteresis gap >= 90 mV.

### 2.2 VBAT broken-wire detection

Setup: as above, plus a solder joint on the VBAT_ADC bodge wire
that can be physically opened mid-run.

Procedure:

1. Run with the wire connected for 5 minutes at V_cell = 4.00 V.
   Expected log: stable `VBAT ~= 4000 mV`, cap=100.
2. Physically open the bodge wire.
3. Expected log within 500 ms: `max-abs-residual > 100 mV` warning.
4. Within 2 consecutive windows (~500 ms total at 250 ms cadence),
   expected log: `graceful shutdown: VBAT_ADC broken wire`.
5. Verify LEDs are off, `bt_bas_set_battery_level(0)` was called,
   BLE LE connections are dropped, advertising has stopped.

Pass criteria: latch time < 1 s; no false-latch under a controlled
300 mA LED burst with the wire connected.

### 2.3 NTC over-temp + floating-pin detection

Setup: hot-air station or small hot plate on the NTC body, plus a
bench power supply replacement for the divider to simulate
floating/shorted.

Procedure (over-temp):

1. Heat NTC to 40 degC (confirmed on an external reference probe).
   Expected: log shows `NTC ~40 degC cap=100`, no over-temp flag.
2. Heat to 52 degC. Expected: log shows `NTC over-temp 52 degC --
   fallback 100 mA cap`, effective cap drops to 33.
3. Cool back to 45 degC. Expected: cap returns to 100.

Procedure (floating pin):

1. Desolder the NTC bodge wire.
2. Within one sample interval: log should show either the OOR
   branch OR the `ntc_floating_probe` HIGH-then-release branch
   firing, both ending in cap=33.

Pass criteria: over-temp fires within 1 degC of the configured
threshold (default 50 degC); floating-pin detected within 2 s of
the bodge being opened.

### 2.4 Watchdog-driven reset

Setup: UART / RTT log capture running. Build with
`CONFIG_WATCHDOG=y`, `CONFIG_WDT_NRFX=y`, and the Cycle 2 aggregator.

Procedure:

1. Patch the thermal guard's k_work handler to return immediately
   without calling `ccp_safety_wdt_feed(CCP_WDT_THERMAL)`.
2. Flash, boot, observe: battery guard continues to pet its side,
   but the aggregator never sees both flags set.
3. Expected: MCU resets within **4000 ms + 250 ms aggregator
   interval** = 4.25 s of boot. (Cycle 3: window raised from 2000 ms
   to give the 2000 ms thermal-sample cadence one full interval of
   slack -- a single missed sample no longer spuriously resets.)
4. On reset, `ccp_rgb_init_safe` SYS_INIT runs, log shows
   `RGB_DIN_MCU pre-driven LOW`, LEDs stay dark until the first
   good NTC sample lands post-reboot.

Pass criteria: reset fires within 4.5 s, RGB never lights during
the reset sequence.

## 3. BLE MITM test plan

Goal: demonstrate that an attacker who does not control the host
cannot silently pair with the Claude Code Pad and gain HID access.

### Threat model

- Attacker is within BLE range (~10 m open-air at +4 dBm TX).
- Attacker has a second BLE-capable device (phone or SDR).
- User has NOT placed the device in pairing mode; the pad has
  existing bonds to two trusted hosts.
- Goal: prevent attacker from completing pairing without user
  confirmation on the trusted host side.

### Positive tests (must pass)

1. Cold-boot the pad. User holds Fn+BT0 for 3 s to enter pairing
   mode. `BT_BONDABLE=y` is asserted for 60 s.
2. Trusted host (Linux `bluetoothctl`) initiates pairing.
3. Numeric-comparison challenge appears on the host. User confirms
   on host.
4. Pair completes; subsequent connections auto-resume the bond.

### Negative tests (must fail to pair, for attacker)

1. Attacker device (e.g., nRF Connect on phone) tries to initiate
   pairing while pad is NOT in pairing mode. Expected: SMP pairing
   request is rejected at the peripheral (`CONFIG_BT_BONDABLE=n`).
2. Attacker initiates pairing DURING the pairing-mode window but
   attempts to fall back to legacy pairing (no SC). Expected:
   pairing rejected (`BT_SMP_SC_PAIR_ONLY=y`).
3. Attacker initiates SC pairing during the window but attempts
   "Just Works" (no MITM). Expected: pairing rejected
   (`BT_SMP_ENFORCE_MITM=y`).

### Observation

Use `btmon` on Linux or Wireshark with an nRF Sniffer to capture
the SMP exchange on each negative test. Confirm the peripheral
sends a Pairing Failed PDU with the expected reason code:

- `BT_SMP_ERR_AUTH_REQUIREMENTS (0x03)` for the MITM rejection.
- `BT_SMP_ERR_ENCRYPTION_KEY_SIZE` or `BT_SMP_ERR_PAIRING_NOT_SUPPORTED`
  for the legacy fallback rejection.

Results are logged inline in this file after each bench session.

## 4. cap-semantics note

ZMK's public `zmk_rgb_underglow_*` API does not expose an absolute-
brightness setter (only relative `change_brt(direction)` and
on/off). Our cap registry therefore implements the cap as a
**ceiling** not as a **target**: effective brightness is always
`min(user_brightness, CONFIG_ZMK_RGB_UNDERGLOW_BRT_MAX,
 strip_off ? 0 : unbounded)`.

For Annex Q compliance the two things that matter are:

- **Absolute peak cap.** Enforced by the Kconfig
  `ZMK_RGB_UNDERGLOW_BRT_MAX=20` (300 mA / 25 LEDs / 60 mA per
  LED -> 20% duty) plus the hardware LDO ceiling.
- **The go-dark path.** Enforced by
  `ccp_safety_graceful_shutdown()` calling `zmk_rgb_underglow_off()`.
  The registry's effective-cap=0 transition also toggles the
  strip via `zmk_rgb_underglow_off()`.

Neither path needs a continuous brightness setpoint. The finer-
grained derate curve (4.00 V -> 3.80 V at 100% -> 0%) remains a
user-facing visual cue: the LEDs visibly dim as the derate ramp
crosses the user-configured brightness, then go dark when cap hits
0. Cycle 3 adds a Custom RGB driver that honours set_brt(x) if
this is deemed insufficient.

## 5. NTC-missing visual indicator (SF-M11)

Status: spec'd, stub in place, implementation deferred.

Goal: a persistent `CCP_CAP_THERMAL = NTC_FALLBACK_CAP=33` state
should be distinguishable from a plain low-battery dim. Both
conditions produce "LEDs are visibly darker than normal".

Planned Cycle 3 implementation: when the thermal guard has latched
on out-of-range for > 2 consecutive samples, blink LED 25 (the 2U
Enter key's LED, bottom-right) at 1 Hz full-cyan while the rest of
the strip runs normal dim. Requires a single-LED-override API from
ZMK that is not present today (tracked upstream as a feature
request).

Meantime, the distinguishing evidence is in the log:

```
[WRN] ccp_thermal_guard: NTC_ADC OOR: XXXX mV -- fallback 100 mA cap
```

Builders should check this after any "LEDs are unexpectedly dim"
report.
