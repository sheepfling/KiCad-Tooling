# RS-485 data same-net fixtures

These Tooling-owned synthetic schematics exercise
`bus.rs485_data_input_output_same_net`. The fault assigns a fitted RS-485
transceiver's D driver-data input and R receiver-data output to one exact native
net. The control keeps those pins on separate nets. Both pins use passive
native electrical types so this heuristic remains independently observable
from ERC output-driver diagnostics.

- `same-data-net.kicad_sch`: D and R share `DATA_SHARED`. SHA-256:
  `d8af98143c7c94d2227206c5e6e93d03f8a82f32c9dbf87f93c6ad37bba4bc3a`.
- `separate-data-nets-control.kicad_sch`: D is on `HOST_TX`; R is on
  `HOST_RX`. SHA-256:
  `457198946c70c987a76ff18a4ea992e780db650dcd908497941fe2e8401f5d90`.

The heuristic requires explicit RS-485 text or a bounded MAX48xx, SP3485,
ADM48xx, SN65HVD485, or THVD identity marker in the native symbol library ID or
component value. This prevents generic D/R pin names on unrelated ICs from
being treated as an RS-485 transceiver. Projects may review, block, disable, or
ignore the finding. A same-net assignment can be intentional for echo or
single-wire operation; the rule does not establish that this topology is wrong,
and it does not prove PCB continuity or off-board wiring.

The TI SN65HVD23x family is CAN, not RS-485, so the identity check deliberately
does not accept the broad `SN65HVD` prefix alone. See TI's
[SN65HVD485E RS-485 datasheet][sn65hvd485e] and
[SN65HVD23x CAN datasheet][sn65hvd23x].

The native lane repeats netlist and ERC exports using digest-pinned KiCad
10.0.0 and 10.0.5 images.

Run the focused cases with:

```sh
.venv/bin/python -I -m pytest tests/test_rs485_data_input_output_same_net.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.rs485_data_input_output_same_net")'

KICAD_RUN_NATIVE_RS485_DATA_SAME_NET_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_rs485_data_input_output_same_net_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.rs485_data_input_output_same_net")'
```

[sn65hvd485e]: https://www.ti.com/lit/ds/symlink/sn65hvd485e.pdf
[sn65hvd23x]: https://www.ti.com/lit/ds/symlink/sn65hvd230.pdf
