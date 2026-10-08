# Synthetic two-pin fuse regressions

These schematics are tooling-owned synthetic fixtures. They contain no product
design or customer source.

| Fixture                            | Topology                                                     | Expected design-lint result                   |
| ---------------------------------- | ------------------------------------------------------------ | --------------------------------------------- |
| `same-net-fuse.kicad_sch`          | Both `Device:Fuse` pins share one local label.               | `component.two_pin_fuse_same_net` reports F1. |
| `distinct-nets-fuse.kicad_sch`     | `Device:Fuse` pins use separate input and output labels.     | No same-net fuse finding.                     |
| `same-net-polyfuse.kicad_sch`      | Both `Device:Polyfuse` pins share one local label.           | `component.two_pin_fuse_same_net` reports F1. |
| `distinct-nets-polyfuse.kicad_sch` | `Device:Polyfuse` pins use separate input and output labels. | No same-net fuse finding.                     |

The synthetic fuse pins use blank names matching the generic KiCad library
symbols. The numbered contacts do not imply polarity or current direction.

Source SHA-256 values:

| Fixture                            | SHA-256                                                            |
| ---------------------------------- | ------------------------------------------------------------------ |
| `same-net-fuse.kicad_sch`          | `11c72397a8dbe96f63f859f005801903468c66fb3bf87d6c870743c5a785bf86` |
| `distinct-nets-fuse.kicad_sch`     | `2dd483a9805b2d26fa7dbf56444ef018a5550f2ac481cd1f58171df1ec03e790` |
| `same-net-polyfuse.kicad_sch`      | `9ed09b2d61650c3a91211385bab4371e5582aeb579db9301254050f549f86ac6` |
| `distinct-nets-polyfuse.kicad_sch` | `bde58f020f1958e4dd5e9f13f21a2df02b3c3bf74b6779d4e8c933767d412376` |

The native fixture lane exports each source twice with the exact digest-pinned
KiCad 10.0.0 and 10.0.5 toolchains selected by the public acceptance projects.
It compares normalized native netlist contracts and the shared lint findings.
Run it with:

```sh
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test \
KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES=1 \
.venv/bin/python -I -m pytest -q tests/test_ci_hosted.py -k NativeTwoPinComponentFixtureTests
```

The check recognizes only exact `Device:Fuse` and `Device:Polyfuse` symbol
families with a complete, unambiguous, fitted two-pin inventory. A same-net
assignment can be an intentional bypass, so the rule defaults to review and
does not declare the topology electrically wrong.
