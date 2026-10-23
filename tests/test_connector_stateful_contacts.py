"""Project-mapped mechanical connector contacts stay distinct in the schematic."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.connector_stateful_contact_models import (
    ConnectorStatefulContactMap,
)
from kicad_tooling.hwrepo.connector_stateful_contacts import (
    RULE_ID,
    stateful_connector_contact_findings,
)
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_candidate_aggregation import candidates
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract
from tests.design_lint_fixtures import coach
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
]


def _map() -> ConnectorStatefulContactMap:
    return ConnectorStatefulContactMap.model_validate_json(
        json.dumps(
            {
                "basis": "Synthetic contact-state map from a tooling-only datasheet fixture",
                "requirements": [
                    {
                        "id": "audio-jack-1",
                        "reference": "J1",
                        "expected_symbol": "Synthetic:AudioJack_2Contact",
                        "expected_value": "Synthetic Audio Jack",
                        "expected_footprint": "Synthetic:AudioJack_2Contact",
                        "expected_part_id": "SYNTH-AUDIO-JACK-001",
                        "native_pin_numbers": ["1", "2"],
                        "contact_pairs": [
                            {
                                "id": "tip-normal-contact",
                                "first_pin": "1",
                                "second_pin": "2",
                                "closed_when": "plug_removed",
                                "source_basis": "Synthetic datasheet section 2, contact table",
                            }
                        ],
                    }
                ],
            }
        )
    )


def _observed(
    *,
    tip_pair_same_net: bool = False,
    first_pin_unassigned: bool = False,
    dnp: bool = False,
    part_id: str = "SYNTH-AUDIO-JACK-001",
) -> NetlistContract:
    tip_contacts = ("J1.1", "J1.2") if tip_pair_same_net else ("J1.1",)
    nets = {
        "AUDIO_TIP": tip_contacts,
        "AUDIO_TIP_SWITCH": () if tip_pair_same_net else ("J1.2",),
    }
    if first_pin_unassigned:
        nets["AUDIO_TIP"] = ()
    return NetlistContract(
        components={
            "J1": ComponentContract(
                value="Synthetic Audio Jack",
                footprint="Synthetic:AudioJack_2Contact",
                part_id=part_id,
            )
        },
        nets={name: pins for name, pins in nets.items() if pins},
        unconnected_nets=({"unconnected-(J1-Pad1)": ("J1.1",)} if first_pin_unassigned else {}),
        dnp_components=("J1",) if dnp else (),
        component_symbols={"J1": "Synthetic:AudioJack_2Contact"},
        component_pin_numbers={"J1": ("1", "2")},
    )


def _findings(observed: NetlistContract) -> tuple[Candidate, ...]:
    return tuple(
        item
        for item in candidates(
            observed,
            connector_stateful_contact_map=_map(),
        )
        if item.rule_id == RULE_ID
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_hardwired_stateful_contacts_are_reviewed() -> None:
    findings = _findings(_observed(tip_pair_same_net=True))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == "J1: mapped switch contacts tip-normal-contact permanently_bypassed"
    assert finding.evidence["first_pin"] == ("J1.1",)
    assert finding.evidence["second_pin"] == ("J1.2",)
    assert finding.evidence["first_nets"] == finding.evidence["second_nets"] == ("AUDIO_TIP",)
    assert finding.evidence["closed_when"] == ("plug_removed",)
    assert finding.evidence["topology_state"] == ("permanently_bypassed",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_distinct_assigned_stateful_contacts_are_quiet() -> None:
    assert _findings(_observed()) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_audio_jack_like_symbol_is_not_inferred_without_a_project_map() -> None:
    assert stateful_connector_contact_findings(_observed(tip_pair_same_net=True), None) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unassigned_mapped_stateful_contact_is_reviewed() -> None:
    findings = _findings(_observed(first_pin_unassigned=True))

    assert len(findings) == 1
    assert findings[0].evidence["topology_state"] == ("unassigned",)
    assert findings[0].evidence["first_nets"] == ()
    assert findings[0].evidence["second_nets"] == ("AUDIO_TIP_SWITCH",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_connector_is_not_treated_as_a_fitted_contact_fault() -> None:
    assert _findings(_observed(tip_pair_same_net=True, dnp=True)) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_exact_part_identity_mismatch_is_visible_as_stale_map_evidence() -> None:
    findings = _findings(_observed(part_id="SYNTH-AUDIO-JACK-002"))

    assert len(findings) == 1
    assert "source" in findings[0].subject
    assert (
        "PART_ID is SYNTH-AUDIO-JACK-002; expected SYNTH-AUDIO-JACK-001"
        in (findings[0].evidence["identity_issues"])
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_contact_findings_are_stable_under_netlist_order_changes() -> None:
    forward = _findings(_observed(tip_pair_same_net=True))
    reverse = _findings(
        _observed(tip_pair_same_net=True).model_copy(
            update={
                "components": dict(reversed(tuple(_observed().components.items()))),
                "nets": dict(reversed(tuple(_observed(tip_pair_same_net=True).nets.items()))),
            }
        )
    )

    assert forward == reverse


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_stateful_contact_policy_is_project_authored_and_configurable() -> None:
    policy = DesignLintPolicy.model_validate_json(
        json.dumps(
            {
                "connector_stateful_contact_map": _map().model_dump(mode="json"),
                "rules": [
                    {
                        "rule_id": RULE_ID,
                        "mode": "block",
                        "reason": "Synthetic project requires this contact topology",
                    }
                ],
            }
        )
    )
    assert policy.connector_stateful_contact_map == _map()
    assert policy.rules == (
        DesignLintRuleOverride(
            rule_id=RULE_ID,
            mode="block",
            reason="Synthetic project requires this contact topology",
        ),
    )
    review = evaluate(
        "synthetic-stateful-contact",
        coach(_observed(tip_pair_same_net=True)),
        DesignLintPolicy(connector_stateful_contact_map=_map()),
    )
    assert review.status == "REVIEW"
    assert tuple(item.rule_id for item in review.findings) == (RULE_ID,)
    report = evaluate(
        "synthetic-stateful-contact",
        coach(_observed(tip_pair_same_net=True)),
        policy,
    )
    assert report.status == "FAIL"
    assert tuple(item.rule_id for item in report.findings) == (RULE_ID,)
    ignored = evaluate(
        "synthetic-stateful-contact",
        coach(_observed(tip_pair_same_net=True)),
        DesignLintPolicy(
            connector_stateful_contact_map=_map(),
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic project defers this contact check",
                ),
            ),
        ),
    )
    assert ignored.status == "PASS"
    assert tuple(item.disposition for item in ignored.findings) == ("RULE_OFF",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_contact_pair_must_bind_distinct_pins_in_the_exact_inventory() -> None:
    invalid = _map().model_dump(mode="json")
    invalid["requirements"][0]["contact_pairs"][0]["second_pin"] = "1"

    with pytest.raises(ValidationError, match="two distinct pins"):
        ConnectorStatefulContactMap.model_validate_json(json.dumps(invalid))


NATIVE_CASES = ("stateful-contact-fault", "stateful-contact-control")
EXPECTED_NATIVE_SOURCE_HASHES = {
    "stateful-contact-fault": "131715fd0c9d4b746a2dc3fe651356e775cfd9c5d5dcea8a98676bb741d881ff",
    "stateful-contact-control": "0d44469c1e8d5284289688e7f95154a600b43393cff13c7c2bf8ff9b129ac652",
}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_stateful_contact_native_fixture_sources_match_reviewed_hashes() -> None:
    fixture_root = (
        Path(__file__).resolve().parent / "fixtures/design_lint/stateful-connector-contacts"
    )
    assert {
        case: hashlib.sha256((fixture_root / f"{filename}.kicad_sch").read_bytes()).hexdigest()
        for case, filename in (
            ("stateful-contact-fault", "fault"),
            ("stateful-contact-control", "control"),
        )
    } == EXPECTED_NATIVE_SOURCE_HASHES


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") != "1",
    reason="digest-pinned native connector fixtures run in package acceptance",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_native_stateful_contact_fault_and_control_are_repeatable(
    tmp_path: Path,
    project: str,
    version: str,
) -> None:
    from kicad_tooling.ci_hosted_connector_return_context import (
        prepare_connector_return_fixture_context,
    )

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

    log = HostedLog(root, f"native-stateful-contact-{project}")
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=config.image,
        log=log,
        case_names=NATIVE_CASES,
        stage_prefix="stateful-contact-fixture",
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    native_events = tuple(
        item for item in events if item.get("stage") == "stateful-contact-fixture/native-export"
    )
    assert tuple(item["status"] for item in native_events) == ("START", "PASS")
    assert native_events[-1]["kicad_version"] == version
    assert context.source_hashes == EXPECTED_NATIVE_SOURCE_HASHES
    assert_native_fixture_mounts(root, native_events[-1]["command_receipt"])

    fault = context.reports[NATIVE_CASES[0], "first"]
    fault_findings = tuple(item for item in fault.findings if item.rule_id == RULE_ID)
    assert len(fault_findings) == 1
    assert fault_findings[0].evidence["first_nets"] == ("AUDIO_TIP",)
    assert fault_findings[0].evidence["second_nets"] == ("AUDIO_TIP",)
    control = context.reports[NATIVE_CASES[1], "first"]
    assert not tuple(item for item in control.findings if item.rule_id == RULE_ID)
    assert context.observed_contracts[NATIVE_CASES[0], "first"].component_pin_numbers["J1"] == (
        "1",
        "2",
    )
    assert context.observed_contracts[NATIVE_CASES[1], "first"].nets["AUDIO_TIP_SWITCH"] == (
        "J1.2",
    )
    for case in NATIVE_CASES:
        assert (
            context.normalized_netlist_hashes[case, "first"]
            == context.normalized_netlist_hashes[case, "repeat"]
        )
