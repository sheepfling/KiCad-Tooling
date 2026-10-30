# Mechanical assembly review

Use a retained [3D board export](3D_VIEWS.md) and a project-authored placement
contract to view one adjacent GLB alongside the board:

```sh
kicad-team assembly-review --project <project-id> \
  --board-receipt build/visualize/<run>/visualization.json \
  --placement-contract examples/projects/<project-id>/docs/assembly-placement.json
```

The MCP `export_assembly_review` tool accepts `project_id`, `board_receipt`,
`placement_contract`, and a fresh `view_id`. Exports must be enabled. Both
surfaces use the same typed service and create a fresh ignored
`build/assembly-review/` receipt. They run no native CAD command.

The JSON contract belongs in the selected project island. Its required fields
are shown below; replace the paths, frames, and hashes with project-reviewed
values:

```json
{
  "schema_version": "1",
  "project_id": "controller",
  "board_glb_sha256": "<SHA-256 of the selected board.glb>",
  "board_frame": "board-export",
  "board_unit": "mm",
  "enclosure_model": "examples/projects/controller/cad/enclosure.glb",
  "enclosure_sha256": "<SHA-256 of the project-owned enclosure.glb>",
  "enclosure_frame": "enclosure-local",
  "enclosure_unit": "m",
  "placement": {
    "source_frame": "enclosure-local",
    "target_frame": "board-export",
    "translation_mm": [12.0, -4.0, 2.0],
    "rotation_xyzw": [0.0, 0.0, 0.0, 1.0]
  }
}
```

`board_frame` and `enclosure_frame` name the GLBs' native coordinate frames.
The rigid `placement` maps enclosure coordinates into the board frame: first
convert the enclosure's declared model unit to millimeters, then rotate using
the normalized XYZW quaternion, then add `translation_mm`. The board model's
declared unit is converted to millimeters too. `mm` and `m` are supported;
unlisted units, unnormalized rotations, and mismatched source/target frames
are rejected. The units and frame origins are project assertions; the GLB
format does not prove their physical meaning.

The service checks the current board source inventory, board receipt, exact
board GLB, contract, and enclosure hash. A missing, changed, invalid, or
external-resource enclosure GLB, or an omitted `placement`, produces an
`INCOMPLETE` board-only view with explicit issues. A verified enclosure GLB is
retained for download even when placement is missing. A partial board export or
unresolved model coverage produces `REVIEW` with the overlay and issues.
The viewer retains both model bytes locally, offers fit/orientation, pan, zoom,
rotation, keyboard controls, and visibility toggles, and never loads a runtime
network resource. The source hashes and selected receipts remain in
`assembly-review.json`.

The opt-in browser regression in [3D views](3D_VIEWS.md) also opens a small
board with a separate meter-scale enclosure panel. It confirms that both models
render offline and that the enclosure visibility control responds. This synthetic
panel is a viewer check, not a verified enclosure for a project.

This is a visual alignment aid. No mesh interference, clearance, tolerance,
enclosure interior, mating feature, or physical fit is calculated. Geometry
coverage and transformed placement must be inspected before mechanical work.
