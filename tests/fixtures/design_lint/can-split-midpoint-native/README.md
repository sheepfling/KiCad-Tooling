# Synthetic split CAN termination native fixtures

These tool-owned schematics exercise the existing project-authored LINT-011
split termination contract after KiCad exports a native XML netlist. They use
synthetic component identities, pin functions, and values.

| Fixture             | Midpoint capacitor reference pin | Expected contract result                      |
| ------------------- | -------------------------------- | --------------------------------------------- |
| `control.kicad_sch` | `C1.2` on `GND`                  | CAN pins, both split legs, and capacitor pass |
| `fault.kicad_sch`   | `C1.2` on `GND_ALT`              | Only the mapped capacitor check fails         |

The control maps `U1.1`/`U1.2` to `CAN_H`/`CAN_L`, `R4`/`R5` as 60-ohm split
legs to `CAN_TERM_MID`, and `C1.1`/`C1.2` from that midpoint to `GND`. The fault
changes only the reference-net label for `C1.2`. Both files are exported twice
with each pinned KiCad version and compared after parsing into the normalized
typed netlist contract.

SHA-256 of the version-controlled sources:

| Fixture             | Source SHA-256                                                     |
| ------------------- | ------------------------------------------------------------------ |
| `control.kicad_sch` | `f69f9084482ce5455740c4ac33628fd226e5243650acd9a2e022984aec830726` |
| `fault.kicad_sch`   | `0c84ea82f7ff60be1d8a1ea6f2815fe9e6593ad1e8ae192f362c02af73bb8db6` |

Normalized native-netlist SHA-256 values match across KiCad 10.0.0 and 10.0.5:

| Fixture | Normalized netlist SHA-256                                         |
| ------- | ------------------------------------------------------------------ |
| Control | `de5d5d2edff5d2f4143bd8a5595734c3ea64f6dfa3844eef626999806fc53c9d` |
| Fault   | `4d0141640743cd0f953fe382941036a396f39b104fe89d9fd1febc43767bacb6` |

Run the optional native lane from an installed editable tooling checkout with
the public reference-template checkout available:

```sh
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test \
KICAD_RUN_NATIVE_CAN_TERMINATION_FIXTURES=1 \
python3.11 -I -B -m pytest -q \
  -m "interface_lint and native_kicad" \
  tests/test_can_native_fixture_lanes.py -k can_split_termination
```

The lane uses the template's digest-pinned KiCad images, mounts fixture input
read-only, disables container networking, and writes receipts below ignored
`build/` directories. It tests native schematic export and the authored
netlist contract; it does not run ERC/DRC or prove component construction,
physical bus-end placement, remote termination, or PCB copper continuity.
