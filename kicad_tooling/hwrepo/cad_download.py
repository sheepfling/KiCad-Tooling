"""Bounded, anonymous downloads of explicitly associated official KiCad CAD assets.

This adapter preserves footprint bytes, including authored model transforms. It
never identifies a manufacturer part or substitutes a similarly named package.
Supplier CAD outside the official library needs a separate provider adapter.
"""
from __future__ import annotations

import csv
import hashlib
import http.client
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlsplit

from .model_inventory import (
    _atoms,  # pyright: ignore[reportPrivateUsage]
    _children,  # pyright: ignore[reportPrivateUsage]
)

_HOST = "gitlab.com"
_BASE = f"https://{_HOST}/kicad/libraries"
_MAX_FOOTPRINT = 1024 * 1024
_MAX_MODEL = 16 * 1024 * 1024
_MAX_LICENSE = 256 * 1024
_MAX_MODELS = 8
_TIMEOUT = 15
_DEADLINE = 45
_HEADER = ("path", "url", "sha256")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_+.,()-]*\Z")
_VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")


@dataclass(frozen=True)
class DownloadedCadAsset:
    """A source URL and digest for one file in a completed download bundle."""

    path: str
    url: str
    sha256: str


def _identity(footprint_id: str, version: str) -> tuple[str, str]:
    if not _VERSION.fullmatch(version):
        raise ValueError("Official CAD downloads require an exact numeric KiCad version")
    fields = footprint_id.split(":")
    if len(fields) != 2 or any(not _NAME.fullmatch(field) for field in fields):
        raise ValueError("Expected an official library:footprint ID without path separators")
    return fields[0], fields[1]


def _url(repository: str, version: str, path: str) -> str:
    return f"{_BASE}/{repository}/-/raw/{version}/{quote(path, safe='/')}"


def _download(url: str, maximum: int) -> bytes:
    """Read one HTTPS response; redirects never forward requests elsewhere."""
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.netloc != _HOST or parsed.query
            or parsed.fragment or not parsed.path.startswith("/kicad/libraries/")):
        raise ValueError("CAD download URL is outside the official KiCad library host")
    connection = http.client.HTTPSConnection(_HOST, timeout=_TIMEOUT)
    started = time.monotonic()
    try:
        connection.request("GET", parsed.path, headers={"User-Agent": "KiCad-Team-Template/1"})
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError(f"Official KiCad CAD download failed: HTTP {response.status}: {url}")
        content_length = response.getheader("Content-Length")
        if content_length is not None and int(content_length) > maximum:
            raise ValueError(f"Official KiCad CAD asset exceeds size limit: {url}")
        result = bytearray()
        while True:
            if time.monotonic() - started > _DEADLINE:
                raise ValueError(f"Official KiCad CAD download exceeded time limit: {url}")
            chunk = response.read1(min(65536, maximum + 1 - len(result)))
            if not chunk:
                break
            result.extend(chunk)
            if len(result) > maximum:
                raise ValueError(f"Official KiCad CAD asset exceeds size limit: {url}")
        if not result:
            raise ValueError(f"Official KiCad CAD asset is empty: {url}")
        return bytes(result)
    except (OSError, http.client.HTTPException) as exc:
        raise ValueError(f"Cannot retrieve official KiCad CAD asset: {url}: {exc}") from exc
    finally:
        connection.close()


def _model_paths(source: bytes, name: str, version: str) -> tuple[str, ...]:
    text = source.decode("utf-8")
    roots = _children(text, 0, len(text))
    if len(roots) != 1 or _atoms(text, roots[0]) != ("footprint", name):
        raise ValueError("Downloaded footprint identity does not match the requested footprint")
    root = roots[0]
    if text[:root.start].strip() or text[root.end:].strip():
        raise ValueError("Unexpected data outside the downloaded footprint")
    prefix = "${KICAD" + version.split(".")[0] + "_3DMODEL_DIR}/"
    paths: list[str] = []
    for child in _children(text, root.start + 1, root.end - 1):
        atoms = _atoms(text, child)
        if not atoms or atoms[0] != "model":
            continue
        if len(atoms) != 2 or not atoms[1].startswith(prefix):
            raise ValueError("Footprint model is not an explicit versioned official KiCad model")
        path = atoms[1][len(prefix):]
        parts = path.split("/")
        if (len(parts) != 2 or not parts[0].endswith(".3dshapes")
                or any(not _NAME.fullmatch(part) for part in parts)
                or PurePosixPath(path).suffix.lower() not in {".step", ".stp", ".wrl"}):
            raise ValueError("Footprint model path is outside the official model library layout")
        if path not in paths:
            paths.append(path)
    if not paths:
        raise ValueError("Official footprint has no assigned 3D model; no model was guessed")
    if len(paths) > _MAX_MODELS:
        raise ValueError("Official footprint exceeds the supported model count")
    return tuple(paths)


def _asset_shape(path: str, value: bytes) -> None:
    suffix = PurePosixPath(path).suffix.lower()
    if suffix in {".step", ".stp"} and not (
        value.lstrip().startswith(b"ISO-10303-21;")
        and b"END-ISO-10303-21;" in value[-100:]
    ):
        raise ValueError(f"Downloaded model is not a STEP file: {path}")
    if suffix == ".wrl" and not value.lstrip().startswith(b"#VRML"):
        raise ValueError(f"Downloaded model is not a VRML file: {path}")
    if path.startswith("licenses/") and b"Creative Commons" not in value:
        raise ValueError(f"Official library license was not returned: {path}")


def _expected(footprint_id: str, version: str, source: bytes) -> dict[str, str]:
    library, name = _identity(footprint_id, version)
    footprint = f"{library}.pretty/{name}.kicad_mod"
    result = {f"footprints/{footprint}": _url("kicad-footprints", version, footprint)}
    for model in _model_paths(source, name, version):
        result[f"3dmodels/{model}"] = _url("kicad-packages3D", version, model)
    for repository in ("kicad-footprints", "kicad-packages3D"):
        result[f"licenses/{repository}/LICENSE.md"] = _url(repository, version, "LICENSE.md")
    return result


def inspect_cached_provenance(footprints_root: Path) -> tuple[DownloadedCadAsset, ...]:
    """Read typed provenance, rejecting corrupt or escaped cached asset paths."""
    bundle = footprints_root.parent.resolve()
    receipt = bundle / "provenance.csv"
    if receipt.is_symlink() or not receipt.is_file() or receipt.stat().st_size > 65536:
        raise ValueError("Official CAD cache has no valid provenance receipt")
    records: list[DownloadedCadAsset] = []
    with receipt.open(encoding="utf-8", newline="") as stream:
        rows = csv.reader(stream)
        if tuple(next(rows, ())) != _HEADER:
            raise ValueError("Official CAD cache has an unsupported provenance header")
        for row in rows:
            if len(row) != 3:
                raise ValueError("Official CAD cache contains malformed provenance")
            path, url, digest = row
            parts = PurePosixPath(path).parts
            if (not parts or path != PurePosixPath(path).as_posix() or ".." in parts
                    or PurePosixPath(path).is_absolute() or "\\" in path
                    or any(part in {"", "."} for part in parts)
                    or not re.fullmatch(r"[0-9a-f]{64}", digest)):
                raise ValueError("Official CAD cache contains unsafe provenance")
            asset = bundle / path
            if (asset.is_symlink() or not asset.resolve().is_relative_to(bundle)
                    or not asset.is_file()):
                raise ValueError("Official CAD cache asset is missing or outside its bundle")
            if hashlib.sha256(asset.read_bytes()).hexdigest() != digest:
                raise ValueError(f"Official CAD cache asset changed: {path}")
            records.append(DownloadedCadAsset(path, url, digest))
    if len({record.path for record in records}) != len(records):
        raise ValueError("Official CAD cache contains duplicate provenance")
    return tuple(records)


def _validate_cache(footprints: Path, footprint_id: str, version: str) -> None:
    library, name = _identity(footprint_id, version)
    if footprints.is_symlink() or footprints.parent.is_symlink():
        raise ValueError("Official CAD cache must not be a symlink")
    records = inspect_cached_provenance(footprints)
    source = footprints / f"{library}.pretty/{name}.kicad_mod"
    expected = _expected(footprint_id, version, source.read_bytes())
    if {item.path: item.url for item in records} != expected:
        raise ValueError("Official CAD cache provenance does not match the requested assets")


def fetch_official_footprint(cache: Path, footprint_id: str, version: str, *,
                             allow_downloads: bool = True) -> Path:
    """Return a complete local footprints root, with sibling models and licenses.

    A failed transfer leaves no usable bundle. Completed bundles are reused only
    after every cached file is checked against its recorded digest. Versions are
    explicit numeric release tags; neither latest nor arbitrary URLs are accepted.
    """
    library, name = _identity(footprint_id, version)
    key = hashlib.sha256(footprint_id.encode("utf-8")).hexdigest()[:24]
    # Check the caller-supplied path before resolve erases a symlink ancestor.
    for ancestor in (cache, *cache.parents):
        if ancestor.is_symlink():
            raise ValueError("Official CAD cache and its ancestors must not be symlinks")
    parent = cache.resolve() / f"kicad-{version}"
    destination = parent / key
    footprints = destination / "footprints"
    if parent.is_symlink():
        raise ValueError("Official CAD cache version directory must not be a symlink")
    if destination.exists() or destination.is_symlink():
        _validate_cache(footprints, footprint_id, version)
        return footprints
    if not allow_downloads:
        raise ValueError("Official CAD is not cached; restart with --allow-downloads to fetch it")
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".cad-download-", dir=parent) as temporary:
        stage = Path(temporary) / "bundle"
        stage.mkdir()
        source_path = f"{library}.pretty/{name}.kicad_mod"
        source = _download(_url("kicad-footprints", version, source_path), _MAX_FOOTPRINT)
        expected = _expected(footprint_id, version, source)
        records: list[DownloadedCadAsset] = []
        for path, url in expected.items():
            maximum = _MAX_LICENSE if path.startswith("licenses/") else _MAX_MODEL
            value = source if path.startswith("footprints/") else _download(url, maximum)
            _asset_shape(path, value)
            target = stage / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(value)
            records.append(DownloadedCadAsset(path, url, hashlib.sha256(value).hexdigest()))
        with (stage / "provenance.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(_HEADER)
            writer.writerows((item.path, item.url, item.sha256) for item in records)
        _validate_cache(stage / "footprints", footprint_id, version)
        try:
            stage.rename(destination)
        except OSError:
            if not destination.is_dir():
                raise
            _validate_cache(footprints, footprint_id, version)
    return footprints
