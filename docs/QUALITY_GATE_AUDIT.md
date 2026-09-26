# Junior workflow quality-gate audit

This audit distinguishes available checks from actual rehearsal coverage. It accompanies the
template's `docs/workflow/QUALITY_GATES.md` checklist and the [corpus runner](CORPUS_REHEARSAL.md).
Project requirements and approvals remain in the template-derived project repository; Python
services, protocol adapters and shared regressions remain in this tooling repository.

## What is available

| Area                 | Shared CLI/MCP behavior                                                                                                  | Important boundary                                                                                                         |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| Connectivity         | Native ERC/DRC and source-bound netlist comparison with independently authored expectations                              | A passing comparison cannot establish completeness of those expectations.                                                  |
| Grounding            | Required domains/pins, wrong/missing/extra connections and component coverage or reasoned exemptions                     | Does not certify return-plane layout, earth continuity or compliance with an electrical standard.                          |
| Power                | Static simultaneous load budgets and modeled startup/steady-state current/power limits                                   | Ratings, derating, thermal limits and model mapping require engineering review.                                            |
| Transients/frequency | Bounded transient and AC analyses, exact ngspice version, model/source hashes, finite measurements and waveform evidence | Effects absent from the model or measurement contract remain unassessed; no automatic PCB extraction or EMC qualification. |
| Part selection/BOM   | Controlled identities, quantities/spares, fitted population, preview/apply and conditional purchasing CSV                | No automatic substitute approval or live stock/price guarantee.                                                            |
| CAD                  | Exact supplier/MPN identity, frozen source, converter provenance, pin/pad consistency and reviewed library import        | Matching numbers and valid geometry do not establish pin function or physical fit.                                         |
| Revision/release     | Source commit and tag binding, scoped evidence, archive integrity and restore                                            | Board revision differs from package version. MCP engineering-review tools do not grant production release authority.       |

The packaged `tool-surfaces.json` records matching operations, behavioral tests and explicit
exceptions. Its inspection proves interface alignment; running the cited tests proves only their
fixtures. Neither establishes that every downloaded design has passed those gates.

## Rehearsal evidence

The September 25 local audit, with receipts dated September 26 UTC, used the split worktrees
at tooling commit `4a76e6502a24e4eac3f3d2ad50899610a8f03f6c` and template commit
`d3b02fa861e95746224f3767e2174fec85c06e4a`, including the uncommitted coverage guidance changes.
Wheel hashes distinguish development builds that have the same setuptools-scm version.

- The prior corpus run covered 335 import candidates, with 330 imports and five preview
  rejections. A four-project native cohort exercised applicable native plots, parts checklists
  and 3D output. It did not establish complete electrical, purchasing or release coverage.
- The quality audit passed 237 focused electrical, parts, CAD and release regression tests.
  These include bad grounds, overloaded rails, stale models/native evidence, simulator and
  measurement failures, wrong CAD identity, BOM drift and archive tampering. Some use synthetic
  native/supplier outputs; they are not live supplier or physical-hardware acceptance.
- A fresh installed wheel ran real ngspice 47 and digest-pinned KiCad 10.0.0 on a disposable
  copy of the controller training fixture. The combined native/electrical verification passed.
  The standalone CLI and MCP electrical findings and input hashes matched exactly.
- Four existing synthetic cases passed: startup, steady-state draw, AC passband and edge
  response. Saved-receipt charts/CSV exported through MCP. The decks illustrate independent
  RC models; they are not a power/signal model of the controller PCB or any downloaded board.
- Five deliberate faults were also exercised against the real saved KiCad evidence and
  simulator: wrong ground pin, excess continuous load, startup current outside its limit,
  AC gain outside its limit and changed model bytes. CLI and MCP both preserved FAIL with
  identical findings; all synthetic source/requirement bytes were restored afterward.
- A live exact `C2040` / `RP2040` CAD lookup produced READY source and a PLAN import preview.
  MCP reused the same verified cache offline. CAD was not applied or approved for a real design.
- Parts preparation returned NEEDS_PARTS for the training identities. No purchasing-ready BOM,
  supplier submission, order, real board revision or production release is claimed by this run.
- Final package CI passed all 937 tests, lint, native/Windows type checks, strict Markdown,
  wheel/source-distribution equivalence and fresh installed CLI/MCP rehearsals, including a
  configured alternate project layout. The template's full portable gate also passed.

Local evidence belongs in the reusable library under `reports/quality-gates-20260926/`, with
the disposable project and its original receipt paths retained in the run archive. Do not commit
downloaded source, generated charts, native outputs or the environment into either repository.

## Improvements made

Diagnosis now reports missing electrical requirements as an `ELECTRICAL_NOT_CONFIGURED` review
task for PCB and schematic projects. It gives the pending-contract setup and combined-check
commands. This does not change a scoped portable PASS into a failed electrical result.

Passing portable/native verification now includes a CLI/MCP next action explaining that full
electrical analysis was not run. Text output shows the electrical analysis status even when
absent. Existing configured static-budget/native-grounding results keep their meaning.

The corpus runner explicitly lists its unexercised stages in JSON and Markdown. The template
first-board guide and agent instructions now point at the complete quality-gate checklist.

## Electrical enforcement follow-up

Normal hosted native lanes now run declared electrical contracts after KiCad checks. Pending or
failed electrical requirements fail the selected project lane. Simulator setup and selected
release rehearsal live in Python with retained logs; YAML only supplies runner prerequisites and
artifact retention. Projects without a contract remain explicitly NOT_CONFIGURED.

Release preparation requires passing declared electrical checks and retains their requirements,
generated decks, logs and waveforms. Check, package, verify and restore bind those receipts to the
clean source commit and revalidate required measurements, waveform coverage and current native
grounding evidence without executing models during restore. Build releases require a contract for
schematic-backed boards; reasoned nonapplicability remains a reviewed project decision. The review
record makes missing electrical coverage visible for engineering-review candidates.

The regression tests include incomplete or stale evidence, rehashed failed measurements,
missing waveforms, changed models, a failing hosted electrical lane and a CLI/MCP archive round
trip. These synthetic fixtures prove workflow enforcement, not real-board design acceptance.

The installed-wheel follow-up exercised the normal native/electrical lane and a checksum-verified
cold ngspice 47 build. Two synthetic reference-board revisions retained 58 candidate artifacts each,
including BOM/placement exports and four electrical waveforms, and restored to their exact source
commits through CLI/MCP. A changed model and the previous candidate were rejected before fresh
preparation. Generic training identities remained NEEDS_PARTS, without purchasing authority.

The real-board samples were StickHub from demos and SBK_RP1 from the rehearsal corpus. Both kept
missing reviewed component/net/electrical requirements and part identities as blockers; StickHub
also reported legacy CAD paths. Pending electrical starters failed the focused lane and prevented
release preparation. These project issues were retained rather than waived. Full local evidence
lives in the reusable library's `reports/workflow-closeout-20260926/` directory.

## Remaining work

1. Author representative, reviewed real-board grounding, power and frequency requirements for
   a small corpus cohort. Never derive passing limits from its observed behavior.
2. Rehearse a real reviewed component population through a purchasing-ready BOM and a complete
   revision/package/restore cycle. Regression fixtures cover the mechanics; the corpus run does not.
3. Retain physical/layout review and measurements for grounding, thermal margin, transients,
   signal integrity, EMC and mechanical fit as appropriate to the design. Automated model checks
   support that review but do not replace it.

For each next rehearsal, retain expected failure as well as success: missing/pending requirements,
wrong ground pin, excess load, insufficient settling or frequency coverage, changed model hash,
wrong MPN/package, changed population, stale BOM and a tampered or incomplete release archive.
