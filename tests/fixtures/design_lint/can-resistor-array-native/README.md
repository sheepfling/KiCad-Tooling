# Synthetic CAN resistor-array native fixtures

These tooling-owned schematics exercise the project-authored LINT-011 mapped
resistor-array contract after KiCad exports a native XML netlist. They contain
only synthetic component identities, pin maps, and values. The requirement is
embedded in a complete typed `electrical.json` fixture.

| Fixture             | RN1.1       | Expected contract result                               |
| ------------------- | ----------- | ------------------------------------------------------ |
| `control.kicad_sch` | `CAN_H`     | CAN pins, both split channels, and array identity pass |
| `fault.kicad_sch`   | `CAN_WRONG` | Only the mapped split-array path fails                 |

RN1 uses two independent 60-ohm channels. Pins 1/2 map CAN_H to
CAN_TERM_MID; pins 3/4 map CAN_L to the same midpoint. The lane checks the
native symbol, footprint, value, PART_ID, complete pin inventory, and exact
net assignment for every channel. A resistor-array channel's internal
resistance is authored evidence and is not measured by KiCad's schematic
netlist export.

Both schematics are exported twice with the digest-pinned KiCad 10.0.0 and
10.0.5 images. Their normalized netlist hashes and source hashes are recorded
by the native lane under ignored `build/` receipts.

The native lane pins these synthetic source inputs:

| Input               | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `control.kicad_sch` | `1f014e79a42f45d5b08d3ef8394dd3b38e992c2af7a67c987c067afa77c3a186` |
| `fault.kicad_sch`   | `cae3faf3cba68758c3ed35755d49b96088799922c3c45af3fdc644f5d6d05a2d` |
| `electrical.json`   | `5c1fc55b40a292e32534aff67e3e17e535edad6e2f10d86fe2a3fe67bba3b872` |

Run the optional native lane from an installed editable Tooling checkout with
the public reference-template checkout available:

```sh
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test \
KICAD_RUN_NATIVE_CAN_TERMINATION_FIXTURES=1 \
.venv/bin/python -I -B -m pytest -q -m "interface_lint and native_kicad" \
  tests/test_can_termination_array_native_fixtures.py
```

The lane verifies source-bound native netlist export and the explicit contract.
It does not prove resistor-array construction, PCB continuity, termination
placement at a physical bus end, or electrical performance.
