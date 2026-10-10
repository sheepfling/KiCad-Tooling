"""Keep design-lint implementation and theme suites reviewable."""

from __future__ import annotations

import ast
import json

import pytest

from kicad_tooling.hwrepo.pcb_return_path_capture import NATIVE_PROBE_SOURCE_PARTS
from tests.lint_architecture_support import (
    EVALUATOR_MAX_LINES,
    FACADE_MAX_LINES,
    HWREPO,
    IMPLEMENTATION_MAX_LINES,
    REPO_ROOT,
    SUPPORT_MODULE_MAX_LINES,
    TESTS,
    THEME_SUITE_MAX_LINES,
)
from tests.lint_architecture_support import (
    line_count as _line_count,
)

pytestmark = pytest.mark.design_lint


def _implementation_path(reference: str) -> str | None:
    """Resolve catalog paths and import-style references to packaged Python files."""
    value = reference.split("#", 1)[0]
    if value.startswith("kicad_tooling/") and value.endswith((".py", ".py.in")):
        return value
    if value.startswith("kicad_tooling."):
        return f"{value.replace('.', '/')}.py"
    return None


PIN_ANALYSIS_MODULES = (
    "connector_identity.py",
    "connector_peer_pin_coverage.py",
    "connector_peer_pin_findings.py",
    "connector_peer_pin_scan.py",
    "connector_pins.py",
    "connector_return_pins.py",
    "component_peer_pin_findings.py",
    "component_peer_pin_scan.py",
    "component_pin_patterns.py",
)
ROLE_MAPPING_MODULES = ("component_roles.py",)
THEME_OWNER_PREFIXES = {
    "connectors": ("connector_",),
    "interfaces": (
        "bus_",
        "can_",
        "control_input_",
        "differential_pair_",
        "digital_peer_",
        "external_protection",
        "i2c_",
        "open_drain_",
        "serial_",
        "spi_",
        "usb_",
    ),
    "components": ("component_", "crystal_", "led_", "rc_", "stm32_", "two_pin_"),
    "power": ("net_dc_", "power_", "regulator_"),
    "returns": ("component_return_", "connector_return_", "return_"),
    "schematic": ("schematic_",),
    "pcb": ("pcb_",),
}
SCHEMATIC_GEOMETRY_THEME_SUITES = (
    "test_schematic_geometry_text.py",
    "test_schematic_geometry_symbol_body.py",
    "test_schematic_geometry_pin_proximity.py",
    "test_schematic_geometry_wire_topology.py",
    "test_schematic_geometry_hierarchy.py",
    "test_schematic_geometry_native_text.py",
    "test_schematic_geometry_native_wire_body.py",
    "test_schematic_geometry_native_symbol_body.py",
    "test_schematic_geometry_native_pin_connectivity.py",
    "test_schematic_geometry_native_wire_topology.py",
)
PCB_REFERENCE_PLANE_THEME_SUITES = (
    "test_pcb_reference_plane_geometry.py",
    "test_pcb_reference_plane_layers.py",
    "test_pcb_reference_plane_contract.py",
    "test_ci_hosted_pcb_reference_planes.py",
)
CONNECTOR_COVERAGE_THEME_SUITES = (
    "test_connector_inventory_coverage.py",
    "test_connector_supply_peer_coverage.py",
    "test_connector_return_role_coverage.py",
    "test_ci_hosted_connector_returns.py",
    "test_ci_hosted_connector_inventory_native.py",
)
HOSTED_ORCHESTRATION_THEME_SUITES = ("test_ci_hosted_native_orchestration.py",)
OPEN_DRAIN_THEME_SUITES = ("test_open_drain_bias_fixture_lane.py",)
I2C_ADDRESS_THEME_SUITES = (
    "test_i2c_address_coverage.py",
    "test_i2c_address_collisions.py",
    "test_i2c_address_straps.py",
    "test_i2c_address_contract.py",
)
USB_HOSTED_THEME_SUITES = (
    "test_hosted_usb_requirements.py",
    "test_usb_data_path_native_fixture_lane.py",
)
POWER_PATH_HOSTED_THEME_SUITES = (
    "test_hosted_power_path_requirements.py",
    "test_power_path_fixture_lane.py",
    "test_power_path_native_fixture_lane.py",
)
IC_RAIL_NATIVE_THEME_SUITES = ("test_ic_rail_capacitor_native_fixture_lane.py",)
POWER_INPUT_THEME_SUITES = (
    "test_power_input_source_paths.py",
    "test_power_input_source_anchors.py",
    "test_power_input_policy.py",
)
DIGITAL_PEER_FIXTURE_THEME_SUITES = (
    "test_ci_hosted_digital_peers.py",
    "test_digital_peer_spi_voltage_fixture_lane.py",
    "test_digital_peer_serial_voltage_fixture_lane.py",
    "test_digital_peer_serial_reference_fixture_lane.py",
)
NATIVE_INTERFACE_THEME_SUITES = (
    "test_ci_hosted_usb_c_ports.py",
    "test_ci_hosted_stm32.py",
    "test_ci_hosted_control_inputs.py",
)
COMPONENT_PEER_POWER_THEME_SUITES = (
    "test_component_peer_power_fixture_lane.py",
    "test_peer_power_assignment_symbol_groups.py",
    "test_peer_power_assignment_part_id_groups.py",
    "test_peer_power_assignment_cli_mcp.py",
    "test_peer_power_assignment_native.py",
)
COMPONENT_RATING_HOSTED_THEME_SUITES = ("test_component_rating_native_fixture_lane.py",)
COMPONENT_LED_THEME_SUITES = ("test_led_rail_native_fixture_lane.py",)
TWO_PIN_NATIVE_THEME_SUITES = ("test_two_pin_component_native_fixture_lane.py",)
COMPLEMENTARY_PAIR_NATIVE_THEME_SUITES = ("test_complementary_pair_native_fixture_lane.py",)
DC_REFERENCE_NATIVE_THEME_SUITES = ("test_net_dc_reference_native_fixture_lane.py",)
PCB_THEME_SUITES = (
    "test_ci_hosted_pcb_fixture_schedule.py",
    "test_ci_hosted_pcb_access.py",
    "test_pcb_decoupling_native_fixture_lane.py",
    "test_pcb_protection_path_native_fixture_lane.py",
    "test_pcb_track_width_native_fixture_lane.py",
    "test_pcb_switching_loop_geometry.py",
    "test_pcb_switching_loop_routes.py",
    "test_pcb_access_fixture_lane.py",
    "test_pcb_access_native_fixture_lane.py",
    "test_pcb_drc_coverage.py",
    "test_pcb_signal_path_coverage.py",
    "test_pcb_signal_path_evidence.py",
    "test_pcb_signal_path_mcp_parity.py",
    "test_ci_hosted_pcb_return_paths.py",
)


def test_design_lint_public_module_stays_a_small_facade() -> None:
    facade = HWREPO / "design_lint.py"

    assert _line_count(facade) < FACADE_MAX_LINES


@pytest.mark.connector_lint
def test_connector_candidate_facade_delegates_by_review_theme() -> None:
    facade = HWREPO / "design_lint_connector_candidates.py"
    owners = (
        HWREPO / "design_lint_connector_pin_candidates.py",
        HWREPO / "design_lint_return_domain_candidates.py",
    )

    assert _line_count(facade) < FACADE_MAX_LINES
    assert all(owner.is_file() for owner in owners)

    tree = ast.parse(facade.read_text(encoding="utf-8"), filename=facade.name)
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    candidate_constructions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Candidate"
    ]

    assert {"connector_pin_candidates", "return_domain_candidates"} <= calls
    assert not candidate_constructions, "Connector dispatch should not construct lint findings."


def test_design_lint_evaluator_stays_a_staged_coordinator() -> None:
    evaluator = HWREPO / "design_lint_evaluator.py"

    assert _line_count(evaluator) < EVALUATOR_MAX_LINES


def test_native_pcb_probe_source_fragments_stay_theme_sized() -> None:
    modules = sorted(HWREPO.glob("native_pcb_probe*.py.in"))
    assert modules, "The isolated native PCB probe should have packaged source fragments."
    assert {path.name for path in modules} == set(NATIVE_PROBE_SOURCE_PARTS)
    oversized = {
        path.name: _line_count(path)
        for path in modules
        if _line_count(path) >= IMPLEMENTATION_MAX_LINES
    }

    assert not oversized, f"Split native PCB probe fragments below 500 lines: {oversized}"


def test_design_lint_implementation_modules_stay_below_review_limit() -> None:
    modules = sorted(HWREPO.glob("design_lint_*.py"))
    modules.extend(HWREPO / name for name in PIN_ANALYSIS_MODULES)
    modules.extend(HWREPO / name for name in ROLE_MAPPING_MODULES)
    assert modules, "Design-lint implementation modules should be discoverable."

    module_sizes = {path.name: _line_count(path) for path in modules}
    oversized = {
        name: lines for name, lines in module_sizes.items() if lines >= IMPLEMENTATION_MAX_LINES
    }

    assert not oversized, (
        "Split design-lint modules at the 500-line review threshold; "
        f"oversized modules: {oversized}"
    )


def test_mapped_coverage_dispatcher_stays_small_and_declarative() -> None:
    dispatcher = HWREPO / "design_lint_mapped_coverage_candidates.py"
    owners = (
        "design_lint_protection_candidates.py",
        "design_lint_crystal_candidates.py",
        "design_lint_regulator_candidates.py",
        "design_lint_rc_filter_candidates.py",
        "design_lint_usb_data_path_candidates.py",
        "design_lint_power_path_candidates.py",
        "design_lint_power_sequence_candidates.py",
    )

    assert _line_count(dispatcher) < FACADE_MAX_LINES
    assert all((HWREPO / name).is_file() for name in owners)

    tree = ast.parse(dispatcher.read_text(encoding="utf-8"), filename=dispatcher.name)
    candidate_constructions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Candidate"
    ]

    assert not candidate_constructions, (
        "Mapped-coverage dispatch should call thematic candidate owners, "
        "not accumulate individual lint findings"
    )


def test_top_level_candidate_aggregation_stays_a_theme_coordinator() -> None:
    aggregator = HWREPO / "design_lint_candidate_aggregation.py"

    assert _line_count(aggregator) < 300

    tree = ast.parse(aggregator.read_text(encoding="utf-8"), filename=aggregator.name)
    candidate_constructions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Candidate"
    ]

    assert not candidate_constructions, (
        "Top-level aggregation should delegate to theme owners, "
        "not contain individual lint findings"
    )


def test_catalogued_lint_implementations_stay_theme_sized() -> None:
    catalog = json.loads((HWREPO / "design-lint-rules.json").read_text(encoding="utf-8"))
    references = {
        path
        for rule in catalog["rules"]
        for reference in rule.get("implementation_refs", [])
        if (path := _implementation_path(reference)) is not None
    }
    coordinator = "kicad_tooling/ci_hosted.py"
    assert coordinator not in references, (
        "Active rule evidence should reference its lint-theme implementation, "
        "not the hosted CI coordinator"
    )
    modules = {name: REPO_ROOT / name for name in references}
    missing = sorted(name for name, path in modules.items() if not path.is_file())
    oversized = {
        name: _line_count(path)
        for name, path in modules.items()
        if path.is_file() and _line_count(path) >= IMPLEMENTATION_MAX_LINES
    }

    assert not missing, f"Catalogued lint implementation files are missing: {missing}"
    assert not oversized, (
        "Keep catalogued lint implementation modules below 500 lines and split by theme; "
        f"oversized={oversized}"
    )


def test_active_catalog_implementation_modules_stay_below_review_limit() -> None:
    catalog = json.loads((HWREPO / "design-lint-rules.json").read_text(encoding="utf-8"))
    implementation_paths = {
        path
        for rule in catalog["rules"]
        if rule.get("status") == "active"
        for reference in rule.get("implementation_refs", [])
        if (path := _implementation_path(reference)) is not None
        and path.startswith("kicad_tooling/hwrepo/")
    }
    modules = {path: REPO_ROOT / path for path in implementation_paths}
    missing = sorted(name for name, path in modules.items() if not path.is_file())
    oversized = {
        name: _line_count(path)
        for name, path in modules.items()
        if path.is_file() and _line_count(path) >= IMPLEMENTATION_MAX_LINES
    }

    assert not missing, f"Active rule references missing implementation modules: {missing}"
    assert not oversized, (
        "Keep active design-lint implementation modules below 500 lines; "
        f"oversized modules: {oversized}"
    )


def test_each_active_rule_declares_a_source_owner_function() -> None:
    catalog = json.loads((HWREPO / "design-lint-rules.json").read_text(encoding="utf-8"))
    coordinators = {
        "kicad_tooling/ci_hosted.py",
        "kicad_tooling/hwrepo/design_lint.py",
        "kicad_tooling/hwrepo/design_lint_candidate_aggregation.py",
        "kicad_tooling/hwrepo/design_lint_evaluator.py",
    }
    invalid_owners: list[str] = []
    for rule in catalog["rules"]:
        if rule.get("status") != "active":
            continue
        owner = rule.get("implementation_owner", "")
        path = _implementation_path(owner)
        theme = rule.get("theme", "")
        function = owner.split("#", 1)[1] if "#" in owner else ""
        if (
            owner not in rule.get("implementation_refs", [])
            or path is None
            or not path.startswith("kicad_tooling/hwrepo/")
            or path in coordinators
            or path.rsplit("/", maxsplit=1)[-1].startswith("design_lint_")
            or not path.rsplit("/", maxsplit=1)[-1].startswith(THEME_OWNER_PREFIXES.get(theme, ()))
            or not function
        ):
            invalid_owners.append(
                f"{rule['rule_id']}: theme={theme or '<missing>'}, owner={owner or '<missing>'}"
            )
            continue
        source = REPO_ROOT / path
        if not source.is_file() or _line_count(source) >= IMPLEMENTATION_MAX_LINES:
            invalid_owners.append(f"{rule['rule_id']}: missing or oversized {path}")
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=path)
        functions = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if function not in functions:
            invalid_owners.append(f"{rule['rule_id']}: undefined owner function {owner}")

    assert not invalid_owners, (
        "Each active rule must name a defined source owner outside shared facades and "
        f"coordinators: {invalid_owners}"
    )


def test_design_lint_theme_suites_stay_below_review_limit() -> None:
    modules = sorted(
        path
        for path in (
            *TESTS.glob("test_design_lint_*.py"),
            *(
                TESTS / name
                for name in (
                    *PCB_THEME_SUITES,
                    *SCHEMATIC_GEOMETRY_THEME_SUITES,
                    *PCB_REFERENCE_PLANE_THEME_SUITES,
                    *CONNECTOR_COVERAGE_THEME_SUITES,
                    *HOSTED_ORCHESTRATION_THEME_SUITES,
                    *OPEN_DRAIN_THEME_SUITES,
                    *I2C_ADDRESS_THEME_SUITES,
                    *USB_HOSTED_THEME_SUITES,
                    *POWER_PATH_HOSTED_THEME_SUITES,
                    *IC_RAIL_NATIVE_THEME_SUITES,
                    *POWER_INPUT_THEME_SUITES,
                    *DIGITAL_PEER_FIXTURE_THEME_SUITES,
                    *NATIVE_INTERFACE_THEME_SUITES,
                    *COMPONENT_PEER_POWER_THEME_SUITES,
                    *COMPONENT_RATING_HOSTED_THEME_SUITES,
                    *COMPONENT_LED_THEME_SUITES,
                    *TWO_PIN_NATIVE_THEME_SUITES,
                    *COMPLEMENTARY_PAIR_NATIVE_THEME_SUITES,
                    *DC_REFERENCE_NATIVE_THEME_SUITES,
                )
            ),
        )
    )
    assert modules, "Design-lint theme suites should be discoverable."

    module_sizes = {path.name: _line_count(path) for path in modules}
    oversized = {
        name: lines for name, lines in module_sizes.items() if lines >= THEME_SUITE_MAX_LINES
    }

    assert not oversized, (
        "Split design-lint theme suites at the 500-line review threshold; "
        f"oversized suites: {oversized}"
    )


def test_design_lint_support_modules_stay_below_review_limit() -> None:
    modules = [TESTS / "hashseed_probe.py"]
    modules.extend(TESTS.rglob("*support*.py"))
    modules.extend((TESTS / "design_lint_fixtures").rglob("*.py"))
    modules.extend((TESTS / "hashseed_probe_cases").rglob("*.py"))

    module_sizes = {
        path.relative_to(TESTS).as_posix(): _line_count(path) for path in sorted(set(modules))
    }
    oversized = {
        name: lines for name, lines in module_sizes.items() if lines >= SUPPORT_MODULE_MAX_LINES
    }

    assert not oversized, (
        "Split design-lint support modules at the 500-line review threshold; "
        f"oversized modules: {oversized}"
    )
