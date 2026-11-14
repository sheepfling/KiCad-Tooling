"""Focused tests for package acceptance and prerelease lint selection."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from kicad_tooling.package_assets import REQUIRED_WHEEL_ASSETS, wheel_contents
from kicad_tooling.package_build import clear_distribution_build_cache
from scripts import ci


@pytest.mark.parametrize(
    "missing_asset",
    (
        "kicad_tooling/hwrepo/design-lint-rules.json",
        "kicad_tooling/hwrepo/pcb_variant_probe.py.in",
        "kicad_tooling/hwrepo/native_pcb_probe_touch_clearance.py.in",
        "kicad_tooling/hwrepo/native_pcb_probe_holes.py.in",
        "kicad_tooling/hwrepo/native_pcb_probe_models.py.in",
        "kicad_tooling/hwrepo/assets/three_d_viewer.js",
        "kicad_tooling/hwrepo/assets/threejs-LICENSE.txt",
        "kicad_tooling/package_build.py",
        "kicad_tooling/pytest_scope.py",
        "kicad_tooling/hwrepo/component_bjt_base_drive.py",
        "kicad_tooling/hwrepo/component_bjt_base_bias.py",
        "kicad_tooling/hwrepo/component_bjt_symbols.py",
        "kicad_tooling/hwrepo/component_mosfet_symbols.py",
        "kicad_tooling/hwrepo/design_lint_component_mosfet_terminals.py",
        "kicad_tooling/hwrepo/component_pin_types.py",
        "kicad_tooling/hwrepo/component_role_models.py",
        "kicad_tooling/hwrepo/power_path_models.py",
        "kicad_tooling/hwrepo/power_sequence_models.py",
        "kicad_tooling/hwrepo/power_connectivity_models.py",
        "kicad_tooling/hwrepo/ic_decoupling_models.py",
        "kicad_tooling/hwrepo/analysis_state_models.py",
        "kicad_tooling/hwrepo/crystal_network_models.py",
        "kicad_tooling/hwrepo/pcb_keepout_models.py",
        "kicad_tooling/hwrepo/usb_c_models.py",
        "kicad_tooling/hwrepo/spi_clock_data_same_net.py",
        "kicad_tooling/hwrepo/spi_control_same_net.py",
        "kicad_tooling/hwrepo/spi_role_assignments.py",
        "kicad_tooling/ci_hosted_spi_clock_control_same_net.py",
        "kicad_tooling/hwrepo/can_tx_rx_same_net.py",
        "kicad_tooling/ci_hosted_can_tx_rx_same_net.py",
        "kicad_tooling/hwrepo/usb_data_same_net.py",
        "kicad_tooling/ci_hosted_usb_data_same_net.py",
        "kicad_tooling/hwrepo/usb_data_pair_endpoints.py",
        "kicad_tooling/hwrepo/usb_data_pair_resistive_bridge.py",
        "kicad_tooling/ci_hosted_usb_data_pair_resistive_bridge.py",
        "kicad_tooling/hwrepo/usb_c_cc_same_net.py",
        "kicad_tooling/hwrepo/usb_c_cc_controller_same_net.py",
        "kicad_tooling/hwrepo/usb_c_cc_endpoint_pairing.py",
        "kicad_tooling/hwrepo/serial_endpoint_role_collision.py",
        "kicad_tooling/hwrepo/mcp_workflow_design_lint.py",
        "kicad_tooling/hwrepo/design_lint_usb_c_same_net_candidates.py",
        "kicad_tooling/ci_hosted_usb_c_cc_controller_same_net.py",
        "kicad_tooling/ci_hosted_usb_c_cc_endpoint_crossed.py",
        "kicad_tooling/ci_hosted_usb_c_cc_same_net.py",
        "kicad_tooling/hwrepo/netlist_pin_assignments.py",
        "kicad_tooling/hwrepo/rs485_ab_same_net.py",
        "kicad_tooling/ci_hosted_rs485_ab_same_net.py",
        "kicad_tooling/ci_hosted_kicad10_images.py",
        "kicad_tooling/hwrepo/can_signal_functions.py",
        "kicad_tooling/hwrepo/can_tx_output_sharing.py",
        "kicad_tooling/hwrepo/component_references.py",
        "kicad_tooling/hwrepo/signal_pair_tx_output_sharing.py",
        "kicad_tooling/ci_hosted_can_tx_output_sharing.py",
        "kicad_tooling/hwrepo/connector_return_distribution_models.py",
        "kicad_tooling/hwrepo/connector_mapped_signal_sharing.py",
        "kicad_tooling/hwrepo/connector_mapped_signal_split_nets.py",
        "kicad_tooling/hwrepo/connector_reviewed_peer_signal_split.py",
        "kicad_tooling/hwrepo/connector_reviewed_peer_signal_evidence.py",
        "kicad_tooling/hwrepo/connector_reviewed_peer_signal_domains.py",
        "kicad_tooling/hwrepo/connector_reviewed_peer_distinct_signals.py",
        "kicad_tooling/hwrepo/fixtures/pcb-return-four-port-db9-return-control.kicad_pcb",
        "kicad_tooling/hwrepo/fixtures/pcb-return-four-port-db9-connector-island.kicad_pcb",
        "kicad_tooling/hwrepo/fixtures/pcb-return-four-port-db9-single-open.kicad_pcb",
    ),
    ids=(
        "rule-catalog",
        "native-pcb-variant-probe",
        "native-touch-clearance-probe",
        "native-pcb-probe-holes",
        "native-pcb-probe-models",
        "offline-3d-viewer-bundle",
        "offline-3d-viewer-license",
        "package-build-service",
        "pytest-scope-service",
        "bjt-base-drive-rule",
        "bjt-base-bias-rule",
        "bjt-symbol-role-owner",
        "mosfet-symbol-role-owner",
        "mosfet-same-net-lint-owner",
        "component-pin-type-service",
        "component-role-models",
        "power-path-models",
        "power-sequence-models",
        "power-connectivity-models",
        "ic-decoupling-models",
        "analysis-state-models",
        "crystal-network-models",
        "pcb-keepout-models",
        "usb-c-models",
        "spi-clock-control-same-net-lint-owner",
        "spi-clock-chip-select-same-net-lint-owner",
        "spi-role-assignments-service",
        "spi-clock-control-same-net-native-fixture-lane",
        "can-tx-rx-same-net-rule-owner",
        "can-tx-rx-same-net-native-fixture-lane",
        "usb-data-same-net-rule-owner",
        "usb-data-same-net-native-fixture-lane",
        "usb-data-pair-endpoints-owner",
        "usb-data-pair-resistive-bridge-rule-owner",
        "usb-data-pair-resistive-bridge-native-fixture-lane",
        "usb-c-cc-same-net-rule-owner",
        "usb-c-cc-controller-same-net-rule-owner",
        "usb-c-cc-endpoint-crossed-rule-owner",
        "serial-endpoint-role-collision-rule-owner",
        "mcp-workflow-design-lint-catalog",
        "usb-c-same-net-candidate-coordinator",
        "usb-c-cc-controller-native-fixture-lane",
        "usb-c-cc-endpoint-crossed-native-fixture-lane",
        "usb-c-cc-same-net-native-fixture-lane",
        "shared-pin-net-assignment-projection",
        "rs485-ab-same-net-rule-owner",
        "rs485-ab-same-net-native-fixture-lane",
        "shared-kicad10-native-images",
        "can-signal-functions",
        "can-tx-output-sharing-rule-owner",
        "component-reference-service",
        "shared-tx-output-groups",
        "can-tx-output-sharing-native-fixture-lane",
        "connector-return-distribution-models",
        "mapped-connector-signal-sharing-rule-owner",
        "mapped-connector-signal-split-nets-rule-owner",
        "reviewed-peer-signal-split-rule-owner",
        "reviewed-peer-signal-evidence-owner",
        "reviewed-peer-signal-domains-rule-owner",
        "reviewed-peer-distinct-signals-rule-owner",
        "four-port-return-control-board",
        "four-port-return-island-board",
        "four-port-return-open-contact-board",
    ),
)
@pytest.mark.architecture
def test_wheel_requires_rule_catalog_and_theme_owned_models(
    tmp_path: Path, missing_asset: str
) -> None:
    wheel = tmp_path / "synthetic.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(
            "synthetic.dist-info/METADATA",
            "Name: kicad-team-tooling\nVersion: 1.0.0\n\n",
        )
        for path in REQUIRED_WHEEL_ASSETS - {missing_asset}:
            archive.writestr(path, "synthetic")
    with pytest.raises(ValueError, match=re.escape(missing_asset)):
        wheel_contents(wheel)


def test_distribution_build_clears_stale_staging_without_removing_receipts(
    tmp_path: Path,
) -> None:
    stale_module = tmp_path / "build/lib/kicad_tooling/hwrepo/removed_rule.py"
    stale_bdist = tmp_path / "build/bdist.synthetic"
    stale_temp = tmp_path / "build/temp.synthetic"
    receipt = tmp_path / "build/ci/run-1/events.jsonl"
    native_receipt = tmp_path / "build/native/run-1/snapshot.json"
    for path in (
        stale_module,
        stale_bdist / "payload",
        stale_temp / "payload",
        receipt,
        native_receipt,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("generated", encoding="utf-8")

    clear_distribution_build_cache(tmp_path)

    assert not (tmp_path / "build/lib").exists()
    assert not stale_bdist.exists()
    assert not stale_temp.exists()
    assert receipt.read_text(encoding="utf-8") == "generated"
    assert native_receipt.read_text(encoding="utf-8") == "generated"


def test_stale_install_is_rejected_before_regressions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ci, "ROOT", tmp_path)
    monkeypatch.setattr(ci.sys, "argv", ["scripts/ci.py"])
    stage = Mock()
    stage.return_value.stdout = str(tmp_path / "other/kicad_tooling/__init__.py")
    monkeypatch.setattr(ci, "stage", stage)

    assert ci.main() == 1
    assert [call.args[0] for call in stage.call_args_list] == ["development-install"]


def test_native_schematic_geometry_gate_remains_opt_in_at_package_level(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ci, "ROOT", tmp_path)
    monkeypatch.setattr(ci.sys, "argv", ["scripts/ci.py"])
    monkeypatch.setenv("KICAD_RUN_NATIVE_SCHEMATIC_GEOMETRY", "1")
    stage = Mock()
    stage.return_value.stdout = str(tmp_path / "kicad_tooling/__init__.py")
    monkeypatch.setattr(ci, "stage", stage)
    native_geometry = Mock()
    monkeypatch.setattr("kicad_tooling.hwrepo.native_geometry_lane.run", native_geometry)
    monkeypatch.setattr(
        ci,
        "build_distributions",
        Mock(side_effect=StopIteration("stop after checks")),
    )

    with pytest.raises(StopIteration, match="stop after checks"):
        ci.main()

    native_geometry.assert_called_once()
    assert native_geometry.call_args.args[0] == tmp_path
    assert native_geometry.call_args.args[1].parent == tmp_path / "build/ci"
    assert native_geometry.call_args.args[2] is stage
