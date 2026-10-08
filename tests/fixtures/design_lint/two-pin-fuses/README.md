# Synthetic two-pin fuse regressions

These schematics are tooling-owned synthetic fixtures. They contain no product
design or customer source.

| Fixture                            | Topology                                                     | Expected design-lint result                   |
| ---------------------------------- | ------------------------------------------------------------ | --------------------------------------------- |
| `same-net-fuse.kicad_sch`          | Both `Device:Fuse` pins share one local label.               | `component.two_pin_fuse_same_net` reports F1. |
| `distinct-nets-fuse.kicad_sch`     | `Device:Fuse` pins use separate input and output labels.     | No same-net fuse finding.                     |
| `same-net-polyfuse.kicad_sch`      | Both `Device:Polyfuse` pins share one local label.           | `component.two_pin_fuse_same_net` reports F1. |
| `distinct-nets-polyfuse.kicad_sch` | `Device:Polyfuse` pins use separate input and output labels. | No same-net fuse finding.                     |

The synthetic pins use generic `Pin_1` and `Pin_2` function names. They do not
imply polarity or current direction.

Source SHA-256 values:

| Fixture                            | SHA-256                                                            |
| ---------------------------------- | ------------------------------------------------------------------ |
| `same-net-fuse.kicad_sch`          | `0aef6e17919aabf2b640183e91d992df28a7cb8db92ea76514afddd31c2f0f93` |
| `distinct-nets-fuse.kicad_sch`     | `34e303f1ff54b324555cba0b7fa015881edebf3a91b32391fc010d0f5f92cc89` |
| `same-net-polyfuse.kicad_sch`      | `3f024223a079ab029edcb6dc9314a6beb82eb75fa5d31ca2140425ae210ad6a7` |
| `distinct-nets-polyfuse.kicad_sch` | `e243a29359c911e2d04787a8d71dc2566c1c09e287251c94bae22ac9a7cfe4e7` |

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
