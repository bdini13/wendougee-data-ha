# Observability deployment · 2026-09-27

Owner requested implementing the researched dashboard improvements, updating
GitHub/README and testing read-only. No new machine control was invoked.

## Delivery

- Installed integration **0.5.1** on unchanged HA **2026.9.1**.
- Full backup `ea38f9a7`: complete, no job errors, database included, 390840320 bytes.
- Staged 0.5.0 and then a reviewed 0.5.1 partial-capture/terminal-timer correction;
  each archive checksum and HA configuration check passed before restart.
- Final archive SHA-256:
  `92726bf05ac7626ee1968b5849ffbd2bdeceb87afde008df5e710fbb2007e8d0`.
- Component rollback copies retained:
  `/config/.wendougee_data_rollback/0.4.0-20260927-observability` and
  `/config/.wendougee_data_rollback/0.5.0-20260927-observability`.
- Dashboard configuration compared with the previous source before replacement,
  backed up privately, saved through HA's API and verified by exact readback.
- Five existing read-only entities enabled via registry APIs: scale weight,
  heating mode, manual time, manual pressure and alarm-detection enable. Existing
  entity IDs preserved; weight-rate remains disabled. Registry backup kept private.
- Optional notification blueprint copied to HA, with no recipient chosen and
  no automation instantiated or notification sent.

## Verification

- **157 protocol/package + 111 HA framework tests = 268 passing.** Tests use
  simulated Bluetooth; network access is disabled in the HA test environment.
- Ruff lint/format, Python compilation, five JSON documents and `git diff --check`
  passed. An initial local test invocation used an obsolete Python 3.9 environment
  and failed collection; the supported Python 3.13/3.14 environments passed.
- GitHub Validate's two jobs passed for implementation `20a2475` and patch `36e6605`.
- Both existing private shot traces independently revalidated all 720 frames each.
  Each replay yielded one shot, 66 mL shot volume and 66 mL cumulative water;
  journal timers were 22.4 s and 26.8 s, with 48 and 56 curve samples respectively.
  Replays used no device connection and did not modify live history.
- All **41 dashboard entity references** present and available across four views.
- Four current Markdown templates and three maintenance-state branches rendered;
  the populated journal branch also rendered with synthetic data through HA's
  template endpoint. The native image endpoint returned HTTP 200 and SVG content.
- Initial final-runtime verification: loaded 0.5.1, successful telemetry, no failed
  polls since restart, idle, no unknown state bits, both boilers disabled and all
  uncertainty locks clear. This is a deployment check, not a long-duration soak.

## Preserved state and remaining gates

Brew schedule remains armed **06:30–09:00 America/New_York**, with both listeners
registered and next on at 06:30 EDT. Steam schedule remains disabled with stored
07:00–09:00 times. No setpoint, helper time or control opt-in was changed.
First scheduled hardware operation is still unverified.

Preserved four observed shots, 342 mL observed water, last-shot volume 66 mL and
the prior cleaning timestamp. The new journal begins empty: old counters cannot
reconstruct individual shots, and private replays were not imported as live events.

Browser automation timed out, so this record does **not** claim visual dashboard QA.
Phone delivery awaits the owner's recipient choice. HA 2026.9.3 upgrading remains
deferred until the first scheduled cycle is verified. Firmware updates and all
unverified engineering/profile controls remain excluded. No attended shot or
cleaning test was required or performed during deployment.
