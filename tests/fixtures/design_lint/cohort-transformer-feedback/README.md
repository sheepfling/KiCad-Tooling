# kicad-happy TF-001 detector-level trial

This tooling-owned synthetic probe evaluates the pinned kicad-happy
`detect_transformer_feedback` function without installing its workflow or
copying its implementation into this repository.

## Pinned source

- Release: `v2.3.1`
- Commit: `06840467ad0f5d76af45f64449b1f5ecb10f052f`
- License: MIT
- Detector: `skills/kicad/scripts/domain_detectors.py`,
  `detect_transformer_feedback`

## Cases and observed behavior

`trial_tf001.py` supplies small in-memory component and pin-net records to the
exact detector function. It includes no KiCad project source or native export.

| Case                  | Synthetic evidence                                                                                                                            | Detector result                                                                            |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `keyword_match`       | UC3842, PC817, and TL431 value/library identities; matching pins/nets; no transformer component                                               | TF-001 lists U1/U2/U3 and labels confidence `deterministic`                                |
| `controller_only`     | UC3842 only, with no optocoupler, TL431, or transformer                                                                                       | TF-001 still emits an isolated-SMPS controller record, with confidence `heuristic`         |
| `role_agnostic_match` | The feedback and shunt nets match arbitrary optocoupler/TL431 pin numbers; the supplied pin names do not identify the roles the report claims | TF-001 reports the same optocoupler and shunt relationship with confidence `deterministic` |

The repeated function calls return identical records for these fixed inputs.
This is a detector-level probe, not a parser, CLI, public-board, or native
KiCad trial. It shows that TF-001 can classify a keyword-and-net pattern; it
does not establish an isolated converter, transformer, valid feedback loop,
or defect. The broad controller-only and role-agnostic records do not add a
deterministic electrical check beyond exact project-authored pin/path
requirements. No local rule or runtime dependency was adopted.

## Reproduce

From the tooling checkout, clone the pinned public source into a temporary
directory, copy only this tooling-owned runner into its scripts directory, and
run it with the active Python interpreter. No package installation is needed.

```sh
git clone --depth 1 --branch v2.3.1 https://github.com/aklofas/kicad-happy.git /private/tmp/kicad-happy-v231
cp tests/fixtures/design_lint/cohort-transformer-feedback/trial_tf001.py /private/tmp/kicad-happy-v231/skills/kicad/scripts/
.venv/bin/python -E -S -B /private/tmp/kicad-happy-v231/skills/kicad/scripts/trial_tf001.py
```

The runner stays in the temporary cohort checkout during execution. The
synthetic contexts are authored in this fixture, and the external source tree
can be removed afterward.
