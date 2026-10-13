# Synthetic two-pin thermistor regressions

These schematics are tooling-owned synthetic fixtures with minimal embedded
symbol geometry. They use the exact `Device:Thermistor_NTC` identity and do not
represent a selected sensor, footprint, temperature range, or application.

| Fixture                              | Topology                                            | Expected result |
| ------------------------------------ | --------------------------------------------------- | --------------- |
| `same-net-thermistor.kicad_sch`      | Both fitted thermistor pins share one local label.  | Review TH1.     |
| `distinct-nets-thermistor.kicad_sch` | The pins use separate sense labels.                 | No finding.     |

The review reports schematic net assignments only. It does not establish
whether a thermistor is required, the correct NTC/PTC type, its rating,
placement, footprint mapping, PCB copper, or physical population. The rule
recognizes only exact stock identities `Device:Thermistor` and
`Device:Thermistor_NTC`, after checking that the native pin inventory has
exactly two distinct pin numbers. Other variants, including 3-wire and
4-wire symbols, remain outside the predicate.

The exact native fixture lane runs repeated exports with digest-pinned KiCad
10.0.0 and 10.0.5. It compares normalized netlists and lint results; it does
not establish electrical or manufacturing approval.

Source SHA-256 values:

| Fixture                              | SHA-256                                                            |
| ------------------------------------ | ------------------------------------------------------------------ |
| `same-net-thermistor.kicad_sch`      | `be417443337f223c51b6caa7305038544df0e5342e90cae91d5fce6a797ac26f` |
| `distinct-nets-thermistor.kicad_sch` | `7a6753de56bf6985d4fd218b96e1f9b951541fd103920baaea503b8999f02a06` |
