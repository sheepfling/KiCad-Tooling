"""Fetch frozen EasyEDA CAD and run a pinned converter with networking disabled.

The provider is a community endpoint, not a manufacturer approval. Cached bundles
are immutable and checked on every use. STEP evidence stays outside the imported
library because this converter does not apply its WRL offsets to STEP geometry.
"""
from __future__ import annotations

import hashlib
import http.client
import importlib.metadata
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from .contracts import parse_easyeda_identity, read_model, repo_path, write_model
from .model_inventory import (
    _atoms,  # pyright: ignore[reportPrivateUsage]
    _children,  # pyright: ignore[reportPrivateUsage]
)
from .models import CadProviderIdentity, CadSourceBundle, CadSourceFile, CadSourceReport

VERSION = "1.0.1"
_ID = re.compile(r"C[1-9][0-9]{0,11}\Z")
_UUID = re.compile(r"[0-9a-f]{32}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_API = "https://easyeda.com/api/products/{supplier_id}/components"
_OBJ = "https://modules.easyeda.com/3dmodel/{uuid}"
_STEP = "https://modules.easyeda.com/qAxj6KHrDKw4blvCG8QJPs7Y/{uuid}"
_TIMEOUT = 15
_DEADLINE = 45
_MAX_JSON = 4 * 1024 * 1024
_MAX_ASSET = 32 * 1024 * 1024
_MAX_OUTPUT = 64 * 1024 * 1024
_ISSUES = (
    "Community-converted CAD needs a datasheet and 3D alignment review before use.",
    "STEP mechanical export is not qualified: converter 1.0.1 does not apply WRL offsets to STEP.",
    "CAD asset licensing is not established by the converter's software license.",
)
# The pinned converter reads these cache files before attempting urllib requests.
# Block its only network entry point even if a cache entry is unexpectedly absent.
_OFFLINE_WORKER = """import runpy, sys, urllib.request
def offline(*args, **kwargs):
    raise RuntimeError('CAD converter network is disabled; frozen source is incomplete')
urllib.request.urlopen = offline
sys.argv = ['easyeda2kicad', *sys.argv[1:]]
runpy.run_module('easyeda2kicad', run_name='__main__')
"""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _download(url: str, maximum: int) -> bytes:
    parsed = urlsplit(url)
    allowed = (
        parsed.netloc == "easyeda.com"
        and re.fullmatch(r"/api/products/C[1-9][0-9]{0,11}/components", parsed.path)
    ) or (
        parsed.netloc == "modules.easyeda.com"
        and re.fullmatch(r"/(?:3dmodel|qAxj6KHrDKw4blvCG8QJPs7Y)/[0-9a-f]{32}", parsed.path)
    )
    if parsed.scheme != "https" or parsed.query or parsed.fragment or not allowed:
        raise ValueError("CAD source URL is outside the supported provider endpoints")
    connection = http.client.HTTPSConnection(parsed.netloc, timeout=_TIMEOUT)
    start = time.monotonic()
    try:
        connection.request("GET", parsed.path, headers={
            "User-Agent": "KiCad-Team-Template/1", "Accept-Encoding": "identity",
        })
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError(f"CAD provider returned HTTP {response.status}; retry later or use another source")
        encoding = response.getheader("Content-Encoding")
        if encoding and encoding.lower() != "identity":
            raise ValueError("CAD provider returned an unsupported content encoding")
        length = response.getheader("Content-Length")
        if length is not None and int(length) > maximum:
            raise ValueError("CAD provider response exceeds the size limit")
        data = bytearray()
        while True:
            if time.monotonic() - start > _DEADLINE:
                raise ValueError("CAD provider exceeded the download time limit")
            chunk = response.read1(min(65536, maximum + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > maximum:
                raise ValueError("CAD provider response exceeds the size limit")
        if not data:
            raise ValueError("CAD provider returned an empty response")
        return bytes(data)
    except (OSError, http.client.HTTPException) as error:
        raise ValueError(f"CAD provider is unavailable: {error}") from error
    finally:
        connection.close()


def _converter_digest() -> str:
    try:
        distribution = importlib.metadata.distribution("easyeda2kicad")
    except importlib.metadata.PackageNotFoundError as error:
        raise ValueError(
            "Install the CAD provider once with: python -m pip install -e '.[cad]'"
        ) from error
    if distribution.version != VERSION:
        raise ValueError(f"CAD sourcing requires easyeda2kicad=={VERSION}; install the pinned cad extra")
    sources = sorted(item for item in distribution.files or ()
                     if str(item).startswith("easyeda2kicad/") and str(item).endswith(".py"))
    if not sources:
        raise ValueError("The CAD converter installation has no recorded Python source files")
    digest = hashlib.sha256()
    for source in sources:
        digest.update(str(source).encode("utf-8") + b"\0")
        digest.update(Path(str(distribution.locate_file(source))).read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _run_converter(bundle: Path, supplier_id: str, logs: Path) -> None:
    arguments = [sys.executable, "-I", "-B", "-c", _OFFLINE_WORKER,
                 "--full", "--lcsc_id", supplier_id, "--output",
                 str(bundle / "library/part"), "--project-relative", "--use-cache"]
    with (logs.joinpath("converter.stdout").open("wb") as stdout,
          logs.joinpath("converter.stderr").open("wb") as stderr):
        try:
            result = subprocess.run(arguments, cwd=bundle, stdin=subprocess.DEVNULL,
                                    stdout=stdout, stderr=stderr, timeout=90, check=False)
        except subprocess.TimeoutExpired as error:
            raise ValueError("The CAD converter exceeded its time limit") from error
    if result.returncode:
        raise ValueError("The CAD converter failed; inspect converter.stderr in the source receipt")


def _safe_identity(identity: CadProviderIdentity, supplier_id: str, base: Path) -> None:
    if identity.supplier_id != supplier_id or identity.component_supplier_id != supplier_id:
        raise ValueError("CAD provider returned a different supplier part identity")
    if not _UUID.fullmatch(identity.model_uuid):
        raise ValueError("CAD provider has no supported paired 3D model UUID")
    for name in (identity.package, identity.model_title):
        if not name or "/" in name or "\\" in name:
            raise ValueError("CAD provider returned an unsafe CAD asset name")
        repo_path(base, f"library/{name}")


def _symbol_identity(path: Path, identity: CadProviderIdentity) -> None:
    text = path.read_text(encoding="utf-8")
    roots = _children(text, 0, len(text))
    if len(roots) != 1 or _atoms(text, roots[0]) != ("kicad_symbol_lib",):
        raise ValueError("Converted symbol library is malformed")
    symbols = [node for node in _children(text, roots[0].start + 1, roots[0].end - 1)
               if _atoms(text, node)[:1] == ("symbol",)]
    if len(symbols) != 1 or _atoms(text, symbols[0]) != ("symbol", identity.symbol_name):
        raise ValueError("Converted symbol does not match the frozen provider identity")
    properties: dict[str, str] = {}
    for child in _children(text, symbols[0].start + 1, symbols[0].end - 1):
        atoms = _atoms(text, child)
        if atoms[:1] == ("property",) and len(atoms) >= 3:
            if atoms[1] in properties:
                raise ValueError("Converted symbol repeats an identity property")
            properties[atoms[1]] = atoms[2]
    expected = {"Manufacturer": identity.manufacturer, "MPN": identity.mpn,
                "LCSC Part": identity.supplier_id, "Footprint": f"part:{identity.package}"}
    if any(properties.get(name) != value for name, value in expected.items()):
        raise ValueError("Converted symbol fields do not match the frozen provider identity")


def _files(bundle: Path, identity: CadProviderIdentity) -> tuple[CadSourceFile, ...]:
    expected = (
        "library/part.kicad_sym",
        f"library/part.pretty/{identity.package}.kicad_mod",
        f"library/part.3dshapes/{identity.model_title}.wrl",
    )
    step = repo_path(bundle, f"library/part.3dshapes/{identity.model_title}.step")
    if step.is_file():
        step.unlink()  # Raw STEP remains in source evidence, never beside installed WRL.
    paths = [path for path in bundle.rglob("*") if path.is_file() or path.is_symlink()]
    if {path.relative_to(bundle).as_posix() for path in paths} != set(expected):
        raise ValueError("Converted CAD bundle is missing assets or contains unexpected files")
    records: list[CadSourceFile] = []
    for name in expected:
        path = repo_path(bundle, name)
        if not path.is_file() or path.stat().st_size > _MAX_OUTPUT:
            raise ValueError("Converted CAD asset is missing or exceeds the size limit")
        data = path.read_bytes()
        if not data:
            raise ValueError("Converted CAD asset is empty")
        if path.suffix == ".wrl" and (not data.startswith(b"#VRML V2.0 utf8")
                                     or b"IndexedFaceSet" not in data):
            raise ValueError("Converted 3D model contains no supported geometry")
        records.append(CadSourceFile(
            path=name, sha256=_sha(data), source_url=(
                _OBJ.format(uuid=identity.model_uuid) if path.suffix == ".wrl"
                else _API.format(supplier_id=identity.supplier_id)),
        ))
    _symbol_identity(repo_path(bundle, expected[0]), identity)
    return tuple(records)


def _bounded_file(path: Path, maximum: int) -> bytes:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError(f"CAD source cache file is missing, linked or exceeds the size limit: {path.name}")
    return path.read_bytes()


def _cached(destination: Path, supplier_id: str, expected_mpn: str | None) -> CadSourceBundle:
    if destination.is_symlink():
        raise ValueError("CAD source cache cannot be a link")
    bundle_dir = repo_path(destination, "bundle")
    metadata = repo_path(bundle_dir, "bundle.json")
    _bounded_file(metadata, 128 * 1024)
    bundle = read_model(metadata, CadSourceBundle)
    if len(bundle.files) != 3 or len({item.path for item in bundle.files}) != 3:
        raise ValueError("CAD source cache has an unexpected file count")
    actual = {p.relative_to(bundle_dir).as_posix() for p in bundle_dir.rglob("*")
              if p.is_file() or p.is_symlink()}
    if actual != {item.path for item in bundle.files} | {"bundle.json"}:
        raise ValueError("CAD source cache inventory changed")
    if bundle.supplier_id != supplier_id or bundle.converter_version != VERSION:
        raise ValueError("CAD source cache identity is inconsistent")
    if expected_mpn is not None and bundle.mpn != expected_mpn:
        raise ValueError("CAD source MPN does not match the requested manufacturer part number")
    for item in bundle.files:
        path = repo_path(destination / "bundle", item.path)
        if _sha(_bounded_file(path, _MAX_OUTPUT)) != item.sha256:
            raise ValueError(f"CAD source cache changed: {item.path}; no automatic overwrite was made")
    raw = repo_path(destination, f"source/{supplier_id}.json")
    raw_bytes = _bounded_file(raw, _MAX_JSON)
    if _sha(raw_bytes) != bundle.source_sha256:
        raise ValueError("The frozen CAD provider response changed")
    identity = parse_easyeda_identity(raw_bytes.decode("utf-8"))
    _safe_identity(identity, supplier_id, destination / "bundle")
    if (identity.manufacturer, identity.mpn, identity.package) != (
            bundle.manufacturer, bundle.mpn, bundle.package):
        raise ValueError("CAD source cache differs from its frozen provider response")
    obj = _bounded_file(repo_path(destination, f"source/{identity.model_uuid}.obj"), _MAX_ASSET)
    step = _bounded_file(repo_path(destination, f"source/{identity.model_uuid}.step"), _MAX_ASSET)
    key = _sha(raw_bytes + b"\0" + obj + b"\0" + step
               + (bundle.converter_sha256 or "").encode("ascii"))
    if destination.name != key:
        raise ValueError("The frozen CAD source snapshot changed")
    return bundle


def _build(parent: Path, supplier_id: str, expected_mpn: str | None, receipt: Path) -> tuple[Path, CadSourceBundle]:
    converter_digest = _converter_digest()
    source_url = _API.format(supplier_id=supplier_id)
    raw = _download(source_url, _MAX_JSON)
    identity = parse_easyeda_identity(raw.decode("utf-8"))
    _safe_identity(identity, supplier_id, parent)
    if expected_mpn is not None and identity.mpn != expected_mpn:
        raise ValueError("CAD source MPN does not match the requested manufacturer part number")
    obj = _download(_OBJ.format(uuid=identity.model_uuid), _MAX_ASSET)
    if b"\nv " not in obj or b"\nf " not in obj:
        raise ValueError("CAD provider returned no usable 3D mesh geometry")
    issues = _ISSUES
    try:
        step = _download(_STEP.format(uuid=identity.model_uuid), _MAX_ASSET)
        if not step.lstrip().startswith(b"ISO-10303-21;"):
            raise ValueError("CAD provider returned an invalid STEP source")
    except ValueError as error:
        # Empty STEP cache bytes are an intentional recorded absence. The pinned
        # converter treats them as a cache hit, so it cannot refetch during conversion.
        step = b""
        issues += (f"Optional STEP source was not captured: {error}",)
    key = _sha(raw + b"\0" + obj + b"\0" + step + converter_digest.encode("ascii"))
    destination = parent / key
    if destination.exists():
        return destination, _cached(destination, supplier_id, expected_mpn)
    with tempfile.TemporaryDirectory(prefix=".cad-source-", dir=parent) as temporary:
        stage = Path(temporary) / "snapshot"
        bundle_dir = stage / "bundle"
        (bundle_dir / "library").mkdir(parents=True)
        frozen = bundle_dir / ".easyeda_cache"
        frozen.mkdir()
        (frozen / f"{supplier_id}.json").write_bytes(raw)
        (frozen / f"{identity.model_uuid}.obj").write_bytes(obj)
        (frozen / f"{identity.model_uuid}.step").write_bytes(step)
        _run_converter(bundle_dir, supplier_id, receipt)
        frozen.rename(stage / "source")
        files = _files(bundle_dir, identity)
        bundle = CadSourceBundle(
            supplier_id=supplier_id, manufacturer=identity.manufacturer, mpn=identity.mpn,
            package=identity.package, symbol_file="library/part.kicad_sym",
            symbol_name=identity.symbol_name,
            footprint_file=f"library/part.pretty/{identity.package}.kicad_mod",
            footprint_name=identity.package,
            model_file=f"library/part.3dshapes/{identity.model_title}.wrl",
            files=files, source_url=source_url, source_sha256=_sha(raw),
            retrieved_at=datetime.now(UTC).isoformat(),
            converter_sha256=converter_digest, issues=issues,
        )
        write_model(bundle_dir / "bundle.json", bundle)
        stage.rename(destination)
    return destination, bundle


def fetch(root: Path, supplier_id: str, output: Path, *, expected_mpn: str | None = None,
          refresh: bool = False, allow_downloads: bool = True) -> CadSourceReport:
    """Freeze one exact supplier part; never place it or approve an electrical design."""
    root = root.resolve()
    output = output if output.is_absolute() else root / output
    output = repo_path(root, output.relative_to(root).as_posix())
    if not output.is_relative_to(root / "build") or output == root / "build":
        raise ValueError("CAD source receipts must be below ignored build/")
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("CAD sourcing requires a new empty receipt directory")
    try:
        if not _ID.fullmatch(supplier_id):
            raise ValueError("Enter an exact LCSC ID such as C2040")
        parent = repo_path(root, f"build/cad-source-cache/easyeda-{VERSION}/{supplier_id}")
        parent.mkdir(parents=True, exist_ok=True)
        pointer = repo_path(parent, "current.txt")
        cache_hit = pointer.is_file() and not refresh
        if cache_hit:
            key = _bounded_file(pointer, 128).decode("ascii").strip()
            if not _DIGEST.fullmatch(key):
                raise ValueError("CAD source cache index is invalid")
            destination = repo_path(parent, key)
            bundle = _cached(destination, supplier_id, expected_mpn)
        else:
            if not allow_downloads:
                raise ValueError("CAD source is not cached; reconnect MCP with --allow-downloads to fetch it")
            destination, bundle = _build(parent, supplier_id, expected_mpn, output)
            with tempfile.NamedTemporaryFile(mode="w", encoding="ascii",
                                             prefix=".current-", dir=parent, delete=False) as stream:
                stream.write(destination.name + "\n")
                temporary = Path(stream.name)
            os.replace(temporary, pointer)
        report = CadSourceReport(
            status="READY", supplier_id=supplier_id,
            bundle_directory=str(destination / "bundle"), bundle=bundle,
            cache_hit=cache_hit, issues=bundle.issues, receipt_directory=str(output),
        )
    except (OSError, ValueError, UnicodeError, subprocess.SubprocessError) as error:
        report = CadSourceReport(status="BLOCKED", supplier_id=supplier_id,
                                 issues=(str(error),), receipt_directory=str(output))
    write_model(output / "cad-source.json", report)
    return report
