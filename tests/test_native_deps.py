"""Cross-platform CI bootstrap must use the container's Python ABI."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from unittest.mock import patch

from kicad_tooling import package_version
from kicad_tooling.native_deps import prepare


class NativeDependencyTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.image = 'example.invalid/kicad@sha256:' + 'a' * 64

    def test_installs_linux_wheels_for_the_observed_container_abi(self) -> None:
        with patch('kicad_tooling.native_deps.subprocess.run') as run:
            run.return_value = subprocess.CompletedProcess([], 0, stdout='3.13\n')
            prepare(self.root, self.image, Path('build/deps'))
        probe, install = (call.args[0] for call in run.call_args_list)
        self.assertIn('linux/amd64', probe)
        self.assertIn('python3', probe)
        self.assertNotIn('pip', probe)
        self.assertIn('manylinux2014_x86_64', install)
        self.assertIn('cp313', install)
        self.assertIn('--only-binary=:all:', install)
        self.assertIn("pydantic==2.13.5", install)
        self.assertIn("snakemd==2.4.1", install)
        self.assertNotIn(".", install)
        package = self.root / "build/deps/kicad_tooling"
        self.assertTrue((package / "__init__.py").is_file())
        self.assertTrue((package / "tool-surfaces.json").is_file())
        self.assertFalse((self.root / "build/deps/tools").exists())
        # No site-packages or checkout fallback: the copied runtime must carry
        # its own distribution identity just as it does in the pip-free image.
        isolated = subprocess.run((
            sys.executable, "-I", "-S", "-c",
            ("import sys; sys.path.insert(0, sys.argv[1]); "
             "from kicad_tooling import package_version; print(package_version())"),
            str(self.root / "build/deps"),
        ), cwd=self.root, capture_output=True, text=True, check=False)
        self.assertEqual(isolated.returncode, 0, isolated.stderr)
        self.assertEqual(isolated.stdout.strip(), package_version())

    def test_missing_package_identity_stops_before_container_or_dependency_download(self) -> None:
        with (patch("kicad_tooling.native_deps.distribution",
                    side_effect=PackageNotFoundError("kicad-team-tooling")),
              patch("kicad_tooling.native_deps.subprocess.run") as run,
              self.assertRaisesRegex(ValueError, "Install kicad-team-tooling")):
            prepare(self.root, self.image, Path("build/deps"))
        run.assert_not_called()
        self.assertFalse((self.root / "build/deps").exists())

    def test_unsupported_container_python_stops_before_dependency_installation(self) -> None:
        with patch("kicad_tooling.native_deps.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, stdout="3.10\n")
            with self.assertRaisesRegex(ValueError, "requires Python >=3.11"):
                prepare(self.root, self.image, Path("build/deps"))
        self.assertEqual(run.call_count, 1)
        self.assertFalse((self.root / "build/deps").exists())

    def test_rejects_unknown_runtime_and_never_reuses_output(self) -> None:
        with patch('kicad_tooling.native_deps.subprocess.run') as run:
            run.return_value = subprocess.CompletedProcess([], 0, stdout='unexpected\n')
            with self.assertRaisesRegex(ValueError, 'Unexpected container'):
                prepare(self.root, self.image, Path('build/deps'))
            self.assertEqual(run.call_count, 1)
        (self.root/'build/deps').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'already exists'):
            prepare(self.root, self.image, Path('build/deps'))
        with self.assertRaisesRegex(ValueError, 'ignored build'):
            prepare(self.root, self.image, Path('projects/deps'))

    def test_missing_wheels_fail_the_setup_instead_of_running_an_incomplete_lane(self) -> None:
        with patch('kicad_tooling.native_deps.subprocess.run') as run:
            run.side_effect = [subprocess.CompletedProcess([], 0, stdout='3.13\n'),
                               subprocess.CalledProcessError(1, ['pip'])]
            with self.assertRaises(subprocess.CalledProcessError):
                prepare(self.root, self.image, Path('build/deps'))


if __name__ == '__main__':
    unittest.main()
