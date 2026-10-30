"""Small structural and offline-resource checks for retained binary glTF files."""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from pathlib import Path

from pydantic import JsonValue


@dataclass(frozen=True, slots=True)
class GlbInfo:
    offline: bool
    has_position_primitive: bool


def inspect_glb(path: Path) -> GlbInfo | None:
    """Read the GLB envelope and JSON chunk without loading geometry into memory."""
    size = path.stat().st_size
    if size < 20:
        return None
    with path.open("rb") as stream:
        header = stream.read(12)
        magic, version, declared_size = struct.unpack("<4sII", header)
        if magic != b"glTF" or version != 2 or declared_size != size:
            return None
        chunk_size, chunk_kind = struct.unpack("<I4s", stream.read(8))
        if chunk_kind != b"JSON" or chunk_size < 2 or chunk_size > 32 * 1024 * 1024:
            return None
        if chunk_size % 4 or 20 + chunk_size > size:
            return None
        try:
            raw_document: JsonValue = json.loads(stream.read(chunk_size))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(raw_document, dict):
            return None
        document: dict[str, JsonValue] = raw_document
        asset = document.get("asset")
        if not isinstance(asset, dict) or asset.get("version") != "2.0":
            return None
        position = 20 + chunk_size
        while position < size:
            if size - position < 8:
                return None
            length, kind = struct.unpack("<I4s", stream.read(8))
            position += 8 + length
            if length % 4 or position > size or kind != b"BIN\x00":
                return None
            stream.seek(length, 1)
        if position != size:
            return None
    offline = True
    for category in ("buffers", "images"):
        entries = document.get(category, [])
        if not isinstance(entries, list):
            return None
        for entry in entries:
            if not isinstance(entry, dict):
                return None
            uri = entry.get("uri")
            if uri is not None and (not isinstance(uri, str) or not uri.startswith("data:")):
                offline = False
    meshes = document.get("meshes")
    has_position_primitive = False
    if isinstance(meshes, list):
        for mesh in meshes:
            if not isinstance(mesh, dict):
                continue
            primitives = mesh.get("primitives")
            if not isinstance(primitives, list):
                continue
            for primitive in primitives:
                if not isinstance(primitive, dict):
                    continue
                attributes = primitive.get("attributes")
                if isinstance(attributes, dict) and isinstance(attributes.get("POSITION"), int):
                    has_position_primitive = True
    return GlbInfo(offline=offline, has_position_primitive=has_position_primitive)
