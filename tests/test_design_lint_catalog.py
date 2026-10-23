"""The shipped lint catalog is tied to implementation and fault/control regressions."""

from __future__ import annotations

import ast
import hashlib
import re
from importlib.resources import files
from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

from kicad_tooling.design_lint import catalog_text
from kicad_tooling.hwrepo.design_lint import (
    evaluate,
    rule_catalog,
    text_report,
)
from kicad_tooling.hwrepo.design_lint_rule_models import (
    DesignLintRuleCatalog,
    DesignLintRuleCatalogDocument,
    DesignLintRuleMetadata,
)
from kicad_tooling.hwrepo.design_lint_rule_types import DesignLintRuleId
from kicad_tooling.hwrepo.models import DesignLintPolicy, DesignLintReport
from tests.design_lint_fixtures import (
    coach,
    observed,
)

pytestmark = pytest.mark.design_lint


def test_catalog_ids_match_the_closed_policy_rule_type() -> None:
    catalog = rule_catalog()
    catalog_ids = tuple(item.rule_id for item in catalog.rules)
    assert sorted(catalog_ids) == sorted(get_args(DesignLintRuleId))
    assert len(catalog_ids) == len(set(catalog_ids))
    assert all(item.status == "active" for item in catalog.rules)
    assert all(
        item.default_mode == "off"
        for item in catalog.rules
        if item.rule_id
        in {
            "schematic.wire_end_on_pin_line",
            "schematic.pin_tip_on_wire_interior",
            "schematic.wire_endpoint_near_pin_tip",
            "schematic.label_near_wire_endpoint",
            "schematic.unmarked_wire_crossing",
            "schematic.unmarked_t_junction",
            "schematic.coincident_text_anchors",
            "schematic.free_text_overlap",
            "schematic.free_text_over_wire",
            "schematic.free_text_over_symbol_body",
            "schematic.wire_through_symbol_body",
            "pcb.board_only_footprint",
            "connector.footprint_peer_pin_all_open",
            "connector.generic_peer_pin_all_open",
            "component.generic_peer_pin_all_open",
            "component.generic_peer_pin_mixed_open",
            "component.generic_peer_pin_assignment_outlier",
            "component.mosfet_gate_without_visible_source_bias",
            "component.mosfet_gate_direct_drive",
            "component.mosfet_terminal_order_on_named_rails",
            "component.mosfet_drain_source_same_net",
            "component.mosfet_gate_source_same_net",
            "component.mosfet_gate_drain_same_net",
            "component.bjt_terminal_order_on_named_rails",
            "component.bjt_collector_emitter_same_net",
            "component.bjt_base_emitter_same_net",
            "component.bjt_base_collector_same_net",
            "component.bjt_base_without_visible_emitter_bias",
            "bus.serial_tx_rx_same_net",
            "bus.serial_tx_outputs_share_net",
        }
    )
    assert all(
        item.default_mode == "review"
        for item in catalog.rules
        if item.rule_id
        not in {
            "schematic.wire_end_on_pin_line",
            "schematic.pin_tip_on_wire_interior",
            "schematic.wire_endpoint_near_pin_tip",
            "schematic.label_near_wire_endpoint",
            "schematic.unmarked_wire_crossing",
            "schematic.unmarked_t_junction",
            "schematic.coincident_text_anchors",
            "schematic.free_text_overlap",
            "schematic.free_text_over_wire",
            "schematic.free_text_over_symbol_body",
            "schematic.wire_through_symbol_body",
            "pcb.board_only_footprint",
            "pcb.required_fitted_reference",
            "connector.footprint_peer_pin_all_open",
            "connector.generic_peer_pin_all_open",
            "component.generic_peer_pin_all_open",
            "component.generic_peer_pin_mixed_open",
            "component.generic_peer_pin_assignment_outlier",
            "component.mosfet_gate_without_visible_source_bias",
            "component.mosfet_gate_direct_drive",
            "component.mosfet_terminal_order_on_named_rails",
            "component.mosfet_drain_source_same_net",
            "component.mosfet_gate_source_same_net",
            "component.mosfet_gate_drain_same_net",
            "component.bjt_terminal_order_on_named_rails",
            "component.bjt_collector_emitter_same_net",
            "component.bjt_base_emitter_same_net",
            "component.bjt_base_collector_same_net",
            "component.bjt_base_without_visible_emitter_bias",
            "bus.serial_tx_rx_same_net",
            "bus.serial_tx_outputs_share_net",
        }
    )
    assert all(item.maturity == "synthetic_validated" for item in catalog.rules)


def test_default_block_requires_project_authored_population_evidence() -> None:
    catalog = rule_catalog()
    blocking_rules = {item.rule_id: item for item in catalog.rules if item.default_mode == "block"}

    assert set(blocking_rules) == {"pcb.required_fitted_reference"}
    requirement = blocking_rules["pcb.required_fitted_reference"]
    assert "project-authored required fitted-reference map" in requirement.predicate
    assert "do not infer requirements from similar components" in requirement.predicate
    assert requirement.fault_fixtures
    assert requirement.valid_control_fixtures
    assert requirement.maturity == "synthetic_validated"


def test_catalog_digest_binds_the_shipped_metadata_bytes() -> None:
    content = files("kicad_tooling.hwrepo").joinpath("design-lint-rules.json").read_bytes()
    assert rule_catalog().sha256 == hashlib.sha256(content).hexdigest()
    assert rule_catalog().schema_version == "3"
    assert {item.theme for item in rule_catalog().rules} <= {
        "connectors",
        "interfaces",
        "components",
        "power",
        "returns",
        "schematic",
        "pcb",
    }


def test_current_catalog_requires_an_explicit_theme_for_every_rule() -> None:
    catalog = rule_catalog()
    assert all(item.theme != "legacy" for item in catalog.rules)
    assert all(item.implementation_owner != "legacy" for item in catalog.rules)
    assert all(item.implementation_owner in item.implementation_refs for item in catalog.rules)

    document = {
        "schema_version": "3",
        "rules": tuple(item.model_dump(mode="python") for item in catalog.rules),
    }
    document["rules"][0].pop("theme")
    with pytest.raises(ValidationError, match="must declare their theme"):
        DesignLintRuleCatalogDocument.model_validate(document)

    document["rules"][0]["theme"] = catalog.rules[0].theme
    document["rules"][0].pop("implementation_owner")
    with pytest.raises(ValidationError, match="must declare an implementation owner"):
        DesignLintRuleCatalogDocument.model_validate(document)

    invalid_owner = catalog.rules[0].model_dump(mode="python")
    invalid_owner["implementation_owner"] = "kicad_tooling/hwrepo/missing.py#missing_check"
    with pytest.raises(ValidationError, match="must be listed in implementation_refs"):
        DesignLintRuleMetadata.model_validate(invalid_owner)


def test_standalone_catalog_text_includes_default_and_evidence_limits() -> None:
    catalog = rule_catalog()
    rendered = catalog_text(catalog)
    assert f"{len(catalog.rules)} active rules" in rendered
    assert catalog.sha256 in rendered
    assert "connector.repeated_pin_function" in rendered
    assert "theme connectors" in rendered
    assert (
        "Owner: kicad_tooling/hwrepo/connector_identity.py#similar_connector_pin_groups" in rendered
    )
    assert "default review" in rendered
    assert "Evidence:" in rendered
    assert "Limits:" in rendered


def test_legacy_catalog_report_defaults_new_metamorphic_fields_to_unreviewed() -> None:
    metadata = rule_catalog().rules[0].model_dump(mode="python")
    metadata.pop("theme")
    metadata.pop("implementation_owner")
    metadata.pop("metamorphic_fixtures")
    metadata.pop("metamorphic_status")
    metadata.pop("metamorphic_not_applicable_basis")
    legacy_rule = DesignLintRuleMetadata.model_validate(metadata)
    assert legacy_rule.theme == "legacy"
    assert legacy_rule.implementation_owner == "legacy"
    assert legacy_rule.metamorphic_status == "unreviewed"
    legacy_catalog = DesignLintRuleCatalog(
        schema_version="1",
        sha256="a" * 64,
        rules=(legacy_rule,),
    )
    assert legacy_catalog.schema_version == "1"


def test_backlog_baseline_ids_match_the_active_catalog() -> None:
    backlog = (Path(__file__).parents[1] / "docs/DESIGN_LINT_BACKLOG.md").read_text(
        encoding="utf-8"
    )
    count_match = re.search(r"The following (\d+) rules are implemented", backlog)
    if count_match is None:
        pytest.fail("Backlog must state the active rule count")
    expected_count = int(count_match.group(1))
    baseline = backlog[count_match.end() :].split("This baseline catches", 1)[0]
    documented_ids = re.findall(r"^- `([^`]+)`$", baseline, flags=re.MULTILINE)
    active_ids = [item.rule_id for item in rule_catalog().rules if item.status == "active"]

    assert expected_count == len(active_ids)
    assert len(documented_ids) == expected_count
    assert sorted(documented_ids) == sorted(active_ids)


def test_documented_catalog_counts_match_the_active_catalog() -> None:
    repository = Path(__file__).parents[1]
    active_count = sum(item.status == "active" for item in rule_catalog().rules)
    count_pattern = re.compile(r"catalog\s+currently\s+contains\s+(\d+)\s+active\s+rules")

    for relative_path in ("docs/DESIGN_LINT.md", "docs/DESIGN_LINT_BACKLOG.md"):
        content = (repository / relative_path).read_text(encoding="utf-8")
        matches = count_pattern.findall(content)
        assert matches == [str(active_count)], relative_path


def test_active_catalog_entries_require_fault_and_control_coverage() -> None:
    entry = rule_catalog().rules[0].model_dump(mode="python")
    entry["fault_fixtures"] = ()
    with pytest.raises(ValidationError):
        DesignLintRuleMetadata.model_validate(entry)

    catalog = rule_catalog()
    with pytest.raises(ValidationError, match="rule IDs must be unique"):
        DesignLintRuleCatalog(
            schema_version=catalog.schema_version,
            sha256=catalog.sha256,
            rules=(catalog.rules[0], catalog.rules[0]),
        )


def test_required_native_fixture_switches_must_be_unique() -> None:
    entry = next(
        rule.model_dump(mode="python")
        for rule in rule_catalog().rules
        if rule.required_native_fixtures
    )
    fixture = entry["required_native_fixtures"][0]
    entry["required_native_fixtures"] = (fixture, fixture)
    with pytest.raises(ValidationError, match="required native fixtures must be unique"):
        DesignLintRuleMetadata.model_validate(entry)


def test_metamorphic_status_requires_fixture_or_reasoned_not_applicability() -> None:
    entry = rule_catalog().rules[0].model_dump(mode="python")
    entry["metamorphic_fixtures"] = ()
    entry["metamorphic_status"] = "covered"
    with pytest.raises(ValidationError, match="needs a registered fixture"):
        DesignLintRuleMetadata.model_validate(entry)

    entry["metamorphic_status"] = "not_applicable"
    with pytest.raises(ValidationError, match="needs a reason"):
        DesignLintRuleMetadata.model_validate(entry)

    entry["metamorphic_not_applicable_basis"] = (
        "This rule evaluates a fixed scalar threshold without reordered source collections."
    )
    validated = DesignLintRuleMetadata.model_validate(entry)
    assert validated.metamorphic_status == "not_applicable"


def test_hashseed_report_tests_are_linked_to_each_rule_they_assert() -> None:
    repository = Path(__file__).parents[1]
    rules = {rule.rule_id: rule for rule in rule_catalog().rules}

    for path in sorted((repository / "tests").glob("test_design_lint_determinism_*.py")):
        module = ".".join(path.relative_to(repository).with_suffix("").parts)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            rule_ids = {
                item.value
                for item in ast.walk(node)
                if isinstance(item, ast.Constant)
                and isinstance(item.value, str)
                and item.value in rules
            }
            reference = f"{module}.{node.name}"
            for rule_id in sorted(rule_ids):
                assert reference in rules[rule_id].metamorphic_fixtures, (
                    f"{reference} asserts {rule_id} but is not linked from its rule catalog entry"
                )


def test_metamorphic_coverage_inventory_matches_the_backlog() -> None:
    catalog = rule_catalog()
    active = [item for item in catalog.rules if item.status == "active"]
    counts = {
        status: sum(item.metamorphic_status == status for item in active)
        for status in ("covered", "not_applicable", "unreviewed")
    }
    backlog = (Path(__file__).parents[1] / "docs/DESIGN_LINT_BACKLOG.md").read_text(
        encoding="utf-8"
    )
    match = re.search(
        r"Current catalog\s+audit:\s*(\d+) covered,\s*(\d+) not applicable,\s*"
        r"(\d+) unreviewed\.",
        backlog,
    )
    if match is None:
        pytest.fail("Backlog must publish the metamorphic coverage inventory")
    assert tuple(int(value) for value in match.groups()) == (
        counts["covered"],
        counts["not_applicable"],
        counts["unreviewed"],
    )
    assert counts["unreviewed"] == 0, (
        "classify every active rule with metamorphic fixtures or a reasoned not-applicable basis"
    )


def test_reports_include_catalog_and_reject_uncatalogued_finding_ids() -> None:
    report = evaluate("synthetic-ports", coach(observed()), DesignLintPolicy())
    assert report.rule_catalog is not None
    assert report.rule_catalog.sha256 == rule_catalog().sha256
    assert f"{len(rule_catalog().rules)} active rules" in text_report(report)
    assert "Schematic geometry coverage: NOT_REQUESTED" in text_report(report)
    assert "PCB decoupling coverage: NOT_REQUESTED" in text_report(report)
    assert "PCB protection-path coverage: NOT_REQUESTED" in text_report(report)
    assert "PCB track-width coverage: NOT_REQUESTED" in text_report(report)
    assert "PCB reference-plane coverage: NOT_REQUESTED" in text_report(report)
    assert "PCB switching-loop coverage: NOT_REQUESTED" in text_report(report)
    assert "PCB differential-pair DRC rule coverage: NOT_REQUESTED" in text_report(report)
    assert "PCB keepout intent coverage: NOT_REQUESTED" in text_report(report)
    assert "I2C address-map coverage: NOT_REQUESTED" in text_report(report)
    assert "Regulator feedback coverage: NOT_REQUESTED" in text_report(report)
    assert "RC filter coverage: NOT_REQUESTED" in text_report(report)
    assert "Connector return-distribution coverage: NOT_REQUESTED" in text_report(report)

    without_return_rule = report.rule_catalog.model_copy(
        update={
            "rules": tuple(
                item for item in report.rule_catalog.rules if item.rule_id != "net.numbered_returns"
            )
        }
    )
    malformed = report.model_dump(mode="python")
    malformed["rule_catalog"] = without_return_rule.model_dump(mode="python")
    with pytest.raises(ValueError, match="absent from the active catalog"):
        DesignLintReport.model_validate(malformed)
