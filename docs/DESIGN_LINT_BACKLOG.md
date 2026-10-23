# Design lint and heuristic backlog

This backlog tracks deterministic checks that can surface likely design
mistakes for review, and the stronger contracts needed to turn a reviewed
requirement into a regression gate. It is not a list of assumed wiring rules.
No rule may join nets, infer an electrical requirement from a name alone, or
declare a board safe to fabricate.

The project repository owns interface intent, electrical requirements,
applicability decisions, and exceptions. This tooling repository owns reusable
analyzers, typed reports, adapters, synthetic fixtures, and regression tests.
No proprietary board source or project fixture is needed to develop this
backlog.

See [current design lint rules](DESIGN_LINT.md) for implemented behavior and
configuration. Items below are proposed work unless explicitly marked
implemented.

## Working rules

### Finding strength

- **Heuristic:** A deterministic pattern is unusual or incomplete, but intent
  is unknown. Report `REVIEW` by default with exact source evidence and a
  question for the reviewer.
- **Contract:** A project-authored, reviewed requirement names the required
  pins, nets, domains, values, or geometry. Compare it with source-bound
  evidence; project policy can make a mismatch blocking.
- **Native check:** KiCad ERC/DRC or another named native tool reports a defined
  condition. Preserve tool/version/source evidence; the result is not
  electrical approval.

An empty or absent contract is a **coverage gap**, not proof of a defect and
not a lint pass. Reports should keep coverage gaps, heuristic findings,
contract mismatches, native diagnostics, and stale review decisions distinct.

### Operationally reconcile existing findings

Before expanding the rule count, use the source-bound reconciliation gate to
compare each project's current lint report with its prior report. Keep every
persistent finding visible, including exact ignores and rule-off findings;
surface new, reclassified, and no-longer-reported findings for review. A
no-longer-reported row is not an automatic dismissal. Verify it against current
source evidence and independently authored requirements before accepting the
change. Missing source, netlist, or catalog hashes block comparison.

Track evidence levels separately: synthetic fault/control tests establish
predicate behavior, exact native fixture runs establish export compatibility,
pinned public baselines establish bounded applicability, and independently
confirmed reviewer dispositions establish field value. Do not infer one level
from another or invent reviewer precision/time measurements. More example
projects expand applicability evidence only when their source, license,
supported topology, and ground truth can be checked.

Use the reusable [review and cohort measurement worksheet](DESIGN_LINT_REVIEW_MEASUREMENT.md)
when recording dispositions, supported-path denominators, seeded mutations, or
review time. Rule-specific sections may add typed counts without changing the
shared evidence boundaries.

The first operational sweep found a stale active-rule fixture locator: the
catalog named a removed three-case hosted validator, while the existing native
fixture test validates four cases. The locator now points to that four-case
test. This was catalog/test reachability drift, not an observed lint-predicate
failure or a board defect.

A public 0BSD training-checkout screen at commit
`ed89536f0dbbcb013145af2994fef41b2250143e` exercised three PCB examples with
the exact KiCad 10.0.0 and 10.0.5 images. It exposed an execution gap: the
container-native lane invoked PCB geometry capture from inside the KiCad image,
where its nested Docker call could not run, so design lint was reported as
`BLOCKED`. The host-to-container runners now pass the catalogued image digest
as an execution marker. Geometry capture uses the image's `/usr/bin/python3`
only when that marker exactly matches the selected project toolchain; retained
command evidence validates that binding and the probe's `/work/build/` paths.
Host execution continues to use the isolated, read-only pinned-image probe.
After the change, the three PCB examples produced source-bound `REVIEW` reports
with complete geometry evidence. Their overall verification remained `FAIL`
because review findings were open; these training fixtures were not treated as
independently adjudicated defects. This improves evidence availability, not
rule precision or field value. The schematic-only passive reference remains
`BLOCKED` because its native netlist contains no component records, so it was
excluded from lint applicability counts.

### Entry requirements

Before implementation, every item needs:

1. A bounded evidence source and exact supported KiCad/tool versions.
2. A deterministic predicate, including which pin functions, properties,
   topology, or geometry it recognizes.
3. At least one synthetic fault fixture and one valid control fixture. Add
   boundary cases for DNP parts, explicit isolation, alternate valid
   topologies, and unsupported metadata where they apply.
4. A statement of what the result cannot establish and which project-authored
   requirement can turn the observation into a regression check.
5. A unique rule ID, stable fingerprint inputs, readable evidence, a
   documented default mode, and a reasoned project override/ignore path.
6. CLI/MCP parity through the shared typed service when a user-facing surface
   changes, plus the required parity test and `tool-surfaces.json` update.

Do not promote a heuristic to default `block` based only on a plausible
electrical convention. Promotion requires project-authored policy and a
contract comparison whose positive and negative controls demonstrate the
intended requirement.

## Lint module boundaries and test selection

- Keep `design_lint.py` as the small public service facade and
  `design_lint_evaluator.py` as a staged coordinator. Put each rule's predicate
  and evidence assembly in the module that owns its source and electrical
  theme; share parsing and common evidence through focused helpers.
  Connector candidate dispatch stays in the 29-line
  `design_lint_connector_candidates.py` facade. Pin and peer-assignment
  prompts live in `design_lint_connector_pin_candidates.py`, return-role and
  return-domain prompts in `design_lint_return_domain_candidates.py`, and
  numbered positive-rail prompts in `design_lint_power_candidates.py`. The
  architecture suite checks that the connector facade delegates and does not
  construct findings.
  Peer prompts are dispatched by interface owner: serial, USB, SPI, USB-C, and
  digital-peer voltage translators have dedicated modules, while
  `design_lint_peer_candidates.py` coordinates source scans and preserves output
  order. Bus checks are split among I2C, SPI, CAN, unconnected-interface, and
  signal-pair candidate modules; `design_lint_bus_candidates.py` preserves their
  established output order without building findings. Architecture tests keep
  both coordinators small and verify that they delegate rather than construct
  `Candidate` records.
  I2C address requirements and coverage now live in
  `i2c_address_models.py`; pull-up requirements and coverage live in
  `i2c_pullup_models.py`. Internal services import these owners directly, and
  the shared registry retains identity-compatible re-exports. Architecture
  tests guard owner size, import boundaries, and export identity. This reduces
  `hwrepo/models.py` from 8,195 to 7,758 lines; shared finite/electrical measure
  aliases now have their canonical owner in `model_primitives.py`.
  Electrical power-budget and simulator contracts now live in
  `electrical_simulation_models.py`. Electrical, SPICE, plot, and chart
  services import that owner directly while `models.py` retains
  identity-compatible exports. Architecture tests protect its size and import
  boundary; the registry shrank from 3,275 to 3,136 lines.
  CAN termination requirements now live in `can_termination_models.py`; the
  contract, evidence, and execution services import that owner directly while
  the shared registry retains identity-compatible exports. The protocol-model
  architecture suite covers CAN and I2C ownership without growing the
  interface-boundary suite past its review limit. This extraction reduces
  `hwrepo/models.py` from 7,758 to 7,583 lines.
  SPI roster, pin, bridge, and bus-topology models now live in `spi_models.py`.
  The contract and roster services import that owner directly, with
  identity-compatible re-exports retained for existing callers. The protocol
  architecture test checks the classes, `SpiMisoRequirement` alias, import
  boundary, and owner size; `hwrepo/models.py` shrank from 7,583 to 7,308 lines.
  UART endpoint and bridge contracts now live in `serial_peer_models.py`,
  logic-limit and fixture records in `serial_logic_models.py`, and RS-485
  topology contracts in `rs485_models.py`. Digital-peer voltage requirements
  join their existing report owner in `digital_peer_voltage_models.py`.
  Exact reference-bond requirements now live in `reference_bond_models.py` and
  are imported directly by serial and USB services.
  Internal tooling services import these owners directly; the shared registry
  keeps identity-compatible exports. The protocol architecture suite checks
  ownership, aliases, internal imports, and owner sizes. This extraction
  reduces `hwrepo/models.py` from 7,308 to 6,584 lines.
  Component voltage/power contracts, connector contact-current contracts, and
  MOSFET operating-state stress contracts now live in three focused rating
  owners. Electrical and hosted-fixture services import those owners directly;
  architecture tests check their size, import boundaries, and compatibility
  identities. This extraction reduced `hwrepo/models.py` from 6,584 to 6,343
  lines without changing the contract schemas.
  Control-input endpoint and bias requirements, heuristic coverage records,
  and their discriminated bias union now live in `control_input_models.py`.
  Control-input and design-lint services import that owner directly while
  `models.py` retains identity-compatible exports. Architecture tests guard
  owner size, import boundaries, and compatibility identity; the registry
  shrank from 6,343 to 6,120 lines without changing contract schemas.
  External-protection requirements and source-bound coverage records now live
  in `external_protection_models.py`. Internal lint services import that owner
  directly, and architecture tests check owner size, import boundaries, and
  identity-compatible registry exports; `models.py` shrank by another 140 lines.
  Schematic-geometry rule IDs, source bindings, and coverage reports now live
  in `schematic_geometry_models.py`. Evaluation and report services import the
  owner directly; architecture tests guard its size, internal import boundary,
  and identity-compatible registry exports. This extraction shrank
  `models.py` from 3,690 to 3,598 lines without changing report behavior.
  Connector peer comparison groups and the reviewed pin-role type now live in
  `connector_peer_pin_models.py`. Connector analysis services import the theme
  owner directly while the shared registry preserves identity-compatible
  exports for external callers. This extraction shrank `models.py` from 3,598
  to 3,575 lines without changing connector-review behavior.
  Return-net and numbered-power-rail observations now live in their respective
  `return_net_models.py` and `power_rail_models.py` theme owners. The analyzers
  import the owner types directly, while `models.py` retains identity-compatible
  exports for existing callers; architecture tests check both owners, imports,
  and compatibility. The extraction shrinks the registry without changing
  report schemas or the advisory status of name-based observations.
  Connector inventory, pin-mapping, and coverage records now live in
  `connector_coverage_models.py`. Connector and lint services import this owner
  directly while the compatibility registry preserves existing exports.
  Architecture tests enforce owner size, imports, and class identity; the move
  shrinks `models.py` from 3,567 to 3,514 lines without changing source-coverage
  policy or report schema.
  Regulator-feedback and RC-filter coverage entries and reports now live beside
  their requirement maps in `regulator_feedback_models.py` and
  `rc_filter_models.py`. Internal lint services import those owners directly,
  while `models.py` keeps identity-compatible exports. Architecture checks
  enforce owner sizes, import boundaries, and compatibility; the registry
  shrank from 3,514 to 3,424 lines without changing schemas or check behavior.
  Differential-pair and signal-path DRC text rendering now lives in the
  focused `design_lint_pcb_drc_report.py` owner, keeping the broader PCB
  coverage report below the architecture review limit without changing output.
  - Treat the existing `hwrepo/models.py` as shrink-only while its shared records
  are split incrementally. Put new lint-specific requirements, findings, and
  coverage reports in theme-owned model modules, import those owners directly
  from internal services, and preserve compatibility re-exports only where
  existing callers need them. Each extraction needs an owner-size check, an
  import-boundary check, and a compatibility test. The PCB RF antenna contract
  and coverage models now live in `hwrepo/pcb_rf_antenna_models.py`, backed by
  shared `model_primitives.py`; internal services import the theme owner, and
  the shared registry carries a shrink-only line ceiling.
  Component and connector peer-pin coverage models now live in
  `component_peer_pin_models.py` and `connector_peer_pin_models.py`;
  peer-analysis services import those owners directly, while `models.py`
  preserves compatibility exports. The interface architecture tests guard the
  owners' size, import boundary, and export identity. This extraction removes
  321 lines from the working registry without changing report schemas.
  Digital peer-voltage, USB peer-reference, and serial peer-reference report
  models now live in their corresponding `*_models.py` modules. Peer coverage,
  evidence, and evaluation services import these owners directly; the
  architecture suite checks all internal imports and compatibility exports.
  This second extraction removes another 446 lines from the registry.
  PCB DRC bounds, signal-path and differential-pair maps, and their coverage
  reports now live in `pcb_drc_models.py`. Internal PCB and lint services use
  that owner; the PCB architecture suite checks its size, import boundary, and
  compatibility exports. This extraction removes another 399 lines.
  PCB decoupling requirements, maps, candidate observations, and source-bound
  coverage reports now live in `pcb_decoupling_models.py`. Internal PCB and
  lint services import that owner; `models.py` preserves identity-compatible
  exports for existing callers. The PCB architecture suite checks the owner
  size, import boundary, registry ownership, and exports. The observation and
  report extraction removed 98 registry lines; moving the authored contract
  models removes another 62 without changing schemas.
  PCB protection-path requirements, maps, entries, and source-bound reports
  now live in `pcb_protection_path_models.py`; internal PCB and lint services
  import from that owner, while `models.py` retains compatibility exports.
  Architecture tests guard its size, registry ownership, and internal import
  boundary. This removes another 160 lines from the shared model registry
  without changing contract or report schemas.
  PCB track-width requirements, maps, and source-bound measurement reports now
  live in `pcb_track_width_models.py`; the PCB checks and lint evaluation
  services import that owner. Architecture tests enforce its size, import
  boundary, and compatibility exports. This extraction reduced the shared
  registry by a further 107 lines.
  PCB reference-plane requirements, native measurements, and coverage reports
  now live in `pcb_reference_plane_models.py`; internal PCB and lint services
  import from that owner while `models.py` retains compatibility exports. The
  PCB architecture tests guard model identity, module size, and the import
  boundary. This extraction reduced the shared registry from 9,225 to 9,050
  lines.
  PCB switching-loop pad and route contracts, maps, and source-bound reports
  now live in `pcb_switching_loop_models.py`. Internal PCB and lint services
  import from that owner; the architecture suite checks its size, compatibility
  exports, and import boundary. Together these reference-plane and switching-
  loop extractions reduced `models.py` from 9,225 to 8,732 lines.
  Native PCB observation records and their versioned connectivity snapshot now
  live in `pcb_connectivity_observations.py` and
  `pcb_connectivity_snapshot.py`. PCB and hosted-evidence services import those
  owners directly; `models.py` keeps identity-preserving compatibility exports.
  A dedicated architecture suite checks owner size, internal imports, and
  compatibility identity. The extraction reduces the shared registry from
  8,732 to 8,195 lines while keeping each owner below 500 lines.
  PCB test-access requirements and native probe request records now live in
  `pcb_test_access_models.py`. Electrical, hosted-fixture, and evidence
  services import these models directly; `models.py` retains identity-
  compatible exports for existing callers. Architecture tests guard the
  owner size, exports, and import boundary. This extraction reduced the shared
  registry from 3,387 to 3,275 lines without changing contract schemas.
  Synthetic RF antenna test builders live in `tests/pcb_rf_antenna_support.py`;
  the focused regression suite is below 500 lines and no longer needs a legacy
  size ceiling.
  The one-command verification lint gate is isolated in
  `tests/test_verify_design_lint.py`; runner failure tests stay in
  `tests/test_verify.py`, and shared synthetic setup lives in bounded
  `tests/verify_support.py` and `tests/verify_design_lint_support.py` modules.
- Keep mapped-topology execution receipts in
  `design_lint_mapped_topology_models.py`. Coverage, evaluation, and report
  modules import the owner directly; `models.py` keeps only the
  identity-compatible export. The report-model architecture suite guards the
  owner size and import boundary.
- Keep `pcb_return_paths.py` as a compatibility facade. Pure checks against
  reviewed return requirements live in `pcb_return_path_checks.py`; native
  source-bound snapshot capture and probe provenance live in
  `pcb_return_path_capture.py`. The PCB architecture suite guards this split.
- Keep the KiCad-isolated native PCB snapshot adapter as a deterministic
  assembly of bounded bootstrap, access, geometry, and scan source fragments.
  Hash the exact assembled executable source in `probe_sha256`; the probe stays
  read-only and runs only in the project's digest-pinned KiCad image.
- Keep active rule predicate modules under `kicad_tooling/hwrepo/`, new
  theme-specific pytest suites, and their support modules below the 500-line
  review threshold. Split a larger module by responsibility, then update
  catalog implementation references, pytest area registration, and the
  architecture size guard. The architecture catalog checks that every active
  rule fault, valid-control, and metamorphic fixture module has both the broad
  `design_lint` marker and a theme-specific area marker or `parity_lint`, so
  focused selections do not silently omit a regression suite. Existing
  oversized lint-marked test suites are
  recorded in `tests/lint_suite_line_ceilings.json`; they may shrink but must
  not grow. Remove each ceiling as its suite is split. The two PCB
  reference-plane fixture lanes now live in their own 389-line module. USB
  and power-path native fixture orchestration, evidence assertions, and authored
  maps live in bounded theme-specific modules. The power-path lane tests are
  split into focused synthetic and digest-pinned pytest modules, with
  `power_lint`, `native_kicad`, and `slow` selection. Other native fixture-lane
  adapters now live in dedicated theme modules. The native test-point probe
  lane has a dedicated PCB adapter and a focused pytest
  module with `pcb_lint`, `native_kicad`, and `slow` selection. Component
  voltage, resistor power, connector contact-current, and MOSFET stress native
  controls now share one export setup and use dedicated theme modules.
  Decoupling placement, protection-entry paths, and track-width native fixtures
  also have independent theme modules, coordinated by a small lane runner and
  shared source-bound probe setup. Their digest-pinned acceptance is split into
  pytest modules with `pcb_lint`, `native_kicad`, and `slow` markers. The
  connector-return fixture lane has been split into a source-bound context, a
  small coordinator, and separate return, power, grounding, peer-pin, off-board,
  mapped-interface, and receipt modules. The digital-peer fixture lane is split
  across SPI participant and roster checks, SPI voltage cases, serial voltage
  and reference checks, and component power-pin cases. Its synthetic lane
  regressions use separate pytest modules for SPI voltage, serial voltage,
  serial reference, and component power. Digest-pinned acceptance is also split
  into SPI, serial/reference, and component-power pytest suites; one
  session-scoped fixture runs both native project toolchains and shares their
  result records across theme-specific assertions. Switching-loop fixture
  setup and native geometry checks now live in separate modules with a small
  coordinator. PCB return-path fixtures separate setup, per-case evaluation,
  and specialized via, copper-plane, net-tie, isolation, and zone-island
  evidence checks. Hosted fixture implementation modules are below 500 lines.
  Several older lint-marked test suites remain in
  `tests/lint_suite_line_ceilings.json`; each is capped at its current size and
  must shrink as it is split. The architecture test caps each hosted theme
  module and function below 500 lines. The mocked hosted PCB return fixture
  test now lives in the 442-line pytest module
  `tests/test_ci_hosted_pcb_return_paths.py`, with a shared disposable-project
  checkout helper in `tests/hosted_ci_support.py`. It is selectable by PCB and
  return-path markers and requires the public template checkout. The USB
  native data-path fixture acceptance now lives in the 160-line pytest
  module `tests/test_usb_data_path_native_fixture_lane.py`, selectable by
  design-lint, interface, native, and slow markers. LED rail/output-path
  native acceptance now lives in the 127-line
  `tests/test_led_rail_native_fixture_lane.py`, parameterized by exact native
  project/version and selectable by component, native, and slow markers. The
  USB SuperSpeed pair acceptance now lives in the 79-line
  `tests/test_complementary_pair_native_fixture_lane.py`, retaining
  cross-version normalized-hash comparison. Connector/capacitor-only
  DC-reference native fault/control acceptance now lives in the 111-line
  `tests/test_net_dc_reference_native_fixture_lane.py`. IC rail-capacitor
  native acceptance now lives in the 146-line
  `tests/test_ic_rail_capacitor_native_fixture_lane.py`, retaining missing-cap,
  fitted-capacitor, DNP, custom-role, and native ERC controls. The legacy
  The former `tests/test_ci_hosted.py` was retired after its remaining native
  connector-return, connector-inventory, and PCB-access checks moved into
  theme-specific suites. Hosted planning, release checks, and mocked fixture
  scheduling already live in bounded suites. Keep each future native fixture
  in its lint-theme module.
  The connector-return pytest lane now keeps its synthetic return, peer-pin,
  and power case builders in bounded support modules, leaving a 427-line
  integration suite selectable with `connector_lint` and `return_path_lint`.
  The power-input source-path regression is split by source topology,
  source-anchor/connector scope, and policy/determinism; synthetic netlist
  builders live in `tests/design_lint_fixtures/power_input_paths.py`. Its
  topology and metadata variants are parametrized so pytest reports and selects
  individual cases.
  The USB-C port, IC rail capacitor, power-sequence, and open-drain bias lanes
  also have independent theme modules. `ci_hosted.py` now contains CI
  orchestration and small compatibility imports/adapters; its architecture
  test caps it below 1,000 lines and keeps local fixture adapters below 100 lines.
  The architecture assertions are also split into core, interface, schematic,
  PCB, and hosted-lane suites; shared review limits live in
  `tests/lint_architecture_support.py`, and the suite-size guard covers these
  architecture test modules themselves.
- Use pytest area markers for broad runs and module names for focused runs.
  Keep synthetic fault/control coverage beside the rule theme, with common
  fixture builders in bounded support modules. The catalog architecture test
  resolves active fault, control, and metamorphic fixture references and
  requires each owning test module to carry `design_lint`, so focused runs do
  not silently omit catalogued evidence. The same references attach a
  `design_lint_rule(rule_id=...)` marker, allowing the rule's fault, control,
  metamorphic, parity, and native tests to be selected as one slice. For
  example, run
  `python -I -m pytest -m 'design_lint_rule(rule_id="power.pin_function_net_role_conflict")'`.
  Avoid a generic checker that accumulates unrelated predicates or duplicate
  copies of shared utilities.
- Use `catalog_lint` to run catalog metadata, implementation-owner, fixture
  reachability, and backlog-synchronization regressions without executing every
  lint theme: `python -I -m pytest -m 'design_lint and catalog_lint'`. Annotated
  prerelease tags can select the same slice with `Lint-Area: catalog_lint`.
- The I2C address-map suite follows this layout: coverage, address collisions,
  strap decoding, and contract validation have separate test modules, with
  shared synthetic builders in `tests/design_lint_fixtures/i2c_addresses.py`.
  Each module is registered for focused `interface_lint` selection.
- The serial peer-reference regressions follow the same theme boundary:
  coverage, review candidates, authored maps, and ambiguity/configuration
  cases are separate pytest suites with shared synthetic builders in
  `tests/serial_peer_reference_support.py`.

## Existing baseline

The following 155 rules are implemented with synthetic regression coverage.
Their actual recognition limits are documented in
[DESIGN_LINT.md](DESIGN_LINT.md):
The catalog currently contains 155 active rules.

The mapped-topology execution receipt now has a focused model owner; internal
coverage, evaluation, and report code import it directly while the shared model
registry keeps a compatibility export. The `v0.5.2rc49` scoped gate (GitHub
Actions run `39435239835`) passed, including its installed-wheel check against
the separate public template and Ubuntu, macOS, and Windows preview jobs. The
package job was skipped under prerelease policy. The preceding docs-only
`v0.5.2rc48` tag failed before tests because its message omitted the required
`Lint-Area` or `Lint-Rule` selector; the later scoped tag passed validation.
The docs-only checkpoint `v0.5.2rc50` at `62aac53` also passed its scoped
design-lint gate (GitHub Actions run `39436260075`), including the installed-
wheel rehearsal against the separate public template and all three preview
jobs. Its annotated tag passed the local scope resolver; the package job was
skipped under prerelease policy.

- `connector.repeated_pin_function`
- `connector.peer_pin_assignment_outlier`
- `connector.peer_pin_assignment_divergence`
- `connector.footprint_peer_pin_assignment_divergence`
- `connector.footprint_peer_pin_metadata_assignment_divergence`
- `connector.footprint_peer_pin_metadata_open_outlier`
- `connector.footprint_peer_pin_missing_metadata_assignment_divergence`
- `connector.footprint_peer_pin_missing_metadata_open_outlier`
- `connector.footprint_peer_pin_open_outlier`
- `connector.footprint_named_power_input_open_outlier`
- `connector.footprint_named_signal_input_open_outlier`
- `connector.footprint_named_power_output_open_outlier`
- `connector.footprint_named_signal_output_open_outlier`
- `connector.footprint_named_signal_mode_dependent_open_outlier`
- `connector.footprint_named_passive_open_outlier`
- `connector.footprint_named_signal_assignment_divergence`
- `connector.footprint_named_power_input_assignment_divergence`
- `connector.footprint_named_power_output_assignment_divergence`
- `connector.footprint_named_passive_assignment_divergence`
- `connector.footprint_named_power_input_all_open`
- `connector.footprint_named_power_output_all_open`
- `connector.footprint_named_signal_all_open`
- `connector.footprint_peer_pin_all_open`
- `connector.generic_peer_pin_all_open`
- `connector.peer_power_input_named_all_open`
- `connector.peer_power_input_open_assignment`
- `connector.peer_power_output_open_assignment`
- `connector.peer_power_output_named_all_open`
- `connector.peer_power_output_named_assignment_divergence`
- `connector.peer_power_input_named_assignment_divergence`
- `component.repeated_supply_pin_function`
- `component.peer_power_pin_assignment_divergence`
- `component.peer_power_input_assignment_divergence`
- `component.peer_power_input_named_assignment_divergence`
- `component.peer_power_input_named_all_open`
- `component.peer_power_input_open_assignment`
- `component.peer_power_output_unconnected`
- `component.peer_signal_input_unconnected`
- `component.peer_bidirectional_pin_unconnected`
- `component.generic_peer_pin_all_open`
- `component.generic_peer_pin_mixed_open`
- `component.generic_peer_pin_assignment_outlier`
- `component.peer_signal_output_unconnected`
- `component.two_pin_passive_same_net`
- `component.two_pin_diode_same_net`
- `component.two_pin_crystal_same_net`
- `component.two_pin_fuse_same_net`
- `component.two_pin_ferrite_same_net`
- `component.two_pin_switch_same_net`
- `connector.no_connected_return`
- `connector.return_pin_on_positive_rail`
- `connector.unconnected_supply_pin`
- `connector.unconnected_return_pin`
- `connector.mapped_interface_signal_unassigned`
- `connector.mapped_interface_shield_unassigned`
- `connector.unconnected_power_input`
- `connector.unconnected_power_output`
- `component.unconnected_power_input`
- `component.unconnected_power_output`
- `component.unconnected_supply_pin`
- `component.unconnected_return_pin`
- `component.mosfet_gate_without_peer`
- `component.mosfet_gate_without_visible_source_bias`
- `component.polarized_capacitor_reversed_on_named_rails`
- `component.diode_anode_below_cathode_on_named_rails`
- `component.led_directly_across_supply_and_return`
- `component.led_directly_driven_from_output`
- `oscillator.output_load_path_mismatch`
- `power.ic_decoupling_below_project_minimum`
- `power.ic_rail_without_fitted_capacitor`
- `power.pin_function_net_role_conflict`
- `power.named_supply_pin_on_negative_rail`
- `power.mapped_series_path_mismatch`
- `power.mapped_sequence_dependency_mismatch`
- `power.input_without_supported_source_path`
- `net.connector_capacitor_only_no_dc_anchor`
- `control.unconnected_control_input`
- `control.connected_control_input_without_visible_bias`
- `signal.open_collector_input_without_visible_bias`
- `signal.open_emitter_input_without_visible_bias`
- `bus.i2c_unconnected_pin`
- `bus.i2c_missing_pullup`
- `bus.i2c_low_equivalent_resistance`
- `bus.i2c_multiple_pullup_rail_families`
- `bus.i2c_peer_reference_review`
- `bus.i2c_address_mismatch`
- `bus.i2c_address_collision`
- `bus.i2c_unmapped_responder`
- `bus.spi_unmapped_participant`
- `bus.serial_unmapped_peer`
- `bus.spi_peer_reference_review`
- `bus.spi_peer_voltage_review`
- `bus.serial_peer_voltage_review`
- `bus.serial_peer_reference_review`
- `bus.rs485_peer_reference_review`
- `bus.usb_peer_reference_review`
- `bus.spi_unconnected_chip_select`
- `bus.spi_active_low_chip_select_without_pullup`
- `bus.usb_c_unconnected_cc_pin`
- `bus.usb_c_unreviewed_port`
- `bus.usb_data_path_mismatch`
- `bus.can_unconnected_line`
- `bus.can_missing_termination`
- `bus.can_peer_assignment_divergence`
- `bus.can_peer_reference_review`
- `bus.complementary_pair_assignment`
- `signal.named_pair_without_reviewed_requirement`
- `net.numbered_returns`
- `net.numbered_power_rails`
- `schematic.wire_end_on_pin_line`
- `schematic.pin_tip_on_wire_interior`
- `schematic.wire_endpoint_near_pin_tip`
- `schematic.label_near_wire_endpoint`
- `schematic.unmarked_wire_crossing`
- `schematic.unmarked_t_junction`
- `schematic.coincident_text_anchors`
- `schematic.free_text_overlap`
- `schematic.free_text_over_wire`
- `schematic.free_text_over_symbol_body`
- `schematic.wire_through_symbol_body`
- `protection.unreviewed_interface_pin`
- `protection.mapped_device_mismatch`
- `oscillator.crystal_load_network_mismatch`
- `power.regulator_feedback_mismatch`
- `filter.rc_corner_mismatch`
- `pcb.decoupling_proximity`
- `pcb.protection_entry_path`
- `pcb.minimum_track_width`
- `pcb.reference_plane_coverage`
- `pcb.switching_loop_geometry`
- `pcb.differential_pair_rule_coverage`
- `pcb.signal_path_rule_coverage`
- `pcb.custom_drc_rule_ignored`
- `pcb.custom_drc_rule_excluded`
- `pcb.core_drc_check_ignored`
- `pcb.core_drc_check_warning`
- `pcb.dfm_drc_check_ignored`
- `pcb.dfm_drc_check_warning`
- `pcb.signal_integrity_drc_check_downgraded`
- `pcb.electrical_drc_check_downgraded`
- `pcb.miscellaneous_drc_check_downgraded`
- `pcb.warning_default_drc_check_ignored`
- `pcb.drc_exclusion_present`
- `pcb.rf_module_antenna_keepout_coverage`
- `pcb.keepout_intent_coverage`
- `pcb.schematic_component_inventory`
- `pcb.schematic_pcb_dnp_mismatch`
- `pcb.schematic_pcb_value_mismatch`
- `pcb.schematic_pcb_pad_net_mismatch`
- `pcb.board_only_footprint`
- `pcb.required_fitted_reference`
- `pcb.touch_pad_reference_clearance`
- `connector.return_distribution`
- `net.return_labels_without_pin_roles`
- `mcu.stm32_cubemx_pin_map`

This baseline catches suspicious connector symmetry and missing named pins,
plus narrow netlist patterns for I2C, SPI, USB-C, and CAN. It does not know that
several similarly named connector returns must be common unless a project
states that requirement. It also cannot establish PCB copper connectivity,
placement, off-board circuitry, or physical continuity from a schematic
netlist.

## Prioritized backlog

Priority is about the next useful, evidence-backed increment. `P0` is a
foundation for trustworthy expansion; protocol-specific schematic checks are
`P1`; geometry-dependent checks and review aids are `P2`; curated knowledge
and optional ecosystem adapters are `P3`.

### Current execution focus

- **Diode rail-polarity review (2026-10-22):** LINT-173 reviews a fitted,
  exact supported two-pin diode whose native `A` and `K` pins resolve to
  differently ordered numeric rails, or a named return and a positive rail.
  A shared potential resolver now serves this heuristic and the existing
  polarized-capacitor rule, preserving the same conflict exclusions. Reverse-
  biased clamp and isolation circuits are valid, so this remains a configurable
  `REVIEW` prompt rather than an inferred defect. Synthetic native fixtures now
  cover both `+3V3`/`+5V` and `GND`/`+3V3` ordering on the exact KiCad
  10.0.0/10.0.5 lanes. No project or cohort board/source is used.

- **Connector native-fixture registry completeness (2026-10-22):** The
  architecture gate now requires every active rule declaring
  `KICAD_RUN_NATIVE_CONNECTOR_FIXTURES` to list its exact fault and control
  test references. The audit exposed eleven rules missing from that explicit
  registry; each now points to its existing native fixture cases. This adds
  no electrical predicate. The focused architecture, catalog-fixture, and
  marker suites pass locally.

- **MOSFET gate peer review (2026-10-22):** The source-bound MOSFET stress
  contract checks authored VDS/VGS limits but does not flag a fitted supported
  three-terminal MOSFET whose gate pin is open or is the only fitted pin on
  its assigned net. The new LINT-170 review rule adds that narrow candidate;
  it does not infer a required driver or safe bias. Synthetic policy,
  applicability, ordering, and CLI/MCP parity cases are registered. Hashed
  native fault/control sources and an exact-version hosted lane are now wired
  into package acceptance. The `v0.5.3rc26` hosted lint gate, installed-wheel
  check, and three platform preview jobs passed (run `39888172919`).

- **MOSFET gate/source bias prompt:** LINT-171 adds an opt-in REVIEW candidate
  when an exact supported three-terminal MOSFET has a fitted peer on its gate
  net but no visible fitted nonzero resistor directly between the gate and
  source nets. A peer does not establish a driver or safe state; internal and
  off-board bias remain outside the native schematic evidence.

- **Pin-connectivity regression review (2026-10-13):** LINT-131 extends the
  source-bound reconciliation baseline with each native pin's net name and peer
  set. A change to an unconnected contact, connector return, power pin, or peer
  topology now becomes exact review evidence even when no heuristic finding
  changes. Snapshot coverage is `COMPLETE` only when native symbol pin
  inventories are available; incomplete data remains `PARTIAL`, older reports
  without snapshots require a refreshed baseline, and different exact KiCad
  versions or toolchain images block comparison. The pin-swap and declared
  polarity concepts in the Apache-2.0, pre-alpha `netspec` cohort were useful
  evidence for this gap; no code or board data was imported, and no separate
  polarity rule was added because the existing project-authored
  `pin_connectivity` contract can state exact pin relationships.

- **Pin-role metadata regression review (2026-10-13):** LINT-132 extends that
  baseline with each native pin's function and electrical type. A symbol-role
  edit now appears in reconciliation even when every pin remains on the same
  net. Older reports without this metadata remain readable, but their role
  comparison is partial until a current baseline is saved. This adopts the
  connectivity-delta review lesson from the pre-alpha Apache-2.0 `netspec`
  cohort; no cohort code or project data was imported.

- **Configured touch-pad clearance (2026-10-13):** LINT-133 converts the
  pinned CP-003 source audit into an opt-in project-authored geometry check.
  It requires an exact pad, expected schematic/PCB net, reference copper net,
  copper layer, and independently approved positive minimum. Native evidence
  uses KiCad's effective pad shape and the filled matching zones, with the
  authored request digest bound to snapshot schema 14. Synthetic fault,
  boundary-control, missing-evidence, and CLI/MCP parity tests pass locally;
  digest-pinned KiCad 10.0.0 and 10.0.5 fixtures passed the hosted native
  stage on `v0.5.0rc248`. The full scoped gate passed on `v0.5.0rc249`
  (run `38395063701`), including the external installed-wheel test and all
  three platform preview jobs. The rotated-pad geometry regression also
  passed on both pinned KiCad versions in `v0.5.0rc250` (run `38396108362`).
  The repeated native DRC comparison passed on both versions in `v0.5.0rc251`
  (run `38397569065`). No board project or proprietary fixture was imported.
  The gate supplies review evidence and does not infer connector ground
  commoning, touch performance, or fabrication acceptance.

- **Pin-assignment-only contract (2026-10-19):** `pin_connectivity` now has
  an `assigned` topology for exact project-reviewed pins that must each have
  one native net assignment without prescribing a net name or commoning the
  pins. Native source evidence must establish pin identity; an observed
  assignment confirms a wired pin, while an open pin needs symbol inventory.
  Open, stale, and ambiguously assigned pins fail closed. Synthetic checks cover
  separate-net and shared-net controls, an open-pin fault, duplicate
  assignment, and missing inventory.
  The connector native fixture reuses its existing three-port peer fault and
  control to show the assignment-only requirement passing on independent nets
  and failing on an open pin. The DB9 native contract also shows assignment-only
  passing on both split-return and common-return exports; only the separately
  authored common-net requirement rejects split returns. A CLI/MCP parity case
  is registered. This extends the explicit project-authored contract; it adds
  no inferred electrical rule.

- **Shared explicit return-pin metadata (2026-10-19; controls updated 2026-10-20):**
  I2C, SPI, CAN, serial, and USB peer-reference checks now share
  `peer_reference_assignments.py` for
  native pin-function and pin-type interpretation. A return-like function
  with native type `unspecified` can support a REVIEW only when the function
  itself names a recognized return role; shield, chassis, frame, protective
  earth, and ordinary signal functions do not. This closes a cross-protocol
  evidence gap while preserving the checks' advisory behavior. Synthetic
  regressions cover split and common references plus non-return controls across
  protocols, including a suffixed `VSS1` function. An added unspecified-type
  I2C control set confirms `SHIELD`, `CHASSIS`, `FRAME`, `PE`, and `GND_SHIELD`
  do not become signal-reference evidence. Focused protocol tests,
  catalog/architecture tests, Ruff, Pyright, and the documentation check pass.
  No project board or proprietary fixture was imported. The rule-scoped
  `v0.5.2rc4` gate passed hosted run `39372713717`: 18 rule-selected tests,
  repeated fault/control exports on digest-pinned KiCad 10.0.0 and 10.0.5 with
  matching normalized hashes, installed-wheel checks against separate project
  checkouts, and all three platform previews. The package-release job was
  skipped under prerelease policy. The preceding cross-protocol gate passed
  hosted run `39371815403`.

- **Pytest architecture selection (2026-10-13):** Split the 501-line
  `tests/test_design_lint_architecture_pytest_style.py` into
  `tests/test_design_lint_architecture_pytest_markers.py` and
  `tests/test_design_lint_architecture_pytest_collection.py`. The first owns
  catalog marker and lint-suite theme checks; the second owns collection-time
  isolation and selector behavior. Both modules are below 500 lines and carry
  only the broad `design_lint` and `architecture` markers, so connector- and
  interface-only selectors do not pull in cross-theme architecture probes.
  The focused architecture run passed 31 tests; connector and interface
  selection each collected zero tests from these modules. The full architecture
  selection then passed 214 tests with 3,082 deselected after fixing one
  internal import to use its theme-owned model and registering native
  variant-probe JSON as an explicit source-bound adapter. The focused
  variant-capture and affected architecture tests passed 12 tests. Hosted tag
  acceptance `v0.5.0rc230` (run `38366989584`) passed the architecture
  selector, external installed-wheel check, and Ubuntu, macOS, and Windows
  preview jobs; the prerelease package job was skipped. No lint predicate
  behavior changed.

- **Test selection and hosted gate follow-up (2026-10-12):** Hosted run
  `38333207786` for tag `v0.5.0rc213` passed its full unit stage but failed the
  repository-wide Ruff format step on the oversized MCP integration suite.
  Follow-up work split that suite by API, import, verification, model, and CLI
  behavior, with shared isolated setup in `tests/mcp_test_support.py`. The
  former 1,073-line suite is now 195 lines, and its stale size ceiling was
  removed. The MCP modules are selectable with `slow and template_checkout`.
  Local evidence passed: 27 MCP tests with 76 subtests, 49 package smoke and
  selected MCP parity tests, five module/suite architecture tests, and Ruff
  format/check across the checkout. No lint predicate or rule behavior changed.

- **Pytest-native contract-coach evidence suites:** The 654-line `unittest`
  suite is split into focused pytest modules for source-bound inspection and
  reporting, and for native capture and runner behavior. The suites use the
  `evidence_lint` and `slow` markers and contain 26 individually selectable
  cases; their shared public-template workspace and fake runner now live in one
  test-support module used by CLI/MCP and electrical parity consumers. The
  old test-module size exception is removed. The change affects test structure
  and selection only; contract-coach behavior and evidence policy are unchanged.

- **Named connector power-pin evidence:** The existing
  `connector.unconnected_supply_pin` and `connector.unconnected_return_pin`
  rules retain default `REVIEW` semantics. Each now has a focused exact-native
  gate with one open named contact and a fully assigned control, selectable by
  its own rule ID. The source fixtures are synthetic and test native pin/net
  extraction; they do not decide whether a connector contact should be used,
  bonded, common, or isolated. Exact KiCad 10.0.0/10.0.5 hosted acceptance
  passed on supply tag `v0.5.0rc156` (run 38250769875) and return tag
  `v0.5.0rc157` (run 38250769672). Earlier runs exposed and corrected a
  native fixture-load issue, a Ruff format issue, and an unreachable fixture
  guide in the Markdown documentation graph.

- **Named component supply-pin evidence:** `component.unconnected_supply_pin`
  now has an exact-native fault/control pair on one synthetic non-connector
  component. The fault leaves U1 VDD open with GND assigned; the control assigns
  both pins. Tagged hosted acceptance `v0.5.0rc158` (run `38252361023`) passed
  the exact KiCad 10.0.0/10.0.5 lane and installed-wheel check. The `REVIEW`
  prompt does not state the correct rail or prove that the pin must connect.

- **Named component return-pin evidence:** `component.unconnected_return_pin`
  now has a separate exact-native fault/control pair on a synthetic
  non-connector component. The fault assigns VDD while leaving GND open, so the
  named return predicate is exercised without relying on a second open pin.
  Tag `v0.5.0rc159` passed hosted acceptance (run `38253423642`), including the
  pinned KiCad 10.0.0/10.0.5 cases and installed-wheel check. The lane preserves
  `REVIEW` semantics and does not assert a required common ground domain.

- **Test architecture — Keep native fixture acceptance selectable by theme.**
  The exact-version empty-netlist fault and nonempty control now live in the
  pytest module `tests/test_empty_netlist_evidence_native_fixture_lane.py`,
  tagged `design_lint`, `evidence_lint`, `native_kicad`, and `slow`. This keeps
  the native evidence boundary selectable without importing another lint
  theme into the broad hosted acceptance module. The former
  `tests/test_ci_hosted.py` has been retired. Serial roster,
  net-label fallback, and reference-bond fixtures live in the focused pytest
  modules `tests/test_serial_peer_native_fixture_lane.py` and
  `tests/test_serial_reference_bond_native_fixture_lane.py`. Native
  digital-peer, USB-C, STM32, connector-return, connector-inventory, and PCB
  access lanes have module-level theme selection and retain native/slow markers.
  Hosted planning/release checks and mocked PCB fixture scheduling also have
  separate selectors; the latter stays synthetic and is excluded from native
  KiCad and slow markers.
  The hosted USB data-path, LED rail, SuperSpeed-pair, DC-reference, and IC
  rail-capacitor native acceptance, plus PCB return-path orchestration, now have focused pytest
  modules and marker selection. More legacy
  extraction remains. This is test organization and selection progress, not a
  new native run; local exact KiCad images remain necessary to revalidate the
  fixture lane. Synthetic serial endpoint-roster tests now keep UART net-label
  discovery in `tests/test_serial_participant_net_labels.py`, with shared
  source builders in `tests/serial_participant_support.py`; both suites are
  selectable with `interface_lint`. Power-sequence dependency checks and
  observed output-to-enable cycle regressions now have separate suites, with
  shared synthetic contract builders in `tests/power_sequence_support.py`.
  External-protection contract comparisons and review-policy candidates now
  have separate pytest suites using `tests/external_protection_support.py`.
  The schematic geometry coverage suite is now six pytest functions instead of
  two `unittest.TestCase` methods, separating opt-in policy, review/block,
  ignore staleness, and supported-capability coverage while retaining its
  `design_lint` and `schematic_lint` markers.
  The schematic text-policy suite now uses four top-level pytest functions,
  and its rule catalog references and architecture guards match the
  `schematic_lint` selector. This preserves existing rule behavior.
  SPI and serial peer-voltage policy tests now use top-level pytest functions;
  the eleven SPI suppression controls have individual names and direct rule
  catalog references. This improves focused interface selection without
  changing either voltage heuristic.
  The grounding and connector-pin contract regressions are also split from
  `tests/test_electrical.py` into
  focused pytest modules selectable with `return_path_lint` and
  `connector_lint`. The repeated connector power-pin example is a small
  synthetic netlist fixture. The connector-role regressions now use pytest
  functions split across connector identity/population, returns, and power-pin
  suites; catalog fixture paths track those owners. These are existing
  contract regressions; the move adds no lint rule or measured reviewer
  outcome. I2C pull-up contract tests
  now have their own `interface_lint` pytest suite, with reusable synthetic
  model builders isolated in `tests/electrical_i2c_support.py`. SPI contract
  tests now have the same focused pytest selection, with builders in
  `tests/electrical_spi_support.py`. Serial peer contracts now use their own
  focused suite and support module as well; these moves continue to shrink the
  old electrical test file without adding rules or changing electrical
  behavior. The previous mixed I2C heuristic suite is now split into bounded
  pytest modules for missing pull-ups, equivalent resistance, and rail-family
  review; parameterized fault/control cases and catalog references are kept
  rule-specific. LED bridge cases also use pytest functions with separately
  selectable topology controls. These are test-organization changes only.
  STM32/CubeMX fault,
  control, and source-binding regressions now
  use top-level pytest functions with their existing `design_lint`,
  `component_lint`, and `interface_lint` markers; catalog references point to
  those functions. This improves selection without changing LINT-050. Four
  I2C electrical-contract parity cases now live as top-level pytest tests in
  `tests/test_electrical_i2c_parity.py`, selected by `interface_lint` and
  `parity_lint`. Their shared project harness and native-netlist serializer
  live in `tests/electrical_parity_support.py`; the electrical tool-surface
  parity registry points to all four cases. The broad parity module shrank
  from 3,061 to 2,647 lines and its no-growth ceiling was lowered accordingly.
  This is test organization and parity evidence only; it adds no lint rule or
  electrical behavior. On 2026-10-11, the USB-C VBUS-path fault/control moved
  into the focused pytest suite `tests/test_electrical_usb_c_parity.py` with
  `design_lint`, `interface_lint`, `parity_lint`, and `slow` selection. The
  shared CLI/MCP harness fixture now has one owner in
  `tests/electrical_parity_support.py`; the I2C and USB-C parity suites both
  use it. This shrank the legacy parity suite by 77 lines and adds no
  electrical behavior. The four-case DB9 common/isolated return matrix now
  lives in `tests/test_electrical_connector_return_parity.py` as a focused
  pytest suite selectable with `return_path_lint` and `parity_lint`; the tool
  surface map follows the moved test. This shrank the legacy module by another
  125 lines without changing grounding behavior.
  Direct and bonded serial-peer parity now live in the themed pytest module
  `tests/test_electrical_serial_peer_parity.py`, selected with `interface_lint`,
  `return_path_lint`, and `parity_lint`. The module reuses the typed serial
  netlist builder and shared CLI/MCP harness; the surface map follows both
  moved cases. This removes another 255 lines from the mixed legacy suite
  without changing electrical checks.
  Digital-peer voltage contract parity now has its own interface pytest suite,
  `tests/test_electrical_digital_peer_voltage_parity.py`. The shared
  `ElectricalParityHarness` owns typed netlist/contract installation, digest
  binding, and CLI/MCP report comparison for the connector-return, serial-peer,
  and digital-peer voltage suites. This removes another 104 lines from the
  mixed legacy suite.
  PCB return-path requirement parity now lives in the focused pytest suite
  `tests/test_electrical_pcb_return_path_parity.py`, selected with
  `return_path_lint` and `parity_lint`. It keeps the synthetic fake-PCB
  connectivity fault/control and CLI/MCP comparison together; the shared
  `ElectricalParityHarness` remains the owner of disposable project setup.
  The surface map follows the move, and the legacy parity suite shrank by
  115 lines without changing return-path checks.
  Connector pin-relationship parity now lives in
  `tests/test_electrical_connector_pin_relationship_parity.py`, selectable by
  `connector_lint`, `return_path_lint`, and `parity_lint`. It exercises the
  authored common-return and common-supply requirements, an intentional
  unconnected pin, and CLI/MCP report parity from the same synthetic netlist.
  The legacy parity suite shrank by another 120 lines; no contract behavior
  changed.
  Combined I2C, CAN, USB-C, and SPI contract parity now lives in the focused
  pytest module `tests/test_electrical_bus_contract_parity.py`, selected with
  `interface_lint` and `parity_lint`. Its 6.7 KB synthetic XML netlist is a
  separate fixture under `tests/fixtures/electrical/`; the passing baseline and
  structured fault mutation still exercise all four authored contracts through
  CLI and MCP. The surface map follows the move, and the legacy suite shrank by
  338 lines without changing contract behavior.
  Component voltage-rating, power-rating, and MOSFET stress parity now live in
  `tests/test_electrical_component_rating_parity.py`, selected with
  `component_lint` and `parity_lint`. Those pytest cases reuse the existing
  typed component builders and the shared source-bound harness; the electrical
  surface map now includes all three. The mixed legacy suite shrank by another
  331 lines. Connector contact-current parity now lives in
  `tests/test_electrical_connector_rating_parity.py`, selected with
  `connector_lint` and `parity_lint`; it uses the same typed harness and the
  shared contact-rating builders. The surface map follows the move, and the
  mixed legacy suite shrank by another 119 lines. This changes test selection
  only, not the lint predicate or its default disposition. On 2026-10-11,
  RS-485 authored-contract fault and control tests moved into the focused pytest
  module `tests/test_electrical_rs485_contract.py`, selectable with
  `design_lint` and `interface_lint`. Reusable builders now live in
  `tests/electrical_rs485_support.py` and are shared by parity and retained-
  evidence suites. The CAN termination and power-connectivity regressions now
  live in `tests/test_electrical_can_termination.py` and
  `tests/test_electrical_power_connectivity.py`, with reusable synthetic
  builders in their theme-owned support modules. Their focused pytest markers
  are `interface_lint` and `power_lint`; neither test theme needs a project
  checkout. Together these extractions shrink `tests/test_electrical.py` from
  1,831 to 385 lines. Its shared synthetic power/simulation contract installer
  now lives in `tests/electrical_simulation_support.py`, and parity/evidence
  consumers import that support module rather than a test module. Contract
  behavior is unchanged. Electrical setup and chart suites now carry the
  `template_checkout` marker, and an architecture check guards external
  electrical fixture consumers against missing that marker. The remaining legacy
  module is below 1,000 lines but stays on the incremental decomposition list
  until it is below the 500-line review threshold. Release evidence replay
  regressions also moved into pytest suites for component ratings, connector
  contacts, PCB return pads, and PCB test access. A shared synthetic
  `ElectricalEvidenceWorkspace` now owns the disposable source-bound report
  setup and omission replay helper. The legacy
  `tests/test_electrical_evidence.py` is now 406 lines and pytest-native. Its
  combined synthetic netlist lives in
  `tests/fixtures/electrical/release-contract-evidence/netlist.xml`; digital-
  peer voltage replay is isolated in the 115-line
  `tests/test_electrical_digital_peer_evidence.py`. Both suites select through
  `evidence_lint`, with the digital-peer suite also marked `interface_lint`.
  This is test architecture work; the evidence rules and release policy did not
  change. On 2026-10-11, the synthetic DC-reference regressions moved from a
  `unittest.TestCase` to top-level pytest functions, with six named
  parameterized controls. Rule-catalog locators now point directly to those
  functions, and the architecture suite verifies both theme scope and
  rule-specific collection. The candidate behavior and default REVIEW policy
  did not change. The remaining decoupling and complementary-pair regressions
  now use top-level pytest functions, with direct rule-catalog locators and
  entries in the architecture suite's pytest-native/theme-scope guard. Their
  existing `power_lint`/`component_lint` and `interface_lint` markers remain;
  boundary controls now have named parameter IDs. The focused selector passed
  27 tests; the pytest-style architecture slice passed 17, and the rule catalog
  suite passed 11. These are test organization and selection improvements;
  neither predicate changed. Connector-verification integration tests also set
  an explicit reasoned `off` override for PCB component inventory, since they
  do not supply that check's exact native board evidence; LINT-102 remains
  covered by its dedicated fixture and acceptance lane.
  The active-rule fixture guard now derives the required area marker from each
  catalogued rule theme; `parity_lint` supplements rather than replaces that
  marker. The audit found six fixture modules missing at least one required
  area marker, including the serial and power-path CLI/MCP parity suites. Their
  markers are corrected, and the architecture check now prevents the same
  selector gap. The architecture slice passed 58 tests; the affected synthetic
  return/power slice passed 36 with two environment-gated skips. Collection
  confirmed that the power-path parity, serial parity, and exact-native
  connector suites are selected by their rule-theme markers. No lint predicate
  or native result changed.

- **Repository module architecture — Prevent new god files while shrinking
  legacy modules.** The `architecture` pytest marker covers module-boundary
  checks and a repository-wide scan of Python modules in `kicad_tooling/`,
  `scripts/`, and `tests/`. New modules must stay below 500 lines; the 38
  existing modules at or above that size have no-growth ceilings in
  `tests/python_module_line_ceilings.json`. Remove each ceiling when its module
  is split below 500 lines. The current inventory has 38 modules at or above
  500 lines and three above 1,000: `hwrepo/models.py`, `hwrepo/mcp_server.py`,
  and `tests/test_mcp.py`. These remain open decomposition work, not accepted
  target sizes; `hwrepo/models.py` remains shrink-only. The focused architecture
  slice passes with `-m architecture` and the documented public template root.
  On 2026-10-10, the five USB connector-to-PHY path contract types moved into
  `hwrepo/usb_data_path_models.py`. Internal services and fixture builders now
  import that owner directly; `hwrepo/models.py` retains compatibility exports,
  and its no-growth ceiling dropped from 5,980 to 5,729 lines. This refactor
  preserves the existing contract behavior and does not add an electrical rule.
  The follow-on `v0.5.0rc40` split moved eight power-path and power-sequence
  contract types into `power_path_models.py` and `power_sequence_models.py`.
  Internal services and regression fixtures import those owners directly;
  `models.py` keeps identity-compatible exports. The new `design_lint` plus
  `power_lint` architecture test guards ownership, import boundaries, and size;
  parameterized package tests require both modules in the wheel. The registry's
  no-growth ceiling is now 5,521 lines. The wheel asset inventory also moved
  from `scripts/ci.py` to `kicad_tooling/package_assets.py`, reducing the CI
  coordinator's ceiling from 556 to 528 lines. This is structural coverage;
  it adds no electrical rule. On 2026-10-11, the shared peer-coverage adapter
  was split into component-pin, digital-voltage, I2C, serial, and USB modules.
  Evaluation coordinators now import each coverage owner directly, and the
  architecture suite guards every module below 500 lines and checks model
  ownership. The extracted adapters preserve existing report fields and add no
  lint rule. The PCB return-path requirement models then moved to
  `pcb_return_path_models.py`; internal services, the native fixture runner,
  and synthetic builders now import that owner directly. The shared registry
  retains identity-compatible exports, while architecture tests guard owner
  size and import boundaries. This split shrank `models.py` by 84 lines and
  lowered its recorded ceiling by the same amount; it changes no return-path
  behavior and adds no lint rule. Ground-domain and exact pin-connectivity
  contract records now live in `grounding_models.py` and
  `pin_connectivity_models.py`; electrical evaluation, evidence, runner, and
  chart services import their owner types directly. Architecture tests preserve
  identity-compatible registry exports and prevent the shared module from
  regaining those definitions. It removes a further 52 lines from the shared
  model registry and adds no lint rule. The STM32/CubeMX contracts and coverage
  records now live in `stm32_pin_map_models.py`; the shared registry preserves
  their compatibility exports, internal services import the owner directly,
  and architecture tests guard ownership and imports. This removes 124 lines
  from `models.py` without changing LINT-050. Hosted impact planning and
  GitHub Actions output writing now have one owner in `ci_hosted_planning.py`;
  `ci_hosted.py` retains compatible imports for callers. The architecture suite
  checks ownership and those exports, and the hosted coordinator ceiling fell
  from 892 to 846 lines without changing execution behavior.
  The reviewed custom component-role pin, binding, and map contracts now live in
  `component_role_models.py`. Component services import that owner directly;
  `models.py` keeps identity-compatible exports. The architecture suite checks
  owner size, import boundaries, and compatibility, and the registry shrank from
  5,061 to 5,022 lines with a matching lower ceiling. This extraction adds no
  lint rule or behavior change. Power source/load pin requirements now live in
  `power_connectivity_models.py`; the power evaluator, evidence services, and
  regression builders import the owner directly while `models.py` preserves
  identity-compatible exports. The architecture and package-asset checks cover
  the new owner, and the shared registry shrank from 5,022 to 4,919 lines. This
  extraction does not change the authored connectivity predicate or its
  evidence boundary. USB-C contract records now live in `usb_c_models.py`, and
  shared pending/not-applicable states live in `analysis_state_models.py`.
  Services and regression builders import those owners directly while
  `models.py` preserves identity-compatible exports. Architecture and wheel
  checks cover the new boundaries; the registry shrank from 4,919 to 4,554
  lines. This extraction adds no lint rule or behavior change.
  On 2026-10-12, the architecture size gate exposed two growing lint suites
  above the 500-line review limit. PCB model-ownership assertions now live in
  `tests/test_design_lint_architecture_pcb_models.py`. Shared CLI/MCP report
  setup moved to `tests/design_lint_mcp_parity_report_support.py`, and
  connector coverage plus ignore-lifecycle assertions moved to
  `tests/test_design_lint_mcp_parity_connector_coverage.py`. Each resulting
  test and support module is below 500 lines. The full architecture-marked
  suite passed 177 tests and 895 subtests; both split CLI/MCP parity scenarios
  also pass. That suite caught a lingering internal import of
  `PcbConnectivitySnapshot` through the compatibility registry, so the native
  fixture adapter now imports it from `pcb_connectivity_snapshot`. No lint
  predicate or policy changed. On 2026-10-12, crystal-network requirements and
  coverage records moved into `crystal_network_models.py`. Internal services
  and synthetic regressions now import that owner directly, while
  `hwrepo/models.py` retains identity-compatible exports. Architecture and
  wheel-asset tests guard the boundary; the shared registry ceiling dropped
  from 4,554 to 4,398 lines. The extraction changes no lint behavior. On
  2026-10-12, the four PCB keepout contract and report models moved into
  `pcb_keepout_models.py`. Internal services import the theme owner directly;
  `hwrepo/models.py` retains identity-compatible exports, including its public
  shared UUID primitive. Architecture and wheel-asset tests guard the new
  owner and imports. The shared registry shrank from 4,398 to 4,261 lines; the
  extraction changes no lint predicate or policy. On 2026-10-13, connector
  return-distribution requirement and evidence models moved into
  `connector_return_distribution_models.py`. Internal services and test
  builders import that owner directly, while `models.py` retains
  identity-compatible exports. A focused connector architecture test guards
  owner size, registry definitions, service imports, and compatibility. The
  registry shrank from 4,247 to 4,186 lines; its no-growth ceiling was lowered
  to 4,186. The extraction changes no report schema or lint behavior.

- **LINT-010 — Keep exact-version I2C fixture acceptance theme-selectable.**
  The native resistor-array fault/control now lives in
  `tests/test_i2c_pullup_native_fixture_lane.py` with pytest markers for design
  lint, interfaces, native KiCad, and slow execution. The move preserves exact
  KiCad 10.0.0/10.0.5 image checks, repeated normalized exports, and the
  channel-specific SDA fault/SCL control assertions. It shrinks the legacy
  hosted test module; exact native execution still requires the digest-pinned
  Docker lane.

- **LINT-011/067 — Keep native CAN fixture acceptance in the interface theme.**
  Split-midpoint termination and peer-assignment fault/control cases now have
  dedicated pytest tests in `tests/test_can_native_fixture_lanes.py`. The
  module pins both supported KiCad images, checks exact synthetic source and
  normalized-netlist digests, and retains CAN termination contract outcomes,
  REVIEW status for the asymmetric peer fixture, and read-only fixture mounts.
  The legacy hosted test module is smaller; native execution still belongs to
  the digest-pinned package acceptance environment.

- **LINT-102 — Compare schematic assignments with placed PCB footprint IDs.**
  The source-bound inventory now reports both missing fitted placements and
  exact `library:footprint` identity differences as review findings. A
  tooling-owned native schematic/PCB fault-control pair pins the expected
  assigned and placed IDs, while the existing mode and exact-ignore lifecycle
  applies to both finding types. The rule does not infer pad-geometry
  equivalence. The exact KiCad 10.0.0/10.0.5 lane is wired into tagged
  acceptance; local native execution remains unavailable without `kicad-cli`
  or a running Docker daemon.

- **LINT-111 — Compare default/base DNP flags across schematic and PCB.**
  The shared native PCB snapshot already records footprint DNP state and the
  source-bound netlist records schematic DNP state. A focused default-REVIEW
  rule now reports mismatches only for matching references with assigned
  footprints. Named variant overrides remain outside its comparison.

- **LINT-086 — Bound the USB split-reference prompt with applicability evidence.**
  The default-REVIEW rule has synthetic direct, series-resistor, USB-C,
  duplicated-contact, shunt, and multiport fault/control coverage. Its exact
  native fixture lane passed in tagged `v0.5.0rc15` (GitHub run `37851810081`)
  on digest-pinned KiCad 10.0.0 and 10.0.5. All 11 topology cases passed on
  each version; repeated normalized netlist contracts matched for every case.
  The 2026-10-09 public remeasurement used the digest-pinned KiCad 10.0.5 image
  `ghcr.io/kicad/kicad@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`.
  CP2102 (`eecf7bb`), FUSB302/RP2040 (`7d95292`), and 16nx (`ca7de22`) each
  had one supported common-reference path and zero baseline prompts. Each
  source was exported twice; normalized typed-netlist hashes matched both the
  repeated export and the earlier 10.0.6 screen. Moving every matched
  connector reference pin to a synthetic net in the typed contract produced
  exactly one stable review per sample. This records applicability,
  cross-version reproducibility, and seeded-fault sensitivity; it does not
  establish field precision or reviewer value. Independent author dispositions
  and review times are optional follow-up evidence, not prerequisites for using
  the rule or continuing lint development. No additional example project is
  needed to continue the rule's implementation. New public or sanitized
  examples would help test applicability boundaries, especially intentional or
  switchable return isolation and unsupported multi-device topologies; they do
  not substitute for independent field dispositions or reviewer-time evidence.
  Keep public source checkouts and raw exports outside this repository, and add
  only minimal tooling-owned synthetic fault/control fixtures with provenance.
  Do not ask reviewers to label a
  synthetic split as a defect: the heuristic detects a review-worthy difference
  and cannot infer whether common reference was intended. Keep the rule at
  default `REVIEW` while field dispositions are unavailable. The prior receipt
  path was an ignored build artifact and is absent from this checkout; public
  source checkouts and exported netlists remain outside this repo. Recreate the
  receipt only if an exact remeasurement needs it. Count a quiet result
  as a supported non-finding only for common-reference paths in
  `common_reference_path_count`; `NO_SUPPORTED_PEER_PATHS` contributes no
  non-finding, and `INCOMPLETE` remains a partial screen. Keep unresolved labels
  visible and keep project defaults and the review-only prompt unchanged while
  evidence is gathered.

  Review evidence now also lists non-endpoint components whose uniquely
  assigned normalized schematic-netlist pins appear on both endpoint
  reference nets. It includes symbol, value, footprint, pin metadata when
  available, and whether the source netlist lists DNP metadata. This is a
  reviewer aid only; it does not change the predicate or infer physical fit,
  component conduction, a required bond, or PCB continuity. Synthetic cases
  cover DNP metadata present and absent, stable ordering, common-reference
  control, and CLI/MCP parity. A direct SuperSpeed fault/control regression
  verifies the same reference-component evidence on the second supported path
  family.

  A new Tooling-authored synthetic native case covers a two-port USB isolator
  with separate host and device reference domains. It expects no peer-reference
  finding and records two recognized connector groups, two incomplete PHY port
  groups, and zero supported data paths. The expected `INCOMPLETE` coverage
  makes the quiet result visibly unsupported; it is not counted as a negative.
  Exact digest-pinned native acceptance passed in tag `v0.5.0rc211` (GitHub run
  `38330024505`) on KiCad 10.0.0 and 10.0.5, including repeated normalized
  netlist exports. See the fixture contract and source hash at
  `../tests/fixtures/design_lint/usb-isolator-peer-reference-native/README.md`.

  A public topology lead is the DStat Mainboard rev 1.2.3 PCB at pinned commit
  `b6b2bbfdb7f8b2997d3035b083edbab2348333dc`. Its board source declares CERN
  OHL v1.2, maps USB1 pin 5 and U6 (TPD2S017) ground to `/USB_GND`, and maps
  FB2's two pads between `/USB_GND` and `GND` ([pinned board source][dstat-pcb]).
  The D+/D− path runs through multi-pin U6, outside the current direct/one-
  resistor path scope, and FB2 is not yet represented by a validated supported
  bond class. Keep this as an applicability lead only: it is excluded from
  supported-path, precision, and reviewer-value counts until an exact native
  export and a scoped topology adapter can evaluate it. No project files or
  netlists were copied into Tooling. A topology-shaped synthetic boundary
  control now confirms that a multi-pin protection array plus a two-pin
  reference ferrite remains `NO_SUPPORTED_PEER_PATHS`: it contributes zero
  supported or common-reference paths, produces no review candidate, and is
  not counted as a quiet non-finding. This validates the exclusion behavior
  only; it does not evaluate DStat or establish support for that adapter path.

- **LINT-094 — Open native power output on comparable peers.** The original
  exact-symbol gate passed tagged GitHub package acceptance in `v0.5.0rc12` (run 37796753272),
  including repeatable synthetic exports on digest-pinned KiCad 10.0.0 and
  10.0.5, the CLI/MCP parity test, and the installed-wheel external-template
  check. Its review prompt covers an open `power_out` pin when a matching
  fitted peer has one assigned net, without claiming that peers should share
  nets. This extension also reviews different symbols carrying one matching
  native `PART_ID` when value, footprint, complete pin inventory, native pin
  type, and per-pin function text match. Identical generic placeholders count
  only as structural metadata, not an electrical role. The expanded fault and
  control passed repeated exports on both pinned KiCad versions locally on
  2026-10-09; retain it for hosted acceptance on the next tagged source. No
  project source or candidate code was imported.

1. **Fail closed on empty native netlists.** LINT-078 now blocks source-bound
   lint when KiCad returns a successful export with zero component records. The
   trigger was a pinned KiCad 10.0.5 probe of a public legacy schematic that
   returned an empty netlist with exit code 0; the source was not copied into
   Tooling. A tooling-owned synthetic blank schematic now reproduces a
   successful empty export on both pinned KiCad 10.0.0 and 10.0.5; its paired
   nonempty control remains parseable, and the normalized typed inventories
   match across versions. Keep this evidence-integrity guard ahead of adding
   more heuristics.
2. **Keep P0 connector and contact-rating cases in acceptance.** LINT-002 and
   LINT-047 cover split-return, missing peer-power-contact, and peer-pin fault
   controls with synthetic source-bound native exports. The
   `NativeConnectorReturnFixtureTests` lane passed both pinned KiCad versions
   on 2026-10-03 and was rerun locally on 2026-10-08 against the current
   checkout: 2 tests and 4 subtests passed. A targeted rerun on 2026-10-09
   passed one native lane test with two exact-version subtests. It includes an
   explicit
   no-connect-marker peer fault;
   J2.1 remains a REVIEW candidate on both versions, while the common-net
   control passes. LINT-079 extends that lane with a current interface role map
   over numeric-only connector pin functions; the pinned KiCad 10.0.0/10.0.5
   run passed locally on 2026-10-04, including cross-version normalized
   netlist equality for mapped return and supply fault/control cases. The
   split-return fault stays `REVIEW`; the
   common-return control passes, and the mapped-role hint does not assert
   required connectivity. The lane includes a two-connector open generic
   power-pin fault and shared-net control, plus a numeric-function/neutral-net
   variant that keeps the exact
   repeated-contact prompt while dropping the numbered-net hint; the common
   control clears that mismatch prompt and retains four open pin-role coverage
   prompts. The LINT-079 report follow-up now identifies per-pin role sources;
   a synthetic three-connector regression now checks two matching supply
   contacts against one outlier across three different generic/numeric symbol
   identities. It reports only when the outlier shares the authored voltage
   domain; all-common and separately authored-domain controls pass. This
   extends typed-netlist coverage and is not a new native-export result. The
   existing source-bound CLI/MCP parity test also now covers three mapped
   custom connector peers with two matching and one split return and supply.
   It now confirms that the role-aware finding suppresses an overlapping
   generic peer-pin warning when it covers the same contacts. The focused
   CLI/MCP parity case passed on 2026-10-07 with synthetic netlist XML and the
   clean public template checkout at commit
   `ed89536f0dbbcb013145af2994fef41b2250143e` as its external project root;
   this verifies adapter parity, not a native KiCad export.
   A typed-netlist partial-map control also confirms that a mapped role finding
   does not suppress the generic peer warning when a third peer remains
   undeclared; the full peer assignments stay available for review.
   Connector coverage now also promotes same-symbol siblings of a reviewed
   custom connector into inventory candidates. A CLI/MCP partial-map case
   confirms the unreviewed sibling remains `UNDECLARED`; this expands coverage,
   not inferred pin roles or required connectivity.
   LINT-077 also passed its source-bound contract,
   CLI/MCP parity, retained-evidence replay, synthetic fixtures, and pinned
   KiCad 10.0.0/10.0.5 native exports. Keep these cases in GitHub CI. Before a
   project adopts a contact-rating requirement, its electrical owner must
   review exact ratings, derating conditions, and per-contact load from
   approved sources.
   Saved local `test_component_and_connector_rating_controls_export_repeatably` receipts cover the
   digest-pinned KiCad 10.0.0 and 10.0.5 images. They record repeatable native
   exports and synthetic fault/control outcomes for component-voltage,
   component-power, connector-contact-current, and MOSFET-stress contracts.
   The connector-contact case passes at 1.60 A / 2.00 A = 0.8 and fails at
   1.61 A / 2.00 A = 0.805; both versions share normalized netlist SHA-256
   `a61bc6c086e4abb5a3af84ddceae10f845a314c2f742cc450b1ed19c7f2419f1` and
   normalized ERC SHA-256
   `dbcb2273e067531c5e027ac9482ccf7ede0b4e2f7bd3ac01ad83b25510664338`, with
   zero native ERC errors. The retained local event receipts are dated
   2026-10-03; no hosted GitHub result for this dirty branch is recorded.
   LINT-074 now also covers direct UART links that terminate at source-identified
   connector candidates. The new MCU-to-header split-reference fault and
   common-reference control passed repeated native exports on pinned KiCad
   10.0.0/10.0.5; an exact authored `separate_nets` map suppresses the prompt.
   Keep it REVIEW-only because different references may be intentional.
   LINT-080 now compares complete DB9 return, two-pin diode, and generic
   peer-pin fault/control reports across independent Python hash secrets. This
   supplements in-process input-reordering tests; it does not replace the
   pinned native fixture lane.
   The process probe now serializes four synthetic DB9 grounding and
   pin-connectivity contract outcomes. Split returns fail the common-domain
   requirement and pass the isolated-domain requirement; the common-return
   control produces the inverse for both contract services. Each result binds
   the typed-netlist digest and the relevant requirement digest. The focused
   determinism/catalog run passed on 2026-10-07: 462 tests and 636 subtests in
   an isolated Python 3.11 environment. Three independently randomized
   processes returned identical serialized reports and check results. This is
   typed-service determinism evidence, not another native export.
   LINT-080 also applies the same three-process check to the multi-device
   MOSFET stress contract. A synthetic change to Q2's on-state
   drain interval changes only Q2's VDS status; Q1 remains passing, and the
   common two-device control passes. The focused lint and MOSFET contract suite
   passed on 2026-10-07 with 615 tests and 732 subtests. The same typed netlist
   digest is retained while the authored requirement digest changes. This
   checks deterministic contract reporting and does not extend the native
   fixture or validate a real component.
   The LINT-063 hash-seed matrix compares direct output-to-LED and parallel-
   resistor faults against a return-side series-resistor control. Both faults
   retain `component.led_directly_driven_from_output` as `REVIEW`; the series
   control clears that rule. Its complete report remains `REVIEW` because the
   synthetic `LED_RETURN` and `GND` nets retain the independent
   `net.return_labels_without_pin_roles` finding. The focused determinism,
   LED-rule, and catalog suite passed on 2026-10-07: 469 tests and 653
   subtests. This is deterministic topology-review evidence, not a resistor
   adequacy or physical-behavior result.
   The four-port DB9 native lane now also evaluates the exported netlists
   against synthetic common-return and per-connector isolation requirements.
   The split case must fail the common
   requirement and pass the isolation requirement; the common-net control must
   do the reverse. The new contract assertions are wired into the exact-version
   acceptance tests. A local native run on 2026-10-07 passed the focused
   acceptance test on KiCad 10.0.0 and 10.0.5 using their catalogued image
   digests and the public workflow-template commit
   `5ca79bedf665a9b6577d96b1d47f13ccd518c968`: 2 tests and 4 version subtests
   passed. All four common-return versus isolated-return contract outcomes
   matched, repeated exports were stable, and normalized netlists matched
   across versions. Hosted acceptance for this DB9 contract pair passed in
   `v0.5.0rc123` (GitHub Actions run `38205232934`). The new rule-scoped lane
   verified that only the DB9 fault/control sources are exported and completed
   hosted acceptance in `v0.5.0rc195` (GitHub Actions run `38312579543`).
   A separate CLI/MCP parity test now exercises the same common-versus-isolated
   DB9 grounding requirement with synthetic netlist XML. It checks the four
   fault/control combinations and requires both surfaces to return identical
   checks. This verifies shared-service behavior, not a native export or PCB
   copper continuity.
   The native acceptance harness now also compares `PinConnectivityAnalysis`
   against its DB9 exports and generic peer-power fixtures. The power cases
   require common +5V across J1.1/J2.1/J3.1, where the open J3.1 fault fails and
   the common control passes; a separate authored contract accepts split J1/J2
   outputs with J3.1 intentionally unconnected and rejects the common-net
   topology. The exact pinned native lane also passed locally on 2026-10-07
   using catalogued KiCad 10.0.0 and 10.0.5 images. All eight pin-connectivity
   relationship outcomes and the stale-symbol-pin fault matched their expected
   statuses; repeated exports were stable and six normalized fixture-netlist
   digests matched across versions. The stale contract names absent pin J1.99
   as unused and fails with `unknown symbol pins=['J1.99']`. Local receipts are
   under `/private/tmp/kct-native-connector-pin-contract-20261007` and
   `/private/tmp/kct-native-stale-pin-*`. This verifies native-export behavior
   for tooling-owned synthetic fixtures; the hosted GitHub run remains pending.
   A follow-up closes an evidence gap for `unconnected` requirements: if a
   referenced component exists but the native netlist has no symbol pin
   inventory for it, the relationship now fails with an explicit missing-
   inventory diagnostic instead of treating the absence as proof of
   intentional disconnection. The installed-service probe passes the valid
   unconnected control and rejects connected, stale-pin, and missing-inventory
   cases. The source-bound CLI/MCP parity regression passed on 2026-10-07
   against the clean public KiCad-Test checkout at commit
   `ed89536f0dbbcb013145af2994fef41b2250143e`. The full suite was rerun on
   2026-10-07 with `KICAD_TEMPLATE_ROOT` set to that clean public checkout:
   2,056 passed, 49 skipped, and 27 parts-assistant HTTP tests failed when the
   sandbox denied `127.0.0.1` socket binds; 2,312 subtests passed. No design-lint
   or electrical-parity test failed. This is a fail-closed service check, not
   evidence that a native exporter omitted pin inventory in the synthetic
   schematic lane. LINT-080 now also repeats the missing-versus-complete
   symbol-pin inventory case across three independently randomized Python
   processes. The missing-inventory requirement fails with the exact component
   named, and the complete inventory control passes; this guards report
   stability without replacing CLI/MCP parity or native-export evidence.
   LINT-080 also extends its three-process hash-seed comparison to a project-
   mapped return-role split and common-net control. The fault remains `REVIEW`
   with per-pin classification-source evidence; the common control remains
   `PASS`. The map catalog and typed-netlist digest are included in the report.
   This verifies report stability for that mapped branch, not native export;
   keep the existing LINT-079 exact-version lane as separate evidence.
   A further LINT-080 extension compares complete source-mapped series
   power-path reports across the same independent processes. The open-element
   fault remains `REVIEW` with one evaluated authored requirement and one
   finding; the repaired path remains `PASS`. This is synthetic typed-netlist
   evidence and does not claim a native export or component-conduction proof.
   LINT-080 now also compares the complete UART-label discovery report and an
   exact source-mapped endpoint control across those processes. The unmapped
   label candidate remains `REVIEW` with `discovery_basis=net_label`; the
   authored endpoint map suppresses that candidate. The report retains its
   separate `connector.no_connected_return` review because the generic header's
   return-pin role is not mapped. This confirms process-stable reporting for
   the heuristic without letting a serial map clear unrelated pin-role
   coverage. It does not prove that a UART peer is required or establish board
   copper connectivity.
   LINT-080 also compares source-mapped power-sequence dependency reports. The
   open-enable fault remains `REVIEW` with the sequence map evaluated against
   three authored stage/dependency requirements and one mismatch; the repaired
   control remains `PASS`. This is typed-netlist evidence and does not establish
   startup behavior on hardware.
   LINT-080 now also compares an exact source-mapped STM32 CubeMX pin-map
   mismatch with a valid control. Both reports retain complete map coverage;
   the map hash stays fixed while the IOC source hash changes with the fault.
   This is contract/report determinism evidence and does not verify compiled or
   flashed firmware behavior.
   Connector coverage output now sorts project interface IDs. Its mapped-return
   fault regression also reverses interface IDs, catalog records/pins, review
   rows, and pin-map keys; coverage and the full lint report remain equal for
   fixed source digests. This is typed-service ordering evidence; existing
   custom-connector CLI/MCP parity remains a separate adapter check.
   The LINT-074 multi-UART split-reference fault and common-reference control
   now also compare complete reports across three independent Python hash
   secrets. The fault localizes to J1/U1; the common control clears that rule
   while preserving unrelated review findings. This extends deterministic
   report coverage, not the rule's electrical applicability or precision.
   The LINT-066 SPI and UART voltage-domain prompts each remain `REVIEW` when
   unmapped and are suppressed only by complete exact maps. LINT-080 now
   confirms byte-identical complete reports across three independently
   randomized Python processes. This is determinism evidence; field precision
   and reviewer value remain unmeasured.
   LINT-080 now also covers LINT-067's split CAN-peer fault and common-pair
   control across those processes. The fault remains `REVIEW`, the control
   omits the divergence finding, and each report carries the digest of its own
   typed-netlist input. This extends determinism and input-binding evidence;
   reviewer value and field false-positive rate remain unmeasured.
   The header-only SPI/UART external-interface boundary is now also compared
   across those processes. Both rules retain `NO_SUPPORTED_ENDPOINTS`, zero
   recognized IC endpoints, and no peer-voltage findings; this confirms the
   report does not promote off-board connector buses to direct on-board IC
   peers. It adds process-determinism evidence, not a defect or field-precision
   measurement. The same boundary now has a source-bound CLI/MCP parity case:
   both surfaces return identical full reports from retained synthetic
   netlist XML, including the two `NO_SUPPORTED_ENDPOINTS` entries and no
   SPI/UART peer-voltage findings.
   The LINT-079 partial-map case now also runs through the three-process
   hash-seed probe: with J3 undeclared, its generic peer-pin outlier remains
   visible alongside the mapped-role finding; complete role coverage suppresses
   only the overlapping generic warning, and an all-common control clears both
   mismatch prompts. This checks report stability and coverage-sensitive
   suppression using synthetic typed netlists, not native exports or a
   connectivity requirement.
   A separate three-process case now compares two different connector symbols
   whose project maps classify generic supply contacts in the same voltage
   domain. An open J2 contact remains a REVIEW finding with its exact empty-net
   evidence; the role-aware group suppresses a duplicate open-pin warning, and
   the common-net control passes. This checks the initial missing-power-pin
   regression class while preserving the rule's REVIEW-only, no-commonality
   boundary; it does not establish that the two interfaces must share a rail.
   LINT-080 also compares the typed LINT-077 contact-rating checks at the exact
   authored 0.80 utilization limit (`PASS`) and at 0.805 (`FAIL`). Both use the
   same synthetic typed-netlist input; the source-bound requirement digest
   changes with the current allocation. This checks process stability of the
   rating calculation, not a complete electrical-analysis run or native export.
   The new reviewed peer-scope case compares three generic `Pin_1` contacts
   marked unlisted while pin 2 is mapped as return. Separate groups retain the
   split-return review and suppress signal comparison; a shared group reports
   both return and signal divergence; a common signal/return control passes.
   The focused determinism/catalog run passed with 465 tests and 641 subtests;
   the mocked native-lane orchestration passed separately and verifies the
   source-pinned fixture set. The exact-version exports remain configured in
   GitHub CI, with no hosted result recorded for this revision.
   LINT-080 now also compares a mapped USB data-path fault and two valid
   topologies across three randomized processes: a missing D+ series resistor
   remains one evaluated mismatch, the complete series-resistor path passes,
   and the documented direct integrated-PHY topology has no path mismatch.
   Its independent STM32 CubeMX and physical differential-pair REVIEW prompts
   remain visible. The focused determinism, USB data-path, and catalog suites
   passed with 472 tests and 644 subtests. This adds typed-report stability and
   suppression-boundary evidence; exact-version native export remains a
   separate acceptance result.
   LINT-084 now closes a narrow power-path gap found while reviewing the
   supported two-pin component families: fitted `Device:Fuse` and
   `Device:Polyfuse` symbols with both pins on one net produce an opt-in-capable
   REVIEW hint. Fault/control, policy, catalog, CLI/MCP parity, and three-process
   hash-seed tests passed locally. The exact KiCad 10.0.0/10.0.5 fixture cases
   are wired into the GitHub package job; the RC4 result must pass before
   counting the pinned native lane as verified. A supplementary local KiCad 10.0.6
   export of all four tooling-owned fuse fixtures now repeats and matches the
   expected fault/control findings; see LINT-084. Keep the predicate limited
   to the two named symbol families and do not infer that every fuse must be
   in series.
   The original DB9 return fault also passed a supplemental local KiCad 10.0.6
   native-export screen: both return heuristics reported the split fault, the
   common-net control passed, and numeric pin functions with neutral net names
   retained the peer-pin detection. The four fixtures had zero native ERC
   errors. This does not replace the digest-pinned 10.0.0/10.0.5 lane; see
   LINT-002 for evidence and fixture hashes.
   3. **Verify exact custom-symbol applicability.** LINT-091 extends the
   project-authored LINT-069 role map with a passive two-pin capacitor role
   consumed only by LINT-046. Synthetic typed cases cover exact identity,
   valid and wrong-return topology, DNP, stale maps, role isolation, and
   ordering; CLI/MCP parity and pinned native fault/control fixtures are in
   place. Tagged acceptance `v0.5.0rc17` (GitHub run `37863872527`) confirmed
   exact KiCad 10.0.0/10.0.5 behavior, with repeatable exports for the mapped
   control and wrong-return fault. This adds custom-symbol applicability to an
   existing REVIEW heuristic, not a new electrical conclusion. LINT-092
   extends LINT-089's native `power_in` evidence to non-connector components
   with generic or absent pin functions. The synthetic lane checks open and
   explicit no-connect faults, connected and DNP controls, connector exclusion,
   and CLI/MCP parity.
   Its focused native regression now mounts only those four synthetic
   component-pin schematics and records a component-specific receipt. Tagged
   hosted acceptance `v0.5.0rc149` (GitHub run `38246884720`) passed the
   `component.unconnected_power_input` selector and exact KiCad 10.0.0/10.0.5
   lane. It remains REVIEW-only and does not infer the pin's positive-supply or
   reference role.
3. **Measure the value of existing REVIEW rules.** Continue with public
   geometry, LED, and peer-connector cases that have applicability signals.
   The public STM32 USB-to-triple-UART sample already recorded under LINT-031
   is an applicability case, not a confirmed-fault benchmark: it has repeated
   generic headers but no independent pinout that can establish whether a
   differing return or supply is wrong. The existing peer-pin and reviewed-role
   rules cover this class. Do not add another connector heuristic from this
   sample without a seeded fault/control that demonstrates new value.
   The LINT-017 `POR_B`/`PORN` native alias lane now passes locally on pinned
   KiCad 10.0.5 and is enabled in the GitHub package job; owner dispositions
   for connected-bias and intentional-NC examples remain open.
   LINT-024 now has full exact-version native coverage on KiCad 10.0.5 and
   10.0.6, including a valid paired-connector layout that remains a REVIEW
   candidate while its contacts share one native net. The exact KiCad 10.0.5
   re-screen of its two public-template J1
   wire/body candidates is complete: both show the same unique layout with
   clean ERC and byte-identical repeated exports. Keep author intent unresolved
   until an owner disposition is available; this is not a false-positive count.
   Avoid repeating the same layout as another sample. Keep the rule opt-in and
   seek a distinct, supported candidate or author disposition for further
   precision measurement. A 2026-10-05 parser rescan after text-alignment
   support now returns complete coverage for all eleven rule groups on the six
   unchanged public schematics, but retains only that same unresolved layout.
   This closes the stale text-support measurement and adds no new candidate or
   author disposition.
   For LINT-061/066, use only source-matched public examples that expose
   supported digital-peer functions. The 2026-10-03 workflow-template screen
   found no LINT-066 candidates in its three examples with native toolchain,
   ERC, DRC, and netlist
   checks passing; their aggregate summaries are `FAIL` because design-lint
   returns `REVIEW` for undeclared connector inventory. Record that sample as
   inapplicable and leave precision unmeasured. For applicable examples, record
   evaluated coverage, confirmed useful findings, false positives, missed
   seeded faults, and reviewer effort. Keep the current opt-in or REVIEW
   defaults until the evidence supports a change.
   The public STM32 USB-device sample recorded under LINT-031 had no
   output-driven LED topology, so LINT-063 was inapplicable and reviewer value
   remains unmeasured. A secondary screen of four KiCad 10.0.5 bundled demos
   also found no supported LINT-066 pattern; all 50 LED-like symbols used
   custom library identities without PART_ID role maps, so local LINT-063 was
   outside its declared predicate on those samples. A repeated kicad-happy
   v2.2.1 screen of the public Arduino
   and Raspberry Pi LED examples then produced both `LA-AUD` classification
   and an `LR-001` error on each: the audit names the fitted 1 kΩ `R1`, while
   the error says no series resistor exists. The public example docs describe
   the GPIO-to-R1-to-LED-to-ground path. Treat `LR-001` as a confirmed false
   positive for this topology; the classification may be useful review context,
   but reviewer effort was not measured and its contradiction prevents direct
   adoption. Exact pins, hashes, and limits are recorded under LINT-031.
   A broader exact-version screen of bundled KiCad project roots is now
   recorded under LINT-063/066/074: it found no supported candidate for those
   rules in this public demo corpus. Stop repeating this generic demo corpus.
   The next useful screen needs a source-matched public design with a direct
   UART peer and explicit reference pins, or a supported SPI/UART peer whose
   native power-pin types and explicit rail labels satisfy LINT-066. Keep
   author disposition, false positives, and reviewer effort unmeasured until
   such a case is available.
   A targeted HALPI2 public-project screen found a documented isolated RS-485
   interface with separate `GND` and `GND_RS485` nets, but no direct UART peer
   link for LINT-074. Keep it as an out-of-scope boundary control; do not widen
   the direct-peer predicate across an isolator based only on TX/RX labels.
   These results do not measure field precision or false-negative rate.
   The 2026-10-07 Calcumaker screen is now pinned and recorded under LINT-031.
   The deterministic label path found one serial-map coverage candidate on each
   of the MCU and keyboard roots, where native package-pin functions and generic
   connector functions left the earlier function-only detector inapplicable.
   The design document describes the MCU-to-keyboard USART link and identifies
   +3V3/GND; a native typed netlist confirms both signals and one reference net
   on each board. This is an applicability/discovery result under an
   intentionally unconfigured tooling roster, not a confirmed defect, ground
   requirement, or field-precision result. The sample has only one +3V3 domain,
   so LINT-066 remains inapplicable; its generic pin functions also leave
   LINT-074 outside its predicate. No source was copied into Tooling. The next
   useful peer/reference sample needs a source-matched public pinout or an
   independently authored synthetic requirement with fault and valid controls.
   A separate Calcumaker PCB geometry screen in LINT-031 used installed KiCad
   10.0.6 on its display, MCU, and keyboard boards; all three snapshots had
   zero tracks, zones, and vias. LINT-020 remains unmeasured on these
   placement-stage boards because it requires native copper connectivity.
   A second 2026-10-07 public screen of [Antmicro's CM4 Baseboard][antmicro-cm4]
   is recorded under LINT-031 as a multi-UART boundary control. Its README says
   KiCad 9.x; the KiCad 10.0.5 export is therefore a compatibility probe. Four
   UART channels are labeled across generic translator and bridge pins, while
   the identified `GND` pins share one schematic net. Existing serial peer and
   reference rules produce no candidates because the pin functions do not name
   TX/RX and the labels do not terminate at one connector candidate. The public
  sample has no approved pinout to establish a missing return. LINT-082 now
  adds a REVIEW-only label-pair path with synthetic split/common, map, ambiguity,
  CLI/MCP, hash-seed, and pinned-native fixture coverage. Its exact KiCad
  10.0.0/10.0.5 synthetic lane passed locally on 2026-10-07; see LINT-082 for
  source and normalized-netlist digests.
   [Antmicro's Debug Toolkit](https://opensource.antmicro.com/projects/ftdi-toolkit/)
   remains inapplicable to direct IC-to-IC peers because it exposes two
   independent FTDI UART channels at headers with selectable IO voltage.
4. **Advance one cohort candidate at a time.** Use LINT-031 to pin the source
   revision and installation procedure, compare fault and valid-control cases
   with the local baseline, and record unique detections, duplicates, misses,
   localization effort, and maintenance cost. The 2026-10-03 kicad-happy
   single-pin trial distinguished the two-peer open-contact fault from its
   common-net control, but its J2.1 prompt duplicates LINT-047. On the new
   valid off-board power-port control, `NT-001` prompts on both mapped contacts;
   local coverage already reports REVIEW when J1 is undeclared and PASS after
   the independently authored interface map is complete. No general
   singleton-net rule is justified. The candidate suppresses J2.1 when an
   explicit no-connect marker is added; the source-bound local native lane
   retains its REVIEW prompt on KiCad 10.0.0 and 10.0.5. Keep that conservative
   prompt because the marker alone does not resolve peer intent. The connected
   UART peer control is quiet under `NT-001`, while its source-bound roster asks
   for REVIEW when undeclared or partial and passes with the complete map. On
   the open test-point/connector fixtures, each `NT-001` item matches a native
   ERC `pin_not_connected` error on both pinned versions. These comparisons add
   no unique singleton-net detection. The off-board serial fixture also
   produces no unique detection: its four valid TX/RX singleton warnings match
   native ERC `isolated_pin_label` warnings, while the source-authored external
   peer map clears the local serial coverage prompt. A repeated-child-sheet
   control is covered below by source-bound geometry and native ERC. Do not add
   a general singleton-net rule; test broader hierarchy styles only when a
   specific gap remains beyond existing source-bound checks.

   A 2026-10-05 follow-up used the same pinned candidate on the mapped generic
   supply fault/control. It emitted `NT-001` INFO for both singleton supply
   contacts only on the split fault, but did not relate them through the
   reviewed voltage domain; the local LINT-079 finding is more specific. This
   adds no unique domain-aware detection and does not justify a general
   singleton-net rule. The next cohort trial should target a distinct gap in
   the higher-priority connector, protocol, or geometry backlog.

   The 2026-10-07 kicad-happy source recheck identified one narrow same-net
   component gap: the local passive rule recognized `Device:R/C/L`, while
   SP-001 also covers two-pin diode symbols. LINT-081 adds exact `Device:D`
   family support with separate fault/control fixtures and keeps the rule at
   REVIEW. The candidate package was not installed; this was a source-informed
   first-party addition. Its exact KiCad 10.0.0/10.0.5 native fixture lane now
   passes locally; no hosted GitHub result is recorded. Its metamorphic case
   adds an unrelated fitted resistor: the typed netlist digest changes, both
   diode fingerprints remain stable, and a scoped D1 ignore stays applied while
   D2 remains open. This verifies ignore scope for this rule family, not across
   every lint rule.

LINT-089 closes one connector gap: every matching generic connector power-input
contact can be open together, so peer-outlier detection has no differing
assignment to report. Native KiCad electrical type now supplies bounded
evidence for a `REVIEW` prompt. The synthetic fault/control pair is repeated on
the digest-pinned KiCad 10.0.0 and 10.0.5 images in the connector acceptance
lane; it does not declare that the contacts must share a net.

- **LINT-012 test selection — Keep USB-C contract regressions theme-selectable.** CC role,
  controller, mode-strap, debug-accessory boundary, VBUS capacitance, and ordered VBUS-path cases
  now live in the pytest modules `tests/test_electrical_usb_c_cc.py` and
  `tests/test_electrical_usb_c_vbus.py`, selected with `interface_lint`; the VBUS module also
  carries `power_lint`. Their shared synthetic builders live in `tests/electrical_usb_c_support.py`
  and are reused by the evidence and CLI/MCP parity suites. The legacy `tests/test_electrical.py`
  shrank from 2,602 to 1,831 lines. All 26 focused pytest cases pass; the existing
  electrical/evidence regressions and USB-C VBUS CLI/MCP parity case also pass with the separate
  public template checkout configured. This is test organization only: no contract behavior or rule
  default changed. A declared debug-accessory role remains `NOT_RUN`; static schematic assignments
  cannot establish its dynamic CC-state behavior. Select the focused slice with
  `.venv/bin/python -I -m pytest tests/test_electrical_usb_c_cc.py
  tests/test_electrical_usb_c_vbus.py -m 'interface_lint'`.

This execution focus is updated as evidence closes. A completed implementation
is not a reason by itself to expand its scope or change its default policy.

### P0 — Coverage and regression foundations

#### LINT-001 — Report contract and interface coverage gaps

- **Status:** Implemented v5. Reports preserve coverage separately from
  electrical findings. The same bounded connector identity feeds inventory
  coverage and connector pin, power-input, decoupling, return-anchor, and USB-C
  heuristics; an exact project-reviewed interface reference can extend those
  checks to a custom symbol. Inventory coverage also includes every instance
  with the same native symbol identity as a reviewed connector, so an unlisted
  peer remains visible for its own interface or not-applicable disposition.
  Discovery remains a documented heuristic.
- **Problem:** A clean heuristic report can still mean that nobody recorded
  which interface a connector implements or dispositioned every symbol pin.
  A partial pin map can hide an omitted interface contact even when no current
  lint rule recognizes its function.
- **Evidence and check:** The interface catalog and connector review map each
  catalog pin to an exported component pin. Every unlisted symbol pin needs a
  reason. `connector_inventory_review` records the project owner's basis for
  checking the full schematic interface inventory. Native KiCad netlist
  evidence supplies symbol identity, pin numbers, pin functions, and net
  assignments. The report names `UNDECLARED`, `INCOMPLETE`, and `STALE`
  references and unaccounted/unknown interface and symbol pins. Missing scope
  review or an empty `UNASSESSED` scope keeps the lane at `REVIEW`; an explicit
  inventory review can confirm a project with no external connectors.
  Connector candidates are discovered by the bounded numeric `J`, `P`, `X`,
  and `CN` reference-prefix scan and by standard `Connector`/`Connector_*`
  symbol-library identities, excluding `Connector:TestPoint*`; project-reviewed
  interface references are also included in connector pin, missing-return,
  power-rail, and USB-C candidate checks. For inventory coverage, each
  project-reviewed custom connector additionally brings every instance with
  the same native symbol identity into scope. Those peers still require their
  own interface map or not-applicable disposition; symbol identity does not
  copy pinout approval.
  Custom symbol identities otherwise require that exact project review. The
  standard family names follow KiCad's
  [10.0.5 symbol-library tree][kicad-symbol-library-10.0.5].
  The report carries the inventory basis and interface-catalog path/digest; the
  enclosing design-lint report binds the project manifest, lint policy,
  schematic source, and native netlist. The shared design-lint service is
  exercised through direct, native-verify, and CLI/MCP paths.
- **Boundary:** Candidate discovery cannot prove that every physical interface
  appears on the schematic or uses a recognized reference prefix or library
  family. Custom aliases and third-party symbol libraries remain outside the
  automatic scan unless one instance with the same native symbol has a
  project-owned interface review; this expands inventory coverage but does
  not infer roles for an unreviewed peer. `UNASSESSED`
  means the scan found no candidate and no review declaration; without an
  inventory review basis it keeps the lane at `REVIEW`. The basis is a
  project-owned assertion, not proof that the schematic contains every
  physical interface. A manually declared interface review reference outside
  the automatic scan is included in coverage and bounded heuristics. Coverage
  never infers that returns, supplies, or protocol
  pins should connect. `grounding` and `pin_connectivity` remain the
  project-authored checks for those relationships. A not-applicable decision
  covers only its named schematic component and does not validate the physical
  assembly.
- **Fixtures:** `tests/test_connector_inventory_coverage.py` covers an undeclared
  candidate, complete interface and symbol-pin accounting, missing and unknown
  catalog/symbol pins, an explicit not-applicable decision, a reviewed
  reference outside candidate prefixes, standard connector symbols under
  nonstandard designators, test-point and nonconnector anti-controls, stale
  references, missing catalog records, a missing inventory review, and the
  `UNASSESSED` no-candidate state. A reviewed custom connector brings other
  instances with the same symbol into coverage while an unrelated custom
  symbol stays outside that inferred group. A typed-netlist test and CLI/MCP
  parity confirm that an omitted peer remains `UNDECLARED`; this new discovery
  case is stable under mapping-order changes, and an explicit
  `not_applicable` disposition closes the sibling coverage gap. It does not
  claim a native KiCad export. The reviewed-return regression in
  `tests/test_connector_return_role_coverage.py` also permutes project interface
  IDs, catalog-record and pin order, review rows, and pin-map
  keys; the coverage and full lint reports stay equal for fixed source digests.
  Parity also confirms the
  nonstandard-reference candidate and suppresses the test-point control. A
  pinned native fixture
  repeats the `U7` connector candidate and test-point
  control exports on KiCad 10.0.0 and 10.0.5 and verifies exact `libsource`
  identity plus normalized-netlist and coverage-report digests. The embedded
  shapes are synthetic; the lane tests identity serialization and parsing, not
  canonical library geometry. A separate control confirms an explicit
  inventory review can cover a project with no external connectors. The
  design-lint regression covers standard connector symbols under a nonstandard
  `U` reference, repeated-pin and peer-pin findings, open supply contacts,
  missing-return review, common-return/power controls, DNP exclusion, and custom
  symbols included only through a project-reviewed interface reference. CLI/MCP
  parity also verifies that custom symbols under nonstandard `A` references
  enter connector coverage and the heuristic only while exact catalog-backed
  interface reviews are present; split returns prompt, and common returns clear
  the candidate. Power
  path and USB-C tests cover the same identity boundary. A CLI/MCP parity case
  checks nonstandard-reference findings. Native fixture orchestration is tested by
  `tests.test_connector_inventory_fixture_lane`; the exact pinned exports run
  in version-parameterized pytest cases in `tests.test_ci_hosted_connector_returns`.
  Native verify and CLI/MCP regressions assert that incomplete or undeclared coverage stays
  visible.
- **Empty-contract integration regression:** The synthetic project in
  [`test_verify_design_lint.py`](../tests/test_verify_design_lint.py) exercises
  `test_empty_connectivity_expectations_still_raise_native_connector_review`.
  It clears the authored component/net expectations and lint policy. Native lint
  still reports the exact `J1.7=GND1` versus `J2.7=GND2` return candidate with
  `UNDECLARED` connector coverage, and verification stays `FAIL` without
  filling in project expectations.
- **Remaining:** Physical connector inventory and symbols with custom library
  aliases remain human-authored scope decisions. Keep `UNASSESSED` distinct in
  reports; do not describe the candidate scan as exhaustive discovery.

#### LINT-002 — Connector mate and pin-role contract comparison

[kicad-symbol-library-10.0.5]: <https://gitlab.com/kicad/libraries/kicad-symbols/-/tree/10.0.5>
[kicad10-pad]: <https://docs.kicad.org/doxygen-python-10.0/classpcbnew_1_1PAD.html>

- **Status:** Implemented v3 for exact `common_net`, `separate_nets`,
  assignment-only, and intentionally `unconnected` relationships through the existing
  `pin_connectivity` contract. Explicit PCB net-tie and physical bond-path
  comparisons are implemented in LINT-025 because the schematic netlist cannot
  prove copper continuity. The native acceptance harness is wired to compare
  DB9 exports against common and per-connector-isolated requirements through
  both `GroundingAnalysis` and `PinConnectivityAnalysis`. It also compares a
  native open peer-power contact and common control against an authored shared
  +5V requirement, plus an independently powered/unused-contact control pair.
  An assignment-only DB9 rule passes on both split-domain and common-domain
  exports; the separate `common_net` rule rejects only the split-domain case.
  These are synthetic test requirements, not project contract files. The
  focused connector gate passed locally on 2026-10-13 with 518 passed, 16
  skipped, and 2,755 deselected; both pinned native connector fixture switches
  were enabled. The DB9 common/isolated contract pair passed hosted acceptance
  in `v0.5.0rc123` (GitHub Actions run `38205232934`), and the focused DB9 lane
  passed in `v0.5.0rc195` (GitHub Actions run `38312579543`). Hosted acceptance
  for the extended connector relationship matrix, including peer-power and
  stale-pin cases, passed in `v0.5.0rc228` (GitHub Actions run `38359915602`)
  with the connector-scoped gate, separate-project installed-wheel check, and
  Ubuntu, macOS, and Windows preview jobs. The prerelease workflow's separate
  package job remained skipped.
- **Problem:** Similar connector instances can have separately named or
  unassigned corresponding pins without a direct, project-readable assertion
  about their intended relationship.
- **Evidence and check:** For an exact project-authored list of component pins,
  `pin_connectivity` compares exported schematic net assignments to a required
  common net, distinct nets, one assignment per pin without prescribing a net,
  or no assignment. An observed net assignment establishes a wired pin for
  `assigned`; an open `assigned` or `unconnected` pin requires native symbol pin
  inventory. Missing inventory fails closed, and stale pin references fail with
  their exact reference. `grounding` continues to check named ground domains
  and coverage.
- **Boundary:** Connector similarity is only a candidate generator. It is not
  the requirement. Do not silently add or alter project contracts to clear a
  finding. Keep accepted isolation explicit. Population-dependent connector
  hints exclude references marked DNP by the native netlist; connector inventory
  coverage still evaluates declared interfaces independently.
- **Fixtures:** Synthetic common-return pass and disconnected-return fault;
  independent-return pass and newly common fault; named wrong-net fault;
  intentionally unconnected pin pass and newly assigned-net fault; stale symbol
  pin reference fault; and missing symbol-pin-inventory fault for an otherwise
  unassigned component. Assignment-only checks pass for pins on different or
  shared nets, fail when one required pin is open or has ambiguous multiple
  assignments, and fail when native pin inventory is unavailable. A
  fitted-versus-DNP connector pair also checks that
  population-dependent pin hints ignore DNP peers while preserving findings on
  fitted connectors. These check the project-authored relationship contract.
- **Related heuristic regressions:** A four-connector synthetic case uses
  DB9 pins 7/9 on separately named `RETURN_PORT_1` through `RETURN_PORT_4`
  and exercises both repeated-function and numbered-return review candidates,
  the `COMMON_RETURN` control, and an explicit rule-off decision for
  intentional isolation. A
  typed-netlist follow-up applies the same pin pattern to spaced
  `0V PWM 1`–`0V PWM 4`, underscored `0V_PWM_1`–`0V_PWM_4`, and compact
  `0V_PWM1`–`0V_PWM4` names; all three produce the numbered-return review. A
  common `0V PWM` net is a quiet control. A tooling-owned synthetic native
  fault/control pair now also preserves the spaced labels through KiCad export.
  This covers the failure's naming pattern without importing a board. A
  local exact-version native run on 2026-10-12 passed for KiCad 10.0.0 and
  10.0.5: the four split names and all eight pin memberships were retained on
  repeated exports, the fault produced `net.numbered_returns`, and the common
  control passed without findings.
  Tagged hosted acceptance for `v0.5.0rc147` (commit `43dfe95`, GitHub Actions
  run `38243428425`) passed with the `net.numbered_returns` pytest scope and
  `KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1`. At that point the rule's native test
  references shared a module-scoped fixture that exported the complete
  connector matrix. A dedicated focused native lane now selects only the PWM
  fault/control pair for this rule; the full connector lane retains the broader
  matrix. Tagged hosted acceptance for `v0.5.0rc148` (commit `5268a7f`, GitHub
  Actions run `38245516011`) passed the focused exact-version fault/control
  lane with the scoped pytest selector and native-fixture flag. The installed-
  wheel check against a separate project checkout and Ubuntu, macOS, and
  Windows preview jobs also passed; the package job was skipped by the
  prerelease workflow.
  The project-policy regression also keeps the default at `REVIEW` while proving
  an explicitly configured `block` override changes the report to `FAIL`
  without changing the finding fingerprint or evidence. A
  separate CLI/MCP parity case binds the spaced-name fixture to a synthetic
  netlist digest and confirms both surfaces return the same review finding;
  it verifies adapter parity, not native KiCad export behavior. A
  three-port case leaves one generic power contact unassigned while sibling
  contacts use separately numbered positive rails; both the pin-function
  mismatch and rail-name candidates identify it. No project board source is
  used. The native DB9 fault/control schematic pair is documented in the
  [four-port DB9 fixture README](../tests/fixtures/design_lint/four-port-db9-returns/README.md).
  A typed synthetic case also leaves a meaningful but unrecognized `BIAS_IN`
  function, with native `power_in` type, open on two exact-symbol connector
  peers. It produces the existing pin-function review; a shared-net assignment
  is the quiet control. The electrical type does not establish a required
  connection.
  The native generic-power-pin omission pair is documented in the
  [peer power-pin fixture README](../tests/fixtures/design_lint/generic-peer-power-pin/README.md).
- A synthetic exact-symbol connector group with incomplete pin-function
  metadata identifies a missing generic contact when two peers share one net,
  and a minority-net outlier when two peers agree. Consistent assignments,
  all-distinct independent ports, and a DNP outlier are controls. No project
  board source is used.
- **Native regression:** Hosted package acceptance exports split-return and
  common-return controls twice with each selected, digest-pinned KiCad 10.0.0
  and 10.0.5 image. This includes the synthetic four-port DB9 pins 7/9 pattern
  on separately named `RETURN_PORT_1` through `RETURN_PORT_4` nets, with exact
  native evidence for all eight pins and a common-net control. A three-port generic-pin fixture
  leaves J3.1 unassigned while J1.1 and J2.1 use separately numbered positive
  rails; the native fault and common-rail control check peer-assignment and
  rail-name findings. It preserves raw export hashes and requires equality
  after normalization to the parsed netlist contract, exact review findings on
  fault cases, and clean lint passes on controls. Raw KiCad XML includes a
  changing export timestamp.
  A second tooling-owned DB9 source pair uses the spaced labels `0V PWM 1`
  through `0V PWM 4` and the common `0V PWM` control. This verifies native name
  parsing without claiming that the four domains should be connected.
  A numeric-function variant renames pins 7/9 to native function text `7`/`9`
  and replaces return-like nets with neutral `NET_A` through `NET_D` labels.
  Both pinned KiCad versions preserve the two exact-symbol repeated-pin
  findings and four per-connector unknown-return coverage prompts. The
  `NET_COMMON` control clears the repeated-pin mismatch while retaining those
  four role-coverage prompts. Its normalized typed-netlist digest also matches
  across versions. This isolates pin-identity evidence from net-name evidence;
  it does not assign an electrical role or require a common return.
  The container mounts only tooling-owned synthetic schematics read-only and
  a generated output directory read-write. A separate native fixture
  set covers different connector symbols: `GND` on a USB-style connector and
  `RTN` on a serial-style connector, matching `PWR` functions on both, and a
  separately assigned `SHIELD` pin. It checks split-return and split-supply
  review findings, an unassigned serial return, and a common-return/common-power
  control that keeps the shield separate. This closes the gap between
  dataclass-only cross-symbol tests and native KiCad parsing without adding a
  rule or inferring that the domains must be common.
  The four-port DB9 netlists are also checked against two explicit synthetic
  grounding requirements: all eight pins on one `COMMON_RETURN` domain, or four
  per-connector `RETURN_PORT_n` domains. The matrix expects the split fault
  to fail the common-domain requirement and pass the isolated-domain
  requirement, with the common-net control producing the inverse. Each
  acceptance receipt records the source, native netlist, and grounding
  requirement hashes. The requirements are test-owned values, not an external
  project's contract.
  The acceptance lane now adds direct `PinConnectivityAnalysis` checks over
  the same DB9 exports and the generic peer-power fixtures. For DB9, the
  common-net requirement fails the split fixture and passes the common-net
  control; the isolated requirement has the inverse result. For generic power
  contacts, J3.1 left open while J1.1/J2.1 share `+5V` fails the common-rail
  requirement, while the complete three-contact control passes. An explicit
  variant requirement accepts separate J1/J2 output nets and an intentionally
  unused J3.1, and rejects the all-common control. The receipts bind each
  source, exported netlist, repeated normalized netlist, and pin-connectivity
  requirement digest. The exact-version lane passed locally on 2026-10-07 using
  the catalogued KiCad 10.0.0 image
  `sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3`
  and KiCad 10.0.5 image
  `sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`.
  All eight expected relationship outcomes and the stale-symbol-pin fault per
  version matched expectations. Repeated exports were stable, and the six
  normalized fixture netlist hashes matched
  across versions:
  `98c326c073ca0bf7ff38c00acddec5bbd2df1f5cb531936f3744a79bae533154`,
  `fbb740fb9f8c29bd880d871f33047aa8993ea99720d7707daca3feff41e3c3f2`,
  `2191755e294a0c26e1a60238e2bc1ef63aefca2b1c7c754c91ef4ec74a619a77`,
  `f150f82193d827efc6293d11e47af1e9ca5b0a050ca81f9a46fba7f40a481c3b`,
  `6db3e3b1076e1d09dcf946d4788da30b95ffe9fa99a8a6101b21c8da7f38a265`, and
  `84d3b98f56d7552448eef5b7113ab76ac28393a0933d722a5037e5ea41e7928f`.
  The four synthetic requirement hashes were
  `34be92f5f2160529103b0ebae985474a4d378adbf92ed28762e2f33a7ad46db0`
  (DB9 common), `47cb72763e37847de4f92dd57db093934bb539be2a8421eddb74f32ba0f7b6e0`
  (DB9 isolated), `42200be02b669b16033dcf9f213fb4c3f7db89d16119fa3c0eda2e998c3bd0b0`
  (peer common power), and
  `89757eec4c33e46a46ebb7a09554d08f1412ce914b0a30629fbbfca611b82665`
  (independent outputs plus unused contact). Receipts are local under
  `/private/tmp/kct-native-connector-pin-contract-20261007`; only tooling-owned
  synthetic schematics were mounted. The hosted GitHub run remains pending.
  A ninth pin-connectivity acceptance case applies an `unconnected` requirement
  to nonexistent pin J1.99 on the DB9 control export. Both versions fail that
  stale requirement with the exact diagnostic `unknown symbol pins=['J1.99']`;
  the source and normalized-netlist hashes match the DB9 common-return control,
  and the requirement digest is
  `bca062795033e030f2ccff16f3700ffeb8e81f8d9da16ddd2287b276ad716cd4`.
  The event receipt now retains stable per-check details alongside check IDs
  and statuses. These are synthetic contract-authoring checks, not board
  findings. Receipts are under `/private/tmp/kct-native-stale-pin-*`.
- **Version evidence (2026-09-30):** The hosted connector-fixture test passed
  against the clean public KiCad-Test checkout at `ed89536f0dbbcb013145af2994fef41b2250143e`,
  using the digest-pinned KiCad 10.0.0 image
  `sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3`
  and KiCad 10.0.5 image
  `sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`.
  Both versions reported the new four-port DB9 fault as `REVIEW` with exact
  J1–J4 pins 7/9 evidence under `connector.repeated_pin_function` and
  `net.numbered_returns`; the common-net control passed without findings. The
  DB9 source hashes are `c4a842c1685d5fbf21985aa22bd0b6436e163025f4381a8ac2544621c264e546`
  (fault) and `3c00cfdee7a7bbba3439baf49f82eb6911ead068cf04ac0782f8f8fe7297cecc`
  (control). Both versions produced the same normalized typed-netlist hashes
  for each case (`98c326c073ca0bf7ff38c00acddec5bbd2df1f5cb531936f3744a79bae533154`
  for the fault and
  `fbb740fb9f8c29bd880d871f33047aa8993ea99720d7707daca3feff41e3c3f2` for the
  control). Raw KiCad XML hashes are retained because export metadata can vary;
  repeatability is measured over the canonical typed netlist. Native event and
  command receipts remain under ignored `build/ci-hosted/native-connector-return-*/`
  paths in the disposable test project.
  The generic peer-power fault also passed in both versions: the exact open
  contact `J3.1` was reported alongside the two numbered rail assignments,
  while the all-connected `+5V` control passed. Its source hashes are
  `4e2382aede1643770a466a9c902b1e960f8a8ab0d1bc676a03db33dfe6e582a8`
  (fault) and `e50d57b2739dc49d3b164e0ea141f48835967fdc1982d3cfdd702f671dc7d197`
  (control); both versions reproduced normalized typed-netlist hashes
  `6db3e3b1076e1d09dcf946d4788da30b95ffe9fa99a8a6101b21c8da7f38a265` and
  `84d3b98f56d7552448eef5b7113ab76ac28393a0933d722a5037e5ea41e7928f`,
  respectively.
- **Mixed-symbol native evidence (2026-09-30):** The extended hosted fixture passed with the exact
  KiCad 10.0.0 image
  `ghcr.io/kicad/kicad:10.0.0@sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3`
  and KiCad 10.0.5 image
  `ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`.
  Both versions retained `J1.4=GND`, `J2.7=RTN`, `J1.1=PWR`, `J2.9=PWR`, and `J3.1=SHIELD` after
  native export. The split case emitted separate `connector.repeated_pin_function` findings for
  ground/return and PWR; the unassigned `J2.7` case emitted one localized ground/return finding; the
  commoned return and power control passed while `J3.1` stayed on `CHASSIS`. Each normalized typed
  netlist repeated identically. Source hashes and fixture boundaries are recorded in the
  [mixed-symbol fixture notes](../tests/fixtures/design_lint/cohort-cross-symbol-connectors/README.md).
- **CI revalidation (2026-10-03):**
  `NativeConnectorReturnFixtureTests` passed both digest-pinned KiCad
  10.0.0/10.0.5 cases. The lane re-exported the tooling-owned DB9 split-return
  fault and common-return control, numeric-function/neutral-net fault and
  control, generic missing peer-power pin, peer-pin
  outlier/divergence cases, and the cross-symbol return/shield controls. It
  used only synthetic fixtures and retained receipts under ignored `build/`.
- **Current local exact-version rerun (2026-10-08):** The same lane passed on
  KiCad 10.0.0 and 10.0.5. The four-port DB9 fault reported
  `connector.repeated_pin_function` and `net.numbered_returns`; the common-net
  control was clean. Numeric-only pin functions with neutral net labels still
  surfaced the pin mismatch while the common-net control removed that mismatch.
  The mapped grounding and pin-connectivity requirements, peer-power faults,
  cross-symbol controls, and normalized repeated exports also passed. Receipts
  remain under ignored `build/ci/native-connector-return-project-*/`; hosted
  acceptance for the current branch is not recorded.
- **Targeted exact-version rerun (2026-10-09):** The DB9 connector-return
  fault/control lane passed on digest-pinned KiCad 10.0.0 and 10.0.5: one
  pytest item and two version subtests. The test revalidated repeated native
  exports and the expected split-return review and common-return control.
  Hosted acceptance for the current branch is not recorded.
- **Hosted scoped-gate confirmation (2026-10-11):** The connector-focused
  prerelease tag `v0.5.0rc123` (commit `371dc42`, GitHub Actions run
  `38205232934`) passed with `KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1`. Its
  pinned KiCad 10.0.0/10.0.5 lane covered the DB9 split/common fault-control
  pair, neutral-name controls, and the explicit common/isolated grounding and
  pin-connectivity contracts. Only tooling-owned synthetic fixtures ran.
- **Named power-input peer regression gate (2026-10-12):** Tag
  `v0.5.0rc198` (commit `67c1576`, GitHub Actions run `38315525975`) passed the
  focused `connector.repeated_pin_function` rule gate, with the digest-pinned
  KiCad 10.0.0/10.0.5 DB9 return-contract fixture lane enabled. The same
  prerelease acceptance run passed its installed-wheel rehearsal against a
  separate project checkout and Ubuntu, macOS, and Windows portability
  previews; the stable-only package job was skipped by prerelease policy. The
  added synthetic fault/control pair leaves a meaningful `BIAS_IN` function
  with native `power_in` type open on two exact-symbol connector peers, then
  assigns both to one net for the quiet control. This validates the existing
  review heuristic on a new pin-function shape; it does not establish that the
  contacts must connect. No project board source was used.
- **Supplemental local native screen (2026-10-07):** The KiCad 10.0.6 CLI
  bundled with the installed application exported the DB9 split-return fault,
  common-return control, and both numeric-function/neutral-label variants
  twice. Raw XML and normalized typed-netlist digests repeated identically.
  The split fault emitted `connector.repeated_pin_function` and
  `net.numbered_returns`; the common control emitted neither. With numeric pin
  functions and neutral net labels, the fault emitted the two exact pin-number
  comparisons plus four unknown-return-role coverage prompts; the common
  control retained only those four coverage prompts. KiCad ERC reported zero
  errors and four synthetic-library warnings per source, with no diagnostic
  for the split return. This supports the bounded review heuristic and confirms
  name-independent pin evidence on one additional KiCad 10.x executable; it
  does not assert a required common ground or PCB continuity. Source and
  normalized digests are in the
  [fixture README](../tests/fixtures/design_lint/four-port-db9-returns/README.md).
- **Remaining:** No additional net-tie work is open here; see the synthetic and
  exact-version evidence recorded under LINT-025. Connector mate similarity
  remains a review candidate and never supplies the relationship contract.

#### LINT-047 — Generic peer connector pin assignments without a majority

- **Status:** Implemented v1 as `connector.peer_pin_assignment_divergence`, a
  default-review hint with exact findings, project rule overrides, and
  fingerprinted ignores.
- **Problem:** Matching connector instances can assign the same pin number to
  different nets while one or more exported pin functions are missing. With
  only two peers, or with no assignment shared by a majority, the existing
  outlier rule cannot say which contact diverged.
- **Predicate:** For fitted J/P/X/CN references using one exact native library
  symbol, compare each exported pin number. Report only when at least two
  contacts are assigned, their net assignments differ, at least one contact
  has unknown role metadata (absent or generic KiCad `Pin_N`), fewer than two
  contacts have meaningful pin-function metadata, and there is no unique
  most-common assignment. A unique repeated assignment belongs to the
  higher-confidence outlier rule. Open contacts
  remain with the existing outlier and named-pin rules; fully named groups
  remain with `connector.repeated_pin_function`.
- **Boundary:** Exact symbol and pin-number identity only makes a candidate
  comparison. It does not establish common function, required connectivity,
  isolation intent, PCB copper, or off-board behavior. Two independent ports
  can be a valid control; the finding asks the project to check its approved
  pinout before writing any connectivity contract.
- **Fixtures:** Two generic peers assigned to different nets; native absent
  function and generic `Pin_N` cases; a four-peer tie
  with two assignments on each net; three distinct assigned nets; same-net
  control; DNP exclusion; fully named and partially named groups delegated to
  the existing function rule; explicit review/block/off and fingerprint-ignore
  policy; CLI/MCP parity. A focused synthetic regression also models four
  nine-contact connectors with two split return-pin assignments and a shared-
  return control that is quiet for this peer-divergence rule. Both split pins
  produce `REVIEW`; the check does not decide that they must be bonded. All
  netlist inputs are synthetic.
- **Native evidence:** The tooling-owned
  [generic peer-pin fixture set](../tests/fixtures/design_lint/generic-peer-pin-assignment-native/README.md)
  exports absent-function and generic `Pin_N` faults and their controls twice
  on digest-pinned KiCad 10.0.0 and 10.0.5. Both report the no-majority fault
  as `connector.peer_pin_assignment_divergence`; each common-net control
  passes. The same lane asserts that a unique two-to-one assignment emits only
  the higher-confidence outlier rule.
- **Focused gate acceptance (2026-10-11):** The annotated tag `v0.5.0rc78`
  declared `Lint-Area: connector_lint` and passed GitHub Actions run
  `38139244092`, including the new synthetic nine-contact split-return case.
  No native fixture switch was needed because this addition expanded
  regression coverage without changing the analyzer.
- **Done:** The new default-review finding is catalogued, source-bound to exact
  pin/net evidence, independently configurable, and exercised by synthetic
  fault/control, exact-version native export, and CLI/MCP parity checks. No
  project source is used.

#### LINT-048 — LED directly across recognized supply and return

- **Status:** Implemented v1 as
  `component.led_directly_across_supply_and_return`, a configurable
  default-review hint.
- **Cohort input:** The pinned kicad-happy `validate_led_resistors` LR-001
  source identifies a potentially useful visible-resistor review question,
  while also estimating LED current from guessed color/voltage/current limits.
  A read-only trial on synthetic KiCad schematics produced LR-001 for an LED
  directly across `+3V3` and `GND`, and no LR-001 for a series-resistor
  control. The candidate also missed the direct-rail fault when a resistor
  appeared in parallel across the same rails, because its topology scan treated
  that resistor as a limiter. The Tooling rule keeps only the independently
  supportable direct rail-to-return pattern and does not copy value/current
  estimates, fixes, severity, or candidate code.
- **Predicate:** For a fitted exact `Device:LED` symbol with exactly two
  inventoried pins, report when both pins have unique, distinct native net
  assignments, and one net has an exclusive recognized positive-rail role
  while the other has an exclusive recognized return role. The candidate
  remains present if a resistor is merely parallel across those same nets.
- **Boundary:** This asks the reviewer to inspect polarity, current limiting,
  and the source/driver. It cannot establish forward operation, current,
  source limiting, resistor value, off-board circuitry, physical copper, or
  whether the LED is part of an unusual protected assembly. Only the exact
  `Device:LED` symbol ID and existing bounded power/return recognizers are in
  scope; custom, addressable, multi-die, incomplete-pin, and unrecognized-net
  cases remain outside the predicate. No resistance threshold or universal
  resistor requirement is asserted.
- **Fixtures:** Synthetic LED directly between recognized supply and return;
  visible series resistor; parallel resistor still faulted; DNP LED; exact
  symbol and pin-inventory boundaries; unrecognized rail; recognition through
  attached native supply/return pin functions; project override, off, exact
  ignore, and CLI/MCP parity. No project source is used.
- **Validation state:** The candidate analyzer trial distinguishes the direct
  rail fault and series control and exposes its parallel-resistor miss. Local
  source-bound predicate, policy lifecycle, test controls, and CLI/MCP parity
  are implemented. Native KiCad 10.0.0 and 10.0.5 source-to-netlist regressions
  now check the direct-rail fault, series-resistor control, and parallel
  resistor fault. The rule reports the two direct bridges and leaves the
  control clear on both versions, with repeated parsed netlists matching.
  Native ERC remains untested. No proprietary project source or fixture was
  inspected or stored.

#### LINT-049 — USB connector-to-PHY data path contract

- **Status:** Implemented v3 as an opt-in, project-mapped REVIEW rule. The
  cohort's universal series-resistor heuristic remains unadopted.
- **Cohort input:** The pinned detector looks for connectors whose value or
  library ID contains `USB`, recognizes a bounded set of D+/D− pin names, and
  reports when it cannot find a 15–33 Ω resistor on the connector-side data
  net. It also attempts to use MCU datasheet features as an exemption.
- **Trial evidence:** The two-pin synthetic USB parser fixture without external resistors produced
  one finding per data line; a visible 22R-per-line control produced no finding. Repeated candidate
  runs had identical filtered output. A separate Tooling comparison on equivalent synthetic
  `NetlistContract` objects emitted the broader named-pair review finding for both cases. This is
  now regression-tested by
  `tests.test_design_lint_named_pairs.test_named_complementary_nets_prompt_for_reviewed_pair_requirements`.
  The fixtures and reproduction commands are in
  [the USB cohort trial](../tests/fixtures/design_lint/cohort-usb-series/README.md).
- **Problem and evidence:** The expected topology depends on the selected PHY.
  ST AN4879 Rev 12 states that the matching output impedance is embedded in
  STM32 internal USB PHY pads and no external resistors are needed
  ([manufacturer note](https://www.st.com/resource/en/application_note/an4879-usb-hardware-and-pcb-guidelines-using-stm32-mcus-stmicroelectronics.pdf)).
  TI's TUSB2036 Rev I datasheet says its USB DP/DM pairs require approximately
  27 Ω series resistors ([manufacturer datasheet](https://www.ti.com/lit/ds/symlink/tusb2036.pdf)).
  The pinned cohort analyzer reports both integrated-PHY and external-PHY
  missing-resistor cases, so its generic prompt is not adopted.
- **Predicate:** A project-authored `design_lint.usb_data_path_map` names the
  exact connector and PHY symbol/footprint, D+/D− endpoint pins, expected nets,
  and per-line `direct`, `series_resistor`, or `inline_component` topology. A
  series path maps the exact fitted resistor symbol, footprint, endpoints, and
  project-approved nominal range. An inline path names one exact multi-pin
  component, maps the connector-side and PHY-side pin for each data line, and
  records every native component pin's expected net or explicit no-connect
  state. An optional reference policy records `common_net`,
  `separate_nets`, or `bonded`; a `bonded` entry also names the exact passive
  two-pin component, value, footprint, and pin-to-net assignments. The rule
  compares those decisions with native KiCad 10 XML netlist evidence. Direct
  paths support documented integrated PHYs; series paths support explicitly
  selected external resistor networks. A direct path can additionally map
  exact multi-pin protection shunts by identity, one D+/D− tap per part, full
  native pin inventory, and expected net or explicit no-connect assignments.
  It uses the standard project `review`,
  `block`, `off`, and exact-ignore lifecycle.
- **Boundary:** This rule checks a schematic decision after the project
  supplies it; it does not infer applicability, select resistor values, or
  validate the referenced manufacturer document. A mapped bond checks native
  component and netlist assignments but does not prove that the component
  conducts or that PCB copper joins the endpoints. The inline map checks exact
  schematic pin assignments, not datasheet pinout truth or protector behavior.
  It supports one inline component or direct-path protection shunts, but does
  not combine these maps or model multi-hop paths. The rule
  does not prove placement, signal integrity, PCB copper continuity, USB-C
  roles, or USB 3.x lane design.
- **Fixtures and validation:** Synthetic integrated-STM32 direct-path control;
  TUSB2036 27R-per-line control; missing, DNP, wrong-value, and wrong-net
  series-part faults; malformed contract topologies; exact six-pin inline-device
  control and required-ground-pin fault; malformed/partial inline maps; exact 0R reference-bond
  control and absent, wrong-identity, wrong-value, DNP, active-pin, and
  wrong-net bond faults; exact multi-pin protection-shunt pin-map control and
  stale identity, population, inventory, net, and no-connect faults in
  `tests/test_usb_data_path_protection_shunts.py`; rule override, disable,
  exact-ignore, CLI/MCP parity,
  mapping-order stability, and independent-process hash-seed stability. The
  hash-pinned native lane now includes a split-reference protection-shunt
  review, a common-reference control, and a miswired shunt-pin fault. Those
  source fixtures are registered but have not run under native KiCad locally.
  The exact topology check adds coverage beyond the broad named-pair prompt,
  because that baseline does not compare connector-to-PHY component topology.
  Fixtures contain no product design.
  A typed exact-map composition control now combines a mapped multi-pin USB
  protection device with a reference ferrite: the valid map stays quiet, while
  absent, miswired, or DNP ferrites produce one reference-path mismatch. These
  cases confirm that the exact path contract reports the bond fault without
  duplicating a split-reference heuristic prompt. Source-hashed synthetic
  native fault/control fixtures now combine the inline protection path with a
  mapped 0R return bond; the exact-version lane must verify their schematic
  exports before this combination counts as native evidence.
  Native schematic netlist exports are now regression-tested with synthetic
  direct-PHY control, external-PHY 27R-per-line control, a source-hashed
  external-PHY control with a mapped 0R reference bond, and resistor-bypass
  fault fixtures on KiCad 10.0.0 and 10.0.5. A synthetic inline-protection
  control, an open required component ground pin, and combined inline-path
  plus mapped-return-bond fault/control fixtures are also source-hashed for
  export on both versions. The valid control has no path finding; the fault
  reports the missing mapped R3 on one reference-path finding. Repeated exports
  must match after normalization to the parsed netlist contract. This does not
  run native ERC
  or validate datasheet pinout, PCB copper, placement, or signal integrity.
  Fixture hashes, exact image digests, and the reproduction command are in
  [the native USB regression README](../tests/fixtures/design_lint/usb-data-path-native/README.md).

#### LINT-003 — Paired-line and differential-interface completeness

- **Status:** Implemented v3 as review-only checks for bounded built-in
  CANH/CANL, USB D+/D−, USB SuperSpeed SSTX/SSRX, TX+/TX−, and RX+/RX−
  aliases, plus opt-in project aliases tied to an exact native symbol identity.
  Stale symbol/function mappings block lint; fitted DNP symbols are skipped.
  Connector peer mapping and physical pair constraints remain separate work.
- **Problem:** A named pair can be half-connected or have one side routed to a
  different interface while ordinary pin-assignment checks pass.
- **Evidence and check:** The native-netlist check reports incomplete pairs when a counterpart
  function is absent, a side lacks a unique net assignment, multiple pins map to one side, or both
  functions share a net. A valid control has exactly one pin per side assigned to distinct nets. USB
  SuperSpeed function aliases include SSTX/SSRX and the USB-IF Standard-A/Standard-B forms
  StdA_SSTX/StdA_SSRX and StdB_SSTX/StdB_SSRX, as documented in the
  [USB-IF USB 3.1 Front-Panel Implementation Document](https://www.usb.org/sites/default/files/USB3p1_Front_Panel_CabCon_Implment_Doc_Rev1p1.pdf).
  The
  [USB Type-C Specification Release 2.0](https://www.usb.org/sites/default/files/USB%20Type-C%20Spec%20R2.0%20-%20August%202019.pdf)
  records the naming transition from SSTX/SSRX to TX/RX. These aliases are checked with synthetic
  fault and valid-control cases plus the
  [pinned native fixture lane](../tests/fixtures/design_lint/complementary-pair-native/README.md).
  Project aliases are separately validated with synthetic vendor-named functions,
  a missing-net fault, a valid pair, a DNP control, stale-map blocking, exact
  symbol binding, CLI/MCP parity, and order-stable alias digests. Add
  project-authored peer maps before comparing across connectors or active devices.
- **Boundary:** Pin naming is vendor- and symbol-dependent; A/B polarity is
  inconsistent across RS-485 vendors. Do not infer off-board pairing,
  impedance, polarity correctness, or isolation from names. Keep this a review
  hint unless an interface contract gives the pair map.
- **Fixtures:** Synthetic open USB data side; both sides on one net; complete
  USB data pair on separate nets; intentionally unused pair with an exact
  project-owned ignore; Standard-A/Standard-B SuperSpeed aliases with open-line
  faults and complete controls; lane-indexed USB-C anti-control; exact-symbol
  project aliases with fault/control/stale-map checks. Repeated native exports
  on KiCad 10.0.0 and 10.0.5 verify the built-in pin-function text survives
  netlist normalization. Cross-component peer pairing, polarity, and PCB
  constraints require separate requirements and evidence.
- **Remaining:** Model explicit connector-to-device pair maps only when a
  cohort fixture demonstrates detection beyond existing `pin_connectivity`
  contracts. Do not infer that similarly named connector or device pins must
  connect across symbols.

#### LINT-004 — Rule catalog and fault/control coverage ledger

- **Status:** Implemented v2; additions to the active rule set must update the
  package catalog and pass its fixture-reference and emission-coverage tests.
  The CLI and read-only MCP surface can list the typed catalog without project
  or native evidence, so teams can inspect rule defaults and limits before
  enabling project overrides.
- **Problem:** A rule can be present without its intended detection range,
  supported evidence, known false positives, or negative controls being easy
  to audit.
- **Evidence and check:** Maintain rule metadata for ID, intent, evidence
  adapter, deterministic predicate, current maturity, supported versions,
  limitations, fixtures, and source references. Validate that every active
  rule has both fault and valid-control fixtures and that emitted IDs exist in
  the catalog. The standalone catalog query returns the same digest-bound typed
  metadata through CLI and MCP.
- **Boundary:** The catalog describes evidence, not electrical approval or
  project applicability. It must not become a duplicate project contract.
- **Fixtures:** Unknown rule ID; missing fault/control fixture entry; a valid
  intentional-isolation control; stable report/fingerprint case; backlog rule
  inventory and repeated guide counts that match the active package catalog;
  CLI/MCP catalog parity without a native summary; readable text output with
  default modes, evidence, and limits.
- **Rule-scoped CLI/MCP parity audit (2026-10-12):** A source scan found
  existing fault/control parity tests omitted from 13 active rules' catalog
  fixture lists. The catalog now indexes I2C pull-up and serial-peer parity,
  comparable component-pin and connector power-output parity, mapped passive
  bypass parity, and PCB keepout, RF antenna, and signal-path coverage parity.
  A catalog regression requires these exact parity cases to remain selectable
  by their rule IDs. The audit also found two power-output parity fixtures
  inheriting the unrelated PCB pad-net check without native board evidence;
  those fixtures now explicitly turn that check off. Three PCB parity modules
  now carry explicit design-lint, PCB, and parity markers. The combined
  13-rule selector passed locally (`232 passed, 12 skipped, 2,855 deselected`);
  catalog, fixture-reference, and reachability checks passed (`17 passed`).
  Skips are environment-gated exact-native cases; this change improves
  regression selection and parity evidence without changing lint predicates.
  The broader parity-area run exposed the generic connector power-input
  finding at `J12.1`; its existing CLI/MCP lifecycle test now asserts that
  finding and is indexed by the rule. The accepted-report check preserves the
  default-off peer outlier as `RULE_OFF` while requiring reviewed findings to
  be `IGNORED`. A third synthetic power-pin parity fixture now explicitly
  disables the unrelated PCB pad-net check because it has no native board
  snapshot. The expanded 14-rule selector passed (`244 passed, 14 skipped,
  2,841 deselected`), the complete `design_lint and parity_lint` slice passed
  (`113 passed, 2,986 deselected, 14 subtests passed`), and the
  catalog/backlog/architecture group passed (`65 passed`).
- **Done when:** CI can identify an undocumented rule or missing required
  fixture, and a reviewer can trace each report finding to its evidence and
  limitations.

#### LINT-076 — Analyzer execution and skipped-check coverage

- **Native prerelease selector audit (2026-10-12):** The architecture suite now
  requires every active catalog rule with exact-native fault, control, or
  metamorphic regressions to declare the corresponding `required_native_fixtures`
  switch. The audit found and closed 17 omissions across component pins,
  connectors, USB/RS-485 peers, PCB checks, and power rules; LINT-074 already
  declared its serial peer-reference lane. Package acceptance also checks all
  test Python support modules for environment-gated native regressions, then
  verifies every catalog switch is both exercised by a test gate and enabled in
  the hosted full acceptance workflow. It also follows fixture arguments from
  each catalogued native test into pytest fixture definitions and requires the
  rule's declared switches to match those reachable gates exactly. This catches
  a plausible but unrelated switch declaration; for example, serial peer
  regressions depend on the shared native digital-peer fixture. These checks
  keep focused annotated tags from silently skipping an exact-native regression.
  They govern test selection only; a passing fixture is not electrical approval.
- **Focused connector-rule tags (2026-10-12):** The connector native fixture
  suite covers split/common returns, peer-pin outliers and divergence,
  positive-rail returns, open generic connector and component power inputs, and
  numbered power-rail names through exact KiCad 10.0.0 and 10.0.5 images. Each
  corresponding catalog rule now names its native test as both a fault and
  valid-control fixture and requires `KICAD_RUN_NATIVE_CONNECTOR_FIXTURES`.
  Rule-scoped tags therefore collect the relevant native cases instead of
  silently skipping this shared fixture lane.
- **Two-pin selector follow-up (2026-10-12):** The shared exact-version lane
  already exercises 16 passive, diode, crystal, fuse, ferrite, and switch
  fault/control sources; the initial selector audit found that only the passive
  rule catalogued its native test.
  The runner now accepts rule IDs and filters the native exports to the
  selected rule. The fuse rule now catalogs a fuse/polyfuse fault/control test
  and requires `KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES`; the passive
  rule's existing native test is now filtered to its own four cases. The
  ferrite rule now catalogs its native fault/control test and selects only its
  two sources. The ferrite local selector passed six tests with two
  exact-native cases skipped and 3,099 unrelated tests deselected because local
  Docker access is denied. Direct pytest rule selection passes for the fuse
  and passive gates (`7 passed, 2 native skips` for fuse and `9 passed, 2
  native skips` for passives; over 3,000 unrelated tests deselected). Tagged
  run `38292257528` for `v0.5.0rc177` passed the focused
  fuse gate, its installed-wheel check against the external template, and all
  three portability previews. The tag enabled the native switch and selected
  the four fuse/polyfuse fault/control sources on the exact pinned versions.
  Its full `package` job was skipped by RC policy, so it is not full package
  acceptance. Tagged run `38292936740` for `v0.5.0rc178` passed the focused
  ferrite gate, its installed-wheel check against the external template, and
  all three portability previews. The tag enabled the native switch and
  selected only the ferrite fault/control source pair on the exact pinned
  versions. Its full `package` job was skipped by RC policy.
  The diode rule now catalogs its fault/control test and selects only its two
  sources. Its local selector passed seven tests with two exact-native cases
  skipped and 3,101 unrelated tests deselected. Hosted run `38293569399`
  for `v0.5.0rc179` passed its scoped lint and installed-wheel steps plus all
  three portability previews; the full package job was skipped by RC policy.
  The crystal rule now catalogs its fault/control test and selects only its two
  sources. Its local selector passed seven tests with two exact-native cases
  skipped and 3,104 unrelated tests deselected. Hosted run `38293748198`
  for `v0.5.0rc180` passed its scoped lint and installed-wheel steps plus all
  three portability previews; the full package job was skipped by RC policy.
  The switch rule now catalogs its fault/control test and selects only its two
  sources. Its selector collects 17 tests (15 passed, 2 exact-native skips),
  deselecting 3,099 unrelated tests. Hosted run `38293853354` for
  `v0.5.0rc181` passed its scoped lint and installed-wheel steps plus all three
  portability previews; the full package job was skipped by RC policy. The
  full package lane continues to run all 16 cases.
- **Rule-scoped native fixture inventory (2026-10-12):** An initial source-based
  comparison of the 17 modules assigned both `native_kicad` and `design_lint`
  markers found 13 native test functions across 11 modules without an active
  rule-catalog fixture reference. The I2C peer-reference, SPI peer-reference,
  CAN peer-reference, and CAN peer-assignment native fault/control tests are
  now linked to active rules and require their existing switches. The PCB
  signal-path native fault/control test is also now linked to LINT-095 and
  requires its existing switch. The native power-path fault/control test now
  links to both the source-path heuristic and mapped-path contract and requires
  `KICAD_RUN_NATIVE_POWER_PATH_FIXTURES`; both rule selectors collect its two
  pinned-version cases. The focused local power slice passed 66 tests, with the
  two native cases skipped because the exact-version lane is hosted. Hosted runs
  `38294501510` (`v0.5.0rc182`), `38294866007` (`v0.5.0rc183`), and
  `38295223564` (`v0.5.0rc184`) passed the scoped lint and installed-wheel
  steps plus all three portability previews; each package job was skipped by
  RC policy. CAN peer-assignment run `38296123722` (`v0.5.0rc185`) and PCB
  signal-path run `38296563673` (`v0.5.0rc186`) also passed those focused jobs
  and previews; their package jobs were skipped by RC policy. Power-rule runs
  `38297901205` (`v0.5.0rc187`) and `38297901239` (`v0.5.0rc188`) passed their
  focused lint and installed-wheel checks against the separate project plus
  all three portability previews; their package jobs were skipped by RC policy.
  **Native test scope audit (2026-10-12):** Six unindexed test functions across
  six modules remain after the rule links above. The inventory architecture
  test now requires each centrally registered native design-lint test function
  to either name an active rule or have an explicit scope disposition. Five
  are separate authored-requirement
  or evidence lanes: CAN termination topology, component ratings, empty-netlist
  export integrity, PCB probe envelopes, and PCB copper continuity. The sixth
  is the public KiCad 10.0.6 connector-ground cohort sample, retained for
  analyzer comparison; its fault/control behavior is already covered by the
  rule-selectable KiCad 10.0.0/10.0.5 return-net lane. I2C pull-up arrays are
  already catalogued under their active rule. These distinctions keep a
  rule-scoped tag from claiming coverage of a different authored contract.
- **Status:** Implemented for demonstrated gaps. `mapped_check_runs`
  distinguishes an optional mapped check that was not configured from one
  that ran with zero findings. It covers USB data-path, series power-path, and
  power-sequence maps, the three mapped checks without a dedicated coverage
  report. A 2026-10-07 review of the LINT-066 public applicability screens found
  that a quiet peer-voltage report did not distinguish missing supported pin
  functions from same-voltage peers. The report now adds bounded
  `digital_peer_voltage_coverage` entries for SPI and UART/USART: counts bind
  recognized and assigned endpoints, direct links, explicit-label comparisons,
  complete-map suppression, candidate groups, the native netlist digest, and
  authored-map provenance. This is a targeted extension, not a global per-rule
  ledger; it does not claim that every interface was recognized. The LINT-086
  USB reference heuristic now also reports bounded coverage: no recognized USB
  endpoints, incomplete endpoint evidence, no supported connector-to-PHY paths,
  or evaluated paths. Its counts bind recognized/supported endpoint groups,
  DNP/incomplete dispositions, supported paths, common/separate reference
  relationships, map-covered split paths, emitted candidates, and the native
  netlist plus typed USB map digests. The CLI text report explains each status
  so a zero-finding run distinguishes absent recognition, incomplete evidence,
  unsupported topology, and a completed path review. The report also includes
  one deterministically ordered `path_entries` record per supported
  connector-to-PHY path, with endpoint identity, reference-pin assignments,
  common/split/map-covered disposition, matched D+/D− pins and nets, and any
  accepted series resistors or two-pin shunt branches. The text and typed JSON
  reports expose this same source-level evidence. The optional entries preserve
  compatibility with earlier schema-2 reports; they describe exported net
  assignments and do not establish a physical return path or copper bond. The
  connector peer-pin review now has a similarly bounded coverage summary: it records candidate
  and fitted connector counts, exact-symbol pin groups, assignment and function
  metadata states, repeated-function groups, finding counts, and the native
  netlist digest. It distinguishes candidates that are all DNP, no exact-symbol
  peers, no comparable pins, incomplete native pin inventories, and evaluated
  groups. A missing, empty, or inconsistent same-symbol inventory raises
  `REVIEW` and identifies its references. The non-connector component peer-pin
  rules now report `component_peer_pin_coverage` entries with
  source-bound counts for exact-symbol groups and cross-symbol shared-`PART_ID`
  candidates, including aliases excluded because their values or footprints do
  not agree. The report names references in those identity-incomplete groups,
  and counts eligible aliases, complete and incomplete inventories, comparable
  and native-type/function-compatible groups, ambiguous assignments,
  deduplicated candidates, findings, and suppressed candidates. It distinguishes
  an ineligible `PART_ID` identity from no peer candidates, missing inventory,
  unsupported pin types/functions, ambiguous assignment, partial evaluation,
  and a completed comparison. These counts expose why the bounded scan did not
  emit a prompt; they do not prove full symbol discovery or require peer pins to
  share a net. Synthetic pytest fault,
  control, applicability-state, input-rule suppression, CLI/MCP parity,
  deterministic-hash-seed, and pinned native fault/control checks exercise this
  coverage. A synthetic CLI/MCP case confirms a mismatched shared-`PART_ID`
  value is reported as incomplete identity coverage without creating an
  electrical finding or changing `PASS` status.
- **PART_ID connector coverage correction (2026-10-22):** The guarded
  cross-symbol connector scan now records incomplete pin metadata separately
  from complete but differing functions or electrical types. Missing, blank,
  and KiCad `~` metadata remain `INCOMPLETE_EVIDENCE`; complete differing
  metadata reports `PARTIALLY_EVALUATED`, including when no peer group is
  comparable. These groups still do not emit an electrical finding or imply
  that pins should share a net. The report schema advances to version 6.
  Synthetic cases cover missing identity, inventory, function metadata,
  unnamed electrical type, and complete metadata mismatches. The focused
  selection uses:

  ```sh
  python -I -m pytest tests/test_connector_part_id_peer_coverage.py \
    -m 'design_lint and connector_lint'
  ```

  No proprietary project source is used.
- **LINT-117 coverage follow-up (2026-10-12):** The generic power-input peer
  comparison now shares the source-bound component-peer scan and coverage
  report. Its entry explains absent comparable peers, incomplete native pin
  inventories, unsupported power-input/function metadata, ambiguous or open
  assignments, and completed comparisons. Open pins remain outside the
  divergence predicate; coverage makes that exclusion visible without turning
  an open pin into an inferred defect. Synthetic fault, common-rail, open-pin,
  DNP, connector, identity, inventory, type, and function controls verify the
  states, with CLI/MCP report parity. The focused rule/area regression slice
  passed 55 tests. Exact KiCad 10.0.0/10.0.5 native fault/control runs passed
  eight selected tests. The local package smoke passed scoped pytest, Ruff,
  host and Windows Pyright, rumdl, wheel and source builds, source-wheel
  comparison, and installed-wheel origin/version checks; it skipped mdrepo and
  the external-template rehearsal, which remain in hosted tagged acceptance.
- **Current working-tree verification (2026-10-09):** The full pytest stage
  passed on the dirty checkout: 2,372 tests passed, 86 environment-gated tests
  skipped, and 1,880 subtests passed. Ruff formatting and lint, host and Windows
  Pyright, Markdown checks, wheel/source builds, and source-archive wheel
  equality passed. A fresh environment installed wheel version
  `0.5.0rc25.dev0+g4e13ff7bf.d20261009`; installed origin and version checks,
  inventory and surface checks against public `KiCAD-Test` commit
  `ed89536f0dbbcb013145af2994fef41b2250143e`, portable verification against a
  writable copy of that checkout, adapted-layout checks, and the onboarding
  playtest passed. The package script itself did not produce one all-stage
  `PASS`: its first wheel install hit sandbox DNS denial, and the direct
  verification command could not write receipts into the read-only external
  checkout. Those stages were resumed with dependency-network access and a
  writable copy; the failed combined receipt remains under ignored
  `build/ci/run-ur6jcsbc/`. Separately, six targeted exact-version native
  connector/component peer-pin pytest items passed on the digest-pinned KiCad
  10.0.0 and 10.0.5 images, including the connector alias and cross-symbol
  component fault/control cases. These local results do not replace hosted
  acceptance for a tagged source.
- **Cohort input:** The public
  [kicad-happy v2.2.1 changelog](https://github.com/aklofas/kicad-happy/blob/v2.2.1/CHANGELOG.md)
  describes a `checks_run` manifest with run/skip reasons and examined counts,
  plus explicit diagnostics where connectivity-graph construction fails or
  conditional DRC rules are skipped. The pure cross-analysis function was
  exercised against synthetic empty inputs at the pinned commit; its ten-entry
  manifest and exact results are recorded under LINT-031. The run confirms
  deterministic skip observability, with no nonzero item counts or findings.
  This is not a proposal to adopt its analyzer or its data model.
- **Problem:** Before v1, the report contained no machine-readable distinction
  between an absent optional USB data-path, series power-path, or power-sequence
  map and a configured map that matched. Other geometry and contract lanes
  already had dedicated coverage models, and ordinary heuristic scanners are
  invoked together through the shared candidate pass.
- **Evidence and check:** Each `mapped_check_runs` entry records the exact rule
  ID, effective mode, state (`NOT_CONFIGURED`, `EVALUATED`, or `BLOCKED`), map
  digest, native-netlist digest, authored item count, emitted finding count,
  and a reason when no map was supplied or source evidence blocks evaluation.
  USB count is the number of mapped interfaces; power-path count is the number
  of paths; power-sequence count is stages plus dependencies. Existing report
  findings remain the detailed mismatch evidence.
- **Boundary:** `EVALUATED` means the typed map comparison ran over the authored
  entries; it does not establish that the requirement is correct, complete,
  electrically appropriate, or equivalent to ERC/DRC. `NOT_CONFIGURED` is
  optional-map state, not a requirement gap. Counts do not claim coverage of
  off-board circuitry. The current slice does not claim a global execution
  ledger for every active rule.
- **Fixtures:** `tests/test_usb_data_paths.py` and
  `tests/test_usb_data_path_reference_bonds.py`,
  `tests/test_power_paths.py`, and `tests/test_power_sequences.py` cover missing
  maps, matching controls, mapped faults, off-mode findings, exact map and
  netlist hashes, and a configured power map without a netlist digest.
  `tests/test_usb_peer_reference_review.py` covers USB coverage states and count
  dispositions, including incomplete, DNP, and unsupported-path controls; the
  input-order and cross-process hash-seed regressions compare the full report.
  Its CLI/MCP parity case compares the same source-bound coverage report.
  `tests/test_connector_peer_pin_coverage.py` covers common-net controls,
  split meaningful returns, two-peer and three-peer open-pin controls,
  incomplete pin inventory, mismatched same-symbol inventories, and an all-DNP
  candidate set. The existing connector CLI/MCP case compares
  the full `DesignLintReport`, including this coverage section. The three-process
  Python hash-seed regression also asserts that the connector peer fault and
  common control retain evaluated, netlist-bound counts across runs. The exact-
  version KiCad 10.0.0/10.0.5 connector fixture lane also asserts the native fault and
  common-control coverage states, counts, finding totals, and netlist hashes
  for both two-peer and three-peer groups, and records those summaries in its
  hosted receipt.
  A local KiCad 10.0.6 compatibility replay (2026-10-08 UTC) of the synthetic
  native exports produced raw netlist hashes
  `6a3d3499390a99cff28dc81e1b4b7c326510d74bebba9308e473b2dd1feb70b6`
  (three-peer fault),
  `ef15956f3023f2b23e27f57343bf50580917f8a15b2197aa7fa48ba409839900`
  (three-peer control),
  `058dfe318e503e6ac872b05415ab66347befd7d735a9831f05e79dbff9fff345`
  (two-peer open contact),
  `d9bb4e9728b34c4dd7b19a0d1b5ca70f937fcc279342c5f02485b3aeb68c2abc`
  (two-peer explicit no-connect marker), and
  `d9c4af9d8d127b301a44db42d6eef7f635f473d3ae28c87f60b26c071caf8e61`
  (two-peer common-net control). All reports were `EVALUATED` and source-hash
  bound; open and marked-open faults each counted one peer-pin outlier, and
  common controls counted none. The exact pinned KiCad 10.0.0/10.0.5 hosted
  results remain necessary.
  Existing parity cases compare the full report for each configured map family.
- **Audit result:** `DesignLintPolicy` maps for STM32 pin assignment, I2C
  addresses, external protection, crystal networks, regulator feedback, RC
  filters, connector-return distribution, and the six PCB geometry families
  have dedicated typed coverage reports. Connector inventory, control-input
  bias, I2C pull-up hints, and per-rule schematic geometry also expose their
  coverage state. Component-role-map validation issues are included in the
  report and block use of an invalid map; absence of this optional enrichment
  does not disable the shared candidate pass. SPI, serial-peer, USB-C, and
  digital-peer voltage requirements are represented in the electrical
  analysis contract, whose pending sections and check rows distinguish
  `NOT_CONFIGURED`, `NOT_APPLICABLE`, and evaluated results. This was a
  source-level audit of the current services, corroborated by their existing
  typed-service and CLI/MCP parity tests; it is not a claim that every
  engineering requirement is present or correct.
- **Aggregate-status clarity (2026-10-03):** Replaying the public template
  showed three examples with passing source-scope, toolchain, ERC, DRC, netlist,
  and source-unchanged checks, while each aggregate summary was `FAIL` only
  because its design-lint gate returned `REVIEW` for undeclared connector
  inventory. `native_status` continues to carry the aggregate summary status.
  Text reports and follow-up guidance now name it as the validation-summary
  status and direct reviewers to the per-check results. This keeps gate status
  distinct from the status of individual native commands; it does not weaken
  evidence acceptance.
- **Next:** Reopen only when a new enabled check family lacks an observable
  outcome or a fixture demonstrates that a configured check can be skipped
  silently. Connector peer-pin coverage closes the identified gap without
  creating a global status registry. Any further status must bind to actual
  service execution.

#### LINT-077 — Source-bound per-contact connector current-rating contract

- **Status:** Implemented in the shared electrical service with typed project
  requirements, CLI/MCP pass/fault parity, and retained-evidence replay. A
  synthetic native schematic and exact-version KiCad 10.0.0/10.0.5 acceptance
  lane passed locally on 2026-10-03. Tagged hosted acceptance for this branch
  revision passed in GitHub run `38143123091` (`v0.5.0rc84`, commit `03e3ad0`)
  with the native rating fixture enabled. No project contract opts into the
  check.
- **Priority:** P0 acceptance coverage for connector-interface ratings. The
  local pinned native evidence is complete; keep the lane in GitHub CI and
  require owner-reviewed source data before project adoption.
- **Cohort input:** kicad-happy v2.2.1 documents CC-001 as connector current
  capacity compared with PCB trace width. We narrowed this to the independently
  authored per-contact rating comparison; trace ampacity is deferred because
  it needs reviewed stack-up, temperature, topology, via/zone, and current
  allocation inputs. No candidate source code, runtime, threshold, or data is
  included.
- **Problem:** ERC and net connectivity do not compare expected current on an
  individual connector contact with that exact contact's rated and reviewed
  derated current. Similar net names and connector symmetry cannot establish
  contact load sharing or current capacity.
- **Contract:** `connector_contact_ratings` binds the exact connector
  reference, symbol, footprint, `PART_ID`, complete native pin inventory, and
  each included contact's pin number, native function, and expected net. The
  owner supplies sourced rated current and conditions, derated allowable
  current, maximum current on that contact, derivation bases, and the accepted
  utilization fraction. Identity or assignment mismatch fails and suppresses
  the numeric comparison as `NOT_APPLICABLE`. Each contact is evaluated
  independently; current is never apportioned across common-net pins.
- **Boundary:** The tooling does not validate datasheets, derive load or
  derating, infer that connector contacts share current, calculate copper or
  cable ampacity, or establish physical contact/copper continuity or
  temperature rise. This remains an owner-authored numeric contract, not a
  general connector heuristic or fabrication approval.
- **Fixtures:** Synthetic tests cover inclusive utilization equality,
  over-limit load, independent loads on contacts sharing a net, wrong symbol,
  footprint, `PART_ID`, inventory, pin function/net, unconnected/DNP/absent
  connectors, invalid derating, authored requirement order, native XML parsing,
  CLI/MCP parity, and retained-evidence replay that rejects omitted check rows. The
  authored-order case reorders multiple connector and contact requirements,
  confirms semantic check rows stay identical while serialized contract data
  changes, and changes one peer contact's current to prove only that
  utilization result changes. The native-map case independently reorders
  exported component, pin-function, and net maps.
  exact-version fixture source and run procedure are in
  `tests/fixtures/design_lint/component-voltage-ratings/README.md`.
- **Native evidence (2026-10-03):**
  `test_component_and_connector_rating_controls_export_repeatably` passed with
  digest-pinned images: KiCad 10.0.0
  `sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3`
  and KiCad 10.0.5
  `sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`.
  The contact source hash is
  `a210495b6df2c7f43ca4d44361c6be6f022d31116dbd4efa200c76faf03f3182`.
  Repeated exports in both versions produce normalized netlist hash
  `a61bc6c086e4abb5a3af84ddceae10f845a314c2f742cc450b1ed19c7f2419f1` and
  normalized ERC hash
  `dbcb2273e067531c5e027ac9482ccf7ede0b4e2f7bd3ac01ad83b25510664338`;
  native ERC errors are absent. The synthetic contact requirement passes at
  1.60 A and fails at 1.61 A in both versions. Raw XML hashes differ between
  KiCad versions; repeatability is measured over normalized typed netlists and
  ERC evidence. The local exact-version rerun on 2026-10-08 also passed against
  both digest-pinned images. The 2026-10-11 hosted run selected
  `design_lint and connector_lint` with
  `KICAD_RUN_NATIVE_COMPONENT_RATING_FIXTURES=1`; its unit stage reported 288
  passed, 15 skipped, and 2,387 deselected. The native fixture test asserts
  repeated exports, normalized netlist/ERC agreement, no ERC errors, and the
  1.60 A control / 1.61 A over-limit fault on the digest-pinned KiCad 10.0.0
  and 10.0.5 images.
- **Next:** Keep this lane enabled in GitHub CI. Before adopting the check on a
  project, independently review exact connector identity, contact ratings,
  environmental derating, and the maximum current assigned to each contact.
  Do not infer current sharing across common-net contacts.

#### LINT-078 — Empty native netlist cannot count as lint evidence

- **Status:** Implemented v1 in the shared contract-coach evidence reader.
  Source-bound contract coaching and design lint now return `BLOCKED` when a
  native netlist has no component records, even when KiCad returned success
  and the artifact hash matches. CLI and MCP use the same check.
- **Priority:** P0 evidence integrity. An empty export removes every
  netlist-based heuristic from consideration, so it must not become a
  `READY_FOR_REVIEW` inventory or an ordinary lint report.
- **Trigger (2026-10-03):** The pinned KiCad 10.0.5 CLI returned exit code 0
  when asked to export the legacy Eeschema source in the public
  [`tclarke/kicad-mikroBUS` repository](https://github.com/tclarke/kicad-mikroBUS),
  at commit `8d8c5699d4aee83d41cb7d3adc2d33b67bf45f7e`, path
  `examples/stm32-mikroBUS`. Its output contained no components, library parts,
  or nets. The run used this digest-pinned KiCad 10.0.5 image:

  ```text
  ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c
  ```

  the input schematic SHA-256 was
  `c37c866924fa316ae3ed194585bb457e696e8d090674c0ddbbf70452ca003b3c` and
  empty netlist SHA-256 was
  `04792857f1bad06326a7c8a30c46e1de89c7a17881cd3756e8eadbbffc213715`.
  The CLI upgrade command also failed on the legacy file's first character.
  This project is therefore not counted as a lint precision trial: the
  tooling's native project path expects modern `.kicad_sch` sources. No project
  source was copied into Tooling.
- **Evidence:** The existing native-validation contract already rejects an
  empty component inventory. The source-bound contract-coach reader could
  still accept a hash-correct empty export when the separate authored-contract
  check had failed with return code 0, and design lint consumes that reader.
  The new guard closes this path. Synthetic regressions cover the direct
  report, design-lint CLI/MCP parity, and the existing valid nonempty export.
- **Native trigger fixture (2026-10-03):** The tooling-owned blank schematic
  `tests/fixtures/design_lint/empty-native-netlist/empty.kicad_sch` exported
  successfully with zero components and zero nets on the exact project-pinned
  KiCad 10.0.0 and 10.0.5 images. Both versions produced the same normalized
  typed-netlist digest, `d893aaecc8176cc3016d7d1505d75f98bd7cb06a7cf95aae77884264f83531d1`;
  repeated raw XML can differ because of export metadata. A synthetic
  two-component control produced the same normalized typed-netlist digest,
  `08650946c2dfeb42dda98b16e7ba9b37b934fdd310e6fb70e9801cfec08fef7d`, on
  both versions. The blank-source SHA-256 is
  `ed107ec68043c2eb02fa6566b289b35f119b37c3296bbd1a0f12705ba36b2c9b`; the
  control source SHA-256 is
  `7d086f4f838504fa3cefc906f7f9e415240b10d89e95c9063c19780922915f16`.
  The native lane is enabled in package GitHub CI and retains receipts only
  under ignored `build/`. Unit and CLI/MCP parity tests independently confirm
  that a successful, hash-correct empty export is blocked by the shared
  source-bound evidence reader. See the
  [empty-netlist fixture notes](../tests/fixtures/design_lint/empty-native-netlist/README.md).
- **Predicate:** For schematic-backed `pcb` and `schematic` projects, parse
  the exact retained native XML and require at least one component record
  before classifying the source as reviewable. Nets may be absent for a
  disconnected symbol; component inventory may not be entirely absent.
- **Boundary:** A nonempty export does not prove that every source symbol or
  net was exported. An independently authored component/net contract remains
  the comparison that detects partial exports; open or incomplete project
  requirements remain review gaps.
- **Next:** Keep the guard in the shared typed service and parity suite. When
  source-to-netlist completeness gains additional native evidence, extend the
  contract comparison rather than treating any nonempty export as complete.

#### LINT-079 — Source-matched connector roles refine generic pin heuristics

- **Status:** Implemented for returns and extended on 2026-10-04 for mapped
  supply contacts. A complete connector coverage entry with a catalog digest
  and exact matches for the current symbol pin inventory, native pin functions,
  and net assignments can supply a role where native pin text is absent,
  generic (`Pin_N`), or numeric-only. Return roles already surfaced split and
  missing return candidates. The supply extension compares generic or
  numeric-only contacts across connector symbols only when their exact
  project-authored `voltage_domain` values match. The focused connector,
  design-lint, rule-catalog, fixture-orchestration, and reviewed
  custom-connector CLI/MCP parity suites passed on 2026-10-07: 574 tests and
  683 subtests. Existing pinned native fixtures have recorded actual exports
  on KiCad 10.0.0 and 10.0.5. The current exact-version lane was rerun locally
  on 2026-10-08 and passed on both versions. Numeric-only pin functions with
  neutral net labels still surfaced the mismatch, and the common-net control
  cleared it. Hosted tagged acceptance passed in GitHub run `38143923818`
  (`v0.5.0rc86`, commit `2155056`) on 2026-10-11. Its unit stage selected
  `design_lint and connector_lint` with
  `KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1`: 293 passed, 10 skipped, 2,387
  deselected, and 10 subtests passed. The connector native lane recorded 59
  passing fixture stages for each digest-pinned KiCad 10.0.0 and 10.0.5
  project, including mapped return/supply role cases and the four-DB9
  split-return fault/common-return control.
- **Priority:** P0 connector coverage. A connector library may leave an
  interface contact generic or number-only, hiding the return or supply role
  from native-function heuristics. The reviewed interface catalog is already
  project-owned, so the lint can use it without inferring electrical intent
  from net names or connector similarity.
- **Predicate:** Use roles only from complete, current, digest-bound interface
  entries whose mapped component pin numbers, native function text, and
  assigned nets match the current netlist. A mapped return role refines
  `connector.repeated_pin_function` and `connector.no_connected_return`; mapped
  return or supply roles refine their unconnected-pin findings. A mapped
  supply role can also group different or missing assignments across connector
  symbols only when every grouped contact has the exact same authored
  `voltage_domain`. Stale, incomplete, digestless, or source-mismatched entries
  supply no roles.
- **Boundary:** A role and matching voltage domain classify candidate contacts;
  they do not mean that supplies must share a net or that independent,
  switched, ORed, or isolated sources are invalid. Return roles likewise do
  not determine common, bonded, or isolated grounding. Project-authored
  `pin_connectivity` and `grounding` requirements remain the only authority for
  those decisions. Findings default to `REVIEW` and follow existing
  per-project mode and exact-ignore behavior.
- **Fixtures:** `tests/test_connector_return_role_coverage.py` contrasts mapped generic
  return roles across USB and serial symbols, a common-net control, open mapped
  return/supply contacts, digestless coverage, and stale net assignments. The
  new synthetic pair uses generic `Pin_1`/`Pin_9` supply contacts on different
  custom connector symbols and neutral split-net names. Native-only lint is
  quiet; a complete map adds one review finding for a shared authored domain.
  A common-net control and a distinct-domain split control stay clear. The
  `tests/test_connector_supply_peer_coverage.py` also covers mapped generic
  supply peers. The same two-connector fixture now leaves the mapped J2 supply contact open:
  coverage stays `COMPLETE`, one REVIEW finding carries the empty assignment,
  and no duplicate unconnected-pin warning is emitted. The common-net control
  passes; the open-pin prompt still does not require a shared rail. The
  three-peer extension uses three connector symbols and numeric/generic power
  pin functions: two mapped contacts agree on one rail while the third differs.
  It reports one localized REVIEW finding for a shared authored voltage domain;
  an all-common control and a distinct-domain control pass. This additional
  case is synthetic typed-netlist evidence, not another native export.
  The report names each native function, project catalog role, and voltage domain;
  it states that this classification does not require commonality.
  `tests/test_design_lint_mcp_parity_peer_pins.py` now exercises three custom connector peers with
  generic returns and supplies through CLI and MCP: two agree on each net and
  one differs, while the all-common control clears both prompts. Removing the
  reviewed maps suppresses these custom-role candidates. The full typed reports
  match across surfaces. A more specific role-aware finding suppresses an
  overlapping lower-confidence peer-pin warning when it covers the same
  contacts. A separate two-peer regression covers the no-majority divergence
  case using synthetic typed-netlist evidence; it adds no native-export claim.
  A three-peer partial-map control leaves the generic outlier visible when the
  role comparison covers J1/J2 but J3 remains undeclared, preserving the full
  peer assignment set for reviewer inspection.
  `NativeConnectorReturnFixtureTests` exercises
  numeric-only pin functions and neutral net names through digest-pinned KiCad
  10.0.0 and 10.0.5
  native exports, with split and common-return controls.
- **Next:** Keep role-based grouping limited to return and supply, and retain
  these digest-pinned native cases in GitHub CI. Evaluate signal or shield
  grouping only when a separate synthetic fault/control pair demonstrates
  incremental value and includes isolated or independent-domain controls.

#### LINT-054 — Metamorphic stability coverage for deterministic rules

- **Status:** Baseline complete for all 155 active rules; CI requires every new
  active rule to add metamorphic fixtures or a reasoned not-applicable basis.
  The package catalog tracks `metamorphic_status`
  (`unreviewed`, `covered`, or `not_applicable`), registered
  `metamorphic_fixtures`, and a required basis for a not-applicable decision.
  This additive catalog change advances its schema to version 2 while report
  readers continue accepting version 1 as unreviewed. Catalog validation
  resolves and runs registered cases; the catalog suite rejects an unreviewed
  active rule and keeps the backlog inventory synchronized. Current catalog
  audit: 155 covered, 0 not applicable, 0 unreviewed. The connector-peer
  hash-seed regression is linked to the named-complementary-pair rule it also
  asserts, so catalog metadata covers every finding checked by that report.
  Control-input metamorphic coverage now relabels both nets, reverses net and
  pin-map order, and reverses capacitor pin inventory order; the recognized
  BOOT/switch-capacitor topology stays quiet, while its unproven same-device
  control retains the same review finding. The comparison uses rule and subject
  identity, not source-bound evidence that must change with the input.
- **Cohort input:** The public
  [kicad-happy-testharness methodology](https://github.com/aklofas/kicad-happy-testharness/blob/main/methodology.md)
  distinguishes baseline consistency from correctness and describes synthetic
  fault fixtures, a small reviewed gold tier, parser checks, and metamorphic
  tests. The methodology review is recorded under LINT-031; no corpus or
  candidate implementation was copied.
- **Problem:** A rule can pass one fault/control pair yet still depend on
  irrelevant input order, or fail to change when its causal input changes.
  Current catalog coverage names faults and valid controls but does not record
  these invariance and covariance properties systematically.
- **Work:** For every active rule, name at least one transformation whose
  semantic finding must stay the same and one causal mutation whose expected
  finding must change. Compare only rule-relevant semantic fields in these
  tests; source hashes, raw native receipts, and other provenance remain
  different when the source bytes change and must not be normalized in actual
  reports. Record unsupported transformations as explicit limits.
- **Boundary:** These tests establish behavior only for the authored synthetic
  transformations. They do not provide a gold answer for arbitrary boards,
  measure field false-positive rates, or establish electrical correctness.
  Public-project corpora and seeded analyzer outputs are not independent truth
  by themselves and are not imported as fixtures.
- **Initial coverage:** The CubeMX parser's conflicting alternate-function
  suffix keys are tested in both line orders and must block coverage. A valid
  `.ioc` pin-assignment reorder must preserve coverage and mismatches while
  changing the retained source hash. Connector-return distribution now also
  checks both that reversing net and pin-map insertion order preserves the
  finding and computed ratio, and that changing from the exact 3.0 ratio
  boundary to 4.0 changes the rule result. The four-connector numbered-return
  fixture also preserves evidence and fingerprint under mapping-order changes;
  replacing numbered sibling nets with one common return removes that naming
  hint. The exact-symbol peer connector outlier also preserves its localized
  open-pin finding under mapping-order changes; connecting the missing contact
  to its peers clears that candidate. The two-peer divergence prompt has the
  same order and agreement controls. Named connector VCC/GND open-pin findings
  preserve evidence under mapping-order changes; assigning those pins clears
  the matching findings independently. The broad multiconductor missing-return
  prompt also preserves its evidence under net/component/pin-function map
  reordering, and adding a recognized connected return pin clears it; existing
  controls keep return-like labels contextual and exclude shield and small
  connectors from the broad rule. The crystal-load, regulator-feedback, and
  RC-corner findings preserve their evidence under native-netlist map
  reordering and clear when corrected component values restore the authored
  target ranges. The I2C unmapped-responder prompt remains stable under native
  netlist map reordering and clears when the responder is added to the authored
  map; the strapped-address mismatch likewise remains stable and clears when
  the native strap assignment matches the mapped address. The SPI missing-roster
  prompt preserves its finding under netlist map reordering, retains the exact
  roster hash, and clears when the omitted device is added to the authored map.
  The missing-IC-decoupling prompt and direct LED rail-bridge finding also
  remain stable under netlist map reordering; adding a fitted capacitor or a
  series LED resistor clears the corresponding candidate. The USB-C
  unreviewed-port prompt preserves its source-hashed role-map evidence under
  netlist map reordering and clears when the project map lists that connector.
  A missing complementary signal assignment preserves its evidence under
  netlist map reordering and clears when the counterpart pin receives a distinct
  net assignment. The named complementary-net prompt likewise preserves its
  finding under netlist-map reordering; an exact project-authored pair map
  suppresses only that naming prompt. Its map digest remains in `BLOCKED`
  coverage until source-bound native DRC evidence is available and in
  `DISABLED` coverage when that check is explicitly turned off. For native
  differential-pair coverage, reversing native rule order and authored pair-map
  requirement order preserves semantic coverage entries while both raw input
  SHA-256 digests change; changing an authored width bound produces a
  `MISMATCH`. Mapped track-width findings are also stable when native track
  observations are reordered; the snapshot digest changes, while moving the
  narrow track to the authored boundary clears the finding. The mapped
  decoupling distance finding preserves its evidence when native pad inventory
  and connected-pad order are reversed; its snapshot digest changes, and moving
  the nearest eligible capacitor to the exact authored threshold clears the
  prompt. Switching-loop area and route findings are stable under pad and
  track-inventory reordering while snapshot digests change; returning native
  pad centers within the authored area limit clears the area finding, and
  measured via-connected route order remains exact. The unmarked orthogonal
  crossing retains its exact review candidate when the two wire records are
  reordered, while its source hash changes; adding a junction marker at the
  crossing clears the hint. The near-pin wire-endpoint hint preserves the pin
  identity and 0.5 mm distance across all supported rotations and mirrors while
  changed transforms produce changed source hashes; moving the endpoint beyond
  the authored search radius clears that candidate. The pin-line endpoint hint
  preserves pin identity and measured distances across supported symbol
  transforms and reversed segment ordering; shifting the wire 0.01 mm off the
  pin axis clears that candidate. The pin-tip-on-wire hint
  preserves pin identity and zero separation across all supported symbol
  transforms and reversed segment order; moving the wire 0.01 mm off the pin
  tip clears that candidate. The unmarked T-junction keeps the same endpoint
  and interior wire identities when source wire records are reordered; adding
  a junction marker at that contact clears the candidate. The label-endpoint
  hint preserves label/wire identities and distance under a joint translation;
  attaching the label directly to the endpoint clears the hint. The coincident
  text-anchor pair retains both text identities under joint translation, while
  separating one anchor clears the pair. The rendered-envelope overlap retains
  the same text pair and translated overlap box under joint translation; moving
  one label clear of the other removes the overlap finding. The wire/text
  crossing retains object identities and overlap length under joint translation;
  moving the wire clear of the text removes the graphical candidate. The text
  over symbol-body finding is stable when its root object is reordered, while
  moving the text away from the body clears the graphical candidate.
  Repeated numeric DB9 pin-function text on four exact-symbol connector peers
  also preserves the localized pin findings when separate return nets are
  renamed to neutral `NET_n` labels; the numbered-return name hint disappears,
  and the all-common pin control clears the repeated-pin finding. Numbered
  positive rails and unnumbered
  return-like labels preserve their findings under input reordering;
  merging or removing sibling labels clears their respective name hints. Next
  source-matched generic supply-role grouping preserves its REVIEW evidence
  and fingerprint under native net, symbol, pin-number, and function mapping
  reordering while the retained netlist digest changes. Putting both contacts
  on one net or assigning distinct authored voltage domains clears that
  candidate. The I2C duplicate-address check preserves collision evidence under responder
  and netlist ordering changes; separating the project-mapped bus segments
  clears that collision. The PHY-specific USB path finding is also stable under
  netlist mapping order, and restoring its mapped series resistor clears the
  diagnosis. The repeated same-function supply-pin finding preserves evidence
  and fingerprint under netlist-map reordering; assigning both pins to one rail
  clears the candidate. Component open supply and return findings preserve
  their evidence and fingerprints under netlist-map reordering; assigning both
  named pins clears those findings. Reset/enable/boot candidates remain stable
  under input-map reordering, and assigning each open pin clears only its own
  finding. I²C, SPI chip-select, and USB-C CC open-pin findings also preserve
  evidence and fingerprints under map reordering; assigning a specific signal
  clears only that signal's candidate. CANH/CANL warnings have the same
  order-stability and one-pin-at-a-time clearing check. The I2C pull-up
  findings preserve evidence under net-map reordering; adding each pull-up
  narrows the missing-line evidence, and adding both clears it. The equivalent
  resistance finding is stable under component ordering and clears in-range.
  The CAN termination prompt is order-stable; fitting a direct 121 Ω resistor
  clears it, while marking that resistor DNP restores the same finding. The
  active-low SPI chip-select bias prompt is order-stable and clears when its
  mapped 10 kΩ pull-up path is fitted.
  Same-net resistor, capacitor, and inductor prompts preserve their evidence
  under component/net-map reordering; splitting each passive's pins clears
  only that part's finding. The exact `Switch:SW_SPST` same-net prompt follows
  the same insertion-order and causal-split axis; the distinct-net control
  stays quiet.
  External-protection findings retain their semantic evidence under net-map
  reordering while the synthetic source hashes change. An authored
  `not_required` decision clears the applicability prompt, and restoring the
  mapped protector net clears the mismatch prompt.
  The reviewed-return map case now permutes project interface IDs,
  catalog-record/pin ordering, review rows, and pin-map keys while preserving
  coverage, findings, evidence, and fingerprints for fixed source digests.
  A three-connector fault/control case now puts two USB ports and one serial
  port in separate authored peer groups: one split mapped return remains a
  REVIEW across all three connectors, commoning the returns clears it, and
  unrelated data pins stay outside the cross-group comparison.
  LINT-081 now adds an unrelated fitted resistor on separate rails to a
  two-diode fault. The native-netlist digest changes while both diode findings
  keep their evidence and fingerprints; an exact ignore for D1 persists and
  leaves D2 active. The four-port numbered-return fixture now uses a digest of
  each synthetic netlist; insertion-order changes and an unrelated fitted
  resistor change that digest while preserving the naming finding. Its exact
  ignore remains scoped to that finding. A separate exact ignore for one of
  the two peer-pin findings remains scoped as well; the other peer finding and
  numbered-return prompt stay open. The mapped power-path rule has the same
  isolation control: an unrelated resistor changes the netlist digest, while
  its exact map-scoped evidence and fingerprint remain stable; its exact
  ignore still applies.
  The mapped-check receipt retains the new netlist digest and unchanged
  requirement-map digest. The mapped power-sequence rule exercises the same
  source-scope invariant, including a changed netlist digest, stable map digest
  and finding fingerprint, and a still-applicable exact ignore. Further axes
  include unrelated-part changes for other evidence-scoped rules.
- **Done when:** Every active rule is assigned a documented metamorphic axis
  or a reasoned not-applicable decision; high-risk source-bound contracts have
  executable invariance and causal-mutation pairs in CI; and the catalog links
  those cases without weakening source hashes or CLI/MCP parity.

#### LINT-080 — Cross-process hash-seed determinism for lint reports

- **Status:** Implemented v78. The cross-process probe supports themed report
  selectors and retains the complete 203-report inventory gate. Fault/control
  and applicability reports cover
  synthetic DB9 returns, same-net two-pin diodes, fuses, and SPST switches,
  direct and parallel-resistor output-driven LED faults with a series-resistor
  control, generic peer-pin outliers, project-mapped connector returns, series
  power paths, power sequences, UART-label discovery, STM32 CubeMX pin maps,
  split and common supply/return assignments across distinct symbols with one
  matching component `PART_ID`,
  the multi-UART split-reference heuristic, SPI/UART voltage-domain review
  with exact-map controls, CAN peer asymmetry, mapped RS-485 split/common
  reference reports, a connector-only SPI/UART
  boundary control, coverage-sensitive connector peer finding suppression,
  generic and named component power-input peer faults and controls,
  generic component peer-pin all-open, mixed-open, and strict-majority
  assignment-outlier reports with valid controls,
  missing-metadata connector-peer split and common-assignment reports both
  with and without a case-insensitive matching `PART_ID`,
  mapped PCB decoupling boundary reports, and a cross-symbol mapped-supply
  open-contact case, plus the typed contact-rating boundary and over-limit
  checks, DB9 grounding and pin-connectivity requirements, multi-device
  MOSFET stress checks, source-mapped USB data-path fault and topology
  controls, synthetic PCB signal-path rule coverage, synthetic keepout
  restriction coverage, switching-loop route ambiguity reports, and
  source-mapped crystal, regulator-feedback, and RC-filter fault/control pairs,
  plus mapped PCB protection-path, track-width, RF antenna keepout, and
  differential-pair DRC rule-coverage pairs, plus synthetic open-control-input
  and source-bound schematic wire-crossing fault/control reports, plus
  source-bound synthetic PCB return-copper disconnect/control checks, a
  same-net split-plane fault/control pair, and a DNP net-tie fault against a
  fitted, explicitly bonded-return control, plus an unstitched front/back
  return-plane fault and through-via control. The v66 extension adds both
  schematic/PCB DNP mismatch directions and a fitted control to the three-
  process source-bound report comparison; the rule remains REVIEW. The v67
  extension adds schematic-only and board-only component-value mutations plus
  an exact-value control, with each source digest changing only on its side.
  The v68 extension adds schematic-side and PCB-side pad-net changes plus a
  matching control, preserving the exact source-side hash distinction.
  The v69 extension adds the opt-in generic connector all-open fault and
  assigned-contact control with exact synthetic netlist hashes.
  The v70 extension adds the spaced `0V PWM 1` through `0V PWM 4` split-return
  fault and common `0V PWM` control to the isolated-process report matrix.
  The v71 extension links every directly asserted lint rule to its
  process-level report test and guards those links in the catalog suite.
  The v72 extension adds every required theme marker to those shared report
  modules and guards the cross-theme marker sets. The `v0.5.1rc18` hosted
  selector exposed four missing marker declarations before the correction.
  The v73 extension keeps the marker and collection architecture tests inside
  the focused `catalog_lint` gate and documents rule/theme selectors for shared
  hash-seed reports.
  The v74 extension adds a source-bound fault/control pair for LINT-165 to the
  three-process comparison and selects it directly by report family. The v75
  extension adds matching `PART_ID` split/common reports with a case-only ID
  difference to that same three-process comparison. The v76 extension adds a
  source-bound schematic symbol-body pin-endpoint review candidate and a clear
  control to the three-process comparison. The v77 extension adds the
  two-USB/one-serial split-return fault and common-return control. Only the
  three mapped return pins produce the return REVIEW; the common-return control
  has no return-divergence finding. An independent D+/D- pair review remains
  visible in both reports. The distinction is stable across the same three
  isolated Python processes. The v78 extension adds an exact project-authored
  ignore for only that return finding; the independent pair review remains
  open across the same process matrix.
  The test
  runs the shared typed services in three isolated Python processes, verifies
  that their runtime hash secrets differ, and compares complete serialized
  design-lint reports plus typed contact-rating and grounding check results
  byte-for-byte.
- **Priority:** P0 determinism foundation. Input-reordering metamorphic tests
  exercise explicit mapping changes in one process; they do not detect all
  output instability caused by set iteration or process hash randomization.
- **Cohort input:** The public
  [kicad-happy v2.3.0 changelog][happy-changelog] records a three-seed
  determinism gate and fixes for hash-seed-dependent analyzer output. Its
  `SP-001` passive-short check overlaps local LINT-051, so this increment
  adopts the determinism test method only and adds no detector or dependency.
- **Evidence:** The pytest-style `tests/test_design_lint_determinism.py` launches
  `tests/hashseed_probe.py` through the active interpreter's isolated pytest
  module entry point with `PYTHONHASHSEED` unset, checks that each process has
  hash randomization enabled and a distinct hash marker, and compares full JSON
  reports for the four-port numeric-pin return fault/common-net control, the
  same-net diode fault/distinct-net control, generic peer-pin outlier fault and
  common-net control, and a project-mapped return-role split/common-net pair.
  It also compares three source-mapped generic-peer reports: a split assignment
  with J3 undeclared, the same split with complete role coverage, and a fully
  common supply/return control. The partial-map report must retain both the
  mapped-role finding and the generic outlier for J2.1 while J3 remains
  `UNDECLARED`; complete coverage suppresses only the overlapping generic
  warning, and the common control has no mismatch findings.
  Three additional reports exercise reviewed peer-assignment scope with three
  generic `Pin_1` signal contacts explicitly declared unlisted and pin 2 mapped
  as return: separate peer groups suppress generic signal comparison while
  retaining all three split-return contacts for review; one shared peer group
  reports both split returns and signal divergence; and a common signal and
  return control passes. These compare complete typed-service reports across
  independently randomized processes, including group and role evidence.
  Three USB data-path reports compare an absent mapped D+ series resistor with
  the valid series path and a valid direct integrated-PHY path. The missing
  resistor remains one `bus.usb_data_path_mismatch` finding with one evaluated
  requirement; both topology controls clear that rule. The direct-path report
  retains its unrelated STM32 CubeMX and physical differential-pair REVIEW
  findings, confirming the USB path map does not suppress independent review
  families.
  The RS-485 extension compares complete typed reports for a mapped
  three-endpoint split-reference case and its common-reference control. Both
  retain the same bus endpoints, pair roles, and A/B line nets. The fault maps
  and observes U2 on `GND_B`; the control maps and observes it on `GND_A`, so
  their exact authored-map digests and typed-netlist digests differ. The fault
  has one `bus.rs485_peer_reference_review` candidate group, while the control
  has none. Three independently randomized Python processes emitted identical
  report JSON for both cases. This verifies deterministic serialization and
  fixture behavior; it does not establish that the references should be
  common or model a netlist regression against one unchanged authored map.
  Hosted tagged acceptance passed in GitHub Actions run `38146346709`
  (`v0.5.0rc91`, commit `3310202`) with the `interface_lint` scope. The hosted
  gate exercised the focused lint and installed wheel against a separate
  project; Ubuntu, macOS, and Windows preview jobs also passed.
  A separate cross-symbol supply-role pair uses two exact, complete interface
  maps with the same authored `external-5v` voltage domain. The open-contact
  fault keeps `J2.5` with an empty net assignment in the REVIEW evidence and
  suppresses the overlapping generic open-pin warning; the common-net control
  passes. The mapped role and voltage domain make these contacts comparable
  for review, but do not require a shared rail.
  The LINT-077 pair compares the typed contact-rating checks at the inclusive
  authored utilization boundary (`1.6 A / 2.0 A = 0.8`, `PASS`) and just above
  it (`1.61 A / 2.0 A = 0.805`, `FAIL`). Both retain the same netlist digest;
  the changed authored load changes the requirement digest. The process probe
  compares these serialized typed check results with the design-lint reports;
  it does not invoke the complete electrical runner or create native evidence.
  The multi-device MOSFET pair uses the same synthetic Q1/Q2 typed netlist and
  changes only Q2's authored on-state drain-potential interval. The fault
  changes only `mosfet-stress/switch-q2/state-on/vds` from `PASS` to `FAIL`;
  Q1's checks remain `PASS`, and every check in the control passes. The netlist
  digest stays fixed while the requirement digest changes. These typed results
  are compared byte-for-byte across the three independently randomized worker
  processes; the test does not invoke native export or the full electrical
  runner.
  The LINT-063 matrix compares a direct output-to-LED candidate and a parallel
  resistor fault with a visible return-side series-resistor control. Both
  faults retain `component.led_directly_driven_from_output`; the series control
  clears that rule. Its full report remains `REVIEW` for the independent
  `net.return_labels_without_pin_roles` finding on the synthetic `LED_RETURN`
  and `GND` nets. This checks the typed topology distinction and complete-report
  stability across hash seeds, not resistor adequacy or physical behavior.
  The PCB decoupling pair compares a candidate 100,001 nm from the mapped IC
  supply pad against the exact 100,000 nm authored limit. The over-limit report
  remains `REVIEW` with `pcb.decoupling_proximity`; the boundary control is
  `PASS`. Both retain the same map digest, while their synthetic typed snapshot
  digests differ.
  The LINT-080 v28 extension compares complete serialized signal-path reports
  for a synthetic clock-rule limit changed from 20 mm to 19 mm and for the
  exact-rule control. The fault remains `REVIEW` with
  `pcb.signal_path_rule_coverage` and `INCOMPLETE` typed coverage; the control
  is `PASS` with `COMPLETE` coverage. A second pair compares a synthetic
  keepout snapshot missing its reviewed track prohibition with the exact
  keepout signature: the fault reports `pcb.keepout_intent_coverage` and
  `INCOMPLETE`, while the control is `PASS` and `COMPLETE`. Pytest-style
  scenario tests assert these fault/control outcomes. Both report pairs are
  included in the existing three-process complete-JSON hash-seed comparison.
  Their provenance fields are deterministic synthetic fixtures; these cases
  do not invoke native export or establish board-level evidence.
  The LINT-080 v29 extension compares a synthetic switching-loop trace with
  two possible track chains against a unique direct-chain control. The ambiguous
  route remains `INCOMPLETE` with an explicit multi-chain issue; the unique
  trace resolves to exactly 1,000,000 nm. The complete design-lint report
  remains `REVIEW` in both cases because component internals are intentionally
  unmeasured. Pytest tests assert both outcomes, and both full reports join the
  three-process JSON comparison to exercise graph traversal ordering.
  It also compares a project-mapped series power-path open-element fault and
  repaired control; the fault retains one `EVALUATED` authored requirement and
  one mismatch finding while the control passes. The power-sequence case
  compares an open-enable fault and repaired control; its fault retains an
  `EVALUATED` map with three stage/dependency requirements and one mismatch
  finding. The UART-label case compares an unmapped alternate-function MCU
  candidate (`REVIEW`, with `discovery_basis=net_label`) against an exact
  source-mapped MCU-to-header control that clears only
  `bus.serial_unmapped_peer`; its independent generic connector return-role
  review remains visible. Both complete reports carry their typed netlist
  digest, and the mapped control includes the authored map path and digest. The
  STM32 case changes one synthetic CubeMX signal assignment and compares it
  with the valid IOC control; both retain complete coverage and the same
  authored map hash, while the IOC source digest differs. The mismatch remains
  `REVIEW` and the control remains `PASS`.
  The connector-role mapped case hashes its typed netlist input, includes the
  interface catalog digest, and checks that the REVIEW evidence names each
  pin's role source. The power-path case checks the mapped run remains
  `EVALUATED` with one authored requirement and one mismatch finding. The test
  asserts each expected `REVIEW` rule and clean `PASS` controls where the
  report has no separate coverage gap; the serial-map control also asserts
  that its independent connector return-role review remains visible. The
  multi-UART pair asserts one localized `bus.serial_peer_reference_review`
  finding for the split J1/U1 reference and no such finding in the
  common-reference control; unrelated review findings remain in the complete
  reports as applicable. The SPI and UART voltage-domain cases each compare an
  unmapped `REVIEW` prompt with a complete exact-map control and assert
  suppression of the matching protocol-specific prompt. The CAN pair asserts
  that the divergent peers remain `REVIEW`, the common-pair control omits the
  finding, and each report's netlist digest changes with its typed input.
  The connector-only header report retains both SPI and UART coverage entries
  as `NO_SUPPORTED_ENDPOINTS`, with zero recognized endpoints, direct links,
  voltage comparisons, or candidate groups; neither direct-peer voltage rule
  appears in its findings. A separate
  `tests.test_design_lint_mcp_parity_spi` case loads the
  same header-only shape from retained synthetic native-netlist XML and asserts
  complete CLI/MCP report equality, preserving the same applicability counts
  and absence of peer-voltage findings.
  The DB9 requirement matrix serializes both `grounding_checks` and
  `pin_relationship_checks` for four combinations: split net assignments
  against common and isolated-domain requirements, plus common assignments
  against each requirement. Each result carries the typed-netlist digest and
  the relevant grounding or pin-connectivity requirement digest. For both
  services, split/common and common/isolated combinations fail, and the other
  two pass. A separate unconnected-pin check compares a component whose native
  pin inventory is absent with the same component carrying a complete
  inventory: missing evidence fails with the exact component name, while the
  complete, unconnected control passes. Both results bind their typed-netlist
  digest to the same requirement digest. The 2026-10-07 focused
  `DesignLintDeterminismTests`, `UsbDataPathTests`, and
  `DesignLintCatalogTests` run passed with 472 tests and 644 subtests in an
  isolated Python 3.11 environment. Its worker
  verified three distinct hash secrets and byte-identical serialized results.
  This is process determinism evidence; the separate pinned native lane remains
  the evidence for KiCad export behavior.
- **Boundary:** All cases use tooling-owned synthetic typed netlists or PCB
  snapshots and project-authored synthetic maps. This detects report instability across the
  listed fault/control and applicability cases; connector return, peer-pin,
  and USB data-path
  cases also have separate pinned native fixture coverage. The peer-scope
  extension's exact-version fixture lane is wired into GitHub CI; this record
  does not include a hosted run for the current revision. The serial reference case checks
  process stability for a heuristic already covered by synthetic native
  fixtures; it does not establish that separate UART references are wrong.
  The series-path case does not prove component conduction, and the sequence
  case does not prove hardware startup behavior. The STM32 map does not verify
  compiled or flashed firmware. UART-label discovery is a coverage prompt, not
  proof that a peer or connection is required; its map control does not
  establish PCB copper continuity. These cases do not prove electrical
  correctness, replace exact-version native exports, or establish that every
  active rule is process-deterministic. The SPI and UART voltage prompts are
  REVIEW clues based on exact typed pin and rail-label evidence; this hash-seed
  case does not measure their usefulness or false-positive rate on field
  designs. The PCB decoupling pair uses synthetic geometry records and adds no
  public-board or native PCB probe result. The mapped-supply case uses synthetic
  typed netlists and authored maps; it does not add a native-export result or
  prove that independent connector supplies are incorrect. The contact-rating
  pair tests the typed comparison function only; the separate exact-version
  native fixture lane remains the evidence for parsing current connector
  identity and assignments from KiCad exports. The MOSFET stress pair tests
  typed multi-device state calculations only; its separate pinned native lane
  remains evidence for parsing the synthetic MOSFET identity and pin map, not
  real-part suitability or process-level native export behavior.
  The LINT-080 v30 extension adds a pytest-style mapped reference-plane gap and
  a complete coverage control. The fault's synthetic zone hole leaves the
  straight-track centerline at exactly 4/5 coverage against a 9/10 authored
  threshold and emits `pcb.reference_plane_coverage`; the full-zone control
  measures 1/1 and stays quiet. Both complete source-bound typed reports join
  the three-process JSON comparison. These use synthetic typed geometry and do
  not invoke native export or establish board-level or physical evidence.
  The LINT-080 v31 extension compares unindexed `GNDA`/`GNDD` return-label
  candidates, numbered `GNDA1`/`GNDA2` candidates, and an explicit GND/RTN pin-
  function control across independent hash seeds. This covers the bounded
  one-letter GND suffix extension without treating similar names as a common
  net or changing review disposition. The v32 extension adds a synthetic
  24-pin library symbol to the three-process report probe. It verifies that all
  pin-function and electrical-type entries have their expected values and are
  serialized in key order. `read_netlist` now sorts pin numbers before
  building these maps; the change adds no lint rule or native KiCad result.
  The v33 extension adds complete fault/control reports for an open
  `power_out` pin across distinct native symbol identities that share a
  `PART_ID`, plus the connected control. It compares the emitted finding,
  peer-group coverage counts, source digest, and full JSON report across three
  independently randomized Python processes. This protects deterministic
  reporting for LINT-094's `PART_ID` comparison extension; it adds no new lint
  rule or native KiCad result. The focused isolated Python 3.11 pytest run
  passed 92 tests; four pinned-native fixture cases were skipped because they
  run in package acceptance. The v34 extension adds a split supply-and-return
  fault across distinct synthetic symbols with one shared `PART_ID`, plus a
  common-assignment control for LINT-070. It compares both complete typed
  reports, including role findings and peer identity evidence, byte-for-byte
  across the same three isolated processes. The focused
  `tests/test_design_lint_determinism.py` pytest run passed; no native export or
  electrical-intent claim is added. The v35 extension adds an exact-symbol
  ordinary signal-output open-pin fault and a fully assigned control. The
  three-process probe compares their complete reports and source-bound peer
  coverage; the fault retains one `component.peer_signal_output_unconnected`
  candidate and the control stays `PASS` with no findings. The focused
  determinism pytest passed; exact-version export remains covered by the
  separate native fixture lane. The v36 extension adds fault/control reports
  for cross-symbol, shared-`PART_ID` peer signal outputs, inputs, and
  bidirectional pins. Each fault has one open pin; each control assigns the
  pin to a separate net. The process probe checks complete reports and confirms
  that the source-bound coverage reports one `PART_ID` peer group, zero exact-
  symbol groups, and the expected candidate/finding counts across all three
  hash seeds. These cross-symbol cases are synthetic typed-netlist evidence;
  they do not add native-export or electrical-intent claims. The v37 extension
  adds LINT-094's three-peer duplicate-candidate case: two peers share an exact
  symbol, while a third alias shares their case-insensitive `PART_ID`. The open
  pin appears in both the exact-symbol and broader identity groups, yet the
  report keeps one finding and records one deduplicated candidate. A complete
  assignment control clears the finding. Full source-bound reports and group
  counts match across the three hash seeds; this adds no lint rule or native
  export result. The focused determinism pytest passed on 2026-10-09.
  The v38 extension adds source-bound reports for a mapped I2C resistor-array
  control and a single SDA-channel net-assignment fault. The control resolves
  the exact array coverage and suppresses only `bus.i2c_missing_pullup`; the
  fault leaves that prompt `OPEN`, while both reports preserve the independent
  `bus.i2c_unmapped_responder` coverage prompt. Each complete report binds the
  synthetic requirement and typed-netlist digests and is compared byte-for-byte
  across three independently randomized Python processes. The requirement
  builders now live in the shared I2C fixture module used by both focused and
  process-level tests. This is typed-netlist determinism evidence, not a new
  native export or an electrical-intent claim. The v39 extension also
  serializes `i2c_pullup_checks` for the same mapped-array pair, comparing
  source-bound typed check records and requirement/netlist digests across the
  three processes. The single SDA channel assignment fault fails only the SDA
  path check while SCL passes; both lines pass in the control. This exercises
  the exact authored contract layer as well as heuristic coverage, without
  changing the project requirement or adding a lint rule. The focused I2C,
  architecture, and cross-process pytest selection passed 45 tests and 7
  subtests on 2026-10-09; the full reports and typed checks matched across
  three distinct hash secrets. The v40 extension adds an authored I2C address-
  map fault where a strap change produces both an address mismatch and a
  same-segment collision, plus the distinct-address control. Each serialized
  case includes the full source-bound report, netlist digest, and the same
  address-map digest. The focused hash-seed interface and inventory tests
  passed on 2026-10-09; full fault and control reports matched across three
  distinct hash secrets. This extends deterministic coverage without adding a
  lint rule or native-export result. The v41 extension adds a mapped external-
  protection fault and repaired control. Both carry the same authored map
  digest; the fault has incomplete protection coverage and a mapped-device
  mismatch, while the repaired control has complete coverage and retains an
  independent named-pair review. Complete reports matched across three distinct
  hash secrets. The focused interface and inventory pytest run passed on
  2026-10-09; this adds no rule or native-export result.
  The v42 extension adds a mapped crystal load-network node fault and valid
  control. Both serialize the same authored crystal-map digest and distinct
  typed-netlist digests with the complete design-lint report. The fault remains
  `REVIEW` with incomplete mapped coverage and the crystal-network mismatch;
  the control has complete coverage and no findings. The full reports matched
  across three distinct hash secrets. The focused analog determinism and
  inventory pytest run passed two tests, and the crystal contract plus
  architecture suites passed 40 tests on 2026-10-09. This adds no lint rule,
  native-export result, or electrical-intent claim.
  The v43 extension adds mapped regulator-feedback divider-value and RC-filter
  cutoff fault/control pairs. Each pair carries one shared authored-map digest
  and distinct typed-netlist digests alongside complete design-lint reports.
  Both numeric faults remain `REVIEW` and identify their exact mapped rule;
  their topologies remain `COMPLETE` while the affected entries are
  `OUT_OF_RANGE`. The corrected controls are `PASS` with complete coverage and
  no findings. All reports matched across three distinct hash secrets. The
  focused determinism and crystal, regulator-feedback, and RC contract pytest
  run passed 49 tests and 9 subtests. `component_lint` selected the crystal/RC
  pair tests (2 passed); `power_lint` selected the regulator test (1 passed).
  The architecture and suite-size checks passed 25 tests on 2026-10-09. This
  adds no lint rule, native-export result, or electrical-intent claim.
  The v44 extension adds mapped PCB protection-entry distance and minimum
  track-width fault/control pairs. Each pair binds one authored-map digest and
  distinct synthetic board and snapshot digests in a complete typed report.
  The protection fault is one nanometer beyond its 100 µm limit and emits
  `pcb.protection_entry_path`; the exact-boundary control passes. The track
  fault is 250 µm against the authored 251 µm minimum and emits
  `pcb.minimum_track_width`; the 251 µm control passes. Track-width coverage
  remains `COMPLETE` while its measured track is below the requirement. Full
  reports matched across three distinct hash secrets. The focused PCB path,
  width, and report-inventory run passed 17 tests; `pcb_lint` selected both
  determinism cases (2 passed), and `return_path_lint` selected protection
  review (1 passed, 1 deselected). Architecture and suite-size checks passed
  25 tests on 2026-10-09. These synthetic measurements add no lint rule,
  native-export result, or electrical-intent claim.
  The v45 extension adds a mapped RF-module antenna-placement fault and exact
  keepout control. Each case carries the same authored-map and netlist digests,
  distinct synthetic board and snapshot digests, and the complete design-lint
  report. Moving the footprint by 100 nm on each coordinate while leaving its
  keepout in place yields `REVIEW`, incomplete antenna coverage, and
  `pcb.rf_module_antenna_keepout_coverage`; the aligned control has complete
  coverage and no findings. Full reports matched across three distinct hash
  secrets. The focused report-inventory, antenna, and determinism selection
  passed 24 tests; `pcb_lint` selected the new case (1 passed). Architecture
  and suite-size checks passed 25 tests on 2026-10-09. This adds no lint rule,
  native-export result, or electrical-intent claim.
  The v46 extension adds a mapped differential-pair native-rule coverage
  mismatch and exact control. The fault changes the native rule's gap maximum from
  0.50 mm to 0.45 mm; it reports `MISMATCH`, incomplete coverage, and
  `pcb.differential_pair_rule_coverage`. The exact-rule control has complete
  coverage and no findings. Both complete reports bind source, project, rules,
  board, netlist, and synthetic DRC-metadata hashes. Map, project, board, and
  netlist hashes match between cases; the rules and source-inventory hashes
  differ. Full reports matched across three distinct hash secrets. The focused
  DRC, determinism, and report inventory selection passed 16 tests; `pcb_lint` selected the new case
  (1 passed). Architecture and suite-size checks passed 25 tests on
  2026-10-09. DRC metadata is synthetic; this adds no native KiCad run, new
  lint rule, or electrical-intent claim. The v47 extension adds complete
  reports for the LINT-101 cross-symbol connector `PART_ID` alias open-contact
  fault, split-assignment fault, and fully assigned common-net control. The
  faults retain one localized outlier or divergence finding with eligible-
  group coverage; the control has complete pin assignments and no findings.
  All three reports are included in the three-process byte-for-byte comparison.
  This adds determinism coverage for both LINT-101 alias paths, not a lint rule,
  native export, or electrical-intent claim. The focused connector peer and
  report-inventory pytest run passed two tests on 2026-10-09; the shared probe
  verified three distinct hash secrets and identical full reports. The v48
  extension adds synthetic complete reports for nine disconnected reset,
  enable, and boot/strap input pins and their connected, visibly biased
  controls. Each report carries the digest of its typed netlist. The fault is
  `REVIEW` with nine `control.unconnected_control_input` findings; the control
  is `PASS` with no findings. Both reports matched byte-for-byte across three
  independently randomized Python processes. The focused report-inventory and
  control-input determinism tests passed two tests; the `power_lint` selector
  selected and passed the new case. Architecture and lint-suite size checks
  passed ten tests. This extends determinism evidence only; it adds no lint
  rule, native export, or electrical-intent claim. The v49 extension adds full
  source-bound schematic reports for an unmarked orthogonal-wire crossing and
  its explicit-junction control. Both use the same typed-netlist digest and
  scanner version field (`10.0.6`), with distinct schematic source digests.
  The crossing report has `COMPLETE` geometry coverage and one
  `schematic.unmarked_wire_crossing` finding at 127 mm; the junction control
  has `COMPLETE` coverage and no findings. The reports matched byte-for-byte
  across three independently randomized Python processes. The focused
  report-inventory and schematic determinism tests passed two tests; the
  `schematic_lint` selector and existing crossing policy regression each
  passed. Architecture and lint-suite size checks passed ten tests. This is
  synthetic source-scan and report-determinism evidence; it invokes no native
  KiCad export and adds no electrical-intent claim. The v50 test-runner
  extension assigns each themed determinism suite to one or more report
  families and lazily imports only their builders. The complete inventory
  still compares all 132 reports across three processes. Local Python 3.11
  runs completed the two-report schematic selector in 1.24 s and the
  interface selector in 1.78 s; the full inventory test took 2.85 s. All 16
  determinism tests passed together in 3.01 s. Architecture and suite-size
  checks passed ten tests. These are local slice timings,
  not a broad suite benchmark. The selector adds no lint predicate or native
  export. The v51 extension adds complete typed return-path checks for a
  disconnected synthetic DB9 return and a connected control. Both use the
  same independently authored requirement digest and include distinct board
  and connectivity-snapshot digests, the declared KiCad 10.0.5 version,
  synthetic image digest, probe-source digest, and ordered check rows. The
  fault fails only the exact return-connectivity check; every control row
  passes. The reports matched across three independently randomized Python
  processes. The focused return-path determinism selector passed, the complete
  inventory passed with 134 reports, the marked return-path suites passed 15
  tests, and architecture and suite-size checks passed 31 tests. This adds no
  lint rule, native KiCad export, or electrical-intent claim. The contract and
  copper-zone regressions now use separate marked pytest modules and shared
  minimal synthetic builders.
  The v52 extension adds a source-bound same-net copper-zone split fault and
  single-island control. Both share the same reviewed direct-return
  requirement, while board and connectivity-snapshot digests differ. The
  fault retains exact F.Cu island indexes 0 and 1 on separate components and
  fails the connectivity row; the connected control places both pads on the
  same filled island and passes all rows. The four-case return-path family
  matched across three independently randomized Python processes. The focused
  selector passed in 1.20 s. All 17 design-lint determinism tests, the 15
  marked return-path tests, and 31 architecture and suite-size tests passed
  together (63 tests); the catalog, fixture, and backlog checks passed 165
  tests and 108 subtests. This remains synthetic evidence and invokes no
  native KiCad export. The v53 extension adds an exact reviewed bonded-return
  topology with separate DGND_A and DGND_B endpoint nets and an NT1 net-tie
  footprint/pad-group requirement. Its fault marks NT1 and both observed tie
  pads DNP; the control retains the same authored requirement with the net tie
  fitted. The six-case return-path family matched across three independently
  randomized Python processes. The DNP case fails the exact bond and
  connectivity rows; the fitted case passes every row. This remains synthetic
  evidence and invokes no native KiCad export. The focused selector passed in
  1.20 s; the return-path, full determinism, architecture, suite-size, and
  catalog slice passed 73 tests in 4.05 s. The v54 extension covers separate
  same-net F.Cu and B.Cu return planes with exact per-pad zone-island
  observations. Its fault has no through via and reports disconnected copper
  groups; its control binds one fitted through via to both endpoint components
  and reports its exact synthetic identity, geometry, and F.Cu-to-B.Cu
  transition. Both retain the
  same direct-return requirement and distinct board/snapshot digests. The
  eight-case return-path family matched across three independently randomized
  Python processes; the fault fails connectivity and the control passes all
  rows. The complete inventory gate passed with 140 reports. This is synthetic
  evidence and invokes no native KiCad export. The v55 extension adds separate
  cross-process reports for a fitted schematic component absent from the PCB,
  a placed reference with a different exact footprint ID, and the matching
  footprint control. All three full reports matched across three randomized
  processes; the two faults remain `REVIEW` and the control passes. The focused
  PCB inventory selector and complete 151-report inventory test passed, and
  Ruff passed for the changed Python modules. These cases use synthetic typed
  snapshots and invoke no native export or electrical-intent check.
  The v56 test-support refactor moves the shared synthetic schematic, board,
  and coverage builders into `tests/design_lint_fixtures/pcb_component_inventory.py`.
  The focused inventory suite and cross-process probe now import the same
  theme-owned fixture service; the inventory test module shrank from 429 to
  341 lines. Its slow determinism module is registered in `tests/conftest.py`
  and has a focused selector in `tests/README.md`. This changes no rule or
  report behavior. The v58 extension adds a source-reference-drift report
  against one unchanged RS-485 map and includes the exact endpoint pin checks.
  Across three independently randomized Python processes, the complete report
  remains byte-stable; the unchanged map digest is retained, heuristic coverage
  stays `INCOMPLETE` without a split-reference candidate, and the exact U2.5
  contract check remains `FAIL`. Tag `v0.5.0rc93` passed scoped hosted
  acceptance in Actions run `38147931718`, including the installed-wheel check
  against a separate project checkout and Ubuntu, macOS, and Windows previews.
  The v59 extension adds three authored power-connectivity result sets from the
  shared typed check service: wrong source net, wrong load net, and a valid
  control. All three retain one identical requirement digest and distinct
  netlist digests. The source fault fails only its source-group check, the load
  fault fails only its load check, and the control passes both checks. Each
  complete serialized result matched across three independently randomized
  Python processes. This strengthens deterministic evidence for project-authored
  power-pin requirements; it adds no inferred wiring rule.
- The v60 extension adds eight complete synthetic fault/control reports for
  generic power-input assignment divergence, named power-input partial opens,
  named power-input assignment divergence, and named power-input pins left
  open on every comparable peer. The focused component-peer determinism suite
  compares each report and its source-bound coverage across three independently
  randomized Python processes. The complete inventory test exposed that its
  previous expected count was two reports behind the actual baseline; the
  pinned inventory is now 165 and both focused tests pass. This adds no lint
  rule, native export, or electrical-intent claim. Tagged acceptance for
  `v0.5.0rc190` passed on 2026-10-12 (GitHub Actions run `38303019793`), with
  the scoped unit gate and `KICAD_RUN_NATIVE_COMPONENT_PEER_POWER_INPUT_FIXTURES`
  enabled, installed-wheel verification against a separate public project
  checkout, and Ubuntu, macOS, and Windows previews. The package-publish job
  was skipped for this prerelease tag.
- The v61 extension adds six complete synthetic reports for generic component
  peer-pin heuristics: all peers open, some peers open, and a strict-majority
  assignment outlier, each with an explicitly connected control. The focused
  tests compare complete reports and source-bound candidate coverage across
  three independently randomized Python processes. Each rule catalog points
  to its own focused regression, while the rules remain opt-in review prompts
  whose peer comparisons do not prove a required pin connection. This adds no
  rule or project-derived fixture.
- The v62 extension adds a separate, focused hash-seed family for named
  connector power-input and power-output alias divergence. Each rule has a
  split-net fault and common-net control built through the shared synthetic
  alias fixture. Complete reports, exact finding evidence, and netlist digests
  are compared across three independently randomized Python processes. Both
  active rule catalogs link the new test as metamorphic coverage, so each
  `design_lint_rule` selector includes it. The report inventory grows from 171
  to 175. This strengthens deterministic regression evidence without adding a
  rule or asserting that the aliases must share a net.
- The v63 extension adds source-bound reports for the configured touch-pad to
  reference-copper clearance rule. It compares a 500 µm fault against the exact
  800 µm project minimum, with the same authored requirement and schematic
  netlist, across three independently randomized Python processes. The rule
  catalog links the regression as metamorphic coverage, and the complete report
  inventory grows from 175 to 177. This adds process-stability evidence only;
  it does not establish general applicability or electrical approval.
- The v64 extension adds source-bound reports for `pcb.required_fitted_reference`:
  a project-required component marked DNP in both source and board, plus a
  matching fitted control. The rule's blocking finding and full typed coverage
  are compared across three independently randomized Python processes. Its
  fault/control pair raises the complete report inventory from 177 to 179.
  This guards report stability for a project-authored fabrication requirement;
  it does not infer the required assembly list.
- The v65 extension adds an opt-in board-only footprint review candidate and a
  matched-inventory control. The candidate is an unmatched mounting-hole
  reference, explicitly kept at `REVIEW` because a board-only footprint may be
  intentional. Full source-bound reports are compared across three randomized
  Python processes; the inventory grows from 179 to 181. This tests report
  stability without classifying the footprint as a defect.
- Tagged acceptance for `v0.5.0rc191` passed on 2026-10-12 (GitHub Actions run
  `38305303770`). The scoped unit gate used the
  `component.generic_peer_pin_all_open` selector with
  `KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES` enabled. Installed-wheel
  verification against the separate project checkout and Ubuntu, macOS, and
  Windows previews also passed. The package job was skipped for this prerelease.
- **Next:** Extend the process-level determinism matrix to other high-risk
  source-bound report families when their complete synthetic fault/control
  reports can be serialized through the same shared service. Keep each
  extension separate from broad analyzer-corpus claims.

#### LINT-005 — Repeated component supply-pin net review

- **Status:** Implemented v1 as a review-only rule for repeated, recognized
  supply-function categories on one fitted non-connector component.
- **Problem:** An IC can have two pins with the same supply function assigned
  to distinct schematic nets while each pin is connected, so an unconnected
  pin check may not raise a question.
- **Evidence and check:** The KiCad 10 native XML netlist groups pins on one
  component by the existing recognized supply-function categories. It reports
  assigned pins when their exact schematic net assignments differ or one pin
  has ambiguous multiple assignments. An open member remains covered by the
  more specific unconnected component supply-pin rule. Findings use the
  existing project rule override and exact-ignore lifecycle.
- **Boundary:** This is a candidate for review, not an instruction to tie the
  pins. Separate nets can be intentional for a filtered supply or a
  datasheet-defined topology. Uncommon/unnamed functions and DNP components
  are outside v1; a schematic netlist cannot show a PCB ferrite or copper path.
- **Fixtures:** Same-function pins split across nets; same rail shared; distinct
  named supply functions on separate rails; explicitly DNP component; one
  unassigned member producing only the specific open-pin finding; exact
  fingerprinted ignore.
- **Done when:** Catalog, limitations, fault/control tests, deterministic
  report evidence, and project policy behavior remain in sync.

#### LINT-006 — Unnumbered return labels without explicit pin roles

- **Status:** Implemented as a review-only netlist candidate for multiple
  populated return-like nets whose attached symbol pin functions do not
  identify a return. It complements the numbered-return rule when connector
  pins have numeric or otherwise uninformative functions.
- **Problem:** Similar return domains can use distinct labels without numeric
  suffixes, so `net.numbered_returns` cannot surface them. Connector pin-role
  comparison may also lack a recognized pin function when the symbol exports
  numeric contact names.
- **Evidence and check:** The source-bound KiCad 10 native XML netlist supplies
  net names, pin membership, and exported pin-function text. If two or more
  populated return-like net labels not already covered by numbered-return
  groups attach only to pins without a recognized return function, the rule
  asks for review. Numbered-return groups are left to
  `net.numbered_returns`; explicitly named return pins are left to the
  connector pin-function rule. When those functions differ across connector
  nets, that separate rule keeps a review prompt; it does not require common
  returns. The bounded return vocabulary now accepts a
  one-letter suffix on `GND`, including `GNDA` and `GNDD`, which KiCad's
  [net-class example](https://docs.kicad.org/8.0/en/eeschema/eeschema.pdf)
  lists as a net matched by `GND*`. Matching names remain review-only and do
  not imply a common electrical domain. The bounded `RET` token is also
  recognized for both numbered and unnumbered candidate groups. TI's
  [UCC28630EVM-572 user guide](https://www.ti.com/lit/ug/sluuax9b/sluuax9b.pdf)
  labels an output return `RET`; this supports the spelling only. Synthetic
  `RET1`/`RET2`, `PORT1_RET`/`PORT2_RET`, and `RET_USB`/`RET_SERIAL` cases
  exercise review candidates, while common-`RET` and `RESET` controls protect
  the boundary. A focused CLI/MCP parity case exercises numbered and
  unindexed candidates plus a common-`RET` control using a tooling-owned
  synthetic project, so the check runs without the separate public template
  checkout. No source schematic was copied.
- **Boundary:** The recognized label and pin-function vocabularies are narrow.
  A return-like label token, including `RET`, is context only and does not
  prove that the label names a ground domain.
  Longer names such as `GNDAUDIO` do not match the one-letter suffix form.
  The rule does not infer that similarly named nets must connect, discover
  off-board grounds, or establish PCB copper or physical continuity. Separate
  analog, chassis, shield, isolated-interface, or other return domains may be
  intentional. Default disposition remains `review` with project override and
  exact-ignore support.
- **Fixtures:** Two unnumbered return-like nets on numeric pins and distinct
  connector symbols; explicit GND/RTN pin-function control; one return-like
  net; ordinary signal nets; explicit return functions split across connector
  symbols, reviewed by the peer-function rule; a numbered sibling pair alone and alongside an
  unnumbered pair; review/block/off/exact ignore and stale fingerprint; catalog
  reachability.
- **Done:** Synthetic fault/control cases, policy lifecycle, catalog entry,
  documentation, and shared CLI/MCP report path are covered. No board source is
  used.

#### LINT-069 — Project-authored roles for custom symbol identities

- **Status:** Implemented first slice: the `led` role extends
  `component.led_directly_driven_from_output`. LINT-091 adds an exact
  `capacitor` role used only by `power.ic_rail_without_fitted_capacitor`.
- **Evidence:** The public KiCad-Team-Workflow-Template training project at
  commit `ed89536f0dbbcb013145af2994fef41b2250143e` documents an Arduino status
  LED path through `R1` (1 kΩ) and custom symbol
  `StatusLedTraining:LED_5mm`. Its KiCad 10.0.5 native export shows the
  schematic series path, but LINT-063 emits no candidate because it recognizes only
  `Device:LED`. The overall project report remains `REVIEW` for undeclared
  connector inventory; this is an applicability gap, not a rule pass, fault,
  or false-positive measurement. Detailed source and netlist hashes are
  recorded under LINT-063. No project source was copied into Tooling.
- **Problem:** Some deterministic rules recognize narrow, standard symbol
  identities. A project may use an approved custom library symbol for the same
  reviewed component role, but the current mode/ignore policy cannot extend
  that rule's applicability. Guessing from `D` references, values, or
  footprint text would create unreviewed classifications.
- **Contract:** `design_lint.component_role_map` in the project test contract
  binds one exact `PART_ID`, native symbol ID, footprint, complete two-pin
  number/function/electrical-type inventory, finite role (`led` or
  `capacitor`), and review basis. Capacitor entries require both native pins
  to be passive. Every native component using that `PART_ID` must match the
  binding. An absent part or changed identity/pin inventory blocks lint and is
  excluded from the heuristic. The accepted map is covered by the existing
  source-bound policy digest; a finding includes the binding and its canonical
  SHA-256, so changing its identity or basis changes the finding fingerprint.
  Pin-order changes do not change the digest or finding.
- **Predicate:** The `led` role extends only the documented two-pin
  output-driven LED heuristic. The `capacitor` role is used only by the fitted
  decoupling-presence hint and requires two native passive pins. Both supply a
  reviewed component classification, not an electrical conclusion or net
  requirement. Unlisted custom symbols stay outside these rules regardless
  of reference, value, or footprint text.
- **Boundary:** A role map establishes project classification, not component
  correctness, part approval, pinout accuracy, fit, electrical limits, or
  fabricated connectivity. It does not change a finding's default `review`
  mode. It must be bound into the design-lint policy digest and finding
  evidence. Unknown symbol formats and multi-unit/ambiguous identities remain
  explicitly unsupported.
- **Fixtures and acceptance:** Synthetic custom-symbol direct-output fault and
  series-resistor control; same-value unrelated-symbol and unmapped-custom
  controls; DNP and stale part, symbol, footprint, and pin-inventory cases;
  map/pin ordering stability; identity/basis-bound digest; and CLI/MCP parity.
  The pinned native lane exports both custom schematics twice on KiCad 10.0.0
  and 10.0.5, checks the complete identity and pin data survived XML parsing,
  confirms the unmapped symbol stays quiet, and confirms the mapped fault and
  series control differ as expected. This is applicability gain, not
  independent electrical detection.
- **V1 complete:** The exact source contract, stale-map blocking, review-basis
  evidence, tests, shared-service parity, native exports, and documentation are
  in place. Additional component roles require their own bounded predicates,
  source fields, controls, and applicability evidence; do not enable arbitrary
  rule-role combinations.

#### LINT-131 — Pin-connectivity change review in design-lint reconciliation

- **Status:** Implemented as source-bound connectivity snapshots embedded in
  `DesignLintReport` and compared by the existing typed reconciliation service.
- **Priority:** P0 regression evidence. Before this change, reconciliation
  retained source and netlist hashes plus lint-finding transitions, but could
  not name which pins changed when a design edit altered connectivity without
  changing any current lint finding.
- **Evidence:** Each native report stores exact KiCad version, toolchain image,
  source hashes, netlist hash, every available symbol pin, its native net name,
  and the other pins on that net. Reconciliation lists added/removed pins and
  changed assignments in stable order. Complete inventories are required for
  `COMPLETE` coverage; incomplete inventories remain `PARTIAL`. Partial
  comparisons list assignment changes only for pins known on both sides; pin
  additions and removals require complete coverage. A baseline
  without a snapshot requires review, and different exact KiCad versions or
  toolchain images block comparison. The CLI and MCP use the same typed report
  and comparison service.
- **Boundary:** A pin change is evidence for review, not proof of a defect.
  Net-label changes also surface for review; the comparison does not decide
  whether a connection is required. Project-authored pin, return, supply, or
  interface contracts remain the authority for intent. A reviewed current
  report can be saved as the next project-owned baseline. No board source is
  stored here.
- **Fixtures:** Synthetic common-return baseline and split-return mutation;
  net-label change; incomplete pin inventory; ambiguous multi-net assignment
  without false pin-removal reports; known assignment changes under partial
  coverage; ready native-summary state missing its netlist digest;
  missing legacy snapshot; exact-toolchain mismatch; CLI/MCP parity. See
  `tests/test_design_lint_connectivity_reconciliation.py`.
- **Cohort input:** The Apache-2.0 [`heibench/netspec`](https://github.com/heibench/netspec)
  repository is pre-alpha and documents connectivity deltas and pin-swap
  review, including a polarized-capacitor reversal that native ERC does not
  distinguish. Local exact pin-to-net contracts already express reviewed
  polarity requirements, so this increment adopts only the baseline-diff idea;
  it adds no runtime dependency and imports no cohort code or board data.

#### LINT-132 — Pin-role metadata change review in design-lint reconciliation

- **Status:** Implemented as a versioned extension to the source-bound native
  connectivity snapshot and typed reconciliation report.
- **Priority:** P0 regression evidence. Net assignments can remain identical
  while a changed KiCad symbol function or electrical type changes the meaning
  of a pin and can alter which review heuristics recognize it.
- **Evidence:** Each current snapshot records the native function and
  electrical type for every inventoried pin when available. Reconciliation
  reports exact per-pin fields that changed, alongside the existing net and
  peer deltas. Complete metadata comparison requires complete pin inventory
  and a native electrical type for every pin. Partial snapshots compare a
  field only when both sides retain it; reports from before snapshot schema 2
  remain readable and expose partial or unavailable metadata comparison until
  the project records a current baseline. Different KiCad versions or
  toolchain images still block comparison. CLI and MCP share the same typed
  service and output model.
- **Boundary:** A function or electrical-type change is review evidence, not a
  defect verdict. It does not infer required wiring, polarity, or component
  behavior. Project-authored pin-connectivity and electrical contracts remain
  the source of intent.
- **Fixtures:** Same pin-to-net topology with a changed return function;
  unchanged topology with a changed native electrical type; stable mapping
  order; incomplete metadata with field-scoped comparisons; legacy schema-1
  baseline; exact-toolchain mismatch; and CLI/MCP output parity. Synthetic
  netlist inputs for mutation and adapter parity are documented in the
  [connectivity snapshot fixture README](../tests/fixtures/design_lint/connectivity-snapshot/README.md).
  The exact-version UART connector fixture lane also captures pin-role
  snapshots from repeated native KiCad 10.0.0 and 10.0.5 exports and checks
  complete, stable metadata.
- **Cohort input:** The Apache-2.0, pre-alpha
  [`heibench/netspec`](https://github.com/heibench/netspec) repository
  documents pin-swap and connectivity-delta review. This increment
  retains native pin metadata with the delta; no cohort code, board, or project
  data was imported.
- **Verification:** Focused reconciliation, architecture, and self-contained
  CLI/MCP parity suites pass locally. The exact-version UART connector
  acceptance lane checks snapshot capture on digest-pinned KiCad 10.0.0 and
  10.0.5 exports. Its capture-specific test has a function-level
  `evidence_lint` marker so the evidence selector can run it independently; the
  scoped tag declares `Native-Fixture: KICAD_RUN_NATIVE_DIGITAL_PEER_FIXTURES`
  to execute those native exports. Hosted acceptance `v0.5.0rc245` (run
  `38386654503`) passed the scoped unit gate with that switch set, the installed-
  wheel external-project check, and all three preview jobs; the package job was
  skipped by prerelease policy. This changes review evidence only; no physical
  electrical acceptance is claimed.

### P1 — Netlist and interface-pattern checks

#### LINT-081 — Same-net two-pin diode coverage

- **Status:** Implemented as `component.two_pin_diode_same_net`, a default
  `review` prompt with exact component, symbol, pin, and net evidence. It uses
  the same bounded native-netlist inventory logic as the existing passive
  rule while keeping a separate rule ID and project disposition.
- **Priority:** P1 incremental coverage. LINT-051 already covers fitted
  `Device:R/C/L` families; a source recheck of cohort rule SP-001 exposed the
  uncovered exact `Device:D` family. This is a narrow extension rather than a
  new generic same-net detector.
- **Predicate:** For exact `Device:D` and `Device:D_*` symbol identities,
  require a fitted component record, exactly two distinct native pin numbers,
  and one unambiguous assigned schematic net for each pin. Report only when
  those two net assignments match. `Device:LED`, custom libraries, incomplete
  inventories, multi-pin symbols, ambiguous or open pins, and DNP parts are
  outside the predicate.
- **Boundary:** A same-net diode may be a deliberate bypass or configuration
  choice. The review finding does not infer diode need, polarity, footprint
  pin mapping, or PCB copper continuity. Do not automatically join or split
  nets. A project may use the existing `review`, `block`, `off`, or exact-ignore
  controls after its owner reviews the case.
- **Fixtures:** Synthetic `Device:D` and `Device:D_Schottky` same-net faults;
  distinct-net controls; DNP, incomplete, ambiguous, `Device:LED`, and custom
  symbol exclusions; ordering and per-component net-split mutations; policy
  and exact-ignore lifecycle; and an unrelated fitted resistor mutation that
  changes the typed-netlist digest but preserves both diode fingerprints and a
  scoped D1 ignore. Shared CLI/MCP parity and repeated native exports on the
  pinned KiCad 10.0.0 and 10.0.5 fixture lane remain separate evidence. All
  sources are tooling-owned synthetic schematics.
- **Cohort boundary:** The public kicad-happy changelog motivated the coverage
  review. No candidate package or source was installed or copied. The local
  implementation is first-party and uses only the existing typed netlist
  service.
- **Verification state:** Unit, catalog, determinism, CLI/MCP, and fixture-lane
  wiring checks pass locally. The
  `test_native_two_pin_passive_same_net_fault_and_control` fixture
  passed on digest-pinned KiCad 10.0.0 and 10.0.5 on 2026-10-07 (one test, ten
  subtests). The same-net diode fault reports REVIEW and its distinct-net
  control passes on both versions. Their source hashes are
  `c7b34973f881f5c8d8e8ac26b07c03dec70b061f66b8338d61fb085583c2aa8b` (fault)
  and `74d19829e8dd9379a26cb6da9dd3cf10a48abce9d724661338f73ce0086bb928`
  (control); normalized typed-netlist hashes are
  `4765e426824bd009258f2ccae3ce118de6b585c3eddebb2437f09287d8cf6929` and
  `6b22eec75df4f715174590f577358d7205a958c1c23b6b09a6bd1875dbb90175`,
  respectively, matching across versions and repeats. This lane exports and
  parses native netlists; it does not run ERC or DRC. The first annotated
  selector tag, `v0.5.0rc226`, was canceled after scope inspection showed it
  omitted the existing diode CLI/MCP parity regression. The catalog now names
  that combined fault/control test; the corrected selector collects ten cases
  (3,279 unrelated tests deselected). All ten passed locally against the pinned
  public template at `5ca79bedf665a9b6577d96b1d47f13ccd518c968` and
  digest-pinned KiCad 10.0.0/10.0.5 fixtures. Tag `v0.5.0rc227` passed hosted
  GitHub Actions run `38357427541`, including the scoped gate with installed-
  wheel acceptance against the separate template and all Linux, macOS, and
  Windows preview jobs.

#### LINT-082 — UART-labeled IC pairs with separate reference nets

- **Status:** Implemented P1 extension to `bus.serial_peer_reference_review`;
  it is in the active rule catalog and defaults to REVIEW. Unit, rule-catalog,
  CLI/MCP parity, and cross-process hash-seed tests pass. The exact KiCad
  10.0.0/10.0.5 native lane passed locally on 2026-10-07. The Antmicro CM4
  Baseboard screen under LINT-031 shows explicit `UART.0.TX/RX` through
  `UART.3.TX/RX` labels on pins whose native functions are generic, so LINT-074
  does not see those direct signal nets.
- **Problem and hypothesis:** A UART-labeled TX/RX pair can directly connect
  two fitted ICs even when neither symbol names its pins TX/RX. If the two
  components also expose explicit reference pins on different schematic nets,
  a review prompt can ask whether the split is intentional. The current direct
  UART-function predicate does not cover that shape.
- **Predicate:** Recognize only numbered UART/USART TX/RX label forms,
  including channel-qualified hierarchical names such as `UART.0.TX`. Require
  one uniquely assigned TX net and one uniquely assigned RX net for the same
  channel; both nets must each connect exactly one pin from the same two fitted
  U/IC components. Require complete native pin number, function, and electrical
  type inventories and exactly one explicit named reference net per component.
  Emit one `REVIEW` when those reference nets differ; remain quiet when they
  match. Suppress only for a current source-matched serial-peer map whose exact
  signal pins, nets, reference pins, and `common_net`, `separate_nets`, or
  `bonded` policy match the observation. A bonded map also requires its exact
  component and side-pin assignments to match the native netlist.
- **Boundary:** This describes a directly connected label-identified signal
  segment; it does not establish that the components are the complete
  end-to-end UART peers or that a split reference is wrong. Keep connector
  endpoints, multi-hop paths, isolators, ambiguous or third-party signal nets,
  DNP components, incomplete pin metadata, and unsupported labels outside v1.
  Do not join nets or traverse an isolator from signal names alone. Project
  requirements and physical continuity remain separate evidence.
- **Verified controls:** A synthetic split-reference
  fault and same-reference control using generic signal pin functions; exact
  `common_net` and `separate_nets` map suppression; exact bonded-reference
  control and broken-bond fault; wrong or stale maps;
  mismatched/missing channel labels; a third connected component; DNP and
  incomplete inventories; shield/chassis reference exclusion; deterministic
  reordering and hash-seed runs; project rule override and exact-ignore lifecycle;
  and CLI/MCP parity pass locally. The serial-reference pytest suite
  `tests/test_ci_hosted_digital_peer_serial.py` exercises this lane on
  digest-pinned KiCad 10.0.0 and 10.0.5. The hosted run on 2026-10-07 exported
  both synthetic label schematics twice per version; the common-reference
  control had no `bus.serial_peer_reference_review` finding, and the split-
  reference fault had that one target finding. Normalized typed-netlist hashes
  matched across repeats and versions: control
  `8e55cec2b7b9ba375881f97934fee182e0c57033aab6796f8052e645a5188654`, fault
  `4b0db5605b6d6a7f9d531e05bb8dba84124a0c35a76242845c29296d3d0786d8`. Source
  hashes are `a0ac8548431af625c5116c1d456e4f2c6cf1714e58cca84c6fe595165d87c561`
  (control) and
  `2006adbfa6c6f1c99e88e3320a1ed7230f01a02f5e143c16a946abaa34f9db20`
  (fault). This serial-label lane exports and parses native netlists; it does
  not run ERC or DRC. The public common-GND sample is a boundary control only;
  it supplies no defect expectation. A tooling-owned synthetic three-channel
  labeled IC-pair fault now checks that all split-reference channels collapse
  to one review group, with a matching all-common quiet control and a
  three-channel order-stability case. This complements the single-channel
  parity/native fixture and public four-channel common-reference screen without
  copying public project source.

#### LINT-083 — Reviewed peer-comparison scopes for connector heuristics

- **Status:** Implemented as optional `peer_assignment_group` and
  `peer_assignment_basis` fields on project-owned connector interface reviews.
  This refines `connector.repeated_pin_function`,
  `connector.peer_pin_assignment_outlier`, and
  `connector.peer_pin_assignment_divergence`; it adds no electrical rule or
  default blocker. Synthetic source-matching tests and CLI/MCP parity coverage
  are in place.
- **Priority:** Precision control for repeated connector symbols used by
  separate interfaces. It reduces cross-interface signal comparisons while
  retaining the higher-value cross-group return and same-domain supply
  prompts. Any next change should address a measured miss or reviewer-cost
  result rather than broaden the predicate.
- **Predicate:** Use group scopes only when every connector participating in a
  comparison has a `COVERED` interface review whose catalog digest, complete
  component-pin inventory, native pin functions, and net assignments still
  match the current normalized native netlist. Partition generic and other
  non-return/supply pin comparisons by the reviewed group. Keep return and
  supply role comparisons cross-group. If any participating scope is absent,
  incomplete, or source-stale, retain the unscoped comparison.
- **Boundary:** A group states which connector instances the generic
  heuristics compare. It does not require common nets or declare nets
  independent. Group review can hide a generic signal mismatch across groups;
  use it only with a reviewed interface inventory and an explicit basis.
  Return and supply review remains active across groups, while explicit
  `pin_connectivity` and `grounding` requirements remain the way to state
  required electrical relationships. The report carries group and basis
  evidence for review.
- **Fixtures:** `test_peer_assignment_groups_scope_generic_pins_but_keep_return_review_global`
  checks that separate groups suppress generic signal comparisons, a shared
  group retains them, split returns remain visible across groups, and partial
  or stale source evidence restores broad comparisons; it also checks that
  same-domain supplies remain comparable across groups. Input-reordering and
  cross-process hash-seed regressions compare complete reports for stable
  ordering. The focused connector, lint, catalog, determinism, CLI/MCP parity,
  and surface suite passed on 2026-10-07: 675 tests and 746 subtests. The
  connector CLI/MCP parity test repeats separate, shared, and incomplete group
  cases through both surfaces. The exact-version connector-return lane now
  includes a synthetic three-port native fault with divergent generic signal
  assignments and split return nets. Separate source-matched groups must
  suppress only generic signal divergence while retaining the cross-group
  return finding; a shared group must report both findings, and the common-net
  control must pass. The lane is wired to the digest-pinned KiCad 10.0.0 and
  10.0.5 package acceptance job. The added typed-netlist regression passed in
  the focused connector/catalog run on 2026-10-07: 485 tests and 643 subtests
  passed; the two exact-version fixture tests were skipped because the native
  lane was not enabled locally because the digest-pinned container runner has
  no reachable Docker daemon. An app-bundled KiCad 10.0.6 CLI was located later
  and used for the public compatibility screen below; it does not substitute
  for the pinned native result.
- **Public sample screen (2026-10-07):** The
  [ARCI-PCB README at the tested commit](https://github.com/stianeklund/ARCI-PCB/blob/1666ea6646917ffcba7aaf7d2845aab62a90fecc/README.md)
  identifies separate UART1/Radio and UART2/Display headers and publishes
  pinout tables for them. A shallow public clone stayed under `/private/tmp`;
  no source was copied into Tooling. The main schematic SHA-256 is
  `6bbc441e3de24442cac3a356d85bc5c948f3e09e60d4ec7b5ba3e992a1695cfc`, and
  `connectors.kicad_sch` is
  `59c8fe5ba3610c1f4aac27f64582b3f2799cd1f2aeb6d5c97bd46ec0d00fce6c`.
  Local KiCad 10.0.6 exported 119 components and 130 nets; the native XML hash
  is `544679f220dd6d906313f41a9a3f41961a48101c450accb3b45564313db4d673`,
  and its normalized typed-netlist hash is
  `f48951028f7bb2dbff428cab3af3095fa3a73e809e58b159f6c826c2c455df16`.
  The exported assignments are J11.1=GND, J11.2=UART1 RX, J11.3=UART1 TX,
  and J13.1=GND, J13.2=UART2 RX, J13.3=UART2 TX. The README tables instead
  list TX on pin 1 and GND on pin 3 for both headers, so the published pinout
  and this native export disagree. The shared typed lint evaluator produced
  49 review candidates, including expected generic signal-pin divergence on
  J11/J13 because those connectors serve distinct UART interfaces, plus
  return-role coverage prompts because no reviewed project role map was
  supplied. The source was made with KiCad 9.0; this KiCad 10.0.6 run is a
  compatibility screen, not the pinned 10.0.0/10.0.5 lane. No project
  contract, ERC/DRC run, or owner disposition was available. Exclude this
  sample from precision and false-positive measurements until its pinout
  discrepancy is resolved; it is not evidence of an electrical defect.

#### LINT-070 — Repeated component power-pin assignment divergence

- **Status:** Implemented v2 as the default-review rule
  `component.peer_power_pin_assignment_divergence`. It preserves exact-symbol
  comparison and adds a guarded comparison for distinct symbols with the same
  native `PART_ID`. The project can use the standard rule override and
  fingerprinted-ignore lifecycle.
- **Problem:** Two repeated IC or module symbols can have every pin connected
  while corresponding ground/return or supply pins use different nets. A
  connector-only peer heuristic and the same-component repeated-supply check
  do not cover that pattern. A project-authored connectivity requirement can
  test a known relationship, but this prompt can reveal an unreviewed split.
- **Predicate:** Group fitted non-connector components by exact native symbol,
  or by a shared nonempty `PART_ID` when the symbols differ. Cross-symbol
  groups also require the same nonempty value and footprint, complete identical
  pin inventories, and identical function and electrical-type metadata for
  every pin. For each comparable pin, require a recognized matching return
  function or matching supply category and exactly one net assignment on every
  peer. Emit a review finding when the assigned nets differ. DNP instances,
  incomplete role metadata, unknown functions, ambiguous assignments, and
  open pins do not enter this comparison; open power pins remain with the more
  specific unconnected component checks.
- **Boundary:** Identical symbol identity and pin number identify a review
  candidate, not a required common domain or interchangeable part. Separate
  analog, digital, chassis, isolated-interface, or voltage rails may be
  intentional. The rule does not merge nets, establish a datasheet requirement,
  test whether ERC would detect a particular case, or prove PCB copper,
  off-board wiring, component conduction, current capacity, or physical
  continuity. Keep the default `review`; use a project-authored contract for
  a required relationship.
- **Fixtures:** Split ground and supply assignments; shared-domain controls;
  missing or differing `PART_ID`, value, or footprint; incomplete or
  mismatched pin inventories and metadata; DNP, open, and ambiguous peers;
  rule `review`/`block`/`off`, exact-ignore, and stale-ignore behavior;
  input-map reorder stability and commoning clears the finding; CLI/MCP parity
  over synthetic KiCad XML. Source-hashed synthetic native schematic pairs
  exercise exact-symbol behavior and distinct-symbol shared-`PART_ID` behavior
  through repeated pinned KiCad 10.0.0/10.0.5 exports. No board source is used.
- **Done:** The rule catalog and review evidence cover exact-symbol and guarded
  shared-`PART_ID` comparisons. The exact-symbol legacy `unittest` regressions
  have been migrated to pytest functions alongside the synthetic fault/control,
  boundary, determinism, and CLI/MCP parity coverage. The distinct-symbol native
  export lane passed on the digest-pinned KiCad 10.0.0 and 10.0.5 images during
  the 2026-10-09 work session. LINT-070 is quiet on the common-assignment
  control; its overall report remains `REVIEW` because the independent LINT-046
  decoupling prompt also applies. The existing exact-symbol native lane passed
  on the same pinned versions. ERC reports `power_pin_not_driven` errors for
  both its shared-domain and split-domain fixture, while the heuristic
  localizes differing peer pins. Field false-positive rates remain unmeasured.
- **Fixture inputs:** The existing
  [synthetic exact-symbol fixtures](../tests/fixtures/design_lint/component-peer-power-native/README.md)
  and new
  [synthetic shared-`PART_ID` fixtures](../tests/fixtures/design_lint/component-peer-power-assignment-native/README.md)
  record source hashes, assignments, and native-lane scope.

#### LINT-051 — Two-pin passive assigned to one schematic net

- **Status:** Implemented v1 as `component.two_pin_passive_same_net`, a
  default-review hint with exact pin/net evidence, project rule overrides, and
  fingerprinted ignores.
- **Problem:** ERC can accept a resistor, capacitor, or inductor whose two pins
  are assigned to the same schematic net. That topology can bypass a series
  element or short a shunt element while every pin remains connected.
- **Predicate:** Recognize the `Device:R`, `Device:C`, and `Device:L` symbol
  families; exact `Device:Varistor` and `Device:Varistor_US` identities; exact
  `Device:Thermistor`, `Device:Thermistor_NTC`, `Device:Thermistor_PTC`,
  `Device:Thermistor_US`, `Device:Thermistor_NTC_US`, and
  `Device:Thermistor_PTC_US` identities; and custom
  capacitor symbols with an exact project-authored role binding, only
  when the native netlist contains exactly two distinct pin
  numbers, one unambiguous net per pin, a fitted component state, and the
  component value. The custom binding must match `PART_ID`, symbol, footprint,
  and the full native pin number/function/electrical-type inventory. Report
  when both pins resolve to the same net. The rule does not infer a required
  series or shunt function.
- **Boundary:** A same-net part may be a deliberate jumper, measurement
  element, or other reviewed topology. Unmapped custom symbols, incomplete or
  multi-pin inventories, DNP parts, unassigned pins, and ambiguous net
  assignments are outside the predicate. The schematic netlist cannot prove
  copper connectivity, physical population, current behavior, or whether the
  symbol-to-footprint pin map is correct. Keep the default at `review`.
- **Fixtures:** Synthetic same-net resistor/capacitor/inductor and thermistor faults;
  distinct-net control; DNP, custom-symbol, multi-pin, missing-inventory,
  unassigned, and ambiguous-assignment exclusions; review/block/off/exact
  ignore and stale-fingerprint lifecycle; CLI/MCP parity; repeated exports
  through exact digest-pinned KiCad 10.0.0 and 10.0.5.
- **Done:** Unit and shared-surface regressions, catalog and documentation,
  source-hashed synthetic schematic exports, and repeatable typed native
  netlist evidence pass. No customer or proprietary board source is used.
- **Fixture inputs:** The
  [synthetic component README](../tests/fixtures/design_lint/two-pin-components/README.md)
  records the source hashes, fault/control topologies, and native export lane.
- **Varistor fixture inputs:** The
  [synthetic varistor README](../tests/fixtures/design_lint/two-pin-varistors/README.md)
  records the source hashes, supported identities, fault/control topologies,
  and evidence boundary.
- **Thermistor fixture inputs:** The
  [synthetic thermistor README](../tests/fixtures/design_lint/two-pin-thermistors/README.md)
  records the source hashes, exact supported identities, fault/control topologies,
  and evidence boundary.
- **Exact varistor extension (2026-10-13):** The public
  [kicad-happy SP-001 analyzer][happy-analyzer] prompted a review of the local
  same-net two-pin symbol allowlist. The official
  [KiCad Device library][kicad-device-library] includes `Device:Varistor` and
  `Device:Varistor_US`, which this rule previously skipped. The first-party
  predicate now recognizes only those two exact stock identities, with a
  source-hashed synthetic same-net fault, distinct-net control, DNP and
  unsupported-identity controls, metamorphic split/order coverage, and shared
  CLI/MCP parity. Its native fixture lane targets KiCad 10.0.0 and 10.0.5.
  The review was source-only: no candidate package was installed, no upstream
  code was copied, and no project design was used. This is a schematic
  topology review prompt; it does not establish protection requirements,
  ratings, orientation, footprint mapping, PCB copper, or physical population.
- **Exact thermistor extension (2026-10-13):** A source review of the official
  [KiCad 10.0.5 `Thermistor` symbol][kicad-thermistor-symbol-10.0.5] and
  [`Thermistor_NTC` symbol][kicad-thermistor-ntc-symbol-10.0.5] confirmed each
  has exactly native pin numbers 1 and 2. LINT-051 now includes only those two
  exact identities after verifying the project netlist has two distinct pins
  and an unambiguous assignment for each. The synthetic same-net fault and
  distinct-net control are source-hashed, exercised through CLI/MCP parity,
  and added to the exact KiCad 10.0.0/10.0.5 native fixture lane. NTC 3-wire,
  NTC 4-wire, PTC, US variants, case drift, and custom symbols remain excluded
  unless separately confirmed and reviewed. The check reports schematic
  topology only; it does not choose a sensor type, rating, application, or
  physical connection. No candidate project or proprietary source was used.
- **PTC and US-style thermistor extension (2026-10-13):** A source review of
  the official KiCad 10.0.5 [PTC][kicad-thermistor-ptc-symbol-10.0.5],
  [US-style][kicad-thermistor-us-symbol-10.0.5],
  [NTC US-style][kicad-thermistor-ntc-us-symbol-10.0.5], and
  [PTC US-style][kicad-thermistor-ptc-us-symbol-10.0.5]
  symbols confirmed each has exactly native pin numbers 1 and 2. LINT-051 now
  recognizes those four exact identities in addition to `Device:Thermistor`
  and `Device:Thermistor_NTC`. Each has source-hashed synthetic same-net and
  distinct-net schematics, and the exact-version native fixture gate checks
  the exports on KiCad 10.0.0 and 10.0.5. CLI/MCP parity covers the existing
  NTC identity and the new PTC identity; direct regressions cover all six.
  Unconfirmed variants, custom identities, and case drift remain excluded.
  The finding still reports schematic topology only. No project board or
  proprietary source was used.
- **Hosted thermistor gate (2026-10-13):** The `v0.5.0rc233` acceptance run
  surfaced two Markdown table-alignment issues in the synthetic fixture README;
  both were corrected. The follow-up `v0.5.0rc234` acceptance (run
  `38370567749`) passed the focused LINT-051 tests, exact KiCad 10.0.0/10.0.5
  native fixture exports, installed-wheel check against a separate project
  checkout, and Ubuntu/macOS/Windows preview orchestration.
- **Expanded native thermistor gate (2026-10-13):** The first expanded run
  exposed duplicate `thermistor` wording in the PTC fixture values. After
  normalizing all four new fixture pairs, `v0.5.0rc237` (run `38374391149`)
  passed the focused LINT-051 gate, KiCad 10.0.0/10.0.5 native fixtures,
  installed-wheel check against a separate project checkout, and all three
  portable preview lanes.
- **PTC and US-style thermistor fixtures:** The synthetic fault/control sources
  are retained in the same fixture directory with their individual hashes.
  They embed only minimal symbol geometry and pin assignments; exact stock
  symbol identity and native exports are checked separately by the pinned
  KiCad lane.
- **Verification (2026-10-13):** Focused synthetic rule and parity tests pass;
  source hashes and fixture selection are guarded by architecture tests. The
  digest-pinned native exports are delegated to the hosted lint-rule gate.
- **Verification (2026-10-13):** The focused rule selector passed 17 tests,
  including the same-net fault, distinct-net control, CLI/MCP parity, and
  repeated native exports on KiCad 10.0.0 and 10.0.5. The package acceptance
  also passed against the separate public template at commit
  `5ca79bedf665a9b6577d96b1d47f13ccd518c968`, including wheel installation,
  external inventory/surface verification, and playtest. The remaining 3,278
  tests were deselected by the rule scope. The local receipt is retained under
  ignored `build/ci/run-yahhu9sd`. Hosted tag acceptance for `v0.5.0rc229`
  (run `38363991457`) passed the focused lint gate, external installed-wheel
  check, and preview orchestration on Ubuntu, macOS, and Windows.
- **Exact custom-capacitor extension (2026-10-09):** The public
  [kicad-happy changelog][happy-changelog] records SP-001 for same-net
  two-pin passives and diodes. The local baseline already covered common
  `Device:R/C/L` symbols, so the incremental gap was opaque custom capacitors
  already classified by a project-authored exact role map. LINT-051 now
  reuses that shared resolver and reports only a role=`capacitor` entry whose
  `PART_ID`, symbol, footprint, and complete native pin inventory match. It
  does not guess from reference, value, or custom symbol name. Synthetic
  unmapped, mapped same-net, distinct-net, and DNP cases pass; a source-bound
  synthetic CLI/MCP parity case confirms both surfaces return the same
  role-bound evidence. A dedicated synthetic same-net schematic and mapped
  distinct-net control are now listed in the two-pin native export lane for
  KiCad 10.0.0 and 10.0.5. This host has no usable Docker socket or native
  KiCad CLI, so those new exact-version exports remain pending package
  acceptance; exact-role native exports are separately recorded by LINT-091.
  No cohort source or project design was copied.
- **Pinned native regression (2026-09-29):** The same two source-hashed synthetic schematics were
  each exported twice with exact KiCad 10.0.0
  (`ghcr.io/kicad/kicad:10.0.0@sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3`)
  and KiCad 10.0.5
  (`ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`).
  Both versions reported `REVIEW` for the same-net `R1` and `PASS` for the distinct-net control.
  Normalized native contracts matched across repeats; KiCad 10.0.0 digests were
  `9ced35ed89028d3fed5ec4be2f3694ec8ce6c375182f8a5b6f75faa22659a628` and
  `5ebfcd51987da4a69b89b34a7a7aa81ce0e2ad2d47047d119d40184a2fff5da5`, respectively. KiCad 10.0.5
  produced the same two normalized digests.

#### LINT-052 — Likely SPI participant missing from the authored roster

- **Status:** Implemented v1 as a configurable, default-review prompt using
  source-bound native pin functions, assignments, and the project electrical
  contract's SPI roster.
- **Problem:** LINT-013 checks the exact membership and endpoints a project
  declares, but a connected SPI-like IC omitted from that roster may otherwise
  be absent from the map's findings.
- **Predicate:** For a fitted U/IC reference, require an assigned clock pin
  function (`SCK`/`SCLK`), at least one assigned data function (`MOSI`/`SDI`/
  `COPI` or `MISO`/`SDO`/`CIPO`), and a named select function (`CS`/`CSN`/
  `NCS`/`NSS`/`SS`/`SSEL`/`CE0`/`CE1`). Emit a coverage prompt when no required
  SPI roster exists or the reference is absent from its controller/device/
  bridge list. Evidence binds the recognized pins, assigned nets, and electrical
  contract path and digest.
- **Boundary:** This is a candidate-generation clue, not a determination that a
  part is an SPI peripheral or that it should connect to a particular bus.
  Controllers, bridges, multi-protocol parts, and unused capabilities can
  match. A mapped reference is treated as covered by the prompt while the
  separate LINT-013 contract comparison reports its pin or identity mismatch.
  Only U/IC prefixes and the listed exact function aliases are recognized.
  This does not prove PCB continuity, internal transfer, or firmware setup.
- **Cohort input:** Source inspection of kicad-happy at
  [`a6bba1a`](https://github.com/aklofas/kicad-happy/tree/a6bba1add1e18b89e3aa0824b9769ed1d9d79174)
  found `validate_spi_bus` limited to chip-select pull-up review and
  `detect_sensor_interfaces` returning detected sensor summaries plus peers
  that share one or more extracted bus nets. Neither compares detected
  references with a project-authored SPI roster. The peer list can support
  review, but cannot name an omitted expected participant. No cohort code or
  project source was copied.
- **Fixtures:** Synthetic SPI controller and two-device source-bound netlist;
  absent roster; one mapped plus one unmapped device; complete roster control;
  DNP, non-IC, and partial function controls; review/block/off/exact-ignore
  behavior; source path/hash evidence; catalog reachability. Existing shared
  CLI/MCP service parity remains the invocation path.
- **Validation state:** Six focused regressions distinguish uncovered
  participants from mapped, DNP, non-IC, and partial-function controls. The
  cohort was reviewed by pinned source only; the SPI peer inventory itself was
  not benchmarked for reviewer-effort gain. No external analyzer dependency,
  cohort implementation, proprietary source, or project fixture was added.
- **Exact-version native validation (2026-09-30):** A synthetic two-device
  schematic with `SPI1_SCLK`, `SPI1_COPI`, `SPI1_CIPO`, and `SPI1_NSS` symbol
  pins was exported twice with the digest-pinned KiCad 10.0.0 and 10.0.5
  images. Both versions preserved all eight pin functions and produced the
  same normalized typed-netlist digest. An absent roster produced review
  candidates for the controller and peripheral; the exact authored roster
  control produced no participant findings. KiCad 10.0.5 raw XML differed
  across repeats, while its parsed netlist was stable. This verifies the native
  field boundary and predicate on these synthetic symbols; it does not prove
  the roster's engineering correctness or PCB connectivity. The fixture and
  image digests are recorded in
  [the native SPI fixture README](../tests/fixtures/design_lint/spi-participant-native/README.md).

#### LINT-053 — Likely USB-C connector missing a reviewed port role

- **Status:** Implemented v1 as a default-review coverage prompt using native
  connector pin functions and the project electrical contract's USB-C port
  map.
- **Problem:** LINT-012 validates source, sink, or dual-role CC and VBUS
  requirements after a project records a USB-C port, but assigned or named
  `CC1`/`CC2` pins with no port-role record otherwise produce no role-coverage
  prompt.
- **Predicate:** For a fitted numeric `J`, `P`, `X`, or `CN` reference, require
  exported pin functions for both exact `CC1` and `CC2` names. Prompt when the
  reference is absent from a required electrical `usb_c.ports` list or no
  required USB-C role map is configured. A mapped reference counts as covered
  by this prompt; the separate role contract reports pin, resistor, VBUS, and
  other mismatches. Evidence includes both connector pins, their assigned or
  unassigned native nets, contract path/digest when present, and roster state.
- **Boundary:** Pin names and reference prefixes only identify likely
  candidates. The finding does not infer that the symbol is a USB-C port, its
  source/sink/dual-role behavior, Rp/Rd values, controller configuration,
  protection, VBUS path, grounding requirement, compliance, or physical
  continuity. Unusual function aliases and connector-reference conventions
  can evade the prompt. DNP components are excluded. Default disposition is
  `REVIEW`; project rule overrides and exact fingerprint ignores remain
  available.
- **Cohort input:** The current public
  [kicad-happy project documentation](https://github.com/aklofas/kicad-happy)
  advertises USB-C CC validation, including pull-down and PD-controller cases.
  LINT-053 adopts only the missing-role coverage question and uses the existing
  project USB-C model; it does not import cohort code, assumed values, fixes,
  or severity. A read-only trial of the pinned kicad-happy v2.1.0 analyzer on
  synthetic unknown-role, source, and sink fixtures found no unique coverage
  beyond the local role-map prompt and role-aware contract. Evaluating the
  local rule on the same parsed native contracts prompted for a role-map review
  in all three cases, including the source and sink controls. For an unknown
  role, the candidate reports sink-specific missing-pull-down findings despite
  reporting its inferred role as `unknown`. Trial details and fixture hashes
  are in the
  [synthetic USB-C cohort fixture notes](../tests/fixtures/design_lint/cohort-usb-c-roles/README.md).
- **Fixtures:** Synthetic paired CC1/CC2 candidate with no role map; valid
  56 kΩ source and 5.1 kΩ sink CC topologies that still lack role-map records;
  mapped-port control; DNP, non-connector, and incomplete-function controls;
  contract source binding; review/block/off/exact-ignore lifecycle; CLI/MCP
  parity.
- **Exact-version native validation (2026-09-30):** The digest-pinned KiCad
  10.0.0 and 10.0.5 fixture lane exported the minimal connector, source, and
  sink schematics twice per version and preserved `J1.4=CC1` and `J1.5=CC2`.
  Both versions reported one `REVIEW` finding for each unreviewed role, even
  with valid 56 kΩ source or 5.1 kΩ sink paths; the map-listed `J1` control
  produced no coverage finding. Normalized contracts repeated with SHA-256
  `e6cfd2495852bee1c052a36927473dd1b8b52653fe8a6b16468e7c7b690c65b7` for
  the minimal connector, `f88a8f36c85ce3c84cb44c145ac57639890a99369821c17d40a733907740e613`
  for the source control, and
  `6ab178bc1c36b936f2ff75995d76fcb2e91fc30a3d5e53c81ad9d22efe7531e0` for
  the sink control. Raw XML hashes varied for some repeated exports under
  both native versions, while the normalized typed contracts matched across
  repeats and versions. This
  lane tests netlist export and lint coverage only; it does not run ERC or
  validate a USB-C design. Fixture source identity and boundaries are recorded in
  [the native USB-C fixture README](../tests/fixtures/design_lint/usb-c-port-native/README.md).

#### LINT-010 — I2C pull-up topology and rail review

- **Status:** Partial v7. The direct discrete-resistor heuristic and authored
  electrical requirement support exact signal nets, rails, and inclusive
  nominal resistance ranges. The authored requirement supports explicitly
  ordered, unbranched resistor chains with exact component identity, per-leg
  nominal ranges, two-pin inventories, and source-bound junction checks. The
  review heuristic also recognizes direct resistors and unbranched discrete
  series chains. The electrical contract supports explicitly mapped
  resistor-array channels with exact component identity, full native pin
  disposition, per-channel pin/net assignments, and datasheet-sourced nominal
  resistance. An optional authored rail-to-input voltage comparison now has
  source-bound synthetic coverage. A passing source-bound requirement for the
  exact ordered SDA/SCL net pair resolves the generic missing-pull-up hint
  only when both authored line checks pass, including optional voltage
  compatibility and resistor-window checks. The optional resistor window
  derives a lower bound from authored pull-up voltage, VOL and sink-current
  limits, and an upper bound from authored bus capacitance and rise-time limit
  using the idealized 30%-to-70% RC relation. This covers an otherwise valid
  mapped resistor array the heuristic cannot recognize. An optional
  project-authored maximum per-resistor tolerance and basis applies a
  conservative worst-case bound to the nominal range before comparing it with
  the derived sink-current and rise-time limits. The report retains the
  electrical contract digest, native netlist digest, bus ID, and exact passing
  check IDs used for that resolution.
- **Problem:** The review heuristic recognizes direct conventional resistors
  and unbranched resistor chains but cannot resolve resistor arrays, branched
  networks, or rail-voltage compatibility on its own. Only a matching passing
  authored contract resolves the array hint; missing, pending, not-applicable,
  mismatched, or failing requirements leave it open. The optional voltage
  contract compares only the explicitly mapped endpoints. The heuristic may
  review valid internal, remote, or deliberately different pull-ups.
- **Evidence and check:** The review heuristic sums each recognized unbranched
  series chain and calculates the parallel equivalent of fitted conventional
  R-reference paths to one named positive rail; it flags equivalents below
  1 kΩ. Every resistor and path total must be in the 1 kΩ–100 kΩ band, and
  each intermediate net must contain exactly the two resistor pins. A
  project-owned `i2c_pullups` electrical requirement names each SDA/SCL net,
  required pull-up rail, and inclusive nominal resistance range; it can also
  name ordered series legs, exact component identity, per-leg resistance
  ranges, and array channel pins with explicit reasons for unlisted package
  pins. The electrical lane fails on a missing or mismatched direct, series,
  or mapped-array path, an intermediate series branch, an incomplete array
  pin disposition, an out-of-range equivalent, or a direct pull-up to another
  recognized positive rail. An optional per-line voltage map compares a
  project-authored maximum pull-up rail voltage with exact SDA/SCL input pins,
  their symbol and footprint identities, native pin inventories, net
  assignments, and independently sourced maximum bus-voltage limits. The
  input-scope basis records how the project reviewed completeness; omitted
  endpoints are not auto-discovered. Values and source bases are bound by the
  electrical contract digest.
  Array internals and authored nominal channel resistance still depend on an
  independently reviewed datasheet pin map. Resolving this schematic hint
  does not prove physical board return paths, copper connectivity, fitted
  resistor behavior, or off-board pull-up behavior. Project rule overrides or
  exact ignores continue to control only heuristic disposition. The optional
  resistor window remains nominal-only unless a maximum per-resistor tolerance
  and basis are supplied. The tool does not verify that source or its coverage
  of every resistor element.
- **Boundary:** The voltage comparison does not verify that the rail ceiling
  or datasheet limits are correct. Its `operating` or `absolute_maximum` limit
  kind is recorded but not independently validated. The optional resistor
  window uses project-supplied maximum bus capacitance and rise time and
  minimum sink current; it does not extract capacitance, model nonlinear or
  active pull-ups, verify the authored resistor-tolerance source, model device
  dynamics, or predict measured waveforms. Netlist topology does not establish transient
  compatibility or off-board behavior.
- **Fixtures:** Two direct 4.7 kΩ resistors passing at 2.35 kΩ equivalent;
  parallel 1 kΩ resistors failing the configured range; missing path; wrong
  rail; DNP exclusion; valid two-leg series chain alone and in parallel with a
  direct path; wrong series identity, value, net, pin inventory, or branched
  junction; valid mapped array; wrong array
  identity, pin, or net; unreviewed native array pin; explicit unused-pin
  reason; equal and inverted resistance bounds; voltage-limit equality pass;
  excessive rail voltage, wrong input net, stale symbol/footprint/pin
  inventory, and DNP endpoint faults; missing, pending, mismatched-bus, wrong
  array-symbol, wrong-channel-net, DNP-array, and symmetric-pin-orientation
  heuristic-coverage controls; a self-contained CLI/MCP parity regression for
  a passing mapped-array control and a missing-array fault, including live
  tool-surface registration without the external reference template;
  retained-evidence replay; source-bound resistor-window passes, lower- and
  upper-bound equality, violations on both sides, and an empty calculated
  window; per-resistor tolerance controls for worst-case pass, exact inclusive
  boundaries, lower- and upper-side failures, missing basis, and out-of-range
  percentages; CLI/MCP parity for passing and excessive-capacitance controls.
  Release verification replays authored voltage and resistor-window checks
  against the source-hashed netlist and rejects omission of any result.
- **Native fixture evidence (2026-10-03):** The synthetic mapped-array
  control and pin/net fault export twice through digest-pinned KiCad 10.0.0
  and 10.0.5. Both versions retain the exact array symbol, footprint, value,
  four-pin inventory, and channel assignments. The control passes SDA and SCL;
  moving only RN1.1 from `I2C_SDA` to `SDA_WRONG` fails SDA with that exact
  mismatch while SCL remains passing. Repeated exports produce identical
  normalized typed-netlist hashes per fixture across both versions: control
  `891918a1106ab700a1cc6278ae9f7eb6372a8eb31cdcfb02d51b6a63487c83bd`, fault
  `33c47e5931fdd2066d496be02486557495a99814e9667627f8a4ba4d39f3820c`. Source
  hashes are `922e40c8815a302e8af30e3eb7e4a53b1b3361be419cc0c56fe3025619a7243d`
  (control) and `062648e3ec3d9c71e976fc40370d4d7a1ab4d6064e73d79fe191878ee052efc4`
  (fault); raw XML hashes are retained in ignored hosted-CI receipts. The
  optional lane exports and parses native netlists; it does not run ERC/DRC.
  See the [native fixture notes](../tests/fixtures/design_lint/i2c-array-native/README.md)
  for the reproducible command and image pins.
- **Native heuristic integration (2026-10-12):** The mapped-array native lane
  now runs the active `bus.i2c_missing_pullup` rule on the same parsed export,
  using the shared source-bound coverage service and a separate synthetic
  project contract. Both exports start with an open heuristic prompt. The
  all-passing array control resolves it; the wrong-SDA fault keeps the prompt
  open while its SCL channel still passes. The native test is indexed as both
  fault and valid control for the rule and requires
  `KICAD_RUN_NATIVE_I2C_PULLUP_FIXTURES`; a synthetic orchestration regression
  checks the same integration without invoking KiCad. The focused tagged
  acceptance `v0.5.0rc189` passed GitHub Actions run `38300304999`; it selected
  this rule and enabled the native fixture switch. Its exact-version native
  fixture covers KiCad 10.0.0 and 10.0.5, and the hosted gate also passed the
  installed-wheel check against a separate public template checkout and the
  Ubuntu, macOS, and Windows preview jobs. The package-release job was skipped
  for the prerelease tag. This validates contract-to-lint behavior on
  native-derived synthetic connectivity, not array internals or physical
  resistor behavior.
- **Remaining:** Rail ceiling and pin-voltage limits remain reviewed inputs;
  the checker does not verify cited source documents or whether the authored
  resistor-tolerance bound covers every element. Actual bus capacitance and
  transient behavior remain reviewed inputs. Internal and off-board pull-ups
  remain an explicit not-applicable decision for this local-netlist contract.

#### LINT-011 — CAN termination topology and bus-end declarations

- **Status:** Partial v2. The project-authored electrical contract checks
  required CANH/CANL pin assignments, exact direct and split local resistor
  paths, endpoint references, inclusive nominal ranges, extra direct paths,
  explicitly external/DNP options, and an optional exact split midpoint
  capacitor mapping.
- **Problem:** A direct 120-ohm resistor check does not model two bus ends,
  split termination, switchable termination, or the project's actual topology.
- **Evidence and check:** `can_termination` names the bus nets, logical
  pins and nets, logical endpoints, topology, exact resistor references/net
  paths, nominal ranges, and DNP options. The electrical analysis and
  retained-evidence replay compare these requirements with the source-bound
  native netlist. Direct paths are checked individually; split termination
  requires two legs to the same declared midpoint. A split endpoint may
  optionally map one capacitor by exact component identity, two native pins,
  reference net, and nominal capacitance range. The check requires exactly two
  native pins and validates both net assignments. External endpoints remain
  explicitly unverifiable from schematic evidence and are reported
  `NOT_APPLICABLE`.
- **Native source fixtures:** `tests.test_can_native_fixture_lanes`
  exports synthetic control and single-pin fault schematics twice with the
  digest-pinned KiCad 10.0.0 and 10.0.5 images. The typed netlist hashes match
  across versions: control
  `de5d5d2edff5d2f4143bd8a5595734c3ea64f6dfa3844eef626999806fc53c9d`, fault
  `4d0141640743cd0f953fe382941036a396f39b104fe89d9fd1febc43767bacb6`. Moving
  only `C1.2` from `GND` to `GND_ALT` leaves the CAN pin, direct-resistor, and
  split-leg checks passing while the mapped capacitor check fails. Source
  hashes and the run command are in
  [`can-split-midpoint-native`](../tests/fixtures/design_lint/can-split-midpoint-native/README.md).
- **Boundary:** Do not require termination on every node or assume a topology
  from CANH/CANL names. The capacitor map is opt-in and does not prove
  placement, voltage derating, impedance, EMC behavior, physical bus-end
  placement, remote termination, or PCB copper continuity. The source fixture
  lane exports netlists only; it does not run ERC/DRC.
- **Fixtures:** Correct two-end termination; missing or misassigned CAN pin;
  missing endpoint; wrong value; unlisted extra direct resistor; split
  termination and crossed leg; mapped midpoint capacitor with boundary and
  missing/value/identity/net/inventory faults; fitted
  requirement with a DNP part; external endpoint with an expected DNP local
  option; CLI/MCP parity; retained-evidence replay.
- **Remaining:** Extend beyond exact direct/split/DNP topology only when an
  independently reviewed project requirement demonstrates the need.

#### LINT-012 — USB-C role-aware CC and VBUS checks

- **Status:** Partial v1 in the project-authored electrical contract. Source and
  sink ports can declare resistor-based Rp/Rd or controller-managed CC pins;
  dual-role ports require two mapped controller pins. Debug-accessory behavior
  is reported `NOT_RUN` and keeps the lane failing until it is modeled. A port
  may also declare an exact ordered connector-to-board VBUS component/net map.
- **Problem:** A connected CC pin alone does not establish that Rd/Rp,
  orientation handling, VBUS, and power direction match the connector's role.
- **Evidence and check:** The `usb_c` electrical section declares each port's
  role, exact connector CC pins/nets, resistor value ranges or controller pins,
  exact controller/protection symbols and footprints, VBUS pin/net assignments,
  ground pins, and protection applicability. CLI, MCP, and retained-evidence
  replay use the same typed check against a source-bound native netlist.
  An optional `vbus_path` checks declared endpoints and an ordered series chain
  by exact component reference, symbol, footprint, mapped pin inventory, and
  pin-to-net assignments. The path is opt-in and project-authored.
- **Boundary:** Do not infer role from resistor labels or connector names.
  A netlist cannot prove controller configuration, internal Rp/Rd behavior,
  current capability, VBUS power-path continuity through switches/fuses,
  orientation handling, PD negotiation, protection effectiveness, remote
  equipment, or compliance. VBUS checks verify declared pin-to-net assignments
  on each side. The optional chain check confirms the authored schematic map;
  it does not prove conduction through a component, switch state or direction,
  the absence of a parallel bypass, or PCB copper/contact continuity.
  Debug-accessory behavior remains unsupported and deliberately cannot pass.
- **Fixtures:** Resistor-based source and sink, controller-managed dual-role port,
  missing or misassigned CC pin, DNP/out-of-range Rp, wrong controller or
  protection symbol/footprint, wrong protection pin net, wrong VBUS pin net,
  debug-accessory unsupported result, valid fuse/load-switch path, missing or
  unfitted path element, wrong element identity/footprint, disconnected mapped
  pin, discontinuous declared chain, CLI/MCP parity, and retained-evidence
  replay.
- **Remaining:** Static controller configuration-pin relationships can use
  the existing project-authored `pin_connectivity` contract; the native source
  and CLI/MCP fault/control tests already cover exact pin-to-net comparisons.
  A USB-C-specific duplicate is not planned unless an independently reviewed
  controller use case demonstrates a gap in that shared contract. Controller
  registers, firmware, dynamic source/sink behavior, and internal Rp/Rd remain
  unverified. A power-path check would need evidence for component conduction
  and actual PCB copper/contact continuity; the current optional contract only
  checks the authored schematic map.

#### LINT-013 — SPI device and chip-select membership

- **Status:** Implemented as an optional project-authored electrical contract;
  automatic discovery of omitted devices remains a heuristic/review question.
- **Problem:** A connected CS pin can still be missing the expected bus/device
  relationship; names do not show which controller owns a device.
- **Evidence and check:** The `spi` section compares explicit controller,
  device, and optional bridge symbol/footprint identities and signal-pin nets
  to the source-bound native netlist from the existing version-pinned native
  export path (currently the KiCad 10 profile). Every declared controller CS
  net must map to at least one device. Multiple devices on a CS net require
  one shared group. MISO can be connected, intentionally unconnected, or
  absent with a reason. A bridge route requires exact observed net assignments
  at its declared endpoints.
- **Boundary:** An omitted device cannot be discovered deterministically from
  the netlist alone. Bridge endpoint mapping does not prove internal transfer,
  direction, power, or enable behavior. Mode, timing, polarity, firmware, PCB
  copper continuity, and signal integrity remain outside this check.
- **Fixtures:** Synthetic one-controller/two-device map; disconnected and
  wrong-net CS; missing controller CS membership; unauthorized and explicitly
  shared select; write-only and unconnected MISO; buffered MISO; wrong bridge
  endpoint; setup pending state; CLI/MCP parity; retained-evidence replay.
- **Remaining:** Candidate discovery is intentionally limited to exact exported
  pin-function aliases and U/IC references. Broaden it only with synthetic
  fault/control pairs for supported aliases. The pinned kicad-happy detector
  review found no SPI-roster comparison; the local `bus.spi_unmapped_participant`
  prompt now supplies that coverage clue without asserting the device belongs
  on a bus.

#### LINT-014 — UART and serial peer mapping

- **Status:** Implemented as an optional project-authored electrical contract;
  direct logic-voltage margins are checked when reviewed endpoint limits are
  supplied; automatic UART peer discovery remains a review heuristic.
- **Problem:** Similar serial connectors can have TX/RX, ground, or voltage
  pins omitted or mis-mapped while each remaining pin is connected.
- **Evidence and check:** The `serial_peers` contract compares authored UART
  endpoint component identity, TX/RX pin perspective, logic-domain labels,
  reference pins, and direct or level-shifted path endpoints to the exact
  source-bound native netlist from the KiCad 10 profile. Direct links require
  TX-to-RX crossing in both directions and matching logic-domain labels.
  Direct links also require `logic_limits` for both endpoints to pass voltage
  compatibility: guaranteed output-low and output-high ranges must fit the
  receiver's low/high thresholds and absolute input range in both directions.
  Each authored limit records its document basis and operating conditions.
  Missing endpoint limits produce `NOT_CONFIGURED` checks rather than a pass.
  Project policy names a common reference net, a verified bond across distinct
  reference nets, distinct unbonded endpoint nets, no applicable reference, or
  an external reference that is unverified. A bonded map names one exact
  passive two-pin component, value, footprint, and side-pin net assignment;
  the native netlist check also requires it fitted with passive pin types.
- **Boundary:** This is pin/netlist membership, not board copper continuity,
  galvanic-isolation proof, shifter transfer behavior, power/enable behavior,
  or external equipment wiring. Voltage comparison uses project-authored
  datasheet limits; it does not verify those values or sources, their test
  conditions, transients, timing, loading, or actual device behavior. Level-
  shifted and external peers remain outside the direct voltage comparison.
  Domain labels are authored identifiers; they do not contain electrical limits.
  The check covers logic-level UART maps, not RS-232 or RS-485. LINT-072 adds
  a separate review heuristic for bounded TX/RX pin functions and exact
  UART/USART-labeled nets; arbitrary net names still do not establish an
  omitted peer declaration.
- **Fixtures:** Correct crossed link; TX-to-TX/RX-to-RX fault; missing and
  misassigned reference pins; same-domain direct pair; different-domain
  level-shifted pair; wrong bridge endpoint; direct-link high-voltage and
  low-level margin faults; exact-limit equality; missing limits; unknown
  external peer; bonded-reference control and missing, DNP, identity, value,
  pin-type, and wrong-net faults; setup pending state; CLI/MCP parity;
  retained-evidence replay; input-reordering stability. Pinned native fixtures
  are required to verify KiCad export of the mapped bond component.
- **Remaining:** Add board-level path or isolation evidence only if a separate
  source-bound artifact can support a deterministic check. Values and
  datasheet-source truth remain project-owner review responsibilities.
  LINT-072 adds a separate default-review coverage prompt for exact exported
  UART-like TX/RX function pairs missing from this authored peer map. It does
  not infer whether those pairs are intended or whether grounds should be
  common; connector pinout and grounding requirements remain project-authored.

#### LINT-015 — RS-485 termination, bias, and fail-safe topology

- **Status:** Implemented as an optional project-authored electrical
  contract, with no default electrical assumptions.
- **Problem:** Differential pair presence does not establish termination or
  bias arrangements for a declared RS-485 topology.
- **Evidence and check:** The `rs485` section declares two-wire half-duplex or
  four-wire full-duplex topology, exact transceiver/connector symbol and
  footprint identities, line/control/reference pin maps, local direct or split
  termination values and nets, optional DNP termination parts, and one explicit
  local/remote/internal-fail-safe/not-required bias decision per pair. Checks
  use the source-bound KiCad 10 native netlist; retained evidence replays the
  same typed service. CLI and MCP share the service and have a parity test.
- **Boundary:** This verifies schematic pin/net membership, component identity,
  DNP state, and authored nominal ranges. It does not choose universal values
  or verify external peers, cable impedance, physical endpoint placement,
  component ratings/tolerance, device fail-safe features, timing, signal
  integrity, PCB copper, isolation, or remote wiring. External and internal
  behavior is explicitly reported as unverified or `NOT_APPLICABLE`.
- **Fixtures:** Synthetic two-wire and four-wire maps; direct and split
  termination; wrong endpoint line; DNP or miswired termination; local, remote,
  internal-fail-safe, and not-required bias; DNP or miswired bias; declared
  isolated references; unknown peer; wrong symbol identity; pending setup;
  CLI/MCP parity; retained-evidence replay.
- **Remaining:** Add a separate PCB-evidence adapter only if a native,
  source-bound artifact can prove the needed path or geometry. Do not infer
  isolation or omitted peers from the schematic netlist.

#### LINT-016 — Required power-source and load relationship review

- **Status:** Implemented as an optional, project-authored rail membership
  contract; ERC retains electrical-type diagnostics.
- **Problem:** Named supply pins can be connected to a net with no declared
  source, or a source can feed loads on a rail that does not meet project
  expectations.
- **Evidence and check:** `power_connectivity` records each rail net, one or
  more required source groups (`all` or `any` alternatives), and every mapped
  load endpoint. Exact symbol/footprint identity, DNP state, and pin/net
  membership are compared with the source-bound KiCad 10 netlist. When the
  power budget is configured, rail IDs and the complete budget load-ID set
  must match the connectivity map. CLI/MCP parity and retained-evidence replay
  use the same typed service.
- **Boundary:** Endpoint roles and map completeness are project-authored. This
  does not infer omitted devices, electrical pin types, current direction,
  physical source/load existence, voltage/current capacity, sequencing,
  protection behavior, or copper continuity. ERC remains authoritative for
  its electrical-type diagnostics; the source/load map does not re-label ERC
  as independent detection.
- **Fixtures:** Synthetic external-input connector alternatives; regulator and
  monitor load endpoints; wrong source net; wrong load net; DNP required source;
  wrong source identity; one-of alternatives with one valid and no valid source;
  power-budget rail/load coverage mismatch; setup pending; CLI/MCP parity;
  retained-evidence replay.
- **Remaining:** Add pin electrical-type context only if it demonstrates a
  specific gap beyond native ERC and retains current-version source evidence.
  Keep source direction, switches, reverse-protection paths, and physical power
  behavior out of the v1 claim.

#### LINT-017 — Reset, enable, and boot-strap bias review

- **Status:** Implemented as an optional project-authored control-signal
  contract. Two configurable review-only candidate rules also report unassigned
  control inputs and connected control nets without a visible resistor path to
  a recognized positive or return net.
- **Problem:** Reset/enable/boot pins may be wired but left without the
  intended bias, driven by multiple outputs, or tied to the wrong domain.
- **Evidence and check:** `control_inputs` declares each signal net, exact
  controlled-input and interface pins, expected KiCad pin electrical types,
  approved driver set/policy, and either exact local resistor paths with
  inclusive nominal ranges or an explicit internal, external, or not-required
  bias decision. The source-bound KiCad 10 netlist checks component identity,
  pin/net membership, pin electrical type, DNP state, resistor value, and
  unlisted output-capable symbol pins connected to each declared control net.
  CLI, MCP, and retained-evidence replay use the same typed service.
- **Connected-input prompt:** `control.connected_control_input_without_visible_bias`
  groups recognized, connected reset/enable/boot input pins by their unique
  assigned net. It reports one REVIEW candidate per net when no fitted,
  conventional two-terminal resistor path reaches a recognized positive or
  return net. Direct resistors and unbranched series chains are recognized
  without a resistance window; each intermediate net must contain exactly the
  two resistor pins. DNP and zero-ohm resistors, branched or ambiguous chains,
  resistor arrays, and jumpers do not satisfy the path. Native output-capable peers are
  included in the evidence for review; they do not suppress the candidate
  because their runtime state is not known. A directly visible resistor in
  either polarity or a supported chain clears the prompt. The existing per-rule `review`, `block`,
  `off`, and exact-ignore controls apply. An exact project control-input
  requirement can resolve a candidate when it covers every detected input on
  that net, its endpoint and driver checks pass, and its local-bias check passes
  or it explicitly records an internal, external, or not-required decision.
  The lint report records the contract path and digest plus each covered or open
  candidate. A failed contract check leaves the heuristic prompt open.
  The bounded reset alias set includes the `POR` token because the official
  KiCad `MCU_Module:CHIP-PRO` symbol names an input `POR_B`; `PORN` remains a
  negative control rather than a substring match.
- **Power bootstrap pin boundary:** Cohort review found KiCad-Happy's LC detector explicitly
  recognizes bootstrap capacitors between pins named `BST`, `BOOT`, `BOOTSTRAP`, or `CBST` and a
  switching node
  ([source](https://github.com/aklofas/kicad-happy/blob/main/skills/kicad/scripts/signal_detectors.py#L698-L710)).
  The tooling's exact `BOOTSTRAP` alias treated that power-stage input as a boot-mode strap in both
  unconnected and connected-input checks. The exact `BOOTSTRAP` alias is removed. For the connected
  missing-bias rule, an exact bare `BOOT` pin is now excluded only when the native netlist shows a
  fitted, exact two-pin unpolarized `Device:C` or `Device:C_Small` between its net and a same-device
  `SW`, `LX`, or `PH` pin net. Bare `BOOT` elsewhere remains reviewable, including the
  unconnected-input rule. Synthetic controls preserve `BOOT0`, DNP-capacitor, wrong-symbol,
  incomplete-inventory, and different-device prompts. A metamorphic case also preserves both the
  quiet and review outcomes when net labels and typed-netlist mapping order change. Source-bound
  native fixtures for both standard capacitor symbols are registered in the KiCad 10.0.5 fixture
  lane. Both pinned local native exports repeated with stable normalized typed-netlist digests and
  zero connected-bias candidates: `Device:C`
  (`1f47dd17c62a0e8e962582fbcc104123d18e5deb6c09b978c858d15443e82d83`) and `Device:C_Small`
  (`803284fdb8a3f1e76cef39efa11b599e523ed4f941f0945dd78cc2d7ab2d41ef`). The four-source fixture
  manifest is `173897d8682ffa2e48412469164c6329235ddeb6b6a197898e0c7349a891358b`. Hosted CI has not
  yet run this extension. This screen does not verify a required capacitor, part value, placement,
  or PCB connectivity. No cohort code or board project was imported.
- **Unconnected-pin input:** KiCad's native XML uses synthetic names such as
  `unconnected-(J1-SHIELD-Pad3)` for pins without net assignments. The native
  adapter now retains those pin references in `NetlistContract.unconnected_nets`
  while excluding the synthetic entries from `nets`. This allows explicit
  `unconnected` requirements and review heuristics to distinguish a true open
  from a separately named electrical net.
- **Boundary:** No universal reset polarity, strap value, or boot state. Do not
  infer requirements from `RESET`, `EN`, `BOOT`, or active-low naming alone.
  KiCad pin types describe library metadata, not firmware runtime direction.
  Internal bias, remote hosts, actual drive behavior, resistor tolerance/rating,
  PCB copper, and physical test access remain unverified. Unlisted
  bidirectional or output-capable pin metadata is a contract-review mismatch,
  not proof of electrical contention. The connected-input prompt does not
  trace resistor arrays or unsupported paths, infer custom rail names, validate
  resistor adequacy, or prove a visible schematic path reaches the physical input.
  An authored internal or external decision records intent and does not verify
  firmware behavior, the remote host, or physical bias implementation.
- **Fixtures:** Correct pull-up/down, including two-resistor unbranched chains
  to positive and return rails; branched, DNP, and zero-ohm chain controls;
  missing resistor; DNP option; wrong rail
  and value; expected shared open-drain drivers; changed native pin type;
  missing type metadata; unlisted push-pull output; explicit internal,
  external, and not-required bias; unassigned reset/enable/boot inputs; valid
  connected and unrelated passive-function controls; the `POR_B` input fault
  and `PORN` nonmatch control; DNP component exclusion; CLI/MCP parity;
  retained-evidence replay.
- **Public sample check:** At KiCAD-Test commit
  `ed89536f0dbbcb013145af2994fef41b2250143e`, read-only netlist exports from
  `arduino-uno-status-led` and `raspberry-pi-status-led` used the pinned KiCad
  10.0.5 image; `controller` used its pinned KiCad 10.0.0 image. They contained
  3, 3, and 2 components respectively, no `input`/`input_low` pin types, and
  no findings. These are negative controls for pins outside the predicate;
  they cannot estimate false positives among recognized control inputs.
- **Pinned native-demo screen (2026-09-29):**
  Three schematics bundled in `ghcr.io/kicad/kicad:10.0.5` were exported
  with exact KiCad 10.0.5 on `linux/amd64`, then parsed through the local
  `read_netlist` adapter. Exact image digest:
  `fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`.
  Inputs: `video/video.kicad_sch`,
  `royalblue54L_feather/RoyalBlue54L-Feather.kicad_sch`, and
  `tiny_tapeout/tinytapeout-demo.kicad_sch`. Across the three exports, the
  heuristic recognized five connected reset/enable pins whose native type is
  `input`: `U11.139 RST#`, `U10.87 RESET`, `U1.G2 ~{RESET}`, `J4.A12 RST`, and
  `U3.3 EN`. It produced zero unconnected-control findings. It also correctly
  excluded `BUS1.A15 RST#` (`output`) and `J8.3 ~{RESET}` (`open_collector`).
  No boot-input alias occurred in these examples. Component counts were 189,
  71, and 150; pin-function counts were 1,784, 243, and 360 respectively.
  The canonical sorted path/SHA-256 manifests for all schematics beneath each
  demo directory hash to `edc6818712f2e40cc049cf8f87961820dccc0782f7d2fa59a1001250979ba1e8`
  (`video`), `48614e87c84fc96e1874c933893a612c71d29b32ca0ed267b6bb2ebe16090092`
  (`royalblue54L_feather`), and
  `29f6620df627ea2db0e9eeda314a5b185b9d361830ab2551a5f122c1c3d27e97`
  (`tiny_tapeout`). Exported netlist SHA-256 values were
  `a8f816d96c592f6d167cbb819117835931dc4823ac35095a95ebc2ae6f827a47`
  (`video`),
  `9e3ee51f1594f61534b3a07cb01742c07d23a7fcc30a87787cf7e2f280880f30`
  (`royalblue54L_feather`), and
  `a31facf732dbb3cb5fa27b46782e33759ec68a198689075149e698b21c81f029`
  (`tiny_tapeout`). Demo schematics stayed inside the digest-pinned public
  KiCad image; their temporary netlist exports and receipts were retained
  under ignored `build/`. The optional test harness copies the public KiCad-Test
  template into an ignored temporary `build/ci` root to select its pinned
  project toolchain. No proprietary or adopter source is used. This validates the
  existing reset/enable aliases and native pin-type filter on these connected
  examples. It does not measure false positives for intentionally unconnected
  control inputs or exercise a boot input.
- **Earlier sample limitation:** The connected examples above alone could not
  exercise unconnected controls or boot/strap aliases. Do not infer required
  polarity, bias, or driver relationships from a pin name.
- **Pinned native unconnected-control regression (2026-09-29):** The opt-in
  `KICAD_RUN_NATIVE_CONTROL_INPUT_FIXTURES=1` lane exports four public demos bundled in
  `ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`
  using exact KiCad 10.0.5 on `linux/amd64`. The container is read-only, has no network, mounts only
  an output directory, and does not copy source into this repository. Per-demo source-file and full
  schematic-directory manifest hashes, raw XML hashes, parsed-contract hashes, and command receipts
  are retained under ignored `build/ci-hosted/native-control-input-demos/`.

  | Public demo source (within `/usr/share/kicad/demos`)                                   | Source file SHA-256                                                | Schematic manifest SHA-256                                         | Review candidates                                                                          |
  | -------------------------------------------------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------ |
  | CM5 Minima: `cm5_minima/CM5_MINIMA_3.kicad_sch`                                        | `b40a486994138c07a45d20e08e6f42405e4b99a88e82a3d55f23704ca9ddc0e7` | `e0c16749ea62d80ca72188261328838d89def9d2529de6880e8e5e127f75a308` | none                                                                                       |
  | Jetson AGX Thor: `jetson-agx-thor-baseboard/jetson-agx-thor-baseboard.kicad_sch`       | `bd943f5c309046e09a1c99e443e1ce23a0c922291371ca60839412694351340b` | `165e4faafce4fab5e52f6b5fd3bf4b87e762dba77869c0c378f944c29309f364` | `J14.23 SDIO_~{RESET}` (reset/input)                                                       |
  | ColdFire/Xilinx: `kit-dev-coldfire-xilinx_5213/kit-dev-coldfire-xilinx_5213.kicad_sch` | `a1109092165ecec0d677142294330258c8990247e804f260d7682fda82602214` | `e1457386ac9585a4283d81f033b0f26a73b1476ed1b613ceab0d91e04efca280` | `VR201.4 SHDN` (enable/input)                                                              |
  | VME-WREN: `vme-wren/vme-wren.kicad_sch`                                                | `4cc3e74f2e47304bd3b360b18bab55d378573bc491b4f210aebe533890aa3dcb` | `aa2f6462f5f9d5c992651b98a79c9034f53c5852f0a131b45a751633be332c8a` | `IC19.3`, `IC21.3 ~{RESET}` (reset/input); `IC30.33 BOOT_B`, `IC30.38 BOOT_A` (boot/input) |

  All four results matched an exact candidate inventory on two exports. Parsed typed-netlist SHA-256
  values were `944f163ca7310f0202a415622088ebbe76d04e55142adc9316c1b24a80629854` (CM5),
  `3f38ebb7e494d63e8980133e1cba7a9c9f6aef34169b934ab67a32e58c69e1c6` (Jetson),
  `2f583eeb67a307249a7c2fd9fd90742b9c4eeeb93aba43e34478098006cc50e4` (ColdFire), and
  `e5ae2120d566f0e98c541dfaa82cc36324cbaeec8f71ca7f4d3c2edc0c67ecbe` (VME). Raw XML hashes are
  retained in lane events because repeated native exports can differ in non-semantic bytes. These
  examples demonstrate native sentinel parsing and bounded alias recognition; they do not establish
  that any candidate must be connected or measure false positives among deliberate no-connect
  control inputs.
- **Pinned native connected-bias screen (2026-09-30):** The same digest-pinned KiCad 10.0.5 image
  and four public demo netlists also exercised the new connected-input prompt. Repeated exports
  produced identical candidate inventories. Source-file and schematic-manifest hashes, raw XML
  hashes, and parsed-netlist hashes are listed above and retained in ignored
  `build/ci-hosted/native-control-input-demos/` receipts. The exact candidate summary hashes are
  asserted by the optional native test.

  | Public demo     | Net-level connected-input prompts | Candidate summary SHA-256                                          |
  | --------------- | --------------------------------: | ------------------------------------------------------------------ |
  | CM5 Minima      |                                 4 | `7c96b511e8fa95eef6dc8fff36c45e92c34e1cfbcc54db7400a2e3149fdd9709` |
  | Jetson AGX Thor |                                24 | `04bd60403bf87f8a4edf249d582a5b7620974dd333b53e5e80c6db9af8dc9f71` |
  | ColdFire/Xilinx |                                 2 | `371dfc8d9313aabf215947750e2ad170d9c5b69f6f03a171ae90e81a73bfb929` |
  | VME-WREN        |                                12 | `2ee541b32622143b5293f6add4da0d0c6b32137ec15521fd2bafb6fe9e3df050` |

  The 42 findings are net-level review prompts, not confirmed defects or a precision estimate. Some
  designs may rely on internal bias, resistor arrays, a connected driver, or other reviewed
  circuitry that the bounded resistor-path predicate does not resolve. This screen measures
  candidate volume and repeatability only.
- **Pinned native revalidation (2026-10-03):** The
  `tests/test_ci_hosted_control_inputs.py::test_native_public_demos_record_connected_bias_and_unconnected_controls`
  lane passed locally with one test and five subtests. It used exact KiCad 10.0.5 from the
  digest-pinned image recorded in the
  [synthetic alias fixture notes](../tests/fixtures/design_lint/control-input-alias/README.md). The
  `POR_B`/`PORN` source exported twice with the same normalized typed-netlist digest; exact pin
  functions and `input` types were preserved, both pins were unassigned, and only `U1.1 POR_B`
  became a reset candidate. Four public demos also reproduced their source hashes, parsed-netlist
  hashes, candidate inventories, and connected-bias summaries. Receipts are under ignored
  `build/ci/` paths. The lane exports netlists only; it does not run ERC/DRC.
- **Rule-scoped native selection (2026-10-20):** The same public demos and
  synthetic `POR_B`/`PORN` and reset-bias-chain fixtures passed with exact
  KiCad 10.0.5: one test and six subtests, with repeated normalized netlists
  and all expected
  candidate inventories. The connected-input screen reports 42 net-level
  bias candidates across the four demos; 7 candidate nets include a native
  output-capable peer (CM5 2/4, Jetson 3/24, ColdFire 0/2, VME 2/12). These
  counts measure review workload only; pin-type metadata does not establish an
  active driver or a false positive. The native demo test is now registered as
  a fault fixture for both control-input rules, and both rules require
  `KICAD_RUN_NATIVE_CONTROL_INPUT_FIXTURES`. Focused collection selects this
  same native test for either rule, so prerelease rule tags exercise the demo
  lane even when the full package job is skipped. Hosted acceptance for
  `v0.5.2rc42` passed (GitHub Actions run 39422510660):
  the focused rule gate and installed-wheel check against the separate public
  template passed, as did Ubuntu, macOS, and Windows previews. The package job
  was skipped under prerelease policy.
  Hosted acceptance for `v0.5.2rc43` also passed (GitHub Actions run 39423202370):
  the connected-bias rule gate and installed-wheel check against the separate
  public template passed, as did Ubuntu, macOS, and Windows previews. The
  package job was skipped under prerelease policy.
- **Pytest selection update (2026-10-20):** The native control-input lane now
  exposes each of six public and synthetic samples as an independent
  parameterized pytest case. The active-rule catalog points to the top-level
  pytest function, and architecture tests keep this suite free of
  `unittest.TestCase`. The first pytest migration still exported all six
  samples for a single `-k` selection. The runner now filters to the selected
  sample IDs while retaining one exact-version, read-only container for the
  selected set. `-k series-bias-fixture` selected one test, deselected five,
  and passed in 1.64 seconds; its setup took 1.62 seconds versus 14.42 seconds
  when the earlier fixture exported all six. The full connected-bias rule
  selector passed 15 tests with 3,852 deselected; all six sample cases shared
  one native run.
- **Hosted prerelease acceptance (2026-10-20):** Tag `v0.5.2rc45` passed the
  focused rule gate and installed-wheel check against a separate public
  project checkout (GitHub Actions run 39430522860). Windows, Ubuntu, and
  macOS preview orchestration also passed. The package job was skipped under
  prerelease policy.
- **Selected native-sample execution (2026-10-20):** Tag `v0.5.2rc46` passed
  the focused connected-input rule gate and installed-wheel check against a
  separate public project checkout (GitHub Actions run 39431831959). Windows,
  Ubuntu, and macOS preview orchestration also passed. The package job was
  skipped under prerelease policy. The local selector `-k
  series-bias-fixture` ran one native sample and deselected five; selecting the
  whole rule retained a single shared native export for all six samples.
- **Series resistor-path extension (2026-10-20):** The connected-input
  heuristic now recognizes a fitted direct resistor or an unbranched series
  chain to a bounded positive or return net, using the shared
  `visible_resistor_paths` service. No resistance window is implied. Synthetic
  tests cover both rail polarities and keep branched, DNP, and zero-ohm paths
  reviewable. A separate tooling-owned reset schematic passed repeated native
  netlist export on exact KiCad 10.0.5, with exact `RESET_N`/DNP assignments,
  a two-pin `RESET_BIAS_MID`, and no bias candidate; its normalized typed
  netlist hash is
  `7460ef30a887211f4bc8f8ef86ecc68e8220d7edfd131a1a86e7aa356f40a99b`.
  The four public-demo inventories remained at 42 review prompts; that volume
  is not a false-positive measurement. This extends topology recognition and
  does not change default `REVIEW` policy or establish resistor adequacy.
- **Hosted prerelease acceptance (2026-10-20):** Tag `v0.5.2rc44` passed the
  focused rule gate and installed-wheel check against a separate public
  project checkout (GitHub Actions run 39428774039). Windows, Ubuntu, and
  macOS preview orchestration also passed. The package job was skipped under
  prerelease policy.
- **Remaining:** The native results validate evidence parsing and bounded
  aliases, not design intent. Public demo screens do not label intent, and
  connected-bias candidate volume is not a false-positive measurement.
  Independently reviewed connected-bias and intentional-NC cases remain open;
  collect dispositions before estimating precision or widening the alias set.

#### LINT-018 — Test-point and programming-access coverage

- **Status:** Implemented v4. The schematic, PCB pad-surface, and optional
  probe envelope checks are reported separately. Each endpoint can require
  front, back, or either exposed board side. Envelope values are project-
  authored and use deterministic KiCad 10 pad geometry.
- **Problem:** Required rails, programming signals, or factory measurement
  nodes may lack an accessible, project-approved test point.
- **Evidence and check:** `test_access` declares each in-scope net as either
  requiring one or more exact test-point/programming/factory connector pins,
  or explicitly not requiring access with a review reason. Its separate
  schematic stage checks component identity, DNP state, native pin inventory,
  electrical type, and exact net assignment. The optional, independently
  required PCB stage checks the exact placed footprint/pad, expected net, and
  outer copper plus the corresponding solder-mask layer declaration on the
  project-selected approach side. An optional circular probe envelope measures
  from that pad center to the nearest fitted, mask-layer-assigned different-net
  pad on each requested side. Native KiCad evidence also measures the target
  aperture for circular, undrilled pads from the pad size and its resolved
  solder-mask expansion. The target aperture must fit the project-authored tip
  diameter plus twice its edge clearance; foreign-pad clearance must fit the
  authored tip radius plus edge clearance. Requirements
  round upward to a whole nanometer; measured distances round down to avoid an
  optimistic floating-point boundary result. For a circular pad, the native
  probe uses its layer-specific copper size plus KiCad's resolved
  `PAD.GetSolderMaskExpansion` value in the [KiCad 10 PAD API][kicad10-pad].
- **Boundary:** The envelope scan skips DNP and same-net pads. Only circular,
  undrilled target apertures have a deterministic fit measurement; other
  shapes and drilled pads remain unproven and fail the configured requirement.
  The check does not inspect exposed tracks, vias, copper-zone mask openings,
  component bodies, fixtures, covers, mechanical reach, or manufacturing test
  coverage. A pass is limited to the measured target aperture and pad-neighbor
  geometry on the exact source board.
- **Regression evidence:** Unit controls cover front/back/either side selection,
  exact and one-nanometer-inside threshold boundaries, and missing/partial
  observations. An end-to-end synthetic receipt test covers request tampering,
  retained replay, aperture and clearance boundary faults, unsupported-shape
  handling, and CLI/MCP parity. The digest-pinned native fixture lane exercises
  a packaged synthetic PCB through KiCad 10.0.0 or 10.0.5, asserting exact
  front/back obstacle identity and distance, circular mask aperture bounds,
  same-net/DNP exclusion, unconnected-pad reporting, unavailable-side handling,
  undersize and exact-boundary aperture controls, unsupported rectangular and
  drilled target pads, expected rule results, and repeatability across
  identical loads.
- **Done when:** The KiCad 10 schematic and PCB stages are independently
  reported, exact endpoint mapping is source-bound, all fixtures pass, and
  configured probe-envelope rules have reviewable, replayable geometry. The
  supported board-object scope and native API behavior are exercised on
  synthetic fixtures.
- **Future scope:** Evaluate oval, rectangular, and custom pad aperture fit
  only when native geometry supports a conservative exact measurement. Tracks,
  vias, zone openings, and mechanical obstruction remain separate bounded
  checks; do not infer overall physical accessibility from pad spacing.

#### LINT-084 — Fitted two-pin fuse bypassed by one net

- **Status:** Implemented as `component.two_pin_fuse_same_net`, a configurable
  default-review hint with exact component, symbol, pin, and net evidence.
  It extends the shared two-pin inventory reader without changing the
  resistor/capacitor/inductor or diode rule dispositions.
- **Priority:** P1 power-path regression coverage. LINT-056 already recognizes
  exact `Device:Fuse` and `Device:Polyfuse` symbols as possible series path
  elements. A source review found that the same-net detector used for passives
  and diodes did not inspect those protection parts; a fuse assigned to one
  net can be bypassed without violating schematic netlist syntax.
- **Predicate:** For fitted exact `Device:Fuse` and `Device:Polyfuse` family
  symbols, require exactly two distinct native pin numbers and one unambiguous
  assigned net per pin. Report when those two pins use the same net. DNP parts,
  custom libraries, incomplete or multi-pin inventories, open pins, and
  ambiguous assignments are outside the predicate.
- **Boundary:** A bypassed fuse may be a deliberate configuration or assembly
  choice. The finding does not infer that every fuse must be in series, assess
  fuse current or interruption ratings, or prove footprint and PCB copper
  behavior. Keep the default at `review`; use project policy for any stronger
  disposition.
- **Fixtures:** Same-net and distinct-net native schematic cases for both fuse
  families; DNP, incomplete, ambiguous, multi-pin, and custom-symbol unit
  controls; review/block/off/exact-ignore lifecycle; per-component split and
  order-stability metamorphic tests; CLI/MCP parity; repeated source-bound
  exports on pinned KiCad 10.0.0 and 10.0.5. The synthetic sources and
  reproduction record are in the
  [two-pin fuse fixture README](../tests/fixtures/design_lint/two-pin-fuses/README.md).
- **Local evidence (2026-10-07):** The focused fuse/catalog/CLI-MCP/determinism
  command passed 480 tests and 646 subtests; surface and script-architecture
  checks passed 25 tests and 308 subtests. The new report stayed identical
  across three independent Python hash secrets. These results validate the
  shared typed service and adapters, not native source export.
- **Supplemental native screen (2026-10-08):** The RC3 and RC4 command receipts
  show the pinned KiCad 10.0.0 and 10.0.5 lanes stopping at
  `two-pin-crystals/distinct-nets-crystal.kicad_sch`, before any fuse fixture is
  reached. The crystal control had `page` outside the root `path` in its
  `sheet_instances` form. The source now uses the same nested form as its fault
  control and other accepted fixtures; its reviewed source hash is updated in
  the crystal README and test manifests. Local KiCad 10.0.6 exported the fixed
  control twice with the same normalized typed-netlist digest
  `b489d9e0960c31e0b98aa9da98627e2762a1b97cd5f136291672a83324b2f3c9`; it
  produces no same-net crystal candidate and the lint report passes. The RC5
  GitHub package lane then passed the crystal, fuse, and polyfuse native
  fault/control exports on pinned KiCad 10.0.0 and 10.0.5, including repeated
  normalized-netlist checks.
  Local KiCad 10.0.6 also exported all four fuse sources twice with identical
  normalized typed-netlist digests:
  - Fuse fault: `368263f15c0627efc7a5f4b58a0b0beddda1dbe4b2d72522d6f24562a98a2a14`
  - Fuse control: `e2172e8968c16de62855b6ef43ac4b5dd891ef753436133c864932b3e97ec72c`
  - Polyfuse fault: `ff8e60df2a6775da8467b094f760a6b52371c809c4c6ce6d7499b9773a4932ca`
  - Polyfuse control: `3cc9839cf451122932c229975be7fad33c7575d8cfa15f07f02823c975146061`
  The fault cases each produce one REVIEW finding; both controls pass. RC5 also
  passed the native geometry checks on KiCad 10.0.5 and 10.0.6. Its package job
  completed all 2,238 tests (2 skipped) and then failed only at Ruff formatting
  in `tests/test_serial_peer_reference_review.py`; RC6 carries that formatting
  correction for a full candidate rerun.
- **Release-candidate regression (2026-10-08):** The `v0.5.0rc1` package job
  ran 2,236 tests (2 failures, 3 errors, 2 skipped). The connector fixture
  expected one lint rule ID even though LINT-089 emits one finding per open
  pin; the assertion now checks both per-pin findings. `v0.5.0rc2` passed all
  three portability preview jobs; its package job ran 2,236 tests and had only
  the two pinned native fuse-fixture errors remaining. `v0.5.0rc3` also passed
  all three preview jobs; its package job had the two native fixture errors.
  RC3 and RC4 command receipts stop at the malformed distinct-net crystal
  control before reaching the fuse cases. RC4 ran 2,238 tests with two errors
  and two skips; RC5 carries the corrected crystal source structure. RC5 ran
  2,238 tests successfully (2 skipped), passed pinned KiCad 10.0.0/10.0.5
  native fault/control exports plus the 10.0.5/10.0.6 geometry checks, and then
  failed at the repository Ruff formatting gate. RC6 contains the formatter's
  correction and must pass its full package workflow before this candidate is
  considered green.
- **Local package smoke (2026-10-08):** After the fixture correction,
  `scripts/ci.py` passed all 2,236 tests with 25 environment skips, formatting,
  Ruff, Linux and Windows type checks, Markdown, repository links, wheel/sdist
  reproducibility, a fresh installed-wheel check, and external inventory,
  verify, adaptation, and playtest stages against a separate public template
  checkout. The sandboxed package run could not access the Docker socket; the
  exact KiCad 10.0.0/10.0.5 matrix was subsequently exercised by the RC5
  GitHub package lane and rerun locally with Docker access on 2026-10-08 below.
- **Acceptance-lane integrity (2026-10-07):** The shared native-fixture
  manifest mounts `tests/fixtures/design_lint` as its read-only root so both
  `two-pin-components/` and `two-pin-fuses/` sources resolve. An always-run
  test checks each registered source path before the optional Docker lane.
  The 10.0.6 screen at that time covered the original eight passive, diode,
  fuse, and polyfuse fault/control sources; the revised fuse sources are
  covered by the 2026-10-08 screen above. Those local screens did not replace
  pinned acceptance; the RC5 GitHub run recorded above supplies that evidence.
- **Exact-version local rerun (2026-10-08):** The current synthetic native lane
  passed on digest-pinned KiCad 10.0.0 and 10.0.5: 1 test and 30 subtests.
  Both same-net fuse and polyfuse cases reported `REVIEW`; their distinct-net
  controls passed. Every export repeated with the expected normalized
  netlist. The corrected crystal fault/control, ferrite fault/control, and
  switch fault/control also passed in the same lane.
- **Hosted acceptance status (2026-10-12):** Tagged run `38288390151` on
  `v0.5.0rc176` passed its focused prerelease lint gate, but the workflow's
  full `package` job was skipped. The earlier RC5 native lane passed, while
  its package job stopped at Ruff; no later full-package result is recorded
  in this entry.
- **Rule-scoped selector (2026-10-12):** `component.two_pin_fuse_same_net`
  now points to a native test that selects only the fuse/polyfuse same-net
  faults and distinct-net controls. The local rule selector passed seven
  tests with two exact-native cases skipped because Docker socket access was
  denied. Tagged run `38292257528` on `v0.5.0rc177` then passed the focused
  gate with the native fixture switch enabled, covering the fuse/polyfuse
  faults and distinct-net controls on KiCad 10.0.0 and 10.0.5. The separate
  installed-wheel check against the external template and all three portability
  previews also passed; the full `package` job was skipped by RC policy.
- **Remaining:** Complete full package acceptance. The focused tagged lint
  gate does not replace that acceptance.

#### LINT-085 — Fitted two-pin ferrite bead bypassed by one net

- **Status:** Implemented as `component.two_pin_ferrite_same_net`, a
  configurable default-review hint using the shared exact two-pin inventory.
- **Priority:** P1 power and filter-path regression coverage. Cohort path
  checks treat ferrite beads as series elements, while the local default
  same-net rules previously covered resistors/capacitors/inductors, diodes,
  and fuses. A schematic can assign both pins of a fitted ferrite to the same
  net without native ERC identifying that the bead is bypassed.
- **Predicate:** For fitted exact `Device:FerriteBead` and
  `Device:FerriteBead_Small` symbols, require exactly two distinct native pin
  numbers and one unambiguous assigned net per pin. Report only when both pins
  use the same net. Other symbol variants, DNP parts, custom symbols,
  incomplete or multi-pin inventories, open pins, and ambiguous assignments
  are outside the predicate.
- **Boundary:** A same-net bead may be an intentional bypass or assembly
  option. The finding does not infer that a bead is required, assess its
  impedance or filtering performance, or prove footprint or PCB-copper
  behavior. Keep the default at `review`; use project policy for any stronger
  disposition.
- **Fixtures:** Synthetic same-net and distinct-net schematics with the exact
  `Device:FerriteBead` identity and typed coverage of `Device:FerriteBead_Small`;
  typed controls for DNP, incomplete, ambiguous,
  multi-pin, unassigned, and custom-symbol cases; review/block/off/exact-ignore
  lifecycle; per-component split and order-stability metamorphic tests;
  CLI/MCP parity; and repeated native exports on the pinned KiCad 10.0.0 and
  10.0.5 acceptance images. The synthetic source and reproduction record are
  in the [two-pin ferrite fixture README](../tests/fixtures/design_lint/two-pin-ferrites/README.md).
- **Local evidence (2026-10-07):** The focused ferrite/catalog/determinism/
  parity/manifest suite passed 516 tests and 661 subtests. Three independent
  Python hash-seed processes emitted identical full reports for same-net fault
  and distinct-net control cases. The locally installed KiCad 10.0.6 CLI
  exported both synthetic source fixtures twice; their normalized netlists
  repeated identically. The fault reports one `component.two_pin_ferrite_same_net`
  review and the distinct-net control reports none. Source hashes are
  `8ede05ea1d9c8afb0cec2f1c8c9bddf527eab015ab779097f4ddc528866751f7` (fault)
  and `199c802ca290b1281622c623f4966b159144f0e95fd99ed0e21a14a0875734a7`
  (control); normalized typed-netlist hashes are
  `cd1fc58eaf995a64f996aa43b8267cd955f7dc5b51bbae98da68d44fca28e415` and
  `01114175c5d792671ffc261fa3f919eeaa18bc892ad6e92478c5c06221c5cecc`.
  KiCad 10.0.6 ERC also returned zero diagnostics for both sources, so ERC did
  not distinguish this topology fault from its valid control. These results
  validate the typed rule, adapters, and 10.0.6 compatibility, not a real
  ferrite part or filter performance.
- **Exact-version local rerun (2026-10-08):** The current native lane passed on
  both digest-pinned images. The same-net fault reported one
  `component.two_pin_ferrite_same_net` review and the distinct-net control
  reported none. Repeated normalized netlists matched.
- **Hosted acceptance status (2026-10-12):** Tagged run `38288390151` on
  `v0.5.0rc176` passed its focused prerelease lint gate, but the workflow's
  full `package` job was skipped. The exact-version ferrite native cases have
  local pinned-version evidence; this tagged run supplies no hosted full-package
  result for them.
- **Rule-scoped selector (2026-10-12):** The ferrite rule now catalogs a
  dedicated exact-native test and requires
  `KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES`. Its selection contains only
  the same-net fault and distinct-net control. The local rule selector passed
  six tests with two exact-native cases skipped and 3,099 unrelated tests
  deselected because Docker socket access is denied locally. The hosted tagged
  run `38292936740` on `v0.5.0rc178` passed the exact-native lane for KiCad
  10.0.0 and 10.0.5, the installed-wheel check against the external template,
  and all three portability previews. The full `package` job was skipped by
  RC policy; RC177 selected the fuse rule and did not exercise ferrite.
- **Remaining:** Complete full package acceptance.
- **Cohort boundary:** This is a first-party deterministic extension prompted
  by the inspected series-path concept. No third-party source, board, fixture,
  or install workflow was copied.

#### LINT-086 — USB peers use different explicit reference nets

- **Status:** Implemented as `bus.usb_peer_reference_review`, a configurable
  default-review hint for supported USB 2.0 and direct USB SuperSpeed paths.
  The USB data-path map can record a reviewed USB 2.0 or direct SuperSpeed
  `common_net`, `separate_nets`, or `bonded` reference decision and verify its
  exact endpoint pins and nets against the native netlist. A `bonded` entry
  additionally maps one exact passive two-pin component, value, footprint, and
  side nets.
- **Priority:** P1 connectivity review. LINT-074/LINT-082 cover UART peers,
  and LINT-049 covers a project-mapped USB data topology; neither notices a
  supported USB connector-to-IC path when connector and PHY reference pins use
  separate explicit nets and no matching reference policy has been authored.
- **Predicate:** USB 2.0 behavior remains unchanged: recognize direct D+/D−, unnumbered UD+/UD−, and
  numbered hub pairs DPn/DMn or USBnD+/USBnD-; support direct, one fitted complete two-pin
  `Device:R` per line, one exact mapped inline component, or a direct path with exact mapped
  protection shunts. Preserve exact pin inventories, net members, and explicit reference-pin
  evidence. Separately, recognize direct USB SuperSpeed P/N pairs when native endpoint pin metadata
  is complete, exactly one positive and negative pin exists per family, connector TX connects to PHY
  RX or connector RX to PHY TX, and each data net contains exactly those two pins. Both endpoint
  references must have explicit bounded return-like pin functions on one net per endpoint. Their
  native electrical types must be passive or power_in, or `unspecified` paired with an explicit
  return-like function such as VSS. The uncertainty remains visible in the review evidence. A
  differing pair of reference nets produces a review; a common reference is quiet. An exact
  `superspeed_interfaces` map can cover a reviewed direct SuperSpeed pair only
  when its endpoint identities, complementary P/N pins and nets, reference-pin
  inventories, and common/separate/bonded decision match. Stale mapped
  expectations produce `bus.usb_data_path_mismatch`. SuperSpeed names are the bounded
  SSTX/SSRX and StdA/StdB aliases documented by the
  [USB-IF Front-Panel Implementation Document](https://www.usb.org/sites/default/files/USB3p1_Front_Panel_CabCon_Implment_Doc_Rev1p1.pdf).
- **Boundary:** Separate nets may be intentional, joined through a reviewed
  bond, or intentionally isolated. This rule asks for review; it does not say
  grounds must be tied. It does not infer unlisted or multi-hop bond paths,
  multiple series components,
  arbitrary extra peers, unmapped multi-pin protection arrays as supported
  paths, lane-indexed
  USB-C pairs, muxes, retimers, other SuperSpeed multi-lane paths, off-board
  wiring, or PCB copper. It does not infer resistor suitability or protection
  performance. `data_port_group` scopes numbered USB 2.0 PHY inventory to one
  pair. The `superspeed_interfaces` map covers exact direct SuperSpeed paths;
  stale or absent maps leave the default REVIEW prompt active. Projects can use
  the rule-level override or a reasoned exact ignore for another reviewed case.
  Incomplete pin inventories, mixed reference domains, DNP
  endpoints or branch parts, shield/chassis/frame/PE functions, and ambiguous
  assignments are skipped. A source-reviewed USB 2.0 or SuperSpeed map
  suppresses the prompt only when connector and PHY identities, supported data
  topology, complete reference-pin inventories, and explicit reference decision
  all match. For
  `bonded`, `bus.usb_data_path_mismatch` separately reports a missing, DNP,
  identity-mismatched, or incorrectly assigned bond; this netlist comparison
  does not prove component conduction or PCB copper.
- **Unsupported-topology coverage:** When one unmapped multi-pin component has
  assigned native pins on both connector-side and PHY-side nets for both
  D+/D−, the typed coverage report records the endpoint pair, component
  identity, inventory size, port group, and exact component pins/net names.
  This is coverage-only evidence: it does not claim that the component passes
  USB data, count the pair as a supported path, or create an electrical
  finding. Other unsupported arrangements can remain unreported. A current
  exact project-authored map remains necessary to evaluate this topology.
- **Fixtures:** Synthetic split-reference fault and common-reference control,
  including native `UD+`/`UD−` PHY-pin aliases and a VSS return pin whose native
  electrical type is `unspecified`; a matching common-reference control and a
  typed non-return `unspecified` pin control keep the acceptance bounded;
  exact mapped inline-protection split-reference fault, common-reference and
  explicit separate-reference controls, plus unmapped-array and extra-peer
  controls;
  two connectors to one numbered hub with per-port evidence, a shared-
  reference control, a crossed-channel control, an unused-port control, and
  exact `data_port_group` maps. A typed three-port regression also checks one
  split-reference review per connector, exact-map suppression, a common-reference
  control, and stable path ordering. The exact-version native lane now also
  includes three-port fault/control schematics: J1/J2 remain common while only
  J3 port 3 is split, and the control common-refs all three ports. See the
  [three-port USB fixture record](../tests/fixtures/design_lint/usb-threeport-peer-reference-native/README.md).
  USB-C duplicated A/B data contacts with two-pin shunt branches and common/split
  reference controls; exact USB-map contact coverage; arbitrary-peer,
  unsupported-branch, split-duplicate-pin, multi-reference-PHY, and isolator-path
  controls;
  stale identity/net faults; exact ignore, review/block/off, input reordering
  and commoning mutation; CLI/MCP parity; direct SuperSpeed TX-to-RX fault,
  common-reference control, exact separate/common/bonded map coverage, stale
  mapped pin/net/identity faults, full-duplex mapping, CLI/MCP parity, and
  same-direction/reversed-polarity/extra-peer and incomplete-metadata
  boundaries; three-process hash-seed determinism; repeated source-hashed native
  exports on the digest-pinned KiCad 10.0.0 and 10.0.5 lane. The typed-netlist
  multi-reference control gives one PHY two explicitly named return pins on
  separate nets and confirms the bounded predicate skips it.
  **Current VSS/unspecified extension (2026-10-20; exact-version acceptance passed):**
  deterministic USB 2.0 and SuperSpeed regressions preserve REVIEW for split
  references, keep a shared reference quiet, and reject an unspecified non-return
  pin. CLI/MCP parity passes on the public template pinned by CI. Local KiCad
  10.0.6 export preserves the native VSS function and unspecified type on both
  synthetic fault/control nets. Tagged acceptance on `v0.5.2rc7` passed the
  exact KiCad 10.0.0/10.0.5 fixture lane; 10.0.6 remains compatibility
  evidence only.
  The two-port hub source-to-netlist cases are documented in the
  [multiport USB fixture README](../tests/fixtures/design_lint/usb-multiport-peer-reference-native/README.md).
  The exact-map extension adds a valid 0R bond control and faults for an absent
  bond, wrong value, symbol, footprint, DNP state, active pin type, and wrong
  side net. CLI and MCP return identical fault evidence. A source-hashed
  native 0R control is registered in the same KiCad 10.0.0/10.0.5 fixture lane;
  it was initially unrun locally and is included in the current native run
  recorded below. A typed exact-map composition case verifies that an inline
  protection path with a reference ferrite remains outside the heuristic review
  count, while LINT-049 reports missing, miswired, or DNP ferrite faults. A new
  typed synthetic-netlist regression covers an exact six-pin protection shunt
  map, split-reference review, common-reference control, stale identity and
  pin/net/no-connect maps, an unmapped array, and unexplained extra peers.
  Three source-hashed synthetic schematics for split-reference review,
  common-reference control, and a wrong shunt-pin assignment are now registered
  in the digest-pinned KiCad 10.0.0/10.0.5 lane. Exact local native execution
  is unavailable in the current environment; the hosted result is recorded in
  Evidence history below. The existing six-pin inline-protection source is also
  evaluated with its exact map and again without a map: the mapped control stays
  supported, while the unmapped report is expected to retain exact U2/D+/D−
  pin/net evidence, zero supported paths, and no USB peer-reference or data-path
  finding. This source-hashed comparison is registered for both pinned KiCad
  versions; its tagged hosted acceptance is recorded in Evidence history below.
- **Evidence history:**

  **Three-port native fixture (2026-10-20; local compatibility):** The new
  source-hashed J1/J2/J3 hub fixture exported twice with KiCad 10.0.6. Both
  normalized typed-netlist hashes repeated, each authored map matched all three
  data paths, and the split-reference fault produced only the J3/U1 port-3
  peer-reference finding; the common-reference control produced none. The
  normalized hashes are `5d9c692a866f5be8bcaea25a1b8a0e17ad027d34283022b3d71048a7b5d59e72`
  (fault) and `fbdfff8ac4a244c36374bcd728d76b98ce6999323156e69edad1b316c83a4bd8`
  (control). The source cases are registered for the digest-pinned KiCad
  10.0.0/10.0.5 lane. This does not establish PCB copper or physical return
  continuity.

  **Tagged hosted acceptance (2026-10-20):** `v0.5.2rc40` (commit `952f03c`,
  run `39418812542`) passed the focused `bus.usb_peer_reference_review` gate
  with `KICAD_RUN_NATIVE_USB_DATA_PATH_FIXTURES=1`. The three-port J1/J2/J3
  fault and control ran on digest-pinned KiCad 10.0.0 and 10.0.5; both matched
  three supported data paths, only the J3/U1 port-3 fault prompted, and both
  exports repeated with matching normalized netlist contracts. The scoped
  installed-wheel check against an external project and all three platform
  preview jobs passed. The separate package job was skipped. This is synthetic
  schematic-export and packaging evidence, not PCB copper or physical return
  continuity.

  **Tagged exact-version acceptance (2026-10-20):** `v0.5.2rc7` (commit
  `eea03f6`, run `39375741595`) passed the focused
  `bus.usb_peer_reference_review` gate with
  `KICAD_RUN_NATIVE_USB_DATA_PATH_FIXTURES=1`. Both USB 2.0 data-path and
  SuperSpeed native fixture lanes ran on digest-pinned KiCad 10.0.0 and 10.0.5,
  including the new VSS/unspecified controls, source-hashed protection-shunt
  cases, exact 0R bond control, and mapped-versus-unmapped protection coverage.
  The installed-wheel rehearsal and Linux, macOS, and Windows preview jobs
  passed; the separate `package` job was skipped.

  **Tagged hosted acceptance (2026-10-19):** `v0.5.1rc50` (commit `8dacb2a`)
  passed GitHub Actions run `39334092708`. The scoped
  `bus.usb_peer_reference_review` gate passed, including the source-hashed
  inline-component fixture on digest-pinned KiCad 10.0.0 and 10.0.5. The
  unmapped U2 case remained coverage-only, with zero supported data paths and
  no USB peer-reference or data-path finding. Its repeated normalized netlist
  contract matched the mapped control; the synthetic typed-netlist regression
  checks the exact D+/D− pin and net assignments. Wheel, sdist, fresh install,
  and external-project inventory, surface, verification, and playtest stages
  passed. This accepts the bounded synthetic check, not arbitrary multi-pin
  path behavior or PCB/physical continuity.

  The predicate, tests, and native fixture sources were already in this branch
  before the alias extension. The pinned lane was wired into the existing USB
  export job but had not run locally at that earlier checkpoint;
  no GitHub result had been recorded for the then-dirty branch. Before the series-path
  extension, the full Python suite passed on 2026-10-07 with the public
  `KiCAD-Test` reference checkout pinned
  at `ed89536f0dbbcb013145af2994fef41b2250143e`: 2,139 tests passed, 49
  environment-gated tests skipped, and 2,368 subtests passed. This includes
  the typed fault/control, catalog-registration, and CLI/MCP parity cases; it
  does not count as native export evidence. After the extension, the focused
  USB peer/data-path suites pass 23 tests and 5 subtests; the grouped lint and
  catalog suite passes 632 tests and 751 subtests. The hosted test module passes
  22 tests and 26 subtests, with its 21 environment-gated cases skipped. A local
  KiCad 10.0.6 export on
  2026-10-07 exposed that the earlier synthetic USB-A fault/control fixture
  ground labels missed their pin endpoints; the fixture sources were corrected
  and now export the intended split and common assignments. Repeated local
  10.0.6 exports of the corrected USB-A and new USB-C cases produced stable
  typed netlist contracts and the expected fault/control results. This is
  compatibility evidence only. At the time these local exports were recorded,
  the exact hosted 10.0.0/10.0.5 lane was pending; its later acceptance is
  recorded below. All fixture sources contain only synthetic
  connector, PHY, resistor, diode-designated branch, and net labels. A
  repeatable local KiCad 10.0.6 export of the series-resistor common-reference
  control and split-reference fault checks the expected GND assignments, one
  review on the split case, and exact R1/R2 pin-to-net evidence. Repeated raw
  netlist hashes are `3931bb9750cf73cf7dcb9f4542c9712e726b49cf5c13d16134b6f4ac9fb4e944`
  (control) and `c6f6fc4b6e42a8a0ab88cf52942b22add8cfd6e9789492f4a70ffc0100970eb2`
  (fault); normalized typed-contract hashes are
  `7c0d218af14fbaeac493684b4bf85ff06d9b0185f6b8db1cd55c54f41669aef7`
  and `1bbada6fd675460660ee6f934185f4d74147b09a016df3831b9571369456bfeb`.
  This is compatibility evidence; exact KiCad 10.0.0/10.0.5 results remain
  pending. The numbered multiport extension was then checked on the local
  KiCad 10.0.6 CLI. The synthetic DP1/DM1 + DP2/DM2 hub fault reports exactly
  one reference-domain review for each matching connector port; the shared
  reference control reports none. Repeated raw netlist hashes are
  `55cc69c350b65d919df34828649a1957bf673fe8175f0fb3e0b314cc2d8f5466`
  (fault) and `1c3326e032210500094ee60f5cdf66c1074cb7caeb3a61a2d77a8724196aeaae`
  (control); normalized typed-contract hashes are
  `62381ebb9c73b28762e759b7ad4c8d4ccee102ace693d3917a1d8b1874e428c4` and
  `b5562947696ab4d4163687ee3e091ec608cc883c7892f035a2979bdd1eb74ea0`.
  The focused USB, data-path, CLI/MCP parity, lint determinism, and catalog
  run passes 523 tests after this extension. Ruff check, format check, and
  `git diff --check` pass. These local checks do not replace the digest-pinned
  KiCad 10.0.0/10.0.5 hosted acceptance lane. At the time, no GitHub result
  was recorded for this dirty branch; the same fixture and heuristic sources
  later passed in tagged `v0.5.0rc15`, as recorded below.
  The hosted test module was also rerun after adding the multiport case registry:
  43 tests ran: 22 passed and 21 native acceptance-gated tests were skipped.
  The Docker daemon was unavailable for that local run, so those local exports
  were pending at the time. The hosted exact-version result is recorded below.
  On 2026-10-08 the full repository suite passed 2,184 tests with 25
  environment-gated skips. `KICAD_TEMPLATE_ROOT` pointed to the public
  KiCad-Team-Workflow-Template checkout at
  `ed89536f0dbbcb013145af2994fef41b2250143e`, and loopback access was enabled
  for its HTTP tests. The run includes the expanded multiport and isolator
  boundary controls, CLI/MCP, catalog, and determinism coverage. The exact
  digest-pinned 10.0.0/10.0.5 native acceptance lane was pending at the time
  because Docker was unavailable locally; hosted acceptance is recorded below.
  Typed-netlist controls give U1 two explicit reference pins on separate nets
  and model an isolator between host and device sides; the USB rule stays quiet
  in both cases. Added coverage tests distinguish no endpoints, incomplete
  endpoint evidence, common-reference paths, split-reference candidates,
  source-mapped split paths, unsupported data paths, and DNP endpoint
  dispositions. Cross-process hash-seed assertions exposed that the earlier
  synthetic multiport common-reference helper overwrote J1's pin when it used
  the same net key twice; the helper now aggregates every assigned reference
  pin. Its valid control reports two common-reference paths and zero review
  candidates. The focused USB module passes 23 tests, the catalog suite passes
  501 tests, the focused CLI/MCP parity case passes, and the three-process
  hash-seed comparison is stable. These checks add no native-export result; the
  2,184-test full run predates the coverage-report change.
  On 2026-10-07, the mapped bonded-reference fault also passed an in-process
  input-reordering comparison and the existing three-process hash-seed report
  probe. The focused USB module passed 11 tests, the determinism module passed
  its cross-process test, the catalog module passed 505 tests, and Ruff check
  and format checks passed. These typed-netlist results predate the exact
  hosted native acceptance recorded below.
  After adding deterministic per-path coverage entries on 2026-10-08, the full
  pytest suite passed with 2,262 tests, 54 environment-gated skips, and 1,963
  subtests. The package acceptance driver passed Ruff, strict Pyright, Windows
  typing, `rumdl`, `mdrepo`, wheel/sdist construction, reproducible wheel rebuild
  from the source distribution, fresh-environment installation, and CLI/MCP
  checks against the public reference checkout and a relocated copy. Its
  external portable verification and playtest also passed. This local run
  proves package and source-level behavior; the exact-version native fixture
  results are recorded below. It does not test physical return continuity.
  The hosted tag run then passed as `v0.5.0rc17` (run `37863872527`). Its
  package suite reported 2,290 passed, 26 skipped, and 2,044 subtests passed;
  `test_native_usb_data_path_fixture_lane_is_repeatable` ran on digest-pinned
  KiCad 10.0.0 and 10.0.5.
  The direct split-reference fault prompted review, its common-reference
  control stayed quiet, the USB-C fault/control behaved as registered, and the
  two-port fault produced two per-port reviews while its common control stayed
  quiet. Repeated normalized netlists matched for every registered case. This
  closes the native schematic-export check for these synthetic fixtures; it
  still does not test PCB copper or physical continuity.
  On 2026-10-09 the three public common-reference screens were also re-exported
  twice in digest-pinned KiCad 10.0.5. All normalized typed contracts matched
  their earlier 10.0.6 results, and each synthetic split-reference mutation
  produced one stable review. The container ran as `linux/amd64` on a
  `linux/aarch64` Docker host. This adds repeatable public-source applicability
  evidence; author dispositions and reviewer time are still unmeasured.
  The existing `test_native_usb_data_path_fixture_lane_is_repeatable` also
  passed locally on the same host with the public template pinned at
  `ed89536f0dbbcb013145af2994fef41b2250143e`: 1 test, 2 exact-version
  subtests. The focused USB analyzer, data-path, determinism, and CLI/MCP parity
  run passed 36 tests and 10 subtests; the backlog Markdown check passed.
- **Applicability screen:**

  The MIT-licensed public
  [CP2102 project][lint086-cp2102]
  is pinned at commit `eecf7bb08afbd1494f3136a5124f4b6b6ea6c63e`. It has
  duplicated USB-C D+/D− contacts, direct nets to a CP2102N, and separate
  two-pin data-to-GND branches. KiCad 10.0.6 exported the design; connector
  and PHY ground pins share `GND`, and the rule emits no split-reference
  review. This is an applicability non-finding, not defect detection, physical
  validation, or a precision-rate sample.

  A synthetic typed-netlist mutation moved the connector returns to
  `USB_GND`; the direct pair still matched and produced one review with both
  contacts and branch pins in evidence. The mutation changed no board or
  project source. No external schematic, board, generated netlist, or part data
  was copied into this repository.

  Two additional public projects were screened at immutable commits:
  [USB-C FUSB302/RP2040][lint086-fusb302] and
  [16nx][lint086-16nx].
  Both use one 27R series resistor per D line and a common GND assignment;
  both were quiet baseline screens. Temporary connector-to-PHY split mutations
  produced one review with both series resistor assignments in evidence. The
  named public projects remain outside this repository. These two quiet
  baselines and two synthetic mutations are applicability checks, not a
  measured precision rate or evidence of product defects.

  **Per-path remeasurement (2026-10-08):** Replayed the retained KiCad 10.0.6
  exports against tooling commit `82cb9b4`. The CP2102 path is J1–U1, the
  FUSB302/RP2040 path is J1–U302, and the 16nx path is J3–U5. All three reports
  were `EVALUATED`, each with one supported connector group, one supported PHY
  group, one `COMMON_REFERENCE` path, and zero separate-reference paths or
  prompts. Each in-memory mutation moved all matched connector reference pins
  to a new synthetic net and produced one separate-reference review for that
  path; source schematics and exports were unchanged. The repeated FUSB302 and
  16nx exports had equal normalized netlist contracts. A second CP2102 export
  was generated with app-bundled KiCad 10.0.6 on 2026-10-09. Its raw XML differs
  from the retained export because timestamped metadata changed; the normalized
  netlist and USB coverage hashes match, and both scans show one common-reference
  path with no prompt. Reapplying the in-memory connector-return split mutation
  to the repeated typed netlist produced one review and the same mutated-netlist
  hash as the original trial. The focused repeat receipt is
  `build/ci/lint-086-public-review-measurement-20261009/cp2102-repeat.json`
  (SHA-256
  `0b9fb78d2241d2c274ef50f73e19dd27409343a96a857ea340f368ef0a708470`).
  Per-path pins, series parts, shunts, source and license hashes, export hashes,
  normalized hashes, and mutation results are in the ignored
  receipt `build/ci/lint-086-public-review-measurement-20261008/receipt.json`
  (SHA-256
  `a4bb641402ffb39dfa6463467117a5782d648ab490ce120964009666282b5663`). These
  earlier 10.0.6 exports establish applicability and fixture sensitivity; at
  that time no digest-pinned execution image was recorded, and no independent
  author disposition or review-time measurement was available.

  **Pinned native remeasurement (2026-10-09):** Re-exported the three pinned
  public sources twice with
  `ghcr.io/kicad/kicad@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`
  (KiCad 10.0.5, `linux/amd64`). The source checkouts matched their pinned
  commits and had no tracked changes; schematic and license hashes are retained
  in the metadata-only receipt. Every repeated normalized typed-netlist hash
  matched its prior 10.0.6 result. Each baseline had one supported
  common-reference path and zero findings; each in-memory connector-reference
  split produced one repeat-stable review. The receipt is
  `build/ci/lint-086-public-review-measurement-20261009/native-10.0.5.json`
  (SHA-256
  `97f2001af8d2dc3574c79269d1060aca84b4c7beabe4b8b09ae95cff76a775b2`). The
  container ran on a `linux/aarch64` Docker host. This confirms reproducibility,
  applicability, and seeded-fault sensitivity. Applying the review worksheet,
  each quiet, fully supported path is a `supported_non_finding`; these are not
  prompted cases requiring a policy disposition and do not establish that the
  reference policy is electrically correct.

  - **CP2102 J1–U1:** One supported common-reference path and zero prompts;
    `supported_non_finding`. Reviewer time is unmeasured.
  - **FUSB302/RP2040 J1–U302:** One supported common-reference path and zero
    prompts; `supported_non_finding`. Reviewer time is unmeasured.
  - **16nx J3–U5:** One supported common-reference path and zero prompts;
    `supported_non_finding`. Reviewer time is unmeasured.

  Each seeded split-reference mutation produced one review. No baseline path
  prompted, so there is no public prompted finding to classify as actionable,
  duplicate, no-action, or unresolved. Reviewer time remains unmeasured because
  no timed baseline-only versus report-assisted review was run.

  **Coverage-boundary screen (2026-10-08):** Re-evaluated two retained public
  [Cynthion hardware exports][cynthion-hardware] under the current USB
  coverage report. The pinned source commit is
  `13aa71c2fb0be3837cd2ec580ee5d2c25fc1c678`; the root schematic SHA-256 is
  `eca9bda94e301f054081c860a184768a242c477a9da9aadd6825ba443cdd1d51`, and
  the repository's [CERN-OHL-P license][cynthion-license]
  SHA-256 is `a389939159561c106f62c5eb8862e0ce90f3a8185fa40dac79631ba55e77644f`.
  Both XML exports identify KiCad 10.0.6 and parse to equal typed netlists;
  their raw XML hashes are `9ea8fc24395a08b90209b30ff534f69e0bc49beb93e12034087f97cc5bff303a`
  and `ae1d9a25a854ec8b0906ced2b7e14663515ce4f97db58c0012d5b4545d0ad9f0`.
  Coverage is `INCOMPLETE`: all four connector groups (J1–J4) and three of
  four PHY groups (U8, U9, U11) are supported; U16 (`PI3USB102G`) is the
  incomplete multi-pin data group. No connector-to-PHY data path matched, so
  the report counted zero common-reference paths, zero separate-reference
  paths, and zero review candidates. Although the inspected reference pins
  share `GND`, this is not a supported non-finding or precision sample. The
  screen demonstrates that coverage makes a zero-finding, unsupported topology
  visible. The public source and exports remain outside the repository in
  temporary storage; only hashes and this summary are recorded here.

  The public [ADAU1701 module](https://github.com/Kononenko-K/ADAU1701_module)
  is pinned at `b05cf09906c4bbb11d92d8b18b25df11f1327d8f`; its hardware
  license file declares CERN-OHL-P (SHA-256
  `01f8d458d093c384fd30fcb5cf295e845286a0887c262fe459d7d16243bdaee4`).
  Its `Hardware/dspmodule.kicad_sch` (SHA-256
  `d234073f4ec8923ccb4b168325f7bac88210a0bf335ed4e011d0102e9c236db4`)
  places an ADuM4160 USB isolator between connector and USB bridge, with
  separate `GND1` and `GND2` references. Two local KiCad 10.0.6 exports parse
  to the same typed netlist contract (SHA-256
  `0ce75ec3e9b6fe2f63795361fe0bfb43b32a558ee3760c956fcff0701d915080`); the
  current direct/one-resistor peer rule emits no finding because it does not
  trace through an isolator. This is an intentional-isolation boundary screen,
  not a supported peer-pair non-finding, precision datapoint, or proof of
  physical behavior. Only hashes and this summary are recorded here; the
  public source and generated exports remain outside the repository.
  **Switchable-return boundary screen:** The GPL-3.0 public
  [USB-sleuth cable tester][usb-sleuth]
  documents a B-side receptacle ground connected to board ground through a DIP
  switch and A-side ground isolated from the MCU sense input through another
  switch during DMM testing. Its [pinned README][usb-sleuth-readme]
  also states that the A/B USB 2.0 data pairs are not connected on the PCB;
  this is a cable tester rather than a supported connector-to-PHY path for
  LINT-086. It is therefore excluded from supported-path and reviewer-value
  counts. This is useful boundary evidence for preserving intentional,
  switchable return domains, not evidence that a USB interface should be
  connected or isolated by default. The repository [LICENSE][usb-sleuth-license]
  declares GPL-3.0 for its hardware documentation; only the pinned source
  reference and this summary are recorded here, with no project files copied
  into Tooling.
  **Pinned public source lead (2026-10-08):** The public
  [StickHub schematic][stickhub-schematic] at commit
  `5f369a785bedc4b1d3b99222c841ac684e04f016` contains native pin-function
  text for `USB1D+`/`USB1D-` through `USB7D+`/`USB7D-`. Its
  [license][stickhub-license] is CC BY-NC-SA 4.0 with a commercial-use
  exemption; the license SHA-256 is
  `9962b75e57113a5df84ba397cec20b8d937a6d5e86dc407471f505ac5a064d88`, and
  the schematic SHA-256 is
  `bf7616095dbeb01b9f3a70f25da4e9916dc9b5424e8414c47dd5f204320d1932`.
  This host has no `kicad-cli`, and the Docker daemon is unavailable, so no
  native export or source-bound USB applicability result was produced. This
  remains a pinned alias-family lead only; the tooling-owned synthetic
  multiport fixture exercises these aliases at the exact-version native gate.
  The public source stays outside the repository; only its commit, hashes, and
  this bounded result are recorded here.
- **Bundled KiCad-demo root replay (2026-10-07):** Re-ran the bounded scanner
  on 35 retained root-project netlists from the pinned KiCad 10.0.5 demo image.
  Every first/repeat XML hash matched its earlier receipt, and all 35 pairs
  parsed to equal typed netlists. Five samples contained recognized USB data
  endpoint groups; the scanner supported two connector groups and three PHY
  groups, while five groups had incomplete evidence. No sample formed a
  supported connector-to-PHY path, so the replay produced zero common-reference
  paths, split-reference candidates, or review findings. The original demo
  source files are absent from this host, so their source bytes could not be
  rechecked during replay; the source hashes remain those in the retained
  export manifest. The result adds no precision or reviewer-value evidence and
  does not establish that the demos lack USB interfaces. The derived receipt is
  ignored at
  `build/ci/public-demo-lint-screen/output/lint-086-root-corpus-replay.json`
  (SHA-256
  `ba3183752f6ae05d8db60e6b8fdb944e95f7b1de812adabbeabf59e8b8d11bc4`). No
  schematic, board, or project source was copied into Tooling.
- **Coverage report improvement:** Each recognized USB endpoint group now
  carries its connector/PHY reference, optional numbered port group, and
  `SUPPORTED`, `INCOMPLETE`, or `DNP` disposition in the typed report and text
  output. This makes the five incomplete groups from the corpus replay
  individually reviewable while preserving the rule's bounded predicate.
  `SUPPORTED` describes endpoint-local evidence only; it does not mean that a
  connector-to-PHY path was matched. The replay localizes those five groups to
  samples 006 (J14 connector), 012 (U5 PHY), and 034 (J15 ports 1/2 and U1);
  they remain incomplete-evidence observations, not defect findings. Older
  schema-version-2 reports without endpoint rows remain readable. Focused USB
  tests, design-lint regressions, catalog validation, CLI/MCP parity,
  cross-process determinism, surface registration, formatting, and Linux
  Pyright all pass for this change. The ignored derived receipt is
  `build/ci/public-demo-lint-screen/output/lint-086-root-corpus-endpoint-groups.json`
  (SHA-256
  `e62023bc2d57ef68350355064d1075deca96d004b942d502e63b9b9cc580a5f6`).
- **Numbered hub alias coverage:** `usb_data_function_identity` now recognizes
  `USBnD+`/`USBnD-` in addition to DPn/DMn and USB_DPn/USB_DMn. The synthetic
  multiport typed-netlist and native fault/control schematics exercise two
  ports under separate and common reference nets. This broadens symbol-function
  recognition only; it does not infer that the references must be common. The
  exact KiCad 10.0.0/10.0.5 gate passed in hosted `v0.5.0rc15` acceptance.
- **Exact native acceptance:** GitHub run `37851810081` retained the USB
  fixture receipts in `build/ci/hosted-37851810081/`. On both KiCad 10.0.0 and
  10.0.5, all 11 native topology cases passed, including split-reference
  faults and common-reference controls for direct USB, USB-C duplicated
  contacts with D-designated shunts, and two numbered hub ports. Each case
  repeated with an equal normalized netlist contract on its version. Event
  receipt SHA-256 values are
  `8417b4af081cf673877b840af6e499e9a1a7b534c48df5ec93704539abdcb8ea`
  (KiCad 10.0.0) and
  `432f8224f7bdb6f4417ab5532284513a2067c8a82a4090aeb32f7e96c4f9798a`
  (KiCad 10.0.5). At that time, the workflow, fixture lane, and heuristic
  sources matched the tagged sources. This establishes exact-version
  schematic-export compatibility for synthetic cases, not physical continuity
  or product approval.
- **UD alias regression (2026-10-09):** A read-only probe of the
  [public SparkFun RFID USB-C Reader source][sparkfun-rfid-reader-source] at
  commit `63c7a5d71cbd1df8f9b420ec320d239ea6a86d33`, file
  `Hardware/SparkFun_USB_RFID_Reader.kicad_sch`, found CH340C pin-function
  aliases `UD+` and `UD-`. Its schematic SHA-256 was
  `315b868e5fa059b3766faeac430519ae6135af3ead2593d0bfff304918447deb`; the
  pinned repository declares CC BY-SA 4.0 for hardware and MIT for code in its
  [license file][sparkfun-rfid-reader-license].
  The probe used only the pin-function names: no schematic, board, project, or
  netlist was copied. That board's data lines pass through a multi-pin TVS, an
  unsupported LINT-086 topology, so it does not count as a supported path or a
  quiet non-finding. The alias table and tooling-owned synthetic USB fault and
  control fixtures now cover the names. Both parametrized native pytest cases
  passed with KiCad 10.0.0 and 10.0.5; each repeated normalized export matched,
  the split-reference fixture emitted one review, and the common-reference
  control stayed quiet. The full pytest suite passed 2,344 tests, skipped 87
  environment-gated cases, and passed 1,880 subtests. The USB peer suite now
  uses module-level pytest functions, the native gate is parametrized by
  toolchain, and the rule catalog points to those functions. These results
  establish deterministic alias handling and native export behavior only.
  The package driver's pytest run with plugin auto-loading disabled also
  passed 2,371 tests, skipped 60, and passed 1,893 subtests. Its wheel and
  source distribution rebuilds, fresh installation, external and adapted
  project checks, and playtest all passed.
- **Expanded native fixture gate (2026-10-12):** The focused
  `bus.usb_peer_reference_review` gate passed in `v0.5.0rc194` (GitHub Actions
  run `38309295549`) with `KICAD_RUN_NATIVE_USB_DATA_PATH_FIXTURES=1`. The
  48-test rule selection ran both the USB data-path and SuperSpeed native
  fixture modules on the digest-pinned KiCad 10.0.0 and 10.0.5 images. The
  expanded data-path fixtures include split-reference and common-reference
  protection-shunt cases plus a wrong shunt-pin assignment; SuperSpeed fault
  and common-reference control results also passed. The scoped package checks,
  installed-wheel external-project checks and playtest, and three portable
  preview jobs passed. This verifies synthetic native-export behavior; it does
  not establish a real board's grounding policy or physical continuity.
- **Reviewer-value measurement protocol:** Use one row per uniquely matched
  connector-to-IC path, plus a run header. Freeze the tooling commit, public or
  approved source URL and immutable revision, license/permission basis, source
  file hash, exact KiCad version and image digest, raw export hash, and
  normalized netlist hash. Capture the report status and the typed
  `supported_data_path_count`, `common_reference_path_count`,
  `separate_reference_path_count`, `mapped_separate_reference_path_count`, and
  emitted prompt count. Do not collapse connector ports, duplicate contacts,
  or multiple PHYs into a single denominator when the report distinguishes
  them.

  Record a quiet common-reference path as `supported_non_finding`. Give every
  prompted path one independently reviewed disposition: `actionable_policy_gap`
  (the prompt caused an authored common/separate/bond decision or exposed a
  mismatch against that decision), `documented_no_action` (approved design
  evidence already resolves the path and no review or contract update is
  needed), `baseline_duplicate` (the same review was already required by ERC or
  another authored check), or `unresolved` (the evidence does not establish
  intended policy). Call a prompt false only for `documented_no_action`; missing
  documentation is `unresolved`, not a false positive. A
  `supported_non_finding` means only that the predicate was quiet on a supported
  path; it does not prove common reference is required. Keep `INCOMPLETE`,
  `NO_SUPPORTED_PEER_PATHS`, DNP-only, and unsupported paths in coverage totals
  but outside the supported-path non-finding denominator.

  Run synthetic split-reference mutations only on tooling-owned fixtures and
  record mutation ID, expected prompt, observed prompt, and miss/pass. These
  measure fixture sensitivity, not field recall. Record reviewer minutes from
  opening the source-bound evidence to a written disposition. To claim a time
  reduction, compare baseline-only and report-assisted review with
  counterbalanced order and publish both sample counts and unresolved cases.
  Report counts and denominators; do not publish a precision or false-positive
  rate when a prompt lacks an independent disposition. Keep source files,
  exports, and reviewer identities out of the tooling repository.
- **Next:** Keep this review-only and measure reviewer usefulness and false
  prompts on approved nonconfidential boards. Do not make common reference a
  universal USB rule. Reviewer effort, false-positive rate, multi-pin
  protection arrays, multiple series components, and indirect-path cases
  remain unmeasured. The synthetic fault/control suite is enough to maintain
  the bounded predicate; more project examples are not required to decide how
  the rule works. Public examples help measure applicability or reviewer value
  only when their relevant reference-pin intent has an independent disposition.
  If that disposition or review-time measurement is unavailable, leave it
  unmeasured rather than infer a defect or false positive. See the
  [USB-A fixture record](../tests/fixtures/design_lint/usb-peer-reference-native/README.md)
  and [USB-C fixture record](../tests/fixtures/design_lint/usb-c-peer-reference-native/README.md).

[sparkfun-rfid-reader-source]: https://github.com/sparkfun/SparkFun_RFID_USB-C_Reader/tree/63c7a5d
[sparkfun-rfid-reader-license]: https://github.com/sparkfun/SparkFun_RFID_USB-C_Reader/blob/63c7a5d/LICENSE.md

#### LINT-087 — Exact serial reference-bond contract

- **Status:** Implemented in `SerialPeerAnalysis` as an explicit `bonded`
  reference policy. It checks the authored endpoint pins and nets plus one
  exact passive two-pin component's symbol, footprint, value, fitted state,
  pin types, and side-net assignments. The serial split-reference lint only
  treats a bonded map as reviewed when that exact component also matches.
- **Priority:** P1 contract regression. A split reference may be intentional,
  but a project that requires a particular bond should fail when its mapped
  part is removed, changed, marked DNP, or disconnected from either return net.
  The check adds authored intent to schematic evidence without changing the
  REVIEW-only heuristic default.
- **Predicate:** `reference_policy: "bonded"` requires one reference net per
  endpoint, distinct endpoint nets, and one exact `ReferenceBondRequirement`
  whose two mapped side nets equal those endpoint nets. The native netlist must
  contain exactly the expected two-pin passive symbol, footprint, value,
  non-DNP state, passive pin types, and pin-to-net assignments. A bond map with
  stale or mismatched evidence does not suppress
  `bus.serial_peer_reference_review`.
- **Boundary:** The result establishes only the exported schematic assignments
  and component metadata. It does not prove component conduction, PCB copper,
  off-board wiring, connector contact behavior, or electrical suitability.
  Project owners must source the part and decide whether a resistor, net tie,
  direct copper connection, or isolation is required for their interface.
- **Fixtures and evidence:** Typed-netlist tests cover a valid bond and missing,
  wrong-value, wrong-footprint, wrong-symbol, DNP, active-pin, wrong-net, and
  unconnected endpoint faults. A CLI/MCP parity case checks the valid control
  and keeps the review visible for a broken bond. Three-process hash-seed
  tests compare the serialized fault and control checks. Synthetic KiCad
  schematics bind J1/J2 references to a 0R R3 control and an R3.2 floating-net
  fault; the exact fixture hashes and outcome are recorded in the
  [synthetic fixture README](../tests/fixtures/design_lint/serial-peer-reference-bond-native/README.md).
  A second typed fault/control pair verifies that an exact fitted
  `Device:FerriteBead` may satisfy the same reviewed bond contract, and that a
  moved bead pin restores the review. The focused serial-reference suite passed
  24 tests and 13 subtests. This composes the shared bond validator with
  LINT-085's exact native ferrite identity and passive-pin evidence; it is not
  an end-to-end native ferrite-bond export.
  Repeated digest-pinned KiCad 10.0.0/10.0.5 exports are wired into the existing
  GitHub serial-peer acceptance job. A local exact-version rerun on 2026-10-08
  passed in both digest-pinned images as part of the package acceptance test
  (`2 passed, 4 subtests` across LINT-077 and LINT-087). For LINT-087, repeated
  normalized netlists matched; the control passed and the fault failed exactly
  `serial/serial-bond/reference` on both versions. The earlier v0.3.2 hosted run
  found ground wires that missed their symbol pins, and v0.4.1 found reversed
  TX/RX declarations in the authored bond map. Both fixture defects were
  corrected; the native sources now bind to the pin endpoints and follow the
  schematic's TX/RX functions.
  **Tagged hosted acceptance:** GitHub run `37851810081` for
  `v0.5.0rc15` passed the reference-bond control and broken-bond fault on both
  digest-pinned KiCad 10.0.0 and 10.0.5. The control matched the authored bond
  map; the fault identified `R3.2` on `FLOATING_GND` instead of `GND_B` and
  failed only `serial/serial-bond/reference`. Repeated normalized netlist
  contracts matched for both cases on both versions. The retained event receipt
  hashes are
  `ab290167b3d294ebdc238af0f53157894de9dbb0e88df5e4f0eb4572f5623b3c`
  (KiCad 10.0.0) and
  `ac57bdf9a719fcbfe386fbb2021533b0b8a9f543a277509b5e71cc66633f9b0d`
  (KiCad 10.0.5), under ignored
  `build/ci/hosted-37851810081/native-serial-peer-project-*/`. The workflow,
  fixture lane, and rule sources are unchanged from the accepted tag.

#### LINT-088 — Fitted two-pin crystal terminals share one net

- **Status:** Implemented as `component.two_pin_crystal_same_net`, defaulting
  to `REVIEW`, with project `review`/`block`/`off` overrides and exact
  fingerprint ignores. It uses the shared native two-pin inventory and is
  covered by fault/control, unsupported-case, metamorphic, CLI/MCP, and
  three-process hash-seed tests.
- **Priority:** P1 topology review. The project-mapped LINT-035 crystal
  network contract can compare a reviewed design, but without that map the
  generic design-lint catalog did not flag a fitted two-terminal crystal whose
  two native pins collapse to one net.
- **Cohort comparison:** The inspected [kicad-happy crystal detector][happy-crystal-detector]
  recognizes crystal circuits and load-capacitor topology, but does not emit
  this bounded same-net finding. No candidate code or runtime dependency was
  adopted; this is a first-party extension of the exact-symbol same-net checks.
- **Predicate:** Recognize only fitted `Device:Crystal` family symbols with
  exactly two distinct native pin numbers, where each has one unambiguous
  native net assignment and both assignments name the same net. Report exact
  component, symbol, value, pins, and net. Project policy may review, block,
  disable, or exactly ignore the finding.
- **Boundary:** A bypassed or disabled crystal can be intentional. This reports
  schematic netlist topology only; it does not establish oscillator behavior,
  frequency suitability, pin-function correctness, footprint mapping, physical
  population, or PCB copper connectivity. Active oscillator symbols, custom
  identities, multi-pin or incomplete inventories, ambiguous/open pins, and
  DNP parts are outside the predicate.
- **Fixtures and evidence:** Tooling-owned same-net fault and distinct-net
  control schematics are source-hashed and run twice on the digest-pinned KiCad
  10.0.0 and 10.0.5 images in the existing two-pin component acceptance lane.
  Typed-netlist tests cover `Device:Crystal` and `Device:Crystal_Small`, while
  a three-pin crystal-family control, DNP, incomplete, ambiguous, open, and
  custom-symbol cases remain quiet. CLI/MCP returns identical evidence for
  fault and control; metamorphic tests preserve the unaffected peer finding
  when one crystal's pins are split. Exact native exports are wired into
  GitHub CI. The exact-version local rerun on 2026-10-08 passed in both pinned
  images: the same-net crystal stayed `REVIEW`, the distinct-net control passed,
  and repeated normalized netlists matched. Hosted package acceptance for this
  revision remains pending.

#### LINT-089 — Generic connector power-input pin is unassigned

- **Status:** Implemented as `connector.unconnected_power_input`, defaulting
  to `REVIEW`, with project `review`/`block`/`off` overrides and exact
  fingerprint ignores. The shared connector candidate set and native pin-type
  inventory drive the same typed report for CLI and MCP.
- **Priority:** P1 connector completeness. A generic peer-pin heuristic flags
  an open pin when one peer differs, but it is silent when every repeated
  connector contact is open. The native `power_in` type gives the heuristic a
  deterministic review signal without supplying the missing interface intent.
- **Predicate:** A fitted connector pin is present in the exported native pin
  electrical-type map as `power_in`; its function is absent, blank, numeric, or
  a generic `Pin_N`; and no exported net assigns that pin. Named supply/return
  checks retain precedence, and overlapping repeated-role or peer-outlier
  prompts are suppressed for the same open pin.
- **Boundary:** KiCad's type does not distinguish a positive supply contact
  from a reference or establish that the contact should be connected. Explicit
  no-connect markers remain review candidates; project owners can record a
  justified exact ignore or disable the rule. DNP instances, non-connector
  pins, meaningful named functions, and assigned pins are outside the
  predicate. The finding does not claim peer pins should share a net or that
  native schematic assignment proves PCB copper continuity.
- **Fixtures and evidence:** The synthetic two-connector fault leaves both
  generic `power_in` pins open while return pins stay connected; the valid
  control assigns both contacts to `+5V`. Source hashes are
  `2e16c602d6ba0068360b3f8b493351f6d7e4d7adbe94946d17db883587f0528f` (fault)
  and `b05c1a3994a4f26f07e18bdfe28c8caaf4a298cbb66b6d1814b20c9a7dce2c13`
  (control). Typed-netlist cases cover blank and absent function, assignment,
  named supply/return deduplication, passive and `power_out` types, DNP,
  blocking, disabling, and exact ignores. CLI/MCP parity and three-process
  determinism include the finding. Local KiCad 10.0.6 exported both sources
  repeatably, preserved native `power_in`, reported exactly the two fault pins,
  and left the control clean. Digest-pinned KiCad 10.0.0 and 10.0.5 repeated
  exports run through `NativeConnectorReturnFixtureTests` in GitHub CI; the
  current local rerun on 2026-10-08 also passed on both exact versions. The
  open `power_in` fault remained `REVIEW` and the connected control passed;
  hosted acceptance passed in `v0.5.1rc47` (commit `7fe9cac`, GitHub Actions
  run `39330933234`). The annotated tag selected this rule and enabled the
  connector native fixture lane; the focused rule tests, exact-version fixture
  checks, installed-wheel rehearsal against a separate project, and Linux,
  macOS, and Windows portability previews passed. The stable-only package job
  was skipped under prerelease policy. This validates the tooling and fixture
  behavior; it does not establish a project's approved pinout or hardware
  connectivity.

#### LINT-090 — USB-C port-side VBUS capacitance contract

- **Status:** Implemented as an explicit per-port disposition in the typed
  USB-C electrical contract. A required declaration binds each fitted
  capacitor by reference, symbol, footprint, pin inventory, and exact VBUS/return
  net assignments, then compares the nominal total to project-authored
  inclusive limits. `pending` remains `NOT_CONFIGURED`; `not_applicable`
  requires a reason. Tooling-owned synthetic native fault/control fixtures and
  full package acceptance passed in tagged `v0.5.0rc17` (GitHub run
  `37863872527`).
- **Inspiration:** The kicad-happy USB checks include UC-004 for undersized
  VBUS capacitance ([candidate releases][happy-uc-releases]). The local
  baseline had USB-C CC, VBUS path, and protection checks but no port-side VBUS
  capacitance comparison. This implementation uses the candidate as a gap
  signal, not as copied code or a universal rule.
- **Predicate:** For a configured USB-C port with `vbus_capacitance.mode` set
  to `required`, every authored capacitor must exist exactly once, be fitted,
  match its symbol and footprint, expose the exact two-pin native inventory,
  assign its pins to the authored port VBUS and ground nets, and have a
  supported nominal capacitance value. The nominal values are summed in nF and
  compared to the authored inclusive range. An additional fitted capacitor
  candidate touching port-side VBUS must be mapped or the check fails.
- **Boundary:** The project supplies the source, applicability decision, and
  numeric limits; the tooling does not provide a Type-C threshold or infer a
  requirement from net names. A project may cite the applicable revision and
  section of its approved source, such as the
  [USB-IF Type-C specification release selected by the project][usb-c-spec-release].
  A passing result does not establish USB
  compliance, tolerance or bias derating, transient response, source-state
  behavior, placement, copper continuity, or hardware acceptance. Capacitors
  on another VBUS domain are outside this port-side inventory. A reviewer may
  choose `not_applicable` only with a project-owned reason.
- **Evidence:** Synthetic fault/control schematics cover 2.2 uF below a
  4500–5000 nF window and 4.7 uF inside it. Focused unit cases also cover
  missing and extra inventory items, DNP, wrong identity, wrong net, unsupported
  values, pending, and not-applicable. CLI and MCP invoke the same typed
  electrical service, with a parity test for pass and under-range fault. The
  native acceptance lane repeats both schematics and compares normalized
  netlists before running the same check; source hashes are pinned in
  `tests/test_ci_hosted_usb_c_ports.py::NativeUsbCPortFixtureTests`. The
  synthetic sources and evidence boundary are
  documented in the [fixture README][usb-cap-fixture-readme].
- **Acceptance:** In GitHub run `37863872527`, digest-pinned KiCad 10.0.0 and
  10.0.5 each exported the fault and control twice with matching normalized
  netlist contracts. The 4700 nF control passed the authored 4500–5000 nF
  window; the 2200 nF fault produced the expected check failure. Project
  adoption still requires the owner to cite and approve the actual limit and
  port applicability. No private project source or requirement was used.

#### LINT-091 — Exact custom-capacitor role for decoupling review

- **Status:** Implemented as an applicability extension to LINT-069 and
  `power.ic_rail_without_fitted_capacitor`. It does not add a new lint rule or
  declare that every IC rail requires a capacitor. Digest-pinned KiCad 10.0.0
  and 10.0.5 native acceptance passed in tagged `v0.5.0rc17` (GitHub run
  `37863872527`).
- **Cohort input:** The kicad-happy source-backed trial under LINT-031 reported
  decoupling-symbol coverage and missing-decoupling observations. That trial
  identified symbol presence as a candidate review signal, while also
  showing broader applicability than the local `power_in` predicate. LINT-091
  addresses a narrower gap in the existing local rule: an opaque custom
  capacitor symbol is not recognized by its library name. No cohort code,
  workflow, project source, or rule threshold is imported.
- **Predicate:** A project-owned `component_role_map` entry classifies a
  capacitor only when exact `PART_ID`, native symbol, footprint, and complete
  two-pin number/function/electrical-type inventory match. The native pins
  must both be passive. A fitted mapped capacitor suppresses LINT-046 only
  when its two pins occupy distinct recognized positive and return nets. DNP
  parts do not count. A mapped component with an unrecognized return leaves
  the review prompt active; a stale map blocks lint. The role cannot activate
  LED heuristics or other rules.
- **Boundary:** The map records reviewed component identity, not datasheet
  suitability, required value, placement, rail demand, copper continuity, or
  physical effectiveness. The rule remains a default `REVIEW` hint, and
  project-authored requirements remain responsible for deciding whether a
  capacitor is required and what values and topology are acceptable.
- **Evidence:** Tooling-owned synthetic KiCad schematics use an opaque
  `Vendor:CAP123` symbol, exact synthetic `PART_ID`, footprint, and passive
  pins named `1` and `2`. The valid control assigns them to `+3V3` and `GND`;
  the fault assigns the return to `CAP_REF`. Typed cases cover DNP, wrong
  return, stale footprint, role isolation from the LED rule, and input-order
  stability. CLI/MCP parity covers unclassified, mapped-valid, and mapped
  fault states. GitHub native acceptance repeats exports on exact KiCad
  10.0.0 and 10.0.5, checks the complete identity and pin inventory, confirms
  zero native ERC errors, and compares deterministic LINT-046 outcomes.
- **Incremental value:** This improves applicability for explicitly reviewed
  custom symbols. It adds no independent electrical defect detection beyond
  LINT-046 and does not measure false-positive rate or reviewer effort.
- **Acceptance:** In GitHub run `37863872527`, the custom-symbol fault and
  control exported twice on digest-pinned KiCad 10.0.0 and 10.0.5 with matching
  normalized netlist and ERC evidence. The mapped valid control cleared the
  LINT-046 prompt; the wrong-return fault retained `REVIEW`. No proprietary
  board source or project expectation is used or stored.

#### LINT-092 — Generic non-connector power-input pin is unassigned

- **Status:** Implemented as a default-`REVIEW` source-bound heuristic using
  KiCad's native pin electrical type. It extends the exact `power_in` signal
  used by LINT-089 to non-connector components; it is not a singleton-net
  warning and does not infer a shared supply/ground requirement.
- **Cohort and backlog context:** Prior LINT-031 trials found general singleton
  warnings duplicative of native ERC and rejected a general singleton-net
  rule. This check uses the narrower native `power_in` type to find an
  unassigned component pin even when every peer is also open. Named supply and
  return pins already use dedicated checks; connector pins remain with
  LINT-089. This is a local extension of that native-evidence boundary. The
  cohort results reinforce the stop condition: do not broaden it into a generic
  singleton-net rule. No third-party code, source, or default electrical
  assumption is imported.
- **Predicate:** A fitted component with native symbol identity has an
  unassigned pin whose electrical type is exactly `power_in` after case-folding
  and whose function is absent, numeric-only, or a generic `Pin_N` placeholder.
  DNP components and native or source-reviewed connector candidates are
  excluded. An explicit no-connect marker remains a review candidate because
  it carries no independent reason why the power-input pin is intentionally
  open.
- **Boundary:** `power_in` does not distinguish positive supply from reference
  or establish that the pin must be connected. This check cannot validate the
  assigned rail, power source, off-board circuitry, copper, population, or
  operation. Projects may review, block, disable, or exactly ignore a finding;
  a required rail relationship belongs in a project-authored contract.
- **Evidence:** Tooling-owned synthetic native schematics cover a floating
  generic pin and an explicit no-connect fault, with a connected control and a
  DNP control. Typed cases also cover missing function metadata, named supply
  deduplication, passive and `power_out` pins, connector exclusion, project
  blocking, exact ignore, and input-order stability. CLI/MCP parity checks the
  fault and connected control. The digest-pinned KiCad 10.0.0/10.0.5 native
  lane records repeated netlist exports and checks the fault, no-connect,
  connected, and DNP outcomes. The focused lane is
  `tests/test_component_power_input_native_fixture_lane.py`; its synthetic
  orchestration test verifies that only those four schematics are mounted.
  No board or project-owned requirement is used.
- **Incremental value:** This closes the generic non-connector edge left by
  LINT-089. It does not duplicate the cohort's broad singleton-net finding;
  independent fault/control tests show the trigger is the native electrical
  pin classification.
- **Acceptance:** GitHub run `37777586540` for `v0.5.0rc9` passed the pinned
  KiCad 10.0.0 and 10.0.5 fixture lanes. Both versions repeated native exports
  and produced REVIEW for the fault and no-connect cases, with PASS for the
  connected and DNP controls. The original run used the broad connector fixture
  lane. Tagged acceptance `v0.5.0rc149` (GitHub run `38246884720`) passed the
  focused component-only selector, the native cases on both pinned versions,
  and the installed-wheel check against a separate project checkout.

#### LINT-093 — Exact two-pin SPST switch is bypassed by one net

- **Status:** Implemented as `component.two_pin_switch_same_net`, defaulting
  to `REVIEW` and using the shared native two-pin inventory. The rule supports
  project `review`, `block`, `off`, and exact-fingerprint ignore decisions.
- **Priority:** P1 component-topology coverage. The existing same-net family
  covered passives, diodes, crystals, fuses, and ferrite beads, but omitted a
  fitted two-terminal switch whose pins had collapsed to one native net.
  LINT-056 also lists switch topologies as unsupported source-path elements;
  this rule checks only the exact same-net bypass case and does not teach the
  source-path heuristic that a switch is a conducting path.
- **Cohort context:** The kicad-happy same-net SP-001 concept and its synthetic
  trial contributed to the existing exact-family checks. This extension adds
  one standard symbol identity where the local two-pin predicate had no
  coverage. No candidate code, package, example, board, or project expectation
  was imported.
- **Predicate:** For exact `Switch:SW_SPST`, require a fitted component, a
  complete inventory of exactly two distinct native pin numbers, and one
  unambiguous assigned net per pin. Emit `REVIEW` only when both assignments
  name the same net. DNP parts, multi-pin or incomplete inventories, open or
  ambiguous assignments, and other switch identities—including `SW_SPDT`,
  `SW_SPST_LED`, and vendor symbols—are outside the predicate.
- **Boundary:** The netlist shows that this schematic net assignment bypasses
  the switch contacts; it does not establish a real switch state, a required
  switching function, the selected footprint's pin mapping, assembly
  population, or PCB copper. A same-net symbol may be deliberate. The rule
  does not infer that all switches should separate nets, and it remains
  review-only by default.
- **Fixtures and evidence:** Synthetic `Switch:SW_SPST` same-net fault and
  distinct-net control schematics are source-hashed. Typed tests cover policy,
  exact ignore, DNP, incomplete, multi-pin, open, ambiguous, and unsupported
  switch identities; order-reversal stability and a one-switch net split are
  metamorphic controls. CLI/MCP parity passed, and the tagged GitHub package
  run `37785605719` passed the shared two-pin native fixture lane on the
  digest-pinned KiCad 10.0.0 and 10.0.5 images. The lane exported all 14
  tooling-owned fault/control schematics twice and matched expected lint
  statuses, including the switch same-net fault and distinct-net control. The
  full package acceptance and all portable preview jobs passed. These are
  synthetic native-export checks; they do not establish physical switch state,
  footprint mapping, assembly population, or PCB continuity.

#### LINT-094 — Open native power output on a comparable peer

- **Status:** Implemented as `component.peer_power_output_unconnected`,
  defaulting to `REVIEW`. Projects can use the existing rule policy to keep
  review, block, disable, or exactly ignore a finding.
- **Priority:** P1 component-population coverage. Existing peer-power rules
  compare assigned supply/return pins, and the open-pin check covers native
  `power_in` pins. An open `power_out` pin on one fitted copy of a component
  could remain unnoticed when another identical copy has that pin assigned.
- **Cohort context:** Similar-part and pin-comparison analyzers establish a
  useful review prompt, not a universal connectivity rule. The local check
  compares native symbol identities or components with the same native
  `PART_ID`, plus complete pin inventory and native electrical metadata; it
  imports no cohort implementation or project data.
- **Predicate:** Group fitted, non-connector instances with an exact matching
  native symbol, or with one shared nonempty `PART_ID` across different
  symbols when values and footprints also match. The cross-symbol path also
  requires present, identical per-pin function text; identical generic
  placeholders are structural evidence only. Require complete, identical,
  unambiguous pin-number inventories and matching `power_out` types for the
  target pin. Emit one review finding when at least one peer pin has no net
  assignment and at least one has exactly one. Recognized supply and return
  functions remain with their more specific checks; shield-labelled native
  power outputs remain eligible because no component-level unconnected-shield
  finding exists. All-open, all-assigned, DNP, incomplete/mismatched,
  missing-type, and multi-net assignments do not trigger this rule.
- **Boundary:** The finding asks whether the open output is intentional or
  needs a connection. It does not require common nets across identical
  outputs, identify what a component output does, prove it is used, validate
  current capacity, or establish PCB copper, off-board wiring, or physical
  population. Native `power_out`, symbol identity, and `PART_ID` are only
  candidate-selection clues; the `PART_ID` may itself be incorrect.
- **Fixtures and evidence:** The typed pytest fault/control matrix covers
  connected versus open peers, same-net and distinct-net output controls,
  DNP, all-open, cross-symbol shared-`PART_ID` fault and control, identical and
  mismatched generic pin-function labels, different part IDs, mismatched values
  or footprints, missing pin functions, incomplete inventory, ambiguous
  assignment, non-`power_out` types, named supply/return
  exclusions, a shield-labelled output fault, stable ordering, duplicate
  suppression, and review/block/off/exact-ignore policy. The synthetic
  native source pair is
  [documented and source-hashed](../tests/fixtures/design_lint/component-peer-power-output-native/README.md);
  the fault leaves U2.2 open while U1.2 is assigned, and the control assigns
  outputs to separate nets. The native pair also exercises identical generic
  `Pin_2` metadata across the symbol aliases. The native lane creates its
  project manifests and toolchain catalog from a synthetic helper, without a
  separate project-template checkout. It exports both fixtures twice on
  digest-pinned KiCad 10.0.0 and 10.0.5 and verifies the exact `PART_ID`, pin
  inventory, functions, electrical types, assignments, normalized netlist
  repeatability, and expected lint result. On 2026-10-09, all four peer-pin
  native lanes passed on both pinned versions: power output, signal output,
  signal input, and bidirectional. The cross-symbol `PART_ID` fault/control
  exports each repeated identically and produced the expected LINT-094 result.
  A source-bound synthetic CLI/MCP parity test exercises shared-`PART_ID`
  open-pin faults and separate-net controls for all four peer pin types. It
  compares complete reports and source-bound peer coverage from the CLI
  subprocess and in-memory MCP service without using an external project
  checkout. The
  earlier tagged acceptance passed in CI run 37796753272 (`v0.5.0rc12`) for
  the then-current exact-symbol fixtures. The earlier complete unit gate,
  source-distribution wheel rebuild and installed-wheel checks against the
  separate template checkout, and Linux/macOS/Windows preview jobs also passed.
  Local verification of the expanded implementation on 2026-10-09 passed the
  full pytest suite (2,351 passed, 85 skipped, 1,912 subtests), the focused
  catalog/determinism/CLI-MCP parity suite (567 passed, 4 skipped, 271
  subtests), Ruff, host and Windows Pyright, and Markdown checks. The source
  distribution reproduced the same wheel, and the installed wheel passed the
  external public-template inventory, CLI/MCP surface, portable verification,
  relocated-layout, and playtest checks from a writable copy of the separate
  checkout. The expanded pinned native fixtures passed on both supported
  versions; this local run used the Docker daemon and did not use a local
  `kicad-cli` installation.
  On 2026-10-09, the current checkout passed the complete package gate against
  the clean public KiCad-Team-Workflow-Template checkout at commit
  `5ca79bedf665a9b6577d96b1d47f13ccd518c968`. The pytest suite reported 2,407
  passed, 59 skipped, and 1,911 subtests passed. Ruff formatting and checks,
  strict host and Windows Pyright, `rumdl`, and `mdrepo` passed. The wheel and
  source distribution built successfully; rebuilding a wheel from the source
  distribution reproduced the package metadata and payload. The fresh installed
  wheel passed external inventory, CLI/MCP surface, portable verification,
  relocated-layout, and playtest checks. The first sandbox run exposed two
  unit-test schedule mocks that omitted the newly added peer-power-assignment
  native lane. Both tests now mock that lane explicitly; the complete gate
  passes with Docker access. This package gate did not run the opt-in exact-
  version native export lanes, which remain separate evidence above.
  This verifies schematic/netlist recognition only; it does not establish PCB
  connectivity or electrical correctness.

#### LINT-098 — Open native signal output on a comparable peer

- **Status:** Implemented as `component.peer_signal_output_unconnected`, with
  pytest typed-netlist regressions, rule-catalog coverage, project policy and
  exact-ignore controls, CLI/MCP parity, and a repeated native-export lane for
  the pinned KiCad 10.0.0 and 10.0.5 profiles. The local native lane passed on
  both profiles on 2026-10-09. Hosted tagged acceptance passed in GitHub run
  `38144622092` (`v0.5.0rc88`, commit `995692f`) on 2026-10-11. The unit stage
  selected `design_lint and component_lint` with
  `KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES=1`: 353 passed, 10 skipped,
  2,327 deselected, and 29 subtests passed. This enabled the exact-version
  native output, input, and bidirectional peer-pin fault/control lanes.
- **Priority:** P1 component-pin completeness. LINT-094 recognizes native
  `power_out` pins, while this rule covers otherwise comparable pins classified
  as ordinary `output`. A missing assignment on one exact-symbol peer can be
  hard to spot in a repeated component group.
- **Predicate:** Compare fitted, non-connector instances with one exact native
  symbol, or one shared native `PART_ID` across distinct symbols with matching
  value and footprint. Require complete identical pin-number inventories,
  native electrical type `output`, matching pin-function metadata, and one
  unambiguous net assignment on at least one peer. Emit a `REVIEW` candidate
  when at least one peer pin has no assignment. Named supply and return pins
  remain with their specific checks. All-open groups, DNP peers, incomplete
  inventories, mixed pin types, and ambiguous assignments are outside the
  predicate.
- **Boundary:** Matching symbols and pin numbers are clues to inspect an open
  output, not requirements to use it or connect peer outputs together. Native
  `output` type does not identify the signal function or expected load. This
  does not infer PWM channel assignments, LED topology, off-board wiring, PCB
  continuity, or physical population. A project-authored `pin_connectivity`
  requirement remains the way to make a specific required relationship a
  regression gate.
- **Fixtures:** Synthetic typed and native-export faults leave one peer's
  output pin open; controls assign the peer pins to the same net and to
  different nets. Typed controls also cover all-open, DNP,
  different-symbol/different-ID, inconsistent value or footprint,
  incomplete-inventory, ambiguous, wrong-electrical-type, and named supply or
  return cases. Input-map reordering preserves the finding fingerprint. The
  native lane exercises the exact-symbol path; cross-symbol `PART_ID` groups
  use typed synthetic coverage.
  Synthetic schematics bind the exact symbol, pin inventory, native output
  type, and expected pin assignments; each source is exported twice on the
  digest-pinned KiCad 10.0.0 and 10.0.5 images.
- **Incremental value:** The extension fills the explicit gap between the
  existing generic unconnected `power_in` check and LINT-094's peer `power_out`
  check. It does not claim a cohort analyzer finding or field precision.
- **Next:** Keep the native lane in package acceptance. Measure the prompt on
  approved, nonconfidential designs before changing its default disposition.

#### LINT-099 — Open native signal input on a comparable peer

- **Status:** Implemented as `component.peer_signal_input_unconnected`, with
  pytest typed-netlist regressions, project policy and exact-ignore controls,
  CLI/MCP parity, and a repeated native-export lane for pinned KiCad 10.0.0 and
  10.0.5. The local native lane passed on both profiles on 2026-10-09; hosted
  tagged acceptance passed in GitHub run `38144622092` (`v0.5.0rc88`, commit
  `995692f`) on 2026-10-11. The focused component gate enabled its
  exact-version native input fault/control lane; shared stage totals are
  recorded under LINT-098.
- **Priority:** P1 component-pin completeness. LINT-094 and LINT-098 cover
  native power and signal outputs. This adds a narrow review prompt for an
  otherwise ordinary `input` or `input_low` pin left open on one comparable
  fitted peer while another peer assigns its matching pin.
- **Predicate:** Compare fitted, non-connector instances with one exact native
  symbol, or one shared native `PART_ID` across distinct symbols with matching
  value and footprint. Require complete identical pin-number inventories,
  matching native input type, and present matching function metadata. Emit a
  `REVIEW` candidate only when at least one peer pin has exactly one net
  assignment and at least one peer pin is unassigned. Named supply and return
  pins, plus recognized reset, enable, and boot controls, remain with their
  specific checks.
- **Boundary:** Matching symbols, pin numbers, electrical types, and function
  metadata are clues to inspect an open input; they do not establish a required
  source or require peer inputs to share a net. This does not infer off-board
  wiring, a missing driver, PCB copper continuity, or physical population. A
  project-authored connectivity requirement remains necessary to make a
  specific required relationship a blocking regression gate.
- **Fixtures:** Synthetic typed and native-export faults leave one peer input
  open. Controls assign the peer inputs to the same net and to separate nets;
  typed tests also cover cross-symbol peers with a shared `PART_ID`.
  Typed boundaries cover all-open peers, DNP, different symbols, incomplete
  inventories, ambiguous assignments, mixed functions or types, passive pins,
  connectors, named supply/return pins, and recognized controls. Cross-process
  hash-seed tests and input-map reordering verify stable reports. Native source
  fixtures are exported twice on both pinned KiCad profiles.
- **Incremental value:** This is a deterministic review hint for missing
  assignments that ERC may not flag when the opposite pin is also typed as an
  input. It does not claim input peers should share a net, and it does not
  replace project-authored connectivity requirements.
- **Next:** Keep the prompt at default `review`; measure usefulness and false
  prompts on approved, nonconfidential boards before considering a default
  change.

#### LINT-100 — Open native bidirectional pin on a comparable peer

- **Status:** Implemented as `component.peer_bidirectional_pin_unconnected`,
  defaulting to `REVIEW`, with pytest fault/control coverage, project policy
  and exact-ignore controls, CLI/MCP parity, and a repeated native-export lane
  for the pinned KiCad 10.0.0 and 10.0.5 profiles. The local native lane passed
  on both profiles on 2026-10-09. Hosted tagged acceptance passed in GitHub
  run `38144622092` (`v0.5.0rc88`, commit `995692f`) on 2026-10-11. The focused
  component gate enabled its exact-version native bidirectional fault/control
  lane; shared stage totals are recorded under LINT-098.
- **Priority:** P1 component-pin completeness. LINT-094, LINT-098, and
  LINT-099 cover native power outputs, signal outputs, and input pins. This
  adds the same bounded missing-assignment prompt for native bidirectional
  pins, including common bus roles such as SDA.
- **Predicate:** Compare fitted non-connector instances with one exact native
  symbol, or one shared native `PART_ID` across distinct symbols with matching
  value and footprint. Require complete identical pin inventories, matching
  native `bidirectional` types, and present matching function metadata. Report
  only when at least one peer assigns the pin to exactly one net and another
  peer assigns it to no net. DNP peers, connectors, all-open groups, mixed
  functions or types, incomplete inventories, and ambiguous assignments are
  skipped.
- **Boundary:** The finding asks whether the open bidirectional pin is
  intentional or missing an assignment. It does not establish bus membership,
  require identical components to use a common net, infer off-board wiring, or
  prove PCB copper or physical population. Use a project-authored connectivity
  requirement to block a specific required relationship.
- **Fixtures:** Synthetic pytest cases cover a three-peer SDA fault, shared-net
  and separate-net controls, DNP and all-open peers, different symbols and
  cross-symbol peers with a shared `PART_ID`,
  incomplete pin inventory, ambiguous assignments, missing or mismatched
  function metadata, connector references, and non-bidirectional pin types.
  Project `review`, `block`, `off`, and exact-fingerprint ignore behavior are
  covered. The synthetic native fault and control schematics bind the exact
  symbol, pin inventory, function, and electrical type; each is exported twice
  on digest-pinned KiCad 10.0.0 and 10.0.5. CLI/MCP parity exercises the shared
  typed service, and hash-seed tests verify stable report JSON.
- **Incremental value:** Native input and output checks do not include
  `bidirectional`, so an open SDA-like peer pin is otherwise outside those
  predicates unless a separate authored interface map covers it. This is a
  review candidate, not evidence that the component belongs on one shared bus.
- **Next:** Keep the rule at default `review`; measure applicability and
  reviewer value on approved, nonconfidential examples.

#### LINT-101 — Connector peer-pin review across native PART_ID aliases

- **Status:** Implemented as a conservative extension of
  `connector.peer_pin_assignment_outlier` and
  `connector.peer_pin_assignment_divergence`. Both remain default-`REVIEW`
  hints. Pytest covers guarded alias eligibility, valid common and isolated
  controls, project policy and ignore lifecycle, mapping-order stability, and
  CLI/MCP parity. Tooling-owned native fault/control schematics are registered
  in the pinned KiCad 10.0.0/10.0.5 connector-return lane. On 2026-10-09 the
  local native lane passed on both pinned versions: 2 tests and 4 subtests,
  including repeated exports and matching normalized typed-netlist hashes
  across versions. The full scoped `v0.5.0rc68` GitHub gate passed on
  2026-10-11 (GitHub Actions run `38131498561`);
  its hosted unit stage enabled `KICAD_RUN_NATIVE_CONNECTOR_FIXTURES` and
  passed the fault/control lane against both pinned KiCad versions. Formatting,
  lint, typing, Markdown, package builds, installed-wheel checks,
  external-template verification, and playtest also passed. The latest
  complete local package acceptance passed from
  source version `0.5.0rc25.dev0+g4e13ff7bf.d20261009` against the public
  template at commit `ed89536f0dbbcb013145af2994fef41b2250143e`: 2,398 tests
  passed, 59 were environment-gated skips, and 1,893 subtests passed. Ruff,
  host and Windows Pyright, Markdown and link checks, wheel and
  source-distribution builds, source-archive wheel equality, fresh
  installed-wheel origin/version checks, external inventory/surface/portable
  verification, relocated-layout checks, and playtest all passed. The ignored
  receipts are under `build/ci/run-c060t4wl/`. The focused connector peer
  selector passed 24 tests on 2026-10-11, including CLI/MCP parity and the
  three-process hash-seed regression. Its source-bound parity project explicitly
  disables the unrelated PCB inventory rule because that synthetic project
  carries no native PCB snapshot. Hosted tagged-source acceptance was
  confirmed by the passing `v0.5.0rc68` gate.
- **Priority:** P1 connector peer-pin completeness. Existing peer comparisons
  grouped only exact native symbol IDs, so equivalent connector parts drawn
  with distinct symbol aliases could be skipped.
- **Predicate:** Compare distinct fitted connector symbols only when every
  member shares one nonempty native `PART_ID`, matching nonempty value and
  footprint, a complete identical pin-number inventory, and matching nonempty
  native function and electrical-type metadata for every pin. Apply the
  existing generic-function outlier/divergence predicates per pin. Skip DNP
  instances, incomplete identity/inventory/metadata, ambiguous multi-net
  assignments, and groups reduced below two peers by reviewed peer scope.
- **Boundary:** A shared `PART_ID` and matching metadata identify a comparison
  candidate. They do not prove the contacts have the same system role or must
  share a net. Keep project-authored connector and connectivity contracts as
  the authority for required bonds, common supplies, and intentional isolation.
- **Fixtures:** The pytest fault leaves J2.2 unassigned while J1.2 is assigned;
  its control assigns both peer pins to one synthetic return. Typed tests and
  the exact-version native lane also cover two assigned contacts on distinct
  nets, which must produce the generic divergence prompt. Additional tests
  cover separate assignments, policy `review`/`block`/`off`, exact fingerprint
  ignores and stale-ignore detection, DNP state, ambiguous nets, value or
  footprint mismatch, incomplete pin inventory, missing or mismatched native
  metadata, project peer-scope isolation, deterministic output, and CLI/MCP
  equality. The three native fixtures are
  [`connector-peer-part-id-native`](../tests/fixtures/design_lint/connector-peer-part-id-native/README.md)
  and contain only synthetic source. Their source hashes are control
  `b8b85aa1fdc8c62547eab58788b120fa6028a8ba65051126f954432f4dd07d2c` and fault
  `db6f556278611edb21a66f8445f7dfc3a2e456a63783dc3d1e8a79a56a69d478`; the
  split-assignment fault is
  `8530bab2ac3537a821be48321e9bb713aa8b2933d714902cc5a30fb4168fa192`.
- **Incremental value:** Adds comparison across symbol aliases that exact-symbol
  grouping cannot see. It does not expand broad similarity matching: identity
  and all-pin metadata must agree, and each result remains subject to the
  existing per-project rule override and exact-ignore controls.
- **Public applicability probe (2026-10-09):** A read-only screen of the
  [public CM4 baseboard sample][antmicro-cm4] at commit
  `d248c2921e8e7f4c9b30c96ea5f376d9b2780f1e` used the root schematic with
  SHA-256 `e56bfc07b813d5f4d6b3e7c713c2096806a800c1877a3f9ef80fed27d8d41551`.
  Its `LICENSE` is Apache-2.0 (SHA-256
  `c95bae1d1ce0235ecccd3560b772ec1efb97f348a79f0fbe0a634f0c2ccefe2c`). The
  source checkout and netlist exports stayed outside this repository. Two
  exports with digest-pinned KiCad 10.0.5
  (`sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`)
  normalized to the same typed contract: 506 components, 393 nets, and
  netlist SHA-256
  `7a4f7e98895b32a7c7f96bcb719676ace53fad2af21e40300515a91c921a921c`.
  Coverage found 15 connector candidates and three exact-symbol peer groups,
  but `PART_ID` alias coverage was `NO_CANDIDATES` (zero groups). The report
  contained 86 exact-symbol divergence prompts and eight outlier prompts; 105
  of 122 exact-symbol pin groups had unknown/generic function metadata. No
  external pinout disposition was collected, so these counts describe review
  load only and cannot be called false positives. This is a reproducible
  compatibility and non-applicability sample, not evidence of LINT-101
  detection gain or defect precision. Separate source-only screens of the
  [Cynthion hardware][cynthion-hardware] and
  [Calcumaker hardware][calcumaker-hardware] examples found no `PART_ID`
  property in their KiCad schematic or board files, so those revisions cannot
  exercise this alias predicate. They were not natively exported for this
  check; these absences are not precision measurements.
- **Bounded public-source search (2026-10-11):**
  A pinned GitHub code search surfaced the Apache-2.0
  [PCBDraft repository](https://github.com/qixuancao/pcbdraft/tree/a194856)
  at commit `a19485657383934de8e9a8a8029795165f12eb14` and [AxxSolder
  hardware](https://github.com/ITGuyFromIA2/AxxSolder_hw/tree/baa001) at
  commit `baa0017696c9cec883c9d7c44b4c3da1bd101a48`.
  PCBDraft's indexed examples and test fixtures did not establish a fitted
  connector-alias group with a shared `PART_ID` or an independent pinout
  disposition. The AxxSolder hit places `part_id` on a `Device:R_Small`
  instance, and GitHub reports no recognized repository license; it is not an
  eligible connector example. No project files were copied. This bounded
  search found no qualified sample and is not evidence of precision.
- **PCBDraft near-miss detail (2026-10-11):** Read-only inspection of the three
  indexed generated schematics at the pinned revision found `Part_ID` (mixed
  case), which the tooling's native CAD reader does not treat as the canonical
  `PART_ID` field. The RC and I²C examples assign that field to J1/J2, but each
  pair uses one exact native symbol ID and distinct `Value` labels; the LED
  example has only one connector. These fixtures therefore do not exercise
  cross-symbol alias eligibility or provide an independent connector pinout
  disposition. See the pinned [RC fixture][pcbdraft-rc-fixture], [I²C
  fixture][pcbdraft-i2c-fixture], and [LED fixture][pcbdraft-led-fixture]. No
  source file was copied; this confirms a non-applicable search result, not
  detection precision.
- **Exact property-name search (2026-10-12):** A read-only GitHub code search
  for the phrase `property "PART_ID"` in `.kicad_sch` files returned four
  indexed files from two repositories: the three PCBDraft generated fixtures
  above and the previously screened AxxSolder schematic. The AxxSolder field
  is on a resistor and its repository has no recognized license; none of the
  four files is an eligible fitted connector-alias sample. This bounded index
  search found no new candidate and does not claim complete GitHub coverage.
- **Next:** Keep the predicate, default `REVIEW`, and synthetic native
  fault/control lane. More public projects are not required to continue
  implementation. Reopen applicability research only for a specifically
  identified, licensed, nonconfidential project with fitted connector aliases
  using distinct native symbols and one shared `PART_ID`. Independent pinout
  dispositions and reviewer time remain unmeasured; do not claim field
  precision or reviewer-value results without them.

#### LINT-102 — Schematic and native PCB component-inventory differences

- **Status:** Implemented as the default-`REVIEW` rule
  `pcb.schematic_component_inventory`. It compares source-bound native
  schematic and PCB evidence and emits exact-fingerprint findings when a
  non-DNP, footprint-assigned schematic reference is absent from board
  footprint inventory or its exact assigned footprint identity differs from
  the placed identity. Projects can select `review`, `block`, or `off`.
- **Priority:** P1 source consistency at the fabrication handoff.
- **Predicate:** Compare case-insensitive component references from the
  source-bound native schematic netlist and KiCad PCB snapshot schema 12, 13,
  or 14. For
  each non-DNP schematic component with a nonempty assigned footprint, report
  a missing-placement candidate when no native board reference matches. When a
  board footprint is present, report a second candidate if its exact
  `library:footprint` identity differs from the schematic assignment.
- **Boundary:** This is a placement and exact-name consistency prompt, not
  proof that every schematic symbol belongs on the PCB or that different
  footprint IDs have different pad geometry. Off-board components and approved
  alternate footprints may need reviewed exact ignores. Empty-footprint
  symbols, DNP components, board-only mechanical or fabrication footprints,
  value differences, DNP disagreements, and pad equivalence are outside this
  predicate. DNP flag differences are handled separately by LINT-111, and
  value-field differences by LINT-112. Missing,
  stale, or unsupported source snapshots are coverage gaps, never passes.
- **Policy and evidence:** Default `REVIEW`; allow project `review`/`block`/`off`
  and the existing exact-fingerprint ignore lifecycle. Bind each finding and
  quiet result to the native netlist digest, board digest, KiCad version, image,
  probe digest, and snapshot schema. Require exact source-bound CLI/MCP service
  parity and a pinned native regression on every supported KiCad version.
- **Fixtures:** Synthetic fitted-part-absent fault, exact-footprint control,
  and present-reference/different-footprint fault; DNP-absent and
  empty-footprint controls; deterministic inventory ordering,
  `review`/`block`/`off`, exact-ignore staleness, unsupported schema, changed
  receipt evidence, and CLI/MCP parity. The exact-version native lane
  uses SHA-256-pinned tooling-owned schematic and PCB fixtures for KiCad 10.0.0
  and 10.0.5, including a one-reference footprint-identity fault and exact
  identity control. Added typed regressions also verify that a case-insensitive
  duplicate schematic reference blocks inventory coverage and that the PCB
  snapshot model rejects case-insensitive duplicate placed references before
  comparison. A separate hash-seed suite compares missing-placement and
  footprint-mismatch faults with an exact-footprint control across three
  randomized Python processes. See the
  [fixture notes](../tests/fixtures/design_lint/component-inventory-footprint-identity/README.md).
  The focused selector passed 12 tests on
  2026-10-11. The full scoped `v0.5.0rc67` GitHub gate passed on that date
  (GitHub Actions run `38130863552`);
  its hosted unit stage enabled `KICAD_RUN_NATIVE_PCB_FIXTURES` and ran the
  fault/control lane against both pinned KiCad versions. Formatting, lint,
  typing, Markdown, package builds, installed-wheel checks, external-template
  verification, and playtest also passed.
- **Cohort boundary:** The pinned [kicad-happy cross-validation source][happy-cross-analysis]
  also compares board-only references and schematic/PCB values using reference
  prefix exclusions. Those broader predicates are not adopted. This rule is
  limited to missing fitted placements and exact assigned-footprint identity
  differences; it does not infer equivalence from names or compare values.
- **Applicability evidence:** No additional project examples are needed to
  implement or test this predicate. Public examples with independent
  off-board dispositions could later estimate how often it prompts review;
  no dispositions or reviewer-time measurements have been collected, so no
  precision or review-value claim is made.
- **Next:** Keep the pinned native lane in hosted acceptance for changes to
  this rule. Keep the default at `REVIEW`; project owners must confirm off-board
  and alternate-footprint exceptions before elevating this comparison to a
  blocking contract. Public examples with independent dispositions remain
  optional evidence for reviewer-value measurement.

#### LINT-103 — Shared I2C peer return-domain review

- **Status:** Implemented as `bus.i2c_peer_reference_review`, defaulting to
  `REVIEW`, with source-netlist-bound coverage, project mode and exact-ignore
  lifecycle, synthetic fault/control and ordering cases, and a focused CLI/MCP
  parity case. The prompt is suppressed when the existing repeated-component
  return review already covers each endpoint in the shared bus group.
- **Priority:** P1 interface-reference review. A shared native SDA/SCL pair
  establishes a direct schematic bus relationship, while ERC cannot establish
  whether the devices' reference domains are intentionally separate.
- **Predicate:** For each fitted U/IC with exactly one native-assigned SDA and
  SCL pin and at least one assigned passive or `power_in` return-like pin,
  group devices by the exact exported SDA/SCL net pair. Emit one grouped review
  when explicit reference-pin assignments span multiple nets. Keep separate
  segments separate, skip DNP and ambiguous or incomplete endpoint evidence,
  and suppress an I2C prompt when `component.peer_power_pin_assignment_divergence`
  already reviews a return assignment for every endpoint in that group.
- **Boundary:** The result asks for review; it does not require common grounding,
  identify all I2C endpoints, resolve level translators or isolation, compare
  voltage limits, prove a board copper path, or establish physical continuity.
  Only native pin-function metadata and exact assigned net pairs are used; rail
  name similarity is not a predicate. This is not a substitute for an approved
  connector pinout or a project-authored connectivity requirement.
- **Fixtures and verification:** Synthetic pytest cases cover split and common
  reference domains, a three-peer bus, separate segments, DNP, incomplete and
  shield-only pins, mapping-order stability, and duplicate suppression when
  the component-peer rule covers the same return assignments. The source-bound
  CLI/MCP case compares the complete typed I2C finding and coverage for split
  and common-reference cases. Synthetic schematic fault/control fixtures feed
  a digest-pinned exact-version KiCad export lane for KiCad 10.0.0 and 10.0.5;
  local exact-native execution remains unavailable in this workspace. See the
  [fixture notes](../tests/fixtures/design_lint/i2c-peer-reference-native/README.md).
  The focused I2C review suite passed 11 tests on 2026-10-11. Its exact-native
  lane is marked `native_kicad` and `slow`. The full scoped `v0.5.0rc69`
  GitHub gate passed on 2026-10-11 (run `38132142651`), enabled
  `KICAD_RUN_NATIVE_I2C_PEER_REFERENCE_FIXTURES`, and passed the native
  fault/control lane on both pinned KiCad versions. Formatting, lint, typing,
  Markdown, package builds, installed-wheel checks, external-template
  verification, and playtest also passed.
- **Rule-scoped gate registration (2026-10-12):** The exact-native test was
  previously covered through the broad interface-area gate, but was absent
  from this rule's catalog. A `Lint-Rule: bus.i2c_peer_reference_review` tag
  therefore did not select its native split/common-reference pair. The catalog
  now links the test as both fault and valid control and requires
  `KICAD_RUN_NATIVE_I2C_PEER_REFERENCE_FIXTURES`; the architecture suite guards
  that association. The rule-scoped `v0.5.0rc182` run `38294501510` passed the
  native fault/control lane on digest-pinned KiCad 10.0.0 and 10.0.5, the
  installed-wheel check against the separate template checkout, and all three
  portability previews; the full package job was skipped by RC policy.
- **Incremental value:** LINT-070 already prompts on split return pins across
  comparable repeated components. LINT-103 adds the direct-I2C-bus relation
  between heterogeneous devices when that repeated-component comparison has no
  matching assignment coverage; the regression confirms no LINT-070 candidate
  for distinct symbols without a shared `PART_ID`. Coverage records when
  LINT-070 covers a group so the new prompt does not duplicate it.
- **Applicability evidence:** No additional project examples are needed to
  implement or test this bounded rule. No independent board dispositions or
  reviewer-time measurements are available, so precision, false-prompt rate,
  and review-time benefit remain unmeasured. Public, nonconfidential examples
  can be added later only to measure those outcomes.
- **Next:** Retain default `REVIEW`. The rule-scoped hosted gate now covers both
  pinned export versions. Keep precision and review-time benefit unmeasured
  until independent board dispositions and reviewer-time observations are
  available. Do not promote the heuristic to a blocking requirement without
  an independent project-authored pinout or grounding contract.

#### LINT-104 — SPI peers share a clock but have split explicit references

- **Status:** Implemented as `bus.spi_peer_reference_review`, defaulting to
  `REVIEW`, with source-netlist-bound applicability coverage, project mode and
  exact-ignore lifecycle, a synthetic fault/control suite, and focused
  CLI/MCP parity. The exact-native lane is registered for digest-pinned KiCad
  10.0.0 and 10.0.5. The full scoped `v0.5.0rc70` GitHub gate passed on
  2026-10-11 (run `38132546468`), enabled
  `KICAD_RUN_NATIVE_SPI_PEER_REFERENCE_FIXTURES`, and passed the fault/control
  lane on both pinned KiCad versions. Formatting, lint, typing, Markdown,
  package builds, installed-wheel checks, external-template verification, and
  playtest also passed.
- **Priority:** P1 interface-reference review. A direct shared SPI clock can
  connect heterogeneous ICs whose explicit return pins are assigned to
  separate schematic nets. Existing component-peer checks need a comparable
  part identity, and the SPI voltage heuristic addresses unequal
  voltage-named supply rails; neither necessarily surfaces this equal-supply,
  different-reference case.
- **Predicate:** For fitted U/IC components, recognize exactly one assigned
  native SCK/SCLK pin with input/output-compatible type and complete native
  pin-number, pin-function, and pin-type inventories. Group only exact shared
  clock-net assignments with at least one output-capable and one input-capable
  endpoint. Emit one grouped review when the explicit passive or `power_in`
  return-like pin assignments span multiple native nets. Preserve a known
  split as a candidate when another endpoint's reference evidence is
  incomplete. Suppress a complete-group prompt only when the existing
  component-peer return findings cover every explicit reference-pin
  assignment in that group.
- **Boundary:** This is a deterministic review heuristic; it does not require
  common grounding, infer SPI membership from MOSI/MISO/chip-select names,
  discover all peers, trace buffers or isolators, judge power or logic
  compatibility, establish that separate references are erroneous, or prove
  a PCB copper or physical return path. Multiple clock ports, ambiguous clock
  directions, DNP endpoints, missing native pin metadata, multiple reference
  nets on one endpoint, shield/chassis-only functions, and unmatched clock
  segments do not become positive split-reference evidence. An independently
  authored interface/grounding contract remains the source of required
  common, bonded, or isolated topology.
- **Fixtures and verification:** Synthetic cases cover a shared SCK with
  `+3V3` on both peers and `GND_A`/`GND_B` on the explicit returns, common
  references, different clock segments, DNP, incomplete metadata, shield-only
  pins, unclear clock direction, partial split with an incomplete peer,
  duplicate suppression, exact evidence, mapping-order stability, policy,
  ignore, and typed coverage. A fault assertion confirms the existing
  `bus.spi_peer_voltage_review` remains quiet on the equal-supply case. A
  parity case compares complete CLI/MCP finding and coverage records. Two
  standalone synthetic KiCad schematics bind source hashes and are configured
  for repeated exact-version native exports on KiCad 10.0.0 and 10.0.5; see
  [the fixture notes](../tests/fixtures/design_lint/spi-peer-reference-native/README.md).
  The focused SPI review suite passed 10 tests on 2026-10-11. Its exact-native
  lane is marked `native_kicad` and `slow`; hosted tagged-source acceptance is
  confirmed by `v0.5.0rc70`.
- **Rule-scoped gate registration (2026-10-12):** The exact-native fault/control
  test was already exercised by the broad interface-area gate, but it was not
  in this rule's fixture catalog. A `Lint-Rule: bus.spi_peer_reference_review`
  tag therefore could not select it. The catalog now links the test as both
  fault and valid control, requires
  `KICAD_RUN_NATIVE_SPI_PEER_REFERENCE_FIXTURES`, and the architecture suite
  guards that association. The rule-scoped `v0.5.0rc183` run `38294866007`
  passed the lint and installed-wheel steps plus all three portability
  previews; the full package job was skipped by RC policy.
- **Incremental value:** The equal `+3V3` control/fault pair isolates return
  assignments as the changed variable. The split case has distinct symbol
  identities and no component-peer assignment finding, while the existing SPI
  voltage heuristic emits no candidate. This demonstrates a new deterministic
  candidate class within the synthetic baseline, not a confirmed defect or
  measured field detection rate.
- **Applicability evidence:** No additional project examples are needed to
  implement or regression-test this bounded predicate. Public, nonconfidential
  schematics may help estimate how often the pattern occurs, but cannot
  substitute for a reviewer disposition or time measurement. No independent
  board dispositions or reviewer-time measurements are available; precision,
  false-prompt rate, and review-time benefit remain unmeasured.
- **Next:** Keep the hosted digest-pinned native lane for changes to this rule.
  Keep default `REVIEW`; only a project-authored contract can establish that
  its peers must share, bond, or isolate their references.

#### LINT-105 — CAN peers share a complete line pair but have split explicit references

- **Status:** Implemented as `bus.can_peer_reference_review`, defaulting to
  `REVIEW`, with source-netlist-bound applicability coverage, project mode and
  exact-ignore lifecycle, synthetic fault/control and mapping-order tests, and
  CLI/MCP parity coverage. Synthetic standalone schematics are registered for
  repeated exports and ERC checks on the digest-pinned KiCad 10.0.0 and 10.0.5
  images. The full scoped `v0.5.0rc66` GitHub gate passed on 2026-10-11
  (GitHub Actions run `38130384785`);
  its hosted unit stage included the native CAN fault/control lane on both
  pinned versions. Ruff format and lint, Pyright and Windows types, Markdown,
  wheel and source-distribution builds, installed-wheel checks, external
  inventory/surface/verification, relocated-layout checks, and playtest also
  passed.
  The `v0.5.0rc63`/`rc64` hosted runs exposed that the synthetic wires attached
  each label to the opposite vertical pin from the intended pin number. The
  exported fault was independent of the reference split: all U1–U3 CAN,
  reference, and supply assignments were reversed. The expected pin map stays
  tied to the authored pin functions; both synthetic schematics and their
  source digests were corrected in `v0.5.0rc65` and verified by the passing
  `v0.5.0rc66` gate.
- **Priority:** P1 interface-reference review. Existing CAN peer heuristics
  identify incomplete or divergent CANH/CANL assignments, but do not flag a
  complete shared CANH/CANL pair whose explicit passive or `power_in` return
  pins use separate schematic nets. General component-peer checks may not
  compare heterogeneous transceiver symbols.
- **Predicate:** For fitted U/IC endpoints with exactly one uniquely assigned
  native CANH and CANL pin on distinct nets, group only exact exported line-net
  pairs. Emit one grouped review when recognized explicit return-pin
  assignments span multiple native nets. Preserve known split evidence when a
  peer's return assignment is incomplete. Suppress a complete-group prompt
  only when existing component-peer return findings cover every explicit
  return-pin assignment in that group.
- **Boundary:** This is a deterministic review heuristic. It does not require
  a common return, infer CAN membership from component names, resolve
  translators or isolated segments, judge transceiver compatibility, or prove
  board copper/off-board continuity. DNP, ambiguous or incomplete CAN pin
  assignments, unrelated CAN line pairs, shield-only functions, and endpoints
  without explicit return pins do not become positive split-reference
  evidence. A project-authored contract remains the authority for common,
  bonded, or isolated topology.
- **Fixtures and verification:** Synthetic tests cover a split reference on
  one complete CANH/CANL pair, common-reference and distinct-bus controls, DNP,
  shield-only and incomplete endpoints, duplicate suppression, exact evidence,
  deterministic ordering, policy/ignore behavior, and typed coverage. The CLI
  and MCP parity case compares findings and coverage. Native fixtures check
  the exact pin-to-net assignments, repeatable netlists and ERC reports, and
  zero ERC errors on KiCad 10.0.0 and 10.0.5. See the
  [fixture notes](../tests/fixtures/design_lint/can-peer-reference-native/README.md).
- **Rule-scoped gate registration (2026-10-12):** The exact-native fault/control
  test was exercised by the broad interface-area gate, but was not in this
  rule's fixture catalog. A `Lint-Rule: bus.can_peer_reference_review` tag
  therefore could not select it. The catalog now links the test as both fault
  and valid control, requires
  `KICAD_RUN_NATIVE_CAN_PEER_REFERENCE_FIXTURES`, and the architecture suite
  guards that association. The rule-scoped `v0.5.0rc184` run `38295223564`
  passed the lint and installed-wheel steps plus all three portability
  previews; the full package job was skipped by RC policy.
- **Incremental value:** The expected pin-to-net maps differ only at U3's
  reference assignment. U1/U2 share one symbol identity and have equal return/supply
  assignments; U3 has a distinct symbol identity, so component-peer comparison
  does not cover the split. All three peers share the same exact CANH/CANL
  pair, and the existing CAN pair-divergence rule stays quiet. This proves a
  distinct candidate class in the synthetic baseline, not field detection or
  that the references should be common.
- **Applicability evidence:** No additional project examples are needed to
  implement or regression-test this bounded predicate. Public,
  nonconfidential schematics could help estimate applicability but cannot
  replace an independent reviewer disposition or reviewer-time measurement.
  Those outcomes remain unmeasured.
- **Next:** Require the registered hosted lane to pass on both exact KiCad
  versions before claiming native acceptance. Keep default `REVIEW`; promote
  only through an independently authored interface or grounding requirement.

#### LINT-106 — Mapped RS-485 endpoints share a pair but use split references

- **Status:** Implemented as `bus.rs485_peer_reference_review`, defaulting to
  `REVIEW`, with source-bound `Rs485Analysis` applicability coverage, project
  mode and exact-ignore lifecycle, synthetic fault/control and mapping-order
  regressions, and CLI/MCP parity. A digest-pinned native fixture lane is
  registered for KiCad 10.0.0 and 10.0.5. Tag `v0.5.0rc77` passed hosted
  acceptance in Actions run `38138351020`, including the native fixture lane
  and the installed-wheel check against a separate project checkout. The
  unchanged-map source-reference-drift regression passed scoped hosted
  acceptance in tag `v0.5.0rc92`, Actions run `38147088547`, including the
  installed-wheel check and Ubuntu, macOS, and Windows previews.
- **Priority:** P1 interface-reference review. An authored RS-485 bus map can
  identify connector or transceiver endpoints and their reference pins, while
  native ERC cannot decide whether peers on the same mapped line pair should
  share, bond, or isolate their reference domains.
- **Predicate:** For fitted endpoints whose exact symbol, footprint, and
  mapped line-pin assignments match one authored RS-485 pair, group only that
  exact native pair. Emit one grouped review when explicit mapped reference
  pins occupy multiple native nets. Preserve a known split if another mapped
  endpoint has incomplete reference evidence. Skip DNP, stale identities,
  line-map mismatches, unshared pairs, and endpoints without mapped reference
  pins.
- **Boundary:** This is a deterministic review heuristic. It does not require
  a common return, infer bus membership or pin roles from names, decide whether
  an interface is isolated, establish a bond, or prove PCB copper or off-board
  continuity. A project-authored contract remains the authority for common,
  bonded, or isolated topology.
- **Fixtures and verification:** Tooling-owned synthetic schematic/map pairs
  differ only at J3.3: the control keeps the mapped transceiver and all three
  connectors on `GND_A`; the fault puts J3.3 on `GND_B` while every endpoint
  shares the exact `RS485_A`/`RS485_B` pair. Synthetic tests also cover common
  references, unshared pairs, DNP, missing references, partial splits,
  source-reference drift against one unchanged map (exact contract `FAIL`,
  heuristic coverage `INCOMPLETE`, with no inferred split-domain finding),
  duplicate suppression, rule mode/ignore behavior, stable findings, and
  source-bound coverage. See the
  [fixture notes](../tests/fixtures/design_lint/rs485-peer-reference-native/README.md).
- **Applicability evidence:** Additional board projects are not needed to
  define or regression-test this bounded predicate. Public nonconfidential
  examples could help estimate how often it prompts review, but need independent
  applicability dispositions. Reviewer effort and field false-prompt rate
  remain unmeasured; no values are inferred.
- **Next:** Keep default `REVIEW`; promote only through an independently
  authored interface or grounding requirement. Reviewer effort and field
  false-prompt rate remain unmeasured.

#### LINT-107 — Connector return pin assigned to a recognized positive rail

- **Status:** Implemented as `connector.return_pin_on_positive_rail`, default
  `REVIEW`. The predicate uses bounded connector-role recognizers and the
  shared positive-rail recognizer. It supports native return functions and
  complete source-matched interface return roles for generic native pins.
- **Problem:** Existing checks prompt on open named returns, differing peer
  assignments, or suspiciously separated return domains. A connected pin
  explicitly identified as a return could still be assigned directly to a
  recognized positive supply rail without those checks identifying this
  specific mismatch.
- **Boundary:** This is a review hint. A rail name or attached pin function
  does not prove electrical potential, an approved connector pinout, or that
  the contact must connect to a particular return domain. The heuristic skips
  shields, DNP connectors, open pins, ambiguous assignments, and unrecognized
  connector identities. A project-authored interface/grounding contract is
  required to make a connectivity expectation blocking.
- **Fixtures:** Tooling-owned synthetic contract tests cover a native GND pin
  on `+5V`, a mapped generic return pin on a recognized positive rail, a
  common-return control, negative-rail and unrecognized-role controls, shields,
  DNP, open assignments, input order, and reassignment. The
  [fixture note](../tests/fixtures/design_lint/return-pin-positive-rail/README.md)
  and its source schematics feed the
  digest-pinned KiCad 10.0.0/10.0.5 connector-return lane.
- **Applicability evidence:** No additional board projects are needed to
  define or regression-test this bounded predicate. Public nonconfidential
  examples could help estimate how often it prompts review, but an independent
  disposition and reviewer-time measurement are needed to assess usefulness.
  Precision and review-time benefit remain unmeasured.
- **Acceptance:** Focused synthetic and mocked native-lane checks pass locally.
  Tagged hosted connector-lint acceptance passed on 2026-10-11 under
  `v0.5.0rc100`, including exact KiCad 10.0.0/10.0.5 fixtures and an
  installed-wheel check against an external project checkout. No physical
  board or proprietary project source was used.

#### LINT-108 — Generic component power-output pin is unassigned

- **Status:** Implemented as `component.unconnected_power_output`, default
  `REVIEW`. The predicate reports a generic, absent, or numeric-only native
  `power_out` pin on a fitted non-connector component when it has no exported
  net and no comparable-peer power-output rule already owns the open pin.
- **Problem:** The existing peer rule only catches an open output when a
  comparable connected peer gives it context. A single-output component, or a
  group with no assigned peer, can still leave an output pin open without that
  rule identifying the open pin.
- **Boundary:** KiCad's `power_out` electrical type is pin metadata, not a
  project requirement. It does not identify the pin's actual function or prove
  that it must connect. The rule is therefore an advisory review prompt;
  named outputs, connector candidates, DNP parts, and open pins already owned
  by the comparable-peer rule are excluded. It does not validate output
  voltage, current, source capability, or PCB copper.
- **Fixtures:** Synthetic contract cases cover an open output, assigned
  control, absent/generic functions, named-output, passive and power-input
  controls, connector and DNP exclusion, peer-rule duplicate suppression,
  stable ordering, assignment clearing, and project policy/ignore handling.
  The fault/control schematics are exported twice with pinned KiCad 10.0.0 and
  10.0.5; CLI/MCP report parity is checked from a tooling-owned synthetic
  project. See the
  [native fixture record](../tests/fixtures/design_lint/generic-component-power-output/README.md).
- **Applicability evidence:** Public examples are not needed to define this
  bounded check. Additional nonconfidential projects could help measure how
  often the prompt is applicable, but each needs an independent disposition;
  applicability and reviewer time remain unmeasured.
- **Acceptance:** Tagged hosted acceptance passed in GitHub Actions run
  `38166720030` for `v0.5.0rc103` on 2026-10-11. The scoped pytest run selected
  `design_lint and power_lint` and enabled
  `KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES=1`, so the pinned KiCad 10.0.0
  and 10.0.5 fault/control exports ran. The installed wheel also passed checks
  against a separate public project checkout. No customer project source or
  proprietary design fixture was used.

#### LINT-109 — Generic connector power-output pin is unassigned

- **Status:** Implemented as `connector.unconnected_power_output`, default
  `REVIEW`, with project `review`/`block`/`off` overrides and exact-fingerprint
  ignores. It uses KiCad's native connector pin-type inventory and produces
  the same typed report through CLI and MCP.
- **Priority:** P1 connector-pin completeness. Connector peer checks can miss
  a generic contact when every matching peer is open. Native `power_out`
  metadata supplies a review clue without claiming a required connection.
- **Predicate:** A fitted connector pin is classified by the native netlist as
  `power_out`, has an absent, blank, numeric, or generic `Pin_N` function, and
  has no exported net assignment. Meaningful named functions and DNP
  connector instances are outside this generic predicate. When enabled, this
  finding owns a matching open peer-outlier or repeated-role finding; when
  disabled, those broader comparisons remain available.
- **Boundary:** Native electrical type does not identify the contact's role or
  prove that it must connect. An explicit no-connect still prompts review.
  This does not establish the approved connector pinout, off-board wiring, PCB
  copper, or physical continuity. A project-authored connector contract is
  needed to make a specific net relationship enforceable.
- **Fixtures:** The tooling-owned fault leaves pin 1 open on two generic
  synthetic connector symbols; the control assigns both pins to `+5V`. Pin 2
  is tied to GND in both sources. Tests cover absent/blank/placeholder function,
  connected, named, non-connector, DNP, policy overrides, stable ordering, and
  duplicate suppression. The
  [native fixture record](../tests/fixtures/design_lint/generic-connector-power-output/README.md)
  binds source hashes and repeated exports on digest-pinned KiCad 10.0.0 and
  10.0.5. A source-bound synthetic CLI/MCP parity test covers fault and
  control reports. No customer or proprietary board fixture is used.
- **Applicability evidence:** More projects are not needed to define this
  bounded predicate. Public or synthetic examples may help tune its candidate
  selection, while field applicability and reviewer-time benefit remain
  unmeasured until findings receive independent dispositions.
- **Acceptance:** Local synthetic, CLI/MCP parity, catalog, architecture, and
  style checks pass. Tagged acceptance for this rule exercises the exact
  KiCad 10.0.0/10.0.5 fault/control lane and the installed-wheel check against
  a separate project checkout. No hardware or electrical approval is inferred.

#### LINT-110 — Named power pin conflicts with a recognized net role

- **Status:** Implemented as `power.pin_function_net_role_conflict`, default
  `REVIEW`. The owner is the focused `power_pin_net_roles.py` power-theme
  module; candidate aggregation remains a thin adapter.
- **Problem:** A fitted IC can have a named positive-supply pin assigned to a
  return-like net, or a named return pin assigned to a recognized positive
  rail. Native ERC can accept some such assignments when the electrical pin
  types do not conflict.
- **Predicate:** Require one exported net assignment and a native pin function
  recognized by `power_function_key` or `is_return_function`. The assigned net
  must be identified as the opposite role by its bounded name or a different
  attached pin function. A recognized label takes precedence; peer functions
  classify only otherwise unnamed rails. The candidate pin's own function
  cannot establish the opposing net role. Connector return pins remain with
  the connector-specific
  rule; positive-supply connector pins remain in scope.
- **Boundary:** This is a name/function review hint, not proof of voltage,
  project intent, or required connectivity. Unrecognized aliases, DNP parts,
  open pins, and multiply assigned pins are outside the predicate. The rule
  defaults to review and supports project `block`, `off`, and exact-fingerprint
  ignore decisions.
- **Fixtures:** Synthetic typed-netlist tests cover both conflict directions,
  recognized-label precedence when peer pin functions disagree, role evidence
  from peer pins, common and negative-rail controls, unknown
  roles, connectors, DNP and ambiguous/open assignments, project policy, stable
  fingerprints, and correction. A positive-supply connector pin on a return net
  remains in scope, while a connector return pin is left to its connector rule;
  a matching positive-rail connector pin is a valid control. A source-bound
  CLI/MCP test exercises the
  shared report service. The digest-pinned native lane repeats the fault and
  control schematic exports on KiCad 10.0.0 and 10.0.5; fixture notes explain
  that passive native pin types isolate this rule from ERC source checks.
- **Applicability evidence:** More examples are not needed to define the
  bounded predicate. Public designs with independently reviewed pinouts can
  help measure applicability and false prompts; reviewer time remains
  unmeasured. A 2026-10-11 screen against the licensed public KiCad-Test
  template at commit `ed89536f0dbbcb013145af2994fef41b2250143e` used a
  temporary checkout and manifest-pinned native containers. The three PCB
  projects that produced component netlists (`controller`,
  `raspberry-pi-status-led`, and `arduino-uno-status-led`, KiCad 10.0.0/10.0.5)
  yielded zero candidates for this rule. The `passive-signal-reference`
  schematic exported no component records and was blocked, so it provides no
  rule evidence; the wiring and harness examples are outside this rule's
  native-netlist applicability. This is a no-candidate screen, not an
  independently adjudicated valid-control or false-positive-rate measurement;
  the aggregate native verification results were not all green. No project
  source or receipts were copied into this repository.
- **Acceptance:** Local synthetic, CLI/MCP parity, catalog, architecture, and
  style checks passed. The focused `design_lint and power_lint and not
  native_kicad` selection passed 352 tests with the public template checkout;
  the architecture slice passed 161 tests. Catalog reachability, rule-specific
  collection, and the exact verify-fixture scope passed. Ruff check and format
  passed. The recorded digest-pinned native fixture lane passed on KiCad 10.0.0
  and 10.0.5: both exports reproduced the named-pin fault as `REVIEW`, kept the
  valid control at `PASS`, and matched across repeat exports (2 passed).
  GitHub run `38190696668` for `v0.5.0rc109` passed its unit gate and all three
  preview jobs; the prerelease gate failed in `ruff-format` on moved parity
  suites. Run `38191557064` for `v0.5.0rc110` passed its unit gate, Ruff
  formatting, Ruff, Pyright, Windows typing, and all preview jobs, then failed
  Markdown lint on one line in a new synthetic-fixture README. The README line
  is wrapped in the follow-up. Run `38191917547` for `v0.5.0rc111` passed its
  unit gate, Ruff, Pyright, Windows typing, Markdown lint, and all preview jobs;
  `mdrepo` then flagged four fixture notes as unreachable. `tests/README.md` now
  links those records. Run `38192227375` for `v0.5.0rc112` passed the full
  prerelease gate, including the scoped unit selection, lint/type/documentation
  checks, wheel and source builds, and installed-wheel verification against the
  separate public project. All three platform previews passed; the package job
  was skipped for this prerelease tag.

#### LINT-111 — Schematic and PCB DNP states differ

- **Status:** Implemented as `pcb.schematic_pcb_dnp_mismatch`, default `REVIEW`,
  comparing the base source-bound schematic netlist and native PCB snapshot,
  plus paired exact-version schematic and PCB exports for declared variants.
- **Priority:** P1 fabrication-handoff consistency. The DNP flag can disagree
  between the schematic and its placed PCB footprint while the reference and
  assigned footprint remain present.
- **Predicate:** For each case-insensitive reference with a nonempty schematic
  footprint assignment and a placed PCB footprint, compare the base schematic
  netlist DNP flag with the native PCB snapshot. For each `schematic.variants`
  entry, first confirm KiCad's native PCB API reports that exact variant name,
  then export the schematic netlist and PCB position files with the same name.
  Compare schematic DNP state with PCB DNP state inferred from all positions
  minus the native `--exclude-dnp` positions. Missing references remain with
  LINT-102.
- **Boundary:** These are CAD flags, not proof of physical population or
  manufacturing intent. A declared variant absent from the PCB blocks variant
  coverage; the check never falls back to default exports. Unlisted variants,
  references absent from either artifact, and symbols without assigned
  footprints are outside this comparison. Project owners can retain REVIEW,
  select an explicit rule mode, or suppress an exact reviewed finding.
- **Fixtures:** Synthetic cases cover both mismatch directions, matched
  fitted and DNP controls, absent placements, empty schematic footprints,
  stable ordering, source evidence in findings, policy/ignore lifecycle,
  CLI/MCP parity, and repeated native exports. Named-variant exports add both
  mismatch directions, a fitted control, a missing-board-variant block, and
  source-change detection. The exact-version lane uses tooling-owned fixtures
  and digest-pinned KiCad 10.0.0/10.0.5. See the
  [fixture record](../tests/fixtures/design_lint/component-inventory-footprint-identity/README.md).
- **Applicability evidence:** Additional project examples are not needed to
  define this consistency check. They may help prioritize future heuristic
  rules, but cannot substitute for project-owned population intent. An
  independent review is still needed to measure whether a finding is
  actionable; no reviewer-time or field-precision claim is made. No project
  source or proprietary fixture is stored.
- **Determinism:** LINT-080 compares both base DNP mismatch directions against
  a matching fitted control across three isolated processes. The complete
  reports retain the schematic netlist, PCB snapshot, and board source hashes;
  the check remains a CAD-state consistency review, not assembly approval.
- **Next:** Keep the default at REVIEW. Board-only footprint coverage is tracked
  separately by LINT-129; evaluate explicitly required fitted-reference
  coverage without inferring assembly intent from component similarity alone.

#### LINT-112 — Schematic and PCB component value fields differ

- **Status:** Implemented as `pcb.schematic_pcb_value_mismatch`, default
  `REVIEW`, using source-bound schematic values and native PCB footprint values
  from snapshot schema 13 or later.
- **Priority:** P1 fabrication-handoff consistency. The schematic component
  value and board footprint value can drift after separate edits or an
  incomplete board update.
- **Predicate:** For each case-insensitive schematic reference with a
  nonempty assigned footprint, require a matching PCB placement and fitted
  state in both sources. Compare the exact value strings after trimming
  surrounding whitespace; retain case sensitivity and report only differences.
- **Boundary:** A different value may be an intentional board label or an
  approved display choice. The finding does not establish part identity,
  electrical equivalence, assembly intent, or the correct manufacturing
  variant. DNP components, population mismatches, board-only footprints,
  schematic-only/off-board components, and variant-specific fields are outside
  this check. Projects can choose `review`, `block`, or `off`, and suppress a
  reviewed exact finding through the existing fingerprint lifecycle.
- **Evidence:** Findings bind the netlist, board, native snapshot, KiCad
  version, image, and probe digests. Snapshot schema 12 remains supported for
  footprint inventory and population checks; it keeps value coverage blocked
  until schema 13 or later is captured.
- **Fixtures:** Synthetic unit cases cover changed value text, matching
  trimmed values, DNP and incomplete-reference controls, case sensitivity,
  ordering, policy modes, and stale-ignore detection. CLI/MCP parity carries a
  typed value finding. The digest-pinned native lane repeats one matching
  control and one stale-board-value fault on KiCad 10.0.0 and 10.0.5. The
  fixture is tooling-owned and synthetic.
- **Cohort context:** The kicad-happy XV schematic/PCB consistency family
  motivated the audit. The local predicate is first-party and uses native
  KiCad evidence; no cohort implementation was copied or executed.
- **Determinism:** LINT-080 compares schematic-side and board-side value
  changes against a matching control across three isolated processes. Each
  mismatch remains a source-bound REVIEW finding; a value match is quiet. This
  tests CAD text consistency and does not establish part identity or assembly
  intent.

#### LINT-113 — Schematic pin and PCB pad net assignments differ

- **Status:** Implemented as `pcb.schematic_pcb_pad_net_mismatch`, default
  `REVIEW`, using the native schematic netlist and PCB pad snapshot schema 12
  or 13. Project policy can choose `block` or `off`; exact reviewed findings
  use the existing ignore lifecycle.
- **Priority:** P1 source consistency. Separate schematic and board edits can
  leave a connected schematic pin's same-numbered PCB pad unassigned or on a
  different net, or assign a PCB net to a pin the schematic exports as
  unconnected.
- **Predicate:** For each assigned or explicitly unconnected schematic pin,
  compare the case-insensitive component reference and exact pin number with
  the same-numbered native PCB pad when both sources contain that reference,
  the schematic has an assigned footprint, and the assigned and placed
  footprint IDs match after trimming. Report missing pads, unassigned board
  pads, exact net-name differences, and board assignments on schematic-
  unconnected pins. Evaluate each placed footprint even when marked DNP; this
  compares source assignments only and does not infer assembly population.
- **Boundary:** This is an exact source-consistency prompt. It does not infer
  that repeated connector pins, USB/serial returns, or similarly named nets
  must be bonded; that requirement must come from reviewed project intent. It
  does not prove routed copper continuity or physical conduction. A custom
  symbol's pin numbers may not map one-to-one to footprint pads, so alternate
  pin maps and mismatched footprint identities remain out of scope or require
  review. Missing, stale, or unsupported source evidence blocks coverage.
- **Fixtures:** Synthetic pytest cases cover missing, unassigned, different,
  and matched pad nets; a board assignment on an unconnected schematic pin;
  alternate-footprint and off-board controls; stable ordering; exact net-name
  comparison; policy, ignore, and stale-ignore behavior; blocked coverage;
  and pad-net-only policy selection. CLI/MCP parity carries the typed finding.
  Tooling-owned native fault/control sources are pinned and repeated on exact
  KiCad 10.0.0 and 10.0.5 in the `KICAD_RUN_NATIVE_PCB_FIXTURES` lane. The
  local exact-version lane passed both cases on 2026-10-12; hosted prerelease
  acceptance is still required. The fixture contains no project/customer
  source.
- **Incremental value:** This check catches cross-artifact assignment drift
  that same-source ERC cannot establish. It does not detect a missing
  common-ground requirement when both schematic and PCB consistently encode
  separate grounds; connector/interface peer heuristics and project-authored
  grounding contracts address that different question.
- **Determinism:** LINT-080 compares schematic-side and PCB-side net changes
  against an exact matching control across three isolated processes. Each
  mismatch remains a source-bound REVIEW finding with its reference, pin,
  exact net names, and native evidence hashes; the control is quiet. It does
  not establish routed copper continuity.

#### LINT-114 — All generic connector peers leave a contact open

- **Status:** Implemented as the opt-in, default-off rule
  `connector.generic_peer_pin_all_open`.
- **Priority:** P1 connector interface review. Similar connector instances can
  repeat an accidentally omitted contact even when generic pin labels and
  electrical types do not state whether peer contacts should be connected.
- **Predicate:** Compare at least two fitted exact-symbol peers with complete
  identical pin inventories. Cross-symbol peers are eligible only with matching
  nonempty native `PART_ID`, component value, footprint, complete pin inventory,
  and matching function and electrical-type metadata on every pin. Prompt when
  a target pin is unassigned on every peer, has absent or generic `Pin_N`
  function metadata, and has native `passive`, `input`, `output`,
  `bidirectional`, `tri_state`, `open_collector`, or `open_emitter`
  electrical type. Require at least one different pin to have the same exact
  single net assignment on every peer. Current source-matched
  `peer_assignment_group` evidence partitions the comparison.
- **Boundary:** The shared assignment is context for review only. A native
  signal type describes KiCad electrical behavior but does not identify the
  interface function, required net, or establish that the contact must connect.
  DNP peers, incomplete identities or inventories, named pin functions, mapped
  return/supply roles, and `power_in`, `power_out`, `free`, or `unspecified`
  pins are outside this rule. Cross-symbol
  matching uses the existing guarded `PART_ID` scan; it does not infer that
  aliases are interchangeable beyond the listed identity evidence. The result
  covers schematic assignments, not PCB copper continuity or off-board wiring.
  Project policy can select `review`, `block`, or `off`; the default remains
  `off` until each project decides whether this prompt is useful.
- **Fixtures:** Synthetic typed-netlist cases cover passive and each supported
  signal-type all-open fault, a
  common-net control, no shared-anchor control, distinct peer groups, DNP and
  specific-role exclusions, guarded cross-symbol `PART_ID` peers, duplicate
  suppression, stable fingerprint under input reordering, policy modes, exact
  ignores, and CLI/MCP parity. Digest-pinned native schematics verify exact-
  symbol and `PART_ID` fault/control behavior on KiCad 10.0.0 and 10.0.5 through
  `tests.test_ci_hosted_connector_returns.test_peer_pin_assignments_and_offboard_scope`.
  The local exact-version lane passed both versions on 2026-10-12. The focused
  `v0.5.0rc139` annotated-tag acceptance passed on the same date (run
  `38226360094`), including exact-version native fixtures and the installed
  wheel against a separate public template checkout. These sources are
  tooling-owned and contain no project board data. The cross-symbol all-open
  extension passed the local exact-version native lane on 2026-10-12 and its
  tagged hosted acceptance in `v0.5.0rc141` on the same date (run
  `38228971529`). The hosted gate passed the scoped lint checks, exact-version
  native fixtures, installed-wheel test against a separate project checkout,
  and preview orchestration on Ubuntu, macOS, and Windows. The signal-pin
  extension adds its own synthetic exact-symbol native fault/control and
  CLI/MCP parity cases. Its local exact-version native lane passed KiCad
  10.0.0 and 10.0.5 on 2026-10-12; its initial tagged hosted acceptance passed
  in `v0.5.0rc142` (run `38232663169`). A follow-up native matrix now checks
  all six supported signal electrical types together, with shared supply and
  return anchors, an open-pin fault, and per-contact connected control on both
  exact KiCad versions. The matrix passed the local KiCad 10.0.0/10.0.5 lane
  on 2026-10-12; its source hashes and expected results are recorded in the
  [signal-type fixture README](../tests/fixtures/design_lint/generic-peer-signal-pin-types-native/README.md).
  The tagged `v0.5.0rc143` acceptance also passed (run `38234660675`),
  including the exact-version native fixture lane, installed-wheel check
  against a separate project checkout, and preview jobs on Ubuntu, macOS, and
  Windows.
  This broadens native metadata evidence; it does not measure false-positive
  rate or reviewer value.
- **Applicability evidence:** More examples can test boundary diversity, but
  do not establish precision or reviewer value without an independent pinout
  disposition. No field-review time or false-positive rate is claimed.
- **Determinism:** LINT-080 compares the all-open generic-contact prompt and a
  connected-contact control across three isolated processes. The finding stays
  opt-in REVIEW evidence with the exact peer anchor; this does not declare the
  contact required or infer that similar pins must be joined.
- **Next:** Keep the heuristic opt-in. The `PART_ID` extension uses the same
  strict identity and pin-metadata gate as existing connector peer checks.
  Collect sanitized, independently reviewed public or synthetic boundary
  cases before considering weaker identities or a different default.

#### LINT-115 — All generic component peers leave a pin open

- **Status:** Implemented as the opt-in, default-off rule
  `component.generic_peer_pin_all_open`.
- **Priority:** P1 component-completeness review. Repeated instances can share
  a clear wiring anchor while the same generic pin remains open on every copy;
  the existing outlier checks do not report this all-open pattern.
- **Predicate:** Compare at least two fitted non-connector peers with complete,
  identical pin inventories. Peers must use the same exact native symbol or
  share a nonempty native `PART_ID` plus matching nonempty value and footprint.
  Cross-symbol groups also require identical native function and electrical
  type metadata for every pin. Prompt only when a target with absent, blank,
  generic `Pin_N`, or numeric-only function metadata has no assignment on any
  peer and another pin has the same exact single-net assignment across the
  group. Supported target electrical types are
  `passive`, `input`, `output`, `bidirectional`, `tri_state`,
  `open_collector`, and `open_emitter`.
- **Boundary:** A shared anchor provides group context only; symbol or part
  identity and common wiring do not establish the generic pin's function or
  required connection. Named functions, recognized supply and return pins,
  `power_in`, `power_out`, `free`, and `unspecified` pins, connectors,
  DNP peers, incomplete identities or inventories, and ambiguous assignments
  are outside the predicate. The prompt is default-off and can be selected as
  `review`, `block`, or `off`, or suppressed by an exact reviewed ignore.
  It covers schematic assignments, not PCB copper continuity, off-board
  wiring, physical population, or approved component requirements.
- **Fixtures:** Typed synthetic tests cover all-open faults, connected same-
  and separate-net controls, missing or different anchors, named and specific
  electrical types, DNP and connector exclusions, exact-symbol and guarded
  cross-symbol `PART_ID` peers, mismatched identities, deterministic
  fingerprints, policy and ignore behavior, source-bound applicability
  coverage, and CLI/MCP parity. Minimal digest-pinned native fault and control
  schematics are recorded in
  [the component peer fixture README](../tests/fixtures/design_lint/component-peer-generic-all-open-native/README.md);
  the local exact-version lane passed on KiCad 10.0.0 and 10.0.5 on
  2026-10-12. Tagged `v0.5.0rc145` acceptance also passed (run `38238425868`),
  including the exact-version native fixture lane, installed-wheel check against
  a separate project checkout, and preview jobs on Ubuntu, macOS, and Windows.
- **Next:** Keep the rule opt-in. Use independent, sanitized pinout
  dispositions to measure reviewer value and false positives before changing
  its default or relaxing its identity and shared-anchor requirements.

#### LINT-116 — Generic component peer pin is open on part of a group

- **Status:** Implemented as the opt-in, default-off rule
  `component.generic_peer_pin_mixed_open`.
- **Priority:** P1 component-completeness review. A generic pin can be assigned
  consistently on several fitted copies while remaining open on another; the
  role-specific component peer checks do not cover passive-pin groups, and
  this prompt adds a larger group with exact assignment consensus.
- **Predicate:** Compare at least three fitted non-connector peers with
  complete, identical pin inventories. Peers must use the same exact native
  symbol or share a nonempty native `PART_ID` plus matching nonempty value and
  footprint. Cross-symbol groups also require identical native function and
  electrical-type metadata for every pin. Prompt only when a target with
  absent, generic `Pin_N`, or numeric-only function metadata is open on
  at least one peer and assigned to the same exact single net on at least two
  other peers. Require another pin with the same exact single-net assignment
  across every peer as an anchor. Supported target electrical types are
  `passive`, `tri_state`, `open_collector`, and `open_emitter`. Native
  `input`, `output`, and `bidirectional` pins stay with their existing peer
  checks to avoid duplicate findings.
- **Boundary:** The anchor, peer identity, and assigned-peer consensus provide
  comparison context only. They do not establish the pin's function or require
  a common net. The rule is default-off and can be selected as `review`,
  `block`, or `off`, or suppressed by an exact reviewed ignore. Named
  functions, recognized supply and return pins, `power_in`, `power_out`,
  `free`, and `unspecified` pins, connectors, DNP peers, incomplete identities
  or inventories, and ambiguous assignments are outside the predicate. It
  covers schematic assignments, not PCB copper continuity, off-board wiring,
  physical population, or approved component requirements.
- **Fixtures:** Typed synthetic tests cover subset-open faults, connected,
  disagreeing-net, one-assigned-peer, two-peer, missing-anchor, DNP,
  connector, electrical-type, function, identity, policy, ignore, and
  input-order controls. CLI/MCP parity and source-bound coverage use the same
  three-peer fault and connected control. Digest-pinned native fault/control
  schematics are recorded in
  [the mixed-open fixture README](../tests/fixtures/design_lint/component-peer-generic-mixed-open-native/README.md);
  the local exact-version lane passed on KiCad 10.0.0 and 10.0.5. Tagged
  hosted acceptance for `v0.5.0rc146` passed on 2026-10-12 (GitHub Actions
  run `38241901424`) with `KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES=1`,
  including the scoped pytest gate, installed-wheel check against a separate
  project checkout, and Ubuntu, macOS, and Windows preview jobs.
- **Next:** Keep the rule opt-in. Use independently reviewed, sanitized
  pinout examples to measure whether the prompt catches useful regressions and
  to record false positives before considering broader peer identities or a
  default-mode change.

#### LINT-117 — Generic peer power-input assignments diverge

- **Status:** Implemented as the default-`REVIEW` rule
  `component.peer_power_input_assignment_divergence`.
- **Priority:** P1 component power-connectivity review. Repeated ICs or modules
  can share the same generic `power_in` pin yet be assigned to different
  schematic nets without native ERC identifying the relationship for review.
- **Predicate:** Compare one pin number across fitted non-connector instances
  of the exact same native symbol only when every peer has a complete,
  identical pin inventory, the target function metadata is absent or generic
  and consistent, the native electrical type is exactly `power_in`, and each
  pin has one unambiguous net assignment. Emit a review candidate when the
  assignments differ. DNP, connector, open, ambiguous, incomplete, named-role,
  and cross-symbol cases are excluded or handled by their existing rules.
- **Boundary:** This is a deterministic heuristic, not an inferred
  connectivity requirement. Matching symbol identity and `power_in` type do
  not establish that the rails must be common; separate supplies can be
  intentional. Net names are not interpreted, and the rule does not establish
  off-board connectivity, PCB copper, physical conduction, or current
  capacity. Projects can review, block, disable, or exactly ignore a finding;
  a required peer relationship belongs in a project-authored contract.
- **Evidence:** Typed synthetic cases cover split and common assignments,
  DNP and connector exclusions, open and incomplete peers, named functions,
  type and symbol mismatches, override/ignore lifecycle, deterministic output,
  and CLI/MCP parity. Dedicated minimal synthetic KiCad fault/control sources
  record the same generic `power_in` pin split and common-rail control in
  [the fixture README](../tests/fixtures/design_lint/generic-peer-power-input-assignment/README.md).
  The exact-version native lane repeats exports on KiCad 10.0.0 and 10.0.5.
  The separate `power.ic_rail_without_fitted_capacitor` review appears in both
  native reports and is tracked independently from this rule's fault/control
  outcome.
- **Hosted acceptance:** Tagged acceptance for `v0.5.0rc160` passed on
  2026-10-12 (GitHub Actions run `38256064816`). The tag selected this rule's
  focused pytest scope with its native fixture switch enabled. Fault and
  control exports passed on digest-pinned KiCad 10.0.0 and 10.0.5; the package,
  installed-wheel check against a separate project checkout, static/type/docs
  checks, and Ubuntu, macOS, and Windows preview jobs also passed.

#### LINT-118 — Generic component peer pin differs from its strict majority

- **Status:** Implemented as the default-`off` rule
  `component.generic_peer_pin_assignment_outlier`; corrected tagged acceptance
  passed in `v0.5.0rc162`.
- **Priority:** P1 component wiring review. Repeated modules or components can
  have one generic pin assigned to a different net than comparable peers, while
  ERC treats each assignment as valid.
- **Predicate:** Compare at least three fitted non-connector peers with the
  exact same native symbol, or a guarded shared PART_ID group with matching
  value, footprint, complete inventories, and per-pin function/type metadata.
  The target pin must have a generic function and one matching passive,
  tri_state, open_collector, or open_emitter type. Require one exact net per
  peer, a strict unique majority greater than half the group, at least one
  differing peer, and a separate pin assigned to the same exact net on every
  peer. Open, ambiguous, incomplete, DNP, connector, and non-generic cases are
  excluded.
- **Boundary:** This is a deterministic review heuristic, not an inferred
  connection requirement. A strict majority and shared anchor are comparison
  clues; they do not establish the target pin's function or required net.
  Projects may enable review, block, disable, or ignore a finding. Required
  relationships belong in an independently authored project contract.
  Netlist evidence does not prove PCB continuity, off-board wiring, population,
  or component behavior.
- **Evidence:** Typed synthetic cases cover a 2:1 fault and consistent,
  distinct, tied, and non-majority controls; two-peer, no-anchor, DNP,
  incomplete, ambiguous, named-function, type, symbol, and connector controls;
  project policy and ignore lifecycle; and deterministic output under mapping
  order changes. CLI/MCP parity uses synthetic assignments and a consistent
  control. Digest-pinned synthetic fault/control schematics are recorded in
  [the fixture README](../tests/fixtures/design_lint/generic-component-peer-pin-assignment-outlier/README.md).
  Exact native exports are configured for KiCad 10.0.0 and 10.0.5. Hosted run
  `38259559695` for `v0.5.0rc161` failed because the embedded unit names in both
  synthetic schematics did not match their library symbol name. The fixtures
  and native-lane policy/log assertions are corrected; the focused pinned
  KiCad 10.0.0/10.0.5 lane passes locally. The corrected tagged run
  `38260619617` passed the rule-scoped gate, installed-wheel check against a
  separate project, and macOS/Windows/Linux preview jobs.
- **Cohort input:** This rule follows the cohort lesson to emit suspicious
  groups as review candidates. No cohort implementation, private project
  source, board, or product expectation was imported.

#### LINT-119 — Named power-input pin is open on a comparable peer

- **Status:** Implemented as the default-`REVIEW` rule
  `component.peer_power_input_open_assignment` with focused synthetic,
  CLI/MCP parity, and policy-lifecycle tests. Exact-version native fixtures are
  included in the tagged acceptance gate.
- **Priority:** P1 component wiring review. A named `power_in` pin such as
  `BIAS_IN` may be left open on one repeated controller or interface component
  while its comparable peers are connected. Generic-unconnected and
  recognized supply/return checks do not necessarily identify this case.
- **Predicate:** Compare a pin only among fitted non-connector peers with an
  exact native symbol or guarded shared `PART_ID`. Require complete matching
  pin inventories, matching native `power_in` types, identical explicit
  non-generic function text that is not a recognized supply or return, and
  unambiguous assignments. Prompt when at least one peer has one net and at
  least one peer is open.
- **Boundary:** The finding asks for review. A pin may intentionally be open,
  and matching identity/function/type do not establish that peers must share a
  net. It does not infer net roles, check PCB continuity or off-board wiring,
  or establish component population. Generic pins and known supply/return
  names remain with their specific checks. Projects can promote, disable, or
  ignore the heuristic; a required connection belongs in a project-owned
  contract.
- **Evidence:** Synthetic tests cover the unique open-peer miss, assigned and
  all-open controls, DNP and connector exclusions, generic and named-role
  boundaries, incomplete metadata, stable output under mapping reordering,
  guarded PART_ID identity, configurable disposition/ignore behavior, and
  CLI/MCP parity. Minimal digest-pinned schematic fault/control sources are
  configured for exact KiCad 10.0.0 and 10.0.5 images. The native acceptance
  lane requires repeated normalized exports to match exactly.
- **Fixture correction:** Hosted run `38275613814` for `v0.5.0rc167` exposed
  that the synthetic fault still assigned both peers to separate nets. It did
  not represent an open pin. The U2 rail wire has been removed and the exact
  native fault/control lane now passes locally on KiCad 10.0.0 and 10.0.5.

#### LINT-120 — Named power-input assignments diverge across comparable peers

- **Status:** Implemented as the default-`REVIEW` rule
  `component.peer_power_input_named_assignment_divergence` with synthetic,
  CLI/MCP parity, policy-lifecycle, and exact-version native fixtures.
- **Priority:** P1 component power-connectivity review. A repeated interface or
  controller component can use the same explicit `power_in` pin function on
  two different nets while native ERC accepts each assignment independently.
- **Predicate:** Compare fitted non-connector peers by exact native symbol or
  guarded shared `PART_ID`. Require complete matching pin inventories, the same
  native `power_in` type, identical explicit non-generic function text not
  recognized as a supply or return, and exactly one net per peer. Prompt when
  those assignments include at least two distinct nets.
- **Boundary:** A split is a review question, not a connectivity requirement.
  Matching symbol or guarded part identity, pin function, and electrical type
  do not establish that the nets should be common. Generic functions, known
  supply/return roles, and open pins remain with their specific rules. The
  check does not interpret net names, validate off-board power, or establish
  PCB continuity, voltage, current capacity, or component behavior. Projects
  can review, block, disable, or fingerprint-ignore a finding; required net
  relationships belong in project-authored contracts.
- **Evidence:** Synthetic cases cover a split fault, a common-net control,
  open and all-open peers, generic and recognized supply functions, function
  and type mismatches, DNP and connector exclusions, incomplete inventories,
  ambiguous assignments, exact-symbol grouping, guarded `PART_ID` grouping,
  value-mismatch exclusion, deterministic mapping order, disposition and
  ignore lifecycle, and CLI/MCP parity. Digest-pinned minimal KiCad fault and
  control sources use native `power_in` metadata; the exact-version lane
  repeats normalized netlist exports on KiCad 10.0.0 and 10.0.5.
- **Cohort input:** This is a deterministic peer-comparison hypothesis. No
  cohort implementation, private project source, board, or product expectation
  was imported.

#### LINT-121 — Named power-input peer pins open everywhere

- **Status:** Implemented as the default-`REVIEW` rule
  `component.peer_power_input_named_all_open`. The check asks for review when
  the same explicit, unrecognized native `power_in` function is unassigned on
  every comparable fitted non-connector peer.
- **Priority:** P1 component power-connectivity review. Existing named checks
  covered split assignments and a mix of assigned and open peers, but did not
  identify a comparable group whose pins were all left open.
- **Predicate:** Require complete matching pin inventories, identical
  explicit non-generic function text not recognized as a supply or return,
  matching native `power_in` types, and at least two fitted peers. Group peers
  by exact native symbol or a guarded shared `PART_ID` with matching value and
  footprint. Emit only when every target pin has no net assignment.
- **Boundary:** The group resemblance does not establish a required
  connection. The rule makes no assignment and does not infer intent from net
  names, validate off-board power, establish PCB continuity, or prove voltage,
  current capacity, population, or component behavior. Projects can review,
  block, disable, or fingerprint-ignore the finding; required connections
  belong in project-authored contracts. Partial, assigned, ambiguous, DNP,
  connector, incomplete, mismatched, generic, and recognized supply/return
  cases remain excluded or with specific existing checks.
- **Evidence:** Synthetic fault/control cases verify the all-open prompt and a
  common assigned control, with exclusions for partial opens, generic or known
  roles, DNP, connectors, incomplete inventories, mismatched function/type,
  ambiguous assignments, and unguarded cross-symbol aliases. Tests cover
  guarded `PART_ID` identity, override and ignore behavior, stable mapping
  order, and CLI/MCP parity. Minimal digest-pinned sources are exercised with
  repeated normalized exports under exact KiCad 10.0.0 and 10.0.5 profiles.
  Local exact-native acceptance passed on 2026-10-12 for both versions; each
  fault/control export repeated to an identical normalized netlist. Tagged
  acceptance in `v0.5.0rc197` (GitHub Actions run `38314561122`) passed the
  rule-scoped gate, exact-version native fixtures, installed-wheel rehearsal
  against a separate project checkout, and portability previews on Ubuntu,
  macOS, and Windows. The stable-only `package` job was skipped by RC policy.
- **Cohort input:** This deterministic hypothesis adds first-party coverage;
  no cohort code, private project source, board, or product expectation was
  imported.

#### LINT-122 — Named supply pin assigned to a negative rail label

- **Status:** Implemented as the default-`REVIEW` rule
  `power.named_supply_pin_on_negative_rail`. The rule recognizes a narrow set
  of explicitly minus-prefixed numeric rail labels and asks for a pinout and
  rail-name review.
- **Priority:** P1 power-assignment review. ERC can accept a named supply pin
  on a separately named rail without knowing whether the documented pin role
  matches the intended board supply. This is a review clue for suspicious
  assignments, not a substitute for a project-owned pinout or voltage map.
- **Predicate:** For each fitted pin with exactly one exported net, recognize
  the pin function through the existing `power_function_key` vocabulary and
  report when the assigned net begins with `-` followed by an explicitly
  supported numeric voltage rail spelling. The recognized spellings are
  limited to the existing positive-rail aliases with the sign reversed.
- **Boundary:** A signed label and pin function do not prove electrical
  potential, a pinout defect, or project intent. A negative or re-referenced
  supply can be intentional, and custom names such as `VEE` are outside the
  predicate. DNP, unassigned, multiply assigned, unknown-function, and
  unrecognized-rail cases do not trigger. The rule does not assess ratings,
  copper continuity, population, or conduction. Project policy can promote,
  disable, or fingerprint-ignore the review; mandatory relationships belong
  in project-authored requirements.
- **Evidence:** Synthetic tests cover recognized numeric spellings, excluded
  aliases and role functions, DNP and ambiguous assignments, correction of
  the assignment, policy and exact-ignore behavior, and CLI/MCP parity. A
  minimal tooling-owned schematic fault and positive-rail control are repeated
  through the digest-pinned KiCad 10.0.0 and 10.0.5 native acceptance lane.
  The prerelease tag gate selects this rule and its native fixture; its hosted
  receipt records the selected version, source and netlist hashes, finding,
  and repeatability result.
- **Cohort input:** This is a first-party extension of named power-pin role
  review. No cohort code, private project source, board, or product expectation
  was imported.

#### LINT-123 — Named power-input connector pin open on one PART_ID alias peer

- **Status:** Implemented as the default-`REVIEW` rule
  `connector.peer_power_input_open_assignment`. It identifies an explicit
  named connector power-input contact that is assigned on one comparable
  symbol alias and open on another.
- **Priority:** P1 connector pinout review. Native ERC can accept the assigned
  and open contacts independently, while symbol aliases can prevent exact
  symbol peer checks from comparing their pin assignments.
- **Predicate:** Use the shared PART_ID peer scan, which requires matching
  native identity, value, footprint, complete pin inventories, and matching
  per-pin function and electrical-type metadata. For a fitted, explicit,
  non-generic `power_in` pin whose function is not recognized as a supply or
  return role, report when distinct symbol aliases have a mix of exactly one
  assigned net and no net assignment. Ambiguous multi-net assignments,
  same-symbol groups, all-open groups, and common assignments are excluded;
  all-open aliases are covered by LINT-124.
- **Boundary:** This is a review prompt, not a connectivity requirement.
  Similar pin metadata does not establish that pins must share a net; an open
  contact can be intentional. The rule does not infer rail roles, validate
  off-board wiring, check PCB continuity, or establish electrical approval.
  Projects can review, block, disable, or fingerprint-ignore the heuristic;
  required connections belong in project-authored contracts.
- **Evidence:** Synthetic regressions cover the alias fault, common and
  all-open controls, identity and metadata guards, generic and recognized-role
  exclusions, DNP and ambiguous assignments, deterministic output, policy and
  ignore behavior, and CLI/MCP parity. Minimal digest-pinned synthetic
  schematic fault/control sources are registered for exact KiCad 10.0.0 and
  10.0.5 native exports, including repeated normalized netlist comparison.
  The sources and their review boundary are recorded in the [synthetic alias
  fixture README](../tests/fixtures/design_lint/connector-named-power-input-peer-native/README.md).
  Hosted acceptance passed for `v0.5.0rc200` (GitHub Actions run
  `38317433341`): the annotated-tag rule selector enabled the native connector
  fixtures, and the focused unit, native, wheel, installed-wheel external
  project rehearsal, and portability preview jobs passed. The stable package
  job was skipped under prerelease policy.
- **Cohort input:** The rule adds first-party deterministic review coverage
  based on a peer-comparison hypothesis. No cohort code, private project
  source, board, or product expectation was imported.

#### LINT-124 — Named power-input connector pin open on every PART_ID alias peer

- **Status:** Implemented as the default-`REVIEW` rule
  `connector.peer_power_input_named_all_open`. It reports an explicit named
  connector power-input contact that is unassigned on every comparable
  cross-symbol alias peer.
- **Priority:** P1 connector pinout review. Exact-symbol peers already receive
  `connector.repeated_pin_function` findings, but fully open named power-input
  contacts on guarded cross-symbol aliases fell outside the generic all-open
  rule and the mixed assigned/open peer rule.
- **Predicate:** Reuse the guarded PART_ID peer scan, requiring matching
  nonempty native identity, value, footprint, complete identical pin
  inventories, and matching nonempty function and electrical-type metadata.
  Compare an explicit, non-generic `power_in` pin whose function is not a
  recognized supply or return role. Report only when every peer alias has no
  net assignment for that pin.
- **Boundary:** The finding is a review prompt, not a requirement to connect
  the contacts. Similar symbol identity and pin metadata do not prove that a
  contact is required or that peers should share a net. Mixed, assigned,
  ambiguous, DNP, same-symbol, generic, recognized supply/return, or incomplete
  groups are excluded or handled by their existing checks. The rule does not
  infer role from net names, establish PCB continuity, validate off-board
  wiring, or establish electrical approval. Required pinout intent belongs in
  project-authored requirements.
- **Evidence:** Synthetic regressions cover all-open fault detection; common,
  mixed, same-symbol, identity, metadata, DNP, and ambiguous controls; stable
  mapping order; policy and exact-ignore lifecycle; and CLI/MCP parity. A
  digest-pinned synthetic all-open schematic fault and common-net control are
  included in the exact KiCad 10.0.0 and 10.0.5 connector lane, which repeats
  normalized exports and verifies the rule outcome. The first tagged attempt
  (`v0.5.0rc201`) exposed a stale two-case unpack in the hosted result
  validator; a catalog-linked synthetic regression now covers that validator.
  The retry (`v0.5.0rc202`, GitHub Actions run `38319891413`) passed, including
  both exact-version native fixture parameters and the installed-wheel exercise
  against the separate public template checkout.
- **Cohort input:** This is a first-party complement to the cross-symbol
  connector open-assignment heuristic. No cohort code, private project source,
  board, or product expectation was imported.

#### LINT-125 — Named power-output connector pin open on one PART_ID alias peer

- **Status:** Implemented as the default-`REVIEW` rule
  `connector.peer_power_output_open_assignment`. The baseline synthetic pair
  previously produced `PASS` when a named `power_out` contact was assigned on
  one connector symbol alias and open on another.
- **Priority:** P1 connector pinout review. This fills the same cross-symbol
  peer gap for named native power outputs that LINT-123 addressed for named
  power inputs.
- **Predicate:** Reuse the guarded PART_ID scan and require matching native
  identity, value, footprint, complete pin inventories, and matching per-pin
  function and electrical-type metadata. Report explicit, unrecognized
  `power_out` functions only when distinct fitted aliases mix one-net and
  open assignments; skip any pin assigned to multiple nets.
- **Boundary:** A heuristic review prompt does not establish that the outputs
  should share a net. Common assignments, split fully assigned nets, all-open
  groups, generic functions, named supplies and returns, DNP peers, same-symbol
  groups, and incomplete identity or pin metadata do not trigger. The check does
  not infer intent from net names or establish PCB continuity, off-board
  wiring, electrical approval, or a required connection. Project-authored
  pinout requirements remain authoritative.
- **Evidence:** Synthetic fault/control tests cover the mixed assignment,
  common, all-open and split-net controls, identity and metadata guards,
  generic and recognized-role exclusions, DNP and ambiguous assignments,
  stable output, policy and exact-ignore lifecycle, and CLI/MCP parity. The
  digest-pinned tooling-owned fault/control pair uses native `power_out` pins.
  Its provenance and source hashes are recorded in the
  [fixture README](../tests/fixtures/design_lint/connector-named-power-output-peer-native/README.md).
  Hosted acceptance passed in `v0.5.0rc205` (GitHub Actions
  run `38322241068`).
  The rule-scoped unit stage ran with
  `KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1`, so the parametrized KiCad 10.0.0 and
  10.0.5 fault/control cases ran. Both versions passed repeated normalized
  netlist checks; the fault reported this rule and the control did not. The
  hosted gate also passed format, lint, Pyright, Windows typing, Markdown,
  wheel and source-distribution checks, and the external-project wheel
  playtest. Windows, macOS, and Ubuntu preview jobs passed. Earlier rc203 and
  rc204 attempts exposed and fixed the native-validator formatting issue and
  the fixture README graph link; neither required changing the rule predicate.
- **Cohort input:** The rule uses the existing peer-comparison pattern as a
  first-party deterministic heuristic. No cohort code, private project source,
  board, or product expectation was imported.

#### LINT-126 — Named power-output connector pin open on every PART_ID alias peer

- **Status:** Implemented as the default-`REVIEW` rule
  `connector.peer_power_output_named_all_open`. This is a separate all-open
  check; LINT-125 remains scoped to mixed assigned/open aliases.
- **Priority:** P1 connector pinout review. LINT-125 intentionally excludes
  groups where every alias is open. The named power-input counterpart already
  has a separate all-open rule, while generic connector checks do not identify
  this explicit, unrecognized power-output role.
- **Predicate:** Reuse the guarded PART_ID alias scan. Require fitted
  connectors with distinct native symbols, matching nonempty PART_ID, value,
  footprint, complete pin inventories, and matching per-pin function and
  electrical-type metadata. Review a pin only when the shared explicit
  function is unrecognized as generic, supply, or return, all aliases identify
  it as native `power_out`, and every alias has no net assignment. Skip
  ambiguous assignments and incomplete or mismatched groups.
- **Boundary:** All-open peers may be intentionally unused. This review prompt
  does not establish that an output contact is required or that aliases should
  share a net, infer intent from labels, or establish PCB/off-board continuity.
  Project-authored pinout and connectivity requirements remain authoritative.
- **Evidence:** Synthetic all-open fault, common and mixed-assignment controls,
  identity and metadata guards, DNP and ambiguity boundaries, stable finding
  fingerprints, policy and exact-ignore lifecycle, and CLI/MCP parity pass.
  A tooling-owned native fixture set binds source hashes and exercises the
  all-open fault plus mixed/common controls on digest-pinned KiCad 10.0.0 and
  10.0.5. Hosted run `38323683834` passed the scoped unit gate with
  `KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1`: both KiCad versions repeated all
  three cases, the all-open fault reported this rule, the mixed fault retained
  its separate rule, and the common-net control reported neither. Format,
  Ruff, Pyright, Windows typing, Markdown, wheel/sdist and installed-wheel
  checks, separate-project verification and playtest, and Ubuntu, Windows,
  and macOS preview jobs also passed.

#### LINT-127 — Named power-output connector aliases assigned to different nets

- **Status:** Implemented as the default-`REVIEW` rule
  `connector.peer_power_output_named_assignment_divergence`; focused hosted
  native acceptance passed in run `38325531351`.
- **Priority:** P1 connector pinout review. LINT-125 covers one alias assigned
  while another is open, and LINT-126 covers aliases open everywhere. The
  synthetic baseline exposed a third state: both explicit power-output pins
  are assigned, but to distinct nets, and the existing named-pin heuristics
  returned `PASS`.
- **Predicate:** Reuse the guarded cross-symbol PART_ID alias scan. Require
  fitted connector aliases with matching nonempty PART_ID, value, footprint,
  complete identical pin inventories, and matching per-pin function and
  electrical-type metadata. Review only an explicit function that is
  unrecognized as generic, supply, or return, native `power_out` on every
  alias, exactly one net assignment per alias, and at least two distinct
  schematic nets. Skip common-net, mixed, all-open, ambiguous, DNP, and
  incomplete or mismatched groups.
- **Boundary:** The different-net assignment may be intentional, including
  separately switched or isolated outputs. This review prompt does not infer
  intent from net names, say that either connection is wrong, or require the
  nets to be joined. Project-authored pinout/connectivity requirements remain
  authoritative; schematic net assignments do not establish PCB or
  off-board continuity.
- **Evidence:** The synthetic fault/control suite covers distinct rails,
  common-net, mixed, all-open, ambiguous, DNP, generic/recognized roles,
  mismatched identity and metadata, stable finding fingerprints, project
  policy and exact-ignore behavior, and CLI/MCP parity. A tooling-owned native
  fixture adds the two-rail fault beside the existing mixed, all-open, and
  common-net cases. The fixture source is hashed. Hosted run `38325531351` used
  `KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1`; the new fault reported this rule and
  all four cases repeated successfully on digest-pinned KiCad 10.0.0 and 10.0.5.
  The unit stage, Ruff, Pyright, Windows typing, Markdown, wheel/sdist and
  installed-wheel checks, separate-project verification and playtest, and
  Ubuntu, Windows, and macOS preview jobs also passed.

#### LINT-128 — Named power-input connector aliases assigned to different nets

- **Status:** Implemented as the default-`REVIEW` rule
  `connector.peer_power_input_named_assignment_divergence`; hosted native
  acceptance passed in tagged run `38326684651` (`v0.5.0rc209`).
- **Priority:** P1 connector pinout review. The input alias checks cover mixed
  assigned/open and all-open cases; LINT-120 covers non-connector peers. All
  connector aliases assigned to different nets previously returned `PASS`.
- **Predicate:** Reuse the guarded cross-symbol PART_ID alias scan. Require
  fitted connector aliases with matching nonempty PART_ID, value, footprint,
  complete identical pin inventories, and matching per-pin function and
  electrical-type metadata. Review only an explicit function that is
  unrecognized as generic, supply, or return, native `power_in` on every
  alias, exactly one net assignment per alias, and at least two distinct
  schematic nets. Skip common-net, mixed, all-open, ambiguous, DNP, and
  incomplete or mismatched groups.
- **Boundary:** Different input nets can be intentional, including separate
  power sources, switched supplies, or isolated domains. The prompt does not
  infer intent from net names, say either assignment is wrong, or require the
  nets to be joined. Project-authored pinout/connectivity requirements remain
  authoritative; schematic assignments do not establish PCB or off-board
  continuity.
- **Evidence:** Synthetic tests cover distinct rails, common-net, mixed,
  all-open, ambiguous, DNP, generic/recognized roles, mismatched identity and
  metadata, stable finding fingerprints, project policy and exact-ignore
  behavior, and CLI/MCP parity. A tooling-owned native fixture extends the
  existing mixed, all-open, and common-net cases with a two-rail fault. The
  source is hashed. Hosted tag `v0.5.0rc209` passed with
  `KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1` and a rule-scoped pytest selector;
  the native fixtures ran on the digest-pinned KiCad 10.0.0 and 10.0.5 lanes.
  The initial `v0.5.0rc208` run exposed a missing expected-source digest entry;
  registering the fixture hash fixed the harness and the corrected tagged run
  passed. The unit gate, lint and type checks, Markdown checks, wheel/sdist and
  installed-wheel checks against a separate project checkout, playtest, and
  Ubuntu, Windows, and macOS preview jobs passed.

### P2 — PCB geometry and schematic review assistance

#### LINT-129 — PCB footprint reference has no schematic counterpart

- **Status:** Implemented as the opt-in, default-`OFF` rule
  `pcb.board_only_footprint`; projects can select `REVIEW`, `BLOCK`, or `OFF`.
- **Priority:** P2 fabrication-source consistency. The existing inventory
  comparison found schematic references missing from the board but did not
  surface unmatched PCB footprint references.
- **Predicate:** Compare each nonempty native PCB footprint reference against
  every source-bound schematic netlist component reference, case-insensitively.
  Emit one review candidate per PCB reference with no schematic counterpart.
- **Boundary:** This is a review heuristic, not an error classification.
  Mechanical, fabrication, fiducial, logo, and other board-only items can be
  intentional. The rule does not infer electrical role, assembly population,
  or manufacturing intent; projects choose its mode and can suppress a reviewed
  exact finding through the fingerprint-ignore lifecycle. The predicate checks
  reference identity only.
- **Evidence:** Synthetic cases cover extra connectors and mounting-hole
  references, exact-reference controls, case-insensitive matching, stable
  ordering, duplicate-reference rejection, missing/unsupported evidence,
  `OFF`/`REVIEW`/`BLOCK`, exact ignores and stale-ignore behavior. A CLI/MCP
  parity case carries the same typed candidate. The rule-scoped tag gate also
  requires the hosted native PCB fixture lane, which captures a hashed
  synthetic J2 board twice against the exact project-selected KiCad toolchain.
  Hosted tag run `v0.5.0rc221` (`38349099362`) passed the scoped gate with
  `KICAD_RUN_NATIVE_PCB_FIXTURES=1`, including repeated native captures on
  KiCad 10.0.0 and 10.0.5. Local synthetic, static, packaging, and installed-
  wheel checks also passed. These tests establish the predicate and source
  boundary; they do not measure field precision or reviewer effort. No
  proprietary project source was used.
- **Determinism:** LINT-080 compares the unmatched mounting-hole review
  candidate with a matched-reference control across three independent Python
  hash seeds. The rule remains default-off; this synthetic fixture explicitly
  enables review mode and does not measure whether real board-only footprints
  are intentional.
- **Next:** Keep the rule default-off. Use independently reviewed, nonconfidential
  project outcomes to estimate which project classes benefit and how many
  intentional extras need ignores before considering any wider default.

#### LINT-130 — Explicitly required fitted PCB references are missing or DNP

- **Status:** Implemented as `pcb.required_fitted_reference`. A project-owned
  map activates the exact check in `BLOCK` mode by default; projects can select
  `REVIEW` or `OFF`. Enabling the rule without a map blocks coverage.
- **Priority:** P1 for projects with an independently reviewed base-assembly
  list. The existing source-to-board inventory and DNP-consistency checks can
  both be clean when a required component is absent from both sources or is
  marked DNP in both.
- **Predicate:** For each mapped reference, require a source schematic
  component and native board footprint, both fitted, with exact footprint ID.
  Optional symbol and PART_ID requirements are also compared exactly. Reference
  lookup is case-insensitive; output ordering and map fingerprints are stable
  when requirement order changes.
- **Boundary:** The project map is the requirement. No peer similarity, naming
  pattern, or repeated interface creates fitted intent. This release covers the
  base assembly only; it does not resolve variants, validate the map against an
  external BOM or approval record, or prove physical population. Missing map
  or source evidence never counts as a pass.
- **Evidence:** Synthetic faults cover a both-DNP reference, missing source and
  board references, exact-footprint mismatch, optional symbol/PART_ID
  differences, missing-map blocking, policy modes, exact ignores, stale
  fingerprints, and order invariance. The both-DNP case is an explicit control
  for LINT-111: the DNP-consistency check emits no mismatch, while LINT-130
  catches the project requirement. CLI/MCP parity and architecture boundaries
  are covered. The native fixture uses hashed synthetic sources, repeats
  KiCad exports, and compares both-DNP and both-fitted cases. Hosted
  exact-version acceptance passed on `v0.5.0rc222` (GitHub Actions run
  `38351032396`).
- **Determinism:** LINT-080 compares the both-DNP fault against a matching
  fitted control across three independent Python hash seeds. The unchanged
  generic population comparison does not report the fault; the exact
  project-authored fitted-reference rule remains the sole blocking finding.
- **Focused selection:**

  ```sh
  python -I -m pytest tests/test_pcb_required_fitted_reference.py \
    -m 'design_lint_rule(rule_id="pcb.required_fitted_reference")'
  ```

#### LINT-133 — Configured capacitive touch-pad clearance

- **Status:** Implemented as the opt-in `pcb.touch_pad_reference_clearance`
  rule with default `REVIEW`; project policy can select `BLOCK`, `OFF`, or an
  exact fingerprint ignore.
- **Priority:** P2 geometry review. The pinned kicad-happy CP-003 source audit
  identified a useful distance concept, but its naming guesses and sampled or
  bounding-box fallbacks are not adopted. A project-owned map provides the
  independently reviewed applicability and threshold.
- **Predicate:** For every mapped exact pad, compare its expected net with the
  source-bound schematic assignment and native PCB pad net. Measure the native
  effective pad shape to all filled zones with the exact mapped reference net
  and layer, then retain the closest zone and integer-nanometer clearance. A
  subminimum measurement or incomplete evidence emits a review candidate.
- **Boundary:** The check does not infer touch-pad identity from `TP`, values,
  or footprint names; does not decide that similarly named returns should be
  connected; and does not prove the reference zone is bonded to connector
  ground. It does not establish sensing performance, electrical approval,
  fabricated copper, or manufacturing readiness. The independently reviewed
  map is the authority for the threshold and exact pad.
- **Evidence:** Synthetic tests cover below-minimum fault, exact-boundary
  control, threshold-only metamorphic behavior, schematic and board net
  disagreement, absent filled copper, map constraints, source-bound request
  coverage, and CLI/MCP parity. Exact-version KiCad 10.0.0 and 10.0.5 native
  fixtures for round and oval pads passed the hosted native test stage in
  `v0.5.0rc248` (GitHub Actions run `38394572077`). The full scoped gate passed
  on `v0.5.0rc249` (run `38395063701`), including the installed-wheel check and
  three platform preview jobs. A new synthetic native case now compares a
  rotated and unrotated oval pad at matching straight zone edges and asserts
  the expected 0.5 mm clearance change. It passed on both pinned KiCad versions
  in `v0.5.0rc250` (run `38396108362`), along with the full scoped gate and
  installed-wheel check and three platform previews. The repeated native DRC
  comparison passed on both pinned versions in `v0.5.0rc251` (run
  `38397569065`): DRC reported no `clearance` violation and its normalized
  violation evidence was identical across repeats, while all four measured
  distances were below their authored minima. The fixtures are gated by
  `KICAD_RUN_NATIVE_PCB_FIXTURES`. On 2026-10-19, plated through-hole circle
  pads were added as a below-minimum fault (1.5 mm requirement, 1.0 mm measured)
  and an inclusive-boundary control (1.0 mm requirement and measurement). Both
  passed the native geometry and repeated DRC checks on KiCad 10.0.0 and 10.0.5
  in `v0.5.1rc38` (GitHub Actions run `39314208147`). The scoped run selected 14
  tests, passed the installed-wheel check against a separate project, and
  passed all three preview jobs. The initial `v0.5.1rc37` attempt exposed an
  over-specific expectation for the unrelated J1.2 oval pad; the test now
  asserts only its established oval controls and the new through-hole cases.
  Project applicability, false-positive rate, and reviewer effort remain
  follow-up evidence, not current claims.
- **Focused selection:**

  ```sh
  python -I -m pytest \
    -m 'design_lint and design_lint_rule(rule_id="pcb.touch_pad_reference_clearance")'
  ```

#### LINT-134 — Generic pin divergence across footprint-similar connector aliases

- **Status:** Implemented as `connector.footprint_peer_pin_assignment_divergence`,
  defaulting to `REVIEW`. Project policy can select `BLOCK`, `OFF`, or an exact
  fingerprint ignore.
- **Priority:** P2 discovery heuristic for connector instances whose custom
  symbol identities differ even though their native value, footprint, pin
  inventory, and per-pin metadata match. This extends the exact-symbol and
  PART_ID alias coverage without treating visual or naming similarity as a
  connectivity requirement.
- **Predicate:** Compare only fitted connectors with no native `PART_ID`,
  exact nonempty value and footprint, complete identical pin inventories, and
  matching nonempty native pin functions and electrical types. Honor a current
  source-matched peer-assignment group when one is available; otherwise keep
  the comparison unscoped. Every compared pin must have exactly one assigned
  schematic net. Review a differing generic `Pin_N` or numeric-only native
  pin-function contact only when another pin in the same scope has an exact
  common-net assignment.
- **Boundary:** Equal value, footprint, pin metadata, and a common assigned
  anchor are only a reason to review. They do not prove identical electrical
  roles or require any nets to be tied. Open and ambiguous pins, incomplete
  inventories or metadata, DNP components, and PART_ID-bearing components do
  not become divergences; coverage records those evidence gaps. Named pin
  functions remain with the existing role checks. The result cannot prove PCB
  copper continuity or off-board wiring.
- **Evidence:** Tooling-owned synthetic fault and control schematics use
  distinct symbols with matching passive pin metadata and no PART_ID. Unit
  tests cover `Pin_N` and numeric-only pin-function labels, shared-anchor
  fault detection, common and named-pin controls, incomplete inventory and
  metadata, open and ambiguous assignments,
  unanchored splits, DNP and PART_ID exclusions, peer-group isolation,
  deterministic ordering, project policy, exact ignores, and CLI/MCP parity.
  The exact-version native fixture lane covers both label styles on KiCad
  10.0.0 and 10.0.5. Hosted acceptance passed in `v0.5.1rc25` (commit
  `334fba64822dd8f31365e1306998fd36066a367c`, GitHub Actions run
  `39297613246`). The tag selected `design_lint and connector_lint` and enabled
  native connector fixtures; the version-parameterized fault/control cases
  verified numeric-only pin-function evidence and repeatable normalized
  netlists on both pinned KiCad versions. No external project source or
  expectation is used.
- **Focused selection:**

  ```sh
  python -I -m pytest tests/test_connector_footprint_peer_pins.py \
    -m 'design_lint and connector_lint'
  ```

#### LINT-135 — Generic pin open on a footprint-similar connector peer

- **Status:** Implemented as `connector.footprint_peer_pin_open_outlier`,
  defaulting to `REVIEW`. Project policy supports `BLOCK`, `OFF`, and exact
  fingerprint ignores.
- **Priority:** P2 discovery heuristic for a generic contact assigned on some
  footprint-similar connector aliases and left open on others.
- **Predicate:** Reuse LINT-134's fitted, PART_ID-free connector candidate
  requirements: distinct symbols, exact nonempty value and footprint,
  complete identical pin inventories, and matching nonempty per-pin native
  function and electrical-type metadata. Within the source-matched peer scope
  when present, review a generic `Pin_N` or numeric-only native pin-function
  contact only if assigned peers share one exact net and a different pin is
  assigned to one exact common net on every peer.
- **Boundary:** This is a prompt to inspect the pinout. Similar metadata and an
  open peer pin do not establish that the contact is required or should be
  connected. Named pins, ambiguous or split assignments, missing inventory or
  metadata, unanchored groups, DNP parts, and PART_ID-bearing parts do not
  trigger this rule. Coverage records open but unanchored groups. No copper
  continuity or off-board wiring is established.
- **Evidence:** Synthetic fault/control schematics and typed netlist cases cover
  `Pin_N` and numeric-only pin-function labels, the anchored open contact,
  common assignment, all-open and unanchored cases,
  named/incomplete/ineligible peers, stable ordering, policy/ignore behavior,
  CLI/MCP parity, and exact-version native exports for both label styles on
  KiCad 10.0.0 and 10.0.5.
  The fixture source is tooling-owned; see the
  [fixture README](../tests/fixtures/design_lint/connector-footprint-alias-native/README.md).
  Hosted native acceptance passed in `v0.5.1rc25` (commit
  `334fba64822dd8f31365e1306998fd36066a367c`, GitHub Actions run
  `39297613246`). The tag selected `design_lint and connector_lint` and enabled
  native connector fixtures; the version-parameterized open-contact faults and
  connected controls repeated on KiCad 10.0.0 and 10.0.5.
- **Focused selection:**

  ```sh
  python -I -m pytest tests/test_connector_footprint_peer_open.py \
    -m 'design_lint and connector_lint'
  ```

#### LINT-136 — Project-authored IC decoupling minimum

- **Status:** Implemented as `power.ic_decoupling_below_project_minimum`,
  defaulting to `REVIEW`. Project policy supports `BLOCK`, `OFF`, and exact
  fingerprint ignores.
- **Priority:** P2 deterministic comparison for projects that have an approved
  nominal capacitance minimum for a specific IC supply pin.
- **Predicate:** The project maps exact IC identity, one `power_in` pin and its
  net, a separate return net, every fitted two-pin capacitor counted toward
  the requirement, a positive minimum in pF, and the independent basis. The
  source-bound native netlist must match component identity, pin inventory,
  pin electrical type, fitted state, and all mapped assignments. Supported
  nominal capacitance spellings are parsed and summed; only a total below the
  authored inclusive minimum is reported as insufficient.
- **Boundary:** No component or threshold is inferred. An absent or stale map
  entry cannot detect an undeclared requirement. Unsupported values, DNP
  parts, identity drift, or pin/net divergence produce mapping review and do
  not count as capacitance. The comparison does not establish source accuracy,
  tolerance, DC-bias derating, voltage rating, placement, current demand,
  transient response, PCB connectivity, or physical return adequacy. LINT-046
  continues to cover selected capacitor-presence prompts; LINT-020 handles its
  separately mapped PCB placement question.
- **Evidence:** Tooling-owned synthetic tests cover the below-minimum fault,
  exact inclusive boundary, summed parallel capacitors, identity/topology,
  DNP-capacitor and DNP-IC mapping faults, unsupported values, stable ordering,
  project policy, and exact ignores. CLI/MCP parity exercises the same fault
  and control. Source-backed KiCad 10.0.0/10.0.5 fixtures include the
  DNP-IC case alongside a synthetic 47 nF fault and 100 nF control. The hosted
  exact-version gate passed on `v0.5.1rc35` (GitHub Actions run
  `39311021307`): all 11 source-hashed fixture cases repeated on digest-pinned
  KiCad 10.0.0 and 10.0.5. The unit, static, package-build, and installed-wheel
  checks against the separate public template also passed. These values
  are test boundaries only, not recommended design limits. No project source
  or cohort fixture is imported.
- **Focused selection:**

  ```sh
  python -I -m pytest tests/test_design_lint_ic_decoupling.py \
    -m 'design_lint and power_lint'
  ```

#### LINT-137 — Generic connector contact open on every footprint alias

- **Status:** Implemented as `connector.footprint_peer_pin_all_open`, defaulting
  to `OFF`. Project policy can select `REVIEW`, `BLOCK`, or an exact
  fingerprint ignore.
- **Priority:** P2 discovery prompt for a generic contact that is open on every
  fitted connector peer, including custom symbol aliases not covered by exact
  symbol or PART_ID grouping.
- **Predicate:** Require distinct native connector symbols with no PART_ID,
  exact nonempty value and footprint, complete identical pin inventories, and
  matching nonempty native function and electrical-type metadata. Within the
  source-matched peer scope when available, identify a generic passive or
  signal pin left unassigned on every peer only when another pin has one exact
  shared net assignment. This finding is disabled by default.
- **Boundary:** Similar metadata and a common anchor are review clues, not
  proof of identical roles or a requirement to connect the open contact. The
  rule excludes named functions, power/free/unspecified electrical types,
  ambiguous or incomplete evidence, unanchored groups, DNP parts, and
  PART_ID-bearing components. It cannot establish PCB copper continuity or
  off-board wiring. An independently approved pinout or connector contract is
  still needed to turn the prompt into a project requirement. Pins explicitly
  typed `power_in` or `power_out` remain with the dedicated unconnected-power
  rules rather than this generic-contact prompt.
- **Evidence:** Tooling-owned synthetic tests cover the anchored all-open
  fault, assigned and unanchored controls, unsupported pin roles, deterministic
  ordering, policy/ignore behavior, CLI/MCP parity, and the source-bound native
  fixture. A cross-rule regression confirms that a power-input pin left open
  across footprint aliases is reported by `connector.unconnected_power_input`,
  while the generic all-open rule stays out of that classification. The
  exact-version native lane exports the all-open fault and
  connected control twice on KiCad 10.0.0 and 10.0.5. The catalog requires the
  pinned native connector lane on rule-scoped prerelease tags; synthetic tests
  do not claim that native result. No project source or private fixture is used.
- **Focused selection:**

  ```sh
  python -I -m pytest tests/test_connector_footprint_peer_open.py \
    -m 'design_lint and connector_lint and design_lint_rule(rule_id="connector.footprint_peer_pin_all_open")'
  ```

#### LINT-138 — Native compilation proof for project custom DRC rules

- **Status:** Implemented as the native `drc_rule_compilation` verification
  check when a PCB project contains `.kicad_dru`. It is a verification gate,
  not a DesignLint catalog heuristic: no project-specific electrical intent is
  inferred, and no rule is added to the design-lint catalog.
- **Problem:** A custom rule file can be present in the project while its
  syntax prevents KiCad DRC from running. Ordinary board validation does not
  retain a direct check that KiCad evaluated the complete authored rule file.
- **Predicate:** In a temporary workspace, copy the project rule file and
  optional settings, append a uniquely named terminal track-to-track
  clearance rule, and run native DRC on a packaged synthetic board with two
  parallel traces on separate nets. Require the exact configured KiCad
  version and a report containing the terminal rule's violation. Retain only
  source hashes, command evidence, and the synthetic native report; remove
  temporary source copies.
- **Boundary:** This proves that the rule parser reached the appended rule. It
  does not prove that each authored condition or layer matches its intended
  objects, that a rule has appropriate limits, or that the design satisfies an
  electrical requirement. Syntactically valid but nonmatching rules require
  separate semantic and project-authored coverage checks.
- **Evidence:** Tooling-owned fixtures include a valid but deliberately
  nonmatching source rule, minimal project settings, and malformed syntax.
  Synthetic tests cover version, report, sentinel, source-hash, and validation
  integration behavior. The `v0.5.1rc78` and `v0.5.1rc79` hosted native runs
  passed KiCad 10.0.5 but failed the 10.0.0 control. The detailed
  `v0.5.1rc80` report showed that KiCad 10.0.0 applied the 10 mm width
  constraint but omitted the custom rule name from its `track_width`
  violation, so a name-based match could not prove the sentinel. The native
  fixture now uses a named clearance rule over two synthetic tracks and keeps
  the minimal `.kicad_pro` project context. Hosted run `v0.5.1rc81`
  (`39364277532`) set `KICAD_RUN_NATIVE_PCB_FIXTURES=1`; its unit stage passed
  489 tests with one skip, including the exact-version LINT-138 native cases
  for KiCad 10.0.0 and 10.0.5. The overall prerelease job then stopped at the
  repository-wide Ruff format check for
  `tests/fixtures/design_lint/cohort-transformer-feedback/trial_tf001.py`; that
  formatting issue is corrected in `v0.5.1rc82`. The broad
  `design_lint and pcb_lint` selector collected 490 tests locally, while rc82's
  seven explicit `Test-Path` modules collected 66. Hosted run `v0.5.1rc82`
  (`39365386701`) passed all 66 tests with no skips in 86.7 seconds. The two
  parametrized native compilation cases passed on KiCad 10.0.0 and 10.0.5
  (42.2 and 42.9 seconds). Compared with rc81, the focused unit stage ran 75%
  faster while retaining both exact-version native cases. Ruff format/lint,
  Pyright, Windows type analysis, wheel/sdist rebuild, installed-wheel
  verification against the separate and adapted template checkouts, and the
  playtest all passed; Linux, macOS, and Windows previews passed. No product
  project or private source is used.
- **Focused selection:**

  ```text
  Lint-Area: pcb_lint
  Native-Fixture: KICAD_RUN_NATIVE_PCB_FIXTURES
  Test-Path: tests/test_ci_pytest_selection.py
  Test-Path: tests/test_lint_gate_scope.py
  Test-Path: tests/test_package_ci.py
  Test-Path: tests/test_pcb_dru_compilation.py
  Test-Path: tests/test_pcb_dru_compilation_architecture.py
  Test-Path: tests/test_validate_drc_rule_compilation.py
  Test-Path: tests/test_pcb_dru_compilation_native.py
  ```

#### LINT-139 — Review explicitly ignored custom PCB rules

- **Status:** Implemented as the default-review rule
  `pcb.custom_drc_rule_ignored` for source-bound, named `.kicad_dru` rules.
- **Gap:** Mapped DRC coverage reports an Ignore severity only when a project
  has authored a matching requirement map. The native compilation probe proves
  that KiCad reaches the rule file, but neither check prompts for an ignored
  custom rule with no mapped requirement.
- **Predicate:** Parse the supported version-1 custom-rule syntax and emit one
  finding for each named top-level rule with an explicit direct
  `(severity ignore)` clause. Bind each candidate to the current rule-file hash,
  declaration ordinal and name, and exact project-configured KiCad version.
- **Policy boundary:** The finding asks an engineer to confirm the suppression
  is intentional. It does not treat Ignore as an electrical defect, infer that
  every custom rule should be active, inspect global `.kicad_pro` ignored
  checks (LINT-140 covers global core checks; LINT-141 covers per-violation
  exclusions), or evaluate
  custom-rule conditions and limits. Projects may select
  `review`, `block`, `off`, or an exact-fingerprint ignore.
- **Evidence:** Tooling-owned synthetic fault/control fragments cover explicit
  Ignore versus error, warning, and exclusion severities. Tests cover source
  hashes, stale/out-of-scope/symlink inputs, deterministic output, standard
  policy dispositions, and CLI/MCP parity. These fixtures are parser tests,
  not native KiCad acceptance or electrical requirements.
- **Focused selection:**

  ```sh
  python -I -m pytest tests/test_pcb_dru_rule_review.py \
    tests/test_design_lint_mcp_parity_pcb_dru_rule_review.py \
    -m 'design_lint and pcb_lint'
  ```

#### LINT-140 — Review suppressed core native PCB DRC checks

- **Status:** Implemented as `pcb.core_drc_check_ignored`, a default-review
  predicate over source-bound KiCad 10.x `.kicad_pro` settings.
- **Gap:** LINT-139 recognizes ignored custom `.kicad_dru` rules. A project can
  also set built-in DRC severities in
  `board.design_settings.rule_severities`; KiCad documents Ignore as disabling
  the selected check. A suppressed unconnected-items check can hide unconnected
  copper in a board DRC run, even though this does not solve schematic net-domain
  intent such as deciding whether two separately named returns should be common.
- **Predicate:** Emit one finding for each source-bound `ignore` setting among
  `unconnected_items`, `shorting_items`, `tracks_crossing`, `clearance`, and
  `copper_edge_clearance`. These checks have Error defaults in the
  [KiCad 10 DRC reference][kicad-10-drc].
  Record the settings-file hash, check ID, configured severity, and exact
  project-configured KiCad version. Scan only KiCad 10.x project settings.
- **Policy boundary:** The finding asks whether the suppression is intentional;
  it does not state that the check must be enabled or that a defect exists.
  The bounded list leaves documented default-ignore footprint and presentation
  checks quiet. Warning downgrades for the five core checks have a separate
  review rule (LINT-143); documented Error-default DFM checks set to Warning
  or Ignore are covered by LINT-144 and LINT-145. Other severity changes,
  custom-rule severities, DRC applicability, and board geometry are outside
  this rule.
  Project policy can choose `review`, `block`, `off`, or exact-fingerprint
  ignore.
- **Synthetic evidence:** Fault and valid-control `.kicad_pro` fragments cover
  an ignored unconnected-items check, active core checks, documented
  non-core ignores, Warning severity, malformed/duplicate JSON, stale source
  hashes, unsupported major versions, deterministic key order, policy
  dispositions, and CLI/MCP parity. No native KiCad process is required for
  this settings parser, and no electrical approval is inferred.
- **Public-example screen:** A read-only scan of six distinct settings files in
  the pinned public reference-template checkout at revision
  `ed89536f0dbbcb013145af2994fef41b2250143e` found no Ignore value among the
  five covered checks (`0/6` settings files). Two files used five other ignored
  checks (`footprint_filters_mismatch`, `footprint_type_mismatch`,
  `missing_courtyard`, `track_not_centered_on_via`, and
  `tuning_profile_track_geometries`); all stayed outside this rule. This is a
  bounded quiet-screen, not a field-precision estimate. Source files were not
  copied into Tooling.
- Reference: [KiCad 10 DRC documentation][kicad-10-drc].
- **Focused selection:** Run `tests/test_pcb_drc_global_severity_review.py` and
  `tests/test_design_lint_mcp_parity_pcb_drc_global_severity_review.py` with
  `-m 'design_lint and pcb_lint'`.

#### LINT-141 — Review persisted per-violation PCB DRC exclusions

- **Status:** Implemented as `pcb.drc_exclusion_present`, a source-bound
  default-review prompt for each persisted KiCad 10.0.x DRC exclusion.
- **Gap:** LINT-139 reviews ignored custom rules and LINT-140 reviews globally
  ignored core checks. KiCad also lets a reviewer exclude one individual DRC
  violation, optionally with a comment, and remembers exclusions between DRC
  runs. Excluded violations are hidden unless the Exclusions view is enabled.
  A saved exception can therefore persist after the original review context is
  forgotten or the board changes.
- **Predicate:** For PCB and PCB-only projects configured for exact KiCad
  `10.0.<patch>` versions, read `board.design_settings.drc_exclusions` from the
  source-hashed `.kicad_pro`. Support schema 2 string records and
  marker/comment pairs, reject an explicitly different settings schema, sort
  records deterministically, and emit one candidate for each unique marker.
  Record the marker, stable marker hash, optional comment, file hash, and exact
  configured patch version.
- **Policy boundary:** The finding asks an engineer to confirm that the
  individual exception remains intentional. It does not assert that the DRC
  violation is still present, that the exception is wrong, or that a saved
  comment constitutes approval. It does not run DRC, resolve marker UUIDs
  against current board objects, inspect copper, or infer electrical intent.
  Project policy can use `review`, `block`, `off`, or an exact-fingerprint
  ignore.
- **Synthetic evidence:** Separate fault and control `.kicad_pro` fragments
  cover multiple exclusions with and without comments, empty/absent lists,
  legacy marker strings, stable identity under list reordering, malformed and
  duplicate entries, duplicate JSON keys, source-hash failures, unsupported
  settings schemas and KiCad minor versions, policy dispositions, and CLI/MCP
  parity. No product board or private source is used.
- **Source basis:** KiCad 10 [documents individual exclusions and optional
  comments][kicad-10-drc-exclusions]. The [tagged 10.0.7 source][kicad-10-project-drc-exclusions]
  writes them to `board.design_settings.drc_exclusions` as marker/comment pairs.
  These sources establish serialization and UI behavior, not field precision.
- **Focused selection:**

  ```sh
  python -I -m pytest tests/test_pcb_drc_exclusion_review.py \
    tests/test_design_lint_mcp_parity_pcb_drc_exclusions.py \
    -m 'design_lint and pcb_lint'
  ```

#### LINT-142 — Review custom PCB rules that assign exclusion severity

- **Status:** Implemented as `pcb.custom_drc_rule_excluded`, a source-bound
  default-review prompt for each named version-1 `.kicad_dru` rule with a
  direct `(severity exclusion)` clause.
- **Gap:** LINT-139 prompts for custom rules with `ignore` severity. A custom
  rule can instead mark every matching violation as an exclusion. This differs
  from saving an individual exclusion in `.kicad_pro` (LINT-141), and authored
  exclusions merit review even when a rule is intentionally conditional.
- **Predicate:** Parse the supported version-1 custom-rule syntax and emit one
  finding for each named top-level rule with a direct exact
  `(severity exclusion)` clause. Bind each candidate to the current rule-file
  hash, declaration ordinal and name, exclusion severity, and exact
  project-configured KiCad version.
- **Policy boundary:** The finding asks whether excluding matching violations
  through this rule is intentional. It does not claim a violation exists, that
  the condition is broad or wrong, or that exclusion severity should be
  changed. It does not evaluate conditions or limits, run DRC, inspect board
  geometry, or replace LINT-139, LINT-141, or mapped project-authored DRC
  coverage. Projects may use `review`, `block`, `off`, or exact-fingerprint
  ignore.
- **Evidence:** Synthetic fault/control fragments cover one exclusion rule and
  active error, warning, and ignored rules. Tests cover source hash failures,
  unsupported KiCad majors and `.kicad_dru` file versions, deterministic output,
  default review disposition, and CLI/MCP parity. This static parser does not
  claim native DRC execution or electrical approval.
- **Source basis:** KiCad 10 documentation describes `exclusion` as distinct
  from `ignore`; excluded violations remain visible under the corresponding
  DRC filter. The check reviews authored use of that behavior rather than
  asserting it is wrong.
- **Focused selection:**

  ```sh
  python -I -m pytest tests/test_pcb_dru_severity_exclusion_review.py \
    tests/test_design_lint_mcp_parity_pcb_dru_severity_exclusion.py \
    -m 'design_lint and pcb_lint'
  ```

#### LINT-143 — Review Error-default core DRC checks downgraded to Warning

- **Status:** Implemented as `pcb.core_drc_check_warning`, a source-bound
  default-review prompt for each of five core KiCad 10.x DRC checks configured
  as Warning even though KiCad documents an Error default.
- **Gap:** LINT-140 reviews these same five checks when set to Ignore. A project
  can instead lower their severity to Warning. KiCad still reports warnings,
  so this check asks for review of the explicit downgrade without treating a
  visible warning as a suppressed or proven defect.
- **Predicate:** Read source-hashed KiCad 10.x `.kicad_pro` settings and emit
  one finding for each Warning setting among `unconnected_items`,
  `shorting_items`, `tracks_crossing`, `clearance`, and
  `copper_edge_clearance`. Record the settings hash, check ID, configured
  severity, and exact project-configured KiCad version.
- **Policy boundary:** The finding asks whether lowering the Error-default
  severity was intentional. It does not assert that Warning is unacceptable,
  a DRC violation exists, or that the board has an electrical defect.
  Documented DFM Error-default checks are covered separately by LINT-144;
  other built-in checks, custom rules, DRC applicability, board geometry, and
  manufacturing approval are outside the predicate. Projects may choose
  `review`, `block`, `off`, or exact-fingerprint ignore.
- **Evidence:** Synthetic fault/control settings cover two downgraded checks,
  active Error settings, an unrelated Warning setting, major-version scope,
  deterministic key ordering, default review policy, and CLI/MCP parity. No
  native DRC process or product board is used.
- **Source basis:** The KiCad 10 [DRC reference][kicad-10-drc] documents Error
  defaults for all five covered checks and states that check severities are
  configurable. The prompt records the configured choice; it does not require
  users to retain the default.
- **Focused selection:**

  ```sh
  python -I -m pytest tests/test_pcb_drc_global_warning_review.py \
    tests/test_design_lint_mcp_parity_pcb_drc_global_warning_review.py \
    -m 'design_lint and pcb_lint'
  ```

#### LINT-144 — Review documented DFM Error-default DRC checks downgraded to Warning

- **Status:** Implemented as `pcb.dfm_drc_check_warning`, a source-bound
  default-review prompt for each Warning setting among thirteen KiCad 10.0.x
  design-for-manufacturing checks documented with Error defaults.
- **Gap:** LINT-143 covers five core electrical checks. KiCad also documents
  Error defaults for manufacturing checks such as hole clearance, track width,
  annular width, malformed board outlines, and solder-mask bridges. Lowering
  those severities can leave a manufacturing condition visible only as a
  warning; this rule asks for review without asserting the board is defective.
- **Predicate:** Read the source-hashed KiCad 10.0.x `.kicad_pro` and emit one
  finding for each Warning setting among `hole_clearance`, `hole_to_hole`,
  `track_width`, `track_angle`, `track_segment_length`, `annular_width`,
  `drill_out_of_range`, `microvia_drill_out_of_range`, `courtyards_overlap`,
  `malformed_courtyard`, `invalid_outline`, `solder_mask_bridge`, and
  `track_on_post_machined_layer`. Record source hash, check ID, configured
  severity, and exact configured KiCad version.
- **Policy boundary:** Warning remains visible in DRC. The prompt asks whether
  lowering the documented default was intentional; it does not claim a DRC
  violation exists, that Warning is unacceptable for every project, or that
  manufacturing is approved. LINT-143 separately covers the core copper-edge
  check. Projects may choose `review`, `block`, `off`, or exact-fingerprint
  ignore.
- **Evidence:** Synthetic fault/control settings cover three downgraded checks,
  all thirteen Error settings, unrelated Warning defaults, a non-DFM
  signal-integrity downgrade, the separate core check, JSON key ordering,
  exact KiCad 10.0.0/10.0.5 profiles, unsupported
  9.0/10.1/11.0 versions, non-PCB projects, default REVIEW policy, and CLI/MCP
  parity. No native DRC process or product board is used.
- **Source basis:** The KiCad 10 [DRC reference][kicad-10-drc] documents the
  Error defaults. The versioned KiCad 10.0.0 and 10.0.5
  [DRC item sources][kicad-10.0.0-drc-items] and
  [10.0.5 source][kicad-10.0.5-drc-items] provide exact project-settings keys;
  no source code or project data is imported.
- **Focused selection:**

  ```sh
  python -I -m pytest tests/test_pcb_drc_dfm_warning_review.py \
    tests/test_design_lint_mcp_parity_pcb_drc_dfm_warning_review.py \
    -m 'design_lint and pcb_lint'
  ```

#### LINT-145 — Review documented DFM Error-default DRC checks set to Ignore

- **Status:** Implemented as `pcb.dfm_drc_check_ignored`, a source-bound
  default-review prompt for each explicit Ignore setting among the thirteen
  KiCad 10.0.x DFM checks documented with Error defaults.
- **Gap:** LINT-140 covers five core checks set to Ignore, and LINT-144 covers
  DFM checks lowered to Warning. A DFM check set to Ignore is disabled in DRC,
  so its violations are not reported by that check. This rule closes the
  corresponding source-settings review gap.
- **Predicate:** Read the source-hashed KiCad 10.0.x `.kicad_pro` and emit one
  finding for each Ignore setting among `hole_clearance`, `hole_to_hole`,
  `track_width`, `track_angle`, `track_segment_length`, `annular_width`,
  `drill_out_of_range`, `microvia_drill_out_of_range`, `courtyards_overlap`,
  `malformed_courtyard`, `invalid_outline`, `solder_mask_bridge`, and
  `track_on_post_machined_layer`. Record source hash, check ID, configured
  severity, and exact configured KiCad version.
- **Policy boundary:** The prompt asks whether suppressing a documented
  Error-default check was intentional. It does not claim a DRC violation
  exists, require every check to remain enabled, determine check applicability,
  or establish electrical or manufacturing approval. Core checks have
  separate rules. Projects may choose `review`, `block`, `off`, or
  exact-fingerprint ignore.
- **Evidence:** Synthetic fault/control settings cover two DFM Ignore values,
  all other DFM settings at Error or Warning, ignored checks outside this DFM
  subset, exact KiCad 10.0.0/10.0.5 profiles, unsupported 9.0/10.1/11.0
  versions, non-PCB projects, JSON key ordering, default REVIEW policy, and
  CLI/MCP parity. The source-settings parser does not run native DRC.
- **Source basis:** KiCad 10 [documents configurable DRC severities and Ignore
  behavior][kicad-10-drc]. The versioned KiCad 10.0.0 and 10.0.5
  [DRC item sources][kicad-10.0.0-drc-items] provide the check IDs and defaults;
  no source code or project data is imported.
- **Focused selection:**

  ```sh
  python -I -m pytest tests/test_pcb_drc_dfm_ignored_review.py \
    tests/test_design_lint_mcp_parity_pcb_drc_dfm_ignored_review.py \
    -m 'design_lint and pcb_lint'
  ```

#### LINT-146 — Review downgraded signal-integrity DRC checks

- **Status:** Implemented as `pcb.signal_integrity_drc_check_downgraded`, a
  source-bound default-review prompt for KiCad 10.0.x signal-integrity DRC
  settings explicitly set to Warning or Ignore.
- **Gap:** LINT-095 checks reviewed path and differential-pair requirements
  against project-authored native rules. It does not review global severity
  overrides in `.kicad_pro`. KiCad documents five signal-integrity DRC checks
  with Error defaults; projects can lower or disable those checks.
- **Predicate:** Read the source-hashed `.kicad_pro` and emit one candidate for
  each Warning or Ignore setting among `length_out_of_range`,
  `skew_out_of_range`, `too_many_vias`, `diff_pair_gap_out_of_range`, and
  `diff_pair_uncoupled_length_too_long`. Record the settings path/hash, exact
  check key, configured severity, and exact project KiCad version. Scope is
  KiCad 10.0.x PCB and PCB-only projects.
- **Policy boundary:** Warning remains visible in DRC; Ignore disables the
  check. Both findings ask whether the severity change was intentional. They
  do not claim a violation exists, assert the board has a signal-integrity
  defect, determine whether a corresponding custom constraint applies, measure
  routes, or replace project-authored path/pair coverage. Project policy may
  set `review`, `block`, `off`, or exact-fingerprint ignore.
- **Source basis:** The KiCad 10 [DRC reference][kicad-10-drc] documents the
  Error-default signal-integrity checks and Ignore behavior. Versioned
  [10.0.0][kicad-10.0.0-drc-items] and
  [10.0.5][kicad-10.0.5-drc-items] DRC item sources confirm the settings keys;
  `too_many_vias` is the serialized KiCad 10 key for the via-count check.
- **Synthetic evidence:** Tooling-owned settings fragments cover Warning,
  Ignore, unchanged Error defaults, unrelated core/DFM severity overrides,
  exact source hashing, deterministic key order, unsupported KiCad versions,
  non-PCB scope, standard REVIEW disposition, and CLI/MCP parity. The check
  reads settings and does not run native DRC.
- **Focused selection:**

  ```sh
  python -I -m pytest tests/test_pcb_signal_integrity_drc_severity.py \
    tests/test_design_lint_mcp_parity_pcb_signal_integrity_drc_severity.py \
    -m 'design_lint and pcb_lint'
  ```

#### LINT-147 — Review downgraded electrical DRC checks

- **Status:** Implemented as `pcb.electrical_drc_check_downgraded`, a
  source-bound default-review prompt for the KiCad 10.0.x `creepage` and
  `starved_thermal` checks explicitly configured as Warning or Ignore.
- **Gap:** LINT-140 and LINT-143 cover the core copper checks, LINT-144 and
  LINT-145 cover documented DFM checks, and LINT-146 covers signal-integrity
  checks. These two Error-default electrical checks were not included in those
  bounded groups. Lowering or disabling creepage review can hide short
  separation against an authored creepage constraint; lowering or disabling
  starved-thermal review can conceal insufficient thermal-relief spokes.
- **Predicate:** Read the source-hashed `.kicad_pro` and emit one candidate
  for each Warning or Ignore setting among `creepage` and `starved_thermal`.
  Record the settings hash, exact key, configured severity, and exact
  project-configured KiCad version. Scope is PCB and PCB-only projects using
  KiCad 10.0.x.
- **Policy boundary:** The finding asks whether the explicit severity change
  is intentional. It does not prove that a creepage constraint applies, that
  a pad uses thermal relief, that a violation exists, or that the selected
  severity is unacceptable. It does not run DRC or inspect board copper.
  Project policy may choose `review`, `block`, `off`, or exact-fingerprint
  ignore; no electrical or manufacturing approval is inferred.
- **Source basis:** The KiCad 10 [DRC reference][kicad-10-drc] documents both
  checks with Error defaults. Versioned [10.0.0][kicad-10.0.0-drc-items] and
  [10.0.5][kicad-10.0.5-drc-items] sources confirm the serialized keys, and
  both `board_design_settings.cpp` versions initialize all checks to Error
  before applying documented exceptions. No KiCad source or project data is
  imported.
- **Synthetic evidence:** Tooling-owned fault/control settings cover Warning,
  Ignore, unchanged Error defaults, unrelated lowered severities, exact source
  hashing, deterministic key order, unsupported KiCad versions, non-PCB
  scope, standard REVIEW disposition, and CLI/MCP parity. No native DRC
  process or product board is used.
- **Focused selection:**

  ```sh
  python -I -m pytest tests/test_pcb_electrical_drc_severity.py \
    tests/test_design_lint_mcp_parity_pcb_electrical_drc_severity.py \
    -m 'design_lint and pcb_lint'
  ```

#### LINT-148 — Review lowered miscellaneous DRC checks

- **Status:** Implemented as `pcb.miscellaneous_drc_check_downgraded`, a
  source-bound default-review prompt for KiCad 10.0.x miscellaneous checks
  whose configured severity is explicitly Warning or Ignore.
- **Gap:** Earlier severity reviews cover the core, DFM, signal-integrity, and
  electrical groups. They did not cover nine other Error-default settings:
  `footprint`, `item_on_disabled_layer`, `items_not_allowed`,
  `npth_inside_courtyard`, `pth_inside_courtyard`, `text_on_edge_cuts`,
  `through_hole_pad_without_hole`, `unresolved_variable`, and
  `zones_intersect`.
- **Predicate:** Read the source-hashed `.kicad_pro` and emit one candidate
  for each explicit Warning or Ignore value among those exact settings for a
  PCB or PCB-only project configured for KiCad 10.0.x. Record the settings
  hash, exact key, severity, and exact configured KiCad version.
- **Policy boundary:** The finding asks whether the explicit severity change
  was intentional. It does not establish that the check applies to the board,
  that a DRC violation exists, or that every project must retain Error. It
  does not run DRC or inspect board geometry; project policy can choose
  `review`, `block`, `off`, or exact-fingerprint ignore.
- **Source basis:** The KiCad 10 [DRC reference][kicad-10-drc] documents the
  Error defaults for eight checks in its miscellaneous table. Versioned
  [10.0.0][kicad-10.0.0-drc-items] and [10.0.5][kicad-10.0.5-drc-items]
  DRC item sources identify all nine serialized keys and list them as
  user-editable; `board_design_settings.cpp` in both versions initializes all
  severities to Error before applying explicit exceptions. The
  `text_on_edge_cuts` Error default is source-confirmed because it is omitted
  from the manual's table. No KiCad source or project design is imported.
- **Synthetic evidence:** Tooling-owned settings cover Warning and Ignore for
  all nine keys, unchanged Error controls, unrelated default Warning/Ignore
  severities, source-hash changes, deterministic ordering, exact KiCad 10.0.0
  and 10.0.5 support, unsupported versions, PCB-only and non-PCB scopes,
  standard REVIEW disposition, and CLI/MCP parity. No native DRC process or
  product board is used.
- **Focused selection:**

  ```sh
  python -I -m pytest \
    -m 'design_lint and design_lint_rule(rule_id="pcb.miscellaneous_drc_check_downgraded")'
  ```

#### LINT-149 — Review ignored Warning-default native DRC checks

- **Status:** Implemented as `pcb.warning_default_drc_check_ignored`, a
  source-bound default-review prompt for explicit `Ignore` settings on native
  DRC checks whose built-in default is Warning in the reviewed KiCad releases.
- **Gap:** Existing DRC severity rules focused on checks whose built-in
  default is Error. KiCad also runs useful checks at Warning by default, and
  changing one to Ignore disables it entirely.
- **Predicate:** For PCB or PCB-only projects configured for exact KiCad
  `10.0.0`, `10.0.3`, `10.0.4`, `10.0.5`, `10.0.6`, or `10.0.7`, read the
  source-hashed `.kicad_pro` and report each
  explicit `Ignore` value among `connection_width`, `copper_sliver`,
  `duplicate_footprints`, `extra_footprint`, `hole_to_hole`,
  `holes_co_located`, `isolated_copper`, `lib_footprint_issues`,
  `lib_footprint_mismatch`, `mirrored_text_on_front_layer`,
  `missing_footprint`, `missing_tuning_profile`, `net_conflict`,
  `nonmirrored_text_on_back_layer`, `padstack`, `schematic_fields_parity`,
  `schematic_parity`, `silk_edge_clearance`, `silk_over_copper`,
  `silk_overlap`, `text_height`, `text_thickness`, `track_dangling`, and
  `via_dangling`. Record the settings hash, key, severity, and exact project
  version.
- **Policy boundary:** The finding asks whether suppressing the check was
  intentional. It does not claim a violation exists, that the rule applies to
  the board, or that every project must preserve KiCad's default. It does not
  run DRC or inspect geometry. The default is `REVIEW` and policy can override
  it per project.
- **Source basis:** Versioned KiCad 10.0.0, 10.0.3, 10.0.4, 10.0.5, 10.0.6,
  and 10.0.7 `board_design_settings.cpp` files establish the defaults; their
  `pcbnew/drc/drc_item.cpp` files map the checks to serialized project keys.
  This exact profile is deliberate: patch releases can change defaults, so
  10.0.1 and 10.0.2 remain out of scope until their source profiles are
  reviewed. No KiCad source or project design is imported.
- **Synthetic evidence:** Tooling-owned `.kicad_pro` fixtures cover every supported key set to
  Ignore, all supported keys left at Warning, unrelated ignored keys, PCB-only and non-PCB scope,
  unsupported patch versions, source-hash mutation, deterministic ordering, standard REVIEW
  disposition, and CLI/MCP parity. The exact synthetic cases and source references are recorded in
  the [fixture README](../tests/fixtures/design_lint/pcb-warning-default-drc-ignored/README.md). No
  native DRC process or product board is used.
- **Focused selection:**

  ```sh
  python -I -m pytest \
    -m 'design_lint and design_lint_rule(rule_id="pcb.warning_default_drc_check_ignored")'
  ```

#### LINT-150 — Review authored oscillator output paths

- **Status:** Implemented as `oscillator.output_load_path_mismatch`, a
  project-mapped, default-review comparison for explicitly named oscillator
  module outputs, fitted load pins, and direct or single-series-resistor
  topologies. A series path also checks its authored inclusive nominal
  resistance range.
- **Gap:** LINT-075 trialed the cohort's generic direct-load hint. It
  over-prompted on an allowed direct-drive fixture and missed wrong-part, DNP,
  and wrong-value series components. Existing generic power-path checks do not
  express an oscillator-specific nominal resistor range for named receiver
  pins.
- **Predicate:** Read `design_lint.oscillator_output_path_map` from the
  project test contract. Match exact module, load, and optional resistor
  identities; check fitted state, native pin inventory and net assignments;
  require all direct loads on the output net, or each mapped load on the
  load-side net of the named resistor; and compare its parsed nominal
  resistance to the inclusive authored range. For a mapped series path, an
  extra recognized fitted two-terminal resistor (including a zero-ohm bridge)
  across the output and load nets is also reviewable. The map SHA-256, basis,
  mapped pins, topology, resistor, and mismatch evidence are included in the
  finding.
- **Policy boundary:** This is not automatic oscillator discovery and does not
  claim that every clock needs a resistor. Direct-drive outputs are valid when
  explicitly mapped. Findings default to `REVIEW`; projects can select `block`,
  `off`, or exact-fingerprint ignore. The extra-resistor scan does not
  enumerate non-resistor or multi-component branches, resistor arrays, or
  hidden paths. The check also does not review the mapped resistor's tolerance,
  PCB routing, signal integrity, or the correctness of the authored electrical
  requirement.
- **Synthetic evidence:** Faults cover split loads, bypassed or reversed
  resistor sides, a second fitted resistor or zero-ohm bridge in parallel,
  missing and DNP components, changed module identity, and an out-of-range
  1 kΩ resistor against a synthetic 22–47 Ω requirement. Direct and in-range
  series controls, a DNP parallel resistor, an unrelated resistor, review/block/
  off/ignore lifecycle, input-order stability, catalog reachability,
  architecture ownership, and CLI/MCP parity are registered. The parity test
  uses the tooling-owned synthetic project and source-bound netlist serializer,
  so it runs without a separately configured public template checkout. A
  separate source-hashed native lane exports a 47R inclusive-boundary control
  and a 1 kOhm value fault with digest-pinned KiCad 10.0.0 and 10.0.5, then
  evaluates the native XML through the typed rule service. It checks
  repeatability and parsed resistor value. Hosted acceptance for that lane is
  recorded by its annotated lint tag. No cohort code, board, or project
  fixture was copied.
- **Focused selection:**

  ```sh
  python -I -m pytest \
    -m 'design_lint and design_lint_rule(rule_id="oscillator.output_load_path_mismatch")'
  ```

#### LINT-151 — Review named power-input pins left open on footprint-alias connectors

- **Status:** Implemented as the default-review rule
  `connector.footprint_named_power_input_open_outlier`.
- **Gap:** The existing footprint-alias open-contact heuristic only considered
  generic pin functions. A named pin can also be an explicit native `power_in`
  contact that is assigned on one similar connector and left open on another.
- **Predicate:** Compare fitted connector references with distinct native
  symbols, exact nonempty matching values and footprints, complete identical
  pin inventories, and matching nonempty native pin functions and electrical
  types. Exclude `PART_ID` groups and DNP instances. If at least two peers
  remain in one unscoped or source-matched assignment scope, review a named,
  non-generic `power_in` pin outside recognized supply and return functions
  when assigned peers share one exact net, at least one peer is open, and a
  different pin has one exact common assignment across the scope.
- **Policy boundary:** Similarity and the common anchor only make this a review
  candidate. The rule does not infer that the contacts share an electrical
  role or must connect, and does not establish PCB copper or off-board
  continuity. Generic contacts, known supply/return roles, `power_out`, all-
  open contacts, ambiguous assignments, and split assigned nets remain out of
  scope. Project policy can keep REVIEW, disable the rule, block on it, or
  record an exact-fingerprint ignore.
- **Synthetic evidence:** Tooling-owned fault and control netlists cover the
  open and commonly assigned BIAS_IN contacts, a missing common anchor,
  different assigned nets, all-open peers, recognized supply roles,
  `power_out`, DNP and `PART_ID` exclusions, stable input ordering, policy
  overrides, and CLI/MCP parity. A separate source-hashed schematic fault and
  control pair is wired into repeated native exports for KiCad 10.0.0 and
  10.0.5. Hosted results determine native acceptance; synthetic tests do not
  claim field effectiveness.
- **Focused selection:**

  ```sh
  python -I -m pytest tests/test_connector_footprint_power_input.py \
    -m 'design_lint and connector_lint and power_lint'
  ```

#### LINT-152 — Review named signal-input pins left open on footprint-alias connectors

- **Status:** Implemented as the default-review rule
  `connector.footprint_named_signal_input_open_outlier`.
- **Gap:** A named native signal input can be assigned on one footprint-similar
  connector and open on another even when the power-input and generic-contact
  rules do not apply.
- **Predicate:** Use the same complete identity and source-matched peer scope
  as LINT-151, but consider only an explicit native `input` pin with a
  non-generic function outside recognized supply and return functions. Require
  assigned peers to share one exact net, at least one open peer, and a separate
  pin with one exact common-net assignment.
- **Policy boundary:** This is a review clue only. Matching footprint, value,
  function, native type, assignments, and anchor do not prove that connectors
  share a role or that the open pin must connect. Generic names, `power_in`,
  `power_out`, passive and other types, DNP/PART_ID peers, all-open groups,
  split assignments, and unanchored groups remain outside the predicate.
  Project policy can retain REVIEW, disable the rule, block on it, or record an
  exact-fingerprint ignore.
- **Synthetic evidence:** Tooling-owned fault and control netlists include
  common-net, missing-anchor, split-net, supply/return, generic, power-type,
  DNP/PART_ID, deterministic ordering, policy, ignore, and CLI/MCP cases. A
  separate source-hashed schematic fault/control pair is registered in the
  repeated native export lane for KiCad 10.0.0 and 10.0.5. Hosted results are
  still required for native acceptance; no product-board effectiveness is
  claimed.
- **Focused selection:**

  ```sh
  python -I -m pytest tests/test_connector_footprint_signal_input.py \
    -m 'design_lint and connector_lint and interface_lint'
  ```

#### LINT-153 — Review named power-output pins left open on footprint-alias connectors

- **Status:** Implemented as the default-review rule
  `connector.footprint_named_power_output_open_outlier`.
- **Gap:** An explicit native power output can be assigned on one connector
  alias and left open on another while the existing named input and generic
  open-contact checks remain quiet.
- **Predicate:** Reuse LINT-151's complete identity and source-matched peer
  scope, but consider only a non-generic native `power_out` pin outside
  recognized supply and return functions. Require assigned peers to share one
  exact net, at least one open peer, and a separate pin with one exact common
  net assignment.
- **Policy boundary:** Similarity and a common anchor create a review prompt;
  they do not prove that connectors share an electrical role or that the open
  output must connect. Generic names, `power_in`, signal/passive types,
  recognized supply and return functions, DNP/PART_ID peers, all-open groups,
  split assignments, and unanchored groups are excluded. Project policy can
  retain REVIEW, disable the rule, block on it, or record an exact-fingerprint
  ignore.
- **Synthetic evidence:** Tooling-owned fault and common-assignment controls
  cover missing anchors, split nets, all-open peers, generic and recognized
  supply/return functions, other native types, DNP/PART_ID exclusion, stable
  ordering, policy overrides, exact ignores, and CLI/MCP parity. A distinct
  source-hashed schematic fault/control pair is registered in the repeated
  native export lane for KiCad 10.0.0 and 10.0.5. Hosted results remain needed
  for native acceptance; no product-board effectiveness is claimed.
- **Focused selection:**

  ```sh
  python -I -m pytest tests/test_connector_footprint_power_output.py \
    -m 'design_lint and connector_lint and power_lint'
  ```

#### LINT-154 — Review named signal-output pins left open on footprint-alias connectors

- **Status:** Implemented as the default-review rule
  `connector.footprint_named_signal_output_open_outlier`.
- **Gap:** The footprint-alias peer scan handles named inputs and power
  contacts, but skipped a native signal `output` function when it was assigned
  on one similar connector and open on another. A disconnected UART transmit
  contact is one plausible case; connector similarity still does not establish
  that the two contacts should connect.
- **Predicate:** Use the same complete identity and source-matched peer scope
  as LINT-151. Consider only a non-generic native `output` pin outside
  recognized supply and return functions. Require assigned peers to share one
  exact net, at least one open peer, and a separate pin with one exact common
  net assignment.
- **Policy boundary:** This is a review clue only. Same value, footprint,
  function, electrical type, and an anchor do not prove a shared role or
  required connection. Generic contacts, input and bidirectional types,
  `power_in`/`power_out`, passive or unsupported types, recognized supply and
  return functions, DNP/PART_ID peers, all-open groups, split assignments, and
  unanchored groups are excluded. Project policy can retain REVIEW, disable
  the rule, block on it, or record an exact-fingerprint ignore.
- **Synthetic evidence:** Tooling-owned cases cover an open UART_TX pin, a
  common-net control, missing anchor, split nets, all-open contacts, generic
  and recognized supply/return functions, other native pin types, DNP/PART_ID
  exclusions, ordering, policy, exact ignore, and CLI/MCP parity. A separate
  source-hashed schematic fault/control pair is registered for native netlist
  exports on KiCad 10.0.0 and 10.0.5. Hosted native results are still required
  for acceptance; no product-board effectiveness is claimed.
- **Focused selection:**

  ```sh
  python -I -m pytest tests/test_connector_footprint_signal_output.py \
    -m 'design_lint and connector_lint and interface_lint'
  ```

#### LINT-155 — Review named signal pins assigned to different nets on footprint-alias connectors

- **Status:** Implemented as the default-review rule
  `connector.footprint_named_signal_assignment_divergence`.
- **Gap:** LINT-134 reviews generic contact divergence, while named power input
  and output divergence is covered for PART_ID aliases. A named signal pin on
  distinct footprint/value aliases could be assigned to different nets without
  a review candidate.
- **Predicate:** Use fitted connectors without PART_ID, distinct native
  symbols, exact nonempty value and footprint, complete identical pin
  inventories, and matching nonempty per-pin function and electrical-type
  metadata. Honor complete source-matched peer-assignment scopes. Consider only
  non-generic functions outside recognized supply and return roles with native
  `input`, `output`, `bidirectional`, `tri_state`, `open_collector`, or
  `open_emitter` types. Require exactly one assigned net per peer, at least two
  different nets, and another pin in the same scope with one exact common net.
- **Policy boundary:** This is a default-review clue. Different nets can be
  intentional for separate ports, channels, isolation, or switching. Similar
  connector metadata and a common anchor do not prove the signal pins should
  connect or that either net assignment is wrong. Power types, passive and
  unsupported types, generic names, recognized supply/return functions,
  ambiguous or open assignments, unanchored groups, DNP parts, PART_ID aliases,
  and incomplete/mismatched evidence are outside the predicate. Projects can
  disable, block on, or exact-fingerprint-ignore the finding; required
  relationships belong in reviewed project contracts.
- **Synthetic evidence:** Fault/control cases cover native signal pin types,
  common-net controls, missing anchors, generic and supply/return functions,
  unsupported types, DNP/PART_ID exclusions, deterministic evidence, policy,
  exact-ignore behavior, and CLI/MCP parity. A source-hashed tooling-owned
  schematic fault uses UART_TX on two distinct nets and reuses the existing
  common-net output control in the pinned native connector lane. Local rule,
  catalog, marker, and parity tests pass; hosted native acceptance is pending.
- **Focused selection:**

  ```sh
  python -I -m pytest tests/test_connector_footprint_named_signal_divergence.py \
    -m 'design_lint and connector_lint and interface_lint'
  ```

#### LINT-156 — Review split named power-input assignments across footprint-alias connectors

- **Status:** Implemented as the default-review rule
  `connector.footprint_named_power_input_assignment_divergence`.
- **Gap:** The connector peer checks cover open named power inputs and split
  named signal assignments across footprint-similar aliases. A named native
  `power_in` contact assigned to distinct nets on those aliases could still
  pass when another contact provided a common anchor. Existing named
  power-input divergence covers `PART_ID` peers, not this bounded
  PART_ID-free footprint/value candidate group.
- **Predicate:** Require fitted connector instances with distinct native
  symbols, no PART_ID, exact nonempty value and footprint, complete identical
  pin inventories, and matching nonempty native function and electrical-type
  metadata. Honor a current source-matched peer-assignment group when present.
  Review an explicit, non-generic `power_in` function outside recognized
  supply and return roles when every peer has exactly one assignment to at
  least two distinct nets and another pin in the same scope has one exact
  common-net assignment.
- **Boundary:** This is a default-review heuristic. Different power-input
  nets can represent separate sources, switched rails, or isolated domains.
  Matching symbol metadata and one common anchor do not prove that the inputs
  should be joined. Generic, recognized supply/return, signal, power-output,
  passive, free, unspecified, open, ambiguous, DNP, PART_ID-bearing, or
  incomplete groups do not trigger. The finding does not establish PCB copper
  continuity or off-board wiring. Project-authored pinout or connectivity
  requirements remain the authority for blocking a specific relationship.
- **Evidence:** Synthetic tests cover a split-net fault, common-net control,
  missing-anchor and metadata/type/function exclusions, open assignments,
  DNP and PART_ID exclusions, mapping-order stability, `REVIEW`/`BLOCK`/`OFF`,
  exact-ignore behavior, and CLI/MCP parity. A source-hashed synthetic native
  fault/control pair is registered in the
  [fixture README](../tests/fixtures/design_lint/connector-footprint-named-power-input-divergence-native/README.md)
  for exact KiCad 10.0.0 and 10.0.5 exports.
  Local native KiCad is unavailable; hosted native acceptance is required by
  the rule-scoped tag gate. No project source or cohort fixture is used.
- **Focused selection:**

  ```sh
  python -I -m pytest tests -m 'design_lint and design_lint_rule(rule_id="connector.footprint_named_power_input_assignment_divergence")'
  ```

#### LINT-157 — Review split named power-output assignments across footprint-alias connectors

- **Status:** Implemented as the default-review rule
  `connector.footprint_named_power_output_assignment_divergence`.
- **Gap:** PART_ID connector peers already receive named power-output
  divergence review, but the equivalent PART_ID-free footprint/value alias
  comparison was uncovered. Two distinct native `power_out` contacts could
  remain assigned to separate nets while other pins provided a common anchor.
- **Predicate:** Reuse the bounded footprint-alias peer scan. Require fitted
  connector instances with distinct native symbols, no PART_ID, exact
  nonempty value and footprint, complete identical pin inventories, matching
  nonempty native function and electrical-type metadata, and any current
  source-matched peer-assignment group. Review an explicit, non-generic
  `power_out` function outside recognized supply and return roles when every
  peer has exactly one assignment to at least two distinct nets and another
  pin in that same scope has one exact common-net assignment.
- **Boundary:** This is a default-review heuristic. Different output nets may
  represent separate sources, switched outputs, or isolated domains. Similar
  symbols, matching metadata, and a common anchor do not prove that either
  assignment is wrong or that the outputs should be joined. Generic,
  recognized supply/return, input, signal, passive, free, unspecified, open,
  ambiguous, DNP, PART_ID-bearing, and incomplete groups do not trigger. The
  finding does not establish PCB copper continuity or off-board wiring.
  Project-authored pinout or connectivity requirements remain authoritative
  when a specific relationship must block.
- **Evidence:** Tooling-owned synthetic tests cover a split-net fault,
  common-net, unanchored, generic, supply/return, wrong native-type, mixed and
  all-open, ambiguous, incomplete or mismatched metadata, DNP, and PART_ID
  controls; mapping-order stability; configurable `REVIEW`/`BLOCK`/`OFF` and
  exact-ignore behavior; and CLI/MCP parity. A
  source-hashed native fault/control pair is registered in the
  [fixture README](../tests/fixtures/design_lint/connector-footprint-named-power-output-divergence-native/README.md)
  for the exact KiCad 10.0.0 and 10.0.5 fixture lane. Hosted native acceptance
  remains pending for this checkpoint. No project source or cohort fixture is
  used.
- **Focused selection:**

  ```sh
  python -I -m pytest tests -m 'design_lint and design_lint_rule(rule_id="connector.footprint_named_power_output_assignment_divergence")'
  ```

#### LINT-158 — Review named power-input contacts left open across footprint aliases

- **Status:** Implemented as the default-review rule
  `connector.footprint_named_power_input_all_open`.
- **Gap:** LINT-151 reviews a named power-input contact when some footprint
  aliases assign it and others leave it open; it deliberately excludes the
  all-open case. The PART_ID-based all-open rule did not cover equivalent
  PART_ID-free aliases matched only by complete, consistent footprint/value
  evidence.
- **Predicate:** Reuse the bounded footprint-alias peer scan. Require fitted
  connector instances with distinct native symbols, no PART_ID, exact
  nonempty value and footprint, complete identical pin inventories, matching
  nonempty native function and electrical-type metadata, and any current
  source-matched peer-assignment group. Review an explicit, non-generic
  `power_in` function outside recognized supply and return roles when every
  peer leaves that contact unassigned and another pin in the same scope has
  one exact common-net assignment.
- **Boundary:** This is a default-review heuristic. A power input may be
  intentionally unused or isolated. Similar symbols, matching metadata, and
  one common anchor do not prove that the contact must connect. Generic,
  recognized supply/return, signal, output, passive, free, unspecified,
  assigned, ambiguous, DNP, PART_ID-bearing, and incomplete groups do not
  trigger. Missing anchor evidence is recorded as unanchored coverage without
  a finding. The prompt does not establish PCB copper continuity or off-board
  wiring; project-authored pinout or connectivity requirements remain
  authoritative when a specific relationship must block.
- **Evidence:** Tooling-owned synthetic tests cover a common-anchor all-open
  fault; common-net, unanchored, generic, supply/return, wrong native-type,
  mixed-open, ambiguous, incomplete or mismatched metadata, DNP, and PART_ID
  controls; mapping-order stability; configurable `REVIEW`/`BLOCK`/`OFF` and
  exact-ignore behavior; and CLI/MCP parity. A source-hashed synthetic native
  fault/control pair is registered in the
  [fixture README](../tests/fixtures/design_lint/connector-footprint-named-power-input-all-open-native/README.md)
  for exact KiCad 10.0.0 and 10.0.5 exports. Hosted native acceptance passed
  under `v0.5.2rc19` (run `39386265101`). No project source or cohort fixture is
  used.
- **Focused selection:**

  ```sh
  python -I -m pytest tests -m 'design_lint and design_lint_rule(rule_id="connector.footprint_named_power_input_all_open")'
  ```

#### LINT-159 — Review named power-output contacts left open across footprint aliases

- **Status:** Implemented as the default-review rule
  `connector.footprint_named_power_output_all_open`.
- **Gap:** LINT-153 reviews a named power-output contact when some footprint
  aliases assign it and others leave it open; it deliberately excludes the
  all-open case. The PART_ID-based all-open rule did not cover equivalent
  PART_ID-free aliases matched only by complete, consistent footprint/value
  evidence.
- **Predicate:** Reuse the bounded footprint-alias peer scan. Require fitted
  connector instances with distinct native symbols, no PART_ID, exact
  nonempty value and footprint, complete identical pin inventories, matching
  nonempty native function and electrical-type metadata, and any current
  source-matched peer-assignment group. Review an explicit, non-generic
  `power_out` function outside recognized supply and return roles when every
  peer leaves that contact unassigned and another pin in the same scope has
  one exact common-net assignment.
- **Boundary:** This is a default-review heuristic. A power output may be
  intentionally unused or isolated. Similar symbols, matching metadata, and
  one common anchor do not prove that the contact must connect. Generic,
  recognized supply/return, input, signal, passive, free, unspecified,
  assigned, ambiguous, DNP, PART_ID-bearing, and incomplete groups do not
  trigger. Missing anchor evidence is recorded as unanchored coverage without
  a finding. The prompt does not establish PCB copper continuity or off-board
  wiring; project-authored pinout or connectivity requirements remain
  authoritative when a specific relationship must block.
- **Evidence:** Tooling-owned synthetic tests cover a common-anchor all-open fault; common-net,
  unanchored, generic, supply/return, wrong native-type, mixed-open, ambiguous, incomplete or
  mismatched metadata, DNP, and PART_ID controls; mapping-order stability; configurable
  `REVIEW`/`BLOCK`/`OFF` and exact-ignore behavior; and CLI/MCP parity. The source-hashed native
  fault is documented in the
  [fixture README](../tests/fixtures/design_lint/connector-footprint-named-power-output-all-open-native/README.md)
  and uses the exact common-net control from the power-output divergence fixture. Both are
  registered for exact KiCad 10.0.0 and 10.0.5 exports. Hosted native acceptance remains pending for
  this checkpoint. No project source or cohort fixture is used.
- **Focused selection:**

  ```sh
  python -I -m pytest tests -m 'design_lint and design_lint_rule(rule_id="connector.footprint_named_power_output_all_open")'
  ```

#### LINT-160 — Review named signal contacts left open across footprint aliases

- **Status:** Implemented as the default-review rule
  `connector.footprint_named_signal_all_open`.
- **Gap:** Named signal rules already review an open contact on only some
  aliases and signal contacts assigned to different nets. They did not cover a
  named signal contact left open on every otherwise matching alias.
- **Predicate:** Reuse the bounded footprint-alias peer scan. Require fitted
  connector instances with distinct native symbols, no PART_ID, exact
  nonempty value and footprint, complete identical pin inventories, matching
  nonempty native function and electrical-type metadata, and any current
  source-matched peer-assignment group. Review explicitly named, non-generic
  `input`, `output`, `bidirectional`, `tri_state`, `open_collector`, or
  `open_emitter` contacts left unassigned on every peer when a separate pin in
  the same scope has one exact common-net assignment.
- **Boundary:** This is a default-review heuristic. A signal may be intentionally
  unused or isolated. Matching metadata and one common anchor do not prove that
  the contact should connect. Generic, recognized supply/return, native power,
  passive, free, unspecified, assigned, ambiguous, DNP, PART_ID-bearing, and
  incomplete groups do not trigger. Missing anchor evidence is recorded as
  unanchored coverage without a finding. The prompt does not establish PCB
  copper continuity or off-board wiring; project-authored pinout or
  connectivity requirements remain authoritative where a relationship must
  block.
- **Evidence:** Tooling-owned synthetic netlist tests cover all six supported
  signal electrical types, an anchored all-open fault, common-net and
  unanchored controls, generic/supply/return/wrong-type/ambiguous/incomplete/
  mismatched/DNP/PART_ID exclusions, mapping-order stability, configurable
  `REVIEW`/`BLOCK`/`OFF` and exact-ignore behavior, and CLI/MCP parity. A
  source-hashed synthetic native fault/control pair is registered for exact
  KiCad 10.0.0 and 10.0.5 exports in the
  [fixture README](../tests/fixtures/design_lint/connector-footprint-named-signal-all-open-native/README.md).
  The common-net control is shared with the existing signal-output fixture.
  No project source or cohort fixture is used.
- **Focused selection:**

  ```sh
  python -I -m pytest tests -m 'design_lint and design_lint_rule(rule_id="connector.footprint_named_signal_all_open")'
  ```

#### LINT-161 — Review mode-dependent named signals left open on connector peers

- **Status:** Implemented as the default-review rule
  `connector.footprint_named_signal_mode_dependent_open_outlier`.
- **Gap:** Named input/output pins already have partial-open checks, and the
  all-open/divergence rules cover other states. Bidirectional, tri-state,
  open-collector, and open-emitter pins assigned on some similar connector
  instances but open on another had no equivalent review prompt.
- **Predicate:** Reuse the bounded footprint-alias scan. Require fitted
  connectors with distinct native symbols, no PART_ID, exact nonempty value and
  footprint, complete identical pin inventories, matching nonempty function
  and electrical-type metadata, one exact assignment on some peers, an open
  contact on another, and a separate exact common-net anchor. Input/output,
  generic, supply/return, power, passive/free/unspecified, split, ambiguous,
  incomplete, DNP, and PART_ID groups are excluded.
- **Boundary:** This is a default-review heuristic. Similar connector metadata
  and a common anchor do not establish a common electrical role or required
  connection; an open bidirectional interface may be intentionally unused or
  isolated. Project-authored connectivity requirements remain authoritative
  when a connection must block. The rule does not prove PCB copper continuity.
- **Evidence:** Synthetic tests cover all four native mode-dependent signal
  types, shared-net and unanchored controls, exclusions, stable finding order,
  `REVIEW`/`BLOCK`/`OFF` and exact-ignore behavior, and CLI/MCP parity. A
  digest-pinned synthetic native fault/control pair runs with KiCad 10.0.0 and
  10.0.5 in the hosted connector lane. No product source or cohort fixture is
  used; see the
  [fixture README](../tests/fixtures/design_lint/connector-footprint-named-signal-mode-dependent-open-native/README.md).
- **Focused selection:**

  ```sh
  python -I -m pytest tests -m 'design_lint and design_lint_rule(rule_id="connector.footprint_named_signal_mode_dependent_open_outlier")'
  ```

#### LINT-162 — Review named passive contacts left open on connector peers

- **Status:** Implemented as the default-review rule
  `connector.footprint_named_passive_open_outlier`.
- **Gap:** Named input, output, and mode-dependent signal contacts had partial-
  open review checks, but explicitly named passive contacts did not. A peer
  connector may share pin metadata and a separate common anchor while one
  instance leaves the passive contact open.
- **Predicate:** Reuse the bounded footprint-alias scan. Require fitted
  connectors with distinct native symbols, no PART_ID, exact nonempty value and
  footprint, complete identical pin inventories, matching nonempty function
  and electrical-type metadata, one exact assignment on some peers, an open
  contact on another, and a separate exact common-net anchor. Only passive
  electrical type is considered; generic, supply/return, active signal, split,
  ambiguous, incomplete, DNP, and PART_ID groups are excluded.
- **Boundary:** This is a default-review heuristic. Similar metadata and a
  common anchor do not establish that the passive contacts share an electrical
  role or must connect. Project-authored connectivity requirements remain
  authoritative when a connection must block. The rule does not prove PCB
  copper continuity.
- **Evidence:** Synthetic tests cover assigned/common and unanchored controls,
  exclusions, stable finding order, `REVIEW`/`BLOCK`/`OFF` and exact-ignore
  behavior, and CLI/MCP parity. A digest-pinned synthetic native fault/control
  pair runs with KiCad 10.0.0 and 10.0.5 in the hosted connector lane. No
  product source or cohort fixture is used; see the
  [fixture README](../tests/fixtures/design_lint/connector-footprint-named-passive-open-native/README.md).
- **Focused selection:**

  ```sh
  python -I -m pytest tests -m 'design_lint and design_lint_rule(rule_id="connector.footprint_named_passive_open_outlier")'
  ```

#### LINT-163 — Review named passive contacts assigned to different nets across connector peers

- **Status:** Implemented as the default-review rule
  `connector.footprint_named_passive_assignment_divergence`.
- **Gap:** Named signal, power-input, and power-output contacts had split-net
  review checks, but named passive contacts did not. Comparable connector
  peers can use different exact net assignments for the same explicitly named
  passive contact while a separate pin provides a common anchor.
- **Predicate:** Reuse the bounded footprint-alias scan. Require fitted
  connectors with distinct native symbols, no PART_ID, exact nonempty value
  and footprint, complete identical pin inventories, matching nonempty
  per-pin function and electrical-type metadata, one exact net per peer, at
  least two different assignments, and a separate common-net anchor. Only
  explicit passive contacts outside recognized generic, supply, and return
  roles are eligible; open, ambiguous, unanchored, incomplete, DNP, and
  PART_ID groups are excluded.
- **Boundary:** This is a default-review heuristic. Similarity and a common
  anchor do not prove that the assignments are wrong or that the nets should
  be joined. Separate passive domains can be intentional. Project-authored
  connectivity requirements remain authoritative when a connection must
  block, and the check does not prove PCB copper continuity.
- **Evidence:** Tooling-owned synthetic fault/control fixtures cover common
  assignments, unanchored and ineligible groups, metadata mismatches, mapping
  order, policy/ignore behavior, and CLI/MCP parity. The digest-pinned native
  fixture lane checks the exact assignments and repeated exports with KiCad
  10.0.0 and 10.0.5. No product source or cohort fixture is used; see the
  [fixture README](../tests/fixtures/design_lint/connector-footprint-named-passive-divergence-native/README.md).
- **Focused selection:**

  ```sh
  python -I -m pytest tests -m 'design_lint and design_lint_rule(rule_id="connector.footprint_named_passive_assignment_divergence")'
  ```

#### LINT-164 — Review split connector-alias assignments when pin metadata differs

- **Status:** Implemented as the default-review rule
  `connector.footprint_peer_pin_metadata_assignment_divergence`.
- **Gap:** The existing footprint-alias scan excludes an entire peer group when
  any pin function or electrical type differs. Coverage counted those groups
  without retaining the target pin or its assignments, so a split net on a
  metadata-mismatched pin could disappear from review.
- **Predicate:** Group fitted connector candidates with distinct native
  symbols, no PART_ID, exact nonempty value and footprint clues, and complete
  identical pin inventories. Within each current peer-assignment scope, require
  present, nonempty native function and electrical-type metadata other than
  the KiCad unnamed marker (`~`) on every peer, a
  difference in at least one metadata field, one exact assigned net per peer,
  and at least two distinct nets. Require a separate pin in the same scope to
  have one exact common-net assignment. Missing, blank, or unnamed (`~`) metadata, open or ambiguous
  targets, incomplete inventories, DNP/PART_ID groups, and unanchored or
  separately scoped peers do not produce the finding; missing metadata is
  covered by LINT-165.
- **Boundary:** The finding is default REVIEW. Different symbol pin roles may
  be intentional; matching value, footprint, inventory, and an anchor do not
  establish interchangeable connectors or a required connection. It prompts
  review of the exact symbol pinouts and project-authored requirements. It
  does not instruct the user to join nets or prove PCB continuity.
- **Evidence:** Tooling-owned synthetic fault/control and policy fixtures test
  split assignments, common-net control, exclusions, source-matched peer
  scopes, stable mapping order, and CLI/MCP parity. Digest-pinned synthetic
  schematic fixtures exercise native netlist export and repeatability on
  KiCad 10.0.0 and 10.0.5. No product project or cohort fixture is used; see
  [fixture](../tests/fixtures/design_lint/connector-footprint-peer-metadata-native/README.md).
- **Focused selection:**

  ```sh
  python -I -m pytest tests -m 'design_lint and design_lint_rule(rule_id="connector.footprint_peer_pin_metadata_assignment_divergence")'
  ```

#### LINT-165 — Review split connector-alias assignments when pin metadata is missing

- **Status:** Implemented as the default-review rule
  `connector.footprint_peer_pin_missing_metadata_assignment_divergence`.
- **Gap:** LINT-164 correctly excludes missing metadata from its metadata-
  difference comparison, but the generic footprint-alias scan only reports an
  aggregate incomplete-metadata count. It does not identify a specific split
  pin whose assignments deserve a human pinout check.
- **Predicate:** Group fitted connector candidates with distinct native
  symbols and complete identical pin inventories. Peers share exact nonempty
  trimmed, case-folded value and footprint clues and either both lack PART_ID
  or share a nonempty trimmed, case-folded PART_ID. Within each current
  peer-assignment scope, require
  missing, blank, or KiCad unnamed (`~`) function or electrical-type metadata
  on at least one peer, exactly one assigned net per peer, at least two
  different assignments, and a separate pin on one exact common net.
- **Boundary:** The finding is default REVIEW. Matching aliases and one common
  anchor do not prove interchangeable connector roles or a required connection.
  It asks the reviewer to inspect exact symbol pinouts and project-authored
  requirements; it does not direct net joining or establish PCB continuity.
  Common, open, ambiguous, unanchored, incomplete-inventory, DNP,
  mismatched-PART_ID, and cross-scope-only groups do not trigger. A matching
  PART_ID is only a project-authored similarity clue, not proof of electrical
  equivalence. Project policy can select REVIEW,
  BLOCK, or OFF and exact-fingerprint ignores.
- **Evidence:** Tooling-owned synthetic tests cover unnamed and absent pin functions, missing
  electrical types, common-assignment controls, missing anchors, open or ambiguous targets,
  incomplete inventories, DNP and mismatched-PART_ID controls, source-matched peer scopes,
  mapping-order and three-process hash-seed determinism, policy and ignore lifecycle, and CLI/MCP
  parity. A matching-PART_ID fault, common-net control, and mismatched-PART_ID control are covered.
  Separate digest-pinned fault/control pairs for peers without PART_ID and case-insensitive matching
  PART_IDs were exported twice on KiCad 10.0.0 and 10.0.5 in local Docker containers. Both
  version-parameterized native tests passed at `v0.5.2rc34` on 2026-10-20; the tests verify exact
  fixture hashes, reported native versions, repeatable normalized netlists, findings on both faults,
  and quiet controls. On 2026-10-20, the focused rule selector passed 26 tests, including a repeat
  of the exact-version native fault/control lane on KiCad 10.0.0 and 10.0.5. Hosted prerelease
  acceptance passed on tag `v0.5.2rc41` (GitHub Actions run 39420789406); its scoped
  lint and installed-wheel check passed, as did preview orchestration on Ubuntu, macOS, and Windows.
  The synthetic
  regression suite uses no product source or cohort fixture; see the
  [base fixture README](../tests/fixtures/design_lint/connector-footprint-peer-missing-metadata-native/README.md)
  and
  [PART_ID fixture README](../tests/fixtures/design_lint/connector-part-id-peer-missing-metadata-native/README.md).
- **Public applicability screen (2026-10-20):** A separate 0BSD training
  checkout at commit `ed89536f0dbbcb013145af2994fef41b2250143e` had no
  supported LINT-165 peer groups. The controller report said
  `NO_CONNECTOR_CANDIDATES`; the Arduino and Raspberry Pi status-LED reports
  said `NO_EXACT_SYMBOL_PEERS`. The passive-signal schematic-only example had
  no component records and was blocked before lint evaluation. These are
  applicability results only: the examples do not measure false positives,
  reviewer effort, or field value. No example source was copied into this
  repository, and no training finding was classified as a defect.
- **Focused selection:**

  ```sh
  python -I -m pytest tests -m 'design_lint and design_lint_rule(rule_id="connector.footprint_peer_pin_missing_metadata_assignment_divergence")'
  ```

#### LINT-166 — Review open connector peers when pin metadata is missing

- **Status:** Implemented as the default-review rule
  `connector.footprint_peer_pin_missing_metadata_open_outlier`.
- **Gap:** The complete-metadata peer scan reports open pins only when function
  and electrical-type metadata match across all peers. The missing-metadata
  rule covered split assignments but left the corresponding partial-open case
  without a pin-specific candidate.
- **Predicate:** Group fitted connector candidates with distinct symbols,
  matching nonempty value and footprint clues, complete identical pin
  inventories, and either absent PART_ID on every peer or one matching
  nonempty PART_ID. In each current peer-assignment scope, require missing,
  blank, or KiCad unnamed (`~`) metadata on at least one peer, agreement among
  all available function and electrical-type values, at least one exact
  single-net assignment, and at least one open peer. All assigned peers must
  use the same exact net. A separate pin in the same scope must have one exact
  common net assignment.
- **Policy boundary:** The candidate defaults to REVIEW. Similar symbols,
  metadata, assignments, and an anchor do not prove the pin roles match or that
  the open pin should connect. Project policy can retain REVIEW, disable the
  rule, block on it, or exact-fingerprint-ignore a finding. Project-authored
  pinout and connectivity contracts remain authoritative. The heuristic does
  not establish PCB copper or off-board continuity.
- **Evidence:** Tooling-owned fault and common-net control tests cover the
  missing-function case, same-role metadata, conflicting available metadata,
  missing anchor, common target, all-open target, ambiguity, incomplete pin
  inventory, DNP exclusion, source-matched peer scopes, deterministic output,
  policy overrides, exact ignores, and CLI/MCP parity. Separate source-hashed
  [native schematic fixtures](../tests/fixtures/design_lint/connector-footprint-peer-missing-metadata-open-native/README.md)
  exercise an explicit no-connect fault and common-net control on KiCad 10.0.0
  and 10.0.5; both version-parameterized tests passed locally on 2026-10-22.
  The fixtures contain no product source or cohort fixture. Reviewer precision
  and field value remain unmeasured.
- **Focused selection:**

  ```sh
  python -I -m pytest tests/test_connector_footprint_peer_missing_metadata_open.py \
    -m 'design_lint and connector_lint and design_lint_rule(rule_id="connector.footprint_peer_pin_missing_metadata_open_outlier")'
  ```

#### LINT-167 — Review open connector peers when known pin roles differ

- **Status:** Implemented as the default-review rule
  `connector.footprint_peer_pin_metadata_open_outlier`.
- **Gap:** LINT-164 reviews split assignments only when every peer has an
  exact net. LINT-166 reviews partial-open pins when available role metadata
  agrees or is incomplete. Neither prompts when all target metadata is present
  but differs and some connector peers are open.
- **Predicate:** Group fitted connector candidates with distinct native
  symbols, matching nonempty value and footprint clues, complete identical
  pin inventories, and no `PART_ID`. Within each current peer-assignment
  scope, require known function and electrical-type metadata on every peer and
  a difference in at least one field. Require at least one exact single-net
  assignment, at least one open peer, and the same exact net on every assigned
  peer. Require a separate exact common-net pin anchor. Ambiguous, common,
  all-open, split, and unanchored targets are excluded.
- **Policy boundary:** This is a lower-confidence REVIEW prompt. Different
  native pin roles can explain an intentional open, and matching value,
  footprint, inventory, and anchor do not prove interchangeable connectors.
  The finding asks reviewers to check exact symbol pinouts and authored
  requirements; it does not direct a connection or establish PCB copper or
  off-board continuity. Project policy can keep REVIEW, disable it, block on
  it, or exact-fingerprint-ignore it.
- **Evidence:** Synthetic fault and valid-control regressions cover common,
  split, all-open, ambiguous, unanchored, DNP, incomplete inventory, PART_ID,
  equal or missing metadata, peer scopes, determinism, policy overrides,
  exact ignores, and CLI/MCP parity. Digest-pinned synthetic native fixtures
  exercise a partial-open fault and a same-target control without a common
  anchor on KiCad 10.0.0 and 10.0.5. The source-hashed
  [native schematic fixtures](../tests/fixtures/design_lint/connector-footprint-peer-metadata-open-native/README.md)
  contain no proprietary project source. Reviewer precision and field value
  remain unmeasured.
- **Coverage correction:** Complete, differing pin functions or electrical
  types now have their own coverage count. They no longer appear as missing
  metadata or suppress the distinction between partial evaluation and absent
  evidence. The report schema advances to version 5; synthetic and exact-native
  fault cases assert the separate counts.
- **No-anchor coverage control (2026-10-22):** The synthetic case with known
  differing roles, a partially open target pin, and no common assigned anchor
  emits no LINT-167 finding and reports `PARTIALLY_EVALUATED`, one differing
  metadata group, and zero eligible matching-metadata groups. The no-finding
  result therefore remains distinguishable from a completed clean comparison.
- **Focused selection:**

  ```sh
  python -I -m pytest tests/test_connector_footprint_peer_metadata_open.py \
    -m 'design_lint and connector_lint and design_lint_rule(rule_id="connector.footprint_peer_pin_metadata_open_outlier")'
  ```

#### LINT-168 — Review unassigned generic signal contacts in mapped interfaces

- **Status:** Implemented as the default-review rule
  `connector.mapped_interface_signal_unassigned`.
- **Gap:** Peer heuristics can compare repeated connector pins, but a single
  connector can still have an unassigned generic contact whose intended signal
  role exists only in the project's independently reviewed interface map.
- **Predicate:** Require a complete connector pin inventory, complete
  source-matched interface map, current interface-catalog digest, a mapped
  `role=signal` contact with no assigned net, no intentional-open reason, a
  generic or missing native pin function, and no native `power_in` or
  `power_out` electrical type. Exclude DNP references.
- **Policy boundary:** The map supplies a review role, not proof that every
  signal contact must connect. The finding asks whether a board connection is
  missing or the contact is intentionally open. Record an intentional open in
  `unconnected_pin_reasons`; assigning a net to a pin with such a reason makes
  connector coverage incomplete. The check does not choose a target net or
  establish PCB copper or off-board continuity.
- **Evidence:** Tooling-owned synthetic fault and valid controls cover an open
  generic UART contact, a connected contact, a reasoned intentional open,
  DNP, non-signal roles, typed power pins, and source-mismatched or digestless
  coverage. Metamorphic coverage checks ordering stability and that assigning
  the contact clears the finding.
  Policy tests cover REVIEW, block, off, and exact-ignore behavior. Tooling-owned
  native fault/control schematics now cover a generic open signal contact and
  its correctly assigned UART control with digest-pinned KiCad 10.0.0 and
  10.0.5 test lanes. A synthetic CLI/MCP parity regression also confirms both
  surfaces emit the same REVIEW finding with the current interface-catalog
  digest and clear the rule when the signal pin is assigned. The hosted
  scoped acceptance on commit `6c4dc8a` passed the exact-native fault/control
  tests for KiCad 10.0.0 and 10.0.5. The overall workflow stopped later at the
  documentation reachability check; the fixture-note link below fixes that.
  No customer or proprietary board source is used; reviewer precision remains
  unmeasured.
  The [native fixture note][mapped-signal-fixture] records source hashes and
  the exact KiCad invocation.

  [mapped-signal-fixture]: ../tests/fixtures/design_lint/mapped-interface-signal-native/README.md
- **Focused selection:**

  ```sh
  python -I -m pytest \
    -m 'design_lint_rule(rule_id="connector.mapped_interface_signal_unassigned")' \
    tests/test_connector_mapped_interface_signal_unassigned.py

  python -I -m pytest \
    tests/test_design_lint_mcp_parity_mapped_interface_signal.py \
    -m 'design_lint_rule(rule_id="connector.mapped_interface_signal_unassigned")'
  ```

  Set `KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1` to include the two exact-version
  fault/control exports in package acceptance.

#### LINT-169 — Review unassigned mapped connector shield contacts

- **Status:** Implemented as the default-review rule
  `connector.mapped_interface_shield_unassigned`.
- **Gap:** A connector pin may have a reviewed shield role even when its native
  symbol pin name and electrical type do not identify that role. Generic peer
  checks cannot safely infer whether an open shield should be bonded.
- **Predicate:** Require a complete pin inventory and complete, source-matched
  interface map with the current catalog digest. A fitted mapped
  `role=shield` pin with no assigned net and no
  `unconnected_pin_reasons` entry produces REVIEW. Exclude DNP references and
  stale, incomplete, or source-mismatched evidence.
- **Policy boundary:** The authored role identifies a contact for review; it
  does not require a bond or select a bond point. A reviewer can record an
  intentional open in `unconnected_pin_reasons`, or use the existing project
  mode and exact-fingerprint ignore controls. The rule does not determine
  signal-return commonality, PCB copper continuity, chassis or external
  grounding, or physical connector assembly.
- **Evidence:** Tooling-owned synthetic fault and controls cover an open
  mapped shield, a connected shield, an intentional open, DNP exclusion,
  non-shield roles, stale or digestless maps, policy overrides, exact ignores,
  and metamorphic ordering/assignment changes. Digest-pinned native schematic
  fault/control fixtures were exercised with KiCad 10.0.0 and 10.0.5. The
  shared CLI/MCP parity regression checks both mapped signal and shield rules.
  The [native fixture note][mapped-shield-fixture] records the source hashes
  and exact-version test lane.
  No customer or proprietary board source is used; reviewer precision on real
  projects remains unmeasured.
- **Focused selection:**

  ```sh
  python -I -m pytest \
    tests/test_connector_mapped_interface_shield_unassigned.py \
    -m 'design_lint_rule(rule_id="connector.mapped_interface_shield_unassigned")'

  python -I -m pytest \
    tests/test_design_lint_mcp_parity_mapped_interface_signal.py \
    -m 'design_lint_rule(rule_id="connector.mapped_interface_shield_unassigned")'
  ```

  Set `KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1` to include the two exact-version
  native exports in package acceptance.

  [mapped-shield-fixture]: ../tests/fixtures/design_lint/mapped-interface-shield-native/README.md

#### LINT-170 — Review supported MOSFET gates without a visible peer

- **Status:** Implemented as `component.mosfet_gate_without_peer`, default
  `REVIEW`. It recognizes only the exact allowlisted three-terminal
  `Transistor_FET:Q_NMOS_*` and `Q_PMOS_*` symbols, a complete three-pin
  inventory, and one exact `G` or `Gate` function. An open gate or
  one whose assigned net has no other fitted component pin becomes a review
  candidate. DNP peers do not clear it. Any other fitted pin clears it.
- **Cohort context:** The LINT-073 MOSFET stress work is project-authored and
  source-bound; it compares explicit operating-state terminal potentials with
  authored VDS/VGS ratings. That does not identify a gate disconnected from
  every other schematic pin. No cohort detector, project design, or example
  fixture is imported for this rule.
- **Boundary:** The prompt does not say a driver or pull resistor is required,
  prove that a same-net peer can drive the gate, establish a safe default
  state, or verify PCB copper, off-board wiring, device behavior, or physical
  gate voltage. Multi-gate devices, third-party symbol identities, incomplete
  inventories, and noncanonical gate names are unsupported. Digest-pinned
  native fault/control fixtures are registered for KiCad 10.0.0 and 10.0.5;
  the `v0.5.3rc26` hosted acceptance gate passed for both versions.
- **Evidence:** Tooling-owned synthetic cases cover open-gate and DNP-peer
  faults; driver, connector, and passive peer controls; unsupported and
  multi-gate symbol controls; all eleven exact native symbol identities and
  both gate-name forms; the single-pin assigned-net case; complete-inventory
  requirements; deterministic ordering; policy modes; exact ignores; and
  CLI/MCP parity. The native gate checks source hashes, native netlist/ERC
  outputs, repeatability, and the expected fault/control candidate. It records
  unrelated native ERC warnings without treating them as approval.
- **Focused selection:**

  ```sh
  python -I -m pytest tests/test_mosfet_gate_connectivity.py \
    -m design_lint_rule

  KICAD_RUN_NATIVE_COMPONENT_RATING_FIXTURES=1 python -I -m pytest \
    tests/test_mosfet_gate_native_fixture.py \
    -m design_lint_rule
  ```

  The package acceptance workflow enables the shared component-rating native
  fixture lane, which now also runs this focused MOSFET gate source pair.
  See the [native fixture note][mosfet-gate-native] for source hashes and lane
  details.

  [mosfet-gate-native]: ../tests/fixtures/design_lint/mosfet-gate-native/README.md

#### LINT-171 — Review MOSFET gate peers without visible source bias

- **Status:** Implemented as the opt-in `component.mosfet_gate_without_visible_source_bias`
  REVIEW candidate. It defaults to `off` because driver implementations can
  establish their own disabled or unpowered state.
- **Predicate:** For the exact supported three-terminal NMOS/PMOS symbol
  allowlist, require a complete native three-pin inventory, exactly one G/Gate
  pin and one S/Source pin, distinct unambiguous net assignments, and at least
  one other fitted pin on the gate net. Prompt only when no fitted nonzero
  two-terminal resistor recognized by the shared resistor-path service is
  directly assigned across those exact schematic nets. An open gate with no
  fitted peer stays with LINT-170.
- **Boundary:** The rule does not prove that a source-bias resistor is
  required, that a driver lacks an internal pull device, or that any resistor
  value is adequate. It does not cover resistor arrays, custom reference
  schemes, alternate resistor topologies, off-board bias, PCB continuity, or
  physical safe state. Project policy can enable, block, disable, or exactly
  ignore the review prompt.
- **Fixtures:** Synthetic fault and controls cover a visible direct resistor,
  wrong-net, DNP and zero-ohm resistors, unsupported symbols and roles,
  incomplete pin assignments, DNP-only gate peers, project overrides, exact
  ignore, deterministic ordering, and adding the declared resistor to clear
  the candidate. The paired source-hashed native fixture uses the same fitted
  gate driver with and without a gate-to-source resistor, exports netlist and
  ERC twice on KiCad 10.0.0 and 10.0.5, and checks that the opt-in finding is
  limited to the no-resistor case. Applicability remains unmeasured; the rule
  stays off by default.
- **Done:** The rule has a theme-owned predicate, catalog metadata, synthetic
  fault/control/metamorphic coverage, exact-version native evidence, project
  policy handling, and backlog documentation. No project or cohort fixture is
  used.

#### LINT-172 — Review reversed polarized capacitors on named rails

- **Status:** Implemented as the default-review rule
  `component.polarized_capacitor_reversed_on_named_rails`.
- **Gap:** Native ERC checks electrical pin types and connectivity, but a
  passive polarized capacitor can connect to two valid, distinct nets with its
  positive terminal assigned to the lower named rail.
- **Predicate:** Recognize only KiCad's four exact `Device:C_Polarized`
  identities, require a fitted component and complete `{1, 2}` pin inventory,
  then require exactly one distinct net assignment per pin. KiCad maps pin 1
  to the positive terminal. Prompt only when signed numeric rail labels order
  pin 1 below pin 2, or when a clearly named negative rail / return is below a
  positive symbolic rail. Conflicting label and peer-pin roles are excluded.
- **Boundary:** This is a REVIEW heuristic. Net names and power-pin functions
  do not prove actual voltage, transient behavior, capacitor rating, board
  copper, or physical orientation. Unknown or unordered symbolic rails,
  third-party symbols, incomplete or ambiguous assignments, and DNP parts are
  not classified. Project policy can retain REVIEW, block, disable, or exact-
  fingerprint-ignore the finding.
- **Fixtures:** Synthetic regressions cover all four exact symbol identities,
  positive and negative numeric rails, return references, correct orientation,
  unordered and unknown rails, conflicting metadata, unsupported symbols,
  incomplete inventories, DNP, open and ambiguous pins, project overrides,
  exact ignores, correction, and deterministic ordering. Tooling-owned native
  fault/control schematics export netlist and ERC twice under the pinned
  KiCad 10.0.0 and 10.0.5 package-acceptance lane. The [fixture note][polarized-capacitor-native]
  records the source boundary. The pin mapping follows the official KiCad
  `Device` symbol library; no project or cohort source is used.
- **Focused selection:**

  ```sh
  python -I -m pytest tests/test_polarized_capacitor_orientation.py \
    -m 'design_lint and component_lint and design_lint_rule(rule_id="component.polarized_capacitor_reversed_on_named_rails")'

  KICAD_RUN_NATIVE_COMPONENT_RATING_FIXTURES=1 python -I -m pytest \
    tests/test_polarized_capacitor_native_fixture.py \
    -m 'design_lint and design_lint_rule(rule_id="component.polarized_capacitor_reversed_on_named_rails")'
  ```

  [polarized-capacitor-native]: ../tests/fixtures/design_lint/polarized-capacitor-native/README.md

#### LINT-173 — Review reverse-biased diodes on explicitly ordered rails

- **Status:** Implemented as `component.diode_anode_below_cathode_on_named_rails`,
  default `REVIEW`.
- **Predicate:** Recognize only fitted `Device:D` and `Device:D_Schottky`
  symbols with complete native two-pin inventory and exactly one `A` and one
  `K` function. Require one unambiguous assignment per pin to distinct nets,
  then compare conservative potential evidence from explicit numeric labels
  and unambiguous native positive/return roles. This includes a named return
  below a numeric or symbolic positive rail and a numeric negative rail below
  a symbolic positive rail. The check uses native pin roles, not assumed pin
  numbers.
- **Boundary:** A reverse-biased diode may be a valid clamp or isolation path.
  Rail names and native pin roles are review evidence rather than measured
  voltage. Conflicting return and positive roles and unordered symbolic
  positive rails are excluded. The rule does not infer required current
  direction, forward drop, device ratings, circuit requirements, PCB copper,
  or off-board behavior. Zener, TVS, multi-terminal,
  custom, DNP, incomplete, ambiguous, open, and same-net parts are excluded.
  Projects can retain `REVIEW`, block, disable, or exact-fingerprint-ignore the
  finding.
- **Fixtures:** Synthetic cases cover generic and Schottky symbols, native A/K
  role mapping independent of pin number, signed numeric rails, negative-to-
  symbolic-positive ordering, named returns, positive roles from peer-pin
  functions, conflicting role controls,
  forward/equal/unknown controls, unsupported identities, DNP, incomplete or
  ambiguous assignments, policy modes, exact ignores, ordering, and repair.
  Minimal tooling-owned KiCad sources export netlist and ERC twice on pinned
  KiCad 10.0.0 and 10.0.5. The gate checks exact source hashes, normalized
  repeatability, zero ERC errors, numeric-rail and named-return faults, and
  the forward-oriented return control.
  See the [native fixture note][diode-rail-native]. This fixture is not an
  electrical approval or field false-positive estimate.
- **Focused selection:**

  ```sh
  python -I -m pytest tests/test_diode_rail_orientation.py \
    -m 'design_lint and component_lint and design_lint_rule(rule_id="component.diode_anode_below_cathode_on_named_rails")'

  KICAD_RUN_NATIVE_COMPONENT_RATING_FIXTURES=1 python -I -m pytest \
    tests/test_diode_rail_orientation_native_fixture.py \
    -m 'design_lint and design_lint_rule(rule_id="component.diode_anode_below_cathode_on_named_rails")'
  ```

  [diode-rail-native]: ../tests/fixtures/design_lint/diode-rail-orientation-native/README.md

#### LINT-095 — Mapped PCB signal-path length and bundle-skew rule coverage

- **Status:** Implemented as the opt-in `pcb.signal_path_rule_coverage` audit.
  The full local package gate passed on 2026-10-08 (2,266 tests passed, 54
  skipped, 2,030 subtests passed), including source and wheel builds,
  rebuilt-wheel equality, and installed-wheel checks against the exact
  CI-pinned public template. Exact-version native fixtures separately passed on
  the same date for KiCad 10.0.0 and 10.0.5: each repeated control run was clean,
  each fault run reported both length and skew violations, and each ignored-
  rule control was clean. The generated boards, rules, DRC reports, normalized
  command receipts, and hash-bearing events are retained under ignored
  `build/ci/native-fixtures/pcb-signal-path/`. Baseline acceptance passed in
  `v0.5.0rc13` (run `37845619358`); the complete canonical violation-record
  comparison passed its exact-version hosted lane in `v0.5.0rc15` (run
  `37851810081`). Repeated control and ignored-rule reports were clean, and
  repeated fault reports retained both target violation records. Some raw DRC
  report hashes differed between repeats even when their canonical finding
  records matched.
- **Problem:** A board can have valid net assignments and still lack the
  reviewed path-length or bundle-skew limits that the interface depends on.
  KiCad DRC already measures these quantities, but project-authored endpoint
  intent can be absent or can drift away from the active native rule.
- **Predicate:** The project maps exact `reference.pad` endpoints, native net,
  independent basis, optional length bounds, and bundles with exact member
  path IDs, pad-selector patterns, and maximum skew. Each endpoint must be on
  the declared net in both the current native schematic netlist and PCB pad
  inventory; it must be fitted and in the same native copper component as its
  mate. Each endpoint rule requires exactly one `A.fromTo()` rule with exact
  supported bounds and a non-ignored native DRC severity. Bundle selectors
  must resolve to exactly the mapped endpoint set before their one exact skew
  rule can be credited.
- **Controls:** Missing rules, wrong bounds, duplicate matches, ignored
  severities, stale schematic endpoints, PCB net mismatches, DNP endpoints,
  split copper components, extra wildcard matches, reordered map/rule inputs,
  review/block/off/exact-ignore behavior, and explicit custom-rule
  `(severity ignore)` have synthetic pytest cases. An ignored custom rule cannot
  count as active coverage. Local lane, schedule, and native fixture tests use a
  tooling-owned synthetic checkout independent of the external template.
  CLI and MCP continue to share `inspect_design_lint`; disabled-policy parity
  passes from a tooling-owned synthetic project without the external template
  checkout. The generated control, fault, and
  explicit-ignore boards and their exact-version lane are documented in the
  [synthetic fixture record](../tests/fixtures/design_lint/signal-path/README.md).
  Hosted acceptance records hashes for each generated board, rule file, and raw
  DRC report, plus native exit codes and the command receipt. The native lane
  includes an identical-geometry case whose mapped rules explicitly use
  `(severity ignore)` and requires those target findings to disappear. Local
  mocked orchestration tests verify the evidence fields and reject both a fault
  missing a target DRC violation and an ignored rule that still reports one;
  they are not native KiCad results.
- **Evidence boundary:** The report binds project settings, board, optional
  rule file, native DRC receipt, exact native PCB connectivity snapshot and
  command, KiCad version, and source hashes. KiCad DRC measures geometry; this
  audit only verifies that the reviewed map is represented by an active rule
  and that its endpoints match source and copper evidence. It does not select
  an electrically appropriate length or skew limit, evaluate off-board
  wiring, or establish physical continuity.
- **Rule-scoped native gate registration (2026-10-12):** The exact-version DRC
  fault/control test was included in broad PCB acceptance but absent from this
  rule's fixture catalog, so `Lint-Rule: pcb.signal_path_rule_coverage` could
  not select it. The catalog now links the test as both fault and valid control,
  requires `KICAD_RUN_NATIVE_PCB_FIXTURES`, and the architecture suite guards
  that association. Hosted run `38296563673` for `v0.5.0rc186` passed the
  focused lint and installed-wheel steps plus all three portability previews;
  the package job was skipped by RC policy.
- **Privacy:** Tooling-owned synthetic data only. No project-specific source,
  observed pinout, contract, or candidate implementation is retained.

#### LINT-096 — Project-authored PCB keepout signature regression

- **Status:** Implemented as the opt-in `pcb.keepout_intent_coverage` rule.
  The native probe records rule-area names, canonical outlines and holes,
  copper-layer membership, and track/via/pad/zone-fill/footprint restrictions
  in snapshot schemas 11, 12, and 13. Synthetic extraction was run with the exact
  digest-pinned KiCad 10.0.0 and 10.0.5 images. Synthetic pytest cases cover
  exact matches, changed geometry/layers/restrictions, missing and duplicate
  names, unsupported snapshot schema, digest order stability, and review,
  block, off, and exact-ignore policy. The full local package gate passed on
  2026-10-08 against the exact CI-pinned public template (2,266 tests passed,
  54 skipped, 2,030 subtests passed), including wheel and source builds and
  installed-wheel external checks. Exact native extraction also passed against
  both pinned KiCad versions. CLI/MCP parity passes from a tooling-owned
  synthetic checkout without the public template. Tagged GitHub acceptance
  passed in `v0.5.0rc13` (run `37845619358`) and was revalidated in
  `v0.5.0rc15` (run `37851810081`).
  Schema 12 now retains footprint identity, fitted state, board origin,
  canonical microdegree orientation, and board side for the next RF keepout
  gate. Its typed and serializer tests pass. On 2026-10-09 the new
  `tests/test_pcb_keepouts_native.py` schema-12 extraction test passed on both
  digest-pinned KiCad 10.0.0 and 10.0.5 images (2 cases). It verifies exact
  front/back footprint identity, DNP state, board coordinates, canonical
  orientation, exact transformed pad centers, and pad-to-footprint binding
  alongside the synthetic rule area.
- **Problem:** A project can retain a named keepout while its outline, copper
  layers, or restrictions drift. Generic ERC/DRC does not know that the
  project intended a particular rule-area definition to remain unchanged.
- **Predicate:** The project maps one unique keepout name to an independently
  reviewed canonical geometry digest, exact copper-layer set, and all five
  native restriction flags. The source-bound probe must return exactly one
  native rule area with that name, and every observed property must match.
  Missing, duplicate, renamed, reshaped, layer-changed, restriction-changed,
  or unsupported-schema cases remain incomplete.
- **Controls:** Synthetic tests compare exact geometry, changed outlines,
  polygon/hole ordering, layer sets, restriction flags, duplicate and missing
  names, and a pre-schema-11 snapshot. Lint behavior is checked under review,
  block, off, and an exact fingerprint ignore. The geometry digest is stable
  under polygon and hole collection reordering.
- **Evidence boundary:** This checks regression of a project-authored KiCad
  rule-area definition. It cannot prove that the reviewed shape, layer set, or
  restriction flags correctly express a vendor drawing or engineering need;
  it does not establish copper exclusion on fabricated boards, module
  placement, RF behavior, or physical continuity. The map must come from an
  independent approved source, not the observed board alone.
- **Privacy:** Tooling-owned synthetic data only. No customer board, module
  outline, connector pinout, project contract, or proprietary expectation is
  retained.

#### LINT-097 — Source-mapped RF module antenna keepout coverage

- **Status:** Implemented as the active opt-in
  pcb.rf_module_antenna_keepout_coverage rule. The project-owned typed map,
  source-bound schematic/board identity checks, explicit onboard/external/DNP
  dispositions, deterministic footprint-local polygon transform, policy modes,
  report and text output are in place; configured-disabled and enabled
  fault/control reports have CLI/MCP parity. Synthetic fault,
  control, metamorphic, and review/block/off/ignore cases pass. The
  tooling-owned native fixture verifies front-side 90-degree and 30-degree,
  plus back-side 270-degree footprint transforms against actual named rule
  areas. Both exact digest-pinned KiCad 10.0.0 and 10.0.5 acceptance runs
  passed. No cohort runtime installation or proprietary board trial is claimed.
- **Cohort input:** The pinned `kicad-happy` `KO-001` source checks component
  and via centers against the bounding box of an existing keepout. That can
  prompt review of nearby objects, but cannot detect a missing keepout, check
  its exact outline, or bind it to an RF module and feed. Do not copy its code,
  thresholds, severity, or dependency.
- **Problem:** LINT-096 detects drift in an independently mapped rule-area
  signature, but does not establish which RF module or feed the area protects.
  A named area can still become detached from the antenna region when the
  module moves or changes.
- **Implemented contract:** A project-authored map names the exact module
  reference and footprint identity, RF feed pad and native net, keepout name,
  vendor-document basis, local-coordinate polygon and holes, copper layers,
  and all rule-area restriction flags. It must also explicitly disposition a
  DNP module or an external-antenna design; neither is inferred from names.
- **Predicate:** The native PCB evidence binds the fitted footprint and RF
  pad/net to the schematic source, capture footprint position, orientation and
  board side, and return exactly one named rule area. Transform the reviewed
  local polygon through the observed footprint placement and compare its exact
  canonical outline, layers and restrictions. Missing, duplicate, stale,
  unsupported, identity-changed or mismatched evidence remains incomplete.
  Default disposition is `REVIEW`; project policy may select `block`, `off`,
  or an exact fingerprint ignore.
- **Fault/control cases:** Synthetic cases cover missing, offset, duplicate,
  geometry, layer, and restriction mismatches; changed symbol, footprint,
  PART_ID, feed pin/net, and DNP state; and unsupported snapshot schema. A
  module moved without its area fails, while moving the module and area
  together passes. Explicit external-antenna and DNP controls pass. Review,
  block, off, and exact-ignore behavior is tested, as is CLI/MCP parity for a
  configured disabled report and enabled fault/control outcomes. The native
  synthetic board has mapped pads on
  front-side 90-degree and 30-degree, and back-side 270-degree footprints;
  each transformed local keepout matches a native rule-area outline on KiCad
  10.0.0 and 10.0.5.
- **Evidence boundary:** The check compares project-reviewed placement intent
  with native PCB geometry. It cannot validate that the vendor drawing was
  interpreted correctly, establish antenna performance, or prove copper
  exclusion on a fabricated board. Native DRC remains a separate check.
- **Acceptance limits:** The enabled CLI/MCP test injects source-matched
  synthetic PCB geometry at the native-scan boundary; it is service-surface
  parity, not exact native execution. Candidate runtime trial remains future
  evidence. The tool accepts only requirements authored in the project
  repository and uses synthetic fixtures here.
- **Privacy:** Develop with tooling-owned synthetic boards and maps only. Do
  not retain customer or proprietary module layouts or contracts.

#### LINT-020 — Decoupling-capacitor proximity and connection evidence

- **Status:** Implemented v2 as the opt-in `pcb.decoupling_proximity` rule with
  project-authored pad and optional return-via distance limits, plus a
  source-bound native PCB snapshot.
- **Inspiration:** [pcb-inspector](https://github.com/takzen/pcb-inspector) and
  [kicad-happy](https://github.com/aklofas/kicad-happy) feature areas. The
  kicad-happy EMC guide lists `DC-003` for a decoupling capacitor that is too
  far from a via. Its example category motivates a second measurement; no
  universal via-distance threshold or candidate code is adopted.
- **Evidence and check:** For each mapped IC supply/return pad pair and its
  candidate capacitor pad pairs, check footprint identity, fitted state,
  expected net assignments, native copper connectivity, and exact transformed
  KiCad pad centers. Measure Euclidean center-to-center distance from IC supply
  pad to capacitor supply pad. Compare using integer squared nanometers to the
  project-authored micrometer threshold. `selection: any` requires one candidate;
  `selection: all` requires each candidate. An optional
  `max_return_via_distance_um` measures each capacitor return pad to the nearest
  via explicitly listed in that pad's native copper-connectivity component;
  the configured candidate policy must meet both limits on the same capacitor.
  With no supply-pad threshold, retain the measured distances as a review
  finding. No via requirement is inferred when the optional limit is absent.
- **Boundary:** These Euclidean distances do not establish a low-inductance
  loop, via-to-plane quality, correct value, or adequate decoupling. The via
  measure excludes nearby vias outside the pad's native copper component.
  Native DRC and schematic connectivity remain separate. A direct plane
  connection may be valid without a via; projects should configure this limit
  only when reviewed layout guidance requires it.
- **Fixtures:** Synthetic close and distant capacitors, multiple IC supply pins
  sharing one bank, exact threshold boundary, wrong-net and disconnected
  candidates, DNP and wrong-footprint controls, nearby unconnected vias, exact
  connected-via distance boundaries, and a rotated pad measured by native KiCad
  10.0.0 and 10.0.5 probes. Repeated native snapshots are identical; moving
  the connected via across the project limit produces a source-bound fault.
- **Evidence locator:** The lint report names the board hash, native snapshot
  path and hash, probe hash, exact KiCad version/image, mapped pads, selected
  capacitors, connected via identity/count, and both measured distances.
  Receipts live under ignored `build/`.
- **Fixtures:** The native synthetic board includes a GND via connected to the
  mapped capacitor return pad. Its control is exactly 1000 um from the pad; a
  source-only coordinate mutation moves it to 2000 um and must produce
  `INCOMPLETE`. Both cases repeat under pinned KiCad 10.0.0 and 10.0.5.
- **Determinism:** LINT-080 compares an authored 100 µm threshold's
  one-nanometer over-limit candidate with its exact-boundary control across
  three independent Python hash seeds. This checks typed-report stability; it
  adds no native export or public-board applicability result.
- **Boundary:** A passing project threshold is a placement screen selected by
  that project. It does not establish loop inductance, capacitor value or bias
  derating, resonance, transient performance, or manufacturing quality.

#### LINT-021 — Mapped net minimum track-width screen

- **Status:** Implemented as `pcb.minimum_track_width`; review by default,
  with project-authored `review`, `block`, `off`, and exact-ignore decisions.
- **Inspiration:** [pcb-inspector](https://github.com/takzen/pcb-inspector).
- **Evidence and check:** A PCB project's `design_lint.pcb_track_width_map`
  names exact nets, project-authored minimum micrometer widths, and each
  requirement's basis. Compare every native KiCad track item's integer
  nanometer width with the configured minimum. Findings retain the track UUID,
  layer, exact width, and endpoints. A net with no track items has incomplete
  coverage because it may be zone-only or unrouted. One threshold applies
  across all copper layers for each mapped net.
- **Boundary:** This check does not inspect zone geometry or via bottlenecks,
  prove track connectivity, infer a current requirement, or calculate
  ampacity, temperature rise, pulse limits, or electrical performance. Native
  DRC and any project-specific copper calculation remain separate evidence.
- **Fixtures:** Native 250 um segment at the exact 250 um boundary and below a
  251 um screen; unrelated-net exclusion; zone-only/unrouted incomplete
  coverage; review, block, off, exact-ignore, and repeated-snapshot controls
  using synthetic boards on pinned KiCad 10.0.0 and 10.0.5. CLI and MCP parity
  use the same typed service and snapshot.
- **Done:** Typed project map, deterministic native measurements, explicit
  incomplete coverage, source-bound reports, policy controls, synthetic
  fault/boundary fixtures, CLI/MCP parity, and catalog/docs are implemented.
  Current and thermal calculation remains deferred until its project inputs
  and adopted model can be validated independently.

#### LINT-022 — Differential-pair physical constraint evidence

- **Status:** Implemented v1 as `pcb.differential_pair_rule_coverage`; review
  by default, with project-authored `review`, `block`, `off`, and exact-ignore
  decisions. Independent pair-geometry validation remains deferred.
- **Inspiration:** [pcb-inspector](https://github.com/takzen/pcb-inspector).
- **Native reference:** The
  [KiCad 10 PCB Editor manual](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html) documents custom
  width, pair-gap, length, skew, and uncoupled-length constraints. Netclass widths are routing
  defaults rather than DRC limits; tuning-profile geometry violations default to Ignore.
- **Head-to-head evidence:** A public synthetic pair was checked with the
  KiCad 10.0.0 and 10.0.5 digest-pinned images. With authored native rules,
  both versions reported the compliant pair without pair-constraint
  violations; separate width, gap, skew, and uncoupled-length faults produced
  the corresponding native DRC types (`track_width`,
  `diff_pair_gap_out_of_range`, `skew_out_of_range`, and
  `diff_pair_uncoupled_length_too_long`). An identical excessive-gap board
  without authored pair rules produced no pair-constraint finding. The small
  track-only fixture also has two unrelated dangling-end warnings; all cases
  had zero unconnected items. A later KiCad 10.0.6 run also checked a
  byte-identical skew fault without its `.kicad_dru`: native DRC emitted no
  pair-rule finding, while the configured copy emitted `skew_out_of_range`.
  This is a synthetic native-tool comparison, not a project-board result.
- **Reproducible fixtures:**
  [`tests/fixtures/design_lint/differential-pair/`](../tests/fixtures/design_lint/differential-pair/README.md)
  retains the seven boards, authored rule files, pinned image digests, run procedure, and expected
  native finding types.
- **Disposition:** Do not add an independent pair-geometry checker solely to
  repeat native DRC. The coverage rule compares an independently authored
  pair/constraint inventory with the project's source-bound `.kicad_dru`,
  `.kicad_pro` ignored severities, and native DRC receipt. It reports exact
  covered, missing, mismatched, duplicate, ignored, unsupported, and
  unrecognized-pair cases. Do not infer that every similarly named pair needs
  the same limits.
- **Boundary:** Geometric match is not impedance or signal-integrity
  qualification; allowed width, gap, skew, and uncoupled length are
  interface- and stack-up-specific. A clean native report without an authored
  constraint is not evidence that the pair meets its intended requirement.
- **Fixtures:** Exact synthetic rules cover width, gap, skew, and uncoupled
  bounds; missing files, wrong-pair selectors, wrong bounds, duplicate rules,
  globally ignored checks, custom rules with `(severity ignore)`, unsupported
  severity clauses, unsupported units, and unsupported net suffixes remain
  visible. The native DRC matrix above verifies that KiCad 10.0.0 and 10.0.5
  catch each corresponding geometry fault when its authored rule exists.
- **Done for v1:** Typed pair map, exact rule parser, source-bound board,
  project settings, rule file and native DRC evidence, policy modes, catalog,
  synthetic fault/control coverage, and CLI/MCP parity. Future work can expand
  supported KiCad condition expressions only with focused fixtures; the audit
  must keep unsupported syntax incomplete rather than guessing equivalence.

#### LINT-023 — Switching-current loop and return-path review

- **Status:** Implemented as the opt-in `pcb.switching_loop_geometry` review
  rule. Synthetic fault/control cases run in unit tests. Hosted native lanes
  exercise connected F.Cu and In1.Cu planes, a split In1.Cu plane, and the exact
  measured area boundary under KiCad 10.0.0 and 10.0.5. Not field-validated.
- **Inspiration:** [pcb-inspector](https://github.com/takzen/pcb-inspector).
- **Evidence and check:** A project-authored ordered list of exact board pads
  supplies the loop polygon. The native KiCad 10 snapshot records actual
  enabled copper layers, transformed pad centers, DNP state, zone identities,
  and filled-island indexes. The rule checks exact footprint/net/fitted state,
  computes an integer shoelace area through the ordered pad centers, compares
  an optional project-authored limit, and requires all return pads to share
  one filled zone island on the declared same-net stack layer.
- **Boundary:** The pad-center polygon does not follow routed trace centerlines
  or zone contours and is only a geometric proxy. The layer-specific same
  island requirement is intentionally strict; a connected return made from
  multiple zones and tracks may remain incomplete. The check cannot establish
  parasitics, emissions, stability, thermal behavior, or electrical
  performance. Hardware or simulation validation remains a separate record.
- **Fixtures:** Synthetic compact and enlarged loop polygons, exact area
  threshold, split filled islands, valid inner-layer return plane, absent
  stack layer, missing stack evidence, and configurable review/block/off/exact
  ignore behavior. The CLI/MCP parity case uses the same source-bound snapshot.
  Hosted native controls use a synthetic four-pad polygon with connected F.Cu,
  connected In1.Cu, and split In1.Cu return planes. Each capture repeats to
  verify deterministic centers and area; connected and split results retain
  their native zone identities. The exact area boundary passes and a one-um2
  lower authored limit flags the same measured geometry.
- **Next:** Do not treat the ordered pad list as a routed path. Before adding a
  comparison, require an explicit per-edge interpretation and prove that the
  native geometry resolves it uniquely. LINT-039 tracks this work. A project
  must select and review any resulting measurements; the existing pad-center
  proxy remains a separately named approximation.

#### LINT-024 — Schematic near-miss and drawing-quality diagnostics

- **Status:** Eleven opt-in review rules run through the shared design-lint
  service, CLI, and MCP. Each catalog default is `off`; project policy can
  enable, block, or ignore each rule independently. LINT-044 now reports
  geometry coverage per enabled rule, so an unsupported text shape does not
  make an unrelated wire-body check appear incomplete.
- **Supported boundary:** Recursively scans project-local hierarchical KiCad
  schematics at file-format version `20231120`, for exact KiCad `10.0.5` and
  `10.0.6`. Each reachable source must appear in the native snapshot's source
  hashes, and each placed symbol must map uniquely through KiCad's project and sheet
  instance path. A reused child file is scanned once per instance. The report
  binds a canonical source-tree digest and every source/instance mapping. It
  supports single-unit, single-conversion symbols, orthogonal rotations, and
  x/y mirrors. Pin geometry rules examine only pins explicitly marked
  unconnected by the matching native netlist and skip explicit no-connect
  markers. Label localization uses parsed supported symbol pin tips to avoid
  treating a label on a pin as detached. The scan reports `PARTIAL` when it
  cannot interpret encountered symbol geometry and hashes the schematic
  bytes. This is a bounded geometry pass, not a complete schematic
  connectivity parser. Missing child sources or ambiguous instance references
  leave coverage blocked or partial.
- **Exact-version matrix (2026-10-03):** The full
  `tests/test_schematic_geometry.py` suite passed 77 tests on each supported
  image. KiCad 10.0.5 used the `ghcr.io/kicad/kicad:10.0.5` image at digest
  `fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c` and
  completed in 82.457 seconds. KiCad 10.0.6 used the `kicad/kicad:10.0.6`
  image at digest
  `18693567392b80da435f9fa952ce3a3e534c66eb5a6033f5b9c80aa3b19dd3ec` and
  completed in 80.761 seconds. Both lanes ran with networking disabled,
  a read-only container root, and a temporary-fixture-only writable mount.
  The text metrics remain calibrated from the 10.0.6 image; the same native
  SVG comparisons pass under 10.0.5. The source scanner also accepts 10.0.5
  and rejects 10.0.0. Receipts and logs are under ignored
  `build/ci/native-schematic-geometry/` and
  `build/ci/native-geometry-matrix-local/`.
- **Connector body-overlap boundary replay (2026-10-05):** The full geometry
  suite passed 79 tests on KiCad 10.0.5 (83.532 seconds) and 10.0.6
  (85.964 seconds), using the digest-pinned images above with networking
  disabled, a read-only container root, and a temporary-fixture-only writable
  mount. A synthetic pair of passive connector contacts share `/SIGNAL`; each
  wire reaches its contact inside the supported body rectangle, producing
  review candidates for J1 and J2. A body-clear variant preserves the same
  10.16 mm body dimensions and moves the edge to the pin tip. Native component/
  pin assignments, nets, and wire geometry match while both candidates clear.
  Both versions confirm J1.1 and J2.1 on `/SIGNAL` and identical
  ERC signatures between variants. The standalone test has no project symbol
  library table, so the matching signatures contain only `lib_symbol_issues`
  warnings; no connectivity or off-grid ERC warning is present. This records
  an intentional candidate class, not a false-positive rate. The rule remains
  default-off.
- **Evidence:** An earlier complete `tests/test_schematic_geometry.py` native
  regression run passed all 39 then-existing tests against KiCad 10.0.6
  (213.092 seconds through the exact container image). The added text-wire
  fault/control regression separately passed in 13.469 seconds against that
  same pinned image. Synthetic fault
  and connected-control fixtures pass
  native KiCad 10.0.6 netlist/ERC parity. Across all 12 orthogonal
  rotation/mirror combinations, transformed pin tips match native ERC
  coordinates and the fault pins remain open in native netlists. The original
  endpoint rule and the wire-interior rule both have synthetic coverage across
  those transforms. The near-pin endpoint rule also has synthetic fault
  coverage and a native netlist/ERC regression across all 12 rotation/mirror
  combinations. The regression passed with exact KiCad 10.0.6 from the official
  `kicad/kicad:10.0.6` linux/amd64 image
  (`sha256:18693567392b80da435f9fa952ce3a3e534c66eb5a6033f5b9c80aa3b19dd3ec`).
  The fault
  netlist leaves `R1.1` unconnected; ERC reports
  `pin_not_connected` and `unconnected_wire_endpoint`. The original rule
  localizes a wire endpoint lying along the pin segment. A second rule finds
  an unconnected pin tip lying in the strict interior of a wire segment. Its
  paired control adds one junction marker; KiCad then places `R1.1` on
  `/CONTROL_NET` and emits no pin-disconnected ERC finding. This new candidate
  gives ERC's open-pin finding a more specific geometric explanation. It is
  review evidence, not an assertion of author intent or a repair instruction.
  A separate explicit no-connect marker on the same wire-crossing pin is a
  valid control: the local marker-exclusion unit test passes, and a new native
  KiCad 10.0.6 test also checks netlist isolation and ERC suppression while
  exercising the marker-aware geometry predicate with the pin supplied as
  unconnected. The full geometry suite, including this control, passes all 77
  tests in 88.962 seconds against the digest-pinned KiCad 10.0.6 image.
  A third rule reports an unattached local/global/hierarchical label anchor
  within 1.27 mm of wire endpoints, while excluding labels that touch any wire
  or pin tip. KiCad 10.0.6 ERC reports `label_dangling` for the synthetic
  near-endpoint fault and none for the attached control; the rule improves
  localization rather than adding electrical detection. The fixed search
  radius can include unrelated nearby endpoints and does not encode intent.
  A fourth rule reports a wire endpoint within 0.5 mm of a native-unconnected
  pin tip, excluding explicit no-connect markers and endpoints already on the
  pin segment. Synthetic boundary and exclusion controls pass, along with
  project-policy and CLI/MCP parity regressions. The exact-version native ERC
  comparison confirms an open pin and dangling-wire diagnostic for the fault;
  the geometric candidate explains where the wire endpoint nearly reaches the
  pin. This is review localization, not a demonstrated new detection. A fifth
  rule reports strict interior/interior orthogonal wire
  crossings without a junction marker, with the exact coordinate and wire
  UUIDs. Its synthetic candidate and explicit-junction/endpoint controls pass.
  An intentional unconnected crossing is valid KiCad usage and produces the
  same candidate; this known false-positive class keeps the rule off by default.
  Native KiCad 10.0.6 reports `wire_dangling` and `unconnected_wire_endpoint`
  diagnostics on both the fault and marked control. The local crossing rule
  identifies the exact unmarked intersection coordinate and wire UUIDs only in
  the fault fixture, adding localization rather than electrical detection.
  The sixth rule reports a wire endpoint on the strict interior of another wire
  without a junction marker. In its synthetic KiCad 10.0.6 fault, the native
  netlist keeps `R1.1` on `/CONTROL_NET` and `R1.2` on
  `unconnected-(R1-Pad2)`; the marked control puts both pins on
  `/CONTROL_NET`. ERC reports an open pin and the unconnected endpoint in the
  fault, and neither in the control. The geometry finding localizes a likely
  missing T-junction but still cannot establish whether the branch was meant
  to connect. CLI/MCP parity and independent review/block/off/ignore behavior
  are covered. A separate isolated-wire fixture confirms exact KiCad 10.0.6
  ERC already reports `wire_dangling` and `unconnected_wire_endpoint` with the
  wire UUID and location; the geometry pass adds no candidate. No custom
  dangling-wire rule was added because it would duplicate native evidence.
  A repeated-child-sheet fault/control pair confirms that exact KiCad 10.0.6's
  native netlist expands a shared channel into separate `R1` and `R2`
  references, separate hierarchical nets, and two unconnected pin assignments
  in the fault; the junction-marked control connects both instances. Fault ERC
  identifies the shared source pin only once. The recursive scan maps the
  shared source pin to both exact instance paths and emits separate geometry
  candidates. End-to-end CLI/MCP parity verifies root and child hashes,
  distinct source bindings and finding fingerprints, plus separate `R1.2` and
  `R2.2` pin-localization findings against source-bound synthetic netlist
  evidence. The exact-version native regression separately checks the
  repeated-sheet connectivity and ERC fault/control.
  Separate CLI/MCP parity regressions verify source and netlist hash binding
  and project opt-in for each rule. A seventh graphical-only rule reports pairs
  of top-level free-text objects with source insertion anchors within 0.001 mm.
  Native KiCad 10.0.6 ERC produces the same diagnostics for coincident and
  separated text controls. The source-bound finding includes both text strings,
  UUIDs, coordinates, sheet-instance path, and source hashes. It does not
  calculate rendered glyph bounds or prove visible overlap. An eighth rule
  measures a bounded standard-font envelope for distinct, horizontal, centered,
  single-line free text. Its 95 printable ASCII advances come from a synthetic
  native KiCad 10.0.6 SVG calibration using the digest-pinned
  `kicad/kicad:10.0.6` image. The tested fault has an actual native stroke-path
  intersection; its separated control has an 8.2247 mm minimum stroke-centerline
  gap. Native netlist and ERC diagnostics are identical for both. The rule
  excludes coincident anchors to avoid duplicating the existing anchor prompt.
  Plain escaped multiline text is supported using 2.0446 mm measured line
  spacing at the 1.27 mm reference size, scaled with font height. Custom faces,
  bold/italic/thick, formatted, non-ASCII, explicitly justified, and rotated
  text leave geometry coverage partial. The bounding
  envelope can still warn when individual character strokes do not collide.
  A ninth rule, `schematic.free_text_over_wire`, clips native schematic wire
  centerlines against that same bounded free-text geometry. It reports only
  when the wire remains inside the envelope by at least a 0.12 mm edge guard
  and overlaps for at least 0.2 mm. The fault and clear-control fixtures use
  the same source wire and differ only in text placement. Exact KiCad 10.0.6
  SVG confirms zero stroke-centerline distance in the fault and 7.9495 mm in
  the control. Native netlist component/pin assignments and nets are identical
  after excluding the project-specific `Sheetfile` property; all three ERC
  violation signatures are identical. This is a drawing review signal, not an
  electrical-connectivity finding. The rule ignores buses, labels, symbol
  fields, pin names/numbers, and symbol graphics; intentionally placing a note
  over a wire can produce a valid review candidate.
  A tenth rule, `schematic.wire_through_symbol_body`, bounds supported embedded
  symbol graphics and reports wire centerlines that remain at least 0.2 mm
  inside the axis-aligned envelope for 0.3 mm or more. It supports rectangle,
  polyline, Bezier, and circle graphics for single-unit, single-conversion
  symbols, including orthogonal rotations and x/y mirrors. In the synthetic
  fault/control pair, only the fault has a body-overlap candidate. Native
  KiCad 10.0.6 component/pin assignments, nets, and six ERC violation
  signatures are identical after normalizing project-specific `Sheetfile`
  metadata. The rule improves drawing localization and does not establish
  electrical intent. A bounded envelope can include empty areas between
  disjoint or curved primitives, and intentional wire crossings remain review
  candidates. Text graphics and unsupported symbol units leave geometry
  coverage partial.
  An eleventh rule, `schematic.free_text_over_symbol_body`, intersects a
  supported top-level free-text envelope with a supported symbol-body envelope.
  It applies a 0.1 mm text guard, 0.15 mm body guard, and 0.1 mm² minimum
  overlap. Exact KiCad 10.0.6 synthetic fault/control SVG confirms the fault's
  text strokes lie inside the resistor body region and the moved control is
  clear. Native net assignments and three ERC violation signatures are
  identical. This is a localized drawing prompt; labels, fields, and
  unsupported text remain outside its scope, and axis-aligned bounds can
  include empty space.
  Symbol-body parsing now supports a bounded three-point arc by finding its
  circle and selected sweep, then including only the cardinal extrema on that
  sweep. Synthetic fault/control cases cover minor and major arcs, all 12
  orthogonal rotation/mirror combinations, text and wire consumers, and a
  collinear-point case that remains partial. The matching native SVG, netlist,
  and ERC regression is registered in the exact KiCad 10.0.5/10.0.6 lane; its
  hosted acceptance passed in `v0.5.1rc39` (GitHub Actions run
  `39316485001`). The focused rule selection passed 9 tests with 4 host-only
  skips; the full schematic-geometry suite passed 87 tests on each pinned
  KiCad 10.0.5 and 10.0.6 image. The installed wheel, external-project
  verification/playtest, and Linux, macOS, and Windows preview jobs passed.
  The prerelease package job was skipped as configured.
- **Typography boundary evidence:** Synthetic controls cover custom face, bold,
  italic, thick stroke, vertical or mirrored justification, rotation, formatted
  text, and a non-ASCII glyph. These remain partial with no text-overlap
  candidate. Exact KiCad 10.0.6 accepts all eight variants; their native
  component identities, pin/net assignments, and ERC signatures match the
  standard-text baseline. Horizontal `left` and `right` justification are now
  supported; native SVG controls confirm both anchor directions and containment
  of every rendered stroke by the calculated text envelope.
  A separate three-line plain-text fixture measures 2.0446 mm baseline spacing
  at 1.27 mm font height and verifies that the heuristic box contains native
  SVG strokes. Its wire-crossing fault and clear control preserve identical
  native netlist/ERC signatures. A literal source newline inside a quoted
  S-expression remains unsupported; serialized single-backslash `\\n` is a
  line break, while doubled-backslash `\\\\n` is literal text.
- **Public-example trial (2026-09-29; multiline follow-up):** At public template commit
  [`ed89536`](https://github.com/search?q=ed89536f0dbbcb013145af2994fef41b2250143e&type=commits),
  five schematic-only examples were copied to a temporary directory and
  exported with the exact KiCad 10.0.6 image. The projects declare KiCad
  10.0.0 or 10.0.5, so this was a cross-version research run, not project
  acceptance evidence. The geometry pass found one wire-through-symbol-body
  candidate in each of the Arduino Uno and Raspberry Pi status LED examples.
  Native SVG review confirmed that both wire centerlines cross the visible J1
  rectangle on the way to a pin. This confirms the bounded geometric predicate
  and its review usefulness; it does not decide whether the drawing convention
  was intended or establish an electrical defect. After adding measured plain
  multiline support, all five unchanged source trees were rescanned: the
  multiline limitation disappeared, while each project remained `PARTIAL`
  because all five use explicit text justification outside the measured model;
  two also contain non-ASCII glyphs. The two symbol-body candidates were
  unchanged. These examples do not establish false-positive or missed-fault
  rates, and reviewer time was not measured. The two symbol-based examples
  also reported missing-library ERC items in this isolated container; those
  ERC results were excluded from the comparison. A separate static screen of
  the sixth project, `status-indicator-harness-interface`, at the same public
  commit recorded zero candidates for the eleven geometry result groups. Its
  per-source tree digest was
  `07e05a85f1f5a6fc4a302c85c840e10f875bfcb0c5220c480b2a48f6b1743a80`.
  This screen supplied no native unconnected-pin set, so the three
  pin-specific rules were not evaluated; the text-overlap, text-over-wire, and
  text-over-body rules remained partial because the example uses explicit text
  justification and non-ASCII glyphs. The example declares KiCad 10.0.5 while
  the scanner currently supports 10.0.6. This cross-version source scan ran no
  native export or ERC, and zero candidates are not evidence of precision or a
  clean design. This scan predates the horizontal-alignment extension below;
  the 2026-10-05 follow-up rescan after that change is recorded below. No
  public project source was copied into this repository.
- **Pytest suite decomposition (2026-10-09):** The former monolithic schematic
  geometry suite is now ten focused pytest modules for text, symbol-body,
  pin-proximity, wire-topology, sheet-hierarchy, and exact-native parity cases.
  The 848-line PCB reference-plane suite is also split into geometry, adjacent
  layer, and contract suites. These modules have focused pytest markers, and
  the architecture test enforces the 500-line review limit for each suite and
  its support modules. The focused geometry, reference-plane, catalog,
  reachability, and architecture run passed 304 tests with 25 exact-native
  tests skipped because no native CLI was configured. The text-only synthetic
  selection collected 25 tests; `pcb_reference_lint` collected 15 tests. The
  digest-pinned lane now runs the schematic geometry suites with pytest and
  records the selected files in its receipts. Its command-construction test
  passed. This host denied access to the Docker socket, so the exact KiCad
  matrix has not been rerun after the split; native results below describe
  earlier single-module runs.
- **CI regression lane (2026-09-29):** Package acceptance now sets
  `KICAD_RUN_NATIVE_SCHEMATIC_GEOMETRY=1` and runs the full
  `test_schematic_geometry.py` suite through the official amd64 KiCad 10.0.6
  image pinned above. With the polyline, rectangle, and circle crossing
  control, all 64 synthetic and native tests passed in 69.858 seconds; image
  pull, container start, and shutdown also passed, for a 71.8-second lane on
  this checkout. That run predates the new no-connect-under-wire native test;
  rerun the lane before recording its result.
  The container disables networking, has a
  read-only root, and can write only in ignored
  `build/ci/native-schematic-geometry/tmp/`; receipts and test output remain
  under ignored `build/ci/`. Native comparisons bind component/pin maps and
  net assignments while excluding temporary source-path metadata.
- **Graphical-only control (2026-09-29):** A synthetic schematic places a
  polyline, rectangle, and circle across an assigned wire. The geometry scan
  returns no candidate in any of its eleven rule groups. Exact KiCad 10.0.6
  SVG checks confirm each primitive renders; component/pin maps, native net
  assignments, and ERC signatures match the same schematic without them.
  This control does not measure a false-positive rate for other graphic
  primitives or public schematics.
- **Horizontal text alignment follow-up (2026-09-29):** The measured text
  envelope now accepts exactly one explicit horizontal alignment option,
  `left` or `right`; default text remains centered. Synthetic fault and clear
  controls for both alignments pass through KiCad 10.0.6. Their native SVG
  strokes stay inside the predicted envelopes, and native netlist and ERC
  signatures match between fault and control. The full geometry lane passed
  all 66 tests in 75.974 seconds in the digest-pinned image. Vertical alignment,
  mirrored text, combined options, and unknown justification tokens still leave
  enabled text rules partial. The public-template samples were subsequently
  rescanned after this change; see the 2026-10-05 record below. This rescan
  updates coverage evidence, not false-positive evidence.
- **Empty justification and em-dash follow-up (2026-09-30):** The exact
  KiCad 10.0.6 SVG exporter renders an empty `(justify)` field with the same
  text anchor and stroked paths as omitted justification. The scanner now treats
  that empty field as centered, while vertical, mirrored, combined, and unknown
  options remain unsupported. A native synthetic text object measures the
  U+2014 em dash at 1.4506 mm advance at the 1.27 mm reference size; its native
  stroke lies inside the existing calibrated vertical envelope. The packaged
  metric schema is version 3 and covers 95 printable ASCII characters plus
  this glyph. The digest-pinned geometry suite passed with both the native
  placement comparison and glyph-bound check.
- **Electrical-glyph follow-up (2026-09-30):** A synthetic one-character
  schematic was exported with the exact KiCad 10.0.6 image recorded above to
  measure U+00B0 degree, U+00B1 plus/minus, U+00B5 micro sign, U+00D7
  multiplication sign, and U+03A9 ohm sign. Their 1.27 mm advances are
  recorded in schema v4 alongside the existing 95 printable ASCII characters
  and U+2014 em dash. The five native SVG stroke groups fit the existing
  vertical envelope. A portable fault/control/translation fixture now checks
  overlap of `10µF ±5V` with `4.7Ω` and a separated control. Other Unicode,
  custom font styles, markup, literal source newlines, and rotated text remain
  outside the measured subset; plain KiCad escaped line breaks remain
  supported. The exact KiCad 10.0.6 geometry suite passed all 76 tests in
  77.382 seconds, including SVG text lengths, stroke-envelope bounds, and the
  new electrical-glyph overlap fault/control.
- **Read-only public-template rescan (2026-09-30):** At public template commit
  [`ed89536`](https://github.com/search?q=ed89536f0dbbcb013145af2994fef41b2250143e&type=commits),
  all six schematic examples were scanned with native unconnected-pin sets
  exported from the digest-pinned KiCad 10.0.6 image. Each scan returned
  `COMPLETE`, with zero unsupported cases across the eleven geometry rule
  families and zero native unconnected pins. The Arduino Uno and Raspberry Pi
  status LED examples retain the two wire-through-symbol-body candidates; the
  other nine groups are empty. No free-text overlap, free-text-over-wire, or
  free-text-over-body candidates were reported. The project manifests declare
  KiCad 10.0.0 or 10.0.5, so this 10.0.6 run is cross-version research rather
  than acceptance for those projects. Their schematics were mounted read-only;
  generated netlists lived in temporary storage, and no project sources were
  copied into this tooling checkout. This small sample demonstrates improved
  coverage for the empty-justify and em-dash cases, not heuristic precision,
  recall, electrical correctness, or manufacturing readiness.
- **Public-template wire/body triage (2026-09-30):** A read-only render and ERC comparison on the
  same template revision examined the Arduino Uno and Raspberry Pi status LED examples. Both produce
  one `J1` wire-through-body candidate for the same geometry: a wire from `(60.96, 73.66)` to
  `(68.58, 73.66)` crosses the `StatusLedTraining:Header_1x02` body envelope from `(60.96, 72.39)`
  to `(66.04, 80.01)`, overlapping it by 4.68 mm. The schematic source SHA-256 values are
  `c2d8442412cb251472a08df31109b8633655aaa375598abbb2e7bbc00961fa1b` and
  `b99ad47237f3f36aaefa3a2ed08e3dae12d9131c7f9a52355401c9d5bada3fba`. SVG and ERC exports used the
  digest-pinned KiCad 10.0.6 image recorded above, with the full public template mounted read-only
  and networking disabled; each ERC report had zero violations. This is one unique geometry repeated
  in two fixtures, not two independent samples. ERC cleanliness does not settle whether the drawing
  overlap is intentional. With no author intent record, count it as unresolved and exclude it from
  both confirmed findings and false-positive rates. The reports stayed under `/private/tmp`; no
  project source was copied into Tooling.
- **Exact-version re-screen (2026-10-03):** Repeated the two-project check with each
  project's declared `ghcr.io/kicad/kicad:10.0.5` image with digest
  `sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c` at public checkout
  `ed89536f0dbbcb013145af2994fef41b2250143e`. The checkout was mounted read-only,
  networking was disabled, and only generated netlist/ERC receipts were written under ignored
  `build/`. Both projects produced byte-identical repeated netlist and ERC exports and zero ERC
  violations. Their native netlists contain no unconnected pins. The KiCad 10.0.5 geometry scans
  were `COMPLETE` with byte-identical repeated scanner output; each found one J1 wire-through-body
  candidate for the same layout, clipped to `(61.16, 73.66)`–`(65.84, 73.66)` for 4.68 mm overlap.
  Each of the other ten result groups was empty. This confirms one unresolved layout repeated in two
  examples, not two independent candidates and not a false positive. The machine-readable receipt
  is `build/cohort-geometry-exact-20261003/public-geometry-screen.json`, SHA-256
  `1cfa6c290c91c20bc16fe9604f9105a5b143bdf17a9683b735991779a511b74c`; it contains source,
  manifest, native-export, and scan hashes. The source files remain only in the public checkout.
- **Parser rescan after text-alignment support (2026-10-05):** Rechecked all six
  schematic projects at the same clean public-template commit
  `ed89536f0dbbcb013145af2994fef41b2250143e`. The current geometry parser
  returned `COMPLETE` with no unsupported cases for all six; the earlier text
  coverage gaps from horizontal justification are now supported. The only
  candidates were the same two `schematic.wire_through_symbol_body` findings
  in the Arduino Uno and Raspberry Pi status LED schematics; the other ten
  result groups were empty. The previous exact KiCad 10.0.6 native screen at
  this source commit recorded zero unconnected pins, so the parser was given an
  empty unconnected-pin set; this follow-up did not rerun native export, ERC,
  or SVG rendering. Source-tree and per-file hashes plus rule counts are in
  the ignored receipt
  `build/ci/lint024-public-template-rescan-20261005-01/receipt.json`,
  SHA-256 `e37d9b7b4532fea97ebbdf6cd062b10deed93a614bd9ee9e6a15204daa845705`.
  This closes the stale text-coverage measurement only. It remains one
  unresolved wire/body layout repeated in two examples, not two independent
  samples or a confirmed false positive. Reviewer effort and false-positive
  rate remain unmeasured; no public source was copied into this repository.
- **Connector body-overlap boundary (2026-10-05):** The synthetic paired-
  connector case above confirms that a wire terminating at a passive pin
  inside a supported body rectangle can be a legitimate drawing and still
  match `schematic.wire_through_symbol_body`. Both connector pins have native
  assignments on the same `/SIGNAL` net. KiCad 10.0.5 and 10.0.6 preserve those
  assignments and identical ERC signatures when the body is moved clear of
  the wires; only the isolated-runner symbol-library warnings remain. This is
  an intentional review-candidate class, not a confirmed false positive on
  either public example. Keep the rule opt-in and do not infer intended
  connector wiring from body geometry.
- **Legacy sheet-property spelling follow-up (2026-10-07):** A read-only
  parser-compatibility probe of the public
  [SH-ESP32 hardware project](https://github.com/hatlabs/SH-ESP32-hardware)
  at commit `167981ac8c3e1a7a0104c20cf9b487b4d722fc60` uses schematic format
  `20231120` with KiCad 8's `Sheetname` and `Sheetfile` property spellings.
  The root schematic SHA-256 is
  `9d88ec492742568f84ae65fd64ef30a409b0968342480b0a33ba04b0247d0b52`; the
  traversed source-tree SHA-256 is
  `3006095773aa86b59cbcbbe718d01187331052ed4d8b0c55357c5997affbc3eb`.
  The recursive scanner previously rejected these; it now accepts either the
  legacy spellings or KiCad 10's spaced names, and rejects duplicate aliases.
  A synthetic repeated-sheet regression binds the root plus both child
  instances. A source-only scan of this public design traversed 10 instances
  but remained `PARTIAL`; it emitted 20 unmarked-crossing, 5 wire-through-body,
  and 2 coincident-text-anchor candidates. It had no native export/ERC or
  native-unconnected-pin list, so pin-local rules were not evaluated. The
  source was made with KiCad 8 while the validated native matrix is KiCad
  10.0.5/10.0.6. The project `LICENSE.md` names CC BY 4.0 while its
  schematic title block names CC BY-SA 4.0, so retain it only as a temporary
  parser probe. Do not count its candidates as findings, false positives, or
  review-effort evidence; no project source was copied into this repository.
- **Next:** Keep all eleven rules default-off and opt-in. Measure false
  positives and reviewer effort on non-proprietary examples with complete
  support for the selected rule. Track each unique candidate layout separately;
  only an author-reviewed intentional overlap counts as a confirmed false
  positive, and unresolved intent stays out of the rate. Measure reviewer
  effort only in an observed review and keep it distinct from native ERC
  agreement. Current font evidence covers plain printable ASCII plus U+00B0,
  U+00B1, U+00B5, U+00D7, U+03A9, and U+2014 at 1.27 mm reference size with
  default/empty, left, or right placement; vertical or mirrored justification,
  formatting, other Unicode glyphs, and unsupported styles remain coverage
  gaps. Measure fault/control behavior for further glyphs before expanding the
  resource.
  Four-way interior crossings and
  T-shaped endpoint contacts have separate fault/control cases. The free
  dangling-wire trial found no incremental geometry value beyond native ERC.
  Keep unresolved, missing, or ambiguous sheet files and instance-reference
  mappings visible as blocked or partial coverage. A project may choose
  `block` only through an explicit rule override.
- **Inspiration:** [kicad-sch-lint](https://github.com/rashuky/kicad-sch-lint)
  and [KiDiff](https://github.com/INTI-CMNB/KiDiff).
- **Evidence and check:** Implemented rules now cover a near-pin wire endpoint,
  a wire endpoint along the pin segment, a pin tip on wire interior, and a label
  close to a wire endpoint, plus T-shaped endpoint contacts without a
  junction marker. The native-unconnected pin requirements and exact KiCad
  boundary are part of each applicable predicate. A synthetic repeated-sheet
  root and shared child fault/control pair exercise hierarchy coverage: the
  native netlist has separate open-pin assignments for R1 and R2 in the fault
  and connected instance-local nets in the control, while fault ERC reports
  one pin violation against their shared source geometry. Recursive scanning
  binds each project-local source to exact instance paths; CLI/MCP parity
  verifies two distinct findings from one reused child. Missing or ambiguous
  mappings produce partial coverage. The text/body collisions are now
  implemented as graphical review aids; source revision differences remain a
  candidate.
  Resolve symbol transforms and pin-tip coordinates against the exact
  supported KiCad version, and attach sheet, coordinate, object IDs, implicated
  netlist pins where available, and localized visuals. Compare every
  electrical symptom with native ERC so duplicates are recorded as better
  localization rather than new detection. The unmarked-crossing advisory
  cannot tell a missed junction from an intentional crossover; exact project
  ignores and reviewer decisions preserve that distinction.
- **Boundary:** Visual proximity is not electrical connectivity. ERC remains
  authoritative for native diagnostics; this feature improves detection or
  review localization only when demonstrated. Rendered appearance cannot
  override the KiCad netlist. Never auto-connect or rewrite schematic geometry
  in this check. The candidate tool also offers fixes; its write path is out of
  scope for this analyzer.
- **Fixtures:** Covered: a wire endpoint just short of a pin tip with boundary
  and exclusion controls; endpoint along the pin segment; pin tip on wire
  middle with and without a junction marker; an explicit no-connect marker on
  the wire-crossing pin with native isolation/ERC parity; near and
  attached labels; and all 12 rotation/mirror combinations for the near-pin
  geometry. A separate
  T-junction fault/control pair checks native netlist pins, native ERC, marker
  suppression, and CLI/MCP parity. A standalone dangling-wire fixture records
  native ERC coverage without a duplicate geometry candidate. A repeated
  child-sheet fault/control pair confirms instance-distinct netlist refs and
  pins, recursive source-tree binding, missing-reference partial coverage,
  project-local path containment, and CLI/MCP parity. One graphical-only
  control verifies visible polyline, rectangle, and circle crossings do not
  become electrical wire candidates or change the native netlist/ERC. Other
  graphical primitives and crowded valid drawings remain for review.
- **Done when:** Exact-version tests cover the remaining geometry classes and
  supported sheet scope, native netlist/ERC behavior is checked, and no
  auto-fixes occur. Duplicate ERC findings are recorded as review
  improvement, not new detection.
- **Catalog-bound native gate (2026-10-13):** All eleven geometry rules now
  declare `KICAD_RUN_NATIVE_SCHEMATIC_GEOMETRY` and list their relevant exact-
  native fault/control tests. Architecture checks bind those references to
  the required lane and ensure native tests cannot be silently omitted from
  rule-scoped tag gates. The five split native suites require the exact-tool
  fixture; they skip unless the lane switch is set, and the native runner
  explicitly passes that switch into pytest. Local focused verification passed
  111 tests; 36 exact-native cases, including the 25 schematic geometry cases,
  skipped because no KiCad CLI was configured. The hosted two-version gate is
  complete: tag `v0.5.0rc223` (GitHub run `38352816037`) passed catalog-scope
  resolution, both digest-pinned native KiCad geometry matrices (10.0.5 and
  10.0.6), installed-wheel acceptance against the separate public template,
  wheel/sdist checks, and Linux/macOS/Windows preview jobs.
- **Pin-endpoint review context (2026-10-20):** Wire/body candidates now carry
  exact same-symbol pin-tip matches for segment endpoints within the bounded
  geometry tolerance. The paired synthetic connector case reports its single
  pin tip per body, while an interior wire crossing has no endpoint match and
  remains a candidate. This adds localization without suppressing candidates
  or inferring electrical intent. The public-template observation remains
  unresolved; no external source or project fixture was copied. Local native
  cases skip without a configured KiCad CLI and remain covered by the exact-
  version hosted lane.

#### LINT-025 — PCB return-reference and connector-ground path evidence

- **Status:** v4 adds a synthetic same-net front/back plane fault and
  through-via control to the electrical contract lane; exact-version hosted
  acceptance for this addition passed in tagged `v0.5.0rc24` (GitHub run
  `37890194399`). It is not field-validated. It covers direct pad
  connectivity, explicit net-tie bonds, DNP state, intentional isolation,
  copper-zone identity, island counts, and exact per-pad island indexes using
  source-bound KiCad 10 `pcbnew`
  evidence and synthetic regressions. Hosted
  native CI runs alternate-layer connected/open controls, connected and split
  plane controls, fitted versus DNP net-tie controls, and separate-domain
  isolation controls through the same adapter. It also retains stable geometry-
  derived via identities, net, center coordinates, layer span, drill/diameter,
  via kind, identical-geometry multiplicity, and per-pad component membership.
  It also lists each filled island with no observed pad anchor. The catalogued
  10.0.0 and 10.0.5 images are covered by the native matrix. The new synthetic
  same-net F.Cu/B.Cu plane pair tests a missing stitch via against a one-via
  control; that addition passed exact-version hosted acceptance in
  `v0.5.0rc24`.
- **Hosted exact-version rerun (2026-10-09):** Tagged package acceptance
  `v0.5.0rc24` passed GitHub run `37890194399`, including the full pytest suite
  and installed-wheel check against a separate project checkout. The run set
  `KICAD_RUN_NATIVE_PCB_FIXTURES=1`; the native PCB regression exercised
  `pcb_return_fixture_lane` for the configured KiCad 10.0.0 and 10.0.5 projects.
  Its unstitched-plane fault keeps one same-net `RETURN` zone on each of
  `F.Cu` and `B.Cu` without a through via and expects disconnected endpoint
  copper components. The paired control adds the exact through via and checks
  connected endpoint membership plus repeatable native geometry. This proves
  the synthetic fixture and pinned adapter behavior, not a production board's
  return path or manufactured continuity.
- **Problem:** Matching schematic nets can still lack an intended physical
  copper path due to unconnected pads, plane splits, net ties, or layout
  changes.
- **Evidence and check:** `pcb_return_paths` names each exact PCB pad and
  expected net and footprint, direct or bonded domain, and exact net-tie
  footprint/pad groups. A read-only native probe refills zones in memory and
  reports each pad's connected pad set, stable via geometry and per-pad
  component membership, directly touched zone UUID/layer identities, and each
  zone's filled-island count and pad-to-island indexes from the exact
  digest-pinned KiCad 10 image.
  KiCad's [GetConnectedItems API](https://docs.kicad.org/doxygen/classCONNECTIVITY__DATA.html)
  returns every item in a copper cluster, so the probe filters those candidates
  by the pad's copper layers and actual filled-island contact before recording
  direct zone evidence. Via IDs hash
  canonical native geometry rather than KiCad object UUIDs, which can change
  between loads. Reports include via positions and layer spans but do not infer
  route order or capacity. The island mapping intersects each filled polygon,
  preserving polygon holes, with KiCad's effective copper-pad shape. Zone
  islands without a mapped pad are recorded as unanchored-to-pad review
  evidence; that does not assert the island is electrically isolated or
  defective. Receipts bind board
  bytes, tool version/image, probe bytes, pad/net/footprint/DNP data,
  copper-zone and island observations, and native net-tie groups; archive replay
  recomputes findings
  from retained data.
  The native CI control routes `J1.1` on `F.Cu` through a plated via to `J2.1`
  on `B.Cu`; its fault keeps both same-net assignments but omits the B.Cu
  connection. Both use the same exact-image adapter and assert the expected
  topology result. Receipt regressions also rehash a tampered pad-group snapshot
  and require replay to reject the changed conclusion. A successful synthetic
  runner response that changes board bytes during capture is rejected as stale;
  this fault is injected at the runner boundary so it is deterministic.
  The public [cohort copper-LVS issue #3787](https://github.com/rjwalters/kicad-tools/issues/3787)
  describes same-net GND planes with physical islands where no stitching via
  bonds the layers. That report supplied a failure-class lead only; no board or
  candidate code was copied. The new tooling-owned pair keeps the two mapped
  pads on one `RETURN` net and one zone on each copper layer, then compares no
  through via with a single through-via control. Its contract result remains
  conditional on the project explicitly requiring that endpoint path.
- **Multiport contract regression (2026-10-20):** A pure synthetic snapshot
  maps both return contacts on four DB9-like connectors into one authored
  direct-return domain. The common-copper control passes; splitting both
  contacts of J4 into a separate copper group or opening only J4.9 fails the
  domain connectivity check while all eight exact pad/net identity checks
  still pass. This tests multi-endpoint contract evaluation; it does not replace
  the exact-version native lane that establishes pad-to-copper evidence.
- **Scoped acceptance (2026-10-20):** Tagged as `v0.5.2rc5` with the
  `return_path_lint` modules and `KICAD_RUN_NATIVE_PCB_FIXTURES` lane.
  Run 39373764914 passed the selected unit checks, exact-version native PCB
  fixtures, package and wheel checks, and installed-wheel rehearsal against a
  separate project.
  Linux, macOS, and Windows preview jobs passed as well.
- **Multiport native board fixtures (2026-10-20; acceptance passed):** Added
  three board-only, tooling-owned fixtures with eight exact J1–J4 return pads
  on one `RETURN` net assignment. The control connects all pads; the faults
  isolate both J4 contacts or leave J4.9 open. The source-bound native lane
  evaluates every pad identity and the common-domain copper result on the
  configured KiCad 10.0.0 and 10.0.5 images. Run 39375039382 completed
  successfully with `KICAD_RUN_NATIVE_PCB_FIXTURES=1`; the selected lane covers
  both pinned versions. Local mocked-lane, package-asset, focused return-path,
  and architecture checks also pass. The `package` workflow job was skipped;
  the passing prerelease job performed the installed-wheel rehearsal.
- **Existing native cases:** Isolation controls verify two declared domains remain separate
  and catch an added fitted net-tie bridge while preserving each domain's local
  connectivity.
  The fixture lane also proves exact net-tie groups and DNP state for a fitted
  bond and its valid-open control. The alternate-layer connected/open controls
  retain stable via geometry and prove whether that via belongs to each
  endpoint's native copper component. The connected fixture repeats an exact
  native load to verify stable IDs and membership. Component membership does
  not establish the ordered route through tracks or prove current capacity.
- **Boundary:** A same-net assignment is not copper continuity; geometry is
  not manufactured continuity. A declared net-tie pass verifies the native
  footprint identity, pad groups, and DNP state, but does not prove that copper
  inside the footprint physically bridges those pads. Isolated domains remain
  valid when declared.
- **Fixtures:** Connected plane; missing pad connection; split plane; four-port
  DB9-like common-return control, whole-connector copper island, and single
  open-contact fault; same-net front/back return planes without and with a
  through-via bond; declared net
  tie; disconnected island; valid isolation; DNP bond; alternate layer
  return. The first connected-plane and split-plane controls are now included in
  the native lane for SMD and plated through-hole pads; fitted and DNP net-tie
  controls plus valid isolation and an unintended isolation bridge are included.
  A connected plane with a separate island that has no pad anchor is included.
- **Done when:** The check agrees with controlled direct, bonded, isolated,
  split-plane, DNP, disconnected-island, and alternate-layer board fixtures;
  emits exact pad and island evidence; replays from a source-bound receipt; and
  clearly stops before fabrication or first-article approval.

### P3 — Curated knowledge and optional cohort integration

#### LINT-030 — Curated engineering-rule knowledge base

- **Status:** Curated v1 in the cohort concept register below; continue adding
  concepts only when a source, applicability boundary, baseline comparison,
  and fault/control plan can be recorded.
- **Inspiration:** [ThomsonLint](https://github.com/holla2040/ThomsonLint) and
  the candidate/fork comparisons recorded in the prior tooling evaluation.
- **Work:** Extract candidate rule concepts into a source-attributed,
  applicability-tagged catalog. For each candidate, record the engineering
  claim, intended design scope, required project inputs, deterministic
  predicate if one exists, false-positive cases, evidence source, and a
  synthetic fault/control plan.
- **Boundary:** A natural-language recommendation or model-generated answer
  cannot make a release decision. Do not copy code or rule text until
  provenance and license are reviewed. Keep AI and hosted services outside
  blocking verification.
- **Done when:** Every adopted concept has an independent fixture-backed rule
  specification, provenance/license record, and a decision to implement,
  defer, or reject.

#### LINT-031 — Candidate analyzer trial and incremental-value register

- **Status:** Detailed source audits, feature trials, and public applicability
  screens are maintained in the [cohort trial register](DESIGN_LINT_COHORT_TRIALS.md).
- **Purpose:** Compare each candidate feature against synthetic faults, valid
  controls, and the existing baseline. Record detection, review, and maintenance
  gains separately; do not adopt a framework wholesale or infer real-board
  defects from public examples without independently reviewed requirements.

#### LINT-032 — Reproducible analyzer adapter contract

- **Status:** Backlog; needed only for adopted external analyzers.
- **Work:** Define a declarative adapter for executable/version, supported
  inputs, invocation, output normalization, timeout/failure semantics, source
  hashes, and license/provenance. CLI and MCP continue to call the same typed
  service.
- **Boundary:** No guessed executable paths, cross-environment Python imports,
  or silently relaxed source/version checks. A missing or failed analyzer is
  `BLOCKED`/unavailable evidence, not `PASS`.
- **Fixtures:** Tool absent; wrong version; malformed output; timeout; valid
  no-finding; finding with source locator; stale source hash.
- **Done when:** An installed wheel is tested against an external project
  checkout, generated receipts stay under ignored `build/`, and documented
  adapter exceptions have parity tests.

#### LINT-050 — MCU firmware pin-map consistency contract

- **Status:** Implemented as a typed, configurable design-lint rule.
  Synthetic service and CLI/MCP parity tests
  pass. Repeated exact-version native source-to-netlist regression lanes pass
  on KiCad 10.0.0 and 10.0.5.
- **Cohort input:** The public
  [STM32-KiCad-Pin-Checker](https://github.com/jbmata/STM32-KiCad-Pin-Checker) README describes
  comparing a KiCad `.net` export with STM32CubeMX `.ioc` `Signal` and `GPIO_Label` values, with
  user-authored aliases and ignored pins. It declares MIT and currently documents a Tkinter desktop
  workflow; CLI/CI appears on its roadmap. A pinned read-only parser trial is recorded under
  [LINT-031](#lint-031--candidate-analyzer-trial-and-incremental-value-register): at commit
  `f0018b5b4334caa5eeb619f9c0059dd7ae4363eb`, the candidate handles order-reversed conflicting
  suffix assignments differently and ignores an escaped PH0 key that the local parser accepts.
  The local parser reports the same `BLOCKED` collision for both orders. No candidate code was
  copied or installed as a dependency, and the GUI was not run. See the
  [README](https://github.com/jbmata/STM32-KiCad-Pin-Checker) and
  [`ioc.py`](https://github.com/jbmata/STM32-KiCad-Pin-Checker/blob/main/ioc.py). The local parser's
  alternate-function key boundary was also checked against an
  [ST-maintained CubeMX `.ioc` sample](https://github.com/STMicroelectronics/STMems_Standard_C_drivers/blob/master/_prj_MKI109V3/_prj_MKI109V3.ioc)
  that uses suffixed physical-pin keys, including escaped spaces; the sample itself was not copied
  into the fixture set.
- **Problem:** A KiCad MCU pin can remain electrically connected while a
  schematic net assignment, CubeMX pin function, or CubeMX user label changes
  independently. ERC does not compare those two sources. The upstream
  desktop workflow is not a reusable CLI/MCP regression gate for this
  repository.
- **Contract:** The project-owned MCU pin-map contract names the
  exact MCU reference, native library symbol, part identity, and repository-
  local `.ioc` input. For every in-scope package port pin, author the exact
  matching KiCad symbol pin number, expected schematic net, and accepted
  CubeMX `Signal` and/or `GPIO_Label` values. The package-port-to-symbol-pin
  map and any cross-name aliases must be explicit; no pin-function guessing
  or fuzzy name normalization. Each excluded port pin requires a reason.
  Bind the contract, `.ioc` bytes, schematic, and exact-version native
  netlist to the same source-bound report.
- **Policy and coverage:** A fitted component whose value or symbol contains
  the literal `STM32` and has no map receives a visible review prompt. This is
  a bounded discovery hint; it does not assume CubeMX is the firmware source.
  A configured map compares exact part, symbol, package pin, KiCad symbol pin,
  schematic net, `.ioc` `Signal`, and any checked `GPIO_Label`. Default findings
  are `REVIEW`; project policy can promote the rule to `block`, set it `off`, or
  record an exact fingerprinted ignore. Missing `.ioc` evidence, duplicate or
  unsupported pin assignments, and changed source bytes are explicit coverage
  errors. Generic GPIO functions need an explicit expected label, including an
  explicit absent-label expectation, or a reasoned package-pin exclusion.
  The parser supports physical-port keys with hyphenated alternate-function
  names and CubeMX escaped-space forms; it does not normalize function or label
  values.
- **Boundary:** The check cannot establish that a project-authored
  package-to-symbol map is correct without a reviewed pinout source. It does
  not validate the MCU part's silicon capabilities, compile or inspect
  firmware, prove board routing, or establish off-board wiring. A matching
  contract only proves agreement among the declared expectation and the
  selected source-bound schematic and `.ioc` observations.
- **Synthetic fixtures:** Matching pin map control; swapped KiCad net; swapped
  CubeMX signal and label; missing IOC assignment; wrong symbol, DNP state, and
  symbol-pin inventory faults; exact accepted aliases; complete package-pin
  inventory with a reasoned exclusion; duplicate and unsupported IOC
  assignments; conflicting alternate-function suffix keys for one physical
  pin; semantically equivalent valid assignments in reordered lines with
  changed source hashes; unmapped fitted STM32 prompt with DNP control; source hash
  mutation; review/block/off/exact-ignore lifecycle; and CLI/MCP parity. The
  parity case also asserts that the mapped `.ioc` digest is carried by both the
  report and its connectivity snapshot, preventing partial source provenance.
  The [synthetic input README](../tests/fixtures/design_lint/stm32-pin-map/README.md)
  documents the invented signal assignments and fixture scope.
- **Pinned native fixtures:** A valid synthetic four-pin MCU map, a schematic
  net drift, and a CubeMX signal drift each export twice and normalize to the
  same parsed netlist on pinned KiCad 10.0.0 and 10.0.5. The
  [fixture README](../tests/fixtures/design_lint/stm32-pin-map-native/README.md)
  records source hashes and the opt-in reproduction command. Additional native versions need
  their own pinned fixture lane. These lanes do not run ERC or DRC. No cohort
  runtime dependency or proprietary project source is required.
- **Done:** Typed contract and report models, bounded `.ioc` parser, source
  hashing, configurable review/block/off/ignore lifecycle, synthetic fault and
  control coverage, CLI/MCP parity, catalog/documentation, and repeated pinned
  KiCad 10.0.0/10.0.5 fixture exports are implemented. Silicon accuracy,
  firmware compilation, PCB routing, and field effectiveness remain outside
  this check.

#### LINT-033 — I2C responder-address collision review

- **Status:** Implemented; synthetic validation only.
- **Cohort input:** [kicad-happy](https://github.com/aklofas/kicad-happy)
  documents address-conflict detection as an analyzer family. This is a
  documented design input, not a benchmark or adoption of its workflow.
- **Evidence and check:** `design_lint.i2c_address_map` declares each segment,
  responder reference, exact symbol, SDA/SCL pins, seven-bit static address,
  and review basis. Strapped entries also declare each address bit's symbol
  pin/function and exact low/high nets. Complete strapped entries are checked
  for disagreement with the authored address; fitted complete responders at
  the same address on the same declared segment produce a collision finding.
  Rule overrides support `review`, `block`, and `off`; exact ignores use the
  standard fingerprint lifecycle.
- **Boundary:** No address is inferred from a value or reference string.
  Fixed addresses are authored expectations without pin derivation; only
  strapped address bits are resolved from the native netlist. Dynamic or
  unresolved entries remain coverage gaps. DNP entries do not enter collision
  groups. Firmware selection, off-board devices, part-pinout truth, and mux
  isolation are not inferred. Segment maps that share either signal net are
  rejected as ambiguous address domains.
- **Fixtures:** Same-segment collision; strapped-address mismatch; distinct
  strap values; same address on separate segments; unresolved strap; dynamic
  address; exact ignore and blocking override; DNP exclusion; invalid shared
  signal segment; CLI/MCP semantic parity. All fixtures are synthetic.
- **Done:** Schema, native netlist evidence, coverage status, deterministic
  findings, fault/control fixtures, docs, catalog entries, and parity tests are
  implemented. Continue validation with cohort-independent fault fixtures and
  identify missed applicable faults before changing maturity or default modes.

#### LINT-034 — External-interface protection coverage contract

- **Status:** Implemented v1; synthetic validation only. Exact direct-shunt
  channel maps and explicit `not_required` decisions are supported.
- **Inspiration:** [kicad-happy](https://github.com/aklofas/kicad-happy)
  documents ESD/protection coverage and mapping protection devices to
  interfaces.
- **Evidence and check:** A project contract names each reviewed connector pin,
  its expected connector symbol/footprint/net, and either an exact direct-shunt
  protection channel or a reasoned `not_required` disposition. Protector
  symbol/footprint, DNP state, complete pin inventory, mapped pin nets, and
  explicit unmapped-pin reasons are compared with the source-bound native
  netlist. Emits `protection.unreviewed_interface_pin` for missing
  applicability and `protection.mapped_device_mismatch` for source mismatches.
  Existing USB-C contract coverage handles CC, connector-side VBUS, and ground
  pins; connector pins whose observed net matches a mapped USB-C protector pin
  are also handled by that contract without duplicate prompts.
- **Boundary:** Never infer that every connector or signal requires a TVS/ESD
  part. A schematic does not establish clamp voltage, pulse rating, device
  suitability, placement, return-via geometry, or protection effectiveness.
  Existing USB-C contract findings must not be emitted a second time by a
  generic rule.
- **Fixtures:** Correct mapped protector; missing device; protector on the
  wrong signal; wrong return/reference pin; DNP option; incomplete device pin
  inventory; explicit unmapped-pin reason; explicit `not_required` decision;
  missing applicability; duplicate coverage against USB-C CC and signal
  protection contracts; CLI/MCP parity for a matching and mismatched map. All
  fixtures are synthetic.
- **Done:** Typed contract, source-bound coverage report, two catalogued
  review rules, review/block/ignore controls, CLI/MCP parity, and synthetic
  fault/control tests are implemented. This is not a field benchmark and does
  not validate protection effectiveness or physical return paths.

#### LINT-035 — Crystal/resonator load-network review

- **Status:** Implemented v1; synthetic validation only.
- **Inspiration:** [kicad-happy](https://github.com/aklofas/kicad-happy)
  documents crystal load-capacitor checks among its schematic analyzer
  families. The upstream documentation informed the candidate; no analyzer
  code, dependency, project data, or workflow was imported.
- **Evidence and check:** `design_lint.crystal_network_map` explicitly maps
  oscillator and resonator values, symbols, footprints, and pins; two load
  capacitors; their signal/reference pins and acceptable nominal values; the
  target load; and stray-capacitance range. The source-bound scanner checks
  exact identities, pin inventories, net assignments, DNP state, and supported
  capacitance text.
  It calculates `C1*C2/(C1+C2) + Cstray` and reports the inputs, assumptions,
  result, and native netlist digest. Missing or mismatched topology and values
  outside target produce a configurable review finding.
- **Boundary:** A schematic topology and nominal capacitance do not prove
  startup, frequency accuracy, drive level, parasitic capacitance, ESR margin,
  layout quality, or operation over environmental limits. The computation
  does not model capacitor tolerances. Do not infer a crystal requirement
  from `Y` references, value text, or symbol descriptions alone.
- **Fixtures:** Correct supported oscillator topology; missing one load cap;
  cap attached to the wrong oscillator pin; potential unlisted parallel load
  capacitor; correct alternate supported topology; unsupported internal
  oscillator; DNP load option; missing profile
  input; unsupported capacitance spelling; and values at and outside authored
  target bounds. All tests use synthetic inputs.
- **Done:** Typed project map, source-bound coverage, review/block/off controls,
  one catalogued deterministic rule, report evidence, CLI/MCP parity, and
  independently calculated synthetic fault/control tests are implemented.
  The nominal estimate and its unverified performance questions are explicit.

#### LINT-036 — Regulator feedback/setpoint plausibility review

- **Status:** Implemented as `power.regulator_feedback_mismatch`; synthetic
  regression-tested in the shared design-lint service and CLI/MCP parity lane.
- **Inspiration:** [kicad-happy](https://github.com/aklofas/kicad-happy)
- **Cohort evidence:** Current project documentation describes a deterministic
  extraction step, regulator feedback-divider calculations, part-family Vref
  lookup with a heuristic fallback, and a separate review pass. Its example
  shows Vfb derived from output and divider values. This is a documented
  capability, not a run or independent performance measurement.
- **Evidence and check:** A project-owned `regulator_feedback_map` names the
  exact adjustable regulator and two resistor identities, output/reference
  nets, mapped pin numbers and regulator pin functions, allowed nominal
  resistor-value ranges, reviewed feedback-reference bounds, target output
  range, and basis. The service
  checks native pin inventory and connectivity, DNP state, recognized direct
  resistors touching the feedback node, source-bound values, and
  `Vout = Vref * (1 + Rupper/Rlower)`. Reported nominal bounds use observed
  resistor values and the authored Vref range.
- **Incremental-value test:** A synthetic upper-resistor mutation leaves the
  existing power source/load membership check at PASS while the new lint
  reports OUT_OF_RANGE with the resistor values, mapped nodes, equation,
  output interval, target range, and project basis. The local source/load
  membership check has no setpoint predicate. A project-specific SPICE model
  may evaluate the output independently; that model-dependent comparison and
  the cohort tool's runtime were not benchmarked.
- **Boundary:** Only the mapped conventional non-inverting two-resistor DC
  divider is evaluated. Do not infer device type, topology, or Vref from an IC
  name. Alternate topologies and fixed-output regulators need separate
  authored profiles and supported equations. Nominal value ranges do not model
  resistor tolerance. The check does not prove stability, compensation,
  startup, load response, device ratings, copper continuity, or PCB feedback
  routing. Extra recognized fitted direct resistors touching FB make coverage
  incomplete; resistor arrays and unrecognized branches are not detected.
- **Fixtures:** Exact adjustable divider and Vref bounds; missing FB pin;
  wrong output/reference net; stale regulator identity; changed resistor value;
  unsupported value; DNP resistor; extra direct fitted resistor on FB;
  compensation capacitor; unmapped fixed-output control; and a non-finite
  arithmetic range that must report incomplete coverage. All are synthetic.
- **Done:** Typed project map, source-bound coverage report, review/block/off
  policy, catalogued rule, CLI/MCP parity, and an explicit synthetic baseline
  test are implemented. No external cohort source, dependency, or private
  project fixture was imported.

#### LINT-037 — Project-scoped first-order RC filter review

- **Status:** Implemented as `filter.rc_corner_mismatch` with synthetic tests,
  source-bound coverage, project review/block/off decisions, and CLI/MCP parity.
- **Inspiration:** [kicad-happy](https://github.com/aklofas/kicad-happy) documents
  passive-network analysis that estimates RC corner frequencies. Its published
  repository declares the MIT license. No source, project example, or dependency
  was imported.
- **Problem:** A connected resistor and capacitor can have valid net assignments
  while nominal values put a reviewed input filter outside its intended
  frequency range.
- **Evidence and check:** An optional project map names the exact resistor and
  capacitor identities, symbols, footprints, pins, input/signal/reference nets,
  accepted nominal value ranges, target cutoff range, and design basis. For the
  explicitly supported series-R / shunt-C low-pass topology, verify the native
  pin map and fitted state, parse the observed values, calculate the nominal
  corner, and emit a review finding when the value or topology misses the authored
  target. The map must be absent by default; no topology is inferred from
  reference or value text.
- **Incremental-value test:** A synthetic capacitor-value mutation preserves
  all pin-to-net assignments while the rule reports the calculated corner and
  authored target. This adds a source-bound schematic-value comparison beyond
  connectivity. The existing SPICE lane evaluates separately authored decks;
  equivalent SPICE coverage was not claimed or benchmarked.
- **Boundary:** The first-order formula does not model source or load impedance,
  multiple poles, active filters, component tolerance, transient behavior,
  anti-alias performance, or analog-front-end safety. Unsupported networks and
  incomplete value parsing produce incomplete coverage, not a pass. The extra
  part scan recognizes supported two-pin resistor/capacitor reference patterns
  only. Coverage does not establish electrical approval or PCB connectivity.
- **Fixtures:** In-range single-pole low-pass; changed capacitor value with
  unchanged pin/net assignments; wrong capacitor net; disconnected reference;
  DNP part; unsupported resistor value; wrong symbol identity; missing pin
  inventory; extra fitted parallel resistor/capacitor; block, off, and exact
  ignore decisions; no-map control; CLI/MCP parity. All inputs are synthetic.
- **Done:** Typed source-bound coverage, fault and control cases, value-mutation
  incremental test, CLI/MCP parity, and catalog/docs are implemented. No
  cohort source, dependency, proprietary board, or project fixture was imported.

#### LINT-038 — Connector return-distribution review

- **Status:** Implemented as `connector.return_distribution` with synthetic fault
  and control cases, source-bound connector coverage, project review/block/off
  decisions, exact ignores, and CLI/MCP parity.
- **Inspiration:** [kicad-happy](https://github.com/aklofas/kicad-happy) reports
  a signal-to-return contact ratio as a connector review metric. Its published
  repository declares the MIT license. That example threshold is not a
  universal requirement and will not be copied as a default.
- **Problem:** Existing rules can flag absent returns and return-function pins
  that disagree across connectors, but they do not summarize whether a
  reviewed external interface allocates enough return contacts for its signal
  count.
- **Evidence and check:** The project interface catalog can label each pin as
  `signal`, `return`, `supply`, `shield`, or `other`. An opt-in project map
  names an interface, minimum signal-contact count, maximum signal-to-return
  ratio, and basis. The checker counts mapped contacts in each role; supply,
  shield, and other contacts do not enter the ratio. An out-of-range ratio or
  missing role evidence produces a review candidate with exact pin lists and
  counts. No project threshold means `NOT_REQUESTED`. The ratio never infers a
  common net; exact shared, bonded, or isolated relationships remain in
  `pin_connectivity` and `grounding` contracts.
- **Incremental-value test:** Compare against
  `connector.repeated_pin_function`, `connector.no_connected_return`, and
  connector-coverage findings. On a synthetic connector with six signal
  contacts and one connected return, the existing missing-return and repeated
  return checks stay quiet while this project threshold emits the distinct
  6:1 distribution question. Two returns meet an inclusive 3:1 boundary;
  splitting their nets does not change the ratio result, while the existing
  repeated-return rule independently asks for review.
- **Fixtures:** Many-signal connector with one connected return; exact 3:1
  boundary with two returns; shared and split return nets; supply and shield
  excluded; below-scope power connector; missing/unaccounted pin roles; no
  threshold; review, block, off, exact ignore; CLI/MCP parity. All inputs are
  synthetic.
- **Boundary:** The ratio is a project-authored review threshold, not a
  universal electrical standard or proof of return-current capacity, copper
  continuity, shield termination, chassis bonding, isolation, off-board
  wiring, or physical assembly. A split-net return can be intentional; the
  established repeated-return candidate remains an independent review signal.
- **Done:** Role-based source-bound coverage, configured thresholds, distinct
  fault/control fixtures, CLI/MCP parity, and catalog/docs are implemented.
  No cohort source, dependency, proprietary board, or project fixture was
  imported.

#### LINT-039 — Explicit switching-loop edge and copper-geometry evidence

- **Status:** Implemented v1 within the documented boundary. Native track
  geometry-kind, endpoint pad/via contacts, and same-layer track adjacency use
  PCB snapshot schema 8; schema 9 adds canonical integer-nanometer filled-zone
  island outlines and holes; the active probe now emits schema 10, adding
  target aperture shape and diameter to access-probe observations. Current
  source-bound geometry scans require schema 10. The opt-in edge map resolves a unique trace chain
  and measures its centerline length; plane edges identify one shared island
  and report its contour area. The exact-version native fixture lane passed on
  digest-pinned KiCad 10.0.0 and 10.0.5, and the installed-wheel external-project
  gate passed on 2026-09-29. Component internals and full routed-loop area remain
  explicitly deferred.
- **Problem:** LINT-023's pad-center polygon is deterministic but does not follow
  the copper route. The native snapshot retains track endpoints, pad/via
  contacts, and native track adjacency, yet the ordered pad list does not say
  which adjacent pads connect through a routed trace, through a component, or
  through a filled plane. A same-net connection can also branch or have
  multiple routes. Guessing these edge roles would turn geometry into invented
  circuit intent.
- **Evidence and check:** The opt-in project-owned edge map covers every loop
  edge with an explicit role and exact endpoint pads. Supported trace edges
  bind the expected net and layer scope, resolve a unique native track chain,
  and report ordered integer-nanometer vertices and length. Component edges
  remain explicit transitions between mapped pins; plane edges verify a shared
  native filled island and report its contour area when schema 9 evidence is
  present. Return `INCOMPLETE` for
  missing edge evidence, unsupported arc geometry, branch ambiguity, stale
  pads, or a route that cannot be uniquely resolved. The current result reports
  the pad-center area proxy and per-edge trace lengths; it does not calculate a
  full routed-loop polygon or area. The contour area is not a current-density,
  parasitic, or electrical-performance estimate.
- **Evidence foundation:** Snapshot schema 8 records each track's segment/arc kind, pad/via
  contacts, and connected tracks at endpoints. Native effective copper shapes determine
  pad/via/track contact, and track candidates come from `CONNECTIVITY_DATA.GetConnectedTracks`. The
  schema checks that every contact refers to a same-net observed object. Native fixtures have
  exercised the synthetic two-segment trace chain and an unsupported arc on KiCad 10.0.0 and 10.0.5.
  Python fixtures test detours, missing and ambiguous paths, arcs, and a 1,100-segment chain. Schema
  9 copies each native filled polygon set and calls `SHAPE_POLY_SET.Unfracture()` before reading its
  filled-island outlines and holes; this preserves clearances represented as slit contours without
  modifying the board or its native fill state. It then canonicalizes integer-nanometer rings.
  API-shaped test doubles exercise ring rotation and direction normalization, duplicate-point
  cleanup, hole ordering, and degenerate-ring rejection. The hosted fixture lane passed all four
  cases twice on both digest-pinned KiCad 10.0.0
  (`ghcr.io/kicad/kicad:10.0.0@sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3`)
  and KiCad 10.0.5
  (`ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`).
  It asserts the synthetic inner-plane bounds are exactly 6 mm square, and requires plane route
  evidence to contain a zone identity and positive contour area. The fixture maps a foreign-net
  through-hole VDD pad inside the plane; the native hole ring around it has exact bounds
  12.3995–13.6005 mm on both axes, and the pad remains outside the GND connected-island inventory.
  The lane also confirms the 15 mm route chain, keeps arc geometry unsupported, and reports the
  split plane as incomplete. A first native run exposed that the synthetic front-plane map placed
  its return pad outside its zone; the fixture zone was extended to cover that mapped pad before the
  successful version matrix. Python fixtures verify exact hole-subtracted area and that multiple
  candidate islands remain ambiguous. Contours do not establish electrical current distribution. See
  the
  [KiCad `SHAPE.Collide` API](https://docs.kicad.org/doxygen-python-10.0/classpcbnew_1_1SHAPE.html),
  [`PAD.GetEffectiveShape`](https://docs.kicad.org/doxygen-python-10.0/classpcbnew_1_1PAD.html), and
  [`CONNECTIVITY_DATA.GetConnectedTracks`](https://docs.kicad.org/doxygen-python-10.0/classpcbnew_1_1CONNECTIVITY__DATA.html)
  references.
- **Boundary:** This comparison must not infer that similar nets should join,
  select a current path through a branch, or claim loop inductance, return
  adequacy, emissions, thermal performance, or electrical behavior. A routed
  centerline polygon is still a geometric screen; a large filled-zone contour
  is not an electric-field or current-density model. Project-authored topology
  and reviewed limits remain required, and the default policy stays `review`.
- **Fixtures:** Two-segment native same-layer chain; synthetic detoured trace
  whose centerline length changes while pad centers remain fixed; missing
  segment; disconnected endpoints; alternate paths and branch spurs;
  unsupported arc; a 1,100-segment route; a multi-layer trace through a via and
  an out-of-scope via fault; explicit component edge; synthetic filled-plane
  hole and area-subtraction control; ring-rotation, reversal, duplicate-point,
  hole-order, and degenerate-ring controls; valid multi-layer plane transition;
  exact native inner-plane outline bounds and a non-empty clearance-hole ring; multiple
  shared plane identities; intentionally incomplete map; and exact boundary
  values.
  The hosted native fixture lane runs each case twice on supported KiCad images
  and preserves source, probe, and toolchain hashes.
- **Incremental-value test:** Show which synthetic route mutations leave the
  pad-center proxy unchanged but change the per-edge measured trace. Also show
  that ambiguous and unsupported routes become incomplete rather than
  selecting a convenient path. A full routed-area metric needs separate
  geometry support for component and zone transitions before it can be
  evaluated against an independent oracle.
- **Done when:** Typed project map, source-bound native evidence, deterministic
  exact-version route and contour fixtures, clear unsupported-state reporting,
  review/block/off and exact-ignore behavior, docs, catalog coverage, and CLI/MCP
  parity (if surfaced) pass the installed-package verification lane.
- **Implementation note:** Initial inspection found that native snapshots
  captured track endpoints and filled-zone island identities without contours.
  Schema 8 added pad/via contacts and native track adjacency; schema 9 adds
  canonical filled-island outline and hole rings; schema 10 adds access-probe
  target aperture shape and diameter. Python analysis resolves only
  unique native trace chains; component internals and full routed-area
  comparison remain future work.

#### LINT-040 — Numbered positive supply-rail review

- **Status:** Implemented as `net.numbered_power_rails` with synthetic fault
  and control cases, review/block/off behavior, and CLI/MCP parity.
- **Cohort failure input:** kicad-happy issue
  [#40](https://github.com/aklofas/kicad-happy/issues/40) reports that its
  name-based PCB power analysis can skip ordinary channel labels such as
  `CH2_VDD` when rail metadata is absent. This tooling does not infer power
  roles or claim that sibling rails should be commoned. The review candidate
  now recognizes the bounded `P`, `CH`, and `RAIL` numeric-prefix forms before
  allowlisted positive-supply stems, so those naming patterns receive an
  explicit human review prompt.
- **Problem:** Connector pin-function matching is useful when symbol metadata
  is recognizable. It can miss sibling supply domains when connector pins
  have numeric or generic functions and their net labels carry the only clue.
- **Evidence and check:** The source-bound KiCad 10 netlist groups names with
  either an explicitly delimited numeric suffix or a bounded `P`, `CH`, or
  `RAIL` numeric prefix when the remaining stem is in a bounded allowlist of
  positive supply names. It emits exact net-to-pin evidence for groups with
  distinct indexes. A small shared-alias map
  treats `+5V`, `5V`, and `5.0V` as one family, along with selected named
  domains such as `VDD`, `VBUS`, and `VIN`.
- **Boundary:** Similar names are only a review clue. These rails can be
  intentionally isolated or supplied independently. The check does not infer
  a connector pin's function, voltage, source capability, required tie,
  off-board path, or PCB continuity. Compact suffixes without a separator are
  deliberately excluded to avoid interpreting voltage digits as indexes.
  Prefix recognition is limited to `P<number>_`, `CH<number>_`, and
  `RAIL<number>_` forms with a recognized supply stem; labels like
  `AUX_5V` or `DC_IN_RAW` are not classified by this rule.
- **Fixtures:** `+5V_1` and `5V-2` on generic connector pins with a third
  corresponding power pin left unassigned; `CH2_VDD`/`CH3_VDD`, `P1_5V`/
  `P2_5.0V`, and `RAIL4_VIN`/`RAIL5_VIN` prefix forms; signal-name,
  unlike-stem, single-rail, common-rail, and compact ambiguous `+5V1`/`+5V2`
  controls; block/off decisions; CLI/MCP parity through the shared design-lint
  service. The `CH2_VDD`/`CH3_VDD` fault and common-net control also export
  twice on pinned KiCad 10.0.0 and 10.0.5; source hashes and exact endpoint
  evidence are recorded in the
  [native fixture README](../tests/fixtures/design_lint/cohort-channel-power-names/README.md).
- **Done:** Cataloged deterministic candidate, exact evidence, conservative
  name controls, policy behavior, and CLI/MCP parity are implemented. This is
  a review signal, not electrical approval or a project wiring requirement.

#### LINT-041 — Named complementary-net pair review

- **Status:** Implemented as
  `signal.named_pair_without_reviewed_requirement` with synthetic fault and
  valid-control cases and the shared design-lint policy lifecycle.
- **Inspiration and evidence:** The read-only `pcb-inspector` trial above
  found a 0.50 mm synthetic skew that native DRC did not report when the
  project pair-rule file was absent. Its 0.15 mm threshold is only a candidate
  default, not a universal requirement. The local rule addresses the missing
  review coverage without adding a guessed geometric threshold.
- **Predicate:** Two populated native-netlist nets have an exact complementary
  suffix pair (`_P/_N`, `_DP/_DM`, `_TXP/_TXN`, `_RXP/_RXN`, `_H/_L`, `+/-`,
  `DP/DM`, `P/N`, or `H/L`) and the exact oriented pair is absent from the
  project-owned `pcb_differential_pair_rule_map`.
- **Boundary:** This only identifies a name-pattern candidate. It cannot
  establish that the nets are a differential interface, inspect board routes,
  or choose width, gap, skew, or uncoupled-length limits. An explicit map
  suppresses the missing-requirement prompt; LINT-022 still checks whether its
  named bounds have exact active native DRC coverage. The finding defaults to
  review and can be blocked, disabled, or exactly ignored per project.
- **Fixtures:** Populated `USB_DP`/`USB_DM` pair without a map; exact project
  pair-map control; ambiguous short names `VIP`/`VIN`; review, block, off, and
  exact-ignore decisions; CLI/MCP parity through the shared typed service.
- **Done:** The rule is cataloged, source-netlist based, deterministic,
  synthetic-tested, and does not assign electrical limits from naming.

#### LINT-042 — Likely I2C responder address-map coverage prompt

- **Status:** Implemented as bus.i2c_unmapped_responder with a synthetic fault,
  mapped-responder and non-IC controls, and project rule-mode coverage.
- **Inspiration and measured input:** The LINT-031 kilint 0.5.1 trial found a
  synthetic IC attached to SDA and SCL without an address declaration. The
  local baseline did not emit a candidate when the project address map was
  absent. The candidate rule's board-name predicate was not adopted.
- **Predicate:** For non-DNP U- or IC-prefixed components, use native symbol
  functions and source-bound net assignments to find uniquely assigned SDA
  and SCL pins on distinct nets. Prompt when that reference is not listed in
  the project-authored I2C address map, including when the map is absent.
- **Boundary:** This is a review prompt; it does not infer addresses or prove
  that a device is an I2C responder. Reference conventions are limited to U
  and IC, and recognized pin functions are limited to SDA, I2C_SDA, SCL, and
  I2C_SCL after punctuation normalization. Bridges and other intentionally
  unaddressed parts may need an exact ignore or project rule override.
  A mapped reference is considered covered here; wrong identity, pins, and
  addresses remain the map comparison's separate findings. DNP parts and
  unassigned signal pins are excluded.
- **Fixtures:** Missing address map; incomplete map with an unlisted peer;
  listed responder; non-IC connector; DNP part; block/off mode; CLI/MCP parity
  through the same typed design-lint service. All inputs are synthetic.
- **Done:** The catalog entry, source-bound candidate, project review policy,
  synthetic regressions, user documentation, and explicit CLI/MCP parity
  assertion are implemented. The rule remains review-only by default; no
  external dependency or private board source is used.

#### LINT-043 — Exact-symbol connector peer-pin outlier review

- **Status:** Implemented v1 as a review-only native-netlist heuristic for
  same-symbol connector contacts whose pin-function metadata is incomplete.
- **Problem:** A generic or unnamed contact can be unconnected, or assigned to
  a minority net, while matching connector instances assign that pin
  consistently. Function-based comparison may not have a usable pin role.
- **Predicate:** For fitted J/P/X/CN references using one exact library symbol,
  compare each pin number's schematic net assignments. Report an unconnected
  peer when another instance is connected, including a two-instance group, or
  a differing assignment when a unique most-common assignment is shared by at
  least two instances. Require at least one peer to lack exported pin-function
  metadata; tied assigned-net patterns remain under
  `connector.peer_pin_assignment_divergence`, and fully named pin groups remain
  under `connector.repeated_pin_function`.
- **Boundary:** Matching symbol contacts are only comparable candidates; they
  do not prove the contacts should share a net. Per-port isolation, optional
  pins, and intentionally unused contacts can be valid. An explicit native
  no-connect marker remains an unassigned contact for this comparison: the
  rule still asks for review when its same-symbol peer is assigned. A marker
  alone does not resolve the interface requirement. Unusual connector
  reference prefixes, missing symbol identity, and absent native pin-number
  inventory are outside the rule. DNP instances are excluded. The check does
  not prove PCB copper or off-board continuity.
- **Fixtures:** Missing generic contact; minority-net outlier; consistent
  common assignment; a two-connector open-contact fault with common-net and
  exact-ignore controls; an explicit no-connect-marker peer fault; all-distinct
  independent ports; DNP outlier; named-pin rule control; project block/off
  overrides and exact fingerprinted ignore.
  The native fault/control set in the tooling-owned
  [fixture README](../tests/fixtures/design_lint/generic-peer-pin-assignment-native/README.md)
  confirms that KiCad retains symbol pin-number inventory when the pin function is
  empty. Its fault localizes open J3.1 while J1.1 and J2.1 share `+5V`; the
  minority-net fault localizes J3.1 on `+3V3` while J1.1 and J2.1 share
  `+5V`. The common-net control passes without findings.
- **Native evidence:** version-parameterized pytest cases in
  `tests.test_ci_hosted_connector_returns` export the minimum two-connector
  open-contact fault, an explicit
  no-connect-marker peer fault, and the common-net control, plus the
  three-connector unique-minority fault and common-net control, twice with
  digest-pinned KiCad 10.0.0 and 10.0.5. The two-connector open and marked-open
  faults both localize J2.1 when J1.1 is assigned `+5V`; the common-net control
  assigns both pin 1 contacts to `+5V` and passes. The same lane also
  exercises the separate no-majority divergence case recorded under LINT-047.
  It validates source hashes, exact typed-netlist assignments and lint
  evidence, and normalized export repeatability.
- **Done:** Catalog, documentation, deterministic predicate, synthetic
  fault/control cases, DNP exclusion, source-bound findings, and exact-version
  native export coverage are implemented. No proprietary project source or
  cohort code is used.

#### LINT-044 — Per-rule schematic geometry coverage

- **Status:** Implemented v1. The source scan retains unsupported conditions by
  affected rule. The report gives each geometry rule `DISABLED`, `COMPLETE`,
  `PARTIAL`, or `UNSUPPORTED`; overall coverage aggregates only enabled rules.
- **Problem:** A limitation in one geometry extractor could make every
  configured schematic rule appear partial. Public examples with multiline
  text showed that this hid usable evidence from unrelated wire geometry.
- **Predicate:** Parser and instance-mapping limitations are assigned to the
  rule classes that depend on them. A wrong KiCad version or schematic format
  leaves each enabled rule unsupported. A supported rule remains complete when
  another disabled rule has unsupported geometry. Missing or ambiguous source
  and native bindings remain blocked at the source-bound service boundary.
- **Boundary:** This refines coverage reporting; it does not expand geometric
  support, suppress findings, or change electrical connectivity. The mapping
  from parser limitation to affected rules is an explicit maintenance surface
  and must be updated when a rule gains new evidence dependencies.
- **Fixtures:** Unsupported formatted text plus a supported wire-through-body
  finding; wire-body-only policy reports complete coverage; text-overlap policy
  reports partial coverage; disabled rules remain disabled; exact-version and
  repeated-sheet reference-mapping boundaries; native netlist/ERC parity for
  the text-only source mutation; shared CLI/MCP report parity.
- **Done:** Per-rule status and unsupported evidence are source-bound,
  deterministic, visible in the typed report, and tested with synthetic
  fault/control inputs. No project source is used.

#### LINT-045 — SPI active-low chip-select idle-bias review

- **Status:** Implemented v1 as a configurable native-netlist review heuristic,
  inspired by the kicad-happy `validate_spi_bus` PR-002 check.
- **Problem:** A peripheral with an assigned active-low chip-select input may
  be selected while the controller pin is inactive or high impedance during
  reset. A connected net and ERC pass do not establish the startup state.
- **Predicate:** For each fitted symbol pin with an explicit active-low
  chip-select spelling and native `input` or `input_low` type, require one
  assigned non-return net. Emit one review candidate per net when there is no
  fitted conventional direct or unbranched series-resistor path of 1 kΩ–100
  kΩ to a positive rail recognized by the existing narrow rail-name or
  supply-function map. DNP devices and resistor paths are excluded. Bare `CS`,
  `SS`, or `CHIPSELECT` names do not establish polarity.
- **Boundary:** This is a review prompt, not a universal external-resistor
  requirement. It cannot see internal bias, controller reset/firmware behavior,
  off-board circuitry, resistor arrays, jumpers, active bias networks, custom
  supply names, or device selection timing. The broad 1 kΩ–100 kΩ range is a
  detection window, not a recommended value or proof of electrical margin.
  Project policy can set the rule to `off`, retain `review`, or explicitly
  promote it to `block`; a fingerprinted ignore records a reviewed exception.
- **Cohort input:** The pinned kicad-happy
  [`validate_spi_bus` PR-002 implementation](https://github.com/aklofas/kicad-happy/blob/a6bba1add1e18b89e3aa0824b9769ed1d9d79174/skills/kicad/scripts/validation_detectors.py#L822-L844)
  selects candidate ICs through part-keyword and pin-name lists and searches
  for a resistor to a non-ground power net. Its runtime trial under LINT-031
  found the missing-bias case and accepted the fitted 10 kΩ control, but it
  also accepted DNP 10 kΩ and 0 Ω anti-controls. LINT-045 narrows the candidate
  to explicit active-low native input pins and fitted 1 kΩ–100 kΩ paths.
  No cohort code was copied.
- **Fixtures:** Missing bias; direct 10 kΩ and unbranched two-resistor valid
  paths; DNP device and resistor; wrong-rail resistor; zero-ohm and out-of-band
  values; bare-polarity and output-pin controls; exact rule `review`/`block`/
  `off` and fingerprint-ignore behavior; shared CLI/MCP parity.
- **Done:** Catalog entry, deterministic predicate, rule-policy lifecycle,
  source-bound report evidence, synthetic fault/control coverage, public cohort
  source attribution, and user documentation are implemented. No cohort code,
  project fixture, or proprietary board source is stored.

#### LINT-046 — IC supply rail without a fitted schematic capacitor

- **Status:** Implemented v1 as a configurable, default-review native-netlist
  heuristic. Cohort comparisons include kicad-happy `DO-DET` and kicad_skills
  `analog.missing_decoupling`; neither cohort implementation is a dependency.
- **Predicate:** For each fitted non-connector component with a native
  `power_in` pin on a uniquely assigned net, recognize a positive rail through
  the existing narrow `power_function_key` net-name or attached-pin-function
  list. Report that rail when no fitted component with a common capacitor
  library symbol name (`C`, `C_*`, `CP`, `CP_*`, or a name containing
  `capacitor`) connects it to a distinct net with a recognized return-like
  name or attached pin function. Explicitly DNP components do not count as ICs
  or capacitors.
- **Boundary:** This asks for datasheet and placement review. A capacitor
  connected between the supply rail and a recognized return-like net does not
  prove that it is required, has the right value, sits near the IC, or has an
  adequate physical return path. Internal, remote, and off-board decoupling
  can be valid. Custom rail names without a recognized pin function or custom
  return labels without a recognized return pin function can evade the
  heuristic; uncommon capacitor symbol IDs can create extra review prompts.
  References beginning J/P/X/CN are excluded as connectors; other connector
  prefixes may be included as IC candidates. Project policy may choose
  `review`, `block`, or `off`, and exact ignores use the existing fingerprint
  lifecycle.
- **Cohort evidence:** At pinned kicad-happy commit `a6bba1add1e18b89e3aa0824b9769ed1d9d79174`,
  repeated source-backed runs distinguish the no-cap fault from the capacitor control while KiCad
  ERC reports no power-source error or capacitor-presence diagnostic. The cohort reports both the
  `power_in` consumer and synthetic `power_out` source as missing decoupling; LINT-046 scopes its
  prompt to the `power_in` consumer. This corroborates review coverage over native ERC, not unique
  detection over LINT-046. Tooling independently implements only the bounded symbol, assigned-net,
  and return-label presence question. The candidate reports were identical across repeats; hashes
  and reproduction details are in the
  [synthetic fixture notes](../tests/fixtures/design_lint/cohort-power-pin-dc/README.md). A second
  trial of kicad_skills `analog.missing_decoupling` on the same source-backed pair duplicates
  LINT-046's fitted-capacitor fault/control result. On a native-exported DNP-capacitor variant,
  LINT-046 correctly emits a rail-level review while the candidate stays quiet because it accepts
  the `C` reference as coverage without checking DNP state. Its `--no-cli` run and exact report
  hashes are recorded in LINT-031 and the fixture notes.
- **Fixtures:** No fitted capacitor; fitted capacitor from the rail to a
  recognized return; DNP capacitor; capacitor on another rail; open or same-net
  capacitor terminals; unrecognized return; DNP IC; connector power pin;
  passive instead of `power_in`; unrecognized rail; policy override/off/exact
  ignore; shared CLI/MCP parity. All Tooling cases are synthetic.
- **Validation state:** Catalog, deterministic predicate, typed report
  evidence, policy lifecycle, synthetic fault/control coverage, and shared
  CLI/MCP parity are implemented. The pinned native lane exports each fixture
  twice and compares normalized netlists and ERC reports on KiCad 10.0.0 and
  10.0.5. The source-backed no-cap fault has `U1.1` and `U2.1` on `+3V3`, no
  `power_pin_not_driven` violation, and one LINT-046 review finding; its
  capacitor-bearing source control has no LINT-046 finding. A sixth native
  case keeps the same mapped `C1` pins but marks the capacitor DNP; both pinned
  versions preserve the DNP state and repeat the netlist/ERC exports, while
  LINT-046 emits a rail-level review because no fitted decoupling capacitor is
  present. Fixture hashes are
  asserted. These results establish only review coverage for fitted
  capacitor-symbol presence, not capacitor need, value, placement, current, or
  PCB return path.
  No proprietary project source or fixture was inspected or stored.

#### LINT-055 — Project-mapped series power-path consistency

- **Status:** Implemented v1 as a default-review project map with typed-netlist
  fault/control cases, CLI/MCP parity, and tooling-owned schematic plus ERC
  exports on KiCad 10.0.0 and 10.0.5. The wrong-source-net fault is flagged by
  the mapped check while native ERC reports zero errors for both fault and
  control.
- **Cohort input:** The pinned kicad-happy `PP-001` candidate walks across
  selected low-resistance components and rejects capacitors. LINT-031 found no
  unique source-path detection on its initial disconnected-pin cases because
  native ERC already reports an undriven power pin. This authored ferrite-path
  rule now has a separate source-side wrong-net case that ERC does not report.
  The candidate's broader ferrite, fuse, jumper, and DNP behavior remains
  unestablished. Tooling does not adopt its component classes, inference,
  severity, or runtime.
- **Need:** The current `power_connectivity` contract checks that source and
  load pins share one exact net. It cannot encode a reviewed series chain
  through a fuse, ferrite, or fitted solder jumper. A project-owned path map
  makes that intended topology independently testable without heuristically
  deciding which components conduct power.
- **Predicate:** For each mapped path, check exact start/end symbol and
  footprint, native pin inventory, fitted state, and pin-to-net assignment.
  Each required two-terminal element must match the mapped identity and join
  the adjacent, ordered nets. The rule reports only when the project supplied
  the requirement and defaults to `REVIEW`.
- **Boundary:** It does not infer that a path is required, identify unlisted
  parallel paths, check values or ratings, establish current direction or
  component conduction, validate datasheet pinout truth, or prove PCB copper
  continuity. Direct same-net requirements remain in `power_connectivity`;
  multi-pin switches and semiconductor paths need separate models.
- **Fixtures:** Synthetic ferrite path pass; open source, element, and load
  faults; DNP, wrong identity, mapped-net mismatch, two-stage bead/fuse
  controls; ordered-map metamorphic comparison; project review/block/off and
  exact-ignore behavior; CLI/MCP parity; and a native ferrite-path control with
  `U2.1` assigned to `VLOAD` while `FB1.1` is assigned to `GND`. A synthetic
  ERC-only `PWR_FLAG` models the load rail as powered across the bead. Both
  native control and fault have zero ERC errors on each pinned version, while
  only the fault receives the mapped-path review. Exports and normalized
  netlist/ERC reports repeat for both versions. No product source is used.
- **Remaining:** The demonstrated gain is limited to this synthetic,
  project-authored wrong-net requirement. Measure false-positive behavior on
  broader non-proprietary circuits before making project-specific policy
  stricter. The rule still does not prove PCB connectivity, component
  conduction, or electrical suitability.
- **Observed overlap:** Open/unassigned endpoints can also trigger existing
  unconnected-pin heuristics or ERC. Those cases remain covered as contract
  faults but are not counted as LINT-055's incremental result. The incremental
  result is the assigned wrong-net case, where native ERC has no errors and the
  exact authored path map reports the source-to-load mismatch.
- **Tagged hosted acceptance:** The scoped `v0.5.0rc71` gate passed on
  2026-10-11 (GitHub Actions run `38133015752`). The native power-path fixture
  lane was enabled with `KICAD_RUN_NATIVE_POWER_PATH_FIXTURES=1`; its control
  and fault passed on pinned KiCad 10.0.0 and 10.0.5.

#### LINT-056 — Unmapped power-input source-path review

- **Status:** Implemented as a default-review heuristic with synthetic
  fault/control, bounded component recognition, project override/ignore,
  CLI/MCP parity, and native KiCad 10.0.0/10.0.5 comparison. Supported path
  evidence includes source-to-load traversal through exact `Device:D` and
  `Device:D_Schottky` identities, plus bidirectional paths through exact
  bridged two-pin and three-pin solder-jumper identities. Native controls also
  cover custom-rail source-anchor coverage and DNP external-source population.
- **Cohort input:** The pinned kicad-happy `PP-001` analyzer flags the same
  ERC-clean wrong-rail fixture when no project path map is supplied. Its
  broader inferred component model and “AC-coupled to ground only” message are
  not copied. Repeated candidate report digests and source pins are recorded
  under LINT-031 and in the synthetic fixture notes:
  [power-path-native](../tests/fixtures/design_lint/power-path-native/README.md).
- **Cohort-derived anti-control (2026-10-11):** The public
  [kicad-happy v2.3.0 changelog](https://github.com/aklofas/kicad-happy/blob/v2.3.0/CHANGELOG.md)
  records a false fuse classification for an `F1`-referenced 74LS32 and a fix
  that uses IC identity rather than the reference prefix. Tooling's path graph
  already recognizes only exact native fuse, polyfuse, and other supported
  symbol identities. A new typed-netlist pair puts an `F1` 74LS32 between the
  synthetic source and load and confirms LINT-056 still reports the
  unsupported path, while the matching `F1`/`Device:Fuse` control clears it.
  This is source-informed first-party coverage, not a runtime trial of
  kicad-happy or a new native export; no cohort code or board source was copied.
- **Bootstrap boundary (2026-10-23):** A source audit of the current
  kicad-happy `PP-001` implementation at commit
  [`4701c26eba7b9788874a0bf9b45c0a3e81db1628`](https://github.com/aklofas/kicad-happy/commit/4701c26eba7b9788874a0bf9b45c0a3e81db1628)
  found a name-token exemption for bootstrap pins. A synthetic control confirms
  LINT-056 stays quiet when a fitted capacitor connects `BST` to the switch
  node; a paired `BOOT_EN` name collision with only a return capacitor remains
  reviewable. Keep the existing topology-based evidence boundary and do not
  add a second PP-001 check. This source audit and typed-netlist pair do not
  measure candidate runtime behavior, reviewer value, or field precision.
- **Predicate:** For a fitted internal native `power_in` pin on a net with a
  fitted, inventoried two-terminal capacitor to a recognized return, emit
  `REVIEW` when no recognized source anchor exists, or when an anchor exists
  but no bounded path reaches it. A recognized positive-rail name or fitted
  `power_out` pin is an anchor. Bidirectional paths use fitted, inventoried
  two-pin resistors at or below 1 ohm, inductors, ferrite beads, fuses,
  polyfuses, and exact `Jumper:SolderJumper_2_Bridged` symbols with native pins
  `1`/`2` mapped to `A`/`B`, exact `Jumper:SolderJumper_3_Bridged12` symbols
  with pins `1`/`2`/`3` mapped to `A`/`C`/`B` and only the 1-to-2 bridge, and
  exact `Jumper:SolderJumper_3_Bridged123` symbols with the same complete pin
  map and all three pins bridged. Each recognized pin must have one net
  assignment. Exact `Device:D` and `Device:D_Schottky` symbols are traversed
  only from the source-side cathode net toward the load-side anode net, with
  complete native pin roles. A path endpoint named by the project power-path
  map is excluded from this heuristic so the exact mapped result is not
  duplicated.
- **Boundary:** A recognized positive net name counts as a source anchor, so
  naming can make an externally disconnected rail appear covered. A custom-
  named external source without an attached fitted `power_out` pin now yields a
  source-anchor coverage prompt; this does not establish that the source is
  missing. A fitted `power_out` pin counts as an anchor without proving that
  its component operates. Unknown switches; open or DNP jumpers; three-pin
  variants other than the exact `Bridged12` and `Bridged123` identities; other
  jumpers; Zener, TVS, and custom diodes; regulators; other semiconductor
  paths; and ambiguous pin inventories are not modeled and can prompt review
  for valid topology. The candidate does not establish that a
  connection is required, that current flows, or that PCB copper or external
  wiring is complete. Project-authored paths remain the stronger requirement.
- **Fixtures:** Control and wrong-rail fault reuse only the tooling-owned
  synthetic ferrite-path schematic. Both retain a fitted capacitor from
  `VLOAD` to `GND`; the fault moves `FB1.1` from `VIN` to `GND`. The valid
  control reaches `VIN` through the bead; the fault does not. Both native ERC
  runs have zero errors and the same violation types on KiCad 10.0.0 and 10.0.5.
  With no map, only the fault gets the new review; with the explicit map, the
  mapped mismatch reports and suppresses duplicate heuristic output. No
  proprietary project source is used.
- **Additional synthetic topology evidence:** A custom-named external
  connector source with no recognized source pin now produces an explicit
  source-anchor REVIEW; the same source with a fitted `power_out` pin is a
  quiet control. A fitted regulator `power_out` pin is an anchor, while its
  DNP state restores a source-path REVIEW. Exact fitted `Device:D` and
  `Device:D_Schottky` symbols now count in the forward direction when native
  pin roles are complete. Reverse, DNP, unsupported, or incompletely mapped
  diodes; open, DNP, or unsupported jumpers; and custom-library bead paths
  remain REVIEW candidates. These are typed
  synthetic netlist fixtures; they do not assert conduction or physical source
  wiring. A separate isolated return remains distinct from board `GND`; the
  fitted external `power_out` case is quiet, and the same valid off-board source
  without source-pin metadata prompts for an exact project decision. A DNP
  external `power_out` does not anchor the assembled circuit. A custom library
  capacitor whose symbol name contains `Capacitor` is recognized, while an
  arbitrary custom symbol name is not assumed to identify a capacitor. Exact
  three-pin `Bridged12` and `Bridged123` identities contribute only their
  encoded terminal groups after the complete native `A`/`C`/`B` pin map and
  one-net-per-pin evidence match. The `Bridged12` control reaches the load
  through pins 1 and 2 while pin 3 stays separate; the `Bridged123` control
  reaches it through pins 1 and 3; a `Bridged12` schematic that puts the load
  on pin 3 remains REVIEW.
- **Native result:** The tooling-owned `fault.kicad_sch` with custom rail
  `LOCAL_A` was exported twice with the digest-pinned KiCad 10.0.0 and 10.0.5
  images. Both versions produced repeatable normalized netlist and ERC
  evidence, retained native `power_pin_not_driven`, and emitted
  `power.input_without_supported_source_path` with
  `source_anchor_state=not_recognized`. This is a source-coverage review on
  top of a native ERC finding, not incremental defect detection. The fitted
  named-rail and `power_out` controls remained quiet for source-path review.
- **Isolation control:** A third native schematic keeps the fitted source path
  intact while returning its decoupling capacitor to `ISO_RETURN`, with no
  `GND` net. Exact KiCad 10.0.0 and 10.0.5 exports retained that separate net,
  repeated to identical normalized netlist/ERC evidence, and produced no
  source-path candidate or native ERC error. This is a valid isolated-domain
  control, not a requirement that other project returns remain separate.
- **Native custom-symbol boundary:** Tooling-owned native schematics exercise
  `Vendor:Power_Capacitor` on both the supported and wrong-rail topologies, and
  an opaque `Vendor:CAP123` symbol on the wrong-rail topology. The named alias
  receives LINT-056 only on the wrong-rail case. The opaque symbol does not
  count as capacitor evidence for LINT-056; the existing LINT-046 decoupling
  rule independently asks for review because no recognized fitted capacitor
  is present. This overlap is reported as LINT-046 evidence, not misattributed
  as a source-path finding.
- **Native DNP external-source boundary (2026-09-30):** The paired
  `external-source-control` and `dnp-external-source-fault` schematics export
  a two-pin synthetic `J1` on custom rail `AUX_INPUT`; pin 1 is `power_out`,
  and pin 2 returns to `GND`. Both pinned versions preserve the exact symbol,
  pin inventory, net assignments, and fitted/DNP state in normalized native
  netlists. The fitted control is quiet; with `J1` marked DNP, the source pin
  is excluded from source-anchor evidence and LINT-056 reports `REVIEW`.
  Native ERC has no errors in either case. This proves the DNP population
  boundary for the exported schematic, not the physical source or assembly.
- **Native alternate-source control (2026-09-30):** The synthetic
  `alternate-source-control` schematic marks `J1` DNP and keeps `J2` fitted.
  Each two-pin `power_out` source has its own ferrite branch to `VLOAD`, and
  both connector returns map to `GND`. Exact native exports under KiCad 10.0.0
  and 10.0.5 retain both branch topologies, the J1-only DNP state, repeatable
  normalized netlists, no ERC errors, and no LINT-056 finding. The check
  confirms a DNP peer does not mask a fitted source path to the internal rail;
  it does not assert that arbitrary external sources should be paralleled.
- **Native no-fitted-source fault (2026-09-30):** The paired
  `both-sources-dnp-fault` schematic preserves the same two distinct branches
  while marking both source connectors DNP. Both native versions retain the
  same normalized netlist after DNP-state normalization, have no ERC errors,
  and produce LINT-056 `REVIEW` on `VLOAD`. This confirms that DNP source pins
  on multiple candidate branches do not count as fitted source anchors.
- **Directional diode slice (2026-10-02):** The heuristic now recognizes only
  exact `Device:D` and `Device:D_Schottky` symbols with a complete two-pin
  inventory and native `A`/`K` functions. It follows the diode's source-to-load
  direction; the reverse orientation remains a default `REVIEW` candidate.
  Unit fixtures cover forward, reverse, DNP, unsupported-symbol, and
  incomplete-role cases. Native KiCad 10.0.0/10.0.5 exports cover a forward
  `Device:D` control, a reverse `Device:D` fault, and a forward
  `Device:D_Schottky` control; normalized netlist/ERC results repeat exactly
  per version, with zero ERC errors. This models a schematic direction clue,
  not a diode's actual conduction, forward drop, ratings, load current, or PCB
  path.
- **Bridged solder-jumper slice (2026-10-02):** The heuristic recognizes the
  exact fitted `Jumper:SolderJumper_2_Bridged` symbol as a bidirectional path
  only when the native inventory contains pins `1` and `2`, their functions are
  uniquely `A` and `B`, and each pin has one distinct net assignment. The
  paired exact `Jumper:SolderJumper_2_Open` topology remains a REVIEW candidate;
  unit cases also preserve three-pole, DNP, incomplete, duplicate-role, and
  unrecognized jumper boundaries. Synthetic native fixtures check both symbols
  under KiCad 10.0.0 and 10.0.5, including repeatable netlist/ERC reports and
  zero ERC errors. This schematic identity is not evidence of the assembled
  solder state or physical copper path. A source-hash-bound synthetic netlist
  also exercises the bridged control and open-symbol fault through CLI and MCP;
  both surfaces return identical reports with PASS and REVIEW respectively.
- **Three-terminal solder-jumper slice:** The heuristic additionally supports
  only `Jumper:SolderJumper_3_Bridged12` and
  `Jumper:SolderJumper_3_Bridged123`, with the complete `1`/`2`/`3` inventory
  mapped to native `A`/`C`/`B` roles. The former contributes a 1-to-2 edge and
  does not imply a path to pin 3; the latter joins all three terminals. Unit
  cases cover both controls, the unbridged-terminal REVIEW, DNP, open-symbol,
  wrong-inventory, wrong-role, and unassigned-terminal boundaries. CLI/MCP
  parity returns identical PASS/PASS/REVIEW results. Native schematics were
  exported twice with digest-pinned KiCad 10.0.0 and 10.0.5; normalized
  netlists and ERC reports repeat, and all cases have zero ERC errors. See the
  native fixture record for source and report digests. This reduces review
  noise on supported topologies; it does not add new defect detection or prove
  solder state or physical continuity.
- **Remaining:** Treat open, DNP, unsupported multi-pin, and other solder jumpers,
  Zener/TVS/custom diodes, switches, regulators, and other unknown path elements
  as unsupported until a synthetic
  fault/control pair can use exact native symbol identity, pin inventory,
  orientation where relevant, and fitted state to distinguish the candidate
  topology. A component `power_out`
  pin remains only a source anchor; it does not prove that device operates or
  that the upstream path is complete. Keep the heuristic at `REVIEW`, and use
  the authored LINT-055 path map when a project needs an exact topology. A
  custom-named external source without exported source-pin evidence still
  needs an explicit project decision.
- **Tagged hosted acceptance:** The scoped `v0.5.0rc71` gate passed on
  2026-10-11 (GitHub Actions run `38133015752`) with
  `KICAD_RUN_NATIVE_POWER_PATH_FIXTURES=1`. Hosted native fixtures passed under
  the pinned KiCad 10.0.0 and 10.0.5 images.

#### LINT-057 — Direct serial logic-voltage compatibility

- **Status:** Implemented as part of the authored `serial_peers` electrical
  contract. It compares both directions of a direct UART link using exact
  endpoint limits and native pin/net evidence; missing limits fail visibly as
  `NOT_CONFIGURED`.
- **Cohort input:** ThomsonLint's [KiCad review guide][thomson-kicad-review]
  lists a net-level voltage guess in its exported analysis; kicad-happy's
  [datasheet workflow][happy-datasheets]
  documents structured electrical-characteristic extraction. These mutable
  `main` references were inspected on 2026-09-30 and supplied the candidate
  category only. Tooling does not adopt heuristic voltage guesses, rely on
  model-generated values, or copy cohort code.
- **Predicate:** For each direction, the driver's guaranteed low output range
  must stay within the receiver's absolute minimum and maximum and below its
  maximum low threshold. The guaranteed high output range must meet the
  receiver's minimum high threshold and remain below its absolute maximum.
  Both directions are checked against the source-bound native TX/RX pin maps.
  Every range carries a document basis and operating conditions.
- **Boundary:** The project supplies the limits and sources. The checker does
  not verify datasheet provenance, test conditions, load, common-mode range,
  transient overshoot, slew rate, timing, or runtime behavior. It applies only
  to direct logic-level serial peers; RS-232, RS-485 and level-shifted routes
  use separate contracts, and external peer voltages are unavailable locally.
- **Fixtures:** Synthetic direct-link control; output-high maximum equal to
  receiver absolute maximum; excessive high level; excessive output-low
  maximum; missing endpoint limits; invalid overlapping input/output ranges;
  level-shifted and external not-applicable controls; CLI/MCP parity; retained
  evidence replay. No product source or fixture is used.

#### LINT-058 — Adjacent reference-plane centerline coverage

- **Status:** Implemented as an opt-in, configurable `REVIEW` heuristic with
  exact synthetic polygon, clearance-hole, threshold, unsupported-geometry,
  mapping, ignore/override, and CLI/MCP parity cases. It consumes the existing
  source-bound KiCad 10 PCB snapshot schema 10 (schema 9 introduced the zone
  contours this rule uses). Its native geometry fixture
  passed twice on each pinned KiCad 10.0.0 and 10.0.5 image with the same exact
  4/15 coverage result, a 0.3 fault threshold, and a 0.25 control threshold. A
  separate native via-hole fixture repeats an exact 2799/4000 coverage result
  on both versions with 0.75 fault and 0.5 control thresholds. A new synthetic
  narrow-void pair uses a 0.65 fixture threshold to distinguish its continuous
  control from a 0.2 mm midpoint notch. Installed KiCad 10.0.6 compatibility
  evidence measured `2799/4000` and `2399/4000`, respectively; the hosted
  10.0.0/10.0.5 repeat lane is now split into pytest suites for reference
  plane, switching-loop, and return-path fixtures. On 2026-10-11, the
  digest-pinned native run passed all eight parametrized cases across KiCad
  10.0.0 and 10.0.5 in 42.67 seconds.
- **Cohort input:** pcb-inspector documents `HEUR-GND-001` as a configurable
  track-to-reference-plane screen with a minimum track length and covered
  fraction. Its manual examples use 5 mm and 0.9; these are not copied as
  defaults. A kicad-happy changelog entry records a false positive when a
  route's own via antipad was counted as a plane gap. This check currently
  counts that clearance as uncovered too. It now annotates a mapped endpoint
  via whose center falls inside a same-net reference-zone hole, but does not
  claim the hole belongs to that via; synthetic model and native regressions
  preserve the known review false-positive instead of claiming it as new defect
  detection. See
  [pcb-inspector's manual](https://github.com/takzen/pcb-inspector/blob/main/MANUAL.md)
  and [kicad-happy's changelog](https://github.com/aklofas/kicad-happy/blob/main/CHANGELOG.md).
  The separate pinned kicad-happy `GP-001` runtime trial under LINT-031 misses
  the midpoint notch because its 2 mm sampling checks only both endpoints.
  A pinned `pcb-inspector` `HEUR-GND-001` trial under LINT-031 detects this
  narrow-void fault and clears the matching control with a fixture-only 0.65
  threshold. It corroborates, but does not extend, this gate: its report marks
  the entire segment affected and gives no exact uncovered-interval measure.
- **Predicate:** For each explicitly mapped signal net and copper layer, the
  checker measures each native straight-track centerline against the union of
  same-net filled-zone polygons on each immediately adjacent copper layer.
  It records an exact rational covered fraction per reference layer; for a
  track between two copper layers, a below-threshold finding is emitted only
  when both adjacent layers miss the authored threshold. The project also
  supplies the minimum segment length. Arc, absent-layer, missing-track, and
  no-adjacent-layer cases remain visible as incomplete coverage.
- **Boundary:** This measures centerline geometry only. It does not infer which
  ground domain or reference net a signal should use, inspect trace-width
  overlap or electromagnetic return fields, prove that the plane connects to
  endpoint pads, or establish current capacity, emissions, continuity, or
  electrical performance. Hole and clearance regions count as uncovered;
  the expected antipad around the signal's own via can lower a short segment's
  score. The report adds possible endpoint-via context when a mapped via center
  falls inside a same-net reference-zone hole, but does not establish hole
  ownership or remove the interval from the score. Intentionally split planes
  can also prompt review. It defaults to `review` and supports `block`, `off`,
  and exact reasoned ignores.
- **Fixtures:** Exact rational hole-subtraction and threshold controls;
  adjacent-layer and wrong-net controls; inner-layer two-sided coverage;
  split-zone gap with REVIEW plus explicit alternate-reference-net control;
  branched-route localization with a passing trunk and a below-threshold branch;
  missing track/layer and unsupported arc controls; configured fault/control;
  project policy; a known signal-via-antipad review false-positive with a
  shifted-hole control that leaves the measured score unchanged; native via
  antipad, endpoint-contact, and hole-context controls on KiCad 10.0.0 and 10.0.5;
  a native two-layer 0.2 mm narrow-void fault/control lane is configured for
  the same pinned versions; source-bound report equality through CLI and MCP.
  No proprietary board or project fixture is used.
- **Remaining:** The center-in-hole annotation is context, not proof of via
  ownership; a synthetic merged-clearance regression now confirms that a hole
  containing an unrelated via remains fully uncovered and is not attributed to
  the endpoint via. The finding explicitly says the contours do not identify
  which clearance created a merged hole. Keep counting those intervals as
  uncovered and keep this rule review-only. Synthetic split-plane and branch
  controls now verify the mapped-net comparison and per-segment localization.
  Short tracks below the authored minimum are always listed in both report
  surfaces. The new per-requirement `review_excluded_short_tracks` option can
  make any such exclusion an explicit `REVIEW` coverage gap; the default leaves
  the project-authored minimum as the scope boundary. Synthetic quiet/review/
  block controls and CLI/MCP parity cover both choices. Tagged hosted
  acceptance passed in `v0.5.0rc72` (GitHub Actions run `38133685685`) with
  `KICAD_RUN_NATIVE_PCB_FIXTURES=1`, including the digest-pinned KiCad
  10.0.0/10.0.5 narrow-void fault/control lane. That tagged run used the former
  combined native wrapper. The focused hosted repeat of the pytest split passed
  in `v0.5.0rc193` (GitHub Actions run `38308617935`): its rule selector ran
  the via-antipad and narrow-void native fault/control cases on the pinned
  KiCad 10.0.0 and 10.0.5 images. The run also passed the scoped package checks
  and installed-wheel external-project inventory, surface, verification, and
  playtest stages; the three portable preview jobs passed. The focused local
  non-native PCB lint slice passed 216 tests. The local 10.0.6 compatibility
  run remains supplementary and is not used as a substitute for the pinned
  versions.

#### LINT-059 — I2C pull-up rail-family review

- **Status:** Implemented as `bus.i2c_multiple_pullup_rail_families`, with
  synthetic fault/control cases, order-stability coverage, project review,
  block, off, and exact-ignore decisions, and the shared CLI/MCP lint report.
- **Cohort input:** The current public kicad-happy changelog describes I2C
  checks and extracted bus summaries that include voltage and pull-up values.
  This suggests that voltage domain belongs alongside resistor topology in
  review evidence; no cohort implementation, package, source fixture, or
  installation workflow was adopted.
- **Engineering basis:** NXP's
  [UM10204 I2C specification, revision 7.0](https://cache.nxp.com/docs/en/user-guide/UM10204.pdf)
  relates device input levels to the VDD supply used by the pull-up resistors. The local check
  therefore asks for review when the visible pull-up paths name more than one recognized rail
  family; it does not decide which voltage is valid.
- **Predicate:** For SDA/SCL nets assigned to distinct nets on one fitted
  component with recognized pin-function names, collect fitted conventional
  direct or unbranched series resistor paths in the existing 1 kΩ–100 kΩ
  recognition window. When any paths across either line use more than one
  normalized positive-rail family, emit one source-bound candidate with each
  line, resistor path, rail net, and family.
- **Boundary:** Rail families come from the bounded power name/function map.
  A difference is only a naming clue; it does not prove incompatible voltages,
  unsafe input limits, or an error. Equal-family net aliases are not treated as
  distinct families. Custom names without a recognized power-pin function,
  internal or remote pull-ups, arrays, active pull-up circuits, level-shifter
  behavior, power sequencing, resistor tolerance, and bus timing are outside
  this candidate. The resistance interval is a detection window, not a design
  requirement. An authored I2C pull-up/voltage contract remains the stronger
  comparison when a project records exact endpoint limits.
- **Fixtures:** One line with pull-ups to two family names; SDA and SCL split
  across different family names; same-rail and same-family alias controls;
  an unrecognized custom rail control; DNP pull-up and DNP bus-device
  controls; block/off/ignore policy; reordered netlist inputs with identical
  fingerprint and evidence.
- **Done:** The rule is cataloged, deterministic, source-bound, synthetic
  tested, and defaults to review. It adds a missing rail-family prompt beside
  existing resistance checks without asserting voltage compatibility or
  merging rails. No proprietary project source or fixture is used.

#### LINT-060 — Mapped external-protection entry and return-via screen

- **Status:** Implemented as `pcb.protection_entry_path`, with synthetic
  fault/control and inventory-order tests plus shared CLI/MCP report parity.
  Its separate native fixture passes on digest-pinned KiCad 10.0.0 and 10.0.5
  images, with repeated source-bound control snapshots, exact 650 um and
  connected-via controls, a disconnected signal fault, and a nearby but
  disconnected reference-via fault. LINT-031 records a read-only runtime
  comparison against kicad-happy's ES-001/ES-002 heuristics; the candidate adds
  no unique detection and misses the disconnected-via fault.
- **Cohort input:** kicad-happy's EMC rules document `ES-001` for distance
  between connector and protector, and `ES-002` for ground vias near the
  protector. Its inspected implementation measures footprint-origin distance
  and classifies ground from net names. Those are useful review hypotheses but
  too coarse to establish pad placement, a project-required reference domain,
  or copper-component continuity.
- **Predicate:** A project-authored `pcb_protection_path_map` names exact
  connector and protector signal/reference pads, expected footprints and nets,
  an optional maximum signal-pad center distance, and/or an optional minimum
  count of native-connected reference vias within a project-selected radius.
  The checker verifies fitted pad inventory, native nets, and shared copper
  connectivity between the connector and protector signal pads. It counts
  vias only from the mapped protector reference pad's native copper component.
- **Boundary:** No net-name ground guessing, connector/device discovery,
  universal ESD placement threshold, or universal via count is applied. The
  straight-line distance is not routed path length, route order, parasitic
  inductance, or transient response. A matching net and nearby via do not prove
  clamp suitability or protection effectiveness. Existing schematic
  `external_protection_map` remains the place for authored connector pin and
  device pin-net requirements; this PCB map independently binds exact board
  pads and geometry. Tests use generic synthetic data only.
- **Fixtures:**
  `kicad_tooling/hwrepo/fixtures/pcb-protection-entry-path.kicad_pcb` exercises
  the pinned native probe. Exact distance and via-radius boundaries; too-distant pad;
  below-minimum via count; nearby but non-connected via fault/control repeated
  through pinned native KiCad 10.0.0/10.0.5; wrong net, footprint,
  DNP state, or copper component; legacy snapshot without connected-via
  inventory; pad/via input permutation; CLI/MCP semantic parity through the
  common typed service; malformed pad ownership and incomplete via limits.
- **Done so far:** Typed map/report, exact integer geometry, source-bound board
  and native snapshot receipts, review/block/off controls, CLI rendering,
  catalog, docs, synthetic controls, and pinned KiCad 10.0.0/10.0.5 native
  fault/control coverage are implemented. The bounded candidate runtime trial
  is complete; remaining maturity work is reviewer-effort measurement and
  evaluation on approved non-proprietary board examples. The implementation
  borrows the test hypothesis, not candidate code or install workflow.

#### LINT-061 — Mapped digital-peer voltage compatibility

- **Status:** Implemented v1 as the project-authored
  `digital_peer_voltages` electrical contract. It checks mapped direct output
  to input paths outside the existing UART and I2C contracts. Missing limits
  report `NOT_CONFIGURED`; stale identity or pin/net mapping prevents the
  voltage comparison. The typed analyzer is shared by CLI and MCP. The
  tooling-owned native SPI fixture repeats through digest-pinned KiCad 10.0.0
  and 10.0.5 exports.
- **Cohort input:** kicad-happy documents `VM-001` for cross-domain voltage
  review. The inspected source estimates rail voltage from names, selects from
  a fixed 1.8 V, 2.5 V, 3.3 V, and 5 V table, and compares devices on a shared
  signal net. A pinned synthetic runtime trial under LINT-031 finds four
  cross-rail SPI nets and stays quiet on a same-rail control. The error severity
  and level-shifter recommendation overstate what inferred rail names prove;
  see the [fixture record](../tests/fixtures/design_lint/cohort-peer-voltage/README.md).
  This supports only a possible review-coverage prompt, not a compatibility
  requirement.
- **Need:** A schematic may connect an output and input on one net while the
  driver guarantee is below the receiver's high threshold or above its
  absolute-maximum input. ERC does not establish the device operating limits.
  LINT-057 covers direct serial peers; I2C requirements cover mapped pull-up
  voltage versus receiver limits. The remaining candidate scope is other
  project-mapped direct digital endpoints, such as SPI or control signals.
- **Predicate:** A project-authored map identifies exact source and receiver
  component symbols, pins, directed net, output `VOL`/`VOH` guarantees,
  receiver `VIL`/`VIH` thresholds, and absolute input limits. Every electrical
  value includes units, operating conditions, and a document/page basis. The
  source-bound netlist must show the mapped endpoints on the same net. Check
  output-low maximum against receiver `VIL`, output-high minimum against
  receiver `VIH`, and the full guaranteed output range against receiver
  absolute limits. Check reverse direction only when separately mapped.
- **Boundary:** Do not infer rail voltage, logic family, or safe tolerance from
  net names, part numbers, library descriptions, or generic voltage tables.
  Direct links only in v1; level shifters, open-drain buses, analog signals,
  off-board peer limits, power sequencing, loading, transients, and timing need
  their own models. A pending required section or a mapped link missing limits
  is `NOT_CONFIGURED`; an omitted optional section in a legacy sidecar makes
  no compatibility claim and is not evidence of safety.
- **Fixtures:** Tooling-owned synthetic SPI output/input fault and compatible
  control; low/high threshold and absolute-limit violations; wrong native net,
  stale symbol, DNP endpoint, and missing limits; CLI/MCP pass/fail parity.
  These demonstrate a distinct voltage-compatibility check beyond the current
  SPI membership baseline. The exact native lane maps `U1.2` to `U2.2` on
  `SPI_MOSI`; with identical repeated typed netlists, the authored 3.3 V
  control passes at 0.3 V margin and the 5.0 V maximum fault fails at −1.4 V
  margin on both pinned versions.
- **Done so far:** Typed source-bound map, reusable LINT-057 margin
  calculation, exact symbol/footprint/pin/net comparisons, pending setup,
  retained-evidence replay integration, user documentation, and synthetic
  unit and CLI/MCP parity tests. No voltage is inferred from names or cohort
  code is imported.
- **Remaining:** Measure reviewer effort and false-positive rate on approved
  non-proprietary examples; keep future peer categories separate from
  open-drain, analog, level-shifted, and external paths.

#### LINT-066 — Unmapped digital peers across voltage-named rails

- **Status:** Implemented as `bus.spi_peer_voltage_review` and
  `bus.serial_peer_voltage_review`, both defaulting to `review`. SPI retains
  its digest-pinned KiCad 10.0.0/10.0.5 native results. UART/USART now has
  source-hashed same-rail control and cross-rail candidate schematics in the
  same repeated-export acceptance lane. Local KiCad 10.0.6 exports preserved
  their pin functions, directions, inventory, and rail assignments twice; the
  control stayed quiet and the candidate emitted one serial review. The
  digest-pinned KiCad 10.0.0 and 10.0.5 lane passed on 2026-10-01; both
  versions produced matching normalized typed-netlist digests for the control
  and candidate, with the expected PASS and REVIEW results.
  Receipts and normalized digests are recorded in the
  [SPI fixture notes](../tests/fixtures/design_lint/spi-peer-voltage-native/README.md)
  and [serial fixture notes](../tests/fixtures/design_lint/serial-peer-voltage-native/README.md).
- **Cohort input:** kicad-happy `VM-001` compares shared signal nets between
  ICs whose supply voltages it estimates from rail names. On a synthetic SPI
  fault with U1 on `+5V` and U2 on `+3V3`, it emitted four `error` findings;
  the same-rail control emitted none. Repeated reports were byte-identical
  under two Python hash seeds. Exact source and fixture hashes are recorded in
  the [trial fixture notes](../tests/fixtures/design_lint/cohort-peer-voltage/README.md).
  The UART/USART extension applies that candidate idea to exact native TX/RX
  pin functions; the upstream runtime trial did not separately benchmark UART,
  so this extension is independently synthetic-validated.
- **Predicate:** From source-bound native pin assignments, identify shared
  exact SPI clock/data/select function nets or UART/USART TX-to-RX function
  nets between fitted U/IC references. For serial, the TX function must be on
  a native output-capable pin and the RX function on an input-capable pin;
  endpoint channel indexes need not match. Emit a candidate only for a
  directionally clear pair, with complete native pin-type inventories and
  exactly one assigned positive `power_in` net per endpoint. Parse one
  explicit positive voltage token from each supply net label and prompt only
  when the nominal label values differ. Suppress only the exact native
  pin/net/symbol/footprint link when LINT-061 has both reviewed output and
  input limits. Partial or stale maps do not suppress uncovered peers. The
  predicate groups shared signals for each directed component pair into one
  finding.
- **Boundary:** Rail names provide a review clue only. This does not establish
  actual supply voltage, source validity, output guarantees, logic thresholds,
  absolute maximum, receiver tolerance, open-drain behavior, analog
  compatibility, sequencing, or the need for translation. It cannot assess
  off-board circuitry, loading, timing, transients, or PCB paths. Open-drain
  electrical types, analog functions, input/input and output/output pairs,
  ambiguous bidirectional pairs, missing native types, unconnected supplies,
  multiple supply nets, and DNP endpoints are skipped. UART prompts also
  require native TX and RX roles to agree with output/input pin types. Complete
  exact voltage maps are handled by LINT-061; each review rule can be disabled,
  ignored by exact fingerprint, or explicitly escalated by project policy, but
  both default to review.
- **Synthetic regressions:** The +5 V/+3.3 V SPI pair emits one finding with
  exact shared pin evidence; its same-voltage control stays quiet. UART/USART
  adds a same-voltage control and a cross-voltage TX-to-RX candidate with
  controls for DNP, absent pin-type inventory, unconnected and multiple
  supplies, mismatched TX/RX roles, wrong native direction, open-collector
  pins, unsupported or ambiguous rail labels, and a level-translated UART path
  with separate endpoint-to-translator nets. This last case is typed-netlist
  unit evidence that the direct-peer rule stays quiet; it does not identify a
  translator or validate its circuit. Both analyzers exercise
  partial/missing-limit maps, complete exact maps, and stale identity. Complete
  limits suppress only covered links so the separate source-backed voltage
  comparison owns the result. Reordered nets, functions, pin types, and pin
  inventories preserve fingerprints. Tests verify default REVIEW, policy
  OFF/block, exact ignores, actionable evidence, and CLI/MCP parity. SPI and
  UART native fixtures pass repeated KiCad 10.0.0/10.0.5 exports; UART also has
  repeated local KiCad 10.0.6 evidence. Exact normalized serial digests are in
  the [serial fixture notes](../tests/fixtures/design_lint/serial-peer-voltage-native/README.md).
- A dedicated source-native translator control puts controller and peripheral
  signals on separate nets across the translator's A/B pins and supply domains;
  the direct-peer prompt stays silent. The exact-version lane passed locally on
  2026-10-07 with digest-pinned KiCad 10.0.0 and 10.0.5. Both versions retained
  the same normalized typed-netlist SHA-256
  `a289c5c15f048b1d8e1cf58f18501b850c3e1b7e3be451a9d9ba275cbd057e28`,
  repeated exports matched within each version, and the rule stayed quiet.
  Source SHA-256 is
  `58f2ac474e5c055fc5ff3f5e2f9be0613fc7339298244de035740ca85eaa80a1`.
  This tests the direct-net predicate boundary, not translator recognition or
  circuit correctness.
- **Public-template applicability screen (2026-10-03):** The clean public
  KiCad-Team-Workflow-Template checkout at commit
  `ed89536f0dbbcb013145af2994fef41b2250143e` has three retained examples with
  source and netlist hashes matching their reports and passing source-scope,
  toolchain, ERC, DRC, netlist, and source-unchanged checks. Each aggregate
  summary is `FAIL` because its design-lint gate returns `REVIEW` for
  undeclared connector inventory. The examples are:
  Arduino status LED (`c2d8442412cb251472a08df31109b8633655aaa375598abbb2e7bbc00961fa1b`,
  `b58861bdb1d65c6b363f8cc7aacb682aea49ca3e21027195f8e0d2755abf57c5`),
  controller (`bd3f349233ffc44f030b1004a1c08e51d1ec0589ecf646384f1ed3353806e5ad`,
  `6b071d54ed8a18b8965624e37d6a8fda02d3311fa3013ca1f7b6a4e798e6a7c8`),
  and Raspberry Pi status LED (`b99ad47237f3f36aaefa3a2ed08e3dae12d9131c7f9a52355401c9d5bada3fba`,
  `a1ace15ab2aeaa5270bb2e880423c33c562893a2b88d2ea253374d4dd2ea048e`).
  Current native-netlist parsing found no supported SPI or UART/USART pin
  functions in any of the three, and the current rule emitted zero candidates.
  This is 0/3 applicable examples; precision, false-positive rate, and reviewer
  effort remain unmeasured. The passive-signal-reference receipt was excluded
  because its netlist check failed: its component test contract is incomplete.
  No source was copied into Tooling; only
  ignored acceptance receipts were read. Next, select a source-matched public
  design with supported digital-peer functions before claiming public-board
  LINT-066 measurement.
- **Pinned KiCad-demo follow-up (2026-10-03):** The four native netlists from
  `test_native_public_demos_record_connected_bias_and_unconnected_controls`
  in `tests/test_ci_hosted_control_inputs.py` was also screened with the LINT-066 predicate:
  CM5 Minima, Jetson AGX Thor, ColdFire/Xilinx, and VME-WREN all produced zero
  candidates. These bundled samples had no recognized same-net SPI or
  directionally clear UART/USART peers on different explicit voltage-named
  rails. This is 0/4 applicable samples, not a precision result. The netlists
  came from the exact KiCad 10.0.5 image and remain in ignored `build/ci/`
  receipts; no demo source was copied into Tooling.
- **Bundled root-project applicability screen (2026-10-03):** The pinned KiCad
  10.0.5 image is:

  ```text
  ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c
  ```

  It contains 36 KiCad project manifests; 35 have a matching top-level
  schematic and were exported twice with networking disabled. All 35 exports
  produced nonempty inventories accepted by `read_netlist`, with 4,263
  component records total. All repeated exports had identical normalized
  typed-netlist evidence. Fourteen raw XML pairs differed while their normalized typed
  inventories matched, so raw XML equality is not used as the repeatability
  result. Across the 35 designs, 26 recognized SPI/UART pin functions yielded
  18 endpoints with supported native types and unique net assignments in
  seven projects. One directionally clear shared SPI peer link was present,
  in Jetson AGX Thor: `U30.39 ~{SPI_CS}` to `U29.1 ~{CS}` on
  `USB Debug, PD/~{PDC_CS}`. Neither endpoint had qualifying unique
  voltage-named supply evidence; LINT-066 emitted zero candidates. The one
  manifest without a matching root schematic (`microwave`) was excluded. This
  is corpus applicability evidence,
  not a precision, recall, false-positive, or reviewer-effort measurement.
  Source-map SHA-256 is
  `307dec53ad7688ff10c44f60474d287937f8ffbe2f42ca4152f859b70c4dddbf`; the
  all-schematic source/hash inventory SHA-256 is
  `8928014281869d38c62db9a8f4e0435c84a07a2b80011e9d06169a5c1eb484fd`.
  Reports and native exports remain under ignored
  `build/ci/public-demo-lint-screen/`; bundled sources were never copied into
  Tooling.
- **Applicability-coverage follow-up (2026-10-07):** The design-lint report now
  distinguishes `NO_SUPPORTED_ENDPOINTS`, `NO_DIRECT_PEERS`, `INCOMPLETE`, and
  `EVALUATED` for each SPI and UART/USART peer-voltage rule. It records
  recognized/assigned endpoint counts, direct links, comparable voltage-label
  pairs, same/different label values, exact-map-suppressed mismatches, review
  groups, and source hashes. Synthetic fault, same-label, missing-pin-type,
  unsupported-function, connector-only external SPI/UART header, and CLI/MCP
  parity cases exercise the fields. Connector-only endpoints remain
  `NO_SUPPORTED_ENDPOINTS`; the heuristic does not treat off-board interfaces
  as direct on-board IC peers. These bounded counts improve applicability
  evidence; they do not estimate field precision or establish complete
  interface discovery.
- **Public coverage replay (2026-10-07):** Replayed the core scanner against
  three previously pinned public netlists without copying source or exports
  into Tooling. This was a bounded applicability scan, not the integrated
  source-bound project report, and no project peer map was supplied. The
  Calcumaker MCU (`113a2837bd155566d753635fb2cec1cb0458fa9f`) returned
  `NO_DIRECT_PEERS` for SPI with one recognized/assigned endpoint and
  `NO_SUPPORTED_ENDPOINTS` for serial. The Calcumaker keyboard at the same
  revision returned `NO_SUPPORTED_ENDPOINTS` for both rules. The Antmicro CM4
  Baseboard (`d248c2921e8e7f4c9b30c96ea5f376d9b2780f1e`) returned
  `NO_DIRECT_PEERS` for both rules, with two recognized/assigned endpoints per
  rule. Each sample produced zero voltage comparisons and zero LINT-066
  candidates. Antmicro's separately recorded label-paired UART paths remain
  in LINT-082's scope; this replay does not assess those paths or establish
  that the designs lack UART interfaces. The results validate the distinction
  between `NO_SUPPORTED_ENDPOINTS` and `NO_DIRECT_PEERS` for these samples;
  they do not measure precision, false positives, missed faults, or reviewer
  effort.

  Root-schematic SHA-256 values are recorded in the Calcumaker and Antmicro
  sample records above. The replayed native-netlist hashes were
  `9ba5a2009d518267e450dd9e89c0edd494c282e3942da9560faf88220992ad02` for the
  MCU, `3f69a81eebcf5023d38d218146edfb8912817ec77d68db737cdce76040ca3a3f` for
  the keyboard, and `31f1125c5b04efc4f70d7c697fea415f717c7c9e232a54110e89865d9c7d9cdf`
  for both byte-identical Antmicro repeat exports. The replay used Python
  3.11.16 and the installed checkout's `read_netlist` and
  `scan_digital_peer_voltage_reviews`. The runtime source hashes were:
  `digital_peer_voltage_review.py`
  `5745259a11bb90d6fbf9b912a090728de1c5fdf072d9030e245f77629e230366`,
  `design_lint.py`
  `944f499cc3a480b88900d45c85397b85a7ed5a88cecd33751fec548910427cf9`,
  `validate.py`
  `f0f0e6fdac75343ae5e2ed16f8fab0a793cc19a537e13c533b6a47c36fe1360c`,
  `models.py` `a48056b881678d629075351c13f9fae246d507209a33cc3638962089d51518f6`,
  `return_nets.py`
  `10a38392b04b50252b69dd1043e4400766c3aee52ef32980238ed2d6233c6055`, and
  `serial_participants.py`
  `0deb569b4ca71ed6f1dfa4be6b7a125931d027582f7cdb1d508dcf00e4797575`. The
  temporary replay test hash was
  `53b30d90c6bf31e8dd686b299d0319d2c87a86e7566e34a1b0bd32f943abc01f`. Its
  command was `.venv/bin/python -I -m unittest discover -s
  /private/tmp/calcumaker-lint-results-113a2837 -p
  test_peer_voltage_coverage.py -v`; the one test and all three sample
  subtests passed. The replay script and all public source/export files remain
  under `/private/tmp`.
- **Selectable external-I/O boundary replay (2026-10-07):** The public
  [Antmicro Debug Toolkit](https://github.com/antmicro/ftdi-toolkit), licensed
  Apache-2.0, documents UART and SPI buses exposed on a 2.54 mm header with
  selectable 5.0 V, 3.3 V, and 1.8 V I/O. Its KiCad 7 schematic was exported
  twice as a compatibility probe with image `ghcr.io/kicad/kicad:10.0.5`
  and digest
  `fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`.
  The Docker image ran as `linux/amd64` emulation on the local `arm64` host.
  This did not run ERC or DRC and does not qualify the source under KiCad 7.
  At upstream commit `6e39ebff19d7230bfa5b8266008d1ca5334f2021`, the root
  schematic SHA-256 is
  `f3e50b1a6f2b599db88fc6581db1cf126b8dcce3f3ce49cdcf8ad81a4e2c5407`.
  The repeated raw XML hashes are
  `6af05f440fc0c334602fee69b50a66d0f290e025273b908cb4a1fe0bd21f4c1f` and
  `2c945a18ae5582599f6832b6da702a4a7e6554483f0ac94f70a84ad7e023f5bb`; the
  normalized typed-netlist hash matched at
  `9f2882fd20da6a2f3582b0061fe421e1e08b81e7c497d22074b9fe895178c672`.
  The export contains 130 components, 77 nets, 270 pin functions, and 471 pin
  electrical types. LINT-066 recognized no supported on-board SPI or
  UART/USART endpoints and made no voltage comparisons or review candidates.
  This is an expected boundary result for externally exposed buses: the
  off-board peer and selected I/O voltage are not established by direct
  on-board IC-to-IC connectivity. It is not a precision, recall, or reviewer-
  effort result. No project source or export was copied into Tooling; the
  source and exports remain under `/private/tmp`. The replay used Python
  3.11.16 and `scan_digital_peer_voltage_reviews`; scanner, parser, and model
  hashes were respectively
  `5745259a11bb90d6fbf9b912a090728de1c5fdf072d9030e245f77629e230366`,
  `f0f0e6fdac75343ae5e2ed16f8fab0a793cc19a537e13c533b6a47c36fe1360c`, and
  `b67704ea6476c68266985646570c47081b3ce44d1f9bd63e30f5af817a3068a4`.
- **Remaining:** Measure reviewer effort and false positives on approved
  non-proprietary examples. Do not promote beyond the default review mode from
  synthetic or native-export evidence alone; no proprietary schematic or board
  is needed for this follow-up.

#### LINT-067 — CAN peer pairs disagree on one shared line

- **Status:** Implemented as `bus.can_peer_assignment_divergence`, default
  `review`, with synthetic same-bus, split-peer, separate-bus, DNP, policy,
  order-stability, and repair controls. Tooling-owned native fault/control
  schematics export and run ERC twice on the exact pinned KiCad 10.0.0 and
  10.0.5 images; neither fixture has ERC errors, while the asymmetric
  assignment reports the exact shared side and complementary net assignments.
  ERC also reports the recorded symbol/footprint library warnings from the
  isolated synthetic library setup.
- The fault and control source records, native hashes, and expected ERC
  warnings are listed in the
  [CAN peer fixture README](../tests/fixtures/design_lint/can-peer-native/README.md).
- **Cohort input:** kicad-happy's public v2.2.1 release notes document
  deterministic CAN protocol checks and a hash-order stability audit. Its
  v2.2.1 runtime trial under LINT-031 did not expose PR-003 in the JSON report
  and emitted the same empty-net missing-termination message for the valid
  control and split-peer fault. No incremental CAN detection was demonstrated.
  This first-party rule uses exact native `CANH`/`CAN_HIGH` and
  `CANL`/`CAN_LOW` pin-function roles to surface a cross-peer assignment
  asymmetry; no candidate code, threshold, or runtime dependency is adopted.
- **Predicate:** For each fitted source component with exactly one recognized
  CANH and one CANL pin function, require each pin to have exactly one native
  net and require the two nets to differ. If two or more complete pairs share
  one exact native net on one side but use multiple exact native nets on the
  complementary side, emit one grouped `REVIEW` finding with each peer's
  exact pin and net assignment.
- **Boundary:** A shared net on one side does not prove the parts belong to one
  bus or that both sides must be common. DNP, incomplete, multi-pin-per-role,
  ambiguous, and same-net pairs are skipped. The prompt cannot establish CAN
  topology, required termination, transceiver behavior, off-board wiring, PCB
  copper continuity, or physical connectivity. Project-owned maps remain the
  stronger expression of intent.
- **Synthetic regressions:** Three peers on one complete pair stay quiet;
  a third peer sharing only one side prompts; two separately connected buses
  remain quiet; DNP exclusion, order stability, fixing the split, default
  `REVIEW`, `block`, `off`, and exact-fingerprint ignore are covered. The
  native pair preserves complete CAN pin inventories, exact assignments,
  direct termination on both candidate pairs, repeatable netlist evidence,
  and zero ERC errors for fault and control on both pinned versions. Expected
  isolated-library warnings are recorded in the native fixture README. The
  CLI and MCP return the same source-bound finding from a synthetic native
  netlist.
- **Rule-scoped gate registration (2026-10-12):** The native fault/control
  test ran under the broad interface-area gate, but its active rule did not
  catalog that test, so a `Lint-Rule: bus.can_peer_assignment_divergence` tag
  could not select it. The catalog now links the test as both fault and valid
  control, requires `KICAD_RUN_NATIVE_CAN_PEER_FIXTURES`, and the architecture
  suite guards the association. The rule-scoped hosted run `38296123722` for
  `v0.5.0rc185` passed the focused lint and installed-wheel steps plus all three
  portability previews; the package job was skipped by RC policy.
- **Remaining:** This is a review-localization gain, not proof the asymmetric
  peer is defective. Reviewer effort and false-positive frequency on approved
  non-proprietary projects remain unmeasured.

#### LINT-062 — Mapped power-sequence dependency coverage

- **Status:** Project-mapped endpoint and dependency checks are implemented as
  `power.mapped_sequence_dependency_mismatch`, with synthetic native-XML
  parsing, installed CLI/MCP parity, and repeated pinned-native KiCad 10.0.0 and
  10.0.5 export coverage. The same rule reports a `REVIEW` when exact mapped
  output/enable endpoints form a closed topology cycle even if the project's
  declared dependency graph is acyclic. Project adoption remains an owner
  decision. Numeric timing checks are deferred until an approved source
  requirement supplies exact limits and operating conditions.
- **Cohort input:** kicad-happy documents `PS-001` as a power-sequencing
  dependency-graph check based on regulator output and enable-pin connections.
  The pinned [detector implementation][kicad-happy-sequence-detector]
  recognizes common enable names and selected device families, forms inferred
  enable-to-output edges, and reports cycles in that inferred graph. A focused
  synthetic runtime trial found the same two-stage cycle twice, once from each
  start node; its acyclic control was quiet. Trial inputs, source hashes, and
  limits are recorded under LINT-031. The local implementation adopts only the
  cycle idea when project-authored stage maps identify exact native output and
  enable pins. Names and family classifications alone do not establish that a
  rail must precede another.

[kicad-happy-sequence-detector]: https://github.com/aklofas/kicad-happy/blob/3cf837b2d6577d1369a45a36d5e9bac0e06ff5b6/skills/kicad/scripts/validation_detectors.py

- **Need:** Some devices require a rail order, a power-good dependency, or a
  bounded delay. A connected schematic net and an ERC pass do not prove the
  required startup sequence.
- **Implemented contract:** An opt-in project-authored `power_sequence_map`
  names exact stage output, power-good, and enable pins; symbol, footprint,
  optional PART_ID, expected nets, enable-control context, required dependency
  edges, and source basis. The native netlist comparison reports changed pin
  assignments, absent/DNP/mismatched components, missing pin inventory, and
  cycles in the declared graph. It also identifies cycles where one exactly
  matched mapped output net drives another mapped stage's enable pin, even when
  that output-to-enable edge is omitted from the dependency list. Only stages
  whose full endpoint inventory matches are used for that inference; no role is
  inferred from pin names or part families. The finding has the standard
  review/block/off and exact-ignore lifecycle.
- **Native evidence:** The synthetic control, open-enable fault, and
  three-stage output-enable-cycle fault are exported twice through
  digest-pinned KiCad 10.0.0 and 10.0.5. Both versions preserve identical
  canonical netlists per fixture; the control passes, the open-enable fault
  produces one localized U2.1 REVIEW, and the cycle fault produces one
  `rail-a`/`rail-b` REVIEW while its declared dependency graph remains acyclic.
  Exact source hashes and canonical netlist hashes are retained in the
  [native fixture record](../tests/fixtures/design_lint/power-sequence-native/README.md).
- **Remaining:** A missing map or omitted stage remains a coverage question;
  the cycle prompt needs exact mapped endpoint records and cannot discover the
  relevant regulator set. Evaluate a separate numeric timing contract only
  when an approved source schema explicitly supplies exact thresholds, units,
  tolerances, operating conditions, and boundary controls.
- **Boundary:** Never decide that a project needs sequencing from a processor
  keyword or `EN`/`PG` pin name alone. A schematic cannot prove ramp timing,
  startup under load, firmware states, supervisor thresholds, brownout
  behavior, or physical rail behavior. Missing maps remain coverage gaps; they
  do not make every board a failure.
- **Fixtures:** Synthetic exact endpoint/dependency control through normalized
  raw netlist XML, installed CLI, and MCP; open enable, mapped output-to-enable
  cycle with an acyclic declared dependency graph and an acyclic valid control,
  changed rail net, symbol/PART_ID mismatch, missing native pin, and DNP faults;
  firmware-declared control; omitted-map no-inference control; explicit graph
  cycle; stable ordering and fix-clears-finding metamorphism. Do not assert
  silicon startup or hardware behavior from these fixtures.
- **Done for v1:** The topology contract has CLI/MCP parity, repeated native
  KiCad 10.0.0/10.0.5 export evidence, and documented project adoption limits.
  A numeric timing extension remains a separate follow-up with its own approved
  source schema and synthetic boundaries; it must not be inferred from device
  names or cohort defaults.
- **Tagged hosted acceptance:** The scoped `v0.5.0rc71` gate passed on
  2026-10-11 (GitHub Actions run `38133015752`) with
  `KICAD_RUN_NATIVE_POWER_SEQUENCE_FIXTURES=1`. Hosted native fixtures passed
  under the pinned KiCad 10.0.0 and 10.0.5 images.
- **Pytest gate revalidation (2026-10-11):** `v0.5.0rc124` (commit
  `c12c004`, GitHub Actions run `38205612152`) passed its scoped
  `power_lint` gate with the native fixture switch enabled. The split native
  suite ran separate parameterized checks for KiCad 10.0.0 and 10.0.5; mocked
  lane orchestration remains a separately selectable synthetic test.

#### LINT-063 — Output-driven LED series-path review

- **Status:** Implemented as `component.led_directly_driven_from_output`, a
  configurable default-review heuristic.
- **Cohort input:** LINT-048 records kicad-happy's LR-001 visible-series-limiter
  question and its direct-rail trial. A separate read-only run of the pinned
  kicad-happy deterministic analyzer classified the direct-output fault as
  `LA-AUD` `ic_direct` and the series-return control as `resistor_limited`, but
  also classified the output-parallel-resistor fault as `resistor_limited`.
  Its one-hop resistor scan does not distinguish that parallel resistor from a
  series path. This is useful corroboration for the simple direct-drive case,
  but it misses the parallel-resistor fault that the local predicate retains.
  The cohort report is also coarser: it names the IC driver but does not bind
  the finding to native output-pin type or pin/net evidence. Exact source hashes
  and repeated report digests are recorded in the synthetic fixture notes. A
  separate public-template screen found that the cohort's `LR-001` emits an
  error on a GPIO-side series resistor in both status-LED examples even while
  `LA-AUD` identifies that same 1 kΩ resistor. This is a reproducible false
  positive outside the local predicate's applicable LED identity map; retain
  the local fault/control behavior and do not adopt the generic candidate rule.
  The source hashes and report digests are recorded under LINT-031.
- **Predicate:** For a fitted exact `Device:LED`, or a custom identity matched
  by the LINT-069 project role map, with two inventoried pins and unique,
  distinct native net assignments, report when one LED terminal net is
  shared with a fitted native `output`, `bidirectional`, `tri_state`,
  `open_collector`, or `open_emitter` pin and the other LED terminal is directly
  assigned to a recognized supply or return net. A visible fitted positive-
  value resistor between an intermediate return-like LED net and a distinct
  recognized return net suppresses the candidate. The resistor check uses the
  shared deterministic two-terminal resistor inventory and does not certify
  value adequacy. An exact project-authored `power_path_map` can suppress this
  prompt only when a `Device:LED` A-to-K path terminates at a
  `current_controlled_sink` endpoint whose `PART_ID`, native pin function,
  electrical type, symbol, footprint, pin, and net match the source-bound
  netlist.
- **Boundary:** Default is `review`; project policy may block, disable, or
  fingerprint-ignore an exact finding. This does not infer that a resistor is
  required, current limits, polarity, output-drive capability, off-board paths,
  population, copper connectivity, or runtime behavior. Only exact supported
  LED identity, known native output-capable pin types, and recognized rail
  roles participate. Unmapped or stale custom identities, DNP devices, missing
  pin metadata, ambiguous assignments, and unrecognized rails remain outside
  the predicate; stale mapped identities block lint. The current-controlled
  sink role is explicit project metadata; a matching path does not prove
  current regulation or electrical suitability.
- **Fixtures:** Synthetic native-netlist faults cover direct output-to-LED and
  a resistor parallel to that path. Controls cover a series resistor on either
  side, non-output and unknown pin types, DNP endpoints, custom symbols, and
  unrecognized rails. CLI/MCP parity uses the same typed service. The eight
  existing tooling-owned schematics are exported twice on digest-pinned KiCad 10.0.0 and
  10.0.5; direct-output, parallel-output-resistor, and mapped custom-symbol
  cases report, while both standard and custom return-side series-resistor
  controls do not. Without the role map, the custom symbol stays outside the
  predicate. The native lane asserts that the parallel-resistor fixture
  actually places its resistor on the same two nets as the LED before
  evaluating the rule. A separate typed-service control now covers an exact
  project-role map for a custom LED with an output-side series resistor, the
  topology used by the public status-LED training examples. The public project
  files remain in their template repository; this regression uses only the
  minimal tooling-owned synthetic netlist.
  Two additional synthetic schematics cover single- and two-channel
  current-controlled sink LED paths. The native lane checks the unmapped
  prompts, then requires each exact mapped driver `PART_ID`/pin signature and
  LED A-to-K path to match before those prompts are suppressed; local native
  execution remains pending the pinned CI lane. A partial map is covered by a
  typed regression and leaves its unlisted LED channel reviewable.
- **Public-template applicability check (2026-10-01):** The clean public
  KiCad-Team-Workflow-Template checkout at
  `ed89536f0dbbcb013145af2994fef41b2250143e` documents its Arduino status LED
  as J1.1 → R1 (1 kΩ) → D1 → J1.2/GND. The KiCad 10.0.5 export and parsed
  native netlist confirm
  `D13_STATUS=(J1.1,R1.1)`, `LED_ANODE=(R1.2,D1.1)`, and
  `GND=(D1.2,J1.2)`. The source schematic SHA-256 is
  `c2d8442412cb251472a08df31109b8633655aaa375598abbb2e7bbc00961fa1b`; the
  native netlist XML SHA-256 is
  `900a175d05b135f37bdd582cc07e83e637b0933b3fe99713e74b0615ff1ad5cf`.
  LINT-063 emitted no finding because D1 uses the exact custom identity
  `StatusLedTraining:LED_5mm`, outside the current `Device:LED` predicate.
  The overall report remained `REVIEW` with zero heuristic findings because
  connector inventory coverage was `UNDECLARED`; this is a non-applicable
  sample, not a clean-pass or false-positive measurement. Only the public
  source and generated receipts in `/private/tmp` were used; no project source
  was copied into this repository.
- **Pinned KiCad-demo applicability screen (2026-10-03):** The same four
  repeated native KiCad 10.0.5 demo netlists used for LINT-017 contain 50
  `LED`-named symbols across CM5 Minima, Jetson AGX Thor, ColdFire/Xilinx, and
  VME-WREN. All 50 use custom library identities rather than `Device:LED`; the
  exports provide no PART_IDs and no reviewed LINT-069 role map was supplied.
  LINT-063 therefore returned zero findings. This tests the custom-identity
  boundary only; it does not estimate precision or validate the LEDs' current
  paths. Native receipts remain under ignored `build/ci/`.
- **Bundled root-project applicability screen (2026-10-03):** The repeated
  KiCad 10.0.5 top-level project screen described under LINT-066 contains one
  instantiated exact `Device:LED`, `Q17ng` `D1`, and no LINT-063 findings. Its
  anode is on `vdd`; its cathode net is shared with `Q2.3` (native `input`)
  and `R2.1` (passive), so the local rule's direct output-capable-pin plus
  opposite-rail predicate does not apply. Source SHA-256 is
  `25f5da785909d7a3fb70588502f0a59e78b3d7520c42d9b1d440455c47141046`; the
  repeated normalized typed-netlist SHA-256 is
  `ccae5ebba5e74da5640401e6c341f4b6e96a8f32c73d11b332f8f7d0923adf8f`.
  This is an out-of-scope topology, not a clean control or precision result.
- **HALPI2 LED re-screen (2026-10-07):** The public KiCad 9.0, CERN-OHL-S v2 source already screened
  under LINT-074 contains eleven exact `Device:LED` instances in the root export. Its repeated KiCad
  10.0.5 typed netlist remains the complete-hierarchy evidence; LINT-063 returned zero findings.
  Four LEDs share a terminal with native output pins, but their opposite terminals are on
  intermediate resistor nets rather than recognized rails. The other exact-symbol LEDs do not
  complete the direct-output/opposite-rail predicate. A repeated standalone-sheet compatibility
  probe on installed KiCad 10.0.6 produced stable typed-netlist digests for `mcu_leds.kicad_sch`
  (`edd52347a980e921a60474a06b0b76898f50eaeb8cb6b51c4160e3371d350f2e`) and `rgb_leds.kicad_sch`
  (`72926234258a08b2780e0f22a4c832ef3678e0151cf098a74e5761f12570ff86`); the first sheet contains
  four exact `Device:LED` symbols and the second uses five custom LED identities. Neither sheet
  emitted a candidate. Because the standalone exports lack parent-sheet context and the repo
  documents KiCad 9.0, treat them only as compatibility probes. This adds no fault/control or
  reviewer-value measurement; do not repeat this source for LINT-063. The sub-sheet source SHA-256
  values are `13e8001418458d5e7cf2d75d47e6780bcccdd0b818f1add787252c96fd760119`
  (`mcu_leds.kicad_sch`) and `7f6d85930e1cc949c84ef71f8f0693d8fd3301ca69369ddc7320043cea0e3501`
  (`rgb_leds.kicad_sch`); the root source hash is recorded with the HALPI2 boundary screen above. No
  project source was copied into Tooling.
- **Applicability extension:** The LINT-069 first slice now permits an exact
  custom LED classification when the project contract binds PART_ID, symbol,
  footprint, complete native pin signature, and review basis. The mapped fault
  and series control pass on both supported native versions. This does not
  establish electrical limits, approve the component, or prove physical
  current limiting.
- **Done:** The rule is catalogued and configurable, deterministic across
  reordered netlist input, source-bound through native exports, and covered by
  fault/control and CLI/MCP parity tests. No proprietary project source or expectation
  was used or stored. The native lane validates the parser and topology prompt,
  not electrical suitability or manufacturing acceptance. The cohort analyzer
  comparison and repeated-report hashes are recorded in the synthetic fixture
  [trial notes](../tests/fixtures/design_lint/cohort-led-resistor/README.md).

#### LINT-064 — Source-bound component voltage-rating margin coverage

- **Status:** Implemented as an opt-in electrical contract and verified against
  the digest-pinned KiCad 10.0.0 and 10.0.5 fixture lanes. No project contract
  currently opts into the check. Synthetic acceptance does not approve a part
  or establish project-level adoption.
- **Cohort input:** The public
  [kicad_skills README](https://github.com/sabas0ba/kicad_skills/blob/53d1af8bc550f60415b4b8e51a6d2d5924ada03f/README.md)
  and its
  [schematic review guide](https://github.com/sabas0ba/kicad_skills/blob/53d1af8bc550f60415b4b8e51a6d2d5924ada03f/docs/guides/kicad-schematic-review.md)
  describe component-rating and voltage-derating review. The guide limits its
  voltage-derating heuristic to rail names that state a voltage. This is
  documentation review only for the rating feature; no rating runtime trial or
  source-level predicate comparison was performed. The pinned repository
  declares Apache-2.0. LINT-031 separately trials only `analog.no_dc_path`.
- **Problem:** ERC and a correct net assignment do not compare an exact fitted
  part's sourced voltage rating with the reviewed maximum stress expected
  across that part. Guessing voltage from a rail name or part description can
  misclassify custom rails, tolerances, transients, and component roles.
- **Deterministic check:** A project-owned requirement identifies
  the exact reference, symbol, footprint, part/catalog identity, native pins or
  endpoint nets, datasheet rating and source basis, a reviewed maximum operating
  stress, its source/calculation basis, and a project-chosen maximum rating
  utilization. The analyzer binds those inputs and the native netlist, verifies
  exact identity and pin/net assignments, then compares the declared stress to
  the declared rating and utilization limit. Missing or stale requirements
  remain coverage gaps. It uses no generic rail-name voltage table or universal
  derating percentage.
- **Boundary:** Project owners remain responsible for the accuracy and
  applicability of the datasheet rating and stress envelope. The analyzer does
  not derive worst-case stress, rail tolerance, ripple, surge, temperature
  derating, lifetime, or component behavior. A review hint cannot prove that a
  part is suitable or promote an unreviewed value to a release decision.
- **Acceptance evidence:** The synthetic parsed-netlist contract control at
  12 V / 16 V = 0.75 passes an 0.8 limit; equality at the limit passes; 13 V /
  16 V fails. Wrong part ID, symbol, footprint, pin inventory, pin/net
  assignment, unconnected pin, DNP state, and missing component fail closed or
  leave utilization not applicable. A CLI/MCP test produces identical
  requirements and findings, and retained evidence replay rejects omitted
  identity, pin, or utilization checks. The native fixture holds its schematic
  and netlist constant while authored stress changes from 15 V / 24 V to 20 V /
  24 V. Exact digest-pinned KiCad 10.0.0 and 10.0.5 runs both reproduced the
  canonical netlist hash
  `62445806a59516cbf1822b34cb4f7a1f020b6be559fa4bef87fba0fb3b91cf3e`. Their
  repeated normalized ERC hashes were respectively
  `8945db6cb5e10cc79180475f596dec5807ca1a246be947c84ad4a3e8c6fbd17b` and
  `b1f928b2543cac139c3067384c152844cae9e49e684e39e666b7d4c18445ab4b`.
  Each report had warnings only and no ERC errors; its signature was unchanged
  between the passing 15 V and failing 20 V authored stress cases. This shows a
  distinct contract-level result beyond the native ERC baseline. Command and
  export receipts are under ignored `build/ci` in the disposable acceptance
  checkout. Exact source hashes, native netlist evidence, and reproducible
  limits are summarized in the
  [synthetic fixture record](../tests/fixtures/design_lint/component-voltage-ratings/README.md).
  The cohort code was not installed or benchmarked, and no real
  project datasheet or design fixture was used.
- **Remaining:** Exercise the opt-in contract on a nonconfidential project with
  owner-reviewed exact-part rating and maximum-stress sources. Keep the check
  inactive where those requirements have not been authored; the tool does not
  derive ratings, worst-case stress, or suitability.

#### LINT-071 — Source-bound component power-rating margin coverage

- **Status:** Implemented as an opt-in electrical contract. Synthetic unit,
  source-bound CLI/MCP, and retained-evidence replay tests pass. Exact-version
  KiCad 10.0.0/10.0.5 native exports now pass twice on both rating fixtures;
  normalized netlist and ERC-type signatures match, with zero ERC errors.
  Controls pass and authored over-limit faults fail on both versions. No project
  requirement opts into the check.
- **Cohort input:** The pinned public kicad_skills README and schematic review
  guide describe rating and derating review, while its PCB guide discusses
  power and thermal review. Those sources do not provide a deterministic
  part-specific dissipation algorithm. This implementation adopts the review
  question only and does not import candidate code, data, threshold, or runtime.
- **Problem:** Native ERC and schematic connectivity do not compare an exact
  fitted component's rated power against a reviewed worst-case dissipation
  envelope after thermal derating.
- **Contract:** `component_power_ratings` binds the exact reference, symbol,
  footprint, `PART_ID`, two native pins and nets, datasheet rated power, a
  project-reviewed derated allowable power, maximum expected dissipation,
  source conditions and calculation bases, and a project-selected utilization
  limit. The checker verifies identity, population, pin inventory, and
  connectivity before comparing expected dissipation with the derated limit.
  A derated limit above the source rating is rejected by schema validation.
- **Boundary:** No dissipation, duty cycle, current, temperature, thermal
  resistance, layout, or derating is inferred by the tooling. Project owners
  remain responsible for sources and corner calculations. V1 covers exact
  two-pin components only; arrays and multi-pin devices need per-element loss
  models. This is not a general part-suitability or release approval.
- **Fixtures:** Exact-part control at 0.10 W / 0.25 W allowable passes a 0.8
  utilization limit; changing only the authored stress to 0.21 W fails at
  0.84. Tests cover inclusive equality, wrong identity, wrong pin inventory,
  wrong or open nets, DNP state, missing part, invalid derating, and source-map
  order. CLI/MCP reports match, and retained evidence replay rejects omitted
  check rows. The synthetic native fixture is source-hashed in
  `tests/fixtures/design_lint/component-voltage-ratings/README.md`; that record
  contains the native results for both voltage and power fixtures.
- **Remaining:** Before any project adopts it, have the electrical owner review
  exact-part rating, operating conditions, derating, and maximum-stress
  sources. No proprietary source or fixture was used.

#### LINT-072 — Likely UART endpoint missing from the serial-peer map

- **Status:** Implemented as `bus.serial_unmapped_peer`, default `REVIEW`, with
  source-hashed contract context, exact ignores, project `review`/`block`/`off`
  overrides, synthetic fault/control and metamorphic tests, native regressions
  on KiCad 10.0.0/10.0.5, and CLI/MCP parity. It extends LINT-014's explicit
  endpoint contract with deterministic discovery coverage; it is not a
  replacement for that contract.
- **Incremental-value hypothesis:** If a fitted component exposes assigned
  TX/RX pin functions, or a fitted U/IC has assigned pins on explicit UART/
  USART-labeled TX/RX nets that also reach a common fitted connector candidate,
  prompt the reviewer when that exact pin pair is absent from `serial_peers`.
  This can surface an interface the native symbol metadata does not name. A
  finding requests review and never declares that the pins should connect or
  that grounds should be joined.
- **Predicate and evidence:** Read the native KiCad 10 normalized netlist's pin
  functions, net names and assignments, fitted/DNP state, and source-hashed
  project serial-peer map. The function path recognizes bounded TX/TXD and
  RX/RXD roles, optionally with a UART/USART prefix and channel number or
  numeric suffix; pins must belong to the same component, have unique
  assignments to distinct nets, and form an unmapped exact pin pair. The
  alternate path recognizes exact UART/USART TX/RX net labels, each with one
  uniquely assigned pin on a fitted U/IC and at least one common fitted
  connector candidate across both nets. It skips MCU pins already classified by
  native serial function. A project map suppresses only its exact TX/RX pin
  pair. Evidence includes discovery basis, channel, exact pins, assigned nets,
  roster state, contract path, and contract digest. Findings use the established
  fingerprint and project-decision lifecycle.
- **Boundary:** Net labels and pin functions are discovery clues, not an
  electrical requirement. The exact label path excludes bare TX/RX names,
  arbitrary aliases, ambiguous or multiple MCU pins, missing connector
  candidates, mismatched channels, and equal TX/RX nets. Unused MCU alternate
  functions and other serial interfaces can still prompt review. It does not
  find missing power/reference assignments or prove board copper continuity,
  component behavior, or off-board wiring. An explicit serial contract remains
  responsible for endpoint perspective, voltage limits, reference policy, and
  direct/shifted path requirements.
- **Fixtures:** Synthetic direct-peer control maps J1/J2; omitted J3 and
  alternate U1 UART channels produce localized review prompts. The separate
  synthetic net-label schematic has MCU package-pin functions `PA2`/`PA3`,
  generic connector pin names, and explicit `UART_TX`/`UART_RX` labels. It
  produces one REVIEW candidate when unmapped; the source-hashed exact-map
  control passes. Negative controls cover absent or DNP connectors, unmatched
  channel labels, ambiguous MCU assignments, bare TX/RX labels, DNP exclusion,
  differential-function exclusion, pending map states, project modes, exact
  ignores, and order stability. The source-bound parity fixture compares CLI
  and MCP reports on the same native XML evidence. Native fixtures export both
  serial scenarios twice under digest-pinned KiCad 10.0.0 and 10.0.5; repeated
  typed netlists and lint reports match within each version. See the
  [native fixture record](../tests/fixtures/design_lint/serial-peer-native/README.md)
  for synthetic source digests and reproduction details.
- **Public applicability sample:** The pinned Calcumaker screen recorded under
  LINT-031 produced one label-based coverage candidate on each of two board
  roots, where native MCU pin functions and generic connector functions did not
  activate the function-only detector. This demonstrates applicability, not a
  confirmed omission, false-positive rate, or review-effort reduction. The
  public sources remained outside Tooling; no project expectation was copied.
- **Cohort input:** The rule reuses the local SPI roster-coverage pattern and
  addresses LINT-014's omitted-peer discovery gap. It does not adopt cohort
  analyzer code or add a runtime dependency.
- **Remaining:** Reviewer effort, false positives, and incremental findings on
  owner-reviewed project maps remain unmeasured. Keep the default at `REVIEW`;
  no private project source or expectation was used.

#### LINT-065 — Connector/capacitor-only net has no visible local DC anchor

- **Status:** Implemented as a default-review heuristic over the native
  KiCad 10 netlist model. The catalog, typed finding, exact ignores, project
  `review`/`block`/`off` overrides, synthetic fault/control tests, and CLI/MCP
  parity are in place. No project data was imported.
- **Cohort input:** The public
  [kicad_skills schematic review guide](https://github.com/sabas0ba/kicad_skills/blob/53d1af8bc550f60415b4b8e51a6d2d5924ada03f/docs/guides/kicad-schematic-review.md)
  documents `analog.no_dc_path`: a net whose pins are all capacitors or
  connectors. Its source and runtime were later pinned and evaluated on
  tooling-owned synthetic fixtures under LINT-031. The candidate duplicates
  the fitted fault but also warns on the DNP-capacitor control because its
  predicate does not inspect population state. No code, examples, or candidate
  installation workflow was copied.
- **Problem:** ERC may have no basis to object when a connector signal and a
  capacitor share a valid assigned net, even if the local schematic shows no
  DC-driving or bias component there. Existing power-input and reset/enable
  checks require recognized native pin roles and do not cover general
  connector-facing signal nets.
- **Predicate:** For each non-return net, require at least one fitted
  connector pin and one fitted pin from a supported capacitor symbol. Every
  other fitted pin assigned to that net must also be one of those two classes.
  Ignore DNP components. Suppress the prompt for unknown symbols, ambiguous
  assignments, return-like pin functions, or any additional fitted component
  pin. Report exact net, pin, and symbol evidence.
- **Boundary:** This pattern does not prove that a DC reference is required
  or missing. A connector may receive its level from an off-board host, a
  component may provide internal bias, and a DC path can exist elsewhere in
  the circuit. Conversely, an additional part pin suppresses the prompt even
  when that part does not establish a DC reference. The rule does not identify
  analog signals, evaluate component values or states, trace DC paths, or
  establish PCB continuity. Use a project-authored contract for any required
  endpoint or bias relationship.
- **Fixtures and value:** Synthetic faults cover a fitted connector and
  capacitor on one non-return net; controls cover DNP connector/capacitor
  cases, a component-only or return net, an additional fitted part pin, and a
  connector designator whose explicit symbol is a resistor. A metamorphic case
  checks stable fingerprints under input reordering and suppression when a
  third component pin is added. A CLI/MCP synthetic native-XML parity case
  compares the finding with a local output-driver control. The native lane now
  also verifies that a DNP capacitor remains in KiCad's exported netlist with
  its DNP state and does not trigger the fitted-part predicate. Tooling-owned
  schematic fault/control fixtures and an opt-in native lane passed with
  pinned KiCad 10.0.0 and 10.0.5; package acceptance CI now runs this lane. All
  three cases have repeatable netlist/ERC evidence and zero ERC errors; the lint
  reports only the fitted fault. This is a demonstrated synthetic detection
  gain over native ERC for this pattern, plus population-state control evidence.
  It does not establish field effectiveness, a false-positive rate, or justify
  blocking policy. Source, normalized evidence, and image receipts are recorded in the
  [native fixture record](../tests/fixtures/design_lint/net-dc-reference/README.md).
- **Remaining:** Measure useful findings and false positives on approved
  nonconfidential projects before considering broader applicability or any
  policy promotion.

#### LINT-068 — Open-output signal input without visible local bias

- **Status:** Implemented as separate `signal.open_collector_input_without_visible_bias`
  and `signal.open_emitter_input_without_visible_bias` rules, both defaulting
  to `REVIEW`, with typed evidence, independent exact ignores and project rule
  overrides, synthetic fault/control tests, and CLI/MCP parity. This adds a
  review prompt for lines outside the narrower I2C, control-input, and active-low
  SPI chip-select checks.
- **Predicate:** From the native netlist, group uniquely assigned fitted pins by
  exact net. A candidate needs one or more `open_collector` outputs with at
  least one `input`/`input_low` peer, or one or more `open_emitter` outputs with
  such a peer. Collector candidates emit the collector rule ID and emitter
  candidates emit the emitter rule ID. A direct or unbranched series path of
  fitted conventional two-terminal resistors to a recognized positive rail
  satisfies the visible open-collector pull-up; the corresponding path to a
  recognized return satisfies the visible open-emitter pull-down. These checks
  do not apply a resistor value window. Nets that are themselves recognized
  rails are excluded.
  Specialized I2C, recognized reset/enable/boot, and active-low SPI chip-select
  functions remain with their more specific rules. Mixed
  open-collector/open-emitter driver types and pins with ambiguous net
  assignments are outside the check.
- **Boundary:** Native pin types do not prove that a local bias is required or
  that the output is used in that mode. Branched or ambiguous resistor paths,
  arrays, jumpers, active circuits, internal or off-board bias, custom rail
  names, resistor adequacy, receiver thresholds, runtime behavior, and PCB
  connectivity are not verified. The result remains a review question; a
  project contract must state any required local topology or operating limits.
- **Fixtures and value:** Tooling-owned netlist tests cover missing expected
  pull-up and pull-down paths, opposite-polarity resistors, DNP outputs,
  specialized-bus exclusions, missing input peers, and input-order stability.
  A synthetic native-XML report fixture asserts both distinct rule identities
  through CLI and MCP. Separate netlist tests exercise independent policy
  overrides and exact ignores. Six tooling-owned native schematic fixtures
  pair an open-collector or open-emitter output with a separate input peer.
  Direct pull-up/pull-down controls pair with otherwise identical DNP-resistor
  faults; two more controls test unbranched series paths to positive and return
  rails. The digest-pinned KiCad 10.0.0/10.0.5 lane exports netlists and ERC
  twice, checks native pin types, net assignments, DNP state, expected lint
  evidence, zero ERC errors, and repeatability. A local run passed on both
  versions; normalized netlist hashes matched across versions and repeated
  exports. The new series controls have normalized netlist hashes
  `733358edc49524e860512a0f4a8ac6afd45b09c4533053218d6a6cf841364fb9` and
  `f7069b305c31262710ea29e895ac470fe79455a5d1b4c31ee2324732164fa880`; both
  report zero ERC errors and no bias finding. Branched and DNP series paths
  remain review candidates in synthetic tests. Source and normalized netlist
  hashes and fixture boundaries are recorded in the
  [native fixture README](../tests/fixtures/design_lint/open-drain-native/README.md).
- **Remaining:** The complete six-case local digest-pinned lane passed on KiCad
  10.0.0 and 10.0.5 on 2026-10-13. Tagged hosted acceptance passed at
  `v0.5.0rc225` (GitHub Actions run 38355497027).
  It included the focused pytest selection and installed-wheel check against a
  separate project checkout. The first attempt at `v0.5.0rc224` exposed a stale
  USB fixture inventory assertion; follow-up commit `be2649d` added the already
  registered `intentional-isolation-boundary` case, and the rerun passed. Source
  hashes and repeated native exports are recorded in the fixture README.
  Measure applicability and false-positive behavior on approved
  nonconfidential projects before considering any policy promotion.

#### LINT-073 — MOSFET operating-state terminal-stress coverage

- **Status:** Implemented as the project-authored `mosfet_stress` electrical
  contract. It binds exact fitted three-pin MOSFET identity and pin functions,
  required operating states, authored terminal-potential intervals, datasheet
  VDS/VGS maxima, and an owner-selected utilization limit. The cohort analyzer
  remains deferred; no cohort code or dependency was added. The exact
  digest-pinned KiCad 10.0.0/10.0.5 acceptance lane passed on 2026-10-02 after
  correcting its state-specific fault assertion. Repeated native exports,
  exact identity and pin maps, equality controls, and over-limit VDS/VGS faults
  pass on both versions with zero native ERC errors; normalized netlist and
  ERC-type evidence repeats within each version. This validates the synthetic
  source and calculation path, not a real device's suitability.
- **Cohort input and installation:** The upstream
  [README](https://github.com/rjwalters/kicad-tools/blob/main/README.md) documents the base
  `pip install kicad-tools` flow, but not the `component-stress` command. Its
  [project metadata](https://github.com/rjwalters/kicad-tools/blob/main/pyproject.toml) declares
  version 0.21.1, MIT, and Python 3.10+. The installed package's `kct analyze --help` exposes
  `component-stress`; the published
  [CLI reference](https://github.com/rjwalters/kicad-tools/blob/main/docs/reference/cli.md) omits
  it. The base install succeeded with pip in a disposable environment; the trial recorded 18
  installed packages and needed no optional native C++ backend. The installed `kicad_tools`
  Python-source tree digest is recorded in the fixture README and local ignored receipts.
- **Contract and calculation:** Each project requirement lists the exact
  fitted MOSFET, symbol/footprint/`PART_ID`, one native pin number and exact
  D/G/S function for each terminal, expected nets, sourced VDS/VGS limits,
  required operating states, and minimum/maximum potential for each terminal
  net in every state. For intervals D=[Dmin,Dmax] and S=[Smin,Smax], the
  checker computes `max(abs(Dmin-Smax), abs(Dmax-Smin))`; it applies the same
  rule for G-S.
  Compare those bounds with the sourced ratings and project-selected
  utilization limits. Native symbol/pin-function and netlist evidence must
  match every authored role and assignment. Missing identity, pin mapping,
  state, or potential coverage is visible as a failing check; only a stress
  metric that needs a missing terminal interval is left not applicable. A
  VGS result may still be calculated when the drain potential is missing, for
  example. Independent net intervals may be conservative when extrema are
  correlated; they do not imply a reachable waveform.
- **Boundary and policy:** The analyzer does not infer operating states,
  terminal roles from reference/value strings, net voltage from names,
  switching waveforms, gate-drive timing, safe operating area, avalanche,
  thermal behavior, or hardware suitability. Project owners supply and review
  state coverage, potential intervals, rating sources, conditions, and
  utilization limits. A generic cohort-derived heuristic remains `REVIEW`; a
  project that declares this electrical contract as required receives blocking
  missing-coverage and over-limit results.
- **Cohort trial:** The version-pinned read-only trial catches
  synthetic VDS/VGS over-limit cases, accepts equality at the rating limits,
  and reports missing required states and node potentials as unresolved. Its
  findings name the MOSFET, state, terminal nets, stress, rating, and margin.
  It also reports all checks as passing for a DNP device and after the
  synthetic MPN changes, demonstrating missing population and expected-identity
  handling. The candidate manifests supplied only scalar steady-state
  potentials, not uncertainty intervals; the candidate trial did not exercise
  duplicate states or multi-device behavior. The local contract separately
  tests exact terminal-role/net mismatches and input-order invariance, and now
  exercises two independently mapped devices through unit and CLI/MCP tests.
  A direct LINT-064 comparison is inapplicable because its exact two-pin
  inventory cannot represent the same three-pin device. The local interval
  calculation is checked against exhaustive endpoint enumeration. Two KiCad
  10.0.6 ERC runs on the
  retained schematic each report the same ten findings; raw JSON differs only
  in the generated date. The deliberately sparse fixture is not a clean
  baseline, and ERC receives no operating-state manifest. LINT-064
  requires an exact two-pin native inventory and one requirement per part, so
  it cannot model D-S and G-S checks for this three-pin device. The state-aware
  multi-terminal capability is therefore a coverage gap, although the trial
  does not measure the unique defects a local contract finds on real designs.
  Exact cohort trial inputs, report digests, installation receipts, and known
  candidate gaps are in the
  [cohort trial README](../tests/fixtures/design_lint/cohort-mosfet-stress/README.md).
- **Synthetic evidence:** Tests cover exact identity, DNP exclusion, native pin
  functions and inventory, pin/net mismatches, missing state and potential
  coverage, conservative interval bounds against an independent arithmetic
  oracle over positive, opposite-polarity, and zero-crossing intervals, equality
  and over-limit boundaries, multiple states, input-order stability, and a
  two-device case where changing Q2's drain interval affects only Q2 VDS. The
  multi-device contract also passes CLI/MCP parity while a Q1 fault leaves Q2
  results passing. Retained-evidence omission rejection remains covered. Both
  control and fault pass/fail outcomes are derived from the same exact native
  netlist. Partial-state controls confirm that one missing interval does not
  suppress the independent voltage comparison for the other terminal pair. A
  tooling-owned schematic is checked twice for repeatable native
  exports and ERC signatures in the existing pinned-image acceptance lane.
  The multi-device regression uses a synthetic typed netlist contract; it does
  not expand the exact-version native fixture beyond one MOSFET.
  Local KiCad 10.0.6 and digest-pinned KiCad 10.0.0/10.0.5 exports pass exact
  identity and pin-map checks with zero ERC errors. The 2026-10-02 pinned run
  repeats normalized netlist digest
  `7061672756bfcb228a64155279b0e637377fc75b6871b3db976729f17292c224` on
  both versions; ERC-type digests are stable within each version and may differ
  between versions. The exact image digests and reproduction command are in
  the [synthetic native fixture record](../tests/fixtures/design_lint/mosfet-stress/README.md).
- **Pytest selection (2026-10-20):** The component-stress regression matrix
  now uses pytest functions and stable parameter IDs, with `design_lint` and
  `component_lint` markers. Before the migration, `-k wrong-drain-function`
  deselected all eight collected test methods because that fault was inside a
  `unittest` subtest; it now runs exactly one case (`1 passed, 17 deselected`).
  The full focused module passes 18 tests, the marker/collection architecture
  slice passes 38 tests, and the component evidence, CLI/MCP parity, and
  determinism slice passes 24 tests with one unrelated test deselected against
  the clean public template at `ed89536f0dbbcb013145af2994fef41b2250143e`.
  This changes test selection only; it adds no electrical rule or evidence.
- **Hosted acceptance (2026-10-20):** Tag `v0.5.2rc47` passed GitHub Actions
  run `39433440216`. Its annotated scope resolved to
  `design_lint and component_lint` with only `tests/test_mosfet_stress.py`;
  the focused gate, installed-wheel check against a separate public project,
  and Windows, Ubuntu, and macOS preview jobs passed. The package job was
  skipped under prerelease policy.
- **Next evidence:** Preserve LINT-064's two-pin identity rules. Before a
  project adopts this explicit requirement, its owner must review exact-part
  ratings, operating conditions, state coverage, potential intervals, and
  calculation bases. Any broader generic heuristic remains deferred without
  approved nonconfidential examples showing its applicability and review value.
  No proprietary project source or fixture is in scope.
- **V1 native acceptance:** Complete for the exact KiCad 10.0.0 and 10.0.5
  images. Follow-up applicability evidence is still required before broadening
  beyond project-authored requirements.

#### LINT-074 — Direct UART peers use different explicit reference nets

- **Status:** Implemented as `bus.serial_peer_reference_review`, defaulting to
  `REVIEW`, with project `review`/`block`/`off` overrides, exact fingerprint
  ignores, typed evidence, synthetic fault/control and metamorphic cases, and
  CLI/MCP parity. The detector covers fitted U/IC endpoints and source-
  identified connector candidates. Its exact-version native acceptance passed
  on KiCad 10.0.0 and 10.0.5 with repeated exports.
- **Problem and incremental-value hypothesis:** A native netlist can show two
  directly linked UART endpoints, each with a populated GND-like pin, while
  their pins occupy distinct nets. One endpoint may be an MCU/IC and the other
  a connector. ERC has no independent requirement that those references be
  common. This prompt adds context when generic numbered-return naming checks
  cannot associate the split with a direct UART signal link.
- **Predicate and suppression:** Find uniquely assigned, directionally clear
  native UART TX-to-RX links among fitted U/IC components and connector
  candidates identified by the bounded connector scan or project interface
  review. Require complete native pin-number, pin-function, and electrical-type
  inventories. Each endpoint must have one unique native net across its
  explicitly named GND/AGND/DGND/PGND/VSS/0V/RTN/RETURN/GROUND pins, with
  `passive` or `power_in` types; report when the endpoint nets differ. Explicit
  SHIELD, CHASSIS, FRAME, and PE functions are excluded. Suppress only when a
  current direct `serial_peers` map exactly matches both endpoint identities,
  TX/RX pins and nets, all explicit return pins and nets, and a `common_net`,
  `separate_nets`, or `bonded` reference policy. A `bonded` map also has to
  match its exact passive component and side-pin nets. Mapping supply pins
  cannot suppress the return-domain prompt.
- **Boundary:** This is a review question. It does not decide whether references
  should be common, joined through a specified component, or intentionally
  isolated. Incomplete pin metadata, DNP endpoints, ambiguous assignments,
  mixed return domains on one endpoint, connector candidates outside the
  bounded identity scan, and unsupported return-role spellings are skipped. A
  matching schematic map records reviewed intent and exact schematic bond
  assignments, but it does not prove component conduction, PCB copper
  continuity, off-board wiring, or electrical suitability.
- **Fixtures and evidence:** Synthetic tests cover IC-to-IC and MCU-to-header
  UART peers with split and common return nets, DNP and incomplete inventories,
  multiple endpoint return nets, exact `common_net`, `separate_nets`, and
  verified `bonded` maps, stale maps, a wrong-role supply-pin map, policy
  overrides, exact ignores, and ordering stability. Multi-port typed-netlist
  tests cover two UART headers on
  one MCU: the split-reference header produces one localized finding, the
  common-reference peer stays quiet, joining the first return clears the rule,
  and reversing component/net/pin-map order preserves the finding. These are
  unit results, not new native exports. The self-contained CLI/MCP regression
  `test_dual_uart_split_reference_localizes_one_header_on_cli_and_mcp` in
  `tests/test_design_lint_serial_parity.py` runs a digest-bound synthetic netlist
  with one MCU driving two UART headers: J1 has the split return, J2 shares the
  MCU return, and only J1 is reported; its all-common control is quiet for this
  rule. The same CLI/MCP case now also applies an exact source-matched
  `separate_nets` peer map and confirms the intentional split no longer prompts.
  This verifies shared-service and adapter parity, not another KiCad export.
  A typed three-header regression adds a third UART port with a common return
  beside one split-reference header and one common-reference header. It checks
  six supported signal links, one localized review, the all-common control, and
  order-independent reports; the cross-process hash-seed probe uses this
  three-header case. This extends synthetic coverage, not native export evidence.
  The native lane retains
  three IC-to-IC
  schematics (same-rail common-reference control, different-supply
  common-reference voltage control, and split-reference fault) plus the new
  MCU-to-header common-reference control and split-reference fault. All are
  exported twice on digest-pinned KiCad 10.0.0 and 10.0.5. The two connector
  cases have matching normalized typed-netlist digests across repeats and
  versions: `08650946c2dfeb42dda98b16e7ba9b37b934fdd310e6fb70e9801cfec08fef7d`
  for the common control and
  `62d7ca8a8fa4b8006d4a9bf38a385d2b132527b3d18edb0f4f8ea95d178f410b` for the
  split-reference fault. On the same native-derived typed netlist, turning only
  this rule off leaves generic `bus.serial_unmapped_peer` and decoupling prompts;
  no other finding identifies the `GND_A`/`GND_B` split. The regression records
  this delta. Source hashes and reproduction details are in the
  [native fixture record](../tests/fixtures/design_lint/serial-peer-connector-reference-native/README.md).
- **Coverage report improvement:** The source-bound report now retains one
  row for each discovered native-function or numbered-label link, with its
  endpoint references, signal nets/pins, and `INCOMPLETE`, `COMMON_REFERENCE`,
  `SEPARATE_REFERENCE_REVIEW`, or `MAP_COVERED_SEPARATE_REFERENCE` disposition.
  This lets reviewers locate incomplete reference evidence from the report
  instead of seeing only a count. Earlier schema-version-2 reports without
  these rows remain readable. Synthetic incomplete, common, separate, mapped,
  and label-discovered cases plus CLI/MCP parity cover the report behavior.
- **Remaining:** The checks establish repeatable tool behavior on bounded
  synthetic native exports. False-positive rate and reviewer effort have not
  been measured on approved nonconfidential designs. Keep the heuristic at
  `REVIEW`; no project should infer that similar-looking reference nets must
  be joined. The Antmicro multi-UART screen under LINT-031 identifies generic
  pin functions and channel labels outside this predicate; proposed LINT-082
  records the narrow extension and its required controls. Do not infer a
  multi-hop peer or cross an isolator from net labels alone.
- **Bundled root-project applicability screen (2026-10-03):** The same 35
  repeat-exported KiCad 10.0.5 root projects produced no direct UART TX-to-RX
  peer links for `serial_participants` and no LINT-074 separate-reference
  candidates. This leaves the public-board applicability and reviewer-value
  question open; the result is not a detector-precision measurement. Source
  mapping, complete schematic inventory, and repeatable typed-netlist digests
  are retained under ignored
  `build/ci/public-demo-lint-screen/output/lint-074-analysis.json`.
- **Public isolated-serial boundary screen (2026-10-03):** The public
  [HALPI2 hardware](https://github.com/hatlabs/HALPI2-hardware) at commit
  `43a04926cf8c5deeb93934d8cd72719e51050c87` declares a CERN-OHL-S v2 license,
  identifies its design as KiCad 9.0, and describes its RS-485 port as
  isolated. On the pinned KiCad 10.0.5 image, repeated exports of the
  source-bound top-level `HALPI2.kicad_sch` produced 659 components and 442
  nets with identical normalized typed-netlist SHA-256
  `8cdb62dd43c7a9e016ce070e8bcedddda76ead56e69d0e91cdb62bb64c1164f4`.
  The native inventory preserves distinct `GND` and `GND_RS485` nets with
  470 and 23 assigned pins respectively. `directly_linked_serial_peers` found
  no direct TX-to-RX peer, so LINT-074 emitted no finding. This is an
  out-of-scope isolated-interface control, not an applicable sample or a
  false-positive measurement; the current rule deliberately does not traverse
  isolator and transceiver paths. The root schematic SHA-256 is
  `2aced504936afebfbdadfb79b3cd0ba01eb96783b3383cb216ebf7f1cfcfefbd`; the
  `rs485.kicad_sch` SHA-256 is
  `5c6c68304f52f88660ffb65df815f3a2fda608f2e44cb0039b392d883752dc53`.
  Native output and typed analysis remain under ignored
  `build/ci/public-demo-lint-screen/output/halpi2/`; no source was copied into
  Tooling.
- **Public optical-isolation boundary screen (2026-10-11):** ST's
  [STEVAL-PCC020V2 manual, UM2945 Rev 2][st-usb-uart-isolation] describes a
  PC/USB domain and an isolated target domain, and explains that galvanic
  isolation protects the host PC. Its schematic labels `GND_USB` and
  `GND_STM`, places the CP2102 on the USB side, and carries the UART signals
  through two ACPL-M61L optocouplers. A tooling-owned synthetic two-direction
  optocoupled UART control confirms that LINT-074 does not bridge those grounds
  or report them as directly linked peers. A separate tooling-owned synthetic
  schematic now exercises this boundary in the digest-pinned native lane: it
  checks both signal directions, exact host/device supply and return pins,
  repeated normalized exports, and the absence of a direct-peer finding on
  KiCad 10.0.0 and 10.0.5. The hosted lane supplies the native result; this is
  not a measurement from the ST design. The manual is contextual evidence only,
  and no manual or project files were copied into Tooling.
- **Applicability report extension (2026-10-07):** LINT-074 now returns
  source-bound coverage for discovered native-function and numbered-label
  UART links. It distinguishes no direct peers, incomplete explicit reference
  metadata, and fully evaluated links; counts common and separate reference
  links, exact-map-covered links, and emitted review groups; and records the
  native netlist and authored-map provenance. Synthetic tests cover split and
  common references, incomplete pin evidence, no discovered direct links, and
  exact-map suppression. A dual-header CLI/MCP case checks one split link and
  one common control. This closes the report gap behind quiet results for this
  rule; the bounded status is not complete interface discovery, and the added
  coverage has not yet been screened on nonconfidential public designs. The
  report field is part of design-lint schema 2; schema 1 remains readable.
- **Focused native-gate repair (2026-10-12):** Review of LINT-074's prior
  `v0.5.0rc126` gate showed that its rule selector covered the synthetic
  multi-channel cases, while its tag enabled the neighboring serial roster
  fixture lane. The exact-version serial reference fault/control cases lived
  in the digital-peer native lane and were not linked from the rule catalog.
  LINT-074 now catalogues those exact native fault/control and cross-version
  repeatability tests and requires
  `KICAD_RUN_NATIVE_DIGITAL_PEER_FIXTURES` on rule-scoped tags. Tag validation
  rejects a missing required lane, and a focused pytest collection regression
  confirms the rule selector collects the native test cases. This closes a
  release-gate coverage gap; it does not claim a physical return-path test.
- **Rule-scoped parity indexing (2026-10-12):** A follow-up selector audit
  found four relevant CLI/MCP parity tests that were not reachable from the
  LINT-074 rule selector: the dual-UART split-reference case, channel-labeled
  generic-UART case, bonded-map control, and serial connector parity case. The
  catalog now indexes those tests as fault/control fixtures. The focused
  selector collects all four; the complete local LINT-074 selector passed
  (`26 passed, 7 skipped, 6 subtests passed`). Tag `v0.5.0rc175` passed hosted
  acceptance run `38285389294`, including the focused lint gate, exact native
  lane, installed-wheel check against a separate template project, and all
  three preview jobs. This improves regression selection and adapter parity
  coverage; it is not additional electrical evidence.
- **Done when:** Complete.

#### LINT-075 — Oscillator-module output load-path review

- **Priority and status:** P3 cohort-derived candidate. The generic discovery
  heuristic is not adopted; its bounded, project-mapped follow-on is active as
  LINT-150. LINT-031 records the initial repeated no-CLI trial and an expanded
  native trial on 11 tooling-owned schematics with KiCad 10.0.6. The candidate
  demonstrates a narrow direct-load hint, a fixture-relative over-prompt for
  an allowed direct-drive topology, and misses for wrong-part, DNP, and
  wrong-value series components. Part-specific applicability remains open.
- **Cohort input:** The public [`kicad_skills` schematic-review
  guide](https://github.com/sabas0ba/kicad_skills/blob/main/docs/guides/kicad-schematic-review.md)
  lists `analog.clock_no_series_resistor`: an oscillator-module output that
  drives a load directly, with resistors and test points treated differently
  from active loads. This is a documented heuristic, not a universal
  clock-design requirement. The candidate review supplied no part-specific
  datasheet basis for when a series resistor is needed. No candidate source or
  fixture was copied into the tooling package.
- **Problem and incremental-value hypothesis:** Native ERC does not compare a
  project's reviewed oscillator-output topology with the source-bound
  schematic. When a specific module requires a source resistor, removing or
  bypassing it can leave a syntactically valid netlist. LINT-150 adds an exact
  project map for topology and nominal resistor range. A review hint for an
  unmapped oscillator output remains deferred because the trial showed an
  allowed direct-drive over-prompt and no measured field benefit.
- **Candidate predicate:** The LINT-150 deterministic path check uses a
  project-authored map for exact oscillator and load identities, output and
  load pins, direct or series topology, and (for series topology) the fitted
  resistor identity, pin endpoints, and reviewed nominal value bounds. It
  compares these expectations with the source-bound native netlist. No
  discovery prompt is included.
- **Boundary:** Do not infer that every clock needs damping, that an output is
  an oscillator module from a generic `CLK` net name, or that a resistor value
  is suitable. Crystal and resonator networks, MCU-generated clocks, clock
  buffers, differential clocks, multiple fanout topologies, DNP links,
  ferrites, zero-ohm links, and off-board loads need explicit applicability
  evidence before support. Matching a map proves only agreement with the
  authored schematic topology; it does not prove the selected part's
  datasheet, signal integrity, placement, PCB copper, or measured waveform.
- **Trial fixtures and open evidence:** The initial no-CLI trial in
  `tests/fixtures/design_lint/cohort-clock-series/` covers X-reference and
  `Oscillator:` library-ID discovery paths, direct and series topology, a
  shunt pull, a passive crystal, DNP, wrong-value, and an authored direct-drive
  alternative. The expanded native set in
  `tests/fixtures/design_lint/cohort-clock-series-native/` adds direct-load
  test-point, series-side test-point, wrong-part, wrong-net, bypass, and pull
  cases. KiCad 10.0.6 exports the expected pin-to-net membership for all 11
  new fixtures, and native ERC reports zero errors. Candidate results repeat
  across two runs; the machine-readable report digest and source hashes are in
  that fixture record. The earlier `series-x-control` no-CLI fixture has a
  native ERC fault: its `+3V3` label is on X1's output wire and VDD pin, and
  ERC reports two undriven power-input errors. Its historical no-CLI record is
  unchanged; the new native controls are separately generated. Exact
  part-specific applicability, an existing first-party clock map, reviewer
  effort, and the full candidate install/container flow remain unmeasured.
  Keep any future finding at `REVIEW` unless a project supplies an independently
  reviewed exact requirement.
- **Done when:** LINT-031 records the pinned cohort version/commit, license,
  rule source hash, isolated install procedure, native version, exact synthetic
  source/output hashes, and result for every fault and control. A first-party
  check is added only if a project-authored topology requirement demonstrates
  unique detection or materially better localization without treating valid
  direct-drive topologies as faults. No proprietary board or project data is
  in scope.

### Cohort source inspection register

The following source observations came from current public project
documentation and selected source inspection on 2026-09-27 through 2026-10-08.
Runtime trial evidence is recorded separately under LINT-031. No cohort tool
has been run on a private board or imported into this repository.

- **Same-net plane copper opens:** Public
  [kicad-tools issue #3787](https://github.com/rjwalters/kicad-tools/issues/3787)
  describes a board whose front and back ground planes share one schematic net
  but remain separate copper islands without ground stitching vias. The issue
  reports that schematic/net assignment and its DRC run did not establish a
  physical bond; its copper-LVS comparison exposed the opens. This failure
  description informed the synthetic LINT-025 unstitched-plane fault and
  through-via control. No candidate analyzer code, board, or project fixture
  was copied, and no head-to-head analyzer trial is claimed.
- **Operating-state MOSFET stress:** The public
  [kicad-tools README](https://github.com/rjwalters/kicad-tools/blob/main/README.md)
  documents the base pip installation, but it does not list
  `kct analyze component-stress`. The public
  [`pyproject.toml`](https://github.com/rjwalters/kicad-tools/blob/main/pyproject.toml)
  declares version 0.21.1, MIT, and Python 3.10+. Its
  [CLI reference](https://github.com/rjwalters/kicad-tools/blob/main/docs/reference/cli.md)
  also omits the subcommand; installed 0.21.1 command help exposes it. A
  disposable Python 3.11.16 install of 18 packages ran the synthetic trial
  under LINT-073. The read-only trial found the seeded VDS/VGS over-stress and
  missing coverage, passed the exact-rating boundary, and exposed DNP and
  expected-MPN gaps. It highlights a multi-terminal, per-state requirement
  that LINT-064's exact two-pin schema cannot express. No local head-to-head or
  unique defect measurement has been completed. Reports and fixture hashes
  are recorded in the cohort trial README. No candidate source, project
  example, or board was copied.
- **STM32 firmware pin-map comparison:** The public
  [STM32-KiCad-Pin-Checker](https://github.com/jbmata/STM32-KiCad-Pin-Checker)
  README documents `.net`/`.ioc` comparison, aliases, ignored pins, an MIT
  declaration, and a GUI-only invocation with CLI/CI listed as future work.
  The source-pinned parser comparison is recorded under LINT-031. It found
  order-dependent handling of conflicting suffix assignments and no support
  for an escaped PH0 key; the local parser handles both cases deterministically.
  The GUI was not run, and no candidate code or dependency was adopted.
- **I2C pull-up voltage context:** The public
  [kicad-happy changelog](https://github.com/aklofas/kicad-happy/blob/main/CHANGELOG.md)
  documents I2C pull-up, rise-time, and voltage-related analysis fields. This
  is documentation review, not a repeat runtime benchmark. LINT-059 uses only
  the category as a prompt to retain pull-up rail identities in evidence.
  LINT-010 now has an opt-in source-bound resistor-window contract derived
  from the [NXP I2C specification](https://www.nxp.com/docs/en/user-guide/UM10204.pdf)
  §7.1 and [TI SLVA689](https://www.ti.com/lit/an/slva689/slva689.pdf);
  the project must author its voltage, capacitance, sink-current, and timing
  assumptions. No guessed rail values or third-party detector code were
  imported.
- **Digital voltage and rail-sequencing review:** The inspected public
  [kicad-happy `VM-001` and `PS-001` source](https://github.com/aklofas/kicad-happy/blob/a6bba1add1e18b89e3aa0824b9769ed1d9d79174/skills/kicad/scripts/validation_detectors.py)
  uses rail-name voltage estimates and generic threshold tables for domain
  crossings, and common enable-pin names plus inferred regulator outputs for
  sequence edges. These remain discovery signals only. LINT-061 implements
  exact project-authored endpoint limits; LINT-062 implements an opt-in
  project-authored dependency graph, with numeric timing checks still deferred.
  The pinned `VM-001` runtime result is recorded under LINT-031. No candidate
  code or project data was copied.
- **Component-rating and voltage-derating review:** The public
  [kicad_skills README](https://github.com/sabas0ba/kicad_skills/blob/53d1af8bc550f60415b4b8e51a6d2d5924ada03f/README.md)
  describes rating checks; its
  [schematic review guide](https://github.com/sabas0ba/kicad_skills/blob/53d1af8bc550f60415b4b8e51a6d2d5924ada03f/docs/guides/kicad-schematic-review.md)
  says the voltage heuristic uses voltage-explicit rail names. The pinned repo
  declares Apache-2.0. These docs were reviewed, but the rating check was not
  source-audited or runtime-trialed; the separate LINT-031 trial covers only
  `analog.no_dc_path`. LINT-064 implements a source-bound contract with exact
  part identity, reviewed stress, and a project-selected margin. It rejects
  generic voltage-name guesses; no candidate code or project data was copied.
  LINT-071 separately checks authored power rating, derated allowable power,
  and worst-case dissipation against the native exact-part identity. Its
  synthetic results do not validate a real thermal calculation. Its exact-
  version native acceptance passes locally on KiCad 10.0.0 and 10.0.5; a
  hosted GitHub run for the current dirty branch is not recorded.
- **Connector/capacitor-only net review:** The public
  [kicad_skills schematic review guide](https://github.com/sabas0ba/kicad_skills/blob/53d1af8bc550f60415b4b8e51a6d2d5924ada03f/docs/guides/kicad-schematic-review.md)
  lists `analog.no_dc_path` for a net whose pins are all capacitors or
  connectors. LINT-065 implements an independent, exact-pin REVIEW candidate
  and explicitly allows off-board or internal bias. The pinned runtime trial
  found no unique detection and an extra warning on a DNP control; its rule and
  data-boundary evidence are recorded under LINT-031. No cohort code, fixture,
  or project data was copied.
- **kicad_skills rule selection and installation:** The
  [README at the pinned commit](https://github.com/sabas0ba/kicad_skills/blob/53d1af8bc550f60415b4b8e51a6d2d5924ada03f/README.md)
  documents a Docker/Bash CLI, KiCad 9.0.9 and 10.0.4 image tags, and a
  first-use image build of about five minutes; the container runs without
  network access. The schematic guide lists single-pin nets,
  missing drivers, decoupling, I2C pull-ups, LED limiting, power-input
  protection, and rating/derating checks; the [PCB review guide][kicad-skills-pcb]
  also discusses power, thermal, and crosstalk review. The single-pin-net
  finding class was already trialed under LINT-031 and repeated on both fault
  and control fixtures, so it is not adopted. Other schematic topics map to
  LINT-010, LINT-046, LINT-048, LINT-056, or source-bound contract candidates
  such as LINT-064. The `analog.no_dc_path` runtime trial used a separately
  installed host-side `--no-cli` fallback and did not validate the documented
  container workflow. It showed no unique detection; no adapter or runtime
  dependency is justified. Its public schematic guide also documents
  `analog.clock_no_series_resistor` for a directly loaded oscillator-module
  output. LINT-075 records a pinned no-CLI trial and an expanded KiCad 10.0.6
  native synthetic trial: it flags direct loads, including a fixture-authorized
  direct-drive alternative, distinguishes a shunt pull, and misses wrong-part,
  DNP, and wrong-value series components. Part applicability, reviewer effort,
  and field precision remain unmeasured.

### Curated rule concept register

This register records concepts that have a specific deterministic or
reviewable candidate. “Adopted” means an independent local implementation has
synthetic tests; it does not mean a cohort tool was benchmarked or that its
engineering advice applies to every design.

| Concept                                                | Source input                                                                                       | Local disposition and next evidence                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| ------------------------------------------------------ | -------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Multiple global or hierarchical labels on one net      | kicad-happy `LB-001`                                                                               | Deferred after a partial exact-version trial: KiCad 10.0.0/10.0.5 ERC reports both distinct labels and the canonical net name for a synthetic alias fault; a repeated-name control is quiet. The candidate runtime and reviewer-time benefit were not measured. See the detailed disposition and fixture record below.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| Repeated connector supply/return functions             | Existing native-netlist patterns and the return-disconnect scenario                                | Adopted as review candidates in LINT-001/002 and synthetic-tested. Exact common, bonded, or isolated intent still belongs in project contracts.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| Numbered positive supply rail names                    | User's similar-connector power-pin scenario                                                        | LINT-040 adds a bounded, explicitly delimited net-name grouping hint for generic or numeric connector pin functions. Intentional isolation and independent sources remain valid; the feature is review-only and not a cohort runtime benchmark.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| Connector return-contact distribution                  | kicad-happy reports a signal-to-ground contact ratio                                               | LINT-038 adopted as an optional project threshold over explicit interface pin roles; synthetic fault/control tests distinguish the ratio question from missing-return and repeated-return findings.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| I2C pull-ups and responder addresses                   | kilint and kicad-happy rule families                                                               | LINT-010/033 provide direct-resistor, authored rail-to-input voltage-limit, and address checks. LINT-042 adds a review prompt for likely U/IC responders omitted from the authored address map, based on native SDA/SCL pin functions. Array channels and collisions have synthetic controls. Optional pull-up feasibility requires project-authored voltage, capacitance, sink-current, and timing bounds; it does not model internal pulls or unreviewed off-board loading.                                                                                                                                                                                                                                                                                                                                                                                                      |
| I2C pull-up feasible resistance window                 | kicad-happy rise-time metrics; NXP UM10204 §7.1; TI SLVA689                                        | LINT-010 derives a lower resistance bound from authored rail maximum, VOL limit, and minimum sink current, plus an upper bound from authored capacitance and rise-time limit. Source-bound controls cover both sides and an empty window; exact CLI/MCP results match. This is an idealized RC calculation over reviewed inputs, not a capacitance extraction, tolerance analysis, or waveform measurement.                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| MOSFET operating-state terminal stress                 | kicad-tools 0.21.1 `component-stress`                                                              | LINT-073 uses the cohort trial as a requirements lead and defers its analyzer because the trial passed DNP and changed-part controls. The local `mosfet_stress` contract checks exact three-pin identity and role mapping, required-state potential intervals, and VDS/VGS utilization; synthetic parity, retained-receipt, and digest-pinned KiCad 10.0.0/10.0.5 acceptance passed on 2026-10-02. The native lane validates synthetic source and calculation behavior, not device suitability.                                                                                                                                                                                                                                                                                                                                                                                    |
| I2C pull-up rail families                              | kicad-happy bus voltage/pull-up summaries; NXP UM10204                                             | LINT-059 prompts when visible fitted pull-up paths use different recognized rail-name families across SDA/SCL. It does not resolve rail values, assert incompatibility, or replace project-authored endpoint voltage limits. Same-family aliases, DNP devices, custom names, and unmodeled pull-up circuits have controls or explicit boundaries.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| SPI participant and CS review                          | kicad-happy `detect_sensor_interfaces` and `validate_spi_bus`                                      | LINT-052 compares bounded SPI-like native pin functions with the source-hashed project roster; it prompts for review when a likely participant is unlisted or no roster exists. Exact-version native exports on KiCad 10.0.0/10.0.5 preserve prefixed SCLK/COPI/CIPO/NSS functions and distinguish an absent-roster prompt from a complete-roster control. Pinned source inspection found that sensor peers are listed by shared extracted nets but not compared with authored membership; its CS detector covers pull-up topology. LINT-045 separately implements the CS-bias prompt. The inventory is a clue, not proof that a device belongs on that bus.                                                                                                                                                                                                                       |
| Unmapped cross-supply digital peers                    | kicad-happy `VM-001`                                                                               | LINT-066 implements default-REVIEW prompts for recognized SPI and UART/USART TX-to-RX peers using complete native pin-type and exact voltage-explicit supply-label evidence. It does not infer incompatibility; complete exact LINT-061 maps take over covered links. Synthetic fault/control and CLI/MCP parity pass. SPI repeated native exports pass on pinned KiCad 10.0.0/10.0.5; UART repeated local KiCad 10.0.6 exports pass and the pinned-version lane is configured. A source-informed GPIO-to-regulator-EN anti-control now protects the protocol-only boundary; this does not measure field false-positive rates. See both fixture notes.                                                                                                                                                                                                                             |
| CAN peer pair net asymmetry                            | kicad-happy v2.2.1 CAN protocol checks; repeated native CAN pin assignments                        | LINT-067 prompts when fitted complete CANH/CANL pairs share one exact schematic net but diverge on the other. It is a review-localization hint, not a determination that the pairs must be joined. Synthetic same-pair, one-side split, separate-bus, and DNP controls plus repeated native exports without ERC errors pass on KiCad 10.0.0/10.0.5; isolated-library warnings are recorded. The LINT-031 runtime trial emitted the same empty-net missing-termination message on control and fault and did not expose PR-003 in JSON. Reviewer effort and field false positives remain unmeasured.                                                                                                                                                                                                                                                                                 |
| USB-C port role-map coverage                           | kicad-happy USB-C CC validation                                                                    | LINT-053 prompts when a connector exports both CC1/CC2 pin functions but is absent from the authored role map. Native exports on KiCad 10.0.0/10.0.5 prove this bounded pin-function field and mapped/unmapped behavior. A pinned v2.1.0 runtime trial recognized simple 56 kΩ source and 5.1 kΩ sink controls, but for an unknown role it emitted sink-specific missing-pull-down findings while reporting the role as unknown. It adds no unique coverage over the local role-map prompt and authored role checks; details and hashes are in the synthetic fixture notes.                                                                                                                                                                                                                                                                                                        |
| LED current-limiter presence                           | kicad-happy `validate_led_resistors`, LR-001; LED audit `LA-AUD`                                   | LINT-048 keeps exact `Device:LED` direct positive-rail/return assignments as a review hint; LINT-063 prompts when a native output-capable pin directly shares an LED terminal and the other terminal is on a recognized rail. A read-only `LA-AUD` trial corroborates the simple direct-output case but misclassifies the parallel-resistor fault as `resistor_limited`; the local rule retains that finding. Native exports on KiCad 10.0.0/10.0.5 assert the parallel resistor shares both LED nets before testing. ERC, current, and electrical qualification remain open; exact cohort hashes and reports are in the synthetic fixture notes.                                                                                                                                                                                                                                  |
| USB external series-resistor topology                  | kicad-happy PR-004; ST AN4879; TI TUSB2036 datasheet                                               | LINT-049 implements an opt-in exact connector-to-PHY path map. The source-backed integrated STM32 direct-path control and TI TUSB2036 27R control both pass; removing a mapped resistor is detected. The generic cohort rule prompts on both PHY classes, so its universal resistor assumption is not adopted. Native source-to-netlist regressions now pass synthetic direct, series, and bypass cases on KiCad 10.0.0 and 10.0.5. Native ERC and electrical qualification remain open.                                                                                                                                                                                                                                                                                                                                                                                           |
| STM32CubeMX to KiCad MCU pin assignments               | jbmata/STM32-KiCad-Pin-Checker README and selected `ioc.py` source                                 | LINT-050 implements a configurable, source-hashed map from exact package pins to KiCad symbol pins, schematic nets, CubeMX signals, and labels. Service and CLI/MCP parity pass, as do repeated native exports on KiCad 10.0.0 and 10.0.5. The pinned trial found order-dependent PA13 suffix conflicts and ignored escaped PH0; local parsing rejects conflicts and accepts PH0. The candidate remains unadopted; GUI behavior and reviewer value were not measured. See LINT-031.                                                                                                                                                                                                                                                                                                                                                                                                |
| IC power-pin DC-source path                            | kicad-happy `audit_power_pin_dc_paths`, PP-001                                                     | LINT-031's mapped wrong-rail follow-up shows PP-001 detects the ERC-clean synthetic fault when no map exists, while the valid path control is quiet. The project-authored LINT-055 map already catches it when supplied. LINT-056 adopts a configurable fallback REVIEW using a narrower explicit passive set; it does not copy the candidate's severity or “AC-coupled” diagnosis. External source recognition, custom paths, and broader false-positive behavior remain open.                                                                                                                                                                                                                                                                                                                                                                                                    |
| Connector/capacitor-only net without visible DC anchor | kicad_skills `analog.no_dc_path`                                                                   | LINT-065 adds a default REVIEW when every fitted pin on a non-return net is a supported connector or capacitor and at least one of each is present. It does not trace DC paths and allows off-board/internal bias. Native KiCad 10.0.0/10.0.5 runs repeat the fault, output-driver control, and DNP-capacitor control; ERC is clean in all. The pinned cohort runtime duplicates the fitted fault, stays quiet on the output-driver control, and warns on the DNP control because it counts unpopulated C/J/P-prefixed symbols. No unique detection; see LINT-031. This is synthetic evidence, not field validation.                                                                                                                                                                                                                                                               |
| Unmapped decoupled power-input source path             | kicad-happy `PP-001`                                                                               | LINT-056 uses native `power_in`, fitted capacitor-to-return evidence, recognized positive rails or `power_out` pins, and a bounded fitted path graph. It recognizes bidirectional passive elements and the exact bridged solder-jumper symbol, and traverses exact supported diodes in the source-to-load direction. It prompts REVIEW when no supported path is found and suppresses the prompt for endpoints covered by an authored LINT-055 map. The synthetic assigned-wrong-rail case is missed by the mapless baseline and native ERC; the check does not infer required connectivity or prove conduction.                                                                                                                                                                                                                                                                   |
| IC decoupling-to-return coverage                       | kicad-happy `DO-DET`; kicad_skills `analog.missing_decoupling`                                     | LINT-046 emits a review prompt for a source-backed no-cap schematic whose `power_in` and `power_out` pins share `+3V3`; native KiCad 10.0.0/10.0.5 report no `power_pin_not_driven` violation. kicad-happy reports the no-cap fault and also synthetic source U2; kicad_skills duplicates the fitted fault/control result in `--no-cli` fallback mode. The kicad_skills DNP case stays quiet although native exports preserve the DNP flag and LINT-046 reports it. These trials add no unique detection; capacitor need/value, placement, and PCB return path remain open. See LINT-031 and the synthetic fixture record.                                                                                                                                                                                                                                                         |
| External connector protection coverage                 | kicad-happy and ThomsonLint `EMC_ESD_001`                                                          | LINT-034 adopted as a source-bound per-pin coverage contract. Applicability is authored; clamp suitability and PCB return geometry remain unverified.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| Crystal load network                                   | kicad-happy crystal analysis                                                                       | LINT-035 adopted for an explicitly mapped Pierce topology, nominal value ranges, and source-bound pins. Startup, tolerance, and placement are not established.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| Adjustable regulator setpoint                          | kicad-happy feedback-divider analysis                                                              | LINT-036 adopted for a project-mapped two-resistor topology and reviewed reference range. No part-name inference or general converter model is used.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| Reset/enable/boot default state                        | ThomsonLint `MS_RST_001`; kicad-happy control-signal review                                        | LINT-017 includes an exact project contract and an optional REVIEW hint for unassigned supported input pins; DNP parts are excluded. Read-only exports from public KiCad demo projects exercised recognized reset, enable, and boot aliases with native input types. These names remain clues and do not establish required polarity, bias, or successful runtime behavior.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| RC filter cutoff                                       | kicad-happy passive-network analysis                                                               | LINT-037 adopted as an explicitly mapped first-order source-bound review; a synthetic value mutation preserves connectivity and triggers a corner-range finding. Multi-stage and loaded networks need separate models.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| Decoupling placement                                   | pcb-inspector, ThomsonLint, and kicad-happy EMC `DC-003`                                           | LINT-020 now optionally checks an authored maximum distance from an exact capacitor return pad to the nearest via in that pad's native copper component. The rule reports the via identity and measured geometry; it does not estimate loop inductance or require a via when the project omits the limit. KiCad 10.0.0/10.0.5 fixtures cover a connected via at the boundary, a moved-via fault, and unconnected nearby-via control. No cohort implementation or board fixture was imported.                                                                                                                                                                                                                                                                                                                                                                                       |
| Mapped track-width screen                              | pcb-inspector power-width analysis; ThomsonLint thermal/power guidance                             | LINT-021 implements project-authored per-net minimum-width screening with native segment evidence. Zone-only nets remain incomplete; current, thermal, via, and plane analysis is deferred.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| Adjacent reference-plane coverage                      | pcb-inspector `HEUR-GND-001`; kicad-happy `GP-001`                                                 | LINT-058 maps exact signal nets/layers and measures centerline fraction over adjacent same-net filled copper. The 5 mm/0.9 cohort example is not a default. A pinned kicad-happy `GP-001` run sampled only the endpoints of a 2 mm route and missed a 0.2 mm midpoint void; a pinned pcb-inspector `HEUR-GND-001` run detects the same fault and clears the control at a fixture-only 0.65 threshold, but reports the full segment affected and adds no unique detection. LINT-058's exact native geometry distinguishes the synthetic fault from its continuous control and reports endpoint-via clearance context while keeping those intervals uncovered; merged-hole ownership remains unknown. The hosted split-suite repeat passed. This review rule does not prove return-current continuity.                                                                               |
| Differential-pair constraints                          | pcb-inspector and ThomsonLint `HS_DIFF_001`                                                        | LINT-022 comparison on synthetic boards showed KiCad 10.0.0/10.0.5 DRC catches configured width, gap, skew, and uncoupled-length faults; no pair finding appears without an authored rule. The tooling now audits project-authored limits against the exact source-bound active native rules. Independent geometry checking is deferred; no cohort implementation or board was imported.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| Missing differential-pair review coverage              | pcb-inspector `HEUR-DIFF-001`                                                                      | LINT-031 measured a unique 0.50 mm skew warning without native pair rules, but its default 0.15 mm limit is not universal and it misses equal-length gap/uncoupled faults. LINT-041 adopts only a deterministic name-pattern prompt for an explicit project pair requirement; native geometry limits remain project-authored under LINT-022.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| Switching-loop geometry                                | pcb-inspector and ThomsonLint buck hot-loop guidance                                               | LINT-023 reports a project-authored pad-center polygon proxy and same-island return-plane check. Native F.Cu, connected In1.Cu, and split In1.Cu synthetic fixtures pass on KiCad 10.0.0/10.0.5. LINT-039 captures why routed comparison needs explicit edge roles and unique route resolution; converter-topology coverage remains open.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| Schematic near-miss localization                       | kicad-sch-lint and KiDiff                                                                          | LINT-024 has eleven opt-in review rules. kicad-sch-lint text-overlap, text-over-wire, text-over-body, and wire-through-body trials each distinguish the synthetic graphical fault from its control while native ERC/netlist signatures remain unchanged. First-party text checks use bounded font envelopes; body checks use supported embedded symbol graphics and axis-aligned envelopes. LINT-044 scopes unsupported coverage to enabled rules. Public-template review found one unique J1 wire/body layout repeated in two examples; KiCad 10.0.6 ERC was clean, but neither project records intent, so the result is unresolved rather than a false-positive measurement. All rules remain default-off review hints; intentional overlaps, crossings, and T-shaped contacts remain possible, and no geometry auto-fix is allowed. Remaining fixture classes are listed there. |
| Analyzer execution and skipped-check coverage          | kicad-happy v2.2.1 `checks_run`, `connectivity_graph_error`, and skipped conditional DRC reporting | LINT-076 adds source-bound execution receipts for the three mapped checks that lacked dedicated coverage. Its audit found no other current service gap that justifies a global per-rule ledger; reopen when a new check can skip without observable status. No cohort code or report format is imported.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| Clock termination and driver topology                  | ThomsonLint `HS_CLK_001`; kicad_skills `analog.clock_no_series_resistor`                           | LINT-031 records the pinned no-CLI trial in LINT-075. It shows a useful direct-load hint but also an over-prompt on an authored direct-drive alternative and misses DNP/wrong-value components. Do not adopt a universal series-resistor rule. A source-bound path map remains conditional on reviewed part requirements and native evidence.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| ADC/op-amp protection and operating range              | ThomsonLint `AN_ADC_001` and analog rule families                                                  | Deferred as a generic rule. Device limits, source impedance, protection ratings, filter targets, and operating conditions need reviewed device-specific inputs; some protection coverage already belongs to LINT-034.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| Universal ESD requirement for every connector          | ThomsonLint `EMC_ESD_001` and kicad-happy protection review                                        | Rejected as a universal blocking rule. LINT-034 instead requires an explicit per-pin protection or not-required decision for scoped external interfaces.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |

**Disposition — multiple global or hierarchical labels on one net (LB-001):**
**Status (2026-10-03):** Keep the electrical lint deferred. A Tooling-owned
synthetic fault with two distinct global labels on one net and a repeated-name
control were exported twice using the exact KiCad 10.0.0 and 10.0.5 images
listed in the [fixture record](../tests/fixtures/design_lint/cohort-label-alias/README.md).
For both versions, the fault adds ERC warning `multiple_net_names`; its
diagnostic names both labels and says which one supplies the netlist name. The
duplicate-name control does not emit that warning. Normalized pin/net
assignments and ERC signatures repeat across exports and versions; raw XML
timestamps differ. Thus the documented kicad-happy [`LB-001`][happy-lb001]
predicate overlaps native ERC for this tested case, and no electrical
detection gain is demonstrated.

This is a partial native comparison, not a trial of the candidate runtime.
The candidate's additional maintainability explanation and review-time value
remain unmeasured, as do intentional aliases, power-label exclusions, and
same-name labels on separate sheets. The existing source geometry reader also
does not yet provide a complete, native-bound label-to-net inventory. Reopen
only if a candidate comparison demonstrates a repeatable review gain, such as
materially better localization or a useful case native ERC misses. Keep any
future result at `REVIEW`; multiple labels alone do not establish a wiring
fault. No cohort code or project data was imported.

### Recorded source review: kicad-happy thermal analyzer (v2.3.1)

- **Source boundary:** Read-only review of the public
  [kicad-happy v2.3.1 release][happy-thermal-v231], tagged at commit
  `06840467ad0f5d76af45f64449b1f5ecb10f052f`; the repository declares MIT.
  The [thermal analyzer source][happy-thermal-source] and release notes include
  rotated-QFN thermal-via counting and a clearer reason when thermal assessment
  is skipped. No analyzer was installed or run, and no cohort code, corpus, or
  board data was copied.
- **Observed checks:** `analyze_thermal.py` estimates junction temperature
  from dissipation, package thermal resistance, ambient conditions, and a PCB
  correction. Its thermal-via warning uses a fixed dissipation threshold of
  0.5 W and a near-unity PCB correction; its recommendation gives a generic
  minimum of five vias for QFN. Its capacitor proximity warnings use a 10 mm
  radius and classify capacitor types from value text. These are deterministic
  predicates over estimated or inferred inputs, not a part-specific thermal
  proof.
- **Local overlap and disposition:** LINT-071 compares exact-part dissipated
  power against an authored derated limit. Native PCB services report geometry
  and connectivity, but this repository has no thermal solver or reviewed
  package-to-board heat model. Defer importing the estimator and its thresholds.
  A future local check needs a project-authored thermal limit and source,
  exact component identity, ambient and power basis, package/board assumptions,
  and explicit thermal-pad/via connectivity evidence. Via-count-only or
  10 mm-only rules do not meet that bar.
- **Next synthetic evidence:** If an authored thermal contract is added, pair
  a no-via fault with pad-connected vias, unrelated vias, wrong-plane vias,
  and DNP controls; include package-specific alternative constructions and
  threshold boundaries. Until the contract and expected outcomes are reviewed,
  do not count the candidate as detection or review gain.

### Cohort cross-analysis rule audit

The public [kicad-happy v2.2.1 changelog][happy-changelog] and
[PCB methodology][happy-pcb-methodology] document several cross-analysis
families. The changelog names CC-001 connector current capacity versus trace
width, EG-001 ESD coverage, DA-001 decoupling adequacy, and XV-001..003
schematic/PCB checks. Its [cross-verification release notes][happy-cross-verify]
also describe differential-pair length/skew, power-trace width, decoupling
placement, bus routing, and thermal-via checks. The methodology describes
per-net route length, minimum power-net track width, via dimensions, and an
approximate IPC-2221 current screen; this is documentation review, not an
implementation audit or runtime trial. The local dispositions below compare
these descriptions with existing tooling so new work targets a demonstrated
gap. This documentary re-audit was recorded on 2026-10-01; pin the exact
candidate commit and installation inputs before any new runtime comparison.

| Candidate                                          | Existing local coverage                                                                                                                                                                                                                  | Disposition and evidence required                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| -------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| CC-001 connector/contact current versus PCB copper | LINT-021 measures project-mapped net track widths; LINT-071 checks authored component power dissipation. LINT-077 now checks owner-authored current against an exact per-contact rating. Neither local check calculates copper ampacity. | The contact slice is implemented in LINT-077 with exact identity/pin binding; hosted native pass, run 38143123091. Defer copper-capacity work until an independently reviewed model defines stack-up, temperature, vias/zones, route topology, branching, and current allocation. Do not infer ratings or current sharing from net names or a net-wide minimum width. The public candidate implementation was not installed or runtime-tested; only its documented question informed this narrower local contract. |
| EG-001 external-connector ESD coverage             | LINT-034 requires a reviewed protection disposition per scoped connector pin; LINT-060 checks mapped PCB entry and return-via geometry.                                                                                                  | Pinned source review found no bounded gap beyond LINT-034; retain no new rule. See the source-review note below.                                                                                                                                                                                                                                                                                                                                                                                                   |
| DA-001 decoupling strategy adequacy                | LINT-046 reviews fitted-capacitor presence; LINT-020 measures project-mapped PCB placement; LINT-136 compares exact mapped capacitors with an authored nominal minimum for one IC power pin.                                             | LINT-136 closes a narrow explicit-requirement gap without adopting the cohort's inferred one-capacitor-per-IC suggestion. Its exact-version hosted gate passed on `v0.5.1rc35` (run `39311021307`). The rule does not choose a universal value or replace placement/return checks.                                                                                                                                                                                                                                 |
| XV-001..003 schematic/PCB consistency              | Existing verification binds native schematic/netlist and PCB artifacts.                                                                                                                                                                  | LINT-102 compares fitted schematic references and assigned footprint identities; LINT-111 compares default DNP flags; LINT-112 compares fitted schematic/PCB value fields. Board-only footprint classification and variant-aware comparisons remain deferred. Cohort source review informed the audit; no code was imported or executed.                                                                                                                                                                           |
| CC-001 style ampacity-target net-class proposal    | LINT-021 accepts project-authored minimum widths and records exact native track measurements.                                                                                                                                            | Treat the public [kicad-tools ampacity-target proposal](https://github.com/rjwalters/kicad-tools/issues/4216) as an unimplemented research lead, not a cohort feature to import. Any future derivation needs a documented, licensed/available calculation basis, explicit copper and temperature assumptions, boundary tests, and comparison with an independent reference. Preserve authored widths as screens until that evidence exists.                                                                        |
| Mapped bundle route length and inter-signal skew   | LINT-095 audits project-authored exact endpoints, bundle membership, and active native DRC length/skew rules; LINT-022 covers differential-pair constraint coverage.                                                                     | Keep using native DRC for route measurement and LINT-095 for authored intent and rule coverage. Reconsider a separate geometry engine only if it adds independently confirmed coverage or materially clearer localization beyond those checks.                                                                                                                                                                                                                                                                     |
| Thermal-via coverage for mapped dissipating parts  | LINT-071 compares exact-part dissipated power with an authored derated power limit; it does not estimate package temperature or via benefit.                                                                                             | Keep deferred until a project-authored thermal requirement identifies the exact package, heat path, layers, connected via population, copper stack, and boundary basis. Test any narrow geometry screen against pad-connected, unconnected, wrong-plane, DNP, and datasheet-supported alternatives. Stop if via count or density is presented as thermal adequacy without an independently reviewed model.                                                                                                         |

**EG-001 source review (2026-10-10):** The pinned
[kicad-happy `check_esd_coverage_gaps` source](https://github.com/aklofas/kicad-happy/blob/06840467ad0f5d76af45f64449b1f5ecb10f052f/skills/kicad/scripts/cross_analysis.py)
collects detected protection nets globally, then prompts for each recognized
connector signal net absent from that set and recommends adding TVS/ESD. The
predicate has no explicit `not_required` disposition or connector-pin
protection map, does not inspect DNP state, and does not establish entry-local
PCB protection. LINT-034 already has synthetic declared, undeclared,
`not_required`, wrong-net, wrong-identity, and DNP cases; this change adds an
explicit alternate mapped-protector control. No candidate code was installed
or run. This is a source review, not a runtime comparison or a claim about
field precision.

**DA-001 source review (2026-10-10):** The pinned
[kicad-happy `check_decoupling_adequacy` source](https://github.com/aklofas/kicad-happy/blob/06840467ad0f5d76af45f64449b1f5ecb10f052f/skills/kicad/scripts/cross_analysis.py)
counts decoupling capacitors and ICs on each reported rail, then recommends at
least one 100 nF capacitor per IC when the counts differ. It does not evaluate
capacitance value, pin-pair coverage, fitted state, shared banks, placement, or
project-approved alternatives in this predicate. LINT-046 reviews capacitor
presence and LINT-020 measures project-mapped placement and optional connected
return-via distance. LINT-136 adds a distinct opt-in comparison only when a
project authors the exact IC power pin, capacitor set, source basis, and
minimum. It does not adopt the cohort's universalized threshold. No candidate
code was installed or run.

No candidate code, installation workflow, project design, or example fixture
is adopted by this audit. Candidate runtime evidence remains under LINT-031;
documentation descriptions alone do not count as a detection gain.

### Domain-specific cohort backlog candidates

The public [kicad-happy changelog](https://github.com/aklofas/kicad-happy/blob/main/CHANGELOG.md)
lists additional domain families. This inventory does not demonstrate local
detection value. LINT-097 is now an implemented, opt-in project-authored check;
the rows below are conditional research leads. Advance a remaining candidate
only when its project-specific source data, applicability, deterministic
comparison, and valid alternatives can be tested without importing a product
design.

| Candidate family                                     | Existing overlap                                                              | First bounded work                                                                                                                                                                                                                                          | Stop or defer when                                                                                                                                                                                                                    |
| ---------------------------------------------------- | ----------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Wireless module antenna and RF feed review           | Covered by implemented opt-in LINT-097                                        | No extra check from KO-001 review; keep its project map and synthetic fault/control suite. Reconsider only if a runtime trial shows a distinct, bounded gap.                                                                                                | Defer if exact module identity, vendor-backed geometry, or module-versus-external-antenna distinction is unavailable.                                                                                                                 |
| Transformer-isolated converter feedback topology     | LINT-036 regulator feedback and LINT-034 interface/protection contracts       | Trial an authored map for exact controller feedback pins, optocoupler/secondary reference parts, and expected connectivity. Use source-bound device limits only for explicit comparisons; do not label topology matching as loop-stability proof.           | The candidate depends on generic component-name guesses, copied reference designs, or undocumented compensation assumptions; the local check duplicates a source-bound feedback contract without clearer findings.                    |
| Supercapacitor and energy-storage operating envelope | LINT-064 voltage ratings, LINT-071 power ratings, and power-path maps         | Inventory the distinct requirement fields needed for exact storage-part identity, working voltage, charge/discharge path, and owner-authored operating bounds. Build fault/control cases only after selecting a narrow source-backed use case.              | Safe charge current, inrush, hold-up, life, or energy behavior would be inferred from symbol connectivity without part-specific ratings, state assumptions, and reviewed calculations.                                                |
| PWM LED driver-to-load topology                      | LINT-048 direct LED assignment and LINT-063 output-driven LED path review     | The explicit power map now covers two synthetic channels: both exact A-to-K paths suppress their prompts, while a partial map leaves the unmatched channel reviewable. One- and two-channel native source fixtures are registered for KiCad 10.0.0/10.0.5.  | The proposal merely rediscovers a directly driven LED, assumes PWM means a missing resistor, or needs current/brightness limits that the project has not supplied. The mapped role does not establish current regulation or adequacy. |
| Audio jack switch-contact state                      | LINT-001 connector coverage and LINT-069 project-authored custom-symbol roles | Trial a project-owned exact connector pin/state map for inserted and removed plug states, with fixtures for normal-open/normal-closed contacts and intentionally unused pins. First prove the native source contains enough identity and pin data.          | KiCad schematic connectivity cannot represent the mechanical state, the library switch pins lack reviewed identities, or the tool would need to infer an audio circuit from reference/value naming.                                   |
| Symbol-library convention admission                  | Board design lint does not validate symbol-library authoring conventions      | LINT-031's pinned KLC S5.1 trial detects its upstream fault/control pair, but warns on a valid generic `Connector` symbol. Consider a separate optional library-admission preflight only if custom or supplier library intake becomes an explicit workflow. | Keep outside electrical design lint; KLC permits exceptions and manual review, and the current checker misclassifies generic Connector libraries.                                                                                     |

#### kicad-happy TF-001 isolated-feedback trial (2026-10-19)

- **Pinned source:** Release `v2.3.1`, commit
  [`06840467ad0f5d76af45f64449b1f5ecb10f052f`][tf001-commit], under the
  declared MIT license. The detector-level function is
  [`detect_transformer_feedback`][tf001-source].
- **Trial:** A tooling-owned in-memory probe called the exact pinned function
  three times with synthetic component and pin-net contexts. It repeated each
  result and compared the records for stability. The matching keyword case
  returned an optocoupler and TL431 finding with `deterministic` confidence,
  despite there being no transformer component in the context. The
  controller-only anti-control still returned a TF-001 isolated-SMPS record
  with no optocoupler or TL431. A role-agnostic pin mapping also returned a
  `deterministic` TF-001 association, although the provided optocoupler and
  TL431 pin names did not match the roles described by the report.
- **Scope:** This is an implementation-level runtime probe, not a parser, CLI,
  native KiCad export, public-board screen, or reviewer measurement. Its
  synthetic contexts and reproduction runner are retained in
  [`cohort-transformer-feedback`](../tests/fixtures/design_lint/cohort-transformer-feedback/README.md).
  No cohort code, product schematic, or board fixture was copied into the
  tooling package.
- **Disposition:** Defer adoption. TF-001 adds topology classification, but
  this trial did not show a unique defect or coverage result over source-bound
  project requirements. The controller-only and role-agnostic results show
  that its labels and confidence overstate the evidence for these synthetic
  cases. LINT-036 and project-authored pin/path contracts remain the exact
  requirements surface; any future broad review hint needs stronger
  applicability controls and a valid-control matrix before adoption.

[tf001-commit]: https://github.com/aklofas/kicad-happy/commit/06840467ad0f5d76af45f64449b1f5ecb10f052f
[tf001-source]: https://github.com/aklofas/kicad-happy/blob/06840467ad0f5d76af45f64449b1f5ecb10f052f/skills/kicad/scripts/domain_detectors.py#L5839-L5892

#### LINT-133 implementation status: capacitive touch-pad clearance

LINT-133 now screens a project-mapped exact pad-to-filled-zone distance against
an independently authored minimum. It uses the native effective pad shape and
source-bound filled copper, and reports incomplete evidence instead of
guessing from `TP`, a footprint name, a sampled point, or a bounding box. The
synthetic fault/control, threshold metamorphic case, missing-evidence cases,
and CLI/MCP parity are implemented. Exact-version native fixtures are coded
for KiCad 10.0.0 and 10.0.5; both versions passed the hosted native fixture
stage on `v0.5.0rc248` (GitHub Actions run `38394572077`). The full scoped gate
passed on `v0.5.0rc249` (run `38395063701`), including the installed-wheel
check. The rotated versus unrotated oval geometry regression passed on both
pinned KiCad versions in `v0.5.0rc250` (run `38396108362`). A new native
comparison now repeats DRC on the same fixture, compares normalized violation
evidence, and asserts that the project-map minimum can report a clearance
review when KiCad's default clearance emits no finding; both pinned versions
passed in `v0.5.0rc251` (run `38397569065`). The plated through-hole fault and
inclusive-boundary control, with 1.0 mm native gaps, passed both pinned
versions and the full scoped acceptance in `v0.5.1rc38` (run `39314208147`).
Independent public or synthetic applicability and reviewer-value evidence also
remain open. No universal clearance value or new project requirement is
inferred.

#### Preliminary source audit: antenna keepout coverage (2026-10-08)

A pinned source inspection of
[kicad-happy `analyze_pcb.py` at `a6bba1a`][happy-pcb-analysis]
and its [PCB layout guidance][happy-pcb-layout]
found a useful idea but not a reusable antenna-coverage check. The guidance
calls for vendor-sourced antenna-area geometry and copper keepout coverage on
the relevant layers. Its inspected `KO-001` implementation checks component
and via center points against the bounding box of an already-present keepout;
that predicate cannot find a missing antenna keepout, verify its exact outline,
or bind the area to an RF pad and module identity. The implementation reports
those findings with error severity, so its disposition is not a suitable local
default.

LINT-097 is now implemented as an opt-in, project-authored map of exact module
identity, RF feed pad/net, antenna disposition, and module-local keepout
polygons. The shared native PCB probe supplies footprint transforms; the
analyzer compares transformed geometry and restrictions with the source-bound
rule area. Default disposition is `REVIEW`, with project policy able to select
`block` or `off` and an exact fingerprint ignore. LINT-096 continues to cover
global named rule-area signature regression. No cohort code, dependency,
project source, or proprietary fixture was copied; no kicad-happy runtime trial
is claimed here.

These candidates were transcribed from public domain-detector descriptions
reviewed on 2026-10-01. They need exact cohort revision pins and isolated
synthetic runtime comparisons under LINT-031 before implementation planning;
their presence here does not recommend adopting `kicad-happy` or adding its
runtime dependency.

The inspected public repositories identify ThomsonLint, kicad-happy, and
pcb-inspector as MIT-licensed; KiDiff v2.6.0 declares GPL-2.0; kicad_skills
declares Apache-2.0. This branch
records their ideas and source links; it does not copy their implementations,
bundled examples, project data, or installation workflows. Read-only runtime
trials for kicad-happy, kicad-sch-lint, pcb-inspector, kilint, and KiDiff are
recorded under LINT-031. The kicad_skills `analog.no_dc_path` trial also found
no unique detection and did not justify an analyzer dependency. Other candidate
runtime trials remain open.

- **[kicad-sch-lint](https://github.com/rashuky/kicad-sch-lint):** Documents
  KiCad 10 schematic geometry checks for pin-line near misses, floating
  labels, dangling wires, junctions, body/wire overlaps, and transformed pin
  tips; its workflow also includes text repair. Use its reported check classes
  to sharpen LINT-024 synthetic fixtures. Rebuild only read-only, source-bound
  checks; leave mutation out. Compare actionable localization with native ERC
  before calling it new detection.
- **[kicad-happy](https://github.com/aklofas/kicad-happy):** Documents
  deterministic schematic extraction and detector families for dividers,
  regulator feedback, oscillators, protection, buses, voltage domains, and
  sequencing, followed by a separate agent review. Its protection-coverage
  concept informed the independent LINT-034 contract and synthetic tests; its
  documented crystal detector family informed LINT-035. No source code,
  project data, skill, plugin, or runtime dependency was imported. The documented
  divider equation informed LINT-036, whose explicit map avoids the upstream
  part-name Vref lookup and fallback heuristic. Its `validate_spi_bus` PR-002
  missing-chip-select-pull-up review check informed LINT-045, which narrows
  applicability to explicitly active-low native input pins and fitted
  resistor-path evidence. The LINT-031 runtime trial matched the missing-bias
  and fitted 10 kΩ cases but accepted DNP 10 kΩ and 0 Ω anti-controls; it added
  no detection beyond the local rule. The USB `validate_usb_bus` PR-004
  series-resistor detector was also run under LINT-031 and deferred to LINT-049
  pending PHY-specific applicability. A v2.1.0 USB-C CC trial is also recorded
  under LINT-031: it matched simple source/sink controls but treated an unknown
  role as missing sink pull-downs, adding no unique value over LINT-053/LINT-012.
  LINT-037 and LINT-038 now have separate independent implementations; other
  detector families remain unverified until they have bounded predicates and
  synthetic fault/control evidence. Its v2.2.1 changelog also describes a
  `checks_run` manifest for cross-analysis, with explicit reasons for skipped
  checks and examined-item counts, plus surfaced connectivity-graph errors and
  skipped conditional DRC rules. The pure `run_all_checks` function was run
  from source at the pinned v2.2.1 commit on two empty synthetic inputs; it
  returned deterministic ten-entry manifests with explicit skip reasons but
  zero examined items and findings. The trial confirmed observability only and
  added no demonstrated local detection or review coverage. It is recorded
  under LINT-076; Tooling did not install the candidate or run its CLI/workflow.
  Its broader installation and review workflow is not required for these typed
  checks.
  Other detector families are not considered verified from documentation
  alone.
- **[pcb-inspector](https://github.com/takzen/pcb-inspector):** Documents
  configurable spatial rules for decoupling, copper width, differential pairs,
  switching loops, and return references. Selected decoupling source uses a
  nearest-pad Euclidean-distance threshold. Compare these metrics under
  LINT-020 through LINT-025. Distance is not loop inductance or copper
  continuity; preserve the measured quantity and avoid stronger claims than
  the evidence supports.
- **[kilint](https://github.com/romkey/kilint):** Documents project-level
  opt-in rule configuration, per-item disables, I2C pull-up resistor-network
  configuration, and style/documentation checks. The project describes itself
  as early alpha. A read-only README recheck on 2026-09-30 says configured
  `R`/`RN` prefixes can identify pull-ups from KiCad PCB pad-net assignments;
  the README observation is documentation review, while the separate LINT-031
  runtime trial below evaluates its direct and series-chain behavior.
  LINT-010 now supports a project-authored, exact resistor-array channel map
  and resolves the matching schematic hint only when the source-bound checks
  pass. This is an independent implementation, not adopted kilint code or a
  runtime dependency. The LINT-031 runtime trial of version 0.5.1 found a unique
  synthetic review prompt for an undeclared U-prefixed I2C responder; LINT-042
  independently implements the coverage prompt from native pin functions and
  project map entries. A separate LINT-031 v0.5.1 pad-net trial found that the
  candidate warns on an unbranched two-resistor SDA chain accepted by Tooling's
  source-bound heuristic; its rule only checks for a direct signal-to-power
  resistor pad assignment. Tooling retains series-path coverage independently.
  Metadata conventions are lower priority than electrical regression coverage.
  Do not reuse its project ignore format without checking this repository's
  fingerprinted review lifecycle.
- **[ThomsonLint](https://github.com/holla2040/ThomsonLint):** Provides
  engineering rule knowledge and applicability guidance. Keep it as curated
  source material for LINT-030. Convert a rule into a deterministic predicate
  and synthetic fault/control pair before adding it to the active catalog.
- **[KiDiff](https://github.com/INTI-CMNB/KiDiff):** Provides visual comparison
  of schematic and PCB revisions. The LINT-031 v2.6.0 trial highlighted
  synthetic common-to-split return-label edits but added no electrical
  detection; it does not infer whether the split is intentional. Treat it only
  as an optional review aid under LINT-024, with no runtime dependency or
  verification credit.

Continue cohort trials on synthetic projects with controlled faults and valid
alternatives. Record tool commit/version and install procedure, then compare
confirmed findings, duplicates, missed faults, false positives, localization
effort, and maintenance cost. Existing runtime results are fixture-specific:
they support bounded review hypotheses, not field effectiveness or approval of
a candidate implementation. Keep false-positive rate, reviewer effort, and
maintenance cost open wherever they were not measured.

## Suggested delivery order

1. Maintain the implemented rule catalog and synthetic fault/control fixtures.
   The LINT-054 baseline now covers all active rules; classify every added rule
   with an executable metamorphic case or reasoned not-applicable basis, and
   add further axes when evidence warrants. Connector discovery remains a
   candidate-generating heuristic, and project intent remains in project-owned
   contracts. LINT-083 keeps optional peer-comparison scopes source-matched and
   restores broad comparisons whenever a participating connector review is
   stale or incomplete.
2. Keep LINT-077's exact-version native lane in GitHub CI. The local KiCad
   10.0.0/10.0.5 exports now repeat with matching normalized netlist/ERC
   evidence; before a project adopts this check, its owner must source and
   review the exact contact limits and per-contact load. Keep copper-ampacity
   work deferred until its physical and current-allocation model has a reviewed
   basis.
   Keep LINT-087's serial reference-bond control and broken-bond fault in the
   exact KiCad 10.0.0/10.0.5 GitHub acceptance lane. The tagged
   `v0.5.0rc15` run (`37851810081`) passed both cases on both versions; retain
   that lane for future changes to the bond contract or native fixture.
3. Keep partial `LINT-010` through `LINT-012` aligned with their actual
   evidence boundaries. LINT-011 now checks the optional split midpoint
   capacitor map from a native schematic export as well as typed contract
   cases; physical bus-end placement and switchable or external termination
   remain outside the schematic contract. LINT-012 already tests
   controller-managed CC and an optional authored VBUS chain; debug-accessory
   behavior is unsupported, and the chain does not prove component conduction
   or PCB/contact continuity. Add coverage only when a reviewed requirement
   supplies a concrete deterministic check.
4. Keep LINT-024's eleven bounded geometry rules opt-in. The current inventory
   already covers the documented near-pin, junction, label, text, and symbol
   body classes with fault/control and native comparisons. The next LINT-024
   work is to measure false positives and reviewer effort on supported,
   non-proprietary examples; expand glyph or geometry support only when a
   concrete fault/control case demonstrates value. Use LINT-044's enabled-rule
   coverage and do not use incomplete text samples for false-positive-rate
   claims.
5. Measure review value for implemented default-REVIEW rules, beginning with
   LINT-086's USB split-reference prompt, then LINT-061/066 digital-peer
   voltage prompts and LINT-063 LED-output prompts. LINT-086 recognizes direct
   USB 2.0 paths or one fitted `Device:R` per data line, same-net USB-C A/B
   contacts, bounded two-pin D-designated shunts, and one exact direct USB
   SuperSpeed P/N pair per endpoint family. Count only supported connector-to-IC
   pairs and record whether the review found missing, intentionally separate,
   or already bonded reference policy. The public CP2102, USB-C FUSB302/RP2040,
   and 16nx projects are common-reference non-finding screens. Synthetic split
   mutations demonstrate prompt behavior; these screens do not measure
   precision or reviewer effort.
   Use supported, nonconfidential examples and record useful findings, false
   positives, seeded misses, and reviewer effort; keep project defaults
   unchanged until that evidence is reviewed. Keep LINT-062 opt-in until
   project owners review exact sequence maps; keep numeric timing checks
   deferred until source-backed requirements and boundary fixtures exist.
   LINT-083 supplies a configurable connector comparison boundary, but does not
   count as a precision measurement for any default-REVIEW rule.
6. Run the controlled candidate trials in `LINT-031` against synthetic faults
   and valid alternatives. Record incremental findings, false positives,
   missed cases, localization effort, and maintenance cost before adopting a
   cohort implementation or adding the adapter contract in `LINT-032`. For new
   domain checks, LINT-075's no-CLI oscillator-output trial is recorded. The
   LINT-133 implements the bounded CP-003 touch-pad clearance concept behind
   an exact project-authored minimum and native pad-geometry measurement. The
   round/oval native lane and full scoped acceptance passed on
   `v0.5.0rc249`; the rotated-pad geometry regression passed on both pinned
   KiCad versions in `v0.5.0rc250`; the repeated DRC comparison passed on both
   pinned versions in `v0.5.0rc251`. The plated through-hole fault and exact
   boundary control then passed on both pinned versions, with the scoped gate
   and installed-wheel check passing in `v0.5.1rc38` (run `39314208147`).
   Project applicability evidence remains open.
   Any first-party path contract still needs native netlist
   evidence and a project-authored requirement map before implementation. The
   other domain-specific cohort families above remain conditional research
   items.
7. LINT-076 now covers mapped-check execution plus bounded applicability
   counts for LINT-066's direct-peer voltage heuristics, LINT-086's USB
   peer-reference heuristic, LINT-074's direct serial reference review, and
   connector and component peer-pin comparisons. The component peer coverage
   summaries make exact-symbol and shared-`PART_ID` groups, pin metadata
   eligibility, and assignment states visible even when a checker has no
   finding to emit.
   Continue it only when an audit identifies another enabled check that can
   silently skip without a matching coverage report or finding; do not add a
   global status registry that only restates the catalog.
   Add a new
   cohort-derived electrical check only after its applicability, deterministic
   predicate, fault/control fixtures, and incremental-value hypothesis are
   recorded. `LINT-033` through `LINT-067` have synthetic implementations or
   explicitly documented remaining limits. LINT-049's project-mapped
   connector-to-PHY topology comparison is implemented with integrated-PHY
   and external-resistor controls. Adoption of the cohort's generic
   resistor-presence prompt remains deferred because its trial flags both
  documented PHY classes; any future generic prompt needs part-specific
  applicability evidence and measurable value under LINT-031. LINT-064 is
  implemented and synthetically verified; project-level adoption still needs
   owner-reviewed exact-part rating and stress sources. LINT-066 is
   synthetically implemented and repeated-export validated on exact KiCad
   10.0.0/10.0.5 for SPI and UART/USART; non-proprietary reviewer-value
   measurements remain open.
   LINT-067 adds a default-review cross-peer CANH/CANL assignment prompt; native
   synthetic fault/control exports pass without ERC errors on the same pinned
   versions. The expected isolated-library warnings are documented. LINT-071
   adds a source-bound component power-rating comparison; synthetic contract,
   CLI/MCP, retained-evidence replay, and repeated native exports on KiCad
   10.0.0 and 10.0.5 pass. Project adoption still needs owner-reviewed exact-
   part rating and stress sources. LINT-072 adds serial-roster coverage; its
   omitted, partially mapped, and fully mapped synthetic native cases repeat
   on those same KiCad versions. Reviewer effort and false-positive rates
   remain open for both rules.

## Completion and release gate

A backlog item is complete only when its evidence adapter and exact version
boundary are documented, its fault and valid-control fixtures run in CI, its
limitations and false-positive cases are stated, and its report is reproducible
and source-bound. If it adds a CLI or MCP operation, the typed service,
surface map, parity test, package smoke suite, and installed-wheel test against
an external checkout are part of the change. Generated receipts remain under
ignored `build/` directories.

Passing these checks means the declared tooling conditions were met. It does
not establish electrical approval, manufacturing readiness, PCB fabrication
quality, or first-article continuity.

[thomson-kicad-review]: <https://github.com/holla2040/ThomsonLint/blob/main/docs/KiCad_Review_Guide.md>
[happy-crystal-detector]: https://github.com/aklofas/kicad-happy/blob/main/skills/kicad/scripts/signal_detectors.py#L818-L950
[happy-datasheets]: <https://github.com/aklofas/kicad-happy#-datasheets--sync-and-extract>
[happy-lb001]: https://github.com/aklofas/kicad-happy/blob/a6bba1add1e18b89e3aa0824b9769ed1d9d79174/skills/kicad/scripts/signal_detectors.py#L4367-L4440
[happy-changelog]: https://github.com/aklofas/kicad-happy/blob/main/CHANGELOG.md
[happy-analyzer]: https://github.com/aklofas/kicad-happy/blob/main/skills/kicad/scripts/signal_detectors.py#L3633-L3673
[kicad-device-library]: https://kicad.github.io/symbols/Device.html
[kicad-thermistor-symbol-10.0.5]: <https://gitlab.com/kicad/libraries/kicad-symbols/-/blob/10.0.5/Device.kicad_symdir/Thermistor.kicad_sym>
[kicad-thermistor-ntc-symbol-10.0.5]: <https://gitlab.com/kicad/libraries/kicad-symbols/-/blob/10.0.5/Device.kicad_symdir/Thermistor_NTC.kicad_sym>
[happy-thermal-v231]: <https://github.com/aklofas/kicad-happy/releases/tag/v2.3.1>
[happy-thermal-source]: <https://github.com/aklofas/kicad-happy/blob/06840467ad0f5d76af45f64449b1f5ecb10f052f/skills/kicad/scripts/analyze_thermal.py>
[happy-uc-releases]: https://github.com/aklofas/kicad-happy/releases
[usb-c-spec-release]: https://www.usb.org/document-library/usb-type-cr-cable-and-connector-specification-release-25
[usb-cap-fixture-readme]: ../tests/fixtures/design_lint/usb-c-vbus-capacitance-native/README.md
[happy-pcb-analysis]: <https://github.com/aklofas/kicad-happy/blob/a6bba1add1e18b89e3aa0824b9769ed1d9d79174/skills/kicad/scripts/analyze_pcb.py>
[happy-pcb-layout]: <https://github.com/aklofas/kicad-happy/blob/main/skills/kicad/references/pcb-layout-analysis.md>
[happy-pcb-methodology]: https://github.com/aklofas/kicad-happy/blob/main/skills/kicad/scripts/methodology_pcb.md
[happy-cross-verify]: https://github.com/aklofas/kicad-happy/blob/main/release-notes.md
[kicad-skills-pcb]: <https://github.com/sabas0ba/kicad_skills/blob/main/docs/guides/kicad-pcb-review.md>

[calcumaker-hardware]: https://github.com/calcumaker/calcumaker/tree/113a283/hardware
[antmicro-cm4]: https://github.com/antmicro/cm4-baseboard/tree/d248c2921e8e7f4c9b30c96ea5f376d9b2780f1e
[cynthion-hardware]: https://github.com/greatscottgadgets/cynthion-hardware/tree/13aa71c2fb0be3837cd2ec580ee5d2c25fc1c678
[cynthion-license]: https://github.com/greatscottgadgets/cynthion-hardware/blob/13aa71c2fb0be3837cd2ec580ee5d2c25fc1c678/LICENSE
[stickhub-schematic]: https://github.com/rbtsco/StickHub/blob/5f369a785bedc4b1d3b99222c841ac684e04f016/StickHub.kicad_sch
[stickhub-license]: https://github.com/rbtsco/StickHub/blob/5f369a785bedc4b1d3b99222c841ac684e04f016/LICENSE.md
[usb-sleuth]: https://github.com/smaroukis/usb-sleuth/tree/6ecdcfdd4bbb30c7d143cdca862ee048d6409ab1
[usb-sleuth-readme]: https://github.com/smaroukis/usb-sleuth/blob/6ecdcfdd4bbb30c7d143cdca862ee048d6409ab1/README.md
[usb-sleuth-license]: https://github.com/smaroukis/usb-sleuth/blob/6ecdcfdd4bbb30c7d143cdca862ee048d6409ab1/LICENSE
[st-usb-uart-isolation]: https://www.st.com/resource/en/user_manual/um2945-getting-started-with-the-stevalpcc020v2-usb-to-ic-uart-interface-board-for-stnrg01x-products-stmicroelectronics.pdf
[dstat-pcb]: https://microfluidics.utoronto.ca/gitlab/mdryden/dstat-hardware/-/raw/b6b2bbfdb7f8b2997d3035b083edbab2348333dc/dstat-mainboard.kicad_pcb
[happy-cross-analysis]: <https://github.com/aklofas/kicad-happy/blob/06840467ad0f5d76af45f64449b1f5ecb10f052f/skills/kicad/scripts/cross_analysis.py>
[pcbdraft-rc-fixture]: https://github.com/qixuancao/pcbdraft/blob/a19485657383934de8e9a8a8029795165f12eb14/examples/results/2026-09-09-single-attempts/cases/rc-1k-100nf/native/rc-1k-100nf-9e558fd9.kicad_sch
[pcbdraft-i2c-fixture]: https://github.com/qixuancao/pcbdraft/blob/a19485657383934de8e9a8a8029795165f12eb14/examples/results/2026-09-09-single-attempts/cases/i2c-3v3-pullups/native/i2c-3v3-pullups-a844fc2a.kicad_sch
[pcbdraft-led-fixture]: https://github.com/qixuancao/pcbdraft/blob/a19485657383934de8e9a8a8029795165f12eb14/examples/results/2026-09-09-single-attempts/cases/led-3v3-330r/native/led-3v3-330r-308123ef.kicad_sch
[kicad-thermistor-ptc-symbol-10.0.5]: <https://gitlab.com/kicad/libraries/kicad-symbols/-/blob/10.0.5/Device.kicad_symdir/Thermistor_PTC.kicad_sym>
[kicad-thermistor-us-symbol-10.0.5]: <https://gitlab.com/kicad/libraries/kicad-symbols/-/blob/10.0.5/Device.kicad_symdir/Thermistor_US.kicad_sym>
[kicad-thermistor-ntc-us-symbol-10.0.5]: <https://gitlab.com/kicad/libraries/kicad-symbols/-/blob/10.0.5/Device.kicad_symdir/Thermistor_NTC_US.kicad_sym>
[kicad-thermistor-ptc-us-symbol-10.0.5]: <https://gitlab.com/kicad/libraries/kicad-symbols/-/blob/10.0.5/Device.kicad_symdir/Thermistor_PTC_US.kicad_sym>

[kicad-10-drc]: https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html#drc-configuration
[kicad-10.0.0-drc-items]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.0/pcbnew/drc/drc_item.cpp
[kicad-10.0.5-drc-items]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.5/pcbnew/drc/drc_item.cpp
[kicad-10-drc-exclusions]: https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html#design-rule-checking
[kicad-10-project-drc-exclusions]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.7/pcbnew/board_design_settings.cpp
[lint086-cp2102]: https://github.com/MAATHES-THILAK-K/USB_TO_UART-CP2102
[lint086-fusb302]: https://github.com/bentwire/USB-C-FUSB302-PI/tree/7d95292262b42767bbeefebadb6bafe055923d50
[lint086-16nx]: https://github.com/16n-faderbank/16nx/tree/ca7de2233011407fdd791839d711547bf41d33d3
