# Synthetic two-pin ferrite regressions

These schematics are tooling-owned synthetic fixtures. They contain no
product design or customer source. Their minimal embedded symbol declarations
use the exact `Device:FerriteBead` identity and two pin numbers needed to test
source-to-netlist recognition. The drawing geometry is illustrative and is not
copied from the KiCad library or intended to represent a physical component.

| Fixture                           | Topology                                                     | Expected design-lint result                       |
| --------------------------------- | ------------------------------------------------------------ | ------------------------------------------------- |
| `same-net-ferrite.kicad_sch`      | Both fitted `Device:FerriteBead` pins share one local label. | `component.two_pin_ferrite_same_net` reports FB1. |
| `distinct-nets-ferrite.kicad_sch` | The two pins use separate input and output labels.           | No same-net ferrite finding.                      |

Source SHA-256 values:

| Fixture                           | SHA-256                                                            |
| --------------------------------- | ------------------------------------------------------------------ |
| `same-net-ferrite.kicad_sch`      | `8ede05ea1d9c8afb0cec2f1c8c9bddf527eab015ab779097f4ddc528866751f7` |
| `distinct-nets-ferrite.kicad_sch` | `199c802ca290b1281622c623f4966b159144f0e95fd99ed0e21a14a0875734a7` |

The native fixture lane exports each source twice with the exact digest-pinned
KiCad 10.0.0 and 10.0.5 toolchains selected by the public acceptance projects.
It compares normalized native netlist contracts and shared lint findings. Run
it with:

```sh
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test \
KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES=1 \
.venv/bin/python -I -m pytest -q tests/test_ci_hosted.py -k NativeTwoPinComponentFixtureTests
```

The check recognizes only fitted `Device:FerriteBead` and
`Device:FerriteBead_Small` symbols with a complete, unambiguous native two-pin
inventory. A typed control confirms the smaller stock symbol identity is
recognized, while other suffixes remain outside the bounded predicate. A
same-net assignment can be an intentional bypass, so the rule defaults to
review and does not declare the topology electrically wrong. It does not
assess ferrite impedance, filtering effectiveness, physical population, or PCB
copper connectivity.
