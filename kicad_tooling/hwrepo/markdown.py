"""Typed SnakeMD builders for Markdown created by repository workflows."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from urllib.parse import quote

from snakemd import Document, Inline, MDList, Paragraph

from .models import ProjectKind


def paragraph(document: Document, *content: str | Inline) -> None:
    """Append one structured paragraph while preserving inline semantics."""
    document.add_block(Paragraph(content))


def markdown_text(document: Document) -> str:
    """Render deterministic Markdown with exactly one final newline."""
    return f"{document}".rstrip("\n") + "\n"


def write_markdown(path: Path, document: Document) -> None:
    """Render one deterministic UTF-8 Markdown document with a final newline."""
    path.write_text(markdown_text(document), encoding="utf-8")


def retitled_document(source: str, title: str) -> Document:
    """Replace the first heading while preserving the authored document body."""
    _, separator, body = source.partition("\n")
    if not separator:
        raise ValueError("Markdown document must contain a title and body")
    document = Document()
    document.add_heading(title)
    remaining = body.strip("\n")
    if remaining:
        document.add_raw(remaining)
    return document


def design_notes() -> Document:
    document = Document()
    document.add_heading("Design notes")
    document.add_paragraph(
        "Record purpose, requirements, interfaces, design decisions and bring-up results here."
    )
    return document


def project_readme(project_id: str, kind: ProjectKind = ProjectKind.PCB) -> Document:
    document = Document()
    document.add_heading(project_id)
    document.add_paragraph("Development project — NOT FOR MANUFACTURE.")
    if kind is ProjectKind.PCB_ONLY:
        document.add_paragraph(
            "PCB-only capture lane: native DRC and layout review apply, but ERC, netlist "
            "parity, product assembly and non-review release authority require an "
            "authoritative schematic and migration to pcb."
        )
    paragraph(
        document,
        "Create the native project in ",
        Inline("kicad/", code=True),
        " using the toolchain selected in ",
        Inline("project.json", link="project.json"),
        ". Complete the source inventory and ",
        Inline("test contract", link="tests/contract.json"),
        ". See ",
        Inline("design notes", link="docs/README.md"),
        ".",
    )
    paragraph(
        document,
        "From the repository root: ",
        Inline(f"python -B -m kicad_tooling.verify --project {project_id}", code=True),
        ".",
    )
    document.add_paragraph(
        "Checks will fail until the native files and engineering expectations exist. "
        "After they are authored, add --depth native for exact KiCad checks and an ignored receipt."
    )
    return document


def imported_project_readme(
    project_id: str,
    project_path: str,
    upstream_documents: Iterable[str],
    kind: ProjectKind = ProjectKind.PCB,
) -> Document:
    document = Document()
    document.add_heading(project_id)
    document.add_paragraph("Imported development project — NOT FOR MANUFACTURE.")
    if kind is ProjectKind.PCB_ONLY:
        document.add_paragraph(
            "PCB-only import: this island preserves a board with no matching schematic. "
            "It has DRC/layout checks only and cannot support product assembly or a "
            "non-review release until an authoritative schematic is added and it is "
            "migrated to pcb."
        )
    paragraph(
        document,
        "Open ",
        Inline("the native project", link=quote(project_path)),
        ". Filenames and native bytes are preserved.",
    )
    paragraph(
        document,
        "Review the ",
        Inline("import receipt", link="docs/import.json"),
        ", including excluded files, and ",
        Inline("design notes", link="docs/README.md"),
        ". Complete the ",
        "board-local " if kind is ProjectKind.PCB_ONLY else "independent ",
        Inline("test contract", link="tests/contract.json"),
        " and ",
        Inline("project metadata", link="project.json"),
        ".",
    )
    paragraph(
        document,
        "From the repository root: ",
        Inline(f"python -B -m kicad_tooling.verify --project {project_id}", code=True),
        ".",
    )
    document.add_paragraph(
        "Import success means source was copied, not that native validation passes. "
        "After independently authoring the contract, add --depth native for exact KiCad checks."
    )
    links = tuple(
        Inline(f"Upstream {name}", link=quote(f"kicad/{name}")) for name in upstream_documents
    )
    if links:
        document.add_block(MDList(links))
    return document


def release_review(
    release_id: str,
    source_commit: str,
    release_class: str,
    electrical: Iterable[tuple[str, str]] = (),
) -> Document:
    document = Document()
    document.add_heading(release_id)
    paragraph(
        document,
        "Source: ",
        Inline(source_commit, code=True),
        ". Class: ",
        Inline(release_class, code=True),
        ".",
    )
    document.add_paragraph(
        "Candidate for engineering review. This report records executed checks; "
        "it is not human approval."
    )
    rows = list(electrical)
    if rows:
        document.add_heading("Electrical coverage", level=2)
        document.add_table(["Project", "Evidence"], rows)
        document.add_paragraph(
            "PASS covers the committed requirements and their recorded applicability decisions. "
            "NOT_CONFIGURED means electrical analysis was not assessed; it is allowed only "
            "for engineering review. Review missing requirements before any build release."
        )
    document.add_paragraph(
        "Manufacturing and assembly files require review of layers, origin, "
        "population, and supplier requirements. Electrical models do not establish physical "
        "grounding, thermal margin, transient behavior, signal integrity or EMC. Retain the "
        "responsible engineers' design reviews and applicable measurements separately."
    )
    return document
