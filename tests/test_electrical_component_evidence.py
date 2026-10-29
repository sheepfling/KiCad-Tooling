"""Source-bound component rating and MOSFET evidence replay regressions."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import electrical_evidence
from kicad_tooling.hwrepo.electrical import SimulationCase
from kicad_tooling.hwrepo.models import ElectricalCheck
from tests.electrical_evidence_support import (
    ElectricalEvidenceWorkspace,
    reject_omitted_electrical_checks,
)
from tests.electrical_evidence_support import (
    electrical_evidence_workspace as _electrical_evidence_workspace_fixture,  # noqa: F401  # pyright: ignore[reportUnusedImport]
)
from tests.test_component_power_ratings import (
    native_netlist_xml as component_power_netlist_xml,
)
from tests.test_component_power_ratings import (
    requirement as component_power_requirement,
)
from tests.test_component_voltage_ratings import (
    native_netlist_xml as component_voltage_netlist_xml,
)
from tests.test_component_voltage_ratings import (
    requirement as component_voltage_requirement,
)
from tests.test_mosfet_stress import (
    native_netlist_xml as mosfet_stress_netlist_xml,
)
from tests.test_mosfet_stress import (
    requirement as mosfet_stress_requirement,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.evidence_lint,
    pytest.mark.template_checkout,
]


@pytest.mark.parametrize(
    (
        "contract_field",
        "requirement_factory",
        "netlist_factory",
        "output_name",
        "expected_check_id",
        "omitted_check_ids",
    ),
    (
        pytest.param(
            "component_voltage_ratings",
            component_voltage_requirement,
            component_voltage_netlist_xml,
            "component-voltage-rating-replay",
            "component-voltage-rating/input-capacitor/utilization",
            (
                "component-voltage-rating/input-capacitor/identity",
                "component-voltage-rating/input-capacitor/pin-1",
                "component-voltage-rating/input-capacitor/pin-2",
                "component-voltage-rating/input-capacitor/utilization",
            ),
            id="voltage-rating",
        ),
        pytest.param(
            "component_power_ratings",
            component_power_requirement,
            component_power_netlist_xml,
            "component-power-rating-replay",
            "component-power-rating/sense-resistor/utilization",
            (
                "component-power-rating/sense-resistor/identity",
                "component-power-rating/sense-resistor/pin-1",
                "component-power-rating/sense-resistor/pin-2",
                "component-power-rating/sense-resistor/utilization",
            ),
            id="power-rating",
        ),
        pytest.param(
            "mosfet_stress",
            mosfet_stress_requirement,
            mosfet_stress_netlist_xml,
            "mosfet-stress-replay",
            "mosfet-stress/switch-q1/state-on/vds",
            (
                "mosfet-stress/switch-q1/identity",
                "mosfet-stress/switch-q1/pin-drain",
                "mosfet-stress/switch-q1/state-on/coverage",
                "mosfet-stress/switch-q1/state-on/vds",
                "mosfet-stress/switch-q1/state-on/vgs",
            ),
            id="mosfet-stress",
        ),
    ),
)
def test_component_requirement_replays_and_rejects_omitted_checks(
    electrical_evidence_workspace: ElectricalEvidenceWorkspace,
    contract_field: str,
    requirement_factory: Callable[[], object],
    netlist_factory: Callable[[], str],
    output_name: str,
    expected_check_id: str,
    omitted_check_ids: tuple[str, ...],
) -> None:
    result = electrical_evidence_workspace.run_native_requirement(
        contract_field=contract_field,
        requirement=requirement_factory(),
        netlist_xml=netlist_factory(),
        output_name=output_name,
    )

    assert {check.id: check for check in result.checks}[expected_check_id].status == "PASS"
    electrical_evidence_workspace.verify()
    reject_omitted_electrical_checks(electrical_evidence_workspace, omitted_check_ids)


@pytest.mark.parametrize("name", ["summary.json", "netlist.xml", "netlist.command.json"])
def test_native_netlist_evidence_changed_during_electrical_replay_is_rejected(
    electrical_evidence_workspace: ElectricalEvidenceWorkspace,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
) -> None:
    workspace = electrical_evidence_workspace
    workspace.run_native_requirement(
        contract_field="component_voltage_ratings",
        requirement=component_voltage_requirement(),
        netlist_xml=component_voltage_netlist_xml(),
        output_name="native-freshness",
    )
    workspace.verify()
    target = (workspace.root / workspace.native.path).parent / name
    original_bytes = target.read_bytes()
    target.write_bytes(original_bytes + b" ")
    with pytest.raises(ValueError):
        workspace.verify()
    target.write_bytes(original_bytes)
    original = electrical_evidence.waveform_checks
    changed = False

    def mutate_after_read(path: Path, case: SimulationCase) -> tuple[ElectricalCheck, ...]:
        nonlocal changed
        checks = original(path, case)
        if not changed:
            changed = True
            target.write_bytes(target.read_bytes() + b" ")
        return checks

    monkeypatch.setattr(electrical_evidence, "waveform_checks", mutate_after_read)
    with pytest.raises(ValueError, match="(Native netlist evidence changed|Evidence hash differs)"):
        workspace.verify()
    assert changed
