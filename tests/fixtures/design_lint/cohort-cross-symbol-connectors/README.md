# Mixed-symbol connector return and supply hints

These five tooling-owned schematics exercise connector role comparison after
KiCad exports distinct library symbols into a native netlist.

| Fixture                          | USB-style and serial-style return pins | Same-function supply pins | Shield pin             | Expected lint result                                       |
| -------------------------------- | -------------------------------------- | ------------------------- | ---------------------- | ---------------------------------------------------------- |
| `cross-symbol-fault.kicad_sch`   | Separate named nets                    | Separate named nets       | Separate `CHASSIS` net | `REVIEW` for return and supply groups                      |
| `cross-symbol-open.kicad_sch`    | Serial return contact is unassigned    | Shared named net          | Separate `CHASSIS` net | `REVIEW` for the return group, with the open pin localized |
| `cross-symbol-control.kicad_sch` | Shared named net                       | Shared named net          | Separate `CHASSIS` net | `PASS`; the shield remains distinct                        |
| `cross-symbol-compound-fault.kicad_sch` | Separate named nets; functions `USB_GND` and `SERIAL_RETURN` | Separate named nets | Separate `CHASSIS` net | `REVIEW` for return and supply groups |
| `cross-symbol-compound-control.kicad_sch` | Shared named net; functions `USB_GND` and `SERIAL_RETURN` | Shared named net | Separate `CHASSIS` net | `PASS`; compound shield roles stay distinct |

The symbols are deliberately different (`Synthetic:UsbPort`,
`Synthetic:SerialPort`, and `Synthetic:ShieldPort`). The USB-style return is
pin 4 `GND`; the serial-style return is pin 7 `RTN`. The compound pair uses
pin functions `USB_GND` and `SERIAL_RETURN` to model exported symbols that
encode return roles inside a function name. Both supply pins are
explicitly named `PWR`. Separate `SHIELD` and compound `USB_SHIELD_GND`
functions must not be grouped as signal returns. This tests only function
normalization and native netlist evidence; it does not require USB, serial, or
shield returns to share a net.

The exact-version native lane exports each source twice on KiCad 10.0.0 and
10.0.5. It compares normalized netlist contracts, verifies the expected
finding identities and pin evidence, and records source and raw-export hashes.
All files are synthetic and contain no customer or proprietary project data.

Reviewed source SHA-256 values:

| Fixture                          | SHA-256                                                            |
| -------------------------------- | ------------------------------------------------------------------ |
| `cross-symbol-fault.kicad_sch`   | `941aa1acc62384d86fe04e7dec77638a5e23cd8b67b196bc1d93130e5e99f21e` |
| `cross-symbol-control.kicad_sch` | `5b9f1a9d18b4e57495d090e815ff192c44f61b8a164ef03622e3d962ac553baf` |
| `cross-symbol-open.kicad_sch`    | `180c28fd280b71febe0c636e799217f0d86a3659c45e280cb86a768b7a03533a` |
| `cross-symbol-compound-fault.kicad_sch` | `c56899dd89bcbb863b319d4754ef7f98e476b4f77b7c614b6aa305eb8c2a0145` |
| `cross-symbol-compound-control.kicad_sch` | `fb746aa2191f080416e8a81f321393a028507e1f1c4756fb757abd7632ff91fb` |
