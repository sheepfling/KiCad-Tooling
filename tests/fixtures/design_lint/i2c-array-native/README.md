# Synthetic I2C resistor-array native fixtures

These schematics exercise the project-authored LINT-010 mapped-array check
after KiCad exports a native XML netlist. They contain only synthetic symbols,
part identities, pin maps, and values.

The synthetic project requirement is stored separately in `pullups.json`
(SHA-256 `38c97126ac75bb0dadf2153decdbcfa2f78101532d401920db54712bb204f5b2`).
The native lane copies it into a temporary project-relative path, validates it
through the shared contract reader, and binds its digest and path to lint
coverage.

| Fixture             | RN1.1       | Expected line checks                                  |
| ------------------- | ----------- | ----------------------------------------------------- |
| `control.kicad_sch` | `I2C_SDA`   | SDA and SCL pass                                      |
| `fault.kicad_sch`   | `SDA_WRONG` | SDA fails with the exact pin/net mismatch; SCL passes |

The 4-pin array maps independent channels RN1.1–RN1.2 and RN1.3–RN1.4 to
SDA/SCL and +3V3. The native export must retain the symbol ID, footprint,
value, expected project `PART_ID`, all four pins, and exact net assignments.
Both schematics include an explicit `Device:C` capacitor under the nonstandard
reference `X1`, connected from SDA to GND. The authored capacitance scope maps
its exact symbol, footprint, two-pin inventory, nets, nominal range, and
effective-capacitance bound; native export must preserve that mapping. The
fault schematic also puts an unmapped `Device:C` symbol at `X2` on SDA, proving
that symbol-based discovery catches a capacitor even when its reference is not
C-prefixed.
Each source is exported twice and compared after parsing to the normalized
typed-netlist contract; raw XML hashes are retained because KiCad may vary
metadata between exports.
The authored contract binds a synthetic maximum resistor tolerance to each
exact array channel, explicitly maps X1, inventories conventional C-prefixed
parts and recognized capacitor-symbol IDs on each bus line, and supplies the
reviewed residual capacitance and rise-time bounds. The control passes with
X1 mapped; the fault remains open and names X2 as an unmapped fitted
capacitor. Both exports
must retain the native-derived channel tolerance checks; the control passes its
mapped capacitance scope and the fault fails on X2. The same native-derived contracts exercise
`bus.i2c_missing_pullup`: without the authored requirement, both fixtures
remain review candidates. The control's passing SDA/SCL topology and electrical
window checks resolve that hint; the wrong-SDA fault keeps it open even though
SCL and both authored tolerance scopes pass. This proves the contract-to-lint
integration on the exported netlist, not the array's internal construction or
the correctness of its synthetic source assumptions.

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
native netlist parsing, the authored schematic contract, and the mapped-array
coverage interaction with the review heuristic. It does not run ERC/DRC or
prove the resistor array's internal construction or physical behavior.
