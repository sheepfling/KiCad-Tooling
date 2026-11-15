# Synthetic connector serial signal on named rail

These native schematic fixtures are synthetic tooling inputs. They contain no
customer, private, or project-specific board data.

The TX/RX cases include a serial connector J1 with a TX pin, a separate signal
pin, and a reference pin assigned to `GND_B`. The reference assignment is
identical in both cases. The control assigns J1.1 to `UART_TX`; the fault
changes only that electrical signal label to `GND_C`. This isolates the
named-rail clue from the independent question of whether the connector return
should share a ground domain.

CTS cases change the exact connector/controller function from RX to CTS. The
fault keeps J1.1 on `GND_C`; the control keeps it on a neutral `UART_TX` net.
RTS cases change the exact function from TX to RTS. The fault assigns J1.2 to
`+3V3`; the control keeps it on neutral `UART_RX`. These synthetic controls
exercise both CTS and RTS recognition without implying that hardware flow
control must be enabled in a real design.

The rule uses the native pin function, complete connector pin inventory, and
single assigned net label to raise a default-REVIEW finding. It does not infer
the approved connector pinout, prove an electrical fault, or inspect PCB copper
or physical continuity.

Source SHA-256:

- `control.kicad_sch`: `a02c6e00f6721090b998eb0d4d38d049580e6f71246353cef054435950a4c746`
- `fault.kicad_sch`: `5c4ec3e6844ca51f105dba9a5e3b422fdbecf0a7846cdfbd89ed328f6b99b0ad`
- `cts-control.kicad_sch`: `73553713739249d27755c3bc1040b11ebdbe553b262af58f4a810a0e6bb24be2`
- `cts-fault.kicad_sch`: `5019a069d0bafc353c8a48894a9053479dacc3129347984727d6682074efe6ac`
- `rts-control.kicad_sch`: `32574617203027bca3e234317e74740746bdf4323ed64e86dc46ed79e182cd7f`
- `rts-fault.kicad_sch`: `e65817db762a1aac10574ef55c913bdcbd648939cc246c987419895daf761b6d`

The native lane exports all sources twice with digest-pinned KiCad 10.0.0 and
10.0.5 images, compares normalized netlists, and requires one finding on each
named-rail fault and none on each matching control. Run it with:

```sh
KICAD_RUN_NATIVE_SERIAL_TX_RX_LABEL_MISMATCH_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_serial_connector_signal_named_rail_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.serial_signal_on_named_rail")'
```

The rule uses the shared typed design-lint evaluator used by CLI and MCP. This
change adds no CLI or MCP operation.
