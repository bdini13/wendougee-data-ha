# Offline firmware, Wi-Fi and recovery audit · September 29, 2026

## Outcome and scope

The app contains a real IoT/MQTT implementation and distinct host/Bluetooth
upgrade paths. A public vendor API returned a cloud broker address. This is
stronger evidence than a Wi-Fi settings screenshot, but does **not** establish
a local LAN API, DATA S compatibility, or the owner's machine's network state.

An Android app package was acquired and analyzed offline. **No machine firmware
image was obtained**, and no stock firmware restore or bootloader unlock has
been established. An APK is phone software, not a machine recovery image.

No app was installed or run. No machine connection, BLE operation, Wi-Fi
provisioning, MQTT connection/subscription, firmware update, bootloader command,
USB test or enclosure access occurred. No HA settings or schedules changed.
Only public pages and unauthenticated read-only metadata requests were used.
No account/device identifiers were supplied or authentication bypass attempted.

| Requested work | Progress | Remaining evidence |
|---|---|---|
| 1. App Wi-Fi/update analysis | App-specific MQTT, Wi-Fi and upgrade components located; public broker discovery confirmed | Exact DATA S message envelope, authenticated routing and LAN capability |
| 2. Firmware acquisition/analysis | Distribution traced; app downloaded, hashed and inspected; update metadata paths located | Device-matched stock firmware, board identification, image signature/boot checks |
| 3. Backup/recovery | Recovery prerequisites and asset inventory defined below | Manufacturer-supported recovery route and complete machine backup; neither verified |

## Artifact provenance

[Official download landing page](https://api.wendougee.com/) links the stable
Android release to [Tencent's package page](https://a.app.qq.com/o/simple.jsp?pkgname=com.g472631889.stf),
and a beta to [PGYER](https://www.pgyer.com/aEoztLyE). The separate daily-build
page was password-protected; it was not accessed beyond its public landing page.

The Tencent stable listing exposed version 3.1.6, size 257003265 bytes, and
published MD5 `30FD357124AB90F7C9AECA6A15616D9A`. Its download host timed out
from this workspace. That APK was **not** acquired or analyzed.

The analyzed artifact is **3.1.0 (260219), ARM64**, from the public
[APKPure download listing](https://apkpure.net/wen-dou-ji-e-bar/com.g472631889.stf/download).
The archive's SHA-1 matches that listing's ARM64 variant. Do not confuse this
with the other architecture's advertised hash, with 3.1.6, or with the owner's
iOS app. The older Android package can contain stale/debug implementation paths.

| Artifact | SHA-256 |
|---|---|
| Downloaded XAPK | `012323162236ce9ca0bf9a269ef9e9446810c9459107072dd4ad73bf2ef0c721` |
| Base APK | `ae0872ed1af44fad3233ae7795f256542e10b4657fb3f697f7f4c46063de05ec` |
| ARM64 split APK | `a0ea01d610083c37135de8dc022ad37a70c013d09b0caa021e407a12401c78f0` |
| Extracted Dart AOT `libapp.so` | `232176d4fb084c9f909dd5d822bbe30a12515ac2f335d703a5bde9fef7a5fc35` |
| Bundled `ble.html` | `696ca1ecf09aa38c3d6d789972cbd16270d40e26532aa21c467562da069717f4` |
| Bundled `common.js` | `96b6185b9ae87c39b45aea11279bf9555a7ab15af78f9884e60cbc8deaa6b554` |
| Bundled `y-modem-send.class.js` | `28858ee303f94809a1cb4bcd78230a958ad9b2a5b81b9486acce51a5433f65df` |

Both APKs carry the same signer certificate:

- SHA-1: `31ca1f6e4d32308f2e5dd2b659f1cc87c3434915` (matches mirror listing).
- SHA-256: `0632f38f3cf80cfeeec2b982c6ca82f8549dc4c3c6d75b655517e9cf3607b920`.

A narrow offline check using Python `cryptography` verified each APK's v2
RSA/SHA-256 signed-data signature, certificate/public-key agreement and chunked
content digest against the [Android v2 signing specification](https://source.android.com/docs/security/features/apksigning/v2).
A single-byte content mutation was rejected for each APK. This was **not** a
full Android `apksigner`/installation validation, and the signer has not been
independently pinned against an APK downloaded from the vendor-linked stable
channel. Integrity relative to the included key is not vendor trust or proof
that the app is safe to execute. No APK was executed.

Raw packages, extracted proprietary assets and downloaded page bodies remain
in ignored private storage; only independent factual notes are published.

## Wi-Fi and MQTT findings

The AOT string inventory contains app-specific paths under
`wendougee_module_device`, not just generic dependencies:

- `service/mqtt_service.dart` and MQTT configuration, message-handler,
  reconnect, resource-manager and status-sync modules.
- `WifiSettingLogic`, `MqttService`, `MqttConfigEntity`, `IotOnlineStatus`,
  `analysisIotData`, `loadIotConnectStatus` and `configWifi` symbols.
- Wi-Fi SSID/IP fields and distinct provision/disconnect command symbols.
- API bases `https://apiserver.wendougee.com` and
  `https://us-apiserver.wendougee.com`, plus `/device/getMqttServer`.

A public GET to the discovered server-discovery path returned success and
broker `en-mqtt.wendougee.com`, port `18831`, labelled as the US service.
The target was [the vendor endpoint](https://apiserver.wendougee.com/device/getMqttServer).
Direct connections to the China API host timed out; the response was obtained
through a public HTTP text-reader service with **no credentials or private
parameters**. Treat it as a point-in-time public response, not a signed API
contract. Region selection could depend on the reader's egress rather than the
owner's location.

This confirms a vendor-cloud broker-discovery facility. It does **not** tell us:

- Whether this DATA S hardware/firmware implements the same IoT path.
- Whether local MQTT or any LAN-only API is available.
- Whether the broker uses TLS; a port number cannot establish encryption.
- Which credentials, topics, permissions or payloads apply to the owner.
- Whether all BLE controls have an IoT equivalent.

No broker connection or topic enumeration was attempted. Developer LAN URLs
embedded in the app are development-server clues, **not** evidence of a machine
HTTP interface and were not probed.

The vendor-linked [public beta build history](https://www.pgyer.com/app/build/5939163cff36f284583cd5bb1bbc9884)
also mentions a flowmeter-related correction supporting BLE and IoT in a 3.1.6
entry. The six-digit feature identifier in that note is not a Modbus function
code or a discovered register. Another entry mentions 100 ms chart updates;
that is **not** evidence of 10 Hz device telemetry or a reason to raise polling.

Recommendation: retain the working local BLE integration. Investigate Wi-Fi as
a possible additional transport only after identifying its device-specific
protocol and offline behavior; do not introduce a mandatory vendor-cloud
dependency into this project.

## Firmware-selection and transfer findings

### Metadata

The AOT image contains `/app/device.upgrade/get_version` and
`/app/device/getBleVersion`, with separate host/Bluetooth upgrade page classes.
Public unauthenticated BLE-version requests returned code 1021, not logged in.
The host-version request returned 502, which does not establish either its
authentication requirements or the absence of firmware. No guessing of device
identifiers, login, or bypass followed.

The bundled legacy/debug `common.js` contains a host-update check at
`/api/device.upgrade/get_version`. It explicitly requires existing user and
device records, and sends current version, device type, account token and device
ID. It expects a new version and download URL in the response. The legacy route
returned 404; the AOT app uses a different route prefix. Do not treat the old
helper as proof of the current production HTTP contract.

The important implication is that firmware selection can be device/account
specific. A random image sharing a model name is not a recovery image for this
unit. No device-matched download URL was obtained. Archive-name inspection found
no obvious bundled machine firmware; this is not an exhaustive proof that no
encoded payload exists anywhere in the app.

### Transfer routine (offline observation only)

In bundled `ble.html`, `execYModem` turns a supplied hexadecimal payload and
filename into a file, requests 128-byte YModem data blocks, constructs an update
preparation register write, and passes start/data/end arrays back to the Flutter
host. The helper uses CRC-16 transport checks. The update preparation is FC06
register `0xFF00`, value `0x00FF`; **it was not sent and must not be added to the
HA allowlist**. This is a debug-asset finding, not a validated DATA S procedure.

A commented YModem header decodes to filename `MCC1-F4-V168.bin` and declared
length 74652 bytes. Only that header exists in the inspected location—not the
firmware payload. The `F4` label makes an STM32F4-class target a hypothesis, not
a hardware identification. The phone's ARM64 `libapp.so` says nothing about the
machine MCU's architecture.

CRC protects transfer integrity, not firmware authenticity. Neither the helper
nor its filename establishes whether the target bootloader enforces a signature,
encryption, model checks, rollback restrictions or readout protection. Separate
host/Bluetooth update screens similarly suggest multiple update domains, not
proof of any particular board/chip arrangement. App Store
[version history](https://apps.apple.com/us/app/wendougee/id1663713132) independently
mentions both host and Bluetooth upgrades.

## Backup and recovery readiness

| Asset / capability | What we have | What it does not recover |
|---|---|---|
| Home Assistant | Previously verified full HA backup and retained integration rollback | MCU firmware, bootloader, radio firmware, calibration |
| Profile/settings evidence | Private captures and repeated readback of two 167-word profile banks | Complete NVM, factory calibration, credentials or flash image |
| Android app | Private, hashed 3.1.0 archive with integrity checks above | Machine stock firmware or bootloader |
| Firmware image | Not obtained | No exact stock rollback package available |
| Hardware/service path | Manual documents an app OTA flow and a USB charging port | No verified data pins, USB bootloader, serial/JTAG/SWD or recovery procedure |

The [manual](https://cdn.webshopapp.com/shops/146778/files/490080000/wendougee-data-s-manual-en.pdf)
labels the USB connector as charging (printed page 1) and describes host OTA
with a manual restart (printed page 36). It does not establish recovery from a
failed boot or custom firmware. See [USB investigation](FIRMWARE_USB_PLAN.md).

Before any flashing or unlock experiment, all of these gates remain required:

1. Identify exact board revision, MCU/radio components and independently reported
   installed host/radio versions. Keep serial and account identifiers private.
2. Obtain vendor-matched stock images, release metadata and hashes; determine
   which bootloader/application/configuration/calibration regions they cover.
3. Establish a supported backup/export path for non-image data and determine
   whether the bootloader itself is recoverable. HA/profile backups are not enough.
4. Obtain the exact service/recovery procedure, including required equipment,
   voltage levels, image selection, interrupted-update behavior and restore checks.
5. Determine signature, anti-rollback and readout-protection behavior before
   touching protection bits. An apparent unlock can erase data; do not assume
   reversibility or apply a generic STM32 procedure to an unidentified board.
6. Prove stock restoration on suitable spare/service hardware before custom
   firmware on the daily-use machine. Preserve thermal, pressure, water-level,
   watchdog and actuator-default safety behavior in any future replacement.

There is currently **no justified bootloader-unlock command** and no verified
recovery path. No unlock, flash or physical intervention was attempted.

## Efficient next work

The highest-value missing artifact is **authenticated update metadata for this
specific unit, without selecting Upgrade**, or a matching stock image supplied
by the manufacturer/dealer. Do not publish the response if it contains tokens,
signed URLs or identifiers. Existing login credentials were not sought from
unrelated files or accounts during this audit.

Prepared questions for the manufacturer/dealer (not sent):

- Which host and radio boards/revisions does this DATA S use, and how can the
  installed versions be read without starting an update?
- Can they supply the exact stock host/radio packages, SHA-256 values, release
  notes and an interrupted-update recovery procedure?
- Which settings/calibration regions must be backed up separately?
- Is the top USB-C port charging-only on this revision; is there a documented
  data/service interface, and what equipment is supported?
- Are firmware signatures, secure boot, rollback restrictions or destructive
  readout-unlock behaviors present? Is a supported development/spare board available?
- Does DATA S Wi-Fi support a documented local interface, or only vendor IoT?

Once a matched image is available, analyze it **offline first**: container/header,
architecture/vector table, version/model markers, memory layout, validation
routine, Modbus dispatch and profile/read-size handling. Those findings can guide
bounded read-only tests without making custom firmware a prerequisite for HA.

## Repository verification

This pass changes documentation only; integration version remains 0.6.3.
All 295 tests passed (174 protocol/package, 121 HA framework), integration build,
Python compilation, JSON parsing, Ruff lint/format and `git diff --check` passed.
Private artifacts are covered by Git ignore rules. The existing CI intentionally
skips documentation-only pushes; checks were run locally. No real-hardware test
or dashboard change was performed.
