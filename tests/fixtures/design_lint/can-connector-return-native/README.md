# Two-pin CAN connector return review fixtures

These tooling-owned schematics are synthetic regressions and do not copy
external project data.

`fault.kicad_sch` has a complete generic two-contact connector with one contact
on each exact CANH/CANL net from a synthetic fitted transceiver. It has no
connector return contact. The review rule should prompt without requiring a
connection to board ground.

The valid control reuses
[`can-generic-connector-native/fault.kicad_sch`](../can-generic-connector-native/fault.kicad_sch),
which has generic CAN contacts plus a separately identified and connected GND
contact. The larger connector should stay outside the two-contact rule.

The digest-pinned KiCad 10.0.0 and 10.0.5 lane exports each source twice and
compares the normalized netlist and exact rule finding. Source digests are
registered in `kicad_tooling/ci_hosted_can_connector_return_cases.py`.

| Case    | Tooling-owned source                           | SHA-256                                                            |
| ------- | ---------------------------------------------- | ------------------------------------------------------------------ |
| Fault   | `can-connector-return-native/fault.kicad_sch`  | `14f85d29d81211f217d520b44057c94fd42b5249b3e243ec284238194be37618` |
| Control | `can-generic-connector-native/fault.kicad_sch` | `b2b88fe7275b176ce214b3723d83844bc71549770ebcdfc3f278ba5792a4cc13` |
