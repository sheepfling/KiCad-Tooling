# Synthetic connector serial signal on named rail

These native schematic fixtures are synthetic tooling inputs. They contain no
customer, private, or project-specific board data.

Both cases include a serial connector J1 with a TX pin, a separate signal pin,
and a reference pin assigned to `GND_B`. The reference assignment is identical
in both cases. The control assigns J1.1 to `UART_TX`; the fault changes only
that electrical signal label to `GND_C`. This isolates the named-rail clue
from the independent question of whether the connector return should share a
ground domain.

The rule uses the native pin function, complete connector pin inventory, and
single assigned net label to raise a default-REVIEW finding. It does not infer
the approved connector pinout, prove an electrical fault, or inspect PCB copper
or physical continuity.

Source SHA-256:

- `control.kicad_sch`: `a02c6e00f6721090b998eb0d4d38d049580e6f71246353cef054435950a4c746`
- `fault.kicad_sch`: `5c4ec3e6844ca51f105dba9a5e3b422fdbecf0a7846cdfbd89ed328f6b99b0ad`

The native lane exports both sources twice with digest-pinned KiCad 10.0.0 and
10.0.5 images, compares normalized netlists, and requires one finding on the
fault and none on the control. Run it with:

```sh
KICAD_RUN_NATIVE_SERIAL_TX_RX_LABEL_MISMATCH_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_serial_connector_signal_named_rail_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.serial_signal_on_named_rail")'
```

The rule uses the shared typed design-lint evaluator used by CLI and MCP. This
change adds no CLI or MCP operation.
