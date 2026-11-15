# SWD named-rail synthetic fixtures

These tooling-owned schematics exercise `bus.swd_signal_on_named_rail` with a
complete native `SWDIO`/`SWCLK` pair and explicit optional `SWO` and `nRESET`
functions. The fault assigns `SWDIO` to `GND`, `SWO` to `+3V3`, and `nRESET` to
`+5V`; the control keeps all four signals on separate neutral nets. Both
exports are expected to pass native ERC, and repeated KiCad 10.0.0 and 10.0.5
exports must preserve the same normalized netlist and lint result.

Fixture hashes:

- `fault.kicad_sch`: `e62b668c34f6c3a77f7923cb8e494e1f9ca54324131a678188a8fc5dca70bc3b`
- `control.kicad_sch`: `29ee2641ec06a7d7ec4b120d4e54007c3c3cdee5cbefdc9061468e08c0a22699`

The schematics are synthetic and not for manufacture. They use native pin
function labels that combine JTMS/SWDIO and JTCK/SWCLK, as found in the public
KiCad STM32WB symbol library. They contain no project board or product source.
