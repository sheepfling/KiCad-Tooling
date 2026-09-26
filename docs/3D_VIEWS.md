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
