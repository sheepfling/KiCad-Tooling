# Tooling regression tests

Install the [development environment](../README.md#development-check) before running these tests.
It uses `python -m pip install -e '.[dev,cad]'` from this tooling checkout in an active virtual
environment; the project-facing extras alone do not install Ruff, Pyright or package build tools.
The shared Python regression suite belongs to this repository. Board contracts,
firmware checks, and product integration tests remain in their project repository.

The suite uses a separate public template checkout for its reference examples.
Set `KICAD_TEMPLATE_ROOT` to that checkout, then run from the tooling repository:

```sh
export KICAD_TEMPLATE_ROOT=/path/to/KiCad-Team-Workflow-Template
python -B -m unittest discover -s tests -v
```

For PowerShell, set the variable with
`$env:KICAD_TEMPLATE_ROOT = "C:\path\to\KiCad-Team-Workflow-Template"`.
Run one module with `python -B -m unittest tests.test_product -v`.

`tests.support.reference_root()` copies the template's public examples, catalogs,
and guidance into a disposable repository. It never copies reusable Python tools
or the shared regression suite into project fixtures. CLI subprocesses load the
same tooling package as the parent test process. Temporary source mutations,
fake native commands, and synthetic release evidence stay in disposable folders.
These fixtures do not establish electrical approval or manufacturing readiness.

Tests must not depend on private designs, hardware, provider credentials, or
network access. The parts assistant tests open a local loopback server; restricted
test environments must allow that local socket. Native acceptance runs separately
against the project's approved KiCad toolchain.

The complete package gate also checks source and wheel distributions, the CLI/MCP
surface declarations, and an installed wheel against external project layouts:

```sh
python scripts/ci.py --project-root "$KICAD_TEMPLATE_ROOT"
```

See [configuration](../docs/CONFIGURATION.md) for layout adapters and
[packaging](../docs/PACKAGING.md) for version and distribution checks.
