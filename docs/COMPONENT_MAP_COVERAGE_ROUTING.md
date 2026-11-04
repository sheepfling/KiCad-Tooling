# Component-map coverage routing decision

This route covers I2C address, crystal-network, regulator-feedback, RC-filter,
and connector return-distribution maps. It fixes how authored maps, optional
precomputed coverage, and one native netlist enter coverage resolution. It does
not change a rule, report schema, fingerprint, or engineering conclusion.

## Route

1. `DesignLintPolicy` supplies authored maps. The public evaluator remains a
   compatibility adapter and packs its legacy coverage parameters into one
   `ComponentMapCoverageInputs` record.
2. Evaluation preparation binds that record to the policy, observed
   `NetlistContract`, and coach's netlist digest in a
   `ComponentMapCoverageRequest`. The resolver is the owner. A missing supplied
   report means “resolve from the configured project map”; with no configured
   map, the output is `NOT_REQUESTED`. It returns one `ComponentMapCoverage`
   record.
3. A supplied positive report (`COMPLETE` or `INCOMPLETE`) is usable only when
   its retained netlist digest matches the coach's current digest. Return
   distribution also requires the same interface-catalog digest as the
   connector coverage used for resolution.
4. Stale or unbound positive coverage becomes `BLOCKED`. The resolver drops
   rows that could create candidates, retains the original digest(s), and
   explains the mismatch. The candidate scanner receives the normalized
   coverage; report assembly serializes those same normalized records.
5. The report validator independently enforces current source identity for
   positive states and reconciles complete finding lists with applicable
   coverage rows. A blocked or incomplete finding list does not become a clean
   comparison.

| Input                   | Owner                         | Meaning of absence or mismatch                                                           |
| ----------------------- | ----------------------------- | ---------------------------------------------------------------------------------------- |
| Authored map            | `DesignLintPolicy`            | No map and no supplied report yields `NOT_REQUESTED`.                                    |
| Observed native netlist | `ContractCoachReport`         | No ready, source-bound netlist blocks evaluation before this route.                      |
| Supplied coverage       | `ComponentMapCoverageInputs`  | `None` asks the resolver to scan the configured map; stale positive reports are blocked. |
| Connector coverage      | Connector coverage producer   | Return-distribution checks require its interface-catalog identity.                       |
| Resolved coverage       | `ComponentMapCoverage`        | Typed report records flow to theme candidates and the public report.                     |

`COMPLETE` means the configured scope was compared; it does not mean every row
passed. An `OUT_OF_RANGE` comparison remains covered and must keep its review
finding. `INCOMPLETE` retains the rows from a current scan and identifies the
unresolved comparison. `BLOCKED` preserves the stale source identity while
withholding rows from candidate generation. `NOT_REQUESTED` means no map or
coverage was requested; it is not evidence of a successful scan.

## Acceptance

The owner accepts one frozen request instead of a wide keyword list. Tests
cover absent maps, valid current coverage, stale netlist coverage, stale
interface-catalog coverage, blocked row suppression, and report-level source
and finding reconciliation. The public evaluator parameters and report JSON
remain stable during this routing step.
