# Repeated signal-function open-pin native fault and control

`fault.kicad_sch` is a tooling-owned synthetic IC with two native input pins
named `READY`. Pin 1 is assigned to `SIGNAL_A`; pin 2 has an explicit
no-connect marker. Pin 3 provides a separate `STATUS` control, and pin 4 is a
generic passive pin. `control.kicad_sch` connects both `READY` pins to the same
net. These files test recognition of pin functions, electrical types, and
unassigned native pins; they do not assert that repeated pins must be tied.

The exact-version fixture lane exports both schematics twice with digest-pinned
KiCad 10.0.0 and 10.0.5 images and checks repeatable normalized netlists and
lint results. Native unconnected-pin evidence does not establish why a pin is
open or whether it should be connected.

Source SHA-256:

- `fault.kicad_sch`: `dce2628e41a0964ddfd5befab4afb4fab43da4ff5ef3a1247e1cbdc5e38841ae`
- `control.kicad_sch`: `f0a448cd74e6a5f0581dc9452f3e3b675e2c48537d000c931fd8197db0980089`

These fixtures contain no project or customer design source.
