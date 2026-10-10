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

## Keep modules cohesive and reuse shared behavior

Before adding a parser, normalizer, validator, path helper, fingerprint routine,
or report conversion, search `kicad_tooling/` for the existing implementation
and extend its canonical service. Do not copy utilities into a second module,
CLI or MCP adapter, or test helper. Add a new shared helper when it has a clear
domain owner or at least two real consumers; avoid catch-all `utils.py` or
`helpers.py` modules.

Give each production module and test module one clear responsibility. As a
guideline, keep new Python modules below 500 lines; reaching that size is a
prompt to split by domain or behavior before adding more. Existing modules over
1,000 lines are decomposition targets: put new independent behavior in a
focused module and adapt it from the existing service instead of growing the
large file. Split those modules incrementally; do not require a wholesale
rewrite as a prerequisite. Keep test-support modules within the same review
threshold. If a module must exceed these review thresholds, record the reason
in the change summary.

Treat `hwrepo/models.py` as a shrink-only compatibility registry during its
incremental split. Put new lint-specific models in theme-owned modules, import
them directly from internal services, and re-export them from `models.py` only
when compatibility requires it. Add architecture tests for each extracted
owner's size, import boundary, and compatibility exports.

Keep design lint's `hwrepo/design_lint.py` as the small public facade. Put
implementation in `design_lint_*` modules grouped by analysis phase
(candidates, coverage, evaluation, or reporting) and by electrical/layout
theme (connectors, interfaces, components, power, returns, schematic, or PCB).
Every rule in `design-lint-rules.json` declares one of those themes and one
`implementation_owner` function in its catalog metadata. The owner must name the
module and function that contain the rule's predicate, appear in
`implementation_refs`, belong to the declared theme's module family, and stay
outside shared facades and dispatchers. The evaluator coordinates typed theme
services; it should not accumulate the individual theme checks. Extend the
matching module when adding a rule, and split a module when it reaches 500
lines. Architecture tests guard active rule owners and new lint-marked
regression suites below that limit. Existing oversized lint suites have
explicit no-growth ceilings in
`tests/lint_suite_line_ceilings.json`; remove each ceiling as its suite is split.

Keep `hwrepo/bus_heuristics.py` as a compatibility facade. Implement protocol
checks in focused `i2c_*`, `can_*`, `spi_*`, `usb_c_*`, or signal-pair modules;
shared passive-path recognition belongs in `resistor_paths.py`. Internal
services should import from the owning module, and the rule catalog should
point to the implementation module. Add size checks for new protocol modules
to `tests/test_design_lint_architecture_interfaces.py`.

Keep `hwrepo/schematic_geometry.py` as a small public facade. Separate source
parsing, geometry primitives, symbol geometry, pin connectivity, wire
connectivity, text layout, obstruction checks, and scan coordination into their
themed modules. Point each rule-catalog implementation reference at the module
that owns its check, and keep the facade and every themed module under the
architecture test's review limits.

Keep `hwrepo/usb_peer_reference_review.py` as a small compatibility facade.
Own endpoint recognition, USB data-path topology, project-map matching, and
scan coordination in `usb_peer_*` modules. Internal services should import
from those owners, and the rule catalog should reference the implementation
module. Guard the facade and module sizes in the architecture suite.

Keep `hwrepo/serial_peer_reference_review.py` as a small compatibility facade.
Separate reference-domain discovery, current-map matching, and scan
coordination into `serial_peer_reference_*` modules. Point internal imports
and catalog references at their owners, with facade and module sizes guarded
by the architecture suite.

Keep `hwrepo/pcb_switching_loops.py` as a small compatibility facade. Separate
pad-loop geometry, return-plane evidence, route topology, route coverage, and
review assembly into `pcb_switching_loop_*` modules. Internal services and the
rule catalog should reference the owning modules, with facade and module sizes
guarded by the architecture suite.

Keep `hwrepo/pcb_drc_coverage.py` as a small compatibility facade. Separate
native rule parsing, requirement comparison, source-bound DRC evidence, and
scan coordination into `pcb_drc_*` modules. Internal services and the rule
catalog should reference the owning modules, and the architecture suite should
guard their size and typed JSON boundaries.

Keep `hwrepo/control_inputs.py` as a small compatibility facade. Separate
control-input inventory, exact contract checks, and heuristic contract
coverage into `control_input_*` modules. Internal services should import from
their owner, and the rule catalog and architecture suite should enforce those
boundaries.

Keep `hwrepo/digital_peer_voltage_review.py` as a small compatibility facade.
Separate typed review records, endpoint/rail analysis, and scan/report assembly
into `digital_peer_voltage_*` modules. Internal services and the rule catalog
should reference the owning modules, with their sizes guarded by the
architecture suite.

Keep `hwrepo/pcb_return_paths.py` as a small compatibility facade. Separate
pure return-requirement evaluation into `pcb_return_path_checks.py` and native,
source-bound snapshot capture into `pcb_return_path_capture.py`. Internal
services should import from these owners, and the PCB architecture suite should
guard the facade, module sizes, and import boundary.

Keep synthetic inputs minimal and store substantial fixtures as separate files
under `tests/fixtures/`. Do not paste generated projects, serialized reports,
or long fixture data into test functions or production modules. Organize tests
by behavior so pytest markers and selectors can run the relevant slice.

Every module named by an active design-lint rule's fault, valid-control, or
metamorphic fixtures must carry the `design_lint` pytest marker. Add the
narrowest applicable area marker (`component_lint`, `connector_lint`,
`interface_lint`, `power_lint`, `evidence_lint`, `return_path_lint`,
`schematic_lint`, or `pcb_lint`) to dedicated suites. Use `parity_lint` for cross-surface tests and
`native_kicad` only when a test actually runs the exact native tool; mocked
native-lane orchestration is still a synthetic test. Mark cross-process or
broad integration tests `slow` when their runtime warrants a separate run.
For example, select USB-C and other interface lint regressions with
`python -I -m pytest tests/test_usb_c_ports.py -m 'design_lint and interface_lint' --durations=10`.

Keep CLI and MCP operations backed by the same typed service. Update
`kicad_tooling/tool-surfaces.json` when adding or changing either surface, and
retain an explicit parity test or documented adapter exception. Run the
package smoke suite and test an installed wheel against an external project
checkout before proposing a release. Keep generated receipts under ignored
`build/` directories.

Do not import private project fixtures or silently edit project expectations
to satisfy a check. Native KiCad results do not establish electrical approval
or manufacturing readiness.
