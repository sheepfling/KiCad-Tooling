# Cross-probe a BOM against saved design drawings

Create a parts receipt and a [findings view](FINDINGS_VIEW.md) for the same
project source snapshot. Then select both receipts explicitly:

```sh
kicad-team cross-probe --project <project-id> \
  --parts-report build/parts/<run>/report.json \
  --findings-view build/findings-view/<run>/review.json
```

The command writes a fresh ignored `build/cross-probe/` receipt with
`index.html` and `cross-probe.json`. The MCP `export_bom_cross_probe` tool uses
the same service with `project_id`, `parts_report`, `findings_view`, and a fresh
`view_id`; it requires exports to be enabled. Both surfaces read saved evidence
and run no native KiCad command.

The page lists every parts-plan component. A unique fitted reference can link
to its placed front-side PCB anchor and to each exact symbol unit on a uniquely
bound schematic sheet. For KiCad 10.0.6 hierarchical exports, the selected
findings view must have matched the SVG sheet title to an exact source-instance
path; a single-sheet legacy root plot retains its supported fallback. Selecting
a component location scrolls to its marker;
selecting the marker returns to the component. Search filters the component
table. The page also retains the original verified SVG plots, their source
hashes, and hashes of both selected receipts.

Board and schematic anchors come from the current KiCad source, parsed with the
tooling's existing S-expression reader. The saved parts and findings receipts
must name the same current source inventory; parts inputs, retained netlist,
native summary, and drawing hashes are checked before export and checked again
before the result is committed. Changed source or selected evidence is rejected.

Duplicate references get no location. DNP and excluded rows get no fitted
placement claim. Unplaced and unsupported rows remain visible with an issue.
Back-side footprints and symbols whose sheet drawing is missing, stale, or
ambiguous retain source coordinates and sheet-instance paths without a marker.
A multi-unit component can have multiple symbol locations, and reused child
sheet instances keep separate drawings and markers. A footprint identity
mismatch is shown as a warning beside the navigation point; the location does
not approve the footprint.

Parts and findings receipts do not record a common assembly variant identity.
The cross-probe report labels variant parity `NOT_RECORDED`; do not use it to
claim that two different variant states match. The output is a navigation aid,
not approval of parts, electrical design, physical placement, or release.
