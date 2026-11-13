# Custom DRC contradictory-bound fixtures

These source files are tooling-owned synthetic KiCad version-1 custom DRC
rules. The fault sets a positive `track_width` minimum of 0.3 mm and maximum
of 0.1 mm. Controls cover an ordered range, equal bounds, one-sided bounds, a
repeated minimum, and an unresolved text variable. No project design or
cohort fixture is used.

The custom-rule source hashes are:

| Fixture                              | SHA-256                                                            |
| ------------------------------------ | ------------------------------------------------------------------ |
| `fault-min-exceeds-max.kicad_dru`    | `74f176418d1d528ca26b43994d706caacd0235dbe13e7a21f35c1cf244158474` |
| `control-valid-range.kicad_dru`      | `bcd4943e92c9df9a9a42d05c542be239f89352e55d287d9cbcba0703db3affc0` |
| `control-equal-bounds.kicad_dru`     | `7245e8e8a7eafb4bf4ff03a923741309aa3140ba5a0a1889e0d3aa610dc3846b` |
| `control-one-sided-bounds.kicad_dru` | `2fae354ddb886457b7f3eb9740281adf0e5b0e7bfa740e6eaed1548be004fe14` |
| `control-repeated-bound.kicad_dru`   | `5ad574495d2fab8e2d08abf209742a8294cf257566bbd87248cad86db0638d9d` |
| `control-text-variable.kicad_dru`    | `2740228a7465e41823efed54e1801aaf632d73ad4a5440d8ac85d125dd085ab4` |

The native probe pairs these rule files with the synthetic two-track board
`tests/fixtures/design_lint/pcb-drc-duplicate-net-settings/board.kicad_pcb`
and its `control-netclass-clearance-default-assignment.kicad_pro` settings.
Their SHA-256 values are respectively
`47914e5502c7b022fba5802c3d8391d636bf5e0fffd672eccb36f281adaecff3` and
`2f2ca16e74fa331f446195d8345fc37cd01786118ced157b6b05d7e4e63677de`.

On the digest-pinned KiCad 10.0.8 image
`ghcr.io/kicad/kicad:10.0.8-amd64@sha256:05f6ac957e351bbbd9e1f9c996be997f61948ed9f94e0c3cab336bfcaf60161c`,
the contradictory fault was accepted and produced two `track_width` errors; the descriptions
reported a 0.1 mm minimum while the actual traces were 0.2 mm. The ordered and equal-bound controls
produced no `track_width` findings. All three normalized violation sets repeated exactly. The probe
does not establish behavior on another KiCad version or for every constraint type.
