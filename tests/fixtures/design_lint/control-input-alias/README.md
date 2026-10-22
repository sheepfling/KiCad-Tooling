# Synthetic control-input native fixtures

These tooling-owned schematics check control-input recognition and visible
bias-path behavior against native KiCad pin-function, electrical-type,
component-identity, and net-assignment evidence.

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

## Bare BOOT bootstrap-capacitor fixtures

`U1.1 BOOT` and `U1.2 SW` use distinct native nets. A fitted, exact two-pin
`Device:C` component bridges those nets. The connected-control heuristic
suppresses its missing-visible-resistor candidate for `U1.1` only when this
same-device topology is present. It does not verify that a capacitor is
required, sized correctly, placed correctly, or physically connected.

A companion fixture uses the exact `Device:C_Small` library identity with its
standard passive pins 1 and 2 on the same topology. The fixture-owned embedded
symbol is intentionally minimal; the test concerns native identity, pin
inventory, and net assignment, not rendered library artwork. KiCad's pinned
10.0.5 `Device.kicad_sym` has SHA-256
`af613124472cc646e2b272d6cd9d0de4f6defa40c2d107251f00f48665666d9a`; its
`C_Small` entry describes an unpolarized small capacitor and declares passive
pins 1 and 2. The [KiCad Device library reference](https://kicad.github.io/symbols/Device.html)
documents the same symbol as an unpolarized capacitor.

Typed-netlist controls keep bare `BOOT` reviewable without a same-device
switch-node pin, with a DNP capacitor, with a non-capacitor symbol identity, or
with an incomplete pin inventory. `BOOT0` remains reviewable even when the same
capacitor topology is present.

## Source and native evidence

| Evidence                                                       | Value                                                              |
| -------------------------------------------------------------- | ------------------------------------------------------------------ |
| `por-b.kicad_sch` source SHA-256                               | `63b1d9b49632c9e54e6576253223be14e4ce9b8bf4cf5485ddc8e4ca2dcf8743` |
| `series-bias-control.kicad_sch` source SHA-256                 | `217665dbcaa4ed740813c9105b89a45a9b70116142ed7593a1bc3ecde6662832` |
| `bare-boot-bootstrap-capacitor.kicad_sch` source SHA-256       | `8a6839b27629799ad42b96b611dc5d086c37609d1f6f698f37e2773885f3541d` |
| `bare-boot-bootstrap-small-capacitor.kicad_sch` source SHA-256 | `513df62ef3085040a997dda72b9e0713a4f353ac4da0a1308a5ee51d8cd44b50` |
| Source-manifest SHA-256                                        | `173897d8682ffa2e48412469164c6329235ddeb6b6a197898e0c7349a891358b` |
| KiCad image                                                    | `ghcr.io/kicad/kicad:10.0.5`                                       |
| Image digest                                                   | `fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c` |
| Pinned `Device.kicad_sym` SHA-256                              | `af613124472cc646e2b272d6cd9d0de4f6defa40c2d107251f00f48665666d9a` |
| POR normalized typed-netlist SHA-256, both exports             | `43392db78020b36af78ec52e2b437c795ec091047486f1b834625e3456718c89` |
| POR first and repeat raw netlist SHA-256                       | `df8095d2efed9006b28850d4fff3d8785737d21fd7887c1044ff0e22fc07740e` |
| Chain normalized typed-netlist SHA-256, both exports           | `7460ef30a887211f4bc8f8ef86ecc68e8220d7edfd131a1a86e7aa356f40a99b` |
| Chain first and repeat raw netlist SHA-256                     | `890e314d65f0b2d50f2463df3afc6852561aec654436ef056bb3841fddf0f213` |
| Bootstrap normalized typed-netlist SHA-256, both exports       | `1f47dd17c62a0e8e962582fbcc104123d18e5deb6c09b978c858d15443e82d83` |
| Bootstrap first and repeat raw netlist SHA-256                 | `49a0b3c4dd797809967666fdfcce6424b8c12f87b9c812f103c2e0555549f223` |
| Small-symbol bootstrap normalized netlist, both exports        | `803284fdb8a3f1e76cef39efa11b599e523ed4f941f0945dd78cc2d7ab2d41ef` |
| Small-symbol bootstrap first and repeat raw netlist SHA-256    | `9f668fd9677644c08675bcb0171e6fedce3646126b4bc6093ed2442b6ca4c7d0` |

The native lane confirms exact `POR_B`/`PORN` pin functions and `input` types,
leaves both pins unassigned, and emits only `U1.1` as a reset candidate. It also
confirms the chain fixture's exact pin assignments, DNP state, isolated
intermediate net, no connected-bias candidate, and repeated normalized export.
The two bootstrap fixtures add native evidence that exact `BOOT`, `SW`, each
capacitor library identity, two-pin inventory, fitted state, and capacitor net
assignments are retained. Both supported topologies produce zero
connected-bias candidates and repeat with matching normalized typed-netlist
hashes; raw export hashes differ as expected.
The pytest lane repeats four public KiCad demos and checks their pinned candidate
inventories and normalized netlists. A selected parameter case exports only
that sample; the full selection shares one container run across all samples.
The lane exports netlists; it does not run ERC or DRC and does not establish
that a reset pin requires bias.

Run from the tooling checkout with a public reference-template checkout
configured:

```sh
KICAD_TEMPLATE_ROOT=/absolute/path/to/KiCad-Test \
KICAD_RUN_NATIVE_CONTROL_INPUT_FIXTURES=1 \
  .venv/bin/python -I -m pytest -q tests/test_ci_hosted_control_inputs.py \
  -k 'bootstrap-capacitor-fixture or bootstrap-small-capacitor-fixture' \
  -m 'design_lint and interface_lint and native_kicad'
```

Receipts remain under ignored `build/ci/` directories. The source fixture is
synthetic and contains no product or proprietary project data.
