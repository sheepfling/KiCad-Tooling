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

The public `candidates()` call accepts 49 arguments and remains available to
direct predicate consumers. Full evaluation now builds the grouped scanner
inputs from `DesignLintEvaluationPreparation`, whose coverage has already been
source-checked. Keep the public call shape for compatibility and continue
migrating direct consumers by capability group. Direct `candidates()` calls
remain unverified observations unless the caller supplies and validates the
relevant source identity.

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

The six schematic power and supply findings in `design_lint_power_candidates`
now retain their typed scan records through `PowerCandidate`. Its projector
owns the existing same-voltage pin map, capacitor-gap fields, conditional
source-anchor state, connector/capacitor fields, repeated-supply pin map, and
numbered-rail map. The adapter still owns rule ordering and finding wording;
the serialized evidence keys and fingerprints stay unchanged. Pin and rail
source maps are copied and frozen so retained records cannot drift from their
report projection after candidate construction.

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
