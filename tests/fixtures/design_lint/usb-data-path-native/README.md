# Native USB data path regression fixtures

These tooling-owned schematics are synthetic controls for the project-mapped
USB connector-to-PHY rule. They contain no proprietary or product source. They model
only one USB 2.0 data pair and the components declared in the map. The
synthetic inline-protection component exercises exact pin-to-net contracts;
it does not represent a real product or validate device behavior. Connector
power, shielding, signal integrity, and PCB routing remain outside this
regression.

| Fixture                                                | Expected path                                                                                | Rule result                                                               |
| ------------------------------------------------------ | -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| `integrated-phy-direct.kicad_sch`                      | Connector D+/D− directly to a synthetic integrated STM32 PHY                                 | No USB data-path finding                                                  |
| `external-phy-series-control.kicad_sch`                | 27 Ω on each TUSB2036 data line; connector and PHY share GND                                 | No USB data-path or reference review                                      |
| `external-phy-series-reference-bond-control.kicad_sch` | 27 Ω data paths; USB_GND and BOARD_GND use a mapped fitted 0R bond                           | No USB data-path or reference review                                      |
| `external-phy-series-reference-fault.kicad_sch`        | Same series paths; connector and PHY returns use separate nets                               | One reference review with exact resistor evidence                         |
| `external-phy-direct-bypass-fault.kicad_sch`           | Connector data lines bypass both resistors before the external PHY                           | One finding for D+ and one for D−                                         |
| `inline-protection-control.kicad_sch`                  | Exact six-pin pass-through component with mapped data and reference pins                     | No USB data-path finding                                                  |
| `inline-protection-ground-fault.kicad_sch`             | Same path with the inline component's required GND pin explicitly unconnected                | Findings for D+ and D− with U2.5 evidence                                 |
| `inline-protection-split-reference.kicad_sch`          | Exact mapped inline path; connector return is USB_GND and PHY/protection return is BOARD_GND | One USB reference review unless separate references are explicitly mapped |

SHA-256 hashes of the version-controlled schematic inputs:

| Fixture                                                | SHA-256                                                            |
| ------------------------------------------------------ | ------------------------------------------------------------------ |
| `integrated-phy-direct.kicad_sch`                      | `e93371b78de2ba8c473ccde0579e551d0da0b44b5d9ed417473ab1dd63781d27` |
| `external-phy-series-control.kicad_sch`                | `87e43a85255a91490cec5e1f8b101a9c408a45c855b9700a099cdc49ce27f01f` |
| `external-phy-series-reference-bond-control.kicad_sch` | `5a178e443dcac77c4342d9b3e86a254556f71bbdc1b707bcb2bb23a1459bd9f3` |
| `external-phy-series-reference-fault.kicad_sch`        | `25e0cea0682898c5300b27024436717fc9b9b50743ef256b922e98909e0520ab` |
| `external-phy-direct-bypass-fault.kicad_sch`           | `0b6173339fc0e2f937247c6eb5aaea1ac51b0b7a26a31058c25119333cb8f0c2` |
| `inline-protection-control.kicad_sch`                  | `cf85e10487c4a92779de40f44fa56ddb518c4897117088652f6ce8f7387be8fd` |
| `inline-protection-ground-fault.kicad_sch`             | `947136aa5a997895493d05e5dd4781ff9ea07f2ffa48e60a20b915d5ddff52dc` |
| `inline-protection-split-reference.kicad_sch`          | `1ca140bcd75dbc3330a3839c53cb6086b22f9f56f4f8d03049f7b84c67558444` |

The native regression runs twice with each of these digest-pinned images:

| KiCad  | Image                                                                                                |
| ------ | ---------------------------------------------------------------------------------------------------- |
| 10.0.0 | `ghcr.io/kicad/kicad:10.0.0@sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3` |
| 10.0.5 | `ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c` |

To reproduce against the public tooling acceptance checkout used for the
reviewed toolchain profiles:

```sh
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test \
KICAD_RUN_NATIVE_USB_DATA_PATH_FIXTURES=1 \
.venv/bin/python -I -m pytest -q tests/test_usb_data_path_native_fixture_lane.py -m 'design_lint and interface_lint and native_kicad'
```

The lane checks KiCad's reported version, exports each read-only fixture twice,
parses the native XML into the same netlist contract used by the rule, checks
the expected mapped topology, and compares normalized parsed output across
repeated exports. It writes command receipts and generated netlists under the
ignored `build/` directory. CI enables the lane in the digest-pinned package
acceptance step.

The same lane now also exports the split-reference fault and common-reference control documented in
the [USB peer-reference fixture record](../usb-peer-reference-native/README.md). Those two cases
exercise `bus.usb_peer_reference_review` on the identical native netlist evidence used by the mapped
data-path check. The external-series pair additionally verifies that one fitted `Device:R` on each
data line does not hide a split-reference review, and that the finding retains both resistor
pin-to-net assignments.

It also exports a separate-reference control whose project map names the exact
fitted R3 symbol, footprint, 0R value, and pin-to-net assignments. This checks
that `reference_policy: "bonded"` resolves the review prompt only when the
mapped component and schematic net assignments match. It is schematic
netlist evidence; it does not prove that the component conducts or that PCB
copper completes the return path.

The inline-protection control and ground-pin fault exercise the exact
project-authored multi-pin component map. The map checks full native pin
inventory, every pin's net or explicit no-connect state, and both connector-to-
PHY data paths. The fault confirms that an open required component ground pin
is reported with its exact pin evidence. The synthetic symbol does not model a
real protection device or establish datasheet pinout correctness.

The split-reference inline fixture exercises the separate peer-reference
heuristic. Its exact topology map identifies the complete protection component
and pin assignments while leaving the reference decision unauthored, so the
tool reports a review. A second native-lane case applies an explicit
separate-reference policy to the same source and confirms that the configured
decision suppresses that prompt.

This is source-to-netlist regression evidence only. The lane does not run ERC,
DRC, PCB copper continuity, component placement, signal-integrity analysis,
or hardware qualification. The controls demonstrate the configured rule's
behavior; they do not determine which topology a real product requires.
