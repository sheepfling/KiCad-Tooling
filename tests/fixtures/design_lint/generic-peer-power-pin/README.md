# Synthetic generic peer power-pin assignment

This pair models three similar connector symbols with a generic pin 1 and a
shared GND pin 2. The fault assigns pin 1 on J1 and J2 to separately numbered
positive rails, while J3 pin 1 has no net assignment. The control assigns all
three pin 1 contacts to `+5V`.

| Fixture             | Pin 1 assignments                          | Expected lint result         |
| ------------------- | ------------------------------------------ | ---------------------------- |
| `fault.kicad_sch`   | J1.1=`+5V_1`, J2.1=`5V-2`, J3.1 unassigned | `REVIEW` with J3.1 localized |
| `control.kicad_sch` | J1.1, J2.1, and J3.1 all use `+5V`         | `PASS`                       |

The review prompt identifies peer drift and an open generic contact. It does
not assert that every similar connector pin must share one rail; independent
supplies and intentionally unused contacts need project review and may be
recorded with project-scoped policy. All contents are synthetic and contain no
proprietary project material.
