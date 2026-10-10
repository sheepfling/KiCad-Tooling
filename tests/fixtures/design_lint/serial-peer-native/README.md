# Native serial-peer map coverage fixture

All files in this directory are synthetic test inputs owned by the tooling
repository. They contain no proprietary project source or copied project data.

`endpoints.kicad_sch` has two correctly crossed UART endpoint pairs. The two
JSON files are independent authored requirements: `peer-map-partial.json`
maps only J1/J2, while `peer-map-complete.json` also maps J3/J4. The
digest-pinned native fixture lane exports the schematic twice with KiCad 10.0.0
and 10.0.5, verifies the complete pin-function and net-assignment maps, and
compares unrostered, partial-map, and complete-map lint reports.

Run this lane from the tooling checkout after installing its development
environment and setting `KICAD_TEMPLATE_ROOT` to a public template checkout:

```sh
KICAD_RUN_NATIVE_SERIAL_PEER_FIXTURES=1 python -I -B -m pytest -q \
  -m "design_lint and interface_lint and native_kicad" \
  tests/test_serial_peer_native_fixture_lane.py
```

Pinned fixture digests:

- `endpoints.kicad_sch`: `7f3e44ba24ba70b382939fa6504ff635b6bb56292b5bcbc36dee307166378060`
- `peer-map-partial.json`: `a0ed823e11c1612aaa12c8baeca75b1f6b1211ae925970fa2c018c6b8c2a24f4`
- `peer-map-complete.json`: `abed02ee20a713a60a7a0715133d8e02acf170fbc904faa170649dcb9d98c673`
- normalized native `NetlistContract` on both toolchain pins:
  `b1c218d4e398b4ae9d311732a2a8227887e3e8cce1b9759fbd2aa2f0be4320fd`

The lane retains command receipts and normalized native results under ignored
`build/ci-hosted/` directories. A passing result verifies that the native
netlist export and review prompt are repeatable; it does not establish PCB
copper continuity, external wiring, or engineering approval.

## Off-board singleton control

`offboard-endpoints.kicad_sch` is a tooling-owned synthetic variant. J1/J2
remain directly paired. J3 and J4 are separate UART connectors whose TX/RX
pins end at the board boundary, so each signal has one schematic pin. The
source is SHA-256
`8b6c8e83a33470f950ed9df9d9e1328502b3480367c8e3a9ed7aa1741e20d14b`.
`peer-map-with-offboard-endpoints.json` independently declares J1/J2 as direct
peers and J3/J4 as external peers; its SHA-256 is
`35f642b79556327e360a6813dc98d9a77cb7e3cdd353a85b85267f622472a4da`.

At the pinned `aklofas/kicad-happy` commit recorded under LINT-031, two
deterministic-only runs produced identical reports (SHA-256
`4bbbf30c8269cae0341440403413d71711dc4afd67303f2c19145817c604ac6c`). The
candidate emitted `NT-001` INFO findings for J3.1/J3.2/J4.1/J4.2. Repeated
native exports from digest-pinned KiCad 10.0.0 and 10.0.5 images preserve those
four one-pin signal nets and the J1/J2 pairings; the normalized pin-to-net
digest is `84d802852f07682498bcd80c690f158f70f1324a412facc3b144979f9d4272f4`.
Each native ERC report has four `isolated_pin_label` warnings on those exact
external signal labels and no `pin_not_connected` items. Other ERC findings
come from synthetic symbol/footprint and grid setup.

`test_authored_external_peers_clear_singleton_uart_coverage_prompts` verifies
that the source-authored external map suppresses only its named J3/J4 TX/RX
pairs in the deterministic `bus.serial_unmapped_peer` service. This service
test uses a synthetic typed netlist; the separate native exports verify the
schematic pin functions and net assignments. The singleton cohort warning
adds no detection beyond ERC or the existing serial-map coverage prompt. This
fixture has no reference pins, so it does not test ground assignment; use an
independent grounding or `pin_connectivity` requirement for that decision.
Candidate reports and native receipts are kept under ignored
`build/ci/cohort-singleton-net-lint/`.

## Alternate-function MCU and UART net-label fallback

`alternate-function-endpoint.kicad_sch` is a synthetic MCU-to-header schematic.
The MCU exports package-pin functions `PA2` and `PA3`; the generic header
exports `Pin_1` and `Pin_2`; explicit `UART_TX` and `UART_RX` labels provide the
only serial-role clue. The source SHA-256 is
`275a14159f90073056e6b0a972f0cd58bcf1439f4b707a0a769b883c05356f03`, and the
independent authored peer map SHA-256 is
`477c059449f5030da6104324c7320ac6aa667cc15c5ef331aeea1df20fe39458`.

The `serial_peer_net_label_fixture_lane` exports the fixture twice with the
catalogued KiCad 10.0.0 and 10.0.5 images, verifies the exact pin-function and
net-assignment maps, and compares an unconfigured roster with the exact-map
control. The unconfigured case returns one `REVIEW` coverage prompt with
`discovery_basis=net_label`; the exact source-hashed map returns `PASS`. The
normalized typed netlist SHA-256 is
`182122efcca2d6595cafeb398cac44889b54cd187750752201ea1084eacc3d4f` on both
versions. This proves repeatable parsing and rule behavior for the synthetic
case; labels do not establish required connectivity, common ground, PCB copper
continuity, or engineering approval.
