# Design-lint data routing decision: I²C pull-up pilot

This decision fixes the input boundary for one existing sniffer family before
reorganizing modules or changing report schemas. It uses the I²C pull-up hints
because they consume both a native netlist and a source-bound account of a
project-authored electrical requirement. The pilot changes routing only; it
does not add a rule or change an engineering conclusion.

## Current route

1. `design_lint_project_inspection.py` reads the project manifest and checks
   contract, records their hashes, and obtains a `ContractCoachReport` from the
   selected native summary. A ready report contains the observed
   `NetlistContract`, source hashes, netlist hash, and native command evidence.
2. `design_lint_project_contexts.py` derives
   `I2cPullupHeuristicCoverage` from the exact electrical contract and that
   netlist. It records contract path/hash when present, netlist hash, coverage
   status, and per-bus entries. It distinguishes an absent, pending, reviewed,
   or not-applicable electrical requirement.
3. `design_lint_evaluation_preparation.py` passes source-bound I²C coverage,
   including an empty `COMPLETE` result, and the coach's netlist hash to
   `resolve_i2c_pullup_coverage` in one typed request. A mismatch blocks the
   evaluation before candidate scanning. It then builds the complete
   `DesignLintCandidateInputs` bundle from normalized coverage,
   policy, and one `PeerDesignLintEvidence` scan, retaining both as typed
   records on `DesignLintEvaluationPreparation`.
4. `design_lint_evaluation_candidates.py` passes the prepared bundle directly
   to `scan_candidate_result()`. The public `candidates()` compatibility
   adapter constructs the same capability groups from its legacy arguments;
   both routes reach the shared scanner.
5. The I²C predicate emits `Candidate` records. Catalog validation, project
   modes, exact ignores, fingerprints, and report assembly occur after scanning.
   The report and reconciliation retain source identity and review state.

## Data to route into the theme

| Input                     | Producer and owner                  | I²C pull-up use                                                                                      | Absence or mismatch                                                                |
| ------------------------- | ----------------------------------- | ---------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| Run identity              | Project inspection and native coach | Kept in the report envelope; binds source, native summary, and catalog                               | Missing source or native proof blocks before scanning                              |
| Observed netlist          | Native coach as `NetlistContract`   | Required for local resistor, pin, and net topology                                                   | No ready netlist means no predicate run                                            |
| Project electrical intent | Project-owned electrical contract   | Read by the coverage producer, never inferred by the predicate                                       | Absent/pending/not-applicable remain distinct coverage states                      |
| Pull-up coverage          | `I2cPullupHeuristicCoverage`        | Required typed input at the theme boundary; can suppress a hint only with matching reviewed coverage | Stale source-bound coverage blocks before scanning; `NOT_CONFIGURED` is not a pass |
| Candidate output          | I²C predicate                       | Stable rule ID, subject, message, and exact evidence                                                 | Unknown active rule ID fails catalog validation                                    |

**Decision:** the first theme input is a frozen typed
`I2cPullupSnifferInput` containing `observed: NetlistContract` and
`coverage: I2cPullupHeuristicCoverage`. The coverage field is required at this
boundary; project inspection already produces a status-bearing record. The
predicate does not receive the whole project config, filesystem root, native
runner, or an untyped bag of optional evidence. Source and tool provenance stay
in the run/report envelope and the coverage record rather than being copied
into each rule's inputs.

The existing public `candidates()` and `evaluate()` signatures remain as
compatibility adapters during the pilot. The public candidate adapter
constructs typed theme inputs from its legacy arguments; full evaluation builds
the same required groups from prepared coverage and project policy. Both reach
the same scanner, and the bus group carries independent I²C pull-up and address
records through `BusCandidateInputs`. Each I²C predicate consumes its own
input directly. This step does not add another parameter to either central
signature.

## Evidence and decision rules

- `NOT_CONFIGURED`, `PENDING`, `NOT_APPLICABLE`, `COMPLETE`, `OPEN`, and
  `BLOCKED` are coverage states, not interchangeable Boolean values. Preserve
  the existing predicate behavior for each state during the pilot.
- A `COVERED` decision can occur only in `COMPLETE` or `OPEN` coverage. The
  latter can include both covered and open entries. Evaluation blocks a record
  that combines a covered decision with an unresolved state before the
  decision can suppress a review prompt. Older contradictory records remain
  parseable for diagnosis.
- `COMPLETE` is a positive scan result even when it has no hint entries. The
  producer retains the native netlist hash in that case; evaluation blocks a
  missing or stale hash before accepting the result. Older serialized records
  remain readable, but an unbound `COMPLETE` result cannot authorize a current
  evaluation.
- A covered pull-up or voltage entry must identify the electrical contract by
  path and digest before evaluation can use it. Project inspection reads and
  rechecks those bytes during the run. The lower-level evaluator has no project
  root, so it requires the identity but relies on its caller to verify that
  identity against the current contract.
- The I²C rule remains a review heuristic when no reviewed requirement covers
  it. A project-authored, source-matched requirement may supply coverage; it
  does not turn an inferred net name into a requirement.
- The low-equivalent-resistance scan returns one named observation per
  affected line, with its typed resistor paths and numeric effective
  resistance, plus explicit SDA and SCL pin tuples. All four I²C pull-up
  candidate rules retain their typed source record on `I2cPullupCandidate`.
  `project_i2c_pullup_evidence` is the single owner of the current string-keyed
  report projection; it preserves line order, pins, formatted values, and
  fingerprints. Internal candidate scans import the typed owner directly;
  `bus_heuristics.py` re-exports a small compatibility adapter for the former
  map-shaped low-resistance result.
- `Candidate.evidence` remains the immutable wire projection used by existing
  report serialization and fingerprint normalization. For I²C pull-up rules,
  the retained typed source record is authoritative and the map is derived.
  Other themes still need this source-to-wire pattern. Changing the public
  evidence shape or fingerprint input requires an explicit versioned migration.
- I²C pull-up, I²C address, and USB data-path projections use the shared
  `CandidateEvidenceProjection` from `design_lint_types.py`. Theme owners still
  control the source-to-field mapping; the shared type freezes the rule ID and
  report fields before they reach the generic candidate boundary.
- An optional `None` at the compatibility API means legacy callers did not
  provide coverage. Normalize it to an explicit `NOT_CONFIGURED` coverage
  record before entering the new theme service. New theme inputs should not
  use `None` to hide missing, pending, or stale evidence.

## Pilot acceptance

Before and after routing, compare the same fault, valid control, absent
requirement, pending requirement, and stale-hash cases. The candidate tuples,
fingerprints, report JSON, and disposition statuses must retain their current
meaning. Exercise the focused I²C synthetic suite and exact native fixture
lane where available, then the catalog and CLI/MCP parity slices. Keep the
pilot in the I²C theme and its coordinator; avoid unrelated module or report
reorganization.

The typed predicate is an implementation owner, not a thin facade. Apply the
existing focused implementation limit to it; use the stricter facade review
limit for a coordinator whose job is only dispatch. A few lines of typed
routing are not a reason to split a cohesive predicate.

## Pilot comparison

The typed route landed in `6f7d968f`. On 2026-10-29, the pre-pilot
`i2c_pullup_candidates` predicate from `6f7d968f^` was run against the same
inputs as the typed theme predicate. A one-time migration check compared the
complete candidate records, their exact fingerprints, and full report JSON
after substituting each predicate into the same evaluation path. The compared
cases were missing pull-ups, both lines fitted, no configured requirement,
pending requirement, not-applicable requirement, reviewed array requirement,
and stale netlist hash. All seven matched; the stale case remained `BLOCKED`.
The check used the current evaluation path for both runs, so it verifies the
predicate migration and its routing, not unrelated changes between whole
checkouts.

The focused synthetic, CLI/MCP parity, architecture, Ruff, and Pyright checks
also passed for the I²C tranche. Keep the existing rule fixtures as the durable
behavior regressions; the historical comparison was a migration check.

The shared scanner now requires connector, component, control, power, bus,
peer, mapped-coverage, and PCB groups. Continue moving direct callers to the
smallest stable theme records their predicates need; do not replace the group
boundary with a global context of optional scans.

## Evaluation request route

Source-bound project inspection now constructs one `DesignLintEvaluationRequest`
and calls `design_lint_evaluator.evaluate_request`. The public
`evaluate(...)` compatibility function packs its established arguments into
the same request and delegates to that operation. Coverage that belongs to a
shared family travels in `ComponentMapCoverageInputs`, `PeerDesignLintScanInputs`,
`PcbInputCoverageInputs`, or `PcbMappedCoverageInputs`; candidate preparation,
catalog validation, disposition, and report assembly then use the same path.
This migration leaves the report contract and the legacy callable signature
unchanged. The inspection architecture test keeps the old adapter confined to
the public `design_lint.py` facade so new internal callers use the typed route.

The scanner forwards the bus record to its owner, adding only component-peer
findings computed during that scan. It does not reconstruct the record from a
fixed list of fields, so newly added bus evidence is not silently lost between
the typed scanner and the bus coordinator. The shared observed netlist and
reviewed connector scope must still agree at the scanner boundary.
The peer coordinator receives one `PeerCandidateScanInputs` record. It combines
the typed peer group with the shared observed netlist, SPI roster, reviewed
connector scope, and `UsbDataPathCandidateInputs`. That USB-owned immutable
record pairs the authored map with its canonical digest; peer and mapped-path
candidate services receive the same instance. Candidate aggregation computes
the digest through `usb_data_path_models.usb_data_path_map_sha256`, which USB
peer coverage and mapped-topology coverage also use. Candidate and coverage
evidence therefore identify the same serialized map content. The coordinator
consumes the request directly; its older multi-argument function remains a
compatibility adapter.
The record and peer evidence group are owned by `design_lint_peer_inputs.py`,
while the older candidate-bundle import remains an identity-compatible
re-export.
Mapped electrical coverage is passed as its own typed group to its coordinator;
the USB and power maps remain explicit shared inputs. Adding a field to either
group does not require rebuilding that group in the central scanner.

## PCB input-geometry coverage route

Signal-path, keepout, RF-antenna, and touch-pad clearance reports now enter
evaluation together as `PcbInputCoverageInputs`, owned by
`design_lint_pcb_geometry_coverage_policy`. The public evaluator remains a
compatibility adapter and packs its existing parameters into this record.
Preparation passes it intact to the policy owner, which binds positive reports
to the current authored map and native board/source identity before the records
reach candidate scanning and report assembly.

At this boundary, `None` means no supplied scan report. The policy owner
resolves that against the authored map: a configured map without a report is
`BLOCKED`, while no map and no report remains `NOT_REQUESTED`. An explicit
`NOT_REQUESTED` or `DISABLED` report cannot stand in for missing configured-map
evidence. This preserves the existing source and absence semantics while
removing four separate optional fields from the central evaluation request.

The mapped checks use a second group, `PcbMappedCoverageInputs`, owned by
`design_lint_pcb_coverage_policy`. It carries differential-pair,
switching-loop, reference-plane, and protection-path reports. Each report
retains its own authored-map digest and coverage status; the policy owner
checks that identity and the retained board/source identity before positive
coverage can reach candidate generation. Missing inputs remain optional at
this boundary so the owner can resolve absence against each check's own map
and mode.

## I²C address candidate route

The other I²C sniffers share the native netlist but have different authority
and absence rules. Their inputs stay distinct at the candidate boundary:

| Consumer                       | Current producer and input                                                                                                                   | Absence or stale meaning                                                                                                                         |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Address mismatch and collision | `resolve_component_map_coverage` compares the project policy's `I2cAddressMap` to the native netlist and produces `I2cAddressCoverageReport` | No map is `NOT_REQUESTED`; missing or stale native hash is `BLOCKED`; only complete entries can establish a static-address mismatch or collision |
| Unmapped responder hint        | Native pin-function inventory plus the project policy's address map                                                                          | An absent map still produces a review hint and is named as `not_configured` in candidate evidence; it is not a successful address check          |
| Peer reference hint            | `scan_i2c_peer_references` derives a native topology scan; component-peer findings prevent duplicate prompts                                 | An empty scan is a valid observed result; incomplete reference evidence remains a review prompt, not a grounding conclusion                      |

**Decision:** `BLOCKED` and `NOT_REQUESTED` address coverage entries cannot
produce mismatch or collision candidates. A blocked report may retain entries
for diagnosis, but they are not authoritative observations. `INCOMPLETE`
coverage can still contain complete entries whose comparisons are valid;
incomplete entries remain coverage gaps. The unmapped-responder heuristic
continues to emit a review prompt when no map exists, and peer-scan duplicate
suppression remains separate.

If a project map is configured but a supplied address coverage report says
`NOT_REQUESTED`, evaluation changes that report to `BLOCKED` with an explicit
missing-comparison issue. A caller cannot turn a configured authored check into
a pass by providing an empty coverage record.

The address-map scanner already consumes a typed `I2cAddressMap`, a typed
native `NetlistContract`, and the netlist digest. The coverage resolver checks
freshness and absence before candidates run. Candidate aggregation now groups
the observed netlist, project map, and resolved coverage into a frozen
`I2cAddressCandidateInput`, and pairs it with the separately typed pull-up
input in `BusCandidateInputs`. The bus boundary rejects mixed native netlists.
The I²C address theme uses it for map mismatch/collision and unmapped-responder
prompts in their existing order. Missing coverage at the public `candidates()`
compatibility boundary becomes explicit `NOT_REQUESTED`; full evaluation still
normalizes a configured map with that state to `BLOCKED`. The public candidate
and report shapes, fingerprints, and central parameter counts remain stable.

Peer reference scans and pull-up coverage remain separate typed routes; their
different evidence and authority rules do not belong in an all-optional I²C
context. Prepared evaluation now carries these records into the same scanner
without expanding central compatibility signatures.

Address mismatch and collision candidates now retain the source-bound coverage
report with the exact eligible entries. Unmapped-responder candidates retain
the named native responder scan record and the map state used for discovery.
`project_i2c_address_evidence` owns the existing string-keyed report projection;
the candidate constructor verifies its rule ID and fields against that typed
source. `BLOCKED` and `NOT_REQUESTED` reports remain ineligible for mismatch
and collision candidates.

The public `candidates()` adapter retains its named legacy keyword inputs in
`LegacyCandidateArguments` while keeping the Python signature compact. Full
evaluation builds the grouped scanner inputs from
`DesignLintEvaluationPreparation`, whose coverage has already been
source-checked. Continue migrating direct consumers by capability group.
Direct `candidates()` calls remain unverified observations unless the caller
supplies and validates the relevant source identity.

Candidate registration has one shared check: after all theme, native, and
rule-specific candidates are collected, every rule ID must be active in the
packaged catalog before project modes and ignores are applied. This prevents
new extension paths appended outside the compatibility aggregator from
reaching disposition with an unknown rule ID.

Peer-reference coverage has a related boundary. Four protocol rule owners now
attach typed bus, clock, or pair identities to their internal candidates. A
candidate checks that its typed identity and serialized evidence agree at
construction. The shared candidate copies and freezes the established evidence
mapping, so later mutation cannot change either its coverage identity or
fingerprint. `PeerReferenceCandidateKeys` collects typed identities for
coverage; a candidate with the right rule ID but no typed identity fails before
disposition. The public finding evidence and fingerprint stay the same. The
broader extension path should formalize typed theme results rather than adding
metadata fields to the shared candidate type for each new rule.

The I²C, SPI, CAN, and RS-485 peer-reference adapters now use typed candidate
subtypes that retain their scan and bus/pair review while deriving
identity-owned wire fields through `project_peer_reference_identity()`.
`PeerReferenceCandidate.from_identity()` remains a compatibility constructor,
but no active peer-reference adapter relies on it. Supplemental evidence is
merged only after identity fields are reserved, so a producer cannot supply
conflicting values. The named `PeerReferenceIdentityProjection` keeps those
fields read-only; the candidate adapter projects them into the established
evidence mapping, which `Candidate` copies and freezes before report
serialization. The source-owning I²C and USB routes also use the shared
`CandidateEvidenceProjection`; remaining per-rule evidence fields still use
the established string-keyed map and need their own staged migration by theme.

The component-peer identity helper now returns a named
`ComponentPeerPinIdentityContext` instead of a positional tuple containing an
unstructured evidence map. Its typed identity and message fields are the
authoritative internal record; the `evidence` property projects the established
`peer_group_*` and exact-symbol fields into the unchanged finding payload.
Part-ID and exact-symbol cases are covered separately so their authority and
serialized fields remain distinct.

Component-peer assignment checks now enter through
`ComponentPeerCandidateInputs` and return a `ComponentPeerCandidateResult`.
Its `ComponentPeerPinFindingCounts` summary is consumed by the component-peer
coverage owner directly; coverage no longer counts component findings by
scanning the full flattened candidate list. The aggregate scan verifies that
the component-owned counts still match the combined findings, and report
validation independently reconciles those findings with published coverage.
The keyword-based component-peer candidate function remains an adapter for
direct callers.

Mapped-coverage scanning receives `MappedCoverageCandidateInputs` and returns
`MappedCoverageCandidateResult`, which provides USB data-path, power-path, and
power-sequence finding counts. Component scanning receives
`ComponentTopologyCandidateInputs` and returns `ComponentCandidateScanResult`
with the oscillator-path count. Candidate aggregation combines those named
counts as `MappedTopologyFindingCounts`; the aggregate scan checks them against
its combined candidates. The report validator separately checks mapped-check
counts against its complete finding list.

## Peer scan context route

The peer evidence coordinator receives digital-voltage, serial-peer, and
RS-485 project contexts together as `PeerDesignLintScanInputs`. Each context
retains its own authored state and source provenance. An absent context remains
`None` in the request and is normalized by the owner to its existing
`not_configured` context; pending and not-applicable records retain their
distinct states. The observed netlist, netlist digest, connector scope, and
USB data-path map remain explicit coordinator inputs, and the resulting scans
flow into the prepared peer and bus candidate groups.

Candidate assembly is a separate route: it passes
`PeerCandidateScanInputs` to the peer candidate coordinator. That record keeps
the observed netlist, prepared peer scans, reviewed connector references, SPI
roster, and `UsbDataPathCandidateInputs` together. The USB-owned record binds
the authored map to its canonical digest; peer and mapped-path candidates
consume the same instance.

The serial reference scanner builds its native pin, component, symbol,
footprint, pin-number, and DNP indexes as one `SerialPeerPinIndex` derived from
the supplied `NetlistContract`. The scanner passes named index fields to its
reference-domain and map-matching owners instead of destructuring a six-item
tuple, keeping those correlated observations together for the scan.

Connector alias scans share `complete_connector_footprint_peer_pin_inventory`
and now receive a `ConnectorFootprintPeerPinInventory` with common pin numbers
and each reference's native display-number map. Both mapping levels are
read-only; incomplete or ambiguous inventories still return `None` and cannot
be promoted to a complete comparison.

## External-protection source admission

Evaluation sends the supplied `ExternalProtectionCoverageReport` and the
coach's current netlist digest to `resolve_external_protection_coverage` as
one `ExternalProtectionCoverageRequest`. The owner checks source binding only
for positive scan states. A stale or unavailable digest produces `BLOCKED`
coverage, retains the report's scope, recorded digest, and electrical-contract
identity, and withholds rows from candidate generation. An absent report
remains `NOT_REQUESTED`; an already blocked report retains its existing issue.
The resolver returns the blocked report and binding issue together so report
assembly and early-blocked dispositions use the same result.

## Control-input and I²C pull-up source admission

Control-input bias and I²C pull-up coverage each enter their theme owner with
the coach's current netlist digest in a typed request. Their resolvers preserve
`None` as absent coverage, retain a supplied report unchanged when it is
admissible, and return a blocked report with the original contract and netlist
identity when binding fails. Blocked reports omit candidate-resolution rows;
the caller then creates the existing early blocked evaluation report. The two
owners keep their different validity rules for `COMPLETE`, `OPEN`, pending,
not-applicable, and not-configured coverage.

## Control-input candidate route

| Input or output   | Owner                                                     | Meaning at the theme boundary                                                                                                                                          |
| ----------------- | --------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Observed topology | Native coach's `NetlistContract`                          | Required; the shared scanner rejects a different observation from the bus or control group.                                                                            |
| Bias coverage     | Project context and `resolve_control_input_bias_coverage` | The project electrical contract can cover a bias hint. Missing legacy input remains absent; stale, unbound, or blocked coverage stops full evaluation before scanning. |
| Control result    | `design_lint_control_candidates`                          | `ControlCandidateResult` returns findings and normalized unconnected pin keys. Candidates retain their typed source records.                                           |

The scanner passes `ControlCandidateInputs` directly to the theme and consumes
the named result. The older `control_candidates()` tuple interface remains an
adapter, as do the central compatibility signatures. Full evaluation validates
coverage identity before the theme sees it; a direct caller of either candidate
API must establish source identity itself. Candidate order, evidence,
fingerprints, and serialized reports remain unchanged by this routing change.
The candidate builder keeps `UnconnectedControlInput`, `ControlInputBiasGap`,
and `OpenOutputBiasGap` records on their candidates. The theme-owned
`design_lint_control_candidate_evidence` module projects these sources into the
existing evidence fields and checks that the rule ID and fields stay aligned.
This preserves useful typed scan data internally without changing report
serialization.

## IC decoupling candidate route

- **Project-authored intent:** `DesignLintPolicy.ic_decoupling_map` carries an
  `IcDecouplingMap` with exact IC identity, power pin and nets, mapped
  capacitors, and minimum nominal capacitance. Those fields are not inferred
  from net names.
- **Observed electrical data:** the native coach's `NetlistContract` supplies
  component identity, pin inventory and type, net assignment, DNP state, and
  capacitor values for comparison.
- **Requirement review:**
  `design_lint_power_decoupling._review_requirement` returns named mapping
  issues and per-capacitor values. Unknown capacitance remains explicit as
  `None`.
- **Candidate:** `ic_decoupling_candidates` retains the existing evidence keys
  and requirement digest. The result reports nominal comparisons and does not
  claim physical adequacy.

The private review result is `_IcDecouplingRequirementReview`, containing
`_IcDecouplingCapacitorValue` records. It replaces a nested tuple whose
positions combined mapping faults with capacitor measurements. Candidate
evidence still projects to the established JSON mapping, so this internal
route does not change the report schema or fingerprint.

## Capacitor hold-up candidate route

- **Project-authored intent:** `DesignLintPolicy.capacitor_hold_up_map` names
  one exact capacitor or a primary capacitor plus explicitly declared parallel
  members. Each member has an exact PART_ID, native value, symbol, footprint,
  and pin pair; all members must match the same authored positive/return nets,
  operating voltage window, maximum constant-current load, and minimum time.
- **Observed electrical data:** the native `NetlistContract` supplies the
  current component identity, DNP state, pin inventory, pin assignments, and
  nominal value. Shared `parse_capacitance_pf` handles the bounded capacitor
  unit set, including mF and F.
- **Requirement check:** `capacitor_hold_up_checks.assess_capacitor_hold_up`
  reports exact source mismatches and computes the ideal constant-current
  estimate with decimal arithmetic. The calculation does not infer component
  intent or operating bounds.
- **Candidate:** `design_lint_power_capacitor_hold_up` retains the current
  netlist, typed requirement map, measured nominal capacitance, estimate, and
  map digest. It sums supported values for all fitted mapped members; a missing
  or DNP member leaves the numeric estimate unavailable. Findings are REVIEW
  by default; the configured policy controls promotion or suppression.

The model does not infer additional bank members and does not establish PCB
copper continuity. Tolerance, voltage dependence, ESR, leakage, load
transients, charging, lifetime, ratings, and the upstream/downstream power path
need separate reviewed inputs and checks.

## PCB measurement and requirement candidate route

| Input or output             | Owner                                                                                              | Meaning at the candidate boundary                                                                                                                                                  |
| --------------------------- | -------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Project maps and policy     | Project-owned contract, normalized by `design_lint_pcb_coverage_policy` and evaluation preparation | A configured but unavailable or mismatched scan is represented by its coverage status and issue; an off rule is disabled, not measured.                                            |
| Native PCB and DRC evidence | Geometry and DRC capture services                                                                  | Coverage records carry the applicable source, receipt, and map identities; the candidate translators do not run native tools.                                                      |
| PCB coverage group          | `design_lint_pcb_inputs.PcbCandidateInputs`                                                        | The scanner passes the same typed group to the measurement and requirement owners. Legacy direct candidate calls may still omit coverage; omission alone is not positive coverage. |
| Candidates                  | PCB measurement and requirement translators                                                        | Existing rule IDs, evidence and fingerprints are retained. `COMPLETE`, `INCOMPLETE`, `BLOCKED`, `DISABLED`, and not-requested meanings remain in their respective reports.         |

The existing keyword-based PCB candidate functions remain callable. The new
typed entry points route the group to those existing translators; they do not
validate file freshness independently. Full project inspection owns source
capture and freshness checks, while prepared evaluation owns map and mode
normalization. Direct callers must establish the evidence identity themselves.

Differential-pair coverage is accepted for a configured, enabled map only
when its retained map digest matches the current authored map. Missing,
disabled, or differently bound coverage becomes `BLOCKED`; scanned coverage
without a current map is also blocked. Project policy can explicitly turn the
rule off, which produces `DISABLED` instead of claiming coverage.
An explicit `off` override takes precedence even when no authored map exists.
The prepared evaluation also checks the retained source-inventory digest and
the project, board, and rules identities against the current coach inventory.
Signal-path coverage uses the same source check and map binding before its
findings are translated. This check covers scanned `COMPLETE` and `INCOMPLETE`
reports; an explicitly disabled rule remains `DISABLED`.
Keepout, RF antenna, and touch-pad geometry coverage follow the same map and
board-source checks. Their reports are normalized by the geometry coverage
policy, which blocks scanned reports without a current map or matching board
identity.
Switching-loop, reference-plane, and protection-path coverage use the shared
board-source identity service and mapped-coverage policy. Scanned reports
reach candidate translation only when both their map digest and board
path/hash match the current authored map and coach source inventory. A scanned
report without its map is blocked; explicit `off` overrides disable the route
even when no map is present.

An incomplete differential-pair requirement finding retains both its typed
entry and the complete source-bound DRC coverage report in
`PcbDifferentialPairCoverageFindingEvidence`. Its constructor requires an
`INCOMPLETE` entry contained in an `INCOMPLETE` report. The PCB-owned projector
preserves the established positive/negative nets, selector, basis, uncovered
constraints, and issues; the candidate's report fields and fingerprint remain
unchanged. This retains the map and native source identities behind the
finding without moving freshness checks out of prepared evaluation.

An incomplete signal-path or skew-bundle finding follows the same source route
through `PcbSignalPathCoverageFindingEvidence`, retaining the exact entry and
complete source-bound report. The typed owner validates report membership and
projects the existing basis, uncovered constraints, issues, and bundle path
IDs. Path and bundle subjects remain selected by the translator; finding order,
report evidence, and fingerprints stay stable.

Switching-loop candidates retain the measured loop entry and complete coverage
report in `PcbSwitchingLoopFindingEvidence`; the projector owns the existing
area, route-edge, return-plane, and measurement-boundary fields. A fully
measured loop still produces a finding when no maximum area was authored, so
the source record preserves both that case and incomplete measurements.
`PcbKeepoutFindingEvidence` and `PcbRfAntennaFindingEvidence` retain their
incomplete named-area or module entry with its complete board-bound report.
Their projectors preserve the existing geometry, layer/restriction, module,
feed, and antenna-clearance fields. Each candidate remains a review prompt for
its owning comparison; map freshness and blocked/disabled handling remain in
coverage policy and evaluation preparation.

Touch-pad clearance findings retain their measured or incomplete entry and
full coverage report in `PcbTouchPadClearanceFindingEvidence`; blocked map
coverage uses a separate `PcbBlockedTouchPadClearanceFindingEvidence` record.
The compatibility service delegates to this typed owner, which preserves the
prior measurement and source-receipt fields and public fingerprint.

Touch-pad clearance candidate construction now belongs to
`design_lint_pcb_touch_pad_clearance_candidate_evidence`. Blocked coverage
retains a separate report-level source record; each incomplete or below-minimum
finding retains its exact entry and complete source report, including board,
snapshot, probe, request, and tool identities. The evidence projections keep
the established sparse blocked fields and per-pad receipt fields. The existing
`pcb_touch_pad_clearance.touch_pad_clearance_violations` function remains a
compatibility adapter, while the PCB requirement translator imports the typed
owner directly.

Decoupling, protection-path, track-width, and reference-plane candidates now
retain their exact coverage entry and source-bound report through
`PcbDecouplingFindingEvidence`, `PcbProtectionPathFindingEvidence`,
`PcbTrackWidthFindingEvidence`, and `PcbReferencePlaneFindingEvidence`.
Theme-owned projectors preserve the existing evidence fields and finding
fingerprints. Their candidate rules keep their distinct qualification:
unbounded complete decoupling coverage remains reviewable; protection-path
findings require incomplete coverage; track-width findings include complete
measurements below the authored minimum; reference-plane findings include
tracks below threshold on every measured reference layer, plus endpoint-via
hole context. Complete controls are filtered before constructing finding
records. Map freshness and blocked/disabled normalization remain in prepared
evaluation.

## Schematic geometry source route

The geometry scanner receives one schematic's bytes, repository path, exact
KiCad version, and native-unconnected pin identities. It binds the report to
the source digest and uses `SchematicSourceDocument` to retain decoded text
with its parsed root span. Wire, junction, and label parsers return named
geometry records with unsupported reasons; the scan coordinator routes those
reasons to the owning rule IDs before assembling `COMPLETE`, `PARTIAL`, or
`UNSUPPORTED` results. Candidate and report schemas remain unchanged.

## USB data-path finding evidence route

`UsbDataPathCandidateInputs` keeps the authored USB map and its canonical digest
together. `usb_data_path_mismatches` compares that map with the admitted native
netlist and returns `UsbDataPathMismatch` records. Each internal
`UsbDataPathCandidate` retains one mismatch and the exact map digest in
`UsbDataPathFindingEvidence`; `project_usb_data_path_evidence` is the only
projection to the existing report fields. The public evidence keys, values,
finding order, and fingerprint inputs remain stable. A missing map still emits
no mapped-path finding, and a finding remains a schematic review prompt rather
than proof of component conduction or PCB continuity.

## CAN termination finding evidence route

`can_buses_without_local_termination` and
`can_buses_with_excessive_local_termination` return the named
`CanTerminationGap` and `CanTerminationExcess` records. The internal
`CanTerminationCandidate` retains that scan record; the CAN-owned
`project_can_termination_evidence` function maps it to the established fields
through the shared `CandidateEvidenceProjection`. The message and evidence
remain a schematic review prompt: visible resistor count does not identify
physical bus endpoints or prove external termination.

## CAN peer-assignment finding route

`can_peer_assignment_divergences` returns `CanPeerAssignmentDivergence`
records for complete native CANH/CANL pairs. `CanPeerCandidate` retains each
record, and `project_can_peer_evidence` maps it to the existing report fields.
The candidate builder owns message wording and finding order. Candidate
selection still describes a review prompt: shared pin roles and native net
names do not prove that devices are on one physical bus.

## Unconnected protocol-pin finding route

The I²C, CAN direction, generic SPI/USB-C/CAN pin, USB 2.0 data, SPI data,
SPI clock, and serial scanners each own their protocol qualification and return
a typed source record. `design_lint_unconnected_interface_candidates` keeps
the existing scan order and message wording, while
`UnconnectedInterfaceCandidate` retains each record and
`project_unconnected_interface_evidence` maps it to the stable rule ID and
report fields. The RS-485 and USB-C SBU translators remain specialized owners.
Full evaluation admits one shared native netlist before these scanners run;
the candidate projection itself does not claim protocol use or PCB routing.

## Signal-pair finding route

The complementary-pin scanner returns `ComplementaryLineGap` records with
positive and negative assignments. Their side maps are read-only and typed,
with named accessors for internal consumers; the former `pins` and `nets`
attributes remain available as compatibility mappings. Name-based pairing
returns `NamedDifferentialPair` records. `SignalPairCandidate` retains either
source, and `project_signal_pair_evidence` owns their existing report fields,
including reviewed alias basis and digest. The scan predicates and their
review-only meaning remain unchanged.

## Generic component peer-pin outlier route

`scan_generic_component_peer_pin_assignment_outliers` returns a
`PeerPinAssignmentOutlier` with peer identity, per-reference assignments, the
strict-majority net, outlier pins, and a shared exact-net anchor. The source
record copies and freezes its assignment map. `GenericPeerPinCandidate`
retains that record, and `project_generic_peer_pin_evidence` owns the existing
report fields; the candidate builder continues to own selection and wording.
Repeated symbol or part identity and a shared anchor remain comparison clues,
not evidence that peer pins must connect.

## Component peer-pin evidence routes

The generic split, named split, partially open, and all-open power-input
findings retain distinct typed variants of their `PeerPinAssignmentOutlier`
scan record. The generic split also retains the exact per-peer native pin
functions used in its evidence. Constructors require the matching electrical
role and assignment state; one component-peer projector preserves the existing
rule-specific fields, including conditional PART_ID identity and open-peer
lists. Peer grouping remains a review heuristic and does not assert that
domains must be connected.

Recognized supply/return divergence retains its `PeerPowerPinAssignmentDivergence`
record. Open power-output, signal-output, signal-input, and bidirectional
findings retain their `PeerPinAssignmentOutlier` plus an explicit native-role
variant; the input rule still filters control pins before candidate creation.
Their projectors preserve the role-specific report fields and peer identity.
The component-peer candidate adapter no longer constructs evidence mappings;
selection and wording remain with the theme service, and projection remains
with its theme-owned evidence module.

## Unconnected component power-pin route

The component pin scanner returns `UnconnectedNamedComponentPin` with the
native pin, function, and closed `supply`/`return` category. Generic power
input and output scans return distinct records with literal `power_in` and
`power_out` roles. `UnconnectedComponentPinCandidate` retains any of these
records, and `project_unconnected_component_pin_evidence` derives the existing
rule ID and report fields, including the optional native pin function. The
component and power translators still own selection and wording; report fields
and fingerprints are unchanged.

## LED topology evidence route

The direct rail-bridge scanner and output-driven LED scanner return distinct
typed records. `LedTopologyCandidate` retains either record, while
`project_led_candidate_evidence` owns both established report projections.
Output-driven findings preserve the reviewed LED role binding and validate its
digest before exposing the existing role fields. Component translation still
owns candidate selection and wording; the report fields and fingerprints remain
unchanged.

## Unconnected connector-pin route

The connector pin scanner returns distinct source records for native or
project-mapped named supply/return pins and generic native `power_in` and
`power_out` pins. `UnconnectedConnectorPinCandidate` retains those records;
`project_unconnected_connector_pin_evidence` owns the existing rule IDs and
wire fields. It preserves project-interface role provenance and omits absent
native pin functions. Connector translation still owns suppression,
deduplication, and wording.

## Repeated and generic connector peer-pin routes

Repeated-function comparisons retain their `SimilarConnectorPinGroup` together
with the observed netlist and reviewed pin-role context used to create the
finding. Generic peer outlier and divergence candidates retain their typed
`ConnectorPeerPinAssignmentOutlier` or
`ConnectorPeerPinAssignmentDivergence` record. Their per-reference assignment
maps are copied and frozen at scan time. The connector evidence owner preserves
the existing role-source, peer-identity, outlier, missing-function, and
reviewed-scope fields; grouping and suppression remain in the connector
translator.

## Connector footprint-peer evidence route

The generic footprint-alias divergence, partially open, and all-open findings
now retain their `ConnectorFootprintPeerPinDivergence`,
`ConnectorFootprintPeerPinOpenOutlier`, or `ConnectorFootprintPeerPinAllOpen`
scan record on `ConnectorFootprintPeerPinCandidate`. The typed records copy
and freeze per-peer assignment maps; the connector-owned projector validates
the assignment state and preserves the existing evidence fields. Candidate
selection and review wording remain in the connector theme service, and the
public report shape is unchanged.

Mapped supply-domain findings retain the exact `NetlistContract`,
`ConnectorCoverageReport`, and ordered `ConnectorMappedPinEvidence` records
through `MappedSupplyDomainsCandidate`. Construction rechecks grouped pins
against current source-matched coverage and preserves the interface-catalog
path and digest. Domain names remain authored classifications; they do not
imply voltage incompatibility.

The scan consumes the `NetlistContract` supplied by its caller. Full evaluation
carries native netlist identity on `DesignLintReport` and
`ConnectorPeerPinHeuristicCoverage`; report validation requires those digests
to match and checks the coverage finding counts. The per-finding source record
does not duplicate that digest, and direct scanner calls do not independently
establish byte identity. These findings remain heuristic similarity reviews
and do not establish that matching connector contacts should be connected.

## BJT and MOSFET terminal-tie route

The six supported BJT collector/emitter, base/emitter, base/collector and
MOSFET drain/source, gate/source, gate/drain predicates now retain a
`ComponentTerminalSameNetEvidence` record on each internal
`ComponentTerminalCandidate`. The source owner validates the rule-to-device
pair and both native net assignments; `project_component_terminal_evidence`
maps the typed pair to the established role-specific pin/net keys and the
existing BJT family or MOSFET channel field. Predicate qualification, message
wording, finding order, report JSON, and fingerprints remain unchanged.

## PCB footprint inventory and population candidate routes

The two per-reference `pcb.schematic_component_inventory` findings now retain
a `PcbInventorySourceEvidence` record containing either the typed missing
placement or footprint-identity comparison and a shared
`PcbComponentInventorySourceReceipt`. The receipt owns the source netlist
digest, board path and digest, native snapshot digest and schema, KiCad
image/version, and probe digest for related PCB comparisons.
`project_pcb_inventory_evidence` owns the existing string-keyed report
projection. The candidate translator still owns finding selection and
wording; rule IDs, evidence fields, report JSON, and fingerprints remain
unchanged.

Per-reference schematic/PCB DNP mismatches use `PcbPopulationMismatchEvidence`
and `project_pcb_population_evidence`. The record includes the same native
receipt and, when present, the paired named-variant export identities. A
blocked named-variant comparison uses a separate
`PcbBlockedVariantPopulationEvidence` record whose constructor requires
`BLOCKED` coverage. `project_named_variant_population_evidence` is also used
by typed value findings that refer to a named variant. Its source owner is
`design_lint_pcb_variant_population_evidence.py`; it returns a
`CandidateEvidenceProjection` for either rule without coupling the two finding
owners. Per-reference value mismatches retain a
`PcbValueMismatchEvidence` record and use
`project_pcb_value_mismatch_evidence`. Blocked value comparisons retain
`PcbBlockedValueComparisonEvidence`, including the inventory state and explicit
`BLOCKED` comparison state. Its projector preserves the prior sparse evidence
shape when the whole inventory is blocked and the full receipt shape when only
the value comparison is blocked. These projectors preserve report fingerprints.

Top-level blocked inventory coverage now uses one
`PcbBlockedComponentInventoryEvidence` source record for both the footprint-
inventory and DNP findings. Its constructor accepts only a `BLOCKED` report;
separate projectors preserve each rule's prior sparse evidence fields, including
the DNP finding's optional snapshot digest. Completed per-reference footprint
and population records remain limited to completed comparisons. None of these
records infer package equivalence, assembly intent, electrical behavior,
physical placement correctness, or actual component population.

Schematic-to-PCB pad-net findings retain a
`PcbPadNetMismatchEvidence` record with the exact typed mismatch and shared
`PcbComponentInventorySourceReceipt`. A blocked comparison uses a separate
`PcbBlockedPadNetComparisonEvidence` record, preserving both the inventory
status and the pad-net comparison's `BLOCKED` state. Their projectors retain the
existing missing-source fallbacks, unconnected/unassigned labels, and public
evidence fields. The receipt's `from_coverage_report` constructor is shared by
the inventory and pad-net translators so optional native identity fields are
copied consistently.

Opt-in board-only footprint findings retain the typed footprint observation
with that same receipt; blocked board-only coverage retains the enclosing
inventory report. Project-required fitted-reference findings retain the exact
authored mismatch, requirement coverage and digest, native receipt, and named-
variant source coverage when applicable. Blocked requirement checks preserve
their enclosing report so the requirement gap and inventory state remain
available together. Both routes use theme-owned projectors for the existing
report fields and fingerprints.

## Mapped network and protection candidate evidence routes

`RegulatorFeedbackFindingEvidence` and `CrystalNetworkFindingEvidence` retain
the exact non-complete coverage entry and its configured report, including the
observed netlist digest. Their theme-owned projectors preserve the existing
field names, sorted pin/value measurements, formatted numeric ranges, issues,
and candidate fingerprints. `INCOMPLETE` and `OUT_OF_RANGE` entries remain
review findings; complete entries are filtered before evidence construction,
and blocked or not-requested reports remain ineligible. Evaluation continues
to own policy disposition and source matching.

## Power-path and RC-filter candidate evidence routes

`PowerPathFindingEvidence` retains the named `PowerPathMismatch` and the
canonical authored-map digest. `power_path_map_sha256` owns that digest in the
power-path domain and is shared by candidate projection and mapped-topology
coverage preparation. `RcFilterFindingEvidence` retains the exact coverage
entry and configured report, including the source netlist identity. Their
theme-owned projectors preserve existing evidence keys and fingerprints;
source freshness and policy disposition remain in evaluation.

## Digital-peer voltage candidate evidence route

The SPI and serial peer-voltage findings now share `DigitalPeerVoltageCandidate`
and `project_digital_peer_voltage_evidence`. The retained source combines the
grouped native peer review with its `DigitalPeerVoltageLintContext`; the owner
preserves each rule's distinct signal-assignment key, parsed label formatting,
authored-map state, and optional contract path and digest. Candidate order,
rule IDs, subjects, messages, and report fingerprints remain with the existing
theme adapters and evaluation path.

The ten schematic power and supply findings in `design_lint_power_candidates`
now retain typed scan records through `PowerCandidate`. Its projector owns the
existing same-voltage pin map, capacitor-gap fields, conditional source-anchor
state, connector/capacitor fields, repeated-supply pin map, numbered-rail map,
and the two native power-pin role findings. Those pin records retain the exact
observed netlist, native function, and unique assigned net; construction
rechecks fitted state, role classification, connector-return scope, and the
opposing rail label or peer-pin evidence. The shared pin-assignment index and
bounded name recognizers remain their canonical owners. The adapters still own
rule ordering and finding wording; serialized evidence keys and fingerprints
stay unchanged. Map-shaped source records are copied and frozen so their
projection cannot drift after candidate construction.

## External-protection candidate evidence route

`UnreviewedProtectionFindingEvidence` retains an undeclared connector pin and
its coverage report as an applicability prompt. `ProtectionMismatchFindingEvidence`
retains the exact incomplete or stale mapped entry and report. Separate
projectors preserve the existing connector, signal, observed-net, device, and
issue fields for both rule IDs. Coverage binding and blocked-state policy stay
in evaluation preparation.

## Return-domain candidate evidence route

Connector return-role gaps and the numbered or unroled return-net hints now
retain explicit source variants through `ReturnDomainCandidate`. The connector
variant carries its connected-pin coverage and optional return-like net-label
clues; the two net-group variants distinguish numbered siblings from labels
whose pins lack native return roles. Their projector preserves the current
conditional clue field and map-shaped report evidence. Connector pin maps and
typed return-net maps are copied and frozen at their source owners.

The authored connector return-distribution candidate retains its exact
`ConnectorReturnDistributionEntry` together with the enclosing
`ConnectorReturnDistributionCoverageReport`, including its netlist and
interface-catalog identities. Its projector preserves the established
role-count, pin-assignment, ratio, basis, and issue fields. All six role maps
are copied and frozen, with explicit serializers preserving ordinary mapping
output. Only `COMPLETE` or `INCOMPLETE` coverage and `OUT_OF_RANGE` or
`INCOMPLETE` entries can produce a finding; blocked and not-requested evidence
remain coverage states.

## SPI chip-select bias candidate evidence route

SPI chip-select bias findings now retain the exact `SpiChipSelectBiasGap`
returned by the heuristic scan through `SpiBiasCandidate`. Its projection
preserves the existing net, active-low pin, recognized rail, and empty visible
pull-up path fields. Resistance-band and authored array-path interpretation
remain in the SPI scan; the candidate adapter keeps the existing review
wording and order.

Unmapped SPI roster prompts retain the discovered participant and exact
`SpiRosterContext` through `UnmappedSpiParticipantCandidate`. Its projection
preserves the five endpoint fields, roster state, and optional authored
contract path and digest. Candidate wording and state selection remain in the
adapter.

USB-C port coverage prompts retain their exact `UnmappedUsbCPort` and
`UsbCPortRosterContext` through `UsbCPortCandidate`. The projector preserves
the CC pin and assignment fields, roster state, and optional authored contract
path and digest. Connector discovery and review wording remain in the adapter.

USB peer-reference prompts retain the exact `UsbPeerReferenceReview`, its
parent `UsbPeerReferenceScan`, and the authored `UsbDataPathCandidateInputs`
through `UsbPeerReferenceCandidate`. Construction rejects a review detached
from its scan. The projector preserves the bounded data topology, endpoint
reference assignments, policy state, component observations, and optional map
digest. Candidate wording remains in the adapter.

USB pin-versus-net polarity prompts retain the exact normalized
`NetlistContract` and the conflicting pin, function, and net through
`UsbDataPolarityCandidate`. Construction checks those values against the
source netlist and rejects a projection that disagrees with the source record.
The existing alias predicate still decides applicability and the adapter still
owns review wording.

SPI shared-clock reference findings retain their exact bus review and parent
scan through `SpiPeerReferenceCandidate`. The SPI projector combines the
canonical clock identity with endpoint, pin, and reference assignments, adding
incomplete-reference clues only when present. The candidate remains a
`PeerReferenceCandidate` subtype, so coverage reconciliation keeps using the
existing typed clock key.

I²C shared-bus reference findings likewise retain their review and parent scan
through `I2cPeerReferenceCandidate`, while keeping the canonical SDA/SCL
identity used by coverage reconciliation. Its projector preserves participant,
signal-pin, and reference-assignment ordering and emits incomplete-reference
clues only when the scan found them.

CAN shared-pair reference findings retain the exact bus and scan through
`CanPeerReferenceCandidate`, along with the canonical CANH/CANL identity. Its
projection preserves participant, line-assignment, and reference-assignment
ordering and keeps incomplete-reference clues conditional.

Mapped RS-485 reference findings retain the authored-map-bound scan, exact
pair, and canonical bus/pair identity through `Rs485PeerReferenceCandidate`.
The projector preserves the current line, participant, reference-assignment,
and sorted reference-net fields; map provenance remains attached to the typed
source record, and incomplete-reference clues remain conditional.

The one-sided-open I3C finding retains its exact `UnconnectedI3cSignalPin`
through `I3cUnconnectedCandidate`. The projection preserves the pin-keyed empty
assignment, role, channel fallback, and paired pin/function/net fields. Scan
selection and review wording remain in the existing translator.

Same-net findings for supported two-pin components retain the exact
`TwoPinComponentOnSameNet` record through `TwoPinSameNetCandidate`. The
component-kind projector preserves the existing rule ID, passive or component
kind field, net, pin assignments, and any reviewed custom-role evidence. It
rejects kinds owned by separate candidate routes, keeping source ownership
aligned with the component scan.

Transformer winding findings retain the exact normalized `NetlistContract`
through `SupportedTransformerObservation`. Named `TransformerWindingPinGroup`
and `TransformerPinNetAssignment` records replace positional group and
pin-to-net tuples. `TransformerCandidate` validates its report projection
against either the same-winding or cross-winding source record; the existing
predicate owners retain candidate selection and review wording.

Serial-peer coverage and reference-domain findings now retain their typed
source variants through `SerialPeerCandidate`. Unmapped endpoints preserve the
discovered endpoint and its authored roster scope; reference reviews preserve
the exact review and containing scan, and reject a review detached from that
scan. The projection keeps the existing conditional native-link, label-link,
discovery-basis, and contract identity fields. Candidate wording and order
remain in the serial adapter.

Power-sequence mismatch findings retain the exact mismatch and authored map;
cycle findings retain the map's declared-cycle state and observed cycles.
`power_sequence_map_sha256` owns the canonical map digest and is shared by
candidate projection and mapped-coverage preparation. Separate projectors
preserve the existing mismatch and cycle evidence fields. Both rule branches
remain eligible only under their existing source and coverage states.

## STM32 CubeMX candidate evidence route

`Stm32PinMapMismatchFindingEvidence` retains the exact pin mismatch and its
coverage report, with matching map, IOC, and native-netlist identities.
`Stm32UnmappedDeviceFindingEvidence` retains the name-based discovery
observation and its incomplete coverage report. Their shared projector keeps
the existing report fields, while source completeness and rule disposition
remain with coverage and evaluation.

## Schematic geometry candidate evidence routes

All 11 schematic geometry routes now retain the exact source scan and finding
in typed candidates. `SchematicPinGeometryCandidate` owns the three
native-unconnected pin/wire proximity rules;
`SchematicWireTopologyCandidate` owns unmarked crossings and T-junctions;
`SchematicLabelEndpointCandidate` owns near-wire label hints;
`SchematicTextGeometryCandidate` owns coincident anchors, text-envelope
overlaps, and text-over-wire overlaps; and
`SchematicSymbolBodyObstructionCandidate` owns text and wire obstructions of
symbol bodies. Each typed source checks that its finding is the same record
held by its `SchematicGeometryScan`. Projections preserve the established
source path and digest, sheet occurrence, coordinates, UUIDs, measured
distances, optional pin-endpoint matches, and KiCad version. The adapter
preserves order while delegating construction; it has no direct
`Candidate(evidence=...)` maps. Common source binding and numeric box/segment
formatting have one owner. Candidate field projection validation keeps the
serialized report fields aligned with each typed record.

## Mapped connector-interface candidate evidence

Nine mapped-interface findings now route through
`MappedInterfacePinFindingEvidence` and `MappedInterfacePinCandidate`. The
source record retains the current `NetlistContract`, `ConnectorCoverageReport`,
exact source-matched `ConnectorMappedPinEvidence`, rule ID, rail-label clue,
and power-contact exclusion scope. Validation keeps each predicate's role,
connection state, generic-function requirement, and single-net clue explicit.
The open signal and shield checks retain their existing behavior when the
overall coverage report is not `COMPLETE`, provided the individual mapping
still source-matches; the other seven findings continue to require complete
coverage. The typed projector preserves the established rule IDs, messages,
subjects, evidence fields, and fingerprints.

## PCB DRC severity candidate evidence

The global severity route now replaces its `(path, digest, severities)` tuple
with `SourceBoundPcbDrcSettings`, which retains the project path, matched source
digest, project kind, KiCad version, and sorted explicit check severities. The
source reader constructs it only after checking the project bytes against the
source inventory both before and after parsing. The settings parser itself
returns `PcbDrcCheckSeverity` records rather than anonymous check/severity
pairs. Each finding carries one typed severity record, its category, and its
catalogued rule ID through
`PcbDrcSeverityFindingEvidence` and `PcbDrcSeverityCandidate`. Validation ties
the check ID to the canonical category inventory and the rule to the configured
severity. The existing KiCad version boundaries remain explicit: core checks
accept the supported `10.*` family, specialized categories require `10.0.*`,
and warning-default checks retain their exact supported-version set. Projection
preserves the established source path, digest, version, check ID, configured
severity, subjects, messages, and fingerprints; the route has no direct
`Candidate(evidence=...)` maps.

## Custom PCB DRC rule candidate evidence

The ignored-rule, excluded-rule, and unresolved text-variable findings now
retain their source through `PcbDruRuleCandidate` or
`PcbDruTextVariableCandidate`. `SourceBoundPcbDruRuleFile` carries the
repository-relative path, verified digest, project kind, KiCad version, and
resolved local read path. The resolved path is used only to read and recheck
the source; projections contain only the existing repository-relative source
identity. Ignored and excluded rule findings retain the canonical parser
record, rule severity, and source file. Text-variable findings retain distinct
project and board source identities and sorted variable names rather than a
dynamically assembled context dictionary.

The source inventory checks, linked-path rejection, byte rechecks, supported
KiCad version boundary for exclusion and variable review, and parser-owned rule
records remain in force. Report field names and ordering, candidate subjects,
messages, and fingerprints are preserved. The text-variable finding still
means only that the audit does not evaluate KiCad substitutions; it does not
claim the resolved rule is faulty or valid.

## Named connector power-alias candidate evidence

All six named power-input and power-output alias findings now retain their
`ConnectorNamedPowerAliasPeer` through
`ConnectorNamedPowerAliasFindingEvidence` and
`ConnectorNamedPowerAliasCandidate`. The evidence record ties the catalog rule
to the native electrical type and finding kind, then validates its exact
assigned/open or distinct-net pin list against the peer assignments. The shared
PART_ID peer scan freezes its assignment mapping, so the retained source cannot
drift after candidate construction. The projector preserves the existing pin
assignment keys, identity basis, PART_ID, peer symbols, pin metadata, optional
peer assignment group, and each finding's supplemental pin list. The six
predicate owners keep their existing selection conditions, rule IDs, subjects,
messages, and ordering.

The broader AST inventory now finds 101 direct `Candidate(evidence=...)`
constructions in production modules across 96 files and 72 in tests across 46
files. Of those, 87 production evidence values and 24 test values are literal
dictionaries. This is a route-triage queue, not a count of confirmed opaque
boundaries. The largest remaining production concentrations tie at two calls
each in `bus_ethernet_pair_labels.py`, `component_repeated_signal_pins.py`,
`connector_peer_pin_all_open.py`, `connector_stateful_contacts.py`, and
`mosfet_gate_connectivity.py`. Review their source records and rule families
before selecting another shared owner.

## Mapped connector contact-sharing candidate evidence

The mapped shield/signal and signal/return findings retain
`MappedConnectorContactSharingFindingEvidence` through
`MappedConnectorContactSharingCandidate`. The source record binds the current
netlist, complete connector coverage, the catalog digest, the selected role
pair, and its mapped pin records. Construction verifies each pin against
current source-matched coverage, rejects unpopulated references and open or
ambiguous pins, and confirms both roles share the recorded native net. The
projector preserves the existing report fields, rule IDs, subjects, messages,
and ordering; predicate selection is unchanged.

The shared source route now leaves 101 direct `Candidate(evidence=...)`
constructions in production modules across 96 files and 72 in tests across 46
files. Literal dictionaries account for 87 production calls and 24 test calls.
The largest remaining production concentrations tie at two calls each in
`bus_ethernet_pair_labels.py`, `component_repeated_signal_pins.py`,
`connector_peer_pin_all_open.py`, `connector_stateful_contacts.py`, and
`mosfet_gate_connectivity.py`.

## Repeated component signal-pin candidate evidence

The divergent-net and unassigned-member findings now retain
`RepeatedSignalPinFindingEvidence` through `RepeatedSignalPinCandidate`. It
binds the current `NetlistContract` to the exact repeated pin group, including
the native function, electrical type, and each pin's net assignments. The
unassigned-member variant also validates its assigned and open pin lists
against that group. The projector preserves the existing evidence keys and
values, rule IDs, subjects, messages, and candidate order.

This route leaves 99 direct `Candidate(evidence=...)` constructions in
production modules across 95 files and 72 in tests across 46 files. Literal
dictionaries account for 87 production calls and 24 test calls. The largest
remaining production concentrations tie at two calls each in
`bus_ethernet_pair_labels.py`, `connector_peer_pin_all_open.py`,
`connector_stateful_contacts.py`, and `mosfet_gate_connectivity.py`.

## Stateful connector contact candidate evidence

Stateful contact-map identity findings retain
`StatefulContactMapMismatchEvidence`; mapped topology findings retain
`StatefulContactTopologyEvidence`. Both retain the project-authored contact
map and exact requirement. Identity findings verify their mismatch details
against the current native component, symbol, value, footprint, PART_ID, and
pin inventory. Topology findings retain the exact contact pair and both pin
net assignments, then verify the derived unassigned, ambiguous, or permanently
bypassed state. The candidate projector preserves the current rule ID, report
fields, subjects, messages, and ordering.

This route leaves 97 direct `Candidate(evidence=...)` constructions in
production modules across 94 files and 72 in tests across 46 files. Literal
dictionaries account for 85 production calls and 24 test calls. The largest
remaining production concentrations tie at two calls each in
`bus_ethernet_pair_labels.py`, `connector_peer_pin_all_open.py`, and
`mosfet_gate_connectivity.py`.

## Ethernet pin-label candidate evidence

The data-pair and management-label findings retain either
`EthernetDataLabelMismatchEvidence` or
`EthernetManagementLabelMismatchEvidence` through
`EthernetLabelMismatchCandidate`. Each source binds the current netlist, exact
pin function and role, assigned native net, and recognized label role. The
shared projector preserves the two existing evidence shapes, rule IDs,
subjects, messages, and predicate ordering. Pair-short suppression remains in
the respective predicate, and the rule catalog now names the evidence and
label-role owners in `implementation_refs`.

This route leaves 95 direct `Candidate(evidence=...)` constructions in
production modules across 93 files and 72 in tests across 46 files. Literal
dictionaries account for 83 production calls and 24 test calls. The largest
remaining production concentrations tie at two calls each in
`connector_peer_pin_all_open.py` and `mosfet_gate_connectivity.py`.

## Generic connector all-open candidate evidence

The exact-symbol and PART_ID branches now retain
`ConnectorAllOpenPeerPinEvidence` through `ConnectorAllOpenPeerPinCandidate`.
The source record keeps the peer identity basis explicit and verifies current
fitted peers, native pin functions and electrical types, all-open assignments,
and shared-anchor contacts against the current `NetlistContract`. The
projector preserves the existing rule ID, report fields, subjects, messages,
and candidate ordering. Predicate selection, reviewed peer scoping, and
PART_ID subsumption are unchanged.

The connector all-open selection passed 80 source, architecture, catalog,
marker, selector, determinism, and CLI/MCP parity tests. Ruff, format,
targeted Pyright, Markdown checks, mdrepo, and `git diff --check` passed. No
exact native KiCad lane was run.

## MOSFET gate candidate evidence

No-peer, source-bias, and direct-drive findings retain distinct source types
through `MosfetGateCandidate`. Each binds a `SupportedMosfetGate` to the
current fitted component, exact supported symbol, complete three-pin
inventory, and unique native gate function through the canonical
`component_mosfet_symbols.mosfet_terminal_role` service. The no-peer variant
verifies the current gate assignment and absence of fitted peers. The
source-bias variant verifies the source terminal, distinct current gate/source
nets, exact fitted gate peers, and absence of a direct resistor recognized by
`resistor_paths.direct_resistors`. The direct-drive variant verifies all D/G/S
roles plus the current output-capable peer pins and types. The projector
preserves existing rule IDs and evidence shapes; predicate behavior, policy
modes, and CLI/MCP mapping are unchanged.

At the MOSFET-gate checkpoint, the AST inventory found 158 direct `Candidate(evidence=...)`
constructions across 132 modules: 86 production calls across 86 modules and
72 test calls across 46 modules. Literal dictionaries account for 76
production calls and 24 test calls. No production module has more than one
direct construction now; the remaining single-call routes still need to be
reviewed by source contract rather than by count alone.

The MOSFET gate selection passed 106 focused source, architecture, catalog,
marker, selector, and CLI/MCP parity tests. Ruff, format, targeted Pyright,
Markdown checks, mdrepo, and `git diff --check` passed. No exact native KiCad
lane was run.

## Footprint-similar connector named-divergence evidence

Named power-input, power-output, signal, and passive footprint-peer divergences retain a
`ConnectorFootprintPeerPinScanSource` with the exact `NetlistContract`, declared
reference scope, and frozen peer-assignment groups. Their shared source owner
checks current peer identity, complete pin inventory, matching native metadata,
per-pin assignments, the selected peer scope, and all common-net anchors. One
projector preserves each rule ID and existing evidence fields. Predicate
selection, findings, messages, and policy behavior are unchanged.

The connector footprint peer, CLI/MCP parity, source, architecture, catalog,
and marker selection passed 251 tests; 26 digest-pinned native cases were
skipped. Ruff, targeted Pyright, format, Markdown, mdrepo, and
`git diff --check` passed. No exact native KiCad lane was run.

## Two-pin same-net source evidence

All two-pin same-net candidates now retain their exact source `NetlistContract`
on `TwoPinComponentOnSameNet`. The shared evidence owner verifies the fitted
component, exact native symbol and value, complete two-pin inventory, single
net assignment for each pin, and any authored custom-role binding before
projecting the existing report fields. LED, buzzer, speaker, battery, motor,
solar-cell, and thermocouple candidates use the same owner as diode, crystal,
fuse, switch, and passive candidates. Rule IDs, messages, predicate selection,
policy behavior, and serialized report fields remain stable.

The focused two-pin source, behavior, catalog, selector, marker, determinism,
and CLI/MCP parity selection passed 235 tests; 26 digest-pinned native cases were skipped.
Ruff, format, targeted Pyright, Rumdl, mdrepo, and `git diff --check` passed.
The parity tests used the separate public `KiCAD-Test` checkout at `ed89536`;
no exact native KiCad lane was run.

The refreshed AST inventory finds 137 direct `Candidate(evidence=...)`
constructions across 111 Python modules: 65 production calls across 65
modules and 72 test calls across 46 modules. Literal dictionaries account for
58 production calls and 24 test calls. This inventory does not classify every
mapping used by typed projectors or other findings.

## BJT base review evidence

BJT base-bias and direct-drive findings retain separate typed source variants
through `BjtBaseCandidate`. Both bind the native symbol, role-mapped base pin,
and assignment to the current `NetlistContract`. Direct-drive evidence also
rechecks the exact fitted output-capable peers and their pin types. Base-bias
evidence rechecks the emitter assignment, fitted base-net peers, absence of a
recognized direct resistor, and the direct-drive exclusion. Their existing
rule IDs, report fields, messages, and selection remain stable. The catalog
preserves the different modes: direct-drive defaults to `review`, while
base-bias defaults to `off`.

The focused BJT source, behavior, catalog, selector, marker, determinism, and
CLI/MCP parity selection passed 80 tests; four digest-pinned native cases were
skipped. Ruff, format, targeted Pyright, and `git diff --check` passed. The
parity test used the separate public `KiCAD-Test` checkout at `ed89536`; no
exact native KiCad lane was run.

## Ethernet open-pair evidence

Ethernet TX/RX data-pair and MDC/MDIO management open-pin findings retain
typed source variants through `EthernetUnconnectedCandidate`. Each source
retains the exact `NetlistContract` and rechecks the fitted IC, complete native
pin inventory, unique complementary roles, open pin, and exact assigned peer
net. The two variants preserve their rule-specific evidence fields; candidate
selection, wording, and default-off policy remain stable.

The focused behavior, source, architecture, catalog, marker, and selector
selection passed 92 tests. Ethernet data CLI/MCP parity passed against the
separate public `KiCAD-Test` checkout at `ed89536`. Ruff, targeted Pyright,
Rumdl, mdrepo, and `git diff --check` passed. No exact native KiCad lane was
run.

## CAN and serial TX-sharing evidence

CAN and serial TX-output-sharing findings now retain `TxOutputSharingGroup`
through `TxOutputSharingCandidate`, alongside the exact source
`NetlistContract`. The typed source re-runs the canonical group service and
rejects a group that no longer matches the current native source. It keeps
each protocol's existing rules for supported references, inventory
requirements, return-like nets, and output-to-output ERC exclusion. The
report projection keeps the existing fields and channel labels; CAN channel
formatting now lives in the shared CAN function owner.

The focused CAN/serial output-sharing, CAN TX/RX, architecture, catalog,
selector, marker, and CLI/MCP parity selection passed 99 tests. Ruff, targeted
Pyright, Rumdl, mdrepo, and `git diff --check` passed. Parity used the separate
public `KiCAD-Test` checkout at `ed89536`; no exact native KiCad lane was run.

## I2C and I3C same-net evidence

I2C and I3C same-net findings retain separate protocol source records through
`TwoWireSameNetCandidate`. Each record binds the exact source `NetlistContract`,
current fitted IC, native SDA/SCL functions, role-pin inventory membership, and
exact shared assignment; the I3C source also keeps the parsed channel. The
projector preserves the distinct I2C and I3C evidence fields and keeps the
existing rule that leaves two native outputs to ERC.

The focused I2C/I3C behavior, source, architecture, determinism, catalog,
marker, selector, and I2C CLI/MCP parity selection passed 89 tests. Ruff,
targeted Pyright, Rumdl, mdrepo, and `git diff --check` passed. No exact native
KiCad lane was run.

## USB-C connector/controller CC same-net evidence

The connector and controller CC same-net rules now share
`UsbCcSameNetCandidate` with distinct source variants. The connector source
retains reviewed connector-reference scope alongside the exact netlist and
rechecks connector identity, native CC roles, role-pin inventory membership,
and exact assignments. The controller source rechecks fitted U/IC identity,
inventory membership for recognized CC pins, exact assignments, and the
existing two-output exclusion. The projection preserves the separate
connector/component fields and current review policies.

The focused source, behavior, architecture, determinism, catalog, marker,
selector, and CLI/MCP parity selection passed 111 tests. Ruff, targeted Pyright,
Rumdl, mdrepo, and `git diff --check` passed. No exact native KiCad lane was
run.

## CAN TX/RX same-net evidence

CAN TX/RX same-net findings retain one `CanTxRxSameNetEvidence` record through
`CanTxRxSameNetCandidate`. The record binds the TX and RX endpoints to the
exact source `NetlistContract`, validates the fitted component, unique roles
within the recognized channel, inventory membership, exact shared assignment,
and current electrical types. The existing output/output exclusion and
rule-specific report fields remain unchanged.

The combined Ethernet and CAN source, behavior, architecture, catalog, marker,
selector, and CLI/MCP parity selection passed 104 tests. Parity used the
separate public `KiCAD-Test` checkout at `ed89536`. Ruff, targeted Pyright,
Rumdl, mdrepo, and `git diff --check` passed. No exact native KiCad lane was
run.

## SPI same-net source evidence

SPI data-role, clock/data, and clock/chip-select same-net findings now share
`SpiSameNetCandidate` with explicit typed variants. Each variant retains the
exact `NetlistContract` and canonical `SpiRoleAssignmentGroup`; construction
rechecks that the role group is current, that each selected role has one
inventoried pin and one net, and that two explicit outputs remain excluded.
The data-role variant keeps its case-insensitive net comparison and preserves
the input-side native net spelling. Each projector emits its existing rule
fields, while predicate ownership, messages, policies, and rule IDs stay
unchanged.

The focused SPI source, behavior, architecture, catalog, marker, selector,
determinism, and CLI/MCP parity selection passed 158 tests. Ruff, format,
targeted Pyright, Rumdl, mdrepo, and `git diff --check` passed. No exact native
KiCad lane was run.

## Named-rail protocol signal source evidence

The CAN controller, I2C, I3C, SPI, serial, Ethernet data, Ethernet management,
USB, RS-485, and USB-C SBU signal-on-named-rail rules now share
`NamedRailSignalCandidate` while retaining protocol-specific typed source
variants. Each source carries a `NamedRailPinSource` bound to its
`NetlistContract`. Validation rechecks the fitted component, exact native
function and inventory, unique rail-like net assignment, and
protocol-specific role/channel or pair identity. RS-485 evidence also
rechecks explicit transceiver identity, while USB-C SBU evidence requires the
current unique SBU1/SBU2 pair and complete pin inventory. USB 2.0 and
SuperSpeed family/side recognition now has one shared owner. Existing
predicate owners, messages, policy modes, and serialized evidence fields stay
stable.

The direct `Candidate(evidence=...)` inventory is now 127 constructions:
55 production calls across 55 modules and 72 test calls across 46 modules.
Literal maps account for 48 production and 24 test calls.

The focused named-rail behavior, source, architecture, catalog, marker, and
selector selection, including RS-485 and USB-C SBU, passed 313 tests. Ruff,
format, targeted Pyright, Rumdl, mdrepo, and `git diff --check` passed. No exact
native KiCad lane was run. The combined regression also found and closed a CAN
TX/RX ambiguity where case-fold duplicate pin-function keys could reach
source construction.

## CAN and RS-485 named-rail line source evidence

CANH/CANL and RS-485 A/B findings retain their complementary line pins through
`NamedRailLineCandidate`, a separate owner from the single-pin signal route.
Each typed source carries a `NamedRailPinSource` bound to its current
`NetlistContract` and revalidates the unique native role pair and complete pin
inventory. The RS-485 variant also rechecks the explicit transceiver identity.
The projectors preserve each rule's existing complementary-pin fields,
identity field, messages, and review policy; malformed or incomplete pairs
remain skipped.

The direct `Candidate(evidence=...)` inventory is now 125 constructions:
53 production calls across 53 modules and 72 test calls across 46 modules.
Literal maps account for 46 production and 24 test calls.

The focused CAN/RS-485 line behavior, source, architecture, catalog, marker,
selector, determinism, and native-gate architecture selection passed 242 tests.
Ruff, format, targeted Pyright, and `git diff --check` passed. No exact native
KiCad lane was run.

## Named connector all-open source evidence

Named power-input, power-output, and signal contacts open across footprint
aliases now use `ConnectorFootprintAllOpenCandidate`. Its typed source retains
the exact `ConnectorFootprintPeerPinScan` and selected
`ConnectorFootprintPeerPinNamedAllOpen` record, then checks that the record
belongs to the scan, every peer remains open, a common anchor exists, and the
contact function and electrical type match the selected rule. Each projector
preserves its existing assignments, open-pin list, symbols, anchor fields,
and optional reviewed peer-group evidence. Predicate selection, wording,
coverage counts, and policy remain unchanged.

The direct `Candidate(evidence=...)` inventory is now 122 constructions:
50 production calls across 50 modules and 72 test calls across 46 modules.
Literal maps account for 43 production and 24 test calls.

The focused named contact behavior, source, architecture, catalog, marker,
selector, and native-gate architecture selection passed 213 tests; the
CLI/MCP parity test passed separately. Ruff, format, targeted Pyright, Rumdl,
mdrepo, and `git diff --check` passed. No exact native KiCad lane was run.

## I2C, CAN, and SPI signal-label role evidence

The I2C, CAN, and SPI label-mismatch adapters now pass typed source variants
through `SignalLabelRoleMismatchCandidate`. Each variant binds the finding to
the current native pin and its unique exact net assignment, and the source
owner rechecks fitted state, native function, parsed pin and net roles, and
the role mismatch. CAN also rechecks the same-symbol opposite-line short
exclusion. SPI label parsing is owned by `spi_participants.py` and reused by
the rule and source validator. Projectors preserve the existing evidence
fields, messages, policies, and rule owners.

The direct `Candidate(evidence=...)` inventory is now 119 constructions:
47 production calls across 47 modules and 72 test calls across 46 modules.
Literal maps account for 40 production and 24 test calls.

The focused I2C/CAN/SPI behavior, source, architecture, catalog, marker,
selector, native-gate architecture, and candidate-scanner parity selection
passed 130 tests. Ruff and targeted Pyright passed. No exact native KiCad lane
was run.

## RS-485 and serial signal-label source evidence

The shared `SignalLabelRoleMismatchCandidate` route now covers RS-485 D/R
pins against explicit UART/USART labels, RS-485 A/B functions against bounded
line labels, and serial TX/RX functions against same-channel UART/USART
labels. The D/R variant retains its exact paired pins and same-channel source
assignments. The A/B variant retains explicit transceiver identity, complete
pin inventory, the complementary native pin, and both distinct assigned
nets. Serial TX/RX evidence rechecks fitted state, exact function and
assignment, complete inventory, and channel. Bounded RS-485 line-label
recognition now belongs to `rs485_line_functions.py`. Existing rule owners,
policy, messages, report fields, and fingerprints remain stable.

The direct `Candidate(evidence=...)` inventory is now 116 constructions:
44 production calls across 44 modules and 72 test calls across 46 modules.
Literal maps account for 37 production and 24 test calls.

The six-rule behavior, typed source, catalog, architecture, marker, selector,
native-gate architecture, and candidate-scanner parity selection passed 146
tests. The RS-485 A/B CLI/MCP parity test passed separately. Ruff, targeted
Pyright, Rumdl, mdrepo, and `git diff --check` passed. No exact native KiCad
lane was run.

## Connector footprint peer metadata evidence

The four connector-footprint metadata rules now project through
`ConnectorFootprintPeerMetadataCandidate`. Its source retains the exact
`NetlistContract`, authored peer grouping, footprint identity group, complete
native pin inventory, target pin, scoped assignment partition, role metadata,
and common-anchor pins. Construction recomputes the current group, scope,
metadata, assignments, and anchors before projection. A typed state selects
one of four separate predicates: complete metadata with split assignments,
complete metadata with partial opens, missing metadata with split assignments,
or missing metadata with partial opens. The rule-specific evidence keys,
missing-value formatting, peer-symbol field names, part-ID basis, messages,
and policies remain unchanged.

The direct `Candidate(evidence=...)` inventory is now 112 constructions:
40 production calls across 40 modules and 72 test calls across 46 modules.
Literal maps account for 33 production and 24 test calls.

The four rule behavior, typed-source, catalog, architecture, marker, selector,
native-gate architecture, and candidate-scanner parity selection passed 182
tests, including the rules' embedded CLI/MCP parity cases. Ruff and targeted
Pyright passed. No exact native KiCad lane was run.

## Unreviewed connector peer-scope evidence

The unreviewed peer-scope rule now constructs
`ConnectorUnanchoredPeerScopeEvidence` from its current peer scan, observed
netlist, complete connector coverage, and one alias cohort. The source owner
rechecks the scan/netlist identity, current fitted alias group, complete
inventory and matching native pin metadata, exact one-net assignments, absence
of common anchors, and source-matched complete interface maps without a
peer-assignment group. It projects the established finding evidence, including
catalog and inventory review identifiers, through
`ConnectorUnanchoredPeerScopeCandidate`; the rule ID, message, policy, and
serialized evidence fields stay stable. The peer scan and source validators
use `netlist_pin_assignments.netlist_pin_net_index` for the shared immutable
case-folded pin-to-exact-net index. The connector-owned assignment projector
retains its deterministic ordering contract without rebuilding the index.

The focused connector scope, peer metadata, named-divergence, typed-source,
architecture, marker, selector, catalog, active-rule reachability, and
public-template CLI/MCP parity selection passed 162 tests. Ruff, targeted
Pyright, Rumdl, mdrepo, and `git diff --check` passed. No exact native KiCad
lane was run. The reviewed-assignment route is documented below.

## Unanchored connector coverage-missing evidence

The incomplete-coverage variant now projects through
`ConnectorUnanchoredCoverageEvidence` and
`ConnectorUnanchoredCoverageCandidate`. The source retains the current native
peer scan, optional connector coverage report, and one cohort of split or
partially open generic contacts. Shared validation checks that the contact
records belong to the current scan, the fitted alias identity and complete
pin inventory still match, native function and electrical metadata remain
complete and equal, assignments still match the current netlist, and no
common-net anchor or authored peer-assignment scope has appeared.

Absent and incomplete coverage remain reviewable under the rule's existing
disposition policy; stale and not-applicable entries suppress the prompt.
Entries marked covered must still have exact source-matched pin maps. The
projection preserves the published evidence keys and coverage statuses. The
rule catalog references the adapter, typed source/candidate, projection,
coverage policy, and shared current-source validator. The new owner modules
are guarded by the connector architecture suite.

The coverage and scope routes, peer metadata and named-divergence regressions,
catalog, marker, selector, and architecture selection passed 278 tests. The
peer assignment regressions passed 14 tests; two exact native-fixture cases
were skipped. Ruff, format, targeted Pyright, JSON parsing, Rumdl, mdrepo, and
`git diff --check` passed. No exact native KiCad lane was run. The reviewed
assignment route is documented below.

## Reviewed unanchored connector assignment evidence

The reviewed assignment adapter now routes through
`ConnectorUnanchoredAssignmentEvidence` and
`ConnectorUnanchoredAssignmentCandidate`. The source retains the exact peer
scan and `ConnectorCoverageReport`. Before projection, it recomputes the
source-matched peer groups from that report, checks that the scan and each
divergence retain the current group and review basis, and revalidates native
identity, complete pin inventory, native metadata, exact net assignments, and
absence of common anchors. The candidate preserves the existing evidence
keys, message, subject, and rule owner. The adapter no longer creates a raw
`Candidate(evidence=...)` for this rule.

The combined reviewed-assignment, unreviewed-scope, coverage-missing, connector
peer metadata, named-divergence, catalog, marker, selector, and architecture
selection passed 298 tests; two native-fixture tests were skipped. Ruff,
format, targeted Pyright, and adjacent connector quality checks passed. No
exact native KiCad lane was run.

At this checkpoint, an AST inventory of direct `Candidate(evidence=...)`
construction finds 109 calls: 37 production calls across 37 modules and 72
test calls across 46 modules. The calls contain 32 production and 24 test
literal evidence maps. This inventory covers direct `Candidate` calls only;
it does not measure other dictionary-shaped interfaces.

## Named connector open-peer evidence

The six named-open connector rules now route through
`ConnectorNamedOpenEvidence` and `ConnectorNamedOpenCandidate`. The typed
source retains the exact peer scan, optional coverage report, open-contact
record, and rule ID. Before projection, it recomputes source-matched peer
groups, rebuilds the scan from the observed netlist and declared references,
and confirms the record still belongs to both scans and matches the selected
electrical role, open pins, and common-anchor scope. The shared peer-group
normalizer is owned by `connector_coverage.py` and is also used by the reviewed
assignment route.

The six adapters preserve their current subjects, messages, rule owners, and
serialized evidence fields. The rule catalog points to the typed owner,
projection, source-group validator and normalizer, scanner, and adapter. The
connector architecture suite guards the new owner's size and checks every
catalog route.

The named-open and adjacent connector behavior, typed-source, architecture,
catalog, marker, selector, CLI/MCP parity, and peer parity selection passed
111 tests. The AST inventory now finds 108 direct `Candidate(evidence=...)`
calls: 36 production calls across 36 modules and 72 test calls across 46
modules. Literal maps account for 31 production and 24 test calls. This
inventory covers direct `Candidate` calls only; it does not measure other
dictionary-shaped interfaces. No exact native KiCad lane was run.

## Generic component peer open evidence

The generic component all-open and mixed-open rules now retain
`GenericComponentPeerOpenScanEvidence` and
`GenericComponentPeerOpenEvidence`. The scan source binds the observed
`NetlistContract`, the exact peer scan, declared connector references, and
rule ID. It rebuilds the rule-specific scan once for the batch; each selected
outlier must belong to that scan and still satisfy the rule's all-open or
same-net mixed-open conditions before projection.

The all-open and mixed-open adapters preserve their existing subjects,
messages, rule owners, evidence keys, and field order. The catalog references
the typed scan and candidate, current-scan validation, semantic validation,
and projection. Component and evidence marker registries include the source
and architecture suites.

The source, behavior, candidate scanner, coverage, architecture, catalog,
marker, selector, determinism, and CLI/MCP parity selection passed 150 tests;
two native fixture tests were skipped. The AST inventory now finds 106 direct
`Candidate(evidence=...)` calls: 34 production calls across 34 modules and 72
test calls across 46 modules. Literal maps account for 29 production and 24
test calls. This inventory covers direct `Candidate` calls only; it does not
measure other dictionary-shaped interfaces. No exact native KiCad lane was
run.

## Native power-pin role evidence

The named power-pin/net-role conflict and named supply pin/negative rail rules
now retain `NamedPowerPinNetRoleConflictEvidence` or
`NamedSupplyPinNegativeRailEvidence` through the existing `PowerCandidate`
projector. Each source binds one native pin function to its exact unique net
assignment and checks fitted state. The role-conflict source also validates
connector-return scope and freezes the bounded opposing label or peer-pin
clues. Both rule adapters still select findings and preserve their existing
order, wording, evidence fields, and fingerprints. The catalog now names the
typed source, projection, and shared assignment index.

The two rule suites, source projection, architecture, catalog, marker, and CLI
and MCP parity tests passed 122 tests. Ruff, targeted Pyright, Rumdl, mdrepo,
JSON parsing, and `git diff --check` passed. No exact native KiCad lane was
run. The AST census now finds 104 direct `Candidate(evidence=...)` calls: 32
production calls across 32 modules and 72 test calls across 46 modules;
literal maps account for 27 production and 24 test calls. This census still
does not measure other dictionary-shaped interfaces.

## Authored power-map candidate evidence

The project-authored IC decoupling and regulator required-passive findings
now also retain typed sources through `PowerCandidate`. The IC decoupling
source keeps the complete authored map, exact requirement, native netlist,
reviewed topology issues, and parsed nominal capacitor values; construction
recomputes the review, total, minimum, and map digest. The regulator source
keeps its authored topology map, exact mismatch, and netlist; construction
reruns the topology comparison. Their projector preserves the existing
serialized evidence fields, including conditional capacitance totals and the
sorted component list. The rule adapters remain responsible for selection,
message wording, and order.

The local decoupling, regulator, power-role, source, architecture, catalog,
marker, rule-selector, regulator CLI/MCP, and power-role CLI/MCP selection
passed 151 tests. The IC decoupling CLI/MCP parity test could not start because
this checkout has no `KICAD_TEMPLATE_ROOT` configured. Ruff, targeted Pyright,
Rumdl, mdrepo, JSON parsing, and `git diff --check` passed; no exact native
KiCad lane ran. The updated AST census now finds 102 direct
`Candidate(evidence=...)` calls: 30 production calls across 30 modules and 72
test calls across 46 modules; literal maps account for 26 production and 24
test calls. Other dictionary-shaped interfaces remain outside this narrow
census.

## Component named-rail terminal-order evidence

The BJT collector/emitter and MOSFET drain/source rail-order scanners now
project through `ComponentTerminalOrderCandidate` with distinct
`BjtTerminalOrderEvidence` and `MosfetTerminalOrderEvidence` source records.
Each record retains the observed netlist, exact fitted symbol and pin roles,
unique native pin-to-net occurrences, and recomputed named-rail potentials.
Construction rejects stale assignments, changed rail evidence, unsupported
roles, and a repaired conventional order. The existing rule owners still
select candidates and supply the same subjects and messages; the projection
keeps the current serialized evidence fields. Both rules now reference the
typed source, projection, and shared source-order-preserving pin assignment
index in the catalog.

The terminal-order source, BJT and MOSFET rule regressions, pin-assignment
index, catalog, and architecture checks passed 125 tests. Catalog, marker,
collection, selector, backlog, and power-pin CLI/MCP parity checks passed 56
more. Ruff and formatting passed; targeted Pyright reported zero errors,
warnings, or information messages. JSON parsing, Rumdl, mdrepo, and
`git diff --check` passed. No native KiCad lane ran. The IC decoupling
CLI/MCP parity lane remains unavailable because `KICAD_TEMPLATE_ROOT` is not
configured.

The refreshed direct-candidate census finds 100 `Candidate(evidence=...)`
calls: 28 production calls across 28 modules and 72 test calls across 46
modules. Literal maps account for 26 production and 24 test calls. This
census covers direct `Candidate` construction only; other dictionary-shaped
interfaces remain outside it. The adjacent diode and polarized-capacitor
routes are completed in the next entry.

## Diode and polarized-capacitor named-rail evidence

The diode A/K and polarized-capacitor pin 1/2 rules now retain separate
`DiodeRailOrientationEvidence` and
`PolarizedCapacitorRailOrientationEvidence` records through
`ComponentPolarityCandidate`. Their symbol services return named terminal
number records and validate the supported identities, native role metadata,
and complete inventories. Both sources use the shared
`NamedRailTerminalEvidence` and validator, which recompute the exact pin
assignment and current named-rail potential while preserving each scanner's
existing evidence spelling. Rule owners still control selection, subjects,
and messages; serialized evidence keys and fingerprints remain unchanged.

The source, diode and capacitor rule suites, BJT/MOSFET source regressions,
pin-assignment helper, and catalog selection passed 95 tests. The catalog,
marker, collection, selector, reachability, and architecture slice passed 58;
component determinism passed 11. Ruff and formatting passed, targeted Pyright
reported zero diagnostics, and JSON parsing, Rumdl, and mdrepo passed. No exact
native KiCad or CLI/MCP parity lane ran; `KICAD_TEMPLATE_ROOT` is not set in
this checkout.

The refreshed direct-candidate census finds 98 calls: 26 production calls
across 26 modules and 72 test calls across 46 modules. Literal maps account
for 24 production and 24 test calls. This census covers direct `Candidate`
construction only; the remaining mapping-shaped interfaces still require a
separate source-bound inventory.

## Connector comparison-scope route

Connector peer, return, and supply comparisons now carry a
`ConnectorComparisonScope` record with named `group` and `basis` fields. The
reference-keyed index remains a map because lookups are by connector
reference; the map values no longer encode two meanings in positional tuples.
Source-matched coverage creates read-only scope maps only for complete maps
whose pin evidence still matches the current netlist. Case-insensitive index
normalization rejects duplicate references.

The public `connector_pins` facade converts its supported legacy tuple-valued
scope inputs into these records before calling the owning services. Internal
candidate and coverage code imports the typed owners directly, so the legacy
shape does not continue through the scan route.

At the scanner boundary, a missing or incomplete scope still produces one
unscoped partition for all participating assignments. It cannot partially
partition the peers and accidentally suppress a finding. The return/supply
singleton review consumes the same named scope fields. This is comparison
scope evidence only: it does not establish a required shared net, continuity,
or electrical isolation. Candidate evidence serialization and fingerprints
remain unchanged.

## Typed connector pin evidence map (2026-11-05)

`netlist_pin_net_index` already exposes the named `NetlistPinNetIndex`
read-only contract: case-folded `reference.pin` keys map to `frozenset`
collections containing the exact native net names. Its 23 production consumer
modules use lookup/iteration only. This corrects the earlier backlog note that
described the published result as mutable.

The occurrence-preserving `netlist_pin_net_assignments` projection now uses
`NetlistPinNetAssignmentsByPin`. It returns a read-only mapping whose
case-folded pin keys map to tuples retaining duplicate native assignments and
source iteration order. Its five production consumers use lookup/iteration
only; `netlist_pin_net_index` derives its set-valued view from this owner.

`source_matched_connector_pin_evidence` now exposes
`ConnectorMappedPinEvidenceByComponentPin`, owned by
`connector_coverage_models.py`. The key type is `Reference`, and each key
retains the exact native `reference.pin` spelling. The producer returns a
`MappingProxyType` for populated and empty results; the frozen
`ConnectorMappedPinEvidence` values retain their existing source-match checks.
Fifteen production consumer modules make 23 direct calls, and the caller audit
found no mutation of the returned maps. Consumers import the named contract
from its theme-owned model module. Lookup behavior, coverage requirements, and
serialized evidence/fingerprints are unchanged.

The focused connector-map, mapped-interface, peer-compatibility, and
architecture slice passed 98 tests with one skipped case. Ruff, formatting,
and targeted Pyright passed. No native KiCad lane ran. Continue the API census
with other mutable mapping routes; do not infer that all such routes are
complete from this checkpoint.

## Component pin-function index route (2026-11-05)

`NetlistContract.pin_functions` remains the source observation. The
component-owned `native_pin_function_index` derives a case-folded pin-key map
with trimmed native function text; `normalized_pin_function_index` derives
the same keys with case-folded function text. Both use the named
`ComponentPinFunctionIndex` contract and return read-only mappings, including
when no function data is present.

The BJT and MOSFET terminal-order scanners and their source-evidence validator
consume these views by lookup or pass them to role/potential checks. The audit
found no consumer mutation. These indexes are derived lookup aids, not source
evidence: terminal evidence continues retaining the exact observed
`NetlistContract`, and validation recomputes the current roles and potentials.
No serialized candidate fields, fingerprints, selection behavior, or report
wording change.

The focused terminal-order and component-polarity selection passed 12 tests;
13 unrelated or marker-excluded cases were deselected. Ruff, targeted Pyright,
Rumdl, and `git diff --check` passed. Alphus runtime-types, Python-style,
Pydantic-practices, and input-contracts report scans found no findings in the
four route modules. No exact native KiCad lane ran.

## Component symbol role-number route (2026-11-05)

The exact BJT and MOSFET symbol services now return `BjtPinRoleNumbers` and
`MosfetPinRoleNumbers` frozen records instead of `dict[str, str]`. Their
fields name the supported roles directly (`base`, `collector`, `emitter`;
`drain`, `gate`, `source`). The service owners still require the exact
supported symbol identity, a complete three-number inventory, and one
unambiguous native function for every required role; unsupported or incomplete
inputs still return `None`.

The import-aware audit found 13 consumers across eight modules (seven BJT and
six MOSFET calls); consumers read fields and do not mutate results. The role
records are derived lookup results, not source evidence. Candidate evidence
continues retaining the observed `NetlistContract` and recomputes symbol roles
against it. Rule selection, source checks, serialized evidence, and report
wording remain unchanged.

The BJT/MOSFET rule, source-evidence, and architecture selection passed 195
tests; 20 native or marker-excluded cases were deselected. Ruff and targeted
Pyright passed. Alphus runtime-types, Python-style, Pydantic-practices, and
input-contracts scans reported no findings in the 11 changed production files.
No exact native KiCad lane ran.

The combined connector/component mapping and role-record selection passed 265
tests with one skipped case. Ruff check/format, targeted Pyright, and
`git diff --check` passed. No exact native KiCad lane ran.

## USB case-folded netlist index route (2026-11-05)

`NetlistContract` retains exact source keys and accepts distinct spellings such
as `U1` and `u1`. The USB peer route now uses the shared
`casefolded_unique_index` owner in `casefold_mapping_lookup.py`. It returns an
immutable mapping of normalized keys and excludes every key with more than one
case-folded source match, so a lookup cannot select a value based on input
order. The four USB peer consumers use this owner directly across 25 calls;
the audit found no mutation of any returned index.

These indexes remain derived lookups, not source evidence. USB candidate
evidence continues to retain its existing scan and authored map; endpoint
recognition fails closed when a required component symbol becomes ambiguous.
The netlist contract and serialized candidate evidence are unchanged.

The focused case-fold tests, USB peer regressions, and architecture guards
passed 146 tests, with two deselected cases. Ruff and targeted Pyright passed.
The six Alphus profiles retained their current totals and reported no findings
in the five route modules. The 1,500-line `hwrepo` file-size candidate and
scoped test-quality candidate both returned zero findings. No exact native
KiCad lane ran. Continue the SA-01 inventory with other returned maps, keeping
local accumulation dictionaries out of the shared-route count.

## Resistor-path map route (2026-11-05)

`visible_resistor_pullups` and `visible_resistor_paths` now return the named
`VisibleResistorPathsByNet` contract: an immutable mapping from exact net names
to sorted tuples of `VisibleResistorPath` records. The import-aware audit found
nine external calls across six production consumers; each performs lookup or
iteration, with no mutation of the returned result.

These maps remain derived resistor-path views, not source evidence. The
underlying `NetlistContract`, discovered paths, numeric resistance, and lint
evidence are unchanged. No serialized candidate or report fields changed.

The focused resistor, I²C, SPI, open-drain, control-input, USB, and architecture
selection passed 216 tests. Ruff and targeted Pyright passed. The fresh
runtime-types, Python-style, Pydantic, and input-contract scans found no
findings in the changed route modules. The architecture profile still reports
low-confidence source-family prompts that can mention themed modules; they do
not establish ownership or call for a split. No exact native KiCad lane ran.
Continue SA-01 with another import-aware returned-map audit, keeping local
accumulators out of the shared-route count.

## Cross-probe board-anchor index route (2026-11-05)

`board_footprint_anchors` now returns the named
`BoardFootprintAnchorsByCasefoldedReference` contract. Its read-only mapping
groups all placements under a case-folded reference key and retains the native
reference spelling and source order in each frozen `BoardFootprintAnchor`.
Case-only collisions therefore remain a multi-anchor result and cannot become
a unique board location.

The import-aware audit found one production consumer in `cross_probe.py`; it
only reads the index. The index is a derived lookup, not source evidence:
`cross_probe.py` verifies the board bytes against the current source hash, and
the resulting `CrossProbeReport` retains that source-hash inventory. No
serialized report or marker behavior changed.

The focused parser and cross-probe consumer selection passed three tests using
the separate public template checkout. Ruff and targeted Pyright passed. The
fresh Alphus scan found no runtime-type, Python-style, Pydantic, or
input-contract findings in the changed route; its provisional complexity scan
still flags `build_cross_probe` for responsibility review. No native KiCad tool
ran.

The optional variant route now also exposes read-only maps in its frozen
`VariantObservation`: artifact paths to validated digests, case-folded
references to parsed schematic components, case-folded references to exact
native names, and the full-board reference index. Construction copies every
map before wrapping it, so caller-owned dictionaries cannot mutate an
observation after validation. The cross-probe operation reads these maps and
revalidates the retained variant evidence before export. Variant evidence
hashes still project into the existing report field; report schema and source
binding are unchanged.

The complete cross-probe and named-variant selection passed 15 tests against
the separate public template checkout. Ruff and targeted Pyright passed. The
scoped Alphus profiles retain their existing totals; the complexity candidate
continues to identify `build_cross_probe` for an ownership review.

### Typed cross-probe request and receipt admission

`CrossProbeBuildRequest` now carries the project identifier, selected parts
receipt, findings receipt, output path, and optional named variant into
`build_cross_probe_request`. The positional `build_cross_probe` function stays
as a compatibility adapter. CLI, MCP, and variant-review composition now build
the same request model and call the typed operation.

`cross_probe_admission.py` owns receipt selection and validation. It admits
only parts and findings that match the selected project and current source
hashes, binds the native summary and optional variant, verifies each retained
drawing, and returns a frozen envelope containing the exact accepted records
and bytes. The operation rechecks that envelope before and after preparing the
HTML view so source or receipt changes abort publication. Anchor capture,
reconciliation, report assembly, and publication remain coordinated by
`cross_probe.py`; no new publication owner is implied by this extraction.

Ruff and targeted Pyright pass for the changed production modules. The
stable current-head Alphus re-sniff found no findings in the changed route
modules across runtime-types, Python-style, Pydantic, input-contracts,
complexity, and shared-utilities. No native KiCad lane is part of this slice.

## Schematic source-tree route (2026-11-05)

The hierarchical schematic reader now returns a VerifiedSchematicSourceTree.
Each SchematicSourceFile retains its repository path, verified SHA-256 digest,
and exact bytes together; model validation checks the digest against those
bytes. The tree also retains the root path and project directory used for
sheet resolution and exposes read-only path-to-file, path-to-bytes, and
path-to-digest projections.

The schematic coverage scanner and findings-view sheet binder now consume
those projections. Schematic instance bindings take the verified tree itself
and reuse each retained digest instead of hashing the payload again. The public
scanner API, serialized finding fields, and source-tree fingerprint remain
unchanged.

The focused source-tree, findings-view, inventory, architecture, and synthetic
open-drain lane selection passed 35 tests with 2 skipped. Ruff and targeted
Pyright passed. No exact native KiCad lane ran. The fresh Alphus scan found no
new finding in this route; see the current record in ALPHUS_QUALITY_GATES.md.
Continue SA-01 with the electrical input-binding map audit, keeping source
admission records distinct from local accumulation dictionaries.

## Electrical input-binding route (2026-11-05)

Electrical input admission now returns BoundElectricalInputs, a frozen record
of path-and-digest entries with explicit roles for design sources, the project
manifest, project checks, electrical requirements, and simulation models.
Repeated paths retain all applicable roles and must resolve to one digest.
Read-only projections expose the complete input hash inventory and the
design-source and simulation-model subsets.

The analyzer uses the source-only projection for native-netlist admission and
simulation requests. End-of-run validation compares the same complete
path-to-digest mapping as before. Saved electrical reports still serialize
input_sha256 with its existing JSON shape, and the evidence verifier continues
to compare that saved map against current inputs. The setup-time
ElectricalInputInventory remains separate: it is an unreviewed capture receipt
and does not include manifest, checks, or requirements as a current-run
admission record.

The electrical evidence, report-owner, CLI/MCP parity, I2C parity, PCB return
parity, and simulator parity selection passed 44 tests and 14 subtests. Ruff
and targeted Pyright passed. The fresh Alphus scan reproduced all nine profile
totals and found no new selector or complaint. No exact native KiCad lane ran.

## Setup and source-state inventory maps (2026-11-05)

The setup-time `ElectricalInputInventory` route is now closed. Its
`source_sha256` and `model_sha256` fields are read-only after validation, while
the shared CLI/MCP service continues to serialize ordinary JSON mappings. This
unreviewed capture receipt remains distinct from the current-run
`BoundElectricalInputs`, which also admits the manifest, checks, and
requirements files.

`SourceState.files_sha256` is also read-only in memory and retains its normal
mapping shape when nested inside static-pipeline and electrical reports. Its
model remains owned by `source_state_models.py`; `models.py` keeps the same
identity-compatible public export. A named Pydantic serializer converts the
immutable mapping at the serialization boundary, avoiding a warning without
changing the report contract.

The focused source-state and electrical setup selection passed 31 tests and 15
subtests with warnings treated as errors. Project Pyright, Ruff, formatting,
and `git diff --check` passed. The three `ElectricalAnalysisReport` indexes
(`input_sha256`, `artifacts_sha256`, and `commands`) have since been traced
through their producer, verifier, release/readiness consumers, and shared
CLI/MCP operation. They are copied and frozen on the report while retaining
their existing JSON objects. The focused implementation and verification are
documented in `ELECTRICAL_ANALYSIS_DATA_ROUTING.md` and the architecture
backlog. Continue the SA-01 inventory with cross-module returns that still
expose an untyped mapping; exclude local accumulation dictionaries.

## Catalog-to-surface route audit: mapped connector supply domains

The active catalog entry for `connector.mapped_supply_domains_share_net`
declares `connectors` as its theme and
`design_lint_connectors_supply_domains.py#mapped_supply_domains_shared_net_candidates`
as its implementation owner. That predicate receives the observed
`NetlistContract` and source-matched `ConnectorCoverageReport`, then emits a
typed candidate whose `MappedSupplyDomainsFindingEvidence` retains both source
records and the exact shared-net assignments. It treats distinct authored
domain identifiers as a review prompt; it does not infer voltage incompatibility
or a physical board fault.

The route continues through `connector_candidates` and
`scan_candidate_result`, then `evaluate_request` applies catalog default modes,
project overrides, and exact-fingerprint ignores through
`resolve_finding_dispositions`. Report assembly retains the catalog and source
identity with the resulting `mode` and `disposition`. The CLI inspection and
MCP `inspect_design_lint` operation both reach the same project-inspection
service and canonical evaluator.

The gap was that no CLI/MCP parity regression selected this exact rule ID.
`tests/test_design_lint_mcp_parity_connector_supply_domains.py` now exercises
the authored interface catalog, native-netlist XML, review mode, and source
digest on both surfaces. It checks the rule owner in the report catalog, the
open review finding and its mapped evidence, and semantic CLI/MCP equality. Its
two controls cover one shared net with one authored domain and distinct domains
on separate nets. A second scenario saves a quiet same-domain report, changes
the authored voltage-domain mapping, and checks that CLI baseline reconciliation
and MCP `reconcile_design_lint` both retain the exact rule as a `NEW` review
transition. The tests use synthetic netlist evidence and do not run native KiCad
or certify electrical approval.

The focused rule, reconciliation-parity, catalog-fixture, rule-selector, and
pytest-marker selection passed 24 tests. Ruff and targeted Pyright passed, and
`git diff --check` was clean. No catalog schema or runtime surface change was
needed. Continue with a rule that has a different evidence input class before
considering module moves.

## Source-bound custom DRC text-variable route

`pcb.custom_drc_text_variable_review` uses a different evidence class from the
connector map route: it reads the project-owned `.kicad_dru` source, the paired
`.kicad_pro` and `.kicad_pcb` sources, their exact digests, and the configured
KiCad version. `pcb_dru_rule_review.py` verifies those inputs against the
current source-hash inventory and emits `PcbDruTextVariableFindingEvidence`.
That typed record retains the unresolved variable names and all three source
identities; it deliberately does not resolve variable values.

Project inspection routes the candidate through the PCB input group into
`evaluate_request`. The catalog's default review mode and project overrides or
exact-fingerprint ignores are applied by the normal disposition service, and
the report preserves the catalog owner and projected hashes. CLI inspection
and MCP `inspect_design_lint` share that evaluator. The CLI and MCP
`reconcile_design_lint` surfaces also share the typed reconciliation service.

`tests/test_design_lint_mcp_parity_pcb_dru_text_variable.py` now asserts the
catalog owner, the source hashes, and the quiet-to-review transition across
inspection and reconciliation. The transition compares separate synthetic
project snapshots with and without the target rule finding, so each side has a
source-matched native-summary receipt. No native KiCad DRC command runs and no
resolved variable value or manufacturing conclusion is asserted.

The focused custom-DRC parity, parser, reconciliation, catalog-fixture,
rule-selector, and marker selection passed 35 tests. Ruff and targeted Pyright
passed; Rumdl and `git diff --check` were clean. The source-text review does not
replace native DRC compilation or validation of resolved variable values.

## Source-bound PCB value-comparison route

`pcb.schematic_pcb_value_mismatch` is owned by
`pcb_component_values.py#compare_schematic_pcb_values`. Project inspection
reaches it through `scan_pcb_geometry`, which captures one native PCB snapshot
and shares that typed evidence with the inventory, population, value, and
pad-net comparisons. The capture binds the board path and digest to the
project's source-hash inventory, checks the configured KiCad version and
pinned image, checks the probe digest and refilled-zone state, and retains
snapshot and native-command receipts. Receipt bytes and digests are checked
again before coverage is returned.

The base-value comparison requires snapshot schema 13 or later. It compares
trimmed CAD value strings for case-insensitive references that have a
nonempty schematic footprint assignment and are fitted in both inputs. Values
are compared case-sensitively. For named variants, the scan requests
same-name netlist and PCB position exports; missing or stale variant evidence
blocks that comparison rather than falling back to base-design data. The
catalog's default disposition is `review`; project overrides and exact
fingerprint ignores use the shared disposition resolver.

`PcbValueMismatchEvidence` retains the mismatch, the shared
`PcbComponentInventorySourceReceipt`, and variant coverage state. The report
projection includes netlist and board identity, snapshot digest and schema,
KiCad version, pinned image, probe digest, and any variant export identities.
The report validator checks the projected board identity against its source
hash inventory. The CLI and MCP inspection paths use the same project
inspection service and evaluator; both reconciliation surfaces use the same
typed reconciliation service.

`tests/test_design_lint_mcp_parity_pcb_value_mismatch.py` now drives the real
capture, inventory comparison, candidate, disposition, and report path for a
source-matched synthetic quiet baseline and value mismatch. Only the external
native-command execution adapter is replaced; the test keeps the capture's
source, version, image, probe, command-shape, and receipt checks active. It
asserts the catalog owner and captured identities, CLI/MCP inspection parity,
and a `NEW` open-review transition through CLI and MCP reconciliation. The
native command result is synthetic, so this verifies route and receipt
semantics without claiming KiCad execution or electrical approval.

The older broad fixture in `tests/test_pcb_component_inventory_mcp_parity.py`
(`test_component_inventory_findings_match_cli_and_mcp`) replaces the entire
geometry scan. It remains useful as report-projection parity coverage; it does
not prove source capture. The new focused fixture separates that guarantee and
is registered as both a fault and valid-control fixture for the active rule.

The focused value-route, underlying comparison, broad inventory parity,
reconciliation, catalog-fixture, selector, and marker selection passed 31
tests. Ruff and targeted Pyright passed. No exact native KiCad lane ran.

## Source-bound PCB pad-net comparison route

`pcb.schematic_pcb_pad_net_mismatch` is owned by
`pcb_pad_net_comparison.py#compare_schematic_pcb_pad_nets`. Project inspection
provides the admitted native schematic netlist and source hashes to
`scan_pcb_geometry`. The scan resolves the rule's mode, captures one shared
`PcbGeometrySourceEvidence`, and passes it to
`scan_pcb_component_inventory` alongside the inventory, population, and value
modes. The source capture checks the authoritative board path and digest,
configured KiCad version, pinned image, probe digest, refilled-zone state,
native command shape, and snapshot/command receipts. The inventory comparison
accepts snapshot schemas 12 through 15.

`evaluate_native_component_inventory_coverage` coordinates the comparisons
that share the snapshot; it is not the owner of the individual pad-net
predicate. It carries the source receipt fields in
`PcbComponentInventorySourceReceipt`: netlist digest, board path and digest,
snapshot digest and schema, KiCad version, image, and probe digest. Missing
netlist identity or unsupported snapshot schema blocks the comparison route.
If only the pad-net predicate raises `ValueError`, the pad-net subcomparison is
`BLOCKED` while other successfully completed inventory checks can remain
complete. An `off` rule mode stays `DISABLED` and emits no pad-net candidate.

The predicate compares explicit schematic pin assignments with same-numbered
native PCB pads for matching case-insensitive references and footprint IDs.
Net names remain exact after native netlist normalization. The result reports
assignment mismatches; it does not infer that peer pins must be bonded or prove
routed copper continuity or physical conduction.

`design_lint_pcb_pad_net_candidates.py` converts either an exact mismatch or a
blocked comparison into a candidate. The evidence owner,
`design_lint_pcb_pad_net_candidate_evidence.py`, projects the typed observation
with the shared source receipt. The active catalog entry points at the
predicate owner. The default rule mode is `review`; the normal disposition
resolver applies project overrides and exact fingerprint ignores after
candidate generation. CLI inspection, MCP inspection, and their
reconciliation operations share the same typed evaluator and source route.

`tests/test_design_lint_mcp_parity_pcb_pad_net_mismatch.py` exercises a quiet
baseline and a mismatching source-bound synthetic project through live source
capture, receipt checks, comparison, candidate projection, CLI/MCP parity, and
a `NEW` open-review reconciliation transition. The test replaces only native
process execution; its snapshot and command receipt are synthetic, and no exact
native KiCad lane ran. The test is registered in the active rule's fault and
valid-control fixtures. The broad
`test_pcb_component_inventory_mcp_parity.py` fixture remains projection
parity because it replaces the full geometry scan; it does not certify source
capture.

## Source-bound PCB DRC exclusion candidate evidence

`pcb.drc_exclusion_present` remains owned by
`pcb_drc_exclusion_review.py#source_bound_pcb_drc_exclusion_candidates`. The
review service admits the configured `.kicad_pro` path from the source-hash
inventory, checks the exact settings digest before and after parsing, and
restricts the rule to PCB projects using the supported KiCad 10.0 settings
schema. Missing, stale, linked, malformed, or unsupported inputs fail closed
or remain out of scope according to the existing service contract.

The candidate route now carries `PcbDrcExclusionFindingEvidence`: the exact
project-relative path, captured source digest, configured KiCad patch version,
and parsed marker/comment record. `project_pcb_drc_exclusion_evidence` owns the
projection into the stable report evidence keys. `PcbDrcExclusionCandidate`
derives its subject and message from that source object and rejects report
fields that do not match the projection. The outer review service still owns
source admission and freshness checks; retaining a digest in a candidate does
not itself prove the file is current.

The candidate rule ID, subject fingerprint, wording, evidence values and key
order, ordering behavior, and disposition flow remain unchanged. This route
does not run DRC, resolve markers against board geometry, or decide whether an
exclusion is acceptable. At the DRC-route checkpoint, a direct-AST inventory
found 28 production `Candidate(evidence=...)` constructions in 28 modules,
with 26 literal maps; this inventory only recognized direct calls named
`Candidate` and did not claim complete data-flow coverage.

## Mapped LED current candidate source evidence

`component.mapped_led_current_range_mismatch` retains the authored
`LedCurrentMap`, an independent typed copy of the normalized netlist, its
supplied source digest, and the exact calculated entry in
`LedCurrentRangeFindingEvidence`. Construction re-evaluates the entry against
those retained inputs. `project_led_current_range_evidence` owns the existing
report mapping, while `LedCurrentRangeCandidate` checks that the candidate
subject, message, rule ID, and evidence still match that source projection.

`led_current_range.py#evaluate_led_current_requirement` remains the
calculation owner and the component scanner remains responsible for whether an
entry becomes a candidate. The report schema, evidence values and key order,
finding order, fingerprint inputs, and review-only policy are unchanged. The
candidate retains the scanner-supplied digest; it does not independently
authenticate the native file. The active catalog-reachability fixture now
exercises this fault. The focused route validation passed 20 tests, targeted
production and test Pyright plus Ruff, and the direct-call census reports zero
generic `Candidate(evidence=...)` calls in production design-lint modules.

## Component-role report-field projection

The shared component-role projector previously returned a generic
`dict[str, tuple[str, ...]]` to the LED and two-pin candidate owners. Those
candidates already retained the authored `ComponentRoleBinding` and its
identity; the returned map represented only the corresponding report fields.

`component_roles.py` now names that output as
`ComponentRoleBindingReportFields`, with explicit keys for role, part ID,
symbol, footprint, pin inventory, basis, and binding digest. Each rule-owned
projector merges those fields only while constructing its existing
`CandidateEvidenceProjection`. The common projection freezes the final
mapping. Synthetic regressions check the exact evidence values and key order;
the architecture test checks the named field set and return type. No rule,
source identity, disposition, or serialized field changed.

The focused LED/two-pin source and architecture selection passed 34 tests.
Targeted Pyright, Ruff, formatting, and scoped `git diff --check` passed. No
exact native KiCad lane was required for this mapping projection.

## Mapped thermal-pad via coverage route

`pcb_thermal_vias.py#pcb_thermal_via_entries` compares each project-authored exact
pad/footprint/net, fitted state, center-distance bound, layer span, and minimum
via multiplicity with one source-bound native PCB connectivity snapshot. It
counts only vias in the pad's KiCad-reported connectivity component, within the
reviewed radius and on the exact required span. The finding projection retains
the typed report and its source digests; scan coordination and project policy
remain in the existing PCB geometry and design-lint evaluation services.

`pcb.explicit_thermal_pad_scope_unreviewed` is a separate review prompt owned by
`design_lint_pcb_thermal_pad_scope.py`. It matches only exact exported `EP`,
`EPAD`, `EXPOSED PAD`, and `THERMAL PAD` functions on fitted PCB endpoints with
assigned footprints, then asks whether an independently authored map entry is
needed. It does not infer that the pad needs vias. Both rules use the shared
typed CLI/MCP design-lint report and default to review. Native fixtures use
source-hashed synthetic inputs and exact KiCad 10.0.0/10.0.5 image pins.
