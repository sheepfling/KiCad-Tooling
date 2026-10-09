"""Synthetic regressions for missing power-output assignments among peers."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    NetlistContract,
)

RULE_ID = "component.peer_power_output_unconnected"
SIGNAL_RULE_ID = "component.peer_signal_output_unconnected"


def peer_power_output_netlist(
    *,
    references: tuple[str, ...] = ("U1", "U2"),
    output_nets: tuple[str | None, ...] = ("VOUT", None),
    dnp: tuple[str, ...] = (),
    symbols: dict[str, str] | None = None,
    output_electrical_types: tuple[str, ...] | None = None,
    output_function: str = "OUT",
    missing_inventory: tuple[str, ...] = (),
    ambiguous_outputs: tuple[str, ...] = (),
) -> NetlistContract:
    if len(references) != len(output_nets):
        raise ValueError("Each peer needs one output-net case")
    symbols = symbols or {reference: "Synthetic:PowerModule" for reference in references}
    output_electrical_types = output_electrical_types or tuple("power_out" for _ in references)
    components = {
        reference: ComponentContract(value="Synthetic module", footprint="Synthetic:Module")
        for reference in references
    }
    nets: dict[str, tuple[str, ...]] = {"DATA": tuple(f"{reference}.1" for reference in references)}
    for reference, net in zip(references, output_nets, strict=True):
        if net is not None:
            nets[net] = (*nets.get(net, ()), f"{reference}.2")
        if reference in ambiguous_outputs:
            nets[f"ALSO_{reference}"] = (f"{reference}.2",)
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        pin_functions={
            **{f"{reference}.1": "IO" for reference in references},
            **{f"{reference}.2": output_function for reference in references},
        },
        pin_electrical_types={
            f"{reference}.2": electrical_type
            for reference, electrical_type in zip(references, output_electrical_types, strict=True)
        },
        component_pin_numbers={
            reference: ("1", "2") for reference in references if reference not in missing_inventory
        },
    )


def lint_report(
    observed: NetlistContract,
    policy: DesignLintPolicy | None = None,
) -> DesignLintReport:
    serialized = observed.model_dump_json().encode("utf-8")
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-peer-power-output",
        netlist_sha256=hashlib.sha256(serialized).hexdigest(),
        observed=observed,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy())


def test_reports_an_open_native_power_output_pin_when_an_exact_peer_is_connected() -> None:
    report = lint_report(peer_power_output_netlist())
    findings = [item for item in report.findings if item.rule_id == RULE_ID]

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.evidence["symbol"] == ("Synthetic:PowerModule",)
    assert finding.evidence["pin_number"] == ("2",)
    assert finding.evidence["pin_electrical_type"] == ("power_out",)
    assert finding.evidence["unassigned_pins"] == ("U2.2",)
    assert finding.evidence["U1.2"] == ("VOUT",)
    assert finding.evidence["U2.2"] == ()
    assert "do not require their outputs to share a net" in finding.message
    assert "component.unconnected_power_input" not in {item.rule_id for item in report.findings}


def test_reports_an_open_native_signal_output_pin_when_an_exact_peer_is_connected() -> None:
    report = lint_report(peer_power_output_netlist(output_electrical_types=("output", "output")))
    findings = [item for item in report.findings if item.rule_id == SIGNAL_RULE_ID]

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.evidence["symbol"] == ("Synthetic:PowerModule",)
    assert finding.evidence["pin_number"] == ("2",)
    assert finding.evidence["pin_electrical_type"] == ("output",)
    assert finding.evidence["unassigned_pins"] == ("U2.2",)
    assert finding.evidence["U1.2"] == ("VOUT",)
    assert finding.evidence["U2.2"] == ()
    assert "do not require their outputs to share a net" in finding.message
    assert RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.parametrize(
    "output_nets",
    (("VOUT", "VOUT"), ("VOUT_A", "VOUT_B")),
)
def test_assigned_peer_outputs_are_valid_same_or_separate_net_controls(
    output_nets: tuple[str, str],
) -> None:
    report = lint_report(peer_power_output_netlist(output_nets=output_nets))

    assert RULE_ID not in {item.rule_id for item in report.findings}
    assert report.status == "PASS"


@pytest.mark.parametrize(
    "output_nets",
    (("VOUT", "VOUT"), ("VOUT_A", "VOUT_B")),
)
def test_assigned_signal_peer_outputs_are_valid_same_or_separate_net_controls(
    output_nets: tuple[str, str],
) -> None:
    report = lint_report(
        peer_power_output_netlist(
            output_nets=output_nets,
            output_electrical_types=("output", "output"),
        )
    )

    assert SIGNAL_RULE_ID not in {item.rule_id for item in report.findings}
    assert report.status == "PASS"


@pytest.mark.parametrize(
    "observed",
    (
        peer_power_output_netlist(
            output_nets=(None, None), output_electrical_types=("output", "output")
        ),
        peer_power_output_netlist(
            output_nets=("VOUT", None),
            dnp=("U2",),
            output_electrical_types=("output", "output"),
        ),
        peer_power_output_netlist(
            output_nets=("VOUT", None),
            symbols={"U1": "Synthetic:SourceA", "U2": "Synthetic:SourceB"},
            output_electrical_types=("output", "output"),
        ),
        peer_power_output_netlist(
            output_nets=("VOUT", None),
            missing_inventory=("U2",),
            output_electrical_types=("output", "output"),
        ),
        peer_power_output_netlist(
            output_nets=("VOUT", None),
            ambiguous_outputs=("U1",),
            output_electrical_types=("output", "output"),
        ),
        peer_power_output_netlist(output_nets=("VOUT", None)),
    ),
)
def test_signal_output_prompt_skips_incomplete_or_non_signal_peer_evidence(
    observed: NetlistContract,
) -> None:
    assert SIGNAL_RULE_ID not in {item.rule_id for item in lint_report(observed).findings}


@pytest.mark.parametrize(
    "observed",
    (
        peer_power_output_netlist(output_nets=(None, None)),
        peer_power_output_netlist(output_nets=("VOUT", None), dnp=("U2",)),
        peer_power_output_netlist(
            output_nets=("VOUT", None),
            symbols={"U1": "Synthetic:SourceA", "U2": "Synthetic:SourceB"},
        ),
        peer_power_output_netlist(output_nets=("VOUT", None), missing_inventory=("U2",)),
        peer_power_output_netlist(output_nets=("VOUT", None), ambiguous_outputs=("U1",)),
        peer_power_output_netlist(
            output_nets=("VOUT", None), output_electrical_types=("power_in", "power_in")
        ),
    ),
)
def test_skips_open_all_dnp_different_symbol_incomplete_ambiguous_and_non_output_cases(
    observed: NetlistContract,
) -> None:
    assert RULE_ID not in {item.rule_id for item in lint_report(observed).findings}


@pytest.mark.parametrize("output_function", ("VDD", "GND"))
def test_named_supply_and_return_outputs_keep_their_specific_findings(
    output_function: str,
) -> None:
    report = lint_report(peer_power_output_netlist(output_function=output_function))
    findings = {item.rule_id: item for item in report.findings}

    assert RULE_ID not in findings
    specific_rule = (
        "component.unconnected_return_pin"
        if output_function == "GND"
        else "component.unconnected_supply_pin"
    )
    assert specific_rule in findings
    assert findings[specific_rule].evidence["U2.2"] == ()


def test_shield_named_power_output_remains_eligible_without_a_component_shield_rule() -> None:
    report = lint_report(peer_power_output_netlist(output_function="SHIELD"))
    findings = {item.rule_id: item for item in report.findings}

    assert RULE_ID in findings
    assert "component.unconnected_return_pin" not in findings
    assert findings[RULE_ID].evidence["unassigned_pins"] == ("U2.2",)


def test_rule_policy_and_exact_ignore_are_project_configurable() -> None:
    observed = peer_power_output_netlist()
    original = lint_report(observed)
    finding = next(item for item in original.findings if item.rule_id == RULE_ID)

    blocked = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project requires every peer output to be disposed",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"

    disabled = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic project disables this peer-output prompt",
                ),
            )
        ),
    )
    assert disabled.status == "PASS"
    assert next(item for item in disabled.findings if item.rule_id == RULE_ID).disposition == (
        "RULE_OFF"
    )

    ignored = lint_report(
        observed,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic project accepts the intentionally open peer output",
                ),
            )
        ),
    )
    ignored_finding = next(
        item for item in ignored.findings if item.fingerprint == finding.fingerprint
    )
    assert ignored_finding.disposition == "IGNORED"


def test_signal_output_review_supports_project_policy_and_exact_ignore() -> None:
    observed = peer_power_output_netlist(output_electrical_types=("output", "output"))
    original = lint_report(observed)
    finding = next(item for item in original.findings if item.rule_id == SIGNAL_RULE_ID)

    blocked = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=SIGNAL_RULE_ID,
                    mode="block",
                    reason="Synthetic project requires a disposition for peer outputs",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"

    disabled = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=SIGNAL_RULE_ID,
                    mode="off",
                    reason="Synthetic project disables the signal-output prompt",
                ),
            )
        ),
    )
    assert disabled.status == "PASS"

    ignored = lint_report(
        observed,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=SIGNAL_RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic project records this output as intentionally unused",
                ),
            )
        ),
    )
    ignored_finding = next(
        item for item in ignored.findings if item.fingerprint == finding.fingerprint
    )
    assert ignored_finding.disposition == "IGNORED"


def test_finding_is_stable_under_map_order_changes() -> None:
    source = peer_power_output_netlist()
    original = lint_report(source)
    reordered_source = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    reordered = lint_report(reordered_source)
    original_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in original.findings
        if item.rule_id == RULE_ID
    }
    reordered_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in reordered.findings
        if item.rule_id == RULE_ID
    }

    assert reordered_findings == original_findings


def test_signal_output_finding_is_stable_under_map_order_changes() -> None:
    source = peer_power_output_netlist(output_electrical_types=("output", "output"))
    original = lint_report(source)
    reordered_source = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    reordered = lint_report(reordered_source)

    def get_findings(report: DesignLintReport) -> dict[str, tuple[str, dict[str, tuple[str, ...]]]]:
        return {
            item.subject: (item.fingerprint, item.evidence)
            for item in report.findings
            if item.rule_id == SIGNAL_RULE_ID
        }

    assert get_findings(reordered) == get_findings(original)


def test_native_fixture_sources_match_reviewed_digests() -> None:
    fixture_root = Path(__file__).resolve().parent / "fixtures/design_lint"
    expected = {
        "component-peer-power-output-native/control.kicad_sch": "1b1d4bb236864087fe619819a3776ad5ef7f4d7d2e462ebb0fc8eaa2c6bf2399",
        "component-peer-power-output-native/fault.kicad_sch": "960e1030966e72c7ce197a971cf71418a8274e9e224ae60ef4d3d540af82790b",
        "component-peer-signal-output-native/control.kicad_sch": "bc5d93308322cd66b404bf058afde73b7b538e5590d84160d26b65af2e53f355",
        "component-peer-signal-output-native/fault.kicad_sch": "0d45eef6e2fc66da65781bb0e06d5c7601788aeb37489e60bf1302bfdad6a04a",
    }

    assert {
        name: hashlib.sha256((fixture_root / name).read_bytes()).hexdigest() for name in expected
    } == expected


def _run_native_peer_output_lane(kind: str) -> None:
    import json
    import shutil
    import tempfile

    from kicad_tooling.ci_hosted import (
        HostedLog,
        component_peer_power_output_fixture_lane,
        component_peer_signal_output_fixture_lane,
    )
    from kicad_tooling.hwrepo.electrical import selected_config
    from tests.support import reference_root

    repository = Path(__file__).resolve().parents[1]
    acceptance = repository / "build/ci"
    acceptance.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="native-peer-power-output-project-", dir=acceptance))
    shutil.copytree(
        reference_root(),
        root,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
    )
    expected_versions = {"controller": "10.0.0", "raspberry-pi-status-led": "10.0.5"}
    expected_images = {
        "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:"
        "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
        "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:"
        "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
    }
    lane = (
        component_peer_power_output_fixture_lane
        if kind == "power"
        else component_peer_signal_output_fixture_lane
    )
    fixture_lane = f"component-peer-{kind}-output-fixture"
    source_hashes = {
        "power": {
            "fault": "960e1030966e72c7ce197a971cf71418a8274e9e224ae60ef4d3d540af82790b",
            "control": "1b1d4bb236864087fe619819a3776ad5ef7f4d7d2e462ebb0fc8eaa2c6bf2399",
        },
        "signal": {
            "fault": "0d45eef6e2fc66da65781bb0e06d5c7601788aeb37489e60bf1302bfdad6a04a",
            "control": "bc5d93308322cd66b404bf058afde73b7b538e5590d84160d26b65af2e53f355",
        },
    }[kind]
    for project, version in expected_versions.items():
        config = selected_config(root, project)
        assert config.kicad_version == version
        assert config.image == expected_images[project]
        log = HostedLog(root, f"native-peer-{kind}-output-{project}")
        lane(root, project=project, image=config.image, log=log)
        events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
        results = {
            item["stage"]: item
            for item in events
            if item.get("stage", "").startswith(fixture_lane + "/")
        }
        assert set(results) == {
            f"{fixture_lane}/native-export",
            f"{fixture_lane}/fault",
            f"{fixture_lane}/control",
        }
        native = results[f"{fixture_lane}/native-export"]
        assert native["status"] == "PASS"
        assert native["kicad_version"] == version
        assert native["image"] == expected_images[project]
        for case, expected_pins, expected_status in (
            ("fault", "U2.2", "REVIEW"),
            ("control", "none", "PASS"),
        ):
            result = results[f"{fixture_lane}/{case}"]
            assert result["status"] == "PASS"
            assert result["source_sha256"] == source_hashes[case]
            assert result["lint_status"] == expected_status
            assert result["unassigned_pins"] == expected_pins
            assert result["repeatable"] == "true"
            assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_PEER_POWER_OUTPUT_FIXTURES") != "1",
    reason="pinned native fixtures run in package acceptance",
)
def test_peer_power_output_fault_and_control_on_pinned_native_versions() -> None:
    _run_native_peer_output_lane("power")


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_PEER_POWER_OUTPUT_FIXTURES") != "1",
    reason="pinned native fixtures run in package acceptance",
)
def test_peer_signal_output_fault_and_control_on_pinned_native_versions() -> None:
    _run_native_peer_output_lane("signal")
