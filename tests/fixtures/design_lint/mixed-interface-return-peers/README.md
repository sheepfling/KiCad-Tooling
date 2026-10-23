# Mixed USB and serial return review fixtures

These are tooling-owned synthetic regression inputs. They contain no customer
or production project source and are marked not for manufacture.

The fault schematic has two USB connectors and one serial connector. The
source-matched interface catalog identifies each connector's return pin, and
the connector review assigns each data interface to its own peer group. All
three returns share one return-comparison group for the fault and common-net
control. The first USB return and serial return share `COMMON_RETURN`; the second
USB return is assigned to `USB2_RETURN`. The lint should raise one review finding
for the split return pins while keeping unrelated data pins scoped to their peer
groups. The fault is also evaluated with
`connector-reviews-separate-return-groups.json`: J1/J2 share one comparison
scope while J3 has another, so the cross-group return prompt is suppressed. This
review-scope control does not claim electrical isolation or continuity.

The control schematic puts all three mapped return pins on `COMMON_RETURN` and
keeps them in one return-comparison group. It should produce no finding for
`connector.repeated_pin_function` or
`connector.return_supply_scope_singleton`. This control demonstrates
deterministic behavior for this reviewed fixture; it does not establish that
every real USB or serial design must common its returns.

The separate-group map deliberately puts J3 in a singleton return-comparison
scope. `connector.repeated_pin_function` stays quiet across the reviewed
boundary, while `connector.return_supply_scope_singleton` asks the reviewer to
confirm that J3's narrower scope is intentional. It does not declare the
returns common, separate, or electrically isolated.

`interfaces.json` and both connector-review maps are part of the source-bound
test input. The hosted lane verifies the exact source hashes, connector-map
coverage, KiCad net assignments, no native ERC errors, and repeatability of
netlist and ERC exports. It runs with the pinned KiCad 10.0.0 and 10.0.5
toolchains declared by `kicad_tooling/ci_hosted_kicad10_images.py`.

Reviewed input SHA-256 values:

| Input                                           | SHA-256                                                            |
| ----------------------------------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`                               | `53af59844b37ac7181a99e22a5bc14cd868ef33083361590cd627e8907e3fb83` |
| `control.kicad_sch`                             | `b0731cac3cba8b946e905a41f2f9251c459573f699d2c2990b2574c4ba7f5c45` |
| `interfaces.json`                               | `e1216ee351d3fcdddd720f2bc6f0e2068bbc9d85e777aa4914c4af8102cb8b99` |
| `connector-reviews.json`                        | `a1ec6317ef6207572c89605a5c0ef1448fe7e5a62b2ec5383edea598dda2d0bc` |
| `connector-reviews-separate-return-groups.json` | `fcbebe5c7c83a15d82daf1ae43c25f461bcd3809b4e9c02f4eaca1a0c8ae3329` |

Run the exact-native gate in its CI lane with:

```sh
KICAD_RUN_NATIVE_MIXED_INTERFACE_RETURN_FIXTURES=1 \
  python -I -m pytest tests/test_connector_mixed_interface_return_native_lane.py \
  -m 'design_lint and connector_lint and interface_lint and return_path_lint and native_kicad'
```
