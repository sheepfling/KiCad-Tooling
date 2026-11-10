"""Guard the bounded probe-envelope owner and its compatibility facade."""

from __future__ import annotations

import ast

import pytest

from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.architecture]


def test_test_access_probe_modules_stay_under_the_review_limit() -> None:
    paths = (
        REPO_ROOT / "kicad_tooling/ci_hosted_pcb_access.py",
        REPO_ROOT / "kicad_tooling/ci_hosted_pcb_access_expectations.py",
        REPO_ROOT / "kicad_tooling/ci_hosted_pcb_access_vias.py",
        REPO_ROOT / "kicad_tooling/ci_hosted_pcb_access_tracks.py",
        REPO_ROOT / "kicad_tooling/ci_hosted_pcb_access_zones.py",
        REPO_ROOT / "kicad_tooling/hwrepo/test_access.py",
        REPO_ROOT / "kicad_tooling/hwrepo/test_access_probe_envelope.py",
        REPO_ROOT / "kicad_tooling/hwrepo/pcb_connectivity_probe_validation.py",
        REPO_ROOT / "kicad_tooling/hwrepo/native_pcb_probe_access.py.in",
        REPO_ROOT / "kicad_tooling/hwrepo/native_pcb_probe_geometry.py.in",
        REPO_ROOT / "kicad_tooling/hwrepo/native_pcb_probe_scan.py.in",
        REPO_ROOT / "tests/pcb_test_access_support.py",
        REPO_ROOT / "tests/test_test_access.py",
        REPO_ROOT / "tests/test_test_access_probe_aperture.py",
        REPO_ROOT / "tests/test_test_access_probe_tracks.py",
        REPO_ROOT / "tests/test_test_access_probe_zones.py",
    )

    assert all(line_count(path) < IMPLEMENTATION_MAX_LINES for path in paths)


def test_probe_envelope_public_imports_have_one_theme_owner() -> None:
    facade = REPO_ROOT / "kicad_tooling/hwrepo/test_access.py"
    tree = ast.parse(facade.read_text(encoding="utf-8"))
    owners = {
        node.module: {alias.name for alias in node.names}
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
    }

    assert owners.get("test_access_probe_envelope") == {
        "pcb_access_probe_request_set",
        "pcb_probe_envelope_checks",
    }
    assert not any(
        isinstance(node, ast.FunctionDef)
        and node.name in {"pcb_access_probe_request_set", "pcb_probe_envelope_checks"}
        for node in tree.body
    )
