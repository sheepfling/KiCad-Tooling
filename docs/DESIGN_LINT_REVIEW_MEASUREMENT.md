# Design-lint review and cohort measurement

Use this worksheet to measure a heuristic or cohort feature against the
current tooling baseline. It supplements deterministic synthetic tests and
exact-version native fixture runs; it does not replace either one.

Keep these evidence levels separate:

1. **Synthetic behavior:** named fault and valid-control fixtures exercise the
   predicate and its supported boundaries.
2. **Native compatibility:** repeatable exports on the exact declared KiCad
   version establish that the source evidence is interpreted consistently.
3. **Applicability:** approved public or otherwise authorized designs show
   where the predicate can and cannot evaluate.
4. **Independent review value:** an informed reviewer records a disposition
   and, when measured, review time. Only this level supports claims about
   useful findings, false prompts, or time saved on real designs.

One level does not imply another. A synthetic split mutation demonstrates
fixture sensitivity, not field recall. A quiet result on a supported path is a
non-finding, not evidence that the path's electrical policy is correct.

## Source and privacy boundary

Use tooling-owned synthetic inputs for seeded faults and controls. For public
or otherwise approved design samples, retain the checkout and generated native
exports outside this repository. Record an immutable source URL and revision,
license or permission basis, source-file hashes, toolchain version and image
digest, export hashes, and report hash. Do not commit project source, raw
exports, reviewer names, customer identifiers, or private file paths. Keep
only the minimum metadata needed to reproduce the conclusion.

If source permission, applicability, or expected policy is unclear, record the
sample as unresolved or unsupported. Do not infer a false positive from a
missing requirement or from a quiet baseline.

## Run header

Fill one header per frozen measurement run. Leave unavailable fields blank and
explain why; do not estimate hashes, counts, times, or dispositions.

| Field                                                          | Value |
| -------------------------------------------------------------- | ----- |
| Measurement ID                                                 |       |
| Tooling commit and rule ID, or cohort name/version/commit      |       |
| Baseline commit and invocation                                 |       |
| Candidate invocation and installation steps                    |       |
| License or permission basis                                    |       |
| Exact KiCad version and image digest, if native export is used |       |
| Source URL and immutable revision, if applicable               |       |
| Source-file SHA-256 values                                     |       |
| Raw export SHA-256 values                                      |       |
| Normalized evidence and report SHA-256 values                  |       |
| Reviewer protocol and counterbalanced order, if measuring time |       |

## One row per evaluation unit

Choose the evaluation unit that matches the rule, such as a connector-to-IC
path, peer group, pin relationship, or board-level geometry requirement. State
the unit and denominator before reviewing results. Do not merge ports,
endpoints, or findings that the report distinguishes.

| Sample / unit ID | Applicability                                      | Baseline result | Candidate result | Independent disposition | Baseline min | Assisted min | Notes |
| ---------------- | -------------------------------------------------- | --------------- | ---------------- | ----------------------- | -----------: | -----------: | ----- |
|                  | `supported` / `incomplete` / `unsupported` / `DNP` |                 |                  |                         |              |              |       |

Use these independent dispositions for a prompted unit:

- `actionable_policy_gap`: review led to an authored requirement or exposed a
  mismatch against an existing reviewed requirement.
- `documented_no_action`: approved design evidence already resolves the case
  and no review or requirement update is needed. This is the only disposition
  counted as a false prompt.
- `baseline_duplicate`: the same review was already required by another
  independent check or native diagnostic.
- `unresolved`: available evidence does not establish the intended policy.

For a quiet, fully supported unit, record `supported_non_finding`; this is not
a false-negative or proof of correctness. Keep incomplete, unsupported, and
DNP-only units in coverage totals, outside supported-path precision
denominators. A missing disposition is unresolved, not a false prompt.

## Seeded mutation results

Run mutations only against tooling-owned synthetic fixtures. List every
applicable mutation and valid control, including expected and observed result.

| Fixture / mutation ID | Case                             | Expected result | Observed result | Pass / miss | Notes |
| --------------------- | -------------------------------- | --------------- | --------------- | ----------- | ----- |
|                       | fault / valid control / boundary |                 |                 |             |       |

Report seeded-fault sensitivity separately from public-sample findings. Do not
combine synthetic controls with independently reviewed field outcomes.

## Summary and decision

Report counts with their denominators:

- Supported, incomplete, unsupported, and DNP-only evaluation units.
- Prompted units by independent disposition.
- Supported non-findings.
- Seeded faults detected, seeded faults missed, and valid controls that
  prompted.
- Unique confirmed findings versus findings already present in the baseline.
- Reviewer minutes per unit. For time saved, compare baseline-only with
  report-assisted review using counterbalanced order and disclose sample
  counts, unresolved cases, and the timing method.
- Installation, version, and maintenance burden for each cohort feature.

Do not publish a precision or false-prompt rate while prompted units remain
unresolved. Do not claim recall from seeded mutations alone. Classify the
incremental outcome as detection gain, review-localization gain, maintenance
gain, duplicate, or no demonstrated gain. Keep a heuristic at `REVIEW` unless
project-authored requirements and their fault/control evidence justify a
blocking comparison.

## Existing rule-specific protocols

- [LINT-031](DESIGN_LINT_BACKLOG.md#lint-031--candidate-analyzer-trial-and-incremental-value-register)
  records cohort feature trials, version/license/install friction, unique and
  duplicate findings, misses, and maintenance cost.
- [LINT-086](DESIGN_LINT_BACKLOG.md#lint-086--usb-peers-use-different-explicit-reference-nets)
  adds USB path counts, reference-policy dispositions, and mutation
  sensitivity fields for its supported topology.
