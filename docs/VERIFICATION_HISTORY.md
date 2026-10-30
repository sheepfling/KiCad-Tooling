# Verification history

Compare two explicitly saved [project overviews](REVIEW_OVERVIEW.md) for the
same project. Run this from the project checkout or pass `--root`:

```sh
kicad-team verification-history --project <id> \
  --baseline build/review-overview/<older>/overview.json \
  --candidate build/review-overview/<newer>/overview.json \
  --baseline-release releases/<older>.json \
  --candidate-release releases/<newer>.json
```

Release manifests are optional and must be chosen explicitly. The command
writes a fresh ignored `build/verification-history/<project>-<run>/` with an
offline `index.html` and typed `history.json`. Use `--output` for a fresh
`build/` directory and `--format json` for the structured result. MCP
`export_verification_history` uses the same service when exports are enabled;
it takes the selected paths plus a fresh `view_id`.

The two overview files anchor recorded source hashes, project manifest hashes,
selected receipt hashes, and capture-time freshness. The comparison rechecks
each selected receipt hash and reads the saved native check and findings
details only when the receipt still matches. It shows source-file hash changes,
individual `PASS`, `FAIL`, and `NOT_RUN` native checks, added or removed
findings, and possible fingerprint changes. A changed fingerprint is paired
only when a rule and title uniquely match on both sides; changed evidence
fields, severity, description, and markers are explained. Duplicate matches
remain separate rather than being treated as one finding.

`CURRENT` on a snapshot means its saved source inventory and manifest bytes
matched the live project when the history page was created. `HISTORICAL` means
they differed. This is separate from the freshness stamped on the original
overview. A selected receipt that is now missing, changed, or malformed gets
its own state. Missing findings evidence produces **no finding delta**; it
cannot be read as resolution. The page must be regenerated after inputs change.

When a release manifest is selected, the view compares its declared artifact
IDs, paths, hashes, and present byte state. It also compares the manifest's
source commit with the snapshot's hash-verified native commit. A mismatch or
unknown commit is explicit. The authored release status is displayed as
source data, separate from actual packaging, approval, electrical judgment,
or manufacturing authorization. This command performs none of those actions.
