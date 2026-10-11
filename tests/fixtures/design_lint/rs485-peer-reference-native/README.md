# RS-485 peer-reference native fixtures

These schematics and maps are synthetic tooling fixtures. They contain no
project-board source or project-owned electrical expectations.
Pin geometry follows KiCad's library-space Y axis; the native netlist check
confirms each sheet-space wire against the fixture map.

| Fixture                       | Purpose                                                                                        | SHA-256                                                            |
| ----------------------------- | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `reference-control.kicad_sch` | One local transceiver and three mapped RS-485 connectors share one exact A/B pair and `GND_A`. | `10be7495b5c4bbdd20fc7f637a0fb77d0dc946c1bb54f8b86e580ab19e8441e3` |
| `reference-control.json`      | Explicit synthetic bus, pair, transceiver, connector, and reference-pin map for the control.   | `96135ffa15a09b2529b0c383e3171d82ec33c271760413a819ca8c2e9cb956c4` |
| `reference-fault.kicad_sch`   | The same pair with J3's mapped reference pin assigned to `GND_B`; U1 stays on `GND_A`.         | `dcceed2427de1a6001cba204dd4f05dee2eb734ae2d77bfb5a58289f7d62622c` |
| `reference-fault.json`        | The same authored map except J3.3 explicitly expects `GND_B`.                                  | `8694c6ee028fdd3aca09eecb1c91e3c938ce35b62385672100d630ad7c2005bb` |

The deterministic review should recognize all four fitted endpoints on the
same exact native pair, retain the explicit reference assignments, and emit one
REVIEW candidate for the split fixture. The control should produce no candidate.
The lint does not require a common return or decide whether any split is safe.

The hosted lane checks these source hashes, exports the schematics twice with
digest-pinned KiCad 10.0.0 and 10.0.5 images, compares normalized netlists and
ERC reports, requires zero ERC errors, and verifies the exact pin-to-net map.

Run the native lane from the tooling checkout with the public template checkout
configured as `KICAD_TEMPLATE_ROOT`:

```sh
KICAD_RUN_NATIVE_RS485_PEER_REFERENCE_FIXTURES=1 python -I -B -m pytest -q \
  -m "design_lint and interface_lint and native_kicad" \
  tests/test_rs485_peer_reference_native_fixture_lane.py
```
