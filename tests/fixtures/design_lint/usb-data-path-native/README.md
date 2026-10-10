# Native USB data path regression fixtures

These tooling-owned schematics are synthetic controls for the project-mapped
USB connector-to-PHY rule. They contain no proprietary or product source. They model
only one USB 2.0 data pair and the components declared in the map; connector
power, shielding, protection, signal integrity, and PCB routing are outside
this regression.

| Fixture                                                | Expected path                                                      | Rule result                                       |
| ------------------------------------------------------ | ------------------------------------------------------------------ | ------------------------------------------------- |
| `integrated-phy-direct.kicad_sch`                      | Connector D+/D− directly to a synthetic integrated STM32 PHY       | No USB data-path finding                          |
| `external-phy-series-control.kicad_sch`                | 27 Ω on each TUSB2036 data line; connector and PHY share GND       | No USB data-path or reference review              |
| `external-phy-series-reference-bond-control.kicad_sch` | 27 Ω data paths; USB_GND and BOARD_GND use a mapped fitted 0R bond | No USB data-path or reference review              |
| `external-phy-series-reference-fault.kicad_sch`        | Same series paths; connector and PHY returns use separate nets     | One reference review with exact resistor evidence |
| `external-phy-direct-bypass-fault.kicad_sch`           | Connector data lines bypass both resistors before the external PHY | One finding for D+ and one for D−                 |

SHA-256 hashes of the version-controlled schematic inputs:

| Fixture                                                | SHA-256                                                            |
| ------------------------------------------------------ | ------------------------------------------------------------------ |
| `integrated-phy-direct.kicad_sch`                      | `e93371b78de2ba8c473ccde0579e551d0da0b44b5d9ed417473ab1dd63781d27` |
| `external-phy-series-control.kicad_sch`                | `87e43a85255a91490cec5e1f8b101a9c408a45c855b9700a099cdc49ce27f01f` |
| `external-phy-series-reference-bond-control.kicad_sch` | `5a178e443dcac77c4342d9b3e86a254556f71bbdc1b707bcb2bb23a1459bd9f3` |
| `external-phy-series-reference-fault.kicad_sch`        | `25e0cea0682898c5300b27024436717fc9b9b50743ef256b922e98909e0520ab` |
| `external-phy-direct-bypass-fault.kicad_sch`           | `0b6173339fc0e2f937247c6eb5aaea1ac51b0b7a26a31058c25119333cb8f0c2` |

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

This is source-to-netlist regression evidence only. The lane does not run ERC,
DRC, PCB copper continuity, component placement, signal-integrity analysis,
or hardware qualification. The controls demonstrate the configured rule's
behavior; they do not determine which topology a real product requires.
