# Synthetic UART peer and reference-domain native fixtures

These tooling-owned schematics use synthetic U1/U2 symbols. Each endpoint has
an exported UART TX/RX function, a supply pin, and an explicit GND pin. The
reference-only fault keeps the supply rails and every other connection equal
to the control, changing only the reference-net names.

| Fixture                            | Supply assignments | Reference assignments | Expected lint result               |
| ---------------------------------- | ------------------ | --------------------- | ---------------------------------- |
| `serial-control.kicad_sch`         | `+3V3` / `+3V3`    | shared `GND`          | quiet control                      |
| `serial-fault.kicad_sch`           | `+5V` / `+3V3`     | shared `GND`          | `bus.serial_peer_voltage_review`   |
| `serial-reference-fault.kicad_sch` | `+3V3` / `+3V3`    | `GND_A` / `GND_B`     | `bus.serial_peer_reference_review` |

The reference-only fault demonstrates a separate-ground review finding while
the voltage-domain heuristic stays quiet. It does not say that the grounds
must be joined; intentional isolation or an explicit bond remains an
engineering decision.

## Source digests

- `serial-control.kicad_sch`: `3c420e5cde0e0c6ee52cb5b5f63fb243237dcb846e7ac6057e61f4b30df7ff79`
- `serial-fault.kicad_sch`: `14f7c4097f270ed806c471df7d49f4f0dd18607de6402312920e16840f5afdd3`
- `serial-reference-fault.kicad_sch`:
  `d3c9a6e14e9bc4314c2b616e8be3962638161b1e056789ea7b66977e430081be`

The native acceptance lane exports each fixture twice with the digest-pinned
KiCad 10.0.0 and 10.0.5 images selected by the public template checkout. Both
versions preserve the exact native TX/RX and GND pin functions, pin types,
complete component-pin inventories, supply assignments, and reference
assignments. All repeated typed-netlist hashes match, and normalized evidence
is identical across the two KiCad versions:

| Fixture                                      | Normalized native netlist SHA-256                                  |
| -------------------------------------------- | ------------------------------------------------------------------ |
| Shared-reference control                     | `ab26230622e20694fa31df7921381d1c0b629a2f4b5b99a24aa05e7ffa99aac8` |
| Voltage-domain fault with common reference   | `c5781c55ed8d12e5fa71b6d4302e9de5893d29014ad392c9e8a6b942368ea11c` |
| Separate-reference fault with matching rails | `c92f4dffc776643127fb64b419f0d117acc97c6ec800549b51e990c407b5da60` |

The shared-reference control has no UART voltage or reference-domain finding.
The voltage fault produces only the voltage-domain finding. The
reference-only fault produces only the separate-reference finding. These
results demonstrate deterministic native-netlist detection for these bounded
synthetic cases; they do not establish field effectiveness, the intended
electrical relationship, PCB copper continuity, external bonding, connector
wiring, or hardware suitability.

Raw native exports and command receipts remain under ignored `build/` paths.
No proprietary project source or fixture was used.
