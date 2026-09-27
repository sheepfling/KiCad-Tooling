# Design lint and project review decisions

Design lint finds patterns that merit review in a source-bound KiCad netlist. It
cannot infer whether matching connector pins should share a net. The project
repository owns the pinout, electrical requirements, and decisions about each
finding. Tooling owns the rules and report format.

The first rules are:

- `connector.repeated_pin_function` flags pins with the same function on two
  or more instances of the same connector symbol when they use different nets
  or a pin has no net. This includes power and ground functions.
- `net.numbered_returns` flags two or more return-like nets with the same stem
  and distinct numeric suffixes, such as `GND1` and `GND2`.

These rules do not claim that the nets must be connected. An intentionally
isolated interface can produce a valid finding. A symbol without named pins,
an uncommon connector reference, or an unrelated net-name pattern can evade
the current rules. Keep ERC, independently reviewed electrical contracts, PCB
inspection, and first-article tests in their own roles.

## Run the lint lane

Run native verification against the intended source, then inspect the retained
project summary:

```sh
kicad-team design-lint --project <board-id> \
  --native-summary build/<run>/native/<board-id>/summary.json --format text
```

`inspect_design_lint` provides the same read-only report through MCP. The
service checks the selected project, exact catalogued KiCad version, source
hashes, netlist hash, and export command evidence. A failed independent
component/net contract does not hide a sound exported netlist. `BLOCKED` means
the evidence or project policy cannot be trusted. `REVIEW` means an open
finding or stale ignore needs attention. `FAIL` means an open finding has been
set to block by project policy. The CLI exits nonzero for all three statuses.

## Record a decision in the project

Add `design_lint` inside the project's `tests/contract.json`. This opts native
`verify` and `ci --kicad` into the lint lane. The report records the
project-owned contract's path and digest separately from the native schematic
source hashes:

```json
{
  "design_lint": {
    "schema_version": "1",
    "rules": [
      {
        "rule_id": "connector.repeated_pin_function",
        "mode": "block",
        "reason": "Connector pin discrepancies require a reviewed decision"
      }
    ],
    "ignores": [
      {
        "rule_id": "net.numbered_returns",
        "fingerprint": "<64-character fingerprint from the report>",
        "reason": "Approved interface pinout keeps these two synthetic returns isolated"
      }
    ]
  }
}
```

The example is a fragment; preserve the existing `schema_version`, `validation`,
and other authored fields. The fingerprint covers the rule, subject, and exact
observed pin/net evidence. A changed connection produces a new fingerprint and
leaves the old ignore stale, so review the change and remove or replace that
decision. Duplicate decisions, unknown rules, and empty reasons fail schema
validation.

Each rule defaults to `review`. A project can set `block` to make an open
finding a policy failure or `off` to disable the rule across that project;
both require a reason, and the report still shows findings under `RULE_OFF`.
An exact ignore suppresses only one observed finding and remains visible with
its reason. Prefer exact ignores when only one pattern is intentional. A `PASS`
means all current lint findings were reviewed or disabled according to this
project policy; it does not approve the wiring.

When the review establishes an actual requirement, express it in the project's
grounding or `pin_connectivity` electrical contract. That stronger check can
verify specified pin relationships and can fail a regression even when names
or heuristic patterns change. See [connector pin review](CONNECTOR_PIN_REVIEW.md).
