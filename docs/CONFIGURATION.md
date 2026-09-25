# Adapting a project repository

The template layout works without an adapter file. Tooling reads the project
checkout passed to `--root`, or the CLI's current working directory. MCP binds
one absolute checkout at startup. Both surfaces use the same configuration and
services; changing a layout does not require a separate MCP adapter.

## Keep the template defaults

The defaults are `catalog/projects.json` for discovery, `catalog/products.json` for the product
index, `catalog/team-policy.json` for team governance, `templates/` for scaffold inputs,
`docs/workflow/` for named workflow guides, and `projects/` for new projects. Existing discovery
catalogs list `projects` and optionally `examples/projects`; their default search depth is one
directory below each root.

Project manifests continue to own the paths to their KiCad project, source
folders, required inputs, checks, and shared assets. Catalog paths for parts,
interfaces, libraries, toolchains, and release policies already live in the
project discovery catalog. Keep these authored records in the project repository.

## Change repository paths

Create `kicad-tooling.toml` at the project root. Every setting is optional;
unknown settings fail validation so a typo cannot silently select the defaults.
This example moves shared metadata and groups boards by team:

```toml
schema_version = "1"

[layout]
discovery = "policy/discovery.json"
products = "policy/products.json"
team_policy = "policy/team-policy.json"
templates = "starter"
workflow_docs = "handbook"
new_project_root = "hardware/team-a"
product_roots = ["assemblies"]
library_roots = ["shared/cad"]
```

The corresponding `policy/discovery.json` contains:

```json
{
  "schema_version": "1",
  "catalogs": {
    "parts": "policy/parts.json",
    "interfaces": "policy/interfaces.json",
    "libraries": "policy/libraries.json",
    "toolchains": "policy/toolchains.json",
    "release_policies": "policy/release-policies.json"
  },
  "project_roots": ["hardware"],
  "project_depth": 2
}
```

A board then lives at `hardware/team-a/<board-id>/project.json`. Discovery searches
through the declared depth, from 1 to 8, and stops at each project island.
IDs must remain unique across the checkout and match the island directory name.
Creation and import use `new_project_root`, which must place the new island
within a configured discovery root at a discoverable depth. A project cannot be
created inside another project. Discovery roots cannot overlap each other,
shared library roots, or product roots.

Product records remain explicit in the product index and live one island below
a configured product root: `assemblies/<product-id>/product.json`. Libraries
similarly live at `shared/cad/<library-id>/`. Moving a directory requires updating
its authored references; configuration does not move files or rewrite source.

Paths must be portable and relative to the checkout. Parent traversal, absolute
paths, symlinks, hidden state, and generated directories cannot expand source
scopes. Discovery is bounded to 10,000 entries. Receipts retain the conventional
`build/` name; MCP only exposes repository receipts and configured island receipts.

After arranging the files, inspect and verify from the project checkout:

```sh
kicad-team template list --format json
kicad-team template diagnose --project-id <board-id> --format json
kicad-team verify --project <board-id> --format json
kicad-team-mcp --root /absolute/path/to/project
```

MCP inventory, project reads and edits, artifact reads, imports, and named guide
reads use these same paths. Product selection, impact planning, parts input
fingerprints, and release snapshots also bind the configured catalogs and the
adapter file.

## Scope of this adapter

Existing islands may describe their own source/check paths in `project.json`.
MCP reads and validates edits to the declared check contract, including a relocated
JSON contract, through the same project boundary.
New islands still use `project.json`, `kicad/`, `docs/`, and `tests/contract.json`;
the scaffold templates must follow that internal contract. Workflow guide
filenames retain their template names within `workflow_docs`.

`template init` retires the reference template catalogs and therefore requires
the default layout. Initialize a new template checkout before adapting paths.
Template-specific fault probes and sample release rehearsals require the named
public reference boards. The full project gate checks the selected repository;
shared Python regression and quality checks run in the tooling repository.
The adapter does not claim arbitrary repository formats.

Configuration is declarative. It does not execute project-supplied Python or
shell hooks. Add new behavior as a reviewed tooling service shared by CLI and
MCP, with regression tests for the additional contract.

## Approve a different KiCad version

Each project selects a `toolchain_id` from its configured toolchains catalog.
Each record supplies the exact `kicad_version`, a digest-pinned container image,
and the team's installer and migration policy. Updating tooling does not change
these project-owned pins. Multiple approved versions may coexist in one checkout.
`check-toolchain` auto-selects only when the catalog has exactly one entry.
Native doctor requires an explicit project or toolchain ID.

The current native adapter implements the
[KiCad 10 CLI and report contract](https://docs.kicad.org/10.0/en/cli/cli.html).
Existing `10.x` records select it by default. A different major version requires
an explicit `"cli_profile": "kicad-10"` field in that toolchain record, after the
team has established that its required commands and report formats are compatible.
This declaration does not certify the new KiCad version. Run import, native
checks, exports, and the relevant acceptance projects against the exact candidate
version before adopting it. An incompatible CLI needs a new adapter in tooling.

Without a declared compatible profile, native operations stop with an actionable
error while portable operations remain available. Version matching, image digest
requirements, and report schema checks remain enforced even with an explicit
profile. No newer KiCad major version has been validated by this extraction.
