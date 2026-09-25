# Working in KiCad Team Tooling

Use Python 3.11 syntax. Run commands from a project checkout or pass an
explicit `--root`; never assume that package files live inside that checkout.
Read [layout and toolchain configuration](docs/CONFIGURATION.md) before assuming
folder names or KiCad versions. Keep adapters declarative and preserve portable
path, source ownership, and exact native-version checks.
Project manifests, KiCad source, requirements, and approvals belong to the
project repository. Reusable Python services, CLI/MCP mappings, and regression
tests belong here.

Keep CLI and MCP operations backed by the same typed service. Update
`kicad_tooling/tool-surfaces.json` when adding or changing either surface, and
retain an explicit parity test or documented adapter exception. Run the
package smoke suite and test an installed wheel against an external project
checkout before proposing a release. Keep generated receipts under ignored
`build/` directories.

Do not import private project fixtures or silently edit project expectations
to satisfy a check. Native KiCad results do not establish electrical approval
or manufacturing readiness.
