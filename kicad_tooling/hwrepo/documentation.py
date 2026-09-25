"""Typed engine for deterministic Markdown layout and repository-documentation policy."""
from __future__ import annotations

import re
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

from .contracts import read_model, repo_path
from .models import (
    DocumentationException,
    DocumentationIssue,
    DocumentationPolicy,
    DocumentationPolicyReport,
)

POLICY_PATH = "catalog/documentation-policy.json"
DEFAULT_ROOTS = ("README.md",)
PRESERVED_LEGAL_NAMES = frozenset({"license.md", "licence.md", "copying.md", "notice.md"})
IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        ".github",
        ".evidence",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "venv",
        "dist",
        "htmlcov",
        "__pycache__",
        "build",
    }
)
HEADING_PATTERN = re.compile(r"^(?P<level>#{1,6})\s+(?P<label>\S.*?)(?:\s+#+)?$")
FENCE_PATTERN = re.compile(r"^\s*(?P<fence>`{3,}|~{3,})")
LINK_PATTERN = re.compile(r"!?\[[^\]\n]*\]\((?P<destination>[^\n)]*)\)")
EXTERNAL_SCHEMES = ("data:", "http:", "https:", "mailto:", "tel:")


def label(path: Path, root: Path) -> str:
    """Return a POSIX repository path for report evidence."""
    return path.relative_to(root).as_posix()


def issue(code: str, path: Path, root: Path, line: int, message: str) -> DocumentationIssue:
    """Create one exact, source-located policy finding."""
    return DocumentationIssue(code=code, path=label(path, root), line=line, message=message)


def markdown_files(root: Path) -> tuple[Path, ...]:
    """Discover tracked-style source documents while excluding generated state."""
    return tuple(
        sorted(
            (
                path
                for path in root.rglob("*")
                if path.is_file()
                and path.suffix.casefold() == ".md"
                and not any(part in IGNORED_DIRECTORIES for part in path.relative_to(root).parts)
            ),
            key=lambda path: label(path, root),
        )
    )


def anchor_slug(value: str) -> str:
    """Use the stable, conservative subset of GitHub-style heading anchor slugs."""
    without_links = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    without_code = re.sub(r"`([^`]*)`", r"\1", without_links)
    normalized = re.sub(r"[^a-z0-9 _-]", "", without_code.casefold())
    return re.sub(r"[ _]+", "-", normalized).strip("-")


def document_headings(
    document: Path, root: Path, text: str
) -> tuple[dict[str, int], tuple[DocumentationIssue, ...]]:
    """Collect anchors and local layout findings without interpreting fenced examples."""
    anchors: dict[str, int] = {}
    findings: list[DocumentationIssue] = []
    previous_level = 0
    h1_count = 0
    opened_fence: str | None = None
    for line_number, line in enumerate(text.splitlines(), start=1):
        fence = FENCE_PATTERN.match(line)
        if fence is not None:
            marker = fence.group("fence")
            if opened_fence is None:
                opened_fence = marker
            elif marker[0] == opened_fence[0] and len(marker) >= len(opened_fence):
                opened_fence = None
            continue
        if opened_fence is not None:
            continue
        heading = HEADING_PATTERN.match(line)
        if heading is None:
            continue
        level = len(heading.group("level"))
        if level == 1:
            h1_count += 1
        if previous_level and level > previous_level + 1:
            findings.append(
                issue(
                    "MD003",
                    document,
                    root,
                    line_number,
                    "Heading levels may increase by only one level at a time.",
                )
            )
        previous_level = level
        slug = anchor_slug(heading.group("label"))
        occurrence = 0
        resolved_slug = slug
        while resolved_slug in anchors:
            occurrence += 1
            resolved_slug = f"{slug}-{occurrence}"
        anchors[resolved_slug] = line_number
    if opened_fence is not None:
        findings.append(
            issue(
                "MD005",
                document,
                root,
                len(text.splitlines()) or 1,
                "Fenced code block is not closed.",
            )
        )
    if h1_count != 1:
        findings.append(
            issue(
                "MD004",
                document,
                root,
                1,
                "Each document must contain exactly one level-one heading.",
            )
        )
    return anchors, tuple(findings)


def layout_issues(document: Path, root: Path, text: str) -> tuple[DocumentationIssue, ...]:
    """Check deterministic whitespace, tab, fence and heading invariants."""
    findings: list[DocumentationIssue] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if "\t" in line:
            findings.append(
                issue("MD001", document, root, line_number, "Tabs are not permitted in Markdown.")
            )
        if line.rstrip(" \t") != line:
            findings.append(
                issue(
                    "MD002",
                    document,
                    root,
                    line_number,
                    "Trailing whitespace is not permitted in Markdown.",
                )
            )
    _, structural = document_headings(document, root, text)
    findings.extend(structural)
    return tuple(findings)


def split_destination(raw: str) -> tuple[str, str | None]:
    """Separate a local Markdown destination from its optional fragment."""
    destination = raw.strip()
    if destination.startswith("<") and ">" in destination:
        destination = destination[1:destination.index(">")]
    elif " " in destination:
        destination = destination.split(maxsplit=1)[0]
    path, marker, fragment = destination.partition("#")
    return unquote(path), unquote(fragment) if marker else None


def local_target(root: Path, document: Path, destination: str) -> Path:
    """Resolve one local link using the shared portable-path boundary."""
    if PurePosixPath(destination).is_absolute():
        raise ValueError("Absolute documentation link")
    parts = list(document.parent.relative_to(root).parts)
    for component in destination.split("/"):
        if component == "..":
            if not parts:
                raise ValueError("Documentation link escapes repository")
            parts.pop()
        elif component != ".":
            parts.append(component)
            # Validate each segment before a later '..' can hide a bad path or link.
            repo_path(root, "/".join(parts))
    return repo_path(root, "/".join(parts))


def link_issues(
    document: Path,
    root: Path,
    text: str,
    anchors_by_path: dict[str, dict[str, int]],
) -> tuple[tuple[DocumentationIssue, ...], tuple[str, ...]]:
    """Check portable local targets and fragments, returning Markdown graph edges."""
    findings: list[DocumentationIssue] = []
    markdown_edges: list[str] = []
    opened_fence: str | None = None
    for line_number, line in enumerate(text.splitlines(), start=1):
        fence = FENCE_PATTERN.match(line)
        if fence is not None:
            marker = fence.group("fence")
            if opened_fence is None:
                opened_fence = marker
            elif marker[0] == opened_fence[0] and len(marker) >= len(opened_fence):
                opened_fence = None
            continue
        if opened_fence is not None:
            continue
        for match in LINK_PATTERN.finditer(line):
            destination, fragment = split_destination(match.group("destination"))
            if destination.casefold().startswith(EXTERNAL_SCHEMES):
                continue
            target = document
            if destination:
                try:
                    target = local_target(root, document, destination)
                except ValueError as exc:
                    findings.append(
                        issue("DOC101", document, root, line_number, f"Unsafe local link: {exc}")
                    )
                    continue
                if not target.is_file():
                    findings.append(
                        issue(
                            "DOC102",
                            document,
                            root,
                            line_number,
                            f"Local link target does not exist: {destination}",
                        )
                    )
                    continue
            target_label = label(target, root)
            if target.suffix.casefold() == ".md":
                markdown_edges.append(target_label)
            if fragment is not None:
                anchors = anchors_by_path.get(target_label)
                if anchors is None or fragment not in anchors:
                    findings.append(
                        issue(
                            "DOC103",
                            document,
                            root,
                            line_number,
                            f"Local link fragment does not exist: #{fragment}",
                        )
                    )
    return tuple(findings), tuple(markdown_edges)


def default_policy() -> DocumentationPolicy:
    """Provide a bounded report even when the repository policy file is invalid."""
    return DocumentationPolicy(roots=DEFAULT_ROOTS)


def validate_policy_paths(root: Path, policy: DocumentationPolicy) -> DocumentationPolicy:
    """Apply the shared portable-path contract to typed documentation policy values."""
    for configured_root in policy.roots:
        repo_path(root, configured_root)
    for namespace in policy.documentation_namespaces:
        repo_path(root, namespace)
        parts = PurePosixPath(namespace).parts
        if len(parts) < 2 or parts[0] != "docs":
            raise ValueError("Documentation namespaces must be directories below docs/")
    for exception in policy.exceptions:
        repo_path(root, exception.path)
    return policy


def namespace_issues(
    documents: tuple[Path, ...], root: Path, namespaces: tuple[str, ...]
) -> tuple[DocumentationIssue, ...]:
    """Keep repository-wide guides in explicit scaffold or adopter namespaces."""
    if not namespaces:
        return ()
    allowed = tuple(PurePosixPath(namespace).parts for namespace in namespaces)
    findings: list[DocumentationIssue] = []
    for document in documents:
        relative = PurePosixPath(label(document, root))
        if not relative.parts or relative.parts[0] != "docs":
            continue
        if relative == PurePosixPath("docs/README.md"):
            continue
        if any(relative.parts[: len(namespace)] == namespace for namespace in allowed):
            continue
        findings.append(
            issue(
                "DOC106",
                document,
                root,
                1,
                "Repository-wide Markdown must live in a configured docs namespace.",
            )
        )
    return tuple(findings)


def active_exceptions(
    exceptions: tuple[DocumentationException, ...], today: date
) -> tuple[tuple[DocumentationException, ...], tuple[DocumentationIssue, ...]]:
    """Keep expired waivers visible instead of silently weakening the document gate."""
    active: list[DocumentationException] = []
    findings: list[DocumentationIssue] = []
    for exception in exceptions:
        if exception.expires < today:
            findings.append(
                DocumentationIssue(
                    code="DOC201",
                    path=exception.path,
                    line=1,
                    message=f"Documentation exception {exception.id} expired on {exception.expires.isoformat()}.",
                )
            )
        else:
            active.append(exception)
    return tuple(active), tuple(findings)


def apply_exceptions(
    findings: tuple[DocumentationIssue, ...], exceptions: tuple[DocumentationException, ...]
) -> tuple[DocumentationIssue, ...]:
    """Suppress only exact code/path matches and fail stale waiver records."""
    retained: list[DocumentationIssue] = []
    used: set[str] = set()
    for finding in findings:
        matching = tuple(
            exception
            for exception in exceptions
            if exception.code == finding.code and exception.path == finding.path
        )
        if matching:
            used.update(exception.id for exception in matching)
        else:
            retained.append(finding)
    for exception in exceptions:
        if exception.id not in used:
            retained.append(
                DocumentationIssue(
                    code="DOC202",
                    path=exception.path,
                    line=1,
                    message=f"Documentation exception {exception.id} is unused.",
                )
            )
    return tuple(retained)


def check(root: Path, today: date | None = None) -> DocumentationPolicyReport:
    """Run Markdown-format and local-documentation graph policy for one repository."""
    resolved_root = root.resolve()
    report_findings: list[DocumentationIssue] = []
    policy = default_policy()
    try:
        policy = validate_policy_paths(
            resolved_root,
            read_model(repo_path(resolved_root, POLICY_PATH), DocumentationPolicy),
        )
        island_roots = tuple(
            path.relative_to(resolved_root).as_posix()
            for directory in ("projects", "products", "examples/projects", "examples/products")
            for path in sorted((resolved_root / directory).glob("*/README.md"))
        )
        policy = validate_policy_paths(resolved_root, policy.model_copy(update={
            "roots": tuple(dict.fromkeys((*policy.roots, *island_roots))),
        }))
    except (OSError, ValueError) as exc:
        report_findings.append(
            DocumentationIssue(
                code="DOC900",
                path=POLICY_PATH,
                line=1,
                message=f"Documentation policy could not be loaded: {exc}",
            )
        )
    documents = markdown_files(resolved_root)
    report_findings.extend(
        namespace_issues(documents, resolved_root, policy.documentation_namespaces)
    )
    anchors_by_path: dict[str, dict[str, int]] = {}
    document_text: dict[str, str] = {}
    for document in documents:
        relative = label(document, resolved_root)
        text = document.read_text(encoding="utf-8")
        document_text[relative] = text
        anchors, _ = document_headings(document, resolved_root, text)
        anchors_by_path[relative] = anchors
        if document.name.casefold() not in PRESERVED_LEGAL_NAMES:
            report_findings.extend(layout_issues(document, resolved_root, text))
    edges: dict[str, tuple[str, ...]] = {}
    for document in documents:
        relative = label(document, resolved_root)
        findings, outgoing = link_issues(
            document,
            resolved_root,
            document_text[relative],
            anchors_by_path,
        )
        report_findings.extend(findings)
        edges[relative] = outgoing
    reachable: set[str] = set()
    pending = list(policy.roots)
    while pending:
        current = pending.pop()
        if current in reachable:
            continue
        if current not in anchors_by_path:
            report_findings.append(
                DocumentationIssue(
                    code="DOC104",
                    path=current,
                    line=1,
                    message="Configured documentation root does not exist.",
                )
            )
            continue
        reachable.add(current)
        pending.extend(edges[current])
    for document in documents:
        relative = label(document, resolved_root)
        if relative not in reachable and document.name.casefold() not in PRESERVED_LEGAL_NAMES:
            report_findings.append(
                issue(
                    "DOC105",
                    document,
                    resolved_root,
                    1,
                    "Markdown document is unreachable from a configured documentation root.",
                )
            )
    effective_today = today or datetime.now(UTC).date()
    active, expiration_findings = active_exceptions(policy.exceptions, effective_today)
    report_findings.extend(expiration_findings)
    final_findings = apply_exceptions(tuple(report_findings), active)
    ordered = tuple(
        sorted(
            final_findings,
            key=lambda finding: (finding.path, finding.line, finding.code, finding.message),
        )
    )
    return DocumentationPolicyReport(
        roots=policy.roots,
        documents=len(documents),
        issues=ordered,
        status="FAIL" if ordered else "PASS",
    )
