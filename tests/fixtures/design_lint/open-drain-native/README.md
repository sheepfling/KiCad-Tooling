# Synthetic open-output bias fixtures

These tooling-owned schematics test a narrow review heuristic using native
KiCad exports. A synthetic open-collector or open-emitter output on U2 and a
separate digital input on U1 share `ALERT_N`; each device's unused pin has an
explicit no-connect marker. R1 directly joins the signal to the expected rail
in the direct controls; the corresponding fault schematics retain R1 with DNP
set. The two series controls use fitted 10 kΩ R1/R2 parts with a two-pin
intermediate net; no value window is applied by this review heuristic.

| Fixture                              | Pin type         | Bias path                           | Expected design-lint result                           |
| ------------------------------------ | ---------------- | ----------------------------------- | ----------------------------------------------------- |
| `collector-control.kicad_sch`        | `open_collector` | Fitted 10 kΩ to `+3V3`              | REVIEW; no bias finding, peer-input review for `U2.2` |
| `collector-fault.kicad_sch`          | `open_collector` | 10 kΩ to `+3V3`, DNP                | REVIEW; missing-bias and peer-input findings          |
| `emitter-control.kicad_sch`          | `open_emitter`   | Fitted 10 kΩ to `GND`               | REVIEW; no bias finding, peer-input review for `U2.2` |
| `emitter-fault.kicad_sch`            | `open_emitter`   | 10 kΩ to `GND`, DNP                 | REVIEW; missing-bias and peer-input findings          |
| `collector-series-control.kicad_sch` | `open_collector` | 10 kΩ + 10 kΩ series path to `+3V3` | REVIEW; no bias finding, peer-input review for `U2.2` |
| `emitter-series-control.kicad_sch`   | `open_emitter`   | 10 kΩ + 10 kΩ series path to `GND`  | REVIEW; no bias finding, peer-input review for `U2.2` |

All six reports include the independent
`component.peer_signal_input_unconnected` prompt for `U2.2`: the native input
on U1 is assigned to `ALERT_N`, while the corresponding input on the exact-symbol
U2 peer is explicitly left open. The fixture tests the bias rule separately
through `bias_rule_status`; its overall lint status is `REVIEW` because of this
second, valid heuristic prompt. The peer-input coverage entry is tied to the
native netlist digest. This is a useful review prompt, not proof that U2.2 must
be connected; a project can record an exact ignore when that open pin is
reviewed and intentional.

The fixture lane is opt-in for package acceptance CI and uses the exact
project-selected KiCad 10.0.0 and 10.0.5 digest-pinned images. It exports each
case's netlist and ERC report twice. The lane checks native electrical pin
types, exact net membership, DNP state, independent rule findings, zero ERC
errors, and repeatable normalized reports. The workflow is configured to run
the lane. The previous tagged acceptance surfaced the peer-input review on
these exact-symbol controls; the lane now records both the bias-specific result
and the independent source-bound peer coverage. Expected ERC warnings include
missing synthetic library and footprint links plus the standalone bias-rail
label; the lane records warning types and does not treat them as errors.

| KiCad version | Digest-pinned image                                                                                  |
| ------------- | ---------------------------------------------------------------------------------------------------- |
| 10.0.0        | `ghcr.io/kicad/kicad:10.0.0@sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3` |
| 10.0.5        | `ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacb662cec5c916e4c`  |

The normalized native netlist hashes matched across both KiCad versions and
their repeated exports:

| Fixture                              | Normalized netlist SHA-256                                         |
| ------------------------------------ | ------------------------------------------------------------------ |
| `collector-control.kicad_sch`        | `bb5b9b6e92a414fd42ee6afe6318e341a6a535bd7d4e1983dc69d3c977758e34` |
| `collector-fault.kicad_sch`          | `6913b490585e072c7641a1800540bb4859b0009d68d4e4428ad2925417f85b20` |
| `emitter-control.kicad_sch`          | `4dce56e48d3b8082026f65dad1d9dd69b7466224ad617786566396aae6f74c9d` |
| `emitter-fault.kicad_sch`            | `6efc7bd50862e1190ebd70962b50dfbfe813f74d51aa8f88d2b7f2f3bc385588` |
| `collector-series-control.kicad_sch` | `733358edc49524e860512a0f4a8ac6afd45b09c4533053218d6a6cf841364fb9` |
| `emitter-series-control.kicad_sch`   | `f7069b305c31262710ea29e895ac470fe79455a5d1b4c31ee2324732164fa880` |

SHA-256 of the version-controlled schematic sources:

| Fixture                              | SHA-256                                                            |
| ------------------------------------ | ------------------------------------------------------------------ |
| `collector-control.kicad_sch`        | `bdb0b34256ef9bac90b7fba687abe5998400c29da2f2467cd1a43e8b1029c177` |
| `collector-fault.kicad_sch`          | `bb4d7075d2892bf2991a3b840ba1db956cdf6a2f6caba1538ef1381c0d937714` |
| `emitter-control.kicad_sch`          | `3f2bcdb733865867bef38ba1fe790518e8aa35225e04117220dcac07e53645f0` |
| `emitter-fault.kicad_sch`            | `b987e6f281edc13de3587614cb3bb19ed80bfeeaccde783dcf1492ef598826e1` |
| `collector-series-control.kicad_sch` | `48fdf3c5f0ab6b37e9a90bfc5d97b9c37c76f27f87f84dbe07601803ac5d52fb` |
| `emitter-series-control.kicad_sch`   | `c4953af0ec31cf3ea0b71b0b6397698867d5d5e217632ff20d83c97f76d3e0c3` |

These fixtures establish schematic pin/net assignments and whether the
resistors are fitted in the source. They do not establish that a particular
output needs an external bias, that the selected value meets device limits,
or that the PCB copper implements the schematic. The finding remains a
review prompt. All sources are synthetic and contain no proprietary or customer
project data; generated exports and receipts remain under ignored `build/`
directories.
