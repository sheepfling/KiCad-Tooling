# RS-485 open data-pin regression

These are synthetic two-pin schematics created only to test the tooling. They
contain no product or cohort design data and are not manufacturing inputs.

Fault (`fault.kicad_sch`): a fitted, explicit RS-485 transceiver has D assigned
to `HOST_TX`; R has an explicit no-connect marker and no net assignment. The
default-off rule retains a finding with `RULE_OFF`; review mode reports
`U1.2: R`.

Control (`control.kicad_sch`): the same pin inventory has D assigned to
`HOST_TX` and R assigned to `HOST_RX`; no finding.

The hosted runner pins each source SHA-256 and checks repeated netlist/ERC
exports using digest-pinned KiCad 10.0.0 and 10.0.5 images. These tests verify
the schematic-level review heuristic only; they do not establish PCB copper,
firmware use, or physical continuity.

Source hashes:

- `fault.kicad_sch`: `39ec0fb43f3175204f550a71506a7b5fd063cf71759f2786ea0bf765f6077c5f`
- `control.kicad_sch`: `fa1ee6811e6351691e186c70411c6fbb139acbbebbb99e556136ad36818ea588`
