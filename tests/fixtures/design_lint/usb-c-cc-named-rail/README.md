# USB-C CC named-rail fixtures

These synthetic KiCad schematics exercise the default-review prompt for fitted
IC pins whose native functions are `CC1` and `CC2`. They are derived only from
the tooling repository's synthetic USB signal fixtures; they contain no
project board data.

| Case | Expected assignments | Expected rule result | SHA-256 |
| --- | --- | --- | --- |
| `fault.kicad_sch` | `J1.1`/`U1.1` on `GND`; `J1.2`/`U1.2` on `+3V3` | Review each fitted controller CC pin | `9f484af298d4a8bbd9e779e7bf2659098f3b05473343411dd5698c4204fa90b2` |
| `control.kicad_sch` | CC pins on neutral `CC1_BUS` and `CC2_BUS` nets | No CC named-rail finding | `e49f410117e4ef7a2d3bead575c68cc184c05efe9c42a3f6bea29c7bab467b5a` |

The function and net-label patterns are review clues. These fixtures do not
establish USB-C source/sink role, Rp/Rd behavior, electrical potential, signal
path through passive components, PCB copper, or physical continuity. Native
KiCad exports must preserve the exact source hashes, pin functions, and net
assignments and repeat identically on KiCad 10.0.0 and 10.0.5.
