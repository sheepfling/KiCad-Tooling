"""I/O boundary helpers.

Raw JSON is decoded here only. Callers must immediately validate it into a
Pydantic model from hwrepo.models; dictionaries do not cross this boundary.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import TYPE_CHECKING, TypeVar, cast

from pydantic import BaseModel, TypeAdapter

from .models import KiCadForeignImportSummary

if TYPE_CHECKING:
    from .models import CadProviderIdentity

Model = TypeVar("Model", bound=BaseModel)


@dataclass(frozen=True)
class KiCadErcItem:
    """Small typed projection of one native ERC detail item."""

    description: str | None
    x: int | float | None
    y: int | float | None


@dataclass(frozen=True)
class KiCadErcViolation:
    """Native ERC rule result used by deterministic fixture comparisons."""

    type: str
    severity: str
    description: str | None
    items: tuple[KiCadErcItem, ...]


@dataclass(frozen=True)
class KiCadErcReport:
    """Versioned, narrow projection of a KiCad ERC JSON report."""

    kicad_version: str
    violations: tuple[KiCadErcViolation, ...]


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _invalid_number(value: str) -> None:
    raise ValueError(f"Invalid JSON number: {value}")


def parse_model_text(document: str, model: type[Model]) -> Model:
    """Validate in-memory JSON with the same strict rules as a file boundary."""
    # Fail duplicate keys and non-finite numbers before Pydantic's decoder applies
    # strict scalar validation while retaining JSON array/enum semantics.
    json.loads(document, object_pairs_hook=_unique_object, parse_constant=_invalid_number)
    return model.model_validate_json(document, strict=True)


def validate_json_object(document: str) -> None:
    """Check JSON object shape without returning untyped native-settings data."""
    decoded: object = json.loads(
        document,
        object_pairs_hook=_unique_object,
        parse_constant=_invalid_number,
    )
    if not isinstance(decoded, dict):
        raise TypeError("JSON document must be an object")


def parse_model(document: str, model: type[Model]) -> Model:
    """Parse one strict serialized contract using the shared JSON boundary."""
    return parse_model_text(document, model)


def read_model(path: Path, model: type[Model]) -> Model:
    """Decode one JSON file and validate it before it reaches application code."""
    document = path.read_text(encoding="utf-8")
    try:
        return parse_model_text(document, model)
    except ValueError as exc:
        raise ValueError(f"{path}: {exc}") from exc


def _read_external_json(path: Path) -> object:
    """Decode unowned KiCad JSON only at this I/O boundary."""
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_invalid_number,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(f"{path}: invalid KiCad JSON: {exc}") from exc


def read_kicad_erc_report(path: Path) -> KiCadErcReport:
    """Decode native ERC JSON into the exact fields used by fixture checks."""
    document = _read_external_json(path)
    if not isinstance(document, dict):
        raise ValueError(f"{path}: expected an ERC report object")  # noqa: TRY004 - input boundary
    report = cast(dict[str, object], document)
    version = report.get("kicad_version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError(f"{path}: ERC report has no KiCad version")
    sheets = report.get("sheets")
    if not isinstance(sheets, list):
        raise ValueError(f"{path}: ERC report sheets must be a list")  # noqa: TRY004 - input boundary

    violations: list[KiCadErcViolation] = []
    for sheet_index, raw_sheet in enumerate(cast(list[object], sheets)):
        if not isinstance(raw_sheet, dict):
            raise ValueError(f"{path}: ERC sheet {sheet_index} must be an object")  # noqa: TRY004 - input boundary
        raw_violations = cast(dict[str, object], raw_sheet).get("violations", [])
        if not isinstance(raw_violations, list):
            raise ValueError(f"{path}: ERC sheet {sheet_index} violations must be a list")  # noqa: TRY004 - input boundary
        for violation_index, raw_violation in enumerate(cast(list[object], raw_violations)):
            if not isinstance(raw_violation, dict):
                raise ValueError(  # noqa: TRY004 - input boundary
                    f"{path}: ERC sheet {sheet_index} violation {violation_index} must be an object"
                )
            values = cast(dict[str, object], raw_violation)
            violation_type = values.get("type")
            severity = values.get("severity")
            if not isinstance(violation_type, str) or not violation_type.strip():
                raise ValueError(
                    f"{path}: ERC sheet {sheet_index} violation {violation_index} has no type"
                )
            if not isinstance(severity, str) or not severity.strip():
                raise ValueError(
                    f"{path}: ERC sheet {sheet_index} violation {violation_index} has no severity"
                )
            description = values.get("description")
            if description is not None and not isinstance(description, str):
                raise ValueError(
                    f"{path}: ERC sheet {sheet_index} violation {violation_index} has an invalid description"
                )
            raw_items = values.get("items", [])
            if not isinstance(raw_items, list):
                raise ValueError(  # noqa: TRY004 - input boundary
                    f"{path}: ERC sheet {sheet_index} violation {violation_index} items must be a list"
                )
            items: list[KiCadErcItem] = []
            for item_index, raw_item in enumerate(cast(list[object], raw_items)):
                if not isinstance(raw_item, dict):
                    raise ValueError(  # noqa: TRY004 - input boundary
                        f"{path}: ERC sheet {sheet_index} violation {violation_index} item {item_index} must be an object"
                    )
                item = cast(dict[str, object], raw_item)
                item_description = item.get("description")
                if item_description is not None and not isinstance(item_description, str):
                    raise ValueError(
                        f"{path}: ERC sheet {sheet_index} violation {violation_index} item {item_index} has an invalid description"
                    )
                raw_position = item.get("pos", {})
                if not isinstance(raw_position, dict):
                    raise ValueError(  # noqa: TRY004 - input boundary
                        f"{path}: ERC sheet {sheet_index} violation {violation_index} item {item_index} position must be an object"
                    )
                position = cast(dict[str, object], raw_position)
                coordinates: list[int | float | None] = []
                for axis in ("x", "y"):
                    coordinate = position.get(axis)
                    if coordinate is not None and (
                        isinstance(coordinate, bool) or not isinstance(coordinate, (int, float))
                    ):
                        raise ValueError(
                            f"{path}: ERC sheet {sheet_index} violation {violation_index} item {item_index} has an invalid {axis} coordinate"
                        )
                    coordinates.append(coordinate)
                items.append(
                    KiCadErcItem(
                        description=item_description,
                        x=coordinates[0],
                        y=coordinates[1],
                    )
                )
            violations.append(
                KiCadErcViolation(
                    type=violation_type,
                    severity=severity,
                    description=description,
                    items=tuple(items),
                )
            )
    return KiCadErcReport(kicad_version=version, violations=tuple(violations))


def kicad_variant_names(path: Path) -> tuple[str, ...]:
    """Extract only authored variant names from a KiCad project file."""
    document = _read_external_json(path)
    if not isinstance(document, dict):
        raise ValueError(f"{path}: project file is not a JSON object")  # noqa: TRY004 - input boundary
    schematic = cast(dict[str, object], document).get("schematic")
    if not isinstance(schematic, dict):
        raise ValueError(f"{path}: schematic settings are missing")  # noqa: TRY004 - input boundary
    variants = cast(dict[str, object], schematic).get("variants")
    if not isinstance(variants, list):
        raise ValueError(f"{path}: schematic.variants is not a list")  # noqa: TRY004 - input boundary
    names: list[str] = []
    for item in cast(list[object], variants):
        value: object = (
            item
            if isinstance(item, str)
            else (cast(dict[str, object], item).get("name") if isinstance(item, dict) else None)
        )
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{path}: schematic.variants contains a nameless entry")
        names.append(value)
    if len({name.casefold() for name in names}) != len(names):
        raise ValueError(f"{path}: schematic.variants has duplicate names")
    return tuple(names)


def require_kicad_json_object(path: Path) -> None:
    if not isinstance(_read_external_json(path), dict):
        raise ValueError(f"{path}: expected a JSON object")  # noqa: TRY004 - input boundary


def read_kicad_import_summary(path: Path) -> KiCadForeignImportSummary:
    """Keep KiCad's full report on disk; pass only actionable fields to services."""
    document = _read_external_json(path)
    if not isinstance(document, dict):
        raise ValueError(f"{path}: expected an import report object")  # noqa: TRY004 - input boundary
    values = cast(dict[str, object], document)
    source_format = values.get("source_format")
    layer_mapping = values.get("layer_mapping")
    errors = values.get("errors")
    warnings = values.get("warnings")
    if (
        not isinstance(source_format, str)
        or not source_format.strip()
        or not isinstance(layer_mapping, dict)
        or not isinstance(errors, list)
        or not isinstance(warnings, list)
    ):
        raise ValueError(f"{path}: import report lacks format, layer map, errors or warnings")

    def messages(items: list[object]) -> tuple[str, ...]:
        return tuple(
            item if isinstance(item, str) else json.dumps(item, sort_keys=True) for item in items
        )

    return KiCadForeignImportSummary(
        source_format=source_format,
        mapped_layers=len(cast(dict[str, object], layer_mapping)),
        errors=messages(cast(list[object], errors)),
        warnings=messages(cast(list[object], warnings)),
    )


def write_model(path: Path, model: BaseModel) -> None:
    """Serialize a validated model with deterministic UTF-8 JSON formatting."""
    path.write_text(
        model.model_dump_json(by_alias=True, indent=2, exclude_none=True) + "\n",
        encoding="utf-8",
    )


def update_project_manifest_inputs(document: str, additions: dict[str, set[str]]) -> str:
    """Add reviewed source inputs while preserving a manifest's other JSON fields."""
    from .models import ProjectManifest

    raw = json.loads(
        document,
        object_pairs_hook=_unique_object,
        parse_constant=_invalid_number,
    )
    manifest = ProjectManifest.model_validate_json(document, strict=True)
    for field in ("required_inputs", "shared_inputs"):
        added = additions[field]
        if added:
            raw[field] = sorted(set(getattr(manifest, field)) | added)
    updated = json.dumps(raw, indent=2, ensure_ascii=False) + "\n"
    ProjectManifest.model_validate_json(updated, strict=True)
    return updated


def repo_path(root: Path, value: str) -> Path:
    """Require a portable, exact-case path that stays inside root."""
    if not value or "\\" in value or ":" in value:
        raise ValueError(f"Nonportable repository path: {value!r}")
    posix = PurePosixPath(value)
    if (
        posix.is_absolute()
        or PureWindowsPath(value).drive
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ValueError(f"Unsafe repository path: {value!r}")
    root = root.resolve()
    current = root
    reserved = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
    for component in posix.parts:
        if (
            component.endswith((".", " "))
            or component.split(".")[0].upper() in reserved
            or any(character in '<>"|?*' or ord(character) < 32 for character in component)
        ):
            raise ValueError(f"Nonportable repository path: {value!r}")
        if current.is_dir():
            names = {entry.name for entry in current.iterdir()}
            if component not in names and component.casefold() in {
                name.casefold() for name in names
            }:
                raise ValueError(f"Path case mismatch: {value!r}")
        current = current / component
        if current.is_symlink() or (current.exists() and current.resolve() != current.absolute()):
            raise ValueError(f"Linked repository path: {value!r}")
    if root not in current.resolve().parents:
        raise ValueError(f"Escaping repository path: {value!r}")
    return current


def update_project_manifest_parts(
    document: str,
    part_ids: tuple[str, ...],
    additions: dict[str, set[str]],
    remove_part_ids: tuple[str, ...] = (),
) -> str:
    """Update reviewed identities and model inputs, retaining other authored JSON fields."""
    from .models import ProjectManifest

    raw = json.loads(document, object_pairs_hook=_unique_object, parse_constant=_invalid_number)
    manifest = ProjectManifest.model_validate_json(document, strict=True)
    raw["component_identity"]["part_ids"] = sorted(
        (set(manifest.component_identity.part_ids) - set(remove_part_ids)) | set(part_ids)
    )
    for field in ("required_inputs", "shared_inputs"):
        if additions[field]:
            raw[field] = sorted(set(getattr(manifest, field)) | additions[field])
    updated = json.dumps(raw, indent=2, ensure_ascii=False) + "\n"
    ProjectManifest.model_validate_json(updated, strict=True)
    return updated


def parse_easyeda_identity(document: str) -> CadProviderIdentity:
    """Project vendor JSON into the exact fields used by the offline CAD adapter."""
    from .models import CadProviderIdentity

    raw = json.loads(document, object_pairs_hook=_unique_object, parse_constant=_invalid_number)
    try:
        if raw["success"] is not True:
            raise ValueError("The CAD provider did not return a successful component lookup")
        result = raw["result"]
        parameters = result["dataStr"]["head"]["c_para"]
        shapes = TypeAdapter(list[str]).validate_python(
            result["packageDetail"]["dataStr"]["shape"],
            strict=True,
        )
        models = [
            shape.removeprefix("SVGNODE~") for shape in shapes if shape.startswith("SVGNODE~")
        ]
        if len(models) != 1:
            raise ValueError("The provider footprint must have exactly one paired 3D model")
        node = json.loads(
            models[0], object_pairs_hook=_unique_object, parse_constant=_invalid_number
        )
        if not isinstance(node["attrs"], dict):
            raise TypeError("The provider model attributes have an unsupported format")
        return CadProviderIdentity.model_validate(
            {
                "supplier_id": result["lcsc"]["number"],
                "component_supplier_id": parameters["Supplier Part"],
                "manufacturer": parameters["Manufacturer"],
                "mpn": parameters["Manufacturer Part"],
                "package": parameters["package"],
                "symbol_name": parameters["name"],
                "model_uuid": node["attrs"]["uuid"],
                "model_title": node["attrs"].get("title", ""),
            },
            strict=True,
        )
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError(
            "The CAD provider returned incomplete or unsupported component metadata"
        ) from error
