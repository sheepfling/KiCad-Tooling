# Complementary-pair native fixtures

These synthetic KiCad schematics exercise the
`bus.complementary_pair_assignment` rule with USB-IF Standard-A pin-function
spellings and Ethernet PHY pin-function aliases.

- `fault.kicad_sch` has SHA-256
  `ec0058d7bbb339b10c93970485e4c5645512f569db64d8982592d7ad34495d6a`.
  The USB `StdA_SSRX-` and Ethernet `TDN` pins are open and should produce
  localized review findings. The other pair pins have distinct assignments.
- `control.kicad_sch` has SHA-256
  `2f327f534795b4d991c0b298c3401a627393d17a9744051d77b11b0a48b9b792`.
  The USB signal pins, ground contact, and Ethernet TDP/TDN/RDP/RDN pins have
  unique assignments; the heuristic should be quiet.

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
