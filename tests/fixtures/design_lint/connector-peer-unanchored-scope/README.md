# Unanchored connector peer-scope parity fixture

This two-connector KiCad XML netlist is synthetic. Both generic contacts are
assigned to different nets on symbol aliases with the same value, footprint,
complete pin inventory, and native pin metadata. One test omits connector
coverage entirely. Another authors complete source-matched pin maps but
intentionally omits a peer-assignment group. The CLI/MCP cases verify that the
tooling asks for pinout and scope review in the first case, then asks whether
the connectors should be compared or kept separate in the second. Neither
finding requires contacts to share nets.

The fixture verifies that the source-bound design-lint service reports both
states through CLI and MCP and keeps them distinct. It does not model a product
board, connector pinout, off-board cable, or electrical requirement.

The `partial-open-*.xml` netlists also exercise missing-coverage prompts. The
two-alias case assigns one generic contact on one alias and leaves its peer
open; the three-alias case assigns that contact to two different nets and
leaves the third alias open. Both use generic native pin metadata and no common
net anchor. Their matching controls add a common-net anchor on the other pin,
which suppresses the unanchored-scope prompt. These XML inputs are synthetic
service and CLI/MCP fixtures; the exact-version KiCad lane separately exercises
the existing schematic fault/control pair.
