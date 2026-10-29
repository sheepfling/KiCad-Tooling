# Serial endpoint-role collision fixtures

These synthetic schematics exercise `bus.serial_endpoint_role_collision`.
The control crosses controller TX to connector RX and controller RX to connector
TX. The fault assigns same-role endpoint pins to direct shared nets. Both are
synthetic topology probes and do not model an approved port map.

| Case | Source SHA-256 |
| --- | --- |
| `control.kicad_sch` | `1195fa229d095fd654635ee545158e429f0da87b705e0a16412a8ba73a570836` |
| `fault.kicad_sch` | `a63ea158cb5f8adc9d0a95328442eded39f8e0e770e58de3f56f73adc86fdb6b` |

The exact-version native lane checks both pin-function identities, connector
net assignments, no ERC errors, and repeated normalized netlist hashes with
digest-pinned KiCad 10.0.0 and 10.0.5 images. Same-role connections can be
intentional in special interfaces; the finding is a review prompt, not a
pinout verdict or a physical-copper check.
