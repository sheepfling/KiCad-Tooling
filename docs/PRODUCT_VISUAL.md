# Product and harness visual review

Select a product and one authored variant from the configured product index:

```sh
kicad-team product-visual --product <product-id> --variant <variant-id>
```

The MCP `export_product_visual` tool accepts `product_id`, `variant_id`, and a
fresh `view_id` when exports are enabled. Both surfaces use the same typed
service and write an ignored `build/product-visual/` receipt without running a
native KiCad command.

The offline page shows the variant's expanded assembly hierarchy, including
omitted instances, and one card per authored electrical, functional,
mechanical, or protocol relation. Cards preserve terminal ID, instance path,
pin, interface identity, harness ID, assurance, and evidence IDs. A search box
filters instances and relations. Omitted relations and broken references stay
visible; they are not silently treated as connected.

When the selected product passes its existing typed policy checks, the receipt
includes the canonical `system.json` and `harness-schedule.json` projections.
The page shows their selected-variant harness rows and links to both records.
If a part, terminal, harness, project, or assembly reference is invalid, the
page remains a review of the authored source and reports issues, while those
canonical projections are unavailable. The exact authored `product.json` and
selected `product-index.json` are retained beside the page.

`product-visual.json` records the product and variant revisions, hashes of the
product record, configured catalogs, each related project manifest, and its
current source inventory. Missing project IDs and unavailable source scopes
are shown separately. Inputs are rechecked before the receipt is committed.

Every line on the page is an **authored relationship**, not an observation of
PCB copper, system wiring, cable construction, or mechanical fit. Product open
items remain visible. This view is not build or release approval.
