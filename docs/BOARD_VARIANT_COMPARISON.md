# Compare observed KiCad board variants

Create a [findings view](FINDINGS_VIEW.md) from a saved native summary and a
design-lint report with complete named PCB variant population evidence. Select
two different variants declared in the project's `.kicad_pro` file:

```sh
kicad-team board-variant-compare --project <project-id> \
  --findings-view build/findings-view/<run>/review.json \
  --before-variant <name> --after-variant <name>
```

The MCP `compare_board_variants` tool accepts `project_id`, `findings_view`,
`before_variant`, `after_variant`, and a fresh `view_id`. It requires exports to
be enabled. Both surfaces use the same typed service and run no new KiCad
command. They write a fresh ignored `build/board-variant-comparison/` receipt
with `index.html` and `comparison.json`.

The comparison verifies the findings and design-lint receipt hashes, current
project source, exact pinned KiCad image, and each selected variant's retained
netlist and full/fitted PCB position files. It also checks that the saved
export commands named the selected variant, source, and output. A missing,
changed, or incomplete input stops the comparison.

The page shows added, removed, and changed footprint-assigned schematic or PCB
reference states, including DNP and unplaced cases. Grouped per-board quantities
count references only when the
selected PCB export fits them **and** the matching schematic netlist fits them
with a `PART_ID`. Fitted PCB-only references, schematic/PCB population
disagreements, and missing part identities stay in a separate unresolved list.
Quantity bars compare native observed populations; they are not an order
quantity, controlled part-revision comparison, or purchasing approval. Use
[product revision BOM comparison](PRODUCT_REVISION_BOM.md) for catalog revision
changes and [BOM cross-probing](CROSS_PROBE.md) to inspect one variant on saved
design drawings.
