# Native UART connector-reference fixtures

These four schematics are synthetic test inputs owned by KiCad-Tooling. They
contain no customer or private project data.

`serial-connector-fault.kicad_sch` directly connects U1's UART TX/RX pins to
J1's RX/TX pins. Both have an assigned 3.3 V supply. U1.4 is on `GND_A`, while
J1.4 is on `GND_B`. This tests the review case where a board-level serial IC
and its connector expose a direct UART link but use distinct schematic return
nets.

`serial-connector-control.kicad_sch` changes only J1.4 to `GND_A`. The
`bus.serial_peer_reference_review` prompt is absent on this control and present
on the split-reference fault. The native acceptance lane exports both sources
twice with digest-pinned KiCad 10.0.0 and 10.0.5 images. Their normalized
`NetlistContract` digests match across both versions and repeats:

- Common-reference control:
  `08650946c2dfeb42dda98b16e7ba9b37b934fdd310e6fb70e9801cfec08fef7d`
- Split-reference fault:
  `62d7ca8a8fa4b8006d4a9bf38a385d2b132527b3d18edb0f4f8ea95d178f410b`

Fixture source SHA-256 values:

- `serial-connector-control.kicad_sch`:
  `7d086f4f838504fa3cefc906f7f9e415240b10d89e95c9063c19780922915f16`
- `serial-connector-fault.kicad_sch`:
  `ee9ce9a51a78c422da96e260720247bb09403abe314921952f29c5d9ba110c20`

The lint report remains `REVIEW` on both cases because the fixture does not
author connector-inventory or serial-peer coverage decisions. The lane asserts
the presence or absence of this specific reference-domain prompt and retains
all findings. A current source-matched `serial_peers` direct map with
`reference_policy: separate_nets` suppresses the prompt in the synthetic
contract tests; that map records reviewed intent and does not prove a bond or
physical continuity.

The incremental-value control disables only this rule on the split-reference
fault. The remaining report has generic UART peer-map coverage and IC
decoupling prompts; no other finding names the `GND_A`/`GND_B` split. This
shows the context the rule adds on this synthetic case, not field precision.

`serial-label-fault.kicad_sch` and `serial-label-control.kicad_sch` cover a
separate case: two fitted U/IC symbols use generic native pin functions
(`B1/B2` and `ADBUS0/ADBUS1`), while the direct signal nets are labeled
`UART.0.TX` and `UART.0.RX`. The fault gives the two ICs distinct return nets;
the control shares `GND_A`. The native lane exports each file twice under the
same KiCad 10.0.0 and 10.0.5 image pins, checks the exact generic pin inventory
and labeled signal assignments, and requires one REVIEW prompt only on the
split-reference case.

In this fixture, TX connects U1.1 (output) to U2.1 (input), and RX connects
U2.2 (output) to U1.2 (input). The typed test-lane helper mirrors those exact
assignments from `serial-label-expected-nets.json`; both the typed helper and
native lane use this manifest. Mocked exports are unit-test evidence, not
native KiCad evidence. The native lane checks the manifest against repeated,
pinned KiCad exports.

Fixture source SHA-256 values:

- `serial-label-control.kicad_sch`:
  `a0ac8548431af625c5116c1d456e4f2c6cf1714e58cca84c6fe595165d87c561`
- `serial-label-fault.kicad_sch`:
  `2006adbfa6c6f1c99e88e3320a1ed7230f01a02f5e143c16a946abaa34f9db20`

The check is advisory. It asks whether the separate references are intentional;
it does not require common grounding or infer electrical approval. Native
schematic evidence does not establish PCB copper, external wiring, or
manufacturing readiness. Exact image digests and receipts are retained by the
CI lane under ignored `build/` paths.
