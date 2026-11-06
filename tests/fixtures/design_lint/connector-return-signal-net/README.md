# Connector return and protocol signal fixtures

These tooling-owned schematics exercise a review heuristic for a fitted
connector return pin that shares a schematic net with a pin whose native
function identifies a supported protocol signal. The check recognizes pin
functions, not net names. It is a prompt to compare against an approved
connector pinout; it does not decide whether the connection is wrong.

The fault assigns J1.1 (SDA) and J1.2 (GND) to `SDA_BUS`. The control keeps
SDA on `SDA_BUS` and assigns GND separately. Both contacts are passive in the
synthetic symbol, and the schematic contains no external project or board
source. These fixtures are not for manufacture.

The native fixture lane verifies the pin functions and assignments after
repeat exports from digest-pinned KiCad 10.0.0 and 10.0.5 images. Run it with
`KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1`.

| Fixture             | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `8ac8180b2d26c0352d4262cddb74e86c5f346c76b905d7d9b1a3b8300493f5a0` |
| `control.kicad_sch` | `675be8d054c2aad583f023362a77e1a90d36c5c56e2b29ed3e48b933c36966c8` |
