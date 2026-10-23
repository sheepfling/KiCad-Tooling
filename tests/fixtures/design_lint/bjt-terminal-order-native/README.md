# Synthetic BJT component fixtures

These tooling-owned schematics use simplified embedded symbols with exact
KiCad `Transistor_BJT:Q_NPN_EBC` and `Transistor_BJT:Q_PNP_BCE` identities and
native B/C/E pin functions. They contain no product board, project contract,
or external cohort data.

| Source              | NPN collector/emitter | PNP collector/emitter | Base-drive path                        | Expected review                          |
| ------------------- | --------------------- | --------------------- | -------------------------------------- | ---------------------------------------- |
| `fault.kicad_sch`   | `GND` / `+5V`         | `+5V` / `GND`         | Both outputs connect directly to bases | Rail-order and base-drive review         |
| `control.kicad_sch` | `+5V` / `GND`         | `GND` / `+5V`         | Each output passes through a 1 kΩ part | No BJT rail-order or direct-drive review |

Both native acceptance lanes export each source twice and check repeatable
netlist and ERC evidence with digest-pinned KiCad 10.0.0 and 10.0.5. The
terminal-order check reviews only conventional rail orientation for an exact
symbol allowlist. Reverse-active circuits and other valid topologies may
intentionally use the flagged orientation; that rule defaults off. The
base-drive check reviews a native output pin that shares the BJT base net and
clears when the visible resistor separates them; it defaults to review. Neither
check validates footprint pin mapping, measured voltage, device ratings, PCB
copper, physical connectivity, or circuit intent.
