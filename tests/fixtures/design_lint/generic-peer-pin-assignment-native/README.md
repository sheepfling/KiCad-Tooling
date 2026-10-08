# Synthetic generic peer-pin assignment fixtures

These tooling-owned schematics exercise the exact-symbol peer assignment rules
when matching connector symbols have an absent or generic pin function. The
three-instance fixtures use the same embedded `Lint:PeerPowerPort` symbol; pin 2 is
explicitly named `GND`. The added placeholder pair labels pin 1 `Pin_1`, as
KiCad commonly does for a pin whose role is unspecified. That label is treated
as unknown role metadata, like an absent function. The two-instance pair checks
the minimum peer-group size for an open contact.

| Fixture                                          | Pin 1 assignment                                                                                 | Expected lint result                                                                                                             |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------- |
| `fault.kicad_sch`                                | J1.1 and J2.1 use `+5V`; J3.1 is open                                                            | `REVIEW`, localized to J3.1 under `connector.peer_pin_assignment_outlier`                                                        |
| `minority-fault.kicad_sch`                       | J1.1 and J2.1 use `+5V`; J3.1 uses `+3V3`                                                        | `REVIEW`, localized to J3.1 under `connector.peer_pin_assignment_outlier`                                                        |
| `divergence-fault.kicad_sch`                     | J1.1 uses `+5V`, J2.1 uses `+3V3`, and J3.1 uses `+12V`                                          | `REVIEW` under `connector.peer_pin_assignment_divergence`; no unique most-common assignment                                      |
| `control.kicad_sch`                              | J1.1, J2.1, and J3.1 use `+5V`                                                                   | `PASS`                                                                                                                           |
| `generic-placeholder-divergence-fault.kicad_sch` | J1.1 uses `+5V`, J2.1 uses `+3V3`, and J3.1 uses `+12V`; pin function is `Pin_1`                 | `REVIEW` under `connector.peer_pin_assignment_divergence`                                                                        |
| `peer-scope-split-return-fault.kicad_sch`        | The same divergent `Pin_1` assignments; pin 2 returns use `RETURN_A`, `RETURN_B`, and `RETURN_C` | Separate reviewed groups keep the cross-port return prompt and scope away generic signal divergence; a shared group reports both |
| `generic-placeholder-control.kicad_sch`          | J1.1, J2.1, and J3.1 use `+5V`; pin function is `Pin_1`                                          | `PASS`                                                                                                                           |
| `two-peer-open-fault.kicad_sch`                  | J1.1 uses `+5V`; J2.1 is open; both pin 2 contacts use `GND`                                     | `REVIEW`, localized to J2.1 under `connector.peer_pin_assignment_outlier`                                                        |
| `two-peer-no-connect-fault.kicad_sch`            | J1.1 uses `+5V`; J2.1 has an explicit no-connect marker; both pin 2 contacts use `GND`           | `REVIEW`, localized to J2.1; the marker does not establish peer-interface intent                                                 |
| `two-peer-common-control.kicad_sch`              | J1.1 and J2.1 use `+5V`; both pin 2 contacts use `GND`                                           | `PASS`                                                                                                                           |
| `single-offboard-port-control.kicad_sch`         | J1.1 is an external 5 V input; J1.2 is its off-board return                                      | `PASS` with a complete synthetic interface map and inventory review                                                              |

The three-connector cases assign every pin 2 to `GND`; both two-connector
cases assign pin 2 to `GND` on each instance. The open-contact fault tests
whether the exported symbol pin-number inventory preserves enough evidence to
find a missing contact when its function name is empty. The minority fault
checks a different assignment when no pin-function role is available. The
no-majority case checks that three distinct assigned nets produce the
lower-confidence divergence rule without an arbitrary outlier. The placeholder
pair proves that a native `Pin_1` label does not promote the finding to the
meaningful repeated-function rule. Neither case says that matching connector
contacts must be connected; project pinout requirements must establish that
intent. The fixtures contain no product source, board reconstruction, or
proprietary data.

The peer-scope fault combines divergent generic signal assignments with split
returns. Its native lane applies complete, source-matched interface reviews
with either distinct per-port groups or one shared group. Distinct groups
suppress only the generic signal comparison; the return mismatch remains a
`REVIEW` across groups. A shared group adds
`connector.peer_pin_assignment_divergence`. The existing common-net control
must pass with the shared group. These cases verify review scope behavior and
do not declare that the returns must be common.

The two-instance fault proves that a connected same-number peer is enough to
prompt review of an open contact; it does not require a three-connector
majority. Its common-net control keeps the prompt quiet. The result remains a
review question because matching symbol pins can have intentionally different
functions or connectivity.

The single-port control declares both one-pin nets as intentional connector
endpoints through a synthetic interface catalog: pin 1 receives external 5 V,
and pin 2 is the external return. With no project map, local connector coverage
is `UNDECLARED` and lint is `REVIEW`; with the complete map, coverage is
`COMPLETE` and lint passes without findings. The pinned cohort singleton-net
analyzer still emits `NT-001` INFO prompts for both contacts because it has no
project interface or off-board source map. This is a valid off-board endpoint
control, not evidence that singleton nets should be joined or that the external
supply is physically present.

## Source hashes

| Source                                           | SHA-256                                                            |
| ------------------------------------------------ | ------------------------------------------------------------------ |
| `fault.kicad_sch`                                | `e9945c83c351ece43064a6c09c770fd8f3ab5fadd550ac58ee5d001f5d8842e2` |
| `minority-fault.kicad_sch`                       | `a071543178ad7668d20a3653fea5196cf556c3b96338b81dbeac97a6360ede2c` |
| `divergence-fault.kicad_sch`                     | `c278b2ff86c869a6dba7c19ee08f064a863d282d251be44fd47c1e8a71254e57` |
| `control.kicad_sch`                              | `94a9897ea50645a4232abf005477e620a4cd9b12330dfc2d6f32734e8157b8be` |
| `generic-placeholder-divergence-fault.kicad_sch` | `f6f4c9b419ab590366ca329b1ac0749706b29536017f2f24145de7ef6bdfaf30` |
| `peer-scope-split-return-fault.kicad_sch`        | `a597bbdee4794b3de8ff08bce5691363a7a123bde303462d64cb692a6a97968e` |
| `generic-placeholder-control.kicad_sch`          | `d63a7f7cd79fd0855de599041dacb8219313ffbb2667f37d1e61e88fbec880c0` |
| `two-peer-open-fault.kicad_sch`                  | `3de502ac74b394afb21cdaef8130026f11f7aa6050018a571dc65b10ae864350` |
| `two-peer-no-connect-fault.kicad_sch`            | `8801b0ff24e9f012e6f2df10247cdc04668db40d3233eb5d2111d279cfdf7256` |
| `two-peer-common-control.kicad_sch`              | `ae23ddb802c9a0f5cf30e89699a2cf6f48b3d15b6e18967387e756dcdf6fa3df` |
| `single-offboard-port-control.kicad_sch`         | `ceaa7038e372ec74a00f7e7c2cb5311377df01624760ab555adb413c4e02d8e9` |

## Exact native export lane

`tests.test_ci_hosted.NativeConnectorReturnFixtureTests` exports the
schematics twice with digest-pinned KiCad 10.0.0 and 10.0.5. The lane checks
fixture hashes, normalized netlist repeatability, exact J1.1/J2.1/J3.1
assignments, open-contact and minority-net outliers, no-majority divergence,
the generic `Pin_1` divergence and control, the split-return peer-scope fault
with separate and shared reviewed groups, its shared-group common-net control,
and the two-instance open-contact boundary, an explicit marked-open peer fault,
and its common-net control, plus the valid off-board singleton endpoint
control. The off-board case checks the undeclared inventory REVIEW and the
complete-map PASS with no lint findings on both KiCad versions. The marked-open
pin remains a REVIEW candidate because the marker does not establish whether
the peer-contact difference is intentional. The lint cannot prove that the
peer pins must share a net.
Receipts stay under ignored `build/ci/` directories.

Run it from the tooling checkout with a separate public KiCad template
checkout configured:

```sh
KICAD_TEMPLATE_ROOT=/absolute/path/to/KiCad-Test \
KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1 \
  .venv/bin/python -I -m pytest -q tests/test_ci_hosted.py::NativeConnectorReturnFixtureTests
```
