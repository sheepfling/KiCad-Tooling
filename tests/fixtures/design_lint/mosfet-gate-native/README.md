# MOSFET gate peer native fixtures

These tooling-owned KiCad schematics test one narrow REVIEW heuristic. The
fault has an open gate pin; the control connects the same supported native
three-terminal MOSFET symbol to a synthetic output pin. A passive peer is also
covered by the source-independent synthetic tests.

| Fixture             | Source SHA-256                                                     |
| ------------------- | ------------------------------------------------------------------ |
| `control.kicad_sch` | `e95ed1a5673723dc690e1fad27d534f3f834c371a489957c0c7050f642d18a75` |
| `fault.kicad_sch`   | `5cd4983eb3ac3abc6370f8d5626fae3fbe8b1e38ce26b32d31e0cb3c7d9a8c6c` |

Run the exact-version native lane with the package acceptance switch:

```sh
KICAD_RUN_NATIVE_COMPONENT_RATING_FIXTURES=1 \
  python -I -m pytest tests/test_mosfet_gate_native_fixture.py \
  -m 'design_lint and component_lint and native_kicad and design_lint_rule(rule_id="component.mosfet_gate_without_peer")'
```

The lane exports netlists and ERC reports twice using the project-selected,
digest-pinned KiCad 10.0.0 and 10.0.5 images. It requires stable normalized
exports, no native ERC errors, one lint finding on the fault, and none on the
control. ERC warnings about the deliberately minimal synthetic symbol and
schematic geometry are retained in the normalized evidence and are not
treated as electrical approval.

Both fixtures were authored for this repository. They contain no project
design, copied cohort implementation, or customer pinout. A finding does not
establish that the MOSFET requires a local driver or bias, or that a same-net
peer can safely control it.
