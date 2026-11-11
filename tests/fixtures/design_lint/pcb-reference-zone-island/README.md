# Reference zone island without a direct pad anchor

These are tooling-owned synthetic boards with synthetic nets, pads, tracks, a
RETURN zone, and a rectangular board outline. The fault/control pair changes
only the copper layer assigned to `J1.1`:

- `fault.kicad_pcb` places the RETURN pad on B.Cu while the filled RETURN zone
  is on F.Cu.
- `control.kicad_pcb` places the same pad on F.Cu so the filled island has a
  direct pad anchor.
- `indirect-control.kicad_pcb` places `J2.1` on F.Cu just outside the zone
  contour. A same-net F.Cu track connects `J2.1` to the zone, so native
  connectivity reaches the filled island even though the pad itself does not
  touch its polygon.
- `via-control.kicad_pcb` places `J2.1` on B.Cu and connects it to the F.Cu
  zone through a plated via with a short same-net track on each copper layer.
  The via touches the island, while the pad does not share its copper layer.

The native connectivity probe on exact KiCad 10.0.0 and 10.0.5 images reports
one unanchored F.Cu island for the fault and none for the direct, track, or via
control. It uses the native connected component plus the copper shapes that
touch each filled island, so a same-net item elsewhere in the component cannot
anchor an unrelated island by itself. The pinned images are:

- `ghcr.io/kicad/kicad:10.0.0@sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3`
- `ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`

With `kicad-cli pcb drc --severity-all --format json`, all four boards have
zero unconnected items and the same violation types: `track_dangling` and
`lib_footprint_issues`. This demonstrates a review-evidence gap in this
standalone fixture; it does not assert how a particular project contract,
schematic, or DRC setup would report a real board.

The rule only considers a zone when a project-authored
`pcb_reference_plane_map` requirement sets `review_unanchored_islands` to
`true`, and only on copper layers immediately adjacent to its mapped signal
layer. An island is considered pad-connected when a native connected component
contains a pad and a pad, track, or via copper shape from that component touches
the island. A missing pad-connected path does not establish that the board is
defective or that the return path is inadequate. The check does not determine
ground intent, return-current adequacy, manufacturability, or physical
continuity beyond KiCad's source-bound copper model. Review the exact geometry
and connectivity before interpreting a candidate.

Fixture SHA-256:

| Board                        | SHA-256                                                                  |
| ---------------------------- | ------------------------------------------------------------------------ |
| `fault.kicad_pcb`            | `501f69644d4f40dae7f2aada3da27595cfb2d32aae8b2213e2909d76c46115d4`     |
| `control.kicad_pcb`          | `609405676e4dc46f00620c4dce0c188391496c91006fe5199762a352c8850f36`     |
| `indirect-control.kicad_pcb` | `2e69f57225cabb1ea91a88234dc2e9edc8550cfab1d2490d58faae07d44fdb76`   |
| `via-control.kicad_pcb`      | `f04acaab75f69b98570d2429c58ad87e4691bbb69df649c0be32be0714505c21`   |
