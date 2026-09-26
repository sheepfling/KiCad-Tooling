# Working in KiCad Team Tooling

Use Python 3.11 syntax. Run commands from a project checkout or pass an
explicit `--root`; never assume that package files live inside that checkout.
Read [layout and toolchain configuration](docs/CONFIGURATION.md) before assuming
folder names or KiCad versions. Keep adapters declarative and preserve portable
path, source ownership, and exact native-version checks.
Project manifests, KiCad source, requirements, and approvals belong to the
project repository. Reusable Python services, CLI/MCP mappings, and regression
tests belong here.

Use normal installed imports and the active interpreter's `-I -m` entry points
for Python subprocesses. Install this checkout with `python -m pip install -e '.[dev]'`
before regression tests. Do not add project/source directories to `PYTHONPATH` or
`sys.path`, guess executable prefixes, or borrow another environment's site-packages.
Keep unavoidable native-tool adapters in the tooling package; see the
[execution contract](docs/PACKAGING.md#execution-and-import-boundaries).

Keep CLI and MCP operations backed by the same typed service. Update
`kicad_tooling/tool-surfaces.json` when adding or changing either surface, and
retain an explicit parity test or documented adapter exception. Run the
package smoke suite and test an installed wheel against an external project
checkout before proposing a release. Keep generated receipts under ignored
`build/` directories.

Do not import private project fixtures or silently edit project expectations
to satisfy a check. Native KiCad results do not establish electrical approval
or manufacturing readiness.
