# USB SuperSpeed complementary-pair fixture

These synthetic KiCad schematics exercise the `bus.complementary_pair_assignment`
rule with the USB-IF Standard-A pin-function spellings `StdA_SSTX+/-` and
`StdA_SSRX+/-`.

- `fault.kicad_sch` — SHA-256:
  `cc8832c4f8ab0b74996f3035ec5c9b85780c11e63bee9a33ea50d319dff2c755`
  - The `StdA_SSRX-` pin is open and should produce one localized review finding.
- `control.kicad_sch` — SHA-256:
  `4c0fcc56824a6004a1f63cfd0fc026f8e90438919eb936c492eeb96e9ecad601`
  - All four signal pins and the ground contact have unique net assignments;
    the heuristic should be quiet.

The digest-pinned native lane exports each schematic twice using exact KiCad
10.0.0 and 10.0.5 images selected from the public reference template. It checks
that native netlists preserve the pin-function strings, parsed contracts are
repeatable across runs and versions, and the fault/control lint results differ
as expected. The fixture is synthetic tooling data; it is not copied from a
project board and is not manufacturing guidance.

Run the native regression with:

```sh
KICAD_RUN_NATIVE_COMPLEMENTARY_PAIR_FIXTURES=1 \
KICAD_TEMPLATE_ROOT=/path/to/public/KiCad-Team-Workflow-Template \
KICAD_RUN_NATIVE_COMPLEMENTARY_PAIR_FIXTURES=1 .venv/bin/python -I -m pytest -q tests/test_complementary_pair_native_fixture_lane.py -m 'design_lint and interface_lint and native_kicad'
```

The source specifications and alias rationale are linked from
[backlog item LINT-003](../../../../docs/DESIGN_LINT_BACKLOG.md#lint-003--paired-line-and-differential-interface-completeness).
