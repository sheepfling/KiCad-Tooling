# Synthetic BJT terminal-order fixtures

These tooling-owned schematics use simplified embedded symbols with exact
KiCad `Transistor_BJT:Q_NPN_EBC` and `Transistor_BJT:Q_PNP_BCE` identities and
native B/C/E pin functions. They contain no product board, project contract,
or external cohort data.

| Source              | NPN collector/emitter | PNP collector/emitter | Expected result              |
| ------------------- | --------------------- | --------------------- | ---------------------------- |
| `fault.kicad_sch`   | `GND` / `+5V`         | `+5V` / `GND`         | Two opt-in REVIEW candidates |
| `control.kicad_sch` | `+5V` / `GND`         | `GND` / `+5V`         | No BJT order candidates      |

The native acceptance lane exports each source twice and checks repeatable
netlist and ERC evidence with digest-pinned KiCad 10.0.0 and 10.0.5. The check
reviews only conventional rail order for an exact symbol allowlist. Reverse-
active circuits and other valid topologies may intentionally use the flagged
orientation. The rule defaults off and does not validate footprint pin mapping,
measured voltage, device ratings, physical connectivity, or circuit intent.
