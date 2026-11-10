# Synthetic I2C low-equivalent-resistance fixtures

These schematics exercise the nominal pull-up resistance review through native
KiCad XML netlist export. They are synthetic tooling fixtures and are not
derived from proprietary board data.

- `control.kicad_sch` connects two 2 kΩ `Device:R` components written with a
  decimal comma in parallel from
  `+3V3` to `I2C_SDA`, producing exactly 1 kΩ. The strict below-1-kΩ predicate
  remains quiet at the boundary. SHA-256:
  `0574dbdecd149637c80ec3d9427a9c7fcea78f9542bb8371ea02ad8b7c4570f2`.
- `fault.kicad_sch` uses two 1.5 kΩ resistors written with a decimal comma in the
  same topology, producing
  750 Ω and one `bus.i2c_low_equivalent_resistance` review. SHA-256:
  `183705336727e538f54e80c94c4d318d6e94b9dba8b247c8bfdea96c504937ce`.

The exact-version lane exports and normalizes each schematic twice with the
digest-pinned KiCad 10.0.0 and 10.0.5 images. The assertion covers the native
symbol IDs, pin inventories, resistor values, SDA and rail assignments, exact
boundary behavior, and the final lint finding. The result does not establish
resistor tolerances, sink-current margin, rise time, bus voltage compatibility,
PCB copper connectivity, or a project-specific design requirement.

Run the focused native case with:

```sh
KICAD_RUN_NATIVE_I2C_PULLUP_FIXTURES=1 .venv/bin/python -I -m pytest -q \
  tests/test_i2c_pullup_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.i2c_low_equivalent_resistance")'
```
