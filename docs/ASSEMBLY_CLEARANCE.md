# Authored box clearance review

`assembly-clearance` measures the retained board GLB against a rectangular
free-space region declared in a selected project's enclosure frame. It builds
on the [assembly review](ASSEMBLY_REVIEW.md): the board receipt, placement
contract, enclosure model, units, source hashes, and board model coverage must
be current before a margin is reported.

```sh
kicad-team assembly-clearance --project <project-id> \
  --board-receipt build/visualize/<run>/visualization.json \
  --placement-contract examples/projects/<project-id>/docs/assembly-placement.json \
  --clearance-contract examples/projects/<project-id>/docs/assembly-clearance.json
```

MCP `export_assembly_clearance` accepts `project_id`, `board_receipt`,
`placement_contract`, `clearance_contract`, and a fresh `view_id` when exports
are enabled. Both surfaces call the same service. The output is an ignored
`build/assembly-clearance/` directory with `assembly-clearance.json`, a local
HTML margin and surface table, and a nested offline 3D assembly viewer.

The clearance contract belongs to the selected project island:

```json
{
  "schema_version": "1",
  "project_id": "controller",
  "placement_contract_sha256": "<SHA-256 of assembly-placement.json>",
  "free_space": {
    "lower": [-0.014, 0.003, -0.003],
    "upper": [-0.010, 0.005, -0.001],
    "basis": "Reviewed enclosure interior free-space region"
  },
  "required_margin_mm": 0.4
}
```

The box bounds use the **enclosure model's declared unit** (`mm` or `m`), and
its axes and origin use the **enclosure model frame**. In this example the unit
is meters. The placement contract maps enclosure coordinates into board
coordinates. The service applies its inverse to every referenced board
triangle vertex, then computes signed distances to all six box faces in
millimeters. Negative face margin means board geometry extends beyond that
declared face. `LOW_CLEARANCE` means the smallest margin is below the authored
requirement; `BOX_INTERFERENCE` means at least one margin is negative. Missing
placement, incomplete model coverage, or unsupported geometry yields
`UNASSESSED` with an issue. No margin is inferred from an absent input.

The same receipt also compares the static triangles in both retained GLBs
after placement and unit conversion. It reports a minimum Euclidean
**surface-to-surface gap** in millimeters, or `MESH_SURFACE_INTERSECTION` when
surfaces touch or cross within a 0.000001 mm numeric contact tolerance.
`LOW_SURFACE_GAP` means separated surfaces fall below
`required_margin_mm`. Triangle-pair comparison is bounded to two million
pairs; unsupported, degenerate, or larger geometry leaves the surface result
`UNASSESSED` with an issue. The box result remains separately visible.

The box is an authored assertion of free space. Surface separation alone does
**not** prove that a board lies outside an enclosure solid, that either model
is watertight, or that the board fits an enclosure interior. The service does
not derive that interior, inspect fasteners or flexible parts, or certify
physical fit. A clear box result applies only to that declared box and
supported static board triangle geometry. Project reviewers must establish
that the box matches the intended mechanical region and that both exports
have the required coverage. The report always records `fit_certified=false`
and `enclosure_mesh_clearance_assessed=false`; the separate surface status
states exactly which triangle comparison succeeded.
