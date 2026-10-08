# Synthetic SPI peer-voltage native fixtures

These two schematics contain only synthetic components and are marked not for
manufacture. U1 has one SPI clock output and one power input; U2 has the
matching SPI clock input and one power input. The full native pin inventory is
deliberately small so the test can prove the source fields used by
`bus.spi_peer_voltage_review`.

| Fixture                             | U1 supply | U2 supply | Expected lint result     |
| ----------------------------------- | --------- | --------- | ------------------------ |
| `peer-control.kicad_sch`            | `+3V3`    | `+3V3`    | No peer-voltage finding  |
| `peer-fault.kicad_sch`              | `+5V`     | `+3V3`    | One default `REVIEW`     |
| `peer-translator-control.kicad_sch` | `+5V`     | `+3V3`    | No direct-peer finding   |

SHA-256 source digests:

- `peer-control.kicad_sch`: `427bfd18783c800ddc0b9e48d4ce95db8d26ac4fb27bf2a36921908016d75cdd`
- `peer-fault.kicad_sch`: `98ca9f8d999892b9441019064f36eba776eec18770e23519cde30ff1a532e5a4`
- `peer-translator-control.kicad_sch`:
  `58f2ac474e5c055fc5ff3f5e2f9be0613fc7339298244de035740ca85eaa80a1`

The native lane exports each source twice with the digest-pinned KiCad 10.0.0
and 10.0.5 images selected by the public template checkout. It requires the
typed native netlist to retain signal directions, power-input pin types,
complete component-pin inventories, and exact rail and signal assignments. The
same source-bound report service must stay quiet for the same-rail and
translator controls and emit one review finding for the direct cross-rail
candidate. The translator control places U1 and U2 on separate SPI nets through
U3's A and B pins; U3 is powered from both rails and shares ground. The new
source was exported and parsed locally with KiCad 10.0.6. The exact-version
lane passed locally on 2026-10-07 with digest-pinned KiCad 10.0.0 and 10.0.5.
Each version repeated identical normalized exports; both versions produced the
same typed-netlist SHA-256,
`a289c5c15f048b1d8e1cf58f18501b850c3e1b7e3be451a9d9ba275cbd057e28`.
Raw exports and receipts remain under ignored `build/` paths.

The lane passed on 2026-10-01 with the pinned KiCad 10.0.0 and 10.0.5 images.
The same-rail native contract normalized to SHA-256
`3a9cbabeeeec8a5b807224c586135de66d801114b30171a2aaa9fba36d40e853` on both
versions. The cross-rail candidate normalized to
`05ca53b0ec60201206608ff8bf99b0d67aeb058f574d07bc60967ddb7ad61003` on both.

Rail labels are test clues only. This fixture does not establish actual
voltage, device limits, an electrical incompatibility, or a requirement to
connect rails. It contains no proprietary design or project data.
