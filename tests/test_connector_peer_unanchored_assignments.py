"""Review generic connector-alias splits only in a current reviewed peer scope."""

from __future__ import annotations

from typing import cast

import pytest

from kicad_tooling.hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
from kicad_tooling.hwrepo.connector_coverage import (
    source_matched_connector_peer_assignment_groups,
)
from kicad_tooling.hwrepo.design_lint import evaluate as evaluate_design_lint
from kicad_tooling.hwrepo.models import (
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    InterfacePin,
    InterfaceRecord,
)
from tests.connector_footprint_peer_support import (
    NETLIST_SHA256,
    PeerNetlistOverrides,
    peer_netlist,
)

pytestmark = [pytest.mark.connector_lint, pytest.mark.design_lint]

RULE_ID = "connector.footprint_peer_pin_unanchored_assignment_divergence"
PEER_GROUP = "synthetic-peer-connectors"
PEER_BASIS = "Synthetic connector pinouts were reviewed as one peer set"
NATIVE_FAULT_CASE = "footprint-alias-unanchored-fault"
NATIVE_CONTROL_CASE = "footprint-alias-control"
NATIVE_CASES = (NATIVE_FAULT_CASE, NATIVE_CONTROL_CASE)


def reviewed_coverage(observed, groups: tuple[str, str] = (PEER_GROUP, PEER_GROUP)):
    interface = InterfaceRecord(
        id="synthetic-generic-port",
        revision="synthetic-1",
        pins=tuple(
            InterfacePin(
                number=str(number),
                signal=f"contact-{number}",
                direction="bidirectional",
                voltage_domain="synthetic-domain",
                mating="synthetic peer",
                orientation="straight",
                mechanical_clearance="synthetic",
            )
            for number in (1, 2)
        ),
    )
    reviews = tuple(
        ConnectorInterfaceReview(
            reference=reference,
            disposition="interface",
            basis="Synthetic exact pin mapping",
            interface_id="synthetic-generic-port",
            pin_map={"1": "1", "2": "2"},
            peer_assignment_group=group,
            peer_assignment_basis=PEER_BASIS,
        )
        for reference, group in zip(("J1", "J2"), groups, strict=True)
    )
    return evaluate_connector_coverage(
        observed,
        ("synthetic-generic-port",),
        reviews,
        interfaces={"synthetic-generic-port": interface},
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256="f" * 64,
        inventory_review=ConnectorInventoryReview(
            basis="Synthetic connector inventory was reviewed"
        ),
    )


def lint_report(observed, coverage=None, policy: DesignLintPolicy | None = None):
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-peer-unanchored-assignment",
        observed=observed,
        netlist_sha256=NETLIST_SHA256,
    )
    return evaluate_design_lint(
        coach.project_id,
        coach,
        policy or DesignLintPolicy(),
        connector_coverage=coverage,
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unanchored_generic_alias_assignments_in_reviewed_peer_group_need_review() -> None:
    observed = peer_netlist(assignments=(("PORT_A", "PORT_B"), ("DATA_A", "DATA_B")))
    coverage = reviewed_coverage(observed)

    assert source_matched_connector_peer_assignment_groups(observed, coverage) == {
        "J1": (PEER_GROUP, PEER_BASIS),
        "J2": (PEER_GROUP, PEER_BASIS),
    }
    report = lint_report(observed, coverage)
    findings = [item for item in report.findings if item.rule_id == RULE_ID]

    assert report.status == "REVIEW"
    assert len(findings) == 2
    assert findings[0].evidence["assignments"] == ("J1.1=PORT_A", "J2.1=PORT_B")
    assert findings[0].evidence["common_anchor_pin_numbers"] == ()
    assert findings[0].evidence["peer_assignment_group"] == (PEER_GROUP,)
    assert findings[1].evidence["assignments"] == ("J1.2=DATA_A", "J2.2=DATA_B")
    assert "does not say the nets must match" in findings[0].message
    coverage = report.connector_peer_pin_coverage
    assert coverage is not None
    alias_coverage = coverage.footprint_alias_coverage
    assert alias_coverage.status == "EVALUATED"
    assert alias_coverage.unanchored_different_assignment_pin_group_count == 2
    assert alias_coverage.reviewed_unanchored_divergence_finding_count == 2


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_common_assignments_and_unreviewed_or_separate_groups_are_quiet() -> None:
    common = peer_netlist(assignments=(("COMMON", "COMMON"), ("DATA", "DATA")))
    assert not any(
        item.rule_id == RULE_ID for item in lint_report(common, reviewed_coverage(common)).findings
    )

    split = peer_netlist(assignments=(("PORT_A", "PORT_B"), ("DATA_A", "DATA_B")))
    unreviewed = lint_report(split)
    assert not any(item.rule_id == RULE_ID for item in unreviewed.findings)

    separate = lint_report(split, reviewed_coverage(split, ("port-a", "port-b")))
    assert not any(item.rule_id == RULE_ID for item in separate.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "overrides",
    (
        pytest.param({"dnp": ("J2",)}, id="dnp-peer"),
        pytest.param({"incomplete_inventory": True}, id="incomplete-inventory"),
        pytest.param({"missing_metadata_pin": "J2.1"}, id="missing-native-metadata"),
        pytest.param(
            {"assignments": (("PORT_A", "PORT_B"), ("DATA", "DATA")), "open_pin": "J1.1"},
            id="open-contact",
        ),
        pytest.param(
            {
                "assignments": (("PORT_A", "PORT_B"), ("DATA", "DATA")),
                "ambiguous_pin": "J1.1",
            },
            id="ambiguous-assignment",
        ),
        pytest.param({"functions": ("TXD", "RXD")}, id="meaningful-functions"),
    ),
)
def test_incomplete_or_named_alias_evidence_stays_quiet(
    overrides: PeerNetlistOverrides,
) -> None:
    fixture_overrides = cast(PeerNetlistOverrides, dict(overrides))
    fixture_overrides.setdefault(
        "assignments",
        (("PORT_A", "PORT_B"), ("DATA_A", "DATA_B")),
    )
    observed = peer_netlist(**fixture_overrides)

    report = lint_report(observed, reviewed_coverage(observed))
    assert not any(item.rule_id == RULE_ID for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_stale_peer_mapping_does_not_scope_changed_native_assignments() -> None:
    original = peer_netlist(assignments=(("PORT_A", "PORT_B"), ("DATA_A", "DATA_B")))
    coverage = reviewed_coverage(original)
    changed = peer_netlist(assignments=(("COMMON", "COMMON"), ("DATA_A", "DATA_B")))

    assert source_matched_connector_peer_assignment_groups(changed, coverage) == {}
    report = lint_report(changed, coverage)
    assert not any(item.rule_id == RULE_ID for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("mode", "disposition"),
    (("review", "OPEN"), ("block", "OPEN"), ("off", "RULE_OFF")),
)
def test_reviewed_unanchored_candidate_obeys_project_mode(mode: str, disposition: str) -> None:
    observed = peer_netlist(assignments=(("PORT_A", "PORT_B"), ("DATA_A", "DATA_B")))
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Synthetic test of project-owned lint policy",
            ),
        )
    )

    findings = [
        item
        for item in lint_report(observed, reviewed_coverage(observed), policy).findings
        if item.rule_id == RULE_ID
    ]

    assert len(findings) == 2
    assert {item.mode for item in findings} == {mode}
    assert {item.disposition for item in findings} == {disposition}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unanchored_finding_is_stable_under_native_mapping_reordering() -> None:
    observed = peer_netlist(assignments=(("PORT_A", "PORT_B"), ("DATA_A", "DATA_B")))
    reordered = observed.model_copy(
        update={
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
        }
    )
    left = lint_report(observed, reviewed_coverage(observed))
    right = lint_report(reordered, reviewed_coverage(reordered))
    left_findings = tuple(item for item in left.findings if item.rule_id == RULE_ID)
    right_findings = tuple(item for item in right.findings if item.rule_id == RULE_ID)

    assert tuple((item.fingerprint, item.evidence) for item in left_findings) == tuple(
        (item.fingerprint, item.evidence) for item in right_findings
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_exact_ignore_is_limited_to_one_unanchored_pin_fingerprint() -> None:
    observed = peer_netlist(assignments=(("PORT_A", "PORT_B"), ("DATA_A", "DATA_B")))
    initial = lint_report(observed, reviewed_coverage(observed))
    ignored = next(item for item in initial.findings if item.rule_id == RULE_ID)
    policy = DesignLintPolicy(
        ignores=(
            DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=ignored.fingerprint,
                reason="Synthetic test of exact finding disposition",
            ),
        )
    )

    report = lint_report(observed, reviewed_coverage(observed), policy)
    findings = [item for item in report.findings if item.rule_id == RULE_ID]

    assert len(findings) == 2
    assert sum(item.disposition == "IGNORED" for item in findings) == 1
    assert sum(item.disposition == "OPEN" for item in findings) == 1


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.skipif(
    __import__("os").environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") != "1",
    reason="digest-pinned native connector fixtures run in package acceptance",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_native_unanchored_alias_fault_and_common_control_repeat(
    tmp_path, project: str, version: str
) -> None:
    import json
    from pathlib import Path

    from kicad_tooling.ci_hosted_connector_return_context import (
        prepare_connector_return_fixture_context,
    )
    from kicad_tooling.ci_hosted_connector_return_fixture_sources import (
        CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES,
        connector_return_fixture_sources,
    )
    from kicad_tooling.ci_hosted_support import HostedLog
    from kicad_tooling.hwrepo.electrical import selected_config
    from tests.native_fixture_support import assert_native_fixture_mounts
    from tests.synthetic_design_lint_project import (
        PINNED_NATIVE_KICAD_IMAGES,
        synthetic_design_lint_project,
    )

    expected_hashes = {
        NATIVE_FAULT_CASE: "2d8fbf390f3b154d77c0bbc603a7260ddc0ff27cf3b9b2e74ab19242dfc4aa40",
        NATIVE_CONTROL_CASE: "d5c77a1b8de808ab82c9f98f0172af7f6f933ce43536dabe00c6fbf83e048e28",
    }
    fixture_root = Path(__file__).resolve().parent / "fixtures/design_lint"
    fixture_sources = connector_return_fixture_sources(fixture_root)
    assert {
        case: CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES[case] for case in NATIVE_CASES
    } == expected_hashes
    assert {
        NATIVE_FAULT_CASE: fixture_sources[NATIVE_FAULT_CASE],
        NATIVE_CONTROL_CASE: fixture_sources[NATIVE_CONTROL_CASE],
    } == {
        NATIVE_FAULT_CASE: fixture_root
        / "connector-footprint-alias-native/unanchored-fault.kicad_sch",
        NATIVE_CONTROL_CASE: fixture_root / "connector-footprint-alias-native/control.kicad_sch",
    }

    image = PINNED_NATIVE_KICAD_IMAGES[version]
    root, _ = synthetic_design_lint_project(
        tmp_path,
        DesignLintPolicy(),
        project_id=project,
        kicad_version=version,
        image=image,
    )
    config = selected_config(root, project)
    assert (config.kicad_version, config.image) == (version, image)
    log = HostedLog(root, f"native-unanchored-peer-{project}")
    context = prepare_connector_return_fixture_context(
        root,
        project,
        image=config.image,
        log=log,
        case_names=NATIVE_CASES,
        stage_prefix="unanchored-footprint-peer-fixture",
    )
    assert context.source_hashes == expected_hashes
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    export_events = tuple(
        event
        for event in events
        if event.get("stage") == "unanchored-footprint-peer-fixture/native-export"
    )
    assert tuple(event["status"] for event in export_events) == ("START", "PASS")
    assert export_events[-1]["kicad_version"] == version
    assert_native_fixture_mounts(root, export_events[-1]["command_receipt"])

    fault_reports = tuple(
        lint_report(
            context.observed_contracts[NATIVE_FAULT_CASE, run],
            reviewed_coverage(context.observed_contracts[NATIVE_FAULT_CASE, run]),
        )
        for run in ("first", "repeat")
    )
    control_reports = tuple(
        lint_report(
            context.observed_contracts[NATIVE_CONTROL_CASE, run],
            reviewed_coverage(context.observed_contracts[NATIVE_CONTROL_CASE, run]),
        )
        for run in ("first", "repeat")
    )
    fault_findings = tuple(item for item in fault_reports[0].findings if item.rule_id == RULE_ID)
    assert len(fault_findings) == 2
    assert fault_reports[1].model_dump(mode="json") == fault_reports[0].model_dump(mode="json")
    assert not any(
        item.rule_id == RULE_ID for report in control_reports for item in report.findings
    )
    assert control_reports[1].model_dump(mode="json") == control_reports[0].model_dump(mode="json")
    for case in NATIVE_CASES:
        assert (
            context.normalized_netlist_hashes[case, "first"]
            == context.normalized_netlist_hashes[case, "repeat"]
        )
