# Design lint and project review decisions

Design lint finds patterns that merit review in a source-bound KiCad netlist. It
cannot infer whether matching connector pins should share a net. The project
repository owns the pinout, electrical requirements, and decisions about each
finding. Tooling owns the rules and report format.

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
  or a generic `Pin_N` placeholder. It asks for review when a peer is
  unconnected while another peer is assigned, including a group of only two
  connector instances, or differs from the unique most-common net assignment
  shared by at least two instances. Tied assigned-net patterns do not nominate
  an arbitrary outlier and are left to
  `connector.peer_pin_assignment_divergence`. This can localize an open generic
  contact that named-function checks cannot identify.
  Digest-pinned native fixtures verify the minimum two-connector open-contact
  case, an explicit no-connect-marker fault, and the common-net control on
  KiCad 10.0.0 and 10.0.5. The marked-open pin still receives a REVIEW prompt:
  an accidental marker can hide a missing contact from ERC. The finding does
  not say that matching pins must share a net.
  Matching symbol contacts do not prove that the pins must share a net;
  isolated ports and intentionally unused contacts remain valid. DNP
  connector instances are excluded. Fully specified meaningful pin groups stay
  with `connector.repeated_pin_function` to avoid duplicate findings. Fully
  reviewed connector sets may use distinct `peer_assignment_group` values to
  keep independent interfaces, such as separate UART channels, out of one
  another's generic pin-number comparisons. A missing or stale group on any
  participating connector keeps the broad comparison active.
- `connector.peer_pin_assignment_divergence` adds a lower-confidence prompt
  when fitted instances of the same exact connector symbol assign the same pin
  number to different nets, all compared contacts are assigned, at least one
  peer has unknown pin-function metadata (absent or generic `Pin_N`), fewer
  than two peers have meaningful role metadata, and no unique most-common
  assignment exists. It covers two-peer, tied, or
  all-distinct assignments that the outlier rule cannot localize to one unique
  most-common net. Review the external pinout to
  decide whether those contacts have a common role; the checker does not assume
  they should be joined. It ignores DNP instances, leaves open contacts to the
  outlier and named-pin rules, and supports the same per-project `review`,
  `block`, `off`, and exact-ignore decisions. Source-matched peer groups scope
  fully reviewed connectors; partial group coverage does not silence the prompt.
- `component.repeated_supply_pin_function` flags recognized matching supply
  functions on one fitted non-connector component when assigned pins use
  different or ambiguous schematic nets. It asks whether the split is
  intentional (for example, a filtered supply) or a missing connection. An
  unassigned member is reported by the more specific component supply-pin
  finding instead.
- `component.peer_power_pin_assignment_divergence` compares a shared pin
  number and recognized supply or return function across fitted non-connector
  instances of the exact same symbol. It prompts when every peer pin is
  assigned but the net assignments differ. The matching symbol and pin are
  only a review clue: separate rails or isolated return domains can be
  intentional, and the rule never joins nets. DNP peers, incomplete pin
  inventories, unknown functions, and open power pins are excluded; open pins
  stay with the component unconnected-pin checks.
- `component.two_pin_passive_same_net` prompts review when both pins of a
  fitted, exactly inventoried `Device:R`, `Device:C`, or `Device:L` symbol
  resolve to the same schematic net. The assigned net bypasses the passive in
  the schematic topology. Custom symbols, incomplete pin inventories,
  multi-pin devices, DNP parts, unassigned pins, and ambiguous assignments are
  outside the predicate. Same-net parts can be intentional; project policy can
  review, block, disable, or exactly ignore the source-bound candidate.
- `component.two_pin_diode_same_net` prompts review when both pins of a
  fitted, exactly inventoried `Device:D` family symbol resolve to the same
  schematic net. The diode is bypassed in that schematic topology. `Device:LED`,
  custom symbols, incomplete pin inventories, multi-pin devices, DNP parts,
  unassigned pins, and ambiguous assignments are outside the predicate.
  Same-net diodes can be intentional; the project can review, block, disable,
  or exactly ignore the source-bound candidate. The hint does not establish
  the correct diode polarity, footprint mapping, PCB copper connection, or
  whether a diode is required.
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
- `component.unconnected_supply_pin` and
  `component.unconnected_return_pin` apply the same named-pin coverage to
  non-connector components, including IC power pins. They only flag pins with
  no net assignment; they do not prove that an assigned pin is on the correct
  rail or that the rail has a valid source.
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
  contract. Each entry binds one exact `PART_ID`, native symbol ID, footprint,
  complete two-pin number/function/electrical-type inventory, and review basis.
  The exact identity is checked against every native component carrying that
  `PART_ID`; a missing or changed part, symbol, footprint, or pin inventory
  blocks lint and does not receive the mapped role. A mapped finding includes
  the basis and a deterministic digest of its role binding. Unlisted custom
  symbols remain outside the rule, including a same-value unrelated symbol.
  It is a default review heuristic, not proof that current limiting is missing. It does not
  infer LED polarity, output limits, off-board paths, board copper, population,
  or runtime behavior. Its native synthetic direct-output fault,
  return-side-series control, and parallel-resistor fault are exported twice on
  pinned KiCad 10.0.0 and 10.0.5. Custom-role native fault/control exports use
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
          }
        ]
      }
    }
  }
  ```

- `power.ic_rail_without_fitted_capacitor` prompts review when a fitted IC has
  an assigned native `power_in` pin on a recognized positive rail and no
  recognized fitted capacitor connects that rail to a distinct return-like
  schematic net. Recognized rails and pin functions use the bounded
  `power_function_key` list, return labels and functions use the existing
  return-name recognizer, and capacitor symbols use common `C`, `C_*`, `CP`,
  `CP_*`, or `*capacitor*` library names. This default-review hint does not
  decide whether the datasheet requires a capacitor, whether its value is
  suitable, or whether it is placed locally with an adequate PCB return path.
  Internal, remote, and off-board
  decoupling can be valid controls; project policy can override or ignore a
  finding. `J`, `P`, `X`, and `CN` references are excluded as connectors;
  projects using other connector prefixes may receive a review prompt.
  Synthetic no-cap, fitted-capacitor, unrecognized-rail, source-backed, and
  DNP-capacitor cases are exported twice by digest-pinned KiCad 10.0.0 and
  10.0.5 fixture lanes; normalized netlists and ERC results repeat. The
  source-backed DNP case confirms that an unpopulated capacitor does not count
  as coverage. See the
  [fixture trial and native regression record](../tests/fixtures/design_lint/cohort-power-pin-dc/README.md).
- `power.mapped_series_path_mismatch` runs only when a project supplies
  `design_lint.power_path_map`. It compares an authored ordered chain of exact
  endpoint and two-terminal component identities, pin inventories, DNP state,
  and net assignments. Each element must be fitted and connect the two
  adjacent mapped nets. This does not infer that two grounds or supplies
  should be joined, determine current direction, prove the component conducts,
  detect unlisted parallel paths, or establish PCB copper continuity. The rule
  defaults to `review` and supports project `block`, `off`, and exact ignores.
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
  polarity, or an electrical requirement. The `POR` token is recognized as a
  reset alias because KiCad's [MCU_Module:CHIP-PRO symbol][chip-pro-symbol]
  names an input `POR_B`; the unrelated token `PORN` remains outside this
  alias.
- `control.connected_control_input_without_visible_bias` reports one review
  candidate per assigned net containing a recognized reset, enable, or
  boot/strap input when no fitted conventional two-terminal resistor is
  directly assigned between that net and a recognized positive or return net.
  A visible resistor in either polarity clears the prompt; output-capable peers
  are included as evidence for review and do not suppress it. The rule uses
  native `input`/`input_low` types, excludes DNP control components, and can be
  changed per project to `review`, `block`, or `off`, or cleared by an exact
  ignore. It does not infer that a local resistor is required. DNP resistors,
  series paths, resistor arrays, jumpers, custom rail names, internal pulls,
  off-board bias, runtime drive, resistor adequacy, and PCB continuity are
  outside the heuristic. When the electrical contract has an exact control
  requirement for every candidate input on the net, the heuristic prompt is
  resolved only after its endpoint and driver checks pass and its local bias
  check passes, or its internal, external, or not-required bias decision is
  explicitly declared. The report records the contract path and digest, signal
  ID, bias basis, and decision. A mismatch or incomplete pin set leaves the
  review prompt open. Declaring internal or off-board bias records design
  intent; it does not independently verify that physical or firmware behavior.
- `signal.open_collector_input_without_visible_bias` asks for review when a
  fitted native `open_collector` output and an `input` or `input_low` pin share
  a non-rail net without a direct fitted conventional resistor to a recognized
  positive rail. `signal.open_emitter_input_without_visible_bias` does the
  same for a fitted native `open_emitter` output without a direct fitted
  resistor to a recognized return. Each prompt defaults to `review` and has
  an independent project override and exact-ignore identity. DNP outputs are
  excluded. I2C, recognized reset/enable/boot inputs, and active-low SPI chip
  selects stay with their narrower rules. Internal or off-board bias, series
  paths, resistor arrays, custom rail names, resistor adequacy, receiver
  thresholds, runtime state, and PCB continuity are outside these heuristics;
  they do not infer that a local resistor is required.
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
  [I2C responder address configuration](#declare-i2c-responder-addresses).
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
  footprint, and pin-to-net assignments. It does not infer a universal
  external-resistor rule from USB names or choose a value.
- `bus.usb_peer_reference_review` prompts on a fitted USB 2.0 D+/D−
  connector-to-U/IC pair when each endpoint has explicit reference pins on one
  native net and those two reference nets differ. Each D line may be direct or
  pass through exactly one complete fitted two-pin `Device:R` between the
  connector-side and PHY-side nets. The review evidence includes the resistor
  reference, symbol, value, pin numbers, and nets. Function aliases include
  hub names DPn/DMn, USB_DPn/USB_DMn, and USBnD+/USBnD-; numbered forms pair
  only when their port numbers match. An
  unnumbered connector pair can match a numbered hub port through its exact
  native nets; two numbered endpoints must carry matching suffixes. Exact USB
  maps can set `data_port_group` when a component exposes several numbered
  ports, so each connector is checked against only its mapped PHY pair. Each
  side may have repeated connector or PHY contacts, provided every pin within
  that port and side shares the same data net. It also allows complete
  fitted two-pin passive components with a `D` designator to branch from D+/D−
  to one endpoint's explicit reference net; the report names both branch pins
  and the symbol identity. Multiple series components, arbitrary extra peers,
  multi-pin protection parts, mixed reference domains, shield/chassis/PE
  functions, and ambiguous metadata remain outside this bounded rule. Separate
  nets can be intentional. The prompt asks whether the interface needs a
  common reference, a designed bond, or isolation; it never declares that the
  grounds must be tied. A current exact USB map with `reference_policy` set to
  `common_net`, `separate_nets`, or `bonded` suppresses the prompt only when it
  names all same-net data contacts and its
  endpoint, direct or one-resistor data-path, and reference-pin identities
  match. Use
  `connector_parallel_pins` and `phy_parallel_pins` alongside each line's
  primary pin to author additional same-net contacts. The same map checks
  those authored pin and net assignments and reports stale assignments
  through `bus.usb_data_path_mismatch`.
  The structured and text coverage reports also identify each recognized
  connector/PHY data group and mark it `SUPPORTED`, `INCOMPLETE`, or `DNP`.
  `SUPPORTED` means the endpoint-local pins and reference are sufficient for
  this bounded scan; it does not mean a peer path was found or electrically
  approved. Numbered DPn/DMn and USBnD+/USBnD- groups retain their port
  number, while unnumbered
  D+/D− groups report a null port group.
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
  and distinct numeric suffixes, such as `GND1` and `GND2`.
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
  as `USB_GND` and `SERIAL_RETURN` on numeric connector pins. This asks for review;
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
digest. The catalog names each deterministic predicate, supported KiCad
evidence boundary, limitations, implementation references, fault/control
regression tests, and each rule's metamorphic review status, registered cases,
or reasoned not-applicable basis. Its source is
`kicad_tooling/hwrepo/design-lint-rules.json`. The current rules are marked
`synthetic_validated`; the catalog currently contains 75 active rules. They
have synthetic regression coverage, but no proprietary or customer board has
been used to claim field validation. Existing netlist rules default to
`review`; schematic geometry rules default to `off` because they have a narrow
exact-version and format boundary.

## Compare STM32 CubeMX and KiCad pin assignments

`mcu.stm32_cubemx_pin_map` compares a project-authored pin map with the
source-bound native KiCad netlist and a repository-local CubeMX `.ioc` file.
For every package pin, the project must either map the exact CubeMX port pin to
an exact KiCad symbol pin, net, and accepted CubeMX `Signal`/`GPIO_Label`, or
exclude that package pin with a reason. The `basis` field should identify the
reviewed MCU pinout used to establish the package-to-symbol mapping.

```json
{
  "design_lint": {
    "stm32_pin_maps": [
      {
        "id": "main-mcu",
        "basis": "Reviewed STM32F103 package pin table, revision 1",
        "reference": "U1",
        "expected_symbol": "MCU_ST_STM32F1:STM32F103C8Tx",
        "expected_part": "STM32F103C8T6",
        "ioc_path": "firmware/controller.ioc",
        "package_pins": ["PA0", "PB6", "PB7", "PA13"],
        "pins": [
          {
            "port_pin": "PA0",
            "symbol_pin": "10",
            "expected_net": "USER_BUTTON",
            "accepted_ioc_signals": ["GPIO_Input"],
            "accepted_ioc_gpio_labels": ["BUTTON"]
          },
          {
            "port_pin": "PB6",
            "symbol_pin": "42",
            "expected_net": "I2C_SCL",
            "accepted_ioc_signals": ["I2C1_SCL"],
            "accepted_ioc_gpio_labels": ["SCL"]
          },
          {
            "port_pin": "PB7",
            "symbol_pin": "43",
            "expected_net": "I2C_SDA",
            "accepted_ioc_signals": ["I2C1_SDA"],
            "accepted_ioc_gpio_labels": ["SDA"]
          }
        ],
        "exclusions": [
          {
            "port_pin": "PA13",
            "reason": "Reserved for the reviewed SWD debug interface"
          }
        ]
      }
    ]
  }
}
```

The example values are illustrative; use the selected part's reviewed package
table and the project's actual KiCad symbol. Cross-name aliases are explicit
accepted values. Generic CubeMX GPIO functions require an explicit label
expectation, which can say that the label must be absent. The checker does not
infer pin functions or merge similarly named nets. It hashes the `.ioc` bytes
into the report and ignore fingerprint, so a source change creates fresh
evidence. The bounded parser accepts physical-pin keys with CubeMX
alternate-function suffixes, including hyphenated names and escaped spaces;
duplicate or conflicting keys for one physical pin remain explicit errors. If
two different suffixed keys normalize to the same physical pin, the scan blocks
coverage rather than choosing whichever `Signal` appeared last.

Without a map, a fitted component whose value or symbol contains `STM32`
receives a default `REVIEW` prompt to confirm whether CubeMX applies and whether
the project needs a map. DNP components do not prompt. This name-based discovery
is bounded and can miss other MCU families or nonstandard identities. For a
configured map, a missing file, duplicate assignment, conflicting suffixed keys
for one physical pin, unsupported pin key, or source change during inspection
blocks comparison. An exact mismatch is
`REVIEW` by default and supports the project `block`, `off`, and exact-ignore
decisions.

This comparison checks agreement among the project-authored expectation, the
native schematic netlist, and selected IOC fields. It cannot prove that the
authored pin map matches the actual silicon, inspect compiled firmware, or
establish PCB routing and off-board behavior. Synthetic service and CLI/MCP
parity cases pass, and the valid control plus schematic-net and CubeMX-signal
drift fixtures export repeatably on pinned KiCad 10.0.0 and 10.0.5. These
native regression lanes do not run ERC or DRC. See the
[native fixture record](../tests/fixtures/design_lint/stm32-pin-map-native/README.md).

## Explore the rule catalog

List all packaged rules, their default mode, predicate, supported evidence,
and limitations without selecting a project or native run:

```sh
kicad-team design-lint --catalog --format text
kicad-team design-lint --catalog --format json
```

The read-only MCP tool `list_design_lint_rules` returns the same typed catalog.
Use this view before adding project overrides; `review`, `block`, and `off`
are explicit project decisions, and the rule metadata states what each check
can and cannot establish.

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
A successful export with no component records is `BLOCKED`; netlist-based
heuristics cannot run on an empty inventory. A nonempty inventory alone does
not establish completeness, which remains the job of the independently authored
component/net contract.

The `mapped_check_runs` records distinguish an absent optional map
(`NOT_CONFIGURED`) from a map comparison that ran and found no mismatch
(`EVALUATED`, zero findings). The first slice covers the USB data-path, series
power-path, and power-sequence maps, which previously had no dedicated coverage
field. Each evaluated entry binds the exact map digest and native netlist
digest, reports the authored map-entry count and emitted finding count, and
retains the rule mode. A rule set to `off` is still evaluated so the report can
show its candidate findings with `RULE_OFF` disposition. A configured map with
no native netlist digest is `BLOCKED`. `NOT_CONFIGURED` means that no
project-authored requirement was supplied; it does not claim the topology is
not required. Other project maps keep their existing domain-specific coverage
reports.

## Record a decision in the project

Native `verify` and `ci --kicad` run design lint automatically for PCB and
schematic projects. Add `design_lint` inside the project's `tests/contract.json`
to record rule overrides or exact ignores. The report records the project-owned
contract's path and digest separately from the native schematic source hashes:

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

Each netlist rule defaults to `review`. Schematic geometry rules default to
`off` and run only when a project explicitly sets their mode to `review` or
`block`. A project can set `block` to make an open finding a policy failure or
`off` to disable a rule across that project; both require a reason, and the
report still shows findings under `RULE_OFF`.
An exact ignore suppresses only one observed finding and remains visible with
its reason. Prefer exact ignores when only one pattern is intentional. A `PASS`
means all current lint findings were reviewed or disabled according to this
project policy; it does not approve the wiring.

## Require PCB return paths and declared isolation

The electrical analysis contract has a separate `pcb_return_paths` section
for the physical PCB stage. It requires the project to name exact pads, their
expected net and footprint, and which pads form one return domain. A direct
domain requires a common net and one native copper-connected pad group:

```json
{
  "pcb_return_paths": {
    "mode": "required",
    "basis": "Reviewed external connector return requirement",
    "domains": [
      {
        "id": "serial-returns",
        "basis": "Approved synthetic DB9 pinout",
        "topology": "direct",
        "endpoints": [
          {
            "pad": "J1.7",
            "net": "0V_SERIAL",
            "footprint": "Synthetic:DB9"
          },
          {
            "pad": "J2.7",
            "net": "0V_SERIAL",
            "footprint": "Synthetic:DB9"
          }
        ],
        "bonds": []
      }
    ]
  }
}
```

For a reviewed bond between differently named nets, use `"topology": "bonded"`
and list each fitted KiCad net-tie reference, exact footprint, and pad group in
`bonds`. Net-tie pad groups are checked against native KiCad data. The report
also compares the separately declared return domains for unintended shared
copper or fitted net ties, so intentional isolation stays explicit.

Run the normal electrical analysis command to capture this evidence. The
adapter uses the project's digest-pinned KiCad 10 image, refills zones in
memory, and retains exact board, pad, net, footprint, DNP, copper-group,
connected zone UUID/layer, per-pad filled-island indexes and count, indexes no
observed pad touches, and net-tie evidence. The probe intersects each filled
island polygon with the pad's effective copper shape and retains the matching
zero-based indexes. Zone names are retained for review but are not treated as
stable identities. The
probe also retains via geometry, layer spans, via kind and multiplicity with
stable IDs derived from canonical geometry rather than KiCad's load-specific
object UUIDs. Each pad records the vias in its native copper component. Reports
show their positions and layer transitions; they do not infer an ordered route
through the tracks or calculate capacity. The board source is mounted read-only
and is never saved by the probe. The currently supported native API boundary is
KiCad 10.

The native fixture lane checks direct same-net routes across layers and retains
the transition via's geometry and per-endpoint component membership in both the
connected and open controls. It also checks a connected copper plane and
same-net split planes, including a connected return plane with an additional
filled island that has no pad anchor. That index is review evidence; the tool
does not infer that the island is electrically isolated or defective. The lane
checks a fitted net tie between two distinct return nets and the same bond marked
DNP. The net-tie controls retain the exact footprint, pad group, population
state, and the two separate native copper groups at its pads. KiCad reports the
zone identity for each pad,
while pad connectivity groups show whether the returns actually share copper.
The zone controls include SMD and plated through-hole pads on split planes; the
probe preserves polygon holes and maps each pad to the island indexes its
copper shape touches. Two additional controls declare separate return domains:
one keeps both domains disconnected, and one adds a fitted net tie that must
make the isolation check fail.
If KiCad says a pad connects to a zone but no filled island intersects its
effective copper shape, evidence capture fails instead of emitting an
incomplete island map. These indexes describe KiCad's current board geometry.

Older electrical contracts remain readable, but `pcb_return_paths` now starts
as `pending` and keeps coverage open until the project declares requirements or
an explicit not-applicable reason. Set it to `not_applicable` for a reviewed
schematic-only project or when no PCB return-path requirement applies. A
missing contract is a coverage gap; this tooling does not infer common grounds
from connector names or similar pin functions.

This check proves connectivity only in KiCad's current board model. It does
not prove manufactured continuity, electrical capacity, bond impedance,
fabrication readiness, or first-article acceptance. A separate review and
physical continuity test remain necessary for those claims. For a declared net
tie, the check verifies the native pad group, footprint identity, and DNP state;
it does not prove that the footprint contains conductive copper joining those
pads. Review that footprint geometry and verify continuity on a first article.

## Declare I2C responder addresses

Address checks need an explicit project map in `design_lint.i2c_address_map`.
The map declares each responder, exact symbol identity, SDA/SCL pins, and
static-address basis. Strapped addresses also map every checked address bit to
a symbol pin, pin function, and exact nets for logic low and high:

```json
{
  "design_lint": {
    "i2c_address_map": {
      "basis": "Synthetic approved controller and responder pinout",
      "segments": [
        {
          "id": "main",
          "sda_net": "I2C_SDA",
          "scl_net": "I2C_SCL",
          "responders": [
            {
              "reference": "U1",
              "expected_symbol": "Synthetic:EEPROM",
              "sda_pin": "U1.1",
              "scl_pin": "U1.2",
              "mode": "strapped",
              "address": 80,
              "address_bits": [
                {
                  "bit": 0,
                  "pin": "U1.3",
                  "function": "A0",
                  "low_net": "GND",
                  "high_net": "+3V3"
                }
              ],
              "basis": "Synthetic part pinout and reviewed 7-bit address 0x50"
            },
            {
              "reference": "U2",
              "expected_symbol": "Synthetic:EEPROM",
              "sda_pin": "U2.1",
              "scl_pin": "U2.2",
              "mode": "fixed",
              "address": 81,
              "address_bits": [],
              "basis": "Synthetic part has a fixed 7-bit address 0x51"
            }
          ]
        }
      ]
    }
  }
}
```

Addresses are seven-bit values written as decimal JSON integers. `fixed` means
the reviewed map supplies the static address and no address-pin mappings.
`strapped` means each listed bit must resolve to exactly its declared low or
high net; the scanner derives the observed address from those source-bound
assignments. `dynamic` accepts no static value or address pins and remains an
explicit coverage gap. This example uses synthetic identifiers and values.

The mismatch and collision rules default to `review`; project overrides can
set either to `block` or `off` with a reason. A mismatch finding is emitted
only for a complete strapped responder. A collision finding includes complete,
fitted responders whose observed addresses match on the same declared segment.
The native netlist hash, symbol identity, bus-pin nets, address-pin functions,
and resolved strap bits appear in the coverage report. DNP responders are
excluded from collision groups. Unresolved or dynamic entries keep coverage
incomplete, so they cannot be mistaken for proven unique addresses.

The map is a reviewed requirement, not a device database. This check does not
discover unlisted or off-board responders, firmware-selected addresses, reset
state changes, or mux isolation by itself. Each electrically isolated mux
channel must be represented as a separate segment with distinct signal nets;
the model rejects segments that share either signal net. Correctness of the
part pinout, address basis, and segment map remains a project review decision.

The report's `i2c_address_coverage` is `NOT_REQUESTED` when no map exists,
`COMPLETE` when every mapped responder has source-bound static or not-fitted
coverage, `INCOMPLETE` when an entry is unresolved or dynamic, and `BLOCKED`
when trusted native evidence is unavailable. An incomplete map keeps lint at
`REVIEW`; a blocked map keeps it `BLOCKED`.

## Review external-interface protection coverage

Connector pinout coverage and protection applicability are separate project
decisions. When an interface pin is mapped in the project connector catalog,
design lint asks for a protection disposition. Record `required` with an exact
device channel map, or `not_required` with the review basis. This records that
each mapped interface pin was considered; it does not recommend protection
for every pin. USB-C CC, VBUS, and ground pins already covered by the USB-C
electrical contract are reported as handled there. A connector signal whose
observed net matches a pin in that contract's exact protector map is also
handled there, avoiding duplicate prompts.

Add the map to `tests/contract.json` under `design_lint.external_protection_map`:

```json
{
  "design_lint": {
    "external_protection_map": {
      "basis": "Synthetic reviewed connector and protector pinout",
      "interfaces": [
        {
          "connector_reference": "J1",
          "expected_connector_symbol": "Synthetic:UsbPort",
          "expected_connector_footprint": "Synthetic:USB-C",
          "connector_pin": "J1.1",
          "signal_net": "USB_DP",
          "disposition": "required",
          "basis": "Synthetic reviewed direct clamp channel",
          "channels": [
            {
              "device_reference": "D1",
              "signal_pin": "D1.1",
              "reference_pin": "D1.2",
              "reference_net": "GND"
            }
          ]
        },
        {
          "connector_reference": "J1",
          "expected_connector_symbol": "Synthetic:UsbPort",
          "expected_connector_footprint": "Synthetic:USB-C",
          "connector_pin": "J1.2",
          "signal_net": "USB_DM",
          "disposition": "not_required",
          "basis": "Synthetic approved module provides protection"
        }
      ],
      "devices": [
        {
          "reference": "D1",
          "expected_symbol": "Synthetic:TVS",
          "expected_footprint": "Synthetic:SOD323",
          "pin_nets": {
            "D1.1": "USB_DP",
            "D1.2": "GND"
          }
        }
      ]
    }
  }
}
```

The connector symbol and footprint are checked for each declared interface
pin. Required channels name a protector signal pin and reference pin, while the
device map accounts for every native symbol pin with an expected net or an
explicit reason for an unmapped pin. A missing applicability decision is a
review finding. A stale connector or device identity, changed pin inventory,
DNP required device, or changed net assignment makes the mapped coverage
incomplete and emits `protection.mapped_device_mismatch`; a project may set
that rule to `block` after reviewing the requirement. The current topology
models direct shunt channels. It does not model series protection paths.

This contract verifies the authored symbol-level mapping against KiCad's
source-bound native netlist. It does not validate datasheet pinout truth,
clamp voltage, pulse rating, capacitance, package suitability, placement,
return-via geometry, copper continuity, or protection effectiveness. An
intentionally isolated or integrated-protection design needs a clear
`not_required` basis. These checks are synthetic-validated and use no private
board fixtures.

## Review a mapped USB connector-to-PHY data path

USB 2.0 data-line series components depend on the selected PHY. Do not treat a
connector name or D+/D− labels as a universal resistor requirement. Add
`design_lint.usb_data_path_map` to `tests/contract.json` only after reviewing
the selected PHY's requirements. Each entry identifies the connector, PHY,
exact D+/D− pins, expected nets, and either a direct path or one fitted series
resistor per line.

```json
{
  "design_lint": {
    "usb_data_path_map": {
      "basis": "Synthetic USB data path contract",
      "interfaces": [
        {
          "id": "external-usb-phy",
          "basis": "Synthetic PHY datasheet review selects 27R series components",
          "connector_reference": "J1",
          "expected_connector_symbol": "Synthetic:UsbA",
          "expected_connector_footprint": "Synthetic:USB-A",
          "phy_reference": "U1",
          "expected_phy_symbol": "Synthetic:TUSB2036",
          "expected_phy_footprint": "Synthetic:QFN",
          "positive": {
            "line": "D+",
            "connector_pin": "J1.1",
            "phy_pin": "U1.1",
            "connector_net": "USB_DP_PORT",
            "phy_net": "USB_DP_PHY",
            "topology": "series_resistor",
            "series_resistor": {
              "reference": "R1",
              "expected_symbol": "Device:R",
              "expected_footprint": "Synthetic:0603",
              "minimum_ohms": 27,
              "maximum_ohms": 27
            }
          },
          "negative": {
            "line": "D-",
            "connector_pin": "J1.2",
            "phy_pin": "U1.2",
            "connector_net": "USB_DM_PORT",
            "phy_net": "USB_DM_PHY",
            "topology": "series_resistor",
            "series_resistor": {
              "reference": "R2",
              "expected_symbol": "Device:R",
              "expected_footprint": "Synthetic:0603",
              "minimum_ohms": 27,
              "maximum_ohms": 27
            }
          }
        }
      ]
    }
  }
}
```

For a documented integrated PHY with no external series parts, declare
`topology: "direct"`, set `connector_net` and `phy_net` to the same net, and
omit `series_resistor`. The project remains responsible for the PHY decision
and its basis. The rule defaults to `review`; a project can set
`bus.usb_data_path_mismatch` to `block` or `off`, or exactly ignore a reviewed
finding. A passing schematic comparison does not prove resistor suitability,
placement, PCB copper continuity, USB-C role behavior, or USB 3.x routing.

For a direct D+/D− interface whose reference decision has also been reviewed,
add the endpoint pin and net assignments to the same interface entry. Both
endpoints need at least one explicit reference pin; multiple pins per endpoint
must all use that endpoint's one declared net. `common_net` requires one shared
net name, while `separate_nets` records distinct expected nets. `bonded` records
two distinct endpoint nets and one exact passive two-pin component intended to
connect them:

```json
{
  "connector_reference_pins": [
    {"pin": "J1.4", "net": "BOARD_GND"}
  ],
  "phy_reference_pins": [
    {"pin": "U1.3", "net": "BOARD_GND"}
  ],
  "reference_policy": "common_net"
}
```

For a designed bond, add the exact component identity and pin assignments:

```json
{
  "connector_reference_pins": [
    {"pin": "J1.4", "net": "USB_GND"}
  ],
  "phy_reference_pins": [
    {"pin": "U1.3", "net": "BOARD_GND"}
  ],
  "reference_policy": "bonded",
  "reference_bond": {
    "reference": "R3",
    "expected_symbol": "Device:R",
    "expected_footprint": "Synthetic:0603",
    "expected_value": "0R",
    "side_a_pin": "R3.1",
    "side_b_pin": "R3.2",
    "side_a_net": "USB_GND",
    "side_b_net": "BOARD_GND"
  }
}
```

This records the project's decision and lets lint check the exact native pin
assignments and, for a bond, the exact fitted component identity and its native
pin-to-net assignments. It does not prove that the component conducts, that
separate nets are joined elsewhere, or that a common net has continuous PCB
copper. Without this explicit map, the
USB peer heuristic asks for review when the two endpoints use distinct
reference nets. `bus.usb_data_path_mismatch` reports a stale mapped pin or net.

The source-bound regression exports synthetic integrated-PHY,
external-PHY-series-resistor, resistor-bypass, split-reference, and
common-reference schematics plus USB-C duplicate-contact and two-pin shunt
fault/control cases with digest-pinned KiCad 10.0.0 and 10.0.5. It
checks the mapped topology and peer-reference heuristic against each native
netlist and compares repeated parsed netlists for stable content. Both
reference cases keep the data paths intact; the split-reference fault produces
one reference review and the common-reference control produces none. This
exercises schematic export and typed lint behavior, not native ERC or PCB
copper. See the [data-path fixture README] and the
[peer-reference fixture README] for source hashes and reproduction details.

[data-path fixture README]: ../tests/fixtures/design_lint/usb-data-path-native/README.md
[peer-reference fixture README]: ../tests/fixtures/design_lint/usb-peer-reference-native/README.md

## Review a mapped crystal load network

Crystal checks require an explicit project-owned `design_lint.crystal_network_map`.
The map names each oscillator and resonator value, symbol, footprint, and
exact pins. It also names two load capacitors, their signal and reference pins,
acceptable nominal capacitor values, a target load range, and the assumed
stray-capacitance range. Omitting the map does not make the tool guess from a
`Y` reference, part value, or symbol description.

```json
{
  "design_lint": {
    "crystal_network_map": {
      "basis": "Synthetic reviewed oscillator requirements and pin map",
      "networks": [
        {
          "oscillator_reference": "U1",
          "expected_oscillator_value": "Synthetic MCU",
          "expected_oscillator_symbol": "Synthetic:Oscillator",
          "expected_oscillator_footprint": "Synthetic:SOIC-8",
          "oscillator_input_pin": "U1.1",
          "oscillator_output_pin": "U1.2",
          "resonator_reference": "Y1",
          "expected_resonator_value": "Synthetic 16 MHz crystal",
          "expected_resonator_symbol": "Device:Crystal",
          "expected_resonator_footprint": "Synthetic:Crystal-3225",
          "resonator_input_pin": "Y1.1",
          "resonator_output_pin": "Y1.2",
          "load_capacitors": [
            {
              "reference": "C1",
              "expected_symbol": "Device:C",
              "expected_footprint": "Synthetic:0603",
              "signal_pin": "C1.1",
              "reference_pin": "C1.2",
              "minimum_nominal_capacitance_pf": 15.0,
              "maximum_nominal_capacitance_pf": 47.0
            },
            {
              "reference": "C2",
              "expected_symbol": "Device:C",
              "expected_footprint": "Synthetic:0603",
              "signal_pin": "C2.1",
              "reference_pin": "C2.2",
              "minimum_nominal_capacitance_pf": 15.0,
              "maximum_nominal_capacitance_pf": 47.0
            }
          ],
          "reference_net": "GND",
          "minimum_target_load_pf": 10.0,
          "maximum_target_load_pf": 12.0,
          "minimum_stray_capacitance_pf": 1.0,
          "maximum_stray_capacitance_pf": 3.0,
          "basis": "Synthetic datasheet limits and authored stray-capacitance estimate"
        }
      ]
    }
  }
}
```

For the supported two-capacitor Pierce topology, the nominal estimate is
`C1*C2/(C1+C2) + Cstray`. The observed values must use an explicit `pF`, `nF`,
`uF`, `p`, `n`, or `u` suffix and fall within their authored nominal ranges.
The whole calculated range must fit inside the authored target range. Missing
or mismatched identities, pin inventories, pin assignments, or fitted parts
leave mapped coverage incomplete and create a review finding; an out-of-range
estimate creates the same catalogued review rule. Project policy can set the
rule to `block` or `off` with a reason, and exact finding ignores remain
source-evidence-specific.

The `crystal_network_coverage` report binds the comparison to the native
netlist digest and shows mapped pin nets, observed capacitance values, the
calculated range, target range, stray-capacitance assumption, and authored
basis. A separate two-pin part with an explicit capacitance value on an
oscillator signal and the reference net is flagged as a potential unlisted
load capacitor for review. The formula uses nominal capacitor values; it does
not model component tolerances. This is not proof of oscillator startup,
frequency accuracy, drive level, ESR margin, parasitics, layout quality, or environmental
performance. This rule is synthetic-validated only and does not use private
board fixtures.

## Review an adjustable regulator feedback divider

The `power.regulator_feedback_mismatch` rule needs a project-owned
`design_lint.regulator_feedback_map`. The project must map the exact regulator
and resistor symbols, footprints, pins, output/reference nets, the feedback
reference-voltage bounds, the acceptable nominal resistor values, and the
target output range.

```json
{
  "design_lint": {
    "regulator_feedback_map": {
      "basis": "Synthetic reviewed adjustable-regulator requirements",
      "regulators": [
        {
          "id": "main-rail",
          "regulator_reference": "U1",
          "expected_regulator_value": "SYNTH-ADJ",
          "expected_regulator_symbol": "Synthetic:AdjustableRegulator",
          "expected_regulator_footprint": "Synthetic:SOIC-8",
          "output_pin": "U1.1",
          "expected_output_pin_function": "OUT",
          "feedback_pin": "U1.2",
          "expected_feedback_pin_function": "FB",
          "output_net": "REG_OUT",
          "reference_net": "GND",
          "upper_resistor": {
            "reference": "R1",
            "expected_symbol": "Device:R",
            "expected_footprint": "Synthetic:0603",
            "feedback_pin": "R1.2",
            "rail_pin": "R1.1",
            "minimum_nominal_resistance_ohms": 178200.0,
            "maximum_nominal_resistance_ohms": 181800.0
          },
          "lower_resistor": {
            "reference": "R2",
            "expected_symbol": "Device:R",
            "expected_footprint": "Synthetic:0603",
            "feedback_pin": "R2.1",
            "rail_pin": "R2.2",
            "minimum_nominal_resistance_ohms": 32670.0,
            "maximum_nominal_resistance_ohms": 33330.0
          },
          "minimum_feedback_reference_voltage_v": 0.792,
          "maximum_feedback_reference_voltage_v": 0.808,
          "minimum_target_output_voltage_v": 5.1,
          "maximum_target_output_voltage_v": 5.22,
          "basis": "Synthetic device reference bounds and board output requirement"
        }
      ]
    }
  }
}
```

The mapped output and feedback pin functions must also match the exported
symbol functions. The upper resistor's `rail_pin` must be on `output_net`; its `feedback_pin`
must share one net with the regulator FB pin and the lower resistor's
`feedback_pin`. The lower resistor's `rail_pin` must be on `reference_net`.
Both resistor values must parse as a supported nominal resistance and fall
within their authored ranges. The calculated interval is
`Vref*(1+Rupper/Rlower)`, using the observed nominal resistor values and the
authored minimum/maximum feedback reference voltages. The entire calculated
interval must fit inside the authored output range. A recognized fitted direct
resistor that also touches the feedback node makes the map incomplete because
the two-resistor equation would omit a DC path.

`regulator_feedback_coverage` binds the result to the native netlist digest and
reports each mapped pin's observed net, nominal resistor values, formula,
calculated interval, target interval, and authored basis. A missing pin,
stale identity, DNP part, unsupported value, wrong net, or extra recognized
feedback resistor is incomplete coverage. An out-of-range nominal value or
setpoint emits a finding that project policy can set to `block` or `off`.
Without a map the rule makes no claim about mapped or unmapped regulators;
fixed-output devices and alternate feedback topologies are not inferred.
If the nominal equation exceeds the supported finite numeric range, coverage
is incomplete and the report omits the calculated interval.

This static check does not model resistor tolerance, FB bias current, loop
stability, compensation, startup, load response, device ratings, copper
continuity, or feedback routing. Compensation capacitors do not affect the
nominal DC equation and are not evaluated. Existing power-connectivity checks
only verify authored source/load pin membership, so they remain unchanged when
a divider value changes; the synthetic regression confirms the new rule adds
that setpoint coverage. This check uses synthetic fixtures only.

## Review a mapped first-order RC filter

The `filter.rc_corner_mismatch` rule runs only when the project supplies
`design_lint.rc_filter_map`. The project names each resistor and capacitor,
their symbols, footprints, pins, input, filtered, and reference nets, acceptable
nominal values, target corner range, and review basis. Without the map, the
coverage report is `NOT_REQUESTED` and the linter does not infer a filter from
component references, values, or net names.

```json
{
  "design_lint": {
    "rc_filter_map": {
      "filters": [
        {
          "id": "sensor-input",
          "resistor_reference": "R1",
          "expected_resistor_symbol": "Device:R",
          "expected_resistor_footprint": "Synthetic:0603",
          "resistor_first_pin": "R1.1",
          "resistor_second_pin": "R1.2",
          "capacitor_reference": "C1",
          "expected_capacitor_symbol": "Device:C",
          "expected_capacitor_footprint": "Synthetic:0603",
          "capacitor_signal_pin": "C1.1",
          "capacitor_reference_pin": "C1.2",
          "input_net": "FILTER_IN",
          "filtered_net": "FILTER_OUT",
          "reference_net": "GND",
          "minimum_nominal_resistance_ohms": 900.0,
          "maximum_nominal_resistance_ohms": 1100.0,
          "minimum_nominal_capacitance_pf": 90000.0,
          "maximum_nominal_capacitance_pf": 110000.0,
          "minimum_target_corner_hz": 1500.0,
          "maximum_target_corner_hz": 1700.0,
          "basis": "Synthetic reviewed input-filter requirement"
        }
      ]
    }
  }
}
```

The check verifies exact component identity, footprint, complete two-pin
inventory, fitted state, mapped pin/net membership, supported nominal values,
and recognized extra fitted resistors or capacitors directly across the mapped
nodes. It estimates the nominal corner with `1/(2*pi*R*C)`. The report binds
coverage to the native netlist SHA-256 and shows the observed values, pin nets,
calculated corner, target range, and authored basis. Missing or mismatched
mapping evidence is `INCOMPLETE`; an out-of-range value or corner emits a
finding that project policy can set to `block` or `off`. Exact finding ignores
are tied to the evidence fingerprint.

The synthetic value-mutation test changes C from `100nF` to `220nF` while all
pin-to-net assignments remain the same. Connectivity therefore remains
unchanged while this source-bound value comparison reports a nominal corner
outside the target. The comparison is separate from project-authored SPICE
decks; equivalent SPICE detection was not benchmarked. The estimate does not
model source or load impedance, multiple poles, active filters, component
tolerance, transient response, analog safety, or PCB copper. Extra-part
recognition is limited to supported two-pin passive reference patterns. These
synthetic checks use no private board fixtures.

## Review connector return-contact distribution

`connector.return_distribution` runs only for an interface that has an
explicit project threshold in `design_lint.connector_return_distribution_map`.
The interface catalog may assign each pin a role: `signal`, `return`,
`supply`, `shield`, or `other`. This is an authored classification; the rule
does not infer roles from pin names, symbol functions, net names, or connector
type. When a threshold is configured, every mapped interface pin needs a
role. Supply, shield, and other contacts are reported but excluded from the
ratio. Without a configured threshold, coverage is `NOT_REQUESTED`.

For example, the shared interface record can classify its contacts this way:

```json
{
  "id": "service-link",
  "revision": "reviewed-rev-a",
  "pins": [
    {"number": "1", "signal": "TX", "role": "signal", "direction": "output", "voltage_domain": "logic-domain", "mating": "RX", "orientation": "straight", "mechanical_clearance": "reviewed"},
    {"number": "2", "signal": "RX", "role": "signal", "direction": "input", "voltage_domain": "logic-domain", "mating": "TX", "orientation": "straight", "mechanical_clearance": "reviewed"},
    {"number": "3", "signal": "RETURN", "role": "return", "direction": "passive", "voltage_domain": "return-domain", "mating": "RETURN", "orientation": "straight", "mechanical_clearance": "reviewed"},
    {"number": "4", "signal": "SHIELD", "role": "shield", "direction": "passive", "voltage_domain": "chassis-domain", "mating": "SHIELD", "orientation": "straight", "mechanical_clearance": "reviewed"}
  ]
}
```

The project contract supplies both threshold values and the design basis:

```json
{
  "design_lint": {
    "connector_return_distribution_map": {
      "requirements": [
        {
          "id": "service-link-return-allocation",
          "interface_id": "service-link",
          "minimum_signal_pin_count": 2,
          "maximum_signal_to_return_ratio": 2.0,
          "basis": "Reviewed synthetic interface return-contact allocation"
        }
      ]
    }
  }
}
```

The report binds counts to the native netlist and interface-catalog digests. It
lists each mapped pin by role, observed signal and return counts, required
return-contact count at the configured ratio, and exact threshold. A missing
role or incomplete connector mapping leaves coverage `INCOMPLETE` and lint at
`REVIEW`; an out-of-range ratio emits a finding that the project can set to
`block` or `off`, or ignore by exact fingerprint. The default finding mode is
`review`.

The ratio asks whether a reviewed connector allocates enough return contacts
for its signal count under the project's own threshold. It does not declare
that the contacts must be electrically common, prove return-current capacity,
PCB continuity, shield termination, chassis bonding, isolation, or off-board
wiring. Use `pin_connectivity` and `grounding` contracts to specify shared,
bonded, or isolated relationships. Existing repeated-return findings continue
to report suspicious net splits independently. Synthetic controls show that
two returns on one net and two returns on separate nets have the same ratio
result; the latter can still produce that separate repeated-return review.

## Review mapped PCB track widths

Add a project-authored minimum for each exact net that needs a width screen.
The example is synthetic; choose thresholds from the project's reviewed
fabrication and electrical requirements.

```json
{
  "design_lint": {
    "pcb_track_width_map": {
      "schema_version": "1",
      "basis": "Synthetic reviewed copper-width screen",
      "requirements": [
        {
          "id": "synthetic-core-rail",
          "basis": "Synthetic project minimum for this routed net",
          "net": "VDD",
          "minimum_width_um": 250
        }
      ]
    }
  }
}
```

The check compares native integer-nanometer track widths against the authored
micrometer minimum, including the exact boundary. A finding records each
below-minimum track's native UUID, copper layer, width, and endpoints. Nets
with no track items produce incomplete coverage, since their copper may be
zone-only or unrouted. A single minimum applies across all copper layers for a
mapped net. This screen does not inspect zones or vias, establish track
connectivity, or calculate ampacity, temperature rise, pulse-current limits,
or electrical performance. It is not a replacement for native DRC or a
project-specific copper calculation.

The measurement is taken from a native KiCad PCB geometry snapshot bound to
the board hash, project netlist hash, exact KiCad version/image, and probe
digest. Synthetic native fault/boundary controls are exercised on pinned KiCad
10.0.0 and 10.0.5 images. The rule defaults to `review`; project policy can set
`block` or `off`, or retain a reasoned exact fingerprint ignore.

Snapshot schema 8 records whether each observed track is a straight segment
or arc and which native pad/via copper shapes each endpoint touches. Snapshot
schema 9 adds canonical integer-nanometer filled-zone island outlines and hole
rings, bound to the same board, exact KiCad image, and probe digest.
Snapshot schema 10 adds target aperture shape and diameter to native access
probe observations. Current source-bound KiCad 10 geometry captures require
schema 10; these aperture fields do not change the schema 9 zone-contour data.
The probe copies each native filled-zone polygon set and calls KiCad's
`SHAPE_POLY_SET.Unfracture()` before recording its outlines and holes. This
preserves clearances that KiCad's filled result represents as fractured outline
paths, without changing the board or its in-memory zone fill. It uses KiCad's
effective pad/via copper shapes for contact evidence and records other native
tracks connected at each endpoint. This
supports exact endpoint-adjacency evidence on the pinned KiCad versions. It
can resolve an explicitly mapped trace edge to one unique native track chain,
and reports its ordered integer-nanometer centerline and length. Missing,
branched, ambiguous, or arc-containing chains remain incomplete. Candidate
tracks come from KiCad's
[`CONNECTIVITY_DATA.GetConnectedTracks`](https://docs.kicad.org/doxygen-python-10.0/classpcbnew_1_1CONNECTIVITY__DATA.html)
API, then native effective track shapes are checked at the exact endpoint.

## Review adjacent reference-plane coverage

Use `design_lint.pcb_reference_plane_map` to screen exact signal nets and route
layers against a project-selected reference net. The example thresholds are
synthetic; set them only from a reviewed interface or layout requirement.

```json
{
  "design_lint": {
    "pcb_reference_plane_map": {
      "schema_version": "1",
      "basis": "Synthetic reviewed signal-return layout screen",
      "requirements": [
        {
          "id": "synthetic-data-reference",
          "basis": "Synthetic route layer and reference selection",
          "signal_net": "DATA",
          "signal_layers": ["F.Cu"],
          "reference_net": "GND",
          "minimum_track_length_um": 1000,
          "minimum_referenced_fraction": 0.9,
          "review_excluded_short_tracks": true
        }
      ]
    }
  }
}
```

For each mapped straight track at least the authored minimum length, the check
measures the exact rational share of its centerline inside filled zones on each
immediately adjacent copper layer. Same-net zones on one layer are combined;
each neighboring layer is measured independently. A track only emits a
below-threshold finding when every immediately adjacent layer misses the
authored fraction. Short segments are excluded and always listed with their IDs
in the human-readable and machine-readable reports. By default they are outside
the configured measurement scope; set `review_excluded_short_tracks` to `true`
to mark coverage incomplete and raise a review when any are excluded. Unsupported
arcs, absent mapped layers, missing tracks, or tracks without an adjacent copper
layer also leave coverage incomplete. Copper clearances around pads and vias
count as uncovered centerline length.

This is a review screen for likely reference-plane gaps. It does not infer
design intent or ground domains, measure trace-width overlap or return-current
fields, prove that a zone island connects to endpoint pads, or establish return
path continuity, emissions, or electrical performance. The report identifies
mapped endpoint vias whose centers fall inside a reference-zone hole. That is
clearance context only: the intervals still count as uncovered, and the hole
may include other clearance geometry. A signal via's expected antipad can
therefore prompt review, especially on short segments; inspect the mapped route
and keep this rule in `review` mode. Project policy can set `block` or `off`, or
retain a reasoned exact fingerprint ignore. The report binds the map, board,
KiCad version and image, native snapshot, netlist, and probe digest. Synthetic
geometry and CLI/MCP parity controls are available; the native fixture lane
validates source-bound filled-contour extraction, including a through-via
antipad and its native track-endpoint contact, on pinned KiCad versions.

## Review switching-current loop geometry

Use `design_lint.pcb_switching_loop_map` only when the project has an
independently reviewed switching topology and exact PCB pad mapping. The
`loop_pads` list is ordered around the intended current path. The analyzer
checks each pad's exact footprint, net, fitted state, and native center, then
calculates the shoelace area through those centers. A project may set an
`maximum_area_um2` review threshold; without one, the measured proxy remains a
review finding.

```json
{
  "design_lint": {
    "pcb_switching_loop_map": {
      "schema_version": "1",
      "basis": "Synthetic reviewed switching topology and stack-up",
      "requirements": [
        {
          "id": "synthetic-buck-input-loop",
          "basis": "Synthetic input capacitor and switching path mapping",
          "loop_pads": [
            {"pad": "Q1.1", "footprint": "Synthetic:QFN", "net": "VIN"},
            {"pad": "C1.1", "footprint": "Synthetic:Cap_0603", "net": "VIN"},
            {"pad": "C1.2", "footprint": "Synthetic:Cap_0603", "net": "GND"},
            {"pad": "Q1.2", "footprint": "Synthetic:QFN", "net": "GND"}
          ],
          "return_net": "GND",
          "return_plane_layer": "In1.Cu",
          "return_plane_pads": [
            {"pad": "C1.2", "footprint": "Synthetic:Cap_0603", "net": "GND"},
            {"pad": "Q1.2", "footprint": "Synthetic:QFN", "net": "GND"}
          ],
          "maximum_area_um2": 5000,
          "route_edges": [
            {"from_pad": "Q1.1", "to_pad": "C1.1", "kind": "trace", "net": "VIN", "layers": ["F.Cu"]},
            {"from_pad": "C1.1", "to_pad": "C1.2", "kind": "component", "component_reference": "C1"},
            {"from_pad": "C1.2", "to_pad": "Q1.2", "kind": "plane", "net": "GND", "plane_layer": "In1.Cu"},
            {"from_pad": "Q1.2", "to_pad": "Q1.1", "kind": "component", "component_reference": "Q1"}
          ]
        }
      ]
    }
  }
}
```

The KiCad 10 native PCB snapshot records the enabled copper stack and each
mapped pad's filled-zone identities and island indexes. Schema 9 also retains
each filled island's exact canonical contour vertices and holes. The native
probe reads each filled outline and hole ring from KiCad's
[`SHAPE_POLY_SET.COutline` and `CHole`](https://docs.kicad.org/doxygen-python-10.0/classpcbnew_1_1SHAPE__POLY__SET.html)
and canonicalizes its integer vertices. The return-plane check
requires all mapped return pads to touch the same filled island of a zone on
the declared layer and net. A split plane, absent layer, missing center, DNP
pad, or unsupported mapping remains visible as incomplete coverage.

The area is a polygon through pad centers, not the routed loop contour. The
check does not follow traces or zone outlines, estimate parasitics or emissions,
or establish switching performance. A shared filled plane island does not
prove that its geometry is adequate. Keep the electrical `pcb_return_paths`
contract for required end-to-end copper connectivity, and record separate
hardware or simulation validation for electrical behavior. The rule defaults
to `review`; project policy may set `block` or `off`, or store an exact
reasoned ignore.

`route_edges` is optional and follows the ordered loop-pad cycle exactly. A
trace edge names its expected net and allowed copper layers; a component edge
names the shared footprint reference; a plane edge names its net and layer.
The analyzer resolves and reports each unique trace chain. Plane edges identify
the unique common native zone island and report its integer-nanometer contour
area from the retained outline and hole rings. The finding reports twice the
shoelace area in integer nm² so the value stays exact. This is only an explicit
filled-copper geometry measurement; it does not estimate current distribution,
loop area, or electrical adequacy. Multiple shared zone identities are marked
ambiguous and do not produce a selected plane. Component internals remain declared with an
explicit evidence limitation, and the route map reports incomplete geometric
coverage. The pad-center polygon remains the only full-loop area metric; the
tool does not calculate a full routed-loop area. Branches, alternate paths,
missing endpoint contacts, out-of-scope vias, and arcs remain incomplete rather
than selecting a convenient route. Trace lengths are geometric evidence, not
a claim about complete current-path adequacy. Synthetic tests verify hole-area
subtraction. The pinned native fixture lane now places an isolated VDD
through-hole pad inside its GND plane and requires a non-empty exported hole
ring with exact bounds around that pad. All four lane cases passed twice on
both digest-pinned KiCad 10.0.0 and 10.0.5 images: the F.Cu trace resolves to
15 mm, an arc remains `UNSUPPORTED_ARC`, the inner plane retains the exact
6 mm square and VDD-pad clearance ring, and the split plane remains
`INCOMPLETE`. The clearance ring bounds are 12.3995–13.6005 mm on both axes
around the synthetic pad at (13, 13) mm. This native evidence tests polygon
capture and route interpretation; it does not establish electrical adequacy.

## Review differential-pair DRC rule coverage

Use this opt-in map when a reviewed interface requirement already defines the
pair identity and its geometric limits. Put it in `design_lint` in the
project's `tests/contract.json`. The example values are synthetic and are not
recommended USB limits.

```json
{
  "design_lint": {
    "pcb_differential_pair_rule_map": {
      "schema_version": "1",
      "basis": "Reviewed interface and stack-up requirement",
      "requirements": [
        {
          "id": "synthetic-usb-data",
          "basis": "Synthetic interface constraint",
          "positive_net": "USB_D_P",
          "negative_net": "USB_D_N",
          "pair_selector": "USB_D_",
          "track_width": {"min_nm": 250000},
          "diff_pair_gap": {"min_nm": 150000, "max_nm": 500000},
          "skew": {"max_nm": 100000},
          "uncoupled_length": {"max_nm": 200000}
        }
      ]
    },
    "rules": [
      {
        "rule_id": "pcb.differential_pair_rule_coverage",
        "mode": "review",
        "reason": "Review native pair-rule coverage against the approved interface limits"
      }
    ]
  }
}
```

The auditor compares each declared constraint with exactly one rule in the
project's `.kicad_dru` file using the exact
`A.inDiffPair('<pair_selector>')` condition and exact min/max values. It reads
ignored severities from the native DRC report, so a rule configured to Ignore
does not count as active. Supported lengths are `mm` and `mil`; supported net
suffixes are `_P`/`_N` and `+`/`-`. Missing rules, changed limits, duplicate
matches, ignored checks, unsupported syntax or units, and unrecognized pair
names remain incomplete review findings. A missing `.kicad_dru` file is
reported as missing coverage.

The report binds the project settings, board, optional rule file, native DRC
report and command, validation summary, selected KiCad version, project image,
and source inventory hashes. The default is `review`; policy can set `block`,
`off`, or an exact fingerprint ignore. A missing map is `NOT_REQUESTED` and
does not infer pair limits from net names. This check audits rule configuration
only. KiCad native DRC evaluates actual board geometry, while engineers remain
responsible for selecting suitable interface and stack-up limits.

When no pair map is present, `pcb.differential_pair_rule_coverage` remains
`NOT_REQUESTED`. The independent
`signal.named_pair_without_reviewed_requirement` heuristic can still identify
common complementary net-name patterns and ask for review; it does not convert
those names into requirements or geometric limits.

## Review mapped PCB decoupling placement

Add exact component pad numbers, footprints, nets, and any reviewed distance
limits to the project's `design_lint` policy. This example uses synthetic
identities and test-only limits; choose project values from an independently
reviewed design requirement.

```json
{
  "design_lint": {
    "rules": [
      {
        "rule_id": "pcb.decoupling_proximity",
        "mode": "review",
        "reason": "Review the mapped bypass network against the device layout guidance"
      }
    ],
    "pcb_decoupling_map": {
      "schema_version": "1",
      "basis": "Synthetic reviewed IC pin map and local bypass requirement",
      "requirements": [
        {
          "id": "synthetic-core-rail",
          "basis": "Synthetic datasheet and placement requirement",
          "ic_reference": "U1",
          "ic_footprint": "Synthetic:IC_QFN",
          "supply_pad": "U1.1",
          "return_pad": "U1.2",
          "supply_net": "VDD",
          "return_net": "GND",
          "selection": "any",
          "max_distance_um": 1000,
          "max_return_via_distance_um": 1000,
          "capacitors": [
            {
              "reference": "C1",
              "footprint": "Synthetic:Cap_0603",
              "supply_pad": "C1.1",
              "return_pad": "C1.2"
            },
            {
              "reference": "C2",
              "footprint": "Synthetic:Cap_0603",
              "supply_pad": "C2.1",
              "return_pad": "C2.2"
            }
          ]
        }
      ]
    }
  }
}
```

The distance is Euclidean center-to-center from the IC supply pad to each
capacitor supply pad, using native KiCad board coordinates transformed through
the placed footprint rotation. The exact comparison uses integer squared
nanometers and includes the configured boundary. `selection: any` accepts one
eligible mapped capacitor within the limit; `selection: all` requires every
mapped candidate to meet it. An eligible candidate must match both expected
nets and footprints, be fitted, and share the native copper connectivity of
the mapped IC supply and return pins. If no distance limit is authored, the
report keeps measured distances and emits a `REVIEW` finding.

When `max_return_via_distance_um` is configured, the same capacitor must also
have a via in its native-connected return-pad component within that limit. The
measurement uses the return pad center and the nearest connected via center;
a physically close via on another net or outside that copper component does
not count. Omitting the field does not require a via. A board that connects a
return pad directly to a plane may be valid without one.

The report names the board and native snapshot hashes, probe hash, exact KiCad
version and image, the connected via identity/count, and both measured
candidate distances. The snapshot is
retained under ignored `build/design-lint/pcb-decoupling-*`. The probe requires
KiCad 10 native `pcbnew` evidence; the synthetic native regression has passed
against the pinned KiCad 10.0.0 and 10.0.5 images. A project can set the rule to
`block` or `off`, or record an exact fingerprint ignore.

This check does not infer decoupling roles. Distance alone does not model the
supply/return loop, plane reference, trace inductance, capacitor value or bias
derating, resonance, transient response, or manufacturing quality. A passing
project threshold is a placement screen, not electrical approval.

## Review a mapped PCB protection-entry path

Use `pcb.protection_entry_path` only after the project has reviewed the
connector pinout and the protection-device pin map. Name the exact board pads,
their expected nets and footprints, and the limits justified by the design.
This rule does not guess that a `GND`-looking net is the intended reference.

```json
{
  "design_lint": {
    "rules": [
      {
        "rule_id": "pcb.protection_entry_path",
        "mode": "review",
        "reason": "Review the authored connector-entry and TVS-reference layout screen"
      }
    ],
    "pcb_protection_path_map": {
      "schema_version": "1",
      "basis": "Synthetic reviewed external-interface pad map",
      "requirements": [
        {
          "id": "synthetic-usb-d-plus-protection",
          "connector_reference": "J1",
          "connector_footprint": "Synthetic:Conn2",
          "connector_signal_pad": "J1.1",
          "protection_reference": "D1",
          "protection_footprint": "Synthetic:TVS",
          "protection_signal_pad": "D1.1",
          "protection_reference_pad": "D1.2",
          "signal_net": "USB_D_P",
          "reference_net": "ESD_RETURN",
          "max_entry_distance_um": 500,
          "minimum_reference_vias": 2,
          "reference_via_radius_um": 3000
        }
      ]
    }
  }
}
```

`max_entry_distance_um` measures Euclidean distance between the connector
signal-pad center and the protector signal-pad center. The optional via fields
count only vias in the mapped reference pad's native copper component and
within its authored radius; configure both fields together. At least one
distance or via-count limit is required. Thresholds are project choices, not
tool defaults.

The report binds the board, native PCB snapshot, probe, exact KiCad version and
image, and netlist digest. Missing or mismatched pads, footprints, nets,
population, native connectivity, geometry, or configured via evidence leave
coverage incomplete. Findings default to `review`; projects may set `block` or
`off`, or record a reasoned exact ignore.

This is a geometric and connectivity screen. Straight-line distance does not
measure routed trace length, current direction, entry order, parasitic
inductance, or transient response. A nearby disconnected via does not count,
but a passing count does not prove a low-inductance path. The check does not
assess clamp suitability, pulse ratings, protection effectiveness, electrical
approval, or manufacturing readiness.

## Opt in to schematic geometry localization

Add any geometry rule entries to the project's `design_lint.rules` list.
Each heuristic has independent project policy and fingerprinted ignores:

```json
{
  "rule_id": "schematic.wire_end_on_pin_line",
  "mode": "review",
  "reason": "Review native-unconnected pins with a wire endpoint along the pin segment"
}
```

```json
{
  "rule_id": "schematic.pin_tip_on_wire_interior",
  "mode": "review",
  "reason": "Review native-unconnected pin tips crossed by a wire segment"
}
```

```json
{
  "rule_id": "schematic.wire_endpoint_near_pin_tip",
  "mode": "review",
  "reason": "Review wire endpoints narrowly missing native-unconnected pin tips"
}
```

```json
{
  "rule_id": "schematic.label_near_wire_endpoint",
  "mode": "review",
  "reason": "Review label anchors placed close to wire endpoints"
}
```

```json
{
  "rule_id": "schematic.unmarked_wire_crossing",
  "mode": "review",
  "reason": "Review orthogonal wire crossings for intended connectivity"
}
```

```json
{
  "rule_id": "schematic.unmarked_t_junction",
  "mode": "review",
  "reason": "Review endpoint-to-interior contacts for missing junction markers"
}
```

```json
{
  "rule_id": "schematic.coincident_text_anchors",
  "mode": "review",
  "reason": "Review free-text objects that share an insertion anchor"
}
```

```json
{
  "rule_id": "schematic.free_text_overlap",
  "mode": "review",
  "reason": "Review distinct free-text objects with overlapping glyph envelopes"
}
```

```json
{
  "rule_id": "schematic.free_text_over_wire",
  "mode": "review",
  "reason": "Review wire centerlines crossing free-text envelopes"
}
```

```json
{
  "rule_id": "schematic.free_text_over_symbol_body",
  "mode": "review",
  "reason": "Review free-text annotations overlapping symbol-body graphics"
}
```

```json
{
  "rule_id": "schematic.wire_through_symbol_body",
  "mode": "review",
  "reason": "Review wire centerlines that overlap symbol-body graphics"
}
```

These rules currently support project-local KiCad `10.0.5` and `10.0.6`
schematic trees in file format `20231120`, embedded single-unit and
single-conversion symbols,
orthogonal rotations, and x/y mirrors. Every reachable child schematic must
remain inside the project source directory and match the native snapshot's
source hashes. Reused child files are scanned once per sheet instance using
the exact KiCad project and hierarchy path to resolve component references.
The native acceptance lane runs the full geometry suite on both exact,
digest-pinned versions. The text-metric resource records its KiCad 10.0.6
calibration source; its SVG comparisons also pass on 10.0.5. Other KiCad
versions remain unsupported until they are added to this version matrix.
The pin geometry rules examine only pins marked unconnected by the matching
source-bound native netlist. Label
localization also uses supported parsed pin tips to exclude labels attached at
pin anchors; unsupported symbol geometry makes dependent pin-localization
rules partial. A
wire_end_on_pin_line candidate
means a wire endpoint lies along the transformed pin segment but away from its
tip. A pin_tip_on_wire_interior candidate means the native netlist marks a pin
unconnected while its transformed tip lies in the strict interior of a wire
segment. A label-near-endpoint candidate means a local, global, or hierarchical
label anchor misses all wire segments and pin tips but lies within the fixed
1.27 mm search radius of one or more wire endpoints. The radius may include an
unrelated nearby endpoint, so inspect the native source and ERC result. Native
ERC already reports a dangling label in the validated fault; this rule improves
localization and is not an additional electrical oracle. A synthetic native
control shows KiCad connects the pin-interior case when a junction marker is
present. The analyzer does not add one automatically.
A wire_endpoint_near_pin_tip candidate means a wire endpoint is more than
0.001 mm and no more than 0.5 mm from a native-unconnected pin tip, excluding
explicit no-connect markers and endpoints already on the pin segment. Its
synthetic fault, threshold boundary, exclusions, project policy, and CLI/MCP
parity are covered. Exact-version native KiCad 10.0.6 netlist/ERC tests cover
this shape and its controls across all 12 supported rotation/mirror
combinations. ERC reports the open pin and dangling wire in the fault; the
geometry finding localizes the likely connection near miss. This is review
evidence, not a separate electrical oracle.

An `unmarked_wire_crossing` candidate records two or more wire UUIDs whose
orthogonal segment interiors meet without a junction marker. Explicit junctions
and endpoint/T contacts are excluded. An intentional unconnected crossing is
valid and produces the same candidate, so the rule stays off by default and
must be reviewed or exactly ignored according to project policy. It does not
infer connectivity from names or override the native netlist.
Graphical-only polylines, rectangles, and circles that cross a native wire are
not treated as wires or junctions. An exact KiCad 10.0.6 synthetic control
confirms these primitives render in SVG while the geometry findings, native
pin/net assignments, and ERC signatures match the schematic without them.

An `unmarked_t_junction` candidate records a wire endpoint that lies within
0.001 mm of another wire segment's strict interior without a junction marker.
The synthetic KiCad 10.0.6 fault leaves two resistor pins on separate nets and
reports an unconnected wire endpoint; adding the marker in the paired control
joins the pins on `/CONTROL_NET` and removes those ERC findings. This is a
useful source-localized review hint, but a T-shaped contact may be intentionally
separate. The rule is off by default, does not infer required connectivity, and
never inserts a junction.

A `coincident_text_anchors` candidate records two top-level free-text objects
whose source insertion anchors are within 0.001 mm. This is a graphical review
prompt only: it does not calculate rendered glyph bounds or prove visible text
overlap, and it treats different text alignments as the same anchor position.
The synthetic pair has identical KiCad ERC findings in the coincident and
separated controls. The rule is off by default and never moves or edits text.

A `free_text_overlap` candidate records two distinct top-level free-text objects
whose conservative glyph envelopes intersect by at least 0.05 mm² after a
0.08 mm per-edge guard. It uses 95 printable ASCII glyph advances plus U+00B0
degree, U+00B1 plus/minus, U+00B5 micro sign, U+00D7 multiplication sign,
U+03A9 ohm sign, and U+2014 em dash advances measured from the exact KiCad
10.0.6 SVG exporter. It supports standard-stroke horizontal text with explicit
positive font sizes. Other Unicode glyphs remain unsupported. Horizontal
placement may be centered by default, represented by an empty `(justify)`
field, or explicitly aligned left or right. Coincident anchors remain the
separate `coincident_text_anchors` rule. Native synthetic renders show the
tested fault's stroke paths intersect and the separated control's paths remain
at least 8.2247 mm apart; native ERC and netlist results are identical between
them. A left/right alignment fault and clear control confirm that the reported
envelope follows the insertion anchor and contains the native SVG strokes; they
also preserve native ERC and netlist results. The axis-aligned envelope can
still flag pairs whose individual strokes do not collide. Plain escaped
multiline text is supported. Its line
spacing is measured as 2.0446 mm at the 1.27 mm reference size from the exact
KiCad 10.0.6 SVG exporter, then scaled with font height; each line uses the
same bounded glyph metrics and the widest line sets the horizontal extent.
Native SVG controls verify the spacing and confirm the reported box contains
all rendered strokes. Vertical or mirrored justification, Unicode glyphs other
than the calibrated set, formatted text, custom faces, bold/italic/thick text,
and rotated text leave enabled text
rules that consume those bounds partial. A doubled backslash followed by
`n` remains literal text; a single KiCad `\\n` escape represents a line break.
Literal source newlines inside quoted S-expressions remain unsupported. The
eight unsupported typography variants have exact KiCad 10.0.6 controls with
unchanged native component identities, pin/net assignments, and ERC signatures.
The rule is off by default, supports project overrides and exact ignores, and
never edits the schematic.

A `free_text_over_wire` candidate records a top-level free-text object and a
native wire segment whose centerline clips the text envelope by at least
0.2 mm after a 0.12 mm edge guard. It shares the `free_text_overlap` font
metrics and therefore supports only standard-stroke horizontal text with the
calibrated glyph set (printable ASCII plus U+00B0, U+00B1, U+00B5, U+00D7,
U+03A9, and U+2014), centered/left/right alignment, and an explicit positive
font size. Other Unicode glyphs leave enabled geometry coverage partial.
Exact KiCad 10.0.6 SVG fault/control evidence confirms the tested wire crosses
the text stroke paths in the fault and remains clear in the control; native
ERC and netlist assignments do not change. Because the check intersects an
axis-aligned glyph envelope, it can still flag intentional note placement or
a gap between glyph strokes. It checks wire objects only, not buses, labels,
symbol fields, pin names or numbers, or symbol graphics. Unsupported text
forms make this rule's coverage partial when enabled. The rule is off by default, supports
project overrides and exact ignores, and never edits the schematic.

A `wire_through_symbol_body` candidate records an electrical wire centerline
inside a supported embedded symbol's axis-aligned body envelope. It supports
single-unit, single-conversion symbols with rectangle, polyline, Bezier, or
circle graphics, plus orthogonal rotations and x/y mirrors. It reports only
after the centerline stays 0.2 mm inside the envelope and overlaps it for at
least 0.3 mm. Envelopes around disjoint, curved, or non-rectangular graphics
can include empty space, so intentional crossings can be candidates. Arcs,
text graphics, multi-unit symbols, and other unsupported primitives leave
this rule's coverage partial when enabled. The finding identifies the symbol, wire, source
hash, sheet instance, body box, and clipped segment; it does not establish pin
connectivity or intent. The synthetic KiCad 10.0.6 fault and clear control
retain identical net assignments and ERC signatures, so this rule adds a
localized drawing review prompt rather than electrical detection. It is off by
default, supports project review, block, off, and exact ignores, and never
changes the schematic.

A `free_text_over_symbol_body` candidate records a top-level, supported
free-text glyph envelope overlapping a supported symbol-body envelope. It
uses the standard-stroke font metrics described above, a 0.1 mm text-edge
guard, a 0.15 mm symbol-body guard, and a 0.1 mm² minimum overlap. Both bounds
are axis-aligned, so spaces between glyph strokes or disjoint symbol graphics
can still produce a candidate. The synthetic KiCad 10.0.6 fault places a note
over a resistor body; the control moves the same note clear. Native SVG shows
the fault's text strokes inside the body region and the control's outside it;
native net assignments and ERC signatures are unchanged. This is drawing
review evidence only. Labels, symbol fields, pin names, and unsupported text
styles are outside this rule or leave its coverage partial when enabled. It is off by
default, supports project review, block, off, and exact ignores, and never
changes schematic geometry.

The report's `schematic_geometry` section binds coverage to the root schematic
path and SHA-256, a canonical source-tree SHA-256 over unique repository-relative
source paths and their hashes, each sheet-instance path and source hash, the
native netlist SHA-256, and the selected KiCad version.
`rule_modes` records each geometry rule's project disposition; `mode`
summarizes the strictest enabled mode. `rule_coverage` reports each rule as
`DISABLED`, `COMPLETE`, `PARTIAL`, or `UNSUPPORTED`, and `unsupported_by_rule`
lists the limitations attached to affected rules. Overall geometry status
aggregates only enabled rules, so an unsupported text shape does not reduce the
coverage of an unrelated enabled wire check.
`NOT_REQUESTED` means the project has no geometry-rule entries; `DISABLED`
means it configured geometry rules but none are enabled. `COMPLETE`,
`PARTIAL`, and `UNSUPPORTED` describe bounded parser coverage, while
`BLOCKED` means source-bound evidence could not be trusted. Partial or
unsupported coverage for an enabled rule leaves the lint report in `REVIEW`,
with limitations listed under the affected rule. Missing child sources or
invalid path mappings block the scan; missing or ambiguous project-instance
reference mappings make dependent rules partial.
The rules never change schematic connectivity or replace ERC.

An exact KiCad 10.0.6 synthetic fault/control pair exercises repeated-sheet
coverage. The native netlist expands a shared child sheet into separate
instance references and open-pin nets in the fault, then assigns each instance
its own hierarchical net in the junction-marked control. Fault ERC reports
one `pin_not_connected` violation against the shared source pin. The recursive
scanner maps that source geometry to both instance references and emits two
separate findings. CLI and MCP parity tests check the tree hash, all three
source bindings, per-instance evidence, and distinct finding fingerprints. A
synthetic source-bound netlist parity case also checks that shared child pin
geometry produces separate `R1.2` and `R2.2` near-miss findings. The native
fault/control regression separately validates repeated-sheet netlist and ERC
behavior. The scan remains review-only; repeated drawings do not establish
whether the connections were intended.

Package acceptance runs the synthetic geometry suite against the digest-pinned
KiCad 10.0.6 image. The container has networking disabled and writes only to
an ignored temporary fixture directory. These eleven rules remain off by
default; native regressions guard their supported behavior without enabling
them for project reports.

## Require an I2C pull-up range

When a reviewed design requirement calls for board-local discrete pull-ups,
record the expected signal nets, rail, and nominal parallel-resistance range
in the project-owned `tests/electrical.json` contract:

```json
{
  "i2c_pullups": {
    "mode": "required",
    "basis": "Synthetic reviewed bus requirement",
    "buses": [
      {
        "id": "service",
        "basis": "Approved synthetic connector and controller pinout",
        "sda": {
          "net": "I2C_SDA",
          "rail": "+3V3",
          "minimum_ohms": 2200,
          "maximum_ohms": 10000
        },
        "scl": {
          "net": "I2C_SCL",
          "rail": "+3V3",
          "minimum_ohms": 2200,
          "maximum_ohms": 10000
        }
      }
    ],
    "arrays": [
      {
        "reference": "RN1",
        "expected_symbol": "Synthetic:ResistorArray",
        "expected_footprint": "Synthetic:RA4",
        "expected_value": "4x4.7k",
        "basis": "Synthetic reviewed datasheet and pin map",
        "channels": [
          {
            "id": "sda",
            "signal_pin": "RN1.1",
            "rail_pin": "RN1.2",
            "signal_net": "I2C_SDA",
            "rail_net": "+3V3",
            "resistance_ohms": 4700,
            "basis": "Synthetic channel one pin pair"
          },
          {
            "id": "scl",
            "signal_pin": "RN1.3",
            "rail_pin": "RN1.4",
            "signal_net": "I2C_SCL",
            "rail_net": "+3V3",
            "resistance_ohms": 4700,
            "basis": "Synthetic channel two pin pair"
          }
        ],
        "unmapped_pin_reasons": {}
      }
    ]
  }
}
```

To check whether a pull-up rail can exceed a connected device pin's reviewed
voltage limit, add `voltage_compatibility` to the SDA or SCL line. The rail
ceiling must include the project's supply tolerance; each input entry names
the exact native pin, symbol, footprint, limit kind, maximum bus voltage, and
its source basis:

```json
"voltage_compatibility": {
  "input_scope_basis": "Synthetic review of all local controller bus endpoints",
  "maximum_rail_voltage_v": 3.45,
  "rail_basis": "Synthetic +3V3 guaranteed maximum including tolerance",
  "input_limits": [
    {
      "pin": "U1.1",
      "expected_symbol": "Synthetic:I2cTarget",
      "expected_footprint": "Synthetic:SOIC8",
      "limit_kind": "absolute_maximum",
      "maximum_bus_voltage_v": 3.6,
      "limit_basis": "Synthetic target datasheet maximum input rating"
    }
  ]
}
```

The check passes at equality and fails when the authored rail ceiling exceeds
any mapped input limit. It also verifies each mapped pin's native symbol,
footprint, pin inventory, population state, and exact line-net assignment.
The project-authored `input_scope_basis` records how reviewers established the
complete local input list; the tool cannot discover an omitted bus endpoint.
These values and source notes are project-authored and source-bound, not
independently verified by tooling. `operating` and `absolute_maximum` identify
which kind of limit the project selected; this check does not establish logic
high margin, transient immunity, bus rise time, capacitance, or sink-current
margin. An absent voltage map means the contract makes no voltage-compatibility
claim.

An optional `electrical_window` on either line derives the lower resistance
bound from the project-reviewed maximum pull-up voltage, maximum low-level
voltage, and weakest-device minimum sink current. It derives the upper bound
from the reviewed maximum bus capacitance and rise-time limit using the
idealized 30%-to-70% relation `tr = 0.8473 × Rp × Cb`:

```json
"electrical_window": {
  "maximum_pullup_voltage_v": 3.45,
  "pullup_voltage_basis": "Synthetic rail maximum including tolerance",
  "maximum_low_level_voltage_v": 0.4,
  "low_level_voltage_basis": "Synthetic weakest-device VOL limit",
  "minimum_sink_current_ma": 3.0,
  "sink_current_basis": "Synthetic weakest-device guaranteed sink current",
  "maximum_bus_capacitance_pf": 100.0,
  "bus_capacitance_basis": "Synthetic total local and cable capacitance bound",
  "maximum_rise_time_ns": 300.0,
  "rise_time_basis": "Synthetic interface timing requirement"
}
```

The authored `minimum_ohms` and `maximum_ohms` are checked against those
derived bounds. Equality passes. The bound values and source notes remain
project inputs; this is not a capacitance extraction or waveform simulation.
The authored `maximum_low_level_voltage_v` and `minimum_sink_current_ma` must
describe the same guaranteed operating point for the weakest applicable bus
device, and the capacitance scope must include all local and remote endpoints
covered by the requirement.
The model does not account for resistor tolerances, nonlinear/active pull-ups,
buffers, off-board loading beyond the authored capacitance, or device-to-device
dynamic behavior. NXP [UM10204 §7.1](https://www.nxp.com/docs/en/user-guide/UM10204.pdf)
derives the 0.8473 factor and pull-up sizing from rise time and bus capacitance;
TI [SLVA689](https://www.ti.com/lit/an/slva689/slva689.pdf) presents the
corresponding sink-current lower bound. Cite the actual part and interface
sources in the project contract rather than copying example values.

To require a conventional resistor chain, add an ordered `series_paths` entry.
List legs from the signal net toward the rail, with an exact identity, net
pair, and nominal range for each resistor:

```json
"series_paths": [
  {
    "id": "sda-chain",
    "basis": "Synthetic reviewed discrete pull-up chain",
    "signal_net": "I2C_SDA",
    "rail_net": "+3V3",
    "resistors": [
      {
        "reference": "R10",
        "expected_symbol": "Device:R",
        "expected_footprint": "Synthetic:R",
        "from_net": "I2C_SDA",
        "to_net": "I2C_SDA_CHAIN",
        "minimum_ohms": 900,
        "maximum_ohms": 1100
      },
      {
        "reference": "R11",
        "expected_symbol": "Device:R",
        "expected_footprint": "Synthetic:R",
        "from_net": "I2C_SDA_CHAIN",
        "to_net": "+3V3",
        "minimum_ohms": 3500,
        "maximum_ohms": 3900
      }
    ]
  }
]
```

The values above are examples, not recommended component values. Electrical
analysis checks the exact named nets against the current source-bound netlist,
combines direct conventional resistors, valid mapped series chains, and
explicitly mapped resistor-array channels in parallel, and fails a configured
line when its equivalent nominal resistance is missing or outside the
inclusive range. A series path must match the declared ordered net sequence;
each leg must match its component identity and resistance range, and every
native pin inventory must contain exactly two pins assigned to the expected
nets. Intermediate nets must contain only the two adjacent resistor pins.
For each array, the contract supplies exact reference, symbol, footprint,
value, channel pins, signal and rail nets, and nominal channel resistance.
Every native array pin must appear in a channel map or have an explicit
`unmapped_pin_reasons` entry. The netlist can verify these identities and
assignments; it cannot establish the array's internal pin topology or channel
resistance. Those values must come from an independently reviewed datasheet
pin map. A direct pull-up to another recognized positive rail also fails the
check. DNP components do not satisfy a required path or channel. The project
contract must be reviewed independently; unless an optional voltage map is
provided, the rule does not determine rail voltage or pin limits. It does not
check bus capacitance, rise time, transient behavior, sink-current margin, or
suitability of an external/internal pull-up.

Set `i2c_pullups` to `{"mode":"not_applicable","reason":"..."}` when the
project has no board-local discrete pull-up requirement, including a reviewed
internal or off-board topology. Set it to `{"mode":"pending","reason":"..."}`
to keep the question visible and prevent the electrical lane from passing.
Older contracts without this section remain readable and make no I2C
pull-up-range claim. Direct paths, exact series paths, and mapped resistor
arrays are only evaluated when the contract declares them.

When the review establishes an actual requirement, express it in the project's
`i2c_pullups`, `can_termination`, grounding, or `pin_connectivity` electrical
contract. Those stronger checks can verify specified bus topology or pin
relationships and can fail a regression even when names or heuristic patterns
change. See [connector pin review](CONNECTOR_PIN_REVIEW.md) and the
[design lint and heuristic backlog](DESIGN_LINT_BACKLOG.md) for planned
coverage, evidence requirements, and synthetic regression criteria.

## Require a CAN termination topology

When the approved bus topology identifies local terminations, record each
required CANH/CANL symbol pin, bus net, logical endpoint, and exact resistor
path in the project-owned `tests/electrical.json` contract:

```json
{
  "can_termination": {
    "mode": "required",
    "basis": "Synthetic reviewed bus topology",
    "buses": [
      {
        "id": "fieldbus",
        "basis": "Approved controller bus interface",
        "high_net": "CAN_H",
        "low_net": "CAN_L",
        "high_pins": ["U1.7"],
        "low_pins": ["U1.6"],
        "endpoints": [
          {
            "id": "local-a",
            "basis": "Local bus-end termination",
            "topology": "direct",
            "resistors": [
              {
                "reference": "R1",
                "first_net": "CAN_H",
                "second_net": "CAN_L",
                "minimum_ohms": 108,
                "maximum_ohms": 132
              }
            ]
          }
        ]
      }
    ]
  }
}
```

The values are examples, not universal CAN requirements. `high_pins` and
`low_pins` identify symbol pins that must map to the corresponding declared
nets; include the bus-facing pins the project wants checked. A second local
end can be added as another direct endpoint. A split endpoint requires two explicitly
mapped resistor legs from `high_net` and `low_net` to one declared
`midpoint_net`, each with its own inclusive resistance range. An `external`
endpoint is reported as `NOT_APPLICABLE` for schematic evidence; an optional
`expected_dnp_resistors` list checks named local options are present, DNP, and
assigned across the declared bus nets. It does not verify remote equipment. A
split endpoint may also declare an optional `midpoint_capacitor` with its exact
reference, symbol, footprint, midpoint and reference pins, reference net, and
inclusive nominal capacitance range. For example:

```json
"midpoint_capacitor": {
  "reference": "C1",
  "expected_symbol": "Device:C",
  "expected_footprint": "Capacitor_SMD:C_0603_1608Metric",
  "midpoint_pin": "C1.1",
  "reference_pin": "C1.2",
  "reference_net": "GND",
  "minimum_nominal_capacitance_pf": 90,
  "maximum_nominal_capacitance_pf": 110
}
```

This check is opt-in and exact: it requires a native pin inventory containing
only the two mapped pins and verifies their net assignments, component
identity, fitted state, and parsed nominal value. It does not infer that every
split termination needs a capacitor, or establish capacitor placement,
bias-voltage derating, impedance, or EMC performance.

The electrical lane compares these requirements with the current
source-bound native netlist and retained evidence replays the same checks.
Missing, DNP, wrong-value, misassigned, or unlisted direct termination parts
fail the authored requirement. The check cannot prove that named endpoints
are physically at opposite bus ends, evaluate cable impedance, or establish
the physical performance of a split midpoint capacitor. Keep ERC/DRC, physical placement review, and
off-board termination evidence separate. Older contracts without this section
make no CAN termination claim; `pending` keeps an unanswered topology visible.
Use `{"mode":"not_applicable","reason":"..."}` when the project has no
CAN interface requiring termination review. An external endpoint belongs in a
required bus declaration so its unverified evidence remains visible.
The separate `bus.can_missing_termination` lint heuristic still asks for
review when no direct resistor is visible. For an approved split or external
topology, record a reasoned project lint decision; the electrical contract
provides the source-bound regression comparison.

## Require a USB-C port role and pin map

Add a reviewed `usb_c` section to project-owned `tests/electrical.json` when a
USB-C port needs a deterministic schematic regression check. Each port declares
its role, connector CC pins/nets, resistor Rp/Rd ranges or exact controller pin
mapping, VBUS pin-to-net assignments on the connector and board sides, ground
pins, and whether exact protection components are required, pending, or not
applicable. For example, a source port with discrete Rp resistors can declare:

```json
{
  "usb_c": {
    "mode": "required",
    "basis": "Reviewed source port pinout and CC requirements",
    "ports": [
      {
        "id": "host-port",
        "basis": "Approved synthetic receptacle role",
        "connector": "J1",
        "role": "source",
        "cc1": {
          "connector_pin": "J1.4",
          "net": "CC1",
          "attachment": {
            "kind": "resistor",
            "behavior": "rp",
            "reference": "R1",
            "rail_net": "+5V",
            "minimum_ohms": 50000,
            "maximum_ohms": 60000
          }
        },
        "cc2": {
          "connector_pin": "J1.5",
          "net": "CC2",
          "attachment": {
            "kind": "resistor",
            "behavior": "rp",
            "reference": "R2",
            "rail_net": "+5V",
            "minimum_ohms": 50000,
            "maximum_ohms": 60000
          }
        },
        "vbus_net": "VBUS_PORT",
        "vbus_pins": [
          {"pin": "J1.1", "net": "VBUS_PORT"},
          {"pin": "U1.1", "net": "VBUS_SYSTEM"}
        ],
        "ground_net": "GND",
        "ground_pins": ["J1.2", "J1.3", "U1.5"],
        "source_rail": "+5V",
        "protection": {
          "mode": "not_applicable",
          "reason": "Protection is covered by a separately reviewed module."
        }
      }
    ]
  }
}
```

The values and topology are examples, not universal USB-C requirements. The
check compares exact pin assignments, fitted resistor references and nominal
ranges, controller/protection identity, footprints, and declared protection
pin nets with the current source-bound native netlist. A controller mapping
proves only the symbol/footprint identity and that its named pins map to CC1
and CC2; it does not inspect firmware, straps, registers, or internal Rp/Rd
behavior. VBUS entries verify the named pins' net assignments separately on
each side; they do not prove continuity through a fuse, switch, connector
contact, or board copper. Current capacity, orientation behavior, PD
negotiation, remote equipment, protection performance, and compliance remain
outside this check. Debug-accessory role is explicitly unsupported and returns
`NOT_RUN`, so it cannot produce a passing electrical lane.

For a controller with a reviewed static mode strap, record the exact pin
relationship in the electrical contract's `pin_connectivity` section. That
shared check can detect a changed or stale schematic pin assignment without
adding controller-specific mode assumptions to the USB-C rule. It verifies the
authored pin/net relationship; the project's cited controller documentation
still determines what that electrical state means.

When the reviewed design requires named series components between connector
VBUS and a board pin, a port may add an optional `vbus_path`. List elements in
connector-to-board order, giving each element's exact symbol, footprint, the
pins on both sides, and the expected net for every mapped pin. A multi-pin
switch can list parallel input pins, output pins, and any control pins whose
net assignment is part of the requirement:

```json
{
  "vbus_path": {
    "id": "input-path",
    "basis": "Reviewed input fuse and load-switch schematic path",
    "connector_pin": "J1.1",
    "connector_net": "VBUS_PORT",
    "board_pin": "U1.1",
    "board_net": "VBUS_SYSTEM",
    "elements": [
      {
        "reference": "F1",
        "symbol": "Device:Fuse",
        "footprint": "Fuse:Fuse_1206_3216Metric",
        "port_side_net": "VBUS_PORT",
        "system_side_net": "VBUS_FUSED",
        "port_side_pins": ["F1.1"],
        "system_side_pins": ["F1.2"],
        "pin_assignments": [
          {"pin": "F1.1", "net": "VBUS_PORT"},
          {"pin": "F1.2", "net": "VBUS_FUSED"}
        ]
      }
    ]
  }
}
```

The contract requires the endpoints to match that port's declared `vbus_pins`
and each element to continue the ordered net chain. The check verifies the
named component exists, is fitted, matches its symbol and footprint, has the
mapped pins in KiCad's native symbol pin inventory, and assigns those pins to
the authored nets. It does not establish conduction through a fuse, switch,
protection device, or connector; switch state or direction; the absence of a
parallel bypass; unlisted component-pin behavior; copper or contact
continuity; current capacity; or power-path suitability. A missing `vbus_path`
does not make a power-path claim and does not change the existing endpoint pin
assignment checks.

Use `{"mode":"pending","reason":"..."}` to keep an unanswered port
requirement visible and prevent the electrical lane from passing. Use
`{"mode":"not_applicable","reason":"..."}` only when the project has no
USB-C port requirement for this check. Older contracts without `usb_c` remain
readable and make no USB-C role claim.

## Require an SPI controller and device map

When the approved schematic intent names an SPI controller and its devices,
record the exact component identities, signal pins, and chip-select membership
in the project-owned `tests/electrical.json` contract:

```json
{
  "spi": {
    "mode": "required",
    "basis": "Synthetic reviewed controller and device pinout",
    "buses": [
      {
        "id": "sensor-bus",
        "basis": "Controller U1 selects the sensor and write-only memory",
        "controller": {
          "reference": "U1",
          "symbol": "Synthetic:SpiController",
          "footprint": "Package_QFP:LQFP-32",
          "sck": {"pin": "U1.1", "net": "SPI_SCK"},
          "mosi": {"pin": "U1.2", "net": "SPI_MOSI"},
          "miso": {"mode": "connected", "pin": "U1.3", "net": "SPI_MISO"},
          "chip_selects": [
            {"pin": "U1.4", "net": "SPI_CS0"},
            {"pin": "U1.5", "net": "SPI_CS1"}
          ]
        },
        "devices": [
          {
            "id": "sensor",
            "reference": "U2",
            "symbol": "Synthetic:SpiPeripheral",
            "footprint": "Package_SO:SOIC-8",
            "sck": {"pin": "U2.1", "net": "SPI_SCK"},
            "mosi": {"pin": "U2.2", "net": "SPI_MOSI"},
            "miso": {"mode": "connected", "pin": "U2.3", "net": "SPI_MISO"},
            "chip_select": {"pin": "U2.4", "net": "SPI_CS0"}
          },
          {
            "id": "memory",
            "reference": "U3",
            "symbol": "Synthetic:SpiWriteOnly",
            "footprint": "Package_SO:SOIC-8",
            "sck": {"pin": "U3.1", "net": "SPI_SCK"},
            "mosi": {"pin": "U3.2", "net": "SPI_MOSI"},
            "miso": {
              "mode": "not_present",
              "reason": "This reviewed write-only device has no MISO pin."
            },
            "chip_select": {"pin": "U3.4", "net": "SPI_CS1"}
          }
        ]
      }
    ]
  }
}
```

Every declared controller chip-select net must map to one or more declared
devices. Two or more devices may share one select only when each names the same
`shared_select_group`; this records an intentional broadcast selection. For an
unused device MISO pin, use `{"mode":"unconnected","pin":"U3.3"}`. Use
`not_present` with a reason when that symbol has no MISO pin. Buffered or
level-shifted signals can declare bridge component identity and exact
`from_pin`/`from_net` and `to_pin`/`to_net` endpoints under `bridges`.

The electrical lane checks exact net assignments, exported symbol pin
inventory, controller/device/bridge symbol and footprint identity, DNP state,
chip-select ownership, and declared direct or bridged routes against the
current source-bound native netlist from the existing version-pinned native
export path (currently the KiCad 10 profile). It does not infer that similarly named
components belong to one bus or that an omitted device should exist. Bridge
checks compare declared endpoints only; they do not verify a buffer's internal
transfer behavior, enable/power conditions, or signal direction. SPI mode,
clock rate, polarity, firmware setup, board copper continuity, and electrical
performance remain outside this check.

Set `spi` to `{"mode":"pending","reason":"..."}` while the bus map awaits
review, so the electrical lane cannot pass. Use
`{"mode":"not_applicable","reason":"..."}` when no SPI membership check
applies. Older contracts without `spi` remain readable and make no SPI map
claim.

## Review unmapped SPI peers across voltage-named rails

`bus.spi_peer_voltage_review` is a default-`review` prompt for a narrow
source-bound case: two fitted U/IC parts share a recognized SPI signal from a
native output-capable pin to a native input-capable pin, each has a complete
native pin-type inventory, and each has exactly one assigned positive
`power_in` rail whose net label contains one explicit voltage token. The rule
reports the two labels and parsed values so a reviewer can check whether a
direct voltage requirement is missing.

The parsed values are clues from net names; they are not measured or sourced
rail voltages. They do not establish device limits or incompatibility. The
rule skips missing or ambiguous pin/supply evidence, DNP parts, unrecognized
SPI names, open-collector signals, and directionally ambiguous peers. It does
not model open-drain or analog buses, translators, external circuitry, timing,
sequencing, loading, or PCB paths.

A complete exact `digital_peer_voltages` entry with sourced output and input
limits suppresses only the matching native pin/net/symbol/footprint link. The
separate mapped voltage check then compares those declared limits. Partial
maps, missing limits, stale identity, or changed assignments leave the review
prompt open. Project lint policy can set the rule to `off` or `block`, and an
exact finding can be ignored through the normal fingerprint workflow. Keep it
at `review` unless a project owner explicitly chooses a stricter policy.

## Review UART peers across voltage-named rails

`bus.serial_peer_voltage_review` applies the same bounded prompt to an exact
native UART/USART TX output connected to an RX input. It requires complete
native pin-type inventories and one unambiguous positive `power_in` supply per
endpoint. TX/RX function names and voltage-explicit rail labels are candidate
evidence only; this rule does not establish compatible or incompatible logic
levels. Use the authored `digital_peer_voltages` contract for sourced limits.
A complete exact map suppresses only the matching pin link, while a partial or
stale map leaves it open for review. The rule defaults to `review` and skips
non-U/IC parts, ambiguous directions, open-drain paths, incomplete pin types,
DNP endpoints, and supplies it cannot identify unambiguously.

The source-bound report also includes one `digital_peer_voltage_coverage`
entry for each rule. It counts recognized and assigned pin functions, direct
peer links, voltage-label comparisons, map-covered mismatches, and review
groups. `NO_SUPPORTED_ENDPOINTS`, `NO_DIRECT_PEERS`, `INCOMPLETE`, and
`EVALUATED` describe only this bounded named-function U/IC scope. An empty
finding list alone does not mean that every interface or voltage relationship
was checked. Coverage is bound to the native netlist and, when configured, the
authored map hash. Net labels remain review clues; these counts do not prove
actual rail voltages or electrical compatibility.

## Review direct UART peers with separate reference pins

`bus.serial_peer_reference_review` prompts when a directionally clear UART
TX-to-RX link includes fitted U/IC parts or connector candidates identified by
the bounded connector scan or a project interface review. It also recognizes a
numbered `UART` or `USART` TX/RX label pair when both nets directly join exactly
one pin from the same two fitted U/IC components. This second path can find
generic pins such as `B1`, `B2`, or `ADBUS0` that native TX/RX function matching
misses. It does not treat those labels as proof of an end-to-end peer or trace
through other components.

Both paths require complete native pin metadata and explicit signal-reference
pins assigned to different native nets. Each endpoint must have one unambiguous
return net across its explicit GND/AGND/DGND/PGND, VSS/VSSA/VSSD/VSSP, 0V, RTN,
RETURN, or GROUND pins. Pin functions marked SHIELD, CHASSIS, FRAME, or PE are
excluded.
Findings include the exact shared signal pins or label assignments and native
reference-pin assignments.
When one IC drives multiple UART headers, each peer is reviewed separately;
a split reference on one header does not make a correctly referenced peer
look faulty.

This is a review question: the nets may be intentionally isolated or joined
through a designed bond. A complete current `serial_peers` direct map suppresses
the prompt only when both component identities, signal assignments, reference
pin assignments, and the declared reference policy match the native netlist.
For `bonded`, that policy also checks one exact passive two-pin component's
symbol, footprint, value, DNP state, passive pin types, and side-pin net
assignments. The check does not prove that the component conducts, PCB copper
continuity, external bonding, connector wiring, or electrical suitability. It
defaults to `review`; projects can configure the standard `off`/`block`
override or ignore an exact fingerprint.

The source-bound report includes `serial_peer_reference_coverage` for this
rule. Its `NO_DIRECT_PEERS`, `INCOMPLETE`, and `EVALUATED` status distinguishes
no discovered direct links from links whose explicit reference-pin evidence is
incomplete and links the heuristic could compare. Counts separate native
function matches from exact numbered UART/USART label matches, then show
supported common-reference and separate-reference links, exact-map-covered
separate links, and emitted review groups. The report binds these counts to the
native netlist hash and records the authored map state and available source and
typed-map hashes. These counts describe only the rule's bounded discovery
predicate; `NO_DIRECT_PEERS` does not establish that a project has no serial
interface, and an evaluated common reference does not establish copper
continuity or external grounding. Design-lint report schema 2 adds this field;
schema 1 reports remain readable. The `link_entries` rows also identify each
peer pair, native net or numbered label channel, signal pins, and whether its
reference evidence is incomplete, common, separately mapped, or still needs
review. This makes an incomplete count traceable to specific endpoints without
expanding the bounded peer-discovery predicate.

## Require an authored UART peer map

When two on-board logic-level UART endpoints are intended to communicate,
record each endpoint's TX/RX perspective, reference pins, identity, and logic
domain in the project-owned `tests/electrical.json` contract:

For direct links, add `logic_limits` to both endpoints. Replace every example
number, source, and condition below with values from the reviewed endpoint
datasheet or interface specification.

```json
{
  "serial_peers": {
    "mode": "required",
    "basis": "Reviewed board UART connection and endpoint pinouts",
    "links": [
      {
        "id": "debug-console",
        "basis": "Board debug connector connects to the onboard controller",
        "endpoint": {
          "id": "debug-connector",
          "reference": "J1",
          "symbol": "Connector_Generic:Conn_01x03",
          "footprint": "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
          "logic_domain": "logic-3v3",
          "tx": {"pin": "J1.2", "net": "UART_TX"},
          "rx": {"pin": "J1.3", "net": "UART_RX"},
          "reference_pins": [{"pin": "J1.1", "net": "GND"}],
          "logic_limits": {
            "output": {
              "low_minimum_v": 0.0,
              "low_maximum_v": 0.2,
              "high_minimum_v": 3.0,
              "high_maximum_v": 3.3,
              "source": "Replace with reviewed endpoint source and table",
              "conditions": "Replace with supply, load, and temperature conditions"
            },
            "input": {
              "absolute_minimum_v": -0.3,
              "low_maximum_v": 0.8,
              "high_minimum_v": 2.0,
              "absolute_maximum_v": 3.6,
              "source": "Replace with reviewed endpoint source and table",
              "conditions": "Replace with supply, load, and temperature conditions"
            }
          }
        },
        "peer": {
          "mode": "direct",
          "endpoint": {
            "id": "controller-uart",
            "reference": "U1",
            "symbol": "Vendor:Controller",
            "footprint": "Package_QFP:LQFP-48",
            "logic_domain": "logic-3v3",
            "tx": {"pin": "U1.10", "net": "UART_RX"},
            "rx": {"pin": "U1.11", "net": "UART_TX"},
            "reference_pins": [{"pin": "U1.12", "net": "GND"}],
            "logic_limits": {
              "output": {
                "low_minimum_v": 0.0,
                "low_maximum_v": 0.2,
                "high_minimum_v": 3.0,
                "high_maximum_v": 3.3,
                "source": "Replace with reviewed endpoint source and table",
                "conditions": "Replace with supply, load, and temperature conditions"
              },
              "input": {
                "absolute_minimum_v": -0.3,
                "low_maximum_v": 0.8,
                "high_minimum_v": 2.0,
                "absolute_maximum_v": 3.6,
                "source": "Replace with reviewed endpoint source and table",
                "conditions": "Replace with supply, load, and temperature conditions"
              }
            }
          }
        },
        "reference_policy": "common_net"
      }
    ]
  }
}
```

Direct peers must have opposite TX/RX net membership in both directions and
the same authored logic-domain label. For direct peers, the electrical
contract also compares guaranteed TX-low/high ranges against the other
endpoint's RX thresholds and absolute input limits in both directions. Each
direction reports its minimum voltage margin and the authored source and test
conditions. Missing limits report `NOT_CONFIGURED`; that is a coverage gap,
not a finding that the endpoint is electrically incompatible.
`reference_policy` can require endpoint
reference pins on one common net, record a bond between distinct reference
nets, require pins on distinct unbonded nets, declare the relationship not
applicable, or mark an external peer's reference as unverified. For a
`bonded` policy, add the exact project-reviewed component and side-pin mapping:

```json
{
  "reference_policy": "bonded",
  "reference_bond": {
    "reference": "R3",
    "expected_symbol": "Device:R",
    "expected_footprint": "Resistor_SMD:R_0603_1608Metric",
    "expected_value": "0R",
    "side_a_pin": "R3.1",
    "side_b_pin": "R3.2",
    "side_a_net": "GND_CONNECTOR",
    "side_b_net": "GND_CONTROLLER"
  }
}
```

Replace the sample component and nets with the reviewed design. This checks
schematic assignments, not electrical conduction or PCB copper. For a
`level_shifted` peer, declare the different logic-domain
labels and each bridge's symbol, footprint, direction, and exact input/output
pin/net assignments. For a remote device not represented in the schematic,
use `{"mode":"external","reason":"..."}`; the report marks peer mapping
and remote voltage-domain checks `NOT_APPLICABLE` and still checks the local
endpoint pins.

The checker compares these declarations with the current source-bound native
netlist from the KiCad 10 profile. A missing or wrong endpoint return pin,
same-side TX/TX map, wrong bridge endpoint, unexpected component identity, or
DNP endpoint fails the declared contract. A mapped bond also fails when its
component or pin assignment is missing, DNP, identity-mismatched, non-passive,
or on the wrong net. Keep the section `pending` while the pinout is under
review; use `not_applicable` when no UART peer map is required.
Older contracts without `serial_peers` remain readable.

This contract verifies schematic pin/net membership only. Distinct nets do
not prove galvanic isolation; bridge endpoint membership does not prove
internal transfer, direction, power, or enable behavior. The checker does not
derive voltage limits from domain names, verify that cited limit sources or
conditions are correct, model transients or actual device behavior, verify PCB
copper paths, or infer external wiring. Level-shifted links and external peers
do not receive the direct voltage comparison. It covers logic-level UART
mapping only; RS-232 and RS-485 need separate rules and requirements.

## Check mapped digital-peer voltage limits

For a direct, push-pull digital connection outside the UART and I2C contracts,
projects can map one output pin to one input pin and provide their reviewed
limits. This is useful for SPI data, clock, and select lines and direct control
signals. The check does not discover peers or assign voltages from rail, net,
or part names. Do not duplicate UART links here; `serial_peers` already checks
both UART directions. Open-drain buses, analog links, level shifters, and
external peers remain outside this direct-link check.

```json
{
  "digital_peer_voltages": {
    "mode": "required",
    "basis": "Reviewed controller and peripheral interface requirements",
    "links": [
      {
        "id": "spi-mosi",
        "basis": "Controller MOSI connects directly to peripheral SDI",
        "driver": {
          "reference": "U1",
          "symbol": "Vendor:Controller",
          "footprint": "Package_QFP:LQFP-48",
          "pin": "U1.12",
          "net": "SPI_MOSI"
        },
        "receiver": {
          "reference": "U2",
          "symbol": "Vendor:Peripheral",
          "footprint": "Package_SO:SOIC-8",
          "pin": "U2.3",
          "net": "SPI_MOSI"
        },
        "output_limits": {
          "low_minimum_v": 0.0,
          "low_maximum_v": 0.2,
          "high_minimum_v": 3.0,
          "high_maximum_v": 3.3,
          "source": "Replace with reviewed output-limit document and table",
          "conditions": "Replace with supply, load, and temperature conditions"
        },
        "input_limits": {
          "absolute_minimum_v": -0.3,
          "low_maximum_v": 0.8,
          "high_minimum_v": 2.0,
          "absolute_maximum_v": 3.6,
          "source": "Replace with reviewed input-limit document and table",
          "conditions": "Replace with supply and temperature conditions"
        }
      }
    ]
  }
}
```

Each endpoint declaration binds reference, symbol, footprint, pin, and net to
the source-bound native netlist. If the map is stale, a pin is unconnected,
either part is DNP, or the expected net differs, the topology check fails and
the voltage comparison is reported as `NOT_APPLICABLE`. Missing output or
input limits report `NOT_CONFIGURED`. With a matching topology, the checker
compares the full guaranteed output-low and output-high ranges against the
receiver thresholds and absolute input limits. It reports the minimum margin
and project-supplied basis, conditions, and source labels. A negative margin
fails this authored comparison.

These checks do not validate the cited sources, load assumptions, voltage
domain, power sequence, output contention, transient overshoot, slew, timing,
firmware behavior, PCB copper, or off-board wiring. The project owns endpoint
selection, ratings, applicability, and any justified exception. Setup marks
the section pending so an owner can record the map or explicitly mark it not
applicable. Older sidecars without this optional section remain readable and
make no voltage-compatibility claim; an absent map is not evidence of
compatibility.

## Check mapped component voltage-rating margins

Use `component_voltage_ratings` when a project has a reviewed maximum voltage
stress envelope and a datasheet working-voltage rating for an exact fitted
part. This is an opt-in project requirement, not a generic rail-name heuristic.
Each entry names the component's symbol, footprint, `PART_ID`, two native pins,
their expected nets, rated working voltage, maximum expected voltage, rating
and stress sources, conditions, and an owner-selected maximum utilization
fraction. The native KiCad netlist must export the matching component property
and exact pin inventory before the numeric comparison can pass.

```json
{
  "component_voltage_ratings": {
    "mode": "required",
    "basis": "Reviewed capacitor selection and input-voltage envelope",
    "requirements": [
      {
        "id": "input-capacitor",
        "reference": "C1",
        "expected_symbol": "Device:C",
        "expected_footprint": "Capacitor_SMD:C_0603_1608Metric",
        "expected_part_id": "CAP-0603-16V",
        "pins": ["C1.1", "C1.2"],
        "nets": ["VINPUT", "GND"],
        "rated_working_voltage_v": 16.0,
        "maximum_expected_voltage_v": 12.0,
        "maximum_utilization_fraction": 0.8,
        "rating_source": "Replace with the exact part datasheet and table",
        "rating_conditions": "Replace with the rated operating conditions",
        "stress_basis": "Replace with the reviewed worst-case voltage envelope"
      }
    ]
  }
}
```

The check compares `maximum_expected_voltage_v / rated_working_voltage_v` with
the project-selected fraction; equality passes. A mismatched reference, DNP
state, symbol, footprint, `PART_ID`, pin inventory, or pin/net assignment fails
the corresponding identity or topology check and leaves utilization
`NOT_APPLICABLE`. Omit the section when no component-rating scope is being
claimed, or record `pending` or `not_applicable` explicitly when that decision
is part of the project review.

The checker does not calculate the expected stress from rail names, infer the
part's rating from its value, or validate the datasheet, operating conditions,
source envelope, transient/ripple stress, temperature derating, lifetime, or
component behavior. A passing ratio only confirms that the recorded inputs
satisfy the recorded limit. It is not a part-selection or release approval.

## Check mapped component power-rating margins

Use `component_power_ratings` when a project has an exact component's sourced
power rating, reviewed thermal derating conditions, and a reviewed maximum
dissipation envelope. This section does not calculate device losses or
temperature derating. Each entry binds the exact symbol, footprint, `PART_ID`,
two native pins and their nets, source-rated power, reviewed derated allowable
power, maximum expected dissipation, and project-selected utilization limit.

```json
{
  "component_power_ratings": {
    "mode": "required",
    "basis": "Reviewed resistor loss and thermal limits",
    "requirements": [
      {
        "id": "current-sense-resistor",
        "reference": "R1",
        "expected_symbol": "Device:R",
        "expected_footprint": "Resistor_SMD:R_0603_1608Metric",
        "expected_part_id": "RES-SENSE-0603",
        "pins": ["R1.1", "R1.2"],
        "nets": ["SENSE_P", "SENSE_N"],
        "rated_power_w": 0.125,
        "derated_allowable_power_w": 0.08,
        "maximum_expected_power_w": 0.04,
        "maximum_utilization_fraction": 0.8,
        "rating_source": "Exact part datasheet, power rating table",
        "rating_conditions": "Datasheet board and ambient conditions",
        "derating_basis": "Reviewed derating curve and project thermal conditions",
        "stress_basis": "Reviewed worst-case current, tolerance, and duty-cycle calculation"
      }
    ]
  }
}
```

The analyzer compares `maximum_expected_power_w / derated_allowable_power_w`
with the project-selected fraction; equality passes. It checks that the
derated allowable power does not exceed the source-rated power. A mismatched
reference, DNP state, symbol, footprint, `PART_ID`, pin inventory, or pin/net
assignment fails its identity or topology check and leaves utilization
`NOT_APPLICABLE`. The current schema covers exact two-pin components; arrays
and multi-pin packages need a separate per-element loss model.

The project owns the accuracy of rated and allowable power, temperature
conditions, derating basis, and worst-case dissipation calculation. The
analyzer does not derive power from rail names, net topology, current, duty
cycle, or component value; it does not validate the cited sources, thermal
layout, board temperature, transients, lifetime, or physical component
behavior. A passing ratio confirms only the authored numeric comparison.
Omit the section when no scope is claimed, or mark it pending/not applicable
when that decision is part of project review.

## Check mapped connector contact-current margins

Use `connector_contact_ratings` when a project has reviewed maximum current
for specific contacts and an exact connector contact rating under stated
conditions. Each entry binds the connector reference, symbol, footprint,
`PART_ID`, complete native pin inventory, and each rated pin's function and
net. The project records the source rating, conditions, reviewed derated
allowable current, maximum expected current on that individual contact, the
load and derating bases, and an accepted utilization fraction.

```json
{
  "connector_contact_ratings": {
    "mode": "required",
    "basis": "Reviewed input-connector contact allocations",
    "requirements": [
      {
        "id": "input-connector",
        "reference": "J1",
        "expected_symbol": "Connector_Generic:Conn_01x02",
        "expected_footprint": "Synthetic:Header_1x02",
        "expected_part_id": "SYNTHETIC-HEADER-2P-3A",
        "native_pin_numbers": ["1", "2"],
        "contacts": [
          {
            "id": "input-current",
            "pin_number": "1",
            "expected_function": "Pin_1",
            "expected_net": "CONTACT_CURRENT",
            "rated_current_a": 3.0,
            "derated_allowable_current_a": 2.0,
            "maximum_expected_current_a": 1.5,
            "maximum_utilization_fraction": 0.8,
            "rating_source": "Exact connector datasheet, contact table",
            "rating_conditions": "Datasheet ambient, wire gauge, and loaded-contact count",
            "derating_basis": "Reviewed derating for the assembly conditions",
            "load_basis": "Reviewed worst-case allocation to this contact"
          }
        ]
      }
    ]
  }
}
```

The checker compares each authored maximum current with that contact's
derated allowable current; equality at the project utilization limit passes.
It does not split a net's total load among multiple contacts. A mismatched
connector identity, population, full pin inventory, pin function, or net
assignment fails the matching check and leaves the current comparison
`NOT_APPLICABLE`.

This contract does not calculate contact rating, derating, current sharing,
wire or cable limits, PCB track/plane/via capacity, physical continuity, or
temperature rise. It cannot prove the assembly follows the cited datasheet
conditions. Project owners must source and review every numeric input; the
result only compares those recorded inputs against the recorded limit. Mark
the section pending or not applicable when that decision belongs in project
review.

## Check MOSFET terminal stress across required states

Use `mosfet_stress` when an owner has reviewed the operating states and voltage
envelopes for an exact three-pin MOSFET. Each requirement binds the fitted
symbol, footprint, `PART_ID`, drain/gate/source pin numbers, native pin
functions, and expected nets. Each required state supplies a minimum and
maximum potential for all three terminal nets. The owner also records the
MOSFET's sourced maximum VDS/VGS ratings and an accepted utilization fraction.
A contract can cover multiple MOSFETs; each device keeps its own exact pin and
net mapping while state intervals are keyed by their authored net names.

```json
{
  "mosfet_stress": {
    "mode": "required",
    "basis": "Reviewed switch operating states and MOSFET absolute ratings",
    "required_states": ["off", "on"],
    "states": [
      {
        "id": "off",
        "net_potentials": {
          "D_NET": {"minimum_v": 0.0, "maximum_v": 0.0},
          "G_NET": {"minimum_v": 0.0, "maximum_v": 0.0},
          "S_NET": {"minimum_v": 0.0, "maximum_v": 0.0}
        }
      },
      {
        "id": "on",
        "net_potentials": {
          "D_NET": {"minimum_v": 47.0, "maximum_v": 49.0},
          "G_NET": {"minimum_v": 9.0, "maximum_v": 11.0},
          "S_NET": {"minimum_v": -0.5, "maximum_v": 0.5}
        }
      }
    ],
    "requirements": [
      {
        "id": "main-switch",
        "reference": "Q1",
        "expected_symbol": "Device:Q_NMOS_GDS",
        "expected_footprint": "Package_TO_SOT_THT:TO-220-3_Vertical",
        "expected_part_id": "EXACT-MOSFET-MPN",
        "drain_pin": "Q1.1",
        "drain_function": "D",
        "drain_net": "D_NET",
        "gate_pin": "Q1.2",
        "gate_function": "G",
        "gate_net": "G_NET",
        "source_pin": "Q1.3",
        "source_function": "S",
        "source_net": "S_NET",
        "rated_maximum_vds_v": 60.0,
        "rated_maximum_vgs_v": 20.0,
        "maximum_utilization_fraction": 0.8,
        "rating_source": "Exact MOSFET datasheet, absolute maximum ratings table",
        "rating_conditions": "Datasheet conditions reviewed for this application",
        "stress_basis": "Reviewed steady-state voltage bounds for off and on states"
      }
    ]
  }
}
```

For interval bounds D=[Dmin,Dmax] and S=[Smin,Smax], the analyzer uses
`max(abs(Dmin-Smax), abs(Dmax-Smin))`; it applies the same calculation to G-S.
This is a conservative bound when terminal intervals are independent. Every
required state must be declared and provide all three terminal-net intervals;
missing state or potential coverage fails that authored requirement. VDS and
VGS are calculated independently when their own terminal-pair intervals are
present, so a missing drain interval can leave a valid G-S comparison
available. Stress is not calculated if native identity, DNP population, exact
three-pin inventory, pin functions, or pin/net assignments do not match.

The project owns state selection, all interval endpoints, exact part identity,
datasheet source and conditions, and its utilization limit. The analyzer does
not infer voltages from net names or values, predict switching waveforms, or
check gate timing, safe operating area, avalanche, thermal limits, PCB copper,
or device suitability. The current schema supports one native pin each for
drain, gate, and source; multi-pin power packages and Kelvin terminals need an
explicit extension. When the section is declared required, its missing
coverage and over-limit checks participate in the electrical gate. This is
source-bound requirement evidence, not electrical or manufacturing approval.

## Require an authored RS-485 topology

When the reviewed bus design identifies the duplex arrangement and local
electrical strategy, record each differential pair, endpoint pin map,
termination, and bias decision in the project's `tests/electrical.json`
contract. This two-wire example uses a fitted local termination and local
bias, while recording the remote endpoint as external:

```json
{
  "rs485": {
    "mode": "required",
    "basis": "Reviewed transceiver data sheet, cable, and system topology",
    "buses": [
      {
        "id": "fieldbus",
        "basis": "Reviewed two-wire half-duplex interface",
        "topology": "two_wire_half_duplex",
        "pairs": [
          {
            "id": "shared",
            "basis": "Transceiver and connector signal pinout",
            "purpose": "bidirectional",
            "line_1_net": "RS485_A",
            "line_2_net": "RS485_B",
            "terminations": [
              {
                "id": "local-end",
                "basis": "Board is a reviewed bus endpoint",
                "topology": "direct",
                "resistors": [
                  {
                    "reference": "R10",
                    "symbol": "Device:R",
                    "footprint": "Resistor_SMD:R_0603_1608Metric",
                    "first_net": "RS485_A",
                    "second_net": "RS485_B",
                    "minimum_ohms": 117,
                    "maximum_ohms": 123
                  }
                ]
              },
              {
                "id": "remote-end",
                "basis": "Remote endpoint is a separately reviewed assembly",
                "topology": "external"
              }
            ],
            "bias": {
              "mode": "local",
              "basis": "Reviewed board-level idle-bus bias requirement",
              "pull_up": {
                "reference": "R11",
                "symbol": "Device:R",
                "footprint": "Resistor_SMD:R_0603_1608Metric",
                "bus_net": "RS485_A",
                "rail_net": "+5V_BIAS",
                "minimum_ohms": 600,
                "maximum_ohms": 750
              },
              "pull_down": {
                "reference": "R12",
                "symbol": "Device:R",
                "footprint": "Resistor_SMD:R_0603_1608Metric",
                "bus_net": "RS485_B",
                "rail_net": "GND_BUS",
                "minimum_ohms": 600,
                "maximum_ohms": 750
              }
            }
          }
        ],
        "endpoints": [
          {
            "id": "transceiver",
            "kind": "transceiver",
            "reference": "U1",
            "symbol": "Vendor:Rs485Transceiver",
            "footprint": "Package_SO:SOIC-8",
            "pins": [
              {"role": "bus_line_1", "pair_id": "shared", "pin": "U1.6", "net": "RS485_A"},
              {"role": "bus_line_2", "pair_id": "shared", "pin": "U1.7", "net": "RS485_B"},
              {"role": "driver_input", "pin": "U1.4", "net": "UART_TX"},
              {"role": "receiver_output", "pin": "U1.1", "net": "UART_RX"},
              {"role": "driver_enable", "pin": "U1.3", "net": "RS485_DE"},
              {"role": "receiver_enable", "pin": "U1.2", "net": "RS485_RE_N"},
              {"role": "reference", "pin": "U1.5", "net": "GND_BUS"}
            ]
          },
          {
            "id": "bus-connector",
            "kind": "connector",
            "reference": "J1",
            "symbol": "Connector_Generic:Conn_01x03",
            "footprint": "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
            "pins": [
              {"role": "bus_line_1", "pair_id": "shared", "pin": "J1.1", "net": "RS485_A"},
              {"role": "bus_line_2", "pair_id": "shared", "pin": "J1.2", "net": "RS485_B"},
              {"role": "reference", "pin": "J1.3", "net": "GND_BUS"}
            ]
          }
        ],
        "external_peers": ["Remote transceiver pin map is maintained with the remote assembly"]
      }
    ]
  }
}
```

The numbers and pin names above are synthetic examples, not recommended values
or universal RS-485 rules. Replace them with the reviewed vendor pinout and
project topology. For four-wire full-duplex buses, declare separate
`board_to_peer` and `peer_to_board` pairs. A split termination uses two
resistor paths, each from one line to the same authored midpoint net. External
termination may list `expected_dnp_resistors` to check that optional local
parts remain DNP. The bias mode can instead be `remote`, `internal_failsafe`,
or `not_required`, each with its reason or authored basis. Internal fail-safe
behavior remains a project declaration: netlist evidence verifies the local
transceiver identity and mapped pins, not its data-sheet feature.

The electrical analysis compares exact endpoint symbol/footprint identity,
mapped pin/net assignments, fitted state, and the inclusive nominal resistor
ranges with the current source-bound native netlist from the version-pinned
KiCad 10 export path. Retained evidence replays the same checks. The result can
catch a changed or DNP declared return pin, pair line, termination resistor,
or local bias path. External peers, remote termination/bias, and internal
fail-safe claims remain unverified or `NOT_APPLICABLE` in the local netlist.
Keep the section `pending` while the topology is under review; use
`not_applicable` when no RS-485 interface requires this map. Older contracts
without `rs485` make no RS-485 topology claim.

This is a schematic pin/netlist check. It does not prove that termination is
at a physical bus end, cable impedance, transceiver feature claims, resistor
tolerance or power rating, common-mode range, timing, polarity conventions,
PCB copper continuity, split-midpoint capacitor behavior, galvanic isolation,
or off-board wiring. It does not choose universal termination or bias values.
For topology and device-specific decisions, follow the selected transceiver
data sheet and the project's cable/system design; see
[ADI AN-960](https://www.analog.com/en/resources/app-notes/an-960.html) and the
[TI RS-485 Design Guide](https://www.ti.com/lit/an/slla272d/slla272d.pdf) for
examples of the design considerations.

## Record power source and load pin membership

The `power` section budgets the reviewed load currents and simulation cases.
Add `power_connectivity` when the project also needs a pin-level regression
for which declared sources and loads belong to each schematic rail:

```json
{
  "power_connectivity": {
    "mode": "required",
    "basis": "Reviewed supply tree and populated board options",
    "rails": [
      {
        "id": "supply",
        "basis": "Unregulated board input rail",
        "net": "VIN_IN",
        "source_groups": [
          {
            "id": "approved-inputs",
            "basis": "Either reviewed connector can provide the external supply",
            "selection": "any",
            "endpoints": [
              {
                "id": "barrel-input",
                "reference": "J1",
                "symbol": "Connector:BarrelJack",
                "footprint": "Connector_BarrelJack:BarrelJack_Horizontal",
                "pins": ["J1.1"]
              },
              {
                "id": "terminal-input",
                "reference": "J2",
                "symbol": "Connector_Generic:Conn_01x02",
                "footprint": "Connector_Generic:TerminalBlock_1x02_P5.08mm",
                "pins": ["J2.1"]
              }
            ]
          }
        ],
        "loads": [
          {
            "id": "load",
            "basis": "Budgeted input-stage load endpoints",
            "endpoints": [
              {
                "id": "regulator-input",
                "reference": "U1",
                "symbol": "Vendor:Regulator",
                "footprint": "Package_SO:SOIC-8",
                "pins": ["U1.1"]
              },
              {
                "id": "voltage-monitor",
                "reference": "U2",
                "symbol": "Vendor:VoltageMonitor",
                "footprint": "Package_SOT:SOT-23-5",
                "pins": ["U2.1"]
              }
            ]
          }
        ]
      }
    ]
  }
}
```

The source groups state required component endpoints and population choices.
With `selection: "all"`, every listed source endpoint must be fitted and
assigned to the named net. With `selection: "any"`, at least one listed
alternative must match; this is useful for reviewed mutually exclusive input
connectors. Every listed load group and endpoint is required. If the same
contract has a configured `power` budget, rail IDs and the complete set of
budget load IDs must match the connectivity map so a load cannot silently drop
out of the pin map. The example is synthetic and makes no voltage or current
recommendation.

The check compares exact symbol/footprint identity, DNP state, and declared pin
membership in the current source-bound KiCad 10 netlist. It names expected
sources and loads from the reviewed contract; it does not infer their role
from a symbol or a net name. It cannot prove that an external source or load
exists, verify electrical pin types or physical current direction, identify
omitted devices that were never declared, verify the voltage/current rating,
sequencing, protection, regulator behavior, or copper path, or decide whether
ERC findings are acceptable. Continue to run ERC and review the complete supply
tree. Keep the section `pending` until the source/load map is reviewed; use
`not_applicable` when this map is not relevant. Older contracts without
`power_connectivity` make no pin-level source/load membership claim.

## Require a mapped series power path

Use `design_lint.power_path_map` when a reviewed supply-tree requirement crosses
one or more fitted two-terminal parts, such as a fuse or ferrite bead. A direct
same-net source/load requirement belongs in `power_connectivity`; this map is
for a named chain of components between distinct nets. It records the intended
relationship without asking a naming heuristic to guess which parts conduct
power:

```json
{
  "design_lint": {
    "power_path_map": {
      "basis": "Synthetic reviewed input-power tree",
      "paths": [
        {
          "id": "input-to-controller",
          "basis": "Synthetic schematic requirement for a fitted input bead",
          "start": {
            "reference": "J1",
            "pin": "J1.1",
            "symbol": "Synthetic:PowerInput",
            "footprint": "Synthetic:Conn2",
            "net": "VIN"
          },
          "end": {
            "reference": "U1",
            "pin": "U1.3",
            "symbol": "Synthetic:Controller",
            "footprint": "Synthetic:QFN",
            "net": "VIN_FILTERED"
          },
          "elements": [
            {
              "reference": "FB1",
              "symbol": "Device:FerriteBead",
              "footprint": "Synthetic:0603",
              "side_a_pin": "FB1.1",
              "side_b_pin": "FB1.2",
              "side_a_net": "VIN",
              "side_b_net": "VIN_FILTERED"
            }
          ]
        }
      ]
    }
  }
}
```

The map checks exact symbol and footprint identity, native pin inventory,
fitted state, and every declared pin's net. Ordered elements must form a
continuous chain with distinct nets. It does not check component value or
rating, infer whether the requirement applies, prove conduction or electrical
suitability, discover additional paths, or validate PCB copper. A schematic
pass is not proof of a physical supply path. Findings default to `review`; set
`power.mapped_series_path_mismatch` to `block` or `off` only with a project
reason, or record an exact fingerprint ignore for a reviewed exception.

## Require mapped power-sequence dependencies

Use `design_lint.power_sequence_map` when an approved requirement says one
regulator's power-good signal must control another rail's enable pin. This is
an opt-in source-to-schematic comparison; it does not infer a sequence from
pin labels or device families. Keep the source document and page in each
`basis` field so reviewers can trace the requirement.

```json
{
  "design_lint": {
    "power_sequence_map": {
      "basis": "Synthetic source page 4, startup dependency table",
      "stages": [
        {
          "id": "rail-a",
          "output": {
            "reference": "U1",
            "pin": "U1.2",
            "symbol": "Synthetic:Regulator",
            "footprint": "Synthetic:SOT23-5",
            "part_id": "SYNTH-REG-A",
            "net": "RAIL_A"
          },
          "power_good": {
            "reference": "U1",
            "pin": "U1.3",
            "symbol": "Synthetic:Regulator",
            "footprint": "Synthetic:SOT23-5",
            "part_id": "SYNTH-REG-A",
            "net": "GOOD_A"
          },
          "enable": null,
          "enable_control": "always_on",
          "basis": "Synthetic source says this upstream stage is always on"
        },
        {
          "id": "rail-b",
          "output": {
            "reference": "U2",
            "pin": "U2.2",
            "symbol": "Synthetic:Regulator",
            "footprint": "Synthetic:SOT23-5",
            "part_id": "SYNTH-REG-B",
            "net": "RAIL_B"
          },
          "power_good": null,
          "enable": {
            "reference": "U2",
            "pin": "U2.1",
            "symbol": "Synthetic:Regulator",
            "footprint": "Synthetic:SOT23-5",
            "part_id": "SYNTH-REG-B",
            "net": "GOOD_A"
          },
          "enable_control": "firmware",
          "basis": "Synthetic downstream regulator enable"
        }
      ],
      "dependencies": [
        {
          "id": "rail-a-before-rail-b",
          "predecessor_stage": "rail-a",
          "successor_stage": "rail-b",
          "signal_net": "GOOD_A",
          "basis": "Synthetic source requires rail A power-good to enable rail B"
        }
      ]
    }
  }
}
```

For a `firmware`-controlled enable, this check can confirm only the schematic
net assignment; it does not inspect firmware behavior. `external` and
`unmodeled` control may be stated without a local enable endpoint, but then
that control path is outside the comparison. If an always-on stage has a
visible enable pin, mapping it checks only its declared schematic net. Cycles
in the declared dependency graph are reported. The linter also finds cycles
where exact mapped stage output nets drive mapped enable pins in a closed
topology, even if those output-to-enable edges are absent from the dependency
list. It skips this inference when a participating stage's mapped endpoints do
not match the native netlist. This remains a review question about topology;
enable polarity, other control paths, and startup behavior are not known.
An absent or incomplete map is not itself a finding, so the requirement still needs owner
review. Findings default to `review`; policy can set them to `block` or `off`,
or record an exact fingerprint ignore for a reviewed exception. No timing
claim is made, and this feature does not establish silicon startup, rail
thresholds, loaded ramp behavior, brownout recovery, firmware state, external
wiring, or PCB copper continuity.

Synthetic fault/control cases cover an open endpoint, an open or DNP element, a
wrong component identity, a mapped-net mismatch, and a two-stage bead/fuse
chain. The CLI and MCP adapters compare the same synthetic retained netlist
evidence. A tooling-owned ferrite-path control and wrong-source-net fault are
exported twice with the digest-pinned KiCad 10.0.0 and 10.0.5 profiles. The
fault keeps `U2.1` assigned to `VLOAD` but assigns `FB1.1` to `GND`; the
project-authored map reports that its expected source-to-load chain differs.
The synthetic `PWR_FLAG` marks the load rail as powered across the ferrite and
is not a physical component. Both fixtures produce zero native ERC errors on
both versions, while only the mapped-path fault receives the lint finding.
Warnings for synthetic library configuration and a one-pin local label remain
on the fixtures. This demonstrates incremental detection over ERC for the
declared map on this synthetic case; it does not establish a field
false-positive rate or prove physical current flow. Separate open-pin unit
cases can also trigger existing generic unconnected-pin checks and are not
counted as this incremental result. See the
[fixture and native regression record](../tests/fixtures/design_lint/power-path-native/README.md).

## Require reviewed reset, enable, and boot-strap connections

Add `control_inputs` when a device data sheet or interface requirement names
control pins whose net, bias, or approved drivers must remain stable. The
contract uses exact component references, symbol and footprint identities,
pin numbers, schematic nets, and KiCad library electrical pin types:

```json
{
  "control_inputs": {
    "mode": "required",
    "basis": "Reviewed controller and supervisor reset requirements",
    "signals": [
      {
        "id": "main-reset",
        "basis": "Controller reset and two approved supervisor sources",
        "signal_net": "RESET_N",
        "driver_policy": "shared_open_drain",
        "driver_basis": "The device documents wired open-drain reset contributors",
        "endpoints": [
          {
            "role": "controlled_input",
            "reference": "U1",
            "symbol": "Vendor:Controller",
            "footprint": "Package_QFN:QFN-16",
            "pin": "U1.1",
            "electrical_type": "input"
          },
          {
            "role": "approved_driver",
            "reference": "U2",
            "symbol": "Vendor:Supervisor",
            "footprint": "Package_SO:SOIC-8",
            "pin": "U2.1",
            "electrical_type": "open_collector"
          },
          {
            "role": "approved_driver",
            "reference": "U3",
            "symbol": "Vendor:Supervisor",
            "footprint": "Package_SO:SOIC-8",
            "pin": "U3.1",
            "electrical_type": "open_collector"
          },
          {
            "role": "external_interface",
            "reference": "J1",
            "symbol": "Connector:DB9",
            "footprint": "Connector:Dsub-9_Male",
            "pin": "J1.9",
            "electrical_type": "passive"
          }
        ],
        "bias": {
          "mode": "local",
          "basis": "Reviewed controller reset pull-up requirement",
          "resistors": [
            {
              "reference": "R1",
              "symbol": "Device:R",
              "footprint": "Resistor_SMD:R_0603_1608Metric",
              "signal_net": "RESET_N",
              "bias_net": "+3V3",
              "direction": "pull_up",
              "minimum_ohms": 9000,
              "maximum_ohms": 11000
            }
          ]
        }
      }
    ]
  }
}
```

The example is synthetic. Replace all endpoints, pin types, nets, resistor
ranges, and driver decisions with the reviewed device and system requirements.
`driver_policy` is one of `none`, `single`, `shared_open_drain`, or
`reviewed_multiple`. Shared and multiple-driver policies need an authored
review basis. The checker confirms the approved pins remain on the declared
net and that their exported pin types still match. It also reports any
output-capable pin type on that net that is absent from the endpoint list.

For `bias.mode: "local"`, each named conventional fitted two-terminal resistor
must retain its exact symbol, footprint, signal/bias net pair, DNP state, and
inclusive nominal resistance range. For `internal`, `external`, or
`not_required`, the contract records the reviewed decision and the bias check
reports `NOT_APPLICABLE`; the native schematic cannot prove those behaviors.
New electrical setup contracts leave `control_inputs` pending until each
control signal is reviewed or explicitly marked not applicable.

The comparison runs against the source-bound native KiCad 10 netlist and is
replayed from retained evidence. KiCad pin electrical types are symbol-library
metadata: they do not identify firmware runtime direction, prove that two
drivers contend, or reveal external device behavior. The check does not infer
requirements from pin names, choose reset polarity or resistor values, verify
resistor tolerance or rating, prove copper continuity or test access, or
validate internal/remote bias. Continue to review ERC, the device data sheet,
the PCB return path, and required first-article tests. Older contracts without
`control_inputs` make no control-signal claim.

## Require reviewed schematic test and service access

Use `test_access` to name rails, programming lines, and factory measurement
nets that need a board-level access point. Each required net names the exact
component pin, symbol, footprint, and exported electrical pin type. `selection`
may be `all` when every listed point is required or `any` for reviewed
alternatives. A net may instead be marked `not_required` with a review basis and
reason, such as a hazardous high-voltage node excluded from routine probing:

```json
{
  "test_access": {
    "mode": "required",
    "basis": "Reviewed service procedure and electrical safety assessment",
    "pcb_accessibility": {
      "mode": "required",
      "basis": "Reviewed factory probe approach and PCB access requirement"
    },
    "decisions": [
      {
        "mode": "required",
        "id": "logic-rail",
        "basis": "Factory procedure measures the logic rail at this point",
        "net": "+3V3",
        "selection": "all",
        "endpoints": [
          {
            "kind": "test_point",
            "reference": "TP1",
            "symbol": "TestPoint:TestPoint",
            "footprint": "TestPoint:TestPoint_Pad_D1.0mm",
            "pin": "TP1.1",
            "electrical_type": "passive",
            "approach_side": "front",
            "probe_envelope": {
              "tip_diameter_mm": 0.8,
              "clearance_mm": 0.2
            }
          }
        ]
      },
      {
        "mode": "not_required",
        "id": "high-voltage-output",
        "basis": "Reviewed hazardous-energy assessment",
        "net": "HV_OUT",
        "reason": "Routine manufacturing and service procedures do not probe this node."
      }
    ]
  }
}
```

The example is synthetic. Substitute only project-reviewed nets, component
identities, pin types, and access decisions. The source-bound KiCad 10
schematic check fails if a required endpoint is absent, DNP, assigned to a
different net, or no longer has the declared symbol, footprint, pin inventory,
or electrical type. Missing `test_access` configuration is reported as
`NOT_CONFIGURED`; use `not_applicable` only when the project has no required
schematic test/service access and record the reason.

The PCB stage is separate. With `pcb_accessibility.mode: "required"`, the
source-bound KiCad 10 board check requires the exact footprint and pad to be
placed on the expected net and the pad layers to declare outer copper and the
corresponding solder-mask layer. Each endpoint can set `approach_side` to
`front`, `back`, or `either`; the default is `either`. A selected side must
have both copper and mask declarations on that same side. On schematic-only
projects or boards without a required physical access point, record a reasoned
`not_applicable` decision for this stage. A pending board-stage decision cannot
pass electrical policy.

An endpoint may add `probe_envelope` with a reviewed `tip_diameter_mm` and
`clearance_mm`. For circular, undrilled target pads, the pinned KiCad 10
geometry probe combines the circular pad size with KiCad's resolved solder-mask
expansion and requires the resulting aperture diameter to fit
`tip_diameter_mm + 2 * clearance_mm`. Other pad shapes and
drilled pads are reported as unproven and fail this configured fit check. The
probe also measures from the target pad center to the nearest fitted,
mask-layer-assigned pad on the same board side that belongs to a different net
or has no net. It compares this distance with
`tip_diameter_mm / 2 + clearance_mm`, rounded upward to the nearest nanometer.
The measured distance is rounded down to a nanometer so floating-point geometry
cannot make a marginal placement pass by rounding up.
For `approach_side: "either"`, at least one exposed side must meet the envelope;
a fixed side checks only that side. The native probe request and result are
retained and rechecked against the exact board, requirement, KiCad image, and
probe source.

The synthetic native acceptance fixture exercises a fitted different-net pad,
a closer same-net pad, a closer DNP pad, a no-net obstacle, front-only access,
an undersize circular aperture, an exact-fit aperture with a mask contraction,
a rectangular target, and a drilled target. It checks front/back/either-side
behavior, exact aperture and clearance boundaries, unsupported-shape reporting,
expected faults, and repeatability across two native loads. Package acceptance
runs it against the project's digest-pinned KiCad 10.0.0 and 10.0.5 images and
retains the request, snapshot, probe, and command receipt under ignored
`build/ci/` output.

This is a bounded pad-aperture and pad-neighbor check. It skips DNP footprints
and same-net neighbor pads; it does not inspect exposed tracks, vias,
copper-zone mask openings, non-circular or drilled target-pad fit, component
bodies, fixtures, covers, probe reach, or manufacturing test coverage. A
passing result describes only the configured geometry around the selected PCB
pad. Review the physical access path and first-article test separately.

[chip-pro-symbol]: https://gitlab.com/kicad/libraries/kicad-symbols/-/blob/25ef404b6a92de5a0cec203eb3270632136758e3/MCU_Module.kicad_sym
