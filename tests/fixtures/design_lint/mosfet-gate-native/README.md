# MOSFET gate native fixtures

These tooling-owned KiCad schematics test three bounded review heuristics. The
open-gate fault and gate-peer control exercise LINT-170. The gate-peer
control is also the no-visible-bias fault for opt-in LINT-171; the
`source-bias-control` adds a fitted 100 kΩ resistor directly across the same
MOSFET's gate and source nets. The gate-peer and source-bias schematics are
direct-output faults for opt-in LINT-177; `series-gate-control` separates the
driver and MOSFET gate with a fitted 22 Ω resistor. A review finding asks for
human review and does not establish whether a resistor or bias is required or
adequate.

| Fixture                                | Source SHA-256                                                     |
| -------------------------------------- | ------------------------------------------------------------------ |
| `control.kicad_sch`                    | `e95ed1a5673723dc690e1fad27d534f3f834c371a489957c0c7050f642d18a75` |
| `fault.kicad_sch`                      | `5cd4983eb3ac3abc6370f8d5626fae3fbe8b1e38ce26b32d31e0cb3c7d9a8c6c` |
| `source-bias-control.kicad_sch`        | `d7529a3ce8d7815669fa764cd1c0a868ea37dd94aae072fe66e05a3e34c48e78` |
| `series-gate-control.kicad_sch`        | `5f6a6b62155601ef51c1d9d3dad30dd2e5b8d02f22fa210f332fdf9566322323` |

Run the exact-version native lane with the package acceptance switch:

```sh
KICAD_RUN_NATIVE_COMPONENT_RATING_FIXTURES=1 \
  python -I -m pytest tests/test_mosfet_gate_native_fixture.py \
  -m 'design_lint and component_lint and native_kicad and design_lint_rule'
```

The lane exports netlists and ERC reports twice using the project-selected,
digest-pinned KiCad 10.0.0 and 10.0.5 images. It requires stable normalized
exports, no native ERC errors, the LINT-170 finding only on the open-gate
fault, the opt-in LINT-171 finding on the gate-peer case without source bias,
and the opt-in LINT-177 finding on both direct-output cases. The series-gate
control is quiet for LINT-177. ERC warnings about the
deliberately minimal synthetic symbol and schematic geometry are retained in
the normalized evidence and are not treated as electrical approval.

All four fixtures were authored for this repository. They contain no project
design, copied cohort implementation, or customer pinout. A gate peer does not
establish that the MOSFET is driven or safe; a visible resistor does not
establish that the resistance is adequate.
