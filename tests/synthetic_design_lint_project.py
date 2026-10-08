"""Small tooling-owned checkout for source-bound CLI/MCP parity tests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import (
    CatalogPaths,
    CheckEvidence,
    CommandEvidence,
    ComponentIdentity,
    DesignLintPolicy,
    IgnoredChecks,
    PcbValidationContract,
    ProjectDiscovery,
    ProjectKind,
    ProjectManifest,
    ProjectTestContract,
    ToolchainRecord,
    ToolchainsCatalog,
    ValidationSummary,
)
from kicad_tooling.validate import hashes

_IMAGE = "registry.invalid/kicad:10.0.5@sha256:" + "a" * 64
PINNED_NATIVE_KICAD_IMAGES = {
    "10.0.0": (
        "ghcr.io/kicad/kicad:10.0.0@sha256:"
        "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3"
    ),
    "10.0.5": (
        "ghcr.io/kicad/kicad:10.0.5@sha256:"
        "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c"
    ),
}
_NETLIST = (
    '<export><components><comp ref="R1"><value>1k</value>'
    "<footprint>Synthetic:R</footprint></comp></components><nets/></export>"
)


def synthetic_design_lint_project(
    base: Path,
    policy: DesignLintPolicy,
    *,
    project_id: str = "controller",
    kicad_version: str = "10.0.5",
    image: str = _IMAGE,
) -> tuple[Path, Path]:
    """Create source-bound, explicitly synthetic evidence without a template checkout."""
    root = base / "repository"
    catalog = root / "catalog"
    project_dir = root / "projects" / project_id
    design_dir = project_dir / "kicad"
    contract_dir = project_dir / "tests"
    native_dir = root / "build/native" / project_id
    for directory in (catalog, design_dir, contract_dir, native_dir):
        directory.mkdir(parents=True, exist_ok=True)

    source_paths = tuple(
        f"kicad/{project_id}{suffix}" for suffix in (".kicad_pro", ".kicad_sch", ".kicad_pcb")
    )
    source_bytes = {
        source_paths[0]: b"synthetic project settings\n",
        source_paths[1]: b"synthetic schematic source\n",
        source_paths[2]: b"synthetic PCB source\n",
    }
    for relative, content in source_bytes.items():
        (project_dir / relative).write_bytes(content)

    write_model(
        catalog / "projects.json",
        ProjectDiscovery(
            catalogs=CatalogPaths(
                parts="catalog/parts.json",
                interfaces="catalog/interfaces.json",
                libraries="catalog/libraries.json",
                toolchains="catalog/toolchains.json",
                release_policies="catalog/release-policies.json",
            ),
            project_roots=("projects",),
        ),
    )
    write_model(
        catalog / "toolchains.json",
        ToolchainsCatalog(
            schema_version="1",
            toolchains=(
                ToolchainRecord(
                    id=f"synthetic-kicad-{kicad_version.replace('.', '-')}",
                    kicad_version=kicad_version,
                    image=image,
                    desktop_edit_policy="Synthetic parity test only",
                    installer_source="Synthetic parity test only",
                    migration_policy="Synthetic parity test only",
                ),
            ),
        ),
    )
    write_model(
        project_dir / "project.json",
        ProjectManifest(
            id=project_id,
            kind=ProjectKind.PCB,
            status="training_fixture",
            assurance_profile="training",
            toolchain_id=f"synthetic-kicad-{kicad_version.replace('.', '-')}",
            project=source_paths[0],
            source_roots=("kicad",),
            required_inputs=source_paths,
            component_identity=ComponentIdentity(required=False, part_ids=()),
        ),
    )
    write_model(
        contract_dir / "contract.json",
        ProjectTestContract(
            validation=PcbValidationContract(
                kind=ProjectKind.PCB,
                components={},
                nets={},
                expected_ignored_checks=IgnoredChecks(erc=(), drc=()),
            ),
            design_lint=policy,
        ),
    )

    source_hashes = hashes(root, (f"projects/{project_id}/kicad",))
    netlist_path = native_dir / "netlist.xml"
    netlist_path.write_text(_NETLIST, encoding="utf-8")
    command_path = native_dir / "netlist.command.json"
    write_model(
        command_path,
        CommandEvidence(
            argv=("synthetic-kicad-cli", "export", "netlist"),
            started_utc="synthetic fixture",
            returncode=0,
        ),
    )
    summary_path = native_dir / "summary.json"
    write_model(
        summary_path,
        ValidationSummary(
            timestamp_utc="synthetic fixture",
            checked_commit="LOCAL_SYNTHETIC",
            project_id=project_id,
            assurance_profile="training",
            not_for_manufacture=True,
            project_kind=ProjectKind.PCB,
            checks={
                "source_scope": CheckEvidence(status="PASS", source_hashes=source_hashes),
                "source_unchanged": CheckEvidence(status="PASS", source_hashes=source_hashes),
                "toolchain": CheckEvidence(
                    status="PASS", observed_version=kicad_version, image=image
                ),
                "netlist": CheckEvidence(status="PASS", returncode=0),
            },
            status="FAIL",
            artifacts_sha256={
                "netlist.xml": digest(netlist_path),
                "netlist.command.json": digest(command_path),
            },
        ),
    )
    return root, summary_path


def run_design_lint_cli(
    base: Path, root: Path, summary: Path, *, project_id: str = "controller"
) -> subprocess.CompletedProcess[str]:
    """Run the installed CLI from another cwd, resolving the repo through --root."""
    return subprocess.run(
        (
            sys.executable,
            "-I",
            "-B",
            "-m",
            "kicad_tooling.design_lint",
            "--root",
            str(root),
            "--project",
            project_id,
            "--native-summary",
            str(summary),
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
