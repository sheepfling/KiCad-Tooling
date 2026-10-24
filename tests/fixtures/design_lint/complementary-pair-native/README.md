# Complementary-pair native fixtures

These synthetic KiCad schematics exercise the
`bus.complementary_pair_assignment` rule with USB-IF Standard-A pin-function
spellings and Ethernet PHY pin-function aliases.
The indexed USB-C lane pair also uses tooling-authored `SSTX1/2` and
`SSRX1/2` functions to ensure each direction/lane combination is evaluated
separately.
The lane-label cases also exercise
`bus.usb_c_superspeed_lane_label_mismatch` against explicit USB-C direction,
lane, and polarity net names.

- `fault.kicad_sch` has SHA-256
  `6147ed074f97e061213d048174c1820d76dc523e682c96e6c58bfb6231e4a49d`.
  The USB `StdA_SSRX-` and Ethernet `TDN` pins are open and should produce
  localized review findings. The other pair pins have distinct assignments.
- `control.kicad_sch` has SHA-256
  `ce1c57f200b9f042fe4174f6b1b4b327b717c3e93623e50f262bf2352b8e6089`.
  The USB signal pins, ground contact, and Ethernet TDP/TDN/RDP/RDN pins have
  unique assignments; the heuristic should be quiet.
- `lane-fault.kicad_sch` has SHA-256
  `9e3b9f4f6d39956d6a803e8a8e9df8ad1006adedaefe6654cd7728367f2a48eb`.
  The USB-C `SSTX1+` and `SSTX1-` pins share one net; the three remaining
  direction/lane pairs have distinct assignments. Its ninth contact is a
  connected GND reference so unrelated return checks stay quiet. One localized
  review is expected for the TX1 pair.
- `lane-control.kicad_sch` has SHA-256
  `9e14b4a936dbfc2907ec031f10dccc4ed32a385134abd568144ea7104a66a853`.
  All four indexed TX/RX lane pairs use separate positive and negative nets;
  its ninth contact is a connected GND reference, and neutral net names keep
  unrelated named-pair review quiet.
- `lane-label-fault.kicad_sch` has SHA-256
  `fe4cf3472eb4961faaef4d935317188d23e7028350c245bb8eb0ef1a29ba0248`.
  The TX1 and TX2 lane labels are swapped while each pair remains separately
  assigned; four pin-localized lane-label reviews and no pair-completeness
  findings are expected.
- `lane-label-control.kicad_sch` has SHA-256
  `a4be145343d775dee661e5381eff65a8895feea6581adfd77cea5f07952bdf91`.
  All four indexed TX/RX pairs have explicit labels matching their connector
  pin functions; both the lane-label and pair-completeness rules stay quiet.
  The overall report may still be `REVIEW` for an independent heuristic, so
  this control asserts only the two rules exercised by this fixture.

The digest-pinned native lane exports each schematic twice using exact KiCad
10.0.0 and 10.0.5 images selected from the public reference template. It checks
that native netlists preserve the pin-function strings, parsed contracts are
repeatable across runs and versions, and fault/control findings differ as
expected. The fixture is synthetic tooling data; it is not copied from a
project board and is not manufacturing guidance.

Run the native regression with:

```sh
KICAD_RUN_NATIVE_COMPLEMENTARY_PAIR_FIXTURES=1 \
KICAD_TEMPLATE_ROOT=/path/to/public/KiCad-Team-Workflow-Template \
.venv/bin/python -I -m pytest -q tests/test_complementary_pair_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad'
```

The source specifications and alias rationale are linked from
[backlog item LINT-003](../../../../docs/DESIGN_LINT_BACKLOG.md#lint-003--paired-line-and-differential-interface-completeness).
