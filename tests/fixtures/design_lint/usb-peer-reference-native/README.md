# Native USB peer reference regression fixtures

These two tooling-owned KiCad schematics are synthetic controls for the
`bus.usb_peer_reference_review` heuristic. Each contains a direct USB 2.0 D+/D−
pair between one connector candidate and one synthetic U-prefixed PHY. The
fault assigns connector GND and PHY AGND to separate schematic nets; the
control assigns both pins to one net. No project board or product source is
included.

| Fixture             | Reference topology                                | Expected heuristic result                  |
| ------------------- | ------------------------------------------------- | ------------------------------------------ |
| `fault.kicad_sch`   | J1.4 `GND` on `USB_GND`; U1.3 `AGND` on `PHY_GND` | One review with exact pin and net evidence |
| `control.kicad_sch` | J1.4 `GND` and U1.3 `AGND` on `BOARD_GND`         | No USB peer reference review               |

SHA-256 of the version-controlled schematic inputs:

| Fixture             | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `4aa97359832c162f5476f1002970ab039b9275d2fae4539a053bec5980bb4bc1` |
| `control.kicad_sch` | `26a52a7f4010f376b44d0fa39780c886dc4859bc9dac1ddb4206d8033ee35ec2` |

The fixtures are included in the existing source-bound USB data-path native
lane. That lane exports every schematic twice in the digest-pinned KiCad
10.0.0 and 10.0.5 images, compares normalized netlists, evaluates the USB path
map and the reference heuristic on the same typed evidence, and records
receipts under ignored `build/`. Reproduce through the configured project
profiles with:

```sh
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test \
KICAD_RUN_NATIVE_USB_DATA_PATH_FIXTURES=1 \
.venv/bin/python -B -m pytest -q tests/test_ci_hosted.py::NativeUsbDataPathFixtureTests
```

The fixture sources and expected outcomes are registered here. A local
KiCad 10.0.6 export exposed and corrected the original ground-wire coordinates;
the current sources place the connector and PHY reference pins on the expected
split nets in the fault and one shared net in the control. Repeated local
10.0.6 exports now produce stable typed netlist contracts.

Hosted package acceptance for tag `v0.5.0rc17` passed (run `37863872527`),
including `NativeUsbDataPathFixtureTests` on the digest-pinned
KiCad 10.0.0 and 10.0.5 images. Both versions passed the split-reference fault
and common-reference control, the USB-C contact fault/control, and the
two-port fault/control; repeated normalized netlists matched. The split
two-port case produced two per-port reference reviews, while the common
control produced none. The package test stage reported 2,290 passed, 26 skipped,
and 2,044 subtests passed. These cases validate repeatable schematic netlist
behavior, not the correct grounding policy for a real interface, a fitted bond,
PCB copper continuity, external wiring, or electrical suitability.

The USB-C duplicate-contact and two-pin branch regression is recorded in the
[USB-C fixture README](../usb-c-peer-reference-native/README.md).

## Read-only cohort comparison (2026-10-07)

The public `aklofas/kicad-happy` repository was checked out at commit
`a6bba1add1e18b89e3aa0824b9769ed1d9d79174` under `/private/tmp`. Its
`LICENSE` SHA-256 is
`f542344efc2d21d18c81507e8168ab256c32ece6e7acb1bc8bde71950c9b6bb5`; the
invoked `skills/kicad/scripts/analyze_schematic.py` SHA-256 is
`beea21348a0794bd3ce02ea85cb537ff8efe7e63bad70bc7773d7bbe4e484315`.
The tool was invoked directly from the checkout; this tested the script path,
not its full installation workflow. No candidate code or project data was
copied into Tooling.

Each fixture was analyzed twice with Python 3.11 using
`--no-hierarchy --only-deterministic --compact`. The repeated full report
hashes matched: fault
`fe14fb25af5211f8994f8d8a5e2d97aaec8d615ceaa1fc6ea45dc598c2971787`, control
`ca6b33157de8f0dd79b2d56b5ad8f118d5f932893343800b95618e28e59aa5b5`. Both
reports contained 10 findings with identical `findings` arrays. In both, the
candidate emitted `NT-001` single-pin prompts for J1.4 `GND` and U1.3 `AGND`,
including on the authored common-reference control. It therefore did not
distinguish the split-reference fault from its common-reference control.

This was a schematic-parser comparison, not a KiCad-native export or ERC run.
The separate pinned native USB fixture lane passed in hosted run
`37863872527`; this candidate comparison itself remains parser-only and is not
a head-to-head comparison on native-exported input. The candidate's generic
singleton warnings add no unique reference-domain finding in this trial. Their
usefulness on field designs and reviewer effort remain unmeasured. Output JSON
stayed under `/private/tmp/kicad-happy-usb-peer-trial-20261007/results/`.
