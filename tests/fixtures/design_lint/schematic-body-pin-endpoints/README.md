# Synthetic symbol-body pin-endpoint review

These schematics are authored for tooling tests and are not for manufacture.
The review candidate has two generic one-pin connectors with wire endpoints at
pin tips inside the supported symbol-body envelopes. The geometry rule should
retain one review candidate per connector and report the matching pin number.

The clear control moves the shared body rectangle 2.54 mm so it no longer
overlaps either wire. No external project source or part expectation is used.

- `pin-endpoint-review-candidate.kicad_sch` — SHA-256
  `1a806d4dfa07e899f2f301d5f7eefd5a0dab52f359afbbdb19908c79cb9e402e`; two
  review candidates, each with one pin-tip match.
- `pin-endpoint-clear-control.kicad_sch` — SHA-256
  `48db8266d3d478d6b8d0b5aa4f0a8ab4374ed6b04ccaab345f734d9d17e3ee29`; no
  wire/body candidates.
