# Compare dated supplier offers for a reviewed BOM

`supplier-analysis` compares two explicitly selected, manually captured
`SourcingSnapshot` JSON files against one saved, source-bound parts receipt.
Snapshots must be generated artifacts inside the checkout's `build/` tree.
The BOM plan and retained netlist are checked before comparison. The view
does not contact suppliers.

Each snapshot has an aware `observed_at` timestamp and a source commit. Its
offers identify a part, supplier, SKU, currency, region, quantity break,
recorded availability, and optional lead time. Offers can also record
`minimum_order_quantity` and `package_multiple`; set both explicitly, using
`1` if there is no constraint. `unit_price_minor` can be omitted or `null`
when no price was observed. An example offer inside a snapshot is:

```json
{
  "id": "offer-42",
  "part_id": "exact-catalog-part-id",
  "supplier": "Example supplier",
  "supplier_sku": "EX-42",
  "source_url": "https://example.invalid/offer",
  "region": "US",
  "currency": "USD",
  "quantity_break": 10,
  "unit_price_minor": 125,
  "availability": "recorded as available",
  "lead_time_days": null,
  "minimum_order_quantity": 10,
  "package_multiple": 5
}
```

Select a comparison date and maximum age explicitly. A snapshot older than
that age is marked `STALE`; one dated after the comparison date is `FUTURE`.
For each offer, the view shows the requested BOM quantity, packaging-adjusted
order quantity, selected quantity break, unit price, and mathematical extended
cost in **minor currency units**. It never chooses a supplier or converts
currencies. Missing prices, packaging terms, unmatched BOM parts, and
ambiguous revisions leave the extended cost unavailable.

```sh
kicad-team supplier-analysis --root /path/to/project-checkout \
  --project controller \
  --parts-receipt build/parts/review/report.json \
  --before build/sourcing/earlier.json \
  --after build/sourcing/later.json \
  --as-of 2026-10-30 --max-age-days 30 --format json
```

MCP `compare_supplier_offers` accepts the same inputs and a `view_id` when
exports are enabled. Both write a fresh ignored `build/supplier-analysis/`
receipt with an offline `index.html`, `supplier-analysis.json`, and exact
copies of the selected parts report and snapshots. The report includes hashes
of the copied evidence and the parts source identity.

Offer freshness, local catalog matching, prices, availability, and lead times
are review evidence only. No live availability, currency exchange, purchasing
decision, order, part substitution, or engineering approval is implied.
