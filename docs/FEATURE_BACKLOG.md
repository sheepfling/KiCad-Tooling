# Product feature backlog

This is the proposed product-facing backlog for KiCad Team Tooling. It covers
engineering workflows, visualization, data exchange, and review; it is separate
from the [design-lint backlog](DESIGN_LINT_BACKLOG.md), which owns individual
electrical rules, and the [architecture backlog](ARCHITECTURE_BACKLOG.md), which
owns the extension path and structural work.

The order below is a recommendation, not a committed schedule or an approval of
any engineering decision. Priorities and scope can change with user feedback.
`P1` is the next useful product increment, `P2` builds on those workflows, and
`P3` needs additional inputs or a narrower user case. `Proposed` means the
listed increment is not implemented. `Partial` means the named foundation exists
but the remaining work is not complete. This inventory reflects the working
checkout on 2026-10-30, including uncommitted work; it does not claim a release.

## Ordered opportunities

| ID   | Priority | Status   | Capability                                | First user outcome                                                     |
| ---- | -------- | -------- | ----------------------------------------- | ---------------------------------------------------------------------- |
| F-01 | P1       | Partial  | Project review overview                   | Find relevant evidence and see what is missing or stale.               |
| F-02 | P1       | Partial  | Schematic and PCB findings explorer       | Locate more findings on the correct drawing and sheet.                 |
| F-03 | P1       | Partial  | Measured time-series import and plots     | Inspect a retained measurement alongside its units and provenance.     |
| F-04 | P1       | Partial  | BOM-to-design cross-probing               | Select a component and find its supported schematic or board location. |
| F-05 | P2       | Partial  | BOM, variant, and revision comparison     | Explain added, removed, changed, and unresolved parts.                 |
| F-06 | P2       | Partial  | Interactive 3D board review               | Rotate and inspect a retained board model offline.                     |
| F-07 | P2       | Partial  | Mechanical assembly review                | Compare explicitly positioned board and enclosure models.              |
| F-08 | P2       | Partial  | Power, grounding, and connectivity views  | Explore authored relationships and observed nets together.             |
| F-09 | P2       | Partial  | Product and harness views                 | Explore assemblies, interfaces, and variant-specific connections.      |
| F-10 | P2       | Partial  | Verification and release history          | Compare evidence and readiness across revisions.                       |
| F-11 | P2       | Partial  | Import and onboarding review              | Resolve dependencies and missing metadata before adoption.             |
| F-12 | P3       | Partial  | Thermal, signal, and physical-test review | Review explicit measurements or models against authored limits.        |
| F-13 | P3       | Partial  | Review notes and handoff                  | Carry source-bound review observations between collaborators.          |
| F-14 | P3       | Partial  | Supplier and cost analysis                | Compare dated, explicitly sourced offers and quantities.               |

## P1 — Connect evidence to the work

### F-01 — Project review overview

**Foundation:** The working checkout now has an offline, explicit-receipt
[overview](REVIEW_OVERVIEW.md) with source and artifact freshness, drawing and
report links, and CLI/MCP parity. New parts receipts now bind their HTML, text,
and CSV outputs to the saved report through a hash manifest; older parts
receipts still show unknown output freshness. New verification receipts with a
captured input inventory bind the saved summary to checkout inputs and top-level
stage files; receipts without the manifest retain unknown freshness.

**First slice:** Generate one local page for a selected project that links to
chosen schematic/PCB, findings, parts, 3D, simulation, and verification
receipts. Show each item's source revision or hashes, status, and whether it is
missing, stale, unavailable, or of unknown freshness. Start with explicit receipt
selection; do not guess that the most recently written artifact is current.

**Done when:** The same typed service backs CLI and MCP, works with configured
project layouts, and tests cover mixed revisions, missing receipts, changed
artifacts, and projects that do not have every evidence type. The overview does
not turn a set of links into a release or electrical approval.

### F-02 — Expand the findings explorer

**Foundation:** The working checkout has an offline
[findings explorer](FINDINGS_VIEW.md) with zoom, filtering, linked findings,
source-bound PCB DRC markers, supported root schematic geometry markers, and
KiCad 10.0.6 repeated-child-sheet geometry markers with exact source-instance
and SVG title binding. Exact native 10.0.6 fault/control exports now calibrate
ERC item positions to those UUID-bound drawings. ERC for other versions,
schematic parity, ambiguous sheets, and other unsupported locations are retained
without guessed placement.

**First slice:** Add exact sheet-instance selection and mapping for hierarchical
schematics, then support ERC markers only after the native coordinate conversion
is demonstrated for each selected KiCad version. Preserve every finding when
the sheet, location, or transformation cannot be verified.

**Done when:** Fault/control fixtures include reused child sheets, missing and
ambiguous locations, and exact-version native SVG/report comparisons; CLI and
MCP return equivalent evidence and dispositions. Keep current limitations
visible until each specific mapping is supported.

**Current slice:** ERC items from exact KiCad 10.0.6 reports now map only when
the source, coordinate unit, UUID sheet path, drawing frame, and source hash all
match. A native fault/control test checks the 100:1 report-to-SVG conversion;
saved-receipt and CLI/MCP tests retain unmapped wrong-sheet findings. Versions
10.0.0 and 10.0.5 remain uncalibrated for ERC marker placement.

### F-03 — Measured time-series import and plots

**Foundation:** [Waveform charts](WAVEFORM_CHARTS.md) render retained ngspice
transient and AC data. They do not import generic measurements.

**First slice:** Import a bounded local CSV with an explicitly selected time
column, channel columns, units, and source identity; produce an offline plot
and full-precision data receipt. Require the user to specify how time is
interpreted; surface invalid, missing, non-finite, or unordered samples.

**Done when:** A retained source hash, column/unit mapping, and import errors
are reviewable; CLI and MCP use the same service; synthetic timestamp, unit,
large-file, and malformed-input cases are covered. Do not infer acceptance
limits or claim that a simulated trace is a physical measurement. Interactive
overlays and cross-run alignment can follow the single-file slice.

**Current slice:** `measured-series` imports one project-owned CSV into an
ignored `build/measured-series/` receipt. It retains original bytes, the source
hash, explicit mappings, full-precision normalized data, static PNG/SVG plots,
and any validation error. `measured-comparison` now overlays two explicit saved
receipts with absolute or elapsed time alignment, exact unit matching, source
freshness, retained full CSVs, show/hide controls, and hover values from a
bounded extrema-preserving display. Interpolation and acceptance comparisons
remain future work.

### F-04 — Cross-probe BOM and design

**Foundation:** Parts preparation has a searchable checklist, grouped quantities,
findings, and a review BOM. It does not select a matching board location.
Exact source-bound location discovery builds on F-02's drawing review work.

**Current slice:** [BOM cross-probing](CROSS_PROBE.md) joins explicit, matching
parts and findings-view receipts into a searchable offline component table with
reversible front-board and verified sheet-instance markers. It retains exact source
coordinates for multi-unit and hierarchical symbols and keeps duplicate, DNP,
excluded, unplaced, unsupported, and back-side cases visible. The selected
receipts have no common variant identity, so variant parity remains unknown.
Exact KiCad 10.0.6 sheet bindings support reused child drawings; missing or
ambiguous bindings retain source coordinates without a marker.

**First slice:** From a source-matched parts review, select a unique fitted
reference and navigate to its supported board or schematic location; allow the
reverse navigation where exact identity is available. Keep duplicate,
unplaced, excluded, and unsupported references visible without assigning an
ambiguous location.

**Done when:** Matched and unmatched references, DNP/exclusion, multi-unit or
hierarchical symbols, changed source, and differing variants have focused
tests. A part match is a navigation aid, not approval of the part or footprint.

## P2 — Compare and connect engineering views

### F-05 — BOM, variant, and revision comparison

**First slice:** Compare two explicitly selected, source-bound parts or product
BOM snapshots. Show reference, part identity/revision, population, and quantity
changes, with separate unresolved and excluded rows. Existing variant BOM
generation remains the input rather than a second variant model.

**Done when:** The comparison rejects or clearly labels incompatible project,
variant, or source scopes; tests cover added/removed parts, changed identities,
DNP, duplicate references, and quantity changes. It does not approve substitutes.

**Current slice:** [BOM comparison](BOM_COMPARISON.md) compares two explicit
source-bound parts receipts, with reference and grouped quantity changes and
separate DNP, excluded, and unresolved rows. Parts receipts do not record a
variant identity, so that scope remains labeled unknown. The same guide now
documents a separate comparison of two authored variants in one indexed product
revision. It retains their product visual reviews, compares included, omitted,
and unresolved instance paths, and uses the canonical product BOM rows for
grouped quantity differences. Cross-revision product snapshots and observed
board-variant population remain future work.

### F-06 — Interactive 3D board review

**Foundation:** The current [3D workflow](3D_VIEWS.md) produces named images,
STEP, GLB, and an offline gallery.

**Current slice:** A retained, structurally valid, self-contained GLB now gets
a hash-bound offline viewer snapshot with rotation, pan, zoom, fit, orientation
buttons, keyboard access, model-coverage notes, source hashes, and links back to
the original exports. Missing or corrupt GLBs are excluded; GLBs with external
resources stay downloadable without an offline viewer. A representative small
board fixture and failure cases are covered by focused tests. An opt-in real
browser check opens that GLB offline and exercises the view, zoom, and keyboard
controls. Native board and browser interaction on a real project remain to be
exercised.

**First slice:** Open the retained, hash-checked GLB in a local offline viewer
with rotate, pan, zoom, fit, and orientation controls. Report missing models
and retain links to the original exports and their source identity.

**Done when:** A small representative board, missing/corrupt GLB, and missing
models are exercised; the viewer has keyboard-accessible controls and no
unreviewed runtime network dependency. The view does not establish physical fit.

### F-07 — Mechanical assembly review

**Depends on:** F-06 and a project-owned model/placement contract.

**Current slice:** [Mechanical assembly review](ASSEMBLY_REVIEW.md) joins an
explicit current board 3D receipt with a project-owned, hash-bound enclosure
GLB and named-frame rigid placement. One offline viewer shows both models in
declared millimeters or meters, with visibility and camera controls. Missing,
stale, unsupported, or unplaced enclosure geometry yields an incomplete
board-only review. The view does not calculate interference or clearance;
an opt-in real-browser check exercises a meter-scale enclosure panel alongside
the board and its visibility control. Representative native enclosure fit remains
open.

**First slice:** Display an explicitly selected enclosure or adjacent assembly
with the board using declared units, coordinate frames, placement transforms,
and source hashes. Make unknown placement or absent models visible.

**Done when:** Unit/transform mismatches and stale or incomplete geometry are
rejected or reported; a known interference and a clear control are tested for
any supported interference calculation. The report states which geometry and
clearances were assessed and does not certify mechanical fit.

### F-08 — Power, grounding, and connectivity views

**First slice:** Render a bounded graph or table for one selected net or one
authored power/ground relationship, connecting explicit project intent with
source-bound observed pins and components. Show missing or unreviewed links.

**Done when:** Tests cover ambiguous labels, separate grounds, unconnected pins,
stale native evidence, and incomplete project maps. Do not derive required
power topology or common grounds solely from signal names.

**Current slice:** [Grounding view](GROUNDING_VIEW.md) compares one exact
authored ground domain with retained, hash-bound native netlist membership.
Missing evidence stays unreviewed; ambiguous, different, unconnected, and
undeclared pins are separated. [Power-tree view](POWER_TREE_VIEW.md) now places
one authored source-group → rail → load map beside exact observed pin membership
and optional authored current-budget checks. It marks the saved analysis source
as current, stale, unknown, or unavailable against the selected checkout.
Broader connectivity tracing, observed current, and PCB copper paths remain.

### F-09 — Product, assembly, and harness views

**Current slice:** [Product visual review](PRODUCT_VISUAL.md) renders one
selected variant's expanded hierarchy, authored relation cards, interface
endpoints, and canonical harness schedule. Omitted instances and unresolved
references remain visible, while broken source contracts prevent a canonical
system or harness projection. The receipt retains product and cross-project
source identities. Observed wiring and interactive system-wide tracing remain
future work.

**First slice:** Visualize one product variant's authored assembly hierarchy and
interface or harness connections, using the existing product view and harness
schedule outputs. Include endpoint identities and unresolved references.

**Done when:** Variants, omitted components, broken references, and cross-project
source identities have tests; the view distinguishes authored relationships
from observed wiring and retains links to the underlying records.

### F-10 — Verification and release history

**Depends on:** F-01's explicit receipt and freshness model.

**Current slice:** [Verification history](VERIFICATION_HISTORY.md) compares
two explicitly chosen saved project overviews, retaining source and manifest
hashes, selected receipt integrity, individual native check and verification
stage states, findings fingerprints, and optional declared release artifacts.
It marks each snapshot against the current checkout separately from its
capture-time freshness. A missing findings receipt cannot create a false
resolved finding. New verification receipts carry checkout input and stage-file
hashes for the overview; historical receipts without those hashes remain
unknown. History rechecks a captured verification manifest and its outputs
before showing stage deltas. Release readiness trends remain open.

**First slice:** Compare two explicitly chosen revision snapshots and show
changes in checks, findings, source, and available release artifacts. Keep
`NOT_RUN`, missing, stale, failed, and passed states distinct.

**Done when:** Cross-revision and missing-evidence cases are reproducible,
fingerprint changes are explained, and a comparison cannot imply that a
historical check applies to the current revision. Packaging and approval
remain separate operations.

### F-11 — Import and onboarding review

**Current slice:** [Import review](IMPORT_REVIEW.md) turns the existing dry-run
import and diagnostics into an offline file, CAD dependency, toolchain, and
action view. A saved preview can guard a later explicit import; changed source
or repository configuration stops the copy. Native toolchain asset presence and
independent electrical expectations still require their own project-owned
review and checks.

**First slice:** Extend the existing scan/import preview to summarize one
design's source files, library/model dependencies, declared toolchain, missing
inputs, and review actions before an explicit import. Show unsupported formats
and unresolved paths rather than silently repairing them.

**Done when:** A representative supported import, missing dependencies,
conflicting IDs, nonportable paths, and a source change between preview and
apply are tested. Project source and project-owned expectations remain under
the project repository's control.

## P3 — Extend review to additional evidence and handoffs

### F-12 — Thermal, signal, and physical-test review

**Depends on:** F-03 for measured series and project-authored requirements.

**Current slice:** `physical-voltage` compares every retained sample of one
saved voltage channel against an optional project-authored envelope. It plots
the series and applicable bounds, shows capture and requirement conditions,
and distinguishes missing limits, mismatches, unsupported types, and stale
inputs. See [physical voltage review](PHYSICAL_VOLTAGE.md). Thermal and signal
integrity cases still need representative inputs and defined decisions.

**First slice:** Select one concrete measurement or model type and display its
data, units, conditions, source, and explicitly authored limits. Report absent
requirements and unsupported coverage as such.

**Done when:** Unit/condition mismatches, missing limits, stale inputs, and a
failing measurement are tested against a valid control. Expand to additional
domains only when representative inputs and a defined review decision exist.

### F-13 — Source-bound review notes and handoff

**Current slice:** `review-handoff` selects two saved overview revisions and
exact finding fingerprints, then packages hash-verified overview and findings
receipts, available drawings, source identity, and project-owned attributed
notes. It marks missing evidence, outdated note scope, and conflicting
assessments without editing the notes. See [review handoff](REVIEW_HANDOFF.md).

**First slice:** Export a portable review packet containing selected findings,
evidence links, source identity, and clearly attributed reviewer notes. Make a
note's scope and any stale fingerprint visible when reopened.

**Done when:** Two revisions, missing evidence, and conflicting or outdated
notes are tested. Keep writing reviewed decisions to project-owned records an
explicit operation; a note is not an electrical or release approval.

### F-14 — Supplier and cost analysis

**Current slice:** `supplier-analysis` compares two explicit saved sourcing
snapshots for one source-bound parts receipt. It shows offer age, catalog
validation, currency, quantity breaks, packaging-adjusted quantities,
unavailable prices, and unresolved BOM references without currency conversion
or supplier access. See [supplier analysis](SUPPLIER_ANALYSIS.md).

**First slice:** Compare explicitly selected, dated supplier snapshots for a
reviewed BOM with currency, quantity breaks, packaging, and unavailable fields
shown. Reuse existing parts and sourcing records.

**Done when:** Tests cover stale offers, mixed currencies, packaging minimums,
missing prices, and unresolved part identities. No live availability, order,
substitution, or purchasing approval is implied.

## Shared delivery criteria

Every feature should identify its user decision, owned service, source and
tool identity, supported and missing coverage, and project-owned inputs.
Where both CLI and MCP expose it, they should call the same typed service and
have a parity test or a documented exception. Use separate synthetic fixtures
for fault and valid-control cases; add exact-native tests when correctness
depends on a KiCad export. Keep generated receipts under ignored `build/`
directories and validate representative workflows in a separate project
checkout. Any live editor integration, hosted sharing, supplier submission, or
other external side effect requires its own explicit design and permissions.
