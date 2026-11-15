# SWD named-rail synthetic fixtures

These tooling-owned schematics exercise `bus.swd_signal_on_named_rail` with a
complete native `SWDIO`/`SWCLK` pair and an explicit `SWO` function. The fault
assigns `SWDIO` to `GND` and `SWO` to `+3V3`; the control keeps all three signals
on separate neutral nets. Both exports are expected to pass native ERC, and
repeated KiCad 10.0.0 and 10.0.5 exports must preserve the same normalized
netlist and lint result.

Fixture hashes:

- `fault.kicad_sch`: `62837263395b23916e1b61ec5687c1d658666c92c7db0a7cc064c44711bfa675`
- `control.kicad_sch`: `787e89740492874bc952fdad71e4f605d449b292c7d0db7d217f5fbc92f77e19`

The schematics are synthetic and not for manufacture. They use native pin
function labels that combine JTMS/SWDIO and JTCK/SWCLK, as found in the public
KiCad STM32WB symbol library. They contain no project board or product source.
