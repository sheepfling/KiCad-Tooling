"""Small structural and offline-resource checks for retained binary glTF files."""

from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path

from pydantic import JsonValue

Point3 = tuple[float, float, float]
Triangle3 = tuple[Point3, Point3, Point3]
Matrix4 = tuple[float, ...]
_IDENTITY: Matrix4 = (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
_MAX_GEOMETRY_BYTES = 64 * 1024 * 1024
_MAX_REFERENCED_VERTICES = 1_000_000
_MAX_TRIANGLES = 200_000


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


def _object(value: JsonValue | None, label: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        # This is malformed file content, not a caller passing the wrong API type.
        raise ValueError(f"GLB {label} must be an object")  # noqa: TRY004
    return value


def _list(value: JsonValue | None, label: str) -> list[JsonValue]:
    if not isinstance(value, list):
        # This is malformed file content, not a caller passing the wrong API type.
        raise ValueError(f"GLB {label} must be an array")  # noqa: TRY004
    return value


def _integer(value: JsonValue | None, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"GLB {label} must be a nonnegative integer")
    return value


def _number(value: JsonValue | None, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        # This is malformed file content, not a caller passing the wrong API type.
        raise ValueError(f"GLB {label} must be a finite number")  # noqa: TRY004
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"GLB {label} must be a finite number")
    return result


def _numbers(value: JsonValue | None, size: int, label: str) -> tuple[float, ...]:
    items = _list(value, label)
    if len(items) != size:
        raise ValueError(f"GLB {label} has the wrong vector size")
    return tuple(_number(item, label) for item in items)


def _document_and_binary(path: Path) -> tuple[dict[str, JsonValue], bytes]:
    content = path.read_bytes()
    if len(content) > _MAX_GEOMETRY_BYTES or len(content) < 28:
        raise ValueError("GLB geometry is empty or exceeds the supported size")
    magic, version, declared = struct.unpack_from("<4sII", content)
    if magic != b"glTF" or version != 2 or declared != len(content):
        raise ValueError("GLB geometry has an invalid envelope")
    offset = 12
    chunks: list[tuple[bytes, bytes]] = []
    while offset < len(content):
        if offset + 8 > len(content):
            raise ValueError("GLB geometry has a truncated chunk")
        size, kind = struct.unpack_from("<I4s", content, offset)
        offset += 8
        if size % 4 or offset + size > len(content):
            raise ValueError("GLB geometry has an invalid chunk length")
        chunks.append((kind, content[offset : offset + size]))
        offset += size
    if len(chunks) != 2 or chunks[0][0] != b"JSON" or chunks[1][0] != b"BIN\x00":
        raise ValueError("GLB geometry requires one embedded JSON and BIN chunk")
    try:
        raw: JsonValue = json.loads(chunks[0][1])
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("GLB geometry has invalid JSON") from exc
    document = _object(raw, "document")
    asset = _object(document.get("asset"), "asset")
    if asset.get("version") != "2.0":
        raise ValueError("GLB geometry needs glTF 2.0")
    required = document.get("extensionsRequired", [])
    if _list(required, "required extensions"):
        raise ValueError("GLB geometry uses an unassessed required extension")
    if document.get("skins") or document.get("animations"):
        raise ValueError("Animated or skinned GLB geometry is unassessed")
    buffers = _list(document.get("buffers"), "buffers")
    if len(buffers) != 1:
        raise ValueError("GLB geometry requires one embedded buffer")
    buffer = _object(buffers[0], "buffer")
    if (
        "uri" in buffer
        or "extensions" in buffer
        or _integer(buffer.get("byteLength"), "buffer length") > len(chunks[1][1])
    ):
        raise ValueError("GLB geometry buffer is external or incomplete")
    return document, chunks[1][1]


def _accessor_span(
    document: dict[str, JsonValue],
    binary: bytes,
    index: int,
    *,
    component_type: tuple[int, ...],
    shape: str,
) -> tuple[int, int, int, int]:
    accessors = _list(document.get("accessors"), "accessors")
    if index >= len(accessors):
        raise ValueError("GLB accessor index is out of range")
    accessor = _object(accessors[index], "accessor")
    if "extensions" in accessor or accessor.get("normalized", False) is True:
        raise ValueError("GLB accessor uses an unassessed geometry encoding")
    kind = _integer(accessor.get("componentType"), "accessor component type")
    count = _integer(accessor.get("count"), "accessor count")
    if (
        kind not in component_type
        or accessor.get("type") != shape
        or not count
        or count > _MAX_REFERENCED_VERTICES
        or "sparse" in accessor
    ):
        raise ValueError("GLB accessor geometry is unsupported")
    views = _list(document.get("bufferViews"), "buffer views")
    view_index = _integer(accessor.get("bufferView"), "accessor buffer view")
    if view_index >= len(views):
        raise ValueError("GLB accessor buffer view is out of range")
    view = _object(views[view_index], "buffer view")
    if "extensions" in view:
        raise ValueError("GLB buffer view uses an unassessed geometry encoding")
    if _integer(view.get("buffer"), "buffer index") != 0:
        raise ValueError("GLB accessor uses another buffer")
    component_size = {5121: 1, 5123: 2, 5125: 4, 5126: 4}[kind]
    width = component_size * (3 if shape == "VEC3" else 1)
    stride = _integer(view.get("byteStride", width), "buffer stride")
    view_offset = _integer(view.get("byteOffset", 0), "buffer view offset")
    view_length = _integer(view.get("byteLength"), "buffer view length")
    accessor_offset = _integer(accessor.get("byteOffset", 0), "accessor offset")
    if (
        stride < width
        or stride % component_size
        or accessor_offset + (count - 1) * stride + width > view_length
        or view_offset + view_length > len(binary)
    ):
        raise ValueError("GLB accessor bytes exceed the embedded buffer view")
    return view_offset + accessor_offset, stride, count, kind


def _matrix_product(left: Matrix4, right: Matrix4) -> Matrix4:
    return tuple(
        sum(left[k * 4 + row] * right[column * 4 + k] for k in range(4))
        for column in range(4)
        for row in range(4)
    )


def _node_matrix(node: dict[str, JsonValue]) -> Matrix4:
    if "matrix" in node:
        if any(key in node for key in ("translation", "rotation", "scale")):
            raise ValueError("GLB node mixes matrix and TRS transforms")
        matrix = _numbers(node["matrix"], 16, "node matrix")
    else:
        tx, ty, tz = _numbers(node.get("translation", [0, 0, 0]), 3, "translation")
        x, y, z, w = _numbers(node.get("rotation", [0, 0, 0, 1]), 4, "rotation")
        sx, sy, sz = _numbers(node.get("scale", [1, 1, 1]), 3, "scale")
        if not math.isclose(x * x + y * y + z * z + w * w, 1, abs_tol=1e-6):
            raise ValueError("GLB node rotation is not normalized")
        matrix = (
            (1 - 2 * (y * y + z * z)) * sx,
            2 * (x * y + z * w) * sx,
            2 * (x * z - y * w) * sx,
            0,
            2 * (x * y - z * w) * sy,
            (1 - 2 * (x * x + z * z)) * sy,
            2 * (y * z + x * w) * sy,
            0,
            2 * (x * z + y * w) * sz,
            2 * (y * z - x * w) * sz,
            (1 - 2 * (x * x + y * y)) * sz,
            0,
            tx,
            ty,
            tz,
            1,
        )
    if any(abs(matrix[index]) > 1e-9 for index in (3, 7, 11)) or not math.isclose(
        matrix[15], 1, abs_tol=1e-9
    ):
        raise ValueError("GLB node has a non-affine transform")
    return matrix


def _transform(matrix: Matrix4, point: Point3) -> Point3:
    x, y, z = point
    result = (
        matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12],
        matrix[1] * x + matrix[5] * y + matrix[9] * z + matrix[13],
        matrix[2] * x + matrix[6] * y + matrix[10] * z + matrix[14],
    )
    if not all(math.isfinite(value) for value in result):
        raise ValueError("GLB transformed geometry is not finite")
    return result


def _scene_geometry(
    path: Path, *, include_triangles: bool
) -> tuple[tuple[Point3, ...], tuple[Triangle3, ...]]:
    """Read referenced static triangles from the default scene and its node transforms."""
    document, binary = _document_and_binary(path)
    scenes = _list(document.get("scenes"), "scenes")
    scene_index = _integer(document.get("scene", 0), "default scene")
    if scene_index >= len(scenes):
        raise ValueError("GLB default scene is missing")
    scene = _object(scenes[scene_index], "scene")
    if "extensions" in scene:
        raise ValueError("GLB scene extensions leave geometry unassessed")
    roots = _list(scene.get("nodes"), "scene nodes")
    nodes = _list(document.get("nodes"), "nodes")
    meshes = _list(document.get("meshes"), "meshes")
    points: list[Point3] = []
    triangles: list[Triangle3] = []

    def visit(index: int, parent: Matrix4, ancestry: frozenset[int]) -> None:
        if index >= len(nodes) or index in ancestry:
            raise ValueError("GLB scene has an invalid or cyclic node")
        node = _object(nodes[index], "node")
        if "skin" in node or "extensions" in node:
            raise ValueError("GLB node geometry is unassessed")
        transform = _matrix_product(parent, _node_matrix(node))
        if "mesh" in node:
            mesh_index = _integer(node["mesh"], "mesh index")
            if mesh_index >= len(meshes):
                raise ValueError("GLB mesh index is out of range")
            mesh = _object(meshes[mesh_index], "mesh")
            if "extensions" in mesh:
                raise ValueError("GLB mesh extensions leave geometry unassessed")
            primitives = _list(mesh.get("primitives"), "primitives")
            for raw in primitives:
                primitive = _object(raw, "primitive")
                if (
                    _integer(primitive.get("mode", 4), "primitive mode") != 4
                    or "targets" in primitive
                    or "extensions" in primitive
                ):
                    raise ValueError("GLB mesh primitive is not an unmodified triangle mesh")
                attributes = _object(primitive.get("attributes"), "primitive attributes")
                position_index = _integer(attributes.get("POSITION"), "POSITION index")
                start, stride, count, _ = _accessor_span(
                    document, binary, position_index, component_type=(5126,), shape="VEC3"
                )
                if "indices" in primitive:
                    index_start, index_stride, index_count, kind = _accessor_span(
                        document,
                        binary,
                        _integer(primitive["indices"], "index accessor"),
                        component_type=(5121, 5123, 5125),
                        shape="SCALAR",
                    )
                    if index_count % 3:
                        raise ValueError("GLB triangle index count is incomplete")
                    format_ = {5121: "<B", 5123: "<H", 5125: "<I"}[kind]
                    selected_indices = [
                        struct.unpack_from(format_, binary, index_start + offset * index_stride)[0]
                        for offset in range(index_count)
                    ]
                else:
                    if count % 3:
                        raise ValueError("GLB triangle vertex count is incomplete")
                    selected_indices = list(range(count))
                selected = set(selected_indices)
                if len(points) + len(selected) > _MAX_REFERENCED_VERTICES:
                    raise ValueError("GLB has too many referenced vertices for clearance review")
                transformed: dict[int, Point3] = {}
                for vertex in sorted(selected):
                    if vertex >= count:
                        raise ValueError("GLB triangle index is out of range")
                    raw_point = struct.unpack_from("<fff", binary, start + vertex * stride)
                    point = _transform(transform, raw_point)
                    points.append(point)
                    if include_triangles:
                        transformed[vertex] = point
                if include_triangles:
                    if len(triangles) + len(selected_indices) // 3 > _MAX_TRIANGLES:
                        raise ValueError("GLB has too many triangles for mesh review")
                    triangles.extend(
                        (
                            transformed[selected_indices[index]],
                            transformed[selected_indices[index + 1]],
                            transformed[selected_indices[index + 2]],
                        )
                        for index in range(0, len(selected_indices), 3)
                    )
        for child in _list(node.get("children", []), "node children"):
            visit(_integer(child, "child node"), transform, ancestry | {index})

    for root in roots:
        visit(_integer(root, "root node"), _IDENTITY, frozenset())
    if not points:
        raise ValueError("GLB default scene has no supported triangle geometry")
    return tuple(points), tuple(triangles)


def mesh_vertices(path: Path) -> tuple[Point3, ...]:
    """Read all rendered triangle vertices, ignoring unreferenced accessor entries."""
    return _scene_geometry(path, include_triangles=False)[0]


def mesh_triangles(path: Path) -> tuple[Triangle3, ...]:
    """Read static triangle geometry for bounded surface comparison."""
    return _scene_geometry(path, include_triangles=True)[1]


def mesh_geometry(path: Path) -> tuple[tuple[Point3, ...], tuple[Triangle3, ...]]:
    """Read vertices and triangles together for an assembly clearance receipt."""
    return _scene_geometry(path, include_triangles=True)
