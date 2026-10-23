# Polarized capacitor polarity fixture

These tooling-owned schematic fixtures verify that KiCad's native XML netlist
preserves the supported polarized symbol identity and the pin-to-rail
assignments consumed by the review heuristic.

- `fault.kicad_sch`: pin 1 is assigned to `-5V`; pin 2 is assigned to `+5V`.
- `control.kicad_sch`: pin 1 is assigned to `+5V`; pin 2 is assigned to `GND`.

Both sources are minimal synthetic examples marked not for manufacture. They
contain no project or cohort design data. The component symbol identity and
pin numbers follow the KiCad `Device:C_Polarized` symbol mapping; pin 1 is the
positive terminal. The exact KiCad source is maintained by the official
[KiCad 10.0.0 symbol library](https://gitlab.com/kicad/libraries/kicad-symbols/-/raw/10.0.0/Device.kicad_symdir/C_Polarized.kicad_sym).

The native fixture suite records the source hashes and exports netlist and ERC
twice against the selected digest-pinned KiCad 10.0.0 and 10.0.5 toolchains.
