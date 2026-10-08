# Multiport USB peer-reference fixtures

These tooling-owned synthetic schematics exercise numbered USB hub channels
through `bus.usb_peer_reference_review`. Both connectors use ordinary D+/D−
functions; one fitted U1 exposes `USB1D+`/`USB1D-` and `USB2D+`/`USB2D-` pin
functions. The fault gives the two connectors and the hub separate explicit
return nets. The control puts all three endpoints on one net. The check asks
for review when they differ; it does not declare that their references must be
common.

| Fixture             | Return assignments                               | Expected review                             |
| ------------------- | ------------------------------------------------ | ------------------------------------------- |
| `fault.kicad_sch`   | J1.4=`USB1_GND`, J2.4=`USB2_GND`, U1.3=`PHY_GND` | Two findings: J1/U1 port 1 and J2/U1 port 2 |
| `control.kicad_sch` | J1.4, J2.4, and U1.3=`BOARD_GND`                 | No USB peer-reference findings              |

The native source hashes are:

| Fixture             | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `9cbc4ebc8692b02fc9ef8b6a1723d926536b2b7a74251ff4d37e045cdacae615` |
| `control.kicad_sch` | `80f5af92083dbc5a3fce319dabb5c80efb535899e482ff6ad952a41f576df0d0` |

The local KiCad 10.0.6 export attached J1.1/J1.2 to U1.1/U1.2 and J2.1/J2.2
to U1.4/U1.5. It emitted both expected port findings on the fault and none on
the control. Repeated exports produced normalized typed-netlist hashes
`62381ebb9c73b28762e759b7ad4c8d4ccee102ace693d3917a1d8b1874e428c4` (fault)
and `b5562947696ab4d4163687ee3e091ec608cc883c7892f035a2979bdd1eb74ea0`
(control). Raw netlist hashes also repeated identically for each fixture. This
is KiCad 10.0.6 compatibility evidence; the repository's exact digest-pinned
KiCad 10.0.0/10.0.5 lane remains the acceptance gate. No board or project source
is used.
