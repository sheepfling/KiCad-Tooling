# SWD generic connector fixtures

These KiCad schematics are synthetic tooling-owned fixtures. The MCU symbol
uses composite native pin functions `SYS_JTMS-SWDIO` and
`SYS_JTCK-SWCLK`; the connector uses generic `Pin_N` contacts.

- `fault.kicad_sch` assigns J1.1 and J1.2 to the MCU's exact SWDIO and SWCLK
  nets. The lint asks for connector association and pinout review.
- `control.kicad_sch` leaves those generic contacts on separate auxiliary nets.

Reviewed SHA-256 values:

- `control.kicad_sch`: `f259e2b4095696ea8d7284d8add909a83800a0ac953b56f57829165c0060f0d3`
- `fault.kicad_sch`: `45e993200c7ba4669083de09c93fbcb5082bdecd540214bdbd7b01da600a1118`

The native lane exports each source twice using digest-pinned KiCad 10.0.0
and 10.0.5 images. It checks the exact endpoint-to-connector nets and requires
repeatable normalized netlists. This validates the synthetic rule path and
those native export versions. It does not establish connector purpose, board
policy, routed copper, field applicability, reviewer value, or manufacturing
readiness.
