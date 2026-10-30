# Compare saved parts BOMs

Select two completed parts receipts for the same project. The comparison reads
their typed purchasing plans and verifies each retained netlist against its
receipt hash. It does not rerun KiCad or resolve new part identities.

```sh
kicad-team bom-compare --root /path/to/project-checkout \
  --project controller \
  --before build/parts/earlier/report.json \
  --after build/parts/later/report.json --format json
```

The command writes a fresh ignored `build/bom-comparison/` receipt with
`comparison.json` and an offline `index.html`. The page separates fitted,
excluded or DNP, and unresolved references. It shows added, removed, changed,
and unchanged references and grouped part quantities, including per-board,
required, spare, and total amounts. Both selected report hashes and their
recorded source hashes remain in the comparison.

MCP `compare_parts_bom` uses the same service when exports are enabled. Pass
`project_id`, `before`, `after`, and a fresh `view_id`.

Parts receipts do not record a variant identity, so this comparison labels
variant scope as `NOT_RECORDED`. Different source path sets are marked
`DIFFERENT_PATHS`; source hash changes are shown without treating historical
evidence as current.

## Compare authored product variants

For two variants declared by one indexed product, use the existing product BOM
projection:

```sh
kicad-team product-variant-bom --root /path/to/project-checkout \
  --product status-indicator-system \
  --before-variant STANDARD --after-variant UNO_ONLY --format json
```

MCP `compare_product_variant_bom` accepts `product_id`, `before_variant`,
`after_variant`, and a fresh `view_id` when exports are enabled. Both surfaces
write the same typed `build/product-variant-bom/` comparison. It retains a full
source-bound product visual review for each variant, with links from the offline
comparison page. The comparison shows included, omitted, and unresolved
procurement instances by exact product path and compares canonical grouped BOM
rows by part identity and revision. It records the product and variant
revisions, product and catalog source hashes, and hashes of both retained
variant reviews.

The two variants must come from the same product source revision. When the
product contract or a catalog identity is unresolved, instance rows remain
visible but canonical BOM quantities are unavailable and the result is
`REVIEW`. No measured board population, approved substitute, purchase, build,
or release decision is inferred from either comparison.
