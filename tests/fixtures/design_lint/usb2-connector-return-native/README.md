# USB 2.0 two-pin connector return review fixtures

This tooling-owned synthetic pair checks the `connector.usb2_pair_without_return_review`
prompt against a complete connector on one exact USB 2.0 PHY D+/D- pair.

| Case    | Source              | Connector                                       | Expected result                     |
| ------- | ------------------- | ----------------------------------------------- | ----------------------------------- |
| Fault   | `fault.kicad_sch`   | Two generic data contacts and no return contact | One bounded reference-return review |
| Control | `control.kicad_sch` | Named D+/D- contacts plus a native GND contact  | No two-pin review                   |

The fault is a tooling regression fixture, not an external product source. The prompt does not
require board ground, infer cable wiring, or verify USB compliance, copper, or physical continuity.
The native source hashes are pinned in
`kicad_tooling/ci_hosted_usb2_connector_return_cases.py`:

| Fixture             | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `d3cce01f646798bc8c8ba9dcbb574842ea540886e5d5fb3fd1db7f0ba79bb20c` |
| `control.kicad_sch` | `d68d586f253471ae0c3ad3bef435ca3dbaaed9600340e4417cd57a6fa50249bc` |

The exact-version lane runs with digest-pinned KiCad 10.0.0 and 10.0.5 images. To run it locally:

```sh
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test \
KICAD_RUN_NATIVE_USB_CONNECTOR_RETURN_FIXTURES=1 \
.venv/bin/python -I -m pytest -q tests/test_usb2_connector_return_native_fixture_lane.py \
  -m 'design_lint and connector_lint and interface_lint and return_path_lint and native_kicad'
```
