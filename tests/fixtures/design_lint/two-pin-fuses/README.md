# Synthetic two-pin fuse regressions

These schematics are tooling-owned synthetic fixtures. They contain no product
design or customer source.

| Fixture                            | Topology                                                     | Expected design-lint result                   |
| ---------------------------------- | ------------------------------------------------------------ | --------------------------------------------- |
| `same-net-fuse.kicad_sch`          | Both `Device:Fuse` pins share one local label.               | `component.two_pin_fuse_same_net` reports F1. |
| `distinct-nets-fuse.kicad_sch`     | `Device:Fuse` pins use separate input and output labels.     | No same-net fuse finding.                     |
| `same-net-polyfuse.kicad_sch`      | Both `Device:Polyfuse` pins share one local label.           | `component.two_pin_fuse_same_net` reports F1. |
| `distinct-nets-polyfuse.kicad_sch` | `Device:Polyfuse` pins use separate input and output labels. | No same-net fuse finding.                     |

Source SHA-256 values:

| Fixture                            | SHA-256                                                            |
| ---------------------------------- | ------------------------------------------------------------------ |
| `same-net-fuse.kicad_sch`          | `b24e66eea8f73d9796223509a4c640ee5fe9c51546e78160df5939681eb3e146` |
| `distinct-nets-fuse.kicad_sch`     | `239758b4394ab8107e3d6d72ebcac426b61e219ff238c8429ea593a4ccb16fb7` |
| `same-net-polyfuse.kicad_sch`      | `3ed2ea8ee4ccbc9706525ad238a03c500d508e8fe5a65953a2682ac69409b30a` |
| `distinct-nets-polyfuse.kicad_sch` | `29344dc47d3642083af2e21473d59ee31f74dab753a45005317710ac2b01f0ed` |

The native fixture lane exports each source twice with the exact digest-pinned
KiCad 10.0.0 and 10.0.5 toolchains selected by the public acceptance projects.
It compares normalized native netlist contracts and the shared lint findings.
Run it with:

```sh
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test \
KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES=1 \
.venv/bin/python -I -m unittest tests.test_ci_hosted.NativeTwoPinComponentFixtureTests
```

The check recognizes only exact `Device:Fuse` and `Device:Polyfuse` symbol
families with a complete, unambiguous, fitted two-pin inventory. A same-net
assignment can be an intentional bypass, so the rule defaults to review and
does not declare the topology electrically wrong.
