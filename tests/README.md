# Tooling regression tests

Install the [development environment](../README.md#development-check) before running these tests.
It uses `python -m pip install -e '.[dev,cad]'` from this tooling checkout in an active virtual
environment; the project-facing extras alone do not install Ruff, Pyright or package build tools.
The shared Python regression suite belongs to this repository. Board contracts,
firmware checks, and product integration tests remain in their project repository.
Pytest is the canonical test runner. Write new tests as `test_*` functions using
plain `assert`, pytest fixtures, and parametrization where they clarify cases.
Do not add new `unittest.TestCase` tests. Existing `TestCase` tests remain
supported while we migrate the suite incrementally, prioritizing lint and
verification coverage. Convert the touched regression tests to pytest functions
when extending a legacy suite. `unittest.mock` remains useful with pytest.

The schematic-to-PCB pad-net native fault and control are synthetic tooling
fixtures; their source boundary and pinned hashes are recorded in the
[fixture README](fixtures/design_lint/schematic-pcb-pad-net/README.md).
The named connector supply/return pin fault and control are also synthetic
tooling fixtures; their source boundary and pinned hashes are recorded in the
[connector pin fixture README](fixtures/design_lint/unconnected-named-connector-pins/README.md).
The non-connector named supply/return-pin faults and assigned control have a separate
[component pin fixture README](fixtures/design_lint/unconnected-named-component-pins/README.md) and
a focused native lane per rule.
The named peer power-input assignment-divergence fault and control are synthetic tooling
fixtures; their source boundary and pinned hashes are recorded in the
[peer power-input fixture README](fixtures/design_lint/named-peer-power-input-divergence/README.md).
The all-open named peer power-input fault and control are separate synthetic tooling fixtures;
their source boundary and pinned hashes are recorded in the
[all-open peer power-input fixture README](fixtures/design_lint/named-peer-power-input-all-open/README.md).
The schematic wire/body pin-endpoint review candidate and clear control are recorded in the
[body pin-endpoint fixture README](fixtures/design_lint/schematic-body-pin-endpoints/README.md).
Native footprint-alias review fixtures also cover named power-input and power-output pins,
named signal-input and signal-output pins, and named-signal assignment divergence. Their
individual READMEs describe the synthetic fault/control topology and pinned source hashes:
[power input](fixtures/design_lint/connector-footprint-named-power-input-native/README.md),
[power output](fixtures/design_lint/connector-footprint-named-power-output-native/README.md),
[signal input](fixtures/design_lint/connector-footprint-named-signal-input-native/README.md),
[signal output](fixtures/design_lint/connector-footprint-named-signal-output-native/README.md),
and
[signal assignment divergence](fixtures/design_lint/connector-footprint-named-signal-divergence-native/README.md).
Named connector power-output peer tests can be selected independently; the native case uses
tooling-owned aliases and digest-pinned KiCad fixtures:

```sh
KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1 .venv/bin/python -I -B -m pytest -q \
  -m 'design_lint_rule(rule_id="connector.peer_power_output_named_all_open")' \
  tests/test_design_lint_connector_named_power_output_peers.py \
  tests/test_design_lint_mcp_parity_connector_named_power_peers.py \
  tests/test_connector_named_power_output_native_fixture_lane.py
```

Fully assigned named power-output aliases on distinct nets have a separate
review selector and synthetic/native regression module:

```sh
KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1 .venv/bin/python -I -B -m pytest -q \
  -m 'design_lint_rule(rule_id="connector.peer_power_output_named_assignment_divergence")' \
  tests/test_design_lint_connector_named_power_output_divergence.py \
  tests/test_design_lint_mcp_parity_connector_named_power_peers.py \
  tests/test_connector_named_power_output_native_fixture_lane.py
```

Fully assigned named power-input aliases on distinct nets have a parallel
review selector and synthetic/native regression module:

```sh
KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1 .venv/bin/python -I -B -m pytest -q \
  -m 'design_lint_rule(rule_id="connector.peer_power_input_named_assignment_divergence")' \
  tests/test_design_lint_connector_named_power_input_divergence.py \
  tests/test_design_lint_mcp_parity_connector_named_power_peers.py \
  tests/test_connector_named_power_input_native_fixture_lane.py
```

The suite uses a separate public template checkout for its reference examples.
Set `KICAD_TEMPLATE_ROOT` to that checkout, then run from the tooling repository:

```sh
export KICAD_TEMPLATE_ROOT=/path/to/KiCad-Team-Workflow-Template
python -I -B -m pytest -q
```

For PowerShell, set the variable with
`$env:KICAD_TEMPLATE_ROOT = "C:\path\to\KiCad-Team-Workflow-Template"`.

Pytest collection does not copy or resolve that checkout. A marker-filtered
selection can therefore collect while the variable is unset; selected tests
that use the shared reference root still require the public checkout.
Run one module with `python -I -B -m pytest -q tests/test_product.py`.

Focused runs use registered markers. `tests/design_lint_test_markers.py`
assigns lint areas by test module; areas can overlap when a fixture checks more
than one concern. Active rule fixture references in the catalog also attach a
`design_lint_rule(rule_id=...)` marker, so one rule's fault, control,
metamorphic, CLI/MCP, and native cases can be selected together. Execution-cost
markers live in `tests/execution_test_markers.py`; mixed modules mark only the
test functions that actually run the exact native tool:

The BJT base-drive review has synthetic rule/policy tests and an exact-version
native source-export lane. Its native cases use only tooling-owned schematics:
direct NPN/PNP drive faults and a series-resistor control.

```sh
.venv/bin/python -I -B -m pytest -q tests/test_bjt_base_drive.py \
  -m 'design_lint and component_lint and design_lint_rule(rule_id="component.bjt_base_direct_drive")'
KICAD_RUN_NATIVE_COMPONENT_BASE_DRIVE_FIXTURES=1 \
  .venv/bin/python -I -B -m pytest -q tests/test_bjt_base_drive_native_fixture.py \
  -m 'design_lint and design_lint_rule(rule_id="component.bjt_base_direct_drive")'
```

The source-bound contract-coach tests are split by inspection/reporting and
capture/runner behavior. Select them without running unrelated tests with:

```sh
.venv/bin/python -I -B -m pytest -q -m 'design_lint and evidence_lint and slow' \
  tests/test_contract_coach_evidence.py tests/test_contract_coach_capture.py \
  --durations=10
```

```sh
python -I -B -m pytest -q -m \
  "design_lint and not native_kicad and not slow and not template_checkout" \
  --durations=20
python -I -B -m pytest -q -m "schematic_lint and not native_kicad and not slow"
python -I -B -m pytest -q -m "connector_lint and not native_kicad and not slow"
python -I -B -m pytest -q -m "return_path_lint and not native_kicad and not slow"
python -I -B -m pytest -q tests/test_design_lint_numbered_returns.py \
  -m "design_lint and connector_lint and return_path_lint"
python -I -B -m pytest -q -m "design_lint and connector_lint" \
  tests/test_electrical_connector_pin_contracts.py
python -I -B -m pytest -q -m \
  'design_lint_rule(rule_id="power.pin_function_net_role_conflict")'
.venv/bin/python -I -B -m pytest -q \
  -m "design_lint and power_lint and component_lint and not slow" \
  tests/test_power_pin_net_roles.py
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test KICAD_RUN_NATIVE_POWER_SEQUENCE_FIXTURES=1 \
  .venv/bin/python -I -B -m pytest -q \
  -m "design_lint and power_lint and native_kicad" \
  tests/test_power_sequence_native_fixture_lane.py
.venv/bin/python -I -B -m pytest -q \
  -m "design_lint and power_lint and parity_lint and slow" \
  tests/test_design_lint_mcp_parity_power_pin_roles.py
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test KICAD_RUN_NATIVE_POWER_PIN_NET_ROLE_FIXTURES=1 \
  .venv/bin/python -I -B -m pytest -q \
  -m "design_lint and power_lint and native_kicad" \
  tests/test_power_pin_net_role_native_fixture_lane.py
python -I -B -m pytest -q -m "design_lint and return_path_lint" \
  tests/test_electrical_return_contracts.py
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1 \
  .venv/bin/python -I -B -m pytest -q \
  -m "design_lint and connector_lint and return_path_lint and native_kicad" \
  tests/test_ci_hosted_connector_returns.py
KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1 .venv/bin/python -I -B -m pytest -q \
  -m 'design_lint_rule(rule_id="connector.unconnected_supply_pin")' \
  tests/test_ci_hosted_connector_returns.py
KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1 .venv/bin/python -I -B -m pytest -q \
  -m 'design_lint_rule(rule_id="connector.unconnected_return_pin")' \
  tests/test_ci_hosted_connector_returns.py
KICAD_RUN_NATIVE_COMPONENT_NAMED_SUPPLY_PIN_FIXTURES=1 \
  .venv/bin/python -I -B -m pytest -q \
  -m 'design_lint_rule(rule_id="component.unconnected_supply_pin")' \
  tests/test_component_named_supply_pin_native_fixture_lane.py
KICAD_RUN_NATIVE_COMPONENT_NAMED_RETURN_PIN_FIXTURES=1 \
  .venv/bin/python -I -B -m pytest -q \
  -m 'design_lint_rule(rule_id="component.unconnected_return_pin")' \
  tests/test_component_named_return_pin_native_fixture_lane.py
python -I -B -m pytest -q \
  -m 'design_lint_rule(rule_id="component.peer_power_input_assignment_divergence")' \
  tests/test_component_peer_power_input_divergence.py \
  tests/test_component_peer_power_input_native_fixture_lane.py \
  tests/test_peer_power_assignment_cli_mcp.py
python -I -B -m pytest -q \
  -m 'design_lint_rule(rule_id="component.peer_power_input_open_assignment")' \
  tests/test_component_peer_power_input_divergence.py \
  tests/test_component_peer_power_input_native_fixture_lane.py \
  tests/test_peer_power_assignment_cli_mcp.py
python -I -B -m pytest -q \
  -m 'design_lint_rule(rule_id="component.peer_power_input_named_assignment_divergence")' \
  tests/test_component_named_peer_power_input_divergence.py \
  tests/test_component_peer_power_input_native_fixture_lane.py \
  tests/test_peer_power_assignment_cli_mcp.py
python -I -B -m pytest -q \
  -m 'design_lint_rule(rule_id="component.peer_power_input_named_all_open")' \
  tests/test_component_named_peer_power_input_all_open.py \
  tests/test_component_named_peer_power_input_all_open_native.py \
  tests/test_peer_power_assignment_cli_mcp.py
.venv/bin/python -I -B -m pytest -q \
  -m "design_lint and component_lint and power_lint and slow" \
  tests/test_design_lint_determinism_power_input_peers.py
KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1 .venv/bin/python -I -B -m pytest -q \
  -m 'design_lint_rule(rule_id="net.numbered_returns")' \
  tests/test_numbered_return_native_fixture_lane.py
KICAD_RUN_NATIVE_DB9_RETURN_CONTRACT_FIXTURES=1 .venv/bin/python -I -B -m pytest -q \
  -m 'design_lint and connector_lint and return_path_lint and design_lint_rule(rule_id="connector.repeated_pin_function")' \
  tests/test_native_db9_return_contracts.py
python -I -B -m pytest -q -m "pcb_lint and not native_kicad and not slow"
.venv/bin/python -I -B -m pytest -q \
  -m "design_lint and pcb_lint" \
  tests/test_pcb_population_mismatch.py tests/test_pcb_component_inventory_mcp_parity.py
.venv/bin/python -I -B -m pytest -q \
  -m 'design_lint and pcb_lint and design_lint_rule(rule_id="pcb.schematic_pcb_pad_net_mismatch")'
.venv/bin/python -I -B -m pytest -q \
  -m 'design_lint_rule(rule_id="pcb.schematic_pcb_dnp_mismatch") and not native_kicad and not slow'
.venv/bin/python -I -B -m pytest -q \
  -m 'design_lint and pcb_lint and design_lint_rule(rule_id="pcb.board_only_footprint")' \
  tests/test_pcb_board_only_footprints.py tests/test_pcb_component_inventory_mcp_parity.py
.venv/bin/python -I -B -m pytest -q \
  -m 'design_lint and pcb_lint and design_lint_rule(rule_id="pcb.required_fitted_reference")' \
  tests/test_pcb_required_fitted_reference.py tests/test_pcb_component_inventory_mcp_parity.py \
  tests/test_pcb_component_inventory_native_fixture_lane.py
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test KICAD_RUN_NATIVE_PCB_FIXTURES=1 \
  .venv/bin/python -I -B -m pytest -q \
  -m 'design_lint_rule(rule_id="pcb.schematic_pcb_dnp_mismatch") and native_kicad' \
  tests/test_pcb_component_inventory_native_fixture_lane.py
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test KICAD_RUN_NATIVE_PCB_FIXTURES=1 \
  .venv/bin/python -I -B -m pytest -q \
  -m 'design_lint_rule(rule_id="pcb.schematic_pcb_dnp_mismatch") and native_kicad' \
  tests/test_pcb_variant_population_native_fixture_lane.py
# The named-variant lane uses fixed synthetic boards and checks both mismatch
# directions, a fitted control, and fail-closed handling when the board variant
# is absent.
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test KICAD_RUN_NATIVE_PCB_FIXTURES=1 \
  .venv/bin/python -I -B -m pytest -q \
  -m 'design_lint and pcb_lint and native_kicad and design_lint_rule(rule_id="pcb.schematic_pcb_pad_net_mismatch")' \
  tests/test_pcb_schematic_pad_net_native_fixture_lane.py
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test .venv/bin/python -I -B -m pytest -q \
  -m "design_lint and pcb_lint" \
  tests/test_pcb_access_fixture_lane.py tests/test_ci_hosted_pcb_fixture_schedule.py
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test KICAD_RUN_NATIVE_PCB_FIXTURES=1 \
  .venv/bin/python -I -B -m pytest -q \
  -m "design_lint and pcb_lint and native_kicad" \
  tests/test_pcb_access_native_fixture_lane.py
python -I -B -m pytest -q -m "design_lint and interface_lint" \
  tests/test_serial_participants.py tests/test_serial_participant_net_labels.py
python -I -B -m pytest -q -m "design_lint and interface_lint" \
  tests/test_electrical_i2c_contracts.py
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Team-Workflow-Template \
  python -I -B -m pytest -q \
  -m "design_lint and interface_lint and parity_lint" \
  tests/test_electrical_usb_c_parity.py
python -I -B -m pytest -q -m "design_lint and interface_lint" \
  tests/test_i2c_peer_reference_review.py tests/test_spi_peer_reference_review.py \
  tests/test_can_peer_reference_review.py tests/test_can_peer_reference_architecture.py
python -I -B -m pytest -q -m "design_lint and interface_lint" \
  tests/test_rs485_peer_reference_review.py tests/test_rs485_peer_reference_architecture.py
python -I -B -m pytest -q -m "architecture and design_lint and interface_lint" \
  tests/test_spi_peer_reference_architecture.py
KICAD_RUN_NATIVE_I2C_PEER_REFERENCE_FIXTURES=1 python -I -B -m pytest -q \
  -m "design_lint and interface_lint and native_kicad" \
  tests/test_i2c_peer_reference_native_fixture_lane.py
KICAD_RUN_NATIVE_SPI_PEER_REFERENCE_FIXTURES=1 python -I -B -m pytest -q \
  -m "design_lint and interface_lint and native_kicad" \
  tests/test_spi_peer_reference_native_fixture_lane.py
KICAD_RUN_NATIVE_CAN_PEER_REFERENCE_FIXTURES=1 python -I -B -m pytest -q \
  -m "design_lint and interface_lint and native_kicad" \
  tests/test_can_native_fixture_lanes.py::test_native_can_peer_reference_fault_and_control
KICAD_RUN_NATIVE_RS485_PEER_REFERENCE_FIXTURES=1 python -I -B -m pytest -q \
  -m "design_lint and interface_lint and native_kicad" \
  tests/test_rs485_peer_reference_native_fixture_lane.py
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Team-Workflow-Template \
  python -I -B -m pytest -q -m "design_lint and interface_lint and parity_lint" \
  tests/test_design_lint_mcp_parity_i2c.py::test_i2c_peer_reference_review_cli_mcp_parity \
  tests/test_design_lint_mcp_parity_spi_reference.py \
  tests/test_design_lint_mcp_parity_can_reference.py \
  tests/test_design_lint_mcp_parity_rs485_reference.py
python -I -B -m pytest -q -m "design_lint and interface_lint" \
  tests/test_electrical_spi_contracts.py
python -I -B -m pytest -q -m "design_lint and interface_lint" \
  tests/test_electrical_serial_contracts.py
python -I -B -m pytest -q -m "design_lint and interface_lint" \
  tests/test_electrical_can_termination.py tests/test_electrical_rs485_contract.py
python -I -B -m pytest -q -m "design_lint and power_lint" \
  tests/test_electrical_power_connectivity.py
python -I -B -m pytest -q tests/test_regulator_feedback.py \
  -m 'design_lint and power_lint'
python -I -B -m pytest -q tests/test_power_sequences.py \
  -m 'design_lint and power_lint'
python -I -B -m pytest -q tests/test_power_sequences.py \
  -m 'design_lint and power_lint' -k 'missing_net_identity and open-enable'
python -I -B -m pytest -q tests/test_power_paths.py \
  -m 'design_lint and power_lint'
python -I -B -m pytest -q tests/test_power_paths.py \
  -m 'design_lint and power_lint' -k 'missing_endpoint and open-source'
python -I -B -m pytest -q \
  -m 'design_lint_rule(rule_id="power.regulator_feedback_mismatch")'
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Team-Workflow-Template \
  python -I -B -m pytest -q -m "component_lint and evidence_lint and template_checkout" \
  tests/test_electrical_component_evidence.py
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Team-Workflow-Template \
  python -I -B -m pytest -q -m "connector_lint and evidence_lint and template_checkout" \
  tests/test_electrical_connector_evidence.py
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Team-Workflow-Template \
  python -I -B -m pytest -q -m "return_path_lint and evidence_lint and template_checkout" \
  tests/test_electrical_pcb_return_evidence.py
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Team-Workflow-Template \
  python -I -B -m pytest -q -m "pcb_lint and evidence_lint and template_checkout" \
  tests/test_electrical_test_access_evidence.py
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Team-Workflow-Template \
  python -I -B -m pytest -q -m "evidence_lint and template_checkout" \
  tests/test_electrical_evidence.py tests/test_electrical_digital_peer_evidence.py
KICAD_RUN_NATIVE_DIGITAL_PEER_FIXTURES=1 python -I -B -m pytest -q \
  -m "design_lint and interface_lint and native_kicad" \
  tests/test_ci_hosted_digital_peer_spi.py tests/test_ci_hosted_digital_peer_serial.py
KICAD_RUN_NATIVE_DIGITAL_PEER_FIXTURES=1 python -I -B -m pytest -q \
  -m "design_lint and component_lint and power_lint and native_kicad" \
  tests/test_ci_hosted_component_peer_power.py
python -I -B -m pytest -q -m "design_lint and interface_lint" \
  tests/test_external_protection_contract.py tests/test_external_protection_review.py
python -I -B -m pytest -q -m "design_lint and power_lint" \
  tests/test_power_sequences.py tests/test_power_sequence_cycles.py
python -I -B -m pytest -q -m architecture
python -I -B -m pytest -q -m "design_lint and template_checkout" --durations=20
python -I -B -m pytest -q -m native_kicad
python -I -B -m pytest -q -m "evidence_lint and native_kicad" \
  tests/test_empty_netlist_evidence_native_fixture_lane.py
KICAD_RUN_NATIVE_I2C_PULLUP_FIXTURES=1 python -I -B -m pytest -q \
  -m "design_lint and interface_lint and native_kicad" \
  tests/test_i2c_pullup_native_fixture_lane.py
KICAD_RUN_NATIVE_CAN_TERMINATION_FIXTURES=1 \
KICAD_RUN_NATIVE_CAN_PEER_FIXTURES=1 python -I -B -m pytest -q \
  -m "design_lint and interface_lint and native_kicad" \
  tests/test_can_native_fixture_lanes.py
KICAD_RUN_NATIVE_SERIAL_PEER_FIXTURES=1 python -I -B -m pytest -q \
  -m "design_lint and interface_lint and native_kicad" \
  tests/test_serial_peer_native_fixture_lane.py
KICAD_RUN_NATIVE_IC_RAIL_CAPACITOR_FIXTURES=1 python -I -B -m pytest -q \
  -m "design_lint and power_lint and native_kicad" \
  tests/test_ic_rail_capacitor_native_fixture_lane.py
KICAD_RUN_NATIVE_SERIAL_PEER_FIXTURES=1 python -I -B -m pytest -q \
  -m "design_lint and interface_lint and return_path_lint and native_kicad" \
  tests/test_serial_reference_bond_native_fixture_lane.py
python -I -B -m pytest -q tests/test_rc_filters.py -k disconnected-capacitor-return
python -I -B -m pytest -q tests/test_power_input_source_paths.py -k jumper
python -I -B -m pytest -q tests/test_digital_peer_spi_voltage_fixture_lane.py -k translator
```

The synthetic design-lint gate in one-command verification can be run with:

```sh
python -I -B -m pytest -q \
  -m "design_lint and connector_lint and template_checkout" \
tests/test_verify_design_lint.py
```

Shared synthetic CLI/MCP report and native-snapshot inputs are documented in
the [parity fixture record](fixtures/design_lint/mcp-parity/README.md).

## Synthetic fixture records

These notes identify the separate fixture inputs used by focused suites:

- [SuperSpeed fixture record](fixtures/design_lint/usb-superspeed-peer-reference-native/README.md)
- [Power-pin net-role native fault and control](fixtures/design_lint/power-pin-net-role-native/README.md)
- [Multi-bus contract parity netlist](fixtures/electrical/multi-bus-contract-parity/README.md)
- [Release-contract evidence netlist](fixtures/electrical/release-contract-evidence/README.md)
- [PCB access probe snapshot](fixtures/pcb-access-probe/README.md)
- [Pinned STM32 cohort parser comparison](fixtures/design_lint/cohort-stm32-pin-checker/README.md)

The first command runs the portable, non-slow design-lint group that is
self-contained. Tests that need the public template checkout carry the
`template_checkout` marker and use the separate command after setting
`KICAD_TEMPLATE_ROOT`. The area
markers select schematic, component, connector, interface, power, evidence,
PCB, return-path, or parity regressions; combine them with `-k` to select a test or
parametrized fault/control case. `native_kicad` selects exact-version fixtures and still
requires each fixture's documented version and environment settings. Markers
narrow local runs; the package acceptance gate continues to run the complete
suite. Add each new lint test module to its area in
`tests/design_lint_test_markers.py`; `tests/conftest.py` applies those markers and
keeps it in both the focused area and the portable `design_lint` selection.
External cohort source comparisons use the opt-in `cohort_trial` marker and run
only when their pinned source checkout is supplied through the documented
environment variable.

Hosted PCB geometry acceptance is split by theme; for example, run only the
synthetic decoupling placement or return-via checks with:

```sh
python -I -B -m pytest -q -m "design_lint and pcb_lint" \
  tests/test_pcb_decoupling.py tests/test_pcb_decoupling_return_vias.py
```

The schematic-to-PCB component inventory review checks missing placements and
exact footprint-ID differences. It has a fast synthetic/parity slice and
exact-version native source-bound fixtures:

```sh
.venv/bin/python -I -B -m pytest -q -m "design_lint and pcb_lint" \
  tests/test_pcb_component_inventory.py tests/test_pcb_component_inventory_mcp_parity.py
.venv/bin/python -I -B -m pytest -q \
  -m "design_lint and pcb_lint and slow" \
  tests/test_design_lint_determinism_pcb_component_inventory.py
KICAD_RUN_NATIVE_PCB_FIXTURES=1 .venv/bin/python -I -B -m pytest -q \
  -m "design_lint and pcb_lint and native_kicad" \
  tests/test_pcb_component_inventory_native_fixture_lane.py
```

The authored power-connectivity contract's source/load fault reports have a
separate cross-process determinism slice:

```sh
.venv/bin/python -I -B -m pytest -q \
  -m "design_lint and power_lint and slow" \
  tests/test_design_lint_determinism_power_connectivity.py
```

Shared hash-seed report tests can cover rules from several themes. Their catalog
references make the process-level report selectable with each asserted rule ID;
the module also carries every applicable area marker. Select one rule or one
theme slice without collecting unrelated tests:

```sh
.venv/bin/python -I -B -m pytest -q \
  -m 'design_lint and design_lint_rule(rule_id="connector.peer_pin_assignment_outlier")' \
  --durations=10
.venv/bin/python -I -B -m pytest -q \
  -m 'design_lint and connector_lint and slow' \
  tests/test_design_lint_determinism_component_peers.py --durations=10
```

The marker and collection architecture tests run in the focused `catalog_lint`
gate, so CI checks both catalog reachability and the selectors used to keep
that gate narrow.

The native decoupling fixture runs separately with:

```sh
python -I -B -m pytest -q -m "design_lint and pcb_lint and native_kicad" \
  tests/test_pcb_decoupling_native_fixture_lane.py
```

Native PCB return evidence is split into focused switching-loop, reference-plane,
and return-path suites. Select one theme without rerunning the other native
geometry lanes:

```sh
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test KICAD_RUN_NATIVE_PCB_FIXTURES=1 \
  .venv/bin/python -I -B -m pytest -q \
  -m "design_lint and pcb_lint and return_path_lint and native_kicad" \
  tests/test_pcb_reference_plane_native_fixture_lane.py
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test KICAD_RUN_NATIVE_PCB_FIXTURES=1 \
  .venv/bin/python -I -B -m pytest -q \
  -m "design_lint and pcb_lint and native_kicad" \
  tests/test_pcb_switching_loop_native_fixture_lane.py
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test KICAD_RUN_NATIVE_PCB_FIXTURES=1 \
  .venv/bin/python -I -B -m pytest -q \
  -m "design_lint and pcb_lint and return_path_lint and native_kicad" \
  tests/test_pcb_return_path_native_fixture_lane.py
```

The hosted PCB return lane also has a focused orchestration test. It uses
synthetic connectivity snapshots and the public template only for project
configuration; it does not run native KiCad:

```sh
python -I -B -m pytest -q \
  -m "design_lint and pcb_lint and return_path_lint and template_checkout" \
  tests/test_ci_hosted_pcb_return_paths.py
```

The digest-pinned USB data-path acceptance has its own interface suite. Set
`KICAD_TEMPLATE_ROOT` to the public template and enable its native lane with:

```sh
KICAD_RUN_NATIVE_USB_DATA_PATH_FIXTURES=1 python -I -B -m pytest -q \
  -m "design_lint and interface_lint and native_kicad" \
  tests/test_usb_data_path_native_fixture_lane.py
```

The bounded USB SuperSpeed peer-reference heuristic has a fast synthetic
fault/control and boundary suite:

```sh
.venv/bin/python -I -m pytest -q \
  -m "design_lint and interface_lint" \
  tests/test_usb_peer_reference_superspeed.py
```

Its full-duplex TX-to-RX and RX-to-TX split-reference fault, common-reference
control, exact pin membership, repeatable netlist exports, exact common and
separate reference maps, and stale-map fault behavior also run against the
digest-pinned KiCad 10.0.0 and 10.0.5 images. The lane uses a synthetic
project-owned toolchain catalog and needs no external project checkout:

```sh
KICAD_RUN_NATIVE_USB_DATA_PATH_FIXTURES=1 python -I -B -m pytest -q \
  -m "design_lint and interface_lint and native_kicad" \
  tests/test_usb_superspeed_peer_reference_native_fixture_lane.py
```

The LED rail/output-path fault and valid series-path controls have a focused
native component suite:

```sh
KICAD_RUN_NATIVE_LED_RAIL_FIXTURES=1 python -I -B -m pytest -q \
  -m "design_lint and component_lint and native_kicad" \
  tests/test_led_rail_native_fixture_lane.py
```

USB SuperSpeed pair acceptance uses the exact-version native interface lane:

```sh
KICAD_RUN_NATIVE_COMPLEMENTARY_PAIR_FIXTURES=1 python -I -B -m pytest -q \
  -m "design_lint and interface_lint and native_kicad" \
  tests/test_complementary_pair_native_fixture_lane.py
```

Connector/capacitor-only DC-reference review also has a focused exact-version
native fault and valid-control lane:

```sh
KICAD_RUN_NATIVE_NET_DC_REFERENCE_FIXTURES=1 python -I -B -m pytest -q \
  -m "design_lint and power_lint and native_kicad" \
  tests/test_net_dc_reference_native_fixture_lane.py
```

Protection-path and track-width acceptance use corresponding modules with the
same marker selection.

`tests.support.reference_root()` copies the template's public examples, catalogs,
and guidance into a disposable repository. It never copies reusable Python tools
or the shared regression suite into project fixtures. CLI subprocesses load the
same tooling package as the parent test process. Temporary source mutations,
fake native commands, and synthetic release evidence stay in disposable folders.
These fixtures do not establish electrical approval or manufacturing readiness.

Use a normal editable development install. The package gate checks its import
origin before the suite; tests do not prepend source directories to `PYTHONPATH`.
The installed-wheel rehearsal runs separately to prove packaging without editable imports.

Tests must not depend on private designs, hardware, provider credentials, or
network access. The parts assistant HTTP tests use a local loopback server and
skip with an explicit reason when the environment denies local socket binding.
Native acceptance runs separately against the project's approved KiCad toolchain.

The complete package gate also checks source and wheel distributions, the CLI/MCP
surface declarations, and an installed wheel against external project layouts:

```sh
python scripts/ci.py --project-root "$KICAD_TEMPLATE_ROOT"
```

See [configuration](../docs/CONFIGURATION.md) for layout adapters and
[packaging](../docs/PACKAGING.md) for version and distribution checks.
