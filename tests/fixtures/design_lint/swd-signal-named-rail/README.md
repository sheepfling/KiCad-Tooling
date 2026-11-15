# SWD named-rail synthetic fixtures

These tooling-owned schematics exercise `bus.swd_signal_on_named_rail` with a
complete native `SWDIO`/`SWCLK` pair. The fault assigns only `SWDIO` to `GND`;
the control keeps the pair on separate signal nets. Both exports are expected
to pass native ERC, and repeated KiCad 10.0.0 and 10.0.5 exports must preserve
the same normalized netlist and lint result.

Fixture hashes:

- `fault.kicad_sch`: `6b1efd506bfd509806edada4a9fca7e48077f0f74c28bb85b12c2dda54eeb794`
- `control.kicad_sch`: `9aa939d5ec1e0cf359adbe1ae9962f5bf8857db107f28775e9ebd479d8f8ba93`

The schematics are synthetic and not for manufacture. They use native pin
function labels that combine JTMS/SWDIO and JTCK/SWCLK, as found in the public
KiCad STM32WB symbol library. They contain no project board or product source.
