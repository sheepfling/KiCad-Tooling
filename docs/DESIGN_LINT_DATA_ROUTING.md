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
3. `design_lint_evaluation_preparation.py` compares source-bound I²C coverage,
   including an empty `COMPLETE` result, with the coach's netlist hash. A
   mismatch blocks the evaluation before candidate scanning.
4. `design_lint_evaluation_candidates.py` constructs required capability-group
   inputs directly from prepared, source-bound evidence. The public
   `candidates()` compatibility adapter constructs those same records from its
   legacy arguments. Both call `scan_candidates()`.
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
- Fingerprints currently hash `Candidate.evidence`, a mapping of named string
  tuples. Keep that public evidence shape and its normalization unchanged in
  this routing pilot. A future typed finding-evidence variant needs its own
  versioned report and fingerprint migration decision.
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
attach typed bus, clock, or pair identities to their internal candidates. Each
candidate checks that its typed identity and serialized evidence agree at
construction and before coverage assembly, since the evidence dictionary can
be mutated after construction. `PeerReferenceCandidateKeys` collects typed
identities for coverage; a candidate with the right rule ID but no typed
identity fails before disposition. The public finding evidence
and fingerprint stay the same. The broader extension path should formalize
typed theme results rather than adding metadata fields to the shared candidate
type for each new rule.
