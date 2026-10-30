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

Open `index.html` in the receipt to browse the views and download the available
STEP and GLB files. The gallery records the export and model-coverage status and
links only to outputs whose hashes still match when it is created. If an export
stops after producing some files, the gallery labels the failed result and shows
only the retained views and exchange files. If a retained file changes or goes
missing during the export, the receipt fails and the gallery omits it. No gallery
is created when the run produces no outputs, including a model-only check.

When a complete, self-contained GLB was retained, the gallery also links to
`viewer.html`. Open it directly from the receipt, including with a `file://`
browser URL. Drag to rotate, Shift-drag or right-drag to pan, and scroll to zoom.
The Fit, orientation, pan, and zoom buttons work by keyboard. Focus the model
for arrow-key rotation, Shift plus arrow-key pan, `+`/`-` zoom, and `F` fit. The page
embeds the exact GLB bytes checked against `board.glb` and records the board
source hashes, model-coverage status, export notes, and links to retained
exchange files and `visualization.json`. It also retains `viewer.js` and its
MIT license in the receipt, with all three viewer files hashed in the report.
No network request or local server is needed to render the snapshot.

An opt-in browser regression opens the retained sample GLB directly from disk
and exercises the orientation, zoom, and keyboard controls. Set
`KICAD_VIEWER_BROWSER` to an installed Chrome-family executable and run
`python -I -m pytest tests/test_three_d_viewer_browser.py -q` from this tooling
checkout. The check needs a browser that can run headless with WebGL; it skips
when no browser path is provided. It checks that the page renders, responds to
controls, and loads no remote resources.

A missing, truncated, or structurally invalid GLB is excluded from the gallery
and fails the export receipt. A GLB with external image or buffer references
remains an exchange file, but gets no offline viewer link. If the browser lacks
WebGL or the model cannot render, the viewer displays an error. The viewer is a
visual aid; missing model assignments are still shown as review notes, and a
rendered board does not establish enclosure fit or clearance.

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

For a project-owned adjacent enclosure GLB and explicit coordinate placement,
see [mechanical assembly review](ASSEMBLY_REVIEW.md).

The offline renderer is bundled from Three.js `0.181.0` and esbuild `0.25.12`.
Its editable source is `kicad_tooling/hwrepo/assets/three_d_viewer.src.js`; the
checked-in browser bundle is `three_d_viewer.js`. To rebuild it, install those
exact npm packages in a temporary directory, copy the source beside its
`node_modules`, then run esbuild with `--bundle --format=iife --minify
--target=es2020` and the license banner. The package includes the upstream
Three.js MIT license as `threejs-LICENSE.txt`. Runtime receipts use the bundled
copy and do not fetch npm packages.

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
