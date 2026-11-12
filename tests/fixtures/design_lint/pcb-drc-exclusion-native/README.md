# Synthetic PCB DRC exclusion round-trip

These project settings exercise saved DRC exclusions with the tooling-owned
fault and control boards in
[`differential-pair-edge-clearance`](../differential-pair-edge-clearance/README.md).
The fault settings contain two `copper_edge_clearance` markers with comments;
their internal-unit coordinates and board-item UUIDs identify the two edge
violations on the fault board. The control settings contain no exclusions and
run against the control board.

The pinned KiCad 10.0.0, 10.0.5, and 10.0.8 Docker lanes run
`kicad-cli pcb drc --severity-all --severity-exclusions` twice per case. The
fault report must preserve both exact comments on the two edge violations, and
the control report must contain no excluded violation. In these report versions
the JSON severity field retains the underlying DRC severity; the comments on
the requested exclusion output identify the matched saved markers.

KiCad documents the [`--severity-exclusions` CLI option][kicad-cli-drc]. The
10.0.5 [PCB marker serializer][kicad-marker-source] records the rule key,
internal-unit location, and item UUIDs used by these synthetic settings.

This is native serialization and matching coverage for synthetic data. It does
not judge whether either exclusion is acceptable or establish electrical or
manufacturing correctness.

[kicad-cli-drc]: https://docs.kicad.org/10.0/en/cli/cli.html
[kicad-marker-source]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.5/pcbnew/pcb_marker.cpp
