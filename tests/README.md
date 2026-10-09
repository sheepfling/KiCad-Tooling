# Tooling regression tests

Install the [development environment](../README.md#development-check) before running these tests.
It uses `python -m pip install -e '.[dev,cad]'` from this tooling checkout in an active virtual
environment; the project-facing extras alone do not install Ruff, Pyright or package build tools.
The shared Python regression suite belongs to this repository. Board contracts,
firmware checks, and product integration tests remain in their project repository.
Pytest is the canonical test runner. Write new tests as `test_*` functions using
plain `assert`, pytest fixtures, and parametrization where they clarify cases.
Do not add new `unittest.TestCase` tests. Existing `TestCase` tests remain
supported while we migrate the suite incrementally, prioritizing lint and
verification coverage. Convert the touched regression tests to pytest functions
when extending a legacy suite. `unittest.mock` remains useful with pytest.

The suite uses a separate public template checkout for its reference examples.
Set `KICAD_TEMPLATE_ROOT` to that checkout, then run from the tooling repository:

```sh
export KICAD_TEMPLATE_ROOT=/path/to/KiCad-Team-Workflow-Template
python -I -B -m pytest -q
```

For PowerShell, set the variable with
`$env:KICAD_TEMPLATE_ROOT = "C:\path\to\KiCad-Team-Workflow-Template"`.
Run one module with `python -I -B -m pytest -q tests/test_product.py`.

Focused runs use registered markers. `tests/conftest.py` assigns lint areas by
test module; areas can overlap when a fixture checks more than one concern. It
also marks exact-native fixture classes separately:

```sh
python -I -B -m pytest -q -m "design_lint and not native_kicad and not slow" --durations=20
python -I -B -m pytest -q -m "schematic_lint and not native_kicad and not slow"
python -I -B -m pytest -q -m "connector_lint and not native_kicad and not slow"
python -I -B -m pytest -q -m "return_path_lint and not native_kicad and not slow"
python -I -B -m pytest -q -m "pcb_lint and not native_kicad and not slow"
python -I -B -m pytest -q -m native_kicad
python -I -B -m pytest -q tests/test_rc_filters.py -k disconnected-capacitor-return
```

The first command runs the portable, non-slow design-lint group. The area
markers select schematic, component, connector, interface, power, PCB,
return-path, or parity regressions; combine them with `-k` to select a test or
parametrized fault/control case. `native_kicad` selects exact-version fixtures and still
requires each fixture's documented version and environment settings. Markers
narrow local runs; the package acceptance gate continues to run the complete
suite. Add each new lint test module to its area in `tests/conftest.py`; this
keeps it in both its focused area and the portable `design_lint` selection.

`tests.support.reference_root()` copies the template's public examples, catalogs,
and guidance into a disposable repository. It never copies reusable Python tools
or the shared regression suite into project fixtures. CLI subprocesses load the
same tooling package as the parent test process. Temporary source mutations,
fake native commands, and synthetic release evidence stay in disposable folders.
These fixtures do not establish electrical approval or manufacturing readiness.

Use a normal editable development install. The package gate checks its import
origin before the suite; tests do not prepend source directories to `PYTHONPATH`.
The installed-wheel rehearsal runs separately to prove packaging without editable imports.

Tests must not depend on private designs, hardware, provider credentials, or
network access. The parts assistant HTTP tests use a local loopback server and
skip with an explicit reason when the environment denies local socket binding.
Native acceptance runs separately against the project's approved KiCad toolchain.

The complete package gate also checks source and wheel distributions, the CLI/MCP
surface declarations, and an installed wheel against external project layouts:

```sh
python scripts/ci.py --project-root "$KICAD_TEMPLATE_ROOT"
```

See [configuration](../docs/CONFIGURATION.md) for layout adapters and
[packaging](../docs/PACKAGING.md) for version and distribution checks.
