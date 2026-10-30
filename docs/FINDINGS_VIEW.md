# Explore schematic and PCB findings

From a project checkout, first run native verification with the project's exact
KiCad toolchain. Select the resulting native `summary.json` or its receipt
directory and create an offline review:

```sh
kicad-team findings-view --project <id> --native-summary build/<native-run>/summary.json
```

Open the `index.html` named by the command. The receipt also contains sanitized
copies of the recorded drawings and `review.json` with source and artifact hashes.
Select a marker to find its entry; select a coordinate in the list to return to
its marker. Use the drawing zoom controls, then scroll within the drawing. Search
and filter findings by source. Findings without reliable
locations, and findings with only some locations mapped, are listed separately.

To include design-lint findings, save a JSON report produced for the **same**
project and native receipt, then pass that saved artifact:

```sh
kicad-team design-lint --project <id> --native-summary build/<native-run>/summary.json --format json > build/lint-report.json
kicad-team findings-view --project <id> --native-summary build/<native-run>/summary.json --lint-report build/lint-report.json
```

Design lint can return a nonzero exit code when it reports review findings; the
JSON output still records its status. The viewer checks the source inventory,
native netlist, manifest, and policy against the saved lint snapshot. Independent
review-map inputs may have changed since that snapshot; rerun lint when needed.
The explorer itself does not rerun KiCad or lint. A successful explorer command
means the review was written; the page separately shows the native and lint
statuses and does not approve the design.

The MCP `export_findings_view` tool uses the same service when exports are enabled.
It accepts `project_id`, `view_id`, `native_summary`, and optional `lint_report`;
the saved inputs must be allowed repository artifacts, and its output uses a
fresh `build/findings-view/<view_id>` directory.

## Location coverage

- Native PCB DRC item coordinates are marked only for KiCad 10.0.0, 10.0.5,
  or 10.0.6, the recorded board export, millimetre coordinates, and an
  unambiguous SVG coordinate frame. Schematic-parity items remain listed
  without PCB markers.
- Supported source-bound schematic geometry lint findings are marked on a
  verified root-sheet export for KiCad 10.0.5 or 10.0.6. For KiCad 10.0.6,
  repeated child sheets can also be marked when the native SVG's unique hidden
  sheet/file title matches an exact UUID-path source instance and the saved
  lint source-tree bindings match that instance. Each matched sheet has its own
  drawing and marker overlay. Missing or duplicate SVG sheet identities stay
  unmapped; hierarchical mapping for other KiCad versions remains unverified.
- KiCad 10.0.6 ERC item positions can be marked on uniquely UUID-bound sheets
  when the native report names the exact schematic, declares millimetres, and
  every position converts into the verified SVG frame. Exact native fault and
  control exports establish that this version reports ERC `pos` fields at
  1/100 of the schematic and SVG millimetre coordinates. Missing sheet UUIDs,
  ambiguous drawings, unsupported units, partial positions, and other KiCad
  versions keep their ERC findings visible without guessed placement.
- Design-lint rules without an explicit supported geometry location are
  listed without a marker. Missing checks, unavailable drawings, partial
  locations, and unsupported SVG coordinate frames are reported on the page.

The markers are review aids over retained evidence. They do not repair source,
establish the completeness of checks, or authorize electrical or manufacturing
decisions. Regenerate the receipt after changing source or review inputs.

The small synthetic drawings and report excerpts used by the review tests are
documented in the [findings-view fixture guide](../tests/fixtures/findings_view/README.md).
