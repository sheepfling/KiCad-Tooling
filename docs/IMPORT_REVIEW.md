# Import and onboarding review

Before importing a native KiCad project, create a local review of the selected
source and proposed project ID:

```sh
kicad-team import-review --root /path/to/project-repository \
  --source /path/to/source/board.kicad_pro \
  --project-id board-id --toolchain kicad-10.0.5
```

The command writes a fresh ignored `build/import-review/<project>-<run>/`
containing an offline `index.html` and typed `review.json`. `--output` chooses a
fresh `build/` directory; `--format json` prints the receipt. Relative source
paths are interpreted against `--root`. The `export_import_review` MCP tool
uses the same service when exports are enabled; it restricts source paths to
the checkout and startup import roots, and requires a fresh `view_id`.

The page combines the existing dry-run importer and import diagnostics. It
shows included source file hashes, excluded and missing files, the declared
toolchain version and image, literal CAD library/model references, unresolved
paths, and repair actions. `PINNED_LIBRARY` means the source names a versioned
KiCad library path; it does not prove that the library exists in the installed
native toolchain. Unsupported source formats and project ID conflicts remain
visible. No source is copied while making the review.

After addressing blockers and reviewing exclusions, apply the same saved
preview explicitly:

```sh
kicad-team template import-project --root /path/to/project-repository \
  --source /path/to/source/board.kicad_pro \
  --project-id board-id --toolchain kicad-10.0.5 \
  --review-receipt build/import-review/<review>/review.json
```

MCP `import_project` accepts the same optional `review_receipt` argument when
writes are enabled. The guarded path rechecks repository configuration,
included file hashes, selected file set, and exclusions before copying; the
importer checks the preview again immediately before staging files and verifies
each copied byte. If anything changed, create a new review. Import still does
not author electrical expectations, validate the circuit, or approve a build.
