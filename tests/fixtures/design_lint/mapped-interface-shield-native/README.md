# Mapped shield-contact native fixtures

These tooling-owned schematic sources exercise a source-matched interface map
whose pin 2 is explicitly reviewed as `role: shield`. The fault leaves that
contact unassigned. The control assigns it to a synthetic `CHASSIS` net. Both
schematics use a native passive pin and contain no board or product data.

The hosted connector acceptance lane exports each source twice with the exact
KiCad 10.0.0 and 10.0.5 images. The expected hashes are registered in
`kicad_tooling/ci_hosted_connector_return_fixture_sources.py`; matching typed
netlist cases are registered in `tests/connector_return_named_peer_cases.py`.

Focused synthetic and native checks:

```sh
python -I -m pytest tests/test_connector_mapped_interface_shield_unassigned.py \
  -m 'design_lint and connector_lint and design_lint_rule(rule_id="connector.mapped_interface_shield_unassigned")'

KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1 python -I -m pytest \
  tests/test_connector_mapped_interface_shield_unassigned.py \
  -m 'design_lint and native_kicad and design_lint_rule(rule_id="connector.mapped_interface_shield_unassigned")'
```

A REVIEW finding asks the project reviewer to decide whether the shield needs
a board bond or should remain isolated. The map's explicit
`unconnected_pin_reasons` entry suppresses an intentional open. This evidence
does not select a bond point or prove PCB continuity.
