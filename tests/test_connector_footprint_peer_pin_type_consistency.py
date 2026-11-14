"""Review electrical-type mismatches on otherwise matching connector aliases."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.connector_footprint_peer_metadata import (
    connector_footprint_peer_pin_metadata_assignment_divergences,
)
from kicad_tooling.hwrepo.connector_footprint_peer_pin_type_consistency import (
    connector_footprint_peer_pin_electrical_type_disagreements,
)
from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintPolicy, DesignLintRuleOverride
from tests.connector_footprint_peer_support import lint_report, peer_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID = "connector.footprint_peer_pin_electrical_type_disagreement"


def _source(
    *,
    types: tuple[str, str] = ("passive", "power_in"),
    anchor_types: tuple[str, str] = ("passive", "passive"),
    functions: tuple[str, str] = ("Pin_1", "Pin_2"),
    assignments: tuple[tuple[str | None, str | None], ...] = (
        ("RETURN", "RETURN"),
        ("DATA", "DATA"),
    ),
    part_id: str | None = None,
    dnp: tuple[str, ...] = (),
    incomplete_inventory: bool = False,
    missing_metadata_pin: str | None = None,
):
    observed = peer_netlist(
        assignments=assignments,
        functions=functions,
        electrical_types=(anchor_types[0], anchor_types[1]),
        part_id=part_id,
        dnp=dnp,
        incomplete_inventory=incomplete_inventory,
        missing_metadata_pin=missing_metadata_pin,
    )
    pin_types = {
        **observed.pin_electrical_types,
        "J1.1": anchor_types[0],
        "J2.1": anchor_types[1],
        "J1.2": types[0],
        "J2.2": types[1],
    }
    if missing_metadata_pin is not None:
        pin_types.pop(missing_metadata_pin, None)
    return observed.model_copy(update={"pin_electrical_types": pin_types})


def _findings(report):
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


def _different_peer_functions_source():
    observed = _source()
    return observed.model_copy(update={"pin_functions": {**observed.pin_functions, "J2.2": "VBUS"}})


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_same_assigned_pin_with_native_type_disagreement_is_localized() -> None:
    observed = _source()
    report = lint_report(observed)

    (finding,) = _findings(report)
    assert finding.mode == "review"
    assert finding.subject == "Synthetic two-contact connector [Synthetic:Connector_2x1] pin 2"
    assert finding.evidence["pin_function"] == ("Pin_2", "Pin_2")
    assert finding.evidence["peer_pin_electrical_types"] == (
        "J1.2=passive",
        "J2.2=power_in",
    )
    assert finding.evidence["assignments"] == ("J1.2=DATA", "J2.2=DATA")
    assert finding.evidence["common_anchor_pin_numbers"] == ("1",)
    assert "does not establish which type is correct" in finding.message
    assert connector_footprint_peer_pin_metadata_assignment_divergences(observed) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "source",
    (
        pytest.param(_source(types=("passive", "passive")), id="same-type-control"),
        pytest.param(_different_peer_functions_source(), id="different-function-control"),
        pytest.param(
            _source(assignments=(("RETURN_A", "RETURN_B"), ("DATA", "DATA"))),
            id="no-common-pin-metadata-anchor",
        ),
        pytest.param(
            _source(assignments=(("RETURN", "RETURN"), ("DATA_A", "DATA_B"))),
            id="target-net-split-belongs-to-assignment-rules",
        ),
        pytest.param(
            _source(assignments=(("RETURN", "RETURN"), ("DATA", None))),
            id="target-open-control",
        ),
        pytest.param(
            _source(incomplete_inventory=True),
            id="incomplete-peer-inventory",
        ),
        pytest.param(
            _source(missing_metadata_pin="J2.2"),
            id="missing-target-metadata",
        ),
        pytest.param(
            _source(anchor_types=("input", "passive")),
            id="other-type-disagreement-prevents-comparison",
        ),
        pytest.param(_source(part_id="SYNTHETIC-PART"), id="part-id-peer-family-excluded"),
        pytest.param(_source(dnp=("J2",)), id="dnp-peer-excluded"),
    ),
)
def test_incomplete_or_nonmatching_peer_evidence_stays_quiet(source) -> None:
    assert not _findings(lint_report(source))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_can_block_disable_or_ignore_the_exact_finding() -> None:
    observed = _source()
    default_finding = _findings(lint_report(observed))[0]
    blocked = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project promotes this symbol consistency review.",
                ),
            )
        ),
    )
    disabled = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic project documents intentional alias type differences.",
                ),
            )
        ),
    )
    ignored = lint_report(
        observed,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=default_finding.fingerprint,
                    reason="Synthetic project accepts this exact reviewed symbol variant.",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert _findings(blocked)[0].mode == "block"
    assert _findings(disabled)[0].disposition == "RULE_OFF"
    assert _findings(ignored)[0].disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_finding_is_stable_under_native_mapping_reordering() -> None:
    source = _source()
    shuffled = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
        }
    )
    initial = _findings(lint_report(source))[0]
    repeated = _findings(lint_report(shuffled))[0]

    assert (initial.fingerprint, initial.evidence) == (repeated.fingerprint, repeated.evidence)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_candidate_evidence_cannot_be_forged_away_from_source() -> None:
    (candidate,) = connector_footprint_peer_pin_electrical_type_disagreements(_source())

    with pytest.raises(ValueError, match="must match its native source evidence"):
        replace(candidate, evidence={**candidate.evidence, "assignments": ("J1.2=OTHER",)})


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_declared_custom_connector_references_remain_source_validated() -> None:
    observed = _source()
    reference_mapping = {"J1": "U1", "J2": "U2"}

    def rename_pin(pin: str) -> str:
        reference, number = pin.rsplit(".", maxsplit=1)
        return f"{reference_mapping[reference]}.{number}"

    declared = observed.model_copy(
        update={
            "components": {
                reference_mapping[key]: value for key, value in observed.components.items()
            },
            "nets": {
                name: tuple(rename_pin(pin) for pin in pins) for name, pins in observed.nets.items()
            },
            "component_symbols": {
                reference_mapping[key]: value for key, value in observed.component_symbols.items()
            },
            "component_pin_numbers": {
                reference_mapping[key]: value
                for key, value in observed.component_pin_numbers.items()
            },
            "pin_functions": {
                rename_pin(pin): value for pin, value in observed.pin_functions.items()
            },
            "pin_electrical_types": {
                rename_pin(pin): value for pin, value in observed.pin_electrical_types.items()
            },
        }
    )

    (candidate,) = connector_footprint_peer_pin_electrical_type_disagreements(
        declared,
        ("U1", "U2"),
    )

    assert candidate.evidence["assignments"] == ("U1.2=DATA", "U2.2=DATA")
