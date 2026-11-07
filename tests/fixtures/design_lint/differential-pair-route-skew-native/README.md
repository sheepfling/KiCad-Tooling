# Routed differential-pair skew fixture

`create.py` makes two synthetic KiCad boards inside the digest-pinned native
container. Each board has exact USB_DP and USB_DN pad-to-pad routes and no
custom `.kicad_dru` skew rule. The equal-length control has an off-path USB_DN
stub at a route junction, verifying that a harmless spur does not hide the
unique mapped path. The fault board adds a rectangular detour to USB_DN beyond
the test's authored 500,000 nm maximum skew.

The fixture lane runs the tooling's native PCB probe on both boards, then checks
that the deterministic analyzer reports the fault and accepts the control from
those exact probe snapshots. It records the generated board, snapshot, probe,
container version, and command hashes under ignored `build/` output.

Run the focused synthetic checks with:

```sh
.venv/bin/python -I -m pytest -q \
  tests/test_pcb_differential_pair_route_skew.py \
  -m 'design_lint and pcb_lint'
```

Run the native lane with:

```sh
KICAD_RUN_NATIVE_PCB_FIXTURES=1 .venv/bin/python -I -m pytest -q \
  tests/test_pcb_differential_pair_route_skew_native.py \
  -m 'design_lint and pcb_lint and native_kicad and design_lint_rule(rule_id="pcb.differential_pair_route_skew")'
```

The board and route contract are synthetic tooling fixtures. They do not import
or represent a product design, and the result does not establish that the
authored skew maximum is suitable for any particular interface. Route length
measurement covers track centerlines; it does not add vertical via-barrel
length, zones, or electrical propagation effects.
