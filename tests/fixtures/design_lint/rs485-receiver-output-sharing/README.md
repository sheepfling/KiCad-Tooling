# RS-485 receiver-output sharing fixtures

These are tooling-owned synthetic schematics. Two fitted transceiver symbols
have explicit RS-485 identity, native `RO` pin functions, complete pin
inventories, and passive native electrical types. The fault assigns both
receiver outputs to `RX_SHARED`; the control gives them separate labels. The
native lane confirms that KiCad exports those assignments and that ERC does
not report the passive-typed pin pairing. It does not establish the devices'
actual output-enable behavior or whether sharing is electrically acceptable.

| Source                                        | Purpose                                 | SHA-256                                                            |
| --------------------------------------------- | --------------------------------------- | ------------------------------------------------------------------ |
| `receiver-outputs-shared.kicad_sch`           | Two fitted RS-485 `RO` pins share a net | `71ad76ad63c8809b3660430114e2f8dcd4c2d998ce42f2e8003bc9b7cbfc1066` |
| `receiver-outputs-separate-control.kicad_sch` | Fitted `RO` pins use separate nets      | `4508463236cfd33c1f681624a4b027ed262c3895e6d5bb7e47dfaedb94f634e0` |

Run from the tooling checkout with the native KiCad Docker images pinned by the
package acceptance lane:

```sh
KICAD_RUN_NATIVE_RS485_RECEIVER_OUTPUT_SHARING_FIXTURES=1 \
  .venv/bin/python -I -m pytest -q \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.rs485_receiver_outputs_share_net")' \
  tests/test_rs485_receiver_output_sharing_native_fixture_lane.py
```
