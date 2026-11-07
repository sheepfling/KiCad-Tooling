# RS-485 two-contact connector return review fixtures

This tooling-owned synthetic pair checks the `connector.rs485_pair_without_return_review`
prompt. It is not a product design and is not for manufacture.

| Case | Source | Expected result |
| --- | --- | --- |
| Fault | `fault.kicad_sch` | Review a complete generic two-contact connector on the exact native A/B pair with no identified reference return. |
| Control | `control.kicad_sch` | Keep quiet when the two connector contacts have explicit native A/B roles. |

Both schematics retain a complete synthetic SN65HVD485 endpoint pin inventory and
the same exact A/B net assignments. The fault/control mutation changes only the
connector contact names. It does not assert that RS-485 requires a local board
ground, and it does not validate termination, biasing, PCB copper, or off-board
wiring.

The source SHA-256 values are:

- `fault.kicad_sch`: `7e4b41a4a9d10ed6358f93effccbca56758fea534e59fc4885450244fafa7886`
- `control.kicad_sch`: `fbdb566de8cb39214c7182b2eec433360b11e48b5b8325ace0484567f5f77a80`

Native exports are repeated with the tooling template's digest-pinned KiCad
10.0.0 and 10.0.5 images. Their exact project versions are checked before
export. These synthetic fixtures test deterministic source extraction only;
they do not establish electrical approval or manufacturing readiness.
