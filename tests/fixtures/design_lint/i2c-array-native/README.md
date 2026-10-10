# Synthetic I2C resistor-array native fixtures

These schematics exercise the project-authored LINT-010 mapped-array check
after KiCad exports a native XML netlist. They contain only synthetic symbols,
part identities, pin maps, and values.

| Fixture             | RN1.1       | Expected line checks                                  |
| ------------------- | ----------- | ----------------------------------------------------- |
| `control.kicad_sch` | `I2C_SDA`   | SDA and SCL pass                                      |
| `fault.kicad_sch`   | `SDA_WRONG` | SDA fails with the exact pin/net mismatch; SCL passes |

The 4-pin array maps independent channels RN1.1–RN1.2 and RN1.3–RN1.4 to
SDA/SCL and +3V3. The native export must retain the symbol ID, footprint,
value, all four pins, and exact net assignments. Each source is exported twice
and compared after parsing to the normalized typed-netlist contract; raw XML
hashes are retained because KiCad may vary metadata between exports.

Run the optional native lane from an installed editable Tooling checkout with
the public reference-template checkout available:

```sh
KICAD_RUN_NATIVE_I2C_PULLUP_FIXTURES=1 \
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test \
python -I -B -m pytest -q -m "interface_lint and native_kicad" \
  tests/test_i2c_pullup_native_fixture_lane.py
```

The lane uses the template's digest-pinned KiCad 10.0.0 and 10.0.5 images,
mounts this fixture directory read-only, disables network access, and writes
receipts only below the Tooling checkout's ignored `build/` directory. It tests
native netlist parsing and the authored schematic contract; it does not run
ERC/DRC or prove the resistor array's internal construction or physical
behavior.
