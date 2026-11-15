"""Review authored pair skew bounds without a routed skew bundle map."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_candidate_aggregation import fingerprint
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.pcb_drc_models import (
    PcbDifferentialPairRuleMap,
    PcbDrcMaximumRequirement,
    PcbDrcMinMaxRequirement,
)
from kicad_tooling.hwrepo.pcb_pair_route_skew_scope import (
    PcbDifferentialPairRouteSkewScopeCandidate,
    pcb_differential_pair_route_skew_scope_candidates,
)
from kicad_tooling.hwrepo.pcb_signal_path_rule_models import (
    PcbSignalPathBundleRequirement,
    PcbSignalPathRequirement,
    PcbSignalPathRuleMap,
)
from tests.test_pcb_drc_coverage import pair_map

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.interface_lint]

RULE = "pcb.differential_pair_route_skew_scope_missing"


def signal_map(
    path_nets: tuple[str, ...], *, bundle_path_nets: tuple[str, ...] = ()
) -> PcbSignalPathRuleMap:
    paths = tuple(
        PcbSignalPathRequirement(
            id=f"path-{index}",
            basis=f"Synthetic reviewed route for {net}",
            net=net,
            from_pad=f"J1.{index}",
            to_pad=f"U1.{index}",
            length=PcbDrcMinMaxRequirement(min_nm=1),
        )
        for index, net in enumerate(path_nets, start=1)
    )
    bundled_ids = tuple(
        f"path-{index}"
        for index, net in enumerate(path_nets, start=1)
        if net.casefold() in {item.casefold() for item in bundle_path_nets}
    )
    bundles = (
        (
            PcbSignalPathBundleRequirement(
                id="synthetic-skew",
                basis="Synthetic pair route review",
                path_ids=bundled_ids,
                from_pad_pattern="J1-*",
                to_pad_pattern="U1-*",
                max_skew=PcbDrcMaximumRequirement(max_nm=100_000),
            ),
        )
        if len(bundled_ids) >= 2
        else ()
    )
    return PcbSignalPathRuleMap(
        basis="Synthetic independent signal-path map",
        paths=paths,
        bundles=bundles,
    )


def candidates(
    *,
    authored_pairs: PcbDifferentialPairRuleMap | None = None,
    authored_signal_paths: PcbSignalPathRuleMap | None = None,
    is_pcb_project: bool = True,
) -> tuple[Candidate, ...]:
    return pcb_differential_pair_route_skew_scope_candidates(
        authored_pairs or pair_map(), authored_signal_paths, is_pcb_project=is_pcb_project
    )


@pytest.mark.design_lint_rule(rule_id=RULE)
def test_skew_bounded_pair_without_signal_path_map_is_reviewable() -> None:
    (finding,) = candidates()

    assert isinstance(finding, PcbDifferentialPairRouteSkewScopeCandidate)
    assert finding.rule_id == RULE
    assert finding.evidence["positive_signal_path_ids"] == ()
    assert finding.evidence["negative_signal_path_ids"] == ()
    assert finding.evidence["signal_path_map_sha256"] == ("absent",)
    assert finding.evidence["declared_max_skew_nm"] == ("100000",)


@pytest.mark.design_lint_rule(rule_id=RULE)
def test_partial_paths_and_unbundled_pair_routes_remain_reviewable() -> None:
    (partial,) = candidates(authored_signal_paths=signal_map(("USB_D_P",)))
    (unbundled,) = candidates(authored_signal_paths=signal_map(("USB_D_P", "USB_D_N")))

    assert partial.evidence["positive_signal_path_ids"] == ("path-1",)
    assert partial.evidence["negative_signal_path_ids"] == ()
    assert unbundled.evidence["positive_signal_path_ids"] == ("path-1",)
    assert unbundled.evidence["negative_signal_path_ids"] == ("path-2",)


@pytest.mark.design_lint_rule(rule_id=RULE)
def test_skew_bundle_covering_both_exact_pair_nets_is_a_quiet_control() -> None:
    assert (
        candidates(
            authored_signal_paths=signal_map(
                ("USB_D_P", "USB_D_N"), bundle_path_nets=("USB_D_P", "USB_D_N")
            )
        )
        == ()
    )


@pytest.mark.design_lint_rule(rule_id=RULE)
def test_pairs_without_skew_bounds_and_non_pcb_projects_are_out_of_scope() -> None:
    authored = pair_map()
    without_skew = authored.model_copy(
        update={
            "requirements": tuple(
                item.model_copy(update={"skew": None}) for item in authored.requirements
            )
        }
    )

    assert candidates(authored_pairs=without_skew) == ()
    assert candidates(is_pcb_project=False) == ()
    assert pcb_differential_pair_route_skew_scope_candidates(None, None, is_pcb_project=True) == ()


@pytest.mark.design_lint_rule(rule_id=RULE)
def test_evidence_and_candidate_fingerprint_are_stable() -> None:
    authored = signal_map(("USB_D_P", "USB_D_N"))
    first = candidates(authored_signal_paths=authored)
    second = candidates(authored_signal_paths=authored)

    assert first == second
    finding = first[0]
    assert isinstance(finding, PcbDifferentialPairRouteSkewScopeCandidate)
    projected = Candidate(
        rule_id=finding.rule_id,
        subject=finding.subject,
        message=finding.message,
        evidence=finding.evidence,
    )
    assert fingerprint(finding) == fingerprint(projected)


@pytest.mark.design_lint_rule(rule_id=RULE)
def test_pair_and_path_order_do_not_change_finding_order() -> None:
    path_map = signal_map(("USB_D_P", "USB_D_N"))
    reordered = path_map.model_copy(update={"paths": tuple(reversed(path_map.paths))})
    original_findings = candidates(authored_signal_paths=path_map)
    reordered_findings = candidates(authored_signal_paths=reordered)
    assert tuple(item.subject for item in original_findings) == tuple(
        item.subject for item in reordered_findings
    )
    assert tuple(item.evidence["positive_signal_path_ids"] for item in original_findings) == tuple(
        item.evidence["positive_signal_path_ids"] for item in reordered_findings
    )
