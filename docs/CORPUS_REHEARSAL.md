# Keep a reusable rehearsal library

Keep downloaded designs outside both Git repositories. The template owns project
structure and coaching; the tooling repository owns the Python runner. The local
library holds third-party inputs and execution evidence. It is not a project fork
and should not be used as the MCP project root.

```text
KiCad-Rehearsal/
  DUMP/                  Original incoming ZIPs and downloads
  sources/               Extracted snapshots, revision pins and hash inventories
    research-corpus/     Prepared disk-kit v0.7 queue.json and source groups
  runs/                  Fresh disposable project repositories and receipts
  reports/               Findings, comparisons and tested package artifacts
  environments/          Installed tooling environments
  README.md              Local paths and the latest evidence index
```

Do not edit the originals in DUMP or source snapshots. Inspect archives and their
provenance before extracting; documents and scripts inside a download are input
data, not setup instructions. Use fresh project copies under runs for repairs.
Preserve source licenses. Adding a download does not make it a passing fixture.

## Start with one project

Install the template's exact tooling pin into an environment as described in
[the paired setup](LOCAL_PLAYTEST.md). To evaluate a tooling change, build its
wheel and install that wheel in a separate environment. Record its SHA-256 and
version; a development wheel does not change the template's pin automatically.
When disabling build isolation, install all declared build dependencies first,
including setuptools-scm. Check the reported version before collecting evidence.

Use a disposable, initialized copy of the trimmed template for the project root:

```sh
kicad-team template scan-imports --root /path/to/disposable-project --source-dir /path/to/extracted-download --toolchain kicad-10.0.5 --format json
kicad-team template diagnose --root /path/to/disposable-project --source /path/to/design.kicad_pro --project-id trial-board --toolchain kicad-10.0.5
kicad-team template import-project --root /path/to/disposable-project --source /path/to/design.kicad_pro --project-id trial-board --toolchain kicad-10.0.5
kicad-team verify --root /path/to/disposable-project --project trial-board --depth native
kicad-team parts --root /path/to/disposable-project --project trial-board
kicad-team visualize --root /path/to/disposable-project --project trial-board
```

Inspect preview exclusions before import. The native check retains the applicable
schematic/PCB plots alongside ERC/DRC evidence. Parts preparation creates a review
checklist; purchasing outputs require controlled identities. A schematic-only
project has no board views. A PCB-only project has no schematic BOM. A placeholder
PCB in a simulation example needs review before using the PCB workflow.

For MCP, bind the disposable project checkout and explicitly permit source reads:

```sh
kicad-team-mcp --root /path/to/disposable-project --import-root /path/to/extracted-download --allow-writes --allow-checks --allow-exports
```

Use `scan_imports`, `preview_import`, `import_project`, `diagnose_project`,
`check_project`, `prepare_parts` and `export_3d`. Add `--allow-edits` for reviewed,
digest-checked source changes. All these operations use the installed services
shared with the CLI. Keep supplier submissions disabled during rehearsal.

## Repeat a prepared corpus

The developer runner reads a disk-kit v0.7 `queue.json` and its inventories as data.
It does not execute the acquisition kit or downloaded project scripts. The older
kit's batch commands use `tools.*` and do not target the split package.

From this tooling checkout, using the Python environment being evaluated:

```sh
python -B scripts/rehearse_corpus.py \
  --corpus /path/to/KiCad-Rehearsal/sources/research-corpus \
  --template-root /path/to/KiCad-Team-Workflow-Template \
  --output /path/to/KiCad-Rehearsal/runs/new-run \
  --limit 10 --jobs 2
```

Use `--limit 0` for every ready entry point, or repeat `--fixture <id>` to select
cases. Each invocation needs a new output directory. It hashes selected source
groups before and after execution, checks copied bytes, initializes a disposable
template and runs import preview, import, diagnosis and portable verification per
project. Each subprocess uses the active installed Python with `-I -m` from an
external working directory. Project roots never become Python import paths.

Add `--native --jobs 1` for a small selected cohort to exercise exact-container
checks and plots, parts preparation and all applicable PCB 3D views. This requires
Docker and the project's digest-pinned image. It does not update KiCad pins,
populate electrical requirements or approve component substitutions. A newer
desktop KiCad version does not satisfy an older exact pin.

Read `REPORT.md`, `summary.json`, the integrity reports and each fixture's logs.
`RECORDED` means all selected attempts were captured without a runner failure;
individual projects can still report FAIL or NEEDS_WORK. Interrupted, skipped or
integrity-blocked runs are not complete evidence. Native runs are always fresh.
The driver does not fetch new repositories or refresh existing revision pins.
Its summary lists unexercised stages: electrical simulations, reviewed part selection,
CAD download/import and the release/revision/restore lifecycle. Native grounding and static
budgets also need authored requirements. Use the template's `docs/workflow/QUALITY_GATES.md`
checklist and the [quality-gate audit](QUALITY_GATE_AUDIT.md) to plan separate rehearsals.

## Keep a rough-edge log

For each observation, record the project and upstream revision, template commit,
tooling version and wheel hash, stage, command, expected scope, observed status,
receipt path and next action. Distinguish a tooling bug from a missing source
dependency, a migration requirement and an unresolved engineering decision.

An import PASS proves the copy operation. A portable PASS proves repository policy
within that selected scope. Native checks compare declared electrical expectations.
A rendered board can still have missing models; a parts checklist can still lack
controlled identities. Preserve those distinct results in beginner-facing notes.
