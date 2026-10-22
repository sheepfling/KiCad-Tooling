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

## Bare BOOT bootstrap-capacitor fixture

`U1.1 BOOT` and `U1.2 SW` use distinct native nets. A fitted, exact two-pin
`Device:C` component bridges those nets. The connected-control heuristic
suppresses its missing-visible-resistor candidate for `U1.1` only when this
same-device topology is present. It does not verify that a capacitor is
required, sized correctly, placed correctly, or physically connected.

Typed-netlist controls keep bare `BOOT` reviewable without a same-device
switch-node pin, with a DNP capacitor, with another symbol identity, or with an
incomplete pin inventory. `BOOT0` remains reviewable even when the same
capacitor topology is present.

## Source and native evidence

| Evidence                                                 | Value                                                              |
| -------------------------------------------------------- | ------------------------------------------------------------------ |
| `por-b.kicad_sch` source SHA-256                         | `63b1d9b49632c9e54e6576253223be14e4ce9b8bf4cf5485ddc8e4ca2dcf8743` |
| `series-bias-control.kicad_sch` source SHA-256           | `217665dbcaa4ed740813c9105b89a45a9b70116142ed7593a1bc3ecde6662832` |
| `bare-boot-bootstrap-capacitor.kicad_sch` source SHA-256 | `8a6839b27629799ad42b96b611dc5d086c37609d1f6f698f37e2773885f3541d` |
| Source-manifest SHA-256                                  | `22465da0163965da2e11583c0afe91c6758d0a22e138da801a623f10d21b839d` |
| KiCad image                                              | `ghcr.io/kicad/kicad:10.0.5`                                       |
| Image digest                                             | `fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c` |
| POR normalized typed-netlist SHA-256, both exports       | `43392db78020b36af78ec52e2b437c795ec091047486f1b834625e3456718c89` |
| POR first and repeat raw netlist SHA-256                 | `df8095d2efed9006b28850d4fff3d8785737d21fd7887c1044ff0e22fc07740e` |
| Chain normalized typed-netlist SHA-256, both exports     | `7460ef30a887211f4bc8f8ef86ecc68e8220d7edfd131a1a86e7aa356f40a99b` |
| Chain first and repeat raw netlist SHA-256               | `890e314d65f0b2d50f2463df3afc6852561aec654436ef056bb3841fddf0f213` |
| Bootstrap normalized typed-netlist SHA-256, both exports | `1f47dd17c62a0e8e962582fbcc104123d18e5deb6c09b978c858d15443e82d83` |
| Bootstrap first raw netlist SHA-256                      | `518d9058efb0a8c11c6ef709e9fc05dd93fac5af33aabf0668ccfb46863d8fda` |
| Bootstrap repeat raw netlist SHA-256                     | `79378aec722a66a57c107af71c2c81e9523456aebf996c43a860cbc34cc63d8f` |

The native lane confirms exact `POR_B`/`PORN` pin functions and `input` types,
leaves both pins unassigned, and emits only `U1.1` as a reset candidate. It also
confirms the chain fixture's exact pin assignments, DNP state, isolated
intermediate net, no connected-bias candidate, and repeated normalized export.
The bootstrap fixture adds native evidence that exact `BOOT`, `SW`, `Device:C`,
pin inventory, DNP state, and capacitor net assignments are retained, and that
the connected-control heuristic stays quiet on this supported topology. Its
two KiCad 10.0.5 exports have the same normalized typed-netlist hash and zero
connected-bias candidates; raw export hashes differ as expected.
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
  -k bootstrap-capacitor-fixture -m 'design_lint and interface_lint and native_kicad'
```

Receipts remain under ignored `build/ci/` directories. The source fixture is
synthetic and contains no product or proprietary project data.
