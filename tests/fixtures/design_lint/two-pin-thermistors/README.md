# Synthetic two-pin thermistor regressions

These schematics are tooling-owned synthetic fixtures with minimal embedded
symbol geometry. They use exact validated stock identities and do not represent
a selected sensor, footprint, temperature range, or application.

| Fixture                                     | Symbol identity            | Topology                                | Expected result |
| ------------------------------------------- | -------------------------- | --------------------------------------- | --------------- |
| `same-net-thermistor.kicad_sch`             | `Device:Thermistor_NTC`    | Both fitted pins share one local label. | Review TH1.     |
| `distinct-nets-thermistor.kicad_sch`        | `Device:Thermistor_NTC`    | The pins use separate sense labels.     | No finding.     |
| `same-net-thermistor-ptc.kicad_sch`         | `Device:Thermistor_PTC`    | Both fitted pins share one local label. | Review TH1.     |
| `distinct-nets-thermistor-ptc.kicad_sch`    | `Device:Thermistor_PTC`    | The pins use separate sense labels.     | No finding.     |
| `same-net-thermistor-us.kicad_sch`          | `Device:Thermistor_US`     | Both fitted pins share one local label. | Review TH1.     |
| `distinct-nets-thermistor-us.kicad_sch`     | `Device:Thermistor_US`     | The pins use separate sense labels.     | No finding.     |
| `same-net-thermistor-ntc-us.kicad_sch`      | `Device:Thermistor_NTC_US` | Both fitted pins share one local label. | Review TH1.     |
| `distinct-nets-thermistor-ntc-us.kicad_sch` | `Device:Thermistor_NTC_US` | The pins use separate sense labels.     | No finding.     |
| `same-net-thermistor-ptc-us.kicad_sch`      | `Device:Thermistor_PTC_US` | Both fitted pins share one local label. | Review TH1.     |
| `distinct-nets-thermistor-ptc-us.kicad_sch` | `Device:Thermistor_PTC_US` | The pins use separate sense labels.     | No finding.     |

The review reports schematic net assignments only. It does not establish
whether a thermistor is required, the correct NTC/PTC type, its rating,
placement, footprint mapping, PCB copper, or physical population. The rule
recognizes only the six listed stock identities, after checking that the
native pin inventory has exactly two distinct pin numbers. Unconfirmed
variants, including 3-wire and 4-wire symbols, remain outside the predicate.

The exact native fixture lane runs repeated exports with digest-pinned KiCad
10.0.0 and 10.0.5. It compares normalized netlists and lint results; it does
not establish electrical or manufacturing approval.

Source SHA-256 values:

| Fixture                                     | SHA-256                                                            |
| ------------------------------------------- | ------------------------------------------------------------------ |
| `same-net-thermistor.kicad_sch`             | `be417443337f223c51b6caa7305038544df0e5342e90cae91d5fce6a797ac26f` |
| `distinct-nets-thermistor.kicad_sch`        | `7a6753de56bf6985d4fd218b96e1f9b951541fd103920baaea503b8999f02a06` |
| `same-net-thermistor-ptc.kicad_sch`         | `431ad6fa27575e7670331ff46f6221efe0ab6ccbe3978ba89c516e07b299bdb8` |
| `distinct-nets-thermistor-ptc.kicad_sch`    | `4ac3d3e6951e84a7d927bb0844f1568f4f195692de6aeb7e395012081312bb84` |
| `same-net-thermistor-us.kicad_sch`          | `7af1b5ff0666f70a8866266a5815de7d9f59308e9456bd2b10a456d84589980b` |
| `distinct-nets-thermistor-us.kicad_sch`     | `23c7a0a02eb48dfff8ce009b102247c896ebee3d4bf24d537c6a0ee7a3990237` |
| `same-net-thermistor-ntc-us.kicad_sch`      | `bb47a0526551c53dd9aee01b883462617c279a2bf083e0dd9a36462022177741` |
| `distinct-nets-thermistor-ntc-us.kicad_sch` | `ce3eb6a2cf144649b5d896b7459b88f82fffa6b10373b939488a96474550e9f3` |
| `same-net-thermistor-ptc-us.kicad_sch`      | `c0be1a4de2ec6af321ac5cfbba968a510492bc2033dc4faf3a8781f1d6b664bd` |
| `distinct-nets-thermistor-ptc-us.kicad_sch` | `b0948f3d294c3510c18ea7f0e9142278e2988241b993c0a8234c380160505ed7` |
