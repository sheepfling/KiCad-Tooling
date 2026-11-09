# SWDIO/SWCLK same-net fixtures

These are synthetic tooling-owned KiCad schematics. The fitted U1 symbol has
complete native pin metadata, including composite functions
`SYS_JTMS-SWDIO` and `SYS_JTCK-SWCLK`. J1 remains on separate auxiliary nets
so only the U1 role pins participate in the fault.

- `fault.kicad_sch` assigns U1.5 and U1.6 to the same `SWD_SHARED` net. J1
  contacts use separate nets. The review rule reports those exact native roles
  and pins.
- `control.kicad_sch` assigns U1.5 and U1.6 to separate `SWD_DATA` and
  `SWD_CLOCK` nets.

Reviewed SHA-256 values:

- `control.kicad_sch`: `a0b087f03a3aa5e422b638ca01cb17b1c984216d9ccf29815c9fbbd09939d7dc`
- `fault.kicad_sch`: `af9f943e6ad53f495ff790b8c41b01812aa1924e3eb5afc33e762151c86ace24`

The selected native lane exports each source twice on digest-pinned KiCad
10.0.0 and 10.0.5 images, verifies the complete expected pin functions and net
assignments, and requires zero ERC errors. It validates this synthetic rule
path and those export versions. It does not establish a project's intent,
debug-access policy, routed copper, physical continuity, or manufacturing
readiness.
