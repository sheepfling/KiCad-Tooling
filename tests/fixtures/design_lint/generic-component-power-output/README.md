# Generic component power-output fixtures

These tooling-owned schematics exercise `component.unconnected_power_output`
with one fitted component and a generic native `power_out` pin.

- `fault.kicad_sch` leaves U1.1 unassigned while U1.2 remains on a separate
  signal net.
- `control.kicad_sch` assigns U1.1 to `POWER_OUTPUT_TEST`; the arbitrary net
  name is not interpreted as a voltage or requirement.

SHA-256:

| Fixture | SHA-256 |
| --- | --- |
| `fault.kicad_sch` | `9d05db034caed6a56eb7fe3de13a06fd414969f39e9e4c57b9deee76edb828eb` |
| `control.kicad_sch` | `cd7494eaac52d82d32e123be5740e2f88c8d6753e4f11a197c3452df0a5951cf` |

The rule defaults to review because native electrical type alone does not
establish that an output must be connected. The exact native regression exports
both schematics twice using digest-pinned KiCad 10.0.0 and 10.0.5 images and
compares normalized netlist contracts. The lane does not run ERC and does not
evaluate output capability, voltage, current, or PCB connectivity.

All fixture sources are synthetic tooling test data, not manufacturing designs.
