"""CI helper for the digest-pinned schematic-geometry native regression."""

from __future__ import annotations

import json
import os
import sys
import uuid
from collections.abc import Callable
from pathlib import Path
from subprocess import CompletedProcess
from typing import TypedDict


class NativeGeometryReceipt(TypedDict):
    kicad_version: str
    container: str
    image: str
    platform: str
    network: str
    root_filesystem: str
    writable_mount: str
    test_files: list[str]
    test_scope: str


KICAD_GEOMETRY_IMAGES = (
    (
        "10.0.5",
        "ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
    ),
    (
        "10.0.6",
        "kicad/kicad:10.0.6@sha256:18693567392b80da435f9fa952ce3a3e534c66eb5a6033f5b9c80aa3b19dd3ec",
    ),
)


def run(root: Path, output: Path, stage: Callable[..., CompletedProcess[str]]) -> None:
    """Run the schematic-geometry suite against every explicitly supported KiCad image."""
    if sys.platform == "win32":
        raise ValueError("The native KiCad geometry lane requires a Unix Docker runner")
    root = root.resolve()
    package_root = Path(__file__).resolve().parents[2]
    if package_root != root:
        raise ValueError(f"Native geometry lane root differs from its installed checkout: {root}")

    fixture_area = root / "build/ci/native-schematic-geometry"
    fixture_area.mkdir(parents=True, exist_ok=True)
    temporary_base = fixture_area / "tmp"
    temporary_base.mkdir(parents=True, exist_ok=True)
    receipts: list[NativeGeometryReceipt] = []
    test_files = tuple(sorted(root.glob("tests/test_schematic_geometry_*.py")))
    if not test_files:
        raise FileNotFoundError("No focused schematic-geometry pytest suites were found")
    test_paths = tuple(path.relative_to(root).as_posix() for path in test_files)

    for version, image in KICAD_GEOMETRY_IMAGES:
        version_slug = version.replace(".", "-")
        temporary_root = temporary_base / version
        temporary_root.mkdir(parents=True, exist_ok=True)
        container = f"kicad-geometry-{version_slug}-{uuid.uuid4().hex[:8]}"
        uid_gid = f"{os.getuid()}:{os.getgid()}"
        container_command = (
            "docker",
            "run",
            "--detach",
            "--rm",
            "--platform",
            "linux/amd64",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=128m",
            "--user",
            uid_gid,
            "--name",
            container,
            "-e",
            f"HOME=/tmp/kicad-geometry-{version_slug}",
            "-v",
            f"{temporary_root.resolve()}:/fixtures:rw",
            "-w",
            "/fixtures",
            "--entrypoint",
            "/bin/sh",
            image,
            "-ec",
            'mkdir -p "$HOME"; exec sleep 3600',
        )
        stage(
            f"native-geometry-image-pull-{version_slug}",
            ("docker", "pull", "--platform", "linux/amd64", image),
            output,
            cwd=root,
        )
        stage(
            f"native-geometry-container-start-{version_slug}",
            container_command,
            output,
            cwd=root,
        )

        try:
            receipt: NativeGeometryReceipt = {
                "kicad_version": version,
                "container": container,
                "image": image,
                "platform": "linux/amd64",
                "network": "none",
                "root_filesystem": "read-only",
                "writable_mount": f"{temporary_root.resolve()}:/fixtures:rw",
                "test_files": list(test_paths),
                "test_scope": f"all focused pytest and native KiCad {version} geometry tests",
            }
            receipts.append(receipt)
            (fixture_area / f"lane-{version}.json").write_text(
                json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )

            wrapper = fixture_area / f"kicad-cli-wrapper-{version}"
            wrapper.write_text(
                "#!/bin/bash\n"
                "set -euo pipefail\n"
                'prefix="${KICAD_GEOMETRY_TEST_TMP%/}/"\n'
                "args=()\n"
                'for argument in "$@"; do\n'
                '  case "$argument" in\n'
                '    "$prefix"*)\n'
                '      relative="${argument#"$prefix"}"\n'
                '      args+=("/fixtures/${relative}")\n'
                "      ;;\n"
                "    /*)\n"
                "      printf 'native geometry path escapes its fixture mount: %s\\n' \"$argument\" >&2\n"
                "      exit 2\n"
                "      ;;\n"
                '    *) args+=("$argument") ;;\n'
                "  esac\n"
                "done\n"
                'exec docker exec --user "$KICAD_GEOMETRY_TEST_USER" --workdir /fixtures '
                '"$KICAD_GEOMETRY_TEST_CONTAINER" kicad-cli "${args[@]}"\n',
                encoding="utf-8",
            )
            wrapper.chmod(0o755)
            environment = os.environ.copy()
            environment.update(
                {
                    "KICAD_GEOMETRY_TEST_CLI": str(wrapper.resolve()),
                    "KICAD_GEOMETRY_TEST_TMP": str(temporary_root.resolve()),
                    "KICAD_GEOMETRY_TEST_CONTAINER": container,
                    "KICAD_GEOMETRY_TEST_USER": uid_gid,
                    "KICAD_GEOMETRY_TEST_VERSION": version,
                    "TMPDIR": str(temporary_root.resolve()),
                }
            )
            test_command = (
                sys.executable,
                "-I",
                "-B",
                "-m",
                "pytest",
                "-q",
                *(str(root / path) for path in test_paths),
            )
            stage(
                f"native-schematic-geometry-tests-{version_slug}",
                test_command,
                output,
                cwd=root,
                environment=environment,
            )
        finally:
            stage(
                f"native-geometry-container-stop-{version_slug}",
                ("docker", "stop", "--timeout", "1", container),
                output,
                cwd=root,
            )

    (fixture_area / "lanes.json").write_text(
        json.dumps({"schema_version": "1", "lanes": receipts}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
