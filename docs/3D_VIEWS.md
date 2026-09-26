# Review a board from multiple sides

From a project checkout with the tooling installed, make one complete 3D review
bundle with:

```sh
kicad-team visualize --project <project-id>
```

The default bundle contains six straight-on views (`top.png`, `bottom.png`,
`left.png`, `right.png`, `front.png`, and `back.png`), four angled views
(`angled.png`, `angled-90.png`, `angled-180.png`, and `angled-270.png`), plus
`board.step` and `board.glb`. The PNGs and a JSON receipt are saved under a fresh
ignored receipt under `build/`.

Straight-on renders request a 1600 by 900 canvas. Angled renders request a square
1600 by 1600 canvas and a camera margin so quarter-turn views have room for the board.
Inspect unusually tall components and unusual board geometry for clipping.

For a quicker focused review, repeat `--view` with the views you need:

```sh
kicad-team visualize --project <project-id> \
  --view top --view angled --view angled-90
```

Available names are `top`, `bottom`, `left`, `right`, `front`, `back`, `angled`,
`angled-90`, `angled-180`, and `angled-270`. STEP and GLB are still exported
with a selected view subset. Use `--check-models` when you only want a static
model-coverage report without starting KiCad.

The MCP `export_3d` tool uses the same named view set. Omit `views` to make the
full bundle, or pass an array such as `['top', 'angled', 'angled-90']`. Its
`view_id` names the receipt directory; `views` controls the camera images.

Inspect the actual images and geometry before making mechanical decisions. A
render is a review aid, not physical-fit or manufacturing approval.

## Portable preview orchestration

The hosted preview wrapper runs on Windows, macOS and Linux with the installed tooling:

```sh
python -I -B -m kicad_tooling.ci_hosted preview --project controller
```

Use an actual registered project ID. The default runner is `auto`: an exact local KiCad CLI
or the project's pinned Linux container through Docker. Select `--runner local --cli` with a
quoted executable path when needed, or `--runner container` for the pinned image. Native tools
must be installed separately; a portable wrapper does not make them available on every runner.

Pass `--root` before `preview` when running outside the project. Each run needs a fresh
`--output` under the project's ignored `build/`; the default is `build/3d-preview`.
Python retains `cli.stdout.txt`, `cli.stderr.txt`, renderer receipts and stage logs under
`build/ci-hosted/preview/`, and preserves a failed renderer's exit code. When GitHub supplies
`GITHUB_STEP_SUMMARY`, Python also appends the escaped review text, including failure reports.
Local runs need no GitHub environment or Bash utilities. Existing receipts are never overwritten.

The manual template Action runs the wrapper with the pinned container on Linux. Package CI
separately exercises its path handling, subprocesses, Unicode logs and failure behavior on actual
Windows, macOS and Linux runners. These orchestration tests use a synthetic child process and do
not claim a native render on all three systems. MCP `export_3d` uses the same underlying renderer;
GitHub log and summary handling remains an operator/CI adapter.
