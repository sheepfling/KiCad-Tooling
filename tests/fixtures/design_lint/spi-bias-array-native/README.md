# Synthetic SPI chip-select resistor-array fixtures

These tooling-owned schematics exercise an exact project-authored SPI bias-array
map through native KiCad netlist export. The SPI peripheral's active-low
`CS_N` input is connected to controller U1.1. RN1.1 is mapped from that select
net to the recognized `+3V3` rail on RN1.2; pins RN1.3 and RN1.4 have reviewed
unused-channel reasons.

| Fixture             | Array channel                            | Contract check | Heuristic result    |
| ------------------- | ---------------------------------------- | -------------- | ------------------- |
| `control.kicad_sch` | RN1.1 on `SPI_CS_N`, RN1.2 on `+3V3`     | PASS           | no pull-up prompt   |
| `fault.kicad_sch`   | RN1.1 on `SPI_CS_WRONG`, RN1.2 on `+3V3` | FAIL           | prompt remains open |
| `no-connect.kicad_sch` | U2.1 explicitly open; controller bias remains mapped | endpoint FAIL, array PASS | no pull-up prompt |

`spi.json` binds the controller, peripheral, and array using synthetic symbol,
footprint, value, `PART_ID`, and channel metadata. The nominal 10 kΩ channel
value is a reviewed authoring assumption; the native netlist cannot verify the
array's internal construction or measured resistance.

## Source binding

| Input               | SHA-256                                                              |
| ------------------- | -------------------------------------------------------------------- |
| `control.kicad_sch` | `ffe5cb313f55aa3f0105392a66ca5eb24c021e448e22daed75ec9c6cc8474203`   |
| `fault.kicad_sch`   | `930e3ea9fd621140ff739c1ff13cd64182c325c5bf8fefe4db7a4e2d231d2e18`   |
| `no-connect.kicad_sch` | `2182e63210555eb3e9eb9d2afdf07164e71988e1c40e54d2712277e071413474` |
| `spi.json`          | `ecadc621e352e50f891f081447b38b993014592e35b52ff1cde653a6251599cb`   |
| KiCad images        | Digest-pinned KiCad 10.0.0 and 10.0.5 from `ci_hosted_spi_native.py` |

The package-acceptance lane exports each schematic twice using the exact
versioned KiCad image, normalizes both native netlists, checks repeatability,
compares the mapped-array electrical result, and verifies the SPI lint finding.
For the explicit no-connect case it also requires native `U2.1` unconnected-pin
evidence and confirms that the missing-bias prompt stays quiet; the separate
SPI endpoint contract correctly remains a failure because its mapped peripheral
pin is open, while the separate resistor-array channel check passes because its
own two mapped pins remain connected. This lane does not run ERC/DRC or establish
electrical approval or PCB continuity.
