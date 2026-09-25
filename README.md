# KiCad Team Tooling

This repository contains the Python CLI and MCP services for KiCad team projects.
Project source, requirements, catalog records, and engineering decisions stay in a
project repository created from the
[KiCad team workflow template](https://github.com/sheepfling/KiCad-Team-Workflow-Template).
The same installed package provides both command surfaces.

This is the first extraction from the template. It is not published on PyPI yet,
and the template still carries its original `tools/` implementation while the
external package and hosted lanes are validated. Do not remove that implementation
or change a project's CI pin until the migration gate passes.
The installed-wheel rehearsal currently covers inventory, declared CLI/MCP
surface alignment, and selected portable verification. Native containers,
behavioral parity tests, and full release rehearsal still rely on the
template's in-tree acceptance path.

## Try the separate package

From a project checkout, install this repository into a Python 3.11 or newer
environment. Replace the path with the location of your tooling checkout:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -e /path/to/KiCad-Tooling
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

```sh
python -B -m unittest discover -s tests -v
python -m ruff check --no-cache kicad_tooling tests
```

The initial package smoke suite builds a disposable project checkout and
checks that inventory and parity do not read Python source from the project.
End-to-end project and native tests still run in the template during the
migration.
Contributors and coding agents should follow [AGENTS.md](AGENTS.md).
