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
python3.11 -m pip install '.[dev]'
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
wheel, including when an offline dependency directory is provided.

The hosted workflow runs for pull requests, main, and `v*` tags. It does not publish
a package. Native and release acceptance runs against the separately pinned template.
PyPI publication remains a separate release action. See the
[repository boundary](../README.md#repository-boundary).

Once published, project repositories should pin an exact tested package version.
Upgrade that pin through a pull request that runs the project's focused and full
acceptance lanes. Private projects can then consume public tooling updates without
copying their designs into the tooling repository.
