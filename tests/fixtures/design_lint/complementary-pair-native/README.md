# Complementary-pair native fixtures

These synthetic KiCad schematics exercise the
`bus.complementary_pair_assignment` rule with USB-IF Standard-A pin-function
spellings and Ethernet PHY pin-function aliases.
The indexed USB-C lane pair also uses tooling-authored `SSTX1/2` and
`SSRX1/2` functions to ensure each direction/lane combination is evaluated
separately.

- `fault.kicad_sch` has SHA-256
  `6147ed074f97e061213d048174c1820d76dc523e682c96e6c58bfb6231e4a49d`.
  The USB `StdA_SSRX-` and Ethernet `TDN` pins are open and should produce
  localized review findings. The other pair pins have distinct assignments.
- `control.kicad_sch` has SHA-256
  `ce1c57f200b9f042fe4174f6b1b4b327b717c3e93623e50f262bf2352b8e6089`.
  The USB signal pins, ground contact, and Ethernet TDP/TDN/RDP/RDN pins have
  unique assignments; the heuristic should be quiet.
- `lane-fault.kicad_sch` has SHA-256
  `03b826311ce60c87b6fbff6af58ea26345f688d0cca132b546455dd1e660dc76`.
  The USB-C `SSTX1+` and `SSTX1-` pins share one net; the three remaining
  direction/lane pairs have distinct assignments. One localized review is
  expected for the TX1 pair.
- `lane-control.kicad_sch` has SHA-256
  `395b30796caaae0ec8c708d1fdfab513b22c7ee6f570d7c4affe084f9bf322d7`.
  All four indexed TX/RX lane pairs use separate positive and negative nets;
  the heuristic should be quiet.

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
