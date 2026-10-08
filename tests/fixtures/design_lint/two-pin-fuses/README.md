# Synthetic two-pin fuse regressions

These schematics are tooling-owned synthetic fixtures. They contain no product
design or customer source.

| Fixture                            | Topology                                                     | Expected design-lint result                   |
| ---------------------------------- | ------------------------------------------------------------ | --------------------------------------------- |
| `same-net-fuse.kicad_sch`          | Both `Device:Fuse` pins share one local label.               | `component.two_pin_fuse_same_net` reports F1. |
| `distinct-nets-fuse.kicad_sch`     | `Device:Fuse` pins use separate input and output labels.     | No same-net fuse finding.                     |
| `same-net-polyfuse.kicad_sch`      | Both `Device:Polyfuse` pins share one local label.           | `component.two_pin_fuse_same_net` reports F1. |
| `distinct-nets-polyfuse.kicad_sch` | `Device:Polyfuse` pins use separate input and output labels. | No same-net fuse finding.                     |

The embedded symbols use the generic KiCad fuse metadata and neutral `~` pin
names. The numbered contacts do not imply polarity or current direction.

Source SHA-256 values:

| Fixture                            | SHA-256                                                            |
| ---------------------------------- | ------------------------------------------------------------------ |
| `same-net-fuse.kicad_sch`          | `97be0fedbe366d9fc04dea730f46552ed9c5c594cb914122205dd5ab58d660a2` |
| `distinct-nets-fuse.kicad_sch`     | `dece283ca01dbd04c034f4b959b9fae8a8423f4e9769592087daebf926e3745e` |
| `same-net-polyfuse.kicad_sch`      | `d35437ae768aafafeadccb7db37ef71b323ea4550a95c8c0ba559fe81a88f67a` |
| `distinct-nets-polyfuse.kicad_sch` | `564dff3e5a0c9e443693d4baa531a334e205f4d7e9a4aae40aaefb603a0caeec` |

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
