# Rehearse the template and tooling together

Keep the two checkouts adjacent. The template holds engineering source and
instructions; this repository holds the installed Python services and their
regression suite. The normal engineer environment installs the template's exact
`requirements-tooling.txt` pin. An editable install is an explicit development
choice for testing a tooling change before proposing a new pin.

From a template checkout:

```sh
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-tooling.txt
kicad-team --version
kicad-team template doctor --format text
kicad-team template list --format text
```

For paired development, replace the pinned package in that disposable environment:

```sh
python -m pip install -e '../KiCad-Tooling[project,mcp,charts,cad]'
```

Changes to shared Python are then picked up from the tooling checkout. No Python
files are copied into the project. Restore the exact requirements pin before
recording acceptance for an engineering release.

## Run the guided rehearsal

Switch to the tooling checkout and run its play-test driver using the installed
project environment. Use a fresh output directory under the tooling checkout’s ignored `build/`:

```sh
cd /absolute/path/to/KiCad-Tooling
/path/to/template/.venv/bin/python scripts/playtest.py \
  --template-root /absolute/path/to/template \
  --output build/playtest-local
```

Add `--native` to exercise the reference controller with its exact catalogued
KiCad image. This rehearsal explicitly selects the container runner, so Docker must
be installed and running, with access to the pinned image. A local KiCad installation
does not satisfy this driver’s native prerequisite. Ordinary project verification
can select an exact local runner separately.

The driver makes disposable project checkouts and retains stage logs and a
summary. It exercises CLI discovery and verification, fresh adoption, creation
and import, plus an actual MCP stdio connection. New and imported projects must
receive actionable diagnosis while their electrical requirements remain
unreviewed; this is an expected coaching result, never manufactured test truth.
The rehearsal does not edit the original reference source or submit supplier data.

## Check a tooling update before changing the pin

Keep the Python environment active, switch to the tooling checkout, and add its
`dev` dependencies. The project-facing extras alone omit package lint, type and build tools.

```sh
cd /absolute/path/to/KiCad-Tooling
python -m pip install -e '.[dev,cad]'
export KICAD_TEMPLATE_ROOT=/absolute/path/to/template
python -B scripts/ci.py --project-root "$KICAD_TEMPLATE_ROOT"
```

The tooling CI owns shared regression, lint, type, package and adapter tests.
It also runs the portable onboarding rehearsal with the freshly installed wheel,
including both MCP sessions, so a source checkout cannot hide a packaging gap.
Project CI runs installed tooling against project-owned contracts, catalogs,
documentation and optional project test suites. Keep native/export/release
receipts with their exact project commit and tooling version. New requirements,
mechanical fit and manufacturing approvals still require engineering review.
