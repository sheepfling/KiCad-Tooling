"""Source and command binding for named-variant population exports."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from kicad_tooling.hwrepo.design_lint_pcb_component_inventory_scan import (
    scan_pcb_component_inventory,
)
from kicad_tooling.hwrepo.models import CommandEvidence
from kicad_tooling.hwrepo.pcb_component_inventory_models import (
    PcbComponentInventoryCoverageReport,
)
from kicad_tooling.hwrepo.pcb_variant_population_capture import (
    _position_references,
    capture_variant_population,
    supports_named_variant_pcb_values,
)
from kicad_tooling.validate import hashes
from tests.design_lint_fixtures.pcb_component_inventory import netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]

IMAGE = "registry.example/kicad:10.0.5@sha256:" + "e" * 64
VARIANT = "Assembly A"


def test_named_variant_pcb_value_support_is_exact_version_scoped() -> None:
    assert not supports_named_variant_pcb_values("10.0.0")
    assert supports_named_variant_pcb_values("10.0.5")
    assert not supports_named_variant_pcb_values("10.1.0")


def make_project(tmp_path: Path) -> tuple[Path, SimpleNamespace]:
    root = tmp_path / "checkout"
    project_directory = root / "projects" / "synthetic"
    project_directory.mkdir(parents=True)
    base = project_directory / "controller"
    base.with_suffix(".kicad_pro").write_text(
        json.dumps({"schematic": {"variants": [{"name": VARIANT}]}}),
        encoding="utf-8",
    )
    base.with_suffix(".kicad_sch").write_text("synthetic schematic", encoding="utf-8")
    base.with_suffix(".kicad_pcb").write_text("synthetic board", encoding="utf-8")
    config = SimpleNamespace(
        project=(base.relative_to(root).as_posix() + ".kicad_pro"),
        source_roots=("projects",),
        image=IMAGE,
    )
    return root, config


def fake_native_runner(
    *,
    board_variant_present: bool = True,
    board_dnp: bool = False,
    mutate_schematic_after_export: bool = False,
):
    calls: list[tuple[str, ...]] = []

    def run_native(
        root: Path,
        output: Path,
        _image: str,
        entrypoint: str,
        command: tuple[str, ...],
    ) -> CommandEvidence:
        calls.append((entrypoint, *command))
        if entrypoint.endswith("python3"):
            request_name = command[-2].rsplit("/", 1)[-1]
            request = json.loads((output / request_name).read_text(encoding="utf-8"))
            rows = [
                {"name": name, "present_on_board": board_variant_present}
                for name in request["variants"]
            ]
            (output / command[-1].rsplit("/", 1)[-1]).write_text(
                json.dumps(
                    {
                        "schema_version": "1",
                        "board_sha256": request["board_sha256"],
                        "project_sha256": request["project_sha256"],
                        "variants": rows,
                    }
                ),
                encoding="utf-8",
            )
        else:
            output_name = command[command.index("--output") + 1].rsplit("/", 1)[-1]
            output_file = output / output_name
            if command[:3] == ("sch", "export", "netlist"):
                output_file.write_text("synthetic variant netlist", encoding="utf-8")
            else:
                fitted = "--exclude-dnp" in command
                references = () if fitted and board_dnp else ("U1",)
                with output_file.open("w", encoding="utf-8", newline="") as stream:
                    writer = csv.writer(stream)
                    writer.writerow(("Ref", "Val", "Package", "PosX", "PosY", "Rot", "Side"))
                    for reference in references:
                        writer.writerow(
                            (reference, "synthetic", "Synthetic:Probe_Module", 1, 2, 0, "top")
                        )
                if mutate_schematic_after_export and fitted:
                    schematic = root / "projects/synthetic/controller.kicad_sch"
                    schematic.write_text("changed schematic", encoding="utf-8")
        return CommandEvidence(
            argv=("docker", "run", entrypoint, *command),
            started_utc="2026-10-12T00:00:00+00:00",
            returncode=0,
        )

    return calls, run_native


def test_variant_capture_binds_same_name_and_source_hashes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, config = make_project(tmp_path)
    calls, runner = fake_native_runner(board_dnp=True)
    monkeypatch.setattr(
        "kicad_tooling.hwrepo.pcb_variant_population_capture.run_variant_native_command", runner
    )
    monkeypatch.setattr(
        "kicad_tooling.hwrepo.pcb_variant_population_capture.read_netlist",
        lambda _path: netlist(components={"U1": "Synthetic:Probe_Module"}),
    )

    capture = capture_variant_population(
        root,
        config,
        root / "build/design-lint/variant-population",
        expected_source_hashes=hashes(root, config.source_roots),
        kicad_version="10.0.5",
    )

    assert capture.coverage.status == "COMPLETE"
    assert (
        capture.coverage.project_sha256
        == hashes(root, config.source_roots)["projects/synthetic/controller.kicad_pro"]
    )
    assert len(capture.sources) == 1
    assert capture.sources[0].variant == VARIANT
    assert capture.sources[0].board_references == ("U1",)
    assert capture.sources[0].fitted_board_references == ()
    export_calls = [call for call in calls if call[0] == "kicad-cli"]
    assert len(export_calls) == 3
    assert all(call[call.index("--variant") + 1] == VARIANT for call in export_calls)
    assert any("--exclude-dnp" in call for call in export_calls)
    evidence = capture.coverage.evidence[0]
    assert evidence.netlist_sha256 != "0" * 64
    assert evidence.board_all_positions_sha256 != evidence.board_fitted_positions_sha256


def test_variant_capture_refuses_board_default_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, config = make_project(tmp_path)
    calls, runner = fake_native_runner(board_variant_present=False)
    monkeypatch.setattr(
        "kicad_tooling.hwrepo.pcb_variant_population_capture.run_variant_native_command", runner
    )

    capture = capture_variant_population(
        root,
        config,
        root / "build/design-lint/variant-population",
        expected_source_hashes=hashes(root, config.source_roots),
        kicad_version="10.0.5",
    )

    assert capture.coverage.status == "BLOCKED"
    assert "refusing to compare a default-variant fallback" in (capture.coverage.issue or "")
    assert len(capture.coverage.evidence) == 0
    assert not any(call[0] == "kicad-cli" for call in calls)
    assert capture.coverage.board_variant_probe_sha256 is not None
    assert capture.coverage.board_variant_request_sha256 is not None
    assert capture.coverage.board_variant_command_sha256 is not None


def test_project_without_named_variants_needs_no_native_variant_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, config = make_project(tmp_path)
    project = root / config.project
    project.write_text(json.dumps({"schematic": {"variants": []}}), encoding="utf-8")
    monkeypatch.setattr(
        "kicad_tooling.hwrepo.pcb_variant_population_capture.run_variant_native_command",
        lambda *_args, **_kwargs: pytest.fail("project has no named variants"),
    )
    output = root / "build/design-lint/variant-population"

    capture = capture_variant_population(
        root,
        config,
        output,
        expected_source_hashes=hashes(root, config.source_roots),
        kicad_version="10.0.5",
    )

    assert capture.coverage.status == "NOT_APPLICABLE"
    assert capture.sources == ()
    assert not output.exists()


def test_variant_capture_blocks_source_changes_during_exports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, config = make_project(tmp_path)
    calls, runner = fake_native_runner(mutate_schematic_after_export=True)
    monkeypatch.setattr(
        "kicad_tooling.hwrepo.pcb_variant_population_capture.run_variant_native_command", runner
    )
    monkeypatch.setattr(
        "kicad_tooling.hwrepo.pcb_variant_population_capture.read_netlist",
        lambda _path: netlist(components={"U1": "Synthetic:Probe_Module"}),
    )

    capture = capture_variant_population(
        root,
        config,
        root / "build/design-lint/variant-population",
        expected_source_hashes=hashes(root, config.source_roots),
        kicad_version="10.0.5",
    )

    assert capture.coverage.status == "BLOCKED"
    assert "changed during variant population capture" in (capture.coverage.issue or "")
    assert capture.sources == ()
    assert len(calls) == 4


def test_position_csv_parser_requires_one_reference_per_row(tmp_path: Path) -> None:
    csv_path = tmp_path / "positions.csv"
    csv_path.write_text("Reference,Value\nU1,probe\n", encoding="utf-8")
    assert _position_references(csv_path) == ("U1",)

    csv_path.write_text("Reference,Value\nU1,probe\nu1,probe\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate references"):
        _position_references(csv_path)

    csv_path.write_text("Value\nprobe\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no reference column"):
        _position_references(csv_path)


def test_variant_population_off_skips_named_variant_native_exports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = PcbComponentInventoryCoverageReport(status="DISABLED", mode="review")
    monkeypatch.setattr(
        "kicad_tooling.hwrepo.design_lint_pcb_component_inventory_scan.capture_variant_population",
        lambda *_args, **_kwargs: pytest.fail("disabled variant rule must not export"),
    )
    monkeypatch.setattr(
        "kicad_tooling.hwrepo.design_lint_pcb_component_inventory_scan.evaluate_native_component_inventory_coverage",
        lambda *_args, **_kwargs: report,
    )
    coach = SimpleNamespace(source_hashes={}, observed=None, netlist_sha256=None)
    evidence = SimpleNamespace(
        snapshot=SimpleNamespace(kicad_version="10.0.5"),
        board_path="projects/synthetic/controller.kicad_pcb",
        board_sha256="a" * 64,
        snapshot_relative_path="build/snapshot.json",
        snapshot_sha256="b" * 64,
        probe_sha256="c" * 64,
    )

    observed = scan_pcb_component_inventory(
        tmp_path,
        SimpleNamespace(),
        coach,
        evidence,
        tmp_path / "build/design-lint",
        inventory_mode="review",
        population_mode="off",
        value_mode="off",
        pad_net_mode="off",
    )

    assert observed is report
