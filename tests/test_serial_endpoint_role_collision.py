"""Review same-role UART functions shared by a connector and local IC."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintIgnore
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.models import DesignLintRuleOverride
from kicad_tooling.hwrepo.serial_endpoint_role_collision import (
    RULE_ID,
    serial_endpoint_role_collision_candidates,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.serial_endpoint_role_collision import (
    serial_endpoint_role_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _report(source, *, mode: str | None = None, ignore: DesignLintIgnore | None = None):
    rules = (
        ()
        if mode is None
        else (
            DesignLintRuleOverride(rule_id=RULE_ID, mode=mode, reason="Review UART endpoint roles"),
        )
    )
    ignores = () if ignore is None else (ignore,)
    return evaluate(
        "synthetic-serial-endpoint-role-collision",
        coach(source),
        DesignLintPolicy(rules=rules, ignores=ignores),
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_same_role_tx_and_rx_endpoint_pairs_request_review() -> None:
    report = _report(serial_endpoint_role_netlist())
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert tuple(item.subject for item in findings) == (
        "J1/U1: serial RX functions share UART_RX",
        "J1/U1: serial TX functions share UART_TX",
    )
    assert all(item.mode == "review" for item in findings)
    assert findings[0].evidence == {
        "connector": ("J1",),
        "controller": ("U1",),
        "role": ("RX",),
        "pins": ("J1.2", "U1.2"),
        "functions": ("UART1_RX", "UART1_RX"),
        "pin_types": ("input", "output"),
        "net": ("UART_RX",),
    }


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_correctly_crossed_tx_rx_and_unsupported_endpoints_are_controls() -> None:
    controls = (
        serial_endpoint_role_netlist(dnp=("J1",)),
        serial_endpoint_role_netlist(dnp=("U1",)),
        serial_endpoint_role_netlist(incomplete_connector_inventory=True),
    )

    for item in controls:
        assert not serial_endpoint_role_collision_candidates(item), item
    expanded_net_findings = serial_endpoint_role_collision_candidates(
        serial_endpoint_role_netlist(extra_net_pin=True)
    )
    assert tuple(item.subject for item in expanded_net_findings) == (
        "J1/U1: serial RX functions share UART_RX",
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_can_block_disable_and_ignore_exact_role_findings() -> None:
    initial = next(
        item for item in _report(serial_endpoint_role_netlist()).findings if item.rule_id == RULE_ID
    )
    blocked = _report(serial_endpoint_role_netlist(), mode="block")
    disabled = _report(serial_endpoint_role_netlist(), mode="off")
    ignored = _report(
        serial_endpoint_role_netlist(),
        ignore=DesignLintIgnore(
            rule_id=RULE_ID,
            fingerprint=initial.fingerprint,
            reason="Reviewed connector pin mapping",
        ),
    )

    assert blocked.status == "FAIL"
    assert (
        next(item for item in disabled.findings if item.rule_id == RULE_ID).disposition
        == "RULE_OFF"
    )
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_assignment_order_is_stable_and_crossing_the_roles_clears_findings() -> None:
    source = serial_endpoint_role_netlist()
    reordered = source.model_copy(update={"nets": dict(reversed(tuple(source.nets.items())))})

    assert serial_endpoint_role_collision_candidates(
        source
    ) == serial_endpoint_role_collision_candidates(reordered)
    assert not serial_endpoint_role_collision_candidates(
        serial_endpoint_role_netlist(collision=False)
    )
