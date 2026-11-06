"""Review connector returns that share a native protocol-signal net."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    DesignLintPolicy,
)
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.design_lint_fixtures import coach
from tests.electrical_parity_support import contract_netlist_xml
from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count
from tests.mcp_parity_support import parity_design_lint_policy, semantic_design_lint_report
from tests.synthetic_design_lint_project import (
    install_synthetic_netlist,
    run_design_lint_cli,
    synthetic_design_lint_project,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.return_path_lint,
]

RULE_ID = "connector.return_pin_shares_protocol_signal_net"
OWNER = (
    "kicad_tooling/hwrepo/connector_return_signal_net.py#return_pin_protocol_signal_net_candidates"
)


def _source(
    *,
    signal_function: str = "SDA",
    shared: bool = True,
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    nets = {"SDA_BUS": ("J1.1", "J1.2")} if shared else {"GND": ("J1.1",), "SDA_BUS": ("J1.2",)}
    return NetlistContract(
        components={"J1": ComponentContract(value="Synthetic two-pin port", footprint="")},
        nets=nets,
        dnp_components=dnp,
        component_symbols={"J1": "Connector_Generic:Conn_01x02"},
        component_pin_numbers={"J1": ("1", "2")},
        pin_functions={"J1.1": "GND", "J1.2": signal_function},
    )


def _report(source: NetlistContract, policy: DesignLintPolicy | None = None) -> DesignLintReport:
    return evaluate("synthetic-return-signal", coach(source), policy or DesignLintPolicy())


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_connector_return_sharing_i2c_signal_requests_review() -> None:
    report = _report(_source())

    assert report.status == "REVIEW"
    (finding,) = _findings(report)
    assert finding.mode == "review"
    assert finding.evidence == {
        "assigned_net": ("SDA_BUS",),
        "return_pins": ("J1.1",),
        "signal_pins": ("J1.2",),
        "signal_pin_roles": ("J1.2: native_function=SDA; protocol_role=I2C SDA",),
    }
    assert "does not establish the pinout" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("function", "expected_role"),
    (
        ("UART2_TXD", "UART TX uart2"),
        ("SCK", "SPI clock default"),
        ("CANH", "CAN CANH"),
        ("USB_D+", "USB data unindexed positive"),
        ("TDP", "Ethernet TX positive"),
    ),
)
def test_protocol_role_families_are_recognized_without_net_name_guessing(
    function: str, expected_role: str
) -> None:
    report = _report(_source(signal_function=function))

    (finding,) = _findings(report)
    assert finding.evidence["signal_pin_roles"] == (
        f"J1.2: native_function={function}; protocol_role={expected_role}",
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_separate_signal_and_return_nets_are_a_control() -> None:
    report = _report(_source(shared=False))

    assert not _findings(report)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_net_name_alone_and_unrecognized_pin_functions_are_controls() -> None:
    report = _report(_source(signal_function="Pin_2"))

    assert not _findings(report)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unpopulated_connector_does_not_support_a_candidate() -> None:
    report = _report(_source(dnp=("J1",)))

    assert not _findings(report)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_candidate_is_stable_under_netlist_order_and_repair_clears_it() -> None:
    source = _source()
    original = _findings(_report(source))[0]
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
        }
    )
    reordered_finding = _findings(_report(reordered))[0]
    repaired = _report(_source(shared=False))

    assert reordered_finding.fingerprint == original.fingerprint
    assert not _findings(repaired)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_review_block_off_and_exact_ignore_policy_apply() -> None:
    baseline = _findings(_report(_source()))[0]
    blocked = _report(
        _source(),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic interface review requires a signal-return disposition.",
                ),
            )
        ),
    )
    disabled = _report(
        _source(),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic control confirms project-scoped rule configuration.",
                ),
            )
        ),
    )
    ignored = _report(
        _source(),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=baseline.fingerprint,
                    reason="Reviewed synthetic intentional tie.",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert _findings(disabled)[0].disposition == "RULE_OFF"
    assert disabled.status == "PASS"
    assert _findings(ignored)[0].disposition == "IGNORED"
    assert ignored.status == "PASS"


def test_catalog_points_to_small_connector_theme_owner() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)
    assert rule.theme == "connectors"
    assert rule.default_mode == "review"
    assert rule.implementation_owner == OWNER
    assert OWNER in rule.implementation_refs
    assert line_count(REPO_ROOT / "kicad_tooling/hwrepo/connector_return_signal_net.py") < (
        IMPLEMENTATION_MAX_LINES
    )


@pytest.mark.parity_lint
@pytest.mark.slow
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_connector_return_signal_lint_cli_mcp_parity(tmp_path: Path) -> None:
    root, native = synthetic_design_lint_project(
        tmp_path,
        parity_design_lint_policy(DesignLintPolicy()),
    )
    source = _source()
    install_synthetic_netlist(native, contract_netlist_xml(source))

    process = run_design_lint_cli(tmp_path, root, native)
    assert process.returncode in {0, 1}, process.stderr + process.stdout
    cli = DesignLintReport.model_validate_json(process.stdout)

    async def inspect_mcp() -> DesignLintReport:
        async with Client(create_server(root), mode="legacy") as client:
            result = await client.call_tool(
                "inspect_design_lint",
                {
                    "project_id": "controller",
                    "native_summary": native.relative_to(root).as_posix(),
                },
            )
        assert not result.is_error, result.content
        assert result.structured_content is not None
        return DesignLintReport.model_validate_json(json.dumps(result.structured_content))

    mcp = asyncio.run(inspect_mcp())
    assert semantic_design_lint_report(cli) == semantic_design_lint_report(mcp)
    assert len(_findings(cli)) == 1


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_mapped_return_signal_rule_owns_complete_source_mapped_contacts() -> None:
    from tests.design_lint_fixtures.connector_mapped_signal_sharing import (
        signal_sharing_coverage,
        signal_sharing_netlist,
    )

    source = signal_sharing_netlist()
    coverage = signal_sharing_coverage(
        source,
        signal_names=("SIGNAL_RETURN", "UART_RX"),
        roles=("return", "signal"),
    )
    report = evaluate(
        "synthetic-return-signal-mapped",
        coach(source),
        DesignLintPolicy(),
        connector_coverage=coverage,
    )

    assert "connector.mapped_signal_return_share_net" in {item.rule_id for item in report.findings}
    assert not _findings(report)
