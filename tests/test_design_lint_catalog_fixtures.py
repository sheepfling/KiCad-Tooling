"""The shipped lint catalog is tied to implementation and fault/control regressions."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint import (
    rule_catalog,
)
from tests.test_design_lint_complementary_pairs import (
    DesignLintComplementaryPairTests as ComplementaryPairCase,
)
from tests.test_design_lint_connector_roles import DesignLintConnectorRoleTests as ConnectorRoleCase
from tests.test_design_lint_control_inputs import DesignLintControlInputTests as ControlInputCase
from tests.test_design_lint_dc_reference import DesignLintDcReferenceTests as DcReferenceCase
from tests.test_design_lint_decoupling import DesignLintDecouplingTests as DecouplingCase
from tests.test_design_lint_i2c import DesignLintI2cTests as I2cCase
from tests.test_design_lint_led_topology import DesignLintLedTopologyTests as LedTopologyCase
from tests.test_design_lint_peer_voltage import DesignLintPeerVoltageTests as PeerVoltageCase
from tests.test_design_lint_policy import DesignLintPolicyTests as PolicyCase
from tests.test_design_lint_power_pin_patterns import (
    DesignLintPowerPinPatternTests as PowerPinPatternCase,
)
from tests.test_design_lint_schematic_connectivity import (
    DesignLintSchematicConnectivityTests as SchematicConnectivityCase,
)
from tests.test_design_lint_schematic_coverage import (
    DesignLintSchematicCoverageTests as SchematicCoverageCase,
)
from tests.test_design_lint_schematic_readability import (
    DesignLintSchematicReadabilityTests as SchematicReadabilityCase,
)
from tests.test_design_lint_schematic_text import DesignLintSchematicTextTests as SchematicTextCase
from tests.test_design_lint_serial_peer_voltage import (
    DesignLintSerialPeerVoltageTests as SerialPeerVoltageCase,
)
from tests.test_design_lint_unconnected_interfaces import (
    DesignLintUnconnectedInterfaceTests as UnconnectedInterfaceCase,
)
from tests.test_pcb_reference_plane_contract import (
    PcbReferencePlaneContractTests as PcbReferencePlaneContractCase,
)
from tests.test_pcb_reference_plane_geometry import (
    PcbReferencePlaneGeometryTests as PcbReferencePlaneGeometryCase,
)
from tests.test_pcb_reference_plane_layers import (
    PcbReferencePlaneLayerTests as PcbReferencePlaneLayerCase,
)
from tests.test_pcb_switching_loop_geometry import (
    PcbSwitchingLoopGeometryTests as PcbSwitchingLoopGeometryCase,
)
from tests.test_pcb_switching_loop_routes import (
    PcbSwitchingLoopRouteTests as PcbSwitchingLoopRouteCase,
)
from tests.test_power_paths import (
    PowerPathTests as PowerPathCase,
)
from tests.test_power_sequences import (
    PowerSequenceTests as PowerSequenceCase,
)
from tests.test_regulator_feedback import (
    RegulatorFeedbackTests as RegulatorFeedbackCase,
)
from tests.test_schematic_geometry_hierarchy import (
    SchematicGeometryHierarchyTests as SchematicGeometryHierarchyCase,
)
from tests.test_schematic_geometry_pin_proximity import (
    SchematicGeometryPinProximityTests as SchematicGeometryPinProximityCase,
)
from tests.test_schematic_geometry_symbol_body import (
    SchematicGeometrySymbolBodyTests as SchematicGeometrySymbolBodyCase,
)
from tests.test_schematic_geometry_text import (
    SchematicGeometryTextTests as SchematicGeometryTextCase,
)
from tests.test_schematic_geometry_wire_topology import (
    SchematicGeometryWireTopologyTests as SchematicGeometryWireTopologyCase,
)
from tests.test_serial_peer_reference_boundaries import (
    SerialPeerReferenceBoundaryTests as SerialPeerReferenceBoundaryCase,
)
from tests.test_serial_peer_reference_coverage import (
    SerialPeerReferenceCoverageTests as SerialPeerReferenceCoverageCase,
)
from tests.test_serial_peer_reference_maps import (
    SerialPeerReferenceMapTests as SerialPeerReferenceMapCase,
)
from tests.test_serial_peer_reference_review import (
    SerialPeerReferenceReviewTests as SerialPeerReferenceReviewCase,
)
from tests.test_stm32_pin_map import (
    Stm32PinMapTests as Stm32PinMapCase,
)

pytestmark = pytest.mark.design_lint


def test_active_rules_reference_existing_regression_fixtures() -> None:
    instances = {
        PeerVoltageCase: PeerVoltageCase(),
        SerialPeerVoltageCase: SerialPeerVoltageCase(),
        SchematicTextCase: SchematicTextCase(),
        DcReferenceCase: DcReferenceCase(),
        DecouplingCase: DecouplingCase(),
        SchematicConnectivityCase: SchematicConnectivityCase(),
        SchematicReadabilityCase: SchematicReadabilityCase(),
        SchematicCoverageCase: SchematicCoverageCase(),
        ConnectorRoleCase: ConnectorRoleCase(),
        LedTopologyCase: LedTopologyCase(),
        PowerPinPatternCase: PowerPinPatternCase(),
        I2cCase: I2cCase(),
        ComplementaryPairCase: ComplementaryPairCase(),
        UnconnectedInterfaceCase: UnconnectedInterfaceCase(),
        ControlInputCase: ControlInputCase(),
        PolicyCase: PolicyCase(),
        SchematicGeometryHierarchyCase: SchematicGeometryHierarchyCase(),
        SchematicGeometryPinProximityCase: SchematicGeometryPinProximityCase(),
        SchematicGeometrySymbolBodyCase: SchematicGeometrySymbolBodyCase(),
        SchematicGeometryTextCase: SchematicGeometryTextCase(),
        SchematicGeometryWireTopologyCase: SchematicGeometryWireTopologyCase(),
        RegulatorFeedbackCase: RegulatorFeedbackCase(),
        PcbReferencePlaneContractCase: PcbReferencePlaneContractCase(),
        PcbReferencePlaneGeometryCase: PcbReferencePlaneGeometryCase(),
        PcbReferencePlaneLayerCase: PcbReferencePlaneLayerCase(),
        PcbSwitchingLoopGeometryCase: PcbSwitchingLoopGeometryCase(),
        PcbSwitchingLoopRouteCase: PcbSwitchingLoopRouteCase(),
        Stm32PinMapCase: Stm32PinMapCase(),
        SerialPeerReferenceReviewCase: SerialPeerReferenceReviewCase(),
        SerialPeerReferenceCoverageCase: SerialPeerReferenceCoverageCase(),
        SerialPeerReferenceMapCase: SerialPeerReferenceMapCase(),
        SerialPeerReferenceBoundaryCase: SerialPeerReferenceBoundaryCase(),
        PowerPathCase: PowerPathCase(),
        PowerSequenceCase: PowerSequenceCase(),
    }
    fixtures: set[tuple[type, str]] = set()
    pytest_fixtures: set[str] = set()
    metamorphic_rules: set[str] = set()
    for entry in rule_catalog().rules:
        assert entry.fault_fixtures
        assert entry.valid_control_fixtures
        if entry.metamorphic_fixtures:
            metamorphic_rules.add(entry.rule_id)
        for name in (
            *entry.fault_fixtures,
            *entry.valid_control_fixtures,
            *entry.metamorphic_fixtures,
        ):
            parts = name.split(".")
            module = None
            module_length = 0
            for length in range(len(parts) - 1, 0, -1):
                try:
                    module = importlib.import_module(".".join(parts[:length]))
                except ModuleNotFoundError:
                    continue
                module_length = length
                break
            assert module is not None, name
            attributes = parts[module_length:]
            owner = module
            for attribute in attributes[:-1]:
                owner = getattr(owner, attribute)
            target = getattr(owner, attributes[-1])
            assert callable(target), name
            if isinstance(owner, type) and owner in instances:
                assert owner in instances, name
                fixtures.add((owner, attributes[-1]))
            else:
                assert len(attributes) == 1, name
                assert target.__name__.startswith("test_"), name
                pytest_fixtures.add(name)

    assert len(metamorphic_rules) >= 2
    assert pytest_fixtures, "catalog should support pytest function fixtures"

    for test_case, method_name in sorted(
        fixtures, key=lambda fixture: (fixture[0].__name__, fixture[1])
    ):
        getattr(instances[test_case], method_name)()


def test_catalog_implementation_references_resolve_to_sources_or_fixtures() -> None:
    repository = Path(__file__).resolve().parents[1]
    for rule in rule_catalog().rules:
        for reference in rule.implementation_refs:
            target, separator, symbol = reference.partition("#")
            target_path = (
                repository / target
                if "/" in target
                else repository.joinpath(*target.split(".")).with_suffix(".py")
            )
            assert target_path.is_file(), f"{rule.rule_id}: missing implementation {target}"
            if not separator or target_path.suffix != ".py":
                continue
            module = ast.parse(target_path.read_text(encoding="utf-8"))
            names = {
                node.name
                for node in module.body
                if isinstance(node, (ast.AsyncFunctionDef, ast.ClassDef, ast.FunctionDef))
            }
            names.update(
                alias.asname or alias.name
                for node in module.body
                if isinstance(node, ast.ImportFrom)
                for alias in node.names
            )
            assert symbol in names, (
                f"{rule.rule_id}: {reference} does not resolve to a top-level source symbol"
            )


def test_every_rule_fixture_module_has_design_lint_selection_marker() -> None:
    repository = Path(__file__).resolve().parents[1]
    for rule in rule_catalog().rules:
        for field in ("fault_fixtures", "valid_control_fixtures", "metamorphic_fixtures"):
            for fixture in getattr(rule, field):
                module_name = ".".join(fixture.split(".")[:2])
                module_path = repository.joinpath(*module_name.split(".")).with_suffix(".py")
                module = ast.parse(module_path.read_text(encoding="utf-8"))
                assignment = next(
                    (
                        node
                        for node in module.body
                        if isinstance(node, ast.Assign)
                        and any(
                            isinstance(target, ast.Name) and target.id == "pytestmark"
                            for target in node.targets
                        )
                    ),
                    None,
                )
                assert assignment is not None, f"{rule.rule_id}: {module_path} is not tagged"
                markers = {
                    node.attr
                    for node in ast.walk(assignment.value)
                    if isinstance(node, ast.Attribute)
                    and node.attr == "design_lint"
                    and isinstance(node.value, ast.Attribute)
                    and node.value.attr == "mark"
                    and isinstance(node.value.value, ast.Name)
                    and node.value.value.id == "pytest"
                }
                assert "design_lint" in markers, (
                    f"{rule.rule_id}: {module_path} lacks the design_lint marker"
                )
