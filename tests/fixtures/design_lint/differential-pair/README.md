# Synthetic differential-pair native DRC matrix

These public synthetic boards compare project-authored KiCad design rules with
native PCB DRC. They do not model a proprietary board or declare universal
USB, serial, or stack-up requirements. The board contains two straight tracks;
KiCad reports two unrelated `track_dangling` warnings because the track ends
are intentionally not attached to pads. The expected comparison ignores those
warnings and checks the pair-rule finding types below. All fixtures have zero
unconnected items in the tested KiCad versions.

| Fixture           | Authored variation                                           | Expected pair-rule findings                                            |
| ----------------- | ------------------------------------------------------------ | ---------------------------------------------------------------------- |
| `control`         | 0.3 mm tracks; 0.2 mm edge gap; equal 20 mm lengths          | none                                                                   |
| `fault-width`     | both tracks are 0.1 mm wide                                  | `track_width`                                                          |
| `fault-gap`       | pair gap exceeds the authored maximum                        | `diff_pair_gap_out_of_range` and `diff_pair_uncoupled_length_too_long` |
| `fault-skew`      | one track is 0.5 mm longer                                   | `skew_out_of_range` and `diff_pair_uncoupled_length_too_long`          |
| `fault-uncoupled` | one track is offset 0.5 mm at both endpoints                 | `diff_pair_uncoupled_length_too_long`                                  |
| `no-rules-skew`   | byte-identical skew fault with no `.kicad_dru` file          | none; demonstrates that native DRC needs an authored pair rule         |
| `no-rules-gap`    | same excessive gap as `fault-gap`, with no `.kicad_dru` file | none; demonstrates missing rule coverage                               |

The five `.kicad_dru` files author synthetic constraints for width, gap, skew,
and uncoupled length. The `no-rules-gap` and `no-rules-skew` cases intentionally
have no rule file; the latter is byte-identical to `fault-skew.kicad_pcb`.
The expected values exercise native DRC only; they are not electrical design
recommendations.

## Re-run with pinned KiCad versions

The image references match the digest-pinned public toolchain catalog in the
KiCad-Test template. Run this from the KiCad-Tooling checkout after Docker has
the images available. Reports go under ignored `build/`.

```sh
mkdir -p build/research/lint022

docker run --rm --platform linux/amd64 \
  -v "$PWD/tests/fixtures/design_lint/differential-pair:/fixtures:ro" \
  -v "$PWD/build/research/lint022:/reports" \
  ghcr.io/kicad/kicad:10.0.0@sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3 \
  sh -lc 'for case in control fault-width fault-gap fault-skew fault-uncoupled no-rules-skew no-rules-gap; do kicad-cli pcb drc --severity-all --format json --output "/reports/10.0.0-${case}.json" "/fixtures/${case}.kicad_pcb" || exit $?; done'

docker run --rm --platform linux/amd64 \
  -v "$PWD/tests/fixtures/design_lint/differential-pair:/fixtures:ro" \
  -v "$PWD/build/research/lint022:/reports" \
  ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c \
  sh -lc 'for case in control fault-width fault-gap fault-skew fault-uncoupled no-rules-skew no-rules-gap; do kicad-cli pcb drc --severity-all --format json --output "/reports/10.0.5-${case}.json" "/fixtures/${case}.kicad_pcb" || exit $?; done'

docker run --rm --platform linux/amd64 \
  -v "$PWD/tests/fixtures/design_lint/differential-pair:/fixtures:ro" \
  -v "$PWD/build/research/lint022:/reports" \
  kicad/kicad:10.0.6@sha256:18693567392b80da435f9fa952ce3a3e534c66eb5a6033f5b9c80aa3b19dd3ec \
  sh -lc 'for case in control fault-skew no-rules-skew; do kicad-cli pcb drc --severity-all --format json --output "/reports/10.0.6-${case}.json" "/fixtures/${case}.kicad_pcb" || exit $?; done'
```

Compare the `violations[].type` values in each report. Do not compare whole
JSON files: report dates, generated UUIDs, and unrelated DRC categories can
vary. The verified result is documented in
[`docs/DESIGN_LINT_BACKLOG.md`](../../../../docs/DESIGN_LINT_BACKLOG.md#lint-022--differential-pair-physical-constraint-evidence).
