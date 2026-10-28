"""Synthetic contract tests for the isolated KiCad PCB-variant probe."""

from __future__ import annotations

import hashlib
import json
import runpy
import sys
from collections.abc import Set as AbstractSet
from pathlib import Path

import pytest

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]


class FakeBoard:
    def __init__(self, variants: AbstractSet[str]) -> None:
        self.variants = {name.casefold() for name in variants}

    def HasVariant(self, name: str) -> bool:
        return name.casefold() in self.variants


class FakePcbNew:
    def __init__(self, variants: AbstractSet[str]) -> None:
        self.board = FakeBoard(variants)

    def LoadBoard(self, _path: str) -> FakeBoard:
        return self.board


def probe_main(monkeypatch: pytest.MonkeyPatch, variants: AbstractSet[str]):
    monkeypatch.setitem(sys.modules, "pcbnew", FakePcbNew(variants))
    path = Path(__file__).parents[1] / "kicad_tooling/hwrepo/pcb_variant_probe.py.in"
    namespace = runpy.run_path(str(path), run_name="native_pcb_variant_probe_test")
    return namespace["main"]


def test_native_probe_reports_named_board_variants_against_source_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    board = tmp_path / "board.kicad_pcb"
    board.write_text("synthetic pcb source", encoding="utf-8")
    board_sha256 = hashlib.sha256(board.read_bytes()).hexdigest()
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "board_sha256": board_sha256,
                "project_sha256": "a" * 64,
                "variants": ["Assembly A", "Assembly B"],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "output.json"

    probe_main(monkeypatch, {"Assembly A"})([str(board), str(request), str(output)])

    observed = json.loads(output.read_text(encoding="utf-8"))
    assert observed == {
        "schema_version": "1",
        "board_sha256": board_sha256,
        "project_sha256": "a" * 64,
        "variants": [
            {"name": "Assembly A", "present_on_board": True},
            {"name": "Assembly B", "present_on_board": False},
        ],
    }


def test_native_probe_rejects_request_bound_to_another_board(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    board = tmp_path / "board.kicad_pcb"
    board.write_text("synthetic pcb source", encoding="utf-8")
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "board_sha256": "b" * 64,
                "project_sha256": "a" * 64,
                "variants": ["Assembly A"],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "output.json"

    with pytest.raises(ValueError, match="different PCB source"):
        probe_main(monkeypatch, {"Assembly A"})([str(board), str(request), str(output)])
    assert not output.exists()
