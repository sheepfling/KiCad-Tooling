# RS-485 data pins on named rails

These Tooling-owned synthetic schematics exercise
`bus.rs485_signal_on_named_rail`. The fault assigns the identified
transceiver's D input to a `GND` label; the control assigns D and R to distinct
signal nets. Both sources retain the complete two-pin inventory and native D/R
function metadata.

- `fault.kicad_sch` SHA-256: `4808cd9ba83174fd0d32d182f5816effa20a88da097dc18dea419f5115a39d23`
- `control.kicad_sch` SHA-256: `aa38e247661a1bf88460122caf2214bf3ad11468debdc4b6edd71a628a02e512`

The rule requires an explicit RS-485 marker in the native symbol library ID or
component value. It accepts only the bounded D/DI/DriverDataIn/DriverInput and
R/RO/ReceiverDataOut/ReceiverOutput aliases. A generic D/R pin, including a
CAN identity such as SN65HVD230, is not enough. Rail-like labels are prompts to
review and do not prove an electrical defect or intended transceiver mode;
projects can adjust the rule mode or record an exact reasoned ignore.

The exact-native lane repeats netlist and ERC exports with digest-pinned KiCad
10.0.0 and 10.0.5 images.

```sh
.venv/bin/python -I -m pytest tests/test_rs485_signal_named_rail.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.rs485_signal_on_named_rail")'

KICAD_RUN_NATIVE_RS485_SIGNAL_NAMED_RAIL_FIXTURES=1 \
  .venv/bin/python -I -m pytest tests/test_rs485_signal_named_rail_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.rs485_signal_on_named_rail")'
```
