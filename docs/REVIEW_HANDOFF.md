# Source-bound review handoff

`review-handoff` exports an offline packet from two explicitly selected project
overview receipts and a project-owned reviewer-notes JSON file. Select one or
more exact finding fingerprints from the findings receipts. The packet shows
those findings across both revisions, source fingerprints and current-source
relations, copied evidence, and the state of each relevant note.

The notes file stays in the project repository. For example:

```json
{
  "schema_version": "1",
  "project_id": "controller",
  "notes": [
    {
      "id": "return-path-question",
      "reviewer": "Engineer A",
      "recorded_at": "2026-10-30T10:00:00Z",
      "snapshot": "candidate",
      "overview_sha256": "<SHA-256 of the exact candidate overview.json>",
      "finding_fingerprint": "<64-character finding fingerprint>",
      "assessment": "needs_review",
      "text": "Confirm the return path on the new revision."
    }
  ]
}
```

The assessment can be `observation`, `needs_review`, or `resolved_claim`.
These are attributed claims, never an approval. A note is `CURRENT` only if
its overview hash matches the selected snapshot and its fingerprint still
identifies a finding in a current findings receipt. `OUTDATED_RECEIPT`,
`OUTDATED_FINGERPRINT`, and `UNAVAILABLE` make other cases visible. Current
notes with differing assessments for the same snapshot and fingerprint are
marked `CONFLICT` without choosing a winner.

```sh
kicad-team review-handoff --root /path/to/project-checkout \
  --project controller \
  --baseline build/review-overview/baseline/overview.json \
  --candidate build/review-overview/candidate/overview.json \
  --notes examples/projects/controller/docs/reviewer-notes.json \
  --fingerprint <64-character-fingerprint> --format json
```

MCP `export_review_handoff_packet` uses the same service with `project_id`,
`view_id`, `baseline`, `candidate`, `notes`, and a `fingerprints` array when
exports are enabled. It writes a fresh ignored `build/review-handoff/` receipt.
Open `index.html` for the offline view. `handoff.json` records all selected
source and artifact hashes; `notes.json`, selected overview and findings
receipts, and verified SVG drawings are copied into the packet. Missing or
changed evidence is listed and omitted from copied links. The service never
writes notes or decisions back to project source.

An overview's historical source relation describes its difference from the
current checkout. It does not invalidate its own retained finding receipt.
The packet does not infer electrical correctness or release readiness.
