"""Inspect one sourced CAD bundle and install project-local libraries with a locked plan.

Installing library data does not select a purchasing part, approve pin functions, or
change placed symbols, pads, nets, routing, or independent electrical expectations.
"""
from __future__ import annotations

import difflib
import hashlib
import os
import re
from collections.abc import Mapping
from pathlib import Path

from ..validate import hashes
from .auto_cad import _Edit, _receipt, _write_edits  # pyright: ignore[reportPrivateUsage]
from .cad_assets import _model_signature, _pads  # pyright: ignore[reportPrivateUsage]
from .contracts import read_model, repo_path, update_project_manifest_inputs
from .discovery import load_config
from .model_inventory import _atoms, _Span  # pyright: ignore[reportPrivateUsage]
from .models import (
    AutoCadPlan,
    CadBundleCheck,
    CadImportPlan,
    CadImportReport,
    CadSourceBundle,
    ProjectManifest,
)
from .part_cad import (
    _nodes,  # pyright: ignore[reportPrivateUsage]
    _properties,  # pyright: ignore[reportPrivateUsage]
    _property,  # pyright: ignore[reportPrivateUsage]
    _quote,  # pyright: ignore[reportPrivateUsage]
    _root,  # pyright: ignore[reportPrivateUsage]
    _scalar,  # pyright: ignore[reportPrivateUsage]
    _tokens,  # pyright: ignore[reportPrivateUsage]
)
from .part_picker import _snapshot, _verify_snapshot  # pyright: ignore[reportPrivateUsage]
from .parts_workflow import local_path, selected_project

_MAX_FILE = 32 * 1024 * 1024
_MAX_TOTAL = 96 * 1024 * 1024
_MAX_FILES = 64
_MAX_MANIFEST = 1024 * 1024
_REVIEW_LIMIT = (
    "Pin numbers are internally consistent; manufacturer pin functions and physical fit "
    "still need review. This imports library data without changing the schematic or PCB."
)


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _unlinked_directory(path: Path) -> Path:
    absolute = Path(os.path.abspath(path))
    for ancestor in (absolute, *absolute.parents):
        if ancestor.is_symlink():
            raise ValueError("CAD bundle directory must not contain a symlink")
    if not absolute.is_dir():
        raise ValueError("CAD bundle directory is missing")
    return absolute


def _files(bundle_dir: Path, expected: Mapping[str, str]) -> dict[str, bytes]:
    directory = _unlinked_directory(bundle_dir)
    if len(expected) > _MAX_FILES or "bundle.json" in expected:
        raise ValueError("CAD bundle has an invalid or oversized recorded file inventory")
    names: set[str] = set()
    folded: set[str] = set()
    entries = 0
    for path in directory.rglob("*"):
        entries += 1
        if entries > _MAX_FILES * 4:
            raise ValueError("CAD bundle exceeds supported directory entry count")
        name = path.relative_to(directory).as_posix()
        if any(piece.casefold() == ".git" for piece in path.relative_to(directory).parts):
            raise ValueError("CAD bundle may not contain Git metadata")
        repo_path(directory, name)
        if name.casefold() in folded:
            raise ValueError("CAD bundle contains case-conflicting paths")
        folded.add(name.casefold())
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError("CAD bundle contains a non-regular file")
        if name != "bundle.json":
            names.add(name)
        if len(names) > _MAX_FILES:
            raise ValueError("CAD bundle exceeds supported file count")
    if names != set(expected):
        raise ValueError("CAD bundle files differ from the recorded complete inventory")
    result: dict[str, bytes] = {}
    total = 0
    for name, digest in sorted(expected.items()):
        path = repo_path(directory, name)
        if path.stat().st_size > _MAX_FILE:
            raise ValueError(f"CAD bundle file exceeds size limit: {name}")
        with path.open("rb") as incoming:
            content = incoming.read(_MAX_FILE + 1)
        total += len(content)
        if len(content) > _MAX_FILE or total > _MAX_TOTAL:
            raise ValueError("CAD bundle exceeds supported byte limits")
        if not content or _sha(content) != digest:
            raise ValueError(f"CAD bundle file is empty or changed: {name}")
        result[name] = content
    return result


def _symbol(source: str, name: str) -> tuple[_Span, tuple[str, ...]]:
    parent = _root(source, "kicad_symbol_lib")
    symbols = _nodes(source, parent, "symbol")
    if len(symbols) != 1 or _atoms(source, symbols[0]) != ("symbol", name):
        raise ValueError("CAD bundle must contain exactly its named native symbol")
    symbol = symbols[0]
    if _nodes(source, symbol, "extends"):
        raise ValueError("Inherited symbols need their full native dependency bundle")
    pins: list[str] = []
    pending = [symbol]
    while pending:
        node = pending.pop()
        pending.extend(_nodes(source, node, "symbol"))
        for pin in _nodes(source, node, "pin"):
            number = _scalar(source, pin, "number")
            if not number or any(ord(char) < 32 for char in number):
                raise ValueError("Sourced symbol has an empty or invalid pin number")
            pins.append(number)
    if not pins:
        raise ValueError("Sourced symbol has no numbered pins")
    return symbol, tuple(sorted(set(pins)))


def _native_member(name: str) -> None:
    if not name or any(char in name for char in "/\\:$") or name in {".", ".."}:
        raise ValueError("Native CAD member must have one unambiguous portable name")
    _quote(name)


def _native_footprint(source: str, name: str) -> str:
    """Normalize only the legacy module header; keep every geometry node intact."""
    if source.lstrip().startswith("(module"):
        parent = _root(source, "module")
        atoms = _atoms(source, parent)
        if len(atoms) != 2 or atoms[1] not in {name, "easyeda2kicad:" + name}:
            raise ValueError("Legacy sourced footprint root differs from its recorded identity")
        tokens = _tokens(source, parent)
        first, identity = tokens[0], tokens[1]
        source = source[:identity.start] + _quote(name) + source[identity.end:]
        source = source[:first.start] + "footprint" + source[first.end:]
    parent = _root(source, "footprint")
    if _atoms(source, parent) != ("footprint", name):
        raise ValueError("Sourced footprint root differs from its recorded identity")
    return source


def _model_reference(source: str, parent: _Span, expected: str) -> str:
    models = _nodes(source, parent, "model")
    if len(models) != 1:
        raise ValueError("Sourced footprint must have exactly one paired WRL model")
    model = models[0]
    expression = source[model.start:model.end]
    reference, _, _, _, hidden = _model_signature(expression)
    if hidden:
        raise ValueError("Sourced footprint's paired model is hidden")
    if reference.startswith("${KIPRJMOD}/"):
        relative = reference.removeprefix("${KIPRJMOD}/")
    else:
        relative = reference
    if "$" in relative or relative != expected:
        raise ValueError("Sourced footprint's model path differs from its recorded WRL file")
    if Path(relative).suffix.casefold() != ".wrl":
        raise ValueError("The sourced CAD flow requires its translated WRL model; STEP substitution is unsupported")
    return reference


def _replace_property(source: str, parent: _Span, name: str, value: str) -> str:
    properties = _properties(source, parent)
    if name not in properties:
        raise ValueError(f"Sourced symbol is missing its {name} property")
    token = _tokens(source, properties[name])[2]
    return source[:token.start] + _quote(value) + source[token.end:]


def _table(source: str | None, kind: str, nickname: str, uri: str) -> str:
    entry = (f'(lib (name {_quote(nickname)})(type "KiCad")'
             f'(uri {_quote(uri)})(options "")(descr "Sourced CAD; review pinout and physical fit"))')
    if source is None:
        return f"({kind}\n  (version 7)\n  {entry}\n)\n"
    parent = _root(source, kind)
    seen: set[str] = set()
    for node in _nodes(source, parent, "lib"):
        name = _scalar(source, node, "name")
        if not name or name.casefold() in seen:
            raise ValueError("Project library table contains duplicate or case-conflicting nicknames")
        seen.add(name.casefold())
        if name.casefold() == nickname.casefold():
            if (name == nickname and _scalar(source, node, "type") == "KiCad"
                    and _scalar(source, node, "uri") == uri
                    and _scalar(source, node, "options", default="") == ""):
                return source
            raise ValueError(f"Project library nickname conflicts with sourced CAD: {nickname}")
    newline = "\r\n" if "\r\n" in source else "\n"
    return source[:parent.end - 1] + "  " + entry + newline + source[parent.end - 1:]


def _diff(edits: tuple[_Edit, ...]) -> str:
    chunks: list[str] = []
    for edit in edits:
        if edit.path.endswith(".wrl"):
            chunks.append(f"Import {edit.path} ({len(edit.after)} bytes; SHA256 {_sha(edit.after)})\n")
        else:
            chunks.append("".join(difflib.unified_diff(
                (edit.before or b"").decode("utf-8").splitlines(keepends=True),
                edit.after.decode("utf-8").splitlines(keepends=True),
                fromfile="a/" + edit.path, tofile="b/" + edit.path)))
    return "".join(chunks)


def _read_bundle(directory: Path) -> tuple[CadSourceBundle, bytes]:
    directory = _unlinked_directory(directory)
    path = repo_path(directory, "bundle.json")
    if not path.is_file() or path.stat().st_size > _MAX_MANIFEST:
        raise ValueError("CAD bundle needs a bounded bundle.json source manifest")
    content = path.read_bytes()
    if len(content) > _MAX_MANIFEST:
        raise ValueError("CAD bundle source manifest exceeds size limit")
    return read_model(path, CadSourceBundle), content


def _checked(directory: Path, bundle: CadSourceBundle) -> tuple[CadBundleCheck, dict[str, bytes]]:
    saved, _ = _read_bundle(directory)
    if saved != bundle:
        raise ValueError("CAD bundle metadata changed after sourcing")
    expected = {item.path: item.sha256 for item in bundle.files}
    if len(expected) != len(bundle.files):
        raise ValueError("CAD bundle repeats a recorded file path")
    files = _files(directory, expected)
    selected = (bundle.symbol_file, bundle.footprint_file, bundle.model_file)
    if len(set(selected)) != 3 or not set(selected).issubset(files):
        raise ValueError("CAD bundle is missing a distinct symbol, footprint or model")
    for name in (bundle.symbol_name, bundle.footprint_name):
        _native_member(name)
    if (Path(bundle.symbol_file).suffix != ".kicad_sym"
            or Path(bundle.footprint_file).suffix != ".kicad_mod"
            or Path(bundle.model_file).suffix != ".wrl"):
        raise ValueError("CAD source identities must name native symbol, footprint and WRL files")
    if Path(bundle.footprint_file).name != bundle.footprint_name + ".kicad_mod":
        raise ValueError("Sourced footprint filename differs from its native identity")
    if not Path(bundle.footprint_file).parent.name.endswith(".pretty"):
        raise ValueError("Sourced footprint must be inside a native .pretty library")
    symbol_text = files[bundle.symbol_file].decode("utf-8")
    symbol, pins = _symbol(symbol_text, bundle.symbol_name)
    properties = _properties(symbol_text, symbol)
    for name, expected_value in (("Manufacturer", bundle.manufacturer), ("MPN", bundle.mpn),
                                 ("LCSC Part", bundle.supplier_id)):
        if _property(symbol_text, properties, name, required=True) != expected_value:
            raise ValueError(f"Sourced symbol {name} differs from the recorded exact part identity")
    bound_footprint = _property(symbol_text, properties, "Footprint", required=True)
    if bound_footprint.split(":")[-1] != bundle.footprint_name or bound_footprint.count(":") != 1:
        raise ValueError("Sourced symbol's footprint assignment differs from its paired footprint")
    footprint_text = _native_footprint(files[bundle.footprint_file].decode("utf-8"), bundle.footprint_name)
    footprint = _root(footprint_text, "footprint")
    if _atoms(footprint_text, footprint) != ("footprint", bundle.footprint_name):
        raise ValueError("Sourced footprint root differs from its recorded identity")
    if _scalar(footprint_text, footprint, "layer") != "F.Cu":
        raise ValueError("Sourced footprint must use the native front-side coordinate system")
    pads = _pads(footprint_text, footprint)
    numbers: list[str] = []
    for pad in pads:
        if not pad.number:
            if pad.kind != "np_thru_hole":
                raise ValueError("Sourced electrical pad has no number")
            continue
        if pad.kind == "np_thru_hole":
            raise ValueError("Sourced mechanical hole unexpectedly has an electrical pad number")
        numbers.append(pad.number)
    numbered = tuple(sorted(set(numbers)))
    if pins != numbered:
        raise ValueError("Symbol pin numbers differ from the paired footprint pad numbers: "
                         f"symbol={','.join(pins)}; footprint={','.join(numbered)}")
    reference = _model_reference(footprint_text, footprint, bundle.model_file)
    model_text = files[bundle.model_file].decode("utf-8")
    if (not model_text.lstrip().startswith("#VRML V2.0 utf8")
            or re.search(r"\b(?:Shape|IndexedFaceSet)\s*\{", model_text) is None):
        raise ValueError("Paired model must contain native VRML geometry")
    if re.search(r"\b(?:Inline|ImageTexture|MovieTexture|AudioClip|Script|EXTERNPROTO|url)\b", model_text):
        raise ValueError("Paired WRL must be self-contained without scripts or external resources")
    return CadBundleCheck(status="READY", symbol_pins=pins, footprint_pads=numbered,
                          model_references=(reference,), issues=(*bundle.issues, _REVIEW_LIMIT)), files


def inspect_bundle(bundle_dir: Path, bundle: CadSourceBundle) -> CadBundleCheck:
    """Check recorded bytes, exact identity and internal pin correspondence, not fit."""
    try:
        result, _ = _checked(bundle_dir, bundle)
        return result
    except (OSError, ValueError, UnicodeError) as error:
        return CadBundleCheck(status="BLOCKED", issues=(str(error),))


def _build(root: Path, project_id: str, directory: Path,
           bundle: CadSourceBundle, original: bytes,
           ) -> tuple[CadBundleCheck, tuple[_Edit, ...], str, str]:
    check, files = _checked(directory, bundle)
    project = selected_project(root, project_id)
    config = load_config(root, project.config)
    if set(hashes(root, config.source_roots)) != set(config.required_inputs):
        raise ValueError("Declare the current project source inventory before importing CAD")
    manifest_path = repo_path(root, project.config)
    manifest = read_model(manifest_path, ProjectManifest)
    project_dir = repo_path(root, project.project).parent
    if not any(project_dir.is_relative_to(repo_path(manifest_path.parent, name))
               for name in manifest.source_roots):
        raise ValueError("Project CAD libraries must live under a declared local source root")
    fingerprint = _sha(original)[:16]
    nickname = f"CAD_{bundle.supplier_id}_{fingerprint}"
    destination = project_dir / "cad" / "sourced" / f"easyeda-{bundle.supplier_id}" / fingerprint
    symbol_id = nickname + ":" + bundle.symbol_name
    footprint_id = nickname + ":" + bundle.footprint_name
    symbol = files[bundle.symbol_file].decode("utf-8")
    parent, _ = _symbol(symbol, bundle.symbol_name)
    symbol = _replace_property(symbol, parent, "Footprint", footprint_id)
    footprint = _native_footprint(files[bundle.footprint_file].decode("utf-8"), bundle.footprint_name)
    parent = _root(footprint, "footprint")
    model = _nodes(footprint, parent, "model")[0]
    token = _tokens(footprint, model)[1]
    model_target = destination / bundle.model_file
    portable_model = "${KIPRJMOD}/" + model_target.relative_to(project_dir).as_posix()
    footprint = footprint[:token.start] + _quote(portable_model) + footprint[token.end:]
    proposed: dict[str, bytes] = {}
    for name, content in ((bundle.symbol_file, symbol.encode("utf-8")),
                          (bundle.footprint_file, footprint.encode("utf-8")),
                          (bundle.model_file, files[bundle.model_file]),
                          ("SOURCE.json", original),
                          ("NOTICE.txt", (
                              b"Source provenance is recorded in SOURCE.json. Its file hashes describe "
                              b"the original provider bundle. Imported symbol and model paths were "
                              b"rewritten for this project; model transforms were preserved.\n"
                              b"CAD licensing terms, manufacturer pin functions and physical fit are "
                              b"not independently verified by this import. No part approval is granted.\n"
                              b"Only the paired WRL is installed. STEP output from easyeda2kicad 1.0.1 "
                              b"is not substituted because it may omit the model translation.\n"
                          ))):
        target = destination / name
        relative = target.relative_to(root).as_posix()
        repo_path(root, relative)
        proposed[relative] = content
    # Local table edits expose only these explicitly selected assets in KiCad's chooser.
    for name, kind, target in (("sym-lib-table", "sym_lib_table", destination / bundle.symbol_file),
                               ("fp-lib-table", "fp_lib_table", (destination / bundle.footprint_file).parent)):
        path = project_dir / name
        relative = path.relative_to(root).as_posix()
        repo_path(root, relative)
        before = path.read_bytes().decode("utf-8") if path.is_file() else None
        uri = "${KIPRJMOD}/" + target.relative_to(project_dir).as_posix()
        proposed[relative] = _table(before, kind, nickname, uri).encode("utf-8")
    before = manifest_path.read_bytes().decode("utf-8")
    additions: dict[str, set[str]] = {
        "required_inputs": {Path(path).relative_to(manifest_path.parent.relative_to(root)).as_posix()
                            for path in proposed},
        "shared_inputs": set(),
    }
    proposed[project.config] = update_project_manifest_inputs(before, additions).encode("utf-8")
    edits: list[_Edit] = []
    tables = {project_dir / "sym-lib-table", project_dir / "fp-lib-table", manifest_path}
    for name, content in sorted(proposed.items()):
        path = repo_path(root, name)
        previous = path.read_bytes() if path.is_file() else None
        if previous == content:
            continue
        if previous is not None and path not in tables:
            raise ValueError(f"Imported CAD asset conflicts with existing source: {name}")
        if path.exists() and not path.is_file():
            raise ValueError(f"CAD destination is not a regular file: {name}")
        edits.append(_Edit(name, previous, content))
    return check, tuple(edits), symbol_id, footprint_id


def _run(root: Path, project_id: str, bundle_dir: Path | None,
         output: Path, locked: Path | None) -> CadImportReport:
    root = root.resolve()
    output = _receipt(root, output)
    check: CadBundleCheck | None = None
    try:
        before = _snapshot(root, project_id)
        spec: CadImportPlan | None = None
        if locked is not None:
            spec = read_model(local_path(root, locked), CadImportPlan)
            if spec.project_id != project_id:
                raise ValueError("CAD import plan belongs to another project")
            _verify_snapshot(root, project_id, spec.preconditions)
            bundle_dir = Path(spec.bundle_dir)
        if bundle_dir is None:
            raise ValueError("Choose a sourced CAD bundle before previewing import")
        directory = _unlinked_directory(bundle_dir)
        bundle, original = _read_bundle(directory)
        if spec is not None and _sha(original) != spec.bundle_sha256:
            raise ValueError("CAD bundle source metadata changed after preview")
        check, edits, symbol_id, footprint_id = _build(root, project_id, directory, bundle, original)
        _verify_snapshot(root, project_id, before)
        # Bind the manifest bytes used for output, as well as every original file hash.
        current_bundle, current_original = _read_bundle(directory)
        if current_bundle != bundle or current_original != original:
            raise ValueError("CAD bundle source changed during preview")
        _checked(directory, bundle)
        after_hashes = {edit.path: _sha(edit.after) for edit in edits}
        if spec is not None and dict(spec.after_hashes) != after_hashes:
            raise ValueError("CAD import differs from the reviewed plan; preview a fresh bundle")
        plan_record = CadImportPlan(project_id=project_id, bundle_dir=str(directory),
            bundle_sha256=_sha(original), preconditions=before, after_hashes=after_hashes)
        plan_path = output / "cad-import-plan.json"
        plan_path.write_text(plan_record.model_dump_json(indent=2) + "\n", encoding="utf-8")
        diff = _diff(edits)
        (output / "cad-import.diff").write_text(diff, encoding="utf-8")
        if spec is not None:
            _write_edits(root, project_id, AutoCadPlan(project_id=project_id,
                preconditions=dict(spec.preconditions), after_hashes=dict(spec.after_hashes)), edits)
        report = CadImportReport(status="APPLIED" if spec is not None else "PLAN",
            project_id=project_id, symbol_id=symbol_id, footprint_id=footprint_id,
            files=tuple(after_hashes), issues=check.issues, check=check, plan_path=str(plan_path),
            receipt_directory=str(output), diff=diff)
    except (OSError, ValueError, UnicodeError) as error:
        report = CadImportReport(status="BLOCKED", project_id=project_id, check=check,
                                 issues=(str(error),), receipt_directory=str(output))
    (output / "cad-import-report.json").write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return report


def plan(root: Path, project_id: str, bundle_dir: Path, output: Path) -> CadImportReport:
    """Preview one immutable source bundle without editing project files."""
    return _run(root, project_id, bundle_dir, output, None)


def apply(root: Path, project_id: str, plan_path: Path, output: Path) -> CadImportReport:
    """Recheck cached source bytes and apply the reviewed import without network access."""
    return _run(root, project_id, None, output, plan_path)
