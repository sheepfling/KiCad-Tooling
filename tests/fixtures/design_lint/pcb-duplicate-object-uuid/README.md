# Duplicate PCB object UUID fixture

These tooling-owned synthetic boards were derived from
`tests/fixtures/design_lint/pcb-reference-zone-island/control.kicad_pcb`. They
contain no customer or cohort design data. The original fault repeats a
disconnected track UUID; additional isolated faults collide a zone `tstamp` or
footprint UUID with a track identity.

| Source                            | SHA-256                                                            | Expected source lint                               |
| --------------------------------- | ------------------------------------------------------------------ | -------------------------------------------------- |
| `control.kicad_pcb`               | `58eb8a374ede66a0c4c53b766b5f30507933c8fbebcdac98d1f4986ca8a0bed4` | No repeated UUID                                   |
| `fault.kicad_pcb`                 | `c579a9593bd10784544898323ae1600dd26e8b65fc4d1a8e54b0acbd22c1cc90` | One review for the two `segment` objects           |
| `footprint-track-fault.kicad_pcb` | `786126c87e1c75e20adb70fc6d557d969f1a419d4b3febe295ac9d6b8532300a` | One review for the `footprint` and `segment`       |
| `zone-tstamp-fault.kicad_pcb`     | `2766d404d6da0d1dec8e9f8a0e31fdcd12c9bba4094ef1fa1813ab3f37117e88` | One review for the `zone` and `segment` identities |

`control.kicad_pcb` is also the distinct-identity control for the zone/track
case, avoiding a second copy of identical source bytes.

The footprint/track fault adds one footprint `(uuid ...)` equal to a track
UUID; the same control remains distinct.

## Native observation

The native test uses these digest-pinned images:

- KiCad 10.0.0:
  `ghcr.io/kicad/kicad:10.0.0@sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3`
- KiCad 10.0.5:
  `ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`

Both versions accepted both boards for DRC. On the fault board, the two
`track_dangling` records and the two members of the `unconnected_items` record
refer to the same UUID. On the control board those records refer to the two
distinct track UUIDs. This source identity ambiguity is the demonstrated value
of the review prompt; the fixture does not establish a general electrical
failure or cover non-track UUID fields.

The legacy-field fault and the tooling-owned control were also accepted by both images and exported
twice per version. The fault changes only the zone's `(tstamp ...)` to match one segment's
`(uuid ...)`. In both versions, the `track_dangling` record for that segment and the corresponding
`unconnected_items` record resolve the shared UUID to `Zone [RETURN]` rather than the track. The
control resolves both segments as tracks. KiCad's pinned 10.0.0 and 10.0.5 PCB S-expression parsers
map zone `tstamp` and `uuid` tokens to the same internal UUID field
([10.0.0 source][kicad-pcb-parser-zone-id-100],
[10.0.5 source][kicad-pcb-parser-zone-id-105]).
These results demonstrate identifier ambiguity for this zone/track case only;
they do not establish an electrical or layout defect.

The footprint/track fault was also accepted by both images and exported twice
per version. The footprint and one track share a UUID; in both versions, the
dangling and unconnected records resolve that UUID to `Footprint J1`. The
distinct-identity control resolves both UUIDs to tracks. This adds one tested
object pair and does not establish a board defect or generalize to all PCB
object types.

[kicad-pcb-parser-zone-id-100]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.0/pcbnew/pcb_io/kicad_sexpr/pcb_io_kicad_sexpr_parser.cpp
[kicad-pcb-parser-zone-id-105]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.5/pcbnew/pcb_io/kicad_sexpr/pcb_io_kicad_sexpr_parser.cpp

Run the native check from the repository root with:

```sh
KICAD_RUN_NATIVE_PCB_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_pcb_duplicate_object_uuid_native.py \
  -m 'design_lint and pcb_lint and evidence_lint and native_kicad and design_lint_rule(rule_id="pcb.duplicate_object_uuid")'
```
