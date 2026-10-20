"""Opt-in runtime comparison for the pinned STM32 CubeMX cohort parser."""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
from types import ModuleType

import pytest

from kicad_tooling.hwrepo.stm32_pin_map import parse_cubemx_ioc

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]
_ROOT = Path(__file__).resolve().parents[1]
_FIXTURES = _ROOT / "tests/fixtures/design_lint/stm32-pin-map"
_SOURCE_HASHES = {
    "ioc.py": "6926aa6a34f20576fd433898cc8e4fdfb9da5dd06aee3ff307decc5b22013c84",
    "compare.py": "24f10fc5e494c9ec5671dae1b1ea4341712ad0111ac020ab314e7cbb73574a15",
}


def _candidate_modules() -> tuple[ModuleType, ModuleType]:
    source_root = os.environ.get("KICAD_STM32_PIN_CHECKER_ROOT")
    if not source_root:
        pytest.skip("set KICAD_STM32_PIN_CHECKER_ROOT to the pinned cohort checkout")
    root = Path(source_root)
    modules: list[ModuleType] = []
    for name, expected_hash in _SOURCE_HASHES.items():
        source = root / name
        content = source.read_bytes()
        assert hashlib.sha256(content).hexdigest() == expected_hash, (
            f"{name} does not match the LINT-031 pinned source"
        )
        spec = importlib.util.spec_from_file_location(f"cohort_stm32_{name[:-3]}", source)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules.append(module)
    return modules[0], modules[1]


@pytest.mark.cohort_trial
def test_candidate_pin_suffix_collisions_are_order_dependent() -> None:
    candidate_ioc, candidate_compare = _candidate_modules()
    forward_path = _FIXTURES / "suffix-conflict-forward.ioc"
    reverse_path = _FIXTURES / "suffix-conflict-reversed.ioc"
    forward = candidate_ioc.parse_ioc(forward_path)
    reverse = candidate_ioc.parse_ioc(reverse_path)
    hardware = {"PA13": "SYS_JTMS-SWDIO"}
    forward_status = candidate_compare.compare(hardware, forward, [])[0][0]
    reverse_status = candidate_compare.compare(hardware, reverse, [])[0][0]
    local_forward = parse_cubemx_ioc(forward_path.read_bytes())
    local_reverse = parse_cubemx_ioc(reverse_path.read_bytes())

    assert (forward_status, reverse_status) == ("WARNING", "OK")
    assert len(local_forward.issues) == len(local_reverse.issues) == 1
    assert all(
        "both identify PA13" in issue for issue in (*local_forward.issues, *local_reverse.issues)
    )


@pytest.mark.cohort_trial
def test_candidate_ignores_escaped_pin_key_supported_by_local_parser() -> None:
    candidate_ioc, _ = _candidate_modules()
    fixture = _FIXTURES / "escaped-pin-key.ioc"
    candidate = candidate_ioc.parse_ioc(fixture)
    local = parse_cubemx_ioc(fixture.read_bytes())

    assert candidate == {}
    assert local.issues == ()
    assert local.pins["ph0"].port_pin == "PH0"
