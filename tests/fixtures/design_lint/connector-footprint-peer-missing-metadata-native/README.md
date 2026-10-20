# Synthetic connector peer missing-metadata fixtures

These tooling-owned schematics exercise a review heuristic for fitted
connector aliases whose target pin has missing or unnamed native function
metadata. Both instances use distinct symbols with the same value, footprint,
and complete two-pin inventory. Pin 2 is a common-net anchor.

| Fixture             | Pin 1 function metadata    | Pin 1 assignments             | Pin 2 anchor       | Expected result |
| ------------------- | -------------------------- | ----------------------------- | ------------------ | --------------- |
| `fault.kicad_sch`   | J1 is `UART_RX`; J2 is `~` | `UART_RX_NET` / `UART_TX_NET` | `COMMON_REFERENCE` | `REVIEW`        |
| `control.kicad_sch` | J1 is `UART_RX`; J2 is `~` | both use `SHARED_PORT`        | `COMMON_REFERENCE` | No finding      |

The split may be intentional. The prompt asks a reviewer to inspect exact
symbol pinouts and project requirements; it does not infer a shared role or
instruct that the nets should be joined. The cases are not derived from a
product board and are not for manufacture.

SHA-256 source digests:

- `fault.kicad_sch`: `7265e062e47c5b1d06a30f40c94cfd23d14cc5f07ff51799ef0afefb21ab2c21`
- `control.kicad_sch`: `407e25454fabe943a4f2b9ad5fd58c8d8af48b836cef20258b32d216902db923`

The digest-pinned lane passed locally on 2026-10-20 for KiCad 10.0.0 and
10.0.5. Each version exported the base and PART_ID fault/control schematics
twice; typed netlists repeated, both faults produced the default `REVIEW`, and
both controls stayed quiet. The run selected two version-parameterized tests
and reported `2 passed`. Hosted package acceptance remains pending.

Reproduce the exact-version cases with the pinned images from
`tests/synthetic_design_lint_project.py`:

    KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1 \
      .venv/bin/python -I -B -m pytest -q \
      tests/test_connector_footprint_peer_missing_metadata_native_fixture_lane.py \
      -m 'design_lint and native_kicad and design_lint_rule(rule_id="connector.footprint_peer_pin_missing_metadata_assignment_divergence")'

Generated receipts and reports stay under ignored `build/` directories.
