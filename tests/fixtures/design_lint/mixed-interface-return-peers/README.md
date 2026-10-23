# Mixed USB and serial return review fixtures

These are tooling-owned synthetic regression inputs. They contain no customer
or production project source and are marked not for manufacture.

The fault schematic has two USB connectors and one serial connector. The
source-matched interface catalog identifies each connector's return pin, and
the connector review assigns each data interface to its own peer group. The
first USB return and serial return share `COMMON_RETURN`; the second USB return
is assigned to `USB2_RETURN`. The lint should raise one review finding for the
split return pins while keeping unrelated data pins scoped to their peer groups.

The control schematic puts all three mapped return pins on `COMMON_RETURN`.
It should produce no finding for `connector.repeated_pin_function`. This
control demonstrates deterministic behavior for this reviewed fixture; it
does not establish that every real USB or serial design must common its
returns. A review finding prompts a project engineer to decide whether the
separation is intended and supported by the interface requirements.

`interfaces.json` and `connector-reviews.json` are part of the source-bound
test input. The hosted lane verifies the exact source hashes, connector-map
coverage, KiCad net assignments, no native ERC errors, and repeatability of
netlist and ERC exports. It runs with the pinned KiCad 10.0.0 and 10.0.5
toolchains declared by `kicad_tooling/ci_hosted_kicad10_images.py`.

Reviewed input SHA-256 values:

| Input                    | SHA-256                                                            |
| ------------------------ | ------------------------------------------------------------------ |
| `fault.kicad_sch`        | `00b59baf0a11d507872a56c633245807d6abf2bb4cefd34a3b855ff7bd96e354` |
| `control.kicad_sch`      | `476bb3396e62037d27fb84423ef3c6d4097ae1382788a34def6a92a3acc8ccc3` |
| `interfaces.json`        | `e1216ee351d3fcdddd720f2bc6f0e2068bbc9d85e777aa4914c4af8102cb8b99` |
| `connector-reviews.json` | `57cd1b4cdf7663f41e0223ff48f83742b7ba3f592abd7664175c17c1c2c0c373` |

Run the exact-native gate in its CI lane with:

```sh
KICAD_RUN_NATIVE_MIXED_INTERFACE_RETURN_FIXTURES=1 \
  python -I -m pytest tests/test_connector_mixed_interface_return_native_lane.py \
  -m 'design_lint and connector_lint and interface_lint and return_path_lint and native_kicad'
```
