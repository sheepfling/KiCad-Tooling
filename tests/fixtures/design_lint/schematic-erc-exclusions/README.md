# Schematic ERC exclusion settings

These `.kicad_pro` files are synthetic settings fixtures. `fault.kicad_pro`
contains two KiCad 10 schema-0 serialized marker records; `control.kicad_pro`
has an empty exclusion list.

The native fixture pairs `fault.kicad_pro` with the tooling-owned
`usb-superspeed-peer-reference-native/control.kicad_sch`. The marker UUIDs and
coordinates identify two intentionally excluded ERC findings in that
schematic. KiCad 10.0.0 and 10.0.5 must reload both exclusions and report them
as excluded. The schematic is kept in its existing fixture directory to avoid
duplicating a substantial native source file.
