# Synthetic POR control-input alias fixture

This tooling-owned schematic checks the bounded reset-alias behavior against
native KiCad pin-function and electrical-type evidence. Both pins are
unassigned native `input` pins. `POR_B` is the positive case for the `POR`
reset token; `PORN` is a deliberate substring nonmatch.

| Pin    | Function | Electrical type | Native assignment | Expected unconnected-input result |
| ------ | -------- | --------------- | ----------------- | --------------------------------- |
| `U1.1` | `POR_B`  | `input`         | none              | reset review candidate            |
| `U1.2` | `PORN`   | `input`         | none              | no candidate                      |

## Source and native evidence

| Evidence                                       | Value                                                              |
| ---------------------------------------------- | ------------------------------------------------------------------ |
| Schematic source SHA-256                       | `63b1d9b49632c9e54e6576253223be14e4ce9b8bf4cf5485ddc8e4ca2dcf8743` |
| Source-manifest SHA-256                        | `962ac0ef41e3a72d103fa69cb27985b4c2ce92fcf14f5c2f71cc2adb4ee04417` |
| KiCad image                                    | `ghcr.io/kicad/kicad:10.0.5`                                       |
| Image digest                                   | `fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c` |
| Normalized typed-netlist SHA-256, both exports | `43392db78020b36af78ec52e2b437c795ec091047486f1b834625e3456718c89` |
| First raw netlist SHA-256                      | `b17fb74e67a7187ac81fed2716ba376736875bd18004b62a1349a31efc3310ef` |
| Repeat raw netlist SHA-256                     | `ce009e2e4afdbe06a7c93ed4ae0dc6d225b673e95bed3917abb049c75a0873c6` |

The native lane confirms exact `POR_B`/`PORN` pin functions and `input` types,
leaves both pins unassigned, and emits only `U1.1` as a reset candidate. The
test also repeats four public KiCad demos and checks their pinned candidate
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
