# Generic I3C connector review fixtures

These tooling-owned synthetic schematics exercise
`bus.i3c_generic_connector_pair_review` through the exact KiCad 10 CLI.
They contain no external project data.

| Fixture             | SHA-256                                                            | Expected result                                                                                                                  |
| ------------------- | ------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------- |
| `fault.kicad_sch`   | `1e82e432628aa3813bfb5a3d99bb195d7e060d3db2a5eb225d4c30c3a8d26d56` | A four-contact generic connector has generic contacts on the exact I3C SDA and SCL nets; report one REVIEW prompt.               |
| `control.kicad_sch` | `1fdf183e04d63df0eca2c65ec61fa2f3b173b9bfe8fb6febe071b3fa82015a1f` | The connector names its I3C SDA and SCL contacts; do not report the generic-contact prompt. Its VCC pin has a `+3V3` assignment. |

The native lane verifies the digest-pinned KiCad 10.0.0 and 10.0.5 images,
exports each source twice, compares normalized netlists, and checks the rule
result. The images are declared in
`tests/synthetic_design_lint_project.py`.

```sh
KICAD_RUN_NATIVE_I3C_GENERIC_CONNECTOR_FIXTURES=1 \
  .venv/bin/python -I -m pytest \
  tests/test_i3c_generic_connector_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.i3c_generic_connector_pair_review")'
```
