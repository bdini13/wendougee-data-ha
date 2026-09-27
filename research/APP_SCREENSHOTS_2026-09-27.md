# Official-app screenshot audit · 2026-09-27

Source: ten owner-supplied screenshots, described as taken earlier that day.
Raw screenshots contain personal identifiers and are not copied into the repository.
Screenshots establish UI evidence, not verified BLE write semantics.

| App evidence | Interpretation / HA disposition |
| --- | --- |
| App V3.1.5(260908) | Recorded installed-app provenance; supersedes “unknown app version.” |
| OTA label V18101(203) | Installed-versus-offered firmware remains unresolved; no OTA action. |
| Separate steam/brew enables, target, Pulse/Full speed | Existing enable controls; targets/mode read-only pending write validation. Live configuration matches Full speed. |
| M-key pressure 9 bar, time 30 s, Record enabled | Pressure/time match cached reads; recording-toggle mapping unresolved. |
| Constant pressure 9bar, 65 mL, marked Bound | Supports separate binding UI; does not resolve physical-paddle activation or coil 154. |
| Product/Clean/Connection records; latest 150; Cloud badges | App history exists, but machine-stored BLE retrieval is unproven. Local HA journal is independent. |
| History temperatures ~92–93 labelled °F | Inconsistent with live ~198 °F; possible label/conversion defect, not proof of wire units. |
| F.V. mL/s, W.V. g/s, Flow mL, Wt. g | Keep instantaneous flow, weight rate, pumped volume and cup weight distinct. Weight-rate signedness remains unresolved. |
| Water-shortage alarm enable toggle | Distinct from active water-shortage telemetry; no alarm-disable testing. |
| Engineering readings and component diagram/toggles | Read-only settings can be surfaced; raw pump/solenoid actuation excluded. Diagram labels are not independently verified pressure limits/plumbing specifications. |
| Wi-Fi disconnected | Does not imply the ESPHome proxy is offline; separate network links. |
| Themes/language, factory reset, upload logs | App preference ownership unresolved; destructive/reset/upload actions not automated. |

Remote HEAD checks: GeeFlow `cf5fe5f659e659718ca98430691503794001fb39`,
LitaLite `3a26b7ec114ff03f228dd8cfc232b3885cd523cb`, Crema
`930879755a76cefef010c05a39485e09cf59b819`; unchanged since the prior audit.
No new machine command was discovered or tested in this screenshot/release pass.

Recommended control validation remains attended and separate: temperature limits,
heating-mode semantics, M-key recording/binding, final weight selection, and then
profile activation only after the conflicting protocol evidence is resolved.
