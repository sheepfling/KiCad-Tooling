# Synthetic control-input native fixtures

These tooling-owned schematics check control-input recognition and visible
bias-path behavior against native KiCad pin-function, electrical-type, and
net-assignment evidence.

## Reset-alias fixture

Both pins are unassigned native `input` pins. `POR_B` is the positive case for
the `POR` reset token; `PORN` is a deliberate substring nonmatch.

| Pin    | Function | Electrical type | Native assignment | Expected unconnected-input result |
| ------ | -------- | --------------- | ----------------- | --------------------------------- |
| `U1.1` | `POR_B`  | `input`         | none              | reset review candidate            |
| `U1.2` | `PORN`   | `input`         | none              | no candidate                      |

## Series-bias fixture

`U1.1 RESET_N` is a fitted native `input` on the `RESET_N` net. Fitted 10 kΩ
resistors R1 and R2 connect that net to `+3V3` through the intermediate
`RESET_BIAS_MID` net. The intermediate net contains only `R1.2` and `R2.1`.
U2 is DNP. The connected-control heuristic recognizes the unbranched chain and
emits no bias candidate. This validates the supported topology, not the
resistor value's suitability or whether a local bias is required.

## Source and native evidence

| Evidence                                             | Value                                                              |
| ---------------------------------------------------- | ------------------------------------------------------------------ |
| `por-b.kicad_sch` source SHA-256                     | `63b1d9b49632c9e54e6576253223be14e4ce9b8bf4cf5485ddc8e4ca2dcf8743` |
| `series-bias-control.kicad_sch` source SHA-256       | `217665dbcaa4ed740813c9105b89a45a9b70116142ed7593a1bc3ecde6662832` |
| Source-manifest SHA-256                              | `8891d8820f24c9d90e3a5cfc58a3bc2f7c9ad6e5775960ac2384754ca750056f` |
| KiCad image                                          | `ghcr.io/kicad/kicad:10.0.5`                                       |
| Image digest                                         | `fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c` |
| POR normalized typed-netlist SHA-256, both exports   | `43392db78020b36af78ec52e2b437c795ec091047486f1b834625e3456718c89` |
| POR first and repeat raw netlist SHA-256             | `df8095d2efed9006b28850d4fff3d8785737d21fd7887c1044ff0e22fc07740e` |
| Chain normalized typed-netlist SHA-256, both exports | `7460ef30a887211f4bc8f8ef86ecc68e8220d7edfd131a1a86e7aa356f40a99b` |
| Chain first and repeat raw netlist SHA-256           | `890e314d65f0b2d50f2463df3afc6852561aec654436ef056bb3841fddf0f213` |

The native lane confirms exact `POR_B`/`PORN` pin functions and `input` types,
leaves both pins unassigned, and emits only `U1.1` as a reset candidate. It also
confirms the chain fixture's exact pin assignments, DNP state, isolated
intermediate net, no connected-bias candidate, and repeated normalized export.
The test repeats four public KiCad demos and checks their pinned candidate
inventories and normalized netlists. The lane exports netlists; it does not run
ERC or DRC and does not establish that a reset pin requires bias.

Run from the tooling checkout with a public reference-template checkout
configured:

```sh
KICAD_TEMPLATE_ROOT=/absolute/path/to/KiCad-Test \
KICAD_RUN_NATIVE_CONTROL_INPUT_FIXTURES=1 \
  .venv/bin/python -I -m pytest -q tests/test_ci_hosted_control_inputs.py::NativeControlInputDemoTests
```

Receipts remain under ignored `build/ci/` directories. The source fixture is
synthetic and contains no product or proprietary project data.
