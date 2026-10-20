"""Pytest regressions for conservative return-label name review."""

from __future__ import annotations

import hashlib

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintReport,
    NetlistContract,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.return_path_lint,
]


NUMBERED_RULE = "net.numbered_returns"
UNINDEXED_RULE = "net.return_labels_without_pin_roles"


def lint_report(
    net_names: tuple[str, str], *, pin_functions: tuple[str, str] = ("7", "7")
) -> DesignLintReport:
    nets_by_name: dict[str, list[str]] = {}
    for index, net_name in enumerate(net_names, start=1):
        nets_by_name.setdefault(net_name, []).append(f"J{index}.7")
    nets = {net_name: tuple(pins) for net_name, pins in nets_by_name.items()}
    functions = {f"J{index}.7": function for index, function in enumerate(pin_functions, start=1)}
    observed = NetlistContract(components={}, nets=nets, pin_functions=functions)
    digest = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-return-name-review",
        observed=observed,
        netlist_sha256=digest,
    )
    return evaluate(coach.project_id, coach, DesignLintPolicy())


def test_letter_suffixed_ground_nets_without_return_pin_roles_request_review() -> None:
    report = lint_report(("GNDA", "GNDD"))

    finding = next(item for item in report.findings if item.rule_id == UNINDEXED_RULE)
    assert report.status == "REVIEW"
    assert finding.evidence == {"GNDA": ("J1.7",), "GNDD": ("J2.7",)}
    assert NUMBERED_RULE not in {item.rule_id for item in report.findings}
    assert "labels alone do not establish that they should be joined" in finding.message


def test_numbered_letter_suffixed_ground_nets_are_grouped_for_review() -> None:
    report = lint_report(("GNDA1", "GNDA2"))

    finding = next(item for item in report.findings if item.rule_id == NUMBERED_RULE)
    assert report.status == "REVIEW"
    assert finding.evidence == {"GNDA1": ("J1.7",), "GNDA2": ("J2.7",)}
    assert UNINDEXED_RULE not in {item.rule_id for item in report.findings}


def test_explicit_return_pin_functions_suppress_letter_suffix_prompt() -> None:
    report = lint_report(("GNDA", "GNDD"), pin_functions=("GND", "RTN"))

    assert report.status == "PASS"
    assert not any(item.rule_id in {NUMBERED_RULE, UNINDEXED_RULE} for item in report.findings)


def test_longer_non_return_tokens_do_not_match_letter_suffix_rule() -> None:
    report = lint_report(("GNDAUDIO", "GNDBUS"))

    assert report.status == "PASS"
    assert not any(item.rule_id in {NUMBERED_RULE, UNINDEXED_RULE} for item in report.findings)


@pytest.mark.parametrize(
    "net_names",
    [
        pytest.param(("RET1", "RET2"), id="number-after-token"),
        pytest.param(("PORT1_RET", "PORT2_RET"), id="number-before-token"),
    ],
)
def test_numbered_ret_tokens_request_review(net_names: tuple[str, str]) -> None:
    report = lint_report(net_names)

    finding = next(item for item in report.findings if item.rule_id == NUMBERED_RULE)
    assert report.status == "REVIEW"
    assert finding.evidence == {
        name: (f"J{index}.7",) for index, name in enumerate(net_names, start=1)
    }
    assert UNINDEXED_RULE not in {item.rule_id for item in report.findings}


def test_unindexed_ret_labels_request_review_without_return_pin_roles() -> None:
    report = lint_report(("RET_USB", "RET_SERIAL"))

    finding = next(item for item in report.findings if item.rule_id == UNINDEXED_RULE)
    assert report.status == "REVIEW"
    assert finding.evidence == {"RET_SERIAL": ("J2.7",), "RET_USB": ("J1.7",)}


def test_common_ret_and_reset_labels_are_valid_controls() -> None:
    common = lint_report(("RET", "RET"))
    reset_names = lint_report(("RESET1", "RESET2"))
    explicit_return_functions = lint_report(("RET_USB", "RET_SERIAL"), pin_functions=("RET", "RET"))

    for report in (common, reset_names, explicit_return_functions):
        assert report.status == "PASS"
        assert not any(item.rule_id in {NUMBERED_RULE, UNINDEXED_RULE} for item in report.findings)
