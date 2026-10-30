# Project review overview

The overview is one offline page for receipts you choose. It does not select the
newest run or rerun KiCad, design lint, parts planning, simulation, or
verification. Run it from the project checkout, or pass `--root` explicitly:

```sh
kicad-team review-overview --project <id> \
  --native-summary build/<native-run>/summary.json \
  --findings-view build/<findings-run>/review.json \
  --parts-report build/<parts-run>/report.json \
  --three-d-report build/<3d-run>/visualization.json \
  --charts-report build/<charts-run>/charts.json \
  --verification-report build/<verify-run>/verification.json
```

Every selector is optional. You can pass a receipt directory instead of its
named JSON file. The command writes a fresh `build/review-overview/<project>-<run>/` with
`index.html` and `overview.json`; use `--output build/review-overview/<name>` to
choose a fresh directory. `--format json` prints the typed result. The
`export_review_overview` MCP tool uses the same service when the server starts
with `--allow-exports`; it takes the same selected receipt paths plus a fresh
`view_id`.

The native receipt supplies schematic and PCB SVG links only for recorded,
hash-matched outputs. Findings, 3D, and chart links likewise require their
saved artifact hashes. A new parts receipt includes `parts-artifacts.json`,
which binds `report.json` to its HTML, text, and CSV hashes. The overview links
only matching outputs and marks changed or missing ones stale. Older parts
receipts without this manifest remain **snapshot hash only** and have unknown
output freshness. When checkout inputs can be inventoried, new verification runs
include `verification-artifacts.json`. It binds the summary to a run-start
inventory of non-ephemeral checkout inputs, records whether those inputs stayed
stable during the run, and hashes the top-level journal and stage files. The
overview links matching stage files. It marks changed inputs or outputs stale.
Receipts without the manifest retain unknown freshness. The native and
electrical stage receipts retain their detailed evidence.

Each card retains the original check status separately from freshness:

| Freshness      | Meaning                                                                               |
| -------------- | ------------------------------------------------------------------------------------- |
| `CURRENT`      | The selected receipt's recorded source and artifact bytes matched at export time.     |
| `STALE`        | Source, toolchain, a referenced receipt, or a recorded artifact differed or was lost. |
| `MISSING`      | A selected receipt path was absent.                                                   |
| `UNAVAILABLE`  | A present receipt was malformed, inaccessible, or belonged to another project.        |
| `UNKNOWN`      | The receipt lacks enough saved identity to prove freshness.                           |
| `NOT_SELECTED` | No receipt was selected for that category; the checkout was not searched for one.     |

The page is a snapshot. Recreate it after changing a source or receipt. A
`CURRENT` link is a byte comparison, not an electrical, mechanical, purchasing,
manufacturing, or release approval. Full source hashes, exact selected paths,
and link hashes are retained in `overview.json`.
