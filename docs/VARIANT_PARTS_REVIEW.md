# Named variant parts review

Use a saved parts receipt and a findings view that includes complete native
population evidence for one named KiCad variant. The variant name must be
declared in the project's `.kicad_pro`; the retained schematic netlist, PCB
positions, commands, tool image, source hashes, and design-lint receipt must
match the selected project. The parts receipt supplies the project's recorded
board count, spare preferences, and source-bound catalog inputs.

```sh
kicad-team variant-parts-review --project controller \
  --parts-report build/parts/<receipt>/report.json \
  --findings-view build/findings-view/<receipt>/review.json \
  --assembly-variant STANDARD
```

The MCP equivalent is `export_variant_parts_review` with `project_id`,
`parts_report`, `findings_view`, `assembly_variant`, and a fresh `view_id`.
Both call the same review service and create a fresh receipt under ignored
`build/variant-parts/`.

Open `index.html` for grouped quantities, the reconciled variant population,
unresolved references, parts findings, and links into the saved schematic and
PCB drawings. `bom.csv` is a review export; `unresolved.csv` names references
omitted from quantities. `variant-parts.json` binds the
source, catalog, selected receipts, variant artifacts, quantities, unresolved
population, and navigation receipt by SHA-256. The nested `navigation/` page
also shows references found only in the native variant netlist.

Order quantities use only fitted schematic components with a matching fitted
PCB position and a usable value, footprint, and `PART_ID`. DNP and BOM-excluded
components remain visible but do not add quantity. A fitted reference without
a match, or a fitted PCB reference without a schematic part, stays unresolved
and blocks the supplier CSV. Catalog identity and part approval checks still
run through the normal purchasing planner. No receipt authorizes purchase,
assembly, electrical approval, or release.

The current regression controls cover two distinct named populations, a
PCB-only fitted reference, a native-only schematic reference, stale evidence,
and CLI/MCP parity. Exact KiCad exports for a representative user project
remain an acceptance step for this backlog item.
