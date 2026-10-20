# Synthetic connector peer metadata fixtures

These tooling-owned schematics exercise a review heuristic for connector
symbol aliases whose native pin metadata differs. Both fitted symbols have the
same value, footprint, and complete pin inventory. Their pin 1 function and
electrical type differ; pin 2 has one common assignment.

| Fixture             | Pin 1 assignments             | Pin 2 anchor       | Expected result           |
| ------------------- | ----------------------------- | ------------------ | ------------------------- |
| `fault.kicad_sch`   | `UART_RX_NET` / `UART_TX_NET` | `COMMON_REFERENCE` | `REVIEW`                  |
| `control.kicad_sch` | shared `SHARED_PORT`          | `COMMON_REFERENCE` | No finding from this rule |

This pair tests the analyzer's boundary. Different symbol roles and split nets
can be intentional. The review prompt does not establish that the connectors
are interchangeable or that the nets should be joined. The fixture is not
derived from a product board and is not for manufacture.

SHA-256 source digests:

- `fault.kicad_sch`: `eb57ac1553fa4a6d76a297375ec840d8b6b01c401401877a470968e4c12a45d6`
- `control.kicad_sch`: `1377db1444bf8c1c15bbde73358fe81e36c11581869ea5f31f2082464e97f45e`

The digest-pinned native lane repeats each export with KiCad 10.0.0 and 10.0.5.
Generated reports and command receipts stay under ignored `build/` directories.
