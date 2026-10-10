# Synthetic CAN peer assignment fixtures

These tooling-owned schematics contain three synthetic CAN transceivers and
direct termination resistors. The control assigns all CANH pins to `NET_A` and
all CANL pins to `NET_B`. The fault keeps U1 and U2 on that pair, while U3
shares `NET_A` and assigns CANL to `NET_C`. The net names are neutral so the
fixture tests cross-peer assignment asymmetry without asserting that the peers
must share a bus.

| Fixture                  | Expected design-lint result                                                          |
| ------------------------ | ------------------------------------------------------------------------------------ |
| `peer-control.kicad_sch` | PASS; no peer divergence finding                                                     |
| `peer-fault.kicad_sch`   | REVIEW; one `bus.can_peer_assignment_divergence` finding with exact peer assignments |

SHA-256 of the version-controlled schematic inputs:

| Fixture                  | SHA-256                                                            |
| ------------------------ | ------------------------------------------------------------------ |
| `peer-control.kicad_sch` | `9adfa39101f0caaa60bde8ca1770659382d6bfc1677e1b2272847bb76d943135` |
| `peer-fault.kicad_sch`   | `60e310e7faae4cee9b8982b1d2abc5be3e8d6c48d815dd9808ae82e7578ecbc6` |

The package acceptance lane exports each source twice using both reviewed digest-pinned images:
KiCad 10.0.0
(`ghcr.io/kicad/kicad:10.0.0@sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3`)
and KiCad 10.0.5
(`ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`).
The normalized native netlist digests are identical across both versions and repeated runs:

| Fixture                  | Normalized netlist SHA-256                                         |
| ------------------------ | ------------------------------------------------------------------ |
| `peer-control.kicad_sch` | `add4ca19eeac84b2f89733cc3a27aa2ff7a1a8945ed4699e3f35ffb882cdeca4` |
| `peer-fault.kicad_sch`   | `337f52c298085c36f4e738f1ba486dceeea15cae32dea6f4094c362f159c8e26` |

Both fixtures have zero native ERC errors. The isolated container library setup
reports repeatable `footprint_link_issues` and `lib_symbol_issues` warnings
because the synthetic and Device libraries are not installed in its temporary
user configuration. The lane records these warning classes and rejects any
ERC error. The fault still produces only the expected lint finding, with exact
CANH/CANL pin functions and net assignments. Native pin/net exports establish
schematic assignments only; they do not establish bus intent, PCB copper,
off-board wiring, or physical connectivity. All source is synthetic and
contains no proprietary or customer project data. Generated exports and receipts stay
under ignored `build/` directories.

Run the optional exact-version native lane from an installed tooling checkout
with the separate reference-template checkout available:

```sh
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test \
KICAD_RUN_NATIVE_CAN_PEER_FIXTURES=1 \
python3.11 -I -B -m pytest -q \
  -m "interface_lint and native_kicad" \
  tests/test_can_native_fixture_lanes.py -k can_peer_assignment
```
