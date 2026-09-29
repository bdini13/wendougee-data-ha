# Firmware and USB investigation · September 29, 2026

The DATA S manufacturer manual (retailer-hosted PDF) labels the top connector
"USB Charging Port" on printed page 1 (PDF page 6). Intended charging use is
documented; whether data pins are connected remains unknown. No USB enumeration
or electrical test has been performed. Confirm the exact hardware revision with
the manufacturer/dealer before treating this as a PC service connection.

Printed page 36 (PDF page 41) documents app-triggered host OTA and a manual power
restart afterward. This does not identify the owner's installed firmware; the
V18101(203) app label remains ambiguous as installed-versus-offered firmware.

Recommended offline investigation:

1. Locate an official, lawfully available firmware package; record target board,
   version and hash. Keep binaries private. Do not flash during discovery.
2. Inspect official-app update metadata/package selection and integrity checks,
   without bypassing access controls or initiating an update.
3. Analyze the package offline for Modbus dispatch, response-size limits, profile
   handling and USB descriptors. Static strings are clues, not hardware proof.
4. Validate only bounded read-only hypotheses through HA with owner approval.

No package download, firmware dump, bootloader transition, flashing, enclosure
opening or USB test was performed in this pass. Existing upstream OTA notes are
not sufficient authority or DATA-S evidence for entering update mode.

Source (product diagram and OTA page visually inspected):
https://cdn.webshopapp.com/shops/146778/files/490080000/wendougee-data-s-manual-en.pdf

The retailer listing did not specify USB data capabilities:
https://espressooutlet.com/products/wendougee-data-s-espresso-machine
