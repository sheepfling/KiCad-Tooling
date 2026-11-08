# Synthetic generic connector USB-C CC review

These schematics are tooling-owned regression fixtures, not product designs.
The connector symbol has generic `Pin_1` and `Pin_2` functions, and the custom
controller symbol exports native `CC1` and `CC2` functions on distinct direct
nets.

- `fault.kicad_sch` assigns one generic connector contact to each controller CC
  net and should request a REVIEW.
- `control.kicad_sch` keeps only the first connector contact on a controller CC
  net; the second is assigned to an unrelated net and should stay quiet.

The fault fixture leaves connector J1.4, whose native function is GND,
unassigned. Its finding reports that open contact for review without deciding
whether the connector's ground contact must be connected.

The native lane exports each source twice with digest-pinned KiCad 10.0.0 and
10.0.5 containers. The source hashes are registered in
`kicad_tooling/ci_hosted_usb_c_generic_connector_cases.py`. No external board,
commercial pinout, or product requirement is represented here.
