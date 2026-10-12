# Cross-symbol named power-input peer fixtures

These tooling-owned schematic sources test
`connector.peer_power_input_open_assignment` and
`connector.peer_power_input_named_all_open`. Two distinct synthetic connector
symbols share a native `PART_ID`, value, footprint, full two-pin inventory, and
matching `BIAS_IN` / `power_in` metadata. `fault.kicad_sch` assigns J1.1 and
leaves J2.1 open; `all-open-fault.kicad_sch` leaves both target contacts open;
`control.kicad_sch` assigns both target contacts to one synthetic net.

The prompt is a review question. Matching schematic identity and pin metadata
do not prove that the contacts should share a net. The sources are synthetic
and are not based on a product board or project requirement.

The digest-pinned native lane exports each source repeatedly with KiCad 10.0.0
and 10.0.5, then checks the normalized netlist and focused lint result.
