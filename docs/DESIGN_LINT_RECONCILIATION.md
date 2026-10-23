# Design-lint finding reconciliation

This guide describes the source-bound baseline workflow, including finding
identity, reconciliation, review dispositions, and refresh behavior.
The [design-lint guide](DESIGN_LINT.md) links here from its overview.

## Reconcile findings against a source-bound baseline

Use a saved `DesignLintReport` to see what changed after a project edit:

```sh
kicad-team design-lint \
  --root . \
  --project controller \
  --native-summary build/validation/controller/summary.json \
  --baseline-report .kicad-team/design-lint-baseline.json
```

The baseline path is relative to `--root`. The CLI reads the current native
summary and compares it with that saved report. MCP exposes the same typed
comparison as `reconcile_design_lint`, taking the prior report as serialized
JSON and the current summary as a repository-relative generated artifact.

The comparison requires both reports to identify the same project and include
source hashes, a native netlist hash, and a design-lint catalog digest. It
reports findings as `PERSISTING`, `NEW`, `RECLASSIFIED`, or
`NO_LONGER_REPORTED`. Both copies of a changed finding remain in the result,
with their fingerprints, evidence, mode, disposition, and reason. Report
status, policy, catalog, manifest, native-validation, stale-ignore, and issue
changes are also surfaced. A changed or no-longer-reported finding returns
`REVIEW`; persistent open findings and a current report that remains `REVIEW` or
`FAIL` also keep the result at `REVIEW`. Missing or mismatched evidence returns
`BLOCKED`.

This is a comparison gate, not a finding filter. Persistent `IGNORED` and
`RULE_OFF` findings remain visible, and a `NO_LONGER_REPORTED` transition does
not by itself mean a defect was fixed or a dismissal was approved. Review the
source and independently authored requirements before accepting a change.
`UNCHANGED` means no findings changed, the current lint report is `PASS`, and
the listed policy context matches the baseline; persistent ignored and
rule-off findings are still printed. It does not mean the design is electrically
correct or ready to build. Keep project-specific reports and their review
decisions in the project repository; this tooling repository stores only
synthetic regression cases.

Each successful native inspection also stores a source-hashed pin-connectivity
snapshot in the lint report. Reconciliation compares each pin's exported net
name and peer pins, so an open, moved, split, or newly joined assignment is
listed even when no heuristic finding changed. It also compares each pin's
native function and electrical type, so symbol-role edits remain visible when
the pin-to-net topology is unchanged. A net-label or pin-role change is review
evidence, not a claim that wiring is wrong. Incomplete pin inventories or
native pin-type metadata produce a `PARTIAL` comparison. Partial snapshots list
metadata changes only where both reports retain the same field; added or
removed pins require complete connectivity coverage. Older baselines without
pin-role metadata require review before they can support a complete metadata
comparison. Different exact KiCad versions or toolchain images block the
comparison. These snapshots record prior source state for regression review;
they do not specify required wiring or replace a project-authored contract.

Connector checks share one bounded candidate set: numeric `J`, `P`, `X`, or
`CN` references, symbols in KiCad's standard `Connector` libraries, and exact
references in the project's reviewed interface map. This identity is shared by
connector pin, power-input, decoupling, return-anchor, and USB-C review checks,
including connectors that use a nonstandard designator. Connector inventory
coverage additionally includes every instance with the same native symbol
identity as a reviewed custom connector, so an omitted peer needs its own
interface or not-applicable disposition. That expansion only identifies
coverage candidates. A custom symbol's pin roles and required net relationships
still come from project-authored requirements; candidate classification alone
never joins nets or declares that pins must match.

The first rules are:

- `connector.repeated_pin_function` flags pins with the same meaningful native
  pin-function role across two or more instances of the same connector symbol
  when they use different nets
  or a pin has no net. It also compares ground/return-like functions across
  connector symbols and within one connector, and compares a narrow set of
  named supply functions across connector symbols. Findings ask whether returns
  should be common, bonded, or intentionally isolated, and whether supply pins
  share a rail, are separate, or have independent sources. Connector instances
  listed as DNP in the native netlist are excluded from these comparisons.
  Generic KiCad `Pin_N` labels are placeholders, not known roles; absent a
  complete, current project interface map, those pins flow to the lower-
  confidence exact-symbol peer assignment rules. A source-matched interface
  map can supply a `return` role for a generic, absent, or numeric-only native
  function. This can compare returns across different connector symbols and
  lets the missing-return check recognize a mapped contact. Numeric pin-function
  text such as `7` can still help compare the same contact across instances of
  that exact symbol, but it does not identify an electrical role on its own or
  say that the contacts must be connected. The review prompt survives
  arbitrary net-label changes. Synthetic native exports verify this with
  numeric `7`/`9` pin functions and neutral net names on digest-pinned KiCad
  10.0.0 and 10.0.5; a common-net control clears only the mismatch prompt and
  keeps the missing pin-role coverage visible. When a mapped return role
  contributes to a finding, its evidence names the per-pin role source; the
  connector-coverage section carries the interface-catalog digest. The finding
  states that this classification does not require commonality.
  A source-matched map can also compare generic or numeric-only `supply`
  contacts across connector symbols when both reviewed interface pins have the
  same exact `voltage_domain` text. Different or missing nets produce a
  `REVIEW` prompt; a common-net control clears it, and a different authored
  domain keeps separate rails out of the group. A role and voltage domain do
  not prove that the nets must be common: separately sourced, switched, ORed,
  or isolated supplies can be intentional. Project-authored `pin_connectivity`
  remains the authority for required relationships. Synthetic native exports
  with generic `Pin_1` and `Pin_9` contacts verify the split, common-net, and
  distinct-domain cases with neutral net names on pinned KiCad 10.0.0 and
  10.0.5. See the [pair](../tests/fixtures/design_lint/cohort-mapped-connector-supplies/README.md).
  A complete connector review can also assign a `peer_assignment_group` and
  `peer_assignment_basis`. When every participating connector has current
  group evidence, generic and signal-function comparisons run only
  within matching groups. Return and supply comparisons remain cross-group so
  separately classified UART or USB ports can still surface split returns or
  same-domain supply assignments. Missing or stale group evidence restores
  the broad comparison. Group membership scopes review candidates; it does not
  mean matching nets are required.
- `connector.peer_pin_assignment_outlier` compares the same pin number across
  fitted instances of an exact shared library symbol when at least one peer
  has no meaningful native pin-function metadata because the role is absent
  or a generic `Pin_N` placeholder. It also compares distinct connector
  symbols when they share a nonempty native `PART_ID` and have matching
  nonempty value and footprint, complete identical pin inventories, and
  matching nonempty function and electrical-type metadata for every pin. This
  guarded alias path asks for review when a peer is unconnected while another
  peer is assigned, including a group of only two connector instances, or
  differs from the unique most-common net assignment shared by at least two
  instances. Tied assigned-net patterns do not nominate an arbitrary outlier
  and are left to `connector.peer_pin_assignment_divergence`. This can
  localize an open generic contact that named-function checks cannot identify.
  Digest-pinned native fixtures verify the minimum two-connector open-contact
  case, an explicit no-connect-marker fault, and the common-net control on
  KiCad 10.0.0 and 10.0.5. The marked-open pin still receives a REVIEW prompt:
  an accidental marker can hide a missing contact from ERC. The finding does
  not say that matching pins must share a net.
  The PART_ID alias fault and common-assignment control also passed repeated
  exports on both pinned versions; the normalized typed netlists match across
  versions.
  Matching symbol or `PART_ID` identity does not prove that the pins must share
  a net; isolated ports and intentionally unused contacts remain valid. Alias
  groups with missing or inconsistent identity, inventory, or pin metadata are
  skipped and included in the coverage summary. DNP connector instances are
  excluded. Fully specified meaningful pin groups stay with
  `connector.repeated_pin_function` to avoid duplicate findings. Fully
  reviewed connector sets may use distinct `peer_assignment_group` values to
  keep independent interfaces, such as separate UART channels, out of one
  another's generic pin-number comparisons. A missing or stale group on any
  participating connector keeps the broad comparison active.
- `connector.peer_pin_assignment_divergence` adds a lower-confidence prompt
  when fitted instances of the same exact connector symbol assign the same pin
  number to different nets, or when guarded `PART_ID` aliases with matching
  identity, pin inventories, and per-pin metadata do so. All compared contacts
  must be assigned, at least one peer must have unknown pin-function metadata
  (absent or generic `Pin_N`), fewer than two peers may have meaningful role
  metadata, and no unique most-common assignment may exist. It covers two-peer, tied, or
  all-distinct assignments that the outlier rule cannot localize to one unique
  most-common net. Review the external pinout to
  decide whether those contacts have a common role; the checker does not assume
  they should be joined. It ignores DNP instances, leaves open contacts to the
  outlier and named-pin rules, and supports the same per-project `review`,
  `block`, `off`, and exact-ignore decisions. Source-matched peer groups scope
  fully reviewed connectors; partial group coverage does not silence the prompt.
- `connector.generic_peer_pin_all_open` is an opt-in, default-off prompt for a
  generic native `passive` or signal contact left unassigned on every fitted
  peer of one exact connector symbol when the peers have complete identical pin
  inventories and share another assigned pin. Signal electrical types covered
  are `input`, `output`, `bidirectional`, `tri_state`, `open_collector`, and
  `open_emitter`. It also compares
  cross-symbol peers only when they share a native `PART_ID` and have matching nonempty value,
  footprint, complete pin inventories, and per-pin function and electrical-type metadata. It
  asks the reviewer to check the approved pinout for an intentionally unused contact or a missing
  connection. The shared pin is context only: a native signal type describes
  KiCad electrical behavior but does not identify the interface function or
  required net. DNP peers, incomplete identities or inventories, named pin
  functions, mapped return/supply roles, and `power_in`, `power_out`, `free`, or
  `unspecified` electrical types are excluded.
  Project policy can set `review`, `block`, or `off`, and exact reviewed findings use the usual
  ignore lifecycle. Synthetic fault/control schematics are exercised through the digest-pinned KiCad
  10.0.0 and 10.0.5 native connector lane; see the
  [exact-symbol fixture record](../tests/fixtures/design_lint/generic-peer-pin-all-open-native/README.md),
  [signal-pin fixture record](../tests/fixtures/design_lint/generic-peer-signal-pin-all-open-native/README.md),
  and [cross-symbol PART_ID fixture
  record](../tests/fixtures/design_lint/connector-peer-part-id-native/README.md).
  The schematic assignment does not establish routed copper continuity or off-board wiring.
- `connector.footprint_named_power_input_open_outlier`,
  `connector.footprint_named_signal_input_open_outlier`, and
  `connector.footprint_named_power_output_open_outlier` and
  `connector.footprint_named_signal_output_open_outlier` prompt for review when
  an explicit native input, power-output, or signal-output contact is assigned
  on some exact footprint/value peers and open on another, with complete
  matching pin evidence and a separate common-net anchor. The power-input rule
  accepts an explicit native `power_in`; the signal-input rule accepts an
  explicit native `input`; the power-output rule accepts an explicit native
  `power_out`; the signal-output rule accepts an explicit native `output`.
  Generic names,
  recognized supply and return functions, DNP instances, PART_ID groups,
  ambiguous or split assignments, and groups without an anchor are excluded.
  Similarity only identifies a review candidate; it does not establish a
  shared role or required connection. The prompt supports project `review`,
  `block`, `off`, and exact-fingerprint ignore policy.
- `connector.footprint_named_signal_mode_dependent_open_outlier` prompts for
  review when a named `bidirectional`, `tri_state`, `open_collector`, or
  `open_emitter` contact is assigned to one exact net on some footprint/value
  peers and left open on another, with a separate common-net anchor. Input and
  output pins remain covered by their dedicated rules. Similarity only prompts
  inspection; it does not establish a shared role or required connection.
- `connector.footprint_named_passive_open_outlier` prompts for review when an
  explicitly named native passive contact is assigned to one exact net on
  some footprint/value peers and left open on another, with a separate
  common-net anchor. Generic, supply/return, active signal, ambiguous,
  incomplete, and unanchored cases are excluded. Similarity does not establish
  that contacts share a role or must connect.
- `connector.footprint_named_signal_assignment_divergence` prompts for review
  when a non-generic native signal pin on matched footprint/value connector
  aliases is assigned to different nets while another pin has one exact
  common-net assignment. Only native `input`, `output`, `bidirectional`,
  `tri_state`, `open_collector`, and `open_emitter` pins qualify. Different
  signal nets can be intentional; the finding does not say they should be
  joined or that either assignment is wrong.
- `connector.footprint_named_power_input_assignment_divergence` prompts for
  review when a non-generic native `power_in` pin on matched footprint/value
  connector aliases is assigned to different nets while another pin has one
  exact common-net assignment. Separate sources, switched rails, and isolated
  power domains can be intentional; the finding does not say the rails should
  be joined.
- `connector.footprint_named_power_output_assignment_divergence` prompts for
  review when a non-generic native `power_out` pin on matched footprint/value
  connector aliases is assigned to different nets while another pin has one
  exact common-net assignment. Separate sources, switched outputs, and
  isolated power domains can be intentional; the finding does not say the
  outputs should be joined.
- `connector.footprint_named_passive_assignment_divergence` prompts for review
  when an explicitly named native passive contact on matched footprint/value
  connector aliases is assigned to different exact nets while another pin has
  one exact common-net assignment. Distinct passive domains can be intentional;
  the finding does not say either assignment is wrong or that the nets should
  be joined.
- `connector.footprint_named_power_input_all_open` prompts for review when an
  explicit non-generic native `power_in` contact is unassigned on every matched
  footprint/value connector alias while another pin has one exact common-net
  assignment. An input can be intentionally unused or isolated; this prompt
  does not require the contacts to be connected.
- `connector.footprint_named_power_output_all_open` prompts for review when an
  explicit non-generic native `power_out` contact is unassigned on every
  matched footprint/value connector alias while another pin has one exact
  common-net assignment. An output can be intentionally unused or isolated;
  the prompt does not require the contacts to connect.
- `connector.footprint_named_signal_all_open` prompts for review when an
  explicit non-generic signal contact with native `input`, `output`,
  `bidirectional`, `tri_state`, `open_collector`, or `open_emitter` type is
  unassigned on every matched footprint/value connector alias while another
  pin has one exact common-net assignment. A signal can be intentionally
  unused or isolated; the prompt does not require the contacts to connect.
- `connector.footprint_peer_pin_all_open` extends this prompt to fitted,
  PART_ID-free connector aliases only when distinct native symbols have exact
  nonempty value and footprint matches, complete identical pin inventories,
  matching native pin functions and electrical types, and another pin with
  one exact shared net assignment. Generic passive or signal contacts left
  open on every peer become an opt-in, default-off finding. A shared footprint
  and net anchor are review clues, not proof of identical roles or required
  wiring. DNP, named pins, native power/free/unspecified types, incomplete or
  ambiguous evidence, and unanchored groups are excluded. The project can
  select review, block, or off and use exact-fingerprint ignores. The
  [tooling-owned fixture record](../tests/fixtures/design_lint/connector-footprint-alias-native/README.md)
  covers assigned, mixed-open, and all-open cases on KiCad 10.0.0 and 10.0.5.
- `connector.footprint_peer_pin_metadata_assignment_divergence` reviews a
  split assignment when matched connector aliases have complete pin inventories
  but present native function or electrical-type metadata differs. The missing-
  metadata case is handled separately below. Distinct connector roles and
  isolated interfaces may be intentional, so this prompt does not say the nets
  should be joined. Coverage reports count complete-but-different metadata
  separately from missing or unnamed metadata; the former is partially
  evaluated evidence, while the latter remains incomplete evidence.
- `connector.footprint_peer_pin_missing_metadata_assignment_divergence` reviews a split assignment
  when matched connector aliases have complete inventories but a target pin has missing, blank, or
  KiCad unnamed (`~`) function or electrical-type metadata. It requires one exact net per peer and a
  separate pin on one exact common net in the same peer scope. Peers can be identified by matching
  nonempty value and footprint when both lack PART_ID, or by matching nonempty PART_ID, value, and
  footprint after trimming and case-folding. A PART_ID match is only a similarity clue. Common,
  open, ambiguous, unanchored, incomplete-inventory, DNP, and mismatched-PART_ID groups do not
  trigger. The default is REVIEW; project policy can select REVIEW, BLOCK, or OFF and
  exact-fingerprint ignores. This asks for exact pinout and project-requirement review; it does not
  infer a shared role or tell the user to join nets. The no-PART_ID and case-insensitive
  matching-PART_ID native fault/control pairs are documented in the
  [base fixture README](../tests/fixtures/design_lint/connector-footprint-peer-missing-metadata-native/README.md)
  and
  [PART_ID fixture README](../tests/fixtures/design_lint/connector-part-id-peer-missing-metadata-native/README.md).
- `connector.peer_power_input_open_assignment` and
  `connector.peer_power_input_named_all_open` compare an explicit, unrecognized
  native `power_in` pin across distinct connector symbols with a guarded shared
  `PART_ID`, matching component identity, complete pin inventories, and matching
  per-pin metadata. The first prompts when the aliases mix one-net and open
  assignments; the second prompts when every alias is open. Both default to
  REVIEW. Matching aliases do not establish that the contacts should share a
  net; exact-symbol peers remain with `connector.repeated_pin_function`.
- `connector.peer_power_input_named_assignment_divergence` prompts when the
  same explicit, unrecognized native `power_in` pin on fully assigned fitted
  aliases with guarded shared PART_ID and matching complete pin metadata is
  assigned to different nets. Common-net, open, mixed, ambiguous, and
  recognized supply/return cases stay with their existing handling. The
  configurable REVIEW prompt asks whether the split is intentional; it does
  not instruct the project to join the nets.
- `connector.peer_power_output_open_assignment` uses the same guarded alias
  identity and metadata checks for explicit, unrecognized native `power_out`
  pins. It prompts when one fitted symbol alias has a single net assignment and
  another is open. The all-open output case is covered separately by
  `connector.peer_power_output_named_all_open`. As with power-input aliases,
  matching metadata does not require a shared net.
- `connector.peer_power_output_named_all_open` prompts when the same explicit,
  unrecognized native `power_out` pin is open on every fitted alias with a
  guarded shared PART_ID, matching value and footprint, complete pin inventory,
  and matching per-pin metadata. It is a configurable REVIEW prompt for pinout
  review; it does not establish that a contact is required or that aliases
  should share a net.
- `connector.peer_power_output_named_assignment_divergence` prompts when the
  same explicit, unrecognized native `power_out` pin on fully assigned fitted
  aliases with guarded shared PART_ID and matching complete pin metadata is
  assigned to different nets. Common-net, open, mixed, ambiguous, and
  recognized supply/return cases stay with their existing handling. The
  configurable REVIEW prompt asks whether the split is intentional; it does
  not instruct the project to join the nets.
- `connector_peer_pin_coverage` is an observability summary for these existing
  connector heuristics. It binds candidate and fitted connector counts,
  exact-symbol and guarded `PART_ID` alias comparison counts,
  common/different/open assignments, native function-metadata availability,
  repeated-function group outcomes, emitted finding counts, and the native
  netlist digest. Alias coverage records candidate identities, skip reasons,
  eligible groups, and compared pin groups. Its status distinguishes no
  candidate connectors, candidates that are all DNP, no comparable peers, no
  comparable pin groups, incomplete pin inventories, and evaluated groups. A
  PART_ID alias summary separates missing or unnamed pin metadata from complete
  but differing function or electrical-type metadata. A quiet evaluated result
  shows which bounded peer comparisons ran; it does not prove that matching
  pins must share a net or that every physical connector was identified.
- `component.repeated_supply_pin_function` flags recognized matching supply
  functions on one fitted non-connector component when assigned pins use
  different or ambiguous schematic nets. It asks whether the split is
  intentional (for example, a filtered supply) or a missing connection. An
  unassigned member is reported by the more specific component supply-pin
  finding instead.
- `component.peer_power_pin_assignment_divergence` compares a shared pin
  number and recognized supply or return function across fitted non-connector
  instances of the exact same symbol. It also compares distinct symbols that
  carry the same native `PART_ID`, but only when value, footprint, complete pin
  inventory, and each pin's function and electrical type match. It prompts
  only when each compared pin has exactly one net assignment and those nets
  differ. The matching symbol or part identity is a review clue: separate
  rails or isolated return domains can be intentional, and the rule never
  joins nets. DNP peers, incomplete metadata, unknown functions, ambiguous
  assignments, and open power pins are excluded; open pins stay with the
  component unconnected-pin checks.
- `component.peer_power_input_assignment_divergence` reviews fitted
  non-connector instances of the exact same native symbol when a generic
  `power_in` pin has different single-net assignments. It requires complete,
  identical native pin inventories and consistent generic function metadata.
  The matching symbol and `power_in` type do not establish that the rails must
  be common; connectors, DNP components, named pins, open assignments, and
  incomplete inventories are handled elsewhere or excluded.
- `component.peer_power_input_named_assignment_divergence` reviews comparable
  fitted non-connector peers when the same explicit, unrecognized native
  `power_in` function is assigned to different single nets. Peers must have
  complete matching pin inventories and identical function text; they may
  match by exact symbol or a guarded shared `PART_ID` with matching value and
  footprint. A split may be intentional, so this prompt does not establish
  that the nets should be common. Generic functions, recognized supply/return
  roles, and open assignments remain with their specific checks.
- `component.peer_power_input_open_assignment` prompts when an explicit,
  otherwise unrecognized native `power_in` pin is assigned on some comparable
  fitted non-connector peers and left open on another. It requires complete
  matching pin inventories, identical function text, and unambiguous
  assignments. Peers may match by exact native symbol or a guarded shared
  `PART_ID` with matching value and footprint. Generic functions and recognized
  supply/return names stay with their existing checks. The default mode is
  REVIEW because an open pin may be intentional; peer identity does not
  establish that pins must share a net. The digest-pinned synthetic examples
  are documented in the [fixture README][peer-open-fixture].
- `component.peer_power_input_named_all_open` prompts when the same explicit,
  unrecognized native `power_in` function is open on every comparable fitted
  non-connector peer. It requires complete matching pin inventories, matching
  native electrical types, identical function text, and exact-symbol or guarded
  `PART_ID` identity. Unlike a partially open group, it does not need an
  assigned peer as an anchor; it reports only a review question and does not
  establish that any pin must be connected. Generic functions, recognized
  supply/return roles, DNP peers, connectors, ambiguous assignments, and
  incomplete or mismatched groups remain excluded. The minimal synthetic
  fault/control sources and their hashes are documented in the
  [all-open fixture README][peer-all-open-fixture].
- `component.peer_power_output_unconnected` prompts when one fitted
  non-connector has an unassigned native `power_out` pin while a comparable
  fitted peer has one unambiguous net assignment. Peers may share an exact
  native symbol, or carry the same native `PART_ID` across distinct symbols
  with matching values and footprints. The cross-symbol case also requires
  identical per-pin function text, including identical generic placeholders
  such as `Pin_2`; a generic placeholder is structural evidence only and does
  not identify the electrical role. It covers the open-output case left outside
  the assigned-pin divergence rule. Review whether the output is intentionally
  unused or its assignment is missing; comparable components do not require
  their outputs to share a net. DNP peers, connector candidates, incomplete or
  mismatched pin inventories, missing electrical-type metadata, ambiguous
  assignments, and recognized named supply/return pins are outside this
  prompt. `PART_ID` and symbol identity are review evidence, not proof of the
  intended pin connection. Shield-labelled native power outputs remain
  eligible for review because there is no component-level unconnected-shield
  rule. It does not establish output function, component operation, current
  capacity, PCB copper continuity, off-board wiring, or physical population.
- `component.peer_signal_output_unconnected` prompts when a fitted non-connector component with an
  comparable peer has an unassigned native `output` pin while the matching pin on another fitted
  peer has one unambiguous net assignment. Comparability uses an exact shared symbol, or the same
  native `PART_ID` across distinct symbols when values, footprints, complete pin inventories, native
  types, and per-pin function text matches. Identical generic placeholders such as `Pin_2` provide
  only structural evidence, not an electrical role. This asks whether the open
  signal output is intentional or missing a connection; matching identities do
  not require the outputs to share a net. DNP peers, connector
  candidates, incomplete or mismatched pin inventories, missing electrical-type metadata, ambiguous
  assignments, and recognized named supply/return pins remain outside the predicate. This does not
  establish output function, PCB continuity, off-board wiring, or physical population.
  Digest-pinned synthetic native fault/control fixtures and hashes are in
  [the peer signal-output fixture notes](../tests/fixtures/design_lint/component-peer-signal-output-native/README.md).
- `component.peer_signal_input_unconnected` prompts when a fitted non-connector component with a
  comparable peer has an unassigned native `input` or `input_low` pin while a matching peer pin has
  one unambiguous net assignment. Comparability uses an exact shared symbol, or the same native
  `PART_ID` across distinct symbols when values, footprints, complete pin inventories, native types,
  and per-pin function text match. Identical generic placeholders provide structural evidence only.
  Review whether the open
  input is intentional or missing a connection; identical inputs do not need a common net.
  Recognized supply, return, reset, enable, and boot pins remain with their specific rules.
  Digest-pinned synthetic native fault/control fixtures and hashes are in
  [the peer signal-input fixture notes](../tests/fixtures/design_lint/component-peer-signal-input-native/README.md).
- `component.peer_bidirectional_pin_unconnected` applies the same bounded review to a native
  `bidirectional` pin, including bus functions such as SDA. Comparability uses an exact shared
  symbol, or the same native `PART_ID` across distinct symbols when values, footprints, complete pin
  inventories, native types, and per-pin function text match. Identical generic placeholders provide
  structural evidence only. It does not establish bus membership, require
  a common net, or prove a source, off-board path, or PCB connection. DNP peers, all-open groups,
  connectors, ambiguous assignments, and other native electrical types are outside the predicate.
  Digest-pinned synthetic native fault/control fixtures and hashes are in
  [the peer bidirectional-pin fixture notes](../tests/fixtures/design_lint/component-peer-bidirectional-native/README.md).
- `component.generic_peer_pin_all_open` is an opt-in, default-off review prompt for a native
  `passive` or signal pin with absent, blank, `Pin_N`, or numeric-only function metadata, left
  unassigned on every fitted non-connector peer with a complete matching pin inventory, when
  another pin has the same exact single-net assignment across the group. Peers must use the exact
  same native symbol or share a native `PART_ID` with matching
  nonempty value and footprint and identical per-pin function and electrical-type metadata. Named
  supply and return pins, `power_in`, `power_out`, `free`, `unspecified`, DNP instances, connector
  candidates, incomplete inventories, and ambiguous assignments are excluded. The shared pin is
  context for review only: neither peer identity nor common wiring proves that the open pin must
  connect. The reviewer should check the approved component requirements for an intentionally
  unused pin or missing connection. The
  [synthetic fixture record](../tests/fixtures/design_lint/component-peer-generic-all-open-native/README.md)
  documents the digest-pinned native fault and control. Coverage is source-bound to the native
  netlist; the result does not establish PCB copper continuity or physical population.
- `component.generic_peer_pin_mixed_open` is an opt-in, default-off review prompt for a native
  `passive`, `tri_state`, `open_collector`, or `open_emitter` pin with absent, `Pin_N`, or
  numeric-only function metadata, assigned to the same exact single net on at least two fitted
  non-connector peers while open on at least one other peer. It requires at least three peers with
  complete matching pin inventories and another pin assigned to the same exact single net across the
  entire group. Peers must use the exact same native symbol or share a native `PART_ID` with
  matching nonempty value and footprint and identical per-pin function and electrical-type metadata.
  Named supply and return pins, `power_in`, `power_out`, `free`, `unspecified`, DNP instances,
  connector candidates, incomplete inventories, and ambiguous assignments are excluded. Peer
  identity, assigned-peer consensus, and the shared pin provide comparison context only; they do not
  prove that the open pin must connect. The reviewer should check the approved component
  requirements for an intentionally unused pin or missing connection. The
  [synthetic fixture record](../tests/fixtures/design_lint/component-peer-generic-mixed-open-native/README.md)
  documents the digest-pinned native fault and control. Coverage is source-bound to the native
  netlist; the result does not establish PCB copper continuity or physical population. Native
  `input`, `output`, and `bidirectional` pins remain with their existing peer checks.
- `component.generic_peer_pin_assignment_outlier` is an opt-in, default-off review prompt for a
  generic `passive`, `tri_state`, `open_collector`, or `open_emitter` pin with exactly one net on
  each of at least three fitted non-connector peers. It requires complete matching inventories,
  consistent native function/type metadata, and a separate pin with the same exact single-net
  assignment across every peer. A target net must have a strict unique majority greater than half
  the peer group, with at least one differing assignment. Peers must use the exact same native
  symbol or share a native `PART_ID` with matching nonempty value and footprint and identical
  per-pin function and electrical-type metadata. Named functions, open or ambiguous assignments,
  DNP instances, connectors, and incomplete inventories are excluded. A majority and shared anchor
  are comparison clues only; they do not identify the pin's role or required net. Review the
  approved component requirements before treating a finding as a defect. The
  [synthetic fixture record](../tests/fixtures/design_lint/generic-component-peer-pin-assignment-outlier/README.md)
  documents the digest-pinned fault and control. The native netlist does not establish PCB copper
  continuity, off-board wiring, or physical population.
- The report gives each of these nine rules a bounded `component_peer_pin_coverage` entry
  tied to the native netlist digest. It counts exact-symbol groups, cross-symbol shared-`PART_ID`
  candidates and eligible groups, shared-identity groups excluded by value or footprint mismatch,
  inventory completeness, comparable and type/function-compatible pins, ambiguous assignments,
  open assignments, deduplicated candidates, findings, and suppressed candidates. The report names
  references in identity-incomplete groups and distinguishes that state from having no comparable
  peers. For `component.peer_power_input_assignment_divergence`, status distinguishes no eligible
  peers, incomplete inventories, unsupported pin types or functions, open assignments, and a
  completed comparison. The named power-input open-assignment rule also reports whether each
  comparable group has complete inventories, matching `power_in` types and explicit functions,
  and a mix of assigned and open peers. Status explains why a rule could not evaluate a group; it
  does not claim that every component or interface was recognized, or that matching peer pins must
  share a net.
- `component.two_pin_passive_same_net` prompts review when both pins of a
  fitted, exactly inventoried `Device:R`, `Device:C`, or `Device:L` family
  member, exact `Device:Varistor` or `Device:Varistor_US` symbol, or exact
  thermistor symbol (`Device:Thermistor`, `Device:Thermistor_NTC`,
  `Device:Thermistor_PTC`, `Device:Thermistor_US`,
  `Device:Thermistor_NTC_US`, or `Device:Thermistor_PTC_US`), resolve to the
  same schematic net. A custom symbol is included only when an
  exact project-authored `component_role_map` capacitor entry matches its
  `PART_ID`, symbol, footprint, and complete native pin inventory. The
  assigned net bypasses the passive in the schematic topology. Other custom
  symbols, incomplete pin inventories, multi-pin devices, DNP parts,
  unassigned pins, and ambiguous assignments are outside the predicate.
  Same-net parts can be intentional; project policy can review, block,
  disable, or exactly ignore the source-bound candidate.
- `component.two_pin_diode_same_net` prompts review when both pins of a
  fitted, exactly inventoried `Device:D` family symbol resolve to the same
  schematic net. The diode is bypassed in that schematic topology. `Device:LED`,
  custom symbols, incomplete pin inventories, multi-pin devices, DNP parts,
  unassigned pins, and ambiguous assignments are outside the predicate.
  Same-net diodes can be intentional; the project can review, block, disable,
  or exactly ignore the source-bound candidate. The hint does not establish
  the correct diode polarity, footprint mapping, PCB copper connection, or
  whether a diode is required.
- `component.two_pin_crystal_same_net` prompts review when a fitted, exactly inventoried
  `Device:Crystal` family symbol has two pins assigned to the same schematic net. This shorts the
  two terminals in the exported netlist. A bypassed or disabled crystal can be intentional, so the
  rule defaults to review and supports project-level `review`, `block`, `off`, and exact-ignore
  decisions. Active oscillator symbols, custom identities, multi-pin components, incomplete or
  ambiguous assignments, and DNP parts are outside the predicate. The report does not establish
  oscillation, frequency suitability, footprint pin mapping, physical population, or PCB copper
  connectivity. See the
  [synthetic source fixtures and hashes](../tests/fixtures/design_lint/two-pin-crystals/README.md).
- `component.two_pin_fuse_same_net` prompts review when both pins of a fitted,
  exactly inventoried `Device:Fuse` or `Device:Polyfuse` family symbol resolve
  to the same schematic net. The fuse is bypassed in that schematic topology.
  Custom symbols, incomplete pin inventories, multi-pin devices, DNP parts,
  unassigned pins, and ambiguous assignments are outside the predicate. A
  same-net fuse may be an intentional bypass; project policy can review, block,
  disable, or exactly ignore the source-bound candidate. The hint does not
  establish that a fuse is required, its rating, footprint mapping, or PCB
  copper connection.
- `component.two_pin_ferrite_same_net` prompts review when both pins of a
  fitted, exactly inventoried `Device:FerriteBead` or
  `Device:FerriteBead_Small` symbol resolve to the same schematic net. The
  bead is bypassed in that schematic topology.
  Custom symbols, incomplete pin inventories, multi-pin devices, DNP parts,
  unassigned pins, and ambiguous assignments are outside the predicate. A
  same-net bead may be an intentional bypass; project policy can review, block,
  disable, or exactly ignore the source-bound candidate. The hint does not
  establish component impedance, filtering effectiveness, footprint mapping,
  or PCB copper connectivity.
- `component.two_pin_switch_same_net` prompts review when both pins of a fitted,
  exactly inventoried `Switch:SW_SPST` symbol are assigned to one schematic
  net. The switch cannot separate those nets in the exported netlist, but that
  bypass may be intentional. Other switch identities, multi-pin symbols,
  incomplete or ambiguous inventories, and DNP parts are outside the
  predicate. The finding does not establish physical switch state, footprint
  pin mapping, assembly population, or PCB copper continuity. See the
  [synthetic native fixture record](../tests/fixtures/design_lint/two-pin-switches/README.md).
- `connector.no_connected_return` flags a connector with at least three
  connected non-shield pins and no connected ground/return-like symbol pin
  function or source-matched project interface return role. A shield pin alone
  does not satisfy this hint. Return-like net labels on those contacts appear
  as context, but a net label does not identify a connector pin role. When the
  symbol exposes a named or source-mapped but unconnected return pin, the
  pin-specific rule below reports it instead. Otherwise, review the approved
  pinout to decide whether a contact is a signal return or the interface is
  intentionally isolated. DNP connector instances are excluded.
- `connector.unconnected_supply_pin` and
  `connector.unconnected_return_pin` flag named connector supply or return pins
  that have no net assignment, unless the repeated-function rule already
  reports that pin. A complete, current project interface map can classify a
  generic, absent, or numeric-only native function as supply or return for
  these checks. DNP connector instances are excluded. Findings ask whether the
  pin is intentionally unused or a connection is missing.
- `connector.return_pin_on_positive_rail` prompts review when a fitted,
  source-identified connector return pin has exactly one assigned net and the
  shared positive-rail recognizer identifies that net from its name or an
  attached native pin function. A complete source-matched interface map can
  identify a return role when native function text is absent or generic.
  Shield pins, DNP connectors, open pins, and ambiguous assignments are
  excluded. A recognized rail name does not prove electrical potential or
  intended connectivity; project policy can review, block, disable, or exactly
  ignore the candidate. The approved connector pinout remains authoritative.
  Synthetic native fault/control sources are registered for the exact-version
  connector-return lane.
- `connector.unconnected_power_input` prompts review when a fitted connector
  pin has native electrical type `power_in`, a generic, absent, or numeric-only
  function, and no exported net assignment. This catches an open generic
  contact even when every matching connector peer is also open. The native type
  does not distinguish positive power from a reference or prove that the pin
  must be connected, so the rule defaults to review and accepts project-level
  `review`, `block`, `off`, or exact-fingerprint ignore decisions. Named supply
  and return pins remain with their more specific checks; DNP connectors are
  excluded. An open contact with an explicit no-connect marker still prompts
  review. See the
  [synthetic native fixture record](../tests/fixtures/design_lint/unconnected-generic-power-input-connector/README.md).
- `connector.unconnected_power_output` prompts review when a fitted connector
  pin has native electrical type `power_out`, a generic, absent, or
  numeric-only function, and no exported net assignment. The native type does
  not identify the contact's role or prove it must connect. Meaningful named
  functions are outside this generic rule, and DNP connectors are excluded.
  The rule defaults to `REVIEW` and accepts
  project `review`, `block`, `off`, or exact-fingerprint ignore decisions.
  When enabled, it owns the same open peer outlier to avoid duplicating the
  contact finding. See the
  [synthetic native fixture record](../tests/fixtures/design_lint/generic-connector-power-output/README.md).
- `component.unconnected_power_input` applies the same native electrical-type
  signal to fitted non-connector components whose `power_in` pin function is
  absent, generic, or numeric-only and has no exported net assignment. It also
  prompts when the pin has an explicit no-connect marker, and excludes DNP
  parts plus connector candidates so their existing rules retain ownership.
  The electrical type does not distinguish positive power from reference or
  prove the pin must connect; the rule defaults to `REVIEW` and supports
  project-level `review`, `block`, `off`, or exact-fingerprint ignore
  decisions. Named supply and return pins remain with their specific checks.
  See the
  [synthetic native fixture record](../tests/fixtures/design_lint/generic-component-power-input/README.md).
- `component.unconnected_power_output` prompts review for a fitted,
  non-connector component pin that KiCad types as `power_out`, has a generic,
  absent, or numeric-only function, and receives no exported net assignment.
  Comparable open outputs remain with the more specific peer rule; named
  outputs, connectors, and DNP components are excluded. The native type does
  not establish the pin's purpose or prove it must connect, so this defaults to
  `REVIEW` and accepts project `review`, `block`, `off`, or exact-fingerprint
  ignore decisions. The synthetic native fault/control pair is exported twice
  on pinned KiCad 10.0.0 and 10.0.5. See the
  [synthetic native fixture record](../tests/fixtures/design_lint/generic-component-power-output/README.md).
- `component.unconnected_supply_pin` and
  `component.unconnected_return_pin` apply the same named-pin coverage to
  non-connector components, including IC power pins. They only flag pins with
  no net assignment; they do not prove that an assigned pin is on the correct
  rail or that the rail has a valid source. A focused exact-native lane exports
  the synthetic open-VDD fault and assigned control twice on pinned KiCad
  10.0.0 and 10.0.5; tag `v0.5.0rc158` passed hosted acceptance (run
  `38252361023`). The separate named return-pin gate passed on
  `v0.5.0rc159` (run `38253423642`). See the
  [named component pin fixture record](../tests/fixtures/design_lint/unconnected-named-component-pins/README.md).
- `component.led_directly_across_supply_and_return` prompts review when a
  fitted exact `Device:LED` symbol has two inventoried pins assigned directly
  to distinct, recognized positive-supply and return nets. It does not
  calculate LED current or resistor value, and it cannot see current limiting
  inside a source, driver, or off-board circuit. A resistor across the same
  two rails is parallel to the LED and does not suppress the finding. Custom
  LED symbols, addressable/multi-die LEDs, ambiguous roles, incomplete pins,
  and unrecognized rail names are outside the predicate. Project policy can
  review, block, disable, or exactly ignore the candidate.
  Synthetic direct-rail, series-resistor, and parallel-resistor schematics are
  exported and checked against the same rule on pinned KiCad 10.0.0 and 10.0.5;
  the native lane does not run ERC. See the
  [fixture trial and native regression record](../tests/fixtures/design_lint/cohort-led-resistor/README.md).
- `component.led_directly_driven_from_output` prompts review when a fitted
  exact `Device:LED` shares one terminal net directly with a fitted native
  output-capable pin and the other terminal is directly on a recognized supply
  or return. A fitted positive-value resistor between an intermediate
  return-like LED net and a separate recognized return suppresses this direct
  topology prompt; that does not assess resistor adequacy. A custom symbol can
  join this rule only through `design_lint.component_role_map` in the project
  contract. The same map can classify an exact custom capacitor identity for
  `power.ic_rail_without_fitted_capacitor`. Each entry binds one exact
  `PART_ID`, native symbol ID, footprint, complete two-pin
  number/function/electrical-type inventory, and review basis; capacitor roles
  additionally require both native pins to be passive.
  The exact identity is checked against every native component carrying that
  `PART_ID`; a missing or changed part, symbol, footprint, or pin inventory
  blocks lint and does not receive the mapped role. A mapped LED finding
  includes the basis and a deterministic digest of its role binding. Unlisted custom
  symbols remain outside these rules, including a same-value unrelated
  symbol. A `capacitor` role affects only the decoupling-presence hint; it does
  not classify the part for other checks.
  It is a default review heuristic, not proof that current limiting is missing.
  A project-authored `power_path_map` may suppress the prompt only for an exact
  `Device:LED` A-to-K path ending at a mapped `current_controlled_sink` endpoint
  whose native `PART_ID`, pin function, electrical type, and net topology match.
  This explicit map is not an inference and does not establish that the device
  actually regulates current or is electrically adequate. The rule does not
  infer LED polarity, output limits, off-board paths, board copper, population,
  or runtime behavior. Its native synthetic direct-output fault,
  return-side-series control, and parallel-resistor fault are exported twice
  on pinned KiCad 10.0.0 and 10.0.5. Single- and two-channel current-sink
  controls are registered in the same pinned native lane; their hosted export
  result is pending. Custom-role native fault/control exports use
  the same pins and exact project mapping. The cohort trial behind the adjacent
  LED review family did not evaluate this topology. See the
  [fixture trial and native regression record](../tests/fixtures/design_lint/cohort-led-resistor/README.md).

  Example project contract entry:

  ```json
  {
    "design_lint": {
      "schema_version": "1",
      "component_role_map": {
        "entries": [
          {
            "part_id": "training-led",
            "symbol": "Training:LED_5mm",
            "footprint": "Training:LED_0603",
            "role": "led",
            "pins": [
              {"number": "1", "function": "A", "electrical_type": "passive"},
              {"number": "2", "function": "K", "electrical_type": "passive"}
            ],
            "basis": "Reviewed the library symbol identity and pin functions"
          },
          {
            "part_id": "training-capacitor",
            "symbol": "Training:CAP_2PIN",
            "footprint": "Training:CAP_0603",
            "role": "capacitor",
            "pins": [
              {"number": "1", "function": "1", "electrical_type": "passive"},
              {"number": "2", "function": "2", "electrical_type": "passive"}
            ],
            "basis": "Reviewed this exact custom capacitor and passive pin inventory"
          }
        ]
      }
    }
  }
  ```

- `power.pin_function_net_role_conflict` prompts review when a fitted pin with
  a recognized positive-supply function is assigned to a return-like net, or
  a recognized return-function pin is assigned to a positive rail. Recognized
  net labels take precedence; only otherwise do other attached pin functions
  supply opposing role evidence. The candidate pin cannot classify its own
  net. Connector return
  pins remain with `connector.return_pin_on_positive_rail`; positive-supply
  connector pins remain in scope. DNP components and open or multiply assigned
  pins are skipped. Function and label names do not establish electrical
  potential or intent, so the rule defaults to `REVIEW` and supports project
  `block`, `off`, and exact-fingerprint ignores. The synthetic fault/control
  regressions and CLI/MCP parity case use a tooling-owned normalized netlist.
- `power.named_supply_pin_on_negative_rail` prompts review when a fitted pin
  with a recognized positive-supply function is assigned to a label using a
  supported, explicitly minus-prefixed numeric voltage spelling. Labels such
  as `VEE`, custom aliases, open or multiply assigned pins, and DNP components
  are excluded. Pin-function and net-label names do not prove potential or
  intent; projects can override or fingerprint-ignore the review. Synthetic
  fault/control, bounded recognition, policy, and CLI/MCP parity cases cover
  this clue. Exact-version native exports are wired into the prerelease gate.
- `power.ic_rail_without_fitted_capacitor` prompts review when a fitted IC has
  an assigned native `power_in` pin on a recognized positive rail and no
  recognized fitted capacitor connects that rail to a distinct return-like
  schematic net. Recognized rails and pin functions use the bounded
  `power_function_key` list, return labels and functions use the existing
  return-name recognizer, and capacitor symbols use common `C`, `C_*`, `CP`,
  `CP_*`, or `*capacitor*` library names. A project may extend this one hint
  to a custom symbol through an exact `component_role_map` capacitor entry
  matching `PART_ID`, symbol, footprint, and complete native pin inventory.
  A stale entry blocks lint; without a matching entry the custom symbol is
  not treated as a capacitor. This default-review hint does not
  decide whether the datasheet requires a capacitor, whether its value is
  suitable, or whether it is placed locally with an adequate PCB return path.
  Internal, remote, and off-board
  decoupling can be valid controls; project policy can override or ignore a
  finding. `J`, `P`, `X`, and `CN` references are excluded as connectors;
  projects using other connector prefixes may receive a review prompt.
  Synthetic no-cap, fitted-capacitor, unrecognized-rail, source-backed, and
  DNP-capacitor cases and exact custom-capacitor role fault/control cases are
  exported twice by digest-pinned KiCad 10.0.0 and 10.0.5 fixture lanes;
  normalized netlists and ERC results repeat. The custom role applies only to
  this presence hint and does not imply value, placement, or physical
  effectiveness. The
  source-backed DNP case confirms that an unpopulated capacitor does not count
  as coverage. See the
  [fixture trial and native regression record](../tests/fixtures/design_lint/cohort-power-pin-dc/README.md).
- `power.mapped_series_path_mismatch` runs only when a project supplies
  `design_lint.power_path_map`. It compares an authored ordered chain of exact endpoint and
  two-terminal component identities, pin inventories, DNP state, and net assignments. An endpoint
  may additionally bind exact `PART_ID`, native pin function, and electrical type; the
  `current_controlled_sink` role requires all three and serves only as explicit LED review metadata.
  Each element must be fitted and connect the two adjacent mapped nets. This does not infer that two
  grounds or supplies should be joined, determine current direction, prove the component conducts,
  detect unlisted parallel paths, or establish PCB copper continuity. The rule defaults to `review`
  and supports project `block`, `off`, and exact ignores.
- `power.mapped_sequence_dependency_mismatch` runs only when a project supplies
  `design_lint.power_sequence_map`. The map names exact rail-stage output pins,
  optional power-good and enable pins, each stage's control context, and the
  required power-good-to-enable dependency edges. The checker compares symbol,
  footprint, optional `PART_ID`, fitted state, native pin inventory, and mapped
  pin/net assignments; it reports cycles in the authored graph and cycles
  formed when one mapped stage output net is assigned to another mapped stage's
  enable pin. The latter requires every participating stage to match the native
  netlist exactly and remains a `REVIEW` prompt. It never infers stage roles or
  required sequencing from `EN`/`PG` names or part families. A match does not
  prove that the source requirement is correct, that timing or voltage
  limits are met, that firmware sequences the rail, or that the physical board
  behaves as required. Synthetic control, open-enable, and output-enable-cycle
  fixtures repeat through digest-pinned KiCad 10.0.0 and 10.0.5 exports; their
  normalized netlists preserve the expected topology. Numeric timing evidence
  is not implemented in v1. The rule defaults to `review` and supports project
  `block`, `off`, and exact ignores. See the
  [native fixture record](../tests/fixtures/design_lint/power-sequence-native/README.md).
- `power.input_without_supported_source_path` is a default-review fallback for
  an internal fitted `power_in` pin on a net with a fitted capacitor to a
  recognized return when no source anchor can be identified, or when a
  recognized anchor exists but no supported path reaches it. Recognized
  positive rail names and fitted `power_out` pins count as source anchors. An
  external source on a custom-named net without a `power_out` pin now produces
  a coverage review instead of silently appearing covered. The heuristic
  recognizes exactly inventoried two-pin resistors at or below 1 Ω, inductors,
  ferrite beads, fuses, and polyfuses. Exact `Device:D` and
  `Device:D_Schottky` identities count as directional paths only when the
  native two-pin inventory gives one `A` and one `K` pin on distinct nets and
  the diode points from source to load. The exact
  `Jumper:SolderJumper_2_Bridged` identity counts as a bidirectional path only
  with native pins `1`/`2` mapped to `A`/`B` and a fitted assembly state. The
  exact `Jumper:SolderJumper_3_Bridged12` and
  `Jumper:SolderJumper_3_Bridged123` identities require the complete native
  `1`/`2`/`3` inventory mapped to `A`/`C`/`B`; the former joins only pins 1
  and 2, while the latter joins all three. Open, DNP, other, or ambiguously
  mapped jumpers remain unsupported. Zener, TVS, custom diodes, switches,
  regulators, and semiconductor paths remain unsupported and can prompt review
  even when their use is valid. A project-authored power-path map suppresses
  the heuristic for its mapped load endpoints, leaving the exact requirement
  report. The heuristic asks for review and cannot establish that a path is
  required or that the PCB, component, or off-board path conducts. It supports
  project `block`, `off`, and exact ignores. A recognized custom capacitor
  library name containing `Capacitor` can supply the fitted-capacitor evidence;
  an arbitrary custom symbol name is not inferred to be a capacitor. A
  separately named isolated return remains separate in the evidence: a fitted
  `power_out` anchor on the isolated supply is a quiet control, while a valid
  external supply represented without source-pin metadata remains a REVIEW
  candidate that needs a project decision. Native fixtures confirm that a
  custom library ID containing `Capacitor` is recognized by name. An opaque
  custom ID is not treated as capacitor evidence; on a rail that the existing
  IC decoupling rule recognizes, that separate rule may still prompt review.
  A native two-pin external-connector pair also confirms that fitted `J1.1`
  `power_out` evidence on a custom rail is an anchor, while the same exported
  pin marked DNP is excluded and produces a source-path REVIEW.
  A separate native alternate-source control marks `J1` DNP and leaves `J2`
  fitted on its own ferrite branch to the same internal rail. It confirms that
  the fitted branch supplies the detected path despite the DNP peer; both
  source branches remain separate in the schematic netlist until they reach
  the load rail. A paired fault with both connectors DNP produces LINT-056
  REVIEW, confirming that neither unpopulated source counts as an anchor.
- `net.connector_capacitor_only_no_dc_anchor` asks for review when every fitted pin
  assigned to a non-return net belongs to a supported connector or capacitor,
  with at least one of each. DNP pins are ignored; an unknown or additional
  fitted component pin suppresses the prompt. Review whether a local DC
  reference is required or provided off-board or internally. This rule does
  not trace DC paths or identify an analog function, and does not prove a bias
  is missing. It defaults to `review` and supports project `block`, `off`, and
  exact ignores. Tool-owned fault and control schematics were exported twice
  with pinned KiCad 10.0.0 and 10.0.5. A third native fixture leaves a DNP
  capacitor assigned to the connector net; both native versions retain its DNP
  state, and the lint ignores it. ERC had zero errors for all three cases while
  this rule reported only the fitted-capacitor fault. This demonstrates
  incremental detection over ERC for the synthetic pattern, not behavior on
  private or field boards.
- `control.unconnected_control_input` flags an unassigned native input pin
  whose symbol function matches a bounded reset, enable, or boot/strap alias.
  The exported pin type must be `input` or `input_low`. This prompts review of
  intentional non-use, internal or off-board handling, and a possibly missing
  connection. Pins on DNP components are excluded. It does not infer bias,
  polarity, or an electrical requirement. Power-stage `BOOTSTRAP` names are
  not treated as boot-mode aliases; bare `BOOT` remains ambiguous and may
  still warrant review. The `POR` token is recognized as a reset alias because
  KiCad's [MCU_Module:CHIP-PRO symbol][chip-pro-symbol]
  names an input `POR_B`; the unrelated token `PORN` remains outside this
  alias.
- `control.connected_control_input_without_visible_bias` reports one review
  candidate per assigned net containing a recognized reset, enable, or
  boot/strap input when no fitted conventional two-terminal resistor path is
  visible from that net to a recognized positive or return net. It recognizes
  direct resistors and unbranched resistor chains whose intermediate nets
  contain exactly the two resistor pins; any positive nominal resistance is
  accepted without claiming adequacy. Output-capable peers are included as
  evidence for review and do not suppress it. The rule uses native
  `input`/`input_low` types, excludes DNP control components, and can be
  changed per project to `review`, `block`, or `off`, or cleared by an exact
  ignore. Power-stage `BOOTSTRAP` names are excluded. For this connected-input
  rule only, a bare `BOOT` pin is omitted from the candidate when native
  netlist evidence shows a fitted exact two-pin unpolarized `Device:C` or
  `Device:C_Small` between its net and a same-device `SW`, `LX`, or `PH` pin
  net. Bare `BOOT` without that exact topology remains reviewable, and the
  unconnected-input rule still treats it as ambiguous. This topology screen
  does not verify capacitor requirement, value, placement, or physical
  connectivity.
  It does not infer that a local resistor is required. DNP and
  zero-ohm resistors, branched or ambiguous paths, resistor arrays, jumpers,
  custom rail names, internal pulls, off-board bias, runtime drive, resistor
  adequacy, and PCB continuity are outside the heuristic. When the electrical
  contract has an exact control requirement for every candidate input on the
  net, the heuristic prompt is
  resolved only after its endpoint and driver checks pass and its local bias
  check passes, or its internal, external, or not-required bias decision is
  explicitly declared. The report records the contract path and digest, signal
  ID, bias basis, and decision. A mismatch or incomplete pin set leaves the
  review prompt open. Declaring internal or off-board bias records design
  intent; it does not independently verify that physical or firmware behavior.
- `signal.open_collector_input_without_visible_bias` asks for review when a
  fitted native `open_collector` output and an `input` or `input_low` pin share
  a non-rail net without a direct or unbranched series path of fitted
  conventional resistors to a recognized positive rail.
  `signal.open_emitter_input_without_visible_bias` does the same for a fitted
  native `open_emitter` output without a direct or unbranched series resistor
  path to a recognized return. Each prompt defaults to `review` and has
  an independent project override and exact-ignore identity. DNP outputs are
  excluded. I2C, recognized reset/enable/boot inputs, and active-low SPI chip
  selects stay with their narrower rules. Branched paths, resistor arrays,
  jumpers, active networks, internal or off-board bias, custom rail names,
  resistor adequacy, receiver thresholds, runtime state, and PCB continuity
  are outside these heuristics; they do not infer that a local resistor is
  required.
- `bus.i2c_unconnected_pin`, `bus.spi_unconnected_chip_select`,
  `bus.usb_c_unconnected_cc_pin`, and `bus.can_unconnected_line` flag unassigned
  SDA/SCL, recognized SPI chip-select, USB-C CC1/CC2, and CANH/CANL pins. These
  ask whether the pin is intentionally unused or a connection is missing; they
  do not infer interface role or off-board wiring.
- `bus.usb_c_unreviewed_port` prompts when a fitted numeric J/P/X/CN connector
  exports both CC1 and CC2 pin functions but is absent from the electrical
  contract's USB-C port-role map. This is a coverage hint: the pin names do not
  establish a USB-C port or its source/sink role, CC attachment, VBUS path, or
  protection requirements. The USB-C contract reports its own pin and topology
  mismatches; DNP connectors are excluded. Plausible source or sink resistor
  paths do not suppress this prompt; only authored role-map membership does.
- `bus.spi_active_low_chip_select_without_pullup` reviews an assigned
  active-low SPI chip-select input with no visible local pull-up path. It only
  uses explicit active-low pin-function spellings and native `input` or
  `input_low` pin types. This is a configurable review hint; an internal bias,
  controller reset behavior, or off-board pull-up can make the schematic valid.

KiCad's native XML netlist represents pins without a net assignment using
synthetic names such as `unconnected-(J1-SHIELD-Pad3)`. The parser retains these
references in `NetlistContract.unconnected_nets` and removes the sentinel from
`nets`, so connectivity checks do not mistake a placeholder for a real shared
net. This preserves native pin-level evidence for unconnected-pin heuristics
and explicit `unconnected` requirements. A sentinel still says only that the
schematic pin has no assigned net; it does not establish that the pin should
have been connected.

- `bus.i2c_missing_pullup` flags a component with named SDA/SCL pins when
  either bus net lacks a visible 1 kΩ–100 kΩ path to a named positive rail.
  Paths may be one conventional resistor or an unbranched series chain of
  fitted conventional resistors. Each resistor and the total chain must be
  within 1 kΩ–100 kΩ; every intermediate net must contain exactly the two
  recognized resistor pins. A branched or otherwise ambiguous junction is
  left for review. This asks the reviewer to check internal or off-board
  pull-ups.
  A matching project-authored `i2c_pullups` requirement can resolve this hint
  only when the exact ordered SDA/SCL pair and both lines pass the current
  source-bound electrical checks. This includes a mapped
  resistor-array channel only when its component identity, complete native
  pin disposition, channel nets, and required resistance range pass. Any
  associated authored voltage-compatibility check must also pass. The report
  records the electrical-contract digest, native-netlist digest, requirement
  ID, and check IDs used; absent, pending, not-applicable, mismatched, and
  failing requirements leave the heuristic prompt open. This resolves a
  schematic review prompt; it does not verify the cited datasheet mapping,
  PCB routing, actual component population, bus timing, or off-board pull-ups.
- `bus.spi_active_low_chip_select_without_pullup` applies the same bounded
  resistor-path scan to assigned active-low chip-select input pins. It
  recognizes `CS_N`, `CSN`, `NCS`, `NSS`, `SS_N`, `CHIPSELECT_N`, and common
  explicit active-low markings such as `~{CS}`, `CS#`, `!CS`, and `/CS` after
  punctuation normalization. Bare `CS`, `SS`, and `CHIPSELECT` do not state
  polarity and are not included. The pin must be exported as `input` or
  `input_low`; fitted direct or unbranched two-terminal resistor paths from
  1 kΩ through 100 kΩ to a recognized positive rail suppress the hint. This
  threshold is a broad detection window, not a recommended value. Resistor
  arrays, jumpers, active bias, custom rail names, internal pulls, controller
  reset behavior, off-board circuits, and device timing are not modeled.
- `bus.i2c_low_equivalent_resistance` combines recognized direct or unbranched
  series pull-up paths in parallel when they connect to the same named positive
  rail. It asks for review when nominal effective resistance falls below 1 kΩ
  on SDA or SCL. This broad boundary is a heuristic; the rule does not set a
  project bus requirement and does not calculate arrays, multiple rails,
  tolerance, sink current, capacitance, or timing. Its findings use the same
  per-project `review`, `block`, `off`, and exact-ignore decisions as the other
  rules.
- `bus.i2c_multiple_pullup_rail_families` prompts when fitted, recognized
  direct or unbranched I2C pull-up paths on SDA and SCL use more than one
  normalized positive-rail family. It asks the reviewer to check the intended
  bus voltage, device input limits, pull-up rails, and any level-shifting
  topology. Rail names alone do not establish voltage or incompatibility.
  Custom rail names without a recognized power-pin function, internal or
  off-board pull-ups, arrays, and active pull-up circuits are outside the
  predicate. The 1 kΩ–100 kΩ path range is a review-detection window, not a
  universal I2C requirement. The rule defaults to `review` and supports
  project `block`, `off`, and exact-ignore decisions.
- `bus.i2c_address_mismatch` and
  `bus.i2c_address_collision` run only when a project supplies
  `design_lint.i2c_address_map`. The map names static
  responders and bus segments; strapped address bits are resolved from exact
  native symbol functions and net assignments. A complete strapped address
  that differs from the authored value, or two fitted mapped responders at
  the same address on one declared segment, produces a review finding. Fixed
  addresses are authored expectations with no pin derivation. Dynamic or
  unresolved entries remain coverage gaps, and separate segments may not
  share an SDA or SCL net. See the section on
  [I2C responder address configuration](DESIGN_LINT.md#declare-i2c-responder-addresses).
- bus.i2c_unmapped_responder is a review-only coverage prompt for non-DNP U/IC
  references whose native symbol pin functions include assigned SDA and
  SCL pins on distinct nets, but whose reference is absent from the
  project-authored address map. It also prompts when no map exists. This uses
  symbol function metadata rather than net-name or part-value guesses. It does
  not establish that the part is an addressable target; a bridge or other
  intentionally unaddressed device may need an exact ignore or a project-level
  rule override. References using other prefixes and nonstandard pin-function
  names are outside the heuristic.
- `bus.complementary_pair_assignment` recognizes a bounded set of CANH/CANL,
  USB D+/D−, USB SuperSpeed SSTX/SSRX and StdA/StdB-prefixed pairs, TX+/TX−,
  and RX+/RX− symbol pin-function pairs. It asks for review
  when one side is absent, a pin has no unique net assignment, multiple pins
  map to one side, or both functions share one schematic net. A complete pair
  on distinct nets passes this heuristic; that does not prove peer mapping,
  polarity, or physical routing. An unused pair remains a review finding until
  the project records an exact reasoned ignore or another applicable decision.
  Projects may add vendor-specific names through
  `design_lint.complementary_pin_function_alias_map` in the project test
  contract. Each entry names the exact native KiCad symbol identity, one pair
  family, the positive and negative pin-function aliases, and the project
  review basis:

  ```json
  {
    "design_lint": {
      "complementary_pin_function_alias_map": {
        "entries": [
          {
            "symbol": "Vendor:SerialPHY",
            "family": "TX0",
            "positive_functions": ["TXOUTP"],
            "negative_functions": ["TXOUTN"],
            "basis": "Reviewed vendor datasheet pin table, revision 2"
          }
        ]
      }
    }
  }
  ```

  The alias map is not inferred from observed net names. If the configured
  symbol is absent or none of its aliases occur in the native pin inventory,
  lint blocks until the map is refreshed. Fitted components are checked;
  components marked DNP are skipped. The map records reviewed pin-function
  roles for this symbol; aliases already covered by the built-in table cannot
  be repeated. It does not require the two nets to be distinct or connected to
  another component, or prove physical pair routing.
  The USB SuperSpeed aliases follow the USB-IF Standard-A/Standard-B signal
  names; lane-indexed USB-C TX1/TX2 and RX1/RX2 pins remain outside this
  single-pair-per-role check. See the [synthetic fault/control and native
  regression record](../tests/fixtures/design_lint/complementary-pair-native/README.md).
- `bus.usb_data_path_mismatch` runs only when a project supplies
  `design_lint.usb_data_path_map`. It compares exact connector and PHY
  identities, D+/D− endpoint pins, native pin inventory, assigned nets, and
  the authored direct or series-resistor topology. A direct path supports an
  explicitly reviewed integrated-PHY disposition; a series path names one
  fitted resistor and a project-selected nominal range. A `bonded` reference
  policy also checks the exact mapped passive two-pin bond identity, value,
  footprint, and pin-to-net assignments. A direct path may also declare exact
  multi-pin protection shunts, including their D+/D− taps and every native pin's
  expected net or explicit no-connect state. The map checks the complete native
  pin inventory and rejects stale identity or pin assignments. Its separate
  `superspeed_interfaces` entries can map an exact direct SuperSpeed P/N peer
  pair and reviewed common, separate, or bonded endpoint-reference policy.
  These entries compare source-bound pin/net assignments and an optional exact
  bond; they do not map SuperSpeed lane routing or signal-integrity limits. It
  does not infer a universal external-resistor rule from USB names or choose a
  value.
- `bus.usb_peer_reference_review` prompts on fitted USB 2.0 D+/D− or bounded
  USB SuperSpeed connector-to-U/IC paths when each endpoint has explicit
  reference pins on one native net and those two reference nets differ. It
  remains a default `REVIEW`: separate references may be intentional, and this
  heuristic does not say that grounds must be tied.

  USB 2.0 paths may be direct, pass through exactly one complete fitted
  two-pin `Device:R` per line, or pass through one multi-pin component named by
  a current exact USB data-path map. A direct path with multi-pin protection
  is supported only when the map names the exact D+/D− taps and every native
  pin assignment. The map must match endpoint identities, complete component
  identity and pin inventory, each pin's net or explicit no-connect state, and
  complete signal-net membership. Complete fitted two-pin passive components
  with a `D` designator may branch from D+/D− to an endpoint reference; the
  report names both branch pins and their symbol identity. Numbered DPn/DMn,
  USB_DPn/USB_DMn, and USBnD+/USBnD- forms pair only when their port numbers
  match. Repeated contacts are supported when every pin on that side and port
  shares the same data net.

  USB SuperSpeed recognition covers the bounded SSTX+/SSTX− and SSRX+/SSRX−
  Standard-A/Standard-B aliases documented by the
  [USB-IF Front-Panel Implementation Document](https://www.usb.org/sites/default/files/USB3p1_Front_Panel_CabCon_Implment_Doc_Rev1p1.pdf).
  It requires complete pin inventories and function/type metadata, one
  positive and one negative pin per family, connector TX to PHY RX or
  connector RX to PHY TX, and exactly the two endpoint pins on each data net.
  This direct-path check excludes lane-indexed USB-C pairs, muxes, retimers,
  series parts, shunts, extra peers, and other multi-hop paths. A matching
  `superspeed_interfaces` entry can record the reviewed exact path and a
  common-net, separate-net, or bonded reference decision. A stale map reports
  `bus.usb_data_path_mismatch`; the heuristic review remains when the observed
  split references do not match the map. Use a project-scoped rule override or
  exact reasoned ignore when review establishes a different intentional case.

  Incomplete pin inventories, ambiguous assignments, mixed reference
  domains, shield/chassis/PE pins, and DNP endpoints remain outside the
  predicate. The structured and text coverage reports identify each
  recognized endpoint family as `SUPPORTED`, `INCOMPLETE`, or `DNP`.
  `SUPPORTED` means the endpoint has enough local evidence to enter this
  bounded scan; it does not mean a peer path was found or electrically
  approved. USB 2.0 numbered groups retain their port number; SuperSpeed
  families are reported separately by TX/RX role. A multi-domain USB isolator
  remains outside the endpoint predicate: its recognized PHY port groups are
  `INCOMPLETE`, with no supported peer path. That quiet result is a partial
  screen, not evidence that the isolated returns should be joined or a supported
  non-finding. See the [synthetic two-port isolation boundary][usb-isolator].
- `signal.named_pair_without_reviewed_requirement` looks for populated source
  nets with recognized `_P/_N`, `_DP/_DM`, `_TXP/_TXN`, `_RXP/_RXN`, `_H/_L`,
  `+/-`, `DP/DM`, `P/N`, or `H/L` suffixes. If the exact pair is absent from
  `design_lint.pcb_differential_pair_rule_map`, it asks whether the names
  represent a physical differential pair and whether project-owned PCB limits
  should be recorded. This is a naming prompt only; it does not measure routes
  or invent width, gap, skew, or uncoupled-length limits. It defaults to
  `review` and supports project `block`, `off`, and exact-ignore decisions.
- `bus.can_missing_termination` flags a named CANH/CANL pair without a visible
  108 Ω–132 Ω resistor connected directly across the two nets. It asks the
  reviewer to check external termination, split termination, and bus topology.
- `bus.can_peer_assignment_divergence` prompts when fitted components with
  exactly one uniquely assigned CANH and CANL pin function share one exact net
  on one side but use multiple exact nets on the other. Evidence lists every
  participating pin/net assignment. This is a default-review asymmetry prompt;
  it does not infer that peers belong to one bus or that both sides must be
  common. DNP, incomplete, multi-pin-role, ambiguous, and same-net pairs are
  skipped. It does not establish termination, transceiver behavior, off-board
  wiring, PCB copper, or physical connectivity. Synthetic native fault and
  same-pair control exports are repeated on KiCad 10.0.0 and 10.0.5; neither
  has ERC errors, while only the split-peer case triggers the lint. The
  isolated synthetic library setup reports the expected symbol/footprint
  library warnings, recorded with the fixture evidence.
- `net.numbered_returns` flags two or more return-like nets with the same stem
  and distinct numeric suffixes, such as `GND1` and `GND2`. Its recognized
  ground token also permits one-letter suffixes, so `GNDA1` and `GNDA2` can
  prompt review. The bounded `RET` token also covers patterns such as
  `RET1`/`RET2` and `PORT1_RET`/`PORT2_RET`; synthetic common-`RET` and
  `RESET1`/`RESET2` controls guard the boundary. TI's
  [UCC28630EVM-572 user guide](https://www.ti.com/lit/ug/sluuax9b/sluuax9b.pdf)
  uses `RET` for an output return label. This source supports the spelling as
  review context only; it does not establish that separate domains should be
  joined. A focused CLI/MCP parity regression covers numbered and unindexed
  `RET` candidates plus a common-`RET` control. The synthetic four-port DB9
  case covers `0V PWM 1` through `0V PWM 4`, with a common `0V PWM` control. See the
  [numbered-return fixture](../tests/fixtures/design_lint/four-port-db9-returns/README.md).
  KiCad's [net-class example](https://docs.kicad.org/8.0/en/eeschema/eeschema.pdf)
  shows `GND*` matching both `GND` and `GNDA`; that naming similarity does not
  establish that the nets should be joined.
- `net.numbered_power_rails` flags separately numbered nets with a bounded
  recognized positive-supply stem. It recognizes explicit suffix forms such as
  `+5V_1` and `5V-2`, plus bounded `P`, `CH`, and `RAIL` prefix forms such as
  `P1_5V`, `CH2_VDD`, and `RAIL3_VIN`. Suffix numbers require a separator;
  names such as `+5V1` are left alone. Similar names only prompt review: the
  rails may be intentionally isolated or have independent sources, and the
  finding never requires a tie or classifies a net as a power rail.
- `net.return_labels_without_pin_roles` flags multiple populated, unnumbered
  return-like net labels when none of their attached exported pin functions
  identifies a return. Nets already included in a numbered-return group are
  left to `net.numbered_returns`. It is intended to catch separate labels such
  as `USB_GND`, `SERIAL_RETURN`, `GNDA`, `GNDD`, and synthetic `RET_USB` /
  `RET_SERIAL` labels on numeric connector pins. This asks for review;
  it does not determine whether the domains should be common, bonded, or
  isolated. Numbered sibling nets remain under `net.numbered_returns`, and
  explicit return pin functions leave this candidate to the connector rules.
- `protection.unreviewed_interface_pin` asks for an explicit protection
  applicability decision for each pin in the project-reviewed interface map.
  A decision can map a required protector or state `not_required` with a basis;
  the rule does not infer that protection is needed from a connector or signal
  name.
- `protection.mapped_device_mismatch` compares an authored protector map with
  the native symbol, footprint, DNP state, complete pin inventory, and exact
  pin-to-net assignments. It is an authored schematic requirement check; its
  default disposition is still review.
- `power.regulator_feedback_mismatch` runs only when a project supplies
  `design_lint.regulator_feedback_map`. It checks explicitly mapped adjustable
  regulators with a conventional two-resistor feedback divider, then compares
  the nominal DC output interval with the authored target. It does not infer
  device roles or reference voltage from a part name.
- `filter.rc_corner_mismatch` runs only when a project supplies
  `design_lint.rc_filter_map`. It checks the mapped first-order series-R and
  shunt-C topology, nominal values, and corner range. It does not infer a filter
  from component references or net names.
- `pcb.decoupling_proximity` runs only when a PCB project supplies
  `design_lint.pcb_decoupling_map`. It verifies exact IC/capacitor pad identity,
  fitted state, expected nets, native copper connectivity, and supply-pad
  center distance against the project's threshold. A project can also set
  `max_return_via_distance_um` to screen the capacitor return pad against the
  nearest via in that pad's native copper-connectivity component. No via limit
  is inferred when the field is omitted.
- `pcb.protection_entry_path` runs only when a PCB project supplies
  `design_lint.pcb_protection_path_map`. It checks exact connector and
  protection signal/reference pads, expected footprints and nets, fitted state,
  native copper connectivity, the straight-line connector-to-protector pad
  distance, and any project-authored connected-reference-via count/radius.
  It does not infer which nets are ground or which connectors require
  protection. A nearby via on a ground-named net does not count unless KiCad
  reports it in the mapped reference pad's native copper component.
- `pcb.minimum_track_width` runs only when a PCB project supplies
  `design_lint.pcb_track_width_map`. It compares every native track item on
  each mapped net with that net's project-authored minimum width.
- `pcb.switching_loop_geometry` runs only when a PCB project supplies
  `design_lint.pcb_switching_loop_map`. It checks exact mapped pads and fitted
  state, measures the polygon through their authored native pad-center order,
  and checks whether the mapped return pads share one filled island on the
  declared copper layer. Hosted KiCad 10.0.0 and 10.0.5 lanes exercise a
  connected F.Cu plane, a connected In1.Cu plane, a split In1.Cu plane, and an
  exact-area boundary; this is analyzer evidence, not a design threshold
  recommendation.
- `connector.return_distribution` runs only when a project supplies
  `design_lint.connector_return_distribution_map`. It counts contacts explicitly
  classified in the interface catalog and checks a project-authored minimum
  signal count and maximum signal-to-return ratio. Supply, shield, and other
  contacts are excluded. The ratio does not require return pins to share a net.

These rules do not claim that the nets must be connected. An intentionally
isolated interface or independent supply can produce a valid finding. The
same-component supply rule recognizes only the existing narrow supply-function
categories, skips explicitly DNP components, and does not inspect component
datasheets or infer whether pins should be tied; a legitimate filtered or
separate supply may produce a review finding. The
cross-symbol supply comparison recognizes only explicitly named functions
such as `PWR`/`POWER`, `VBUS`, `VCC`, `VDD`, and common voltage labels; it keeps
different names such as `VBUS` and `VCC` separate. A symbol without named pins,
an uncommon connector reference, or an unrelated net-name pattern can evade
the current rules. The return coverage hint can also flag intentionally
isolated multi-pin interfaces. Unconnected-pin hints depend on KiCad's exported
symbol pin definitions retaining the function name; anonymous and uncommon
return or supply names can evade them. Keep ERC, independently reviewed
electrical contracts, PCB inspection, and first-article tests in their own roles.
The I2C hint recognizes only `SDA`, `SCL`, `I2C_SDA`, and `I2C_SCL` symbol pin
functions, conventional resistor references, values from 1 kΩ through 100 kΩ,
and named positive rails. External-board pull-ups and internal pull-ups are not
visible in this netlist and can produce a valid review finding. The CAN hint
recognizes `CANH`/`CAN_HIGH` and `CANL`/`CAN_LOW` pin functions and a direct
two-terminal resistor from 108 Ω through 132 Ω. It will review valid designs
that use off-board or split termination. Neither check establishes interface
timing, placement, or electrical performance. The unconnected SPI hint only
recognizes pin functions that normalize to `CS`, `CSN`, `NCS`, `NSS`, `SS`,
`SSN`, `CHIPSELECT`, or `CHIPSELECTN`. The USB-C hint only checks that `CC1` and
`CC2` have a net assignment; it does not check role-appropriate pull resistors
or protection. The SPI active-low bias hint uses explicit low-polarity aliases,
native `input`/`input_low` pin types, conventional resistor references, 1 kΩ–
100 kΩ direct or unbranched series paths, and recognized positive rail names.
It may review valid designs that rely on internal bias, controller startup
behavior, resistor arrays, active circuits, custom rail names, or off-board
bias. It does not judge a suitable value or runtime state. All three
resistor-based hints ignore components explicitly marked DNP in the native
netlist.

`bus.spi_unmapped_participant` compares likely SPI-capable ICs with the
source-hashed electrical contract roster. It looks for an assigned SCK/SCLK
pin, assigned SPI data pin, and a named chip-select pin function on a fitted
U/IC reference. If the roster is absent or omits that reference, it asks the
reviewer whether the component is a missing roster entry, controller, bridge,
or unrelated pin-function match. It does not declare that the part belongs on
an SPI bus. The recognized function aliases and reference prefixes are
documented in the versioned rule catalog; unsupported names can evade the
prompt. LINT-013 separately compares every authored controller/device/bridge
mapping with the native netlist. Exact-version native fixture exports on KiCad
10.0.0 and 10.0.5 preserve prefixed SCLK/COPI/CIPO/NSS functions and distinguish
the absent-roster prompt from a complete-roster control; repeated parsed
netlists match after normalization. The fixture checks this export boundary,
not the engineering correctness of the authored roster or PCB connectivity.

`bus.serial_unmapped_peer` reviews exact exported TX/TXD and RX/RXD pin-function
pairs assigned to distinct nets against the source-hashed project
`serial_peers` map. It also has a bounded fallback for explicit `UART_TX`/
`UART_RX` or `USART1_TX`/`USART1_RX`-style net labels: each role must have one
uniquely assigned pin on a fitted U/IC, and both nets must reach at least one
common fitted connector candidate. The fallback is skipped when the MCU already
exports a recognized serial pin function. A mapped endpoint suppresses only
its exact TX/RX pin pair. An absent map, a pending map, or a map that omits the
pair produces a review-only coverage prompt. It asks whether the component is
a mapped logic-level UART endpoint, an unused alternate function, or another
interface. Pin functions and net labels are discovery clues; they do not
establish protocol, electrical standard, peer, reference, power-pin intent, or
that a connection is required. They do not prove PCB continuity or external
wiring. Bare TX/RX labels, arbitrary aliases, ambiguous assignments, and DNP
components are excluded. Projects can set this rule to `block` or `off`, or
ignore a specific fingerprint. LINT-014's explicit serial contract remains
the deterministic check for authored endpoint, voltage-domain, reference,
and direct/shifted path requirements. Exact-version native fixtures on KiCad
10.0.0 and 10.0.5 verify both discovery paths, exact-map suppression, and
repeatable normalized netlists. This validates the export and coverage prompt,
not PCB copper or external wiring.

The report also includes `connector_coverage`, a separate review-coverage
summary. It checks project-declared component-to-interface pin maps against the
configured interface catalog and exported symbol pin numbers. Candidate
discovery combines numeric `J`, `P`, `X`, and `CN` references with standard
`Connector` and `Connector_*` library identities; `Connector:TestPoint*`
symbols are excluded. The project manifest must also include a reasoned
`connector_inventory_review` basis for the complete schematic inventory.
Unreviewed or incomplete connector candidates, a missing inventory review, or
an empty unassessed scope keep the lane at `REVIEW`; `UNASSESSED` means neither
the reference-prefix scan nor the recognized standard-library scan found
candidates, not that the project has no physical interfaces. Pin coverage does
not assert shared nets or ground domains. The inventory review is a
project-owned statement whose content is bound by the manifest digest; it does
not independently prove that every physical interface was identified. Custom
library aliases and connector symbols outside the recognized library naming
family can still evade candidate discovery. The synthetic native regression
checks library identity export and parsing on KiCad 10.0.0 and 10.0.5; it does
not validate canonical library geometry or pinout. See the
[connector pin review guide](CONNECTOR_PIN_REVIEW.md#record-connector-interface-coverage)
and the [native fixture record](../tests/fixtures/design_lint/connector-inventory-native/README.md)
for the source and report digests.

Every report also carries the versioned rule catalog and its package-byte
digest. Catalog schema 3 gives every rule one implementation theme: connectors,
interfaces, components, power, returns, schematic, or PCB, and one source owner
function for its predicate. The owner must appear in the rule's implementation
references, belong to the matching theme module family, and remain outside
shared dispatchers. The theme supports focused review; it does not state that
a design requirement exists or that the rule proves electrical intent. The
catalog also names each deterministic predicate, supported KiCad evidence
boundary, limitations, implementation references, fault/control regression
tests, and each rule's
metamorphic review status, registered cases, or reasoned not-applicable basis.
Its source is
`kicad_tooling/hwrepo/design-lint-rules.json`. The current rules are marked
`synthetic_validated`; the catalog currently contains 153 active rules. They
have synthetic regression coverage, but no proprietary or customer board has
been used to claim field validation. Existing netlist rules default to
`review`; schematic geometry rules and generic all-open connector and
component peer heuristics default to `off`. These prompts need project-specific
review because a generic contact may be intentionally unused. Both connector
and component generic-peer heuristics remain default-off, including the
strict-majority peer-assignment outlier prompt.

## Source and fixture links

[chip-pro-symbol]: https://gitlab.com/kicad/libraries/kicad-symbols/-/blob/25ef404b6a92de5a0cec203eb3270632136758e3/MCU_Module.kicad_sym
[peer-all-open-fixture]: ../tests/fixtures/design_lint/named-peer-power-input-all-open/README.md
[peer-open-fixture]: ../tests/fixtures/design_lint/named-peer-power-input-open/README.md
[usb-isolator]: ../tests/fixtures/design_lint/usb-isolator-peer-reference-native/README.md
