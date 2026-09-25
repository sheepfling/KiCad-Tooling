"""Fail-closed synthetic KiCad check; this is not hardware approval."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from .check_toolchain import cli_executable, toolchain
from .hwrepo.contracts import repo_path, write_model
from .hwrepo.discovery import load_config
from .hwrepo.generation import csv_cell
from .hwrepo.models import (
    CheckEvidence,
    CommandEvidence,
    ComponentContract,
    NetlistContract,
    PcbOnlyValidationContract,
    PcbValidationContract,
    ProjectConfig,
    ProjectKind,
    SchematicValidationContract,
    ValidationSummary,
)


def local_state(path: Path) -> bool:
    """Only known non-source KiCad preferences/cache files are excluded."""
    return path.suffix == ".kicad_prl" or path.name == "fp-info-cache"
def hashes(
    root: Path, source_roots: Sequence[str] | None = None
) -> dict[str, str]:
    """Hash the declared design and library roots, excluding local KiCad state."""
    root = root.resolve()
    roots = ("projects",) if source_roots is None else tuple(source_roots)
    if not roots or any(not item for item in roots):
        raise ValueError("source_roots must be a non-empty list of relative directories")
    result: dict[str, str] = {}
    for item in roots:
        directory: Path = repo_path(root, item)
        if not directory.is_dir():
            raise ValueError(f"Declared source root is missing: {item}")
        for path in sorted(directory.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"Source symlink is not allowed: {path}")
            if path.is_file() and not local_state(path):
                # Git manifests use forward-slash repository paths on every OS.
                key: str = path.relative_to(root).as_posix()
                repo_path(root, key)  # Also reject linked/junction ancestors.
                if key in result:
                    raise ValueError(f"Overlapping source roots include: {key}")
                result[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"{label}: expected object")
    return cast(Mapping[str, object], value)


def _sequence(value: object, label: str) -> tuple[object, ...]:
    if not isinstance(value, list):
        raise TypeError(f"{label}: expected list")
    return tuple(cast(list[object], value))


def check_report(
    path: Path,
    kind: Literal["erc", "drc"],
    config: ProjectConfig | None = None,
) -> int:
    """Adapter: parse a third-party KiCad report to one typed count."""
    data = _mapping(json.loads(path.read_text(encoding="utf-8")), "KiCad report")
    version = data.get("kicad_version")
    if not isinstance(version, str) or not version:
        raise ValueError("Missing KiCad report identity")
    if config is not None:
        if version != config.kicad_version:
            raise ValueError("Report toolchain identity differs")
        if data.get("$schema") != f"https://schemas.kicad.org/{kind}.v1.json":
            raise ValueError("Unexpected report schema")
        if data.get("included_severities") != ["error", "warning", "exclusion"]:
            raise ValueError("Report must include errors, warnings and exclusions")
        ignored = _sequence(data.get("ignored_checks"), "ignored-check inventory")
        keys = tuple(
            str(_mapping(item, "ignored check").get("key", ""))
            for item in ignored
        )
        expected = (
            config.validation.expected_ignored_checks.erc
            if kind == "erc"
            else config.validation.expected_ignored_checks.drc
        )
        if sorted(keys) != sorted(expected):
            raise ValueError(f"Disabled-check inventory changed: {keys}")
    if kind == "erc":
        sheets = _sequence(data.get("sheets"), "ERC sheets")
        if not sheets:
            raise ValueError("Missing ERC sheets")
        findings = tuple(
            _sequence(_mapping(sheet, "ERC sheet").get("violations"), "ERC findings")
            for sheet in sheets
        )
    else:
        drc_categories = ("violations", "unconnected_items")
        if config is None or config.kind is not ProjectKind.PCB_ONLY:
            drc_categories += ("schematic_parity",)
        findings = tuple(
            _sequence(data.get(key), f"DRC {key}")
            for key in drc_categories
        )
    return sum(len(items) for items in findings)


def native_report_examples(path: Path, kind: str) -> tuple[str, ...]:
    """Read a few rule descriptions from KiCad JSON for the repair coach."""
    try:
        data = _mapping(json.loads(path.read_text(encoding="utf-8")), "KiCad report")
        if kind == "erc":
            sheets = _sequence(data.get("sheets"), "ERC sheets")
            groups = tuple(
                _sequence(_mapping(sheet, "ERC sheet").get("violations"), "ERC findings")
                for sheet in sheets
            )
        else:
            groups = tuple(
                _sequence(data.get(key), f"DRC {key}")
                for key in ("violations", "unconnected_items", "schematic_parity")
                if data.get(key) is not None
            )
        examples: list[str] = []
        for group in groups:
            for item in group:
                record = _mapping(item, "KiCad finding")
                rule, description = record.get("type"), record.get("description")
                if isinstance(rule, str) and isinstance(description, str):
                    examples.append(f"{rule}: {description}")
                if len(examples) == 3:
                    return tuple(examples)
        return tuple(examples)
    except (OSError, ValueError, TypeError):
        return ()


def read_netlist(path: Path) -> NetlistContract:
    """Parse actual KiCad names, including hierarchical nets and unassigned footprints."""
    tree = ET.parse(path).getroot()
    components: dict[str, ComponentContract] = {}
    for comp in tree.findall("./components/comp"):
        ref = comp.attrib["ref"]
        if ref in components:
            raise ValueError("Duplicate reference in netlist")
        components[ref] = ComponentContract(
            value=comp.findtext("value", ""),
            footprint=comp.findtext("footprint", ""),
            part_id=comp.findtext("./fields/field[@name='PART_ID']") or None,
        )
    nets: dict[str, tuple[str, ...]] = {}
    for net in tree.findall("./nets/net"):
        name = net.attrib["name"].lstrip("/")
        if name in nets:
            raise ValueError("Duplicate normalized net name")
        nets[name] = tuple(
            sorted(
                f"{node.attrib['ref']}.{node.attrib['pin']}"
                for node in net.findall("node")
            )
        )
    return NetlistContract(components=components, nets=nets)


def check_netlist(path: Path, validation: PcbValidationContract | SchematicValidationContract) -> NetlistContract:
    """Compare a native export with reviewed expectations, never an empty scaffold."""
    if not validation.components:
        raise ValueError("Complete the component test contract before native validation")
    contract = read_netlist(path)
    compared = {reference: component if validation.components.get(reference) is not None
                and validation.components[reference].part_id is not None
                else component.model_copy(update={"part_id": None})
                for reference, component in contract.components.items()}
    if compared != validation.components or contract.nets != validation.nets:
        changed_components = sorted(key for key in set(contract.components) | set(validation.components)
                                    if compared.get(key) != validation.components.get(key))
        changed_nets = sorted(key for key in set(contract.nets) | set(validation.nets)
                              if contract.nets.get(key) != validation.nets.get(key))
        raise ValueError(f"Independent netlist contract mismatch: components={changed_components}, nets={changed_nets}")
    return contract
def svg_files(output: Path, name: str) -> list[Path]:
    files: list[Path] = (
        list((output / "schematic").glob("*.svg"))
        if name == "schematic_svg" else [output / "pcb.svg"]
    )
    if not files or any(not p.is_file() or p.stat().st_size == 0 for p in files):
        raise ValueError("Missing SVG export")
    for path in files:
        if ET.parse(path).getroot().tag != "{http://www.w3.org/2000/svg}svg":
            raise ValueError("Export is not an SVG document")
    return files
def execute(
    argv: Sequence[str], cwd: Path, output: Path, name: str
) -> CommandEvidence:
    record = CommandEvidence(
        argv=tuple(argv),
        started_utc=datetime.now(UTC).isoformat(),
        returncode=127,
    )
    try:
        result = subprocess.run(
            argv, cwd=cwd, text=True, capture_output=True, timeout=180, check=False,
        )
        record = record.model_copy(
            update={
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        record = record.model_copy(update={"error": str(exc)})
    write_model(output / f"{name}.command.json", record)
    return record


def write_native_bom(
    path: Path, components: Mapping[str, ComponentContract], disposition: str,
) -> None:
    """Write the native review BOM with the same CSV cell policy as other exports."""
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("Reference", "Value", "Footprint", "Disposition"))
        for reference, component in components.items():
            writer.writerow(tuple(csv_cell(cell) for cell in (
                reference, component.value, component.footprint, disposition,
            )))


def validate(
    root: Path, output: Path, cli: str, config_path: Path | None = None
) -> ValidationSummary:
    """Run a typed, fail-closed KiCad check for one declared configuration."""
    output.mkdir(parents=True, exist_ok=False)
    root = root.resolve()
    from .hwrepo.evidence import source_state

    source_before = source_state(root)
    checks: dict[str, CheckEvidence] = {}
    before: dict[str, str] = {}
    source_roots: tuple[str, ...] = ("projects",)
    config: ProjectConfig | None = None
    profile: Literal["training", "development", "production"] | None = None
    not_for_manufacture: bool | None = None
    selected_config = root / (
        Path("examples/projects/controller/project.json") if config_path is None else config_path
    )
    try:
        if root not in selected_config.resolve().parents:
            raise ValueError("Configuration path must remain inside the repository root")
        config = load_config(root, selected_config)
        from .hwrepo.product import check as check_product
        from .hwrepo.product import (
            check_harness_interface_contract,
            check_project_netlist,
            check_system_wiring_contract,
        )
        from .hwrepo.repository import check_repository
        from .lint_registry import lint

        governance = lint(root, [config.project_id])
        repository = check_repository(root, (config.project_id,))
        product_policy = check_product(
            root, selected_project_ids=(config.project_id,)
        )
        checks["governance"] = CheckEvidence(
            status=governance.status,
            error="; ".join(governance.issues) if governance.issues else None,
        )
        checks["repository"] = CheckEvidence(status=repository.status,
            error="; ".join(repository.issues) if repository.issues else None)
        checks["product_policy"] = CheckEvidence(
            status=product_policy.status,
            error=(
                "; ".join(
                    f"{issue.code}: {issue.message}"
                    for issue in product_policy.issues
                )
                if product_policy.issues
                else None
            ),
        )
        if governance.status != "PASS" or repository.status != "PASS" or product_policy.status != "PASS":
            raise ValueError(
                f"Repository preflight failed: {governance.issues}; {repository.issues}; {product_policy.issues}"
            )
        declared_toolchain = toolchain(root, config.toolchain_id)
        if (
            config.kicad_version != declared_toolchain.kicad_version
            or config.image != declared_toolchain.image
        ):
            raise ValueError(
                f"Configuration toolchain must match declared toolchain {config.toolchain_id}"
            )
        profile = config.assurance_profile
        not_for_manufacture = config.not_for_manufacture
        source_roots = config.source_roots
        before = hashes(root, source_roots)
        if set(before) != set(config.required_inputs):
            raise ValueError(
                f"Input inventory differs; missing={set(config.required_inputs) - set(before)}, "
                f"extra={set(before) - set(config.required_inputs)}"
            )
        checks["source_scope"] = CheckEvidence(
            status="PASS",
            source_hashes=before,
        )
        executable = cli_executable(cli)
        if executable is None:
            raise ValueError("KiCad executable is missing")
        version = execute((executable, "version"), root, output, "version")
        actual = version.stdout.strip()
        if version.returncode != 0 or actual != config.kicad_version:
            raise ValueError(
                f"Expected KiCad {config.kicad_version}; observed {actual!r}"
            )
        checks["toolchain"] = CheckEvidence(
            status="PASS",
            observed_version=actual,
            image=config.image,
        )
        base = repo_path(root, config.project)
        commands: dict[str, tuple[str, ...]] = {}
        if config.kind is ProjectKind.PCB:
            validation = config.validation
            if not isinstance(validation, PcbValidationContract):
                raise ValueError("PCB project requires a PCB validation contract")
            commands.update(
                {
                    "erc": (
                        "sch", "erc", "--format", "json", "--severity-all",
                        "--exit-code-violations", "--output", str(output / "erc.json"),
                        str(base.with_suffix(".kicad_sch")),
                    ),
                    "schematic_svg": (
                        "sch", "export", "svg", "--output", str(output / "schematic"),
                        str(base.with_suffix(".kicad_sch")),
                    ),
                    "drc": (
                        "pcb", "drc", "--format", "json", "--severity-all",
                        "--exit-code-violations", "--schematic-parity", "--refill-zones",
                        "--output", str(output / "drc.json"), str(base.with_suffix(".kicad_pcb")),
                    ),
                    "netlist": (
                        "sch", "export", "netlist", "--format", "kicadxml", "--output",
                        str(output / "netlist.xml"), str(base.with_suffix(".kicad_sch")),
                    ),
                    "pcb_svg": (
                        "pcb", "export", "svg", "--layers", "F.Cu,F.SilkS,Edge.Cuts,Cmts.User",
                        "--output", str(output / "pcb.svg"), str(base.with_suffix(".kicad_pcb")),
                    ),
                }
            )
        elif config.kind is ProjectKind.PCB_ONLY:
            validation = config.validation
            if not isinstance(validation, PcbOnlyValidationContract):
                raise ValueError("PCB-only project requires a PCB-only validation contract")
            commands.update(
                {
                    "drc": (
                        "pcb", "drc", "--format", "json", "--severity-all",
                        "--exit-code-violations", "--refill-zones",
                        "--output", str(output / "drc.json"), str(base.with_suffix(".kicad_pcb")),
                    ),
                    "pcb_svg": (
                        "pcb", "export", "svg", "--layers", "F.Cu,F.SilkS,Edge.Cuts,Cmts.User",
                        "--output", str(output / "pcb.svg"), str(base.with_suffix(".kicad_pcb")),
                    ),
                }
            )
        else:
            commands.update(
                {
                    "erc": (
                        "sch", "erc", "--format", "json", "--severity-all",
                        "--exit-code-violations", "--output", str(output / "erc.json"),
                        str(base.with_suffix(".kicad_sch")),
                    ),
                    "schematic_svg": (
                        "sch", "export", "svg", "--output", str(output / "schematic"),
                        str(base.with_suffix(".kicad_sch")),
                    ),
                }
            )
        if config.kind is ProjectKind.SYSTEM_WIRING:
            check_system_wiring_contract(root, config)
            checks["system_contract"] = CheckEvidence(status="PASS")
        elif config.kind is ProjectKind.HARNESS_INTERFACE:
            check_harness_interface_contract(root, config)
            checks["harness_contract"] = CheckEvidence(status="PASS")
        if config.electrical is not None or config.component_identity.required or (
            isinstance(config.validation, SchematicValidationContract) and config.validation.components
        ):
            commands["netlist"] = ("sch", "export", "netlist", "--format", "kicadxml", "--output",
                                   str(output / "netlist.xml"), str(base.with_suffix(".kicad_sch")))
        for name, arguments in commands.items():
            command = execute((executable, *arguments), root, output, name)
            evidence = CheckEvidence(status="FAIL", returncode=command.returncode)
            try:
                if command.returncode != 0 and not (name in {"erc", "drc"} and command.returncode == 5):
                    raise ValueError(
                        f"KiCad command failed with {command.returncode}"
                    )
                if name in {"erc", "drc"}:
                    kind: Literal["erc", "drc"] = "erc" if name == "erc" else "drc"
                    # KiCad uses exit 5 for findings. Retain their count and report
                    # identity even when the gate correctly rejects the design.
                    findings = check_report(output / f"{name}.json", kind, config)
                    evidence = evidence.model_copy(update={"findings": findings})
                    ignored = (
                        config.validation.expected_ignored_checks.erc
                        if kind == "erc"
                        else config.validation.expected_ignored_checks.drc
                    )
                    evidence = evidence.model_copy(
                        update={
                            "findings": findings,
                            "expected_ignored_checks": ignored,
                        }
                    )
                    if findings:
                        raise ValueError(f"{findings} findings, including exclusions")
                    if command.returncode != 0:
                        raise ValueError(f"KiCad command failed with {command.returncode}")
                elif name == "netlist":
                    validation = config.validation
                    if not isinstance(validation, (PcbValidationContract, SchematicValidationContract)):
                        raise ValueError("Netlist check requires an electrical component contract")
                    check_netlist(output / "netlist.xml", validation)
                    if config.electrical is not None:
                        from .hwrepo.electrical import grounding_checks, load_analysis

                        electrical = load_analysis(root, config)
                        if electrical is not None:
                            ground = grounding_checks(electrical.grounding, read_netlist(output / "netlist.xml"))
                            failures = [row.detail for row in ground if row.status not in {"PASS", "NOT_APPLICABLE"}]
                            checks["grounding"] = CheckEvidence(
                                status="FAIL" if failures else "PASS",
                                error="; ".join(failures) if failures else None,
                            )
                    identity = check_project_netlist(
                        root, config.project_id, output / "netlist.xml"
                    )
                    disposition = (
                        "NOT FOR MANUFACTURE"
                        if config.not_for_manufacture
                        else "ENGINEERING — RELEASE REVIEW REQUIRED"
                    )
                    write_native_bom(output / "bom.csv", validation.components, disposition)
                    evidence = evidence.model_copy(
                        update={"identity_status": identity.status}
                    )
                else:
                    evidence = evidence.model_copy(
                        update={
                            "files": tuple(
                                path.relative_to(output).as_posix()
                                for path in svg_files(output, name)
                            )
                        }
                    )
                checks[name] = evidence.model_copy(update={"status": "PASS"})
            except (OSError, ValueError, TypeError, KeyError, ET.ParseError) as exc:
                checks[name] = evidence.model_copy(update={"error": str(exc)})
    except (OSError, ValueError) as exc:
        checks["preflight"] = CheckEvidence(status="FAIL", error=str(exc))

    try:
        after = hashes(root, source_roots)
        checks["source_unchanged"] = CheckEvidence(
            status="PASS" if before == after else "FAIL",
            source_hashes=after,
        )
    except (OSError, ValueError) as exc:
        checks["source_unchanged"] = CheckEvidence(status="FAIL", error=str(exc))

    required = {"source_scope", "toolchain", "source_unchanged"}
    if config is not None and config.kind is ProjectKind.PCB:
        required.update({"erc", "schematic_svg", "drc", "netlist", "pcb_svg"})
    elif config is not None and config.kind is ProjectKind.PCB_ONLY:
        required.update({"drc", "pcb_svg"})
    else:
        required.update({"erc", "schematic_svg"})
        if config is not None and config.kind is ProjectKind.SYSTEM_WIRING:
            required.add("system_contract")
        elif config is not None and config.kind is ProjectKind.HARNESS_INTERFACE:
            required.add("harness_contract")
    if config is not None and config.electrical is not None:
        required.add("grounding")
    if config is not None and (config.electrical is not None or config.component_identity.required or (
        isinstance(config.validation, SchematicValidationContract) and config.validation.components
    )):
        required.add("netlist")
    status = (
        "PASS"
        if required.issubset(checks)
        and all(evidence.status == "PASS" for evidence in checks.values())
        else "FAIL"
    )
    summary = ValidationSummary(
        timestamp_utc=datetime.now(UTC).isoformat(),
        checked_commit=source_before.commit or "LOCAL_UNBOUND",
        source=source_before.model_copy(update={
            "clean": source_before.clean and source_state(root) == source_before,
        }),
        project_id=None if config is None else config.project_id,
        pr_head_commit=os.environ.get("PR_HEAD_SHA"),
        assurance_profile=profile,
        not_for_manufacture=not_for_manufacture,
        project_kind=None if config is None else config.kind,
        checks=checks,
        status=status,
        artifacts_sha256={
            path.relative_to(output).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(output.rglob("*"))
            if path.is_file()
        },
    )
    write_model(output / "summary.json", summary)
    return summary
def main() -> int:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--cli", default="kicad-cli",
        help="KiCad CLI command or path (relative paths use the caller's cwd)",
    )
    parser.add_argument(
        "--config", type=Path, default=Path("examples/projects/controller/project.json")
    )
    args: argparse.Namespace = parser.parse_args()
    summary = validate(args.root.resolve(), args.output.resolve(), args.cli, args.config)
    print(summary.model_dump_json(indent=2))
    return 0 if summary.status == "PASS" else 1
if __name__ == "__main__":
    sys.exit(main())
