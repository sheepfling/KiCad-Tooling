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

The suite uses a separate public template checkout for its reference examples.
Set `KICAD_TEMPLATE_ROOT` to that checkout, then run from the tooling repository:

```sh
export KICAD_TEMPLATE_ROOT=/path/to/KiCad-Team-Workflow-Template
python -I -B -m pytest -q
```

For PowerShell, set the variable with
`$env:KICAD_TEMPLATE_ROOT = "C:\path\to\KiCad-Team-Workflow-Template"`.
Run one module with `python -I -B -m pytest -q tests/test_product.py`.

Focused runs use registered markers. `tests/conftest.py` assigns lint areas by
test module; areas can overlap when a fixture checks more than one concern. It
also marks exact-native fixture classes separately:

```sh
python -I -B -m pytest -q -m \
  "design_lint and not native_kicad and not slow and not template_checkout" \
  --durations=20
python -I -B -m pytest -q -m "schematic_lint and not native_kicad and not slow"
python -I -B -m pytest -q -m "connector_lint and not native_kicad and not slow"
python -I -B -m pytest -q -m "return_path_lint and not native_kicad and not slow"
python -I -B -m pytest -q -m "pcb_lint and not native_kicad and not slow"
python -I -B -m pytest -q -m "design_lint and interface_lint" \
  tests/test_serial_participants.py tests/test_serial_participant_net_labels.py
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

The first command runs the portable, non-slow design-lint group that is
self-contained. Tests that need the public template checkout carry the
`template_checkout` marker and use the separate command after setting
`KICAD_TEMPLATE_ROOT`. The area
markers select schematic, component, connector, interface, power, evidence,
PCB, return-path, or parity regressions; combine them with `-k` to select a test or
parametrized fault/control case. `native_kicad` selects exact-version fixtures and still
requires each fixture's documented version and environment settings. Markers
narrow local runs; the package acceptance gate continues to run the complete
suite. Add each new lint test module to its area in `tests/conftest.py`; this
keeps it in both its focused area and the portable `design_lint` selection.

Hosted PCB geometry acceptance is split by theme; for example, run only the
synthetic decoupling placement or return-via checks with:

```sh
python -I -B -m pytest -q -m "design_lint and pcb_lint" \
  tests/test_pcb_decoupling.py tests/test_pcb_decoupling_return_vias.py
```

The native decoupling fixture runs separately with:

```sh
python -I -B -m pytest -q -m "design_lint and pcb_lint and native_kicad" \
  tests/test_pcb_decoupling_native_fixture_lane.py
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
