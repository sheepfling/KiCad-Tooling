"""Turn existing import, portable, and native findings into repair guidance."""
from __future__ import annotations

import csv
import os
import shlex
import xml.etree.ElementTree as ET
from collections import Counter
from contextlib import nullcontext
from pathlib import Path, PurePosixPath
from typing import Literal

from .contracts import read_model, repo_path
from .diagnostic_journal import DiagnosticJournal
from .discovery import load_config, load_registry, settings
from .importing import import_project
from .model_inventory import inspect_models
from .models import (
    DiagnosticFinding,
    DiagnosticReport,
    PartsCatalog,
    PartStatus,
    PcbValidationContract,
    ProjectKind,
    ProjectManifest,
    ProjectStaticPipelineReport,
    ToolchainsCatalog,
    ValidationSummary,
)
from .repository import cad_dependencies
from .selection import ProjectSelector, resolve_project_ids

IMPORT_GUIDE = "docs/workflow/IMPORT_WORKFLOW.md"
CHECKS_GUIDE = "docs/workflow/CHECKS_AND_CI.md"
FIRST_BOARD_GUIDE = "docs/workflow/FIRST_BOARD.md"
BOM_GUIDE = "docs/workflow/BOM_POLICY.md"


def quote_argument(value: str, windows: bool | None = None) -> str:
    """Use a copyable argument for the host shell (PowerShell or POSIX)."""
    use_windows = os.name == "nt" if windows is None else windows
    if use_windows:
        return "'" + value.replace("'", "''") + "'"
    return shlex.quote(value)


def finding(
    severity: str, code: str, location: str, observed: str, action: str, guide: str
) -> DiagnosticFinding:
    return DiagnosticFinding.model_validate({
        "severity": severity, "code": code, "location": location,
        "observed": observed, "action": action, "guide": guide,
    })


def report(
    project_id: str, scope: str, findings: list[DiagnosticFinding], next_command: str,
    follow_up_command: str | None = None,
) -> DiagnosticReport:
    return DiagnosticReport.model_validate({
        "project_id": project_id,
        "scope": scope,
        "status": "NEEDS_WORK" if any(row.severity == "BLOCKING" for row in findings) else "PASS",
        "findings": tuple(findings),
        "next_command": next_command,
        "follow_up_command": follow_up_command,
    })


def import_guidance(message: str) -> str:
    if "matching .kicad_sch or .kicad_pcb" in message:
        return (
            "This .kicad_pro has neither a matching schematic nor board. Find the complete "
            "saved project or choose the correct .kicad_pro. A board without a schematic can "
            "be imported as pcb_only; do not fabricate a missing design file."
        )
    if "Select an existing .kicad_pro" in message:
        return "Select the actual .kicad_pro file for one complete design, then preview again."
    if "outside the selected project directory" in message or "is not in the subpath of" in message:
        return (
            "Move the referenced sheet and its dependencies into this project, update its "
            "Sheetfile path in KiCad, then preview the import again. Do not silently drop the sheet."
        )
    if "Missing schematic sheet" in message:
        return (
            "Find the intended sheet, correct its Sheetfile spelling and case in KiCad, "
            "and verify the file is present before retrying."
        )
    if "Nonportable repository path" in message or "Case-colliding" in message:
        return (
            "Rename the source path to a portable, unique spelling and update every KiCad "
            "reference to it before retrying."
        )
    if "Linked source path" in message:
        return (
            "Replace the symlink with the actual reviewed project-local asset, or declare a "
            "shared library dependency, then preview again."
        )
    if "Source and destination directories must not overlap" in message:
        return "Use an external source copy and a distinct destination island, then preview again."
    if "variable" in message:
        return (
            "Resolve the sheet path to a reviewed project-local dependency, update Sheetfile "
            "in KiCad, and preview again."
        )
    return "Repair the named source or project selection, then rerun the dry-run import."


def diagnose_import(
    root: Path, source: Path, project_id: str, toolchain_id: str,
    journal: DiagnosticJournal | None = None,
) -> DiagnosticReport:
    """Preview an import and group omissions without copying the candidate project."""
    root = root.resolve()
    with journal.stage("import-preview") if journal is not None else nullcontext():
        preview = import_project(root, source, project_id, toolchain_id, dry_run=True)
        if journal is not None:
            journal.save_model("import-preview", preview)
    findings = [
        finding("BLOCKING", "IMPORT", source.as_posix(), issue,
                import_guidance(issue), IMPORT_GUIDE)
        for issue in preview.issues
    ]
    if preview.status == "PASS":
        toolchains = read_model(
            repo_path(root, settings(root).catalogs.toolchains), ToolchainsCatalog,
        )
        toolchain = next(item for item in toolchains.toolchains if item.id == toolchain_id)
        major = toolchain.kicad_version.split(".")[0]
        copied = frozenset(preview.copied_sha256)
        source_roots: set[str] = set()
        for name in copied:
            parent = PurePosixPath(name).parent
            while parent != PurePosixPath("."):
                source_roots.add(parent.as_posix())
                parent = parent.parent
        source_dir = source.parent.resolve()
        for name in sorted(copied):
            path = source_dir / name
            if path.suffix not in {".kicad_pcb", ".kicad_mod"} and path.name not in {
                "sym-lib-table", "fp-lib-table",
            }:
                continue
            for issue in cad_dependencies(
                source_dir, path, source_dir, major, copied,
                frozenset(source_roots), exposed_inputs=copied,
            ):
                guidance = repository_guidance(issue, major)
                location = f"{source_dir}/{guidance.location}"
                findings.append(finding(
                    "BLOCKING", "CAD_PATH", location, guidance.observed,
                    guidance.action + " Repair the original source, then preview import again.",
                    IMPORT_GUIDE,
                ))
    if preview.excluded:
        counts = Counter(preview.excluded.values())
        actions = {
            "generated export": "Regenerate working Gerbers, drills or other exports from the "
                "imported source under ignored build/; do not commit the old export.",
            "local state or build output": "Leave caches, preferences and prior build outputs "
                "behind. Recreate them locally only if needed.",
            "artifact restricted by repository hygiene; review separately":
                "Inspect the excluded list for authored documentation or assets. Move needed "
                "source into an allowed project path under an explicit team policy; keep vendor "
                "packages and generated media outside the source repository.",
            "separate nested project; import independently": "Preview and import that separate "
                "design using its own .kicad_pro and project ID.",
            "separate sibling project; import independently": "Preview and import that separate "
                "design using its own .kicad_pro and project ID.",
            "schematic outside the selected hierarchy": "Check whether this is an unused "
                "backup or a separate design. Never silently discard a sheet referenced "
                "by the selected schematic.",
        }
        for reason, count in sorted(counts.items()):
            examples = [name for name, value in preview.excluded.items() if value == reason][:3]
            findings.append(finding(
                "REVIEW", "IMPORT_EXCLUSIONS", source.parent.as_posix(),
                f"{count} excluded as {reason}; examples: {', '.join(examples)}",
                actions.get(reason, "Review the excluded list in import-preview.json before copying."),
                IMPORT_GUIDE,
            ))
    command = (
        "python -B -m kicad_tooling.template "
        + ("diagnose" if any(row.severity == "BLOCKING" for row in findings) else "import-project")
        + f" --root {quote_argument(str(root))} --source {quote_argument(str(source))} "
        + f"--project-id {quote_argument(project_id)} "
        + f"--toolchain {quote_argument(toolchain_id)}"
    )
    return report(project_id, "import", findings, command)


def repository_guidance(issue: str, kicad_major: str | None = None) -> DiagnosticFinding:
    if issue.startswith("CAD_PATH: "):
        location, _, observed = issue.removeprefix("CAD_PATH: ").partition(": ")
        if "machine-local dependency" in observed:
            normalized = observed.casefold().replace("\\", "/")
            installed = any(prefix in normalized for prefix in (
                "/usr/share/kicad/", "/applications/kicad/", "/program files/kicad/"
            ))
            if installed:
                variable = (
                    "FOOTPRINT_DIR" if "/footprints/" in normalized else
                    "SYMBOL_DIR" if "/symbols/" in normalized else
                    "3DMODEL_DIR" if "/3dmodels/" in normalized else None
                )
                library = (
                    f"${{KICAD{kicad_major}_{variable}}}"
                    if kicad_major is not None and variable is not None else
                    "the pinned versioned KiCad library variable"
                )
                action = (
                    f"Replace the machine-specific installed-library prefix with {library}, "
                    "verify the named library exists in the pinned KiCad toolchain, and rerun "
                    "the portable check. Do not copy standard KiCad libraries into the project."
                )
            else:
                action = (
                    "Move the actual asset into this project or a declared shared library, update "
                    "the KiCad reference to a portable path, and verify it opens on another machine."
                )
        elif "undocumented path variable" in observed or "invalid versioned" in observed:
            action = (
                "Replace the legacy variable with the correct pinned KiCad library variable, "
                "or use a reviewed project-local asset via KIPRJMOD. Verify the target exists."
            )
        elif "case mismatch" in observed:
            action = (
                "Make the reference spelling match the file and every parent directory exactly; "
                "rerun the check on a case-sensitive host."
            )
        elif "missing dependency" in observed or "missing embedded model" in observed:
            action = (
                "Find and include the intended asset or correct the reference. Do not create "
                "a placeholder model solely to satisfy this check."
            )
        elif any(marker in observed for marker in (
            "not in this project's required_inputs", "no inventoried inputs",
            "outside this project's source_roots", "exposes unlisted files",
        )):
            action = (
                "If this is board-local, add the asset under this project's source_roots and "
                "required_inputs. If multiple boards use it, move it into a registered "
                "libraries/<id>/ directory, declare its catalog ID and complete shared "
                "inventory in each board's project.json, then update the KiCad table."
            )
        else:
            action = "Correct the named KiCad dependency and rerun the selected portable check."
        return finding("BLOCKING", "CAD_PATH", location or "KiCad source",
                       observed or issue, action, IMPORT_GUIDE)
    code, _, detail = issue.partition(": ")
    if code in {"TRACKED_GENERATED_OUTPUT", "TRACKED_LOCAL_STATE"}:
        action = (
            "Remove this generated/local file from the Git index, keep any needed local copy, "
            "and confirm the ignore rule and clean CI run."
        )
    elif code == "UNREGISTERED_DESIGN":
        action = "Register or import this separate native project as its own island."
    elif code == "TRACKED_UNMANAGED_ARTIFACT":
        action = (
            "Review whether this is authored source or a generated/vendor artifact. Put needed "
            "documentation images under docs/assets; keep build outputs under ignored build/, "
            "and remove prohibited files from the Git index."
        )
    elif code == "REPOSITORY_LOAD":
        action = (
            "Run 'python -B -m kicad_tooling.template doctor', repair Git or the named registry input, "
            "then rerun diagnostics."
        )
    else:
        action = "Inspect the named repository input and correct the source or declaration."
    return finding("BLOCKING", code or "REPOSITORY", detail or "repository", issue,
                   action, CHECKS_GUIDE)


def portable_findings(
    root: Path, project_id: str, journal: DiagnosticJournal | None = None,
    portable_report: ProjectStaticPipelineReport | None = None,
) -> list[DiagnosticFinding]:
    """Explain captured portable evidence, or run a fresh lane for standalone diagnosis."""
    if portable_report is None:
        from ..ci import project_static_pipeline

        result = project_static_pipeline(root, (project_id,))
        if journal is not None:
            journal.save_model("portable", result)
    else:
        if portable_report.projects != (project_id,):
            raise ValueError("Captured portable report does not match the diagnosed project")
        result = portable_report
    registry = load_registry(root)
    project = next(item for item in registry.projects if item.id == project_id)
    manifest_path = repo_path(root, project.config)
    manifest = read_model(manifest_path, ProjectManifest)
    config = load_config(root, project.config)
    contract_path = repo_path(manifest_path.parent, manifest.checks).relative_to(root).as_posix()
    findings = [
        finding(
            "BLOCKING", "ELECTRICAL_SETUP" if ": electrical:" in issue else "REGISTRY",
            config.electrical or contract_path if ": electrical:" in issue else "project/catalog",
            issue,
            ("Complete the pending requirements or review stale model bindings; "
             f"run kicad_tooling.template doctor --electrical --project-id {project_id} --format text. "
             f"Use kicad_tooling.electrical --project {project_id} --capture-inputs for unreviewed hash candidates; never refresh approvals automatically.")
            if ": electrical:" in issue else
            "Correct the named project manifest, inventory, or catalog record; rerun the selected check. "
            "Do not relax the contract to hide a source problem.",
            "docs/workflow/ELECTRICAL_ANALYSIS.md" if ": electrical:" in issue else CHECKS_GUIDE,
        ) for issue in result.registry.issues
    ]
    findings.extend(
        repository_guidance(issue, config.kicad_version.split(".")[0])
        for issue in result.repository.issues
    )
    findings.extend(
        finding("BLOCKING", issue.code, issue.location, issue.message,
                "Correct the authored product/catalog relationship, then regenerate and rerun "
                "the selected check.", "docs/workflow/PRODUCT_WORKFLOW.md")
        for issue in result.product.issues
    )
    findings.extend(
        finding("BLOCKING", "GENERATION", "generated view", issue,
                "Review the source records, regenerate ignored views with "
                "'python -B -m kicad_tooling.hardware generate', then rerun the check.", CHECKS_GUIDE)
        for issue in result.generation.issues
    )
    for name, command in result.project_tests.commands.items():
        if command.returncode == 0:
            continue
        detail = command.error or "\n".join(command.stderr.strip().splitlines()[-16:])
        action = (
            "Check the island's tests/ directory and discoverable test_*.py files. Nested "
            "test directories need __init__.py; fix the named import or syntax error and rerun "
            "the selected check."
            if name == "discovery" or "none were discovered" in (command.error or "") else
            "Open the failing test and its assertion, repair the design or test fixture from "
            "the requirement, then rerun the selected verification. The complete test stderr "
            "is in this run's portable.json."
        )
        findings.append(finding(
            "BLOCKING", "PROJECT_TEST", name, detail or f"exit {command.returncode}",
            action, "tests/README.md",
        ))
    if config.kind is ProjectKind.PCB_ONLY:
        findings.append(finding(
            "REVIEW", "PCB_ONLY_SCOPE", project.config,
            "Board-only validation has no schematic, ERC, netlist, or native assembly BOM.",
            "Capture the board with DRC, then create or adopt an authoritative schematic "
            "before product or manufacturing release.", IMPORT_GUIDE,
        ))
    elif config.kind is ProjectKind.PCB and isinstance(config.validation, PcbValidationContract):
        if not config.validation.components:
            findings.append(finding(
                "BLOCKING", "EMPTY_COMPONENT_CONTRACT", contract_path,
                "The independent component contract is empty.",
                "Have an engineer author and review expected references, values, footprints "
                f"and nets in {contract_path} from design requirements; do not copy the "
                "export merely to make the check pass.", FIRST_BOARD_GUIDE,
            ))
        if not config.validation.nets:
            findings.append(finding(
                "REVIEW", "EMPTY_NET_CONTRACT", contract_path,
                "The independent expected-net list is empty.",
                "Check the circuit requirements and author the expected nets in "
                f"{contract_path}. A deliberately net-free design needs an explicit "
                "engineering review; do not copy the exported netlist as test truth.",
                FIRST_BOARD_GUIDE,
            ))
        if not manifest.component_identity.required:
            findings.append(finding(
                "REVIEW", "PART_ID_SCOPE", project.config,
                "Controlled component identity is not yet required for this project.",
                "Assign stable PART_ID fields and reviewed catalog records before generating "
                "a purchasing BOM or preparing a release.", BOM_GUIDE,
            ))
        if manifest.release_exports is None:
            findings.append(finding(
                "REVIEW", "EXPORT_SETTINGS", project.config,
                "No release export settings are declared.",
                "Review layer, drill-origin and placement settings, then declare "
                "release_exports before a manufacturing export.",
                "docs/workflow/RELEASE_READINESS.md",
            ))
    if config.kind in {ProjectKind.PCB, ProjectKind.PCB_ONLY}:
        try:
            with journal.stage("model-inventory") if journal is not None else nullcontext():
                model_inventory = inspect_models(root, config)
                if journal is not None:
                    journal.save_model("models", model_inventory)
                findings.extend(model_inventory.findings)
        except (OSError, ValueError) as exc:
            findings.append(finding(
                "BLOCKING", "MODEL_INVENTORY", project.config, str(exc),
                "Repair the selected board or its declared model paths, then rerun diagnostics. "
                "Model inspection does not require a native runner or approve mechanical fit.",
                "docs/workflow/THREE_D_WORKFLOW.md",
            ))
    return findings


def native_findings(
    path: Path, project_id: str, root: Path | None = None,
    journal: DiagnosticJournal | None = None,
) -> list[DiagnosticFinding]:
    if root is not None:
        root = root.resolve()
    summary_path = path / "summary.json" if path.is_dir() else path
    try:
        summary = read_model(summary_path, ValidationSummary)
    except (OSError, ValueError) as exc:
        return [finding(
            "BLOCKING", "NATIVE_REPORT", str(summary_path), str(exc),
            "Select this project's native summary.json from a fresh KiCad check.", CHECKS_GUIDE,
        )]
    if journal is not None:
        journal.save_model("native-summary", summary)
    if summary.project_id != project_id:
        return [finding(
            "BLOCKING", "NATIVE_REPORT", str(summary_path),
            f"Report project is {summary.project_id!r}, expected {project_id!r}.",
            "Use the report from the selected project and exact checked source.", CHECKS_GUIDE,
        )]
    findings: list[DiagnosticFinding] = []
    if root is not None:
        scope = summary.checks.get("source_scope")
        if scope is None or not scope.source_hashes:
            findings.append(finding(
                "BLOCKING", "NATIVE_SOURCE", str(summary_path),
                "The native report has no declared source hashes.",
                "Run a fresh selected native check; do not use an unbound report to guide "
                "release or BOM decisions.", CHECKS_GUIDE,
            ))
        else:
            from ..validate import hashes

            try:
                registry = load_registry(root)
                project = next(item for item in registry.projects if item.id == project_id)
                config = load_config(root, project.config)
                current = hashes(root, config.source_roots)
                if current != scope.source_hashes:
                    findings.append(finding(
                        "BLOCKING", "STALE_NATIVE_REPORT", str(summary_path),
                        "The declared design files differ from those checked in this native report.",
                        "Run a fresh native check against the current source before using its "
                        "ERC, DRC or netlist findings to guide repairs.", CHECKS_GUIDE,
                    ))
            except (OSError, ValueError, StopIteration) as exc:
                findings.append(finding(
                    "BLOCKING", "NATIVE_SOURCE", str(summary_path), str(exc),
                    "Repair project discovery or the declared source inventory, then rerun "
                    "native validation.", CHECKS_GUIDE,
                ))
    for name, check in summary.checks.items():
        if check.status == "PASS":
            continue
        observed = check.error or f"{name} status is {check.status}"
        if name in {"erc", "drc"}:
            from ..validate import native_report_examples

            examples = native_report_examples(summary_path.parent / f"{name}.json", name)
            if examples:
                observed += "; examples: " + "; ".join(examples)
            if "Disabled-check inventory changed" in observed:
                setup = "Schematic Setup's ERC settings" if name == "erc" else "Board Setup's DRC settings"
                action = (
                    f"In KiCad {setup}, enable the named disabled checks, then resolve "
                    "resulting findings. Do not change the "
                    "development contract to mirror disabled defaults."
                )
            else:
                action = (
                    f"Inspect {summary_path.parent / (name + '.json')} for each violation, "
                    "unconnected item, parity error or exclusion; correct the design and rerun "
                    "into a fresh output directory."
                )
            guide = IMPORT_GUIDE
        elif name == "netlist":
            contract_path = "the project's declared tests contract"
            if root is not None:
                try:
                    registry = load_registry(root)
                    project = next(item for item in registry.projects if item.id == project_id)
                    manifest_path = repo_path(root, project.config)
                    manifest = read_model(manifest_path, ProjectManifest)
                    contract_path = repo_path(manifest_path.parent, manifest.checks).relative_to(
                        root
                    ).as_posix()
                except (OSError, ValueError, StopIteration):
                    pass
            action = (
                "Compare the native export with independently reviewed component and net "
                f"expectations in {contract_path}. Fix the design or correct a reviewed "
                "requirement; do not blindly copy observed nets into the contract."
            )
            guide = "tests/README.md"
        elif name in {"preflight", "toolchain", "source_scope"}:
            action = (
                "Run 'python -B -m kicad_tooling.template doctor --native --toolchain <id>', "
                "check the manifest's exact KiCad version and required inputs, then rerun."
            )
            guide = CHECKS_GUIDE
        elif name == "source_unchanged":
            action = "Close KiCad, preserve the changed source, and rerun from a stable source state."
            guide = CHECKS_GUIDE
        else:
            action = (
                f"Open {summary_path.parent / (name + '.command.json')} for the exact KiCad "
                "invocation, stdout and stderr; repair the named source or export setting, "
                "then rerun into a fresh output directory."
            )
            guide = CHECKS_GUIDE
        location = summary_path.parent / f"{name}.json" if name in {"erc", "drc"} else summary_path
        findings.append(finding("BLOCKING", "NATIVE_" + name.upper(),
                                str(location), observed, action, guide))
    if summary.status == "FAIL" and not any(check.status != "PASS" for check in summary.checks.values()):
        findings.append(finding(
            "BLOCKING", "NATIVE_REPORT", str(summary_path),
            "Native summary failed but contains no failed check to explain why.",
            "Inspect the full native output and rerun with a fresh directory; retain this "
            "diagnostic log if the tool itself is faulty.", CHECKS_GUIDE,
        ))
    return findings


def bom_findings(root: Path, path: Path) -> list[DiagnosticFinding]:
    """Explain native BOM identity gaps without changing a schematic or catalog."""
    try:
        registry = load_registry(root)
        parts = {
            part.id: part for part in read_model(
                repo_path(root, registry.catalogs.parts), PartsCatalog
            ).parts
        }
        with path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != ["Reference", "Value", "Footprint", "PartID", "DNP"]:
                raise ValueError("Expected native BOM columns Reference, Value, Footprint, PartID, DNP")
            rows = list(reader)
        if not rows:
            raise ValueError("Native BOM has no fitted components")
        if any(None in row or not row["Reference"] or any(value is None for value in row.values())
               for row in rows):
            raise ValueError("Native BOM contains missing or extra cells")
    except (OSError, ValueError, csv.Error) as exc:
        return [finding("BLOCKING", "BOM_INPUT", str(path), str(exc),
                        "Select the native assembly/bom.csv from a successful schematic export.",
                        BOM_GUIDE)]
    missing = [row["Reference"] for row in rows if not row["PartID"]]
    unknown = [row["Reference"] for row in rows if row["PartID"] and row["PartID"] not in parts]
    training = [row["Reference"] for row in rows
                if row["PartID"] in parts and parts[row["PartID"]].status is PartStatus.TRAINING]
    findings: list[DiagnosticFinding] = []
    if missing or unknown:
        observed = f"{len(missing)} missing PART_ID; {len(unknown)} unknown catalog ID"
        examples = ", ".join((missing + unknown)[:8])
        findings.append(finding(
            "BLOCKING", "BOM_PART_ID", str(path), f"{observed}; references: {examples}",
            "Assign a stable PART_ID in the schematic for each fitted component and add "
            "reviewed records to catalog/parts.json. Regenerate the native BOM; never hand-edit "
            "the exported CSV.", BOM_GUIDE,
        ))
    if training:
        findings.append(finding(
            "REVIEW", "BOM_TRAINING_PART", str(path),
            f"{len(training)} references use not-for-manufacture catalog records.",
            "Replace training placeholders with reviewed sourceable parts before release.", BOM_GUIDE,
        ))
    return findings


def bom_binding_findings(
    root: Path, project_id: str, bom: Path, native_report: Path | None
) -> list[DiagnosticFinding]:
    """Bind BOM rows to a hashed netlist from this project's current native run."""
    if native_report is None:
        return [finding(
            "BLOCKING", "BOM_BINDING", str(bom), "No project native report was supplied.",
            "Run native validation for this project and pass its project summary.json "
            "with --native-report alongside --bom.", BOM_GUIDE,
        )]
    summary_path = native_report / "summary.json" if native_report.is_dir() else native_report
    try:
        from ..validate import hashes, read_netlist
        from .evidence import digest

        summary = read_model(summary_path, ValidationSummary)
        if summary.project_id != project_id:
            raise ValueError(f"Native report belongs to {summary.project_id!r}, not {project_id!r}")
        registry = load_registry(root)
        project = next(item for item in registry.projects if item.id == project_id)
        config = load_config(root, project.config)
        scope = summary.checks.get("source_scope")
        if scope is None or not scope.source_hashes or hashes(root, config.source_roots) != scope.source_hashes:
            raise ValueError("Native report does not match the current declared design files")
        netlist_path = summary_path.parent / "netlist.xml"
        if summary.artifacts_sha256.get("netlist.xml") != digest(netlist_path):
            raise ValueError("Native netlist is missing or differs from the report inventory")
        netlist = read_netlist(netlist_path)
        tree = ET.parse(netlist_path).getroot()
        expected_references = {
            component.attrib["ref"]
            for component in tree.findall("./components/comp")
            if not {property_.get("name") for property_ in component.findall("property")}
            & {"exclude_from_bom", "dnp"}
        }
        with bom.open(newline="", encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
        if not rows:
            raise ValueError("Native BOM has no fitted references")
        references: list[str] = []
        for row in rows:
            reference = row.get("Reference")
            if not isinstance(reference, str) or not reference:
                raise ValueError("Native BOM has a missing reference")
            references.append(reference)
        if len(set(references)) != len(references):
            raise ValueError("Native BOM repeats a reference")
        if set(references) != expected_references:
            raise ValueError(
                "BOM fitted-reference coverage differs from this project's netlist; "
                f"missing={sorted(expected_references - set(references))[:8]}, "
                f"extra={sorted(set(references) - expected_references)[:8]}"
            )
        mismatched = [
            str(reference) for reference, row in zip(references, rows)
            if (component := netlist.components.get(str(reference))) is None
            or row.get("Value") != component.value
            or row.get("Footprint") != component.footprint
            or (row.get("PartID") or None) != component.part_id
        ]
        if mismatched:
            raise ValueError(
                "BOM rows differ from this project's native netlist: "
                + ", ".join(mismatched[:8])
            )
    except (OSError, ValueError, KeyError, TypeError, StopIteration, csv.Error, ET.ParseError) as exc:
        return [finding(
            "BLOCKING", "BOM_BINDING", str(bom), str(exc),
            "Select a fresh BOM from this project's schematic and its matching native "
            "summary. Do not relabel or hand-edit an export from another board.", BOM_GUIDE,
        )]
    return []


def diagnose_project(
    root: Path, project_id: str, native_report: Path | None = None,
    bom: Path | None = None,
    journal: DiagnosticJournal | None = None,
    portable_report: ProjectStaticPipelineReport | None = None,
) -> DiagnosticReport:
    """Give one project a portable check and optional native/BOM follow-up."""
    root = root.resolve()
    try:
        with journal.stage("project-selection") if journal is not None else nullcontext():
            selected = (
                resolve_project_ids(root, ProjectSelector(project_ids=(project_id,)))
                if portable_report is None else (project_id,)
            )
        with journal.stage("portable") if journal is not None else nullcontext():
            findings = portable_findings(root, selected[0], journal, portable_report)
    except (OSError, ValueError, TypeError) as exc:
        if journal is not None:
            journal.event("discovery", "HANDLED", f"{type(exc).__name__}: {exc}")
        findings = [finding(
            "BLOCKING", "DISCOVERY", "catalog/projects.json", str(exc),
            "Repair project discovery or the selected project ID, then rerun diagnostics.",
            CHECKS_GUIDE,
        )]
    if native_report is not None:
        with journal.stage("native-report") if journal is not None else nullcontext():
            findings.extend(native_findings(native_report, project_id, root, journal))
    if bom is not None:
        with journal.stage("bom") if journal is not None else nullcontext():
            findings.extend(bom_binding_findings(root, project_id, bom, native_report))
            findings.extend(bom_findings(root, bom))
    follow_up_command: str | None = None
    if any(row.code in {"STALE_NATIVE_REPORT", "NATIVE_REPORT"} for row in findings):
        next_command = (
            f"python -B -m kicad_tooling.verify --root {quote_argument(str(root))} "
            f"--project {quote_argument(project_id)} --depth native"
        )
        if bom is not None:
            follow_up_command = (
                f"python -B -m kicad_tooling.template diagnose --root {quote_argument(str(root))} "
                f"--project-id {quote_argument(project_id)} "
                f"--native-report FRESH_NATIVE_DIR --bom {quote_argument(str(bom))}"
            )
    elif any(row.severity == "BLOCKING" for row in findings):
        next_command = (
            f"python -B -m kicad_tooling.template diagnose --root {quote_argument(str(root))} "
            f"--project-id {quote_argument(project_id)}"
        )
        if native_report is not None:
            next_command += f" --native-report {quote_argument(str(native_report))}"
        if bom is not None:
            next_command += f" --bom {quote_argument(str(bom))}"
    else:
        next_command = (
            f"python -B -m kicad_tooling.verify --root {quote_argument(str(root))} "
            f"--project {quote_argument(project_id)}"
        )
    return report(project_id, "project", findings, next_command, follow_up_command)


def format_text(result: DiagnosticReport, detail: Literal["brief", "full"] = "brief") -> str:
    """Show a short repair queue or every finding without losing its source location."""
    blocking = sum(row.severity == "BLOCKING" for row in result.findings)
    review = len(result.findings) - blocking
    lines = [f"{result.status}: {result.scope} diagnostics for {result.project_id}",
             f"{blocking} blocking finding(s); {review} review task(s)."]
    if detail == "full":
        number = 0
        for severity in ("BLOCKING", "REVIEW"):
            for row in result.findings:
                if row.severity != severity:
                    continue
                number += 1
                lines.extend((
                    f"{number}. [{row.severity}] {row.code} at {row.location}",
                    f"   Observed: {row.observed}",
                    f"   Fix: {row.action}",
                    f"   Guide: {row.guide}",
                ))
    else:
        groups: dict[tuple[str, str, str, str], list[DiagnosticFinding]] = {}
        for severity in ("BLOCKING", "REVIEW"):
            for row in result.findings:
                if row.severity == severity:
                    groups.setdefault((row.severity, row.code, row.action, row.guide), []).append(row)
        for number, ((severity, code, action, guide), rows) in enumerate(groups.items(), 1):
            lines.append(f"{number}. [{severity}] {code} ({len(rows)} finding(s))")
            for row in rows[:3]:
                lines.append(f"   At {row.location}: {row.observed}")
            if len(rows) > 3:
                lines.append(f"   ... and {len(rows) - 3} more in diagnosis.json")
            lines.extend((f"   Fix: {action}", f"   Guide: {guide}"))
    if not result.findings:
        lines.append("No diagnosed problems in this scope. Continue with the selected verification command.")
    lines.append(f"Next command: {result.next_command}")
    if result.follow_up_command is not None:
        lines.append(
            "After the fresh run, replace FRESH_NATIVE_DIR with that receipt's native/ "
            "directory and recheck the BOM:"
        )
        lines.append(f"Follow-up command: {result.follow_up_command}")
    lines.append("Diagnostic success does not approve the electrical design or a release.")
    if any(row.code.startswith("NATIVE_") or row.code.startswith("BOM_")
           or row.code == "STALE_NATIVE_REPORT" for row in result.findings):
        lines.append(
            "After changing KiCad source or check settings, use kicad_tooling.verify --depth native "
            "for a fresh report and replace any --native-report/--bom paths above."
        )
    if result.run_directory is not None:
        lines.append(f"Run log: {Path(result.run_directory) / 'events.log'}")
        lines.append(f"Full findings: {Path(result.run_directory) / 'diagnosis.json'}")
    return "\n".join(lines)
