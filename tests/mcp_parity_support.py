"""Shared harness and small fixture readers for CLI/MCP parity suites."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from kicad_tooling.hwrepo.contracts import (
    parse_model_text,
    read_model,
    write_model,
)
from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import (
    CheckEvidence,
    ComponentIdentity,
    ConnectorInventoryReview,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    PartRecord,
    PartsCatalog,
    PartStatus,
    ProjectKind,
    ProjectManifest,
    ProjectTestContract,
    ValidationSummary,
)
from kicad_tooling.validate import hashes
from tests import test_parts_workflow as native_fixture
from tests.support import (
    initialize_git,
    reference_root,
)


def parity_workspace(base: Path) -> tuple[Path, Path, Path]:
    root = base / "repository"
    shutil.copytree(
        reference_root(),
        root,
        ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
    )
    manifest_path = root / "examples/projects/controller/project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    write_model(
        manifest_path,
        manifest.model_copy(
            update={
                "connector_inventory_review": ConnectorInventoryReview(
                    basis="Synthetic parity fixture reviewed the complete schematic interface inventory"
                )
            }
        ),
    )
    island = root / "examples/projects/controller"
    contract_path = island / "tests/contract.json"
    contract = read_model(contract_path, ProjectTestContract)
    write_model(
        contract_path,
        contract.model_copy(
            update={
                "design_lint": parity_design_lint_policy(contract.design_lint or DesignLintPolicy())
            }
        ),
    )
    initialize_git(root)
    incoming = root / "build/incoming/Incoming board.kicad_pro"
    incoming.parent.mkdir(parents=True)
    incoming.write_text("{}", encoding="utf-8")
    incoming.with_suffix(".kicad_sch").write_text("(kicad_sch)", encoding="utf-8")
    incoming.with_suffix(".kicad_pcb").write_text("(kicad_pcb)", encoding="utf-8")
    return root, island, incoming


def parity_design_lint_policy(policy: DesignLintPolicy) -> DesignLintPolicy:
    """Keep unrelated native PCB inventory capture out of synthetic parity cases."""
    native_rules = (
        "pcb.schematic_component_inventory",
        "pcb.schematic_pcb_dnp_mismatch",
        "pcb.schematic_pcb_value_mismatch",
        "pcb.schematic_pcb_pad_net_mismatch",
    )
    overrides = {item.rule_id: item for item in policy.rules}
    inventory_override = overrides.get("pcb.schematic_component_inventory")
    if inventory_override is not None and inventory_override.mode != "off":
        return policy
    additions: list[DesignLintRuleOverride] = []
    for rule_id in native_rules:
        if rule_id not in overrides:
            additions.append(
                DesignLintRuleOverride(
                    rule_id=rule_id,
                    mode="off",
                    reason="Synthetic parity fixture has no native PCB inventory snapshot evidence",
                )
            )
    return policy.model_copy(update={"rules": (*policy.rules, *additions)})


async def parity_cli_process(base: Path, root: Path, module: str, *arguments: str):
    # A foreign cwd proves --root rather than process cwd selects the board.
    return await asyncio.to_thread(
        subprocess.run,
        (
            sys.executable,
            "-I",
            "-B",
            "-m",
            module,
            "--root",
            str(root),
            *arguments,
            "--format",
            "json",
        ),
        cwd=base,
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )


def parity_native_evidence(root: Path, island: Path) -> Path:
    """Retain a valid netlist whose independent electrical check explicitly failed."""
    manifest_path = island / "project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    write_model(
        manifest_path,
        manifest.model_copy(
            update={
                "component_identity": ComponentIdentity(required=True, part_ids=("resistor-1k",)),
            }
        ),
    )
    write_model(
        root / "catalog/parts.json",
        PartsCatalog(
            schema_version="0.1",
            parts=(
                PartRecord(
                    id="resistor-1k",
                    revision="A",
                    description="Synthetic parity-test identity",
                    part_class="resistor",
                    unit="each",
                    manufacturer="Vishay",
                    mpn="MRS25000C1001FCT00",
                    datasheet_url="https://example.invalid/test-only",
                    lifecycle="active",
                    status=PartStatus.APPROVED,
                ),
            ),
        ),
    )
    config = load_config(root, manifest_path)
    directory = root / "build/native/controller"
    directory.mkdir(parents=True)
    (directory / "netlist.xml").write_text(native_fixture.NETLIST, encoding="utf-8")
    write_model(directory / "netlist.command.json", native_fixture.command())
    current = hashes(root, config.source_roots)
    write_model(
        directory / "summary.json",
        ValidationSummary(
            timestamp_utc="2026-09-24T00:00:00+00:00",
            checked_commit="LOCAL_UNBOUND",
            project_id="controller",
            project_kind=ProjectKind.PCB,
            checks={
                "source_scope": CheckEvidence(status="PASS", source_hashes=current),
                "source_unchanged": CheckEvidence(status="PASS", source_hashes=current),
                "toolchain": CheckEvidence(
                    status="PASS", observed_version=config.kicad_version, image=config.image
                ),
                "netlist": CheckEvidence(
                    status="FAIL", returncode=0, error="Independent electrical contract differs"
                ),
            },
            status="FAIL",
            artifacts_sha256={
                "netlist.xml": digest(directory / "netlist.xml"),
                "netlist.command.json": digest(directory / "netlist.command.json"),
            },
        ),
    )
    return directory / "summary.json"


class McpParityHarness:
    def __init__(self) -> None:
        self._assertions = unittest.TestCase()

    def __getattr__(self, name: str):
        if name == "assertEqual":
            return self._assert_equal
        if name == "subTest" or name.startswith(("assert", "fail")):
            return getattr(self._assertions, name)
        raise AttributeError(name)

    def _assert_equal(self, first: object, second: object, msg: str | None = None) -> None:
        if isinstance(first, DesignLintReport) and isinstance(second, DesignLintReport):
            first = semantic_design_lint_report(first)
            second = semantic_design_lint_report(second)
        self._assertions.assertEqual(first, second, msg=msg)

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="mcp-semantic-parity-")
        self.base = Path(self.temporary.name).resolve()
        self.root, self.island, self.incoming = parity_workspace(self.base)

    async def cli_process(self, module, *arguments):
        if module == "kicad_tooling.design_lint":
            self._isolate_unrelated_native_pcb_inventory()
        return await parity_cli_process(self.base, self.root, module, *arguments)

    async def cli(self, module, model, *arguments, expected_exit=0):
        process = await self.cli_process(module, *arguments)
        self.assertEqual(process.returncode, expected_exit, process.stderr + process.stdout)
        return parse_model_text(process.stdout, model)

    async def call(self, client, tool, model, arguments=None):
        if tool == "inspect_design_lint":
            self._isolate_unrelated_native_pcb_inventory()
        result = await client.call_tool(tool, arguments or {})
        self.assertFalse(result.is_error, result.content)
        self.assertIsNotNone(result.structured_content)
        return model.model_validate_json(json.dumps(result.structured_content))

    def _isolate_unrelated_native_pcb_inventory(self) -> None:
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        policy = parity_design_lint_policy(contract.design_lint or DesignLintPolicy())
        if contract.design_lint != policy:
            write_model(contract_path, contract.model_copy(update={"design_lint": policy}))

    @staticmethod
    def semantic(report: BaseModel, receipt: str | None = None) -> Any:
        def normalize(value: Any, field: str | None = None) -> Any:
            if isinstance(value, dict):
                return {key: normalize(item, key) for key, item in value.items()}
            if isinstance(value, list):
                return [normalize(item) for item in value]
            if isinstance(value, str):
                if field == "started_utc":
                    return "<command-start>"
                if receipt is not None:
                    value = value.replace(receipt, "<receipt>")
                if field == "stderr":
                    value = re.sub(
                        r"(?m)^(Ran \d+ tests? in )\d+(?:\.\d+)?s$", r"\1<elapsed>s", value
                    )
            return value

        return normalize_per_run_pcb_geometry_paths(normalize(report.model_dump(mode="json")))

    def receipt_equal(self, cli, mcp, field="run_directory") -> None:
        left = getattr(cli, field)
        right = getattr(mcp, field)
        self.assertNotEqual(left, right)
        self.assertTrue(Path(left).is_relative_to(self.root / "build"))
        self.assertTrue(Path(right).is_relative_to(self.root / "build"))
        self.assertEqual(self.semantic(cli, left), self.semantic(mcp, right))

    def import_args(self):
        return {
            "source": self.incoming.relative_to(self.root).as_posix(),
            "project_id": "incoming",
            "toolchain_id": "kicad-10.0.5",
        }

    def damage_import(self) -> None:
        self.incoming.with_suffix(".kicad_sch").write_text(
            '(kicad_sch (sheet (property "Sheetfile" "missing.kicad_sch")))',
            encoding="utf-8",
        )

    def native_evidence(self) -> Path:
        """Retain a valid netlist whose independent electrical check explicitly failed."""
        return parity_native_evidence(self.root, self.island)

    def rehash_native_netlist(self, native: Path) -> None:
        """Refresh the retained synthetic netlist digest after a test mutation."""
        netlist = native.parent / "netlist.xml"
        summary = read_model(native, ValidationSummary)
        write_model(
            native,
            summary.model_copy(
                update={
                    "artifacts_sha256": {
                        **summary.artifacts_sha256,
                        "netlist.xml": digest(netlist),
                    }
                }
            ),
        )


def semantic_design_lint_report(report: DesignLintReport) -> dict[str, Any]:
    """Remove per-run PCB geometry output IDs before semantic parity comparison."""
    return normalize_per_run_pcb_geometry_paths(report.model_dump(mode="json"))


def normalize_per_run_pcb_geometry_paths(value: Any) -> Any:
    """Normalize only generated PCB geometry run IDs in a typed report or dump."""
    if isinstance(value, dict):
        return {key: normalize_per_run_pcb_geometry_paths(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_per_run_pcb_geometry_paths(item) for item in value]
    if isinstance(value, str):
        return re.sub(
            r"build/design-lint/pcb-geometry-[0-9a-f]{12}",
            "build/design-lint/pcb-geometry-<run>",
            value,
        )
    return value


def comprehensive_lint_netlist() -> str:
    """Read the synthetic XML used by the broad design-lint parity case."""
    path = Path(__file__).parent / "fixtures/design_lint/mcp-parity/comprehensive-netlist.xml"
    return path.read_text(encoding="utf-8")


def pcb_native_snapshot_shim() -> str:
    """Read the synthetic native snapshot executable used by PCB parity tests."""
    path = Path(__file__).parent / "fixtures/design_lint/mcp-parity/pcb-native-snapshot-shim.py"
    return path.read_text(encoding="utf-8")


def run_mcp_parity(case_type: type[McpParityHarness], method_name: str) -> None:
    """Run one legacy async parity body from an ordinary pytest function."""
    case = case_type()
    try:
        case.setUp()
        asyncio.run(getattr(case, method_name)())
    finally:
        temporary = getattr(case, "temporary", None)
        if temporary is not None:
            temporary.cleanup()
