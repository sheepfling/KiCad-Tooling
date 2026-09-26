# KiCad Team Tooling

This repository contains the Python CLI and MCP services for KiCad team projects.
Project source, requirements, catalog records, and engineering decisions stay in a
project repository created from the
[KiCad team workflow template](https://github.com/sheepfling/KiCad-Team-Workflow-Template).
The same installed package provides both command surfaces.

The template now consumes this package through an exact dependency pin. It keeps
project structure, catalogs, engineering contracts, agent guidance, and onboarding
documents. Shared Python implementation, reusable GitHub workflows and their regression
suite live here. See [project CI](docs/PROJECT_CI.md) for pinned callers and upgrades.
The package is not published on PyPI yet; the template pins a reviewed Git commit.

## Try the separate package

From a project checkout, install this repository into a Python 3.11 or newer
environment. Replace the path with the location of your tooling checkout:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -e '/path/to/KiCad-Tooling[project,mcp,charts,cad]'
.venv/bin/kicad-team template list --format text
.venv/bin/kicad-team verify --project <id> --format text
.venv/bin/kicad-team surface --format text
```

Use `--root /absolute/path/to/project` to run a CLI from another directory. The
default is the current working directory. The inventory reports input presence;
`verify` runs the selected checks and writes a fresh ignored receipt. Add
`--depth native` after a KiCad source change, using the exact selected local CLI
or digest-pinned image.

MCP is an optional extra. Install it from the tooling checkout, then start it
with an absolute project root:

```sh
.venv/bin/python -m pip install -e '/path/to/KiCad-Tooling[mcp]'
.venv/bin/kicad-team-mcp --root /absolute/path/to/project
```

The server starts read-only. Explicit flags enable checks, source creation,
reviewed edits, exports, downloads, or supplier submissions. See the project's
[MCP guide](https://github.com/sheepfling/KiCad-Team-Workflow-Template/blob/main/docs/workflow/MCP.md)
for the permission and review workflow.

The board renderer creates six orthographic and four angled views by default.
See [3D view selection](docs/3D_VIEWS.md) to request a smaller view set from
the CLI or MCP.

## Configure another layout or KiCad version

The template layout is the default. A project-owned `kicad-tooling.toml` can
relocate catalogs, scaffold templates, workflow guides, and project creation.
Discovery supports bounded nested groups while retaining unique project IDs.
CLI and MCP share these settings. See [configuration](docs/CONFIGURATION.md)
for an example and the explicit native compatibility policy.

Package versions now come from Git through `setuptools-scm`. Run
`kicad-team --version` to see the installed version; see
[packaging and release checks](docs/PACKAGING.md) before tagging a release.

## Repository boundary

| Repository                      | Owns                                                                                |
| ------------------------------- | ----------------------------------------------------------------------------------- |
| Template                        | Folder layout, agent guidance, policy documents, starter catalogs, and thin CI      |
| Tooling                         | Python CLI and MCP services, schemas, parity inventory, package tests, and releases |
| Populated acceptance repository | Representative KiCad projects and end-to-end release rehearsals                     |

The populated acceptance repository should be a separate template-derived
checkout under the owner's account. It can be private. Its real project data
must not be copied into this public package. Keep small synthetic fixtures here
for isolated tool tests, and run the full project universe in that acceptance
repository against a pinned tooling build.

The template contract version and the tooling package version are separate.
Once releases begin, project repositories should pin a tested tooling version
and update it through a checked pull request, rather than consuming a moving
branch or unbounded latest release.

## Development check

The project-facing extras do not include package regression, lint or build tools.
From the tooling checkout, create a development environment and install `dev` plus
CAD support before running these checks. On macOS/Linux:

```sh
cd /absolute/path/to/KiCad-Tooling
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev,cad]'
export KICAD_TEMPLATE_ROOT=/absolute/path/to/KiCad-Team-Workflow-Template
python -B -m unittest discover -s tests -v
python -m ruff check --no-cache kicad_tooling tests
```

On Windows, create the environment with `py -3.11 -m venv .venv` and activate it
with `.venv\Scripts\Activate.ps1`. In PowerShell, set the fixture path with
`$env:KICAD_TEMPLATE_ROOT = "C:\path\to\KiCad-Team-Workflow-Template"`.

The shared regression suite uses an explicitly selected external template for
public reference data. It does not copy Python tooling into that checkout:

```sh
export KICAD_TEMPLATE_ROOT=/absolute/path/to/KiCad-Team-Workflow-Template
python -B scripts/ci.py --project-root "$KICAD_TEMPLATE_ROOT"
```

Package CI owns shared lint, typing, regressions and wheel/source-distribution
checks. Project CI owns project policy, documentation, contracts, local suites and
pinned native lanes. See [local workflow rehearsal](docs/LOCAL_PLAYTEST.md) for
CLI/MCP checks across the two repositories and [tests](tests/README.md) for coverage.
Contributors and coding agents should follow [AGENTS.md](AGENTS.md).
Read the [quality-gate audit](docs/QUALITY_GATE_AUDIT.md) for electrical, parts, CAD, BOM and
revision coverage, the current rehearsal evidence and remaining enforcement gaps.
