# Synthetic component voltage-rating fixture

`rating-control.kicad_sch` is a tooling-owned synthetic schematic. It adapts
the existing tooling fixture at `power-path-native/fault.kicad_sch` and adds a
`PART_ID` property to capacitor C1. It contains no product design or proprietary
project data.

The pinned native export lane expects KiCad 10.0.0 and 10.0.5 to preserve C1 as
`Device:C`, footprint `Synthetic:0603`, part ID `CAP-0603-16V`, and exact pin
assignments `C1.1=VLOAD`, `C1.2=GND`. It exports the same fixture twice,
compares canonical parsed netlist hashes and normalized ERC hashes, and records
the ERC signature as the native baseline for both authored stress cases.

The control requirement uses a 24 V working rating, 15 V reviewed maximum
stress, and 0.8 maximum utilization; the inclusive calculation passes at 0.625.
The fault changes only the synthetic reviewed stress to 20 V and must fail at
0.833333.... The normalized native ERC signature remains the same because KiCad
does not evaluate the project-authored rating limit. Native export supplies
identity and connectivity evidence; the stress and rating values remain
explicit synthetic requirements, not measurements inferred by KiCad.

## Exact-version trial results

Both digest-pinned runs produced the same normalized netlist hash
`62445806a59516cbf1822b34cb4f7a1f020b6be559fa4bef87fba0fb3b91cf3e`.
KiCad 10.0.0 produced normalized ERC hash
`8945db6cb5e10cc79180475f596dec5807ca1a246be947c84ad4a3e8c6fbd17b`; KiCad
10.0.5 produced `b1f928b2543cac139c3067384c152844cae9e49e684e39e666b7d4c18445ab4b`.
Each repeated export matched its version's normalized hash. Both ERC reports
contained only warnings (`footprint_link_issues`, `isolated_pin_label`, and
`lib_symbol_issues`) and no errors. The exact command and output receipts are
generated under ignored `build/ci` directories by the acceptance test.

## Synthetic component power-rating fixture

`power-control.kicad_sch` is a tooling-owned, two-pin resistor schematic with
`PART_ID=RES-SYNTHETIC-0603`, footprint `Synthetic:R_0603`, and assignments
`R1.1=INPUT`, `R1.2=OUTPUT`. Its source SHA-256 is
`0c3f36df5ce9601d5424a9928da7c13b07199c95a4c80e9c59675c96618beba1`. The
part name, datasheet values, rating conditions, derating curve, and stress
calculation are synthetic. They describe no real component or project.

The exact-version native lane exports this schematic twice on KiCad 10.0.0 and
10.0.5, checks exact component identity and pin/net assignments, and verifies
repeatable normalized netlist and ERC-type signatures with no ERC errors. The
control uses 0.10 W expected dissipation against a 0.25 W reviewed allowable
limit at an 0.8 utilization ceiling and passes at 0.4. The fault keeps the
schematic and native evidence unchanged, changes only reviewed expected
dissipation to 0.21 W, and must fail at 0.84. ERC has no rating or thermal
model, so the same native ERC result is expected for both authored power
requirements.

## Exact-version component-rating results

On 2026-10-01, the lane exported both schematics twice through the exact
digest-pinned KiCad images selected by the public template checkout. The
normalized native netlist hashes matched between both versions and repeated
exports:

- Voltage-rating fixture: `62445806a59516cbf1822b34cb4f7a1f020b6be559fa4bef87fba0fb3b91cf3e`.
- Power-rating fixture: `b431f33ff99bbe2422151479e3c4b46a4a3102572a769c595764fdd8b5682de5`.

KiCad 10.0.0 produced normalized ERC hashes
`8945db6cb5e10cc79180475f596dec5807ca1a246be947c84ad4a3e8c6fbd17b` for the voltage fixture and
`dbcb2273e067531c5e027ac9482ccf7ede0b4e2f7bd3ac01ad83b25510664338` for the power fixture. KiCad
10.0.5 produced `b1f928b2543cac139c3067384c152844cae9e49e684e39e666b7d4c18445ab4b` and
`dbcb2273e067531c5e027ac9482ccf7ede0b4e2f7bd3ac01ad83b25510664338`, respectively. Every repeated
report matched its normalized hash; all four exports reported zero ERC errors. The voltage
control/fault remained `PASS`/`FAIL` at 15 V/20 V authored stress, and the power control/fault
remained `PASS`/`FAIL` at 0.10 W/0.21 W expected dissipation. Native export supplies identity and
connectivity evidence; only the project-authored requirements evaluate rating margins.

Exact command and output receipts are generated under ignored `build/ci`
directories by the acceptance test.

## Synthetic connector contact-rating fixture

`contact-control.kicad_sch` is a tooling-owned two-pin connector with
`PART_ID=SYNTHETIC-HEADER-2P-3A`, footprint `Synthetic:Header_1x02`, and
pin assignments `J1.1=CONTACT_CURRENT`, `J1.2=GND`. Its source SHA-256 is
`a210495b6df2c7f43ca4d44361c6be6f022d31116dbd4efa200c76faf03f3182`.
All part names, rating values, conditions, and load allocations are synthetic.

The digest-pinned native fixture lane exports the schematic twice with KiCad
10.0.0 and 10.0.5, checks the exact connector identity and pin map, and records
normalized netlist and ERC hashes. It compares a synthetic 1.60 A per-contact
load against a 2.00 A reviewed allowable current at a 0.8 utilization ceiling,
then changes only the authored load to 1.61 A and expects `PASS`/`FAIL`.

The retained local receipts record both pinned versions with no native ERC
errors. Each produced normalized netlist SHA-256
`a61bc6c086e4abb5a3af84ddceae10f845a314c2f742cc450b1ed19c7f2419f1` and
normalized ERC SHA-256
`dbcb2273e067531c5e027ac9482ccf7ede0b4e2f7bd3ac01ad83b25510664338`.
The 1.60 A case passed at exactly 0.8 utilization; the 1.61 A case failed at
0.805. The receipts are under ignored `build/ci/` outputs and were generated
locally; no hosted GitHub result for the current dirty branch is recorded.
