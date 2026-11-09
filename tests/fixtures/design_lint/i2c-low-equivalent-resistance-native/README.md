# Synthetic I2C low-equivalent-resistance fixtures

These schematics exercise the nominal pull-up resistance review through native
KiCad XML netlist export. They are synthetic tooling fixtures and are not
derived from proprietary board data.

- `control.kicad_sch` connects two 2 kΩ `Device:R` components in parallel from
  `+3V3` to `I2C_SDA`, producing exactly 1 kΩ. The strict below-1-kΩ predicate
  remains quiet at the boundary. SHA-256:
  `62c084d84647d91126b1892bc88a3410fb42512d34d3dc42430189107f61dacd`.
- `fault.kicad_sch` uses two 1.5 kΩ resistors in the same topology, producing
  750 Ω and one `bus.i2c_low_equivalent_resistance` review. SHA-256:
  `b1f58647560672950fc58bc2e4e776a2cf6c3310396a5c0bc8980f9c2b7aa632`.

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
