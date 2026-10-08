# Native mapped power-path regression fixtures

These tooling-owned schematics contain a synthetic power source, a fitted
two-terminal ferrite bead, a synthetic load, a return capacitor, and an ERC-only
power flag. They contain no product or proprietary source. The control connects
`U1.1` on `VIN` through `FB1` to `U2.1` on `VLOAD`. The fault leaves the load
assigned to `VLOAD` but connects `FB1.1` to `GND`, breaking the mapped
source-to-load path without leaving a pin unassigned. The ERC power flag marks
the synthetic load rail as powered across the bead; it is not a component or
physical source in the modeled design. The isolated-return control preserves the
same supported source path while returning `C1.2` to `ISO_RETURN`; that net is
separate from `GND`. The custom-capacitor fixtures use the tooling-owned
`Vendor:Power_Capacitor` alias; the opaque-capacitor fault uses
`Vendor:CAP123`, whose name does not identify it to the capacitor recognizer.
The external-source pair uses a two-pin synthetic `J1`: pin 1 is a `power_out`
source on the custom rail `AUX_INPUT`, and pin 2 returns to `GND`. The control
has J1 fitted; the fault marks only J1 DNP, exercising assembly-state filtering
without changing the exported topology. The alternate-source control puts a
DNP `J1` and fitted `J2` on separate input branches, each with its own ferrite
to the same internal `VLOAD` rail. This checks that a DNP source does not hide
the fitted alternative while avoiding two `power_out` pins on one schematic
net. `both-sources-dnp-fault` retains the same branch topology but marks both
connectors DNP, so neither branch supplies a fitted source anchor.

The directional-diode fixtures replace the bead with `D1`. For the standard
`Device:D` and `Device:D_Schottky` symbols, native pin 2 is `A` and pin 1 is
`K`. Their forward controls place `D1.2` on `VIN` and `D1.1` on `VLOAD`; the
reverse fault swaps those nets. The rule uses exact symbol identity, pin roles,
net assignment, and fitted state to bound this path candidate.

The solder-jumper fixtures replace the bead with `JP1`. The control uses the
exact `Jumper:SolderJumper_2_Bridged` identity, with native pin 1/`A` on `VIN`
and pin 2/`B` on `VLOAD`; the heuristic treats this exact fitted symbol as a
bidirectional path. The paired fault uses `Jumper:SolderJumper_2_Open` on the
same nets. It remains a REVIEW candidate because the symbol does not declare a
bridged path. Both fixtures use a minimal tooling-owned cached symbol
definition; the native acceptance test separately verifies KiCad's exported
symbol identities, pin inventories, pin functions, and net assignments.

The three-terminal fixtures use minimal synthetic cached symbol definitions
with native pin 1/`A`, 2/`C`, and 3/`B`. The `Bridged12` control puts the source
on pin 1 and load on pin 2 while keeping pin 3 on a separate net. The
`Bridged123` control puts the source on pin 1 and load on pin 3, with pin 2 on
its own net. The fault keeps that pin 1-to-pin 3 topology but uses
`Jumper:SolderJumper_3_Bridged12`; only pins 1 and 2 are bridged, so LINT-056
must continue to report REVIEW for the load path. These controls exercise the
symbol's encoded connectivity without copying library drawing data or assuming
the physical solder state.

| Fixture                                                  | Expected mapped-path result                          | Expected no-map lint result                      | Expected native ERC errors |
| -------------------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------ | -------------------------- |
| `control.kicad_sch`                                      | No path mismatch                                     | No source-path or decoupling finding             | None                       |
| `fault.kicad_sch`                                        | Review: `FB1.1` is assigned to `GND`, expected `VIN` | LINT-056 REVIEW                                  | None                       |
| `diode-control.kicad_sch`                                | No map; forward `Device:D` path control              | No LINT-056 finding                              | None                       |
| `diode-reverse-fault.kicad_sch`                          | No map; reverse `Device:D` path                      | LINT-056 REVIEW                                  | None                       |
| `schottky-diode-control.kicad_sch`                       | No map; forward `Device:D_Schottky` control          | No LINT-056 finding                              | None                       |
| `bridged-jumper-control.kicad_sch`                       | No map; fitted bridged solder jumper path control    | No LINT-056 finding                              | None                       |
| `open-jumper-fault.kicad_sch`                            | No map; open solder jumper on the same nets          | LINT-056 REVIEW                                  | None                       |
| `bridged-three-pin12-control.kicad_sch`                  | No map; `Bridged12` source/load on pins 1/2          | No LINT-056 finding                              | None                       |
| `bridged-three-pin123-control.kicad_sch`                 | No map; `Bridged123` source/load on pins 1/3         | No LINT-056 finding                              | None                       |
| `bridged-three-pin12-unbridged-terminal-fault.kicad_sch` | `Bridged12` source/load on pins 1/3                  | LINT-056 REVIEW                                  | None                       |
| `isolated-control.kicad_sch`                             | No path mismatch; `ISO_RETURN` stays separate        | No source-path or decoupling finding             | None                       |
| `custom-capacitor-control.kicad_sch`                     | No path mismatch                                     | No source-path or decoupling finding             | None                       |
| `custom-capacitor-fault.kicad_sch`                       | Review: `FB1.1` is assigned to `GND`, expected `VIN` | LINT-056 REVIEW                                  | None                       |
| `opaque-capacitor-fault.kicad_sch`                       | Review: `FB1.1` is assigned to `GND`, expected `VIN` | LINT-046 REVIEW; no LINT-056 source-path finding | None                       |
| `external-source-control.kicad_sch`                      | No path map; external-source candidate only          | Fitted `J1.1` is an anchor; no LINT-056 finding  | None                       |
| `dnp-external-source-fault.kicad_sch`                    | No path map; external-source candidate only          | DNP `J1.1` is not an anchor; LINT-056 REVIEW     | None                       |
| `alternate-source-control.kicad_sch`                     | No path map; separate source branches reach `VLOAD`  | DNP `J1` does not mask fitted `J2`; no finding   | None                       |
| `both-sources-dnp-fault.kicad_sch`                       | No path map; neither external source is fitted       | Both source anchors excluded; LINT-056 REVIEW    | None                       |

KiCad still reports fixture-only warnings for the unconfigured synthetic
symbol/footprint libraries and a one-pin local label. These warnings are
present on all fixtures; none produces an ERC error. The native comparison
therefore shows a concrete mapped-path detection that ERC misses for this
synthetic fault, plus valid separated-return and custom-library controls. The
opaque custom symbol also preserves an important boundary: LINT-056 does not
count it as capacitor evidence, while LINT-046 independently asks for capacitor
review. These fixtures do not establish a field false-positive rate.

SHA-256 of the version-controlled schematic inputs:

| Fixture                                                  | SHA-256                                                            |
| -------------------------------------------------------- | ------------------------------------------------------------------ |
| `control.kicad_sch`                                      | `2f81814b683e60208a405e1bed48ea99e72578590ca5b5d3cf5f36217091e83b` |
| `fault.kicad_sch`                                        | `8a042a236f587869ee1da38a04f1dcb8e9f67b38e71b83d32e6000dd0ee7e8f1` |
| `diode-control.kicad_sch`                                | `b750aa6d2f2a35c8e377108d9ff170dba4ac8c916c9bf45ae5df2ee63f2d3a6e` |
| `diode-reverse-fault.kicad_sch`                          | `3ccc41b19fefe5cc4d2bd4dcdeab63b1a4818b8ea08c06dfa271623097d71d01` |
| `schottky-diode-control.kicad_sch`                       | `e445d0500527b88bdbe5e8c7c6b48190c5d3b3b15199b564c4167fdf3d2cecb6` |
| `bridged-jumper-control.kicad_sch`                       | `b01f9bd7ae106c81928443606fd88e4db34c76a024cf647d264ef0738d91f57d` |
| `open-jumper-fault.kicad_sch`                            | `0af7bfb07703ced61d99d4769201f164193f34eaeef84611ddb767f234119e59` |
| `bridged-three-pin12-control.kicad_sch`                  | `c952212ba4302cb5b1c613b2b788b7d5be16dab5d792f21b118af8aa5e3db02b` |
| `bridged-three-pin123-control.kicad_sch`                 | `87bf21582a48fb399e9eb0739e78140ad0eb721d2622f81ed0db752d34307abd` |
| `bridged-three-pin12-unbridged-terminal-fault.kicad_sch` | `c246a84d7d12059c927a8ecda26c5383e826d89dbee47f7c86b152491cd1f214` |
| `isolated-control.kicad_sch`                             | `efed3c0180961a10925e61df2a9e147e85d6b7fd13f0db8c32d84a4e77b30970` |
| `custom-capacitor-control.kicad_sch`                     | `333c63e0a3b629d5d2769d53321f11fe7bb7c21bdf4c47af705994d0d357a4fc` |
| `custom-capacitor-fault.kicad_sch`                       | `3c70ab0b0a1f6d8846e424d286ba461c5645371067728c44e0f216b63ef5bca9` |
| `opaque-capacitor-fault.kicad_sch`                       | `46dfad381efae9194734a9b88cad6adf2ead95b9d254436bb060c12e2265eb35` |
| `external-source-control.kicad_sch`                      | `dd3c7433c0070a1f00a30ed8646085c4a4cd349010c9b2216486f8bff2707539` |
| `dnp-external-source-fault.kicad_sch`                    | `e1e77f3335c5e5cec3bd3805f87feb644f5ba6486555cf3aba17199ea10f9b30` |
| `alternate-source-control.kicad_sch`                     | `42d4afac7c4f409b706f09ac5673efaeb0847f0e2042eea4e4623873be77c752` |
| `both-sources-dnp-fault.kicad_sch`                       | `bbd21576756b29d75c60f1074326309f22741c12f2e699c00fe6b9a4b153020b` |

The package acceptance lane exports each fixture twice using the selected
project profile's digest-pinned KiCad 10.0.0 or 10.0.5 image, verifies the
reported KiCad version, parses the native XML and ERC JSON, compares normalized
reports, and runs the shared design-lint service. Both versions repeat the
normalized netlist and ERC results. For the external-source pair, the lane
also requires KiCad to preserve J1's exact two-pin inventory, `J1.1` electrical
type `power_out`, `J1.2` return assignment, and fitted/DNP state. Native ERC has
no error for any case. The
control, isolated-return control, and custom-capacitor control pass lint. The
base and named-custom wrong-rail faults receive LINT-056 without a path map. The
opaque custom capacitor does not produce a LINT-056 candidate; LINT-046 reports
that it could not recognize a fitted capacitor. With the authored path map,
each wrong-rail topology produces the exact mapped mismatch without a duplicate
LINT-056 finding. The isolated-return control confirms that a separate
`ISO_RETURN` is not joined to `GND` by the checker. Fixture inputs are mounted
read-only, with generated output and receipts under ignored `build/`
directories. The diode fixtures additionally require the native netlist to
preserve exact symbol identity, pin numbers, `A`/`K` functions, source/load net
assignments, and zero ERC errors on both supported versions.

For `alternate-source-control`, native export must retain separate
`J1.1`/`FB1.1` and `J2.1`/`FB2.1` source branches, both connector return pins on
`GND`, both fitted ferrites joining their respective source net to `VLOAD`,
and only `J1` in the DNP inventory. The fitted J2 branch reaches the load, so
LINT-056 stays quiet even though the other source candidate is DNP. The
normalized netlist is identical under KiCad 10.0.0 and 10.0.5
(`4e2e751a4bd270e0629bdb4b4828938f4ada5a4a9e7d2bb350529cc85defd2f2`). The
normalized ERC digests are `b84f626c41061a554c3b5795b0b104d9ed5f170c2c0f2ed741805632a89cf296`
for KiCad 10.0.0 and
`c92e516546e7bd299f9aaee2eefa049fa5a50a0414fec3a89ded15ee3995e27a` for KiCad
10.0.5. Both versions repeat identically and report no ERC errors.
The paired `both-sources-dnp-fault` export must preserve the same two source
branches but mark both connectors DNP. After normalizing away the DNP list, its
parsed netlist must equal the alternate-source control. With neither external
source fitted, LINT-056 reports REVIEW on `VLOAD`; ERC still reports no errors.
The all-DNP normalized netlist is identical for KiCad 10.0.0 and 10.0.5
(`414bee60e89197c8ee0f84d33be5934fbaa92b4f6bcb745b683e24dd86898704`). Its
normalized ERC digest matches the alternate-source control for each version:
`b84f626c41061a554c3b5795b0b104d9ed5f170c2c0f2ed741805632a89cf296` on KiCad
10.0.0 and `c92e516546e7bd299f9aaee2eefa049fa5a50a0414fec3a89ded15ee3995e27a`
on KiCad 10.0.5. Repeated reports match within each version.

## KiCad 10.0.0

- Control netlist SHA-256:
  `35081621f5b6831dd015c8e4a20ecbc052f3378d2fdf3033d2adcdc62aa04bf6`
- Fault netlist SHA-256:
  `48aed0faa464f6d45ad6df8860079af300d14d8376465ca71adcf99f54babd01`
- Isolated-return netlist SHA-256:
  `fd838e8b1fc1f36157bfecbb5b1b0c93b2b55d655e928ee645cbe4aba852f817`
- Control ERC SHA-256:
  `f8e407d4e5b87529b2e927f023d19a59ca62746d8529e1d52fd630b124c232eb`
- Fault ERC SHA-256:
  `8945db6cb5e10cc79180475f596dec5807ca1a246be947c84ad4a3e8c6fbd17b`
- Isolated-return ERC SHA-256:
  `f55a045b3aca06265f3c8d7aac333bd265c3966a649362db1bce7dfb8ee4fac7`
- External-source control netlist SHA-256:
  `faa636f4c2e22b2c62a82f724ed26b46f524d2d73b169fd7102d121b329e0025`
- DNP external-source fault netlist SHA-256:
  `cac49b15b4480d3737acc4ff268dd533b39dc2f0c2e8c9dba7d8751047fd4508`
- External-source pair ERC SHA-256:
  `9b5de6b46f13d8d51f7e21e74afe2f72a990bc273eaae36356524cdcf8671568`
- No-map and mapped lint: control and isolated-return control PASS; fault REVIEW.
- External-source population: fitted control PASS; DNP source fault REVIEW.

## KiCad 10.0.5

- Control netlist SHA-256:
  `35081621f5b6831dd015c8e4a20ecbc052f3378d2fdf3033d2adcdc62aa04bf6`
- Fault netlist SHA-256:
  `48aed0faa464f6d45ad6df8860079af300d14d8376465ca71adcf99f54babd01`
- Isolated-return netlist SHA-256:
  `fd838e8b1fc1f36157bfecbb5b1b0c93b2b55d655e928ee645cbe4aba852f817`
- Control ERC SHA-256:
  `0a1d35b6044d05d719b070204bd4465ee9c5ecc6976b9471376a299747ca24e4`
- Fault ERC SHA-256:
  `b1f928b2543cac139c3067384c152844cae9e49e684e39e666b7d4c18445ab4b`
- Isolated-return ERC SHA-256:
  `368c6cf46b5583baf358521e0e3691e2492955b3b3a9bf40f8dad920168f8915`
- External-source control netlist SHA-256:
  `faa636f4c2e22b2c62a82f724ed26b46f524d2d73b169fd7102d121b329e0025`
- DNP external-source fault netlist SHA-256:
  `cac49b15b4480d3737acc4ff268dd533b39dc2f0c2e8c9dba7d8751047fd4508`
- External-source pair ERC SHA-256:
  `3793202b601653518aec936f4b0e91909eab642a54bd965141a3498f1dbd2dfe`
- No-map and mapped lint: control and isolated-return control PASS; fault REVIEW.
- External-source population: fitted control PASS; DNP source fault REVIEW.

On both versions, all three fixtures have zero ERC errors and the same warning
types (`footprint_link_issues`, `isolated_pin_label`, and
`lib_symbol_issues`). Only the wrong-rail fault receives the no-map heuristic;
with the authored map, its mapped mismatch is reported without a duplicate
heuristic. The isolated-return control is topology evidence, not a claim that
every separated return should remain isolated.

## Directional diode slice

The native lane checked all three schematics with KiCad 10.0.0 and 10.0.5.
Each normalized netlist and ERC report repeated identically on the second
export. All had zero ERC errors and the fixture warning types listed above.

| Fixture                  | Normalized netlist SHA-256 (both versions)                         | Normalized ERC SHA-256 (10.0.0)                                    | Normalized ERC SHA-256 (10.0.5)                                    | LINT-056 |
| ------------------------ | ------------------------------------------------------------------ | ------------------------------------------------------------------ | ------------------------------------------------------------------ | -------- |
| `diode-control`          | `82bcd072097ebd40e16eb17c167aeac561fedbd95cad2af3881efeaa82f5f052` | `c25138359c7ec6f91f8ed8725ff25532fd287a9f1dff600979bde7bee4611a56` | `7a21a998be12e0928aaed4f15723fe6eca4208b3d550ed5a7097edefee745fc9` | PASS     |
| `diode-reverse-fault`    | `84cfded304ecf6669060fc7679d28ff902fae11b9aa344b05c097bd0721f4f3d` | `c25138359c7ec6f91f8ed8725ff25532fd287a9f1dff600979bde7bee4611a56` | `7a21a998be12e0928aaed4f15723fe6eca4208b3d550ed5a7097edefee745fc9` | REVIEW   |
| `schottky-diode-control` | `6fe69d855124d052660b94aec99ae0baa07e2f45fa8509286b8233421fa650fc` | `4599bc195b4cbaff385014264ee3c96235fc8ff4f4388739affe498aa9825249` | `ff3242595a6b7d94e8cdebcad7250d1c06168046f40911afdc46e81e6fc11a14` | PASS     |

The results confirm the bounded schematic graph and the native symbol mapping.
They do not establish diode electrical behavior, suitability, or board copper
continuity.

## Bridged solder-jumper slice

The native lane checks the fitted bridged control and open-symbol fault with
KiCad 10.0.0 and 10.0.5. It requires each normalized netlist and ERC report to
repeat, preserves the exact KiCad symbol ID and native pin mapping, and requires
zero ERC errors. The bridged control should have no LINT-056 finding; the open
symbol should remain `REVIEW`. These checks validate the bounded schematic
interpretation only. They do not establish the physical solder state, footprint
population, copper continuity, or current capacity.

| Fixture                   | Normalized netlist SHA-256 (both versions)                         | Normalized ERC SHA-256 (10.0.0)                                    | Normalized ERC SHA-256 (10.0.5)                                    | LINT-056 |
| ------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ | ------------------------------------------------------------------ | -------- |
| `bridged-jumper-control`  | `c56fe3316a4d1c20988bbe26031bbcbaec594152770cacedd57fcaa64a9fe068` | `9a48b30533a7c31594a53d2ed93867ea3ce0c14e8c9a356d7fec884c07e62827` | `1f7359f49abf9900209365ff19fad13fdfe17698c44698e042afe9b701fe4c1c` | PASS     |
| `open-jumper-fault`       | `fcd13153354d628759a81a763877c2d7e71391edca4e50a2e196d86407bb7ab8` | `2e8d6bbdc4d189df611580b973ac542f9d8b12db94a53dfbeb5f7ee49e65be7e` | `34633dc5b97b99bc594ef27b14ae0f9c6d2672703b41b92e29717a75c851dc68` | REVIEW   |

Both normalized reports repeat identically on the second export for each exact
KiCad version. The open jumper produces a LINT-056 review while the explicitly
bridged control remains quiet; native ERC reports zero errors for both.
The CLI/MCP parity regression also checks these two cases using synthetic
source-hash-bound netlists; both surfaces return the same PASS and REVIEW
reports.

## Three-terminal bridged solder-jumper slice

The native lane verifies the exact `Jumper:SolderJumper_3_Bridged12` and
`Jumper:SolderJumper_3_Bridged123` symbol IDs, complete pin inventory, native
`A`/`C`/`B` functions, and each assigned terminal net. It checks the encoded
bridge edges against two quiet controls and a REVIEW fault. Each fixture was
exported twice on KiCad 10.0.0 and 10.0.5; normalized netlists and ERC reports
repeat, and every export has zero ERC errors. The normalized netlist digest is
the same for both KiCad versions; ERC digests are version-specific.

| Fixture                                        | Normalized netlist SHA-256 (both versions)                         | Normalized ERC SHA-256 (10.0.0)                                    | Normalized ERC SHA-256 (10.0.5)                                    | LINT-056 |
| ---------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ | ------------------------------------------------------------------ | -------- |
| `bridged-three-pin12-control`                  | `fd81fc3c7fb75d4c9eab70af9547e65ade2266a03dd8dd20cc41d75e2bf65549` | `e2b5b3e212f1b692948ed32cd7f50bfc29211e8f58caf4d3e0650e8349b8b404` | `e603e0d8c196c7a4d4314d7a9a1fa52ce61dfe1e7855132a5b73276a7cc098e8` | PASS     |
| `bridged-three-pin123-control`                 | `d5175bafd2932aa595cfa5542f6f97928ee9f0758a77b92dbf58389516c5a8cb` | `54aa58250fcf0e1851fd4f7b9b8235f79496c86f260cf37cd8a8fcf09c37a0c0` | `ddc2ce5b3fe261178b79cf92fd2e3d772669286e12b0e061fef6369a700cb2bf` | PASS     |
| `bridged-three-pin12-unbridged-terminal-fault` | `4cfee2dc30010a4822869ac5e5a561c0cb854a7544a6b812a24a967907137626` | `59144de9c2c753ad35a08373d1cda675f32dac0f53eaddc7b8a450f7987c5e44` | `479e3ceedf60c4ebaaa73e9be76a7b043f2571ca9310bedd6483aff35d3bacb8` | REVIEW   |

These are schematic-topology review controls, not claims about actual solder
state, PCB continuity, or current capacity. The incremental gain is fewer
unsupported-topology prompts on the two exact supported configurations; the
pin 1-to-pin 3 case under `Bridged12` remains visible for review.

## Read-only kicad-happy comparison

On 2026-09-30, the pinned kicad-happy commit
`a6bba1add1e18b89e3aa0824b9769ed1d9d79174` (declared MIT) ran its deterministic
schematic analyzer twice on these same two files with `--no-hierarchy
--only-deterministic`. Filtered findings and full reports repeated exactly.
The control had no `PP-001`; the wrong-rail fault had `PP-001` on `U2.1`. The
candidate's message says the load is “likely AC-coupled to ground only”; this
wording and the candidate's `error` severity were not adopted. The local rule
reports only that it found no path in a bounded supported component set and
defaults to `REVIEW`.

- Control: no `PP-001`; report SHA-256
  `b65723f226bc985e3b46c5c760712f2f262fa414cc99ce00bb34e67efdc9c168`.
- Fault: `PP-001` on `U2.1`; report SHA-256
  `1d8b308e0baa0b252b1cae2f72835ce9b368db98ece7a015b36a0966cfd8d5a7`.

The comparison was read-only. The cohort checkout and reports remained under
`/private/tmp`; no cohort code or additional project data was copied into this
repository.

The inspected analyzer SHA-256 was
`beea21348a0794bd3ce02ea85cb537ff8efe7e63bad70bc7773d7bbe4e484315`; its
`signal_detectors.py` SHA-256 was
`b4780c08ef9e3b97e852b759593bb8ffb34c89b9264054d3cf2865309e22a429`.
Reproduce the direct, read-only run with the disposable checkout and report
directory shown here:

```sh
HAPPY=/private/tmp/kicad-happy-lint-trial
OUT=/private/tmp/kicad-happy-mapped-power-path-20260930
mkdir -p "$OUT"
for case in control fault; do
  for run in first repeat; do
    .venv/bin/python -B -I \
      "$HAPPY/skills/kicad/scripts/analyze_schematic.py" \
      "tests/fixtures/design_lint/power-path-native/$case.kicad_sch" \
      --no-hierarchy --only-deterministic --output "$OUT/$case.$run.json"
  done
done
```

Reproduce against the public tooling acceptance checkout:

```sh
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test \
KICAD_RUN_NATIVE_POWER_PATH_FIXTURES=1 \
.venv/bin/python -B -m unittest tests.test_power_path_fixture_lane.NativePowerPathFixtureTests
```

The mapped check compares only project-authored identities and net
assignments. It does not prove the ferrite conducts or is suitable, detect
unlisted parallel paths, assess ratings, establish PCB copper continuity, or
prove a physical power path. Separate synthetic unit cases cover open pins;
those can also trigger generic unconnected-pin checks and are not counted as
the incremental ERC result above.
