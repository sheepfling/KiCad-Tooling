# Duplicate PCB object UUID fixture

These tooling-owned synthetic boards were derived from
`tests/fixtures/design_lint/pcb-reference-zone-island/control.kicad_pcb`. They
contain no customer or cohort design data. The only fault mutation is the UUID
of the second disconnected copper track: the control assigns it a distinct ID,
while the fault repeats the first track's ID.

| Source              | SHA-256                                                            | Expected source lint                               |
| ------------------- | ------------------------------------------------------------------ | -------------------------------------------------- |
| `control.kicad_pcb` | `58eb8a374ede66a0c4c53b766b5f30507933c8fbebcdac98d1f4986ca8a0bed4` | No repeated UUID                                   |
| `fault.kicad_pcb`   | `c579a9593bd10784544898323ae1600dd26e8b65fc4d1a8e54b0acbd22c1cc90` | One review candidate for the two `segment` objects |

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

Run the native check from the repository root with:

```sh
KICAD_RUN_NATIVE_PCB_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_pcb_duplicate_object_uuid_native.py \
  -m 'design_lint and pcb_lint and evidence_lint and native_kicad and design_lint_rule(rule_id="pcb.duplicate_object_uuid")'
```
