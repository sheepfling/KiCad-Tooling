# Synthetic SPI combo-interface participant fixture

This tooling-owned KiCad schematic models one combo-interface IC with exported
pin functions `SCL/SPC`, `SDA/SDI/SDO`, `SDO/SA0`, and `CS`. ST's LSM6DSOX
datasheet documents these dual-interface names and meanings; this fixture uses
only synthetic component identity, values, nets, and topology. No product board
or project source is included.

Source SHA-256:

`78fb20b4e2770c1e68b16727ebd4f1014bd76c4d4d512647b38960d41f02f7ff`

| Case                   | SPI roster          | Expected lint result                                       |
| ---------------------- | ------------------- | ---------------------------------------------------------- |
| `composite-unrostered` | No roster           | `REVIEW` for U1 with clock, data, and chip-select evidence |
| `composite-rostered`   | Exact U1 device map | `PASS`; no SPI roster candidate                            |

The regression also checks that plain `SCL` and `SDA` functions do not by
themselves make a device an SPI candidate. The slash-separated aliases are
split into exact tokens; this does not infer active interface mode, protocol
configuration, or device membership.

The [ST LSM6DSOX datasheet](https://www.st.com/resource/en/datasheet/lsm6dsox.pdf)
is the public source for the pin-function aliases. The fixture and rule do not
store vendor libraries, board data, or runtime dependencies.
