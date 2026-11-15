# RS-485 data pins on named rails

These tooling-owned synthetic schematics exercise
`bus.rs485_signal_on_named_rail`. The fault assigns the identified
transceiver's D input and an explicitly identified MAX485 module connector's
DI input to a `GND` label. The control assigns both endpoints' DI/D and RO/R
pins to distinct signal nets. Both sources retain the complete two-pin
inventories and native pin-function metadata.

- `fault.kicad_sch` SHA-256: `a75fbc5e1f4df313e8c85df80abbf98b0746da4b35c33d3ca44f0e9b4bd70e18`
- `control.kicad_sch` SHA-256: `89558687fad23317ce7f83e75f55c18f632bd8ea6b9e710dd0c4776af873a2e8`

The rule requires an explicit RS-485 marker in the native symbol library ID or
component value and accepts fitted ICs and recognized connectors with bounded
D/DI/DriverDataIn/DriverInput and R/RO/ReceiverDataOut/ReceiverOutput aliases.
The connector fixture represents an explicitly identified MAX485 module, not a
generic serial header. A generic D/R pin, including a CAN identity such as
SN65HVD230, is not enough. Rail-like labels prompt review but do not prove an
electrical defect or intended transceiver mode; projects can adjust the rule
mode or record an exact reasoned ignore.

The exact-native lane repeats netlist and ERC exports with digest-pinned KiCad
10.0.0 and 10.0.5 images.

```sh
.venv/bin/python -I -m pytest tests/test_rs485_signal_named_rail.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.rs485_signal_on_named_rail")'

KICAD_RUN_NATIVE_RS485_SIGNAL_NAMED_RAIL_FIXTURES=1 \
  .venv/bin/python -I -m pytest tests/test_rs485_signal_named_rail_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.rs485_signal_on_named_rail")'
```
