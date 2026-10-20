# Synthetic PART_ID connector peer missing-metadata fixtures

These tooling-owned schematics exercise the missing-metadata review heuristic
when two distinct connector symbols share a project-authored `PART_ID`. J1 uses
`SYNTHETIC-PEER-001` and J2 uses `synthetic-peer-001` to verify case-insensitive
identity matching. Both use the same value, footprint, and complete two-pin
inventory; pin 2 is a common-net anchor.

| Fixture             | Pin 1 assignments             | Pin 2 anchor       | Expected result |
| ------------------- | ----------------------------- | ------------------ | --------------- |
| `fault.kicad_sch`   | `UART_RX_NET` / `UART_TX_NET` | `COMMON_REFERENCE` | `REVIEW`        |
| `control.kicad_sch` | both use `SHARED_PORT`        | `COMMON_REFERENCE` | No finding      |

The matching `PART_ID` is only a similarity clue, not proof that both
connectors have the same electrical role. The fault asks a reviewer to inspect
the exact symbol pinouts and project requirements; it does not direct the user
to join the split nets. These synthetic cases are not derived from a product
board and are not for manufacture.

SHA-256 source digests:

- `fault.kicad_sch`: `5684bcf7293542cbc8bf2b05e68a3a7c9f6d0db6f0b7aaac0590721f1b58907b`
- `control.kicad_sch`: `880e000dc1646fe5a8a4183b60ac36150d6e965e9dd7b8055ac286e0a0e1f75c`

These cases ran as part of the local digest-pinned KiCad 10.0.0 and 10.0.5
fault/control acceptance recorded in the
[companion fixture record](../connector-footprint-peer-missing-metadata-native/README.md).
Generated reports and receipts stay under ignored `build/` directories.
