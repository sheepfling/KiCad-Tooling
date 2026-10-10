# Synthetic repeated-connector return domains

This pair tests a case where two matching connectors have the same signal pin
functions, but their return contacts are assigned to separate net domains.
Each connector has two `GND` contacts and four common `DATA` contacts.

| Fixture             | Return assignment                          | Expected Tooling result                                                   |
| ------------------- | ------------------------------------------ | ------------------------------------------------------------------------- |
| `fault.kicad_sch`   | J1.1/J1.2 use `GND1`; J2.1/J2.2 use `GND2` | `REVIEW` for repeated connector return functions and numbered return nets |
| `control.kicad_sch` | All four return contacts use `GND`         | `PASS`                                                                    |

The split domains are a synthetic regression prompt. They do not establish
that all USB, serial, or other connector returns must be bonded. A project must
author the intended interface and grounding requirements; intentional
isolation can be reviewed and configured. These files contain no proprietary project
source or reconstructed board details.

Both schematics were exported and checked with KiCad CLI 10.0.6. Native ERC
reported the same two `lib_symbol_issues` warnings for the deliberately
embedded synthetic `Lint:Port6` symbol library in both cases. The netlists
confirm the intended difference: the fault has two separate return nets while
the control has one shared return net. The native comparison does not claim
that ERC can infer which relationship is correct.

The cohort comparison used the MIT-licensed `aklofas/kicad-happy` analyzer at
commit `a6bba1add1e18b89e3aa0824b9769ed1d9d79174`, invoked directly without
installation. Its `connector_ground_audit` / `CG-AUD` rule emitted no finding
for either fixture. Its `ground_domains` summary classified `GND1` and `GND2`
as signal domains and reported `multiple_domains: false` on the fault; the
shared `GND` was also classified as signal on the control. The audit's
documented signal-to-ground allocation ratio is per connector and its trigger
is `>4`; where this fixture's two return contacts are counted, its 4:2
allocation is 2:1. That rule does not compare matching return-pin groups
across connectors.

The existing Tooling `design_lint` evaluated the same KiCad-generated XML
netlists: the fault returned `REVIEW` with `connector.repeated_pin_function`
and `net.numbered_returns`, while the control returned `PASS`. Related
synthetic contract cases are in
`tests/test_design_lint_connector_roles.py`; the native fixture lane is in
`tests/test_connector_return_fixture_lane.py`. Hosted package acceptance now
repeats the native exports with the public template's exact
KiCad 10.0.0 and 10.0.5 images. The optional direct local export test remains
available from `tests/test_native_connector_return_lint.py` when
`KICAD_CONNECTOR_LINT_TEST_CLI` points to KiCad 10.0.6.
Repeatability is checked on the canonical typed netlist, since KiCad 10.0.0
adds a second-resolution export timestamp to raw XML; each raw XML digest is
still retained separately.
This pair is a reproducible cohort-analysis fixture, not a production
connector requirement.
