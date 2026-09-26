# Reusable project CI

Tooling owns the shared GitHub job definitions as well as their Python implementation. A project
repository keeps four small callers, project data, a reviewed `requirements-tooling.txt`, and its
own triggers and selection controls. The public
[template workflows](https://github.com/sheepfling/KiCad-Team-Workflow-Template/tree/main/.github/workflows)
show the complete callers.

## Workflow interfaces

| Workflow in `.github/workflows/` | Inputs                                                    | Behavior                                                                             |
| -------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `kicad-template.yml`             | `focus` (default `full`), `value`, `exclude_tag`, `shard` | Plan scope, portable checks, declared native lanes, release rehearsal and final gate |
| `3d-preview.yml`                 | Required `project_id`                                     | Selected board views, STEP and GLB                                                   |
| `electrical-analysis.yml`        | Required `project_id`                                     | Declared electrical requirements and charts                                          |
| `release-candidate.yml`          | Required `project_id`                                     | Prepare, verify, package and restore engineering review                              |

All inputs are strings. Acceptance uses the caller event: pull requests plan from their base
commit, pushes run full acceptance, and manual dispatch accepts `full`, `branch`, `project`,
`product` or `tag`. `value` supplies the selected ID or branch base. `exclude_tag` and
`shard=INDEX/COUNT` narrow manual cohorts. A shard is partial evidence.

A caller job uses this form; replace `<reviewed-40-character-commit>` with an actual Tooling SHA:

```yaml
permissions:
  contents: read
jobs:
  acceptance:
    name: Verification
    uses: sheepfling/KiCad-Tooling/.github/workflows/kicad-template.yml@<reviewed-40-character-commit>
```

Keep cancellation policy and manual input menus in the caller. Do not copy the reusable jobs,
pass secrets, or add checkout/install steps to a calling job. Jobs execute in the adopting
repository's Actions run, using its token, source and artifacts. Every checkout uses GitHub's
caller defaults, including the pull-request merge commit. No project data is checked out into
this public repository. Private adopters must allow these public reusable workflows in their
Actions policy. Project tests execute trusted code; retain normal fork-PR permission boundaries.

Each job installs the adopting repository's `requirements-tooling.txt`. There are two explicit
pins: the workflow commit selects job orchestration, and the requirements pin selects Python.
Update both through a reviewed project PR when a workflow requires newer Python services.
Existing compatible Python pins can remain unchanged for orchestration-only updates.
Never replace either pin with an unbounded branch or latest version.

## Validation and evidence

Portable policy runs on Linux/macOS, with the installed-command and path smoke lane on Windows.
Native KiCad, simulator builds and release jobs use Linux and declared, pinned native tools.
The same installed Python commands can be rehearsed locally on supported platforms; GitHub
runner and artifact setup remains declarative YAML.

The final `Template acceptance` job rejects failed, cancelled, missing or unexpectedly skipped
prerequisites through `kicad_tooling.ci_hosted gate`. GitHub can qualify a reusable job's check name
with the caller job name. When migrating, inspect the actual successful check-run name and update
required checks and the project governance catalog together. Keep the existing required gate
until the replacement has passed. Do not disable protection or require a skipped matrix child.

Logs and receipts remain in the caller's `build/ci-hosted/` and run artifacts, including failures.
Package CI tests orchestration boundaries and Python behavior against a pinned external public
fixture. A paired workflow change also needs a real project PR run; exercise focused selection
and the affected manual lanes before updating adopters. Passing CI does not approve a design.
