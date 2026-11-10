# Mapped named-signal native fixtures

These tooling-owned schematics exercise a connector contact with the explicit
native pin function `PWM_SYNC`. The fault leaves the independently mapped
signal pin open; the control assigns it to `PWM_SYNC`. The signal is not a
recognized protocol alias, so the map supplies the review context. No project
or customer source is included.

The exact-version native lane exports each source twice with digest-pinned
KiCad 10.0.0 and 10.0.5, verifies the native pin-function and assignment
records, then evaluates the source-matched interface map. Run it with:

```sh
KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1 .venv/bin/python -I -B -m pytest -q \
  tests/test_connector_mapped_named_signal_native.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="connector.mapped_interface_signal_unassigned")'
```
