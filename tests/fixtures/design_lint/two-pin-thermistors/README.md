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
| `same-net-thermistor-ptc.kicad_sch`         | `5d7678f58af0a323961c1af73173a1dbcd52c7ad09fac43f1f0cd1545ff65762` |
| `distinct-nets-thermistor-ptc.kicad_sch`    | `452b3245be262532becb18866bf8a28dd01e9235214580fc67c74f98210daab5` |
| `same-net-thermistor-us.kicad_sch`          | `2c01ec413b9a122d7d96ead9f18a5fa470e419a89be1241e3216b0a8a7b0b56c` |
| `distinct-nets-thermistor-us.kicad_sch`     | `a0881cd4e53dc6b4d0de89401d81d4714254b52db1f12afa6163a6263307947f` |
| `same-net-thermistor-ntc-us.kicad_sch`      | `4953e4dbfb058fc5b563249736e823b296016504e3782534db9761562870d59f` |
| `distinct-nets-thermistor-ntc-us.kicad_sch` | `bbc82a02e7a9e17d63b5d1d0541b8763b836e0934a43eab99c92980f8ac3409f` |
| `same-net-thermistor-ptc-us.kicad_sch`      | `0f43667c614d9c8c72f257101b173551e947f280ca11a47f32868b40d11320ef` |
| `distinct-nets-thermistor-ptc-us.kicad_sch` | `4ca99c33fa15936b648832d1d116b578cf12433b40653f3d82120751c4f40301` |
