# Evidence collection

Implemented and tested offline on 2026-09-20. This tooling prepares the next
hardware-validation gate; its existence does not authorize or claim a live run.

## What the envelope records

Schema `wendougee-data-evidence/v1` stores:

- source (`synthetic` or `hardware_capture`) and privacy status;
- UTC capture time, machine model, firmware, and official-app version;
- stable capability IDs from the capability map;
- the exact allowlisted request and CRC-validated response;
- decoded values, units, known limitations, and physical-comparison status.

Decoded claims are regenerated from response bytes during validation. A document
is rejected if its request, CRC, response shape, capability IDs, units, decoded
values, or limitation text do not match the implementation. This makes the file
replayable and discourages hand-edited claims that no longer match the frame.

The envelope never collects the Bluetooth address, discovered device name, or a
Home Assistant identifier. Text fields reject common MAC-address, `WDG_Data_*`,
serial, credential, and token patterns. That is a guardrail, not proof of
anonymity: unknown configuration words may still contain device-specific data.

## Private baseline command

Install the editable development package, then invoke:

```sh
wendougee-evidence capture-baseline \
  --model "DATA S" \
  --firmware "unknown" \
  --official-app-version "unknown" \
  --output research/artifacts/private/evidence/baseline.json
```

The command describes its scope and requires typing `READ ONLY` immediately
before Bluetooth access. It requires exactly one visible `WDG_Data_*`
advertisement (and refuses an ambiguous multi-machine result), verifies
the expected GATT layout, subscribes to notifications, and sends each of these
fixed operations exactly once over one bounded session:

| Operation | Request |
|---|---|
| Telemetry | FC03, register 1404, count 22 |
| Configuration | FC03, register 0, count 37 |
| Water-alarm enable setting | FC03, register 396, count 1 |
| Operating state | FC01, coil 182, count 24 |

It does not send a control, profile, boiler-setting, cleaning, provisioning,
reset, OTA, FF55, or brew command. It does not retry an uncertain transaction.
Any failure invalidates the session, and the client disconnects. The official app
must be disconnected, the machine must be attended, and every real run requires
fresh explicit approval under `AGENTS.md`.

The writer refuses paths outside the explicit private root and refuses to
overwrite an existing file. `research/artifacts/private/` is ignored by Git.

## Offline validation and reporting

Validate a private document and print a report without raw frames:

```sh
wendougee-evidence validate \
  research/artifacts/private/evidence/baseline.json
```

The report marks present and missing operations and repeats that physical
comparison has not happened. CRC validity proves transport integrity only. It
does not prove field meaning, units, calibration, safe ranges, or machine state.

## Publication boundary

Hardware captures begin as `private_unreviewed`. Do not commit them directly.
Before extracting a minimal public fixture, inspect every byte and decoded field
for serials, names, addresses, tokens, account data, or other identifiers; record
who reviewed it and when. Preserve model/firmware/app provenance, but publish
unknowns as unknown rather than inventing metadata. The tooling does not
automatically promote or upload evidence.
