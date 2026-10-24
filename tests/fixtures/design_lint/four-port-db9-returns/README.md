# Synthetic four-port DB9 return domains

This fixture set uses four embedded, synthetic nine-pin connector symbols. Pins 7
and 9 are explicitly named `GND` in the fixture symbol metadata and receive
local return labels. The fault assigns each connector's two contacts to one of
four separately named `RETURN_PORT_n` nets; the control assigns all eight
contacts to one `COMMON_RETURN` net.

The other seven contacts are wired to matching `SIGNAL<n>` nets across all four
connectors. This keeps the regression focused on the return contacts and avoids
warnings caused by unrelated unassigned synthetic pins.

| Fixture                         | Assignment                                                      | Expected lint result                                            |
| ------------------------------- | --------------------------------------------------------------- | --------------------------------------------------------------- |
| `fault.kicad_sch`               | J1–J4 pins 7/9 use `RETURN_PORT_n`                              | `REVIEW` for repeated return functions and numbered return nets |
| `control.kicad_sch`             | All J1–J4 pins 7/9 use `COMMON_RETURN`                          | `PASS`                                                          |
| `pwm-fault.kicad_sch`           | J1–J4 pins 7/9 use `0V PWM 1` through `0V PWM 4`                | `REVIEW` for numbered return nets                               |
| `pwm-control.kicad_sch`         | All J1–J4 pins 7/9 use `0V PWM`                                 | `PASS`                                                          |
| `ret-numbered-fault.kicad_sch`  | J1/J2 use `RET1`/`RET2`; J3/J4 use `PORT3_RET`/`PORT4_RET`; CAN, I2C, and SPI return labels are split by port | `REVIEW` with exact numbered-return evidence |
| `ret-unindexed-fault.kicad_sch` | J1/J2 use `RET_USB`/`RET_SERIAL`; J3/J4 use neutral labels      | `REVIEW` for unindexed return-like labels                       |
| `ret-control.kicad_sch`         | All J1–J4 pins 7/9 use one `RET` net with numeric pin functions | No numbered or unindexed RET-label finding                      |

The PWM-named pair is a tooling-owned synthetic reproduction of the supplied
name pattern. It checks that native KiCad export preserves the spaces and
numeric suffixes used by the deterministic numbered-return heuristic. The
review only asks whether the domains are common, bonded, or intentionally
isolated; it does not require joining them.

The fixture deliberately tests detection of a suspicious pattern. It does not
assert that every DB9 return must be bonded. A real project's connector pinout
and grounding contract must state whether returns are common, bonded through a
specified path, or isolated. The fixture contains no proprietary project source or
board reconstruction. All fixture labels and component attributes are generated
synthetic values.

## RET token native fault and control coverage

The source-hash-pinned native lane also covers three synthetic return-label
cases. The numbered fault exercises `RET1`/`RET2`, `PORT3_RET`/`PORT4_RET`,
`CAN1_GND`/`CAN2_GND`, `I2C1_0V`/`I2C2_0V`, and `SPI1_RET`/`SPI2_RET`; it must
produce exact numbered-return evidence for each split family. The
unindexed fault assigns `RET_USB` and `RET_SERIAL` to separate connector return
pairs while leaving two neutral-label pairs as controls; it must produce the
unindexed return-label review without a numbered-return finding. The common
`RET` control places all eight contacts on one net and must produce neither
return-label finding. Its numeric pin functions can still leave connector-role
coverage open; this fixture does not claim the pinout itself is approved.

The focused source-bound lane is gated by
`KICAD_RUN_NATIVE_CONNECTOR_FIXTURES` and checks exact KiCad 10.0.0 and 10.0.5
exports, repeated normalized-netlist hashes, and exact pin membership. Every
finding remains a review prompt: it does not prescribe joining returns.

## Explicit grounding-contract checks

The pinned native connector lane also evaluates these same exported netlists
against two synthetic `GroundingAnalysis` requirements. One
requires J1–J4 pins 7/9 to share `COMMON_RETURN`; the other requires each connector's
pin pair to use its own `RETURN_PORT_n` domain. The split fault must fail the common
contract and pass the isolated contract. The common-net control must pass the
common contract and fail the isolated contract. This verifies that the
requirement—not the heuristic—decides which topology is acceptable. Each
receipt includes the schematic, native netlist, and requirement digests. These
are test-owned values, not a project contract file or production approval. The
matrix is enabled for KiCad 10.0.0 and 10.0.5. The hosted prerelease gate for
`v0.5.0rc123` (commit `371dc42`, GitHub Actions run `38205232934`) passed,
including these synthetic common/isolated contract cases on both executables.

The electrical service CLI/MCP parity test separately serializes synthetic
common-return and isolated-return netlists as XML and checks all four
requirement/topology combinations. It requires matching CLI and MCP checks,
including a passing split-return design when isolation is the stated
requirement. This is service-parity coverage; it does not count as a native
KiCad export or establish PCB copper continuity.

## Numeric pin functions with neutral net names

The `numeric-function-neutral-fault.kicad_sch` variant gives pins 7 and 9 the
numeric function text `7` and `9`, then assigns each connector's contacts to
neutral `NET_A` through `NET_D` labels. Native KiCad export must retain the
numeric pin-function strings, and lint must report the two exact-symbol
`connector.repeated_pin_function` prompts. It also leaves
`connector.no_connected_return` open for each connector because the numeric
functions do not identify return roles. No net-name rule contributes. The
`numeric-function-neutral-control.kicad_sch` variant uses the same numeric
function strings and one neutral `NET_COMMON` for all eight contacts. The
repeated-pin prompt clears, while the four return-role coverage prompts stay
open until a project pinout supplies the electrical role.

These controls show that the connector review prompt depends on repeated native
pin-function evidence, not ground-looking net names, and preserve the separate
coverage gap for unknown pin roles. They do not establish that the contacts must
be common. Both variants are included in the source-hash checked, repeat-export
native lane for KiCad 10.0.0 and 10.0.5.

## Supplemental local native probe (2026-10-07)

The app-bundled KiCad 10.0.6 CLI exported the four fixtures twice. Raw XML and
normalized typed-netlist hashes were identical across repeats. The local
design-lint evaluator reported both the repeated-return and numbered-return
findings on the split fault, no such findings on the common-return control,
and pin-function-based repeated-pin findings on the neutral-label fault. The
neutral-label control cleared those findings while retaining the four
unknown-return-role coverage prompts. Native ERC reported zero errors and four
`lib_symbol_issues` warnings per source; none of the diagnostics identified a
split return. This is supplemental 10.0.6 compatibility evidence. It does not
replace the digest-pinned 10.0.0/10.0.5 acceptance lane, establish a required
common return, or prove PCB continuity. Receipts are under ignored local
scratch path `/private/tmp/kicad-tooling-native-10.0.6-db9/`.

| Fixture                                      | Source SHA-256                                                     | Repeated raw native XML SHA-256                                    | Repeated normalized typed-netlist SHA-256                          |
| -------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| `pwm-fault.kicad_sch`                        | `c4a842c1685d5fbf21985aa22bd0b6436e163025f4381a8ac2544621c264e546` | `f5c9428f86fb5a429e5d4550dcf7f39c845f3a476129754700fed0124401f324` | `98c326c073ca0bf7ff38c00acddec5bbd2df1f5cb531936f3744a79bae533154` |
| `pwm-control.kicad_sch`                      | `3c00cfdee7a7bbba3439baf49f82eb6911ead068cf04ac0782f8f8fe7297cecc` | `07ce84591f187d0be1b02705b2950af4493299cafab8f352e1977959c00c4a60` | `fbb740fb9f8c29bd880d871f33047aa8993ea99720d7707daca3feff41e3c3f2` |
| `numeric-function-neutral-fault.kicad_sch`   | `8b54babacd735da898cbd477b641a57085ff03b74bf0d9aa665fc8625a36f65f` | `5fb7b8b4d7f5ade8ac9fbd14fc8080f31ccc953d8b83d0ae76c6f6476f5e6137` | `6a2e7d4b2c5cce09130a5ca037d674d4b289316281c0bc620bd7949ad866d13b` |
| `numeric-function-neutral-control.kicad_sch` | `49e3bca48e79e4b46ce4eba8298026b5c730fca56b119a3ec407dfaafbcf54cd` | `b208452e91c4d79d25c14e8fdbcc56e246393d80fedb63c1d0e2968bfef012c4` | `162b69f7992c357ce86f64744cb0a14ed5bcdf8f3b8f801903548f0f091747f0` |

## Digest-pinned native acceptance for PWM labels (2026-10-12)

The exact-version connector lane exported both PWM-named schematics twice on
KiCad 10.0.0 and 10.0.5. The repeated normalized typed-netlist hashes match for
each source and across both versions. The fault remains `REVIEW` for repeated
return functions and numbered return nets; the common `0V PWM` control is
`PASS` with the expected eight pin memberships.

| Fixture                 | Source SHA-256                                                     | Normalized typed-netlist SHA-256                                   | Result |
| ----------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ | ------ |
| `pwm-fault.kicad_sch`   | `c4a842c1685d5fbf21985aa22bd0b6436e163025f4381a8ac2544621c264e546` | `98c326c073ca0bf7ff38c00acddec5bbd2df1f5cb531936f3744a79bae533154` | REVIEW |
| `pwm-control.kicad_sch` | `3c00cfdee7a7bbba3439baf49f82eb6911ead068cf04ac0782f8f8fe7297cecc` | `fbb740fb9f8c29bd880d871f33047aa8993ea99720d7707daca3feff41e3c3f2` | PASS   |

Tagged hosted acceptance for `v0.5.0rc147` (commit `43dfe95`, GitHub Actions
run `38243428425`) passed the `net.numbered_returns` pytest scope. At that point,
the referenced native tests shared a module-scoped fixture that exported the
entire connector matrix. The focused native lane now maps this rule to the two
PWM schematics only; full connector acceptance still runs the complete matrix.
Tagged hosted acceptance for `v0.5.0rc148` (commit `5268a7f`, GitHub Actions run
`38245516011`) passed the focused native lane with the scoped pytest selector
and native-fixture flag, and passed the installed-wheel check against a separate
project checkout.

Run the focused exact-version fault/control pair with:

```sh
KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1 .venv/bin/python -I -B -m pytest -q \
  -m 'design_lint_rule(rule_id="net.numbered_returns")' \
  tests/test_numbered_return_native_fixture_lane.py
```

The native lane uses a minimal tooling-owned synthetic project manifest to
select each pinned KiCad version. It copies only `pwm-fault.kicad_sch` and
`pwm-control.kicad_sch` into the read-only fixture mount, then exports each
twice for repeatability.

## Native PCB copper fault/control fixtures

Three tooling-owned board fixtures under
`kicad_tooling/hwrepo/fixtures/pcb-return-four-port-db9-*.kicad_pcb` exercise
the same eight contacts (`J1.7`, `J1.9` through `J4.7`, `J4.9`) with every pad
assigned to `RETURN`. The control routes all contacts into one copper group.
One fault isolates both J4 contacts together; the other leaves only J4.9 open.
The exact-version PCB lane is configured to evaluate all eight pad identities
and the project-authored direct-return domain against native copper
connectivity on KiCad 10.0.0 and 10.0.5. These small board-only fixtures test
native evidence and contract evaluation; they do not model a physical DB9
footprint, current capacity, manufacturing, or a requirement that returns must
be common.
