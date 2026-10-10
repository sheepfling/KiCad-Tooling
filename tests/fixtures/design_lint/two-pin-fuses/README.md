# Synthetic two-pin fuse regressions

These schematics are tooling-owned synthetic fixtures. They contain no product
design or customer source.

| Fixture                            | Topology                                                     | Expected design-lint result                   |
| ---------------------------------- | ------------------------------------------------------------ | --------------------------------------------- |
| `same-net-fuse.kicad_sch`          | Both `Device:Fuse` pins share one local label.               | `component.two_pin_fuse_same_net` reports F1. |
| `distinct-nets-fuse.kicad_sch`     | `Device:Fuse` pins use separate input and output labels.     | No same-net fuse finding.                     |
| `same-net-polyfuse.kicad_sch`      | Both `Device:Polyfuse` pins share one local label.           | `component.two_pin_fuse_same_net` reports F1. |
| `distinct-nets-polyfuse.kicad_sch` | `Device:Polyfuse` pins use separate input and output labels. | No same-net fuse finding.                     |

The embedded Fuse and Polyfuse symbol metadata and geometry are adapted from
the [KiCad Symbols 10.0.5 library](https://gitlab.com/kicad/libraries/kicad-symbols/-/tree/10.0.5),
commit `60d2dc9981920ee40eb5caa4dc01b23f713beca7`, under the library's
[CC BY-SA 4.0 license and exception](https://gitlab.com/kicad/libraries/kicad-symbols/-/blob/10.0.5/LICENSE.md).
Fixture references, values, UUIDs, wires, labels, and contracts are synthetic.
The pins are unnamed; contacts 1 and 2 do not imply polarity or current
direction.

Source SHA-256 values:

| Fixture                            | SHA-256                                                            |
| ---------------------------------- | ------------------------------------------------------------------ |
| `same-net-fuse.kicad_sch`          | `b69792902442ef89c103f5a4b783b73633b88d9519ab01c5b77df9b654df62ca` |
| `distinct-nets-fuse.kicad_sch`     | `c9c6afa14db03137c1bbc78b82875d159f79b5ebabbb7ea21c6eac1e33fc6edb` |
| `same-net-polyfuse.kicad_sch`      | `1537a762c427dbc77e3afb35fd2faecb494e69674b8ca3f7e04e7497fd96e3ad` |
| `distinct-nets-polyfuse.kicad_sch` | `f4d7ba7f0d27d295c725f2286dace93fa4163b3dbb04130d0c913f05660fc037` |

The native fixture lane exports each source twice with the exact digest-pinned
KiCad 10.0.0 and 10.0.5 toolchains selected by the public acceptance projects.
It compares normalized native netlist contracts and the shared lint findings.
Run it with:

```sh
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test \
KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES=1 \
.venv/bin/python -I -m pytest -q tests/test_two_pin_component_native_fixture_lane.py -m 'design_lint and component_lint and native_kicad'
```

The check recognizes only exact `Device:Fuse` and `Device:Polyfuse` symbol
families with a complete, unambiguous, fitted two-pin inventory. A same-net
assignment can be an intentional bypass, so the rule defaults to review and
does not declare the topology electrically wrong.
