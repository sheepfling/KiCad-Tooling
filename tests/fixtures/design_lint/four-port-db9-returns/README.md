# Synthetic four-port DB9 return domains

This fixture pair uses four embedded, synthetic nine-pin connector symbols. Pins 7
and 9 are explicitly named `GND` in the fixture symbol metadata and receive
local return labels. The fault assigns each connector's two contacts to one of
four separately numbered `0V PWM` nets; the control assigns all eight contacts
to one `0V PWM` net.

The other seven contacts are wired to matching `SIGNAL<n>` nets across all four
connectors. This keeps the regression focused on the return contacts and avoids
warnings caused by unrelated unassigned synthetic pins.

| Fixture             | Assignment                                       | Expected lint result                                            |
| ------------------- | ------------------------------------------------ | --------------------------------------------------------------- |
| `fault.kicad_sch`   | J1–J4 pins 7/9 use `0V PWM 1` through `0V PWM 4` | `REVIEW` for repeated return functions and numbered return nets |
| `control.kicad_sch` | All J1–J4 pins 7/9 use `0V PWM`                  | `PASS`                                                          |

The fixture deliberately tests detection of a suspicious pattern. It does not
assert that every DB9 return must be bonded. A real project's connector pinout
and grounding contract must state whether returns are common, bonded through a
specified path, or isolated. The fixture contains no proprietary project source or
board reconstruction.

## Explicit grounding-contract checks

The pinned native connector lane also evaluates these same exported netlists
against two synthetic `GroundingAnalysis` requirements. One
requires J1–J4 pins 7/9 to share `0V PWM`; the other requires each connector's
pin pair to use its own `0V PWM n` domain. The split fault must fail the common
contract and pass the isolated contract. The common-net control must pass the
common contract and fail the isolated contract. This verifies that the
requirement—not the heuristic—decides which topology is acceptable. Each
receipt includes the schematic, native netlist, and requirement digests. These
are test-owned values, not a project contract file or production approval. The
matrix is enabled for KiCad 10.0.0 and 10.0.5; the next hosted native run is
still needed to confirm this extension on those executables.

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
| `fault.kicad_sch`                            | `c4a842c1685d5fbf21985aa22bd0b6436e163025f4381a8ac2544621c264e546` | `f5c9428f86fb5a429e5d4550dcf7f39c845f3a476129754700fed0124401f324` | `98c326c073ca0bf7ff38c00acddec5bbd2df1f5cb531936f3744a79bae533154` |
| `control.kicad_sch`                          | `3c00cfdee7a7bbba3439baf49f82eb6911ead068cf04ac0782f8f8fe7297cecc` | `07ce84591f187d0be1b02705b2950af4493299cafab8f352e1977959c00c4a60` | `fbb740fb9f8c29bd880d871f33047aa8993ea99720d7707daca3feff41e3c3f2` |
| `numeric-function-neutral-fault.kicad_sch`   | `8b54babacd735da898cbd477b641a57085ff03b74bf0d9aa665fc8625a36f65f` | `5fb7b8b4d7f5ade8ac9fbd14fc8080f31ccc953d8b83d0ae76c6f6476f5e6137` | `6a2e7d4b2c5cce09130a5ca037d674d4b289316281c0bc620bd7949ad866d13b` |
| `numeric-function-neutral-control.kicad_sch` | `49e3bca48e79e4b46ce4eba8298026b5c730fca56b119a3ec407dfaafbcf54cd` | `b208452e91c4d79d25c14e8fdbcc56e246393d80fedb63c1d0e2968bfef012c4` | `162b69f7992c357ce86f64744cb0a14ed5bcdf8f3b8f801903548f0f091747f0` |
