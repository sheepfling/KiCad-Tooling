# Compare saved product BOM revisions

Save a [product visual review](PRODUCT_VISUAL.md) for each product source
revision, then select those two receipts explicitly:

```sh
kicad-team product-revision-bom --root /path/to/project-checkout \
  --baseline build/product-visual/<older>/product-visual.json \
  --candidate build/product-visual/<newer>/product-visual.json
```

The command writes an offline `index.html` and typed `comparison.json` under a
fresh ignored `build/product-revision-bom/` directory. Use `--output` for a
specific fresh directory and `--format json` for the structured result. MCP
`compare_product_revision_bom` uses the same service with `baseline`,
`candidate`, and a fresh `view_id` when exports are enabled.

New product visual receipts retain the exact product record and parts catalog
bytes used at capture. The comparison verifies every saved page and source file
hash before projecting the canonical product BOM from those saved inputs. It
shows added, removed, and changed instance paths; grouped part identity,
revision, and quantity differences; both variant identities; and whether each
saved source inventory still matches the live checkout. Historical source is
valid for historical comparison and is labeled separately from current source.

An older product visual receipt without the saved parts catalog still shows
its instance changes but marks canonical BOM quantities unavailable. A changed
saved artifact or a different product ID is rejected. The authored BOM does not
verify observed board population, approve substitutes, or authorize purchases
or builds.
