# Saved release readiness view

Capture a computed release check for an explicitly selected manifest:

```sh
kicad-team release-readiness-view --manifest build/releases/<id>/manifest.json
```

Run it from the project checkout or pass `--root`. The command writes a fresh,
ignored `build/release-readiness-view/<id>-<run>/` with `index.html` and
`readiness.json`. `--output` chooses a fresh `build/` directory and `--format
json` prints the typed receipt. MCP `export_release_readiness_view` runs the same
service when exports are enabled; it takes `manifest` and a fresh `view_id`.

The receipt contains the **computed** release status and each policy issue,
along with the check date, selected manifest hash, checked source commit, a
checkout input inventory, and hashes of files directly declared as release
artifacts or evidence and the files listed inside retained native, electrical,
and export evidence reports. It records whether this dependency inventory was
complete and whether the selected inputs stayed stable while the
check ran. A `FAIL` result is retained so a later review can see why a candidate
was blocked. The page does not authorize build, approval, packaging, or
publication.

To compare two saved results, select both readiness receipts and their release
manifests in [verification history](VERIFICATION_HISTORY.md). History rechecks
the receipt page, manifest, source binding, and declared files. `STALE`,
`MISSING`, and `UNAVAILABLE` are visible separately from the computed `PASS` or
`FAIL` status. A changed file never becomes evidence of improved readiness.
