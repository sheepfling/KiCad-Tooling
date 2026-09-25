# Package versions and release checks

The distribution name is `kicad-team-tooling`; the installed commands are
`kicad-team` and `kicad-team-mcp`. The package is not published on PyPI yet.

`setuptools-scm` derives the package version from Git tags and commit history.
Use a release tag such as `v0.1.0` on the reviewed release commit. Untagged commits
produce development versions; dirty checkouts are identified in the version.
Do not hand-edit a Python version constant or use a fallback that disguises a
checkout with missing history as a release.

Install from a Git checkout with its tags, or build from a generated source
distribution. A plain source archive without Git or source-distribution metadata
cannot establish a version and fails the build. CI fetches full Git history.

```sh
python3.11 -m pip install -e '.[dev]'
python3.11 -m build
kicad-team --version
```

The installed command reads distribution metadata and works outside a project
checkout. It does not invoke Git at runtime. The legacy policy contract version
in `hwrepo` remains separate from the package version and project KiCad pins.

## Acceptance before publication

```sh
python3.11 scripts/ci.py --project-root /path/to/populated-project-checkout
```

The Python CI driver records each stage's output and timing under ignored
`build/ci/`. It runs unit tests, Ruff, strict Pyright, markdown checks, and packaging.
It builds a wheel and source distribution, rebuilds the wheel from that source
distribution outside any Git tree, compares metadata and package contents, then
installs the rebuilt wheel in a fresh environment. The installed command must
report the same version and pass the external checkout's inventory and declared
CLI/MCP surface check. The reference controller also gets portable verification
when present in the acceptance checkout. A second disposable copy relocates its
project groups and catalogs and must pass the same inventory, surface, and portable
verification. The rehearsal checks that imports come from the newly installed
wheel. It does not borrow another environment's site-packages or modify import paths.

## Execution and import boundaries

Install the tooling normally for project use, or use pip's editable installation
for development. The package gate first verifies that an isolated Python process
imports this checkout's installed package. Tests do not inject `PYTHONPATH` or
modify `sys.path` to make an uninstalled checkout appear usable.

First-party subprocesses use the active interpreter and `-I -m` module entry points.
Project roots select engineering data, never Python import roots. Normal imports
share services between the CLI and MCP. Package checks install a fresh wheel with
its declared dependencies; there is no custom executable or site-packages override.

The pinned `rumdl` dependency is a Rust executable, and its Python module launcher
does not work in the installed 0.2.77 wheel. The small
`python -I -m kicad_tooling.markdown_check` adapter resolves exactly one binary from
that installed distribution's file metadata. It never searches PATH, guesses a
Scripts/bin location, or looks for a development build. Missing metadata fails the check.

Native KiCad checks create a standard virtual environment inside the digest-pinned
image. Its own Python reports the site-packages location; ABI-matched dependencies
and the exact executing tooling package with its version metadata are deployed
there. Launches use that environment's Python with `-I -m`, without `PYTHONPATH`.
The environment deliberately inherits the pinned image's KiCad Python bindings;
it does not inherit packages from the host or consuming project's directories.

The hosted workflow runs for pull requests, main, and `v*` tags. It does not publish
a package. Native and release acceptance runs against the separately pinned template.
PyPI publication remains a separate release action. See the
[repository boundary](../README.md#repository-boundary).

Once published, project repositories should pin an exact tested package version.
Upgrade that pin through a pull request that runs the project's focused and full
acceptance lanes. Private projects can then consume public tooling updates without
copying their designs into the tooling repository.
