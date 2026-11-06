# Conflicting custom DRC severity fixtures

These tooling-owned `.kicad_dru` files differ only in their direct severity
clauses. The fault assigns both `error` and `warning` to
`SyntheticTrackWidth`; the control assigns only `error`. Both use the same
canonical track condition and a 0.4 mm track-width minimum. Neither file or
the temporary probe board contains project design data.

| Input                                 | SHA-256                                                            |
| ------------------------------------- | ------------------------------------------------------------------ |
| `fault-multiple-severities.kicad_dru` | `e682b07006dcb97a231012cbf396535018b3d4b5754c0d272d7e735a01db2ba2` |
| `control-one-severity.kicad_dru`      | `8e75fa7d5483d38a641d0c888fb85fcc2d83f77c91f2dbee2486d1948e4b67fc` |

The repeatable terminal-sentinel probe used digest-pinned
`ghcr.io/kicad/kicad:10.0.0@sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3`
and
`ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`.
On KiCad 10.0.0, both authored rules produced zero named track-width findings while the appended
sentinel fired. On KiCad 10.0.5, the fault produced two named warnings and the single-error control
produced two named errors. Each input was run twice per version with identical observed severities.

This trial supports a source-level review prompt for conflicting severity
declarations. It does not establish universal last-clause precedence, explain
the 10.0.0 absence of authored findings, or prove that either rule matches a
production board.
