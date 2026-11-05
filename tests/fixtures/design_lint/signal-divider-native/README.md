# Synthetic signal-divider native fixtures

These tooling-authored schematics exercise a project-mapped positive-source
divider feeding one named analog input. They contain no product schematic or
project requirements.

| Fixture | Change | Expected coverage |
| --- | --- | --- |
| `control.kicad_sch` | 220 kΩ / 33 kΩ divider from `SENSOR_OUT` to `GND` | Complete and within the authored input range |
| `value-fault.kicad_sch` | Upper resistor changes to 180 kΩ | Calculated nominal input is above the authored limit |
| `split-tap-fault.kicad_sch` | Lower resistor tap uses `ADC_OTHER` | Incomplete mapped topology |

The native lane exports each source twice with digest-pinned KiCad 10.0.0 and
10.0.5, compares normalized netlist and ERC outputs, then evaluates the source-
bound map. It does not validate tolerances, analog front-end protection,
receiver leakage, PCB routing, or a physical product.

Run the focused native lane with:

```sh
KICAD_RUN_NATIVE_SIGNAL_DIVIDER_FIXTURES=1 \
  .venv/bin/python -I -m pytest -q \
  tests/test_signal_divider_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad'
```
