# Cross-symbol named power-output peer fixtures

These tooling-owned schematic sources test
`connector.peer_power_output_open_assignment`. Two distinct synthetic
connector symbols share a native `PART_ID`, value, footprint, full two-pin
inventory, and matching `BIAS_OUT` / `power_out` metadata. `fault.kicad_sch`
assigns J1.1 and leaves J2.1 open; `control.kicad_sch` assigns both target
contacts to one synthetic net.

The prompt is a review question. Matching schematic identity and pin metadata
do not prove that the contacts should share a net. All-open groups are outside
this mixed-assignment rule. These sources are synthetic and are not based on a
product board or project requirement.

The digest-pinned native lane exports each source repeatedly with KiCad 10.0.0
and 10.0.5, then checks the normalized netlist and focused lint result.
