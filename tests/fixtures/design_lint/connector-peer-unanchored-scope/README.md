# Unanchored connector peer-scope parity fixture

This two-connector KiCad XML netlist is synthetic. Both generic contacts are
assigned to different nets on symbol aliases with the same value, footprint,
complete pin inventory, and native pin metadata. The project test authors
complete connector pin maps but intentionally omit a peer-assignment group.

The fixture verifies that the source-bound design-lint service asks for a
peer-scope review through both CLI and MCP. It does not model a product board,
connector pinout, off-board cable, or electrical requirement.
