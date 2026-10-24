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
)
from tests.lint_architecture_support import (
    line_count as _line_count,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.architecture]


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
    "connector_footprint_named_power_input_divergence.py",
    "connector_footprint_named_power_input_all_open.py",
    "connector_footprint_named_power_output_divergence.py",
    "connector_footprint_named_signal_divergence.py",
    "connector_footprint_peer_pins.py",
    "connector_footprint_peer_pin_types.py",
    "connector_peer_pin_coverage.py",
    "connector_peer_pin_findings.py",
    "connector_peer_pin_scan.py",
    "connector_peer_named_power_aliases.py",
    "connector_peer_power_input.py",
    "connector_peer_power_output.py",
    "connector_pins.py",
    "connector_return_pins.py",
    "component_peer_pin_findings.py",
    "component_power_input_peer_scan.py",
    "component_peer_pin_all_open.py",
    "component_peer_pin_mixed_open.py",
    "component_peer_pin_identity.py",
    "component_peer_pin_scan.py",
    "component_peer_pin_assignment_outlier.py",
    "component_peer_pin_evaluation.py",
    "component_pin_patterns.py",
)
ROLE_MAPPING_MODULES = ("component_roles.py",)
COMPONENT_THEME_MODULES = (
    "oscillator_output_path_candidates.py",
    "oscillator_output_paths.py",
)
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
        "rs485_",
        "serial_",
        "spi_",
        "usb_",
    ),
    "components": (
        "component_",
        "design_lint_component_",
        "crystal_",
        "led_",
        "mosfet_",
        "oscillator_",
        "rc_",
        "stm32_",
        "two_pin_",
    ),
    "power": ("net_dc_", "power_", "regulator_"),
    "returns": ("component_return_", "connector_return_", "return_"),
    "schematic": ("schematic_",),
    "pcb": ("pcb_",),
}


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
    modules.extend(HWREPO / name for name in COMPONENT_THEME_MODULES)
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


def test_two_pin_solar_cell_rule_has_a_focused_component_owner() -> None:
    from kicad_tooling.hwrepo.design_lint import rule_catalog

    rule = next(
        item
        for item in rule_catalog().rules
        if item.rule_id == "component.two_pin_solar_cell_same_net"
    )
    owner = "kicad_tooling/hwrepo/two_pin_solar_cells.py#two_pin_solar_cell_same_net_candidates"
    assert rule.theme == "components"
    assert rule.implementation_owner == owner
    assert owner in rule.implementation_refs
    assert (HWREPO / "two_pin_solar_cells.py").is_file()
    assert _line_count(HWREPO / "two_pin_solar_cells.py") < IMPLEMENTATION_MAX_LINES


def test_two_pin_thermocouple_rule_has_a_focused_component_owner() -> None:
    from kicad_tooling.hwrepo.design_lint import rule_catalog

    rule = next(
        item
        for item in rule_catalog().rules
        if item.rule_id == "component.two_pin_thermocouple_same_net"
    )
    owner = "kicad_tooling/hwrepo/two_pin_thermocouples.py#two_pin_thermocouple_same_net_candidates"
    assert rule.theme == "components"
    assert rule.implementation_owner == owner
    assert owner in rule.implementation_refs
    assert (HWREPO / "two_pin_thermocouples.py").is_file()
    assert _line_count(HWREPO / "two_pin_thermocouples.py") < IMPLEMENTATION_MAX_LINES


def test_transformer_winding_rule_has_a_focused_component_owner() -> None:
    from kicad_tooling.hwrepo.design_lint import rule_catalog

    rule = next(
        item
        for item in rule_catalog().rules
        if item.rule_id == "component.transformer_winding_same_net"
    )
    owner = "kicad_tooling/hwrepo/design_lint_component_transformers.py#transformer_winding_same_net_candidates"
    assert rule.theme == "components"
    assert rule.implementation_owner == owner
    assert owner in rule.implementation_refs
    assert (HWREPO / "design_lint_component_transformers.py").is_file()
    assert _line_count(HWREPO / "design_lint_component_transformers.py") < IMPLEMENTATION_MAX_LINES


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


@pytest.mark.rule_gate_integrity
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
        filename = path.rsplit("/", maxsplit=1)[-1] if path is not None else ""
        theme_owned_lint = filename.startswith(f"design_lint_{theme}_") or (
            theme == "components" and filename.startswith("design_lint_component_")
        )
        function = owner.split("#", 1)[1] if "#" in owner else ""
        if (
            owner not in rule.get("implementation_refs", [])
            or path is None
            or not path.startswith("kicad_tooling/hwrepo/")
            or path in coordinators
            or (filename.startswith("design_lint_") and not theme_owned_lint)
            or not (filename.startswith(THEME_OWNER_PREFIXES.get(theme, ())) or theme_owned_lint)
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
