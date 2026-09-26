"""Prepare, check, package, verify and restore evidence-backed release candidates."""

from __future__ import annotations

import argparse
import subprocess
import zipfile
from pathlib import Path

from .hwrepo.contracts import read_model, repo_path
from .hwrepo.models import (
    ReleaseClass,
    ReleaseExportReport,
    ReleaseManifest,
    ReleasePackageReport,
    ReleaseReadinessReport,
)
from .hwrepo.release import check


def format_text(
    command: str,
    report: ReleaseReadinessReport | ReleaseExportReport | ReleasePackageReport,
    output: Path | None = None,
) -> str:
    """Summarize release evidence without hiding the structured report."""
    if isinstance(report, ReleaseReadinessReport):
        lines = [
            f"{report.status}: release readiness for {report.release_id} ({report.release_class.value})",
            f"Issues: {len(report.issues)}. Build authorized: no.",
        ]
        for issue in report.issues[:5]:
            lines.append(f"- {issue.code} at {issue.location}: {issue.message}")
        if len(report.issues) > 5:
            lines.append(f"...and {len(report.issues) - 5} more; use JSON for every issue.")
        return "\n".join(lines)
    if isinstance(report, ReleaseExportReport):
        lines = [
            f"{report.status}: release export for {report.project_id}",
            f"Output: {output}",
            f"Toolchain: {report.toolchain_id}; artifacts: {len(report.artifacts_sha256)}.",
        ]
        failed = [
            name
            for name, record in report.commands.items()
            if record.returncode != 0 or record.error is not None
        ]
        if failed:
            lines.append(f"Failed commands: {', '.join(failed)}. Inspect their command.json files.")
        elif report.status == "FAIL":
            lines.append("Inspect exports.json and output files for missing or changed artifacts.")
        for issue in report.issues:
            lines.append(f"Finding: {issue}")
        return "\n".join(lines)
    lines = [
        f"{report.status}: release {command}",
        f"Manifest: {report.manifest}; source commit: {report.source_commit}",
        f"Package: {report.package}",
        f"SHA-256: {report.package_sha256}",
    ]
    if command == "restore":
        lines.append(f"Restored to: {output}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        nargs="?",
        default="check",
        choices=("prepare", "check", "package", "verify", "restore", "export"),
    )
    parser.add_argument("--manifest", help="Repository-relative release manifest")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--project", action="append", default=[])
    parser.add_argument("--variant", action="append", default=[], metavar="PRODUCT:VARIANT")
    parser.add_argument(
        "--assembly-variant",
        metavar="KICAD_VARIANT",
        help="KiCad component population for a direct board export",
    )
    parser.add_argument("--release-id")
    parser.add_argument(
        "--release-class",
        choices=[value.value for value in ReleaseClass],
        default="engineering_review",
    )
    parser.add_argument("--cli", help="Use an installed pinned KiCad CLI; default uses Docker")
    parser.add_argument(
        "--ngspice", default="ngspice", help="Exact approved simulator for release preparation"
    )
    parser.add_argument(
        "--portable",
        type=Path,
        help="Reuse a full or exact-project release portable report from this clean source",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--destination", type=Path)
    parser.add_argument(
        "--json", action="store_true", help="Print the full candidate manifest when preparing"
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        help="Output format (prepare defaults to text; other commands to JSON)",
    )
    args = parser.parse_args()
    if args.json and (args.command != "prepare" or args.format is not None):
        parser.error("--json is only for prepare and cannot be combined with --format")
    if args.variant and args.command != "prepare":
        parser.error("--variant selects a product during prepare; export uses --assembly-variant")
    if args.assembly_variant is not None and args.command != "export":
        parser.error("--assembly-variant is only for export; prepare uses product board_variants")
    root = args.root.resolve()
    try:
        if args.command == "prepare":
            from .hwrepo.releasing import prepare, resolve_variants

            if args.release_id is None:
                parser.error("prepare requires --release-id and --project or --variant")
            selections = resolve_variants(root, tuple(args.variant))
            manifest = prepare(
                root,
                args.release_id,
                tuple(args.project),
                selections,
                ReleaseClass(args.release_class),
                args.cli,
                args.portable,
                args.ngspice,
            )
            if args.json or args.format == "json":
                print(manifest.model_dump_json(indent=2))
            else:
                print(f"Prepared {manifest.release_class.value} candidate {manifest.release_id}")
                print(f"Source: {manifest.source_commit}; toolchain: {manifest.toolchain_id}")
                print(
                    f"Retained {len(manifest.artifacts)} artifacts. Review is required before manufacture."
                )
                print(f"Candidate written to build/releases/{manifest.release_id}/manifest.json")
            return 0
        if args.command == "export":
            from .hwrepo.discovery import load_registry
            from .hwrepo.exports import export

            if len(args.project) != 1 or args.output is None:
                parser.error("export requires one --project and --output")
            project = next(
                project for project in load_registry(root).projects if project.id == args.project[0]
            )
            report = export(
                root,
                project.config,
                args.output.resolve(),
                args.cli or "kicad-cli",
                args.assembly_variant,
            )
        elif args.command in {"verify", "restore"}:
            from .hwrepo.packaging import restore, verify

            if args.archive is None:
                parser.error("verify and restore require --archive")
            if args.command == "restore":
                if args.destination is None:
                    parser.error("restore requires a new --destination directory")
                report = restore(args.archive, args.destination)
            else:
                report = verify(args.archive)
        elif args.command == "package":
            from .hwrepo.packaging import package

            if args.manifest is None or args.output is None:
                parser.error("package requires --manifest and --output")
            report = package(root, args.manifest, args.output)
        else:
            if args.manifest is None:
                parser.error("check requires --manifest")
            manifest = read_model(repo_path(root, args.manifest), ReleaseManifest)
            report = check(root, manifest)
    except (
        OSError,
        TypeError,
        ValueError,
        StopIteration,
        subprocess.SubprocessError,
        zipfile.BadZipFile,
    ) as exc:
        parser.error(str(exc))
    if args.format == "text":
        location = args.destination if args.command == "restore" else args.output
        print(format_text(args.command, report, location))
    else:
        print(report.model_dump_json(indent=2))
    return 0 if report.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
