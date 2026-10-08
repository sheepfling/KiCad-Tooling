# Connector pin relationship review

KiCad ERC checks unconnected pins and undriven power inputs according to their
symbol pin types. It cannot decide whether three otherwise valid connector pins
must share one rail or remain separate. Make that decision in an independently
approved connector pinout. Project source, requirements, and approvals stay in
the project repository. See the [KiCad ERC rules][kicad-erc].

## Inspect candidate relationships

From a project checkout, capture a fresh netlist with its catalogued exact
KiCad version:

```sh
kicad-team contract-coach --project-id <board-id> --capture --format text
```

The CLI and MCP contract coach compare pin functions on repeated instances of
the same connector symbol. A function such as `PWR` on `J1`, `J2`, and `J3`
appears for review when any of those pins is absent from the exported nets or
they use differing nets. Ground/return-like functions also compare across
connector symbol types and within one connector, so a `GND` pin on a USB symbol
and an `RTN` pin on a serial symbol can surface together. A narrow set of named
supply functions also compares across symbols: `PWR`/`POWER`, `VBUS`, `VCC`,
`VDD`, and common voltage labels. The checker preserves rail identity, so
`VBUS` and `VCC` are not treated as synonyms. These hints use symbol pin
definitions even when a pin is unconnected. The connector-reference hint
recognizes `J`, `P`, `X`, and `CN` numbers. Other pin names and unusual
reference prefixes may need direct review without a hint.

A connector with at least three connected non-shield pins and no connected
ground/return-like pin also appears for review. A shield connection does not
count as a signal return. This is a missing-context prompt; isolated interfaces
can be valid. If assigned nets have return-like names but the symbol pin
functions do not identify a return, the lint report shows those names as
context. It does not treat the net label as proof of the connector pin's role.

Design lint also reports an individual named supply or return pin when the
native netlist shows no net assignment and no repeated-function finding already
covers it. This catches a potentially forgotten connector power or return pin
even when there is no matching pin on another connector. It remains a review
hint because unused pins and isolated interfaces can be intentional.

The report also flags numbered return-like net names such as `0V CTRL 1` /
`0V CTRL 2` and `USB1_GND` / `USB2_GND`. Net-name hints are deliberately
narrow and do not include shield names. Every hint is `UNREVIEWED`: similar
names or functions are reasons to compare the approved pinout with the design,
not proof that the pins should be tied.

The separate [design lint lane](DESIGN_LINT.md) gives these patterns stable
finding fingerprints and project-owned review decisions. Native `verify` and
`ci --kicad` runs retain that lint report alongside the KiCad results.

Capture writes only under the project's ignored `build/` directory. A retained
native summary can be inspected with
`--native-summary build/<run>/<board-id>/summary.json` after its source,
toolchain, and netlist hashes are checked. Native PCB validation exports the
netlist even when the component contract is empty; it still fails that empty
contract and names any detected connector candidates in the failure.

## Record connector interface coverage

Design lint reports whether each symbol-backed connector candidate has a
project-owned interface pin map or a reasoned not-applicable decision. The
candidate scan recognizes numeric `J`, `P`, `X`, and `CN` references and
symbols from standard `Connector` or `Connector_*` libraries, excluding
`Connector:TestPoint*`. It can miss custom library aliases and can include
local jumpers or test headers; `UNASSESSED` never means that every physical
interface was found. When one custom symbol instance has a project-owned
interface review, instances using the same exact symbol are also listed for
inventory disposition. Each peer still needs its own interface map or
not-applicable review; matching symbol identity does not establish wiring.

The project manifest can bind a catalogued interface to a schematic component
and map each interface pin number to the component's pin number. Every other
exported symbol pin needs a reason in `unlisted_pin_reasons`. For example, a
shield or mounting pin can be accounted for there without asserting that it is
connected to signal return:

```json
{
  "connector_inventory_review": {
    "basis": "Reviewed the complete schematic component inventory for external interfaces"
  },
  "interfaces": ["service-serial"],
  "connector_reviews": [
    {
      "reference": "J1",
      "disposition": "interface",
      "basis": "Reviewed service connector pinout revision C",
      "interface_id": "service-serial",
      "pin_map": {"1": "1", "2": "2"},
      "unlisted_pin_reasons": {"3": "Shield pin reviewed separately"}
    },
    {
      "reference": "J2",
      "disposition": "not_applicable",
      "basis": "Local manufacturing jumper; not an external interface"
    }
  ]
}
```

This is a fragment of `project.json`. `connector_inventory_review` records the
project owner's review basis for the complete schematic interface inventory.
Every external or local connector candidate still needs an entry in
`connector_reviews`; use `not_applicable` for a reviewed component that is not
an external interface. If the project has no external connectors, the basis
can say that the complete schematic inventory was reviewed and none are
present. `service-serial` must exist in the configured interface catalog.
Coverage compares catalog pin numbers and the complete pin-number inventory
exported for each symbol; it does not compare signal names or assert net
relationships. Use the electrical contract's `pin_connectivity` and
`grounding` sections for required common nets, isolated domains, and grounds.

## Scope comparisons between similar connector instances

Some boards use the same generic connector symbol for separate interfaces,
such as UART1 and UART2 headers. A reviewed connector can set
`peer_assignment_group` to define which instances the generic pin-assignment
heuristics should compare. Each group needs a `peer_assignment_basis`:

```json
{
  "interfaces": ["uart-header"],
  "connector_reviews": [
    {
      "reference": "J1",
      "disposition": "interface",
      "basis": "Reviewed UART1 connector pinout revision A",
      "interface_id": "uart-header",
      "pin_map": {"1": "1", "2": "2", "3": "3"},
      "peer_assignment_group": "uart1",
      "peer_assignment_basis": "J1 is the UART1 interface"
    },
    {
      "reference": "J2",
      "disposition": "interface",
      "basis": "Reviewed UART2 connector pinout revision A",
      "interface_id": "uart-header",
      "pin_map": {"1": "1", "2": "2", "3": "3"},
      "peer_assignment_group": "uart2",
      "peer_assignment_basis": "J2 is the UART2 interface"
    }
  ]
}
```

Groups scope comparisons of generic pin numbers and non-return/supply pin
functions. Return and supply comparisons remain cross-group, so a split ground
or mismatched same-domain supply still receives a review prompt. Group
membership does not declare nets common or separate. Every participating
connector needs a current, complete group review before scoping takes effect;
an unreviewed, incomplete, or stale peer restores the broad comparison.

The interface catalog can give each pin an optional heuristic role: `signal`,
`return`, `supply`, `shield`, or `other`. A complete source-matched map can
refine connector checks when native pin-function text is absent, generic
(`Pin_N`), or numeric-only: `return` roles participate in the repeated-return
and connected-return hints, while unconnected `return` and `supply` roles
participate in their pin-specific hints. Generic or numeric-only supply
contacts across connector symbols also receive a repeated-pin review prompt
when their exact authored `voltage_domain` values match and their net
assignments differ. This can expose a split supply that native pin functions
do not name. Stale, incomplete, or digestless coverage is ignored for this
role refinement. Matching roles and domains only identify a review candidate;
they do not declare common nets, bonds, or required connectivity. Independent,
switched, ORed, or isolated sources can be intentional. Use the electrical
contract's `pin_connectivity` and `grounding` sections to author required
relationships.

The project can also opt in to the return-distribution heuristic described in
the [design lint guide](DESIGN_LINT.md#review-connector-return-contact-distribution).
For that check, classify every mapped pin. Its threshold counts only `signal`
and `return`; the other roles are excluded and shown in the report. These
classification roles still do not declare that return contacts share a net.

The report distinguishes `COMPLETE`, `INCOMPLETE`, `UNDECLARED`,
`SCOPE_UNREVIEWED`, and `UNASSESSED` coverage. An unreviewed or incomplete
candidate, missing inventory review, or empty unassessed scope keeps design
lint at `REVIEW` even if all heuristic findings were ignored. `COMPLETE` means
the project recorded its inventory review and the declared interface and
symbol pin inventories were accounted for; it does not independently prove
that the review found every real-world interface.

## Author the connection requirement

In the project-owned electrical contract, a required `pin_connectivity`
section lists reviewed pin relationships. For three hypothetical connector
power pins that must share the approved `+5V` net:

```json
{
  "pin_connectivity": {
    "mode": "required",
    "basis": "Approved synthetic connector pinout and electrical-owner review",
    "rules": [
      {
        "id": "shared-port-power",
        "basis": "All three ports receive the same reviewed rail",
        "topology": "common_net",
        "pins": ["J1.1", "J2.1", "J3.1"],
        "net": "+5V"
      }
    ]
  }
}
```

These references are synthetic, not a USB or serial connector pinout. The
`net` field names an approved rail; omitting it checks only that the pins
share one net. Include a supply-source pin in the rule or use the reviewed
net name when the source connection matters. A missing pin, a pin on several
nets, the wrong net, or an unknown component fails the check.

For intentionally independent outputs, use `"topology": "separate_nets"`
with the selected pins and no `net` field. This fails if those pins become
shorted onto one schematic net. A repeated function name alone never selects
`common_net` or `separate_nets`. To record an intentionally unused pin, use
`"topology": "unconnected"` with the exact pin and a basis explaining the
approved disposition. The check fails if the pin later receives a schematic
net assignment. It also requires native symbol pin inventory for each referenced
component; absent inventory fails closed as missing evidence, and a stale pin
reference fails against the available inventory. Pin relationships can cover
power, returns, and other reviewed connector functions. The separate
`grounding` section still covers declared ground domains and component
ground-pin review.

```json
{
  "id": "reserved-mode-pin",
  "basis": "This assembly does not populate the optional mode connection",
  "topology": "unconnected",
  "pins": ["J1.7"]
}
```

New `kicad-team electrical --init` contracts start with `pin_connectivity`
pending, so the owner must review it. Older contracts without the section
remain valid for compatibility, but their electrical report makes no claim
about connector pin relationships. Review and add the section before relying
on this check for a production handoff.

## Regression cases and limits

The tooling regressions use only synthetic connector symbols and netlists:

- Three approved `PWR` pins must share `+5V`; one unconnected or on another
  net fails the reviewed relationship.
- Three approved return pins must share `GND`; three separate return nets or
  one stray pin fail the exact ground-domain requirement.
- Two connector supplies are intentionally independent; separate nets pass
  and a newly shared net fails the reviewed relationship.

Run native and electrical verification against the exact source intended for
release:

```sh
kicad-team verify --project <board-id> --depth electrical --format text
```

The checks establish schematic net membership or an explicitly required
unconnected disposition. A specified net tie or bond needs its own schematic
and PCB review; a direct `common_net` rule does not describe an indirect path.
Review connector pads, planes, and reference points on the PCB, then test
first-article continuity according to the approved pinout before production
acceptance.

[kicad-erc]: https://docs.kicad.org/10.0/en/eeschema/eeschema.html
