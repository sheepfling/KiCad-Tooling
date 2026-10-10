# Synthetic channel-prefixed power-name fixtures

These tooling-owned schematics exercise the bounded `P<number>_`,
`CH<number>_`, and `RAIL<number>_` naming forms recognized by
`net.numbered_power_rails`. They contain no product or customer design data.

The fixtures were derived from the tooling-owned
[`cohort-connector-ground-domains/control.kicad_sch`](../cohort-connector-ground-domains/control.kicad_sch)
source. The embedded connector pin 3 function was changed from `DATA1` to
`VDD`; its labels are the only other changes:

- `fault.kicad_sch`: J1.3 is `CH2_VDD`, and J2.3 is `CH3_VDD`.
- `control.kicad_sch`: J1.3 and J2.3 both use `CH2_VDD`.

The fault must produce a review candidate with exact evidence for both pins.
The common-net control must produce no numbered-power-rail finding. Neither
case says that similarly named rails must be joined.

## Source hashes

| Source              | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `d6a52dd120801e0bf5776e82421ceb64670b26a9ace28afafd89b608a61aabb3` |
| `control.kicad_sch` | `37c7c28963b530a679cd3dc2087a4fa3b5d97dda52250332556406c66b9e1fc7` |

## Exact native export lane

`tests.test_ci_hosted_connector_returns.NativeConnectorReturnFixtureTests` exports these
schematics twice through the digest-pinned KiCad 10.0.0 and 10.0.5 images.
It checks source hashes, normalized typed netlist repeatability, exact
`J1.3`/`J2.3` evidence, the fault finding, and the common-net control. Receipts
stay under ignored `build/ci/` directories.

Run the lane from the tooling checkout with a separate public KiCad template
checkout configured:

```sh
KICAD_TEMPLATE_ROOT=/absolute/path/to/KiCad-Test \
KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1 \
  .venv/bin/python -I -m pytest -q tests/test_ci_hosted_connector_returns.py \
  -m 'design_lint and connector_lint and power_lint and native_kicad'
```
