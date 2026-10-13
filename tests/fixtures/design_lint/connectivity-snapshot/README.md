# Connectivity snapshot reconciliation fixture

`netlist.xml` is a tooling-owned, hand-authored KiCad XML-shaped synthetic
netlist. It is not a native KiCad export. The CLI/MCP reconciliation test
changes only J1 pin 4's function from `GND` to `RETURN`, keeping every pin's
net and electrical type unchanged. This verifies that both adapters surface
the source-bound pin-role metadata delta consistently.
