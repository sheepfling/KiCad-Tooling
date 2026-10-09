# Design lint and heuristic backlog

This backlog tracks deterministic checks that can surface likely design
mistakes for review, and the stronger contracts needed to turn a reviewed
requirement into a regression gate. It is not a list of assumed wiring rules.
No rule may join nets, infer an electrical requirement from a name alone, or
declare a board safe to fabricate.

The project repository owns interface intent, electrical requirements,
applicability decisions, and exceptions. This tooling repository owns reusable
analyzers, typed reports, adapters, synthetic fixtures, and regression tests.
No proprietary board source or project fixture is needed to develop this
backlog.

See [current design lint rules](DESIGN_LINT.md) for implemented behavior and
configuration. Items below are proposed work unless explicitly marked
implemented.

## Working rules

### Finding strength

- **Heuristic:** A deterministic pattern is unusual or incomplete, but intent
  is unknown. Report `REVIEW` by default with exact source evidence and a
  question for the reviewer.
- **Contract:** A project-authored, reviewed requirement names the required
  pins, nets, domains, values, or geometry. Compare it with source-bound
  evidence; project policy can make a mismatch blocking.
- **Native check:** KiCad ERC/DRC or another named native tool reports a defined
  condition. Preserve tool/version/source evidence; the result is not
  electrical approval.

An empty or absent contract is a **coverage gap**, not proof of a defect and
not a lint pass. Reports should keep coverage gaps, heuristic findings,
contract mismatches, native diagnostics, and stale review decisions distinct.

### Entry requirements

Before implementation, every item needs:

1. A bounded evidence source and exact supported KiCad/tool versions.
2. A deterministic predicate, including which pin functions, properties,
   topology, or geometry it recognizes.
3. At least one synthetic fault fixture and one valid control fixture. Add
   boundary cases for DNP parts, explicit isolation, alternate valid
   topologies, and unsupported metadata where they apply.
4. A statement of what the result cannot establish and which project-authored
   requirement can turn the observation into a regression check.
5. A unique rule ID, stable fingerprint inputs, readable evidence, a
   documented default mode, and a reasoned project override/ignore path.
6. CLI/MCP parity through the shared typed service when a user-facing surface
   changes, plus the required parity test and `tool-surfaces.json` update.

Do not promote a heuristic to default `block` based only on a plausible
electrical convention. Promotion requires project-authored policy and a
contract comparison whose positive and negative controls demonstrate the
intended requirement.

## Existing baseline

The following 85 rules are implemented with synthetic regression coverage.
Their actual recognition limits are documented in
[DESIGN_LINT.md](DESIGN_LINT.md):

- `connector.repeated_pin_function`
- `connector.peer_pin_assignment_outlier`
- `connector.peer_pin_assignment_divergence`
- `component.repeated_supply_pin_function`
- `component.peer_power_pin_assignment_divergence`
- `component.peer_power_output_unconnected`
- `component.peer_signal_input_unconnected`
- `component.peer_signal_output_unconnected`
- `component.two_pin_passive_same_net`
- `component.two_pin_diode_same_net`
- `component.two_pin_crystal_same_net`
- `component.two_pin_fuse_same_net`
- `component.two_pin_ferrite_same_net`
- `component.two_pin_switch_same_net`
- `connector.no_connected_return`
- `connector.unconnected_supply_pin`
- `connector.unconnected_return_pin`
- `connector.unconnected_power_input`
- `component.unconnected_power_input`
- `component.unconnected_supply_pin`
- `component.unconnected_return_pin`
- `component.led_directly_across_supply_and_return`
- `component.led_directly_driven_from_output`
- `power.ic_rail_without_fitted_capacitor`
- `power.mapped_series_path_mismatch`
- `power.mapped_sequence_dependency_mismatch`
- `power.input_without_supported_source_path`
- `net.connector_capacitor_only_no_dc_anchor`
- `control.unconnected_control_input`
- `control.connected_control_input_without_visible_bias`
- `signal.open_collector_input_without_visible_bias`
- `signal.open_emitter_input_without_visible_bias`
- `bus.i2c_unconnected_pin`
- `bus.i2c_missing_pullup`
- `bus.i2c_low_equivalent_resistance`
- `bus.i2c_multiple_pullup_rail_families`
- `bus.i2c_address_mismatch`
- `bus.i2c_address_collision`
- `bus.i2c_unmapped_responder`
- `bus.spi_unmapped_participant`
- `bus.serial_unmapped_peer`
- `bus.spi_peer_voltage_review`
- `bus.serial_peer_voltage_review`
- `bus.serial_peer_reference_review`
- `bus.usb_peer_reference_review`
- `bus.spi_unconnected_chip_select`
- `bus.spi_active_low_chip_select_without_pullup`
- `bus.usb_c_unconnected_cc_pin`
- `bus.usb_c_unreviewed_port`
- `bus.usb_data_path_mismatch`
- `bus.can_unconnected_line`
- `bus.can_missing_termination`
- `bus.can_peer_assignment_divergence`
- `bus.complementary_pair_assignment`
- `signal.named_pair_without_reviewed_requirement`
- `net.numbered_returns`
- `net.numbered_power_rails`
- `schematic.wire_end_on_pin_line`
- `schematic.pin_tip_on_wire_interior`
- `schematic.wire_endpoint_near_pin_tip`
- `schematic.label_near_wire_endpoint`
- `schematic.unmarked_wire_crossing`
- `schematic.unmarked_t_junction`
- `schematic.coincident_text_anchors`
- `schematic.free_text_overlap`
- `schematic.free_text_over_wire`
- `schematic.free_text_over_symbol_body`
- `schematic.wire_through_symbol_body`
- `protection.unreviewed_interface_pin`
- `protection.mapped_device_mismatch`
- `oscillator.crystal_load_network_mismatch`
- `power.regulator_feedback_mismatch`
- `filter.rc_corner_mismatch`
- `pcb.decoupling_proximity`
- `pcb.protection_entry_path`
- `pcb.minimum_track_width`
- `pcb.reference_plane_coverage`
- `pcb.switching_loop_geometry`
- `pcb.differential_pair_rule_coverage`
- `pcb.signal_path_rule_coverage`
- `pcb.rf_module_antenna_keepout_coverage`
- `pcb.keepout_intent_coverage`
- `connector.return_distribution`
- `net.return_labels_without_pin_roles`
- `mcu.stm32_cubemx_pin_map`

This baseline catches suspicious connector symmetry and missing named pins,
plus narrow netlist patterns for I2C, SPI, USB-C, and CAN. It does not know that
several similarly named connector returns must be common unless a project
states that requirement. It also cannot establish PCB copper connectivity,
placement, off-board circuitry, or physical continuity from a schematic
netlist.

## Prioritized backlog

Priority is about the next useful, evidence-backed increment. `P0` is a
foundation for trustworthy expansion; protocol-specific schematic checks are
`P1`; geometry-dependent checks and review aids are `P2`; curated knowledge
and optional ecosystem adapters are `P3`.

### Current execution focus

- **LINT-086 — Measure review value for the USB split-reference prompt.**
  The default-REVIEW rule has synthetic direct, series-resistor, USB-C,
  duplicated-contact, shunt, and multiport fault/control coverage. Its exact
  native fixture lane passed in tagged `v0.5.0rc15` (GitHub run `37851810081`)
  on digest-pinned KiCad 10.0.0 and 10.0.5. All 11 topology cases passed on
  each version; repeated normalized netlist contracts matched for every case.
  The 2026-10-09 public remeasurement used the digest-pinned KiCad 10.0.5 image
  `ghcr.io/kicad/kicad@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`.
  CP2102 (`eecf7bb`), FUSB302/RP2040 (`7d95292`), and 16nx (`ca7de22`) each
  had one supported common-reference path and zero baseline prompts. Each
  source was exported twice; normalized typed-netlist hashes matched both the
  repeated export and the earlier 10.0.6 screen. Moving every matched
  connector reference pin to a synthetic net in the typed contract produced
  exactly one stable review per sample. This records applicability,
  cross-version reproducibility, and seeded-fault sensitivity; it does not
  establish field precision or reviewer value. Independent author dispositions
  and review times remain absent. The metadata-only receipt is retained under
  the ignored `build/ci/lint-086-public-review-measurement-20261009/` directory;
  the public source checkouts and exported netlists remain outside this repo.
  The next work is a source-bound review with independent disposition and
  observed time on approved, nonconfidential examples. Count a quiet result
  as a supported non-finding only for common-reference paths in
  `common_reference_path_count`; `NO_SUPPORTED_PEER_PATHS` contributes no
  non-finding, and `INCOMPLETE` remains a partial screen. Keep unresolved labels
  visible and keep project defaults and the review-only prompt unchanged while
  evidence is gathered.

- **LINT-094 — Open native power outputs on exact-symbol peers.** This gate
  passed tagged GitHub package acceptance in `v0.5.0rc12` (run 37796753272),
  including repeatable synthetic exports on digest-pinned KiCad 10.0.0 and
  10.0.5, the CLI/MCP parity test, and the installed-wheel external-template
  check. Its review prompt covers an open `power_out` pin when a matching
  fitted peer has one assigned net, without claiming that peers should share
  nets. No project source or candidate code was imported.

1. **Fail closed on empty native netlists.** LINT-078 now blocks source-bound
   lint when KiCad returns a successful export with zero component records. The
   trigger was a pinned KiCad 10.0.5 probe of a public legacy schematic that
   returned an empty netlist with exit code 0; the source was not copied into
   Tooling. A tooling-owned synthetic blank schematic now reproduces a
   successful empty export on both pinned KiCad 10.0.0 and 10.0.5; its paired
   nonempty control remains parseable, and the normalized typed inventories
   match across versions. Keep this evidence-integrity guard ahead of adding
   more heuristics.
2. **Keep P0 connector and contact-rating cases in acceptance.** LINT-002 and
   LINT-047 cover split-return, missing peer-power-contact, and peer-pin fault
   controls with synthetic source-bound native exports. The
   `NativeConnectorReturnFixtureTests` lane passed both pinned KiCad versions
   on 2026-10-03 and was rerun locally on 2026-10-08 against the current
   checkout: 2 tests and 4 subtests passed. It includes an explicit
   no-connect-marker peer fault;
   J2.1 remains a REVIEW candidate on both versions, while the common-net
   control passes. LINT-079 extends that lane with a current interface role map
   over numeric-only connector pin functions; the pinned KiCad 10.0.0/10.0.5
   run passed locally on 2026-10-04, including cross-version normalized
   netlist equality for mapped return and supply fault/control cases. The
   split-return fault stays `REVIEW`; the
   common-return control passes, and the mapped-role hint does not assert
   required connectivity. The lane includes a two-connector open generic
   power-pin fault and shared-net control, plus a numeric-function/neutral-net
   variant that keeps the exact
   repeated-contact prompt while dropping the numbered-net hint; the common
   control clears that mismatch prompt and retains four open pin-role coverage
   prompts. The LINT-079 report follow-up now identifies per-pin role sources;
   a synthetic three-connector regression now checks two matching supply
   contacts against one outlier across three different generic/numeric symbol
   identities. It reports only when the outlier shares the authored voltage
   domain; all-common and separately authored-domain controls pass. This
   extends typed-netlist coverage and is not a new native-export result. The
   existing source-bound CLI/MCP parity test also now covers three mapped
   custom connector peers with two matching and one split return and supply.
   It now confirms that the role-aware finding suppresses an overlapping
   generic peer-pin warning when it covers the same contacts. The focused
   CLI/MCP parity case passed on 2026-10-07 with synthetic netlist XML and the
   clean public template checkout at commit
   `ed89536f0dbbcb013145af2994fef41b2250143e` as its external project root;
   this verifies adapter parity, not a native KiCad export.
   A typed-netlist partial-map control also confirms that a mapped role finding
   does not suppress the generic peer warning when a third peer remains
   undeclared; the full peer assignments stay available for review.
   Connector coverage now also promotes same-symbol siblings of a reviewed
   custom connector into inventory candidates. A CLI/MCP partial-map case
   confirms the unreviewed sibling remains `UNDECLARED`; this expands coverage,
   not inferred pin roles or required connectivity.
   LINT-077 also passed its source-bound contract,
   CLI/MCP parity, retained-evidence replay, synthetic fixtures, and pinned
   KiCad 10.0.0/10.0.5 native exports. Keep these cases in GitHub CI. Before a
   project adopts a contact-rating requirement, its electrical owner must
   review exact ratings, derating conditions, and per-contact load from
   approved sources.
   Saved local `NativeComponentRatingFixtureTests` receipts cover the
   digest-pinned KiCad 10.0.0 and 10.0.5 images. They record repeatable native
   exports and synthetic fault/control outcomes for component-voltage,
   component-power, connector-contact-current, and MOSFET-stress contracts.
   The connector-contact case passes at 1.60 A / 2.00 A = 0.8 and fails at
   1.61 A / 2.00 A = 0.805; both versions share normalized netlist SHA-256
   `a61bc6c086e4abb5a3af84ddceae10f845a314c2f742cc450b1ed19c7f2419f1` and
   normalized ERC SHA-256
   `dbcb2273e067531c5e027ac9482ccf7ede0b4e2f7bd3ac01ad83b25510664338`, with
   zero native ERC errors. The retained local event receipts are dated
   2026-10-03; no hosted GitHub result for this dirty branch is recorded.
   LINT-074 now also covers direct UART links that terminate at source-identified
   connector candidates. The new MCU-to-header split-reference fault and
   common-reference control passed repeated native exports on pinned KiCad
   10.0.0/10.0.5; an exact authored `separate_nets` map suppresses the prompt.
   Keep it REVIEW-only because different references may be intentional.
   LINT-080 now compares complete DB9 return, two-pin diode, and generic
   peer-pin fault/control reports across independent Python hash secrets. This
   supplements in-process input-reordering tests; it does not replace the
   pinned native fixture lane.
   The process probe now serializes four synthetic DB9 grounding and
   pin-connectivity contract outcomes. Split returns fail the common-domain
   requirement and pass the isolated-domain requirement; the common-return
   control produces the inverse for both contract services. Each result binds
   the typed-netlist digest and the relevant requirement digest. The focused
   determinism/catalog run passed on 2026-10-07: 462 tests and 636 subtests in
   an isolated Python 3.11 environment. Three independently randomized
   processes returned identical serialized reports and check results. This is
   typed-service determinism evidence, not another native export.
   LINT-080 also applies the same three-process check to the multi-device
   MOSFET stress contract. A synthetic change to Q2's on-state
   drain interval changes only Q2's VDS status; Q1 remains passing, and the
   common two-device control passes. The focused lint and MOSFET contract suite
   passed on 2026-10-07 with 615 tests and 732 subtests. The same typed netlist
   digest is retained while the authored requirement digest changes. This
   checks deterministic contract reporting and does not extend the native
   fixture or validate a real component.
   The LINT-063 hash-seed matrix compares direct output-to-LED and parallel-
   resistor faults against a return-side series-resistor control. Both faults
   retain `component.led_directly_driven_from_output` as `REVIEW`; the series
   control clears that rule. Its complete report remains `REVIEW` because the
   synthetic `LED_RETURN` and `GND` nets retain the independent
   `net.return_labels_without_pin_roles` finding. The focused determinism,
   LED-rule, and catalog suite passed on 2026-10-07: 469 tests and 653
   subtests. This is deterministic topology-review evidence, not a resistor
   adequacy or physical-behavior result.
   The four-port DB9 native lane now also evaluates the exported netlists
   against synthetic common-return and per-connector isolation requirements.
   The split case must fail the common
   requirement and pass the isolation requirement; the common-net control must
   do the reverse. The new contract assertions are wired into the exact-version
   acceptance tests. A local native run on 2026-10-07 passed the focused
   acceptance test on KiCad 10.0.0 and 10.0.5 using their catalogued image
   digests and the public workflow-template commit
   `5ca79bedf665a9b6577d96b1d47f13ccd518c968`: 2 tests and 4 version subtests
   passed. All four common-return versus isolated-return contract outcomes
   matched, repeated exports were stable, and normalized netlists matched
   across versions. The corresponding hosted GitHub run remains pending.
   A separate CLI/MCP parity test now exercises the same common-versus-isolated
   DB9 grounding requirement with synthetic netlist XML. It checks the four
   fault/control combinations and requires both surfaces to return identical
   checks. This verifies shared-service behavior, not a native export or PCB
   copper continuity.
   The native acceptance harness now also compares `PinConnectivityAnalysis`
   against its DB9 exports and generic peer-power fixtures. The power cases
   require common +5V across J1.1/J2.1/J3.1, where the open J3.1 fault fails and
   the common control passes; a separate authored contract accepts split J1/J2
   outputs with J3.1 intentionally unconnected and rejects the common-net
   topology. The exact pinned native lane also passed locally on 2026-10-07
   using catalogued KiCad 10.0.0 and 10.0.5 images. All eight pin-connectivity
   relationship outcomes and the stale-symbol-pin fault matched their expected
   statuses; repeated exports were stable and six normalized fixture-netlist
   digests matched across versions. The stale contract names absent pin J1.99
   as unused and fails with `unknown symbol pins=['J1.99']`. Local receipts are
   under `/private/tmp/kct-native-connector-pin-contract-20261007` and
   `/private/tmp/kct-native-stale-pin-*`. This verifies native-export behavior
   for tooling-owned synthetic fixtures; the hosted GitHub run remains pending.
   A follow-up closes an evidence gap for `unconnected` requirements: if a
   referenced component exists but the native netlist has no symbol pin
   inventory for it, the relationship now fails with an explicit missing-
   inventory diagnostic instead of treating the absence as proof of
   intentional disconnection. The installed-service probe passes the valid
   unconnected control and rejects connected, stale-pin, and missing-inventory
   cases. The source-bound CLI/MCP parity regression passed on 2026-10-07
   against the clean public KiCad-Test checkout at commit
   `ed89536f0dbbcb013145af2994fef41b2250143e`. The full suite was rerun on
   2026-10-07 with `KICAD_TEMPLATE_ROOT` set to that clean public checkout:
   2,056 passed, 49 skipped, and 27 parts-assistant HTTP tests failed when the
   sandbox denied `127.0.0.1` socket binds; 2,312 subtests passed. No design-lint
   or electrical-parity test failed. This is a fail-closed service check, not
   evidence that a native exporter omitted pin inventory in the synthetic
   schematic lane. LINT-080 now also repeats the missing-versus-complete
   symbol-pin inventory case across three independently randomized Python
   processes. The missing-inventory requirement fails with the exact component
   named, and the complete inventory control passes; this guards report
   stability without replacing CLI/MCP parity or native-export evidence.
   LINT-080 also extends its three-process hash-seed comparison to a project-
   mapped return-role split and common-net control. The fault remains `REVIEW`
   with per-pin classification-source evidence; the common control remains
   `PASS`. The map catalog and typed-netlist digest are included in the report.
   This verifies report stability for that mapped branch, not native export;
   keep the existing LINT-079 exact-version lane as separate evidence.
   A further LINT-080 extension compares complete source-mapped series
   power-path reports across the same independent processes. The open-element
   fault remains `REVIEW` with one evaluated authored requirement and one
   finding; the repaired path remains `PASS`. This is synthetic typed-netlist
   evidence and does not claim a native export or component-conduction proof.
   LINT-080 now also compares the complete UART-label discovery report and an
   exact source-mapped endpoint control across those processes. The unmapped
   label candidate remains `REVIEW` with `discovery_basis=net_label`; the
   authored endpoint map suppresses that candidate. The report retains its
   separate `connector.no_connected_return` review because the generic header's
   return-pin role is not mapped. This confirms process-stable reporting for
   the heuristic without letting a serial map clear unrelated pin-role
   coverage. It does not prove that a UART peer is required or establish board
   copper connectivity.
   LINT-080 also compares source-mapped power-sequence dependency reports. The
   open-enable fault remains `REVIEW` with the sequence map evaluated against
   three authored stage/dependency requirements and one mismatch; the repaired
   control remains `PASS`. This is typed-netlist evidence and does not establish
   startup behavior on hardware.
   LINT-080 now also compares an exact source-mapped STM32 CubeMX pin-map
   mismatch with a valid control. Both reports retain complete map coverage;
   the map hash stays fixed while the IOC source hash changes with the fault.
   This is contract/report determinism evidence and does not verify compiled or
   flashed firmware behavior.
   Connector coverage output now sorts project interface IDs. Its mapped-return
   fault regression also reverses interface IDs, catalog records/pins, review
   rows, and pin-map keys; coverage and the full lint report remain equal for
   fixed source digests. This is typed-service ordering evidence; existing
   custom-connector CLI/MCP parity remains a separate adapter check.
   The LINT-074 multi-UART split-reference fault and common-reference control
   now also compare complete reports across three independent Python hash
   secrets. The fault localizes to J1/U1; the common control clears that rule
   while preserving unrelated review findings. This extends deterministic
   report coverage, not the rule's electrical applicability or precision.
   The LINT-066 SPI and UART voltage-domain prompts each remain `REVIEW` when
   unmapped and are suppressed only by complete exact maps. LINT-080 now
   confirms byte-identical complete reports across three independently
   randomized Python processes. This is determinism evidence; field precision
   and reviewer value remain unmeasured.
   LINT-080 now also covers LINT-067's split CAN-peer fault and common-pair
   control across those processes. The fault remains `REVIEW`, the control
   omits the divergence finding, and each report carries the digest of its own
   typed-netlist input. This extends determinism and input-binding evidence;
   reviewer value and field false-positive rate remain unmeasured.
   The header-only SPI/UART external-interface boundary is now also compared
   across those processes. Both rules retain `NO_SUPPORTED_ENDPOINTS`, zero
   recognized IC endpoints, and no peer-voltage findings; this confirms the
   report does not promote off-board connector buses to direct on-board IC
   peers. It adds process-determinism evidence, not a defect or field-precision
   measurement. The same boundary now has a source-bound CLI/MCP parity case:
   both surfaces return identical full reports from retained synthetic
   netlist XML, including the two `NO_SUPPORTED_ENDPOINTS` entries and no
   SPI/UART peer-voltage findings.
   The LINT-079 partial-map case now also runs through the three-process
   hash-seed probe: with J3 undeclared, its generic peer-pin outlier remains
   visible alongside the mapped-role finding; complete role coverage suppresses
   only the overlapping generic warning, and an all-common control clears both
   mismatch prompts. This checks report stability and coverage-sensitive
   suppression using synthetic typed netlists, not native exports or a
   connectivity requirement.
   A separate three-process case now compares two different connector symbols
   whose project maps classify generic supply contacts in the same voltage
   domain. An open J2 contact remains a REVIEW finding with its exact empty-net
   evidence; the role-aware group suppresses a duplicate open-pin warning, and
   the common-net control passes. This checks the initial missing-power-pin
   regression class while preserving the rule's REVIEW-only, no-commonality
   boundary; it does not establish that the two interfaces must share a rail.
   LINT-080 also compares the typed LINT-077 contact-rating checks at the exact
   authored 0.80 utilization limit (`PASS`) and at 0.805 (`FAIL`). Both use the
   same synthetic typed-netlist input; the source-bound requirement digest
   changes with the current allocation. This checks process stability of the
   rating calculation, not a complete electrical-analysis run or native export.
   The new reviewed peer-scope case compares three generic `Pin_1` contacts
   marked unlisted while pin 2 is mapped as return. Separate groups retain the
   split-return review and suppress signal comparison; a shared group reports
   both return and signal divergence; a common signal/return control passes.
   The focused determinism/catalog run passed with 465 tests and 641 subtests;
   the mocked native-lane orchestration passed separately and verifies the
   source-pinned fixture set. The exact-version exports remain configured in
   GitHub CI, with no hosted result recorded for this revision.
   LINT-080 now also compares a mapped USB data-path fault and two valid
   topologies across three randomized processes: a missing D+ series resistor
   remains one evaluated mismatch, the complete series-resistor path passes,
   and the documented direct integrated-PHY topology has no path mismatch.
   Its independent STM32 CubeMX and physical differential-pair REVIEW prompts
   remain visible. The focused determinism, USB data-path, and catalog suites
   passed with 472 tests and 644 subtests. This adds typed-report stability and
   suppression-boundary evidence; exact-version native export remains a
   separate acceptance result.
   LINT-084 now closes a narrow power-path gap found while reviewing the
   supported two-pin component families: fitted `Device:Fuse` and
   `Device:Polyfuse` symbols with both pins on one net produce an opt-in-capable
   REVIEW hint. Fault/control, policy, catalog, CLI/MCP parity, and three-process
   hash-seed tests passed locally. The exact KiCad 10.0.0/10.0.5 fixture cases
   are wired into the GitHub package job; the RC4 result must pass before
   counting the pinned native lane as verified. A supplementary local KiCad 10.0.6
   export of all four tooling-owned fuse fixtures now repeats and matches the
   expected fault/control findings; see LINT-084. Keep the predicate limited
   to the two named symbol families and do not infer that every fuse must be
   in series.
   The original DB9 return fault also passed a supplemental local KiCad 10.0.6
   native-export screen: both return heuristics reported the split fault, the
   common-net control passed, and numeric pin functions with neutral net names
   retained the peer-pin detection. The four fixtures had zero native ERC
   errors. This does not replace the digest-pinned 10.0.0/10.0.5 lane; see
   LINT-002 for evidence and fixture hashes.
   3. **Verify exact custom-symbol applicability.** LINT-091 extends the
   project-authored LINT-069 role map with a passive two-pin capacitor role
   consumed only by LINT-046. Synthetic typed cases cover exact identity,
   valid and wrong-return topology, DNP, stale maps, role isolation, and
   ordering; CLI/MCP parity and pinned native fault/control fixtures are in
   place. Tagged acceptance `v0.5.0rc17` (GitHub run `37863872527`) confirmed
   exact KiCad 10.0.0/10.0.5 behavior, with repeatable exports for the mapped
   control and wrong-return fault. This adds custom-symbol applicability to an
   existing REVIEW heuristic, not a new electrical conclusion. LINT-092 extends LINT-089's native
   `power_in` evidence to non-connector components whose pin functions are
   generic or absent. The synthetic lane checks open and explicit no-connect
   faults, connected and DNP controls, connector exclusion, and CLI/MCP parity.
   It remains REVIEW-only and does not infer the pin's positive-supply or
   reference role.
3. **Measure the value of existing REVIEW rules.** Continue with public
   geometry, LED, and peer-connector cases that have applicability signals.
   The public STM32 USB-to-triple-UART sample already recorded under LINT-031
   is an applicability case, not a confirmed-fault benchmark: it has repeated
   generic headers but no independent pinout that can establish whether a
   differing return or supply is wrong. The existing peer-pin and reviewed-role
   rules cover this class. Do not add another connector heuristic from this
   sample without a seeded fault/control that demonstrates new value.
   The LINT-017 `POR_B`/`PORN` native alias lane now passes locally on pinned
   KiCad 10.0.5 and is enabled in the GitHub package job; owner dispositions
   for connected-bias and intentional-NC examples remain open.
   LINT-024 now has full exact-version native coverage on KiCad 10.0.5 and
   10.0.6, including a valid paired-connector layout that remains a REVIEW
   candidate while its contacts share one native net. The exact KiCad 10.0.5
   re-screen of its two public-template J1
   wire/body candidates is complete: both show the same unique layout with
   clean ERC and byte-identical repeated exports. Keep author intent unresolved
   until an owner disposition is available; this is not a false-positive count.
   Avoid repeating the same layout as another sample. Keep the rule opt-in and
   seek a distinct, supported candidate or author disposition for further
   precision measurement. A 2026-10-05 parser rescan after text-alignment
   support now returns complete coverage for all eleven rule groups on the six
   unchanged public schematics, but retains only that same unresolved layout.
   This closes the stale text-support measurement and adds no new candidate or
   author disposition.
   For LINT-061/066, use only source-matched public examples that expose
   supported digital-peer functions. The 2026-10-03 workflow-template screen
   found no LINT-066 candidates in its three examples with native toolchain,
   ERC, DRC, and netlist
   checks passing; their aggregate summaries are `FAIL` because design-lint
   returns `REVIEW` for undeclared connector inventory. Record that sample as
   inapplicable and leave precision unmeasured. For applicable examples, record
   evaluated coverage, confirmed useful findings, false positives, missed
   seeded faults, and reviewer effort. Keep the current opt-in or REVIEW
   defaults until the evidence supports a change.
   The public STM32 USB-device sample recorded under LINT-031 had no
   output-driven LED topology, so LINT-063 was inapplicable and reviewer value
   remains unmeasured. A secondary screen of four KiCad 10.0.5 bundled demos
   also found no supported LINT-066 pattern; all 50 LED-like symbols used
   custom library identities without PART_ID role maps, so local LINT-063 was
   outside its declared predicate on those samples. A repeated kicad-happy
   v2.2.1 screen of the public Arduino
   and Raspberry Pi LED examples then produced both `LA-AUD` classification
   and an `LR-001` error on each: the audit names the fitted 1 kΩ `R1`, while
   the error says no series resistor exists. The public example docs describe
   the GPIO-to-R1-to-LED-to-ground path. Treat `LR-001` as a confirmed false
   positive for this topology; the classification may be useful review context,
   but reviewer effort was not measured and its contradiction prevents direct
   adoption. Exact pins, hashes, and limits are recorded under LINT-031.
   A broader exact-version screen of bundled KiCad project roots is now
   recorded under LINT-063/066/074: it found no supported candidate for those
   rules in this public demo corpus. Stop repeating this generic demo corpus.
   The next useful screen needs a source-matched public design with a direct
   UART peer and explicit reference pins, or a supported SPI/UART peer whose
   native power-pin types and explicit rail labels satisfy LINT-066. Keep
   author disposition, false positives, and reviewer effort unmeasured until
   such a case is available.
   A targeted HALPI2 public-project screen found a documented isolated RS-485
   interface with separate `GND` and `GND_RS485` nets, but no direct UART peer
   link for LINT-074. Keep it as an out-of-scope boundary control; do not widen
   the direct-peer predicate across an isolator based only on TX/RX labels.
   These results do not measure field precision or false-negative rate.
   The 2026-10-07 Calcumaker screen is now pinned and recorded under LINT-031.
   The deterministic label path found one serial-map coverage candidate on each
   of the MCU and keyboard roots, where native package-pin functions and generic
   connector functions left the earlier function-only detector inapplicable.
   The design document describes the MCU-to-keyboard USART link and identifies
   +3V3/GND; a native typed netlist confirms both signals and one reference net
   on each board. This is an applicability/discovery result under an
   intentionally unconfigured tooling roster, not a confirmed defect, ground
   requirement, or field-precision result. The sample has only one +3V3 domain,
   so LINT-066 remains inapplicable; its generic pin functions also leave
   LINT-074 outside its predicate. No source was copied into Tooling. The next
   useful peer/reference sample needs a source-matched public pinout or an
   independently authored synthetic requirement with fault and valid controls.
   A separate Calcumaker PCB geometry screen in LINT-031 used installed KiCad
   10.0.6 on its display, MCU, and keyboard boards; all three snapshots had
   zero tracks, zones, and vias. LINT-020 remains unmeasured on these
   placement-stage boards because it requires native copper connectivity.
   A second 2026-10-07 public screen of [Antmicro's CM4 Baseboard][antmicro-cm4]
   is recorded under LINT-031 as a multi-UART boundary control. Its README says
   KiCad 9.x; the KiCad 10.0.5 export is therefore a compatibility probe. Four
   UART channels are labeled across generic translator and bridge pins, while
   the identified `GND` pins share one schematic net. Existing serial peer and
   reference rules produce no candidates because the pin functions do not name
   TX/RX and the labels do not terminate at one connector candidate. The public
  sample has no approved pinout to establish a missing return. LINT-082 now
  adds a REVIEW-only label-pair path with synthetic split/common, map, ambiguity,
  CLI/MCP, hash-seed, and pinned-native fixture coverage. Its exact KiCad
  10.0.0/10.0.5 synthetic lane passed locally on 2026-10-07; see LINT-082 for
  source and normalized-netlist digests.
   [Antmicro's Debug Toolkit](https://opensource.antmicro.com/projects/ftdi-toolkit/)
   remains inapplicable to direct IC-to-IC peers because it exposes two
   independent FTDI UART channels at headers with selectable IO voltage.
4. **Advance one cohort candidate at a time.** Use LINT-031 to pin the source
   revision and installation procedure, compare fault and valid-control cases
   with the local baseline, and record unique detections, duplicates, misses,
   localization effort, and maintenance cost. The 2026-10-03 kicad-happy
   single-pin trial distinguished the two-peer open-contact fault from its
   common-net control, but its J2.1 prompt duplicates LINT-047. On the new
   valid off-board power-port control, `NT-001` prompts on both mapped contacts;
   local coverage already reports REVIEW when J1 is undeclared and PASS after
   the independently authored interface map is complete. No general
   singleton-net rule is justified. The candidate suppresses J2.1 when an
   explicit no-connect marker is added; the source-bound local native lane
   retains its REVIEW prompt on KiCad 10.0.0 and 10.0.5. Keep that conservative
   prompt because the marker alone does not resolve peer intent. The connected
   UART peer control is quiet under `NT-001`, while its source-bound roster asks
   for REVIEW when undeclared or partial and passes with the complete map. On
   the open test-point/connector fixtures, each `NT-001` item matches a native
   ERC `pin_not_connected` error on both pinned versions. These comparisons add
   no unique singleton-net detection. The off-board serial fixture also
   produces no unique detection: its four valid TX/RX singleton warnings match
   native ERC `isolated_pin_label` warnings, while the source-authored external
   peer map clears the local serial coverage prompt. A repeated-child-sheet
   control is covered below by source-bound geometry and native ERC. Do not add
   a general singleton-net rule; test broader hierarchy styles only when a
   specific gap remains beyond existing source-bound checks.

   A 2026-10-05 follow-up used the same pinned candidate on the mapped generic
   supply fault/control. It emitted `NT-001` INFO for both singleton supply
   contacts only on the split fault, but did not relate them through the
   reviewed voltage domain; the local LINT-079 finding is more specific. This
   adds no unique domain-aware detection and does not justify a general
   singleton-net rule. The next cohort trial should target a distinct gap in
   the higher-priority connector, protocol, or geometry backlog.

   The 2026-10-07 kicad-happy source recheck identified one narrow same-net
   component gap: the local passive rule recognized `Device:R/C/L`, while
   SP-001 also covers two-pin diode symbols. LINT-081 adds exact `Device:D`
   family support with separate fault/control fixtures and keeps the rule at
   REVIEW. The candidate package was not installed; this was a source-informed
   first-party addition. Its exact KiCad 10.0.0/10.0.5 native fixture lane now
   passes locally; no hosted GitHub result is recorded. Its metamorphic case
   adds an unrelated fitted resistor: the typed netlist digest changes, both
   diode fingerprints remain stable, and a scoped D1 ignore stays applied while
   D2 remains open. This verifies ignore scope for this rule family, not across
   every lint rule.

LINT-089 closes one connector gap: every matching generic connector power-input
contact can be open together, so peer-outlier detection has no differing
assignment to report. Native KiCad electrical type now supplies bounded
evidence for a `REVIEW` prompt. The synthetic fault/control pair is repeated on
the digest-pinned KiCad 10.0.0 and 10.0.5 images in the connector acceptance
lane; it does not declare that the contacts must share a net.

This execution focus is updated as evidence closes. A completed implementation
is not a reason by itself to expand its scope or change its default policy.

### P0 — Coverage and regression foundations

#### LINT-001 — Report contract and interface coverage gaps

- **Status:** Implemented v5. Reports preserve coverage separately from
  electrical findings. The same bounded connector identity feeds inventory
  coverage and connector pin, power-input, decoupling, return-anchor, and USB-C
  heuristics; an exact project-reviewed interface reference can extend those
  checks to a custom symbol. Inventory coverage also includes every instance
  with the same native symbol identity as a reviewed connector, so an unlisted
  peer remains visible for its own interface or not-applicable disposition.
  Discovery remains a documented heuristic.
- **Problem:** A clean heuristic report can still mean that nobody recorded
  which interface a connector implements or dispositioned every symbol pin.
  A partial pin map can hide an omitted interface contact even when no current
  lint rule recognizes its function.
- **Evidence and check:** The interface catalog and connector review map each
  catalog pin to an exported component pin. Every unlisted symbol pin needs a
  reason. `connector_inventory_review` records the project owner's basis for
  checking the full schematic interface inventory. Native KiCad netlist
  evidence supplies symbol identity, pin numbers, pin functions, and net
  assignments. The report names `UNDECLARED`, `INCOMPLETE`, and `STALE`
  references and unaccounted/unknown interface and symbol pins. Missing scope
  review or an empty `UNASSESSED` scope keeps the lane at `REVIEW`; an explicit
  inventory review can confirm a project with no external connectors.
  Connector candidates are discovered by the bounded numeric `J`, `P`, `X`,
  and `CN` reference-prefix scan and by standard `Connector`/`Connector_*`
  symbol-library identities, excluding `Connector:TestPoint*`; project-reviewed
  interface references are also included in connector pin, missing-return,
  power-rail, and USB-C candidate checks. For inventory coverage, each
  project-reviewed custom connector additionally brings every instance with
  the same native symbol identity into scope. Those peers still require their
  own interface map or not-applicable disposition; symbol identity does not
  copy pinout approval.
  Custom symbol identities otherwise require that exact project review. The
  standard family names follow KiCad's
  [10.0.5 symbol-library tree][kicad-symbol-library-10.0.5].
  The report carries the inventory basis and interface-catalog path/digest; the
  enclosing design-lint report binds the project manifest, lint policy,
  schematic source, and native netlist. The shared design-lint service is
  exercised through direct, native-verify, and CLI/MCP paths.
- **Boundary:** Candidate discovery cannot prove that every physical interface
  appears on the schematic or uses a recognized reference prefix or library
  family. Custom aliases and third-party symbol libraries remain outside the
  automatic scan unless one instance with the same native symbol has a
  project-owned interface review; this expands inventory coverage but does
  not infer roles for an unreviewed peer. `UNASSESSED`
  means the scan found no candidate and no review declaration; without an
  inventory review basis it keeps the lane at `REVIEW`. The basis is a
  project-owned assertion, not proof that the schematic contains every
  physical interface. A manually declared interface review reference outside
  the automatic scan is included in coverage and bounded heuristics. Coverage
  never infers that returns, supplies, or protocol
  pins should connect. `grounding` and `pin_connectivity` remain the
  project-authored checks for those relationships. A not-applicable decision
  covers only its named schematic component and does not validate the physical
  assembly.
- **Fixtures:** `tests/test_connector_coverage.py` covers an undeclared
  candidate, complete interface and symbol-pin accounting, missing and unknown
  catalog/symbol pins, an explicit not-applicable decision, a reviewed
  reference outside candidate prefixes, standard connector symbols under
  nonstandard designators, test-point and nonconnector anti-controls, stale
  references, missing catalog records, a missing inventory review, and the
  `UNASSESSED` no-candidate state. A reviewed custom connector brings other
  instances with the same symbol into coverage while an unrelated custom
  symbol stays outside that inferred group. A typed-netlist test and CLI/MCP
  parity confirm that an omitted peer remains `UNDECLARED`; this new discovery
  case is stable under mapping-order changes, and an explicit
  `not_applicable` disposition closes the sibling coverage gap. It does not
  claim a native KiCad export. The reviewed-return regression also permutes
  project interface IDs, catalog-record and pin order, review rows, and pin-map
  keys; the coverage and full lint reports stay equal for fixed source digests.
  Parity also confirms the
  nonstandard-reference candidate and suppresses the test-point control. A
  pinned native fixture
  repeats the `U7` connector candidate and test-point
  control exports on KiCad 10.0.0 and 10.0.5 and verifies exact `libsource`
  identity plus normalized-netlist and coverage-report digests. The embedded
  shapes are synthetic; the lane tests identity serialization and parsing, not
  canonical library geometry. A separate control confirms an explicit
  inventory review can cover a project with no external connectors. The
  design-lint regression covers standard connector symbols under a nonstandard
  `U` reference, repeated-pin and peer-pin findings, open supply contacts,
  missing-return review, common-return/power controls, DNP exclusion, and custom
  symbols included only through a project-reviewed interface reference. CLI/MCP
  parity also verifies that custom symbols under nonstandard `A` references
  enter connector coverage and the heuristic only while exact catalog-backed
  interface reviews are present; split returns prompt, and common returns clear
  the candidate. Power
  path and USB-C tests cover the same identity boundary. A CLI/MCP parity case
  checks nonstandard-reference findings. Native fixture orchestration is tested by
  `tests.test_connector_inventory_fixture_lane`; the exact pinned exports run
  in `tests.test_ci_hosted.NativeConnectorReturnFixtureTests`. Native verify
  and CLI/MCP regressions assert that incomplete or undeclared coverage stays
  visible.
- **Remaining:** Physical connector inventory and symbols with custom library
  aliases remain human-authored scope decisions. Keep `UNASSESSED` distinct in
  reports; do not describe the candidate scan as exhaustive discovery.

#### LINT-002 — Connector mate and pin-role contract comparison

[kicad-symbol-library-10.0.5]: <https://gitlab.com/kicad/libraries/kicad-symbols/-/tree/10.0.5>
[kicad10-pad]: <https://docs.kicad.org/doxygen-python-10.0/classpcbnew_1_1PAD.html>

- **Status:** Implemented v2 for exact `common_net`, `separate_nets`, and
  intentionally `unconnected` relationships through the existing
  `pin_connectivity` contract. Explicit PCB net-tie and physical bond-path
  comparisons are implemented in LINT-025 because the schematic netlist cannot
  prove copper continuity. The native acceptance harness is wired to compare
  DB9 exports against common and per-connector-isolated requirements through
  both `GroundingAnalysis` and `PinConnectivityAnalysis`. It also compares a
  native open peer-power contact and common control against an authored shared
  +5V requirement, plus an independently powered/unused-contact control pair.
  These are synthetic test requirements, not project contract files. The full
  pin-connectivity matrix passed locally on the pinned native images on
  2026-10-07; the hosted GitHub result remains pending.
- **Problem:** Similar connector instances can have separately named or
  unassigned corresponding pins without a direct, project-readable assertion
  about their intended relationship.
- **Evidence and check:** For an exact project-authored list of component pins,
  `pin_connectivity` compares exported schematic net assignments to a required
  common net, distinct nets, or no assignment. An `unconnected` requirement
  also requires native symbol pin inventory; missing inventory fails closed,
  and stale pin references fail with their exact reference. `grounding`
  continues to check named ground domains and coverage.
- **Boundary:** Connector similarity is only a candidate generator. It is not
  the requirement. Do not silently add or alter project contracts to clear a
  finding. Keep accepted isolation explicit. Population-dependent connector
  hints exclude references marked DNP by the native netlist; connector inventory
  coverage still evaluates declared interfaces independently.
- **Fixtures:** Synthetic common-return pass and disconnected-return fault;
  independent-return pass and newly common fault; named wrong-net fault;
  intentionally unconnected pin pass and newly assigned-net fault; stale symbol
  pin reference fault; and missing symbol-pin-inventory fault for an otherwise
  unassigned component. A fitted-versus-DNP connector pair also checks that
  population-dependent pin hints ignore DNP peers while preserving findings on
  fitted connectors. These check the project-authored relationship contract.
- **Related heuristic regressions:** A four-connector synthetic case uses
  numeric DB9 pins 7/9 on separately numbered `0V PWM` returns and exercises
  both repeated-function and numbered-return review candidates, the common-net
  control, and an explicit rule-off decision for intentional isolation. A
  three-port case leaves one generic power contact unassigned while sibling
  contacts use separately numbered positive rails; both the pin-function
  mismatch and rail-name candidates identify it. No project board source is
  used. The native DB9 fault/control schematic pair is documented in the
  [four-port DB9 fixture README](../tests/fixtures/design_lint/four-port-db9-returns/README.md).
  The native generic-power-pin omission pair is documented in the
  [peer power-pin fixture README](../tests/fixtures/design_lint/generic-peer-power-pin/README.md).
- A synthetic exact-symbol connector group with incomplete pin-function
  metadata identifies a missing generic contact when two peers share one net,
  and a minority-net outlier when two peers agree. Consistent assignments,
  all-distinct independent ports, and a DNP outlier are controls. No project
  board source is used.
- **Native regression:** Hosted package acceptance exports split-return and
  common-return controls twice with each selected, digest-pinned KiCad 10.0.0
  and 10.0.5 image. This includes the exact synthetic four-port DB9 pins 7/9
  pattern on separately numbered `0V PWM` nets, with exact native evidence for
  all eight pins and a common-net control. A three-port generic-pin fixture
  leaves J3.1 unassigned while J1.1 and J2.1 use separately numbered positive
  rails; the native fault and common-rail control check peer-assignment and
  rail-name findings. It preserves raw export hashes and requires equality
  after normalization to the parsed netlist contract, exact review findings on
  fault cases, and clean lint passes on controls. Raw KiCad XML includes a
  changing export timestamp.
  A numeric-function variant renames pins 7/9 to native function text `7`/`9`
  and replaces return-like nets with neutral `NET_A` through `NET_D` labels.
  Both pinned KiCad versions preserve the two exact-symbol repeated-pin
  findings and four per-connector unknown-return coverage prompts. The
  `NET_COMMON` control clears the repeated-pin mismatch while retaining those
  four role-coverage prompts. Its normalized typed-netlist digest also matches
  across versions. This isolates pin-identity evidence from net-name evidence;
  it does not assign an electrical role or require a common return.
  The container mounts only tooling-owned synthetic schematics read-only and
  a generated output directory read-write. A separate native fixture
  set covers different connector symbols: `GND` on a USB-style connector and
  `RTN` on a serial-style connector, matching `PWR` functions on both, and a
  separately assigned `SHIELD` pin. It checks split-return and split-supply
  review findings, an unassigned serial return, and a common-return/common-power
  control that keeps the shield separate. This closes the gap between
  dataclass-only cross-symbol tests and native KiCad parsing without adding a
  rule or inferring that the domains must be common.
  The four-port DB9 netlists are also checked against two explicit synthetic
  grounding requirements: all eight pins on one `0V PWM` domain, or four
  per-connector `0V PWM n` domains. The matrix expects the split fault
  to fail the common-domain requirement and pass the isolated-domain
  requirement, with the common-net control producing the inverse. Each
  acceptance receipt records the source, native netlist, and grounding
  requirement hashes. The requirements are test-owned values, not an external
  project's contract.
  The acceptance lane now adds direct `PinConnectivityAnalysis` checks over
  the same DB9 exports and the generic peer-power fixtures. For DB9, the
  common-net requirement fails the split fixture and passes the common-net
  control; the isolated requirement has the inverse result. For generic power
  contacts, J3.1 left open while J1.1/J2.1 share `+5V` fails the common-rail
  requirement, while the complete three-contact control passes. An explicit
  variant requirement accepts separate J1/J2 output nets and an intentionally
  unused J3.1, and rejects the all-common control. The receipts bind each
  source, exported netlist, repeated normalized netlist, and pin-connectivity
  requirement digest. The exact-version lane passed locally on 2026-10-07 using
  the catalogued KiCad 10.0.0 image
  `sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3`
  and KiCad 10.0.5 image
  `sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`.
  All eight expected relationship outcomes and the stale-symbol-pin fault per
  version matched expectations. Repeated exports were stable, and the six
  normalized fixture netlist hashes matched
  across versions:
  `98c326c073ca0bf7ff38c00acddec5bbd2df1f5cb531936f3744a79bae533154`,
  `fbb740fb9f8c29bd880d871f33047aa8993ea99720d7707daca3feff41e3c3f2`,
  `2191755e294a0c26e1a60238e2bc1ef63aefca2b1c7c754c91ef4ec74a619a77`,
  `f150f82193d827efc6293d11e47af1e9ca5b0a050ca81f9a46fba7f40a481c3b`,
  `6db3e3b1076e1d09dcf946d4788da30b95ffe9fa99a8a6101b21c8da7f38a265`, and
  `84d3b98f56d7552448eef5b7113ab76ac28393a0933d722a5037e5ea41e7928f`.
  The four synthetic requirement hashes were
  `34be92f5f2160529103b0ebae985474a4d378adbf92ed28762e2f33a7ad46db0`
  (DB9 common), `47cb72763e37847de4f92dd57db093934bb539be2a8421eddb74f32ba0f7b6e0`
  (DB9 isolated), `42200be02b669b16033dcf9f213fb4c3f7db89d16119fa3c0eda2e998c3bd0b0`
  (peer common power), and
  `89757eec4c33e46a46ebb7a09554d08f1412ce914b0a30629fbbfca611b82665`
  (independent outputs plus unused contact). Receipts are local under
  `/private/tmp/kct-native-connector-pin-contract-20261007`; only tooling-owned
  synthetic schematics were mounted. The hosted GitHub run remains pending.
  A ninth pin-connectivity acceptance case applies an `unconnected` requirement
  to nonexistent pin J1.99 on the DB9 control export. Both versions fail that
  stale requirement with the exact diagnostic `unknown symbol pins=['J1.99']`;
  the source and normalized-netlist hashes match the DB9 common-return control,
  and the requirement digest is
  `bca062795033e030f2ccff16f3700ffeb8e81f8d9da16ddd2287b276ad716cd4`.
  The event receipt now retains stable per-check details alongside check IDs
  and statuses. These are synthetic contract-authoring checks, not board
  findings. Receipts are under `/private/tmp/kct-native-stale-pin-*`.
- **Version evidence (2026-09-30):** The hosted connector-fixture test passed
  against the clean public KiCad-Test checkout at `ed89536f0dbbcb013145af2994fef41b2250143e`,
  using the digest-pinned KiCad 10.0.0 image
  `sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3`
  and KiCad 10.0.5 image
  `sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`.
  Both versions reported the new four-port DB9 fault as `REVIEW` with exact
  J1–J4 pins 7/9 evidence under `connector.repeated_pin_function` and
  `net.numbered_returns`; the common-net control passed without findings. The
  DB9 source hashes are `c4a842c1685d5fbf21985aa22bd0b6436e163025f4381a8ac2544621c264e546`
  (fault) and `3c00cfdee7a7bbba3439baf49f82eb6911ead068cf04ac0782f8f8fe7297cecc`
  (control). Both versions produced the same normalized typed-netlist hashes
  for each case (`98c326c073ca0bf7ff38c00acddec5bbd2df1f5cb531936f3744a79bae533154`
  for the fault and
  `fbb740fb9f8c29bd880d871f33047aa8993ea99720d7707daca3feff41e3c3f2` for the
  control). Raw KiCad XML hashes are retained because export metadata can vary;
  repeatability is measured over the canonical typed netlist. Native event and
  command receipts remain under ignored `build/ci-hosted/native-connector-return-*/`
  paths in the disposable test project.
  The generic peer-power fault also passed in both versions: the exact open
  contact `J3.1` was reported alongside the two numbered rail assignments,
  while the all-connected `+5V` control passed. Its source hashes are
  `4e2382aede1643770a466a9c902b1e960f8a8ab0d1bc676a03db33dfe6e582a8`
  (fault) and `e50d57b2739dc49d3b164e0ea141f48835967fdc1982d3cfdd702f671dc7d197`
  (control); both versions reproduced normalized typed-netlist hashes
  `6db3e3b1076e1d09dcf946d4788da30b95ffe9fa99a8a6101b21c8da7f38a265` and
  `84d3b98f56d7552448eef5b7113ab76ac28393a0933d722a5037e5ea41e7928f`,
  respectively.
- **Mixed-symbol native evidence (2026-09-30):** The extended hosted fixture passed with the exact
  KiCad 10.0.0 image
  `ghcr.io/kicad/kicad:10.0.0@sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3`
  and KiCad 10.0.5 image
  `ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`.
  Both versions retained `J1.4=GND`, `J2.7=RTN`, `J1.1=PWR`, `J2.9=PWR`, and `J3.1=SHIELD` after
  native export. The split case emitted separate `connector.repeated_pin_function` findings for
  ground/return and PWR; the unassigned `J2.7` case emitted one localized ground/return finding; the
  commoned return and power control passed while `J3.1` stayed on `CHASSIS`. Each normalized typed
  netlist repeated identically. Source hashes and fixture boundaries are recorded in the
  [mixed-symbol fixture notes](../tests/fixtures/design_lint/cohort-cross-symbol-connectors/README.md).
- **CI revalidation (2026-10-03):**
  `NativeConnectorReturnFixtureTests` passed both digest-pinned KiCad
  10.0.0/10.0.5 cases. The lane re-exported the tooling-owned DB9 split-return
  fault and common-return control, numeric-function/neutral-net fault and
  control, generic missing peer-power pin, peer-pin
  outlier/divergence cases, and the cross-symbol return/shield controls. It
  used only synthetic fixtures and retained receipts under ignored `build/`.
- **Current local exact-version rerun (2026-10-08):** The same lane passed on
  KiCad 10.0.0 and 10.0.5. The four-port DB9 fault reported
  `connector.repeated_pin_function` and `net.numbered_returns`; the common-net
  control was clean. Numeric-only pin functions with neutral net labels still
  surfaced the pin mismatch while the common-net control removed that mismatch.
  The mapped grounding and pin-connectivity requirements, peer-power faults,
  cross-symbol controls, and normalized repeated exports also passed. Receipts
  remain under ignored `build/ci/native-connector-return-project-*/`; hosted
  acceptance for the current branch is not recorded.
- **Supplemental local native screen (2026-10-07):** The KiCad 10.0.6 CLI
  bundled with the installed application exported the DB9 split-return fault,
  common-return control, and both numeric-function/neutral-label variants
  twice. Raw XML and normalized typed-netlist digests repeated identically.
  The split fault emitted `connector.repeated_pin_function` and
  `net.numbered_returns`; the common control emitted neither. With numeric pin
  functions and neutral net labels, the fault emitted the two exact pin-number
  comparisons plus four unknown-return-role coverage prompts; the common
  control retained only those four coverage prompts. KiCad ERC reported zero
  errors and four synthetic-library warnings per source, with no diagnostic
  for the split return. This supports the bounded review heuristic and confirms
  name-independent pin evidence on one additional KiCad 10.x executable; it
  does not assert a required common ground or PCB continuity. Source and
  normalized digests are in the
  [fixture README](../tests/fixtures/design_lint/four-port-db9-returns/README.md).
- **Remaining:** No additional net-tie work is open here; see the synthetic and
  exact-version evidence recorded under LINT-025. Connector mate similarity
  remains a review candidate and never supplies the relationship contract.

#### LINT-047 — Generic peer connector pin assignments without a majority

- **Status:** Implemented v1 as `connector.peer_pin_assignment_divergence`, a
  default-review hint with exact findings, project rule overrides, and
  fingerprinted ignores.
- **Problem:** Matching connector instances can assign the same pin number to
  different nets while one or more exported pin functions are missing. With
  only two peers, or with no assignment shared by a majority, the existing
  outlier rule cannot say which contact diverged.
- **Predicate:** For fitted J/P/X/CN references using one exact native library
  symbol, compare each exported pin number. Report only when at least two
  contacts are assigned, their net assignments differ, at least one contact
  has unknown role metadata (absent or generic KiCad `Pin_N`), fewer than two
  contacts have meaningful pin-function metadata, and there is no unique
  most-common assignment. A unique repeated assignment belongs to the
  higher-confidence outlier rule. Open contacts
  remain with the existing outlier and named-pin rules; fully named groups
  remain with `connector.repeated_pin_function`.
- **Boundary:** Exact symbol and pin-number identity only makes a candidate
  comparison. It does not establish common function, required connectivity,
  isolation intent, PCB copper, or off-board behavior. Two independent ports
  can be a valid control; the finding asks the project to check its approved
  pinout before writing any connectivity contract.
- **Fixtures:** Two generic peers assigned to different nets; native absent
  function and generic `Pin_N` cases; a four-peer tie
  with two assignments on each net; three distinct assigned nets; same-net
  control; DNP exclusion; fully named and partially named groups delegated to
  the existing function rule; explicit review/block/off and fingerprint-ignore
  policy; CLI/MCP parity. All netlist inputs are synthetic.
- **Native evidence:** The tooling-owned
  [generic peer-pin fixture set](../tests/fixtures/design_lint/generic-peer-pin-assignment-native/README.md)
  exports absent-function and generic `Pin_N` faults and their controls twice
  on digest-pinned KiCad 10.0.0 and 10.0.5. Both report the no-majority fault
  as `connector.peer_pin_assignment_divergence`; each common-net control
  passes. The same lane asserts that a unique two-to-one assignment emits only
  the higher-confidence outlier rule.
- **Done:** The new default-review finding is catalogued, source-bound to exact
  pin/net evidence, independently configurable, and exercised by synthetic
  fault/control, exact-version native export, and CLI/MCP parity checks. No
  project source is used.

#### LINT-048 — LED directly across recognized supply and return

- **Status:** Implemented v1 as
  `component.led_directly_across_supply_and_return`, a configurable
  default-review hint.
- **Cohort input:** The pinned kicad-happy `validate_led_resistors` LR-001
  source identifies a potentially useful visible-resistor review question,
  while also estimating LED current from guessed color/voltage/current limits.
  A read-only trial on synthetic KiCad schematics produced LR-001 for an LED
  directly across `+3V3` and `GND`, and no LR-001 for a series-resistor
  control. The candidate also missed the direct-rail fault when a resistor
  appeared in parallel across the same rails, because its topology scan treated
  that resistor as a limiter. The Tooling rule keeps only the independently
  supportable direct rail-to-return pattern and does not copy value/current
  estimates, fixes, severity, or candidate code.
- **Predicate:** For a fitted exact `Device:LED` symbol with exactly two
  inventoried pins, report when both pins have unique, distinct native net
  assignments, and one net has an exclusive recognized positive-rail role
  while the other has an exclusive recognized return role. The candidate
  remains present if a resistor is merely parallel across those same nets.
- **Boundary:** This asks the reviewer to inspect polarity, current limiting,
  and the source/driver. It cannot establish forward operation, current,
  source limiting, resistor value, off-board circuitry, physical copper, or
  whether the LED is part of an unusual protected assembly. Only the exact
  `Device:LED` symbol ID and existing bounded power/return recognizers are in
  scope; custom, addressable, multi-die, incomplete-pin, and unrecognized-net
  cases remain outside the predicate. No resistance threshold or universal
  resistor requirement is asserted.
- **Fixtures:** Synthetic LED directly between recognized supply and return;
  visible series resistor; parallel resistor still faulted; DNP LED; exact
  symbol and pin-inventory boundaries; unrecognized rail; recognition through
  attached native supply/return pin functions; project override, off, exact
  ignore, and CLI/MCP parity. No project source is used.
- **Validation state:** The candidate analyzer trial distinguishes the direct
  rail fault and series control and exposes its parallel-resistor miss. Local
  source-bound predicate, policy lifecycle, test controls, and CLI/MCP parity
  are implemented. Native KiCad 10.0.0 and 10.0.5 source-to-netlist regressions
  now check the direct-rail fault, series-resistor control, and parallel
  resistor fault. The rule reports the two direct bridges and leaves the
  control clear on both versions, with repeated parsed netlists matching.
  Native ERC remains untested. No proprietary project source or fixture was
  inspected or stored.

#### LINT-049 — USB connector-to-PHY data path contract

- **Status:** Implemented v2 as an opt-in, project-mapped REVIEW rule. The
  cohort's universal series-resistor heuristic remains unadopted.
- **Cohort input:** The pinned detector looks for connectors whose value or
  library ID contains `USB`, recognizes a bounded set of D+/D− pin names, and
  reports when it cannot find a 15–33 Ω resistor on the connector-side data
  net. It also attempts to use MCU datasheet features as an exemption.
- **Trial evidence:** The two-pin synthetic USB parser fixture without external resistors produced
  one finding per data line; a visible 22R-per-line control produced no finding. Repeated candidate
  runs had identical filtered output. A separate Tooling comparison on equivalent synthetic
  `NetlistContract` objects emitted the broader named-pair review finding for both cases. This is
  now regression-tested by
  `tests.test_design_lint.DesignLintTests.test_named_complementary_nets_prompt_for_reviewed_pair_requirements`.
  The fixtures and reproduction commands are in
  [the USB cohort trial](../tests/fixtures/design_lint/cohort-usb-series/README.md).
- **Problem and evidence:** The expected topology depends on the selected PHY.
  ST AN4879 Rev 12 states that the matching output impedance is embedded in
  STM32 internal USB PHY pads and no external resistors are needed
  ([manufacturer note](https://www.st.com/resource/en/application_note/an4879-usb-hardware-and-pcb-guidelines-using-stm32-mcus-stmicroelectronics.pdf)).
  TI's TUSB2036 Rev I datasheet says its USB DP/DM pairs require approximately
  27 Ω series resistors ([manufacturer datasheet](https://www.ti.com/lit/ds/symlink/tusb2036.pdf)).
  The pinned cohort analyzer reports both integrated-PHY and external-PHY
  missing-resistor cases, so its generic prompt is not adopted.
- **Predicate:** A project-authored `design_lint.usb_data_path_map` names the
  exact connector and PHY symbol/footprint, D+/D− endpoint pins, expected nets,
  and per-line `direct` or `series_resistor` topology. A series path maps the
  exact fitted resistor symbol, footprint, endpoints, and project-approved
  nominal range. An optional reference policy records `common_net`,
  `separate_nets`, or `bonded`; a `bonded` entry also names the exact passive
  two-pin component, value, footprint, and pin-to-net assignments. The rule
  compares those decisions with native KiCad 10 XML netlist evidence. Direct
  paths support documented integrated PHYs; series paths support explicitly
  selected external resistor networks. It uses the standard project `review`,
  `block`, `off`, and exact-ignore lifecycle.
- **Boundary:** This rule checks a schematic decision after the project
  supplies it; it does not infer applicability, select resistor values, or
  validate the referenced manufacturer document. A mapped bond checks native
  component and netlist assignments but does not prove that the component
  conducts or that PCB copper joins the endpoints. V1 models one conventional
  resistor per data line or a direct path. It does not prove placement, signal
  integrity, PCB copper continuity, protector behavior, USB-C roles, or USB
  3.x lane design.
- **Fixtures and validation:** Synthetic integrated-STM32 direct-path control;
  TUSB2036 27R-per-line control; missing, DNP, wrong-value, and wrong-net
  series-part faults; malformed contract topologies; exact 0R reference-bond
  control and absent, wrong-identity, wrong-value, DNP, active-pin, and
  wrong-net bond faults; rule override, disable, exact-ignore, CLI/MCP parity,
  mapping-order stability, and independent-process hash-seed stability. The
  new fault is distinct from the broad named-pair prompt
  because that baseline does not compare connector-to-PHY component topology.
  Fixtures contain no product design.
  Native schematic netlist exports are now regression-tested with synthetic
  direct-PHY control, external-PHY 27R-per-line control, a source-hashed
  external-PHY control with a mapped 0R reference bond, and resistor-bypass
  fault fixtures on KiCad 10.0.0 and 10.0.5. The controls have no USB path
  finding; the bypass fault produces one finding for each data line. Repeated
  exports match after normalization to the parsed netlist contract. This does
  not run native ERC or validate PCB copper, placement, or signal integrity.
  Fixture hashes, exact image digests, and the reproduction command are in
  [the native USB regression README](../tests/fixtures/design_lint/usb-data-path-native/README.md).

#### LINT-003 — Paired-line and differential-interface completeness

- **Status:** Implemented v3 as review-only checks for bounded built-in
  CANH/CANL, USB D+/D−, USB SuperSpeed SSTX/SSRX, TX+/TX−, and RX+/RX−
  aliases, plus opt-in project aliases tied to an exact native symbol identity.
  Stale symbol/function mappings block lint; fitted DNP symbols are skipped.
  Connector peer mapping and physical pair constraints remain separate work.
- **Problem:** A named pair can be half-connected or have one side routed to a
  different interface while ordinary pin-assignment checks pass.
- **Evidence and check:** The native-netlist check reports incomplete pairs when a counterpart
  function is absent, a side lacks a unique net assignment, multiple pins map to one side, or both
  functions share a net. A valid control has exactly one pin per side assigned to distinct nets. USB
  SuperSpeed function aliases include SSTX/SSRX and the USB-IF Standard-A/Standard-B forms
  StdA_SSTX/StdA_SSRX and StdB_SSTX/StdB_SSRX, as documented in the
  [USB-IF USB 3.1 Front-Panel Implementation Document](https://www.usb.org/sites/default/files/USB3p1_Front_Panel_CabCon_Implment_Doc_Rev1p1.pdf).
  The
  [USB Type-C Specification Release 2.0](https://www.usb.org/sites/default/files/USB%20Type-C%20Spec%20R2.0%20-%20August%202019.pdf)
  records the naming transition from SSTX/SSRX to TX/RX. These aliases are checked with synthetic
  fault and valid-control cases plus the
  [pinned native fixture lane](../tests/fixtures/design_lint/complementary-pair-native/README.md).
  Project aliases are separately validated with synthetic vendor-named functions,
  a missing-net fault, a valid pair, a DNP control, stale-map blocking, exact
  symbol binding, CLI/MCP parity, and order-stable alias digests. Add
  project-authored peer maps before comparing across connectors or active devices.
- **Boundary:** Pin naming is vendor- and symbol-dependent; A/B polarity is
  inconsistent across RS-485 vendors. Do not infer off-board pairing,
  impedance, polarity correctness, or isolation from names. Keep this a review
  hint unless an interface contract gives the pair map.
- **Fixtures:** Synthetic open USB data side; both sides on one net; complete
  USB data pair on separate nets; intentionally unused pair with an exact
  project-owned ignore; Standard-A/Standard-B SuperSpeed aliases with open-line
  faults and complete controls; lane-indexed USB-C anti-control; exact-symbol
  project aliases with fault/control/stale-map checks. Repeated native exports
  on KiCad 10.0.0 and 10.0.5 verify the built-in pin-function text survives
  netlist normalization. Cross-component peer pairing, polarity, and PCB
  constraints require separate requirements and evidence.
- **Remaining:** Model explicit connector-to-device pair maps only when a
  cohort fixture demonstrates detection beyond existing `pin_connectivity`
  contracts. Do not infer that similarly named connector or device pins must
  connect across symbols.

#### LINT-004 — Rule catalog and fault/control coverage ledger

- **Status:** Implemented v2; additions to the active rule set must update the
  package catalog and pass its fixture-reference and emission-coverage tests.
  The CLI and read-only MCP surface can list the typed catalog without project
  or native evidence, so teams can inspect rule defaults and limits before
  enabling project overrides.
- **Problem:** A rule can be present without its intended detection range,
  supported evidence, known false positives, or negative controls being easy
  to audit.
- **Evidence and check:** Maintain rule metadata for ID, intent, evidence
  adapter, deterministic predicate, current maturity, supported versions,
  limitations, fixtures, and source references. Validate that every active
  rule has both fault and valid-control fixtures and that emitted IDs exist in
  the catalog. The standalone catalog query returns the same digest-bound typed
  metadata through CLI and MCP.
- **Boundary:** The catalog describes evidence, not electrical approval or
  project applicability. It must not become a duplicate project contract.
- **Fixtures:** Unknown rule ID; missing fault/control fixture entry; a valid
  intentional-isolation control; stable report/fingerprint case; backlog rule
  inventory and repeated guide counts that match the active package catalog;
  CLI/MCP catalog parity without a native summary; readable text output with
  default modes, evidence, and limits.
- **Done when:** CI can identify an undocumented rule or missing required
  fixture, and a reviewer can trace each report finding to its evidence and
  limitations.

#### LINT-076 — Analyzer execution and skipped-check coverage

- **Status:** Implemented for demonstrated gaps. `mapped_check_runs`
  distinguishes an optional mapped check that was not configured from one
  that ran with zero findings. It covers USB data-path, series power-path, and
  power-sequence maps, the three mapped checks without a dedicated coverage
  report. A 2026-10-07 review of the LINT-066 public applicability screens found
  that a quiet peer-voltage report did not distinguish missing supported pin
  functions from same-voltage peers. The report now adds bounded
  `digital_peer_voltage_coverage` entries for SPI and UART/USART: counts bind
  recognized and assigned endpoints, direct links, explicit-label comparisons,
  complete-map suppression, candidate groups, the native netlist digest, and
  authored-map provenance. This is a targeted extension, not a global per-rule
  ledger; it does not claim that every interface was recognized. The LINT-086
  USB reference heuristic now also reports bounded coverage: no recognized USB
  endpoints, incomplete endpoint evidence, no supported connector-to-PHY paths,
  or evaluated paths. Its counts bind recognized/supported endpoint groups,
  DNP/incomplete dispositions, supported paths, common/separate reference
  relationships, map-covered split paths, emitted candidates, and the native
  netlist plus typed USB map digests. The CLI text report explains each status
  so a zero-finding run distinguishes absent recognition, incomplete evidence,
  unsupported topology, and a completed path review. The report also includes
  one deterministically ordered `path_entries` record per supported
  connector-to-PHY path, with endpoint identity, reference-pin assignments,
  common/split/map-covered disposition, matched D+/D− pins and nets, and any
  accepted series resistors or two-pin shunt branches. The text and typed JSON
  reports expose this same source-level evidence. The optional entries preserve
  compatibility with earlier schema-2 reports; they describe exported net
  assignments and do not establish a physical return path or copper bond. The
  connector peer-pin review now has a similarly bounded coverage summary: it records candidate
  and fitted connector counts, exact-symbol pin groups, assignment and function
  metadata states, repeated-function groups, finding counts, and the native
  netlist digest. It distinguishes candidates that are all DNP, no exact-symbol
  peers, no comparable pins, incomplete native pin inventories, and evaluated
  groups. A missing, empty, or inconsistent same-symbol inventory raises
  `REVIEW` and identifies its references.
- **Cohort input:** The public
  [kicad-happy v2.2.1 changelog](https://github.com/aklofas/kicad-happy/blob/v2.2.1/CHANGELOG.md)
  describes a `checks_run` manifest with run/skip reasons and examined counts,
  plus explicit diagnostics where connectivity-graph construction fails or
  conditional DRC rules are skipped. This is an observability idea, not a
  proposal to adopt its analyzer or its data model.
- **Problem:** Before v1, the report contained no machine-readable distinction
  between an absent optional USB data-path, series power-path, or power-sequence
  map and a configured map that matched. Other geometry and contract lanes
  already had dedicated coverage models, and ordinary heuristic scanners are
  invoked together through the shared candidate pass.
- **Evidence and check:** Each `mapped_check_runs` entry records the exact rule
  ID, effective mode, state (`NOT_CONFIGURED`, `EVALUATED`, or `BLOCKED`), map
  digest, native-netlist digest, authored item count, emitted finding count,
  and a reason when no map was supplied or source evidence blocks evaluation.
  USB count is the number of mapped interfaces; power-path count is the number
  of paths; power-sequence count is stages plus dependencies. Existing report
  findings remain the detailed mismatch evidence.
- **Boundary:** `EVALUATED` means the typed map comparison ran over the authored
  entries; it does not establish that the requirement is correct, complete,
  electrically appropriate, or equivalent to ERC/DRC. `NOT_CONFIGURED` is
  optional-map state, not a requirement gap. Counts do not claim coverage of
  off-board circuitry. The current slice does not claim a global execution
  ledger for every active rule.
- **Fixtures:** `tests/test_usb_data_paths.py`,
  `tests/test_power_paths.py`, and `tests/test_power_sequences.py` cover missing
  maps, matching controls, mapped faults, off-mode findings, exact map and
  netlist hashes, and a configured power map without a netlist digest.
  `tests/test_usb_peer_reference_review.py` covers USB coverage states and count
  dispositions, including incomplete, DNP, and unsupported-path controls; the
  input-order and cross-process hash-seed regressions compare the full report.
  Its CLI/MCP parity case compares the same source-bound coverage report.
  `tests/test_connector_peer_pin_coverage.py` covers common-net controls,
  split meaningful returns, two-peer and three-peer open-pin controls,
  incomplete pin inventory, mismatched same-symbol inventories, and an all-DNP
  candidate set. The existing connector CLI/MCP case compares
  the full `DesignLintReport`, including this coverage section. The three-process
  Python hash-seed regression also asserts that the connector peer fault and
  common control retain evaluated, netlist-bound counts across runs. The exact-
  version KiCad 10.0.0/10.0.5 connector fixture lane also asserts the native fault and
  common-control coverage states, counts, finding totals, and netlist hashes
  for both two-peer and three-peer groups, and records those summaries in its
  hosted receipt.
  A local KiCad 10.0.6 compatibility replay (2026-10-08 UTC) of the synthetic
  native exports produced raw netlist hashes
  `6a3d3499390a99cff28dc81e1b4b7c326510d74bebba9308e473b2dd1feb70b6`
  (three-peer fault),
  `ef15956f3023f2b23e27f57343bf50580917f8a15b2197aa7fa48ba409839900`
  (three-peer control),
  `058dfe318e503e6ac872b05415ab66347befd7d735a9831f05e79dbff9fff345`
  (two-peer open contact),
  `d9bb4e9728b34c4dd7b19a0d1b5ca70f937fcc279342c5f02485b3aeb68c2abc`
  (two-peer explicit no-connect marker), and
  `d9c4af9d8d127b301a44db42d6eef7f635f473d3ae28c87f60b26c071caf8e61`
  (two-peer common-net control). All reports were `EVALUATED` and source-hash
  bound; open and marked-open faults each counted one peer-pin outlier, and
  common controls counted none. The exact pinned KiCad 10.0.0/10.0.5 hosted
  results remain necessary.
  Existing parity cases compare the full report for each configured map family.
- **Audit result:** `DesignLintPolicy` maps for STM32 pin assignment, I2C
  addresses, external protection, crystal networks, regulator feedback, RC
  filters, connector-return distribution, and the six PCB geometry families
  have dedicated typed coverage reports. Connector inventory, control-input
  bias, I2C pull-up hints, and per-rule schematic geometry also expose their
  coverage state. Component-role-map validation issues are included in the
  report and block use of an invalid map; absence of this optional enrichment
  does not disable the shared candidate pass. SPI, serial-peer, USB-C, and
  digital-peer voltage requirements are represented in the electrical
  analysis contract, whose pending sections and check rows distinguish
  `NOT_CONFIGURED`, `NOT_APPLICABLE`, and evaluated results. This was a
  source-level audit of the current services, corroborated by their existing
  typed-service and CLI/MCP parity tests; it is not a claim that every
  engineering requirement is present or correct.
- **Aggregate-status clarity (2026-10-03):** Replaying the public template
  showed three examples with passing source-scope, toolchain, ERC, DRC, netlist,
  and source-unchanged checks, while each aggregate summary was `FAIL` only
  because its design-lint gate returned `REVIEW` for undeclared connector
  inventory. `native_status` continues to carry the aggregate summary status.
  Text reports and follow-up guidance now name it as the validation-summary
  status and direct reviewers to the per-check results. This keeps gate status
  distinct from the status of individual native commands; it does not weaken
  evidence acceptance.
- **Next:** Reopen only when a new enabled check family lacks an observable
  outcome or a fixture demonstrates that a configured check can be skipped
  silently. Connector peer-pin coverage closes the identified gap without
  creating a global status registry. Any further status must bind to actual
  service execution.

#### LINT-077 — Source-bound per-contact connector current-rating contract

- **Status:** Implemented in the shared electrical service with typed project
  requirements, CLI/MCP pass/fault parity, and retained-evidence replay. A
  synthetic native schematic and exact-version KiCad 10.0.0/10.0.5 acceptance
  lane passed locally on 2026-10-03. The lane remains enabled in GitHub CI; no
  hosted run for this dirty branch is recorded. No project contract opts into
  the check.
- **Priority:** P0 acceptance coverage for connector-interface ratings. The
  local pinned native evidence is complete; keep the lane in GitHub CI and
  require owner-reviewed source data before project adoption.
- **Cohort input:** kicad-happy v2.2.1 documents CC-001 as connector current
  capacity compared with PCB trace width. We narrowed this to the independently
  authored per-contact rating comparison; trace ampacity is deferred because
  it needs reviewed stack-up, temperature, topology, via/zone, and current
  allocation inputs. No candidate source code, runtime, threshold, or data is
  included.
- **Problem:** ERC and net connectivity do not compare expected current on an
  individual connector contact with that exact contact's rated and reviewed
  derated current. Similar net names and connector symmetry cannot establish
  contact load sharing or current capacity.
- **Contract:** `connector_contact_ratings` binds the exact connector
  reference, symbol, footprint, `PART_ID`, complete native pin inventory, and
  each included contact's pin number, native function, and expected net. The
  owner supplies sourced rated current and conditions, derated allowable
  current, maximum current on that contact, derivation bases, and the accepted
  utilization fraction. Identity or assignment mismatch fails and suppresses
  the numeric comparison as `NOT_APPLICABLE`. Each contact is evaluated
  independently; current is never apportioned across common-net pins.
- **Boundary:** The tooling does not validate datasheets, derive load or
  derating, infer that connector contacts share current, calculate copper or
  cable ampacity, or establish physical contact/copper continuity or
  temperature rise. This remains an owner-authored numeric contract, not a
  general connector heuristic or fabrication approval.
- **Fixtures:** Synthetic tests cover inclusive utilization equality,
  over-limit load, independent loads on contacts sharing a net, wrong symbol,
  footprint, `PART_ID`, inventory, pin function/net, unconnected/DNP/absent
  connectors, invalid derating, authored requirement order, native XML parsing,
  CLI/MCP parity, and retained-evidence replay that rejects omitted check rows. The
  authored-order case reorders multiple connector and contact requirements,
  confirms semantic check rows stay identical while serialized contract data
  changes, and changes one peer contact's current to prove only that
  utilization result changes. The native-map case independently reorders
  exported component, pin-function, and net maps.
  exact-version fixture source and run procedure are in
  `tests/fixtures/design_lint/component-voltage-ratings/README.md`.
- **Native evidence (2026-10-03):**
  `NativeComponentRatingFixtureTests.test_component_and_connector_rating_controls_export_repeatably`
  passed with digest-pinned images: KiCad 10.0.0
  `sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3`
  and KiCad 10.0.5
  `sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`.
  The contact source hash is
  `a210495b6df2c7f43ca4d44361c6be6f022d31116dbd4efa200c76faf03f3182`.
  Repeated exports in both versions produce normalized netlist hash
  `a61bc6c086e4abb5a3af84ddceae10f845a314c2f742cc450b1ed19c7f2419f1` and
  normalized ERC hash
  `dbcb2273e067531c5e027ac9482ccf7ede0b4e2f7bd3ac01ad83b25510664338`;
  native ERC errors are absent. The synthetic contact requirement passes at
  1.60 A and fails at 1.61 A in both versions. Raw XML hashes differ between
  KiCad versions; repeatability is measured over normalized typed netlists and
  ERC evidence. The local exact-version rerun on 2026-10-08 also passed against
  both digest-pinned images; the current dirty branch still has no hosted
  acceptance result.
- **Next:** Keep this lane enabled in GitHub CI. Before adopting the check on a
  project, independently review exact connector identity, contact ratings,
  environmental derating, and the maximum current assigned to each contact.
  Do not infer current sharing across common-net contacts.

#### LINT-078 — Empty native netlist cannot count as lint evidence

- **Status:** Implemented v1 in the shared contract-coach evidence reader.
  Source-bound contract coaching and design lint now return `BLOCKED` when a
  native netlist has no component records, even when KiCad returned success
  and the artifact hash matches. CLI and MCP use the same check.
- **Priority:** P0 evidence integrity. An empty export removes every
  netlist-based heuristic from consideration, so it must not become a
  `READY_FOR_REVIEW` inventory or an ordinary lint report.
- **Trigger (2026-10-03):** The pinned KiCad 10.0.5 CLI returned exit code 0
  when asked to export the legacy Eeschema source in the public
  [`tclarke/kicad-mikroBUS` repository](https://github.com/tclarke/kicad-mikroBUS),
  at commit `8d8c5699d4aee83d41cb7d3adc2d33b67bf45f7e`, path
  `examples/stm32-mikroBUS`. Its output contained no components, library parts,
  or nets. The run used this digest-pinned KiCad 10.0.5 image:

  ```text
  ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c
  ```

  the input schematic SHA-256 was
  `c37c866924fa316ae3ed194585bb457e696e8d090674c0ddbbf70452ca003b3c` and
  empty netlist SHA-256 was
  `04792857f1bad06326a7c8a30c46e1de89c7a17881cd3756e8eadbbffc213715`.
  The CLI upgrade command also failed on the legacy file's first character.
  This project is therefore not counted as a lint precision trial: the
  tooling's native project path expects modern `.kicad_sch` sources. No project
  source was copied into Tooling.
- **Evidence:** The existing native-validation contract already rejects an
  empty component inventory. The source-bound contract-coach reader could
  still accept a hash-correct empty export when the separate authored-contract
  check had failed with return code 0, and design lint consumes that reader.
  The new guard closes this path. Synthetic regressions cover the direct
  report, design-lint CLI/MCP parity, and the existing valid nonempty export.
- **Native trigger fixture (2026-10-03):** The tooling-owned blank schematic
  `tests/fixtures/design_lint/empty-native-netlist/empty.kicad_sch` exported
  successfully with zero components and zero nets on the exact project-pinned
  KiCad 10.0.0 and 10.0.5 images. Both versions produced the same normalized
  typed-netlist digest, `d893aaecc8176cc3016d7d1505d75f98bd7cb06a7cf95aae77884264f83531d1`;
  repeated raw XML can differ because of export metadata. A synthetic
  two-component control produced the same normalized typed-netlist digest,
  `08650946c2dfeb42dda98b16e7ba9b37b934fdd310e6fb70e9801cfec08fef7d`, on
  both versions. The blank-source SHA-256 is
  `ed107ec68043c2eb02fa6566b289b35f119b37c3296bbd1a0f12705ba36b2c9b`; the
  control source SHA-256 is
  `7d086f4f838504fa3cefc906f7f9e415240b10d89e95c9063c19780922915f16`.
  The native lane is enabled in package GitHub CI and retains receipts only
  under ignored `build/`. Unit and CLI/MCP parity tests independently confirm
  that a successful, hash-correct empty export is blocked by the shared
  source-bound evidence reader. See the
  [empty-netlist fixture notes](../tests/fixtures/design_lint/empty-native-netlist/README.md).
- **Predicate:** For schematic-backed `pcb` and `schematic` projects, parse
  the exact retained native XML and require at least one component record
  before classifying the source as reviewable. Nets may be absent for a
  disconnected symbol; component inventory may not be entirely absent.
- **Boundary:** A nonempty export does not prove that every source symbol or
  net was exported. An independently authored component/net contract remains
  the comparison that detects partial exports; open or incomplete project
  requirements remain review gaps.
- **Next:** Keep the guard in the shared typed service and parity suite. When
  source-to-netlist completeness gains additional native evidence, extend the
  contract comparison rather than treating any nonempty export as complete.

#### LINT-079 — Source-matched connector roles refine generic pin heuristics

- **Status:** Implemented for returns and extended on 2026-10-04 for mapped
  supply contacts. A complete connector coverage entry with a catalog digest
  and exact matches for the current symbol pin inventory, native pin functions,
  and net assignments can supply a role where native pin text is absent,
  generic (`Pin_N`), or numeric-only. Return roles already surfaced split and
  missing return candidates. The supply extension compares generic or
  numeric-only contacts across connector symbols only when their exact
  project-authored `voltage_domain` values match. The focused connector,
  design-lint, rule-catalog, fixture-orchestration, and reviewed
  custom-connector CLI/MCP parity suites passed on 2026-10-07: 574 tests and
  683 subtests. Existing pinned native fixtures have recorded actual exports
  on KiCad 10.0.0 and 10.0.5. The current exact-version lane was rerun locally
  on 2026-10-08 and passed on both versions. Numeric-only pin functions with
  neutral net labels still surfaced the mismatch, and the common-net control
  cleared it. Hosted acceptance for this revision remains pending.
- **Priority:** P0 connector coverage. A connector library may leave an
  interface contact generic or number-only, hiding the return or supply role
  from native-function heuristics. The reviewed interface catalog is already
  project-owned, so the lint can use it without inferring electrical intent
  from net names or connector similarity.
- **Predicate:** Use roles only from complete, current, digest-bound interface
  entries whose mapped component pin numbers, native function text, and
  assigned nets match the current netlist. A mapped return role refines
  `connector.repeated_pin_function` and `connector.no_connected_return`; mapped
  return or supply roles refine their unconnected-pin findings. A mapped
  supply role can also group different or missing assignments across connector
  symbols only when every grouped contact has the exact same authored
  `voltage_domain`. Stale, incomplete, digestless, or source-mismatched entries
  supply no roles.
- **Boundary:** A role and matching voltage domain classify candidate contacts;
  they do not mean that supplies must share a net or that independent,
  switched, ORed, or isolated sources are invalid. Return roles likewise do
  not determine common, bonded, or isolated grounding. Project-authored
  `pin_connectivity` and `grounding` requirements remain the only authority for
  those decisions. Findings default to `REVIEW` and follow existing
  per-project mode and exact-ignore behavior.
- **Fixtures:** `tests/test_connector_coverage.py` contrasts mapped generic
  return roles across USB and serial symbols, a common-net control, open mapped
  return/supply contacts, digestless coverage, and stale net assignments. The
  new synthetic pair uses generic `Pin_1`/`Pin_9` supply contacts on different
  custom connector symbols and neutral split-net names. Native-only lint is
  quiet; a complete map adds one review finding for a shared authored domain.
  A common-net control and a distinct-domain split control stay clear. The
  same two-connector fixture now leaves the mapped J2 supply contact open:
  coverage stays `COMPLETE`, one REVIEW finding carries the empty assignment,
  and no duplicate unconnected-pin warning is emitted. The common-net control
  passes; the open-pin prompt still does not require a shared rail. The
  three-peer extension uses three connector symbols and numeric/generic power
  pin functions: two mapped contacts agree on one rail while the third differs.
  It reports one localized REVIEW finding for a shared authored voltage domain;
  an all-common control and a distinct-domain control pass. This additional
  case is synthetic typed-netlist evidence, not another native export.
  The report names each native function, project catalog role, and voltage domain;
  it states that this classification does not require commonality.
  `tests/test_mcp_parity.py` now exercises three custom connector peers with
  generic returns and supplies through CLI and MCP: two agree on each net and
  one differs, while the all-common control clears both prompts. Removing the
  reviewed maps suppresses these custom-role candidates. The full typed reports
  match across surfaces. A more specific role-aware finding suppresses an
  overlapping lower-confidence peer-pin warning when it covers the same
  contacts. A separate two-peer regression covers the no-majority divergence
  case using synthetic typed-netlist evidence; it adds no native-export claim.
  A three-peer partial-map control leaves the generic outlier visible when the
  role comparison covers J1/J2 but J3 remains undeclared, preserving the full
  peer assignment set for reviewer inspection.
  `NativeConnectorReturnFixtureTests` exercises
  numeric-only pin functions and neutral net names through digest-pinned KiCad
  10.0.0 and 10.0.5
  native exports, with split and common-return controls.
- **Next:** Keep role-based grouping limited to return and supply, and retain
  these digest-pinned native cases in GitHub CI. Evaluate signal or shield
  grouping only when a separate synthetic fault/control pair demonstrates
  incremental value and includes isolated or independent-domain controls.

#### LINT-054 — Metamorphic stability coverage for deterministic rules

- **Status:** Baseline complete for all 85 active rules; CI requires every new
  active rule to add metamorphic fixtures or a reasoned not-applicable basis.
  The package catalog tracks `metamorphic_status`
  (`unreviewed`, `covered`, or `not_applicable`), registered
  `metamorphic_fixtures`, and a required basis for a not-applicable decision.
  This additive catalog change advances its schema to version 2 while report
  readers continue accepting version 1 as unreviewed. Catalog validation
  resolves and runs registered cases; the catalog suite rejects an unreviewed
  active rule and keeps the backlog inventory synchronized. Current catalog
  audit: 85 covered, 0 not applicable, 0 unreviewed.
- **Cohort input:** The public
  [kicad-happy-testharness methodology](https://github.com/aklofas/kicad-happy-testharness/blob/main/methodology.md)
  distinguishes baseline consistency from correctness and describes synthetic
  fault fixtures, a small reviewed gold tier, parser checks, and metamorphic
  tests. The methodology review is recorded under LINT-031; no corpus or
  candidate implementation was copied.
- **Problem:** A rule can pass one fault/control pair yet still depend on
  irrelevant input order, or fail to change when its causal input changes.
  Current catalog coverage names faults and valid controls but does not record
  these invariance and covariance properties systematically.
- **Work:** For every active rule, name at least one transformation whose
  semantic finding must stay the same and one causal mutation whose expected
  finding must change. Compare only rule-relevant semantic fields in these
  tests; source hashes, raw native receipts, and other provenance remain
  different when the source bytes change and must not be normalized in actual
  reports. Record unsupported transformations as explicit limits.
- **Boundary:** These tests establish behavior only for the authored synthetic
  transformations. They do not provide a gold answer for arbitrary boards,
  measure field false-positive rates, or establish electrical correctness.
  Public-project corpora and seeded analyzer outputs are not independent truth
  by themselves and are not imported as fixtures.
- **Initial coverage:** The CubeMX parser's conflicting alternate-function
  suffix keys are tested in both line orders and must block coverage. A valid
  `.ioc` pin-assignment reorder must preserve coverage and mismatches while
  changing the retained source hash. Connector-return distribution now also
  checks both that reversing net and pin-map insertion order preserves the
  finding and computed ratio, and that changing from the exact 3.0 ratio
  boundary to 4.0 changes the rule result. The four-connector numbered-return
  fixture also preserves evidence and fingerprint under mapping-order changes;
  replacing numbered sibling nets with one common return removes that naming
  hint. The exact-symbol peer connector outlier also preserves its localized
  open-pin finding under mapping-order changes; connecting the missing contact
  to its peers clears that candidate. The two-peer divergence prompt has the
  same order and agreement controls. Named connector VCC/GND open-pin findings
  preserve evidence under mapping-order changes; assigning those pins clears
  the matching findings independently. The broad multiconductor missing-return
  prompt also preserves its evidence under net/component/pin-function map
  reordering, and adding a recognized connected return pin clears it; existing
  controls keep return-like labels contextual and exclude shield and small
  connectors from the broad rule. The crystal-load, regulator-feedback, and
  RC-corner findings preserve their evidence under native-netlist map
  reordering and clear when corrected component values restore the authored
  target ranges. The I2C unmapped-responder prompt remains stable under native
  netlist map reordering and clears when the responder is added to the authored
  map; the strapped-address mismatch likewise remains stable and clears when
  the native strap assignment matches the mapped address. The SPI missing-roster
  prompt preserves its finding under netlist map reordering, retains the exact
  roster hash, and clears when the omitted device is added to the authored map.
  The missing-IC-decoupling prompt and direct LED rail-bridge finding also
  remain stable under netlist map reordering; adding a fitted capacitor or a
  series LED resistor clears the corresponding candidate. The USB-C
  unreviewed-port prompt preserves its source-hashed role-map evidence under
  netlist map reordering and clears when the project map lists that connector.
  A missing complementary signal assignment preserves its evidence under
  netlist map reordering and clears when the counterpart pin receives a distinct
  net assignment. The named complementary-net prompt likewise preserves its
  finding under netlist-map reordering; an exact project-authored pair map
  suppresses only that naming prompt. Its map digest remains in `BLOCKED`
  coverage until source-bound native DRC evidence is available and in
  `DISABLED` coverage when that check is explicitly turned off. For native
  differential-pair coverage, reversing native rule order and authored pair-map
  requirement order preserves semantic coverage entries while both raw input
  SHA-256 digests change; changing an authored width bound produces a
  `MISMATCH`. Mapped track-width findings are also stable when native track
  observations are reordered; the snapshot digest changes, while moving the
  narrow track to the authored boundary clears the finding. The mapped
  decoupling distance finding preserves its evidence when native pad inventory
  and connected-pad order are reversed; its snapshot digest changes, and moving
  the nearest eligible capacitor to the exact authored threshold clears the
  prompt. Switching-loop area and route findings are stable under pad and
  track-inventory reordering while snapshot digests change; returning native
  pad centers within the authored area limit clears the area finding, and
  measured via-connected route order remains exact. The unmarked orthogonal
  crossing retains its exact review candidate when the two wire records are
  reordered, while its source hash changes; adding a junction marker at the
  crossing clears the hint. The near-pin wire-endpoint hint preserves the pin
  identity and 0.5 mm distance across all supported rotations and mirrors while
  changed transforms produce changed source hashes; moving the endpoint beyond
  the authored search radius clears that candidate. The pin-line endpoint hint
  preserves pin identity and measured distances across supported symbol
  transforms and reversed segment ordering; shifting the wire 0.01 mm off the
  pin axis clears that candidate. The pin-tip-on-wire hint
  preserves pin identity and zero separation across all supported symbol
  transforms and reversed segment order; moving the wire 0.01 mm off the pin
  tip clears that candidate. The unmarked T-junction keeps the same endpoint
  and interior wire identities when source wire records are reordered; adding
  a junction marker at that contact clears the candidate. The label-endpoint
  hint preserves label/wire identities and distance under a joint translation;
  attaching the label directly to the endpoint clears the hint. The coincident
  text-anchor pair retains both text identities under joint translation, while
  separating one anchor clears the pair. The rendered-envelope overlap retains
  the same text pair and translated overlap box under joint translation; moving
  one label clear of the other removes the overlap finding. The wire/text
  crossing retains object identities and overlap length under joint translation;
  moving the wire clear of the text removes the graphical candidate. The text
  over symbol-body finding is stable when its root object is reordered, while
  moving the text away from the body clears the graphical candidate.
  Repeated numeric DB9 pin-function text on four exact-symbol connector peers
  also preserves the localized pin findings when separate return nets are
  renamed to neutral `NET_n` labels; the numbered-return name hint disappears,
  and the all-common pin control clears the repeated-pin finding. Numbered
  positive rails and unnumbered
  return-like labels preserve their findings under input reordering;
  merging or removing sibling labels clears their respective name hints. Next
  source-matched generic supply-role grouping preserves its REVIEW evidence
  and fingerprint under native net, symbol, pin-number, and function mapping
  reordering while the retained netlist digest changes. Putting both contacts
  on one net or assigning distinct authored voltage domains clears that
  candidate. The I2C duplicate-address check preserves collision evidence under responder
  and netlist ordering changes; separating the project-mapped bus segments
  clears that collision. The PHY-specific USB path finding is also stable under
  netlist mapping order, and restoring its mapped series resistor clears the
  diagnosis. The repeated same-function supply-pin finding preserves evidence
  and fingerprint under netlist-map reordering; assigning both pins to one rail
  clears the candidate. Component open supply and return findings preserve
  their evidence and fingerprints under netlist-map reordering; assigning both
  named pins clears those findings. Reset/enable/boot candidates remain stable
  under input-map reordering, and assigning each open pin clears only its own
  finding. I²C, SPI chip-select, and USB-C CC open-pin findings also preserve
  evidence and fingerprints under map reordering; assigning a specific signal
  clears only that signal's candidate. CANH/CANL warnings have the same
  order-stability and one-pin-at-a-time clearing check. The I2C pull-up
  findings preserve evidence under net-map reordering; adding each pull-up
  narrows the missing-line evidence, and adding both clears it. The equivalent
  resistance finding is stable under component ordering and clears in-range.
  The CAN termination prompt is order-stable; fitting a direct 121 Ω resistor
  clears it, while marking that resistor DNP restores the same finding. The
  active-low SPI chip-select bias prompt is order-stable and clears when its
  mapped 10 kΩ pull-up path is fitted.
  Same-net resistor, capacitor, and inductor prompts preserve their evidence
  under component/net-map reordering; splitting each passive's pins clears
  only that part's finding. The exact `Switch:SW_SPST` same-net prompt follows
  the same insertion-order and causal-split axis; the distinct-net control
  stays quiet.
  External-protection findings retain their semantic evidence under net-map
  reordering while the synthetic source hashes change. An authored
  `not_required` decision clears the applicability prompt, and restoring the
  mapped protector net clears the mismatch prompt.
  The reviewed-return map case now permutes project interface IDs,
  catalog-record/pin ordering, review rows, and pin-map keys while preserving
  coverage, findings, evidence, and fingerprints for fixed source digests.
  LINT-081 now adds an unrelated fitted resistor on separate rails to a
  two-diode fault. The native-netlist digest changes while both diode findings
  keep their evidence and fingerprints; an exact ignore for D1 persists and
  leaves D2 active. The four-port numbered-return fixture now uses a digest of
  each synthetic netlist; insertion-order changes and an unrelated fitted
  resistor change that digest while preserving the naming finding. Its exact
  ignore remains scoped to that finding. A separate exact ignore for one of
  the two peer-pin findings remains scoped as well; the other peer finding and
  numbered-return prompt stay open. The mapped power-path rule has the same
  isolation control: an unrelated resistor changes the netlist digest, while
  its exact map-scoped evidence and fingerprint remain stable; its exact
  ignore still applies.
  The mapped-check receipt retains the new netlist digest and unchanged
  requirement-map digest. The mapped power-sequence rule exercises the same
  source-scope invariant, including a changed netlist digest, stable map digest
  and finding fingerprint, and a still-applicable exact ignore. Further axes
  include unrelated-part changes for other evidence-scoped rules.
- **Done when:** Every active rule is assigned a documented metamorphic axis
  or a reasoned not-applicable decision; high-risk source-bound contracts have
  executable invariance and causal-mutation pairs in CI; and the catalog links
  those cases without weakening source hashes or CLI/MCP parity.

#### LINT-080 — Cross-process hash-seed determinism for lint reports

- **Status:** Implemented v32. Fault/control and applicability reports cover
  synthetic DB9 returns, same-net two-pin diodes, fuses, and SPST switches,
  direct and parallel-resistor output-driven LED faults with a series-resistor
  control, generic peer-pin outliers, project-mapped connector returns, series
  power paths, power sequences, UART-label discovery, STM32 CubeMX pin maps,
  the multi-UART split-reference heuristic, SPI/UART voltage-domain review
  with exact-map controls, CAN peer asymmetry, a connector-only SPI/UART
  boundary control, coverage-sensitive connector peer finding suppression,
  mapped PCB decoupling boundary reports, and a cross-symbol mapped-supply
  open-contact case, plus the typed contact-rating boundary and over-limit
  checks, DB9 grounding and pin-connectivity requirements, multi-device
  MOSFET stress checks, source-mapped USB data-path fault and topology
  controls, synthetic PCB signal-path rule coverage, synthetic keepout
  restriction coverage, and switching-loop route ambiguity reports. The test
  runs the shared typed services in three isolated Python processes, verifies
  that their runtime hash secrets differ, and compares complete serialized
  design-lint reports plus typed contact-rating and grounding check results
  byte-for-byte.
- **Priority:** P0 determinism foundation. Input-reordering metamorphic tests
  exercise explicit mapping changes in one process; they do not detect all
  output instability caused by set iteration or process hash randomization.
- **Cohort input:** The public
  [kicad-happy v2.3.0 changelog][happy-changelog] records a three-seed
  determinism gate and fixes for hash-seed-dependent analyzer output. Its
  `SP-001` passive-short check overlaps local LINT-051, so this increment
  adopts the determinism test method only and adds no detector or dependency.
- **Evidence:** The pytest-style `tests/test_design_lint_determinism.py` launches
  `tests/hashseed_probe.py` through the active interpreter's isolated pytest
  module entry point with `PYTHONHASHSEED` unset, checks that each process has
  hash randomization enabled and a distinct hash marker, and compares full JSON
  reports for the four-port numeric-pin return fault/common-net control, the
  same-net diode fault/distinct-net control, generic peer-pin outlier fault and
  common-net control, and a project-mapped return-role split/common-net pair.
  It also compares three source-mapped generic-peer reports: a split assignment
  with J3 undeclared, the same split with complete role coverage, and a fully
  common supply/return control. The partial-map report must retain both the
  mapped-role finding and the generic outlier for J2.1 while J3 remains
  `UNDECLARED`; complete coverage suppresses only the overlapping generic
  warning, and the common control has no mismatch findings.
  Three additional reports exercise reviewed peer-assignment scope with three
  generic `Pin_1` signal contacts explicitly declared unlisted and pin 2 mapped
  as return: separate peer groups suppress generic signal comparison while
  retaining all three split-return contacts for review; one shared peer group
  reports both split returns and signal divergence; and a common signal and
  return control passes. These compare complete typed-service reports across
  independently randomized processes, including group and role evidence.
  Three USB data-path reports compare an absent mapped D+ series resistor with
  the valid series path and a valid direct integrated-PHY path. The missing
  resistor remains one `bus.usb_data_path_mismatch` finding with one evaluated
  requirement; both topology controls clear that rule. The direct-path report
  retains its unrelated STM32 CubeMX and physical differential-pair REVIEW
  findings, confirming the USB path map does not suppress independent review
  families.
  A separate cross-symbol supply-role pair uses two exact, complete interface
  maps with the same authored `external-5v` voltage domain. The open-contact
  fault keeps `J2.5` with an empty net assignment in the REVIEW evidence and
  suppresses the overlapping generic open-pin warning; the common-net control
  passes. The mapped role and voltage domain make these contacts comparable
  for review, but do not require a shared rail.
  The LINT-077 pair compares the typed contact-rating checks at the inclusive
  authored utilization boundary (`1.6 A / 2.0 A = 0.8`, `PASS`) and just above
  it (`1.61 A / 2.0 A = 0.805`, `FAIL`). Both retain the same netlist digest;
  the changed authored load changes the requirement digest. The process probe
  compares these serialized typed check results with the design-lint reports;
  it does not invoke the complete electrical runner or create native evidence.
  The multi-device MOSFET pair uses the same synthetic Q1/Q2 typed netlist and
  changes only Q2's authored on-state drain-potential interval. The fault
  changes only `mosfet-stress/switch-q2/state-on/vds` from `PASS` to `FAIL`;
  Q1's checks remain `PASS`, and every check in the control passes. The netlist
  digest stays fixed while the requirement digest changes. These typed results
  are compared byte-for-byte across the three independently randomized worker
  processes; the test does not invoke native export or the full electrical
  runner.
  The LINT-063 matrix compares a direct output-to-LED candidate and a parallel
  resistor fault with a visible return-side series-resistor control. Both
  faults retain `component.led_directly_driven_from_output`; the series control
  clears that rule. Its full report remains `REVIEW` for the independent
  `net.return_labels_without_pin_roles` finding on the synthetic `LED_RETURN`
  and `GND` nets. This checks the typed topology distinction and complete-report
  stability across hash seeds, not resistor adequacy or physical behavior.
  The PCB decoupling pair compares a candidate 100,001 nm from the mapped IC
  supply pad against the exact 100,000 nm authored limit. The over-limit report
  remains `REVIEW` with `pcb.decoupling_proximity`; the boundary control is
  `PASS`. Both retain the same map digest, while their synthetic typed snapshot
  digests differ.
  The LINT-080 v28 extension compares complete serialized signal-path reports
  for a synthetic clock-rule limit changed from 20 mm to 19 mm and for the
  exact-rule control. The fault remains `REVIEW` with
  `pcb.signal_path_rule_coverage` and `INCOMPLETE` typed coverage; the control
  is `PASS` with `COMPLETE` coverage. A second pair compares a synthetic
  keepout snapshot missing its reviewed track prohibition with the exact
  keepout signature: the fault reports `pcb.keepout_intent_coverage` and
  `INCOMPLETE`, while the control is `PASS` and `COMPLETE`. Pytest-style
  scenario tests assert these fault/control outcomes. Both report pairs are
  included in the existing three-process complete-JSON hash-seed comparison.
  Their provenance fields are deterministic synthetic fixtures; these cases
  do not invoke native export or establish board-level evidence.
  The LINT-080 v29 extension compares a synthetic switching-loop trace with
  two possible track chains against a unique direct-chain control. The ambiguous
  route remains `INCOMPLETE` with an explicit multi-chain issue; the unique
  trace resolves to exactly 1,000,000 nm. The complete design-lint report
  remains `REVIEW` in both cases because component internals are intentionally
  unmeasured. Pytest tests assert both outcomes, and both full reports join the
  three-process JSON comparison to exercise graph traversal ordering.
  It also compares a project-mapped series power-path open-element fault and
  repaired control; the fault retains one `EVALUATED` authored requirement and
  one mismatch finding while the control passes. The power-sequence case
  compares an open-enable fault and repaired control; its fault retains an
  `EVALUATED` map with three stage/dependency requirements and one mismatch
  finding. The UART-label case compares an unmapped alternate-function MCU
  candidate (`REVIEW`, with `discovery_basis=net_label`) against an exact
  source-mapped MCU-to-header control that clears only
  `bus.serial_unmapped_peer`; its independent generic connector return-role
  review remains visible. Both complete reports carry their typed netlist
  digest, and the mapped control includes the authored map path and digest. The
  STM32 case changes one synthetic CubeMX signal assignment and compares it
  with the valid IOC control; both retain complete coverage and the same
  authored map hash, while the IOC source digest differs. The mismatch remains
  `REVIEW` and the control remains `PASS`.
  The connector-role mapped case hashes its typed netlist input, includes the
  interface catalog digest, and checks that the REVIEW evidence names each
  pin's role source. The power-path case checks the mapped run remains
  `EVALUATED` with one authored requirement and one mismatch finding. The test
  asserts each expected `REVIEW` rule and clean `PASS` controls where the
  report has no separate coverage gap; the serial-map control also asserts
  that its independent connector return-role review remains visible. The
  multi-UART pair asserts one localized `bus.serial_peer_reference_review`
  finding for the split J1/U1 reference and no such finding in the
  common-reference control; unrelated review findings remain in the complete
  reports as applicable. The SPI and UART voltage-domain cases each compare an
  unmapped `REVIEW` prompt with a complete exact-map control and assert
  suppression of the matching protocol-specific prompt. The CAN pair asserts
  that the divergent peers remain `REVIEW`, the common-pair control omits the
  finding, and each report's netlist digest changes with its typed input.
  The connector-only header report retains both SPI and UART coverage entries
  as `NO_SUPPORTED_ENDPOINTS`, with zero recognized endpoints, direct links,
  voltage comparisons, or candidate groups; neither direct-peer voltage rule
  appears in its findings. A separate `tests.test_mcp_parity` case loads the
  same header-only shape from retained synthetic native-netlist XML and asserts
  complete CLI/MCP report equality, preserving the same applicability counts
  and absence of peer-voltage findings.
  The DB9 requirement matrix serializes both `grounding_checks` and
  `pin_relationship_checks` for four combinations: split net assignments
  against common and isolated-domain requirements, plus common assignments
  against each requirement. Each result carries the typed-netlist digest and
  the relevant grounding or pin-connectivity requirement digest. For both
  services, split/common and common/isolated combinations fail, and the other
  two pass. A separate unconnected-pin check compares a component whose native
  pin inventory is absent with the same component carrying a complete
  inventory: missing evidence fails with the exact component name, while the
  complete, unconnected control passes. Both results bind their typed-netlist
  digest to the same requirement digest. The 2026-10-07 focused
  `DesignLintDeterminismTests`, `UsbDataPathTests`, and
  `DesignLintCatalogTests` run passed with 472 tests and 644 subtests in an
  isolated Python 3.11 environment. Its worker
  verified three distinct hash secrets and byte-identical serialized results.
  This is process determinism evidence; the separate pinned native lane remains
  the evidence for KiCad export behavior.
- **Boundary:** All cases use tooling-owned synthetic typed netlists or PCB
  snapshots and project-authored synthetic maps. This detects report instability across the
  listed fault/control and applicability cases; connector return, peer-pin,
  and USB data-path
  cases also have separate pinned native fixture coverage. The peer-scope
  extension's exact-version fixture lane is wired into GitHub CI; this record
  does not include a hosted run for the current revision. The serial reference case checks
  process stability for a heuristic already covered by synthetic native
  fixtures; it does not establish that separate UART references are wrong.
  The series-path case does not prove component conduction, and the sequence
  case does not prove hardware startup behavior. The STM32 map does not verify
  compiled or flashed firmware. UART-label discovery is a coverage prompt, not
  proof that a peer or connection is required; its map control does not
  establish PCB copper continuity. These cases do not prove electrical
  correctness, replace exact-version native exports, or establish that every
  active rule is process-deterministic. The SPI and UART voltage prompts are
  REVIEW clues based on exact typed pin and rail-label evidence; this hash-seed
  case does not measure their usefulness or false-positive rate on field
  designs. The PCB decoupling pair uses synthetic geometry records and adds no
  public-board or native PCB probe result. The mapped-supply case uses synthetic
  typed netlists and authored maps; it does not add a native-export result or
  prove that independent connector supplies are incorrect. The contact-rating
  pair tests the typed comparison function only; the separate exact-version
  native fixture lane remains the evidence for parsing current connector
  identity and assignments from KiCad exports. The MOSFET stress pair tests
  typed multi-device state calculations only; its separate pinned native lane
  remains evidence for parsing the synthetic MOSFET identity and pin map, not
  real-part suitability or process-level native export behavior.
  The LINT-080 v30 extension adds a pytest-style mapped reference-plane gap and
  a complete coverage control. The fault's synthetic zone hole leaves the
  straight-track centerline at exactly 4/5 coverage against a 9/10 authored
  threshold and emits `pcb.reference_plane_coverage`; the full-zone control
  measures 1/1 and stays quiet. Both complete source-bound typed reports join
  the three-process JSON comparison. These use synthetic typed geometry and do
  not invoke native export or establish board-level or physical evidence.
  The LINT-080 v31 extension compares unindexed `GNDA`/`GNDD` return-label
  candidates, numbered `GNDA1`/`GNDA2` candidates, and an explicit GND/RTN pin-
  function control across independent hash seeds. This covers the bounded
  one-letter GND suffix extension without treating similar names as a common
  net or changing review disposition. The v32 extension adds a synthetic
  24-pin library symbol to the three-process report probe. It verifies that all
  pin-function and electrical-type entries have their expected values and are
  serialized in key order. `read_netlist` now sorts pin numbers before
  building these maps; the change adds no lint rule or native KiCad result.
- **Next:** Extend the process-level determinism matrix to other high-risk
  source-bound report families when their complete synthetic fault/control
  reports can be serialized through the same shared service. Keep each
  extension separate from broad analyzer-corpus claims.

#### LINT-005 — Repeated component supply-pin net review

- **Status:** Implemented v1 as a review-only rule for repeated, recognized
  supply-function categories on one fitted non-connector component.
- **Problem:** An IC can have two pins with the same supply function assigned
  to distinct schematic nets while each pin is connected, so an unconnected
  pin check may not raise a question.
- **Evidence and check:** The KiCad 10 native XML netlist groups pins on one
  component by the existing recognized supply-function categories. It reports
  assigned pins when their exact schematic net assignments differ or one pin
  has ambiguous multiple assignments. An open member remains covered by the
  more specific unconnected component supply-pin rule. Findings use the
  existing project rule override and exact-ignore lifecycle.
- **Boundary:** This is a candidate for review, not an instruction to tie the
  pins. Separate nets can be intentional for a filtered supply or a
  datasheet-defined topology. Uncommon/unnamed functions and DNP components
  are outside v1; a schematic netlist cannot show a PCB ferrite or copper path.
- **Fixtures:** Same-function pins split across nets; same rail shared; distinct
  named supply functions on separate rails; explicitly DNP component; one
  unassigned member producing only the specific open-pin finding; exact
  fingerprinted ignore.
- **Done when:** Catalog, limitations, fault/control tests, deterministic
  report evidence, and project policy behavior remain in sync.

#### LINT-006 — Unnumbered return labels without explicit pin roles

- **Status:** Implemented as a review-only netlist candidate for multiple
  populated return-like nets whose attached symbol pin functions do not
  identify a return. It complements the numbered-return rule when connector
  pins have numeric or otherwise uninformative functions.
- **Problem:** Similar return domains can use distinct labels without numeric
  suffixes, so `net.numbered_returns` cannot surface them. Connector pin-role
  comparison may also lack a recognized pin function when the symbol exports
  numeric contact names.
- **Evidence and check:** The source-bound KiCad 10 native XML netlist supplies
  net names, pin membership, and exported pin-function text. If two or more
  populated return-like net labels not already covered by numbered-return
  groups attach only to pins without a recognized return function, the rule
  asks for review. Numbered-return groups are left to
  `net.numbered_returns`; explicitly named return pins are left to the
  connector pin-function rule. The bounded return vocabulary now accepts a
  one-letter suffix on `GND`, including `GNDA` and `GNDD`, which KiCad's
  [net-class example](https://docs.kicad.org/8.0/en/eeschema/eeschema.pdf)
  lists as a net matched by `GND*`. Matching names remain review-only and do
  not imply a common electrical domain.
- **Boundary:** The recognized label and pin-function vocabularies are narrow.
  Longer names such as `GNDAUDIO` do not match the one-letter suffix form.
  The rule does not infer that similarly named nets must connect, discover
  off-board grounds, or establish PCB copper or physical continuity. Separate
  analog, chassis, shield, isolated-interface, or other return domains may be
  intentional. Default disposition remains `review` with project override and
  exact-ignore support.
- **Fixtures:** Two unnumbered return-like nets on numeric pins and distinct
  connector symbols; explicit GND/RTN pin-function control; one return-like
  net; ordinary signal nets; a numbered sibling pair alone and alongside an
  unnumbered pair; review/block/off/exact ignore and stale fingerprint; catalog
  reachability.
- **Done:** Synthetic fault/control cases, policy lifecycle, catalog entry,
  documentation, and shared CLI/MCP report path are covered. No board source is
  used.

#### LINT-069 — Project-authored roles for custom symbol identities

- **Status:** Implemented first slice: the `led` role extends
  `component.led_directly_driven_from_output`. LINT-091 adds an exact
  `capacitor` role used only by `power.ic_rail_without_fitted_capacitor`.
- **Evidence:** The public KiCad-Team-Workflow-Template training project at
  commit `ed89536f0dbbcb013145af2994fef41b2250143e` documents an Arduino status
  LED path through `R1` (1 kΩ) and custom symbol
  `StatusLedTraining:LED_5mm`. Its KiCad 10.0.5 native export shows the
  schematic series path, but LINT-063 emits no candidate because it recognizes only
  `Device:LED`. The overall project report remains `REVIEW` for undeclared
  connector inventory; this is an applicability gap, not a rule pass, fault,
  or false-positive measurement. Detailed source and netlist hashes are
  recorded under LINT-063. No project source was copied into Tooling.
- **Problem:** Some deterministic rules recognize narrow, standard symbol
  identities. A project may use an approved custom library symbol for the same
  reviewed component role, but the current mode/ignore policy cannot extend
  that rule's applicability. Guessing from `D` references, values, or
  footprint text would create unreviewed classifications.
- **Contract:** `design_lint.component_role_map` in the project test contract
  binds one exact `PART_ID`, native symbol ID, footprint, complete two-pin
  number/function/electrical-type inventory, finite role (`led` or
  `capacitor`), and review basis. Capacitor entries require both native pins
  to be passive. Every native component using that `PART_ID` must match the
  binding. An absent part or changed identity/pin inventory blocks lint and is
  excluded from the heuristic. The accepted map is covered by the existing
  source-bound policy digest; a finding includes the binding and its canonical
  SHA-256, so changing its identity or basis changes the finding fingerprint.
  Pin-order changes do not change the digest or finding.
- **Predicate:** The `led` role extends only the documented two-pin
  output-driven LED heuristic. The `capacitor` role is used only by the fitted
  decoupling-presence hint and requires two native passive pins. Both supply a
  reviewed component classification, not an electrical conclusion or net
  requirement. Unlisted custom symbols stay outside these rules regardless
  of reference, value, or footprint text.
- **Boundary:** A role map establishes project classification, not component
  correctness, part approval, pinout accuracy, fit, electrical limits, or
  fabricated connectivity. It does not change a finding's default `review`
  mode. It must be bound into the design-lint policy digest and finding
  evidence. Unknown symbol formats and multi-unit/ambiguous identities remain
  explicitly unsupported.
- **Fixtures and acceptance:** Synthetic custom-symbol direct-output fault and
  series-resistor control; same-value unrelated-symbol and unmapped-custom
  controls; DNP and stale part, symbol, footprint, and pin-inventory cases;
  map/pin ordering stability; identity/basis-bound digest; and CLI/MCP parity.
  The pinned native lane exports both custom schematics twice on KiCad 10.0.0
  and 10.0.5, checks the complete identity and pin data survived XML parsing,
  confirms the unmapped symbol stays quiet, and confirms the mapped fault and
  series control differ as expected. This is applicability gain, not
  independent electrical detection.
- **V1 complete:** The exact source contract, stale-map blocking, review-basis
  evidence, tests, shared-service parity, native exports, and documentation are
  in place. Additional component roles require their own bounded predicates,
  source fields, controls, and applicability evidence; do not enable arbitrary
  rule-role combinations.

### P1 — Netlist and interface-pattern checks

#### LINT-081 — Same-net two-pin diode coverage

- **Status:** Implemented as `component.two_pin_diode_same_net`, a default
  `review` prompt with exact component, symbol, pin, and net evidence. It uses
  the same bounded native-netlist inventory logic as the existing passive
  rule while keeping a separate rule ID and project disposition.
- **Priority:** P1 incremental coverage. LINT-051 already covers fitted
  `Device:R/C/L` families; a source recheck of cohort rule SP-001 exposed the
  uncovered exact `Device:D` family. This is a narrow extension rather than a
  new generic same-net detector.
- **Predicate:** For exact `Device:D` and `Device:D_*` symbol identities,
  require a fitted component record, exactly two distinct native pin numbers,
  and one unambiguous assigned schematic net for each pin. Report only when
  those two net assignments match. `Device:LED`, custom libraries, incomplete
  inventories, multi-pin symbols, ambiguous or open pins, and DNP parts are
  outside the predicate.
- **Boundary:** A same-net diode may be a deliberate bypass or configuration
  choice. The review finding does not infer diode need, polarity, footprint
  pin mapping, or PCB copper continuity. Do not automatically join or split
  nets. A project may use the existing `review`, `block`, `off`, or exact-ignore
  controls after its owner reviews the case.
- **Fixtures:** Synthetic `Device:D` and `Device:D_Schottky` same-net faults;
  distinct-net controls; DNP, incomplete, ambiguous, `Device:LED`, and custom
  symbol exclusions; ordering and per-component net-split mutations; policy
  and exact-ignore lifecycle; and an unrelated fitted resistor mutation that
  changes the typed-netlist digest but preserves both diode fingerprints and a
  scoped D1 ignore. Shared CLI/MCP parity and repeated native exports on the
  pinned KiCad 10.0.0 and 10.0.5 fixture lane remain separate evidence. All
  sources are tooling-owned synthetic schematics.
- **Cohort boundary:** The public kicad-happy changelog motivated the coverage
  review. No candidate package or source was installed or copied. The local
  implementation is first-party and uses only the existing typed netlist
  service.
- **Verification state:** Unit, catalog, determinism, CLI/MCP, and fixture-lane
  wiring checks pass locally. `NativeTwoPinComponentFixtureTests` passed on
  digest-pinned KiCad 10.0.0 and 10.0.5 on 2026-10-07 (one test, ten
  subtests). The same-net diode fault reports REVIEW and its distinct-net
  control passes on both versions. Their source hashes are
  `c7b34973f881f5c8d8e8ac26b07c03dec70b061f66b8338d61fb085583c2aa8b` (fault)
  and `74d19829e8dd9379a26cb6da9dd3cf10a48abce9d724661338f73ce0086bb928`
  (control); normalized typed-netlist hashes are
  `4765e426824bd009258f2ccae3ce118de6b585c3eddebb2437f09287d8cf6929` and
  `6b22eec75df4f715174590f577358d7205a958c1c23b6b09a6bd1875dbb90175`,
  respectively, matching across versions and repeats. This lane exports and
  parses native netlists; it does not run ERC or DRC. No hosted GitHub result is
  recorded.

#### LINT-082 — UART-labeled IC pairs with separate reference nets

- **Status:** Implemented P1 extension to `bus.serial_peer_reference_review`;
  it is in the active rule catalog and defaults to REVIEW. Unit, rule-catalog,
  CLI/MCP parity, and cross-process hash-seed tests pass. The exact KiCad
  10.0.0/10.0.5 native lane passed locally on 2026-10-07. The Antmicro CM4
  Baseboard screen under LINT-031 shows explicit `UART.0.TX/RX` through
  `UART.3.TX/RX` labels on pins whose native functions are generic, so LINT-074
  does not see those direct signal nets.
- **Problem and hypothesis:** A UART-labeled TX/RX pair can directly connect
  two fitted ICs even when neither symbol names its pins TX/RX. If the two
  components also expose explicit reference pins on different schematic nets,
  a review prompt can ask whether the split is intentional. The current direct
  UART-function predicate does not cover that shape.
- **Predicate:** Recognize only numbered UART/USART TX/RX label forms,
  including channel-qualified hierarchical names such as `UART.0.TX`. Require
  one uniquely assigned TX net and one uniquely assigned RX net for the same
  channel; both nets must each connect exactly one pin from the same two fitted
  U/IC components. Require complete native pin number, function, and electrical
  type inventories and exactly one explicit named reference net per component.
  Emit one `REVIEW` when those reference nets differ; remain quiet when they
  match. Suppress only for a current source-matched serial-peer map whose exact
  signal pins, nets, reference pins, and `common_net`, `separate_nets`, or
  `bonded` policy match the observation. A bonded map also requires its exact
  component and side-pin assignments to match the native netlist.
- **Boundary:** This describes a directly connected label-identified signal
  segment; it does not establish that the components are the complete
  end-to-end UART peers or that a split reference is wrong. Keep connector
  endpoints, multi-hop paths, isolators, ambiguous or third-party signal nets,
  DNP components, incomplete pin metadata, and unsupported labels outside v1.
  Do not join nets or traverse an isolator from signal names alone. Project
  requirements and physical continuity remain separate evidence.
- **Verified controls:** A synthetic split-reference
  fault and same-reference control using generic signal pin functions; exact
  `common_net` and `separate_nets` map suppression; exact bonded-reference
  control and broken-bond fault; wrong or stale maps;
  mismatched/missing channel labels; a third connected component; DNP and
  incomplete inventories; shield/chassis reference exclusion; deterministic
  reordering and hash-seed runs; project rule override and exact-ignore lifecycle;
  and CLI/MCP parity pass locally. The `NativeDigitalPeerFixtureTests` lane
  passed on digest-pinned KiCad 10.0.0 and 10.0.5 on 2026-10-07. It exported
  both synthetic label schematics twice per version; the common-reference
  control had no `bus.serial_peer_reference_review` finding, and the split-
  reference fault had that one target finding. Normalized typed-netlist hashes
  matched across repeats and versions: control
  `8e55cec2b7b9ba375881f97934fee182e0c57033aab6796f8052e645a5188654`, fault
  `4b0db5605b6d6a7f9d531e05bb8dba84124a0c35a76242845c29296d3d0786d8`. Source
  hashes are `a0ac8548431af625c5116c1d456e4f2c6cf1714e58cca84c6fe595165d87c561`
  (control) and
  `2006adbfa6c6f1c99e88e3320a1ed7230f01a02f5e143c16a946abaa34f9db20`
  (fault). This serial-label lane exports and parses native netlists; it does
  not run ERC or DRC. The public common-GND sample is a boundary control only;
  it supplies no defect expectation.

#### LINT-083 — Reviewed peer-comparison scopes for connector heuristics

- **Status:** Implemented as optional `peer_assignment_group` and
  `peer_assignment_basis` fields on project-owned connector interface reviews.
  This refines `connector.repeated_pin_function`,
  `connector.peer_pin_assignment_outlier`, and
  `connector.peer_pin_assignment_divergence`; it adds no electrical rule or
  default blocker. Synthetic source-matching tests and CLI/MCP parity coverage
  are in place.
- **Priority:** Precision control for repeated connector symbols used by
  separate interfaces. It reduces cross-interface signal comparisons while
  retaining the higher-value cross-group return and same-domain supply
  prompts. Any next change should address a measured miss or reviewer-cost
  result rather than broaden the predicate.
- **Predicate:** Use group scopes only when every connector participating in a
  comparison has a `COVERED` interface review whose catalog digest, complete
  component-pin inventory, native pin functions, and net assignments still
  match the current normalized native netlist. Partition generic and other
  non-return/supply pin comparisons by the reviewed group. Keep return and
  supply role comparisons cross-group. If any participating scope is absent,
  incomplete, or source-stale, retain the unscoped comparison.
- **Boundary:** A group states which connector instances the generic
  heuristics compare. It does not require common nets or declare nets
  independent. Group review can hide a generic signal mismatch across groups;
  use it only with a reviewed interface inventory and an explicit basis.
  Return and supply review remains active across groups, while explicit
  `pin_connectivity` and `grounding` requirements remain the way to state
  required electrical relationships. The report carries group and basis
  evidence for review.
- **Fixtures:** `test_peer_assignment_groups_scope_generic_pins_but_keep_return_review_global`
  checks that separate groups suppress generic signal comparisons, a shared
  group retains them, split returns remain visible across groups, and partial
  or stale source evidence restores broad comparisons; it also checks that
  same-domain supplies remain comparable across groups. Input-reordering and
  cross-process hash-seed regressions compare complete reports for stable
  ordering. The focused connector, lint, catalog, determinism, CLI/MCP parity,
  and surface suite passed on 2026-10-07: 675 tests and 746 subtests. The
  connector CLI/MCP parity test repeats separate, shared, and incomplete group
  cases through both surfaces. The exact-version connector-return lane now
  includes a synthetic three-port native fault with divergent generic signal
  assignments and split return nets. Separate source-matched groups must
  suppress only generic signal divergence while retaining the cross-group
  return finding; a shared group must report both findings, and the common-net
  control must pass. The lane is wired to the digest-pinned KiCad 10.0.0 and
  10.0.5 package acceptance job. The added typed-netlist regression passed in
  the focused connector/catalog run on 2026-10-07: 485 tests and 643 subtests
  passed; the two exact-version fixture tests were skipped because the native
  lane was not enabled locally because the digest-pinned container runner has
  no reachable Docker daemon. An app-bundled KiCad 10.0.6 CLI was located later
  and used for the public compatibility screen below; it does not substitute
  for the pinned native result.
- **Public sample screen (2026-10-07):** The
  [ARCI-PCB README at the tested commit](https://github.com/stianeklund/ARCI-PCB/blob/1666ea6646917ffcba7aaf7d2845aab62a90fecc/README.md)
  identifies separate UART1/Radio and UART2/Display headers and publishes
  pinout tables for them. A shallow public clone stayed under `/private/tmp`;
  no source was copied into Tooling. The main schematic SHA-256 is
  `6bbc441e3de24442cac3a356d85bc5c948f3e09e60d4ec7b5ba3e992a1695cfc`, and
  `connectors.kicad_sch` is
  `59c8fe5ba3610c1f4aac27f64582b3f2799cd1f2aeb6d5c97bd46ec0d00fce6c`.
  Local KiCad 10.0.6 exported 119 components and 130 nets; the native XML hash
  is `544679f220dd6d906313f41a9a3f41961a48101c450accb3b45564313db4d673`,
  and its normalized typed-netlist hash is
  `f48951028f7bb2dbff428cab3af3095fa3a73e809e58b159f6c826c2c455df16`.
  The exported assignments are J11.1=GND, J11.2=UART1 RX, J11.3=UART1 TX,
  and J13.1=GND, J13.2=UART2 RX, J13.3=UART2 TX. The README tables instead
  list TX on pin 1 and GND on pin 3 for both headers, so the published pinout
  and this native export disagree. The shared typed lint evaluator produced
  49 review candidates, including expected generic signal-pin divergence on
  J11/J13 because those connectors serve distinct UART interfaces, plus
  return-role coverage prompts because no reviewed project role map was
  supplied. The source was made with KiCad 9.0; this KiCad 10.0.6 run is a
  compatibility screen, not the pinned 10.0.0/10.0.5 lane. No project
  contract, ERC/DRC run, or owner disposition was available. Exclude this
  sample from precision and false-positive measurements until its pinout
  discrepancy is resolved; it is not evidence of an electrical defect.

#### LINT-070 — Repeated component power-pin assignment divergence

- **Status:** Implemented v1 as the default-review rule
  `component.peer_power_pin_assignment_divergence`. The predicate is limited
  to fitted non-connector peers with an exact shared symbol, pin number, and
  recognized return or supply role; the project can use the standard rule
  override and fingerprinted-ignore lifecycle.
- **Problem:** Two repeated IC or module symbols can have every pin connected
  while corresponding ground/return or supply pins use different nets. A
  connector-only peer heuristic and the same-component repeated-supply check
  do not cover that pattern. A project-authored connectivity requirement can
  test a known relationship, but this prompt can reveal an unreviewed split.
- **Predicate:** Group fitted non-connector components by exact native symbol.
  For each pin number present on all peers, require a recognized matching
  return function or matching supply category and an unambiguous assignment
  on every peer. Emit a review finding when the exact assigned net sets differ.
  DNP instances, incomplete role metadata, unknown functions, and open pins do
  not enter this comparison; open power pins remain with the more specific
  unconnected component checks.
- **Boundary:** Identical symbol identity and pin number identify a review
  candidate, not a required common domain or interchangeable part. Separate
  analog, digital, chassis, isolated-interface, or voltage rails may be
  intentional. The rule does not merge nets, establish a datasheet requirement,
  test whether ERC would detect a particular case, or prove PCB copper,
  off-board wiring, component conduction, current capacity, or physical
  continuity. Keep the default `review`; use a project-authored contract for
  a required relationship.
- **Fixtures:** Split ground and supply assignments; shared-domain controls;
  different-symbol and DNP controls; an open return handled only by the
  specific component open-pin rule; rule `review`/`block`/`off`, exact-ignore,
  and stale-ignore behavior; input-map reorder stability and commoning clears
  the finding; CLI/MCP parity over synthetic KiCad XML. A source-hashed native
  schematic pair also exercises identical synthetic module symbols with both
  common-domain and split-domain assignments through repeated pinned KiCad
  10.0.0/10.0.5 exports. No board source is used.
- **Done:** Cataloged rule, exact peer pin/net evidence, synthetic
  fault/control and metamorphic regressions, configurable disposition, and
  shared-service CLI/MCP parity are in place. The native export acceptance
  lane passed on the digest-pinned KiCad 10.0.0 and 10.0.5 images. ERC reports
  two `power_pin_not_driven` errors for the common-domain control and four for
  the split-domain fault, so ERC reports a generic power-source problem in
  both cases while the heuristic localizes the differing peer pins. Field
  false-positive rates remain unmeasured.
- **Fixture inputs:** The
  [synthetic native fixtures](../tests/fixtures/design_lint/component-peer-power-native/README.md)
  record source hashes, assignments, and native-lane scope.

#### LINT-051 — Two-pin passive assigned to one schematic net

- **Status:** Implemented v1 as `component.two_pin_passive_same_net`, a
  default-review hint with exact pin/net evidence, project rule overrides, and
  fingerprinted ignores.
- **Problem:** ERC can accept a resistor, capacitor, or inductor whose two pins
  are assigned to the same schematic net. That topology can bypass a series
  element or short a shunt element while every pin remains connected.
- **Predicate:** Recognize exact `Device:R`, `Device:C`, and `Device:L` symbol
  families only when the native netlist contains exactly two distinct pin
  numbers, one unambiguous net per pin, a fitted component state, and the
  component value. Report when both pins resolve to the same net. The rule
  does not infer a required series or shunt function.
- **Boundary:** A same-net part may be a deliberate jumper, measurement
  element, or other reviewed topology. Custom symbols, incomplete or
  multi-pin inventories, DNP parts, unassigned pins, and ambiguous net
  assignments are outside the predicate. The schematic netlist cannot prove
  copper connectivity, physical population, current behavior, or whether the
  symbol-to-footprint pin map is correct. Keep the default at `review`.
- **Fixtures:** Synthetic same-net resistor/capacitor/inductor fault;
  distinct-net control; DNP, custom-symbol, multi-pin, missing-inventory,
  unassigned, and ambiguous-assignment exclusions; review/block/off/exact
  ignore and stale-fingerprint lifecycle; CLI/MCP parity; repeated exports
  through exact digest-pinned KiCad 10.0.0 and 10.0.5.
- **Done:** Unit and shared-surface regressions, catalog and documentation,
  source-hashed synthetic schematic exports, and repeatable typed native
  netlist evidence pass. No customer or proprietary board source is used.
- **Fixture inputs:** The
  [synthetic component README](../tests/fixtures/design_lint/two-pin-components/README.md)
  records the source hashes, fault/control topologies, and native export lane.
- **Pinned native regression (2026-09-29):** The same two source-hashed synthetic schematics were
  each exported twice with exact KiCad 10.0.0
  (`ghcr.io/kicad/kicad:10.0.0@sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3`)
  and KiCad 10.0.5
  (`ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`).
  Both versions reported `REVIEW` for the same-net `R1` and `PASS` for the distinct-net control.
  Normalized native contracts matched across repeats; KiCad 10.0.0 digests were
  `9ced35ed89028d3fed5ec4be2f3694ec8ce6c375182f8a5b6f75faa22659a628` and
  `5ebfcd51987da4a69b89b34a7a7aa81ce0e2ad2d47047d119d40184a2fff5da5`, respectively. KiCad 10.0.5
  produced the same two normalized digests.

#### LINT-052 — Likely SPI participant missing from the authored roster

- **Status:** Implemented v1 as a configurable, default-review prompt using
  source-bound native pin functions, assignments, and the project electrical
  contract's SPI roster.
- **Problem:** LINT-013 checks the exact membership and endpoints a project
  declares, but a connected SPI-like IC omitted from that roster may otherwise
  be absent from the map's findings.
- **Predicate:** For a fitted U/IC reference, require an assigned clock pin
  function (`SCK`/`SCLK`), at least one assigned data function (`MOSI`/`SDI`/
  `COPI` or `MISO`/`SDO`/`CIPO`), and a named select function (`CS`/`CSN`/
  `NCS`/`NSS`/`SS`/`SSEL`/`CE0`/`CE1`). Emit a coverage prompt when no required
  SPI roster exists or the reference is absent from its controller/device/
  bridge list. Evidence binds the recognized pins, assigned nets, and electrical
  contract path and digest.
- **Boundary:** This is a candidate-generation clue, not a determination that a
  part is an SPI peripheral or that it should connect to a particular bus.
  Controllers, bridges, multi-protocol parts, and unused capabilities can
  match. A mapped reference is treated as covered by the prompt while the
  separate LINT-013 contract comparison reports its pin or identity mismatch.
  Only U/IC prefixes and the listed exact function aliases are recognized.
  This does not prove PCB continuity, internal transfer, or firmware setup.
- **Cohort input:** Source inspection of kicad-happy at
  [`a6bba1a`](https://github.com/aklofas/kicad-happy/tree/a6bba1add1e18b89e3aa0824b9769ed1d9d79174)
  found `validate_spi_bus` limited to chip-select pull-up review and
  `detect_sensor_interfaces` returning detected sensor summaries plus peers
  that share one or more extracted bus nets. Neither compares detected
  references with a project-authored SPI roster. The peer list can support
  review, but cannot name an omitted expected participant. No cohort code or
  project source was copied.
- **Fixtures:** Synthetic SPI controller and two-device source-bound netlist;
  absent roster; one mapped plus one unmapped device; complete roster control;
  DNP, non-IC, and partial function controls; review/block/off/exact-ignore
  behavior; source path/hash evidence; catalog reachability. Existing shared
  CLI/MCP service parity remains the invocation path.
- **Validation state:** Six focused regressions distinguish uncovered
  participants from mapped, DNP, non-IC, and partial-function controls. The
  cohort was reviewed by pinned source only; the SPI peer inventory itself was
  not benchmarked for reviewer-effort gain. No external analyzer dependency,
  cohort implementation, proprietary source, or project fixture was added.
- **Exact-version native validation (2026-09-30):** A synthetic two-device
  schematic with `SPI1_SCLK`, `SPI1_COPI`, `SPI1_CIPO`, and `SPI1_NSS` symbol
  pins was exported twice with the digest-pinned KiCad 10.0.0 and 10.0.5
  images. Both versions preserved all eight pin functions and produced the
  same normalized typed-netlist digest. An absent roster produced review
  candidates for the controller and peripheral; the exact authored roster
  control produced no participant findings. KiCad 10.0.5 raw XML differed
  across repeats, while its parsed netlist was stable. This verifies the native
  field boundary and predicate on these synthetic symbols; it does not prove
  the roster's engineering correctness or PCB connectivity. The fixture and
  image digests are recorded in
  [the native SPI fixture README](../tests/fixtures/design_lint/spi-participant-native/README.md).

#### LINT-053 — Likely USB-C connector missing a reviewed port role

- **Status:** Implemented v1 as a default-review coverage prompt using native
  connector pin functions and the project electrical contract's USB-C port
  map.
- **Problem:** LINT-012 validates source, sink, or dual-role CC and VBUS
  requirements after a project records a USB-C port, but assigned or named
  `CC1`/`CC2` pins with no port-role record otherwise produce no role-coverage
  prompt.
- **Predicate:** For a fitted numeric `J`, `P`, `X`, or `CN` reference, require
  exported pin functions for both exact `CC1` and `CC2` names. Prompt when the
  reference is absent from a required electrical `usb_c.ports` list or no
  required USB-C role map is configured. A mapped reference counts as covered
  by this prompt; the separate role contract reports pin, resistor, VBUS, and
  other mismatches. Evidence includes both connector pins, their assigned or
  unassigned native nets, contract path/digest when present, and roster state.
- **Boundary:** Pin names and reference prefixes only identify likely
  candidates. The finding does not infer that the symbol is a USB-C port, its
  source/sink/dual-role behavior, Rp/Rd values, controller configuration,
  protection, VBUS path, grounding requirement, compliance, or physical
  continuity. Unusual function aliases and connector-reference conventions
  can evade the prompt. DNP components are excluded. Default disposition is
  `REVIEW`; project rule overrides and exact fingerprint ignores remain
  available.
- **Cohort input:** The current public
  [kicad-happy project documentation](https://github.com/aklofas/kicad-happy)
  advertises USB-C CC validation, including pull-down and PD-controller cases.
  LINT-053 adopts only the missing-role coverage question and uses the existing
  project USB-C model; it does not import cohort code, assumed values, fixes,
  or severity. A read-only trial of the pinned kicad-happy v2.1.0 analyzer on
  synthetic unknown-role, source, and sink fixtures found no unique coverage
  beyond the local role-map prompt and role-aware contract. Evaluating the
  local rule on the same parsed native contracts prompted for a role-map review
  in all three cases, including the source and sink controls. For an unknown
  role, the candidate reports sink-specific missing-pull-down findings despite
  reporting its inferred role as `unknown`. Trial details and fixture hashes
  are in the
  [synthetic USB-C cohort fixture notes](../tests/fixtures/design_lint/cohort-usb-c-roles/README.md).
- **Fixtures:** Synthetic paired CC1/CC2 candidate with no role map; valid
  56 kΩ source and 5.1 kΩ sink CC topologies that still lack role-map records;
  mapped-port control; DNP, non-connector, and incomplete-function controls;
  contract source binding; review/block/off/exact-ignore lifecycle; CLI/MCP
  parity.
- **Exact-version native validation (2026-09-30):** The digest-pinned KiCad
  10.0.0 and 10.0.5 fixture lane exported the minimal connector, source, and
  sink schematics twice per version and preserved `J1.4=CC1` and `J1.5=CC2`.
  Both versions reported one `REVIEW` finding for each unreviewed role, even
  with valid 56 kΩ source or 5.1 kΩ sink paths; the map-listed `J1` control
  produced no coverage finding. Normalized contracts repeated with SHA-256
  `e6cfd2495852bee1c052a36927473dd1b8b52653fe8a6b16468e7c7b690c65b7` for
  the minimal connector, `f88a8f36c85ce3c84cb44c145ac57639890a99369821c17d40a733907740e613`
  for the source control, and
  `6ab178bc1c36b936f2ff75995d76fcb2e91fc30a3d5e53c81ad9d22efe7531e0` for
  the sink control. Raw XML hashes varied for some repeated exports under
  both native versions, while the normalized typed contracts matched across
  repeats and versions. This
  lane tests netlist export and lint coverage only; it does not run ERC or
  validate a USB-C design. Fixture source identity and boundaries are recorded in
  [the native USB-C fixture README](../tests/fixtures/design_lint/usb-c-port-native/README.md).

#### LINT-010 — I2C pull-up topology and rail review

- **Status:** Partial v6. The direct discrete-resistor heuristic and authored
  electrical requirement support exact signal nets, rails, and inclusive
  nominal resistance ranges. The authored requirement supports explicitly
  ordered, unbranched resistor chains with exact component identity, per-leg
  nominal ranges, two-pin inventories, and source-bound junction checks. The
  review heuristic also recognizes direct resistors and unbranched discrete
  series chains. The electrical contract supports explicitly mapped
  resistor-array channels with exact component identity, full native pin
  disposition, per-channel pin/net assignments, and datasheet-sourced nominal
  resistance. An optional authored rail-to-input voltage comparison now has
  source-bound synthetic coverage. A passing source-bound requirement for the
  exact ordered SDA/SCL net pair resolves the generic missing-pull-up hint
  only when both authored line checks pass, including optional voltage
  compatibility and resistor-window checks. The optional resistor window
  derives a lower bound from authored pull-up voltage, VOL and sink-current
  limits, and an upper bound from authored bus capacitance and rise-time limit
  using the idealized 30%-to-70% RC relation. This covers an otherwise valid
  mapped resistor array the heuristic cannot recognize. An optional
  project-authored maximum per-resistor tolerance and basis applies a
  conservative worst-case bound to the nominal range before comparing it with
  the derived sink-current and rise-time limits. The report retains the
  electrical contract digest, native netlist digest, bus ID, and exact passing
  check IDs used for that resolution.
- **Problem:** The review heuristic recognizes direct conventional resistors
  and unbranched resistor chains but cannot resolve resistor arrays, branched
  networks, or rail-voltage compatibility on its own. Only a matching passing
  authored contract resolves the array hint; missing, pending, not-applicable,
  mismatched, or failing requirements leave it open. The optional voltage
  contract compares only the explicitly mapped endpoints. The heuristic may
  review valid internal, remote, or deliberately different pull-ups.
- **Evidence and check:** The review heuristic sums each recognized unbranched
  series chain and calculates the parallel equivalent of fitted conventional
  R-reference paths to one named positive rail; it flags equivalents below
  1 kΩ. Every resistor and path total must be in the 1 kΩ–100 kΩ band, and
  each intermediate net must contain exactly the two resistor pins. A
  project-owned `i2c_pullups` electrical requirement names each SDA/SCL net,
  required pull-up rail, and inclusive nominal resistance range; it can also
  name ordered series legs, exact component identity, per-leg resistance
  ranges, and array channel pins with explicit reasons for unlisted package
  pins. The electrical lane fails on a missing or mismatched direct, series,
  or mapped-array path, an intermediate series branch, an incomplete array
  pin disposition, an out-of-range equivalent, or a direct pull-up to another
  recognized positive rail. An optional per-line voltage map compares a
  project-authored maximum pull-up rail voltage with exact SDA/SCL input pins,
  their symbol and footprint identities, native pin inventories, net
  assignments, and independently sourced maximum bus-voltage limits. The
  input-scope basis records how the project reviewed completeness; omitted
  endpoints are not auto-discovered. Values and source bases are bound by the
  electrical contract digest.
  Array internals and authored nominal channel resistance still depend on an
  independently reviewed datasheet pin map. Resolving this schematic hint
  does not prove physical board return paths, copper connectivity, fitted
  resistor behavior, or off-board pull-up behavior. Project rule overrides or
  exact ignores continue to control only heuristic disposition. The optional
  resistor window remains nominal-only unless a maximum per-resistor tolerance
  and basis are supplied. The tool does not verify that source or its coverage
  of every resistor element.
- **Boundary:** The voltage comparison does not verify that the rail ceiling
  or datasheet limits are correct. Its `operating` or `absolute_maximum` limit
  kind is recorded but not independently validated. The optional resistor
  window uses project-supplied maximum bus capacitance and rise time and
  minimum sink current; it does not extract capacitance, model nonlinear or
  active pull-ups, verify the authored resistor-tolerance source, model device
  dynamics, or predict measured waveforms. Netlist topology does not establish transient
  compatibility or off-board behavior.
- **Fixtures:** Two direct 4.7 kΩ resistors passing at 2.35 kΩ equivalent;
  parallel 1 kΩ resistors failing the configured range; missing path; wrong
  rail; DNP exclusion; valid two-leg series chain alone and in parallel with a
  direct path; wrong series identity, value, net, pin inventory, or branched
  junction; valid mapped array; wrong array
  identity, pin, or net; unreviewed native array pin; explicit unused-pin
  reason; equal and inverted resistance bounds; voltage-limit equality pass;
  excessive rail voltage, wrong input net, stale symbol/footprint/pin
  inventory, and DNP endpoint faults; missing, pending, mismatched-bus, wrong
  array-symbol, wrong-channel-net, DNP-array, and symmetric-pin-orientation
  heuristic-coverage controls; a self-contained CLI/MCP parity regression for
  a passing mapped-array control and a missing-array fault, including live
  tool-surface registration without the external reference template;
  retained-evidence replay; source-bound resistor-window passes, lower- and
  upper-bound equality, violations on both sides, and an empty calculated
  window; per-resistor tolerance controls for worst-case pass, exact inclusive
  boundaries, lower- and upper-side failures, missing basis, and out-of-range
  percentages; CLI/MCP parity for passing and excessive-capacitance controls.
  Release verification replays authored voltage and resistor-window checks
  against the source-hashed netlist and rejects omission of any result.
- **Native fixture evidence (2026-10-03):** The synthetic mapped-array
  control and pin/net fault export twice through digest-pinned KiCad 10.0.0
  and 10.0.5. Both versions retain the exact array symbol, footprint, value,
  four-pin inventory, and channel assignments. The control passes SDA and SCL;
  moving only RN1.1 from `I2C_SDA` to `SDA_WRONG` fails SDA with that exact
  mismatch while SCL remains passing. Repeated exports produce identical
  normalized typed-netlist hashes per fixture across both versions: control
  `891918a1106ab700a1cc6278ae9f7eb6372a8eb31cdcfb02d51b6a63487c83bd`, fault
  `33c47e5931fdd2066d496be02486557495a99814e9667627f8a4ba4d39f3820c`. Source
  hashes are `922e40c8815a302e8af30e3eb7e4a53b1b3361be419cc0c56fe3025619a7243d`
  (control) and `062648e3ec3d9c71e976fc40370d4d7a1ab4d6064e73d79fe191878ee052efc4`
  (fault); raw XML hashes are retained in ignored hosted-CI receipts. The
  optional lane exports and parses native netlists; it does not run ERC/DRC.
  See the [native fixture notes](../tests/fixtures/design_lint/i2c-array-native/README.md)
  for the reproducible command and image pins.
- **Remaining:** Rail ceiling and pin-voltage limits remain reviewed inputs;
  the checker does not verify cited source documents or whether the authored
  resistor-tolerance bound covers every element. Actual bus capacitance and
  transient behavior remain reviewed inputs. Internal and off-board pull-ups
  remain an explicit not-applicable decision for this local-netlist contract.

#### LINT-011 — CAN termination topology and bus-end declarations

- **Status:** Partial v2. The project-authored electrical contract checks
  required CANH/CANL pin assignments, exact direct and split local resistor
  paths, endpoint references, inclusive nominal ranges, extra direct paths,
  explicitly external/DNP options, and an optional exact split midpoint
  capacitor mapping.
- **Problem:** A direct 120-ohm resistor check does not model two bus ends,
  split termination, switchable termination, or the project's actual topology.
- **Evidence and check:** `can_termination` names the bus nets, logical
  pins and nets, logical endpoints, topology, exact resistor references/net
  paths, nominal ranges, and DNP options. The electrical analysis and
  retained-evidence replay compare these requirements with the source-bound
  native netlist. Direct paths are checked individually; split termination
  requires two legs to the same declared midpoint. A split endpoint may
  optionally map one capacitor by exact component identity, two native pins,
  reference net, and nominal capacitance range. The check requires exactly two
  native pins and validates both net assignments. External endpoints remain
  explicitly unverifiable from schematic evidence and are reported
  `NOT_APPLICABLE`.
- **Native source fixtures:** `tests.test_ci_hosted.NativeCanTerminationFixtureTests`
  exports synthetic control and single-pin fault schematics twice with the
  digest-pinned KiCad 10.0.0 and 10.0.5 images. The typed netlist hashes match
  across versions: control
  `de5d5d2edff5d2f4143bd8a5595734c3ea64f6dfa3844eef626999806fc53c9d`, fault
  `4d0141640743cd0f953fe382941036a396f39b104fe89d9fd1febc43767bacb6`. Moving
  only `C1.2` from `GND` to `GND_ALT` leaves the CAN pin, direct-resistor, and
  split-leg checks passing while the mapped capacitor check fails. Source
  hashes and the run command are in
  [`can-split-midpoint-native`](../tests/fixtures/design_lint/can-split-midpoint-native/README.md).
- **Boundary:** Do not require termination on every node or assume a topology
  from CANH/CANL names. The capacitor map is opt-in and does not prove
  placement, voltage derating, impedance, EMC behavior, physical bus-end
  placement, remote termination, or PCB copper continuity. The source fixture
  lane exports netlists only; it does not run ERC/DRC.
- **Fixtures:** Correct two-end termination; missing or misassigned CAN pin;
  missing endpoint; wrong value; unlisted extra direct resistor; split
  termination and crossed leg; mapped midpoint capacitor with boundary and
  missing/value/identity/net/inventory faults; fitted
  requirement with a DNP part; external endpoint with an expected DNP local
  option; CLI/MCP parity; retained-evidence replay.
- **Remaining:** Extend beyond exact direct/split/DNP topology only when an
  independently reviewed project requirement demonstrates the need.

#### LINT-012 — USB-C role-aware CC and VBUS checks

- **Status:** Partial v1 in the project-authored electrical contract. Source and
  sink ports can declare resistor-based Rp/Rd or controller-managed CC pins;
  dual-role ports require two mapped controller pins. Debug-accessory behavior
  is reported `NOT_RUN` and keeps the lane failing until it is modeled. A port
  may also declare an exact ordered connector-to-board VBUS component/net map.
- **Problem:** A connected CC pin alone does not establish that Rd/Rp,
  orientation handling, VBUS, and power direction match the connector's role.
- **Evidence and check:** The `usb_c` electrical section declares each port's
  role, exact connector CC pins/nets, resistor value ranges or controller pins,
  exact controller/protection symbols and footprints, VBUS pin/net assignments,
  ground pins, and protection applicability. CLI, MCP, and retained-evidence
  replay use the same typed check against a source-bound native netlist.
  An optional `vbus_path` checks declared endpoints and an ordered series chain
  by exact component reference, symbol, footprint, mapped pin inventory, and
  pin-to-net assignments. The path is opt-in and project-authored.
- **Boundary:** Do not infer role from resistor labels or connector names.
  A netlist cannot prove controller configuration, internal Rp/Rd behavior,
  current capability, VBUS power-path continuity through switches/fuses,
  orientation handling, PD negotiation, protection effectiveness, remote
  equipment, or compliance. VBUS checks verify declared pin-to-net assignments
  on each side. The optional chain check confirms the authored schematic map;
  it does not prove conduction through a component, switch state or direction,
  the absence of a parallel bypass, or PCB copper/contact continuity.
  Debug-accessory behavior remains unsupported and deliberately cannot pass.
- **Fixtures:** Resistor-based source and sink, controller-managed dual-role port,
  missing or misassigned CC pin, DNP/out-of-range Rp, wrong controller or
  protection symbol/footprint, wrong protection pin net, wrong VBUS pin net,
  debug-accessory unsupported result, valid fuse/load-switch path, missing or
  unfitted path element, wrong element identity/footprint, disconnected mapped
  pin, discontinuous declared chain, CLI/MCP parity, and retained-evidence
  replay.
- **Remaining:** Static controller configuration-pin relationships can use
  the existing project-authored `pin_connectivity` contract; the native source
  and CLI/MCP fault/control tests already cover exact pin-to-net comparisons.
  A USB-C-specific duplicate is not planned unless an independently reviewed
  controller use case demonstrates a gap in that shared contract. Controller
  registers, firmware, dynamic source/sink behavior, and internal Rp/Rd remain
  unverified. A power-path check would need evidence for component conduction
  and actual PCB copper/contact continuity; the current optional contract only
  checks the authored schematic map.

#### LINT-013 — SPI device and chip-select membership

- **Status:** Implemented as an optional project-authored electrical contract;
  automatic discovery of omitted devices remains a heuristic/review question.
- **Problem:** A connected CS pin can still be missing the expected bus/device
  relationship; names do not show which controller owns a device.
- **Evidence and check:** The `spi` section compares explicit controller,
  device, and optional bridge symbol/footprint identities and signal-pin nets
  to the source-bound native netlist from the existing version-pinned native
  export path (currently the KiCad 10 profile). Every declared controller CS
  net must map to at least one device. Multiple devices on a CS net require
  one shared group. MISO can be connected, intentionally unconnected, or
  absent with a reason. A bridge route requires exact observed net assignments
  at its declared endpoints.
- **Boundary:** An omitted device cannot be discovered deterministically from
  the netlist alone. Bridge endpoint mapping does not prove internal transfer,
  direction, power, or enable behavior. Mode, timing, polarity, firmware, PCB
  copper continuity, and signal integrity remain outside this check.
- **Fixtures:** Synthetic one-controller/two-device map; disconnected and
  wrong-net CS; missing controller CS membership; unauthorized and explicitly
  shared select; write-only and unconnected MISO; buffered MISO; wrong bridge
  endpoint; setup pending state; CLI/MCP parity; retained-evidence replay.
- **Remaining:** Candidate discovery is intentionally limited to exact exported
  pin-function aliases and U/IC references. Broaden it only with synthetic
  fault/control pairs for supported aliases. The pinned kicad-happy detector
  review found no SPI-roster comparison; the local `bus.spi_unmapped_participant`
  prompt now supplies that coverage clue without asserting the device belongs
  on a bus.

#### LINT-014 — UART and serial peer mapping

- **Status:** Implemented as an optional project-authored electrical contract;
  direct logic-voltage margins are checked when reviewed endpoint limits are
  supplied; automatic UART peer discovery remains a review heuristic.
- **Problem:** Similar serial connectors can have TX/RX, ground, or voltage
  pins omitted or mis-mapped while each remaining pin is connected.
- **Evidence and check:** The `serial_peers` contract compares authored UART
  endpoint component identity, TX/RX pin perspective, logic-domain labels,
  reference pins, and direct or level-shifted path endpoints to the exact
  source-bound native netlist from the KiCad 10 profile. Direct links require
  TX-to-RX crossing in both directions and matching logic-domain labels.
  Direct links also require `logic_limits` for both endpoints to pass voltage
  compatibility: guaranteed output-low and output-high ranges must fit the
  receiver's low/high thresholds and absolute input range in both directions.
  Each authored limit records its document basis and operating conditions.
  Missing endpoint limits produce `NOT_CONFIGURED` checks rather than a pass.
  Project policy names a common reference net, a verified bond across distinct
  reference nets, distinct unbonded endpoint nets, no applicable reference, or
  an external reference that is unverified. A bonded map names one exact
  passive two-pin component, value, footprint, and side-pin net assignment;
  the native netlist check also requires it fitted with passive pin types.
- **Boundary:** This is pin/netlist membership, not board copper continuity,
  galvanic-isolation proof, shifter transfer behavior, power/enable behavior,
  or external equipment wiring. Voltage comparison uses project-authored
  datasheet limits; it does not verify those values or sources, their test
  conditions, transients, timing, loading, or actual device behavior. Level-
  shifted and external peers remain outside the direct voltage comparison.
  Domain labels are authored identifiers; they do not contain electrical limits.
  The check covers logic-level UART maps, not RS-232 or RS-485. LINT-072 adds
  a separate review heuristic for bounded TX/RX pin functions and exact
  UART/USART-labeled nets; arbitrary net names still do not establish an
  omitted peer declaration.
- **Fixtures:** Correct crossed link; TX-to-TX/RX-to-RX fault; missing and
  misassigned reference pins; same-domain direct pair; different-domain
  level-shifted pair; wrong bridge endpoint; direct-link high-voltage and
  low-level margin faults; exact-limit equality; missing limits; unknown
  external peer; bonded-reference control and missing, DNP, identity, value,
  pin-type, and wrong-net faults; setup pending state; CLI/MCP parity;
  retained-evidence replay; input-reordering stability. Pinned native fixtures
  are required to verify KiCad export of the mapped bond component.
- **Remaining:** Add board-level path or isolation evidence only if a separate
  source-bound artifact can support a deterministic check. Values and
  datasheet-source truth remain project-owner review responsibilities.
  LINT-072 adds a separate default-review coverage prompt for exact exported
  UART-like TX/RX function pairs missing from this authored peer map. It does
  not infer whether those pairs are intended or whether grounds should be
  common; connector pinout and grounding requirements remain project-authored.

#### LINT-015 — RS-485 termination, bias, and fail-safe topology

- **Status:** Implemented as an optional project-authored electrical
  contract, with no default electrical assumptions.
- **Problem:** Differential pair presence does not establish termination or
  bias arrangements for a declared RS-485 topology.
- **Evidence and check:** The `rs485` section declares two-wire half-duplex or
  four-wire full-duplex topology, exact transceiver/connector symbol and
  footprint identities, line/control/reference pin maps, local direct or split
  termination values and nets, optional DNP termination parts, and one explicit
  local/remote/internal-fail-safe/not-required bias decision per pair. Checks
  use the source-bound KiCad 10 native netlist; retained evidence replays the
  same typed service. CLI and MCP share the service and have a parity test.
- **Boundary:** This verifies schematic pin/net membership, component identity,
  DNP state, and authored nominal ranges. It does not choose universal values
  or verify external peers, cable impedance, physical endpoint placement,
  component ratings/tolerance, device fail-safe features, timing, signal
  integrity, PCB copper, isolation, or remote wiring. External and internal
  behavior is explicitly reported as unverified or `NOT_APPLICABLE`.
- **Fixtures:** Synthetic two-wire and four-wire maps; direct and split
  termination; wrong endpoint line; DNP or miswired termination; local, remote,
  internal-fail-safe, and not-required bias; DNP or miswired bias; declared
  isolated references; unknown peer; wrong symbol identity; pending setup;
  CLI/MCP parity; retained-evidence replay.
- **Remaining:** Add a separate PCB-evidence adapter only if a native,
  source-bound artifact can prove the needed path or geometry. Do not infer
  isolation or omitted peers from the schematic netlist.

#### LINT-016 — Required power-source and load relationship review

- **Status:** Implemented as an optional, project-authored rail membership
  contract; ERC retains electrical-type diagnostics.
- **Problem:** Named supply pins can be connected to a net with no declared
  source, or a source can feed loads on a rail that does not meet project
  expectations.
- **Evidence and check:** `power_connectivity` records each rail net, one or
  more required source groups (`all` or `any` alternatives), and every mapped
  load endpoint. Exact symbol/footprint identity, DNP state, and pin/net
  membership are compared with the source-bound KiCad 10 netlist. When the
  power budget is configured, rail IDs and the complete budget load-ID set
  must match the connectivity map. CLI/MCP parity and retained-evidence replay
  use the same typed service.
- **Boundary:** Endpoint roles and map completeness are project-authored. This
  does not infer omitted devices, electrical pin types, current direction,
  physical source/load existence, voltage/current capacity, sequencing,
  protection behavior, or copper continuity. ERC remains authoritative for
  its electrical-type diagnostics; the source/load map does not re-label ERC
  as independent detection.
- **Fixtures:** Synthetic external-input connector alternatives; regulator and
  monitor load endpoints; wrong source net; wrong load net; DNP required source;
  wrong source identity; one-of alternatives with one valid and no valid source;
  power-budget rail/load coverage mismatch; setup pending; CLI/MCP parity;
  retained-evidence replay.
- **Remaining:** Add pin electrical-type context only if it demonstrates a
  specific gap beyond native ERC and retains current-version source evidence.
  Keep source direction, switches, reverse-protection paths, and physical power
  behavior out of the v1 claim.

#### LINT-017 — Reset, enable, and boot-strap bias review

- **Status:** Implemented as an optional project-authored control-signal
  contract. Two configurable review-only candidate rules also report unassigned
  control inputs and connected control nets without a directly visible resistor
  to a recognized positive or return net.
- **Problem:** Reset/enable/boot pins may be wired but left without the
  intended bias, driven by multiple outputs, or tied to the wrong domain.
- **Evidence and check:** `control_inputs` declares each signal net, exact
  controlled-input and interface pins, expected KiCad pin electrical types,
  approved driver set/policy, and either exact local resistor paths with
  inclusive nominal ranges or an explicit internal, external, or not-required
  bias decision. The source-bound KiCad 10 netlist checks component identity,
  pin/net membership, pin electrical type, DNP state, resistor value, and
  unlisted output-capable symbol pins connected to each declared control net.
  CLI, MCP, and retained-evidence replay use the same typed service.
- **Connected-input prompt:** `control.connected_control_input_without_visible_bias`
  groups recognized, connected reset/enable/boot input pins by their unique
  assigned net. It reports one REVIEW candidate per net when no fitted,
  conventional two-terminal resistor is directly assigned between that net
  and a recognized positive or return net. Native output-capable peers are
  included in the evidence for review; they do not suppress the candidate
  because their runtime state is not known. A directly visible resistor in
  either polarity clears the prompt. The existing per-rule `review`, `block`,
  `off`, and exact-ignore controls apply. An exact project control-input
  requirement can resolve a candidate when it covers every detected input on
  that net, its endpoint and driver checks pass, and its local-bias check passes
  or it explicitly records an internal, external, or not-required decision.
  The lint report records the contract path and digest plus each covered or open
  candidate. A failed contract check leaves the heuristic prompt open.
  The bounded reset alias set includes the `POR` token because the official
  KiCad `MCU_Module:CHIP-PRO` symbol names an input `POR_B`; `PORN` remains a
  negative control rather than a substring match.
- **Unconnected-pin input:** KiCad's native XML uses synthetic names such as
  `unconnected-(J1-SHIELD-Pad3)` for pins without net assignments. The native
  adapter now retains those pin references in `NetlistContract.unconnected_nets`
  while excluding the synthetic entries from `nets`. This allows explicit
  `unconnected` requirements and review heuristics to distinguish a true open
  from a separately named electrical net.
- **Boundary:** No universal reset polarity, strap value, or boot state. Do not
  infer requirements from `RESET`, `EN`, `BOOT`, or active-low naming alone.
  KiCad pin types describe library metadata, not firmware runtime direction.
  Internal bias, remote hosts, actual drive behavior, resistor tolerance/rating,
  PCB copper, and physical test access remain unverified. Unlisted
  bidirectional or output-capable pin metadata is a contract-review mismatch,
  not proof of electrical contention. The connected-input prompt does not
  trace resistor chains or arrays, infer custom rail names, validate resistor
  adequacy, or prove a visible schematic path reaches the physical input.
  An authored internal or external decision records intent and does not verify
  firmware behavior, the remote host, or physical bias implementation.
- **Fixtures:** Correct pull-up/down; missing resistor; DNP option; wrong rail
  and value; expected shared open-drain drivers; changed native pin type;
  missing type metadata; unlisted push-pull output; explicit internal,
  external, and not-required bias; unassigned reset/enable/boot inputs; valid
  connected and unrelated passive-function controls; the `POR_B` input fault
  and `PORN` nonmatch control; DNP component exclusion; CLI/MCP parity;
  retained-evidence replay.
- **Public sample check:** At KiCAD-Test commit
  `ed89536f0dbbcb013145af2994fef41b2250143e`, read-only netlist exports from
  `arduino-uno-status-led` and `raspberry-pi-status-led` used the pinned KiCad
  10.0.5 image; `controller` used its pinned KiCad 10.0.0 image. They contained
  3, 3, and 2 components respectively, no `input`/`input_low` pin types, and
  no findings. These are negative controls for pins outside the predicate;
  they cannot estimate false positives among recognized control inputs.
- **Pinned native-demo screen (2026-09-29):**
  Three schematics bundled in `ghcr.io/kicad/kicad:10.0.5` were exported
  with exact KiCad 10.0.5 on `linux/amd64`, then parsed through the local
  `read_netlist` adapter. Exact image digest:
  `fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`.
  Inputs: `video/video.kicad_sch`,
  `royalblue54L_feather/RoyalBlue54L-Feather.kicad_sch`, and
  `tiny_tapeout/tinytapeout-demo.kicad_sch`. Across the three exports, the
  heuristic recognized five connected reset/enable pins whose native type is
  `input`: `U11.139 RST#`, `U10.87 RESET`, `U1.G2 ~{RESET}`, `J4.A12 RST`, and
  `U3.3 EN`. It produced zero unconnected-control findings. It also correctly
  excluded `BUS1.A15 RST#` (`output`) and `J8.3 ~{RESET}` (`open_collector`).
  No boot-input alias occurred in these examples. Component counts were 189,
  71, and 150; pin-function counts were 1,784, 243, and 360 respectively.
  The canonical sorted path/SHA-256 manifests for all schematics beneath each
  demo directory hash to `edc6818712f2e40cc049cf8f87961820dccc0782f7d2fa59a1001250979ba1e8`
  (`video`), `48614e87c84fc96e1874c933893a612c71d29b32ca0ed267b6bb2ebe16090092`
  (`royalblue54L_feather`), and
  `29f6620df627ea2db0e9eeda314a5b185b9d361830ab2551a5f122c1c3d27e97`
  (`tiny_tapeout`). Exported netlist SHA-256 values were
  `a8f816d96c592f6d167cbb819117835931dc4823ac35095a95ebc2ae6f827a47`
  (`video`),
  `9e3ee51f1594f61534b3a07cb01742c07d23a7fcc30a87787cf7e2f280880f30`
  (`royalblue54L_feather`), and
  `a31facf732dbb3cb5fa27b46782e33759ec68a198689075149e698b21c81f029`
  (`tiny_tapeout`). Demo schematics stayed inside the digest-pinned public
  KiCad image; their temporary netlist exports and receipts were retained
  under ignored `build/`. The optional test harness copies the public KiCad-Test
  template into an ignored temporary `build/ci` root to select its pinned
  project toolchain. No proprietary or adopter source is used. This validates the
  existing reset/enable aliases and native pin-type filter on these connected
  examples. It does not measure false positives for intentionally unconnected
  control inputs or exercise a boot input.
- **Earlier sample limitation:** The connected examples above alone could not
  exercise unconnected controls or boot/strap aliases. Do not infer required
  polarity, bias, or driver relationships from a pin name.
- **Pinned native unconnected-control regression (2026-09-29):** The opt-in
  `KICAD_RUN_NATIVE_CONTROL_INPUT_FIXTURES=1` lane exports four public demos bundled in
  `ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`
  using exact KiCad 10.0.5 on `linux/amd64`. The container is read-only, has no network, mounts only
  an output directory, and does not copy source into this repository. Per-demo source-file and full
  schematic-directory manifest hashes, raw XML hashes, parsed-contract hashes, and command receipts
  are retained under ignored `build/ci-hosted/native-control-input-demos/`.

  | Public demo source (within `/usr/share/kicad/demos`)                                   | Source file SHA-256                                                | Schematic manifest SHA-256                                         | Review candidates                                                                          |
  | -------------------------------------------------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------ |
  | CM5 Minima: `cm5_minima/CM5_MINIMA_3.kicad_sch`                                        | `b40a486994138c07a45d20e08e6f42405e4b99a88e82a3d55f23704ca9ddc0e7` | `e0c16749ea62d80ca72188261328838d89def9d2529de6880e8e5e127f75a308` | none                                                                                       |
  | Jetson AGX Thor: `jetson-agx-thor-baseboard/jetson-agx-thor-baseboard.kicad_sch`       | `bd943f5c309046e09a1c99e443e1ce23a0c922291371ca60839412694351340b` | `165e4faafce4fab5e52f6b5fd3bf4b87e762dba77869c0c378f944c29309f364` | `J14.23 SDIO_~{RESET}` (reset/input)                                                       |
  | ColdFire/Xilinx: `kit-dev-coldfire-xilinx_5213/kit-dev-coldfire-xilinx_5213.kicad_sch` | `a1109092165ecec0d677142294330258c8990247e804f260d7682fda82602214` | `e1457386ac9585a4283d81f033b0f26a73b1476ed1b613ceab0d91e04efca280` | `VR201.4 SHDN` (enable/input)                                                              |
  | VME-WREN: `vme-wren/vme-wren.kicad_sch`                                                | `4cc3e74f2e47304bd3b360b18bab55d378573bc491b4f210aebe533890aa3dcb` | `aa2f6462f5f9d5c992651b98a79c9034f53c5852f0a131b45a751633be332c8a` | `IC19.3`, `IC21.3 ~{RESET}` (reset/input); `IC30.33 BOOT_B`, `IC30.38 BOOT_A` (boot/input) |

  All four results matched an exact candidate inventory on two exports. Parsed typed-netlist SHA-256
  values were `944f163ca7310f0202a415622088ebbe76d04e55142adc9316c1b24a80629854` (CM5),
  `3f38ebb7e494d63e8980133e1cba7a9c9f6aef34169b934ab67a32e58c69e1c6` (Jetson),
  `2f583eeb67a307249a7c2fd9fd90742b9c4eeeb93aba43e34478098006cc50e4` (ColdFire), and
  `e5ae2120d566f0e98c541dfaa82cc36324cbaeec8f71ca7f4d3c2edc0c67ecbe` (VME). Raw XML hashes are
  retained in lane events because repeated native exports can differ in non-semantic bytes. These
  examples demonstrate native sentinel parsing and bounded alias recognition; they do not establish
  that any candidate must be connected or measure false positives among deliberate no-connect
  control inputs.
- **Pinned native connected-bias screen (2026-09-30):** The same digest-pinned KiCad 10.0.5 image
  and four public demo netlists also exercised the new connected-input prompt. Repeated exports
  produced identical candidate inventories. Source-file and schematic-manifest hashes, raw XML
  hashes, and parsed-netlist hashes are listed above and retained in ignored
  `build/ci-hosted/native-control-input-demos/` receipts. The exact candidate summary hashes are
  asserted by the optional native test.

  | Public demo     | Net-level connected-input prompts | Candidate summary SHA-256                                          |
  | --------------- | --------------------------------: | ------------------------------------------------------------------ |
  | CM5 Minima      |                                 4 | `7c96b511e8fa95eef6dc8fff36c45e92c34e1cfbcc54db7400a2e3149fdd9709` |
  | Jetson AGX Thor |                                24 | `04bd60403bf87f8a4edf249d582a5b7620974dd333b53e5e80c6db9af8dc9f71` |
  | ColdFire/Xilinx |                                 2 | `371dfc8d9313aabf215947750e2ad170d9c5b69f6f03a171ae90e81a73bfb929` |
  | VME-WREN        |                                12 | `2ee541b32622143b5293f6add4da0d0c6b32137ec15521fd2bafb6fe9e3df050` |

  The 42 findings are net-level review prompts, not confirmed defects or a precision estimate. Some
  designs may rely on internal bias, resistor arrays, a connected driver, or other reviewed
  circuitry that the direct-resistor predicate does not resolve. This screen measures candidate
  volume and repeatability only.
- **Pinned native revalidation (2026-10-03):** The
  `NativeControlInputDemoTests` lane passed locally with one test and five
  subtests. It used exact KiCad 10.0.5 from the digest-pinned image recorded in
  the [synthetic alias fixture notes](../tests/fixtures/design_lint/control-input-alias/README.md).
  The `POR_B`/`PORN` source exported twice with the same normalized typed-netlist
  digest; exact pin functions and `input` types were preserved, both pins were
  unassigned, and only `U1.1 POR_B` became a reset candidate. Four public demos
  also reproduced their source hashes, parsed-netlist hashes, candidate
  inventories, and connected-bias summaries. Receipts are under ignored
  `build/ci/` paths. The lane exports netlists only; it does not run ERC/DRC.
- **Remaining:** The native results validate evidence parsing and bounded
  aliases, not design intent. Public demo screens do not label intent, and
  connected-bias candidate volume is not a false-positive measurement.
  Independently reviewed connected-bias and intentional-NC cases remain open;
  collect dispositions before estimating precision or widening the alias set.

#### LINT-018 — Test-point and programming-access coverage

- **Status:** Implemented v4. The schematic, PCB pad-surface, and optional
  probe envelope checks are reported separately. Each endpoint can require
  front, back, or either exposed board side. Envelope values are project-
  authored and use deterministic KiCad 10 pad geometry.
- **Problem:** Required rails, programming signals, or factory measurement
  nodes may lack an accessible, project-approved test point.
- **Evidence and check:** `test_access` declares each in-scope net as either
  requiring one or more exact test-point/programming/factory connector pins,
  or explicitly not requiring access with a review reason. Its separate
  schematic stage checks component identity, DNP state, native pin inventory,
  electrical type, and exact net assignment. The optional, independently
  required PCB stage checks the exact placed footprint/pad, expected net, and
  outer copper plus the corresponding solder-mask layer declaration on the
  project-selected approach side. An optional circular probe envelope measures
  from that pad center to the nearest fitted, mask-layer-assigned different-net
  pad on each requested side. Native KiCad evidence also measures the target
  aperture for circular, undrilled pads from the pad size and its resolved
  solder-mask expansion. The target aperture must fit the project-authored tip
  diameter plus twice its edge clearance; foreign-pad clearance must fit the
  authored tip radius plus edge clearance. Requirements
  round upward to a whole nanometer; measured distances round down to avoid an
  optimistic floating-point boundary result. For a circular pad, the native
  probe uses its layer-specific copper size plus KiCad's resolved
  `PAD.GetSolderMaskExpansion` value in the [KiCad 10 PAD API][kicad10-pad].
- **Boundary:** The envelope scan skips DNP and same-net pads. Only circular,
  undrilled target apertures have a deterministic fit measurement; other
  shapes and drilled pads remain unproven and fail the configured requirement.
  The check does not inspect exposed tracks, vias, copper-zone mask openings,
  component bodies, fixtures, covers, mechanical reach, or manufacturing test
  coverage. A pass is limited to the measured target aperture and pad-neighbor
  geometry on the exact source board.
- **Regression evidence:** Unit controls cover front/back/either side selection,
  exact and one-nanometer-inside threshold boundaries, and missing/partial
  observations. An end-to-end synthetic receipt test covers request tampering,
  retained replay, aperture and clearance boundary faults, unsupported-shape
  handling, and CLI/MCP parity. The digest-pinned native fixture lane exercises
  a packaged synthetic PCB through KiCad 10.0.0 or 10.0.5, asserting exact
  front/back obstacle identity and distance, circular mask aperture bounds,
  same-net/DNP exclusion, unconnected-pad reporting, unavailable-side handling,
  undersize and exact-boundary aperture controls, unsupported rectangular and
  drilled target pads, expected rule results, and repeatability across
  identical loads.
- **Done when:** The KiCad 10 schematic and PCB stages are independently
  reported, exact endpoint mapping is source-bound, all fixtures pass, and
  configured probe-envelope rules have reviewable, replayable geometry. The
  supported board-object scope and native API behavior are exercised on
  synthetic fixtures.
- **Future scope:** Evaluate oval, rectangular, and custom pad aperture fit
  only when native geometry supports a conservative exact measurement. Tracks,
  vias, zone openings, and mechanical obstruction remain separate bounded
  checks; do not infer overall physical accessibility from pad spacing.

#### LINT-084 — Fitted two-pin fuse bypassed by one net

- **Status:** Implemented as `component.two_pin_fuse_same_net`, a configurable
  default-review hint with exact component, symbol, pin, and net evidence.
  It extends the shared two-pin inventory reader without changing the
  resistor/capacitor/inductor or diode rule dispositions.
- **Priority:** P1 power-path regression coverage. LINT-056 already recognizes
  exact `Device:Fuse` and `Device:Polyfuse` symbols as possible series path
  elements. A source review found that the same-net detector used for passives
  and diodes did not inspect those protection parts; a fuse assigned to one
  net can be bypassed without violating schematic netlist syntax.
- **Predicate:** For fitted exact `Device:Fuse` and `Device:Polyfuse` family
  symbols, require exactly two distinct native pin numbers and one unambiguous
  assigned net per pin. Report when those two pins use the same net. DNP parts,
  custom libraries, incomplete or multi-pin inventories, open pins, and
  ambiguous assignments are outside the predicate.
- **Boundary:** A bypassed fuse may be a deliberate configuration or assembly
  choice. The finding does not infer that every fuse must be in series, assess
  fuse current or interruption ratings, or prove footprint and PCB copper
  behavior. Keep the default at `review`; use project policy for any stronger
  disposition.
- **Fixtures:** Same-net and distinct-net native schematic cases for both fuse
  families; DNP, incomplete, ambiguous, multi-pin, and custom-symbol unit
  controls; review/block/off/exact-ignore lifecycle; per-component split and
  order-stability metamorphic tests; CLI/MCP parity; repeated source-bound
  exports on pinned KiCad 10.0.0 and 10.0.5. The synthetic sources and
  reproduction record are in the
  [two-pin fuse fixture README](../tests/fixtures/design_lint/two-pin-fuses/README.md).
- **Local evidence (2026-10-07):** The focused fuse/catalog/CLI-MCP/determinism
  command passed 480 tests and 646 subtests; surface and script-architecture
  checks passed 25 tests and 308 subtests. The new report stayed identical
  across three independent Python hash secrets. These results validate the
  shared typed service and adapters, not native source export.
- **Supplemental native screen (2026-10-08):** The RC3 and RC4 command receipts
  show the pinned KiCad 10.0.0 and 10.0.5 lanes stopping at
  `two-pin-crystals/distinct-nets-crystal.kicad_sch`, before any fuse fixture is
  reached. The crystal control had `page` outside the root `path` in its
  `sheet_instances` form. The source now uses the same nested form as its fault
  control and other accepted fixtures; its reviewed source hash is updated in
  the crystal README and test manifests. Local KiCad 10.0.6 exported the fixed
  control twice with the same normalized typed-netlist digest
  `b489d9e0960c31e0b98aa9da98627e2762a1b97cd5f136291672a83324b2f3c9`; it
  produces no same-net crystal candidate and the lint report passes. The RC5
  GitHub package lane then passed the crystal, fuse, and polyfuse native
  fault/control exports on pinned KiCad 10.0.0 and 10.0.5, including repeated
  normalized-netlist checks.
  Local KiCad 10.0.6 also exported all four fuse sources twice with identical
  normalized typed-netlist digests:
  - Fuse fault: `368263f15c0627efc7a5f4b58a0b0beddda1dbe4b2d72522d6f24562a98a2a14`
  - Fuse control: `e2172e8968c16de62855b6ef43ac4b5dd891ef753436133c864932b3e97ec72c`
  - Polyfuse fault: `ff8e60df2a6775da8467b094f760a6b52371c809c4c6ce6d7499b9773a4932ca`
  - Polyfuse control: `3cc9839cf451122932c229975be7fad33c7575d8cfa15f07f02823c975146061`
  The fault cases each produce one REVIEW finding; both controls pass. RC5 also
  passed the native geometry checks on KiCad 10.0.5 and 10.0.6. Its package job
  completed all 2,238 tests (2 skipped) and then failed only at Ruff formatting
  in `tests/test_serial_peer_reference_review.py`; RC6 carries that formatting
  correction for a full candidate rerun.
- **Release-candidate regression (2026-10-08):** The `v0.5.0rc1` package job
  ran 2,236 tests (2 failures, 3 errors, 2 skipped). The connector fixture
  expected one lint rule ID even though LINT-089 emits one finding per open
  pin; the assertion now checks both per-pin findings. `v0.5.0rc2` passed all
  three portability preview jobs; its package job ran 2,236 tests and had only
  the two pinned native fuse-fixture errors remaining. `v0.5.0rc3` also passed
  all three preview jobs; its package job had the two native fixture errors.
  RC3 and RC4 command receipts stop at the malformed distinct-net crystal
  control before reaching the fuse cases. RC4 ran 2,238 tests with two errors
  and two skips; RC5 carries the corrected crystal source structure. RC5 ran
  2,238 tests successfully (2 skipped), passed pinned KiCad 10.0.0/10.0.5
  native fault/control exports plus the 10.0.5/10.0.6 geometry checks, and then
  failed at the repository Ruff formatting gate. RC6 contains the formatter's
  correction and must pass its full package workflow before this candidate is
  considered green.
- **Local package smoke (2026-10-08):** After the fixture correction,
  `scripts/ci.py` passed all 2,236 tests with 25 environment skips, formatting,
  Ruff, Linux and Windows type checks, Markdown, repository links, wheel/sdist
  reproducibility, a fresh installed-wheel check, and external inventory,
  verify, adaptation, and playtest stages against a separate public template
  checkout. The sandboxed package run could not access the Docker socket; the
  exact KiCad 10.0.0/10.0.5 matrix was subsequently exercised by the RC5
  GitHub package lane and rerun locally with Docker access on 2026-10-08 below.
- **Acceptance-lane integrity (2026-10-07):** The shared native-fixture
  manifest mounts `tests/fixtures/design_lint` as its read-only root so both
  `two-pin-components/` and `two-pin-fuses/` sources resolve. An always-run
  test checks each registered source path before the optional Docker lane.
  The 10.0.6 screen at that time covered the original eight passive, diode,
  fuse, and polyfuse fault/control sources; the revised fuse sources are
  covered by the 2026-10-08 screen above. Those local screens did not replace
  pinned acceptance; the RC5 GitHub run recorded above supplies that evidence.
- **Exact-version local rerun (2026-10-08):** The current synthetic native lane
  passed on digest-pinned KiCad 10.0.0 and 10.0.5: 1 test and 30 subtests.
  Both same-net fuse and polyfuse cases reported `REVIEW`; their distinct-net
  controls passed. Every export repeated with the expected normalized
  netlist. The corrected crystal fault/control, ferrite fault/control, and
  switch fault/control also passed in the same lane.
- **Remaining:** The current dirty branch still needs hosted package acceptance
  before release. RC5's earlier native lane passed, but its package job stopped
  at Ruff; RC6 must pass the complete package workflow.

#### LINT-085 — Fitted two-pin ferrite bead bypassed by one net

- **Status:** Implemented as `component.two_pin_ferrite_same_net`, a
  configurable default-review hint using the shared exact two-pin inventory.
- **Priority:** P1 power and filter-path regression coverage. Cohort path
  checks treat ferrite beads as series elements, while the local default
  same-net rules previously covered resistors/capacitors/inductors, diodes,
  and fuses. A schematic can assign both pins of a fitted ferrite to the same
  net without native ERC identifying that the bead is bypassed.
- **Predicate:** For fitted exact `Device:FerriteBead` and
  `Device:FerriteBead_Small` symbols, require exactly two distinct native pin
  numbers and one unambiguous assigned net per pin. Report only when both pins
  use the same net. Other symbol variants, DNP parts, custom symbols,
  incomplete or multi-pin inventories, open pins, and ambiguous assignments
  are outside the predicate.
- **Boundary:** A same-net bead may be an intentional bypass or assembly
  option. The finding does not infer that a bead is required, assess its
  impedance or filtering performance, or prove footprint or PCB-copper
  behavior. Keep the default at `review`; use project policy for any stronger
  disposition.
- **Fixtures:** Synthetic same-net and distinct-net schematics with the exact
  `Device:FerriteBead` identity and typed coverage of `Device:FerriteBead_Small`;
  typed controls for DNP, incomplete, ambiguous,
  multi-pin, unassigned, and custom-symbol cases; review/block/off/exact-ignore
  lifecycle; per-component split and order-stability metamorphic tests;
  CLI/MCP parity; and repeated native exports on the pinned KiCad 10.0.0 and
  10.0.5 acceptance images. The synthetic source and reproduction record are
  in the [two-pin ferrite fixture README](../tests/fixtures/design_lint/two-pin-ferrites/README.md).
- **Local evidence (2026-10-07):** The focused ferrite/catalog/determinism/
  parity/manifest suite passed 516 tests and 661 subtests. Three independent
  Python hash-seed processes emitted identical full reports for same-net fault
  and distinct-net control cases. The locally installed KiCad 10.0.6 CLI
  exported both synthetic source fixtures twice; their normalized netlists
  repeated identically. The fault reports one `component.two_pin_ferrite_same_net`
  review and the distinct-net control reports none. Source hashes are
  `8ede05ea1d9c8afb0cec2f1c8c9bddf527eab015ab779097f4ddc528866751f7` (fault)
  and `199c802ca290b1281622c623f4966b159144f0e95fd99ed0e21a14a0875734a7`
  (control); normalized typed-netlist hashes are
  `cd1fc58eaf995a64f996aa43b8267cd955f7dc5b51bbae98da68d44fca28e415` and
  `01114175c5d792671ffc261fa3f919eeaa18bc892ad6e92478c5c06221c5cecc`.
  KiCad 10.0.6 ERC also returned zero diagnostics for both sources, so ERC did
  not distinguish this topology fault from its valid control. These results
  validate the typed rule, adapters, and 10.0.6 compatibility, not a real
  ferrite part or filter performance.
- **Exact-version local rerun (2026-10-08):** The current native lane passed on
  both digest-pinned images. The same-net fault reported one
  `component.two_pin_ferrite_same_net` review and the distinct-net control
  reported none. Repeated normalized netlists matched.
- **Remaining:** The exact-version native lane is enabled in GitHub CI, but the
  current dirty branch has no hosted package result.
- **Cohort boundary:** This is a first-party deterministic extension prompted
  by the inspected series-path concept. No third-party source, board, fixture,
  or install workflow was copied.

#### LINT-086 — USB peers use different explicit reference nets

- **Status:** Implemented as `bus.usb_peer_reference_review`, a configurable
  default-review hint. The exact USB data-path map can record a reviewed
  `common_net`, `separate_nets`, or `bonded` reference decision and verify its
  named pins and nets against the native netlist. A `bonded` entry additionally
  maps one exact passive two-pin component, value, footprint, and side nets.
- **Priority:** P1 connectivity review. LINT-074/LINT-082 cover UART peers,
  and LINT-049 covers a project-mapped USB data topology; neither notices a
  supported USB 2.0 connector-to-IC pair when its connector and PHY reference
  pins use separate explicit nets and no reference policy has been authored.
- **Predicate:** For fitted connector-to-U/IC pairs, recognize one or more
  supported USB 2.0 D+ and D− pins at each endpoint, with all pins on one side
  assigned to that side's native net. Each line may be direct or cross exactly
  one fitted, complete two-pin `Device:R` between the connector-side and PHY-side
  nets. The function aliases include direct names such as D+/D− and numbered
  hub pairs DPn/DMn or USBnD+/USBnD-, which are grouped by matching numeric
  port number. One
  unnumbered endpoint can pair with a numbered endpoint when the exact nets
  identify one path; two numbered endpoints must use the same group. Each
  endpoint's explicit reference pins
  must use one unambiguous native net; differing nets produce a review. Each
  complete fitted two-pin passive D-designated branch may connect a data net to
  an endpoint reference. Findings retain data functions, contact pins, resistor
  assignments, accepted branch pins and partner nets, endpoint identities, and
  reference functions/types.
- **Boundary:** Separate nets may be intentional, joined through a reviewed
  bond, or intentionally isolated. This rule asks for review; it does not say
  grounds must be tied. It does not infer unlisted or multi-hop bond paths,
  multiple series components,
  arbitrary extra peers, multi-pin protection arrays, USB 3.x paths, off-board
  wiring, or PCB copper. It does not infer resistor suitability or protection
  performance. A `data_port_group` in an exact USB map scopes same-side PHY
  inventory to one numbered pair. Incomplete pin inventories, mixed reference
  domains, DNP endpoints or branch parts, shield/chassis/frame/PE functions,
  and ambiguous assignments are skipped. A source-reviewed USB map suppresses
  the prompt only when connector and PHY identities, direct or one-resistor
  data topology, complete reference pin inventories, and explicit reference
  decision all match. For `bonded`, `bus.usb_data_path_mismatch` separately
  reports a missing, DNP, identity-mismatched, or incorrectly assigned bond;
  this netlist comparison does not prove component conduction or PCB copper.
- **Fixtures:** Synthetic split-reference fault and common-reference control;
  two connectors to one numbered hub with per-port evidence, a shared-
  reference control, a crossed-channel control, an unused-port control, and
  exact `data_port_group` maps;
  USB-C duplicated A/B data contacts with two-pin shunt branches and common/split
  reference controls; exact USB-map contact coverage; arbitrary-peer,
  unsupported-branch, split-duplicate-pin, multi-reference-PHY, and isolator-path
  controls;
  stale identity/net faults; exact ignore, review/block/off, input reordering
  and commoning mutation; CLI/MCP parity; repeated source-hashed native
  exports on the digest-pinned KiCad 10.0.0 and 10.0.5 lane. The typed-netlist
  multi-reference control gives one PHY two explicitly named return pins on
  separate nets and confirms the bounded predicate skips it.
  The two-port hub source-to-netlist cases are documented in the
  [multiport USB fixture README](../tests/fixtures/design_lint/usb-multiport-peer-reference-native/README.md).
  The exact-map extension adds a valid 0R bond control and faults for an absent
  bond, wrong value, symbol, footprint, DNP state, active pin type, and wrong
  side net. CLI and MCP return identical fault evidence. A source-hashed
  native 0R control is registered in the same KiCad 10.0.0/10.0.5 fixture lane;
  it has not run on this host because `kicad-cli` and the Docker daemon are
  unavailable, so pinned native-export evidence remains pending.
- **Evidence status:** The predicate, tests, and native fixture sources are in
  this branch. The pinned native lane is wired into the existing USB export
  job but has not run on this host because the Docker daemon is unavailable;
  no GitHub result has been recorded for this dirty branch. Before the series-path
  extension, the full Python suite passed on 2026-10-07 with the public
  `KiCAD-Test` reference checkout pinned
  at `ed89536f0dbbcb013145af2994fef41b2250143e`: 2,139 tests passed, 49
  environment-gated tests skipped, and 2,368 subtests passed. This includes
  the typed fault/control, catalog-registration, and CLI/MCP parity cases; it
  does not count as native export evidence. After the extension, the focused
  USB peer/data-path suites pass 23 tests and 5 subtests; the grouped lint and
  catalog suite passes 632 tests and 751 subtests. The hosted test module passes
  22 tests and 26 subtests, with its 21 environment-gated cases skipped. A local
  KiCad 10.0.6 export on
  2026-10-07 exposed that the earlier synthetic USB-A fault/control fixture
  ground labels missed their pin endpoints; the fixture sources were corrected
  and now export the intended split and common assignments. Repeated local
  10.0.6 exports of the corrected USB-A and new USB-C cases produced stable
  typed netlist contracts and the expected fault/control results. This is
  compatibility evidence only. At the time these local exports were recorded,
  the exact hosted 10.0.0/10.0.5 lane was pending; its later acceptance is
  recorded below. All fixture sources contain only synthetic
  connector, PHY, resistor, diode-designated branch, and net labels. A
  repeatable local KiCad 10.0.6 export of the series-resistor common-reference
  control and split-reference fault checks the expected GND assignments, one
  review on the split case, and exact R1/R2 pin-to-net evidence. Repeated raw
  netlist hashes are `3931bb9750cf73cf7dcb9f4542c9712e726b49cf5c13d16134b6f4ac9fb4e944`
  (control) and `c6f6fc4b6e42a8a0ab88cf52942b22add8cfd6e9789492f4a70ffc0100970eb2`
  (fault); normalized typed-contract hashes are
  `7c0d218af14fbaeac493684b4bf85ff06d9b0185f6b8db1cd55c54f41669aef7`
  and `1bbada6fd675460660ee6f934185f4d74147b09a016df3831b9571369456bfeb`.
  This is compatibility evidence; exact KiCad 10.0.0/10.0.5 results remain
  pending. The numbered multiport extension was then checked on the local
  KiCad 10.0.6 CLI. The synthetic DP1/DM1 + DP2/DM2 hub fault reports exactly
  one reference-domain review for each matching connector port; the shared
  reference control reports none. Repeated raw netlist hashes are
  `55cc69c350b65d919df34828649a1957bf673fe8175f0fb3e0b314cc2d8f5466`
  (fault) and `1c3326e032210500094ee60f5cdf66c1074cb7caeb3a61a2d77a8724196aeaae`
  (control); normalized typed-contract hashes are
  `62381ebb9c73b28762e759b7ad4c8d4ccee102ace693d3917a1d8b1874e428c4` and
  `b5562947696ab4d4163687ee3e091ec608cc883c7892f035a2979bdd1eb74ea0`.
  The focused USB, data-path, CLI/MCP parity, lint determinism, and catalog
  run passes 523 tests after this extension. Ruff check, format check, and
  `git diff --check` pass. These local checks do not replace the digest-pinned
  KiCad 10.0.0/10.0.5 hosted acceptance lane. At the time, no GitHub result
  was recorded for this dirty branch; the same fixture and heuristic sources
  later passed in tagged `v0.5.0rc15`, as recorded below.
  The hosted test module was also rerun after adding the multiport case registry:
  43 tests ran: 22 passed and 21 native acceptance-gated tests were skipped.
  The Docker daemon was unavailable for that local run, so those local exports
  were pending at the time. The hosted exact-version result is recorded below.
  On 2026-10-08 the full repository suite passed 2,184 tests with 25
  environment-gated skips. `KICAD_TEMPLATE_ROOT` pointed to the public
  KiCad-Team-Workflow-Template checkout at
  `ed89536f0dbbcb013145af2994fef41b2250143e`, and loopback access was enabled
  for its HTTP tests. The run includes the expanded multiport and isolator
  boundary controls, CLI/MCP, catalog, and determinism coverage. The exact
  digest-pinned 10.0.0/10.0.5 native acceptance lane was pending at the time
  because Docker was unavailable locally; hosted acceptance is recorded below.
  Typed-netlist controls give U1 two explicit reference pins on separate nets
  and model an isolator between host and device sides; the USB rule stays quiet
  in both cases. Added coverage tests distinguish no endpoints, incomplete
  endpoint evidence, common-reference paths, split-reference candidates,
  source-mapped split paths, unsupported data paths, and DNP endpoint
  dispositions. Cross-process hash-seed assertions exposed that the earlier
  synthetic multiport common-reference helper overwrote J1's pin when it used
  the same net key twice; the helper now aggregates every assigned reference
  pin. Its valid control reports two common-reference paths and zero review
  candidates. The focused USB module passes 23 tests, the catalog suite passes
  501 tests, the focused CLI/MCP parity case passes, and the three-process
  hash-seed comparison is stable. These checks add no native-export result; the
  2,184-test full run predates the coverage-report change.
  On 2026-10-07, the mapped bonded-reference fault also passed an in-process
  input-reordering comparison and the existing three-process hash-seed report
  probe. The focused USB module passed 11 tests, the determinism module passed
  its cross-process test, the catalog module passed 505 tests, and Ruff check
  and format checks passed. These typed-netlist results predate the exact
  hosted native acceptance recorded below.
  After adding deterministic per-path coverage entries on 2026-10-08, the full
  pytest suite passed with 2,262 tests, 54 environment-gated skips, and 1,963
  subtests. The package acceptance driver passed Ruff, strict Pyright, Windows
  typing, `rumdl`, `mdrepo`, wheel/sdist construction, reproducible wheel rebuild
  from the source distribution, fresh-environment installation, and CLI/MCP
  checks against the public reference checkout and a relocated copy. Its
  external portable verification and playtest also passed. This local run
  proves package and source-level behavior; the exact-version native fixture
  results are recorded below. It does not test physical return continuity.
  The hosted tag run then passed as `v0.5.0rc17` (run `37863872527`). Its
  package suite reported 2,290 passed, 26 skipped, and 2,044 subtests passed;
  `NativeUsbDataPathFixtureTests` ran on digest-pinned KiCad 10.0.0 and 10.0.5.
  The direct split-reference fault prompted review, its common-reference
  control stayed quiet, the USB-C fault/control behaved as registered, and the
  two-port fault produced two per-port reviews while its common control stayed
  quiet. Repeated normalized netlists matched for every registered case. This
  closes the native schematic-export check for these synthetic fixtures; it
  still does not test PCB copper or physical continuity.
  On 2026-10-09 the three public common-reference screens were also re-exported
  twice in digest-pinned KiCad 10.0.5. All normalized typed contracts matched
  their earlier 10.0.6 results, and each synthetic split-reference mutation
  produced one stable review. The container ran as `linux/amd64` on a
  `linux/aarch64` Docker host. This adds repeatable public-source applicability
  evidence; author dispositions and reviewer time are still unmeasured.
  The existing `NativeUsbDataPathFixtureTests` also passed locally on the same
  host with the public template pinned at
  `ed89536f0dbbcb013145af2994fef41b2250143e`: 1 test, 2 exact-version
  subtests. The focused USB analyzer, data-path, determinism, and CLI/MCP parity
  run passed 36 tests and 10 subtests; the backlog Markdown check passed.
- **Applicability screen:**

  The MIT-licensed public [CP2102 project](https://github.com/MAATHES-THILAK-K/USB_TO_UART-CP2102)
  is pinned at commit `eecf7bb08afbd1494f3136a5124f4b6b6ea6c63e`. It has
  duplicated USB-C D+/D− contacts, direct nets to a CP2102N, and separate
  two-pin data-to-GND branches. KiCad 10.0.6 exported the design; connector
  and PHY ground pins share `GND`, and the rule emits no split-reference
  review. This is an applicability non-finding, not defect detection, physical
  validation, or a precision-rate sample.

  A synthetic typed-netlist mutation moved the connector returns to
  `USB_GND`; the direct pair still matched and produced one review with both
  contacts and branch pins in evidence. The mutation changed no board or
  project source. No external schematic, board, generated netlist, or part data
  was copied into this repository.

  Two additional public projects were screened at immutable commits:
  [USB-C FUSB302/RP2040](https://github.com/bentwire/USB-C-FUSB302-PI/tree/7d95292262b42767bbeefebadb6bafe055923d50)
  and [16nx](https://github.com/16n-faderbank/16nx/tree/ca7de2233011407fdd791839d711547bf41d33d3).
  Both use one 27R series resistor per D line and a common GND assignment;
  both were quiet baseline screens. Temporary connector-to-PHY split mutations
  produced one review with both series resistor assignments in evidence. The
  named public projects remain outside this repository. These two quiet
  baselines and two synthetic mutations are applicability checks, not a
  measured precision rate or evidence of product defects.

  **Per-path remeasurement (2026-10-08):** Replayed the retained KiCad 10.0.6
  exports against tooling commit `82cb9b4`. The CP2102 path is J1–U1, the
  FUSB302/RP2040 path is J1–U302, and the 16nx path is J3–U5. All three reports
  were `EVALUATED`, each with one supported connector group, one supported PHY
  group, one `COMMON_REFERENCE` path, and zero separate-reference paths or
  prompts. Each in-memory mutation moved all matched connector reference pins
  to a new synthetic net and produced one separate-reference review for that
  path; source schematics and exports were unchanged. The repeated FUSB302 and
  16nx exports had equal normalized netlist contracts. A second CP2102 export
  was generated with app-bundled KiCad 10.0.6 on 2026-10-09. Its raw XML differs
  from the retained export because timestamped metadata changed; the normalized
  netlist and USB coverage hashes match, and both scans show one common-reference
  path with no prompt. Reapplying the in-memory connector-return split mutation
  to the repeated typed netlist produced one review and the same mutated-netlist
  hash as the original trial. The focused repeat receipt is
  `build/ci/lint-086-public-review-measurement-20261009/cp2102-repeat.json`
  (SHA-256
  `0b9fb78d2241d2c274ef50f73e19dd27409343a96a857ea340f368ef0a708470`).
  Per-path pins, series parts, shunts, source and license hashes, export hashes,
  normalized hashes, and mutation results are in the ignored
  receipt `build/ci/lint-086-public-review-measurement-20261008/receipt.json`
  (SHA-256
  `a4bb641402ffb39dfa6463467117a5782d648ab490ce120964009666282b5663`). These
  earlier 10.0.6 exports establish applicability and fixture sensitivity; at
  that time no digest-pinned execution image was recorded, and no independent
  author disposition or review-time measurement was available.

  **Pinned native remeasurement (2026-10-09):** Re-exported the three pinned
  public sources twice with
  `ghcr.io/kicad/kicad@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`
  (KiCad 10.0.5, `linux/amd64`). The source checkouts matched their pinned
  commits and had no tracked changes; schematic and license hashes are retained
  in the metadata-only receipt. Every repeated normalized typed-netlist hash
  matched its prior 10.0.6 result. Each baseline had one supported
  common-reference path and zero findings; each in-memory connector-reference
  split produced one repeat-stable review. The receipt is
  `build/ci/lint-086-public-review-measurement-20261009/native-10.0.5.json`
  (SHA-256
  `97f2001af8d2dc3574c79269d1060aca84b4c7beabe4b8b09ae95cff76a775b2`). The
  container ran on a `linux/aarch64` Docker host. This confirms reproducibility,
  applicability, and seeded-fault sensitivity; independent author dispositions
  and reviewer time remain unmeasured.

  **Coverage-boundary screen (2026-10-08):** Re-evaluated two retained public
  [Cynthion hardware exports][cynthion-hardware] under the current USB
  coverage report. The pinned source commit is
  `13aa71c2fb0be3837cd2ec580ee5d2c25fc1c678`; the root schematic SHA-256 is
  `eca9bda94e301f054081c860a184768a242c477a9da9aadd6825ba443cdd1d51`, and
  the repository's [CERN-OHL-P license][cynthion-license]
  SHA-256 is `a389939159561c106f62c5eb8862e0ce90f3a8185fa40dac79631ba55e77644f`.
  Both XML exports identify KiCad 10.0.6 and parse to equal typed netlists;
  their raw XML hashes are `9ea8fc24395a08b90209b30ff534f69e0bc49beb93e12034087f97cc5bff303a`
  and `ae1d9a25a854ec8b0906ced2b7e14663515ce4f97db58c0012d5b4545d0ad9f0`.
  Coverage is `INCOMPLETE`: all four connector groups (J1–J4) and three of
  four PHY groups (U8, U9, U11) are supported; U16 (`PI3USB102G`) is the
  incomplete multi-pin data group. No connector-to-PHY data path matched, so
  the report counted zero common-reference paths, zero separate-reference
  paths, and zero review candidates. Although the inspected reference pins
  share `GND`, this is not a supported non-finding or precision sample. The
  screen demonstrates that coverage makes a zero-finding, unsupported topology
  visible. The public source and exports remain outside the repository in
  temporary storage; only hashes and this summary are recorded here.

  The public [ADAU1701 module](https://github.com/Kononenko-K/ADAU1701_module)
  is pinned at `b05cf09906c4bbb11d92d8b18b25df11f1327d8f`; its hardware
  license file declares CERN-OHL-P (SHA-256
  `01f8d458d093c384fd30fcb5cf295e845286a0887c262fe459d7d16243bdaee4`).
  Its `Hardware/dspmodule.kicad_sch` (SHA-256
  `d234073f4ec8923ccb4b168325f7bac88210a0bf335ed4e011d0102e9c236db4`)
  places an ADuM4160 USB isolator between connector and USB bridge, with
  separate `GND1` and `GND2` references. Two local KiCad 10.0.6 exports parse
  to the same typed netlist contract (SHA-256
  `0ce75ec3e9b6fe2f63795361fe0bfb43b32a558ee3760c956fcff0701d915080`); the
  current direct/one-resistor peer rule emits no finding because it does not
  trace through an isolator. This is an intentional-isolation boundary screen,
  not a supported peer-pair non-finding, precision datapoint, or proof of
  physical behavior. Only hashes and this summary are recorded here; the
  public source and generated exports remain outside the repository.
  **Pinned public source lead (2026-10-08):** The public
  [StickHub schematic][stickhub-schematic] at commit
  `5f369a785bedc4b1d3b99222c841ac684e04f016` contains native pin-function
  text for `USB1D+`/`USB1D-` through `USB7D+`/`USB7D-`. Its
  [license][stickhub-license] is CC BY-NC-SA 4.0 with a commercial-use
  exemption; the license SHA-256 is
  `9962b75e57113a5df84ba397cec20b8d937a6d5e86dc407471f505ac5a064d88`, and
  the schematic SHA-256 is
  `bf7616095dbeb01b9f3a70f25da4e9916dc9b5424e8414c47dd5f204320d1932`.
  This host has no `kicad-cli`, and the Docker daemon is unavailable, so no
  native export or source-bound USB applicability result was produced. This
  remains a pinned alias-family lead only; the tooling-owned synthetic
  multiport fixture exercises these aliases at the exact-version native gate.
  The public source stays outside the repository; only its commit, hashes, and
  this bounded result are recorded here.
- **Bundled KiCad-demo root replay (2026-10-07):** Re-ran the bounded scanner
  on 35 retained root-project netlists from the pinned KiCad 10.0.5 demo image.
  Every first/repeat XML hash matched its earlier receipt, and all 35 pairs
  parsed to equal typed netlists. Five samples contained recognized USB data
  endpoint groups; the scanner supported two connector groups and three PHY
  groups, while five groups had incomplete evidence. No sample formed a
  supported connector-to-PHY path, so the replay produced zero common-reference
  paths, split-reference candidates, or review findings. The original demo
  source files are absent from this host, so their source bytes could not be
  rechecked during replay; the source hashes remain those in the retained
  export manifest. The result adds no precision or reviewer-value evidence and
  does not establish that the demos lack USB interfaces. The derived receipt is
  ignored at
  `build/ci/public-demo-lint-screen/output/lint-086-root-corpus-replay.json`
  (SHA-256
  `ba3183752f6ae05d8db60e6b8fdb944e95f7b1de812adabbeabf59e8b8d11bc4`). No
  schematic, board, or project source was copied into Tooling.
- **Coverage report improvement:** Each recognized USB endpoint group now
  carries its connector/PHY reference, optional numbered port group, and
  `SUPPORTED`, `INCOMPLETE`, or `DNP` disposition in the typed report and text
  output. This makes the five incomplete groups from the corpus replay
  individually reviewable while preserving the rule's bounded predicate.
  `SUPPORTED` describes endpoint-local evidence only; it does not mean that a
  connector-to-PHY path was matched. The replay localizes those five groups to
  samples 006 (J14 connector), 012 (U5 PHY), and 034 (J15 ports 1/2 and U1);
  they remain incomplete-evidence observations, not defect findings. Older
  schema-version-2 reports without endpoint rows remain readable. Focused USB
  tests, design-lint regressions, catalog validation, CLI/MCP parity,
  cross-process determinism, surface registration, formatting, and Linux
  Pyright all pass for this change. The ignored derived receipt is
  `build/ci/public-demo-lint-screen/output/lint-086-root-corpus-endpoint-groups.json`
  (SHA-256
  `e62023bc2d57ef68350355064d1075deca96d004b942d502e63b9b9cc580a5f6`).
- **Numbered hub alias coverage:** `usb_data_function_identity` now recognizes
  `USBnD+`/`USBnD-` in addition to DPn/DMn and USB_DPn/USB_DMn. The synthetic
  multiport typed-netlist and native fault/control schematics exercise two
  ports under separate and common reference nets. This broadens symbol-function
  recognition only; it does not infer that the references must be common. The
  exact KiCad 10.0.0/10.0.5 gate passed in hosted `v0.5.0rc15` acceptance.
- **Exact native acceptance:** GitHub run `37851810081` retained the USB
  fixture receipts in `build/ci/hosted-37851810081/`. On both KiCad 10.0.0 and
  10.0.5, all 11 native topology cases passed, including split-reference
  faults and common-reference controls for direct USB, USB-C duplicated
  contacts with D-designated shunts, and two numbered hub ports. Each case
  repeated with an equal normalized netlist contract on its version. Event
  receipt SHA-256 values are
  `8417b4af081cf673877b840af6e499e9a1a7b534c48df5ec93704539abdcb8ea`
  (KiCad 10.0.0) and
  `432f8224f7bdb6f4417ab5532284513a2067c8a82a4090aeb32f7e96c4f9798a`
  (KiCad 10.0.5). The workflow, fixture lane, and heuristic sources match the
  tagged sources; current uncommitted changes do not modify those files. This
  establishes exact-version schematic-export compatibility for synthetic
  cases, not physical continuity or product approval.
- **Reviewer-value measurement protocol:** Use one row per uniquely matched
  connector-to-IC path, plus a run header. Freeze the tooling commit, public or
  approved source URL and immutable revision, license/permission basis, source
  file hash, exact KiCad version and image digest, raw export hash, and
  normalized netlist hash. Capture the report status and the typed
  `supported_data_path_count`, `common_reference_path_count`,
  `separate_reference_path_count`, `mapped_separate_reference_path_count`, and
  emitted prompt count. Do not collapse connector ports, duplicate contacts,
  or multiple PHYs into a single denominator when the report distinguishes
  them.

  Record a quiet common-reference path as `supported_non_finding`. Give every
  prompted path one independently reviewed disposition: `actionable_policy_gap`
  (the prompt caused an authored common/separate/bond decision or exposed a
  mismatch against that decision), `documented_no_action` (approved design
  evidence already resolves the path and no review or contract update is
  needed), `baseline_duplicate` (the same review was already required by ERC or
  another authored check), or `unresolved` (the evidence does not establish
  intended policy). Call a prompt false only for `documented_no_action`; missing
  documentation is `unresolved`, not a false positive. A
  `supported_non_finding` means only that the predicate was quiet on a supported
  path; it does not prove common reference is required. Keep `INCOMPLETE`,
  `NO_SUPPORTED_PEER_PATHS`, DNP-only, and unsupported paths in coverage totals
  but outside the supported-path non-finding denominator.

  Run synthetic split-reference mutations only on tooling-owned fixtures and
  record mutation ID, expected prompt, observed prompt, and miss/pass. These
  measure fixture sensitivity, not field recall. Record reviewer minutes from
  opening the source-bound evidence to a written disposition. To claim a time
  reduction, compare baseline-only and report-assisted review with
  counterbalanced order and publish both sample counts and unresolved cases.
  Report counts and denominators; do not publish a precision or false-positive
  rate when a prompt lacks an independent disposition. Keep source files,
  exports, and reviewer identities out of the tooling repository.
- **Next:** Keep this review-only and measure reviewer usefulness and false
  prompts on approved nonconfidential boards. Do not make common reference a
  universal USB rule. Reviewer effort, false-positive rate, multi-pin
  protection arrays, multiple series components, and indirect-path cases
  remain unmeasured. See the
  [USB-A fixture record](../tests/fixtures/design_lint/usb-peer-reference-native/README.md)
  and [USB-C fixture record](../tests/fixtures/design_lint/usb-c-peer-reference-native/README.md).

#### LINT-087 — Exact serial reference-bond contract

- **Status:** Implemented in `SerialPeerAnalysis` as an explicit `bonded`
  reference policy. It checks the authored endpoint pins and nets plus one
  exact passive two-pin component's symbol, footprint, value, fitted state,
  pin types, and side-net assignments. The serial split-reference lint only
  treats a bonded map as reviewed when that exact component also matches.
- **Priority:** P1 contract regression. A split reference may be intentional,
  but a project that requires a particular bond should fail when its mapped
  part is removed, changed, marked DNP, or disconnected from either return net.
  The check adds authored intent to schematic evidence without changing the
  REVIEW-only heuristic default.
- **Predicate:** `reference_policy: "bonded"` requires one reference net per
  endpoint, distinct endpoint nets, and one exact `ReferenceBondRequirement`
  whose two mapped side nets equal those endpoint nets. The native netlist must
  contain exactly the expected two-pin passive symbol, footprint, value,
  non-DNP state, passive pin types, and pin-to-net assignments. A bond map with
  stale or mismatched evidence does not suppress
  `bus.serial_peer_reference_review`.
- **Boundary:** The result establishes only the exported schematic assignments
  and component metadata. It does not prove component conduction, PCB copper,
  off-board wiring, connector contact behavior, or electrical suitability.
  Project owners must source the part and decide whether a resistor, net tie,
  direct copper connection, or isolation is required for their interface.
- **Fixtures and evidence:** Typed-netlist tests cover a valid bond and missing,
  wrong-value, wrong-footprint, wrong-symbol, DNP, active-pin, wrong-net, and
  unconnected endpoint faults. A CLI/MCP parity case checks the valid control
  and keeps the review visible for a broken bond. Three-process hash-seed
  tests compare the serialized fault and control checks. Synthetic KiCad
  schematics bind J1/J2 references to a 0R R3 control and an R3.2 floating-net
  fault; the exact fixture hashes and outcome are recorded in the
  [synthetic fixture README](../tests/fixtures/design_lint/serial-peer-reference-bond-native/README.md).
  A second typed fault/control pair verifies that an exact fitted
  `Device:FerriteBead` may satisfy the same reviewed bond contract, and that a
  moved bead pin restores the review. The focused serial-reference suite passed
  24 tests and 13 subtests. This composes the shared bond validator with
  LINT-085's exact native ferrite identity and passive-pin evidence; it is not
  an end-to-end native ferrite-bond export.
  Repeated digest-pinned KiCad 10.0.0/10.0.5 exports are wired into the existing
  GitHub serial-peer acceptance job. A local exact-version rerun on 2026-10-08
  passed in both digest-pinned images as part of the package acceptance test
  (`2 passed, 4 subtests` across LINT-077 and LINT-087). For LINT-087, repeated
  normalized netlists matched; the control passed and the fault failed exactly
  `serial/serial-bond/reference` on both versions. The earlier v0.3.2 hosted run
  found ground wires that missed their symbol pins, and v0.4.1 found reversed
  TX/RX declarations in the authored bond map. Both fixture defects were
  corrected; the native sources now bind to the pin endpoints and follow the
  schematic's TX/RX functions.
  **Tagged hosted acceptance:** GitHub run `37851810081` for
  `v0.5.0rc15` passed the reference-bond control and broken-bond fault on both
  digest-pinned KiCad 10.0.0 and 10.0.5. The control matched the authored bond
  map; the fault identified `R3.2` on `FLOATING_GND` instead of `GND_B` and
  failed only `serial/serial-bond/reference`. Repeated normalized netlist
  contracts matched for both cases on both versions. The retained event receipt
  hashes are
  `ab290167b3d294ebdc238af0f53157894de9dbb0e88df5e4f0eb4572f5623b3c`
  (KiCad 10.0.0) and
  `ac57bdf9a719fcbfe386fbb2021533b0b8a9f543a277509b5e71cc66633f9b0d`
  (KiCad 10.0.5), under ignored
  `build/ci/hosted-37851810081/native-serial-peer-project-*/`. The workflow,
  fixture lane, and rule sources are unchanged from the accepted tag.

#### LINT-088 — Fitted two-pin crystal terminals share one net

- **Status:** Implemented as `component.two_pin_crystal_same_net`, defaulting
  to `REVIEW`, with project `review`/`block`/`off` overrides and exact
  fingerprint ignores. It uses the shared native two-pin inventory and is
  covered by fault/control, unsupported-case, metamorphic, CLI/MCP, and
  three-process hash-seed tests.
- **Priority:** P1 topology review. The project-mapped LINT-035 crystal
  network contract can compare a reviewed design, but without that map the
  generic design-lint catalog did not flag a fitted two-terminal crystal whose
  two native pins collapse to one net.
- **Cohort comparison:** The inspected [kicad-happy crystal detector][happy-crystal-detector]
  recognizes crystal circuits and load-capacitor topology, but does not emit
  this bounded same-net finding. No candidate code or runtime dependency was
  adopted; this is a first-party extension of the exact-symbol same-net checks.
- **Predicate:** Recognize only fitted `Device:Crystal` family symbols with
  exactly two distinct native pin numbers, where each has one unambiguous
  native net assignment and both assignments name the same net. Report exact
  component, symbol, value, pins, and net. Project policy may review, block,
  disable, or exactly ignore the finding.
- **Boundary:** A bypassed or disabled crystal can be intentional. This reports
  schematic netlist topology only; it does not establish oscillator behavior,
  frequency suitability, pin-function correctness, footprint mapping, physical
  population, or PCB copper connectivity. Active oscillator symbols, custom
  identities, multi-pin or incomplete inventories, ambiguous/open pins, and
  DNP parts are outside the predicate.
- **Fixtures and evidence:** Tooling-owned same-net fault and distinct-net
  control schematics are source-hashed and run twice on the digest-pinned KiCad
  10.0.0 and 10.0.5 images in the existing two-pin component acceptance lane.
  Typed-netlist tests cover `Device:Crystal` and `Device:Crystal_Small`, while
  a three-pin crystal-family control, DNP, incomplete, ambiguous, open, and
  custom-symbol cases remain quiet. CLI/MCP returns identical evidence for
  fault and control; metamorphic tests preserve the unaffected peer finding
  when one crystal's pins are split. Exact native exports are wired into
  GitHub CI. The exact-version local rerun on 2026-10-08 passed in both pinned
  images: the same-net crystal stayed `REVIEW`, the distinct-net control passed,
  and repeated normalized netlists matched. Hosted package acceptance for this
  revision remains pending.

#### LINT-089 — Generic connector power-input pin is unassigned

- **Status:** Implemented as `connector.unconnected_power_input`, defaulting
  to `REVIEW`, with project `review`/`block`/`off` overrides and exact
  fingerprint ignores. The shared connector candidate set and native pin-type
  inventory drive the same typed report for CLI and MCP.
- **Priority:** P1 connector completeness. A generic peer-pin heuristic flags
  an open pin when one peer differs, but it is silent when every repeated
  connector contact is open. The native `power_in` type gives the heuristic a
  deterministic review signal without supplying the missing interface intent.
- **Predicate:** A fitted connector pin is present in the exported native pin
  electrical-type map as `power_in`; its function is absent, blank, numeric, or
  a generic `Pin_N`; and no exported net assigns that pin. Named supply/return
  checks retain precedence, and overlapping repeated-role or peer-outlier
  prompts are suppressed for the same open pin.
- **Boundary:** KiCad's type does not distinguish a positive supply contact
  from a reference or establish that the contact should be connected. Explicit
  no-connect markers remain review candidates; project owners can record a
  justified exact ignore or disable the rule. DNP instances, non-connector
  pins, meaningful named functions, and assigned pins are outside the
  predicate. The finding does not claim peer pins should share a net or that
  native schematic assignment proves PCB copper continuity.
- **Fixtures and evidence:** The synthetic two-connector fault leaves both
  generic `power_in` pins open while return pins stay connected; the valid
  control assigns both contacts to `+5V`. Source hashes are
  `2e16c602d6ba0068360b3f8b493351f6d7e4d7adbe94946d17db883587f0528f` (fault)
  and `b05c1a3994a4f26f07e18bdfe28c8caaf4a298cbb66b6d1814b20c9a7dce2c13`
  (control). Typed-netlist cases cover blank and absent function, assignment,
  named supply/return deduplication, passive and `power_out` types, DNP,
  blocking, disabling, and exact ignores. CLI/MCP parity and three-process
  determinism include the finding. Local KiCad 10.0.6 exported both sources
  repeatably, preserved native `power_in`, reported exactly the two fault pins,
  and left the control clean. Digest-pinned KiCad 10.0.0 and 10.0.5 repeated
  exports run through `NativeConnectorReturnFixtureTests` in GitHub CI; the
  current local rerun on 2026-10-08 also passed on both exact versions. The
  open `power_in` fault remained `REVIEW` and the connected control passed;
  hosted acceptance for the current branch remains unrecorded.

#### LINT-090 — USB-C port-side VBUS capacitance contract

- **Status:** Implemented as an explicit per-port disposition in the typed
  USB-C electrical contract. A required declaration binds each fitted
  capacitor by reference, symbol, footprint, pin inventory, and exact VBUS/return
  net assignments, then compares the nominal total to project-authored
  inclusive limits. `pending` remains `NOT_CONFIGURED`; `not_applicable`
  requires a reason. Tooling-owned synthetic native fault/control fixtures and
  full package acceptance passed in tagged `v0.5.0rc17` (GitHub run
  `37863872527`).
- **Inspiration:** The kicad-happy USB checks include UC-004 for undersized
  VBUS capacitance ([candidate releases][happy-uc-releases]). The local
  baseline had USB-C CC, VBUS path, and protection checks but no port-side VBUS
  capacitance comparison. This implementation uses the candidate as a gap
  signal, not as copied code or a universal rule.
- **Predicate:** For a configured USB-C port with `vbus_capacitance.mode` set
  to `required`, every authored capacitor must exist exactly once, be fitted,
  match its symbol and footprint, expose the exact two-pin native inventory,
  assign its pins to the authored port VBUS and ground nets, and have a
  supported nominal capacitance value. The nominal values are summed in nF and
  compared to the authored inclusive range. An additional fitted capacitor
  candidate touching port-side VBUS must be mapped or the check fails.
- **Boundary:** The project supplies the source, applicability decision, and
  numeric limits; the tooling does not provide a Type-C threshold or infer a
  requirement from net names. A project may cite the applicable revision and
  section of its approved source, such as the
  [USB-IF Type-C specification release selected by the project][usb-c-spec-release].
  A passing result does not establish USB
  compliance, tolerance or bias derating, transient response, source-state
  behavior, placement, copper continuity, or hardware acceptance. Capacitors
  on another VBUS domain are outside this port-side inventory. A reviewer may
  choose `not_applicable` only with a project-owned reason.
- **Evidence:** Synthetic fault/control schematics cover 2.2 uF below a
  4500–5000 nF window and 4.7 uF inside it. Focused unit cases also cover
  missing and extra inventory items, DNP, wrong identity, wrong net, unsupported
  values, pending, and not-applicable. CLI and MCP invoke the same typed
  electrical service, with a parity test for pass and under-range fault. The
  native acceptance lane repeats both schematics and compares normalized
  netlists before running the same check; source hashes are pinned in
  `NativeUsbCPortFixtureTests`. The synthetic sources and evidence boundary are
  documented in the [fixture README][usb-cap-fixture-readme].
- **Acceptance:** In GitHub run `37863872527`, digest-pinned KiCad 10.0.0 and
  10.0.5 each exported the fault and control twice with matching normalized
  netlist contracts. The 4700 nF control passed the authored 4500–5000 nF
  window; the 2200 nF fault produced the expected check failure. Project
  adoption still requires the owner to cite and approve the actual limit and
  port applicability. No private project source or requirement was used.

#### LINT-091 — Exact custom-capacitor role for decoupling review

- **Status:** Implemented as an applicability extension to LINT-069 and
  `power.ic_rail_without_fitted_capacitor`. It does not add a new lint rule or
  declare that every IC rail requires a capacitor. Digest-pinned KiCad 10.0.0
  and 10.0.5 native acceptance passed in tagged `v0.5.0rc17` (GitHub run
  `37863872527`).
- **Cohort input:** The kicad-happy source-backed trial under LINT-031 reported
  decoupling-symbol coverage and missing-decoupling observations. That trial
  identified symbol presence as a candidate review signal, while also
  showing broader applicability than the local `power_in` predicate. LINT-091
  addresses a narrower gap in the existing local rule: an opaque custom
  capacitor symbol is not recognized by its library name. No cohort code,
  workflow, project source, or rule threshold is imported.
- **Predicate:** A project-owned `component_role_map` entry classifies a
  capacitor only when exact `PART_ID`, native symbol, footprint, and complete
  two-pin number/function/electrical-type inventory match. The native pins
  must both be passive. A fitted mapped capacitor suppresses LINT-046 only
  when its two pins occupy distinct recognized positive and return nets. DNP
  parts do not count. A mapped component with an unrecognized return leaves
  the review prompt active; a stale map blocks lint. The role cannot activate
  LED heuristics or other rules.
- **Boundary:** The map records reviewed component identity, not datasheet
  suitability, required value, placement, rail demand, copper continuity, or
  physical effectiveness. The rule remains a default `REVIEW` hint, and
  project-authored requirements remain responsible for deciding whether a
  capacitor is required and what values and topology are acceptable.
- **Evidence:** Tooling-owned synthetic KiCad schematics use an opaque
  `Vendor:CAP123` symbol, exact synthetic `PART_ID`, footprint, and passive
  pins named `1` and `2`. The valid control assigns them to `+3V3` and `GND`;
  the fault assigns the return to `CAP_REF`. Typed cases cover DNP, wrong
  return, stale footprint, role isolation from the LED rule, and input-order
  stability. CLI/MCP parity covers unclassified, mapped-valid, and mapped
  fault states. GitHub native acceptance repeats exports on exact KiCad
  10.0.0 and 10.0.5, checks the complete identity and pin inventory, confirms
  zero native ERC errors, and compares deterministic LINT-046 outcomes.
- **Incremental value:** This improves applicability for explicitly reviewed
  custom symbols. It adds no independent electrical defect detection beyond
  LINT-046 and does not measure false-positive rate or reviewer effort.
- **Acceptance:** In GitHub run `37863872527`, the custom-symbol fault and
  control exported twice on digest-pinned KiCad 10.0.0 and 10.0.5 with matching
  normalized netlist and ERC evidence. The mapped valid control cleared the
  LINT-046 prompt; the wrong-return fault retained `REVIEW`. No proprietary
  board source or project expectation is used or stored.

#### LINT-092 — Generic non-connector power-input pin is unassigned

- **Status:** Implemented as a default-`REVIEW` source-bound heuristic using
  KiCad's native pin electrical type. It extends the exact `power_in` signal
  used by LINT-089 to non-connector components; it is not a singleton-net
  warning and does not infer a shared supply/ground requirement.
- **Cohort and backlog context:** Prior LINT-031 trials found general singleton
  warnings duplicative of native ERC and rejected a general singleton-net
  rule. This check uses the narrower native `power_in` type to find an
  unassigned component pin even when every peer is also open. Named supply and
  return pins already use dedicated checks; connector pins remain with
  LINT-089. This is a local extension of that native-evidence boundary. The
  cohort results reinforce the stop condition: do not broaden it into a generic
  singleton-net rule. No third-party code, source, or default electrical
  assumption is imported.
- **Predicate:** A fitted component with native symbol identity has an
  unassigned pin whose electrical type is exactly `power_in` after case-folding
  and whose function is absent, numeric-only, or a generic `Pin_N` placeholder.
  DNP components and native or source-reviewed connector candidates are
  excluded. An explicit no-connect marker remains a review candidate because
  it carries no independent reason why the power-input pin is intentionally
  open.
- **Boundary:** `power_in` does not distinguish positive supply from reference
  or establish that the pin must be connected. This check cannot validate the
  assigned rail, power source, off-board circuitry, copper, population, or
  operation. Projects may review, block, disable, or exactly ignore a finding;
  a required rail relationship belongs in a project-authored contract.
- **Evidence:** Tooling-owned synthetic native schematics cover a floating
  generic pin and an explicit no-connect fault, with a connected control and a
  DNP control. Typed cases also cover missing function metadata, named supply
  deduplication, passive and `power_out` pins, connector exclusion, project
  blocking, exact ignore, and input-order stability. CLI/MCP parity checks the
  fault and connected control. The digest-pinned KiCad 10.0.0/10.0.5 native
  lane records repeated netlist exports and checks the fault, no-connect,
  connected, and DNP outcomes. No board or project-owned requirement is used.
- **Incremental value:** This closes the generic non-connector edge left by
  LINT-089. It does not duplicate the cohort's broad singleton-net finding;
  independent fault/control tests show the trigger is the native electrical
  pin classification.
- **Acceptance:** GitHub run `37777586540` for `v0.5.0rc9` passed the pinned
  KiCad 10.0.0 and 10.0.5 fixture lanes. Both versions repeated native exports
  and produced REVIEW for the fault and no-connect cases, with PASS for the
  connected and DNP controls.

#### LINT-093 — Exact two-pin SPST switch is bypassed by one net

- **Status:** Implemented as `component.two_pin_switch_same_net`, defaulting
  to `REVIEW` and using the shared native two-pin inventory. The rule supports
  project `review`, `block`, `off`, and exact-fingerprint ignore decisions.
- **Priority:** P1 component-topology coverage. The existing same-net family
  covered passives, diodes, crystals, fuses, and ferrite beads, but omitted a
  fitted two-terminal switch whose pins had collapsed to one native net.
  LINT-056 also lists switch topologies as unsupported source-path elements;
  this rule checks only the exact same-net bypass case and does not teach the
  source-path heuristic that a switch is a conducting path.
- **Cohort context:** The kicad-happy same-net SP-001 concept and its synthetic
  trial contributed to the existing exact-family checks. This extension adds
  one standard symbol identity where the local two-pin predicate had no
  coverage. No candidate code, package, example, board, or project expectation
  was imported.
- **Predicate:** For exact `Switch:SW_SPST`, require a fitted component, a
  complete inventory of exactly two distinct native pin numbers, and one
  unambiguous assigned net per pin. Emit `REVIEW` only when both assignments
  name the same net. DNP parts, multi-pin or incomplete inventories, open or
  ambiguous assignments, and other switch identities—including `SW_SPDT`,
  `SW_SPST_LED`, and vendor symbols—are outside the predicate.
- **Boundary:** The netlist shows that this schematic net assignment bypasses
  the switch contacts; it does not establish a real switch state, a required
  switching function, the selected footprint's pin mapping, assembly
  population, or PCB copper. A same-net symbol may be deliberate. The rule
  does not infer that all switches should separate nets, and it remains
  review-only by default.
- **Fixtures and evidence:** Synthetic `Switch:SW_SPST` same-net fault and
  distinct-net control schematics are source-hashed. Typed tests cover policy,
  exact ignore, DNP, incomplete, multi-pin, open, ambiguous, and unsupported
  switch identities; order-reversal stability and a one-switch net split are
  metamorphic controls. CLI/MCP parity passed, and the tagged GitHub package
  run `37785605719` passed the shared two-pin native fixture lane on the
  digest-pinned KiCad 10.0.0 and 10.0.5 images. The lane exported all 14
  tooling-owned fault/control schematics twice and matched expected lint
  statuses, including the switch same-net fault and distinct-net control. The
  full package acceptance and all portable preview jobs passed. These are
  synthetic native-export checks; they do not establish physical switch state,
  footprint mapping, assembly population, or PCB continuity.

#### LINT-094 — Open native power output on one exact-symbol peer

- **Status:** Implemented as `component.peer_power_output_unconnected`,
  defaulting to `REVIEW`. Projects can use the existing rule policy to keep
  review, block, disable, or exactly ignore a finding.
- **Priority:** P1 component-population coverage. Existing peer-power rules
  compare assigned supply/return pins, and the open-pin check covers native
  `power_in` pins. An open `power_out` pin on one fitted copy of a component
  could remain unnoticed when another identical copy has that pin assigned.
- **Cohort context:** Similar-part and pin-comparison analyzers establish a
  useful review prompt, not a universal connectivity rule. The local check
  uses native symbol identity, complete pin inventory, and native electrical
  type; it imports no cohort implementation or project data.
- **Predicate:** Group fitted, non-connector instances with an exact matching
  native symbol. Require complete, identical, unambiguous pin-number
  inventories and matching `power_out` types for that pin. Emit one review
  finding when at least one peer pin has no net assignment and at least one
  has exactly one. Recognized supply and return functions remain with their
  more specific checks; shield-labelled native power outputs remain eligible
  because no component-level unconnected-shield finding exists. All-open,
  all-assigned, DNP, incomplete/mismatched, missing-type, and multi-net
  assignments do not trigger this rule.
- **Boundary:** The finding asks whether the open output is intentional or
  needs a connection. It does not require common nets across identical
  outputs, identify what a component output does, prove it is used, validate
  current capacity, or establish PCB copper, off-board wiring, or physical
  population. Native `power_out` is only a candidate-selection clue.
- **Fixtures and evidence:** The typed pytest fault/control matrix covers
  connected versus open peers, same-net and distinct-net output controls,
  DNP, all-open, different symbols, incomplete inventory, ambiguous
  assignment, non-`power_out` types, named supply/return exclusions, a
  shield-labelled output fault, stable ordering, and review/block/off/exact-ignore
  policy. The synthetic
  native source pair is
  [documented and source-hashed](../tests/fixtures/design_lint/component-peer-power-output-native/README.md);
  the fault leaves U2.2 open while U1.2 is assigned, and the control assigns
  outputs to separate nets. A repeated-export lane is configured for the
  digest-pinned KiCad 10.0.0 and 10.0.5 versions. CLI/MCP parity exercises the
  shared design-lint service. Tagged acceptance passed in CI run 37796753272
  (`v0.5.0rc12`): the fault and control fixtures were each exported twice on
  digest-pinned KiCad 10.0.0 and 10.0.5, with repeatable parsed contracts and
  the expected REVIEW on U2.2 versus PASS for control. The complete unit gate,
  source-distribution wheel rebuild and installed-wheel checks against the
  separate template checkout, and Linux/macOS/Windows preview jobs also passed.
  This verifies schematic/netlist recognition only; it does not establish PCB
  connectivity or electrical correctness.

#### LINT-098 — Open native signal output on one exact-symbol peer

- **Status:** Implemented as `component.peer_signal_output_unconnected`, with
  pytest typed-netlist regressions, rule-catalog coverage, project policy and
  exact-ignore controls, CLI/MCP parity, and a repeated native-export lane for
  the pinned KiCad 10.0.0 and 10.0.5 profiles. Hosted acceptance is pending.
- **Priority:** P1 component-pin completeness. LINT-094 recognizes native
  `power_out` pins, while this rule covers otherwise comparable pins classified
  as ordinary `output`. A missing assignment on one exact-symbol peer can be
  hard to spot in a repeated component group.
- **Predicate:** Compare fitted, non-connector instances with one exact native
  symbol and complete identical pin-number inventories. For each pin number,
  require native electrical type `output` on every peer, matching pin-function
  metadata, and one unambiguous net assignment on at least one peer. Emit a
  `REVIEW` candidate when at least one peer pin has no assignment. Named supply
  and return pins remain with their specific checks. All-open groups, DNP
  peers, different symbols, incomplete inventories, mixed pin types, and
  ambiguous assignments are outside the predicate.
- **Boundary:** Matching symbols and pin numbers are clues to inspect an open
  output, not requirements to use it or connect peer outputs together. Native
  `output` type does not identify the signal function or expected load. This
  does not infer PWM channel assignments, LED topology, off-board wiring, PCB
  continuity, or physical population. A project-authored `pin_connectivity`
  requirement remains the way to make a specific required relationship a
  regression gate.
- **Fixtures:** Synthetic typed and native-export faults leave one peer's
  output pin open; controls assign the peer pins to the same net and to
  different nets. Typed controls also cover all-open, DNP, different-symbol,
  incomplete-inventory, ambiguous, wrong-electrical-type, and named supply or
  return cases. Input-map reordering preserves the finding fingerprint.
  Synthetic schematics bind the exact symbol, pin inventory, native output
  type, and expected pin assignments; each source is exported twice on the
  digest-pinned KiCad 10.0.0 and 10.0.5 images.
- **Incremental value:** The extension fills the explicit gap between the
  existing generic unconnected `power_in` check and LINT-094's peer `power_out`
  check. It does not claim a cohort analyzer finding or field precision.
- **Next:** Keep the native lane in package acceptance. Measure the prompt on
  approved, nonconfidential designs before changing its default disposition.

#### LINT-099 — Open native signal input on one exact-symbol peer

- **Status:** Implemented as `component.peer_signal_input_unconnected`, with
  pytest typed-netlist regressions, project policy and exact-ignore controls,
  CLI/MCP parity, and a repeated native-export lane for pinned KiCad 10.0.0 and
  10.0.5. Hosted acceptance is pending.
- **Priority:** P1 component-pin completeness. LINT-094 and LINT-098 cover
  native power and signal outputs. This adds a narrow review prompt for an
  otherwise ordinary `input` or `input_low` pin left open on one exact-symbol
  fitted peer while another peer assigns its matching pin.
- **Predicate:** Compare fitted, non-connector instances with one exact native
  symbol and complete identical pin-number inventories. Require matching
  native input type and present matching function metadata. Emit a `REVIEW` candidate
  only when at least one peer pin has exactly one net assignment and at least
  one peer pin is unassigned. Named supply and return pins, plus recognized
  reset, enable, and boot controls, remain with their specific checks.
- **Boundary:** Matching symbols, pin numbers, electrical types, and function
  metadata are clues to inspect an open input; they do not establish a required
  source or require peer inputs to share a net. This does not infer off-board
  wiring, a missing driver, PCB copper continuity, or physical population. A
  project-authored connectivity requirement remains necessary to make a
  specific required relationship a blocking regression gate.
- **Fixtures:** Synthetic typed and native-export faults leave one peer input
  open. Controls assign the peer inputs to the same net and to separate nets.
  Typed boundaries cover all-open peers, DNP, different symbols, incomplete
  inventories, ambiguous assignments, mixed functions or types, passive pins,
  connectors, named supply/return pins, and recognized controls. Cross-process
  hash-seed tests and input-map reordering verify stable reports. Native source
  fixtures are exported twice on both pinned KiCad profiles.
- **Incremental value:** This is a deterministic review hint for missing
  assignments that ERC may not flag when the opposite pin is also typed as an
  input. It does not claim input peers should share a net, and it does not
  replace project-authored connectivity requirements.
- **Next:** Keep the prompt at default `review`; measure usefulness and false
  prompts on approved, nonconfidential boards before considering a default
  change.

### P2 — PCB geometry and schematic review assistance

#### LINT-095 — Mapped PCB signal-path length and bundle-skew rule coverage

- **Status:** Implemented as the opt-in `pcb.signal_path_rule_coverage` audit.
  The full local package gate passed on 2026-10-08 (2,266 tests passed, 54
  skipped, 2,030 subtests passed), including source and wheel builds,
  rebuilt-wheel equality, and installed-wheel checks against the exact
  CI-pinned public template. Exact-version native fixtures separately passed on
  the same date for KiCad 10.0.0 and 10.0.5: each repeated control run was clean,
  each fault run reported both length and skew violations, and each ignored-
  rule control was clean. The generated boards, rules, DRC reports, normalized
  command receipts, and hash-bearing events are retained under ignored
  `build/ci/native-fixtures/pcb-signal-path/`. Baseline acceptance passed in
  `v0.5.0rc13` (run `37845619358`); the complete canonical violation-record
  comparison passed its exact-version hosted lane in `v0.5.0rc15` (run
  `37851810081`). Repeated control and ignored-rule reports were clean, and
  repeated fault reports retained both target violation records. Some raw DRC
  report hashes differed between repeats even when their canonical finding
  records matched.
- **Problem:** A board can have valid net assignments and still lack the
  reviewed path-length or bundle-skew limits that the interface depends on.
  KiCad DRC already measures these quantities, but project-authored endpoint
  intent can be absent or can drift away from the active native rule.
- **Predicate:** The project maps exact `reference.pad` endpoints, native net,
  independent basis, optional length bounds, and bundles with exact member
  path IDs, pad-selector patterns, and maximum skew. Each endpoint must be on
  the declared net in both the current native schematic netlist and PCB pad
  inventory; it must be fitted and in the same native copper component as its
  mate. Each endpoint rule requires exactly one `A.fromTo()` rule with exact
  supported bounds and a non-ignored native DRC severity. Bundle selectors
  must resolve to exactly the mapped endpoint set before their one exact skew
  rule can be credited.
- **Controls:** Missing rules, wrong bounds, duplicate matches, ignored
  severities, stale schematic endpoints, PCB net mismatches, DNP endpoints,
  split copper components, extra wildcard matches, reordered map/rule inputs,
  review/block/off/exact-ignore behavior, and explicit custom-rule
  `(severity ignore)` have synthetic pytest cases. An ignored custom rule cannot
  count as active coverage. Local lane, schedule, and native fixture tests use a
  tooling-owned synthetic checkout independent of the external template.
  CLI and MCP continue to share `inspect_design_lint`; disabled-policy parity
  passes from a tooling-owned synthetic project without the external template
  checkout. The generated control, fault, and
  explicit-ignore boards and their exact-version lane are documented in the
  [synthetic fixture record](../tests/fixtures/design_lint/signal-path/README.md).
  Hosted acceptance records hashes for each generated board, rule file, and raw
  DRC report, plus native exit codes and the command receipt. The native lane
  includes an identical-geometry case whose mapped rules explicitly use
  `(severity ignore)` and requires those target findings to disappear. Local
  mocked orchestration tests verify the evidence fields and reject both a fault
  missing a target DRC violation and an ignored rule that still reports one;
  they are not native KiCad results.
- **Evidence boundary:** The report binds project settings, board, optional
  rule file, native DRC receipt, exact native PCB connectivity snapshot and
  command, KiCad version, and source hashes. KiCad DRC measures geometry; this
  audit only verifies that the reviewed map is represented by an active rule
  and that its endpoints match source and copper evidence. It does not select
  an electrically appropriate length or skew limit, evaluate off-board
  wiring, or establish physical continuity.
- **Privacy:** Tooling-owned synthetic data only. No project-specific source,
  observed pinout, contract, or candidate implementation is retained.

#### LINT-096 — Project-authored PCB keepout signature regression

- **Status:** Implemented as the opt-in `pcb.keepout_intent_coverage` rule.
  The native probe records rule-area names, canonical outlines and holes,
  copper-layer membership, and track/via/pad/zone-fill/footprint restrictions
  in snapshot schemas 11 and 12. Synthetic extraction was run with the exact
  digest-pinned KiCad 10.0.0 and 10.0.5 images. Synthetic pytest cases cover
  exact matches, changed geometry/layers/restrictions, missing and duplicate
  names, unsupported snapshot schema, digest order stability, and review,
  block, off, and exact-ignore policy. The full local package gate passed on
  2026-10-08 against the exact CI-pinned public template (2,266 tests passed,
  54 skipped, 2,030 subtests passed), including wheel and source builds and
  installed-wheel external checks. Exact native extraction also passed against
  both pinned KiCad versions. CLI/MCP parity passes from a tooling-owned
  synthetic checkout without the public template. Tagged GitHub acceptance
  passed in `v0.5.0rc13` (run `37845619358`) and was revalidated in
  `v0.5.0rc15` (run `37851810081`).
  Schema 12 now retains footprint identity, fitted state, board origin,
  canonical microdegree orientation, and board side for the next RF keepout
  gate. Its typed and serializer tests pass. On 2026-10-09 the new
  `tests/test_pcb_keepouts_native.py` schema-12 extraction test passed on both
  digest-pinned KiCad 10.0.0 and 10.0.5 images (2 cases). It verifies exact
  front/back footprint identity, DNP state, board coordinates, canonical
  orientation, exact transformed pad centers, and pad-to-footprint binding
  alongside the synthetic rule area.
- **Problem:** A project can retain a named keepout while its outline, copper
  layers, or restrictions drift. Generic ERC/DRC does not know that the
  project intended a particular rule-area definition to remain unchanged.
- **Predicate:** The project maps one unique keepout name to an independently
  reviewed canonical geometry digest, exact copper-layer set, and all five
  native restriction flags. The source-bound probe must return exactly one
  native rule area with that name, and every observed property must match.
  Missing, duplicate, renamed, reshaped, layer-changed, restriction-changed,
  or unsupported-schema cases remain incomplete.
- **Controls:** Synthetic tests compare exact geometry, changed outlines,
  polygon/hole ordering, layer sets, restriction flags, duplicate and missing
  names, and a pre-schema-11 snapshot. Lint behavior is checked under review,
  block, off, and an exact fingerprint ignore. The geometry digest is stable
  under polygon and hole collection reordering.
- **Evidence boundary:** This checks regression of a project-authored KiCad
  rule-area definition. It cannot prove that the reviewed shape, layer set, or
  restriction flags correctly express a vendor drawing or engineering need;
  it does not establish copper exclusion on fabricated boards, module
  placement, RF behavior, or physical continuity. The map must come from an
  independent approved source, not the observed board alone.
- **Privacy:** Tooling-owned synthetic data only. No customer board, module
  outline, connector pinout, project contract, or proprietary expectation is
  retained.

#### LINT-097 — Source-mapped RF module antenna keepout coverage

- **Status:** Implemented as the active opt-in
  pcb.rf_module_antenna_keepout_coverage rule. The project-owned typed map,
  source-bound schematic/board identity checks, explicit onboard/external/DNP
  dispositions, deterministic footprint-local polygon transform, policy modes,
  report and text output are in place; the configured disabled report has
  CLI/MCP parity. Synthetic fault,
  control, metamorphic, and review/block/off/ignore cases pass. The
  tooling-owned native fixture verifies front-side 90-degree and 30-degree,
  plus back-side 270-degree footprint transforms against actual named rule
  areas. Both exact digest-pinned KiCad 10.0.0 and 10.0.5 acceptance runs
  passed. No cohort runtime installation or proprietary board trial is claimed.
- **Cohort input:** The pinned `kicad-happy` `KO-001` source checks component
  and via centers against the bounding box of an existing keepout. That can
  prompt review of nearby objects, but cannot detect a missing keepout, check
  its exact outline, or bind it to an RF module and feed. Do not copy its code,
  thresholds, severity, or dependency.
- **Problem:** LINT-096 detects drift in an independently mapped rule-area
  signature, but does not establish which RF module or feed the area protects.
  A named area can still become detached from the antenna region when the
  module moves or changes.
- **Implemented contract:** A project-authored map names the exact module
  reference and footprint identity, RF feed pad and native net, keepout name,
  vendor-document basis, local-coordinate polygon and holes, copper layers,
  and all rule-area restriction flags. It must also explicitly disposition a
  DNP module or an external-antenna design; neither is inferred from names.
- **Predicate:** The native PCB evidence binds the fitted footprint and RF
  pad/net to the schematic source, capture footprint position, orientation and
  board side, and return exactly one named rule area. Transform the reviewed
  local polygon through the observed footprint placement and compare its exact
  canonical outline, layers and restrictions. Missing, duplicate, stale,
  unsupported, identity-changed or mismatched evidence remains incomplete.
  Default disposition is `REVIEW`; project policy may select `block`, `off`,
  or an exact fingerprint ignore.
- **Fault/control cases:** Synthetic cases cover missing, offset, duplicate,
  geometry, layer, and restriction mismatches; changed symbol, footprint,
  PART_ID, feed pin/net, and DNP state; and unsupported snapshot schema. A
  module moved without its area fails, while moving the module and area
  together passes. Explicit external-antenna and DNP controls pass. Review,
  block, off, and exact-ignore behavior is tested, as is CLI/MCP parity for a
  configured disabled report. The native synthetic board has mapped pads on
  front-side 90-degree and 30-degree, and back-side 270-degree footprints;
  each transformed local keepout matches a native rule-area outline on KiCad
  10.0.0 and 10.0.5.
- **Evidence boundary:** The check compares project-reviewed placement intent
  with native PCB geometry. It cannot validate that the vendor drawing was
  interpreted correctly, establish antenna performance, or prove copper
  exclusion on a fabricated board. Native DRC remains a separate check.
- **Acceptance limits:** Enabled CLI/MCP fault-case parity and a candidate
  runtime trial remain future evidence. The tool accepts only requirements
  authored in the project repository and uses synthetic fixtures here.
- **Privacy:** Develop with tooling-owned synthetic boards and maps only. Do
  not retain customer or proprietary module layouts or contracts.

#### LINT-020 — Decoupling-capacitor proximity and connection evidence

- **Status:** Implemented v2 as the opt-in `pcb.decoupling_proximity` rule with
  project-authored pad and optional return-via distance limits, plus a
  source-bound native PCB snapshot.
- **Inspiration:** [pcb-inspector](https://github.com/takzen/pcb-inspector) and
  [kicad-happy](https://github.com/aklofas/kicad-happy) feature areas. The
  kicad-happy EMC guide lists `DC-003` for a decoupling capacitor that is too
  far from a via. Its example category motivates a second measurement; no
  universal via-distance threshold or candidate code is adopted.
- **Evidence and check:** For each mapped IC supply/return pad pair and its
  candidate capacitor pad pairs, check footprint identity, fitted state,
  expected net assignments, native copper connectivity, and exact transformed
  KiCad pad centers. Measure Euclidean center-to-center distance from IC supply
  pad to capacitor supply pad. Compare using integer squared nanometers to the
  project-authored micrometer threshold. `selection: any` requires one candidate;
  `selection: all` requires each candidate. An optional
  `max_return_via_distance_um` measures each capacitor return pad to the nearest
  via explicitly listed in that pad's native copper-connectivity component;
  the configured candidate policy must meet both limits on the same capacitor.
  With no supply-pad threshold, retain the measured distances as a review
  finding. No via requirement is inferred when the optional limit is absent.
- **Boundary:** These Euclidean distances do not establish a low-inductance
  loop, via-to-plane quality, correct value, or adequate decoupling. The via
  measure excludes nearby vias outside the pad's native copper component.
  Native DRC and schematic connectivity remain separate. A direct plane
  connection may be valid without a via; projects should configure this limit
  only when reviewed layout guidance requires it.
- **Fixtures:** Synthetic close and distant capacitors, multiple IC supply pins
  sharing one bank, exact threshold boundary, wrong-net and disconnected
  candidates, DNP and wrong-footprint controls, nearby unconnected vias, exact
  connected-via distance boundaries, and a rotated pad measured by native KiCad
  10.0.0 and 10.0.5 probes. Repeated native snapshots are identical; moving
  the connected via across the project limit produces a source-bound fault.
- **Evidence locator:** The lint report names the board hash, native snapshot
  path and hash, probe hash, exact KiCad version/image, mapped pads, selected
  capacitors, connected via identity/count, and both measured distances.
  Receipts live under ignored `build/`.
- **Fixtures:** The native synthetic board includes a GND via connected to the
  mapped capacitor return pad. Its control is exactly 1000 um from the pad; a
  source-only coordinate mutation moves it to 2000 um and must produce
  `INCOMPLETE`. Both cases repeat under pinned KiCad 10.0.0 and 10.0.5.
- **Determinism:** LINT-080 compares an authored 100 µm threshold's
  one-nanometer over-limit candidate with its exact-boundary control across
  three independent Python hash seeds. This checks typed-report stability; it
  adds no native export or public-board applicability result.
- **Boundary:** A passing project threshold is a placement screen selected by
  that project. It does not establish loop inductance, capacitor value or bias
  derating, resonance, transient performance, or manufacturing quality.

#### LINT-021 — Mapped net minimum track-width screen

- **Status:** Implemented as `pcb.minimum_track_width`; review by default,
  with project-authored `review`, `block`, `off`, and exact-ignore decisions.
- **Inspiration:** [pcb-inspector](https://github.com/takzen/pcb-inspector).
- **Evidence and check:** A PCB project's `design_lint.pcb_track_width_map`
  names exact nets, project-authored minimum micrometer widths, and each
  requirement's basis. Compare every native KiCad track item's integer
  nanometer width with the configured minimum. Findings retain the track UUID,
  layer, exact width, and endpoints. A net with no track items has incomplete
  coverage because it may be zone-only or unrouted. One threshold applies
  across all copper layers for each mapped net.
- **Boundary:** This check does not inspect zone geometry or via bottlenecks,
  prove track connectivity, infer a current requirement, or calculate
  ampacity, temperature rise, pulse limits, or electrical performance. Native
  DRC and any project-specific copper calculation remain separate evidence.
- **Fixtures:** Native 250 um segment at the exact 250 um boundary and below a
  251 um screen; unrelated-net exclusion; zone-only/unrouted incomplete
  coverage; review, block, off, exact-ignore, and repeated-snapshot controls
  using synthetic boards on pinned KiCad 10.0.0 and 10.0.5. CLI and MCP parity
  use the same typed service and snapshot.
- **Done:** Typed project map, deterministic native measurements, explicit
  incomplete coverage, source-bound reports, policy controls, synthetic
  fault/boundary fixtures, CLI/MCP parity, and catalog/docs are implemented.
  Current and thermal calculation remains deferred until its project inputs
  and adopted model can be validated independently.

#### LINT-022 — Differential-pair physical constraint evidence

- **Status:** Implemented v1 as `pcb.differential_pair_rule_coverage`; review
  by default, with project-authored `review`, `block`, `off`, and exact-ignore
  decisions. Independent pair-geometry validation remains deferred.
- **Inspiration:** [pcb-inspector](https://github.com/takzen/pcb-inspector).
- **Native reference:** The
  [KiCad 10 PCB Editor manual](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html) documents custom
  width, pair-gap, length, skew, and uncoupled-length constraints. Netclass widths are routing
  defaults rather than DRC limits; tuning-profile geometry violations default to Ignore.
- **Head-to-head evidence:** A public synthetic pair was checked with the
  KiCad 10.0.0 and 10.0.5 digest-pinned images. With authored native rules,
  both versions reported the compliant pair without pair-constraint
  violations; separate width, gap, skew, and uncoupled-length faults produced
  the corresponding native DRC types (`track_width`,
  `diff_pair_gap_out_of_range`, `skew_out_of_range`, and
  `diff_pair_uncoupled_length_too_long`). An identical excessive-gap board
  without authored pair rules produced no pair-constraint finding. The small
  track-only fixture also has two unrelated dangling-end warnings; all cases
  had zero unconnected items. A later KiCad 10.0.6 run also checked a
  byte-identical skew fault without its `.kicad_dru`: native DRC emitted no
  pair-rule finding, while the configured copy emitted `skew_out_of_range`.
  This is a synthetic native-tool comparison, not a project-board result.
- **Reproducible fixtures:**
  [`tests/fixtures/design_lint/differential-pair/`](../tests/fixtures/design_lint/differential-pair/README.md)
  retains the seven boards, authored rule files, pinned image digests, run procedure, and expected
  native finding types.
- **Disposition:** Do not add an independent pair-geometry checker solely to
  repeat native DRC. The coverage rule compares an independently authored
  pair/constraint inventory with the project's source-bound `.kicad_dru`,
  `.kicad_pro` ignored severities, and native DRC receipt. It reports exact
  covered, missing, mismatched, duplicate, ignored, unsupported, and
  unrecognized-pair cases. Do not infer that every similarly named pair needs
  the same limits.
- **Boundary:** Geometric match is not impedance or signal-integrity
  qualification; allowed width, gap, skew, and uncoupled length are
  interface- and stack-up-specific. A clean native report without an authored
  constraint is not evidence that the pair meets its intended requirement.
- **Fixtures:** Exact synthetic rules cover width, gap, skew, and uncoupled
  bounds; missing files, wrong-pair selectors, wrong bounds, duplicate rules,
  globally ignored checks, custom rules with `(severity ignore)`, unsupported
  severity clauses, unsupported units, and unsupported net suffixes remain
  visible. The native DRC matrix above verifies that KiCad 10.0.0 and 10.0.5
  catch each corresponding geometry fault when its authored rule exists.
- **Done for v1:** Typed pair map, exact rule parser, source-bound board,
  project settings, rule file and native DRC evidence, policy modes, catalog,
  synthetic fault/control coverage, and CLI/MCP parity. Future work can expand
  supported KiCad condition expressions only with focused fixtures; the audit
  must keep unsupported syntax incomplete rather than guessing equivalence.

#### LINT-023 — Switching-current loop and return-path review

- **Status:** Implemented as the opt-in `pcb.switching_loop_geometry` review
  rule. Synthetic fault/control cases run in unit tests. Hosted native lanes
  exercise connected F.Cu and In1.Cu planes, a split In1.Cu plane, and the exact
  measured area boundary under KiCad 10.0.0 and 10.0.5. Not field-validated.
- **Inspiration:** [pcb-inspector](https://github.com/takzen/pcb-inspector).
- **Evidence and check:** A project-authored ordered list of exact board pads
  supplies the loop polygon. The native KiCad 10 snapshot records actual
  enabled copper layers, transformed pad centers, DNP state, zone identities,
  and filled-island indexes. The rule checks exact footprint/net/fitted state,
  computes an integer shoelace area through the ordered pad centers, compares
  an optional project-authored limit, and requires all return pads to share
  one filled zone island on the declared same-net stack layer.
- **Boundary:** The pad-center polygon does not follow routed trace centerlines
  or zone contours and is only a geometric proxy. The layer-specific same
  island requirement is intentionally strict; a connected return made from
  multiple zones and tracks may remain incomplete. The check cannot establish
  parasitics, emissions, stability, thermal behavior, or electrical
  performance. Hardware or simulation validation remains a separate record.
- **Fixtures:** Synthetic compact and enlarged loop polygons, exact area
  threshold, split filled islands, valid inner-layer return plane, absent
  stack layer, missing stack evidence, and configurable review/block/off/exact
  ignore behavior. The CLI/MCP parity case uses the same source-bound snapshot.
  Hosted native controls use a synthetic four-pad polygon with connected F.Cu,
  connected In1.Cu, and split In1.Cu return planes. Each capture repeats to
  verify deterministic centers and area; connected and split results retain
  their native zone identities. The exact area boundary passes and a one-um2
  lower authored limit flags the same measured geometry.
- **Next:** Do not treat the ordered pad list as a routed path. Before adding a
  comparison, require an explicit per-edge interpretation and prove that the
  native geometry resolves it uniquely. LINT-039 tracks this work. A project
  must select and review any resulting measurements; the existing pad-center
  proxy remains a separately named approximation.

#### LINT-024 — Schematic near-miss and drawing-quality diagnostics

- **Status:** Eleven opt-in review rules run through the shared design-lint
  service, CLI, and MCP. Each catalog default is `off`; project policy can
  enable, block, or ignore each rule independently. LINT-044 now reports
  geometry coverage per enabled rule, so an unsupported text shape does not
  make an unrelated wire-body check appear incomplete.
- **Supported boundary:** Recursively scans project-local hierarchical KiCad
  schematics at file-format version `20231120`, for exact KiCad `10.0.5` and
  `10.0.6`. Each reachable source must appear in the native snapshot's source
  hashes, and each placed symbol must map uniquely through KiCad's project and sheet
  instance path. A reused child file is scanned once per instance. The report
  binds a canonical source-tree digest and every source/instance mapping. It
  supports single-unit, single-conversion symbols, orthogonal rotations, and
  x/y mirrors. Pin geometry rules examine only pins explicitly marked
  unconnected by the matching native netlist and skip explicit no-connect
  markers. Label localization uses parsed supported symbol pin tips to avoid
  treating a label on a pin as detached. The scan reports `PARTIAL` when it
  cannot interpret encountered symbol geometry and hashes the schematic
  bytes. This is a bounded geometry pass, not a complete schematic
  connectivity parser. Missing child sources or ambiguous instance references
  leave coverage blocked or partial.
- **Exact-version matrix (2026-10-03):** The full
  `tests/test_schematic_geometry.py` suite passed 77 tests on each supported
  image. KiCad 10.0.5 used the `ghcr.io/kicad/kicad:10.0.5` image at digest
  `fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c` and
  completed in 82.457 seconds. KiCad 10.0.6 used the `kicad/kicad:10.0.6`
  image at digest
  `18693567392b80da435f9fa952ce3a3e534c66eb5a6033f5b9c80aa3b19dd3ec` and
  completed in 80.761 seconds. Both lanes ran with networking disabled,
  a read-only container root, and a temporary-fixture-only writable mount.
  The text metrics remain calibrated from the 10.0.6 image; the same native
  SVG comparisons pass under 10.0.5. The source scanner also accepts 10.0.5
  and rejects 10.0.0. Receipts and logs are under ignored
  `build/ci/native-schematic-geometry/` and
  `build/ci/native-geometry-matrix-local/`.
- **Connector body-overlap boundary replay (2026-10-05):** The full geometry
  suite passed 79 tests on KiCad 10.0.5 (83.532 seconds) and 10.0.6
  (85.964 seconds), using the digest-pinned images above with networking
  disabled, a read-only container root, and a temporary-fixture-only writable
  mount. A synthetic pair of passive connector contacts share `/SIGNAL`; each
  wire reaches its contact inside the supported body rectangle, producing
  review candidates for J1 and J2. A body-clear variant preserves the same
  10.16 mm body dimensions and moves the edge to the pin tip. Native component/
  pin assignments, nets, and wire geometry match while both candidates clear.
  Both versions confirm J1.1 and J2.1 on `/SIGNAL` and identical
  ERC signatures between variants. The standalone test has no project symbol
  library table, so the matching signatures contain only `lib_symbol_issues`
  warnings; no connectivity or off-grid ERC warning is present. This records
  an intentional candidate class, not a false-positive rate. The rule remains
  default-off.
- **Evidence:** An earlier complete `tests/test_schematic_geometry.py` native
  regression run passed all 39 then-existing tests against KiCad 10.0.6
  (213.092 seconds through the exact container image). The added text-wire
  fault/control regression separately passed in 13.469 seconds against that
  same pinned image. Synthetic fault
  and connected-control fixtures pass
  native KiCad 10.0.6 netlist/ERC parity. Across all 12 orthogonal
  rotation/mirror combinations, transformed pin tips match native ERC
  coordinates and the fault pins remain open in native netlists. The original
  endpoint rule and the wire-interior rule both have synthetic coverage across
  those transforms. The near-pin endpoint rule also has synthetic fault
  coverage and a native netlist/ERC regression across all 12 rotation/mirror
  combinations. The regression passed with exact KiCad 10.0.6 from the official
  `kicad/kicad:10.0.6` linux/amd64 image
  (`sha256:18693567392b80da435f9fa952ce3a3e534c66eb5a6033f5b9c80aa3b19dd3ec`).
  The fault
  netlist leaves `R1.1` unconnected; ERC reports
  `pin_not_connected` and `unconnected_wire_endpoint`. The original rule
  localizes a wire endpoint lying along the pin segment. A second rule finds
  an unconnected pin tip lying in the strict interior of a wire segment. Its
  paired control adds one junction marker; KiCad then places `R1.1` on
  `/CONTROL_NET` and emits no pin-disconnected ERC finding. This new candidate
  gives ERC's open-pin finding a more specific geometric explanation. It is
  review evidence, not an assertion of author intent or a repair instruction.
  A separate explicit no-connect marker on the same wire-crossing pin is a
  valid control: the local marker-exclusion unit test passes, and a new native
  KiCad 10.0.6 test also checks netlist isolation and ERC suppression while
  exercising the marker-aware geometry predicate with the pin supplied as
  unconnected. The full geometry suite, including this control, passes all 77
  tests in 88.962 seconds against the digest-pinned KiCad 10.0.6 image.
  A third rule reports an unattached local/global/hierarchical label anchor
  within 1.27 mm of wire endpoints, while excluding labels that touch any wire
  or pin tip. KiCad 10.0.6 ERC reports `label_dangling` for the synthetic
  near-endpoint fault and none for the attached control; the rule improves
  localization rather than adding electrical detection. The fixed search
  radius can include unrelated nearby endpoints and does not encode intent.
  A fourth rule reports a wire endpoint within 0.5 mm of a native-unconnected
  pin tip, excluding explicit no-connect markers and endpoints already on the
  pin segment. Synthetic boundary and exclusion controls pass, along with
  project-policy and CLI/MCP parity regressions. The exact-version native ERC
  comparison confirms an open pin and dangling-wire diagnostic for the fault;
  the geometric candidate explains where the wire endpoint nearly reaches the
  pin. This is review localization, not a demonstrated new detection. A fifth
  rule reports strict interior/interior orthogonal wire
  crossings without a junction marker, with the exact coordinate and wire
  UUIDs. Its synthetic candidate and explicit-junction/endpoint controls pass.
  An intentional unconnected crossing is valid KiCad usage and produces the
  same candidate; this known false-positive class keeps the rule off by default.
  Native KiCad 10.0.6 reports `wire_dangling` and `unconnected_wire_endpoint`
  diagnostics on both the fault and marked control. The local crossing rule
  identifies the exact unmarked intersection coordinate and wire UUIDs only in
  the fault fixture, adding localization rather than electrical detection.
  The sixth rule reports a wire endpoint on the strict interior of another wire
  without a junction marker. In its synthetic KiCad 10.0.6 fault, the native
  netlist keeps `R1.1` on `/CONTROL_NET` and `R1.2` on
  `unconnected-(R1-Pad2)`; the marked control puts both pins on
  `/CONTROL_NET`. ERC reports an open pin and the unconnected endpoint in the
  fault, and neither in the control. The geometry finding localizes a likely
  missing T-junction but still cannot establish whether the branch was meant
  to connect. CLI/MCP parity and independent review/block/off/ignore behavior
  are covered. A separate isolated-wire fixture confirms exact KiCad 10.0.6
  ERC already reports `wire_dangling` and `unconnected_wire_endpoint` with the
  wire UUID and location; the geometry pass adds no candidate. No custom
  dangling-wire rule was added because it would duplicate native evidence.
  A repeated-child-sheet fault/control pair confirms that exact KiCad 10.0.6's
  native netlist expands a shared channel into separate `R1` and `R2`
  references, separate hierarchical nets, and two unconnected pin assignments
  in the fault; the junction-marked control connects both instances. Fault ERC
  identifies the shared source pin only once. The recursive scan maps the
  shared source pin to both exact instance paths and emits separate geometry
  candidates. End-to-end CLI/MCP parity verifies root and child hashes,
  distinct source bindings and finding fingerprints, plus separate `R1.2` and
  `R2.2` pin-localization findings against source-bound synthetic netlist
  evidence. The exact-version native regression separately checks the
  repeated-sheet connectivity and ERC fault/control.
  Separate CLI/MCP parity regressions verify source and netlist hash binding
  and project opt-in for each rule. A seventh graphical-only rule reports pairs
  of top-level free-text objects with source insertion anchors within 0.001 mm.
  Native KiCad 10.0.6 ERC produces the same diagnostics for coincident and
  separated text controls. The source-bound finding includes both text strings,
  UUIDs, coordinates, sheet-instance path, and source hashes. It does not
  calculate rendered glyph bounds or prove visible overlap. An eighth rule
  measures a bounded standard-font envelope for distinct, horizontal, centered,
  single-line free text. Its 95 printable ASCII advances come from a synthetic
  native KiCad 10.0.6 SVG calibration using the digest-pinned
  `kicad/kicad:10.0.6` image. The tested fault has an actual native stroke-path
  intersection; its separated control has an 8.2247 mm minimum stroke-centerline
  gap. Native netlist and ERC diagnostics are identical for both. The rule
  excludes coincident anchors to avoid duplicating the existing anchor prompt.
  Plain escaped multiline text is supported using 2.0446 mm measured line
  spacing at the 1.27 mm reference size, scaled with font height. Custom faces,
  bold/italic/thick, formatted, non-ASCII, explicitly justified, and rotated
  text leave geometry coverage partial. The bounding
  envelope can still warn when individual character strokes do not collide.
  A ninth rule, `schematic.free_text_over_wire`, clips native schematic wire
  centerlines against that same bounded free-text geometry. It reports only
  when the wire remains inside the envelope by at least a 0.12 mm edge guard
  and overlaps for at least 0.2 mm. The fault and clear-control fixtures use
  the same source wire and differ only in text placement. Exact KiCad 10.0.6
  SVG confirms zero stroke-centerline distance in the fault and 7.9495 mm in
  the control. Native netlist component/pin assignments and nets are identical
  after excluding the project-specific `Sheetfile` property; all three ERC
  violation signatures are identical. This is a drawing review signal, not an
  electrical-connectivity finding. The rule ignores buses, labels, symbol
  fields, pin names/numbers, and symbol graphics; intentionally placing a note
  over a wire can produce a valid review candidate.
  A tenth rule, `schematic.wire_through_symbol_body`, bounds supported embedded
  symbol graphics and reports wire centerlines that remain at least 0.2 mm
  inside the axis-aligned envelope for 0.3 mm or more. It supports rectangle,
  polyline, Bezier, and circle graphics for single-unit, single-conversion
  symbols, including orthogonal rotations and x/y mirrors. In the synthetic
  fault/control pair, only the fault has a body-overlap candidate. Native
  KiCad 10.0.6 component/pin assignments, nets, and six ERC violation
  signatures are identical after normalizing project-specific `Sheetfile`
  metadata. The rule improves drawing localization and does not establish
  electrical intent. A bounded envelope can include empty areas between
  disjoint or curved primitives, and intentional wire crossings remain review
  candidates. Arcs, text graphics, and unsupported symbol units leave geometry
  coverage partial.
  An eleventh rule, `schematic.free_text_over_symbol_body`, intersects a
  supported top-level free-text envelope with a supported symbol-body envelope.
  It applies a 0.1 mm text guard, 0.15 mm body guard, and 0.1 mm² minimum
  overlap. Exact KiCad 10.0.6 synthetic fault/control SVG confirms the fault's
  text strokes lie inside the resistor body region and the moved control is
  clear. Native net assignments and three ERC violation signatures are
  identical. This is a localized drawing prompt; labels, fields, and
  unsupported text remain outside its scope, and axis-aligned bounds can
  include empty space.
- **Typography boundary evidence:** Synthetic controls cover custom face, bold,
  italic, thick stroke, vertical or mirrored justification, rotation, formatted
  text, and a non-ASCII glyph. These remain partial with no text-overlap
  candidate. Exact KiCad 10.0.6 accepts all eight variants; their native
  component identities, pin/net assignments, and ERC signatures match the
  standard-text baseline. Horizontal `left` and `right` justification are now
  supported; native SVG controls confirm both anchor directions and containment
  of every rendered stroke by the calculated text envelope.
  A separate three-line plain-text fixture measures 2.0446 mm baseline spacing
  at 1.27 mm font height and verifies that the heuristic box contains native
  SVG strokes. Its wire-crossing fault and clear control preserve identical
  native netlist/ERC signatures. A literal source newline inside a quoted
  S-expression remains unsupported; serialized single-backslash `\\n` is a
  line break, while doubled-backslash `\\\\n` is literal text.
- **Public-example trial (2026-09-29; multiline follow-up):** At public template commit
  [`ed89536`](https://github.com/search?q=ed89536f0dbbcb013145af2994fef41b2250143e&type=commits),
  five schematic-only examples were copied to a temporary directory and
  exported with the exact KiCad 10.0.6 image. The projects declare KiCad
  10.0.0 or 10.0.5, so this was a cross-version research run, not project
  acceptance evidence. The geometry pass found one wire-through-symbol-body
  candidate in each of the Arduino Uno and Raspberry Pi status LED examples.
  Native SVG review confirmed that both wire centerlines cross the visible J1
  rectangle on the way to a pin. This confirms the bounded geometric predicate
  and its review usefulness; it does not decide whether the drawing convention
  was intended or establish an electrical defect. After adding measured plain
  multiline support, all five unchanged source trees were rescanned: the
  multiline limitation disappeared, while each project remained `PARTIAL`
  because all five use explicit text justification outside the measured model;
  two also contain non-ASCII glyphs. The two symbol-body candidates were
  unchanged. These examples do not establish false-positive or missed-fault
  rates, and reviewer time was not measured. The two symbol-based examples
  also reported missing-library ERC items in this isolated container; those
  ERC results were excluded from the comparison. A separate static screen of
  the sixth project, `status-indicator-harness-interface`, at the same public
  commit recorded zero candidates for the eleven geometry result groups. Its
  per-source tree digest was
  `07e05a85f1f5a6fc4a302c85c840e10f875bfcb0c5220c480b2a48f6b1743a80`.
  This screen supplied no native unconnected-pin set, so the three
  pin-specific rules were not evaluated; the text-overlap, text-over-wire, and
  text-over-body rules remained partial because the example uses explicit text
  justification and non-ASCII glyphs. The example declares KiCad 10.0.5 while
  the scanner currently supports 10.0.6. This cross-version source scan ran no
  native export or ERC, and zero candidates are not evidence of precision or a
  clean design. This scan predates the horizontal-alignment extension below;
  the 2026-10-05 follow-up rescan after that change is recorded below. No
  public project source was copied into this repository.
- **CI regression lane (2026-09-29):** Package acceptance now sets
  `KICAD_RUN_NATIVE_SCHEMATIC_GEOMETRY=1` and runs the full
  `test_schematic_geometry.py` suite through the official amd64 KiCad 10.0.6
  image pinned above. With the polyline, rectangle, and circle crossing
  control, all 64 synthetic and native tests passed in 69.858 seconds; image
  pull, container start, and shutdown also passed, for a 71.8-second lane on
  this checkout. That run predates the new no-connect-under-wire native test;
  rerun the lane before recording its result.
  The container disables networking, has a
  read-only root, and can write only in ignored
  `build/ci/native-schematic-geometry/tmp/`; receipts and test output remain
  under ignored `build/ci/`. Native comparisons bind component/pin maps and
  net assignments while excluding temporary source-path metadata.
- **Graphical-only control (2026-09-29):** A synthetic schematic places a
  polyline, rectangle, and circle across an assigned wire. The geometry scan
  returns no candidate in any of its eleven rule groups. Exact KiCad 10.0.6
  SVG checks confirm each primitive renders; component/pin maps, native net
  assignments, and ERC signatures match the same schematic without them.
  This control does not measure a false-positive rate for other graphic
  primitives or public schematics.
- **Horizontal text alignment follow-up (2026-09-29):** The measured text
  envelope now accepts exactly one explicit horizontal alignment option,
  `left` or `right`; default text remains centered. Synthetic fault and clear
  controls for both alignments pass through KiCad 10.0.6. Their native SVG
  strokes stay inside the predicted envelopes, and native netlist and ERC
  signatures match between fault and control. The full geometry lane passed
  all 66 tests in 75.974 seconds in the digest-pinned image. Vertical alignment,
  mirrored text, combined options, and unknown justification tokens still leave
  enabled text rules partial. The public-template samples were subsequently
  rescanned after this change; see the 2026-10-05 record below. This rescan
  updates coverage evidence, not false-positive evidence.
- **Empty justification and em-dash follow-up (2026-09-30):** The exact
  KiCad 10.0.6 SVG exporter renders an empty `(justify)` field with the same
  text anchor and stroked paths as omitted justification. The scanner now treats
  that empty field as centered, while vertical, mirrored, combined, and unknown
  options remain unsupported. A native synthetic text object measures the
  U+2014 em dash at 1.4506 mm advance at the 1.27 mm reference size; its native
  stroke lies inside the existing calibrated vertical envelope. The packaged
  metric schema is version 3 and covers 95 printable ASCII characters plus
  this glyph. The digest-pinned geometry suite passed with both the native
  placement comparison and glyph-bound check.
- **Electrical-glyph follow-up (2026-09-30):** A synthetic one-character
  schematic was exported with the exact KiCad 10.0.6 image recorded above to
  measure U+00B0 degree, U+00B1 plus/minus, U+00B5 micro sign, U+00D7
  multiplication sign, and U+03A9 ohm sign. Their 1.27 mm advances are
  recorded in schema v4 alongside the existing 95 printable ASCII characters
  and U+2014 em dash. The five native SVG stroke groups fit the existing
  vertical envelope. A portable fault/control/translation fixture now checks
  overlap of `10µF ±5V` with `4.7Ω` and a separated control. Other Unicode,
  custom font styles, markup, literal source newlines, and rotated text remain
  outside the measured subset; plain KiCad escaped line breaks remain
  supported. The exact KiCad 10.0.6 geometry suite passed all 76 tests in
  77.382 seconds, including SVG text lengths, stroke-envelope bounds, and the
  new electrical-glyph overlap fault/control.
- **Read-only public-template rescan (2026-09-30):** At public template commit
  [`ed89536`](https://github.com/search?q=ed89536f0dbbcb013145af2994fef41b2250143e&type=commits),
  all six schematic examples were scanned with native unconnected-pin sets
  exported from the digest-pinned KiCad 10.0.6 image. Each scan returned
  `COMPLETE`, with zero unsupported cases across the eleven geometry rule
  families and zero native unconnected pins. The Arduino Uno and Raspberry Pi
  status LED examples retain the two wire-through-symbol-body candidates; the
  other nine groups are empty. No free-text overlap, free-text-over-wire, or
  free-text-over-body candidates were reported. The project manifests declare
  KiCad 10.0.0 or 10.0.5, so this 10.0.6 run is cross-version research rather
  than acceptance for those projects. Their schematics were mounted read-only;
  generated netlists lived in temporary storage, and no project sources were
  copied into this tooling checkout. This small sample demonstrates improved
  coverage for the empty-justify and em-dash cases, not heuristic precision,
  recall, electrical correctness, or manufacturing readiness.
- **Public-template wire/body triage (2026-09-30):** A read-only render and ERC comparison on the
  same template revision examined the Arduino Uno and Raspberry Pi status LED examples. Both produce
  one `J1` wire-through-body candidate for the same geometry: a wire from `(60.96, 73.66)` to
  `(68.58, 73.66)` crosses the `StatusLedTraining:Header_1x02` body envelope from `(60.96, 72.39)`
  to `(66.04, 80.01)`, overlapping it by 4.68 mm. The schematic source SHA-256 values are
  `c2d8442412cb251472a08df31109b8633655aaa375598abbb2e7bbc00961fa1b` and
  `b99ad47237f3f36aaefa3a2ed08e3dae12d9131c7f9a52355401c9d5bada3fba`. SVG and ERC exports used the
  digest-pinned KiCad 10.0.6 image recorded above, with the full public template mounted read-only
  and networking disabled; each ERC report had zero violations. This is one unique geometry repeated
  in two fixtures, not two independent samples. ERC cleanliness does not settle whether the drawing
  overlap is intentional. With no author intent record, count it as unresolved and exclude it from
  both confirmed findings and false-positive rates. The reports stayed under `/private/tmp`; no
  project source was copied into Tooling.
- **Exact-version re-screen (2026-10-03):** Repeated the two-project check with each
  project's declared `ghcr.io/kicad/kicad:10.0.5` image with digest
  `sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c` at public checkout
  `ed89536f0dbbcb013145af2994fef41b2250143e`. The checkout was mounted read-only,
  networking was disabled, and only generated netlist/ERC receipts were written under ignored
  `build/`. Both projects produced byte-identical repeated netlist and ERC exports and zero ERC
  violations. Their native netlists contain no unconnected pins. The KiCad 10.0.5 geometry scans
  were `COMPLETE` with byte-identical repeated scanner output; each found one J1 wire-through-body
  candidate for the same layout, clipped to `(61.16, 73.66)`–`(65.84, 73.66)` for 4.68 mm overlap.
  Each of the other ten result groups was empty. This confirms one unresolved layout repeated in two
  examples, not two independent candidates and not a false positive. The machine-readable receipt
  is `build/cohort-geometry-exact-20261003/public-geometry-screen.json`, SHA-256
  `1cfa6c290c91c20bc16fe9604f9105a5b143bdf17a9683b735991779a511b74c`; it contains source,
  manifest, native-export, and scan hashes. The source files remain only in the public checkout.
- **Parser rescan after text-alignment support (2026-10-05):** Rechecked all six
  schematic projects at the same clean public-template commit
  `ed89536f0dbbcb013145af2994fef41b2250143e`. The current geometry parser
  returned `COMPLETE` with no unsupported cases for all six; the earlier text
  coverage gaps from horizontal justification are now supported. The only
  candidates were the same two `schematic.wire_through_symbol_body` findings
  in the Arduino Uno and Raspberry Pi status LED schematics; the other ten
  result groups were empty. The previous exact KiCad 10.0.6 native screen at
  this source commit recorded zero unconnected pins, so the parser was given an
  empty unconnected-pin set; this follow-up did not rerun native export, ERC,
  or SVG rendering. Source-tree and per-file hashes plus rule counts are in
  the ignored receipt
  `build/ci/lint024-public-template-rescan-20261005-01/receipt.json`,
  SHA-256 `e37d9b7b4532fea97ebbdf6cd062b10deed93a614bd9ee9e6a15204daa845705`.
  This closes the stale text-coverage measurement only. It remains one
  unresolved wire/body layout repeated in two examples, not two independent
  samples or a confirmed false positive. Reviewer effort and false-positive
  rate remain unmeasured; no public source was copied into this repository.
- **Connector body-overlap boundary (2026-10-05):** The synthetic paired-
  connector case above confirms that a wire terminating at a passive pin
  inside a supported body rectangle can be a legitimate drawing and still
  match `schematic.wire_through_symbol_body`. Both connector pins have native
  assignments on the same `/SIGNAL` net. KiCad 10.0.5 and 10.0.6 preserve those
  assignments and identical ERC signatures when the body is moved clear of
  the wires; only the isolated-runner symbol-library warnings remain. This is
  an intentional review-candidate class, not a confirmed false positive on
  either public example. Keep the rule opt-in and do not infer intended
  connector wiring from body geometry.
- **Legacy sheet-property spelling follow-up (2026-10-07):** A read-only
  parser-compatibility probe of the public
  [SH-ESP32 hardware project](https://github.com/hatlabs/SH-ESP32-hardware)
  at commit `167981ac8c3e1a7a0104c20cf9b487b4d722fc60` uses schematic format
  `20231120` with KiCad 8's `Sheetname` and `Sheetfile` property spellings.
  The root schematic SHA-256 is
  `9d88ec492742568f84ae65fd64ef30a409b0968342480b0a33ba04b0247d0b52`; the
  traversed source-tree SHA-256 is
  `3006095773aa86b59cbcbbe718d01187331052ed4d8b0c55357c5997affbc3eb`.
  The recursive scanner previously rejected these; it now accepts either the
  legacy spellings or KiCad 10's spaced names, and rejects duplicate aliases.
  A synthetic repeated-sheet regression binds the root plus both child
  instances. A source-only scan of this public design traversed 10 instances
  but remained `PARTIAL`; it emitted 20 unmarked-crossing, 5 wire-through-body,
  and 2 coincident-text-anchor candidates. It had no native export/ERC or
  native-unconnected-pin list, so pin-local rules were not evaluated. The
  source was made with KiCad 8 while the validated native matrix is KiCad
  10.0.5/10.0.6. The project `LICENSE.md` names CC BY 4.0 while its
  schematic title block names CC BY-SA 4.0, so retain it only as a temporary
  parser probe. Do not count its candidates as findings, false positives, or
  review-effort evidence; no project source was copied into this repository.
- **Next:** Keep all eleven rules default-off and opt-in. Measure false
  positives and reviewer effort on non-proprietary examples with complete
  support for the selected rule. Track each unique candidate layout separately;
  only an author-reviewed intentional overlap counts as a confirmed false
  positive, and unresolved intent stays out of the rate. Measure reviewer
  effort only in an observed review and keep it distinct from native ERC
  agreement. Current font evidence covers plain printable ASCII plus U+00B0,
  U+00B1, U+00B5, U+00D7, U+03A9, and U+2014 at 1.27 mm reference size with
  default/empty, left, or right placement; vertical or mirrored justification,
  formatting, other Unicode glyphs, and unsupported styles remain coverage
  gaps. Measure fault/control behavior for further glyphs before expanding the
  resource.
  Four-way interior crossings and
  T-shaped endpoint contacts have separate fault/control cases. The free
  dangling-wire trial found no incremental geometry value beyond native ERC.
  Keep unresolved, missing, or ambiguous sheet files and instance-reference
  mappings visible as blocked or partial coverage. A project may choose
  `block` only through an explicit rule override.
- **Inspiration:** [kicad-sch-lint](https://github.com/rashuky/kicad-sch-lint)
  and [KiDiff](https://github.com/INTI-CMNB/KiDiff).
- **Evidence and check:** Implemented rules now cover a near-pin wire endpoint,
  a wire endpoint along the pin segment, a pin tip on wire interior, and a label
  close to a wire endpoint, plus T-shaped endpoint contacts without a
  junction marker. The native-unconnected pin requirements and exact KiCad
  boundary are part of each applicable predicate. A synthetic repeated-sheet
  root and shared child fault/control pair exercise hierarchy coverage: the
  native netlist has separate open-pin assignments for R1 and R2 in the fault
  and connected instance-local nets in the control, while fault ERC reports
  one pin violation against their shared source geometry. Recursive scanning
  binds each project-local source to exact instance paths; CLI/MCP parity
  verifies two distinct findings from one reused child. Missing or ambiguous
  mappings produce partial coverage. The text/body collisions are now
  implemented as graphical review aids; source revision differences remain a
  candidate.
  Resolve symbol transforms and pin-tip coordinates against the exact
  supported KiCad version, and attach sheet, coordinate, object IDs, implicated
  netlist pins where available, and localized visuals. Compare every
  electrical symptom with native ERC so duplicates are recorded as better
  localization rather than new detection. The unmarked-crossing advisory
  cannot tell a missed junction from an intentional crossover; exact project
  ignores and reviewer decisions preserve that distinction.
- **Boundary:** Visual proximity is not electrical connectivity. ERC remains
  authoritative for native diagnostics; this feature improves detection or
  review localization only when demonstrated. Rendered appearance cannot
  override the KiCad netlist. Never auto-connect or rewrite schematic geometry
  in this check. The candidate tool also offers fixes; its write path is out of
  scope for this analyzer.
- **Fixtures:** Covered: a wire endpoint just short of a pin tip with boundary
  and exclusion controls; endpoint along the pin segment; pin tip on wire
  middle with and without a junction marker; an explicit no-connect marker on
  the wire-crossing pin with native isolation/ERC parity; near and
  attached labels; and all 12 rotation/mirror combinations for the near-pin
  geometry. A separate
  T-junction fault/control pair checks native netlist pins, native ERC, marker
  suppression, and CLI/MCP parity. A standalone dangling-wire fixture records
  native ERC coverage without a duplicate geometry candidate. A repeated
  child-sheet fault/control pair confirms instance-distinct netlist refs and
  pins, recursive source-tree binding, missing-reference partial coverage,
  project-local path containment, and CLI/MCP parity. One graphical-only
  control verifies visible polyline, rectangle, and circle crossings do not
  become electrical wire candidates or change the native netlist/ERC. Other
  graphical primitives and crowded valid drawings remain for review.
- **Done when:** Exact-version tests cover the remaining geometry classes and
  supported sheet scope, native netlist/ERC behavior is checked, and no
  auto-fixes occur. Duplicate ERC findings are recorded as review
  improvement, not new detection.

#### LINT-025 — PCB return-reference and connector-ground path evidence

- **Status:** v4 adds a synthetic same-net front/back plane fault and
  through-via control to the electrical contract lane; existing LINT-025
  controls were synthetic-validated, and exact-version hosted acceptance for
  this addition is pending. It is not field-validated. It covers direct pad
  connectivity, explicit net-tie bonds, DNP state, intentional isolation,
  copper-zone identity, island counts, and exact per-pad island indexes using
  source-bound KiCad 10 `pcbnew`
  evidence and synthetic regressions. Hosted
  native CI runs alternate-layer connected/open controls, connected and split
  plane controls, fitted versus DNP net-tie controls, and separate-domain
  isolation controls through the same adapter. It also retains stable geometry-
  derived via identities, net, center coordinates, layer span, drill/diameter,
  via kind, identical-geometry multiplicity, and per-pad component membership.
  It also lists each filled island with no observed pad anchor. The catalogued
  10.0.0 and 10.0.5 images are covered by the native matrix. The new synthetic
  same-net F.Cu/B.Cu plane pair tests a missing stitch via against a one-via
  control; exact-version hosted acceptance for that addition is pending.
- **Problem:** Matching schematic nets can still lack an intended physical
  copper path due to unconnected pads, plane splits, net ties, or layout
  changes.
- **Evidence and check:** `pcb_return_paths` names each exact PCB pad and
  expected net and footprint, direct or bonded domain, and exact net-tie
  footprint/pad groups. A read-only native probe refills zones in memory and
  reports each pad's connected pad set, stable via geometry and per-pad
  component membership, directly touched zone UUID/layer identities, and each
  zone's filled-island count and pad-to-island indexes from the exact
  digest-pinned KiCad 10 image.
  KiCad's [GetConnectedItems API](https://docs.kicad.org/doxygen/classCONNECTIVITY__DATA.html)
  returns every item in a copper cluster, so the probe filters those candidates
  by the pad's copper layers and actual filled-island contact before recording
  direct zone evidence. Via IDs hash
  canonical native geometry rather than KiCad object UUIDs, which can change
  between loads. Reports include via positions and layer spans but do not infer
  route order or capacity. The island mapping intersects each filled polygon,
  preserving polygon holes, with KiCad's effective copper-pad shape. Zone
  islands without a mapped pad are recorded as unanchored-to-pad review
  evidence; that does not assert the island is electrically isolated or
  defective. Receipts bind board
  bytes, tool version/image, probe bytes, pad/net/footprint/DNP data,
  copper-zone and island observations, and native net-tie groups; archive replay
  recomputes findings
  from retained data.
  The native CI control routes `J1.1` on `F.Cu` through a plated via to `J2.1`
  on `B.Cu`; its fault keeps both same-net assignments but omits the B.Cu
  connection. Both use the same exact-image adapter and assert the expected
  topology result. Receipt regressions also rehash a tampered pad-group snapshot
  and require replay to reject the changed conclusion. A successful synthetic
  runner response that changes board bytes during capture is rejected as stale;
  this fault is injected at the runner boundary so it is deterministic.
  The public [cohort copper-LVS issue #3787](https://github.com/rjwalters/kicad-tools/issues/3787)
  describes same-net GND planes with physical islands where no stitching via
  bonds the layers. That report supplied a failure-class lead only; no board or
  candidate code was copied. The new tooling-owned pair keeps the two mapped
  pads on one `RETURN` net and one zone on each copper layer, then compares no
  through via with a single through-via control. Its contract result remains
  conditional on the project explicitly requiring that endpoint path.
- **Remaining:** No synthetic path or pad-island evidence case remains in this
  item. Native isolation controls verify two declared domains remain separate
  and catch an added fitted net-tie bridge while preserving each domain's local
  connectivity. The fixture lane also proves exact net-tie groups and DNP state
  for a fitted bond and its valid-open control. The alternate-layer connected/open controls now
  retain the stable via geometry and prove whether that via belongs to each
  endpoint's native copper component. The connected fixture repeats an exact
  native load to verify stable IDs and membership. Component membership does not
  establish the ordered route through tracks or prove current capacity.
- **Boundary:** A same-net assignment is not copper continuity; geometry is
  not manufactured continuity. A declared net-tie pass verifies the native
  footprint identity, pad groups, and DNP state, but does not prove that copper
  inside the footprint physically bridges those pads. Isolated domains remain
  valid when declared.
- **Fixtures:** Connected plane; missing pad connection; split plane; same-net
  front/back return planes without and with a through-via bond; declared net
  tie; disconnected island; valid isolation; DNP bond; alternate layer
  return. The first connected-plane and split-plane controls are now included in
  the native lane for SMD and plated through-hole pads; fitted and DNP net-tie
  controls plus valid isolation and an unintended isolation bridge are included.
  A connected plane with a separate island that has no pad anchor is included.
- **Done when:** The check agrees with controlled direct, bonded, isolated,
  split-plane, DNP, disconnected-island, and alternate-layer board fixtures;
  emits exact pad and island evidence; replays from a source-bound receipt; and
  clearly stops before fabrication or first-article approval.

### P3 — Curated knowledge and optional cohort integration

#### LINT-030 — Curated engineering-rule knowledge base

- **Status:** Curated v1 in the cohort concept register below; continue adding
  concepts only when a source, applicability boundary, baseline comparison,
  and fault/control plan can be recorded.
- **Inspiration:** [ThomsonLint](https://github.com/holla2040/ThomsonLint) and
  the candidate/fork comparisons recorded in the prior tooling evaluation.
- **Work:** Extract candidate rule concepts into a source-attributed,
  applicability-tagged catalog. For each candidate, record the engineering
  claim, intended design scope, required project inputs, deterministic
  predicate if one exists, false-positive cases, evidence source, and a
  synthetic fault/control plan.
- **Boundary:** A natural-language recommendation or model-generated answer
  cannot make a release decision. Do not copy code or rule text until
  provenance and license are reviewed. Keep AI and hosted services outside
  blocking verification.
- **Done when:** Every adopted concept has an independent fixture-backed rule
  specification, provenance/license record, and a decision to implement,
  defer, or reject.

#### LINT-031 — Candidate analyzer trial and incremental-value register

- **Status:** Partial v16; read-only synthetic comparisons across seven cohort
  repositories, a first-party public-template applicability replay,
  kicad_skills schematic-rule trials, a ThomsonLint board-export trial, and
  public project review samples are recorded below. The UART peer heuristic now
  has an alternate-function net-label path, covered by synthetic fault/control
  tests and a pinned public hardware applicability screen; the screen found
  map-coverage candidates, not confirmed defects. A repeated
  public-template LED trial now records a contradictory cohort LED error on
  valid GPIO-side resistor paths. The latest
  `analog.clock_no_series_resistor` run covers seven tooling-owned schematic
  controls through the candidate's `--no-cli` fallback. A pinned kicad-happy
  single-pin connectivity follow-up covers a synthetic open-contact fault and
  common-net control, a native explicit-no-connect case, and a valid off-board
  endpoint comparison against project-authored connector coverage. Additional
  UART-peer, test-point, repeated-sheet, and off-board serial comparisons now
  measure the rule against local source-bound coverage and exact-version native
  ERC. Each trial is evaluated by feature, not by wholesale adoption. The
  off-board serial warnings duplicate native `isolated_pin_label` diagnostics;
  an authored external peer map clears the local TX/RX coverage prompts. The
  exact-version LINT-024 geometry
  re-screen and local explicit-no-connect comparison are also recorded; the
  latter preserves the peer REVIEW finding while the pinned candidate suppresses
  it. A pinned `kicad-happy` singleton-net comparison on the USB split-reference
  fault and common-reference control produced identical candidate findings on
  both inputs, adding no incremental USB reference-domain result.
- **References:** [kicad-happy](https://github.com/aklofas/kicad-happy),
  [pcb-inspector](https://github.com/takzen/pcb-inspector),
  [kilint](https://github.com/romkey/kilint),
  [kicad-sch-lint](https://github.com/rashuky/kicad-sch-lint),
  [KiDiff](https://github.com/INTI-CMNB/KiDiff),
  [kicad_skills](https://github.com/sabas0ba/kicad_skills),
  [kicad-tools](https://github.com/rjwalters/kicad-tools), and
  [ThomsonLint](https://github.com/holla2040/ThomsonLint).
- **Work:** For each useful candidate feature, record version/commit, license,
  installation friction, data boundary, supported KiCad versions, reproducible
  invocation, confirmed unique findings, duplicate findings, missed fixture
  faults, false positives, reviewer effort, and maintenance cost.
- **Boundary:** Documentation is not a local benchmark. Do not claim a
  candidate found a real defect until it is run on approved synthetic fixtures
  or otherwise authorized non-proprietary inputs.
- **Done when:** Adopt only the analyzer or knowledge item with demonstrated
  incremental detection, review, or maintenance value; retain no dependency
  solely to aggregate duplicate warnings.

##### Recorded review sample: Calcumaker UART-label applicability screen (2026-10-07)

- **Source boundary:** Read-only screen of the public `calcumaker` repository
  at pinned commit `113a2837bd155566d753635fb2cec1cb0458fa9f` ([source][calcumaker-revision]).
  Its [design document][calcumaker-design]
  describes the MCU-to-keyboard USART link and its +3V3/GND interface. The
  [hardware directory][calcumaker-hardware] declares CERN-OHL-S-2.0; its
  [license][calcumaker-license] SHA-256 is
  `253ad3f89603e728abfa60c36fbcaf8225cf55c1eab12725f19fb3d74d647f3a`.
  The selected root schematics are `calcumaker-mcu.kicad_sch`
  (`33654a8c539f58635376d16e400b3aacfe9c89163e889fdea7111687bd5b1693`)
  and `calcumaker-keyboard.kicad_sch`
  (`1657bb5bd63965eef0e046ef557605547cbda8eca3bcbd191c2b79063388562f`).
  The checkout, native exports, and trial script stayed under `/private/tmp`;
  no source or generated report was copied into Tooling.
- **Native evidence:** Exported both roots with the digest-pinned KiCad 10.0.5
  image `sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`.
  The exported native XML netlist hashes are
  `9ba5a2009d518267e450dd9e89c0edd494c282e3942da9560faf88220992ad02` for the
  75-component MCU root and
  `3f69a81eebcf5023d38d218146edfb8912817ec77d68db737cdce76040ca3a3f` for the
  227-component keyboard root. ERC emitted 155 and 198 warnings respectively,
  with no errors; these are not clean-project acceptance results.
- **Observed result:** Under an intentionally unconfigured serial-map context,
  LINT-072 emitted one REVIEW coverage candidate per root from exact `UART_TX`
  and `UART_RX` net labels. The MCU candidate is U1.16/U1.17 and the keyboard
  candidate is U1.10/U1.9; each pair shares its TX/RX nets with a fitted
  connector candidate. Neither root exports native TX/RX function names for
  those pins, and the connector pins are generic. The earlier native-function
  detector and direct-peer/reference predicates returned no candidates. The
  netlist shows +3V3 and GND on both roots; the single +3V3 family makes
  LINT-066 inapplicable, while generic serial functions keep LINT-074 outside
  its predicate.
- **Incremental-value result:** The sample demonstrates that strict labeled-net
  discovery reaches a documented interface the function-only path cannot
  classify. It does not show an omitted project requirement, wrong wiring,
  missing ground, field precision, reviewer-effort reduction, or a true positive.
  Keep the result REVIEW-only and use an independently authored peer map to
  resolve it in a real project.
- **Reproduction and disposition:** The pinned source, exact hashes, native
  exports, and a temporary screen asserting one `net_label` result per root are
  recorded in the task's external scratch area only. The checked-in synthetic
  fixture and native lane independently verify the detector and exact-map
  suppression on KiCad 10.0.0 and 10.0.5. No candidate analyzer was installed;
  no cohort code, project source, or board expectation was adopted.

##### Recorded sample: Calcumaker PCB geometry screen (2026-10-07)

- **Source boundary:** Read-only screen of the same public `calcumaker`
  checkout and pinned commit `113a2837bd155566d753635fb2cec1cb0458fa9f`.
  Its [display floor plan][calcumaker-display-floorplan] says the display PCB
  has no tracks, routed vias, or copper zones; the [hardware wiring
  review][calcumaker-wiring-review] describes KiCad 10.0.6 verification. No
  source or snapshot was copied into tracked Tooling content.
- **Native probe:** Ran the tooling-owned `native_pcb_probe.py.in` with the
  installed KiCad 10.0.6 `pcbnew` Python. The display board
  (`2078707fbe48a3a0d683cb14bbba8b94532819d502de2f390937ef191e2f0579`) had
  86 components and 699 pads; the MCU board
  (`f343795fc150aa5ac5bd68b7fb7f5391b8c813530fbefae01f51b14a21272490`) had
  75 components and 329 pads; the keyboard board
  (`9b20249b35ddfa956b9222186c94529a80edd493a146b424d280175eb4bef83a`) had
  227 components and 618 pads. Each snapshot reports zero tracks, zero zones,
  zero vias, and `zones_refilled=true`. Receipts are under ignored
  `build/public-lint-screen/`; they use the installed app rather than a
  project-selected digest-pinned container.
- **Applicability result:** These are placement-stage PCBs, not routed copper
  examples. LINT-020 requires native copper connectivity to decide whether
  mapped IC and capacitor pads form eligible candidates, so this sample cannot
  measure its connection or proximity findings. The result is inapplicable,
  not a finding or false-positive count. Re-screen only after a routed public
  revision is available; no universal distance or electrical expectation is
  inferred.

##### Recorded review sample: Antmicro CM4 Baseboard multi-UART boundary screen (2026-10-07)

- **Source boundary:** Read-only screen of the public
  [antmicro/cm4-baseboard repository][antmicro-cm4] at commit
  `d248c2921e8e7f4c9b30c96ea5f376d9b2780f1e`. The repository declares
  Apache-2.0; its `LICENSE` SHA-256 is
  `c95bae1d1ce0235ecccd3560b772ec1efb97f348a79f0fbe0a634f0c2ccefe2c`.
  The root schematic SHA-256 is
  `e56bfc07b813d5f4d6b3e7c713c2096806a800c1877a3f9ef80fed27d8d41551`, and
  the PCB SHA-256 is
  `e6d5b83d6086030c290afe2d5e7c8035408697d3611ba4f28b83fc75451cdff5`.
  The README identifies KiCad 9.x and describes a USB-C input with a USB-4xUART
  bridge. The [hardware portal](https://openhardware.antmicro.com/boards/cm4-baseboard/)
  also describes four UARTs exposed over USB, and the
  [source schematic PDF](https://openhardware.antmicro.com/imported/boards/cm4-baseboard/doc/cm4-baseboard-main-d248c292-schematic.pdf)
  shows the bridge channels. The public checkout and all exports stayed under
  `/private/tmp`; no source, project expectation, or generated output was copied
  into Tooling.
- **Native evidence:** KiCad 10.0.5 ran from the digest-pinned image
  `sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`.
  Two repeat exports had byte-identical XML; a separate earlier XML differed
  only in its volatile `<date>` field. All parsed to the same normalized
  `NetlistContract` SHA-256
  `cf012f85fea7458c2b7c05e6a609269ca8de0a15365a3ef85164bbdc53b5a8e5`:
  506 components, 393 nets, 1,821 pin assignments, and 36 DNP components. This
  is a KiCad 9-to-10 compatibility probe, not acceptance under the source's
  authored KiCad version. ERC reported 1,338 violations (13 errors and 1,325
  warnings), including 818 symbol-library and 506 footprint-link issues because
  the custom libraries were not configured; it is not a clean ERC baseline.
- **Observed result:** The native netlist has eight hierarchical labels from
  `UART.0.TX/RX` through `UART.3.TX/RX`. Their paired pins use generic function
  names such as `B1`, `B2`, `ADBUS0`, and `DDBUS1`, with active components on
  the labeled nets. The baseline `directly_linked_serial_peers` and
  `bus.serial_unmapped_peer` predicates did not identify UART participants.
  LINT-082 now recognizes four direct label-paired IC segments, while
  `bus.serial_peer_reference_review` remains quiet because each pair's explicit
  return pins are assigned to the same schematic net `GND`. The netlist also
  contains distinct `GNDD` and `Ethernet/VSS` names. No numbered-return group
  was found. These assignments do not establish the intended bonding of all
  return domains or PCB copper continuity.
- **Review load and interpretation:** With no project-authored connector map,
  the lint run returned 173 REVIEW findings, including ten
  `connector.no_connected_return` prompts on connectors whose native pin roles
  are generic or unavailable. The public source provides no independently
  approved external pinout to classify these as defects or false positives.
  This count is coverage and review workload, not a precision measurement.
  The common `GND` assignment across the four UART channels is a useful
  schematic control; it is not proof that a different return would be wrong.
- **Incremental-value result:** The screen exposed a gap in the native
  TX/RX-function predicate: explicitly UART-labeled signal pairs can cross two
  fitted ICs whose pin functions are generic. LINT-082 now adds a narrow
  label-based REVIEW path for numbered UART/USART labels and exact two-IC direct
  segments. Synthetic split/common, stale/exact map, ambiguity, DNP, incomplete
  metadata, CLI/MCP parity, and hash-seed coverage pass. The exact native fault/
  control lane now passes on KiCad 10.0.0 and 10.0.5; see LINT-082 for normalized
  netlist hashes. The public sample still shows no defect and does not establish
  that the labeled components are complete end-to-end serial peers.
- **Reproduction and disposition:** The two repeated raw XML exports had SHA-256
  `31f1125c5b04efc4f70d7c697fea415f717c7c9e232a54110e89865d9c7d9cdf`; the
  normalized report SHA-256 was
  `35a31e63e6f07eac7c1292805979535ebb643b949597a8ac16c91e3eebc4ace8` on both
  runs. Keep the export and typed evidence outside the repository. No cohort
  analyzer was installed, no code or expectation was copied, and no electrical
  conclusion was drawn from the sample.

##### Recorded review sample: public STM32 USB device schematic (2026-10-03)

- **Source boundary:** Read-only trial of
  [stm32_usb_device](https://github.com/tmilkovic51/stm32_usb_device) at commit
  `93225b1d01f7e2a995875d1724888b313120c652`. The declared CERN-OHL-P-2.0
  license file SHA-256 is
  `5c82236273f7fa5d569c152951904c711f549cb786e829bc489486c41838255f`; the
  selected schematic SHA-256 is
  `4b6eed311ab9eec4c456476c488e5cce5497fc45f490ea42f180829da58368ea`. The
  checkout and trial output stayed under `/private/tmp`; no source or output
  was copied into this repository.
- **Native evidence:** KiCad 10.0.5 used the pinned
  `ghcr.io/kicad/kicad:10.0.5` image with digest
  `fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`.
  The exported netlist SHA-256 is
  `ece16a554cd97be8efaa516d2569175f84da0a91f584db07d7287a758ac1c422`; the
  parsed netlist contains 33 components. The review run produced nine lint
  prompts. Two exact-symbol connector prompts on native `Pin_2`/`Pin_3`
  placeholders were corrected to `connector.peer_pin_assignment_divergence`,
  which treats those roles as unknown and lower confidence.
- **Interpretation:** The sample has no approved external pinout or owner
  dispositions, so the prompts are not confirmed defects and cannot measure
  precision. No seeded defect was present, so misses were not measured. Its
  single D1 is a power LED, not an output-driven LED topology; LINT-063 is
  inapplicable. Reviewer value and effort remain unmeasured. This is an
  applicability and classification check only, not a clean-project benchmark.
- **Next evidence:** Keep these rules at REVIEW. Evaluate further public
  examples only when connector role and intended connectivity can be resolved
  from an independent public pinout or an explicitly synthetic requirement.
  Record owner disposition, confirmed defects, valid alternatives, seeded
  misses, and review effort before changing policy or claiming detection gain.

##### Recorded trial: kicad-happy LED checks on public template examples (2026-10-03)

- **Candidate and installation:** `aklofas/kicad-happy` at commit
  `a6bba1add1e18b89e3aa0824b9769ed1d9d79174`, declared MIT. The tested
  `skills/kicad/scripts/analyze_schematic.py` SHA-256 is
  `beea21348a0794bd3ce02ea85cb537ff8efe7e63bad70bc7773d7bbe4e484315`.
  This used the GitHub checkout and Python 3.11 directly; no package or
  dependency was installed. Candidate reports and the local report were saved
  under ignored `build/cohort-public-led-review-20261003/`. No project source
  or candidate code was copied into Tooling.
- **Inputs and repeatability:** Read-only screening of the clean public
  KiCad-Team-Workflow-Template at commit
  `ed89536f0dbbcb013145af2994fef41b2250143e`. The Arduino status LED schematic
  SHA-256 is
  `c2d8442412cb251472a08df31109b8633655aaa375598abbb2e7bbc00961fa1b`; the
  controller is
  `bd3f349233ffc44f030b1004a1c08e51d1ec0589ecf646384f1ed3353806e5ad`; the
  Raspberry Pi status LED is
  `b99ad47237f3f36aaefa3a2ed08e3dae12d9131c7f9a52355401c9d5bada3fba`. Each
  invocation used `--no-hierarchy --only-deterministic --compact`; the two
  reports for each input were byte-identical. First/repeat report SHA-256:
  Arduino `797c5d818dec18a4c68d38a829a0ce5c3b75d5c246cd524e729410ea18751619`,
  controller `773c0ebd0dad02a626547d6c3249140b62f391872c89bf412553cde5dde6298a`,
  Raspberry Pi
  `037a0b84f8119dc75983fe27eaad5924954acbd8566f29aec4a3d52798b79e8e`.
- **Observed result:** Both LED examples emitted `LA-AUD` INFO findings naming
  `D1`, `R1`, and a 1000 Ω resistor with `drive_method=resistor_limited`. Each
  same report also emitted heuristic-error `LR-001` for D1, claiming there is
  no series current-limiting resistor. Their public design notes independently
  describe GPIO → 1 kΩ R1 → D1 → ground. Source review of this candidate
  revision confirms `LR-001` accepts an adjacent resistor only when its other
  net is classified as a power or ground rail; the valid GPIO-side resistor
  ends at a signal net. The controller example had no LED and no LR-001 prompt.
- **Local comparison:** The Arduino example has no custom-LED PART_ID role map,
  so local LINT-063 is not applicable. The current source-bound local report
  used the same schematic SHA and KiCad 10.0.5 netlist SHA-256
  `900a175d05b135f37bdd582cc07e83e637b0933b3fe99713e74b0615ff1ad5cf`; it has
  zero heuristic findings and `REVIEW` status because connector inventory is
  `UNDECLARED`. Its retained native summary status is `FAIL`, so this is not a
  clean project result. The report SHA-256 is
  `ac46ee1b8444f43b25202cecad9d7ad774b4098ab24888fcc4fb81aff902bb51`; the
  source-matched native summary SHA-256 is
  `1cea5943ae950f150c78443c8a168e1922da709f072740c63029b90489f135fa1`.
- **Incremental-value result:** `LR-001` did not add a valid detection; it
  produced a repeatable false positive on two documented series-resistor
  controls, and its own `LA-AUD` output contradicted it. `LA-AUD` did provide
  concise resistor-reference/value context, but the benefit over the native
  netlist and project documentation was not measured. Do not adopt the
  candidate check, its error severity, or its generic resistor recommendation.
  Keep a local rule conditional on exact supported component roles and
  source-bound connectivity evidence.
- **Boundary:** This is one public template revision with two similar training
  examples and one no-LED control. It does not estimate field precision,
  false-negative rate, reviewer effort, or behavior on other resistor
  placements. It does not establish current adequacy, LED ratings, or hardware
  safety.

##### Methodology review: kicad-happy-testharness

- **Source:** The public
  [testharness README](https://github.com/aklofas/kicad-happy-testharness)
  and [methodology](https://github.com/aklofas/kicad-happy-testharness/blob/main/methodology.md)
  were read on 2026-09-30. The inspected `main` revision was not pinned and the
  harness was not installed or run.
- **Observed practice:** Its documentation says corpus baselines primarily
  measure consistency rather than correctness, and describes a correctness
  layer with parser verification, synthetic detector fixtures, a small curated
  gold tier, metamorphic tests, and property invariants.
- **Incremental disposition:** Adopt only the test-method idea through
  LINT-054. The LINT-050 parser now has a synthetic metamorphic pilot: both
  orderings of conflicting suffixed pin keys produce `BLOCKED` coverage. This
  is local test evidence, not a result from the candidate harness.
- **Boundary:** No candidate code, corpus project, analyzer baseline, output,
  or project fixture was copied. The harness license and runtime behavior were
  not evaluated because no dependency or source reuse is proposed. A large
  open-source corpus or a passing seeded baseline is not treated as independent
  correctness evidence.

##### First-party public reference-template applicability replay (2026-10-01)

- **Corpus and source boundary:** Read-only native verification used the public
  reference-template checkout at commit
  `5ca79bedf665a9b6577d96b1d47f13ccd518c968`. The four selected example
  projects were `arduino-uno-status-led`, `controller`,
  `passive-signal-reference`, and `raspberry-pi-status-led`. No project source
  was copied into Tooling or changed; all generated receipts are under the
  template checkout's ignored `build/` directory.
- **Tooling and native pins:** The Tooling checkout was at `cbaed9b` with uncommitted goal changes.
  Its runtime source closure was recorded as SHA-256
  `3d28fc31b5d6273e803b2a180afd410f52e24b157688e0936570d289bc178431` over `pyproject.toml` and the
  sorted `.py`, `.json`, `.in`, and `.txt` files under `kicad_tooling/`. The 162-file digest hashes
  each relative path, NUL, file bytes, and NUL, with `pyproject.toml` first and package files in
  sorted path order. Native runs used each project's catalogued image: KiCad 10.0.0
  (`ghcr.io/kicad/kicad:10.0.0@sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3`)
  for `controller`, and KiCad 10.0.5
  (`ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`)
  for the other three projects.
- **Invocation and repetition:** Each project ran twice through
  `kicad-team verify --depth native --runner container`, using fresh receipt directories. Both runs
  had identical project source-hash maps, parsed `NetlistContract` values, lint findings,
  connector-coverage state, and next action. The raw netlist SHA changed on every repeat because
  KiCad writes a timestamp into `<design><date>`; after replacing only that element, all four raw
  XML pairs were byte-identical. The report intentionally retains the hash of the exact native
  artifact; the timestamp does not change the parsed evidence or the deterministic lint decision.
  Table digests are SHA-256 over sorted, compact JSON from
  `read_netlist(...).model_dump(mode="json")`.

  | Public example             | KiCad  | Lint   | Findings | Connector coverage        | Parsed-netlist SHA-256 prefix |
  | -------------------------- | ------ | ------ | -------- | ------------------------- | ----------------------------- |
  | `arduino-uno-status-led`   | 10.0.5 | REVIEW | 0        | UNDECLARED (`J1`)         | 50085baec78f4726              |
  | `controller`               | 10.0.0 | REVIEW | 0        | UNASSESSED (no candidate) | c42f2a6ba6b4230b              |
  | `passive-signal-reference` | 10.0.5 | REVIEW | 0        | UNASSESSED (no candidate) | d893aaecc8176cc3              |
  | `raspberry-pi-status-led`  | 10.0.5 | REVIEW | 0        | UNDECLARED (`J1`)         | 099a7c3df72d1d37              |

- **Interpretation:** The reports surfaced explicit connector-inventory
  coverage gaps and emitted no heuristic candidate on these four examples.
  `UNASSESSED` is not a reviewed no-interface decision. All four overall native
  verification runs ended `FAIL` and had `DESIGN_LINT.REVIEW` as a blocking
  finding; `passive-signal-reference` also lacks an independently authored
  native component/net contract. These training examples have no owner disposition
  for the lint coverage questions, so this replay is neither a clean-pass
  corpus nor a false-positive or missed-fault measurement. It found no design
  defect and provides no basis to promote or suppress a rule.
- **Local evidence:** Full source maps, exact raw and parsed netlist hashes,
  reports, and native command receipts remain at
  `build/ci/acceptance-template-5ca79bed/build/design-lint-public-template-5ca79bed/`
  in the Tooling checkout. This local result is development evidence from a
  dirty source tree, not a release benchmark. Repeat on a clean Tooling
  revision and add owner-reviewed, non-proprietary examples before measuring
  field precision or reviewer effort.

##### Source recheck: ThomsonLint KiCad exporter

- **Source:** The public
  [KiCad review guide](https://github.com/holla2040/ThomsonLint/blob/main/docs/KiCad_Review_Guide.md)
  and repository README were read on 2026-09-30. The inspected `main`
  revision was not pinned; no candidate code, example, or project export was
  copied.
- **Observed workflow:** The guide documents a standalone KiCad 9/10 exporter
  and says its export step has no external Python dependencies. It emits
  schematic and board JSON with classifications and precomputed summaries
  such as decoupling proximity, widths, trace lengths, and plane layers. Its
  findings step is AI-assisted and uses those exports together with images or
  PDFs; the guide describes this as the review workflow rather than a
  deterministic command-line lint result. The repository declares MIT, while
  the broader reporting workflow lists separate JSON-schema and AI-driver
  requirements.
- **Incremental disposition:** This is useful as engineering-rule and export
  coverage input, but it does not demonstrate an independently reproducible
  lint finding. The relevant deterministic metrics already have source-bound
  local checks or project-authored contracts in LINT-020 through LINT-025.
  Do not add an analyzer dependency or treat an AI finding as a verification
  gate. The bounded exporter-only trial below checks metric extraction and
  repeatability separately from lint detection.
- **Boundary:** The trial covers only synthetic KiCad 10 board fixtures. It is
  not a general parser conformance or maintenance-cost benchmark, and no
  project data was supplied.

##### Recorded trial: ThomsonLint board metrics export (2026-10-03)

- **Candidate and install:** Public `main` was pinned at commit
  [`8e9099a6cd88d05b1e1723038b1e22a5cc4592e1`](https://github.com/holla2040/ThomsonLint/commit/8e9099a6cd88d05b1e1723038b1e22a5cc4592e1);
  its standalone exporter reports version `1.0`, and
  `tools/kicad-export.py` SHA-256 is
  `39ad24da80d76c063bce23f9e619e3496e6292a86e5d132a818aa4c6333a9d09`.
  The candidate declares MIT in `LICENSE` (SHA-256
  `ede2d1df7b44ba6fe6e49c445404e5a1f650c2ad8b3396a2a363da5df4b54fe1`).
  The trial used a shallow Git checkout and the system Python standard library;
  it installed no package or additional dependency. No candidate source was
  copied into Tooling.
- **Method:** Ran the candidate's documented CLI twice per fixture over the
  seven Tooling-owned boards in
  [`differential-pair`](../tests/fixtures/design_lint/differential-pair/README.md):
  `python3 tools/kicad-export.py <case>.kicad_pro --output <output-dir>`.
  Temporary projects contained only the selected `.kicad_pcb` plus a generated
  empty `.kicad_pro`; receipts are under ignored
  `build/research/lint031-thomsonlint-v1.0/`. After removing only the volatile
  top-level `export_date`, both runs produced identical JSON for all seven
  boards. Output hashes below are SHA-256 of compact, sorted-key JSON after
  removing only that field; source hashes cover the original fixture bytes.
  The candidate parsed the fixture's KiCad 10 board format. To reproduce the
  candidate checkout, clone
  `https://github.com/holla2040/ThomsonLint.git` at depth 1 and detach at the
  recorded commit, then run the stated CLI once per case and compare two
  exports using that normalization.
- **Observed extraction:** The control exported `USB_D_P` and `USB_D_N` at
  20.0 mm each and 0.3 mm width. The width fault exported 0.1 mm minimum and
  maximum width for both nets. The skew fault exported 20.0 mm and 20.5 mm;
  the uncoupled and gap cases retained the expected per-net lengths and widths.
  The `no-rules-skew` and `no-rules-gap` exports were semantically identical to
  their corresponding physical boards because the candidate consumes the PCB
  file and does not read the project's `.kicad_dru` rules.
- **Fixture and output digests:**

  | Case              | Fixture source SHA-256                                             | Normalized output SHA-256                                          |
  | ----------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
  | `control`         | `aa2ead4fa9c9f707db2e82ecf0cd05e43ab0f37a09535122f1803065a9b95f72` | `70f3f33b1440eec75e685c77e6bd2a36c0ee4c8315c2c97816acec6671d63993` |
  | `fault-width`     | `18156288673b79532e0576b656b22ee0c56e79fe836ee8a41d3300a16a954146` | `b0bf8bc57158166f6eb0f554113035bae5fe6823dffe7e3c78c03f8ca91988fd` |
  | `fault-gap`       | `461d70ff5412252500d42f07bb87cc21e895453a9e1ffbe0e10eb1a8f03567d1` | `488f8c24b4a12cb43c687a9cce383ad32988fbe05b791b5acbb9c780dc0cd79f` |
  | `fault-skew`      | `96e696451b3f795830f20672c1223acdae1f3c54289e6d12da71f9706e912709` | `8cd4e82da7291f5400851179b16876be8d579a479f3565336727f96909d1347d` |
  | `fault-uncoupled` | `7ef76bbe9000cfdd29cf473e34a5f784d0db7356a48d3180f36cd08cf1afeb64` | `118abe67319b7bcf80ef1fb1d43187594fc2a84cbb9dbc526da27af0f917c3ea` |
  | `no-rules-skew`   | `96e696451b3f795830f20672c1223acdae1f3c54289e6d12da71f9706e912709` | `8cd4e82da7291f5400851179b16876be8d579a479f3565336727f96909d1347d` |
  | `no-rules-gap`    | `461d70ff5412252500d42f07bb87cc21e895453a9e1ffbe0e10eb1a8f03567d1` | `488f8c24b4a12cb43c687a9cce383ad32988fbe05b791b5acbb9c780dc0cd79f` |

- **Incremental value:** The exporter made the seeded width and skew values
  visible, but emitted no lint findings or rule severities. It does not compare
  pair spacing or uncoupled length, and it cannot distinguish a board with an
  authored design-rule limit from the same geometry without one. The existing
  pinned native DRC fixture lane reports the authored width/skew violations
  directly; this exporter-only trial did not run native DRC. Unique
  deterministic findings: zero. Duplicate lint findings: zero. False-positive
  rate and reviewer effort: not measured because the exporter emitted no
  findings.
- **Disposition and limit:** Do not adopt this exporter as a lint engine or
  runtime dependency. It can serve as a basic geometry-export example, but this
  fixture trial demonstrates no detection or review gain over the existing
  native evidence. The seven-case extraction replay is not broad parser
  conformance, and no general maintenance-cost estimate was made.

##### Source recheck: kicad-happy EMC decoupling metrics

- **Source:** The public
  [EMC pre-compliance guide](https://github.com/aklofas/kicad-happy/blob/main/emc-precompliance.md)
  was read on 2026-09-30. The inspected `main` revision was not pinned; the
  detector implementation was not benchmarked in this recheck.
- **Observed concept:** The guide groups DC-001 through DC-003 under PCB
  decoupling and describes capacitor-to-via distance as a connection-inductance
  review signal. It lists PCB evidence as required, but does not establish a
  project-independent distance limit.
- **Incremental disposition:** Extend LINT-020 with an optional project-owned
  capacitor-return-pad to native-connected-via distance limit. Synthetic cases
  distinguish connected and unconnected nearby vias, and pinned KiCad 10.0.0/
  10.0.5 fixture lanes validate a boundary control and moved-via fault. The
  local rule reports geometry only and does not claim an inductance estimate.
- **Boundary:** This is a concept review, not a runtime comparison against the
  cohort analyzer. No candidate code, report, board, threshold, or project
  fixture was copied. No cohort dependency was added.

##### Source recheck: kicad-happy v2.2.1 CAN and determinism notes

- **Source:** The public
  [v2.2.1 release](https://github.com/aklofas/kicad-happy/releases/tag/v2.2.1)
  and matching changelog were read on 2026-10-01. The release notes identify
  protocol checks for CAN and a hash-order audit that compares repeated
  analyzer outputs with varied Python hash seeds.
- **Observed scope:** The CAN protocol family checks protocol-specific
  electrical parameters; the release note does not describe the local
  cross-peer net-assignment predicate. The hash-order audit is a consistency
  guard, not an independent correctness oracle.
- **Incremental disposition:** LINT-067 adds a first-party review prompt for
  complete source-bound CANH/CANL peer pairs that share one side but split the
  other. Synthetic fault/control netlists establish the bounded behavior, and
  native repeated KiCad 10.0.0/10.0.5 exports with zero ERC errors and known
  isolated-library warnings establish its evidence boundary. No candidate
  source or fixture was copied; the cohort was not installed or
  runtime-benchmarked for this finding.
- **Boundary:** Release notes are source inspection, not a trial of the
  candidate CAN detector. The local prompt cannot infer bus intent, electrical
  correctness, or physical continuity.

##### Source recheck: kicad-happy v2.3.0/v2.3.1 determinism update (2026-10-07)

- **Source:** The public
  [changelog][happy-changelog] now lists v2.3.1, released 2026-10-06. Its
  v2.3.0 entry records hash-seed-dependent output fixes and a three-seed
  determinism gate over each analyzer.
- **Incremental value:** This adds a reusable verification method, not an
  electrical finding. LINT-080 applies it to complete synthetic DB9 fault and
  common-return reports, same-net diode fault and distinct-net control
  reports, and generic peer-pin outlier fault/common-net control reports under
  three independent Python hash secrets. The same
  v2.3.0 entry adds `SP-001` for same-net two-pin passives or diodes. LINT-051
  covers resistor, capacitor, and inductor families; its diode family was a
  specific coverage gap. LINT-081 adds only exact `Device:D` family support as
  a local review rule; no candidate code or fixture was copied and no runtime
  dependency was added.
- **Boundary:** This was source inspection only. No kicad-happy version was
  installed or run for this update; no cohort code, fixture, or project design
  was copied. LINT-080 is first-party test code; its present matrix covers
  synthetic connector-return, peer-pin assignment, and same-net diode reports.

##### Recorded trial: kicad-happy v2.2.1 CAN output on peer fixtures

- **Candidate:** The public kicad-happy v2.2.1 archive declares MIT. The
  extracted archive has no Git metadata; its SHA-256 is
  `dc770679619e3dc90b7cc97cf27342500a21ddd148119605f3a9db1576f0c5b6`.
  Tested analyzer files are pinned by SHA-256: `analyze_schematic.py`
  `beea21348a0794bd3ce02ea85cb537ff8efe7e63bad70bc7773d7bbe4e484315`,
  `validation_detectors.py`
  `b4f0b0deb0ce4bd5c598840f3cdc1eaceced883fc2929d7e7a1a9c0a27acbfc9`,
  `detector_helpers.py`
  `68fdc890755b53be1e25f5a7d07f72a2a8ca30dc5b0b67f4e2dfafebbe4ebc63`,
  and `kicad_types.py`
  `2e12971ba2bff4ff5b221697dbf79400b27e3aef8c3896be64e9497c27814c44`.
- **Inputs and data boundary:** Used only the Tooling-owned synthetic
  `tests/fixtures/design_lint/can-peer-native/peer-control.kicad_sch` and
  `peer-fault.kicad_sch`. Candidate-only scratch copies replace the three
  transceiver `Value` strings with `SN65HVD230` so its CAN device keyword
  matcher recognizes them; the source fixtures remain unchanged. Scratch
  schematic hashes are control
  `1a47ddbd4605e549c73a1c9bfd876a4b5891e89d39233bcdecce2d73d74113bd` and
  fault `37e3184d9e461140db306fa264e97f3cd607ecebe7fbdedc14380615a87c7fb8`.
  Both include direct 120R termination across their assigned CANH/CANL pairs.
  All candidate inputs and output reports stayed under `/private/tmp`; no
  project source or candidate code was copied into this repository.
- **Invocation:** Ran the candidate's deterministic schematic script directly
  without installation or lifecycle/network checks:

  ```sh
  python -B -I "$HAPPY/skills/kicad/scripts/analyze_schematic.py" \
    "$FIXTURES/control.kicad_sch" --no-hierarchy --only-deterministic \
    --output "$OUT/control.json"
  python -B -I "$HAPPY/skills/kicad/scripts/analyze_schematic.py" \
    "$FIXTURES/fault.kicad_sch" --no-hierarchy --only-deterministic \
    --output "$OUT/fault.json"
  ```

- **Observed result:** Both candidate outputs repeated byte-for-byte on a
  second run. Control output SHA-256 was
  `c01fbfcebe833c89b5ef0c01671b5bc091b44470581b0aadb412f83afe3752e5`; fault
  output SHA-256 was
  `2c4ab6cecb32d904cba1cc1b72ca9adc102e1a697cbb1e8a4afda32a5b990375`.
  Neither JSON report exports the documented `PR-003` validation findings.
  Instead, `protocol_compliance.findings` reports the same CAN “missing 120Ω”
  issue for both cases with `nets: ["", ""]`, `has_termination: false`, and
  `termination_ohms: null`. The general finding list contains only `DS-001`,
  `SS-001`, and `LC-007`. The protocol message therefore does not distinguish
  the valid control from the peer-assignment fault and misstates the visible
  termination evidence.
- **Incremental-value result:** No useful CAN detection or localization was
  demonstrated through the candidate's JSON interface. The output is a
  reproducible false positive on the control, not an independent confirmation
  of LINT-067. Retain no candidate dependency for this capability; the local
  `bus.can_peer_assignment_divergence` rule remains the deterministic
  review-localization check, with bus intent and physical continuity left to
  project requirements and PCB evidence.
- **Limit:** This is one synthetic symbol-library representation and one
  deterministic CLI mode. Other symbol libraries, analyzer modes, termination
  topologies, and reviewer effort remain unmeasured. No claim is made about
  field false-positive rates or all kicad-happy protocol checks.

##### Recorded trial: kicad-happy EMC protection-via heuristic

- **Candidate:** The local read-only kicad-happy archive reports v2.2.1 in its
  [changelog](https://github.com/aklofas/kicad-happy/blob/main/CHANGELOG.md).
  Its extracted source has no Git metadata, so the exact tested
  scripts are pinned by SHA-256: `analyze_pcb.py`
  `546acfa4218716c1db41d5bda66ab1a2ee7aeac4f723e188bc64b382b7bc7674`,
  `analyze_emc.py`
  `b79b5f6f27b0e62c42f1f158521a3242fa581b3658b68ceab1e7b683b4404203`,
  `emc_rules.py`
  `5389056387238a9d2aed224ec54f40b4eb7b2e3dbe1d766975fb2adff1aea3a8`,
  and `finding_schema.py`
  `0b3ecaf9d647d4e69ff31c321d314d0fcd49fadceb6d6ad718cd46d3c29ece49`.
- **Invocation and data boundary:** Ran the direct Python 3.11 PCB and EMC
  analyzer scripts without installing a package or adding a runtime
  dependency. The input was the tooling-owned
  `pcb-protection-entry-path.kicad_pcb` fixture plus a minimal synthetic
  protection-device finding; outputs and the disconnected-via mutation stayed
  under `/private/tmp`. The control board SHA-256 is
  `64d0393d7951420eb6cadaf4c4b7c788cbadc1f7d39a3b6fb071f7a56ab8115c`; the
  moved-via fault board SHA-256 is
  `35146571c21782790cc147f05d97a5a38bfcbda9491620692bafe77063ae9970`.
- **Observed result:** The candidate emitted the same `ES-002` info finding
  (“Single ground via near ESD device D1”) for both boards. Its heuristic
  counts a net-name-classified ground via inside 3 mm of the TVS footprint
  origin; it does not verify that the via shares copper with the mapped
  reference pad. The fault via is 1.5 mm from the exact D1.2 pad and 2.5 mm
  from the D1 footprint origin, so it remains inside both geometric radii but
  is disconnected from D1.2. This is the published
  [ES-001/ES-002 category](https://github.com/aklofas/kicad-happy/blob/main/emc-precompliance.md)
  exercised with a mapped synthetic fault. The candidate emitted no `ES-001`
  finding for the 0.65 mm connector/protector placement.
- **Local comparison:** The project-authored map reports one native-connected
  reference via and `COMPLETE` on the control. On the moved-via fault, the
  KiCad 10.0.0 and 10.0.5 native lanes report zero connected reference vias
  within the authored 2 mm pad-centered radius and `INCOMPLETE`; the fault
  snapshot is repeated and source/version/image bound. Repeated candidate EMC
  runs produced identical ES-001/ES-002 summaries for each input.
- **Incremental-value result:** The candidate adds no unique detection. Its
  single-via advisory duplicates an intentionally configured minimum of one
  on the valid control, while it misses the nearby-but-disconnected-via fault
  that the local map catches. Retain the bounded hypothesis and native
  regression; do not adopt the analyzer or its universal 3 mm threshold.

##### Recorded trial: kicad-happy schematic analyzer

- **Candidate:** `aklofas/kicad-happy`, commit
  `a6bba1add1e18b89e3aa0824b9769ed1d9d79174`, declared MIT license.
- **Invocation:** Ran its `skills/kicad/scripts/analyze_schematic.py` directly
  with Python 3.11 and `--output` into `/private/tmp`. No package install or
  analyzer dependency install was needed for this path. The checkout and all
  generated reports stayed outside this repository; no cohort code or board
  data was copied into Tooling.
- **Inputs:** Six existing synthetic `.kicad_sch` fixtures from
  `tests/fixtures/design_lint`: pin-line near-miss fault/control, pin tip on
  wire interior with/without a junction, and unmarked/marked orthogonal wire
  crossings. All six invocations completed and emitted parseable JSON.
- **Observed output:** Every fixture produced five total analyzer findings,
  including two generic `NT-001` single-pin-net findings. Those same two
  connectivity findings appeared on both fault and control fixtures, so they
  did not distinguish the tested geometry regressions. The unmarked-crossing
  and junction-marked-crossing cases had identical connectivity findings; no
  crossing-specific finding was emitted. For the pin-line and pin-interior
  fault cases, the parser represented the nearby named label as a named net
  with zero pins, while the controls had that label on the pin net. This is
  reviewable raw extraction evidence, but the analyzer did not turn that
  difference into a localized near-miss diagnostic. Datasheet-coverage,
  sourcing, and lifecycle messages were unrelated to these electrical
  fixtures and were excluded from the comparison.
- **Incremental-value result:** No unique actionable lint detection was
  demonstrated on this fixture set. Raw net extraction may help a reviewer,
  but reviewer effort was not measured and the existing source-bound
  geometry rules already provide more specific coordinates and wire IDs.
  This trial does not justify adopting the analyzer or adding it as a runtime
  dependency. It does not evaluate PCB checks, hierarchical sheets, or
  connector-ground distribution.
- **Still unmeasured:** Full install workflow, supported KiCad version matrix,
  output stability across releases, reviewer effort, maintenance cost, and
  broader connector/power-pin behavior. One synthetic generic two-peer
  connector fault/control pair is measured in the follow-up below; keep the
  remaining fields open rather than extrapolating from these direct script
  runs.

##### Follow-up trial: kicad-happy generic connector single-pin findings (2026-10-03)

- **Candidate and install:** Public `aklofas/kicad-happy` was checked out from
  GitHub at commit
  [`a6bba1add1e18b89e3aa0824b9769ed1d9d79174`](https://github.com/aklofas/kicad-happy/tree/a6bba1add1e18b89e3aa0824b9769ed1d9d79174);
  its repository declares MIT. The tested
  `skills/kicad/scripts/analyze_schematic.py` SHA-256 is
  `beea21348a0794bd3ce02ea85cb537ff8efe7e63bad70bc7773d7bbe4e484315` and
  `LICENSE` SHA-256 is
  `f542344efc2d21d18c81507e8168ab256c32ece6e7acb1bc8bde71950c9b6bb5`.
  This used a direct GitHub checkout and the active Python 3.11 interpreter;
  no package or runtime dependency was installed. The checkout and reports
  stayed under `/private/tmp`, and no cohort code was copied into Tooling.
- **Inputs and invocation:** Ran twice per input with
  `analyze_schematic.py <fixture> --no-hierarchy --only-deterministic
  --compact --output <report.json>`. The inputs are the tooling-owned
  `two-peer-open-fault.kicad_sch` and
  `two-peer-common-control.kicad_sch`; their SHA-256 values are recorded in
  the [fixture notes](../tests/fixtures/design_lint/generic-peer-pin-assignment-native/README.md).
  The four JSON reports parsed successfully and each same-input pair was
  byte-identical: fault output SHA-256
  `8ae9bcf67b9620b3a8acbc6419b164dcd1216e8b1a2f517d69d777fc93df4f12`,
  control output SHA-256
  `9b9144d1f91f0557a2866e9de27ce296003abd9240675a9135fb7ee1e12ecce1`.
- **Observed result:** On the open-contact fault, deterministic rule `NT-001`
  emitted INFO findings for `J2.1` on `__unnamed_0` and for `J1.1` on the
  single-pin `+5V` net. The common-net control emitted neither `NT-001`
  finding. Unrelated datasheet, ESD, rail-source, sourcing, and lifecycle
  findings were excluded. The reports contained seven total findings on the
  fault and four on the control; the count difference came from the two
  connectivity findings and one topology-dependent ESD audit.
- **Source review:** At this pinned revision, `NT-001` skips nets marked
  `no_connect` and pins whose native type is `no_connect`, `free`,
  `unspecified`, or `unconnected`. The explicit-marker path has the synthetic
  follow-up below; the native pin-type exclusions still lack fault/control
  coverage.
- **Explicit no-connect control (2026-10-03):** A temporary derivative of
  `two-peer-open-fault.kicad_sch` placed a native no-connect marker at `J2.1`
  (`106.68, 104.14` mm); the derived source SHA-256 is
  `0ffbf3d600e64d5b4bf7b8caab9039553314ee829fd136b30aa2e9bed6bdf77e`. The
  same pinned analyzer and deterministic-only command ran twice. Both reports
  had SHA-256
  `c826cf174aecb54934e067fa163bf20f797803b3f485d6ca52e06c2712614615`, emitted
  no finding for `J2.1`, and retained only the `NT-001` prompt for `J1.1` on
  `+5V`. This confirms the candidate's explicit-no-connect exclusion for this
  synthetic input; it is not a KiCad-native export or proof that the remaining
  singleton prompt is useful. The direct candidate invocation had no project
  interface or off-board source map.
- **Local comparison and disposition:** The tooling-owned fixture specification
  expects `J2.1` to produce `connector.peer_pin_assignment_outlier` with REVIEW
  and the common-net control to clear that rule. The focused local regression
  `test_two_peer_open_generic_contact_prompts_and_supports_exact_ignore`
  passed (1 test). Therefore `J2.1` is a corroborating duplicate, not a new
  detection. `J1.1` is a possible coverage prompt for a singleton external
  endpoint, but the pair does not establish whether it should connect to a
  local source. The candidate's explicit no-connect derivative suppresses its
  `J2.1` prompt while retaining the `J1.1` singleton prompt. The local
  `NetlistContract` records assigned and unconnected pins but has no native
  no-connect-marker field, so its current peer rule cannot distinguish an
  explicitly marked open contact from a wire-open contact. The source-bound
  native marker case is now part of the fixture lane and keeps the REVIEW
  finding on both pinned versions. A marker alone does not resolve peer intent,
  so keep that conservative prompt. The off-board serial and repeated-child
  sheet comparisons below add no unique detection beyond authored interface
  coverage, native ERC, and the local source-bound geometry check. Do not adopt
  a general singleton-net REVIEW rule from this candidate. Additional singleton
  trials need a named scenario where current source-bound checks miss a defect.
  The open test-point result is recorded below and duplicates native ERC. Do not
  adopt candidate code, its wording/severity, or a runtime dependency from this
  trial.
- **Valid off-board endpoint control (2026-10-03):** Added the synthetic
  `single-offboard-port-control.kicad_sch` fixture (SHA-256
  `ceaa7038e372ec74a00f7e7c2cb5311377df01624760ab555adb413c4e02d8e9`). Its
  independent interface record declares J1.1 as an external 5 V input and
  J1.2 as its off-board return. At the pinned kicad-happy commit and script hash
  above, two `--no-hierarchy --only-deterministic --compact` runs were
  byte-identical (report SHA-256
  `d661679b9fa63ae336062b8b2ef135e0fef0a5e7b06a846fbeabcf1e8aeead2e`):
  `NT-001` emitted INFO for both J1.1 (`+5V`) and J1.2 (`GND`) because the
  candidate has no project interface or external-source mapping.
- **Source-bound local result:** The same schematic was exported twice using
  digest-pinned KiCad 10.0.0 and 10.0.5. Parsed normalized contracts were
  repeatable and cross-version identical (SHA-256
  `453a8f7b74958209e704257212a1e96d651c5df107ec6d8c2bef08d21ce3dfbc`). A
  synthetic interface catalog and complete connector-inventory review produced
  `coverage_status=COMPLETE`; local design lint returned PASS with no findings
  on both versions. The 10.0.0 raw XML differed between repeat exports, while
  the typed normalized contract remained identical. Native lane evidence and
  the fixture remain tooling-owned; no candidate code or project data was
  copied. The machine-readable run summary is retained under ignored
  `build/ci/cohort-singleton-net-lint/trial-evidence.json`.
- **Connected UART peer comparison (2026-10-03):** Ran the same pinned analyzer
  twice on synthetic `serial-peer-native/endpoints.kicad_sch`
  (SHA-256 `7f3e44ba24ba70b382939fa6504ff635b6bb56292b5bcbc36dee307166378060`).
  Both reports were byte-identical (SHA-256
  `f786d703847396e99c385d1ccc60a47f8884aa170c287f04ce51aa83b0908c60`) and
  emitted no `NT-001` findings because each TX/RX net has two connected pins.
  The existing source-bound native serial lane passed on KiCad 10.0.0/10.0.5:
  its undeclared and partial peer maps return REVIEW, while the complete authored
  map passes. This connected-endpoint sample adds no singleton-net detection;
  it does not cover an off-board serial port whose signals are singleton nets.
- **Open test-point/connector comparison (2026-10-03):** On the synthetic
  connector-inventory control, `NT-001` reported U8.1 on `__unnamed_0`; on the
  open connector fault it reported U7.1, U7.2, and U8.1. Two analyzer runs per
  fixture were byte-identical. Pinned KiCad 10.0.0 and 10.0.5 ERC reports for
  the same sources contain `pin_not_connected` errors for exactly those pins.
  The normalized violation content repeats across runs after excluding the
  report date. The source-bound connector-inventory lane passes on both exact
  versions: it marks the connector fault UNDECLARED and the test-point-only
  control COMPLETE, since standard test points are intentionally outside
  connector inventory. This cohort result duplicates native ERC and adds no
  unique detection. Synthetic library-configuration warnings are excluded from
  the pin comparison. Full inputs, hashes, tool images, and normalized ERC
  receipts are in ignored `build/ci/cohort-singleton-net-lint/trial-evidence.json`.
- **Repeated-child-sheet hierarchy comparison (2026-10-03):** Ran the pinned
  analyzer twice with hierarchy discovery enabled and deterministic rules only
  on the tooling-owned repeated-sheet fault and junction-marked control. The
  four source hashes are recorded in ignored
  `build/ci/cohort-singleton-net-lint/trial-evidence.json`; fault and control
  reports were byte-identical across repeats (SHA-256
  `d61c88cc8f79cf93504784335e5e2732dfcd6f54b1b9f360ae3c086cfee809b7` and
  `674c9e1b072858292bdd82236afe3f50ef28dacbb4e815855f2d4189f6fcc7f2`). On the
  fault, `NT-001` reports R1.1/R1.2 and R2.1/R2.2 as singleton nets. Native
  KiCad 10.0.5 and 10.0.6 repeated-sheet regressions confirm that R1.2/R2.2
  are the two open instance pins, while R1.1/R2.1 sit on separate instance
  `CONTROL_NET` nets. The source-bound geometry scanner reports both missing
  T-junctions and native ERC identifies the shared open source pin; both
  controls are already localized without a generic singleton warning. The
  candidate is quiet under `NT-001` on the marked control, where its separate
  `SP-001` findings describe the fixture's deliberately joined resistor pins.
  This is an analysis fixture, not a product circuit. The trial adds no unique
  singleton-net detection and leaves the relevance of the label-only singleton
  prompts dependent on independently stated intent.
- **Off-board UART singleton (2026-10-03):**

  Added synthetic `offboard-endpoints.kicad_sch` and an independently authored serial map that
  declares J1/J2 as direct peers and J3/J4 as external peers. At the pinned kicad-happy commit, two
  deterministic-only runs were byte-identical (report SHA-256
  `4bbbf30c8269cae0341440403413d71711dc4afd67303f2c19145817c604ac6c`) and `NT-001` reported
  J3.1/J3.2/J4.1/J4.2 on their four singleton TX/RX nets. Repeated native KiCad 10.0.0 and 10.0.5
  exports preserve those one-pin nets and the direct J1/J2 pairings; their normalized pin-to-net
  digest is `84d802852f07682498bcd80c690f158f70f1324a412facc3b144979f9d4272f4`. ERC reports four
  `isolated_pin_label` warnings on exactly those labels and no `pin_not_connected` items; remaining
  ERC findings are synthetic symbol, footprint, and grid issues. The new local regression loads the
  authored external map and confirms `bus.serial_unmapped_peer` suppresses J3/J4 only; it runs on a
  synthetic typed netlist, while the separate native exports bind the schematic pin functions and
  net assignments. The singleton candidate adds no unique detection. This fixture has no reference
  pins and says nothing about whether either external serial port must share board ground. Source
  and map digests, exact images, repeat hashes, and native results are recorded in ignored
  `build/ci/cohort-singleton-net-lint/trial-evidence.json`; fixture details are in the
  [serial-peer README](../tests/fixtures/design_lint/serial-peer-native/README.md).
- **Incremental-value decision:** This is a valid false-positive control for a
  general singleton-net warning: both contacts are documented external
  endpoints, yet the cohort rule still prompts. The source-bound local path
  reports connector coverage UNDECLARED and lint REVIEW when the project map is
  absent; with the complete map, coverage is COMPLETE and no local electrical
  finding is warranted. The connected UART sample is quiet, the open
  test-point/connector and off-board serial findings duplicate native ERC, and
  the repeated-sheet fault is already localized by source-bound geometry and
  native ERC. Do not add a general singleton-net rule based on these trials.
  Broader hierarchy styles remain unmeasured; any further singleton trial must
  name a defect class that current source-bound connector, serial roster,
  geometry, and ERC checks do not cover.
- **Boundary:** This is one synthetic fault/control pair at one candidate
  commit. It measures one repeated-child-sheet case, not all singleton
  topologies or hierarchy styles. Reviewer effort, field precision, and
  maintenance burden remain unmeasured; the findings do not justify treating a
  singleton net as an electrical defect.

##### Recorded trial: kicad-happy VM-001 voltage-domain heuristic

- **Candidate and provenance:** `aklofas/kicad-happy`, commit
  `a6bba1add1e18b89e3aa0824b9769ed1d9d79174`, v2.2.1 changelog, declared MIT. The extracted archive
  had no Git metadata. The exact tested `validation_detectors.py` and `LICENSE` hashes, plus both
  fixture hashes, are recorded in the
  [synthetic fixture notes](../tests/fixtures/design_lint/cohort-peer-voltage/README.md).
- **Invocation:** Ran `skills/kicad/scripts/analyze_schematic.py` directly
  with Python 3.11 isolated mode and `--no-hierarchy --only-deterministic
  --compact`. No package was installed. The detector's datasheet lookup helper
  was unavailable in the isolated interpreter; no cached device facts affected
  the result. Reports remain under ignored `build/ci`.
- **Inputs and output:** On the synthetic U1 `+5V` to U2 `+3V3` SPI case,
  VM-001 emitted four findings, one each for `SPI_CS`, `SPI_MISO`, `SPI_MOSI`,
  and `SPI_SCK`; all were severity `error`. The same-rail control emitted no
  VM-001 finding. Full reports contained 13 and 6 candidate findings,
  respectively, including unrelated rules. Each full report was byte-identical
  across runs with `PYTHONHASHSEED=1` and `73`.
- **Incremental-value result:** The candidate demonstrates a possible
  coverage prompt when no project-authored LINT-061 map names a cross-rail
  digital peer. Its rail-name estimate, generic voltage thresholds, error
  severity, and level-shifter recommendation do not establish actual pin
  direction or receiver tolerance. Retain the idea only as a possible local
  REVIEW prompt under LINT-066; do not adopt candidate code, thresholds, or an
  installation dependency.
- **Boundary and open evidence:** This trial used only the candidate's
  schematic parser on synthetic source. No `kicad-cli` was on PATH during the
  trial, so there was no native export or ERC comparison. An app-bundled
  KiCad 10.0.6 CLI was found on 2026-10-07 and used for separate fixture and
  public-project probes; this cohort trial has not been rerun with native KiCad.
  A same-rail negative control does not measure false positives on 5 V-tolerant
  or mixed-supply parts. Reviewer effort, false-positive rate, performance,
  and behavior on approved non-proprietary projects remain unmeasured.

##### Recorded trial: kicad-happy USB-C CC topology check

- **Candidate:** `aklofas/kicad-happy` v2.1.0, commit
  `f765dc0916e9752fe2639ca5bad4bda2d5161b8f`, declared MIT. The bounded source
  review covered its USB-C role classifier and `UC-003` finding text.
- **Invocation:** Ran only the deterministic analyzer directly with Python
  3.11, `--no-hierarchy`, and `--only-deterministic`. No package install or
  hosted review service was needed. Repeated runs had identical focused
  `usb_compliance` and `UC-*` results for each fixture. Checkout and reports
  stayed under `/private/tmp`; candidate code and output were not copied into
  this repository.
- **Inputs and result:** Three synthetic CC1/CC2 schematics were tested. The
  unconfigured connector had no CC attachments; the source control used two
  56 kΩ resistors to `+5V`; the sink control used two 5.1 kΩ resistors to
  `GND`. The candidate marked the source and sink controls as expected and
  emitted no `UC-003` findings for them. On the unconfigured pair it reported
  two sink-specific missing-pull-down findings while its role field was
  `unknown`.
- **Incremental-value result:** No unique actionable coverage was demonstrated.
  Evaluating LINT-053 on the same three parsed native contracts produced the
  `J1` role-map prompt for each one, including the valid source and sink
  controls, because none had a project role record. LINT-012 checks the
  project-declared CC requirements after the role is recorded. The candidate's
  sink assumption can be inapplicable to a source, dual-role, or
  controller-managed port, and the analyzer has no project-authored role map
  to resolve that question. Do not add it as a dependency or treat `UC-003` as
  proof of a missing required resistor.
- **Native evidence:** Each fixture was exported twice with digest-pinned
  KiCad 10.0.0 and 10.0.5 and parsed with the local native netlist parser.
  Parsed normalized contracts match across repeats and versions. Raw XML also
  matched across repeats in 10.0.0; in 10.0.5 the source and unconfigured raw
  XML differed, while their normalized parsed contracts remained identical.
  Source hashes, normalized netlist digests, image pins, and reproduction
  boundaries are recorded in the
  [synthetic fixture notes](../tests/fixtures/design_lint/cohort-usb-c-roles/README.md).
- **Boundary:** This is a parser-level comparison on synthetic schematics. It
  does not run ERC, verify USB compliance, prove the required role, inspect PCB
  copper, or assess real hardware.

##### Recorded trial: kicad-sch-lint schematic geometry checks

- **Candidate:** `rashuky/kicad-sch-lint`, commit
  `97218e396de9a93d52de49a6710d4dcc0c1131c8`, version `0.1.0`, declared MIT
  license. Its package declares no runtime dependencies for linting; PDF
  rendering is optional.
- **Invocation:** Built and installed the local checkout into a disposable
  Python 3.11 virtual environment with `--no-build-isolation --no-deps`, then
  ran the installed `python -B -I -m kschlint lint <fixture> --severity info
  --codes wire-end-on-pin-line,pin-on-wire-middle,missing-junction,
  four-way-junction,dangling-wire,label-floating --json`. Pure schematic lint
  did not require `kicad-cli`. The candidate checkout, wheel, environment, and
  output remained under `/private/tmp`; no source or project data was copied
  into this repository.
- **Inputs:** The same six synthetic `.kicad_sch` files recorded in the
  kicad-happy trial. All six invocations completed and emitted valid JSON.
- **Observed output:** The pin-line fault reported `wire-end-on-pin-line` and
  `dangling-wire` at the same coordinate; its connected control reported no
  findings. The existing Tooling rule already identifies that fault using the
  native-unconnected pin and retains the wire UUID, so the second warning is a
  duplicate with less source identity. The pin-tip-on-wire-interior fault and
  its junction-marked control both emitted the same `pin-on-wire-middle` and
  `dangling-wire` warnings. The candidate did not distinguish the two
  connectivity states; its warning text says the pin connects in both cases.
  For the unmarked crossing it reported four dangling endpoints and no
  crossing finding. The marked control reported those same four endpoints
  plus `four-way-junction`; no `missing-junction` finding appeared on this
  fixture pair. The four-way warning on the marked control is a review hint,
  not evidence of an electrical fault. Native ERC was not part of this initial
  candidate run; the later KiCad 10.0.6 comparison is recorded under LINT-024
  and shows generic dangling-wire diagnostics in both crossing cases.
- **Incremental-value result:** The six geometry cases in this trial did not
  demonstrate a unique actionable finding beyond current near-miss localization. It showed useful
  comparison cases for control sensitivity and reinforces that schematic
  geometry must not declare electrical connectivity without native evidence.
  Do not adopt its analyzer or mutation workflow as a verification dependency.
- **Still unmeasured:** Repeatability across the candidate's claimed KiCad
  version range, reviewer effort, and performance on larger hierarchical
  designs. The exact-version comparison found no unique electrical finding;
  any review-time advantage from the candidate's generic dangling-wire output
  remains unmeasured.

##### Recorded follow-up trial: kicad-sch-lint free-text overlap

- **Candidate:** The same MIT `rashuky/kicad-sch-lint` commit and disposable
  Python 3.11 installation recorded above. Only its read-only `text-overlap`
  check ran; candidate fixes and other checks were not invoked.
- **Inputs:** Synthetic copies of the tooling-owned
  `connected-pin-control.kicad_sch` fixture under `/private/tmp`, each with two
  standard 1.27 mm free-text objects. The fault places `LONG_LABEL_ALPHA` at
  `(25.4, 25.4)` and `LONG_LABEL_BETA` at `(29.0, 25.4)`; the control moves the
  second anchor to `(50.8, 25.4)`. No board or project source was imported.
- **Observed output:** The candidate reported one `text-overlap` on the fault
  with source UUIDs and approximate overlap box
  `[20.498, 24.403, 34.328, 26.149]`; the separated control had no finding.
  The pre-existing Tooling geometry scan had no candidate in either case
  because the source anchors were distinct. This is a new graphical review
  signal, not an electrical detection.
- **Native validation:** Exact KiCad 10.0.6 from the digest-pinned
  `kicad/kicad:10.0.6` image
  (`sha256:18693567392b80da435f9fa952ce3a3e534c66eb5a6033f5b9c80aa3b19dd3ec`)
  exported both schematics to SVG and ERC. The fault's 89 and 95 text stroke
  segments have a zero minimum centerline distance, below the native 0.1524 mm
  stroke width. The control's minimum is 8.2247 mm. Both schematics have the
  same native netlist and identical three baseline ERC violations; the overlap
  itself changes neither connectivity nor ERC.
- **Decision:** Add a first-party, opt-in `schematic.free_text_overlap` rule
  using a native-render-calibrated standard-font envelope. Keep its default
  `off`; a project's explicit `review`, `block`, `off`, and exact-ignore policy
  controls disposition. Do not adopt the candidate package or its `error`
  severity. The local rule identifies the pair and overlap box and explains
  that rendered review is required.
- **Still unmeasured:** Reviewer time saved, false-positive rate on public
  real-world schematics, larger hierarchical typography coverage, and any
  advantage over direct KiCad rendering. Rotation, custom faces, explicit
  justification, non-ASCII, formatted, and bold/italic/thick cases are
  currently unsupported rather than inferred.

##### Recorded follow-up trial: kicad-sch-lint text-over-wire

- **Candidate:** `rashuky/kicad-sch-lint`, commit
  `97218e396de9a93d52de49a6710d4dcc0c1131c8`, version `0.1.0`, declared MIT.
  The candidate checkout and outputs stayed in `/private/tmp`; the analyzer
  was read-only and no candidate code or project source was copied into
  Tooling.
- **Inputs:** Synthetic fault and control copies of the tooling-owned
  `connected-pin-control.kicad_sch`. The fault places `WIRE CROSSING FAULT`
  over the horizontal wire at y=71.12 mm; the control places `WIRE CLEAR
  CONTROL` 8.89 mm below it. No proprietary board or schematic was used.
- **Candidate result:** Its `text-over-wire` code reported the fault and
  returned no finding for the control. The SVG path comparison with exact
  KiCad 10.0.6 measured 0.000000 mm minimum text-stroke-to-wire distance in
  the fault and 7.9495 mm in the control. ERC violation signatures match
  between the pair. Native netlist nets match, and component/pin assignments
  match after excluding the project-specific `Sheetfile` property.
- **Decision:** Implement a separate deterministic
  `schematic.free_text_over_wire` geometry rule using the existing native-SVG
  calibrated text metrics, a fixed edge guard, and a minimum clipped wire
  length. Keep it `off` by default, review-only unless a project explicitly
  raises its mode, and subject to exact fingerprint ignores. Do not add the
  candidate dependency or infer required electrical connectivity from text
  placement.
- **Limit:** This is graphical evidence only. Standard-font axis-aligned
  envelopes can flag intentional annotation over a wire and do not test buses,
  labels, symbol fields, pin labels, or rendered symbol graphics. Broader
  typography and false-positive rates remain unmeasured.

##### Recorded follow-up trial: kicad-sch-lint wire-through-body

- **Candidate:** `rashuky/kicad-sch-lint`, commit
  `97218e396de9a93d52de49a6710d4dcc0c1131c8`, version `0.1.0`, declared MIT.
  Its temporary checkout and environment remained under `/private/tmp`; no
  candidate code or project source was copied into Tooling.
- **Inputs:** Synthetic fault and control copies of the tooling-owned
  `connected-pin-control.kicad_sch`. Both include the same extra wire; the
  fault places it through the `Lint:R` body at y=76.2 mm, while the control
  moves it below the body. No proprietary board or schematic was used.
- **Candidate result:** `wire-through-body` reported one finding on the fault
  and none on the control, with an approximately 2.1 mm body overlap.
- **Native validation:** Exact KiCad 10.0.6 from the digest-pinned
  `kicad/kicad:10.0.6` image
  (`sha256:18693567392b80da435f9fa952ce3a3e534c66eb5a6033f5b9c80aa3b19dd3ec`)
  exported both synthetic sources to netlist and ERC. Component/pin
  assignments and nets match after excluding the project-specific `Sheetfile`
  property; all six ERC violation signatures match. The geometry change does
  not affect connectivity or native ERC.
- **Decision:** Add a first-party, source-bound
  `schematic.wire_through_symbol_body` review rule using supported embedded
  symbol graphics and an explicit guard and minimum length. Keep it default-off.
  Do not add the candidate dependency or infer electrical intent from
  graphical overlap.
- **Limit:** The candidate measurement and first-party predicate use an
  axis-aligned envelope. Disjoint primitives and non-rectangular bodies may
  create false positives; reviewer time saved and public-project false-positive
  rates remain unmeasured.

##### Recorded follow-up trial: kicad-sch-lint text-over-body

- **Candidate:** `rashuky/kicad-sch-lint`, commit
  `97218e396de9a93d52de49a6710d4dcc0c1131c8`, version `0.1.0`, declared MIT.
  The temporary candidate installation, synthetic copies, and outputs remained
  under `/private/tmp`; no proprietary board or project file was used.
- **Inputs:** Two copies of the tooling-owned
  `connected-pin-control.kicad_sch` with the same top-level `BODY NOTE` text.
  The fault places its anchor at `(76.2, 76.2)` over the R1 body; the control
  moves it to `(88.9, 76.2)`. The body outline is x=74.93..77.47 mm and
  y=73.66..78.74 mm.
- **Candidate result:** `text-over-body` reported one finding for the fault,
  identifying the note UUID and R1, and no finding for the control.
- **Native validation:** Digest-pinned KiCad 10.0.6 exports both synthetic
  schematics to netlist, ERC, and SVG. Native text-stroke bounds are
  x=71.1502..81.3103 mm for the fault and x=83.8502..94.0103 mm for the
  control, with the same y bounds; only the fault overlaps the body region.
  Component/pin assignments and nets match after excluding `Sheetfile`
  metadata, and all three ERC violation signatures match.
- **Decision:** Add a separate source-bound
  `schematic.free_text_over_symbol_body` rule using supported standard-font
  text and symbol envelopes. Keep it default-off with independent project
  review/block/off and exact-ignore dispositions. Do not adopt the candidate
  dependency or auto-move text.
- **Limit:** Axis-aligned glyph and body bounds can include empty space.
  Intentional annotation inside a symbol outline remains a review candidate;
  reviewer effort and false-positive rates on public projects are unmeasured.

##### Recorded trial: pcb-inspector deterministic PCB heuristics

- **Candidate:** `takzen/pcb-inspector`, commit
  `d29e1208d4cdcd07ebac7f8632c9554cbd18121b`, package version `0.1.0`,
  declared MIT license. Its isolated installation resolved the candidate's
  runtime stack, including `mcp 2.2.0`, `pydantic 2.13.5`, and `shapely 2.1.2`;
  all installation artifacts stayed in `/private/tmp`.
- **Invocation:** In the disposable Python 3.11 environment, ran
  `pcb-inspector analyze <synthetic-board.kicad_pcb> --output <report.json>
  --format json --config /private/tmp/pcb-inspector-trial/rules.yaml`.
  Only Layer 2 heuristics ran; native DRC, vision, MCP, live editing, and
  automatic fixes were not invoked. The candidate checkout, environment, and
  reports remained under `/private/tmp`.
- **Inputs and native comparison:** Synthetic differential-pair fixtures in
  `tests/fixtures/design_lint/differential-pair/`, plus local synthetic PCB
  geometry fixtures. Native DRC ran separately in the cached
  `kicad/kicad:10.0.6@sha256:18693567392b80da435f9fa952ce3a3e534c66eb5a6033f5b9c80aa3b19dd3ec`
  image, with source mounts read-only and receipts under `/private/tmp`.
  Configured pair rules produced `skew_out_of_range` on `fault-skew`; the
  same fault without its `.kicad_dru` rules produced only two unrelated
  dangling-track warnings and no pair finding. The compliant control produced
  no pair finding.
- **Observed candidate output:** With its default `max_diff_pair_skew_mm` of
  0.15 mm, pcb-inspector reported the synthetic 0.50 mm skew while the
  compliant control reported none. This demonstrates a unique review signal
  when project DRC constraints are absent, but the candidate's default limit
  is not an independently approved requirement for arbitrary interfaces.
  Equal-length `fault-gap` and `fault-uncoupled` cases produced no skew finding;
  the candidate does not replace native pair-gap or uncoupled-length rules.
  Its generic 0.25 mm VDD trace-width hint on the decoupling fixture did not
  match a project-authored width/current requirement and is not counted as a
  confirmed defect. Candidate-provided golden boards were not treated as
  independent evidence.
- **Incremental-value result:** Keep no runtime dependency. Adopt the bounded
  idea that recognized complementary net names without a reviewed pair map
  deserve a configurable REVIEW prompt. Local rule
  `signal.named_pair_without_reviewed_requirement` asks the project to review
  applicability and author limits; it intentionally does not copy the
  candidate's global 0.15 mm threshold or claim geometric adequacy. Native
  DRC remains the exact geometry check after a project-authored constraint is
  added.
- **Still unmeasured:** Results across the candidate's supported-version
  range, performance on larger boards, reviewer localization effort, and
  false-positive rates across real interface naming conventions. No private
  design was inspected.

##### Follow-up trial: pcb-inspector HEUR-GND-001 narrow-void pair (2026-10-08)

- **Candidate and provenance:** `takzen/pcb-inspector` at pinned commit
  [`d29e120`](https://github.com/takzen/pcb-inspector/tree/d29e1208d4cdcd07ebac7f8632c9554cbd18121b),
  package version `0.1.0`, declared MIT. The pinned `LICENSE` SHA-256 is
  `3eae2a63788fe64ea502c55590fd655b9193bee63180c3ee55b7836fad7b1cda`; the
  selected `return_paths.py` SHA-256 is
  `1ba2f3d991ef50c59ed3a1458342b93c6bd4b0e326d6d16725a5264fd8db9ef2`.
  The disposable Python 3.11 install resolved `mcp 2.2.0`, `pydantic 2.13.5`,
  and `shapely 2.1.2` along with the candidate's other declared dependencies.
  Checkout, environment, configuration, and reports stayed under
  `/private/tmp`; no candidate code was copied into Tooling.
- **Invocation:** Ran `pcb-inspector analyze <board.kicad_pcb> --format json
  --output <report.json> --config <rules.yaml>` twice for each fixture. The
  temporary config disabled native DRC/ERC and vision, enabled heuristics,
  and set `HEUR-GND-001.min_track_length_mm: 0.1` plus
  `min_referenced_fraction: 0.65`. These values include this 2 mm test route
  and separate its measured fault from its control; they are not product-board
  defaults or project requirements.
- **Inputs:** The same tooling-owned two-layer synthetic boards used by
  LINT-058: a 2 mm F.Cu `DATA` segment over a B.Cu `GND` fill with one endpoint
  through-via clearance; the fault adds a 0.2 mm midpoint notch. Source hashes
  are `2ac9f1f5680219ee04e3a27ac398922dbeede4abfd41a478a6b35eb035cc6113`
  (control) and `4d1a2f44dcc8f4eb8605d0668d3bb1556c94d49c849308b88082f31a2252a7fc`
  (fault). No external board or project expectation was used.
- **Observed result:** Both runs of the control passed with no findings. Both
  runs of the fault emitted one `HEUR-GND-001` warning on `DATA`, locating the
  segment midpoint at `(11, 13)` mm. Its report describes the full `2.0 mm`
  segment as affected and recommends expanding the ground pour; it does not
  report the exact uncovered interval or assign the notch to a physical cause.
  The candidate reads the filled copper contours from the PCB source directly
  and measures the route against them. Full report bytes include timestamps;
  after normalizing the timestamp and runtime, repeat reports matched with
  SHA-256 `a03e9ca10e19dc2649cdc50e57eb69f8b86405056d58d4cfe2fc94e3c0f3058d`
  (control) and
  `77e8b39c90c206bfcc4a4fe6a433ce4e3fcc7d9db46f52495129a38194dca6d8`
  (fault).
- **First-party comparison and disposition:** LINT-058 measures the same
  source-bound fixture pair at `2799/4000` for the control and `2399/4000` for
  the fault; with the same 0.65 review threshold, it passes the control and
  reports the fault. This candidate trial corroborates the narrow-void
  regression, but adds no distinct defect detection beyond LINT-058. Keep the
  first-party gate and its exact native evidence; do not add a runtime
  dependency. The candidate's segment-level output is less specific than the
  source-bound covered fractions and via-hole context already reported here.
  Like LINT-058, its result is a geometric review hint, not proof of actual
  return-current continuity or an electrical defect.
- **Still unmeasured:** Broader-board false-positive and false-negative rates,
  reviewer effort, and performance on large pours. The pinned KiCad 10.0.0 and
  10.0.5 hosted repeat for LINT-058 remains pending.

##### Recorded trial: KiDiff schematic revision comparison

- **Candidate:** [INTI-CMNB/KiDiff](https://github.com/INTI-CMNB/KiDiff), v2.6.0;
  commit `d77f103ca7c3580e28584eed209753818640d2b9`, GPL-2.0.
  The published `kicad10_auto:1.9.0` image was pinned to digest
  `sha256:493666a06d900ed3352c50b0f75a76ccdfe194999c097d455021cab9e3c723fa`;
  runtime reported KiCad/Pcbnew 10.0.4 and KiDiff 2.6.0. This is a
  cross-version research run: the fixture's original native contract evidence
  was generated with KiCad 10.0.6.
- **Installation and boundary:** Upstream documents a root-level `make install`
  that copies commands into `/usr/local/bin`; its Python package depends on
  KiAuto and still requires KiCad/Pcbnew, wxWidgets, ImageMagick, and PDF
  conversion tools. The host lacked several native dependencies, so the trial
  used the published Linux image. Only the synthetic fixture directory was
  mounted read-only; rendered files went to a separate temporary output
  directory. No cohort implementation or private design data was copied into
  this repository.
- **Reproduction:** From this repository root, set `IMAGE` to the digest above,
  `FIXTURES=tests/fixtures/design_lint/cohort-connector-ground-domains`, and
  `OUT` to a disposable directory, then run:

  ```sh
  mkdir -p "$OUT"
  docker run --rm --platform linux/amd64 \
    --mount type=bind,src="$PWD/$FIXTURES",dst=/trial/input,readonly \
    --mount type=bind,src="$OUT",dst=/trial/output \
    --entrypoint "" "$IMAGE" \
    kicad-diff.py /trial/input/control.kicad_sch /trial/input/fault.kicad_sch \
    --all_pages --no_reader --resolution 96 \
    --output_dir /trial/output --output_name split-returns
  ```

- **Inputs and observed output:** The public synthetic pair keeps both
  six-contact connectors and their four data contacts fixed while changing
  return labels from common `GND` to separate `GND1` and `GND2`. KiDiff emitted
  a one-page red/green PDF highlighting the changed labels at J1/J2 pins 1/2.
  Comparing the control with itself produced no colored changes. Each run
  exited successfully and emitted three non-fatal Pcbnew enum assertion
  messages on stderr. The full-page result makes the change visible, though
  the labels need zoom for comfortable reading.
- **Incremental-value result:** This is review visualization, not an electrical
  finding. The split-return fault already produces a Tooling `REVIEW` while the
  common-return control passes; KiDiff adds no unique detection and does not
  explain whether the split is intentional. A valid text-only or graphical
  edit would also be highlighted. Reviewer effort and general false-positive
  rates were not measured. Do not add a runtime dependency or use the visual
  diff as verification evidence; retain it as an optional human review aid.
- **Still unmeasured:** Other page layouts, larger schematics, unchanged
  geometry with text-only edits, reviewer localization time, and KiCad 10.0.6
  behavior. No auto-apply or source mutation was used.

##### Recorded trial: kicad-happy repeated-connector return domains

- **Candidate:** `aklofas/kicad-happy`, commit
  `a6bba1add1e18b89e3aa0824b9769ed1d9d79174`, declared MIT license. This is a
  second fixture batch for the same analyzer, not a second candidate tool.
- **Inputs:** The public synthetic fault/control pair in
  `tests/fixtures/design_lint/cohort-connector-ground-domains/`. Each of two
  identical six-contact connectors has four shared data functions and two
  `GND` pin functions. The fault assigns connector returns to `GND1` and
  `GND2`; the control assigns all four return contacts to `GND`. No proprietary board
  files or project-specific source were used. See the
  [fixture notes](../tests/fixtures/design_lint/cohort-connector-ground-domains/README.md)
  for the exact native and candidate analyzer observations.
- **Native evidence:** Exported both fixtures and ran ERC with KiCad CLI
  10.0.6. The netlists preserve the intended split-versus-common return
  topology. ERC emitted the same two synthetic-library warnings on each
  fixture and no connectivity violation; it does not infer the intended
  relationship. Tooling's `read_netlist` plus default `design_lint` policy
  returned `REVIEW` on the fault with `connector.repeated_pin_function` and
  `net.numbered_returns`, including the J1/J2 pin and net evidence. The
  control returned `PASS`.
- **Invocation:** Direct Python 3.11 script invocation, with no package
  installation, network lifecycle audit, or source copied from the candidate:

  ```sh
  python -B -I "$HAPPY/skills/kicad/scripts/analyze_schematic.py" \
    "$FIXTURES/fault.kicad_sch" --no-hierarchy --only-deterministic \
    --output "$OUT/fault.json"
  python -B -I "$HAPPY/skills/kicad/scripts/analyze_schematic.py" \
    "$FIXTURES/control.kicad_sch" --no-hierarchy --only-deterministic \
    --output "$OUT/control.json"
  ```

  Here `HAPPY` names the checkout at the commit above, `FIXTURES` names the
  fixture directory, and `OUT` is a scratch report directory outside source
  control. The native source checks were run serially to avoid concurrent
  KiCad CLI instance-lock cleanup.
- **Observed candidate output:** Both runs completed and returned five general
  findings; none identified the split return domains. The structured
  `ground_domains` output classified `GND1` and `GND2` as `signal` domains and
  reported `multiple_domains: false` for the fault. It likewise classified
  the shared `GND` net as `signal` and reported `multiple_domains: false` for
  the control. The connector ground-distribution audit emitted no actionable
  finding. Its documented `>4` signal-to-ground ratio is not a contract for
  whether matching returns on separate connectors share a net; even if this
  fixture's two return contacts are counted, its 4:2 allocation is below that
  threshold.
- **Incremental-value result:** No unique connector-return detection or useful
  review evidence was demonstrated. The analyzer did parse the connector pin
  maps, but did not surface the fault. The current Tooling check distinguished
  the pair using connector pin functions plus the numbered-return net names.
  Keep no runtime dependency and do not treat the candidate's ground-domain
  summary as evidence that numbered return nets are common.
- **Still unmeasured:** Candidate behavior on alternate ground naming,
  explicit intent/ground-domain configuration, other connector families, and
  reviewer localization time. Native ERC cannot establish the copper return
  path; PCB connectivity remains a separate verification lane.

##### Recorded follow-up trial: kicad-happy mapped generic supply contacts

- **Candidate:** The same `aklofas/kicad-happy` commit
  `a6bba1add1e18b89e3aa0824b9769ed1d9d79174`. Its deterministic `NT-001`
  implementation reports singleton nets; see the pinned
  [analyzer source](https://github.com/aklofas/kicad-happy/blob/a6bba1add1e18b89e3aa0824b9769ed1d9d79174/skills/kicad/scripts/analyze_schematic.py#L3695-L3755).
- **Inputs and execution:** The synthetic split-supply fault and common-net
  control in
  `tests/fixtures/design_lint/cohort-mapped-connector-supplies/` were analyzed
  twice each with `--no-hierarchy --only-deterministic`. Source hashes,
  commands, raw-report hashes, and stable projection hashes are recorded in the
  [fixture notes](../tests/fixtures/design_lint/cohort-mapped-connector-supplies/README.md).
  No board or candidate report was copied into Tooling.
- **Observed output:** The fault reports `NT-001` INFO findings for singleton
  `SUPPLY_ALPHA` on J1.1 and `SUPPLY_BETA` on J2.9; the common-net control has
  neither. Both reports say `ground_domains.multiple_domains: false`. A
  singleton `CHASSIS` prompt appears in both, while generic ESD, datasheet,
  sourcing, and lifecycle observations are outside this comparison. Raw JSON
  differs on repeat only because `inputs.run_id` and
  `capability_mode_ref.run_id` change; the canonical projection of ground
  domains and `NT-001` evidence is stable.
- **Local comparison and disposition:** Native-only Tooling lint has no
  repeated-role candidate for these generic pins. A complete source-matched
  map adds one `connector.repeated_pin_function` REVIEW with both `supply`
  roles and their exact shared `external-5v` domain; the common-net control and
  different-domain control pass. `NT-001` therefore adds a broad singleton-net
  review clue over the native-only baseline but does not identify a required
  relationship or establish a defect. The same candidate warning can apply to
  valid off-board power contacts, as recorded in the earlier connector trial.
  Treat this as review context, not a confirmed detection or a reason to add a
  second local rule. The source-matched local finding is more specific; no
  candidate dependency is justified.
- **Still unmeasured:** Reviewer time saved, field false-positive rate, and
  prevalence of this topology in non-confidential designs. Same-domain
  singleton rails may be intentional; project-authored connectivity remains
  the requirement that can make a mismatch blocking.

##### Recorded trial: kicad-happy IC power-pin DC-path audit

- **Candidate:** `aklofas/kicad-happy`, commit
  `a6bba1add1e18b89e3aa0824b9769ed1d9d79174`, declared MIT. Its `PP-001`
  detector walks from each `power_in` pin across selected low-resistance
  components and rejects capacitor edges; its documented implementation also
  skips named rails and connector-bearing nets. See the pinned
  [detector source](https://github.com/aklofas/kicad-happy/blob/a6bba1add1e18b89e3aa0824b9769ed1d9d79174/skills/kicad/scripts/signal_detectors.py#L4443-L4629).
- **Inputs:** Tooling-owned synthetic `fault.kicad_sch` and `control.kicad_sch`
  under `tests/fixtures/design_lint/cohort-power-pin-dc/`. The fault puts a
  `power_in` pin and a decoupling capacitor on generic `LOCAL_A`; the control
  changes only that net name to `+3V3`. The latter is only a detector
  non-finding control: neither file shows a source component. No proprietary material
  was used. The
  [fixture README](../tests/fixtures/design_lint/cohort-power-pin-dc/README.md)
  retains the source hashes and reproduction command.
- **Invocation:** Reused the pinned temporary cohort checkout and ran its
  script directly with the repository's Python 3.11 environment, `-B -I`,
  `--no-hierarchy`, and `--only-deterministic`. JSON reports stayed under
  `/private/tmp`. Both fault and control returned the same `PP-001` / `RS-001`
  result sets on a second run. Then exported the same synthetic fault and
  name-only control through digest-pinned KiCad 10.0.0 and 10.0.5, adding a
  source-backed `power_out` control. Each netlist and ERC report was generated
  twice in a network-disabled container with read-only fixture mount and
  reports under `/private/tmp`; normalized netlist contracts and normalized
  ERC violation details matched on repeat. Source hashes and reproduction
  commands are in the fixture README.
- **Observed output:** The fault produced heuristic `PP-001` (“no DC path to a
  power rail”) and `RS-001` (“no declared source”). The `+3V3` control omitted
  `PP-001` but still produced `RS-001`; it does not establish that naming a
  net is a valid source. The equivalent synthetic `NetlistContract` passed
  Tooling's current `design_lint.evaluate` with no candidate because no
  project-authored power-connectivity map was supplied. Native ERC reported
  `power_pin_not_driven` as an error on `U1.1` for both the `LOCAL_A` fault and
  the name-only `+3V3` control in KiCad 10.0.0 and 10.0.5. The source-backed
  control put `U1.1`, `U2.1` (`power_out`), and `C1.1` on `+3V3`; both native
  versions omitted `power_pin_not_driven`. Other library-table and isolated
  label warnings came from the minimal synthetic fixture and are not counted
  as source-path evidence.
- **Disposition:** Do not adopt `PP-001` as an additional detector for this
  case. It adds no finding beyond native ERC: KiCad already flags the
  undriven `power_in` pin whether its net is called `LOCAL_A` or `+3V3`, and
  clears that violation when a same-net `power_out` source is present. The
  cohort's more specific “no DC path to a power rail” wording may help
  localization, but reviewer effort was not measured. Keep source-backed
  power maps as the deterministic project-authored requirement; evaluate a
  broader path heuristic only against resistor, ferrite, fuse, jumper, and
  DNP controls where ERC behavior is measured separately. The candidate's
  error severity is not a local policy recommendation.
- **Not measured:** External connector sources, regulator-output and
  multi-stage paths, filters, ferrites, fuses, solder jumpers, DNP parts,
  internal rails, false-positive rate, and reviewer effort. The new control is
  synthetic ERC evidence only; it is not a power-source design recommendation
  or an electrical approval.

##### Follow-up trial: kicad-happy decoupling-presence detector

- **Candidate and source:** The same pinned kicad-happy checkout produced a
  distinct `DO-DET` observation for a fitted IC whose recognized positive rail
  had no capacitor symbol anywhere on that schematic net. The upstream
  detector is in the pinned
  [signal detector source](https://github.com/aklofas/kicad-happy/blob/a6bba1add1e18b89e3aa0824b9769ed1d9d79174/skills/kicad/scripts/signal_detectors.py#L3480-L3510).
- **Inputs and result:** The synthetic `no-cap.kicad_sch` fault is derived
  from the capacitor-bearing `+3V3` control in the preceding trial by removing
  its capacitor symbol and power pin connection. The candidate emits
  “IC U1 missing decoupling on +3V3” for the fault and “Decoupling coverage on
  +3V3” for the capacitor-bearing control. The result distinguishes capacitor
  symbol presence; it does not establish a datasheet requirement, value,
  placement, or physical return path.
- **Source-backed incremental-value follow-up:** Added a no-cap fixture with
  `U1.1` (`power_in`) and `U2.1` (`power_out`) connected to the same `+3V3`
  net, removing missing-source ambiguity. Repeated netlist and ERC runs on
  digest-pinned KiCad 10.0.0 and 10.0.5 show the expected two pin types on the
  same rail and no `power_pin_not_driven` violation; the normalized native
  reports match. LINT-046 emits its default `REVIEW` prompt for this fault,
  while the source-backed capacitor control passes without a prompt. The pinned
  kicad-happy analyzer was then run twice on each source-backed fixture. Its
  `DO-DET` findings distinguish the no-cap source-backed fault (U1 and U2
  reported missing decoupling) from the capacitor control (coverage reported
  for C1, no missing-decoupling finding). Both pairs of raw JSON reports were
  byte-identical on repeat. The extra U2 finding shows broader applicability
  than LINT-046's `power_in` target and is not counted as a confirmed defect.
  This corroborates review coverage over native ERC, not unique detection over
  the local heuristic. Fixture hashes, report hashes, reproduction command,
  and exact image digests are recorded in the
  [synthetic fixture notes](../tests/fixtures/design_lint/cohort-power-pin-dc/README.md).
- **PP-001 source-backed recheck (2026-09-30):** Repeated the pinned analyzer
  run on all four source-less and source-backed fixtures. Reports were
  byte-identical on repeat. `PP-001` remains limited to the `LOCAL_A` fault;
  it does not report on the source-backed no-cap case or capacitor control.
  On the name-only `+3V3` control, `PP-001` is absent while separate `RS-001`
  still reports that the rail has no source. This confirms no unique
  source-path coverage from `PP-001` for the source-backed pair. The same
  reports show `DO-DET` distinguishing capacitor presence, including a prompt
  on source component `U2`; applicability to U2 is not proof that it needs a
  capacitor. Full focused findings, candidate-source hashes, report hashes,
  and the command are recorded in the linked fixture notes.
- **PP-001 wrong-rail follow-up (2026-09-30):** Ran the same pinned analyzer
  twice on the native ferrite-path control and assigned-wrong-net fault. The
  fault produced `PP-001` for `U2.1`; the valid control produced none. Full
  report SHA-256 values repeated exactly: control
  `b65723f226bc985e3b46c5c760712f2f262fa414cc99ce00bb34e67efdc9c168`, fault
  `1d8b308e0baa0b252b1cae2f72835ce9b368db98ece7a015b36a0966cfd8d5a7`. The
  native fixture has zero ERC errors and identical violation types for control
  and fault. The authored LINT-055 map already catches the fault when supplied;
  without a map, the old local baseline returned no finding. LINT-056 adopts
  only a bounded default-`REVIEW` fallback for that uncovered configuration.
  It does not copy PP-001's “likely AC-coupled” claim or `error` severity. The
  pinned candidate source and fixture boundaries are recorded in the
  [power-path fixture notes](../tests/fixtures/design_lint/power-path-native/README.md).
- **Baseline and disposition:** The local schematic design-lint baseline had
  no equivalent prompt when no project-authored decoupling map was supplied.
  The existing `pcb.decoupling_proximity` rule is a separate opt-in PCB
  measurement requiring an authored pad map and threshold. Adopt the bounded
  presence prompt as LINT-046 with default `review`, based on its incremental
  review coverage and deterministic synthetic fault/control behavior. Keep it
  separate from mapped PCB placement checks and native ERC: ERC does not
  diagnose the absence of a capacitor symbol in this source-backed control.
- **Validation boundary:** Cohort runtime evidence covers source-less and
  source-backed synthetic no-cap fault/control pairs; the local source-backed
  fixtures are also native-validated on KiCad 10.0.0 and 10.0.5. Neither the
  cohort nor this heuristic determines
  whether a capacitor is required, its value, placement, or physical return
  performance. Internal, external, or off-board decoupling and uncommon
  capacitor or rail naming remain unmeasured.

##### Recorded trial: kicad-happy LED current-limiter prompt

- **Candidate:** [aklofas/kicad-happy](https://github.com/aklofas/kicad-happy)
  at commit `a6bba1add1e18b89e3aa0824b9769ed1d9d79174`, declared MIT. Its
  `validate_led_resistors` LR-001 detector uses component classification,
  assigned schematic nets, and conventional resistor topology; its source
  also estimates forward voltage and current from assumed color/default
  values. The direct inspection was limited to the pinned
  [LR-001 source](https://github.com/aklofas/kicad-happy/blob/a6bba1add1e18b89e3aa0824b9769ed1d9d79174/skills/kicad/scripts/validation_detectors.py#L1085-L1245).
- **Inputs and invocation:** Three tooling-owned KiCad schematic fixtures in
  `tests/fixtures/design_lint/cohort-led-resistor/` were parsed by the pinned
  candidate using Python 3.11, `-B -I`, `--no-hierarchy`, and
  `--only-deterministic`. The direct-rail LED fault emitted one LR-001 finding;
  the fitted series-resistor control emitted none; and the direct-rail fault
  with a parallel resistor also emitted none. The
  [fixture README](../tests/fixtures/design_lint/cohort-led-resistor/README.md)
  records all source hashes, commands, and candidate outputs. Repeating all three runs
  produced the same filtered LR-001 summaries. Reports stayed in ignored
  `build/`; no cohort implementation or project data was copied.
- **Baseline and disposition:** Before this local rule, Tooling's native
  netlist heuristic baseline had no LED current-limiting candidate. The trial
  supports a review prompt for the direct rail-to-return pattern and the
  series-resistor control. It also exposes a candidate miss: an across-rails
  parallel resistor is accepted as if it were in series. LINT-048 therefore
  keeps only a narrower direct-assignment predicate, which still reports this
  case. It does not import the candidate's guessed values, sizing, fixes,
  severity, or install flow.
- **Validation boundary:** These synthetic sources were accepted by the
  candidate parser but were not exported or checked by native KiCad in this
  environment. The cohort output and local candidate are review evidence only;
  they do not establish current, source limiting, resistor suitability,
  forward polarity, physical connectivity, or that every LED needs an external
  resistor. False-positive rate, reviewer effort, and the native ERC
  comparison remain unmeasured.

##### Recorded trial: kilint I2C address-map coverage

- Candidate: [romkey/kilint](https://github.com/romkey/kilint) at commit
  923320614b25ec0e5d2bc40d835b32233ad71f0c, version 0.5.1, declared MIT
  license. The cohort checkout and trial environment stayed under
  /private/tmp; no candidate code, project data, or fixture was copied into
  Tooling.
- Installation: Installed the local checkout into a disposable Python 3.11
  virtual environment. The global interpreter lacked PyYAML and hatchling;
  pip resolved kilint 0.5.1 and PyYAML 6.0.3 in the isolated environment.
  This requires Python packaging and a source checkout, but no native KiCad
  executable or GUI setup for this rule.
- Invocation: The isolated kilint CLI ran lint on each synthetic directory
  with a temporary config enabling only rule 20, i2c-address-declared, and
  JSON output. Each run used --fail-on error so the default INFO finding
  remained visible without making it an error gate.
- Inputs: Four independently constructed, minimal synthetic PCB S-expression
  files under /private/tmp/kilint-synthetic-trial: U1 on I2C1 SDA/SCL without
  an address property; the same IC with address 0x44; a connector-only
  control; and a U1 attached to SDA and SCL names that identify different
  buses. These files were parsed by kilint; native KiCad import/ERC was not
  run, so they test the candidate predicate and report, not KiCad file
  validity or copper connectivity.
- Observed output: The undeclared U1 produced one INFO finding naming U1 and
  both I2C nets. The declared-address, connector-only, and cross-bus controls
  produced no findings. The rule uses board pad-net names and U references by
  default; its address declaration is a kilint-specific property.
- Baseline comparison: Before the local rule, Tooling returned
  i2c_address_coverage status NOT_REQUESTED when the project omitted its map
  and emitted no missing-responder candidate. Its address comparison only
  covered responders already named by the project map. The candidate thus
  demonstrated unique review coverage on one synthetic fault, not new
  electrical detection or an address-collision check. False positives were
  zero on three controls; reviewer time and performance were not measured.
- Disposition: Keep no kilint runtime dependency. Implement the concept
  independently as bus.i2c_unmapped_responder: it uses native exported symbol
  pin functions and assigned nets, accepts U and IC reference prefixes,
  compares against the project address map, and participates in the existing
  review/block/off and exact-ignore lifecycle. This covers the missing-map
  case without importing kilint's parser, property convention, examples, or
  configuration format.
- Boundary: The local rule is still only a heuristic. Incorrect symbol
  function metadata and other reference prefixes can evade it; bridges or
  other intentionally unaddressed ICs can be review candidates. The project
  can list static or dynamic responders, turn the rule off, or record a
  reasoned exact ignore. No proprietary board or project-specific file was
  inspected.

##### Recorded trial: kilint I2C pull-up series-chain coverage

- **Candidate:** `romkey/kilint`, commit
  `923320614b25ec0e5d2bc40d835b32233ad71f0c`, version 0.5.1, declared MIT.
  Reused the disposable Python 3.11 environment recorded above. The tested
  `kilint/rules/i2c.py` SHA-256 is
  `c9b57c0b465066299c6833228ced91419aff8f14313f023fd047ade0313c4513`.
- **Predicate and data boundary:** Rule 18 (`i2c-pullups`) recognizes a
  configured `R`/`RN` component only when one board pad net is an I2C line and
  another pad net on that same component is a power net. It reads PCB pad-net
  assignments; it does not trace intermediate resistor nets or use component
  values. Two independently authored synthetic `.kicad_pcb` net-assignment
  fixtures stayed under `/private/tmp`: direct control hash
  `0831b5afbd2c1809c0e1739c60c01a6a959b75d623d602fbdad281f022a112e3` and
  two-resistor SDA chain hash
  `b79660dc39db6ae8ce390e2ceeaa0f84fdce8b558bfe95b9a8234fd49ce3180c`.
  They contain no copper geometry and were not imported or checked by native
  KiCad.
- **Invocation:** The prior isolated install supplied the `kilint` entry point;
  a temporary configuration enabled only rule 18. The config SHA-256 is
  `618dc3ffd9db29a76590a54d37e673944ad1ed704b4c39e94aa7419ae84fe5b3`.

  ```sh
  "$KILINT" lint "$FIXTURES/control" --config "$FIXTURES/kilint.yml" \
    --format json --fail-on error
  "$KILINT" lint "$FIXTURES/series" --config "$FIXTURES/kilint.yml" \
    --format json --fail-on error
  ```

- **Observed result:** The direct control produced no findings. The series
  fixture produced one rule-18 warning on `I2C1_SDA`; `I2C1_SCL` remained quiet
  because it had a direct resistor. Repeated output hashes matched exactly:
  control `ebda66d4aea6426d8f4bd751555878cba2e908780963c70975af842a55f65622`,
  series `3c6433ecc35b47db0db28471d7887ac8071a5538b922dce2054fec2fef5d6f64`.
- **Local comparison and disposition:** Tooling's bounded heuristic accepts
  the equivalent source-bound two-leg topology; the existing synthetic
  `2.2 kΩ + 2.2 kΩ` case totals 4.4 kΩ and passes. The focused tests for valid
  series paths and low-equivalent series paths passed (`2 passed`). The cohort
  rule therefore adds no unique finding for this fixture and misses a valid
  series-path alternative. Keep no kilint runtime dependency and retain the
  first-party series-chain behavior.
- **Limit:** This is a pad-net parser comparison, not a KiCad-native import,
  electrical simulation, or PCB-copper check. Resistor population state,
  branching, resistor arrays, internal pull-ups, field false positives, and
  reviewer effort were not measured in this candidate run.

##### Recorded trial: kicad-happy USB series-resistor prompt

- **Candidate:** [aklofas/kicad-happy](https://github.com/aklofas/kicad-happy)
  at commit `a6bba1add1e18b89e3aa0824b9769ed1d9d79174`, declared MIT. The
  `validate_usb_bus` PR-004 detector source is pinned at
  [validation_detectors.py](https://github.com/aklofas/kicad-happy/blob/a6bba1add1e18b89e3aa0824b9769ed1d9d79174/skills/kicad/scripts/validation_detectors.py#L894-L945).
- **Inputs and invocation:** Two tooling-owned synthetic schematic-parser
  fixtures in `tests/fixtures/design_lint/cohort-usb-series/` were analyzed
  with Python 3.11, `-B -I`, `--no-hierarchy`, and
  `--only-deterministic`. The candidate no-external-resistor fixture emitted
  one PR-004 prompt per data pin; the visible 22R-per-line control emitted
  none. Repeated runs produced identical filtered findings. The fixture README
  records hashes and commands. Reports stayed in ignored `build/`; no
  candidate code or product design was copied. No package installation or full
  candidate workflow was measured.
- **Baseline and disposition:** Before the source-backed project map was added, Tooling emitted the
  broader `signal.named_pair_without_reviewed_requirement` prompt on `USB_D+`/`USB_D−` for both the
  no-resistor candidate and resistor control. That prompt asks whether the names indicate a physical
  pair; it does not review resistor topology. The exact alias baseline is covered by
  `tests.test_design_lint.DesignLintTests.test_named_complementary_nets_prompt_for_reviewed_pair_requirements`.
  The candidate detector remains unadopted because its generic 15–33 Ω assumption prompts on a
  documented integrated-PHY direct path. The local exact map adds component topology coverage only
  when a project supplies its reviewed decision.
- **Validation boundary:** The fixtures test only candidate parser behavior
  on a two-pin named data pair. The no-external-resistor case is a candidate
  prompt, not a confirmed electrical fault. They do not model a complete
  connector, a documented PHY, USB-C, USB 3.x, resistor branches, or PCB
  routing. This candidate trial was parser-only and did not import/export with
  KiCad or compare ERC. Separate local LINT-049 native regressions, recorded in
  the source-backed PHY trial below, exercise synthetic direct, series, and
  bypass fixtures on pinned KiCad 10.0.0 and 10.0.5. Native ERC, electrical
  applicability, false-positive rate, and reviewer effort remain unmeasured.

##### Recorded source-backed USB PHY applicability trial

- **Candidate:** The same pinned kicad-happy checkout and `validate_usb_bus`
  PR-004 detector described above.
- **Manufacturer evidence:** ST AN4879 Rev 12 (June 2026), FAQ lines 914–918, says STM32 internal
  USB PHY pads include matching output impedance and need no external resistors. Its implementation
  table identifies STM32F103 as full-speed with an integrated PHY. TI's TUSB2036 Rev I datasheet
  (March 2017), Section 9.2, says USB DP/DM pairs require approximately 27 Ω series resistors.
  Links:
  [ST AN4879](https://www.st.com/resource/en/application_note/an4879-usb-hardware-and-pcb-guidelines-using-stm32-mcus-stmicroelectronics.pdf),
  [TI TUSB2036](https://www.ti.com/lit/ds/symlink/tusb2036.pdf).
- **Inputs and outcome:** `integrated-stm32-fs-direct` and
  `external-hub-no-series-resistors` each produced two PR-004 prompts;
  `external-hub-control-27r-series` produced none. Two repeated
  `--only-deterministic` runs per fixture had identical filtered output. The
  candidate distinguishes a visible 27R pair from no parts, but gives a false
  prompt for the source-backed direct integrated-PHY control.
- **Local comparison:** The project-authored `usb_data_path_map` accepts both
  the direct integrated-PHY control and the TUSB2036 27R control. Removing
  required R1 from the TUSB2036 synthetic native-netlist model produces one
  `bus.usb_data_path_mismatch` finding on D+. Existing named-pair review alone
  does not inspect that series component topology. DNP, wrong value, wrong
  endpoints, exact ignore, override, and disable paths are also regression
  tested.
- **Limits:** The cohort candidate run was a parser-only trial over synthetic
  schematic source, not native KiCad import. The separate LINT-049 native lane
  exports the direct, series, and bypass fixtures on pinned KiCad 10.0.0 and
  10.0.5 and checks the local rule against those parsed netlists. Native ERC,
  electrical qualification, the selected resistor range, false-positive
  rates, and reviewer effort remain open.

##### Recorded trial: kicad-happy singleton warnings on USB reference pins (2026-10-07)

- **Candidate:** The public `aklofas/kicad-happy` checkout at commit
  `a6bba1add1e18b89e3aa0824b9769ed1d9d79174`, declared MIT. The analyzer
  script and license hashes, invocation, fixture hashes, and repeat report
  hashes are recorded in the
  [USB peer-reference fixture record](../tests/fixtures/design_lint/usb-peer-reference-native/README.md).
- **Inputs and repeatability:** Ran the candidate's schematic analyzer twice
  on the tooling-owned direct-USB split-reference fault and common-reference
  control. Each same-input pair produced byte-identical full JSON reports.
  The candidate emitted the same two `NT-001` singleton-pin prompts for
  J1.4 `GND` and U1.3 `AGND` on both inputs; the complete candidate finding
  arrays were identical and contained ten findings each.
- **Incremental-value result:** The candidate did not distinguish the split
  reference from the common-reference control and added no unique
  reference-domain finding. The local typed heuristic does distinguish this
  synthetic pair, with a REVIEW on the split case and no peer-reference
  finding on the common case. The local KiCad-native export lane has not run
  on this host, so this is not a direct comparison on native-exported input.
  Keep the generic singleton analyzer unadopted for this use case.
- **Boundary:** This was a parser-only run of a direct script from the pinned
  checkout; its full installation workflow, native import/ERC behavior,
  reviewer effort, and field precision were not measured. No cohort code or
  external project source was copied into Tooling; the reports remained under
  `/private/tmp`.

##### Recorded trial: kicad-happy SPI chip-select pull-up prompt

- **Candidate:** [aklofas/kicad-happy](https://github.com/aklofas/kicad-happy)
  at commit `a6bba1add1e18b89e3aa0824b9769ed1d9d79174`, declared MIT. Its
  `validate_spi_bus` PR-002 source is pinned at
  [validation_detectors.py](https://github.com/aklofas/kicad-happy/blob/a6bba1add1e18b89e3aa0824b9769ed1d9d79174/skills/kicad/scripts/validation_detectors.py#L822-L844).
- **Inputs and invocation:** Four tooling-owned schematic-parser fixtures in
  `tests/fixtures/design_lint/cohort-spi-bias/` were analyzed with Python 3.11,
  `-B -I`, `--no-hierarchy`, and `--only-deterministic`. The no-pull-up case
  emitted one PR-002 prompt; a fitted 10k control emitted none. DNP 10k and 0R
  anti-controls also emitted none. Repeated runs produced identical filtered
  findings. The [fixture README](../tests/fixtures/design_lint/cohort-spi-bias/README.md)
  records hashes and commands; output stayed in ignored `build/`. No package
  installation or full candidate workflow was measured.
- **Baseline and disposition:** Tooling's existing LINT-045 rule reports the no-pull-up case,
  accepts the fitted 10k control, and still prompts for the DNP and 0R cases. Those controls are
  covered by
  `tests.test_design_lint.DesignLintTests.test_spi_active_low_select_bias_hint_is_review_only_and_configurable`
  and
  `tests.test_design_lint.DesignLintTests.test_spi_select_bias_hint_checks_recognized_paths_and_valid_controls`.
  PR-002 adds no new detection on this fixture set and misses two deliberately invalid paths by
  treating DNP and zero-ohm components as pull-ups. Keep no cohort dependency; the local rule
  already applies a fitted-state and resistance window and requires an explicit active-low input.
- **Applicability and boundary:** The synthetic pin belongs to a W25Q80BV-style flash device.
  Winbond's
  [W25Q80BV datasheet, section 4.1](https://www.winbond.com/upload/technical-support/f0f72951-b845-42ea-9010-faaeab26872f.pdf#page=7)
  says `/CS` must track VCC at power-up and describes a pull-up for cases where it is needed. This
  does not state that every board needs an external part; host reset-time drive must be reviewed.
  The fixture tests parser behavior, not a complete flash circuit or power sequence. Native KiCad
  import, ERC, and netlist comparison remain unavailable.

##### Recorded trial: kicad-happy PS-001 power-sequence cycle

- **Candidate and provenance:** `aklofas/kicad-happy`, commit
  `3cf837b2d6577d1369a45a36d5e9bac0e06ff5b6`, declares MIT in its
  [pinned license file](https://github.com/aklofas/kicad-happy/blob/3cf837b2d6577d1369a45a36d5e9bac0e06ff5b6/LICENSE).
  The pinned `validation_detectors.py` SHA-256 is
  `c62fd47cbafb506c730a34bcd6e07c36f8e550c50a0dd913402c326d8b996868`; the
  pinned `detector_helpers.py` SHA-256 is
  `68fdc890755b53be1e25f5a7d07f72a2a8ca30dc5b0b67f4e2dfafebbe4ebc63`.
- **Trial boundary:** Executed the source's `validate_power_sequencing`,
  `_get_pin_net`, and `match_ic_keywords` functions with a small synthetic
  `AnalysisContext` and an explicitly supplied regulator inventory. No package
  was installed, no candidate source was added to this repository, and no
  project design data was used. The candidate parser and regulator-discovery
  pipeline were not exercised.
- **Observed result:** The mutual-enable synthetic fault produced two `PS-001`
  cycle findings for the same two-stage cycle, one from each start node. The
  acyclic control produced no finding; repeated calls with the same input order
  returned the same summaries. No field precision, reviewer effort, or
  installation cost was measured.
- **Incremental disposition:** The detector's inferred regulator-output to
  enable-edge idea is useful when a project maps its exact stage endpoints but
  omits a dependency edge. LINT-062 adopts only this bounded prompt within the
  existing project-authored map: exact matching mapped endpoints form an
  output-to-enable cycle, and the local rule reports one `REVIEW`. It does not
  discover regulators from device names or create project requirements. The
  local prompt now passes a synthetic three-stage native export on pinned
  KiCad 10.0.0 and 10.0.5. The candidate's duplicate cycle emission and `error`
  severity are not adopted.
- **Remaining limits:** With no `power_sequence_map`, this remains an explicit
  coverage question. The local check cannot find unmapped stages and does not
  establish enable polarity, alternative control paths, startup state, timing,
  or physical behavior. One synthetic control does not estimate false-positive
  rate.

##### Recorded trial: kicad_skills `analog.no_dc_path`

- **Candidate and provenance:** `sabas0ba/kicad_skills`, commit
  `53d1af8bc550f60415b4b8e51a6d2d5924ada03f`, package version `0.1.0`, declared
  Apache-2.0. The pinned
  [rule source](https://github.com/sabas0ba/kicad_skills/blob/53d1af8bc550f60415b4b8e51a6d2d5924ada03f/src/eda_toolkit/kicad/sch_review.py)
  has SHA-256
  `fd7427eb29ee099e3cb8868869be8e8b75ed7d72aeba07ad1b4fa5a8e8597d54`; the
  pinned license file has SHA-256
  `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4`.
- **Installation and supported versions:** The current upstream README
  documents a Docker/Bash wrapper, a first-use image build of about five
  minutes, no network inside the container, and KiCad 9.0.9/10.0.4 image tags.
  The official container workflow was not built or run in this trial. Instead,
  the source package was built and installed without dependencies into an
  isolated Python 3.11 environment under `/private/tmp`, using the exact
  setuptools 83.0.0 build-backend pin from the candidate source. This measured
  only the `--no-cli` geometry-fallback path; the candidate's KiCad version
  compatibility remains untested.
- **Invocation and data boundary:** Ran
  `python -I -m eda_toolkit.cli sch review --no-cli --json --output <report> <fixture>`
  with the isolated interpreter against the three tooling-owned fixtures below.
  Their source hashes and native reproduction evidence are in the
  [fixture record](../tests/fixtures/design_lint/net-dc-reference/README.md).
  The checkout, environment, reports, and temporary files stayed under
  `/private/tmp`. No project design data, candidate source, fixture, or runtime
  dependency was added to this repository.
- **Observed results:** `analog.no_dc_path` appeared on the fitted-capacitor
  fault, stayed quiet on the output-driver control, and also appeared on the
  DNP-capacitor control. The DNP result is an overbroad warning against the
  local fitted-component predicate: the candidate groups `C`/`J`/`P` reference
  prefixes, requires a capacitor-prefixed pin, and does not inspect DNP state
  or exact symbol identity. The local rule reports the same fitted fault and
  excludes the DNP part. Local native KiCad 10.0.0/10.0.5 runs independently
  confirm the DNP control retains `C1`'s DNP flag and remains quiet; both
  candidate and local results remain heuristic prompts, not proof that a
  physical interface needs bias.
- **Incremental-value result:** No unique detection was demonstrated. The candidate duplicates the
  local finding on the fault and adds a DNP warning that the local fitted-part predicate
  intentionally suppresses. Its reports are pinned here for the fault
  (`73db4f5604b60adaaedc21ea807946669721cb3a27c433836a9c2ac302af6d29`), output-driver control
  (`6656ec89a49d24b69ce7d319a2709f1c3c59f22410449a9831c3162d3908d4b0`), and DNP control
  (`0406e85fcb7a8c4e82aba8d164864fa94cecdde80e4e4bdc63ef81da3127a702`). Do not adopt a runtime
  dependency for this rule.
- **Still unmeasured:** The official container build and invocation, native
  candidate netlist export, reviewer effort, behavior across the advertised
  KiCad matrix, and results on approved non-proprietary project data. The local
  native fixture result is not a field false-positive estimate.

##### Recorded trial: kicad_skills `analog.missing_decoupling`

- **Candidate and provenance:** `sabas0ba/kicad_skills`, commit
  `53d1af8bc550f60415b4b8e51a6d2d5924ada03f`, package version `0.1.0`, declared
  Apache-2.0. The pinned implementation is in the same
  [rule source](https://github.com/sabas0ba/kicad_skills/blob/53d1af8bc550f60415b4b8e51a6d2d5924ada03f/src/eda_toolkit/kicad/sch_review.py)
  as the `analog.no_dc_path` trial and has SHA-256
  `fd7427eb29ee099e3cb8868869be8e8b75ed7d72aeba07ad1b4fa5a8e8597d54`.
- **Installation and invocation:** Installed into the same isolated temporary
  Python 3.11 environment with `--no-build-isolation --no-deps`. The direct
  `python -I -m eda_toolkit.cli sch review --no-cli --json --output <report>
  <fixture>` invocation uses geometry fallback; it does not exercise the
  candidate Docker wrapper, KiCad CLI export, or native ERC. Reports were
  repeated and were byte-identical. Candidate source, environment, and reports
  remained outside this repository.
- **Inputs and results:** Six tooling-owned schematics in
  `tests/fixtures/design_lint/cohort-power-pin-dc/` cover no-cap and fitted-cap
  controls, an unrecognized-rail case, a source-backed fault/control pair, and
  a source-backed DNP-capacitor case. The candidate flags both fitted no-cap
  rails, stays quiet on fitted-cap controls and unrecognized `LOCAL_A`, and
  also stays quiet when the only capacitor is DNP. The two no-cap commands exit
  2 because an unrelated `power.no_ground` finding is an error; their JSON
  still contains the targeted warning. Report hashes and per-fixture outcomes
  are in the [fixture record](../tests/fixtures/design_lint/cohort-power-pin-dc/README.md).
- **Incremental-value result:** No unique detection over LINT-046 was shown.
  The fitted source-backed fault/control results duplicate the local
  review/control behavior. The DNP case exposes a candidate blind spot: its
  capacitor-prefix heuristic does not account for population state. Native
  KiCad 10.0.0 and 10.0.5 exports retain the DNP flag; LINT-046 still emits a
  rail-level review because no fitted capacitor connects the supply to return.
  This is synthetic regression evidence, not proof that a real board requires
  decoupling. Do not add a runtime dependency.
- **Still unmeasured:** The documented Docker workflow, native candidate
  export, advertised KiCad version matrix, reviewer effort, and behavior on
  approved non-proprietary project data. The fallback trial does not measure
  field precision.

##### Recorded trial: kicad_skills `analog.clock_no_series_resistor`

- **Candidate and provenance:** `sabas0ba/kicad_skills`, commit
  `53d1af8bc550f60415b4b8e51a6d2d5924ada03f`, package version `0.1.0`, declared
  Apache-2.0. The rule source and license hashes match the earlier
  `analog.no_dc_path` trial. Its implementation selects `X` references or
  `Oscillator:` library symbols, then judges only output-net component
  membership; it does not read a project-authored path map, DNP state, or
  resistor value.
- **Installation and version boundary:** Reused the isolated Python 3.11.16
  environment at `/private/tmp/eda-cohort-trial-venv` from the previous
  `kicad_skills` trial, built with its setuptools 83.0.0 pin and installed with
  `--no-build-isolation --no-deps`. Ran
  `python -I -m eda_toolkit.cli sch review --no-cli --json`; KiCad CLI was not
  available, so the result used geometry fallback without ERC or native
  netlist evidence. The Docker API socket returned permission denied, so the
  documented container workflow and advertised KiCad versions were not
  exercised.
- **Inputs and repeatability:** Seven tooling-authored schematics in
  `tests/fixtures/design_lint/cohort-clock-series/` cover direct output,
  direct output with a shunt pull, a fitted series-resistor control, a
  trial-designated direct-drive alternative, a DNP series component,
  a 1 MOhm series component, and a passive crystal. Every JSON report was
  byte-identical across two runs. Exact source and report hashes are in the
  [fixture record](../tests/fixtures/design_lint/cohort-clock-series/README.md).
- **Observed result:** The rule reported both direct-load fixtures, including
  the synthetic direct-drive alternative that the trial setup permits. It
  correctly reported that a shunt pull was not a series element,
  stayed quiet for the fitted series control and crystal control, and missed
  the DNP and 1 MOhm series-component cases. This is a fixture-relative
  over-prompt and two bounded predicate gaps, not a field false-positive rate
  or an electrical determination that any specific series value is required.
- **Incremental disposition:** The candidate supplies an understandable
  discovery hint, but does not compare a source-bound project expectation and
  cannot honor per-part direct-drive applicability. The synthetic run does not
  justify a generic first-party rule or a runtime dependency. A project-owned
  map could still compare exact output/load pins, direct-versus-series choice,
  part identity, DNP state, and a reviewed value range; design that separately
  only if a project has a reviewed clock-output requirement.
- **Still unmeasured:** Native KiCad netlist/ERC behavior, the documented
  candidate container workflow, reviewer effort, applicability on exact parts,
  and results on approved non-proprietary designs. No product or proprietary source
  was used.

##### Recorded trial: kicad-happy `GP-001` narrow reference-plane void

- **Candidate and provenance:** `aklofas/kicad-happy` tag `v2.3.1`, commit
  `06840467ad0f5d76af45f64449b1f5ecb10f052f`, declared MIT; the pinned
  `LICENSE` SHA-256 is
  `f542344efc2d21d18c81507e8168ab256c32ece6e7acb1bc8bde71950c9b6bb5`.
  The trial analyzed `skills/kicad/scripts/analyze_pcb.py` (SHA-256
  `943ae5f9c2db2f394b3965d13f68ae0e9e2f246c7773a725f9b9aa6116f878cd`)
  and `skills/emc/scripts/emc_rules.py` (SHA-256
  `9d77a407d6a8687f0e21b989e5dec18ed4e3f2c9f962da355a4338836deae2d1`).
  Its README documents PCB analysis for KiCad 6 through 10. The candidate says
  its analysis scripts need Python 3.10+ and no required packages; the trial
  cloned the repository under `/private/tmp` and invoked the selected scripts
  directly, without installing or copying candidate code into Tooling.
- **Inputs and invocation:** Two synthetic two-layer boards use a
  2 mm F.Cu `DATA` segment, a B.Cu `GND` zone, and the same endpoint through-via
  clearance. The control has continuous copper apart from that expected
  clearance. The fault adds a 0.2 mm notch across the route midpoint. Input
  board SHA-256 values are `2ac9f1f5680219ee04e3a27ac398922dbeede4abfd41a478a6b35eb035cc6113`
  (control) and `4d1a2f44dcc8f4eb8605d0668d3bb1556c94d49c849308b88082f31a2252a7fc`
  (fault). The selected analyzer was run with `python3.11 -I
  skills/kicad/scripts/analyze_pcb.py --full --only-deterministic
  --gp001-debug <board>` and its EMC consumer was run separately. Candidate
  The two candidate JSON output hashes repeated byte-for-byte. Control:
  `7bb3046edbde5db9ff20898ca92e1fef37d000b58d9af20c79f5386d071b85fb`;
  fault: `6d67504f9ce78180c283d9808fc373b44f4cc3319e03cfc2e87b00ee005d38da`.
  The original output receipts remain in temporary storage; only
  hashes and synthetic fixture identities are retained here.
- **Observed result:** GP-001 samples at a fixed 2 mm interval. On this 2 mm
  route it inspected only the two endpoints: the first sample was credited to
  the via's antipad, and the second found plane copper. It emitted no GP-001
  finding for either input, missing the narrow midpoint void. The EMC consumer
  also emitted “Return path analysis data not available” for both no-finding
  reports because the producer omits the empty analysis section; this is
  inconclusive evidence status, not a second electrical finding. Candidate
  outputs were deterministic across repeated runs.
- **First-party comparison:** LINT-058 measured the same native source-bound
  geometry with exact polygon/centerline intersection. With a fixture-only
  0.65 threshold, the intact control measured `2799/4000` and passed; the
  notched fault measured `2399/4000` and remained `REVIEW`. Both reports retain
  the endpoint via-hole context while counting its clearance as uncovered.
  Board hashes match the fixtures
  `kicad_tooling/hwrepo/fixtures/pcb-reference-narrow-void-control.kicad_pcb`
  and `...-fault.kicad_pcb`. The native probe snapshots repeated exactly on
  the installed KiCad 10.0.6 compatibility environment, with hashes
  `0e181b461e407af820a73335ea092d42488868231a58ed9bffef62dffb3fdbc0`
  (control) and `469f8970fe5e699172071d9771712b3e9b2e5a2cbb51e4d67b681d55a161bce9`
  (fault). A hosted repeat lane now runs the fault/control pair on the pinned
  KiCad 10.0.0 and 10.0.5 images; those exact-version results remain pending.
- **Disposition and limits:** The selected cohort heuristic misses this
  deliberately narrow defect; this comparison justifies retaining the
  first-party exact-geometry rule and regression pair. It does not establish a
  field miss rate, endorse the fixture's threshold for product boards, or
  prove return-current continuity. No cohort implementation, source board,
  proprietary project, or product expectation was adopted. Reviewer effort and
  long-term maintenance cost remain unmeasured.

The shipped `kicad_tooling/hwrepo/design-lint-rules.json` catalog currently
contains 85 active rules. Each entry has a deterministic predicate, evidence
adapter, exact supported KiCad profile boundary, maturity, limitations,
implementation references, and named synthetic fault and valid-control tests.
The schematic geometry rules default to `off`; other active rules default to
`review`.
The report carries this catalog and a SHA-256 digest of its packaged bytes.
Tests assert that catalog IDs match the closed policy type, each active rule is
reachable from a synthetic fault case, and every named fixture still exists and
runs. `synthetic_validated` means regression-tested against authored fixtures;
it does not claim field validation or effectiveness against private boards.

#### LINT-032 — Reproducible analyzer adapter contract

- **Status:** Backlog; needed only for adopted external analyzers.
- **Work:** Define a declarative adapter for executable/version, supported
  inputs, invocation, output normalization, timeout/failure semantics, source
  hashes, and license/provenance. CLI and MCP continue to call the same typed
  service.
- **Boundary:** No guessed executable paths, cross-environment Python imports,
  or silently relaxed source/version checks. A missing or failed analyzer is
  `BLOCKED`/unavailable evidence, not `PASS`.
- **Fixtures:** Tool absent; wrong version; malformed output; timeout; valid
  no-finding; finding with source locator; stale source hash.
- **Done when:** An installed wheel is tested against an external project
  checkout, generated receipts stay under ignored `build/`, and documented
  adapter exceptions have parity tests.

#### LINT-050 — MCU firmware pin-map consistency contract

- **Status:** Implemented as a typed, configurable design-lint rule.
  Synthetic service and CLI/MCP parity tests
  pass. Repeated exact-version native source-to-netlist regression lanes pass
  on KiCad 10.0.0 and 10.0.5.
- **Cohort input:** The public
  [STM32-KiCad-Pin-Checker](https://github.com/jbmata/STM32-KiCad-Pin-Checker) README describes
  comparing a KiCad `.net` export with STM32CubeMX `.ioc` `Signal` and `GPIO_Label` values, with
  user-authored aliases and ignored pins. It declares MIT and currently documents a Tkinter desktop
  workflow; CLI/CI appears on its roadmap. The inspected `ioc.py` recognizes selected `.Signal` and
  `.GPIO_Label` lines and strips suffix text after `-` when normalizing a port pin. No version or
  commit was pinned for this source inspection, no runtime trial was performed, and no candidate
  code was copied. Inspection of the published `main` source on 2026-09-30 shows suffixed keys
  normalize to one dictionary entry, where a later `Signal` assignment can replace an earlier one.
  The local parser now has a synthetic regression requiring conflicting suffixes for one physical
  pin to produce `BLOCKED` coverage instead of silently accepting one value. This is source
  inspection and local anti-control evidence, not a runtime evaluation of the GUI. See the
  [README](https://github.com/jbmata/STM32-KiCad-Pin-Checker) and
  [`ioc.py`](https://github.com/jbmata/STM32-KiCad-Pin-Checker/blob/main/ioc.py). The local parser's
  alternate-function key boundary was also checked against an
  [ST-maintained CubeMX `.ioc` sample](https://github.com/STMicroelectronics/STMems_Standard_C_drivers/blob/master/_prj_MKI109V3/_prj_MKI109V3.ioc)
  that uses suffixed physical-pin keys, including escaped spaces; the sample itself was not copied
  into the fixture set.
- **Problem:** A KiCad MCU pin can remain electrically connected while a
  schematic net assignment, CubeMX pin function, or CubeMX user label changes
  independently. ERC does not compare those two sources. The upstream
  desktop workflow is not a reusable CLI/MCP regression gate for this
  repository.
- **Contract:** The project-owned MCU pin-map contract names the
  exact MCU reference, native library symbol, part identity, and repository-
  local `.ioc` input. For every in-scope package port pin, author the exact
  matching KiCad symbol pin number, expected schematic net, and accepted
  CubeMX `Signal` and/or `GPIO_Label` values. The package-port-to-symbol-pin
  map and any cross-name aliases must be explicit; no pin-function guessing
  or fuzzy name normalization. Each excluded port pin requires a reason.
  Bind the contract, `.ioc` bytes, schematic, and exact-version native
  netlist to the same source-bound report.
- **Policy and coverage:** A fitted component whose value or symbol contains
  the literal `STM32` and has no map receives a visible review prompt. This is
  a bounded discovery hint; it does not assume CubeMX is the firmware source.
  A configured map compares exact part, symbol, package pin, KiCad symbol pin,
  schematic net, `.ioc` `Signal`, and any checked `GPIO_Label`. Default findings
  are `REVIEW`; project policy can promote the rule to `block`, set it `off`, or
  record an exact fingerprinted ignore. Missing `.ioc` evidence, duplicate or
  unsupported pin assignments, and changed source bytes are explicit coverage
  errors. Generic GPIO functions need an explicit expected label, including an
  explicit absent-label expectation, or a reasoned package-pin exclusion.
  The parser supports physical-port keys with hyphenated alternate-function
  names and CubeMX escaped-space forms; it does not normalize function or label
  values.
- **Boundary:** The check cannot establish that a project-authored
  package-to-symbol map is correct without a reviewed pinout source. It does
  not validate the MCU part's silicon capabilities, compile or inspect
  firmware, prove board routing, or establish off-board wiring. A matching
  contract only proves agreement among the declared expectation and the
  selected source-bound schematic and `.ioc` observations.
- **Synthetic fixtures:** Matching pin map control; swapped KiCad net; swapped
  CubeMX signal and label; missing IOC assignment; wrong symbol, DNP state, and
  symbol-pin inventory faults; exact accepted aliases; complete package-pin
  inventory with a reasoned exclusion; duplicate and unsupported IOC
  assignments; conflicting alternate-function suffix keys for one physical
  pin; semantically equivalent valid assignments in reordered lines with
  changed source hashes; unmapped fitted STM32 prompt with DNP control; source hash
  mutation; review/block/off/exact-ignore lifecycle; and CLI/MCP parity. The
  [synthetic input README](../tests/fixtures/design_lint/stm32-pin-map/README.md)
  documents the invented signal assignments and fixture scope.
- **Pinned native fixtures:** A valid synthetic four-pin MCU map, a schematic
  net drift, and a CubeMX signal drift each export twice and normalize to the
  same parsed netlist on pinned KiCad 10.0.0 and 10.0.5. The
  [fixture README](../tests/fixtures/design_lint/stm32-pin-map-native/README.md)
  records source hashes and the opt-in reproduction command. Additional native versions need
  their own pinned fixture lane. These lanes do not run ERC or DRC. No cohort
  runtime dependency or proprietary project source is required.
- **Done:** Typed contract and report models, bounded `.ioc` parser, source
  hashing, configurable review/block/off/ignore lifecycle, synthetic fault and
  control coverage, CLI/MCP parity, catalog/documentation, and repeated pinned
  KiCad 10.0.0/10.0.5 fixture exports are implemented. Silicon accuracy,
  firmware compilation, PCB routing, and field effectiveness remain outside
  this check.

#### LINT-033 — I2C responder-address collision review

- **Status:** Implemented; synthetic validation only.
- **Cohort input:** [kicad-happy](https://github.com/aklofas/kicad-happy)
  documents address-conflict detection as an analyzer family. This is a
  documented design input, not a benchmark or adoption of its workflow.
- **Evidence and check:** `design_lint.i2c_address_map` declares each segment,
  responder reference, exact symbol, SDA/SCL pins, seven-bit static address,
  and review basis. Strapped entries also declare each address bit's symbol
  pin/function and exact low/high nets. Complete strapped entries are checked
  for disagreement with the authored address; fitted complete responders at
  the same address on the same declared segment produce a collision finding.
  Rule overrides support `review`, `block`, and `off`; exact ignores use the
  standard fingerprint lifecycle.
- **Boundary:** No address is inferred from a value or reference string.
  Fixed addresses are authored expectations without pin derivation; only
  strapped address bits are resolved from the native netlist. Dynamic or
  unresolved entries remain coverage gaps. DNP entries do not enter collision
  groups. Firmware selection, off-board devices, part-pinout truth, and mux
  isolation are not inferred. Segment maps that share either signal net are
  rejected as ambiguous address domains.
- **Fixtures:** Same-segment collision; strapped-address mismatch; distinct
  strap values; same address on separate segments; unresolved strap; dynamic
  address; exact ignore and blocking override; DNP exclusion; invalid shared
  signal segment; CLI/MCP semantic parity. All fixtures are synthetic.
- **Done:** Schema, native netlist evidence, coverage status, deterministic
  findings, fault/control fixtures, docs, catalog entries, and parity tests are
  implemented. Continue validation with cohort-independent fault fixtures and
  identify missed applicable faults before changing maturity or default modes.

#### LINT-034 — External-interface protection coverage contract

- **Status:** Implemented v1; synthetic validation only. Exact direct-shunt
  channel maps and explicit `not_required` decisions are supported.
- **Inspiration:** [kicad-happy](https://github.com/aklofas/kicad-happy)
  documents ESD/protection coverage and mapping protection devices to
  interfaces.
- **Evidence and check:** A project contract names each reviewed connector pin,
  its expected connector symbol/footprint/net, and either an exact direct-shunt
  protection channel or a reasoned `not_required` disposition. Protector
  symbol/footprint, DNP state, complete pin inventory, mapped pin nets, and
  explicit unmapped-pin reasons are compared with the source-bound native
  netlist. Emits `protection.unreviewed_interface_pin` for missing
  applicability and `protection.mapped_device_mismatch` for source mismatches.
  Existing USB-C contract coverage handles CC, connector-side VBUS, and ground
  pins; connector pins whose observed net matches a mapped USB-C protector pin
  are also handled by that contract without duplicate prompts.
- **Boundary:** Never infer that every connector or signal requires a TVS/ESD
  part. A schematic does not establish clamp voltage, pulse rating, device
  suitability, placement, return-via geometry, or protection effectiveness.
  Existing USB-C contract findings must not be emitted a second time by a
  generic rule.
- **Fixtures:** Correct mapped protector; missing device; protector on the
  wrong signal; wrong return/reference pin; DNP option; incomplete device pin
  inventory; explicit unmapped-pin reason; explicit `not_required` decision;
  missing applicability; duplicate coverage against USB-C CC and signal
  protection contracts; CLI/MCP parity for a matching and mismatched map. All
  fixtures are synthetic.
- **Done:** Typed contract, source-bound coverage report, two catalogued
  review rules, review/block/ignore controls, CLI/MCP parity, and synthetic
  fault/control tests are implemented. This is not a field benchmark and does
  not validate protection effectiveness or physical return paths.

#### LINT-035 — Crystal/resonator load-network review

- **Status:** Implemented v1; synthetic validation only.
- **Inspiration:** [kicad-happy](https://github.com/aklofas/kicad-happy)
  documents crystal load-capacitor checks among its schematic analyzer
  families. The upstream documentation informed the candidate; no analyzer
  code, dependency, project data, or workflow was imported.
- **Evidence and check:** `design_lint.crystal_network_map` explicitly maps
  oscillator and resonator values, symbols, footprints, and pins; two load
  capacitors; their signal/reference pins and acceptable nominal values; the
  target load; and stray-capacitance range. The source-bound scanner checks
  exact identities, pin inventories, net assignments, DNP state, and supported
  capacitance text.
  It calculates `C1*C2/(C1+C2) + Cstray` and reports the inputs, assumptions,
  result, and native netlist digest. Missing or mismatched topology and values
  outside target produce a configurable review finding.
- **Boundary:** A schematic topology and nominal capacitance do not prove
  startup, frequency accuracy, drive level, parasitic capacitance, ESR margin,
  layout quality, or operation over environmental limits. The computation
  does not model capacitor tolerances. Do not infer a crystal requirement
  from `Y` references, value text, or symbol descriptions alone.
- **Fixtures:** Correct supported oscillator topology; missing one load cap;
  cap attached to the wrong oscillator pin; potential unlisted parallel load
  capacitor; correct alternate supported topology; unsupported internal
  oscillator; DNP load option; missing profile
  input; unsupported capacitance spelling; and values at and outside authored
  target bounds. All tests use synthetic inputs.
- **Done:** Typed project map, source-bound coverage, review/block/off controls,
  one catalogued deterministic rule, report evidence, CLI/MCP parity, and
  independently calculated synthetic fault/control tests are implemented.
  The nominal estimate and its unverified performance questions are explicit.

#### LINT-036 — Regulator feedback/setpoint plausibility review

- **Status:** Implemented as `power.regulator_feedback_mismatch`; synthetic
  regression-tested in the shared design-lint service and CLI/MCP parity lane.
- **Inspiration:** [kicad-happy](https://github.com/aklofas/kicad-happy)
- **Cohort evidence:** Current project documentation describes a deterministic
  extraction step, regulator feedback-divider calculations, part-family Vref
  lookup with a heuristic fallback, and a separate review pass. Its example
  shows Vfb derived from output and divider values. This is a documented
  capability, not a run or independent performance measurement.
- **Evidence and check:** A project-owned `regulator_feedback_map` names the
  exact adjustable regulator and two resistor identities, output/reference
  nets, mapped pin numbers and regulator pin functions, allowed nominal
  resistor-value ranges, reviewed feedback-reference bounds, target output
  range, and basis. The service
  checks native pin inventory and connectivity, DNP state, recognized direct
  resistors touching the feedback node, source-bound values, and
  `Vout = Vref * (1 + Rupper/Rlower)`. Reported nominal bounds use observed
  resistor values and the authored Vref range.
- **Incremental-value test:** A synthetic upper-resistor mutation leaves the
  existing power source/load membership check at PASS while the new lint
  reports OUT_OF_RANGE with the resistor values, mapped nodes, equation,
  output interval, target range, and project basis. The local source/load
  membership check has no setpoint predicate. A project-specific SPICE model
  may evaluate the output independently; that model-dependent comparison and
  the cohort tool's runtime were not benchmarked.
- **Boundary:** Only the mapped conventional non-inverting two-resistor DC
  divider is evaluated. Do not infer device type, topology, or Vref from an IC
  name. Alternate topologies and fixed-output regulators need separate
  authored profiles and supported equations. Nominal value ranges do not model
  resistor tolerance. The check does not prove stability, compensation,
  startup, load response, device ratings, copper continuity, or PCB feedback
  routing. Extra recognized fitted direct resistors touching FB make coverage
  incomplete; resistor arrays and unrecognized branches are not detected.
- **Fixtures:** Exact adjustable divider and Vref bounds; missing FB pin;
  wrong output/reference net; stale regulator identity; changed resistor value;
  unsupported value; DNP resistor; extra direct fitted resistor on FB;
  compensation capacitor; unmapped fixed-output control; and a non-finite
  arithmetic range that must report incomplete coverage. All are synthetic.
- **Done:** Typed project map, source-bound coverage report, review/block/off
  policy, catalogued rule, CLI/MCP parity, and an explicit synthetic baseline
  test are implemented. No external cohort source, dependency, or private
  project fixture was imported.

#### LINT-037 — Project-scoped first-order RC filter review

- **Status:** Implemented as `filter.rc_corner_mismatch` with synthetic tests,
  source-bound coverage, project review/block/off decisions, and CLI/MCP parity.
- **Inspiration:** [kicad-happy](https://github.com/aklofas/kicad-happy) documents
  passive-network analysis that estimates RC corner frequencies. Its published
  repository declares the MIT license. No source, project example, or dependency
  was imported.
- **Problem:** A connected resistor and capacitor can have valid net assignments
  while nominal values put a reviewed input filter outside its intended
  frequency range.
- **Evidence and check:** An optional project map names the exact resistor and
  capacitor identities, symbols, footprints, pins, input/signal/reference nets,
  accepted nominal value ranges, target cutoff range, and design basis. For the
  explicitly supported series-R / shunt-C low-pass topology, verify the native
  pin map and fitted state, parse the observed values, calculate the nominal
  corner, and emit a review finding when the value or topology misses the authored
  target. The map must be absent by default; no topology is inferred from
  reference or value text.
- **Incremental-value test:** A synthetic capacitor-value mutation preserves
  all pin-to-net assignments while the rule reports the calculated corner and
  authored target. This adds a source-bound schematic-value comparison beyond
  connectivity. The existing SPICE lane evaluates separately authored decks;
  equivalent SPICE coverage was not claimed or benchmarked.
- **Boundary:** The first-order formula does not model source or load impedance,
  multiple poles, active filters, component tolerance, transient behavior,
  anti-alias performance, or analog-front-end safety. Unsupported networks and
  incomplete value parsing produce incomplete coverage, not a pass. The extra
  part scan recognizes supported two-pin resistor/capacitor reference patterns
  only. Coverage does not establish electrical approval or PCB connectivity.
- **Fixtures:** In-range single-pole low-pass; changed capacitor value with
  unchanged pin/net assignments; wrong capacitor net; disconnected reference;
  DNP part; unsupported resistor value; wrong symbol identity; missing pin
  inventory; extra fitted parallel resistor/capacitor; block, off, and exact
  ignore decisions; no-map control; CLI/MCP parity. All inputs are synthetic.
- **Done:** Typed source-bound coverage, fault and control cases, value-mutation
  incremental test, CLI/MCP parity, and catalog/docs are implemented. No
  cohort source, dependency, proprietary board, or project fixture was imported.

#### LINT-038 — Connector return-distribution review

- **Status:** Implemented as `connector.return_distribution` with synthetic fault
  and control cases, source-bound connector coverage, project review/block/off
  decisions, exact ignores, and CLI/MCP parity.
- **Inspiration:** [kicad-happy](https://github.com/aklofas/kicad-happy) reports
  a signal-to-return contact ratio as a connector review metric. Its published
  repository declares the MIT license. That example threshold is not a
  universal requirement and will not be copied as a default.
- **Problem:** Existing rules can flag absent returns and return-function pins
  that disagree across connectors, but they do not summarize whether a
  reviewed external interface allocates enough return contacts for its signal
  count.
- **Evidence and check:** The project interface catalog can label each pin as
  `signal`, `return`, `supply`, `shield`, or `other`. An opt-in project map
  names an interface, minimum signal-contact count, maximum signal-to-return
  ratio, and basis. The checker counts mapped contacts in each role; supply,
  shield, and other contacts do not enter the ratio. An out-of-range ratio or
  missing role evidence produces a review candidate with exact pin lists and
  counts. No project threshold means `NOT_REQUESTED`. The ratio never infers a
  common net; exact shared, bonded, or isolated relationships remain in
  `pin_connectivity` and `grounding` contracts.
- **Incremental-value test:** Compare against
  `connector.repeated_pin_function`, `connector.no_connected_return`, and
  connector-coverage findings. On a synthetic connector with six signal
  contacts and one connected return, the existing missing-return and repeated
  return checks stay quiet while this project threshold emits the distinct
  6:1 distribution question. Two returns meet an inclusive 3:1 boundary;
  splitting their nets does not change the ratio result, while the existing
  repeated-return rule independently asks for review.
- **Fixtures:** Many-signal connector with one connected return; exact 3:1
  boundary with two returns; shared and split return nets; supply and shield
  excluded; below-scope power connector; missing/unaccounted pin roles; no
  threshold; review, block, off, exact ignore; CLI/MCP parity. All inputs are
  synthetic.
- **Boundary:** The ratio is a project-authored review threshold, not a
  universal electrical standard or proof of return-current capacity, copper
  continuity, shield termination, chassis bonding, isolation, off-board
  wiring, or physical assembly. A split-net return can be intentional; the
  established repeated-return candidate remains an independent review signal.
- **Done:** Role-based source-bound coverage, configured thresholds, distinct
  fault/control fixtures, CLI/MCP parity, and catalog/docs are implemented.
  No cohort source, dependency, proprietary board, or project fixture was
  imported.

#### LINT-039 — Explicit switching-loop edge and copper-geometry evidence

- **Status:** Implemented v1 within the documented boundary. Native track
  geometry-kind, endpoint pad/via contacts, and same-layer track adjacency use
  PCB snapshot schema 8; schema 9 adds canonical integer-nanometer filled-zone
  island outlines and holes; the active probe now emits schema 10, adding
  target aperture shape and diameter to access-probe observations. Current
  source-bound geometry scans require schema 10. The opt-in edge map resolves a unique trace chain
  and measures its centerline length; plane edges identify one shared island
  and report its contour area. The exact-version native fixture lane passed on
  digest-pinned KiCad 10.0.0 and 10.0.5, and the installed-wheel external-project
  gate passed on 2026-09-29. Component internals and full routed-loop area remain
  explicitly deferred.
- **Problem:** LINT-023's pad-center polygon is deterministic but does not follow
  the copper route. The native snapshot retains track endpoints, pad/via
  contacts, and native track adjacency, yet the ordered pad list does not say
  which adjacent pads connect through a routed trace, through a component, or
  through a filled plane. A same-net connection can also branch or have
  multiple routes. Guessing these edge roles would turn geometry into invented
  circuit intent.
- **Evidence and check:** The opt-in project-owned edge map covers every loop
  edge with an explicit role and exact endpoint pads. Supported trace edges
  bind the expected net and layer scope, resolve a unique native track chain,
  and report ordered integer-nanometer vertices and length. Component edges
  remain explicit transitions between mapped pins; plane edges verify a shared
  native filled island and report its contour area when schema 9 evidence is
  present. Return `INCOMPLETE` for
  missing edge evidence, unsupported arc geometry, branch ambiguity, stale
  pads, or a route that cannot be uniquely resolved. The current result reports
  the pad-center area proxy and per-edge trace lengths; it does not calculate a
  full routed-loop polygon or area. The contour area is not a current-density,
  parasitic, or electrical-performance estimate.
- **Evidence foundation:** Snapshot schema 8 records each track's segment/arc kind, pad/via
  contacts, and connected tracks at endpoints. Native effective copper shapes determine
  pad/via/track contact, and track candidates come from `CONNECTIVITY_DATA.GetConnectedTracks`. The
  schema checks that every contact refers to a same-net observed object. Native fixtures have
  exercised the synthetic two-segment trace chain and an unsupported arc on KiCad 10.0.0 and 10.0.5.
  Python fixtures test detours, missing and ambiguous paths, arcs, and a 1,100-segment chain. Schema
  9 copies each native filled polygon set and calls `SHAPE_POLY_SET.Unfracture()` before reading its
  filled-island outlines and holes; this preserves clearances represented as slit contours without
  modifying the board or its native fill state. It then canonicalizes integer-nanometer rings.
  API-shaped test doubles exercise ring rotation and direction normalization, duplicate-point
  cleanup, hole ordering, and degenerate-ring rejection. The hosted fixture lane passed all four
  cases twice on both digest-pinned KiCad 10.0.0
  (`ghcr.io/kicad/kicad:10.0.0@sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3`)
  and KiCad 10.0.5
  (`ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`).
  It asserts the synthetic inner-plane bounds are exactly 6 mm square, and requires plane route
  evidence to contain a zone identity and positive contour area. The fixture maps a foreign-net
  through-hole VDD pad inside the plane; the native hole ring around it has exact bounds
  12.3995–13.6005 mm on both axes, and the pad remains outside the GND connected-island inventory.
  The lane also confirms the 15 mm route chain, keeps arc geometry unsupported, and reports the
  split plane as incomplete. A first native run exposed that the synthetic front-plane map placed
  its return pad outside its zone; the fixture zone was extended to cover that mapped pad before the
  successful version matrix. Python fixtures verify exact hole-subtracted area and that multiple
  candidate islands remain ambiguous. Contours do not establish electrical current distribution. See
  the
  [KiCad `SHAPE.Collide` API](https://docs.kicad.org/doxygen-python-10.0/classpcbnew_1_1SHAPE.html),
  [`PAD.GetEffectiveShape`](https://docs.kicad.org/doxygen-python-10.0/classpcbnew_1_1PAD.html), and
  [`CONNECTIVITY_DATA.GetConnectedTracks`](https://docs.kicad.org/doxygen-python-10.0/classpcbnew_1_1CONNECTIVITY__DATA.html)
  references.
- **Boundary:** This comparison must not infer that similar nets should join,
  select a current path through a branch, or claim loop inductance, return
  adequacy, emissions, thermal performance, or electrical behavior. A routed
  centerline polygon is still a geometric screen; a large filled-zone contour
  is not an electric-field or current-density model. Project-authored topology
  and reviewed limits remain required, and the default policy stays `review`.
- **Fixtures:** Two-segment native same-layer chain; synthetic detoured trace
  whose centerline length changes while pad centers remain fixed; missing
  segment; disconnected endpoints; alternate paths and branch spurs;
  unsupported arc; a 1,100-segment route; a multi-layer trace through a via and
  an out-of-scope via fault; explicit component edge; synthetic filled-plane
  hole and area-subtraction control; ring-rotation, reversal, duplicate-point,
  hole-order, and degenerate-ring controls; valid multi-layer plane transition;
  exact native inner-plane outline bounds and a non-empty clearance-hole ring; multiple
  shared plane identities; intentionally incomplete map; and exact boundary
  values.
  The hosted native fixture lane runs each case twice on supported KiCad images
  and preserves source, probe, and toolchain hashes.
- **Incremental-value test:** Show which synthetic route mutations leave the
  pad-center proxy unchanged but change the per-edge measured trace. Also show
  that ambiguous and unsupported routes become incomplete rather than
  selecting a convenient path. A full routed-area metric needs separate
  geometry support for component and zone transitions before it can be
  evaluated against an independent oracle.
- **Done when:** Typed project map, source-bound native evidence, deterministic
  exact-version route and contour fixtures, clear unsupported-state reporting,
  review/block/off and exact-ignore behavior, docs, catalog coverage, and CLI/MCP
  parity (if surfaced) pass the installed-package verification lane.
- **Implementation note:** Initial inspection found that native snapshots
  captured track endpoints and filled-zone island identities without contours.
  Schema 8 added pad/via contacts and native track adjacency; schema 9 adds
  canonical filled-island outline and hole rings; schema 10 adds access-probe
  target aperture shape and diameter. Python analysis resolves only
  unique native trace chains; component internals and full routed-area
  comparison remain future work.

#### LINT-040 — Numbered positive supply-rail review

- **Status:** Implemented as `net.numbered_power_rails` with synthetic fault
  and control cases, review/block/off behavior, and CLI/MCP parity.
- **Cohort failure input:** kicad-happy issue
  [#40](https://github.com/aklofas/kicad-happy/issues/40) reports that its
  name-based PCB power analysis can skip ordinary channel labels such as
  `CH2_VDD` when rail metadata is absent. This tooling does not infer power
  roles or claim that sibling rails should be commoned. The review candidate
  now recognizes the bounded `P`, `CH`, and `RAIL` numeric-prefix forms before
  allowlisted positive-supply stems, so those naming patterns receive an
  explicit human review prompt.
- **Problem:** Connector pin-function matching is useful when symbol metadata
  is recognizable. It can miss sibling supply domains when connector pins
  have numeric or generic functions and their net labels carry the only clue.
- **Evidence and check:** The source-bound KiCad 10 netlist groups names with
  either an explicitly delimited numeric suffix or a bounded `P`, `CH`, or
  `RAIL` numeric prefix when the remaining stem is in a bounded allowlist of
  positive supply names. It emits exact net-to-pin evidence for groups with
  distinct indexes. A small shared-alias map
  treats `+5V`, `5V`, and `5.0V` as one family, along with selected named
  domains such as `VDD`, `VBUS`, and `VIN`.
- **Boundary:** Similar names are only a review clue. These rails can be
  intentionally isolated or supplied independently. The check does not infer
  a connector pin's function, voltage, source capability, required tie,
  off-board path, or PCB continuity. Compact suffixes without a separator are
  deliberately excluded to avoid interpreting voltage digits as indexes.
  Prefix recognition is limited to `P<number>_`, `CH<number>_`, and
  `RAIL<number>_` forms with a recognized supply stem; labels like
  `AUX_5V` or `DC_IN_RAW` are not classified by this rule.
- **Fixtures:** `+5V_1` and `5V-2` on generic connector pins with a third
  corresponding power pin left unassigned; `CH2_VDD`/`CH3_VDD`, `P1_5V`/
  `P2_5.0V`, and `RAIL4_VIN`/`RAIL5_VIN` prefix forms; signal-name,
  unlike-stem, single-rail, common-rail, and compact ambiguous `+5V1`/`+5V2`
  controls; block/off decisions; CLI/MCP parity through the shared design-lint
  service. The `CH2_VDD`/`CH3_VDD` fault and common-net control also export
  twice on pinned KiCad 10.0.0 and 10.0.5; source hashes and exact endpoint
  evidence are recorded in the
  [native fixture README](../tests/fixtures/design_lint/cohort-channel-power-names/README.md).
- **Done:** Cataloged deterministic candidate, exact evidence, conservative
  name controls, policy behavior, and CLI/MCP parity are implemented. This is
  a review signal, not electrical approval or a project wiring requirement.

#### LINT-041 — Named complementary-net pair review

- **Status:** Implemented as
  `signal.named_pair_without_reviewed_requirement` with synthetic fault and
  valid-control cases and the shared design-lint policy lifecycle.
- **Inspiration and evidence:** The read-only `pcb-inspector` trial above
  found a 0.50 mm synthetic skew that native DRC did not report when the
  project pair-rule file was absent. Its 0.15 mm threshold is only a candidate
  default, not a universal requirement. The local rule addresses the missing
  review coverage without adding a guessed geometric threshold.
- **Predicate:** Two populated native-netlist nets have an exact complementary
  suffix pair (`_P/_N`, `_DP/_DM`, `_TXP/_TXN`, `_RXP/_RXN`, `_H/_L`, `+/-`,
  `DP/DM`, `P/N`, or `H/L`) and the exact oriented pair is absent from the
  project-owned `pcb_differential_pair_rule_map`.
- **Boundary:** This only identifies a name-pattern candidate. It cannot
  establish that the nets are a differential interface, inspect board routes,
  or choose width, gap, skew, or uncoupled-length limits. An explicit map
  suppresses the missing-requirement prompt; LINT-022 still checks whether its
  named bounds have exact active native DRC coverage. The finding defaults to
  review and can be blocked, disabled, or exactly ignored per project.
- **Fixtures:** Populated `USB_DP`/`USB_DM` pair without a map; exact project
  pair-map control; ambiguous short names `VIP`/`VIN`; review, block, off, and
  exact-ignore decisions; CLI/MCP parity through the shared typed service.
- **Done:** The rule is cataloged, source-netlist based, deterministic,
  synthetic-tested, and does not assign electrical limits from naming.

#### LINT-042 — Likely I2C responder address-map coverage prompt

- **Status:** Implemented as bus.i2c_unmapped_responder with a synthetic fault,
  mapped-responder and non-IC controls, and project rule-mode coverage.
- **Inspiration and measured input:** The LINT-031 kilint 0.5.1 trial found a
  synthetic IC attached to SDA and SCL without an address declaration. The
  local baseline did not emit a candidate when the project address map was
  absent. The candidate rule's board-name predicate was not adopted.
- **Predicate:** For non-DNP U- or IC-prefixed components, use native symbol
  functions and source-bound net assignments to find uniquely assigned SDA
  and SCL pins on distinct nets. Prompt when that reference is not listed in
  the project-authored I2C address map, including when the map is absent.
- **Boundary:** This is a review prompt; it does not infer addresses or prove
  that a device is an I2C responder. Reference conventions are limited to U
  and IC, and recognized pin functions are limited to SDA, I2C_SDA, SCL, and
  I2C_SCL after punctuation normalization. Bridges and other intentionally
  unaddressed parts may need an exact ignore or project rule override.
  A mapped reference is considered covered here; wrong identity, pins, and
  addresses remain the map comparison's separate findings. DNP parts and
  unassigned signal pins are excluded.
- **Fixtures:** Missing address map; incomplete map with an unlisted peer;
  listed responder; non-IC connector; DNP part; block/off mode; CLI/MCP parity
  through the same typed design-lint service. All inputs are synthetic.
- **Done:** The catalog entry, source-bound candidate, project review policy,
  synthetic regressions, user documentation, and explicit CLI/MCP parity
  assertion are implemented. The rule remains review-only by default; no
  external dependency or private board source is used.

#### LINT-043 — Exact-symbol connector peer-pin outlier review

- **Status:** Implemented v1 as a review-only native-netlist heuristic for
  same-symbol connector contacts whose pin-function metadata is incomplete.
- **Problem:** A generic or unnamed contact can be unconnected, or assigned to
  a minority net, while matching connector instances assign that pin
  consistently. Function-based comparison may not have a usable pin role.
- **Predicate:** For fitted J/P/X/CN references using one exact library symbol,
  compare each pin number's schematic net assignments. Report an unconnected
  peer when another instance is connected, including a two-instance group, or
  a differing assignment when a unique most-common assignment is shared by at
  least two instances. Require at least one peer to lack exported pin-function
  metadata; tied assigned-net patterns remain under
  `connector.peer_pin_assignment_divergence`, and fully named pin groups remain
  under `connector.repeated_pin_function`.
- **Boundary:** Matching symbol contacts are only comparable candidates; they
  do not prove the contacts should share a net. Per-port isolation, optional
  pins, and intentionally unused contacts can be valid. An explicit native
  no-connect marker remains an unassigned contact for this comparison: the
  rule still asks for review when its same-symbol peer is assigned. A marker
  alone does not resolve the interface requirement. Unusual connector
  reference prefixes, missing symbol identity, and absent native pin-number
  inventory are outside the rule. DNP instances are excluded. The check does
  not prove PCB copper or off-board continuity.
- **Fixtures:** Missing generic contact; minority-net outlier; consistent
  common assignment; a two-connector open-contact fault with common-net and
  exact-ignore controls; an explicit no-connect-marker peer fault; all-distinct
  independent ports; DNP outlier; named-pin rule control; project block/off
  overrides and exact fingerprinted ignore.
  The native fault/control set in the tooling-owned
  [fixture README](../tests/fixtures/design_lint/generic-peer-pin-assignment-native/README.md)
  confirms that KiCad retains symbol pin-number inventory when the pin function is
  empty. Its fault localizes open J3.1 while J1.1 and J2.1 share `+5V`; the
  minority-net fault localizes J3.1 on `+3V3` while J1.1 and J2.1 share
  `+5V`. The common-net control passes without findings.
- **Native evidence:** `tests.test_ci_hosted.NativeConnectorReturnFixtureTests`
  exports the minimum two-connector open-contact fault, an explicit
  no-connect-marker peer fault, and the common-net control, plus the
  three-connector unique-minority fault and common-net control, twice with
  digest-pinned KiCad 10.0.0 and 10.0.5. The two-connector open and marked-open
  faults both localize J2.1 when J1.1 is assigned `+5V`; the common-net control
  assigns both pin 1 contacts to `+5V` and passes. The same lane also
  exercises the separate no-majority divergence case recorded under LINT-047.
  It validates source hashes, exact typed-netlist assignments and lint
  evidence, and normalized export repeatability.
- **Done:** Catalog, documentation, deterministic predicate, synthetic
  fault/control cases, DNP exclusion, source-bound findings, and exact-version
  native export coverage are implemented. No proprietary project source or
  cohort code is used.

#### LINT-044 — Per-rule schematic geometry coverage

- **Status:** Implemented v1. The source scan retains unsupported conditions by
  affected rule. The report gives each geometry rule `DISABLED`, `COMPLETE`,
  `PARTIAL`, or `UNSUPPORTED`; overall coverage aggregates only enabled rules.
- **Problem:** A limitation in one geometry extractor could make every
  configured schematic rule appear partial. Public examples with multiline
  text showed that this hid usable evidence from unrelated wire geometry.
- **Predicate:** Parser and instance-mapping limitations are assigned to the
  rule classes that depend on them. A wrong KiCad version or schematic format
  leaves each enabled rule unsupported. A supported rule remains complete when
  another disabled rule has unsupported geometry. Missing or ambiguous source
  and native bindings remain blocked at the source-bound service boundary.
- **Boundary:** This refines coverage reporting; it does not expand geometric
  support, suppress findings, or change electrical connectivity. The mapping
  from parser limitation to affected rules is an explicit maintenance surface
  and must be updated when a rule gains new evidence dependencies.
- **Fixtures:** Unsupported formatted text plus a supported wire-through-body
  finding; wire-body-only policy reports complete coverage; text-overlap policy
  reports partial coverage; disabled rules remain disabled; exact-version and
  repeated-sheet reference-mapping boundaries; native netlist/ERC parity for
  the text-only source mutation; shared CLI/MCP report parity.
- **Done:** Per-rule status and unsupported evidence are source-bound,
  deterministic, visible in the typed report, and tested with synthetic
  fault/control inputs. No project source is used.

#### LINT-045 — SPI active-low chip-select idle-bias review

- **Status:** Implemented v1 as a configurable native-netlist review heuristic,
  inspired by the kicad-happy `validate_spi_bus` PR-002 check.
- **Problem:** A peripheral with an assigned active-low chip-select input may
  be selected while the controller pin is inactive or high impedance during
  reset. A connected net and ERC pass do not establish the startup state.
- **Predicate:** For each fitted symbol pin with an explicit active-low
  chip-select spelling and native `input` or `input_low` type, require one
  assigned non-return net. Emit one review candidate per net when there is no
  fitted conventional direct or unbranched series-resistor path of 1 kΩ–100
  kΩ to a positive rail recognized by the existing narrow rail-name or
  supply-function map. DNP devices and resistor paths are excluded. Bare `CS`,
  `SS`, or `CHIPSELECT` names do not establish polarity.
- **Boundary:** This is a review prompt, not a universal external-resistor
  requirement. It cannot see internal bias, controller reset/firmware behavior,
  off-board circuitry, resistor arrays, jumpers, active bias networks, custom
  supply names, or device selection timing. The broad 1 kΩ–100 kΩ range is a
  detection window, not a recommended value or proof of electrical margin.
  Project policy can set the rule to `off`, retain `review`, or explicitly
  promote it to `block`; a fingerprinted ignore records a reviewed exception.
- **Cohort input:** The pinned kicad-happy
  [`validate_spi_bus` PR-002 implementation](https://github.com/aklofas/kicad-happy/blob/a6bba1add1e18b89e3aa0824b9769ed1d9d79174/skills/kicad/scripts/validation_detectors.py#L822-L844)
  selects candidate ICs through part-keyword and pin-name lists and searches
  for a resistor to a non-ground power net. Its runtime trial under LINT-031
  found the missing-bias case and accepted the fitted 10 kΩ control, but it
  also accepted DNP 10 kΩ and 0 Ω anti-controls. LINT-045 narrows the candidate
  to explicit active-low native input pins and fitted 1 kΩ–100 kΩ paths.
  No cohort code was copied.
- **Fixtures:** Missing bias; direct 10 kΩ and unbranched two-resistor valid
  paths; DNP device and resistor; wrong-rail resistor; zero-ohm and out-of-band
  values; bare-polarity and output-pin controls; exact rule `review`/`block`/
  `off` and fingerprint-ignore behavior; shared CLI/MCP parity.
- **Done:** Catalog entry, deterministic predicate, rule-policy lifecycle,
  source-bound report evidence, synthetic fault/control coverage, public cohort
  source attribution, and user documentation are implemented. No cohort code,
  project fixture, or proprietary board source is stored.

#### LINT-046 — IC supply rail without a fitted schematic capacitor

- **Status:** Implemented v1 as a configurable, default-review native-netlist
  heuristic. Cohort comparisons include kicad-happy `DO-DET` and kicad_skills
  `analog.missing_decoupling`; neither cohort implementation is a dependency.
- **Predicate:** For each fitted non-connector component with a native
  `power_in` pin on a uniquely assigned net, recognize a positive rail through
  the existing narrow `power_function_key` net-name or attached-pin-function
  list. Report that rail when no fitted component with a common capacitor
  library symbol name (`C`, `C_*`, `CP`, `CP_*`, or a name containing
  `capacitor`) connects it to a distinct net with a recognized return-like
  name or attached pin function. Explicitly DNP components do not count as ICs
  or capacitors.
- **Boundary:** This asks for datasheet and placement review. A capacitor
  connected between the supply rail and a recognized return-like net does not
  prove that it is required, has the right value, sits near the IC, or has an
  adequate physical return path. Internal, remote, and off-board decoupling
  can be valid. Custom rail names without a recognized pin function or custom
  return labels without a recognized return pin function can evade the
  heuristic; uncommon capacitor symbol IDs can create extra review prompts.
  References beginning J/P/X/CN are excluded as connectors; other connector
  prefixes may be included as IC candidates. Project policy may choose
  `review`, `block`, or `off`, and exact ignores use the existing fingerprint
  lifecycle.
- **Cohort evidence:** At pinned kicad-happy commit `a6bba1add1e18b89e3aa0824b9769ed1d9d79174`,
  repeated source-backed runs distinguish the no-cap fault from the capacitor control while KiCad
  ERC reports no power-source error or capacitor-presence diagnostic. The cohort reports both the
  `power_in` consumer and synthetic `power_out` source as missing decoupling; LINT-046 scopes its
  prompt to the `power_in` consumer. This corroborates review coverage over native ERC, not unique
  detection over LINT-046. Tooling independently implements only the bounded symbol, assigned-net,
  and return-label presence question. The candidate reports were identical across repeats; hashes
  and reproduction details are in the
  [synthetic fixture notes](../tests/fixtures/design_lint/cohort-power-pin-dc/README.md). A second
  trial of kicad_skills `analog.missing_decoupling` on the same source-backed pair duplicates
  LINT-046's fitted-capacitor fault/control result. On a native-exported DNP-capacitor variant,
  LINT-046 correctly emits a rail-level review while the candidate stays quiet because it accepts
  the `C` reference as coverage without checking DNP state. Its `--no-cli` run and exact report
  hashes are recorded in LINT-031 and the fixture notes.
- **Fixtures:** No fitted capacitor; fitted capacitor from the rail to a
  recognized return; DNP capacitor; capacitor on another rail; open or same-net
  capacitor terminals; unrecognized return; DNP IC; connector power pin;
  passive instead of `power_in`; unrecognized rail; policy override/off/exact
  ignore; shared CLI/MCP parity. All Tooling cases are synthetic.
- **Validation state:** Catalog, deterministic predicate, typed report
  evidence, policy lifecycle, synthetic fault/control coverage, and shared
  CLI/MCP parity are implemented. The pinned native lane exports each fixture
  twice and compares normalized netlists and ERC reports on KiCad 10.0.0 and
  10.0.5. The source-backed no-cap fault has `U1.1` and `U2.1` on `+3V3`, no
  `power_pin_not_driven` violation, and one LINT-046 review finding; its
  capacitor-bearing source control has no LINT-046 finding. A sixth native
  case keeps the same mapped `C1` pins but marks the capacitor DNP; both pinned
  versions preserve the DNP state and repeat the netlist/ERC exports, while
  LINT-046 emits a rail-level review because no fitted decoupling capacitor is
  present. Fixture hashes are
  asserted. These results establish only review coverage for fitted
  capacitor-symbol presence, not capacitor need, value, placement, current, or
  PCB return path.
  No proprietary project source or fixture was inspected or stored.

#### LINT-055 — Project-mapped series power-path consistency

- **Status:** Implemented v1 as a default-review project map with typed-netlist
  fault/control cases, CLI/MCP parity, and tooling-owned schematic plus ERC
  exports on KiCad 10.0.0 and 10.0.5. The wrong-source-net fault is flagged by
  the mapped check while native ERC reports zero errors for both fault and
  control.
- **Cohort input:** The pinned kicad-happy `PP-001` candidate walks across
  selected low-resistance components and rejects capacitors. LINT-031 found no
  unique source-path detection on its initial disconnected-pin cases because
  native ERC already reports an undriven power pin. This authored ferrite-path
  rule now has a separate source-side wrong-net case that ERC does not report.
  The candidate's broader ferrite, fuse, jumper, and DNP behavior remains
  unestablished. Tooling does not adopt its component classes, inference,
  severity, or runtime.
- **Need:** The current `power_connectivity` contract checks that source and
  load pins share one exact net. It cannot encode a reviewed series chain
  through a fuse, ferrite, or fitted solder jumper. A project-owned path map
  makes that intended topology independently testable without heuristically
  deciding which components conduct power.
- **Predicate:** For each mapped path, check exact start/end symbol and
  footprint, native pin inventory, fitted state, and pin-to-net assignment.
  Each required two-terminal element must match the mapped identity and join
  the adjacent, ordered nets. The rule reports only when the project supplied
  the requirement and defaults to `REVIEW`.
- **Boundary:** It does not infer that a path is required, identify unlisted
  parallel paths, check values or ratings, establish current direction or
  component conduction, validate datasheet pinout truth, or prove PCB copper
  continuity. Direct same-net requirements remain in `power_connectivity`;
  multi-pin switches and semiconductor paths need separate models.
- **Fixtures:** Synthetic ferrite path pass; open source, element, and load
  faults; DNP, wrong identity, mapped-net mismatch, two-stage bead/fuse
  controls; ordered-map metamorphic comparison; project review/block/off and
  exact-ignore behavior; CLI/MCP parity; and a native ferrite-path control with
  `U2.1` assigned to `VLOAD` while `FB1.1` is assigned to `GND`. A synthetic
  ERC-only `PWR_FLAG` models the load rail as powered across the bead. Both
  native control and fault have zero ERC errors on each pinned version, while
  only the fault receives the mapped-path review. Exports and normalized
  netlist/ERC reports repeat for both versions. No product source is used.
- **Remaining:** The demonstrated gain is limited to this synthetic,
  project-authored wrong-net requirement. Measure false-positive behavior on
  broader non-proprietary circuits before making project-specific policy
  stricter. The rule still does not prove PCB connectivity, component
  conduction, or electrical suitability.
- **Observed overlap:** Open/unassigned endpoints can also trigger existing
  unconnected-pin heuristics or ERC. Those cases remain covered as contract
  faults but are not counted as LINT-055's incremental result. The incremental
  result is the assigned wrong-net case, where native ERC has no errors and the
  exact authored path map reports the source-to-load mismatch.

#### LINT-056 — Unmapped power-input source-path review

- **Status:** Implemented as a default-review heuristic with synthetic
  fault/control, bounded component recognition, project override/ignore,
  CLI/MCP parity, and native KiCad 10.0.0/10.0.5 comparison. Supported path
  evidence includes source-to-load traversal through exact `Device:D` and
  `Device:D_Schottky` identities, plus bidirectional paths through exact
  bridged two-pin and three-pin solder-jumper identities. Native controls also
  cover custom-rail source-anchor coverage and DNP external-source population.
- **Cohort input:** The pinned kicad-happy `PP-001` analyzer flags the same
  ERC-clean wrong-rail fixture when no project path map is supplied. Its
  broader inferred component model and “AC-coupled to ground only” message are
  not copied. Repeated candidate report digests and source pins are recorded
  under LINT-031 and in the synthetic fixture notes:
  [power-path-native](../tests/fixtures/design_lint/power-path-native/README.md).
- **Predicate:** For a fitted internal native `power_in` pin on a net with a
  fitted, inventoried two-terminal capacitor to a recognized return, emit
  `REVIEW` when no recognized source anchor exists, or when an anchor exists
  but no bounded path reaches it. A recognized positive-rail name or fitted
  `power_out` pin is an anchor. Bidirectional paths use fitted, inventoried
  two-pin resistors at or below 1 ohm, inductors, ferrite beads, fuses,
  polyfuses, and exact `Jumper:SolderJumper_2_Bridged` symbols with native pins
  `1`/`2` mapped to `A`/`B`, exact `Jumper:SolderJumper_3_Bridged12` symbols
  with pins `1`/`2`/`3` mapped to `A`/`C`/`B` and only the 1-to-2 bridge, and
  exact `Jumper:SolderJumper_3_Bridged123` symbols with the same complete pin
  map and all three pins bridged. Each recognized pin must have one net
  assignment. Exact `Device:D` and `Device:D_Schottky` symbols are traversed
  only from the source-side cathode net toward the load-side anode net, with
  complete native pin roles. A path endpoint named by the project power-path
  map is excluded from this heuristic so the exact mapped result is not
  duplicated.
- **Boundary:** A recognized positive net name counts as a source anchor, so
  naming can make an externally disconnected rail appear covered. A custom-
  named external source without an attached fitted `power_out` pin now yields a
  source-anchor coverage prompt; this does not establish that the source is
  missing. A fitted `power_out` pin counts as an anchor without proving that
  its component operates. Unknown switches; open or DNP jumpers; three-pin
  variants other than the exact `Bridged12` and `Bridged123` identities; other
  jumpers; Zener, TVS, and custom diodes; regulators; other semiconductor
  paths; and ambiguous pin inventories are not modeled and can prompt review
  for valid topology. The candidate does not establish that a
  connection is required, that current flows, or that PCB copper or external
  wiring is complete. Project-authored paths remain the stronger requirement.
- **Fixtures:** Control and wrong-rail fault reuse only the tooling-owned
  synthetic ferrite-path schematic. Both retain a fitted capacitor from
  `VLOAD` to `GND`; the fault moves `FB1.1` from `VIN` to `GND`. The valid
  control reaches `VIN` through the bead; the fault does not. Both native ERC
  runs have zero errors and the same violation types on KiCad 10.0.0 and 10.0.5.
  With no map, only the fault gets the new review; with the explicit map, the
  mapped mismatch reports and suppresses duplicate heuristic output. No
  proprietary project source is used.
- **Additional synthetic topology evidence:** A custom-named external
  connector source with no recognized source pin now produces an explicit
  source-anchor REVIEW; the same source with a fitted `power_out` pin is a
  quiet control. A fitted regulator `power_out` pin is an anchor, while its
  DNP state restores a source-path REVIEW. Exact fitted `Device:D` and
  `Device:D_Schottky` symbols now count in the forward direction when native
  pin roles are complete. Reverse, DNP, unsupported, or incompletely mapped
  diodes; open, DNP, or unsupported jumpers; and custom-library bead paths
  remain REVIEW candidates. These are typed
  synthetic netlist fixtures; they do not assert conduction or physical source
  wiring. A separate isolated return remains distinct from board `GND`; the
  fitted external `power_out` case is quiet, and the same valid off-board source
  without source-pin metadata prompts for an exact project decision. A DNP
  external `power_out` does not anchor the assembled circuit. A custom library
  capacitor whose symbol name contains `Capacitor` is recognized, while an
  arbitrary custom symbol name is not assumed to identify a capacitor. Exact
  three-pin `Bridged12` and `Bridged123` identities contribute only their
  encoded terminal groups after the complete native `A`/`C`/`B` pin map and
  one-net-per-pin evidence match. The `Bridged12` control reaches the load
  through pins 1 and 2 while pin 3 stays separate; the `Bridged123` control
  reaches it through pins 1 and 3; a `Bridged12` schematic that puts the load
  on pin 3 remains REVIEW.
- **Native result:** The tooling-owned `fault.kicad_sch` with custom rail
  `LOCAL_A` was exported twice with the digest-pinned KiCad 10.0.0 and 10.0.5
  images. Both versions produced repeatable normalized netlist and ERC
  evidence, retained native `power_pin_not_driven`, and emitted
  `power.input_without_supported_source_path` with
  `source_anchor_state=not_recognized`. This is a source-coverage review on
  top of a native ERC finding, not incremental defect detection. The fitted
  named-rail and `power_out` controls remained quiet for source-path review.
- **Isolation control:** A third native schematic keeps the fitted source path
  intact while returning its decoupling capacitor to `ISO_RETURN`, with no
  `GND` net. Exact KiCad 10.0.0 and 10.0.5 exports retained that separate net,
  repeated to identical normalized netlist/ERC evidence, and produced no
  source-path candidate or native ERC error. This is a valid isolated-domain
  control, not a requirement that other project returns remain separate.
- **Native custom-symbol boundary:** Tooling-owned native schematics exercise
  `Vendor:Power_Capacitor` on both the supported and wrong-rail topologies, and
  an opaque `Vendor:CAP123` symbol on the wrong-rail topology. The named alias
  receives LINT-056 only on the wrong-rail case. The opaque symbol does not
  count as capacitor evidence for LINT-056; the existing LINT-046 decoupling
  rule independently asks for review because no recognized fitted capacitor
  is present. This overlap is reported as LINT-046 evidence, not misattributed
  as a source-path finding.
- **Native DNP external-source boundary (2026-09-30):** The paired
  `external-source-control` and `dnp-external-source-fault` schematics export
  a two-pin synthetic `J1` on custom rail `AUX_INPUT`; pin 1 is `power_out`,
  and pin 2 returns to `GND`. Both pinned versions preserve the exact symbol,
  pin inventory, net assignments, and fitted/DNP state in normalized native
  netlists. The fitted control is quiet; with `J1` marked DNP, the source pin
  is excluded from source-anchor evidence and LINT-056 reports `REVIEW`.
  Native ERC has no errors in either case. This proves the DNP population
  boundary for the exported schematic, not the physical source or assembly.
- **Native alternate-source control (2026-09-30):** The synthetic
  `alternate-source-control` schematic marks `J1` DNP and keeps `J2` fitted.
  Each two-pin `power_out` source has its own ferrite branch to `VLOAD`, and
  both connector returns map to `GND`. Exact native exports under KiCad 10.0.0
  and 10.0.5 retain both branch topologies, the J1-only DNP state, repeatable
  normalized netlists, no ERC errors, and no LINT-056 finding. The check
  confirms a DNP peer does not mask a fitted source path to the internal rail;
  it does not assert that arbitrary external sources should be paralleled.
- **Native no-fitted-source fault (2026-09-30):** The paired
  `both-sources-dnp-fault` schematic preserves the same two distinct branches
  while marking both source connectors DNP. Both native versions retain the
  same normalized netlist after DNP-state normalization, have no ERC errors,
  and produce LINT-056 `REVIEW` on `VLOAD`. This confirms that DNP source pins
  on multiple candidate branches do not count as fitted source anchors.
- **Directional diode slice (2026-10-02):** The heuristic now recognizes only
  exact `Device:D` and `Device:D_Schottky` symbols with a complete two-pin
  inventory and native `A`/`K` functions. It follows the diode's source-to-load
  direction; the reverse orientation remains a default `REVIEW` candidate.
  Unit fixtures cover forward, reverse, DNP, unsupported-symbol, and
  incomplete-role cases. Native KiCad 10.0.0/10.0.5 exports cover a forward
  `Device:D` control, a reverse `Device:D` fault, and a forward
  `Device:D_Schottky` control; normalized netlist/ERC results repeat exactly
  per version, with zero ERC errors. This models a schematic direction clue,
  not a diode's actual conduction, forward drop, ratings, load current, or PCB
  path.
- **Bridged solder-jumper slice (2026-10-02):** The heuristic recognizes the
  exact fitted `Jumper:SolderJumper_2_Bridged` symbol as a bidirectional path
  only when the native inventory contains pins `1` and `2`, their functions are
  uniquely `A` and `B`, and each pin has one distinct net assignment. The
  paired exact `Jumper:SolderJumper_2_Open` topology remains a REVIEW candidate;
  unit cases also preserve three-pole, DNP, incomplete, duplicate-role, and
  unrecognized jumper boundaries. Synthetic native fixtures check both symbols
  under KiCad 10.0.0 and 10.0.5, including repeatable netlist/ERC reports and
  zero ERC errors. This schematic identity is not evidence of the assembled
  solder state or physical copper path. A source-hash-bound synthetic netlist
  also exercises the bridged control and open-symbol fault through CLI and MCP;
  both surfaces return identical reports with PASS and REVIEW respectively.
- **Three-terminal solder-jumper slice:** The heuristic additionally supports
  only `Jumper:SolderJumper_3_Bridged12` and
  `Jumper:SolderJumper_3_Bridged123`, with the complete `1`/`2`/`3` inventory
  mapped to native `A`/`C`/`B` roles. The former contributes a 1-to-2 edge and
  does not imply a path to pin 3; the latter joins all three terminals. Unit
  cases cover both controls, the unbridged-terminal REVIEW, DNP, open-symbol,
  wrong-inventory, wrong-role, and unassigned-terminal boundaries. CLI/MCP
  parity returns identical PASS/PASS/REVIEW results. Native schematics were
  exported twice with digest-pinned KiCad 10.0.0 and 10.0.5; normalized
  netlists and ERC reports repeat, and all cases have zero ERC errors. See the
  native fixture record for source and report digests. This reduces review
  noise on supported topologies; it does not add new defect detection or prove
  solder state or physical continuity.
- **Remaining:** Treat open, DNP, unsupported multi-pin, and other solder jumpers,
  Zener/TVS/custom diodes, switches, regulators, and other unknown path elements
  as unsupported until a synthetic
  fault/control pair can use exact native symbol identity, pin inventory,
  orientation where relevant, and fitted state to distinguish the candidate
  topology. A component `power_out`
  pin remains only a source anchor; it does not prove that device operates or
  that the upstream path is complete. Keep the heuristic at `REVIEW`, and use
  the authored LINT-055 path map when a project needs an exact topology. A
  custom-named external source without exported source-pin evidence still
  needs an explicit project decision.

#### LINT-057 — Direct serial logic-voltage compatibility

- **Status:** Implemented as part of the authored `serial_peers` electrical
  contract. It compares both directions of a direct UART link using exact
  endpoint limits and native pin/net evidence; missing limits fail visibly as
  `NOT_CONFIGURED`.
- **Cohort input:** ThomsonLint's [KiCad review guide][thomson-kicad-review]
  lists a net-level voltage guess in its exported analysis; kicad-happy's
  [datasheet workflow][happy-datasheets]
  documents structured electrical-characteristic extraction. These mutable
  `main` references were inspected on 2026-09-30 and supplied the candidate
  category only. Tooling does not adopt heuristic voltage guesses, rely on
  model-generated values, or copy cohort code.
- **Predicate:** For each direction, the driver's guaranteed low output range
  must stay within the receiver's absolute minimum and maximum and below its
  maximum low threshold. The guaranteed high output range must meet the
  receiver's minimum high threshold and remain below its absolute maximum.
  Both directions are checked against the source-bound native TX/RX pin maps.
  Every range carries a document basis and operating conditions.
- **Boundary:** The project supplies the limits and sources. The checker does
  not verify datasheet provenance, test conditions, load, common-mode range,
  transient overshoot, slew rate, timing, or runtime behavior. It applies only
  to direct logic-level serial peers; RS-232, RS-485 and level-shifted routes
  use separate contracts, and external peer voltages are unavailable locally.
- **Fixtures:** Synthetic direct-link control; output-high maximum equal to
  receiver absolute maximum; excessive high level; excessive output-low
  maximum; missing endpoint limits; invalid overlapping input/output ranges;
  level-shifted and external not-applicable controls; CLI/MCP parity; retained
  evidence replay. No product source or fixture is used.

#### LINT-058 — Adjacent reference-plane centerline coverage

- **Status:** Implemented as an opt-in, configurable `REVIEW` heuristic with
  exact synthetic polygon, clearance-hole, threshold, unsupported-geometry,
  mapping, ignore/override, and CLI/MCP parity cases. It consumes the existing
  source-bound KiCad 10 PCB snapshot schema 10 (schema 9 introduced the zone
  contours this rule uses). Its native geometry fixture
  passed twice on each pinned KiCad 10.0.0 and 10.0.5 image with the same exact
  4/15 coverage result, a 0.3 fault threshold, and a 0.25 control threshold. A
  separate native via-hole fixture repeats an exact 2799/4000 coverage result
  on both versions with 0.75 fault and 0.5 control thresholds. A new synthetic
  narrow-void pair uses a 0.65 fixture threshold to distinguish its continuous
  control from a 0.2 mm midpoint notch. Installed KiCad 10.0.6 compatibility
  evidence measured `2799/4000` and `2399/4000`, respectively; the hosted
  10.0.0/10.0.5 repeat lane is added and awaiting execution.
- **Cohort input:** pcb-inspector documents `HEUR-GND-001` as a configurable
  track-to-reference-plane screen with a minimum track length and covered
  fraction. Its manual examples use 5 mm and 0.9; these are not copied as
  defaults. A kicad-happy changelog entry records a false positive when a
  route's own via antipad was counted as a plane gap. This check currently
  counts that clearance as uncovered too. It now annotates a mapped endpoint
  via whose center falls inside a same-net reference-zone hole, but does not
  claim the hole belongs to that via; synthetic model and native regressions
  preserve the known review false-positive instead of claiming it as new defect
  detection. See
  [pcb-inspector's manual](https://github.com/takzen/pcb-inspector/blob/main/MANUAL.md)
  and [kicad-happy's changelog](https://github.com/aklofas/kicad-happy/blob/main/CHANGELOG.md).
  The separate pinned kicad-happy `GP-001` runtime trial under LINT-031 misses
  the midpoint notch because its 2 mm sampling checks only both endpoints.
  A pinned `pcb-inspector` `HEUR-GND-001` trial under LINT-031 detects this
  narrow-void fault and clears the matching control with a fixture-only 0.65
  threshold. It corroborates, but does not extend, this gate: its report marks
  the entire segment affected and gives no exact uncovered-interval measure.
- **Predicate:** For each explicitly mapped signal net and copper layer, the
  checker measures each native straight-track centerline against the union of
  same-net filled-zone polygons on each immediately adjacent copper layer.
  It records an exact rational covered fraction per reference layer; for a
  track between two copper layers, a below-threshold finding is emitted only
  when both adjacent layers miss the authored threshold. The project also
  supplies the minimum segment length. Arc, absent-layer, missing-track, and
  no-adjacent-layer cases remain visible as incomplete coverage.
- **Boundary:** This measures centerline geometry only. It does not infer which
  ground domain or reference net a signal should use, inspect trace-width
  overlap or electromagnetic return fields, prove that the plane connects to
  endpoint pads, or establish current capacity, emissions, continuity, or
  electrical performance. Hole and clearance regions count as uncovered;
  the expected antipad around the signal's own via can lower a short segment's
  score. The report adds possible endpoint-via context when a mapped via center
  falls inside a same-net reference-zone hole, but does not establish hole
  ownership or remove the interval from the score. Intentionally split planes
  can also prompt review. It defaults to `review` and supports `block`, `off`,
  and exact reasoned ignores.
- **Fixtures:** Exact rational hole-subtraction and threshold controls;
  adjacent-layer and wrong-net controls; inner-layer two-sided coverage;
  split-zone gap with REVIEW plus explicit alternate-reference-net control;
  branched-route localization with a passing trunk and a below-threshold branch;
  missing track/layer and unsupported arc controls; configured fault/control;
  project policy; a known signal-via-antipad review false-positive with a
  shifted-hole control that leaves the measured score unchanged; native via
  antipad, endpoint-contact, and hole-context controls on KiCad 10.0.0 and 10.0.5;
  a native two-layer 0.2 mm narrow-void fault/control lane is configured for
  the same pinned versions; source-bound report equality through CLI and MCP.
  No proprietary board or project fixture is used.
- **Remaining:** The center-in-hole annotation is context, not proof of via
  ownership; a synthetic merged-clearance regression now confirms that a hole
  containing an unrelated via remains fully uncovered and is not attributed to
  the endpoint via. The finding explicitly says the contours do not identify
  which clearance created a merged hole. Keep counting those intervals as
  uncovered and keep this rule review-only. Synthetic split-plane and branch
  controls now verify the mapped-net comparison and per-segment localization.
  Short tracks below the authored minimum are always listed in both report
  surfaces. The new per-requirement `review_excluded_short_tracks` option can
  make any such exclusion an explicit `REVIEW` coverage gap; the default leaves
  the project-authored minimum as the scope boundary. Synthetic quiet/review/
  block controls and CLI/MCP parity cover both choices. Exact hosted results
  for the new narrow-void lane are pending; the local 10.0.6 compatibility run
  does not substitute for the pinned 10.0.0/10.0.5 evidence.

#### LINT-059 — I2C pull-up rail-family review

- **Status:** Implemented as `bus.i2c_multiple_pullup_rail_families`, with
  synthetic fault/control cases, order-stability coverage, project review,
  block, off, and exact-ignore decisions, and the shared CLI/MCP lint report.
- **Cohort input:** The current public kicad-happy changelog describes I2C
  checks and extracted bus summaries that include voltage and pull-up values.
  This suggests that voltage domain belongs alongside resistor topology in
  review evidence; no cohort implementation, package, source fixture, or
  installation workflow was adopted.
- **Engineering basis:** NXP's
  [UM10204 I2C specification, revision 7.0](https://cache.nxp.com/docs/en/user-guide/UM10204.pdf)
  relates device input levels to the VDD supply used by the pull-up resistors. The local check
  therefore asks for review when the visible pull-up paths name more than one recognized rail
  family; it does not decide which voltage is valid.
- **Predicate:** For SDA/SCL nets assigned to distinct nets on one fitted
  component with recognized pin-function names, collect fitted conventional
  direct or unbranched series resistor paths in the existing 1 kΩ–100 kΩ
  recognition window. When any paths across either line use more than one
  normalized positive-rail family, emit one source-bound candidate with each
  line, resistor path, rail net, and family.
- **Boundary:** Rail families come from the bounded power name/function map.
  A difference is only a naming clue; it does not prove incompatible voltages,
  unsafe input limits, or an error. Equal-family net aliases are not treated as
  distinct families. Custom names without a recognized power-pin function,
  internal or remote pull-ups, arrays, active pull-up circuits, level-shifter
  behavior, power sequencing, resistor tolerance, and bus timing are outside
  this candidate. The resistance interval is a detection window, not a design
  requirement. An authored I2C pull-up/voltage contract remains the stronger
  comparison when a project records exact endpoint limits.
- **Fixtures:** One line with pull-ups to two family names; SDA and SCL split
  across different family names; same-rail and same-family alias controls;
  an unrecognized custom rail control; DNP pull-up and DNP bus-device
  controls; block/off/ignore policy; reordered netlist inputs with identical
  fingerprint and evidence.
- **Done:** The rule is cataloged, deterministic, source-bound, synthetic
  tested, and defaults to review. It adds a missing rail-family prompt beside
  existing resistance checks without asserting voltage compatibility or
  merging rails. No proprietary project source or fixture is used.

#### LINT-060 — Mapped external-protection entry and return-via screen

- **Status:** Implemented as `pcb.protection_entry_path`, with synthetic
  fault/control and inventory-order tests plus shared CLI/MCP report parity.
  Its separate native fixture passes on digest-pinned KiCad 10.0.0 and 10.0.5
  images, with repeated source-bound control snapshots, exact 650 um and
  connected-via controls, a disconnected signal fault, and a nearby but
  disconnected reference-via fault. LINT-031 records a read-only runtime
  comparison against kicad-happy's ES-001/ES-002 heuristics; the candidate adds
  no unique detection and misses the disconnected-via fault.
- **Cohort input:** kicad-happy's EMC rules document `ES-001` for distance
  between connector and protector, and `ES-002` for ground vias near the
  protector. Its inspected implementation measures footprint-origin distance
  and classifies ground from net names. Those are useful review hypotheses but
  too coarse to establish pad placement, a project-required reference domain,
  or copper-component continuity.
- **Predicate:** A project-authored `pcb_protection_path_map` names exact
  connector and protector signal/reference pads, expected footprints and nets,
  an optional maximum signal-pad center distance, and/or an optional minimum
  count of native-connected reference vias within a project-selected radius.
  The checker verifies fitted pad inventory, native nets, and shared copper
  connectivity between the connector and protector signal pads. It counts
  vias only from the mapped protector reference pad's native copper component.
- **Boundary:** No net-name ground guessing, connector/device discovery,
  universal ESD placement threshold, or universal via count is applied. The
  straight-line distance is not routed path length, route order, parasitic
  inductance, or transient response. A matching net and nearby via do not prove
  clamp suitability or protection effectiveness. Existing schematic
  `external_protection_map` remains the place for authored connector pin and
  device pin-net requirements; this PCB map independently binds exact board
  pads and geometry. Tests use generic synthetic data only.
- **Fixtures:**
  `kicad_tooling/hwrepo/fixtures/pcb-protection-entry-path.kicad_pcb` exercises
  the pinned native probe. Exact distance and via-radius boundaries; too-distant pad;
  below-minimum via count; nearby but non-connected via fault/control repeated
  through pinned native KiCad 10.0.0/10.0.5; wrong net, footprint,
  DNP state, or copper component; legacy snapshot without connected-via
  inventory; pad/via input permutation; CLI/MCP semantic parity through the
  common typed service; malformed pad ownership and incomplete via limits.
- **Done so far:** Typed map/report, exact integer geometry, source-bound board
  and native snapshot receipts, review/block/off controls, CLI rendering,
  catalog, docs, synthetic controls, and pinned KiCad 10.0.0/10.0.5 native
  fault/control coverage are implemented. The bounded candidate runtime trial
  is complete; remaining maturity work is reviewer-effort measurement and
  evaluation on approved non-proprietary board examples. The implementation
  borrows the test hypothesis, not candidate code or install workflow.

#### LINT-061 — Mapped digital-peer voltage compatibility

- **Status:** Implemented v1 as the project-authored
  `digital_peer_voltages` electrical contract. It checks mapped direct output
  to input paths outside the existing UART and I2C contracts. Missing limits
  report `NOT_CONFIGURED`; stale identity or pin/net mapping prevents the
  voltage comparison. The typed analyzer is shared by CLI and MCP. The
  tooling-owned native SPI fixture repeats through digest-pinned KiCad 10.0.0
  and 10.0.5 exports.
- **Cohort input:** kicad-happy documents `VM-001` for cross-domain voltage
  review. The inspected source estimates rail voltage from names, selects from
  a fixed 1.8 V, 2.5 V, 3.3 V, and 5 V table, and compares devices on a shared
  signal net. A pinned synthetic runtime trial under LINT-031 finds four
  cross-rail SPI nets and stays quiet on a same-rail control. The error severity
  and level-shifter recommendation overstate what inferred rail names prove;
  see the [fixture record](../tests/fixtures/design_lint/cohort-peer-voltage/README.md).
  This supports only a possible review-coverage prompt, not a compatibility
  requirement.
- **Need:** A schematic may connect an output and input on one net while the
  driver guarantee is below the receiver's high threshold or above its
  absolute-maximum input. ERC does not establish the device operating limits.
  LINT-057 covers direct serial peers; I2C requirements cover mapped pull-up
  voltage versus receiver limits. The remaining candidate scope is other
  project-mapped direct digital endpoints, such as SPI or control signals.
- **Predicate:** A project-authored map identifies exact source and receiver
  component symbols, pins, directed net, output `VOL`/`VOH` guarantees,
  receiver `VIL`/`VIH` thresholds, and absolute input limits. Every electrical
  value includes units, operating conditions, and a document/page basis. The
  source-bound netlist must show the mapped endpoints on the same net. Check
  output-low maximum against receiver `VIL`, output-high minimum against
  receiver `VIH`, and the full guaranteed output range against receiver
  absolute limits. Check reverse direction only when separately mapped.
- **Boundary:** Do not infer rail voltage, logic family, or safe tolerance from
  net names, part numbers, library descriptions, or generic voltage tables.
  Direct links only in v1; level shifters, open-drain buses, analog signals,
  off-board peer limits, power sequencing, loading, transients, and timing need
  their own models. A pending required section or a mapped link missing limits
  is `NOT_CONFIGURED`; an omitted optional section in a legacy sidecar makes
  no compatibility claim and is not evidence of safety.
- **Fixtures:** Tooling-owned synthetic SPI output/input fault and compatible
  control; low/high threshold and absolute-limit violations; wrong native net,
  stale symbol, DNP endpoint, and missing limits; CLI/MCP pass/fail parity.
  These demonstrate a distinct voltage-compatibility check beyond the current
  SPI membership baseline. The exact native lane maps `U1.2` to `U2.2` on
  `SPI_MOSI`; with identical repeated typed netlists, the authored 3.3 V
  control passes at 0.3 V margin and the 5.0 V maximum fault fails at −1.4 V
  margin on both pinned versions.
- **Done so far:** Typed source-bound map, reusable LINT-057 margin
  calculation, exact symbol/footprint/pin/net comparisons, pending setup,
  retained-evidence replay integration, user documentation, and synthetic
  unit and CLI/MCP parity tests. No voltage is inferred from names or cohort
  code is imported.
- **Remaining:** Measure reviewer effort and false-positive rate on approved
  non-proprietary examples; keep future peer categories separate from
  open-drain, analog, level-shifted, and external paths.

#### LINT-066 — Unmapped digital peers across voltage-named rails

- **Status:** Implemented as `bus.spi_peer_voltage_review` and
  `bus.serial_peer_voltage_review`, both defaulting to `review`. SPI retains
  its digest-pinned KiCad 10.0.0/10.0.5 native results. UART/USART now has
  source-hashed same-rail control and cross-rail candidate schematics in the
  same repeated-export acceptance lane. Local KiCad 10.0.6 exports preserved
  their pin functions, directions, inventory, and rail assignments twice; the
  control stayed quiet and the candidate emitted one serial review. The
  digest-pinned KiCad 10.0.0 and 10.0.5 lane passed on 2026-10-01; both
  versions produced matching normalized typed-netlist digests for the control
  and candidate, with the expected PASS and REVIEW results.
  Receipts and normalized digests are recorded in the
  [SPI fixture notes](../tests/fixtures/design_lint/spi-peer-voltage-native/README.md)
  and [serial fixture notes](../tests/fixtures/design_lint/serial-peer-voltage-native/README.md).
- **Cohort input:** kicad-happy `VM-001` compares shared signal nets between
  ICs whose supply voltages it estimates from rail names. On a synthetic SPI
  fault with U1 on `+5V` and U2 on `+3V3`, it emitted four `error` findings;
  the same-rail control emitted none. Repeated reports were byte-identical
  under two Python hash seeds. Exact source and fixture hashes are recorded in
  the [trial fixture notes](../tests/fixtures/design_lint/cohort-peer-voltage/README.md).
  The UART/USART extension applies that candidate idea to exact native TX/RX
  pin functions; the upstream runtime trial did not separately benchmark UART,
  so this extension is independently synthetic-validated.
- **Predicate:** From source-bound native pin assignments, identify shared
  exact SPI clock/data/select function nets or UART/USART TX-to-RX function
  nets between fitted U/IC references. For serial, the TX function must be on
  a native output-capable pin and the RX function on an input-capable pin;
  endpoint channel indexes need not match. Emit a candidate only for a
  directionally clear pair, with complete native pin-type inventories and
  exactly one assigned positive `power_in` net per endpoint. Parse one
  explicit positive voltage token from each supply net label and prompt only
  when the nominal label values differ. Suppress only the exact native
  pin/net/symbol/footprint link when LINT-061 has both reviewed output and
  input limits. Partial or stale maps do not suppress uncovered peers. The
  predicate groups shared signals for each directed component pair into one
  finding.
- **Boundary:** Rail names provide a review clue only. This does not establish
  actual supply voltage, source validity, output guarantees, logic thresholds,
  absolute maximum, receiver tolerance, open-drain behavior, analog
  compatibility, sequencing, or the need for translation. It cannot assess
  off-board circuitry, loading, timing, transients, or PCB paths. Open-drain
  electrical types, analog functions, input/input and output/output pairs,
  ambiguous bidirectional pairs, missing native types, unconnected supplies,
  multiple supply nets, and DNP endpoints are skipped. UART prompts also
  require native TX and RX roles to agree with output/input pin types. Complete
  exact voltage maps are handled by LINT-061; each review rule can be disabled,
  ignored by exact fingerprint, or explicitly escalated by project policy, but
  both default to review.
- **Synthetic regressions:** The +5 V/+3.3 V SPI pair emits one finding with
  exact shared pin evidence; its same-voltage control stays quiet. UART/USART
  adds a same-voltage control and a cross-voltage TX-to-RX candidate with
  controls for DNP, absent pin-type inventory, unconnected and multiple
  supplies, mismatched TX/RX roles, wrong native direction, open-collector
  pins, unsupported or ambiguous rail labels, and a level-translated UART path
  with separate endpoint-to-translator nets. This last case is typed-netlist
  unit evidence that the direct-peer rule stays quiet; it does not identify a
  translator or validate its circuit. Both analyzers exercise
  partial/missing-limit maps, complete exact maps, and stale identity. Complete
  limits suppress only covered links so the separate source-backed voltage
  comparison owns the result. Reordered nets, functions, pin types, and pin
  inventories preserve fingerprints. Tests verify default REVIEW, policy
  OFF/block, exact ignores, actionable evidence, and CLI/MCP parity. SPI and
  UART native fixtures pass repeated KiCad 10.0.0/10.0.5 exports; UART also has
  repeated local KiCad 10.0.6 evidence. Exact normalized serial digests are in
  the [serial fixture notes](../tests/fixtures/design_lint/serial-peer-voltage-native/README.md).
- A dedicated source-native translator control puts controller and peripheral
  signals on separate nets across the translator's A/B pins and supply domains;
  the direct-peer prompt stays silent. The exact-version lane passed locally on
  2026-10-07 with digest-pinned KiCad 10.0.0 and 10.0.5. Both versions retained
  the same normalized typed-netlist SHA-256
  `a289c5c15f048b1d8e1cf58f18501b850c3e1b7e3be451a9d9ba275cbd057e28`,
  repeated exports matched within each version, and the rule stayed quiet.
  Source SHA-256 is
  `58f2ac474e5c055fc5ff3f5e2f9be0613fc7339298244de035740ca85eaa80a1`.
  This tests the direct-net predicate boundary, not translator recognition or
  circuit correctness.
- **Public-template applicability screen (2026-10-03):** The clean public
  KiCad-Team-Workflow-Template checkout at commit
  `ed89536f0dbbcb013145af2994fef41b2250143e` has three retained examples with
  source and netlist hashes matching their reports and passing source-scope,
  toolchain, ERC, DRC, netlist, and source-unchanged checks. Each aggregate
  summary is `FAIL` because its design-lint gate returns `REVIEW` for
  undeclared connector inventory. The examples are:
  Arduino status LED (`c2d8442412cb251472a08df31109b8633655aaa375598abbb2e7bbc00961fa1b`,
  `b58861bdb1d65c6b363f8cc7aacb682aea49ca3e21027195f8e0d2755abf57c5`),
  controller (`bd3f349233ffc44f030b1004a1c08e51d1ec0589ecf646384f1ed3353806e5ad`,
  `6b071d54ed8a18b8965624e37d6a8fda02d3311fa3013ca1f7b6a4e798e6a7c8`),
  and Raspberry Pi status LED (`b99ad47237f3f36aaefa3a2ed08e3dae12d9131c7f9a52355401c9d5bada3fba`,
  `a1ace15ab2aeaa5270bb2e880423c33c562893a2b88d2ea253374d4dd2ea048e`).
  Current native-netlist parsing found no supported SPI or UART/USART pin
  functions in any of the three, and the current rule emitted zero candidates.
  This is 0/3 applicable examples; precision, false-positive rate, and reviewer
  effort remain unmeasured. The passive-signal-reference receipt was excluded
  because its netlist check failed: its component test contract is incomplete.
  No source was copied into Tooling; only
  ignored acceptance receipts were read. Next, select a source-matched public
  design with supported digital-peer functions before claiming public-board
  LINT-066 measurement.
- **Pinned KiCad-demo follow-up (2026-10-03):** The four native netlists from
  `NativeControlInputDemoTests` were also screened with the LINT-066 predicate:
  CM5 Minima, Jetson AGX Thor, ColdFire/Xilinx, and VME-WREN all produced zero
  candidates. These bundled samples had no recognized same-net SPI or
  directionally clear UART/USART peers on different explicit voltage-named
  rails. This is 0/4 applicable samples, not a precision result. The netlists
  came from the exact KiCad 10.0.5 image and remain in ignored `build/ci/`
  receipts; no demo source was copied into Tooling.
- **Bundled root-project applicability screen (2026-10-03):** The pinned KiCad
  10.0.5 image is:

  ```text
  ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c
  ```

  It contains 36 KiCad project manifests; 35 have a matching top-level
  schematic and were exported twice with networking disabled. All 35 exports
  produced nonempty inventories accepted by `read_netlist`, with 4,263
  component records total. All repeated exports had identical normalized
  typed-netlist evidence. Fourteen raw XML pairs differed while their normalized typed
  inventories matched, so raw XML equality is not used as the repeatability
  result. Across the 35 designs, 26 recognized SPI/UART pin functions yielded
  18 endpoints with supported native types and unique net assignments in
  seven projects. One directionally clear shared SPI peer link was present,
  in Jetson AGX Thor: `U30.39 ~{SPI_CS}` to `U29.1 ~{CS}` on
  `USB Debug, PD/~{PDC_CS}`. Neither endpoint had qualifying unique
  voltage-named supply evidence; LINT-066 emitted zero candidates. The one
  manifest without a matching root schematic (`microwave`) was excluded. This
  is corpus applicability evidence,
  not a precision, recall, false-positive, or reviewer-effort measurement.
  Source-map SHA-256 is
  `307dec53ad7688ff10c44f60474d287937f8ffbe2f42ca4152f859b70c4dddbf`; the
  all-schematic source/hash inventory SHA-256 is
  `8928014281869d38c62db9a8f4e0435c84a07a2b80011e9d06169a5c1eb484fd`.
  Reports and native exports remain under ignored
  `build/ci/public-demo-lint-screen/`; bundled sources were never copied into
  Tooling.
- **Applicability-coverage follow-up (2026-10-07):** The design-lint report now
  distinguishes `NO_SUPPORTED_ENDPOINTS`, `NO_DIRECT_PEERS`, `INCOMPLETE`, and
  `EVALUATED` for each SPI and UART/USART peer-voltage rule. It records
  recognized/assigned endpoint counts, direct links, comparable voltage-label
  pairs, same/different label values, exact-map-suppressed mismatches, review
  groups, and source hashes. Synthetic fault, same-label, missing-pin-type,
  unsupported-function, connector-only external SPI/UART header, and CLI/MCP
  parity cases exercise the fields. Connector-only endpoints remain
  `NO_SUPPORTED_ENDPOINTS`; the heuristic does not treat off-board interfaces
  as direct on-board IC peers. These bounded counts improve applicability
  evidence; they do not estimate field precision or establish complete
  interface discovery.
- **Public coverage replay (2026-10-07):** Replayed the core scanner against
  three previously pinned public netlists without copying source or exports
  into Tooling. This was a bounded applicability scan, not the integrated
  source-bound project report, and no project peer map was supplied. The
  Calcumaker MCU (`113a2837bd155566d753635fb2cec1cb0458fa9f`) returned
  `NO_DIRECT_PEERS` for SPI with one recognized/assigned endpoint and
  `NO_SUPPORTED_ENDPOINTS` for serial. The Calcumaker keyboard at the same
  revision returned `NO_SUPPORTED_ENDPOINTS` for both rules. The Antmicro CM4
  Baseboard (`d248c2921e8e7f4c9b30c96ea5f376d9b2780f1e`) returned
  `NO_DIRECT_PEERS` for both rules, with two recognized/assigned endpoints per
  rule. Each sample produced zero voltage comparisons and zero LINT-066
  candidates. Antmicro's separately recorded label-paired UART paths remain
  in LINT-082's scope; this replay does not assess those paths or establish
  that the designs lack UART interfaces. The results validate the distinction
  between `NO_SUPPORTED_ENDPOINTS` and `NO_DIRECT_PEERS` for these samples;
  they do not measure precision, false positives, missed faults, or reviewer
  effort.

  Root-schematic SHA-256 values are recorded in the Calcumaker and Antmicro
  sample records above. The replayed native-netlist hashes were
  `9ba5a2009d518267e450dd9e89c0edd494c282e3942da9560faf88220992ad02` for the
  MCU, `3f69a81eebcf5023d38d218146edfb8912817ec77d68db737cdce76040ca3a3f` for
  the keyboard, and `31f1125c5b04efc4f70d7c697fea415f717c7c9e232a54110e89865d9c7d9cdf`
  for both byte-identical Antmicro repeat exports. The replay used Python
  3.11.16 and the installed checkout's `read_netlist` and
  `scan_digital_peer_voltage_reviews`. The runtime source hashes were:
  `digital_peer_voltage_review.py`
  `5745259a11bb90d6fbf9b912a090728de1c5fdf072d9030e245f77629e230366`,
  `design_lint.py`
  `944f499cc3a480b88900d45c85397b85a7ed5a88cecd33751fec548910427cf9`,
  `validate.py`
  `f0f0e6fdac75343ae5e2ed16f8fab0a793cc19a537e13c533b6a47c36fe1360c`,
  `models.py` `a48056b881678d629075351c13f9fae246d507209a33cc3638962089d51518f6`,
  `return_nets.py`
  `10a38392b04b50252b69dd1043e4400766c3aee52ef32980238ed2d6233c6055`, and
  `serial_participants.py`
  `0deb569b4ca71ed6f1dfa4be6b7a125931d027582f7cdb1d508dcf00e4797575`. The
  temporary replay test hash was
  `53b30d90c6bf31e8dd686b299d0319d2c87a86e7566e34a1b0bd32f943abc01f`. Its
  command was `.venv/bin/python -I -m unittest discover -s
  /private/tmp/calcumaker-lint-results-113a2837 -p
  test_peer_voltage_coverage.py -v`; the one test and all three sample
  subtests passed. The replay script and all public source/export files remain
  under `/private/tmp`.
- **Selectable external-I/O boundary replay (2026-10-07):** The public
  [Antmicro Debug Toolkit](https://github.com/antmicro/ftdi-toolkit), licensed
  Apache-2.0, documents UART and SPI buses exposed on a 2.54 mm header with
  selectable 5.0 V, 3.3 V, and 1.8 V I/O. Its KiCad 7 schematic was exported
  twice as a compatibility probe with image `ghcr.io/kicad/kicad:10.0.5`
  and digest
  `fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`.
  The Docker image ran as `linux/amd64` emulation on the local `arm64` host.
  This did not run ERC or DRC and does not qualify the source under KiCad 7.
  At upstream commit `6e39ebff19d7230bfa5b8266008d1ca5334f2021`, the root
  schematic SHA-256 is
  `f3e50b1a6f2b599db88fc6581db1cf126b8dcce3f3ce49cdcf8ad81a4e2c5407`.
  The repeated raw XML hashes are
  `6af05f440fc0c334602fee69b50a66d0f290e025273b908cb4a1fe0bd21f4c1f` and
  `2c945a18ae5582599f6832b6da702a4a7e6554483f0ac94f70a84ad7e023f5bb`; the
  normalized typed-netlist hash matched at
  `9f2882fd20da6a2f3582b0061fe421e1e08b81e7c497d22074b9fe895178c672`.
  The export contains 130 components, 77 nets, 270 pin functions, and 471 pin
  electrical types. LINT-066 recognized no supported on-board SPI or
  UART/USART endpoints and made no voltage comparisons or review candidates.
  This is an expected boundary result for externally exposed buses: the
  off-board peer and selected I/O voltage are not established by direct
  on-board IC-to-IC connectivity. It is not a precision, recall, or reviewer-
  effort result. No project source or export was copied into Tooling; the
  source and exports remain under `/private/tmp`. The replay used Python
  3.11.16 and `scan_digital_peer_voltage_reviews`; scanner, parser, and model
  hashes were respectively
  `5745259a11bb90d6fbf9b912a090728de1c5fdf072d9030e245f77629e230366`,
  `f0f0e6fdac75343ae5e2ed16f8fab0a793cc19a537e13c533b6a47c36fe1360c`, and
  `b67704ea6476c68266985646570c47081b3ce44d1f9bd63e30f5af817a3068a4`.
- **Remaining:** Measure reviewer effort and false positives on approved
  non-proprietary examples. Do not promote beyond the default review mode from
  synthetic or native-export evidence alone; no proprietary schematic or board
  is needed for this follow-up.

#### LINT-067 — CAN peer pairs disagree on one shared line

- **Status:** Implemented as `bus.can_peer_assignment_divergence`, default
  `review`, with synthetic same-bus, split-peer, separate-bus, DNP, policy,
  order-stability, and repair controls. Tooling-owned native fault/control
  schematics export and run ERC twice on the exact pinned KiCad 10.0.0 and
  10.0.5 images; neither fixture has ERC errors, while the asymmetric
  assignment reports the exact shared side and complementary net assignments.
  ERC also reports the recorded symbol/footprint library warnings from the
  isolated synthetic library setup.
- The fault and control source records, native hashes, and expected ERC
  warnings are listed in the
  [CAN peer fixture README](../tests/fixtures/design_lint/can-peer-native/README.md).
- **Cohort input:** kicad-happy's public v2.2.1 release notes document
  deterministic CAN protocol checks and a hash-order stability audit. Its
  v2.2.1 runtime trial under LINT-031 did not expose PR-003 in the JSON report
  and emitted the same empty-net missing-termination message for the valid
  control and split-peer fault. No incremental CAN detection was demonstrated.
  This first-party rule uses exact native `CANH`/`CAN_HIGH` and
  `CANL`/`CAN_LOW` pin-function roles to surface a cross-peer assignment
  asymmetry; no candidate code, threshold, or runtime dependency is adopted.
- **Predicate:** For each fitted source component with exactly one recognized
  CANH and one CANL pin function, require each pin to have exactly one native
  net and require the two nets to differ. If two or more complete pairs share
  one exact native net on one side but use multiple exact native nets on the
  complementary side, emit one grouped `REVIEW` finding with each peer's
  exact pin and net assignment.
- **Boundary:** A shared net on one side does not prove the parts belong to one
  bus or that both sides must be common. DNP, incomplete, multi-pin-per-role,
  ambiguous, and same-net pairs are skipped. The prompt cannot establish CAN
  topology, required termination, transceiver behavior, off-board wiring, PCB
  copper continuity, or physical connectivity. Project-owned maps remain the
  stronger expression of intent.
- **Synthetic regressions:** Three peers on one complete pair stay quiet;
  a third peer sharing only one side prompts; two separately connected buses
  remain quiet; DNP exclusion, order stability, fixing the split, default
  `REVIEW`, `block`, `off`, and exact-fingerprint ignore are covered. The
  native pair preserves complete CAN pin inventories, exact assignments,
  direct termination on both candidate pairs, repeatable netlist evidence,
  and zero ERC errors for fault and control on both pinned versions. Expected
  isolated-library warnings are recorded in the native fixture README. The
  CLI and MCP return the same source-bound finding from a synthetic native
  netlist.
- **Remaining:** This is a review-localization gain, not proof the asymmetric
  peer is defective. Reviewer effort and false-positive frequency on approved
  non-proprietary projects remain unmeasured.

#### LINT-062 — Mapped power-sequence dependency coverage

- **Status:** Project-mapped endpoint and dependency checks are implemented as
  `power.mapped_sequence_dependency_mismatch`, with synthetic native-XML
  parsing, installed CLI/MCP parity, and repeated pinned-native KiCad 10.0.0 and
  10.0.5 export coverage. The same rule reports a `REVIEW` when exact mapped
  output/enable endpoints form a closed topology cycle even if the project's
  declared dependency graph is acyclic. Project adoption remains an owner
  decision. Numeric timing checks are deferred until an approved source
  requirement supplies exact limits and operating conditions.
- **Cohort input:** kicad-happy documents `PS-001` as a power-sequencing
  dependency-graph check based on regulator output and enable-pin connections.
  The pinned [detector implementation][kicad-happy-sequence-detector]
  recognizes common enable names and selected device families, forms inferred
  enable-to-output edges, and reports cycles in that inferred graph. A focused
  synthetic runtime trial found the same two-stage cycle twice, once from each
  start node; its acyclic control was quiet. Trial inputs, source hashes, and
  limits are recorded under LINT-031. The local implementation adopts only the
  cycle idea when project-authored stage maps identify exact native output and
  enable pins. Names and family classifications alone do not establish that a
  rail must precede another.

[kicad-happy-sequence-detector]: https://github.com/aklofas/kicad-happy/blob/3cf837b2d6577d1369a45a36d5e9bac0e06ff5b6/skills/kicad/scripts/validation_detectors.py

- **Need:** Some devices require a rail order, a power-good dependency, or a
  bounded delay. A connected schematic net and an ERC pass do not prove the
  required startup sequence.
- **Implemented contract:** An opt-in project-authored `power_sequence_map`
  names exact stage output, power-good, and enable pins; symbol, footprint,
  optional PART_ID, expected nets, enable-control context, required dependency
  edges, and source basis. The native netlist comparison reports changed pin
  assignments, absent/DNP/mismatched components, missing pin inventory, and
  cycles in the declared graph. It also identifies cycles where one exactly
  matched mapped output net drives another mapped stage's enable pin, even when
  that output-to-enable edge is omitted from the dependency list. Only stages
  whose full endpoint inventory matches are used for that inference; no role is
  inferred from pin names or part families. The finding has the standard
  review/block/off and exact-ignore lifecycle.
- **Native evidence:** The synthetic control, open-enable fault, and
  three-stage output-enable-cycle fault are exported twice through
  digest-pinned KiCad 10.0.0 and 10.0.5. Both versions preserve identical
  canonical netlists per fixture; the control passes, the open-enable fault
  produces one localized U2.1 REVIEW, and the cycle fault produces one
  `rail-a`/`rail-b` REVIEW while its declared dependency graph remains acyclic.
  Exact source hashes and canonical netlist hashes are retained in the
  [native fixture record](../tests/fixtures/design_lint/power-sequence-native/README.md).
- **Remaining:** A missing map or omitted stage remains a coverage question;
  the cycle prompt needs exact mapped endpoint records and cannot discover the
  relevant regulator set. Evaluate a separate numeric timing contract only
  when an approved source schema explicitly supplies exact thresholds, units,
  tolerances, operating conditions, and boundary controls.
- **Boundary:** Never decide that a project needs sequencing from a processor
  keyword or `EN`/`PG` pin name alone. A schematic cannot prove ramp timing,
  startup under load, firmware states, supervisor thresholds, brownout
  behavior, or physical rail behavior. Missing maps remain coverage gaps; they
  do not make every board a failure.
- **Fixtures:** Synthetic exact endpoint/dependency control through normalized
  raw netlist XML, installed CLI, and MCP; open enable, mapped output-to-enable
  cycle with an acyclic declared dependency graph and an acyclic valid control,
  changed rail net, symbol/PART_ID mismatch, missing native pin, and DNP faults;
  firmware-declared control; omitted-map no-inference control; explicit graph
  cycle; stable ordering and fix-clears-finding metamorphism. Do not assert
  silicon startup or hardware behavior from these fixtures.
- **Done for v1:** The topology contract has CLI/MCP parity, repeated native
  KiCad 10.0.0/10.0.5 export evidence, and documented project adoption limits.
  A numeric timing extension remains a separate follow-up with its own approved
  source schema and synthetic boundaries; it must not be inferred from device
  names or cohort defaults.

#### LINT-063 — Output-driven LED series-path review

- **Status:** Implemented as `component.led_directly_driven_from_output`, a
  configurable default-review heuristic.
- **Cohort input:** LINT-048 records kicad-happy's LR-001 visible-series-limiter
  question and its direct-rail trial. A separate read-only run of the pinned
  kicad-happy deterministic analyzer classified the direct-output fault as
  `LA-AUD` `ic_direct` and the series-return control as `resistor_limited`, but
  also classified the output-parallel-resistor fault as `resistor_limited`.
  Its one-hop resistor scan does not distinguish that parallel resistor from a
  series path. This is useful corroboration for the simple direct-drive case,
  but it misses the parallel-resistor fault that the local predicate retains.
  The cohort report is also coarser: it names the IC driver but does not bind
  the finding to native output-pin type or pin/net evidence. Exact source hashes
  and repeated report digests are recorded in the synthetic fixture notes. A
  separate public-template screen found that the cohort's `LR-001` emits an
  error on a GPIO-side series resistor in both status-LED examples even while
  `LA-AUD` identifies that same 1 kΩ resistor. This is a reproducible false
  positive outside the local predicate's applicable LED identity map; retain
  the local fault/control behavior and do not adopt the generic candidate rule.
  The source hashes and report digests are recorded under LINT-031.
- **Predicate:** For a fitted exact `Device:LED`, or a custom identity matched
  by the LINT-069 project role map, with two inventoried pins and unique,
  distinct native net assignments, report when one LED terminal net is
  shared with a fitted native `output`, `bidirectional`, `tri_state`,
  `open_collector`, or `open_emitter` pin and the other LED terminal is directly
  assigned to a recognized supply or return net. A visible fitted positive-
  value resistor between an intermediate return-like LED net and a distinct
  recognized return net suppresses the candidate. The resistor check uses the
  shared deterministic two-terminal resistor inventory and does not certify
  value adequacy.
- **Boundary:** Default is `review`; project policy may block, disable, or
  fingerprint-ignore an exact finding. This does not infer that a resistor is
  required, current limits, polarity, output-drive capability, off-board paths,
  population, copper connectivity, or runtime behavior. Only exact supported
  LED identity, known native output-capable pin types, and recognized rail
  roles participate. Unmapped or stale custom identities, DNP devices, missing
  pin metadata, ambiguous assignments, and unrecognized rails remain outside
  the predicate; stale mapped identities block lint.
- **Fixtures:** Synthetic native-netlist faults cover direct output-to-LED and
  a resistor parallel to that path. Controls cover a series resistor on either
  side, non-output and unknown pin types, DNP endpoints, custom symbols, and
  unrecognized rails. CLI/MCP parity uses the same typed service. Eight
  tooling-owned schematics are exported twice on digest-pinned KiCad 10.0.0 and
  10.0.5; direct-output, parallel-output-resistor, and mapped custom-symbol
  cases report, while both standard and custom return-side series-resistor
  controls do not. Without the role map, the custom symbol stays outside the
  predicate. The native lane asserts that the parallel-resistor fixture
  actually places its resistor on the same two nets as the LED before
  evaluating the rule.
- **Public-template applicability check (2026-10-01):** The clean public
  KiCad-Team-Workflow-Template checkout at
  `ed89536f0dbbcb013145af2994fef41b2250143e` documents its Arduino status LED
  as J1.1 → R1 (1 kΩ) → D1 → J1.2/GND. The KiCad 10.0.5 export and parsed
  native netlist confirm
  `D13_STATUS=(J1.1,R1.1)`, `LED_ANODE=(R1.2,D1.1)`, and
  `GND=(D1.2,J1.2)`. The source schematic SHA-256 is
  `c2d8442412cb251472a08df31109b8633655aaa375598abbb2e7bbc00961fa1b`; the
  native netlist XML SHA-256 is
  `900a175d05b135f37bdd582cc07e83e637b0933b3fe99713e74b0615ff1ad5cf`.
  LINT-063 emitted no finding because D1 uses the exact custom identity
  `StatusLedTraining:LED_5mm`, outside the current `Device:LED` predicate.
  The overall report remained `REVIEW` with zero heuristic findings because
  connector inventory coverage was `UNDECLARED`; this is a non-applicable
  sample, not a clean-pass or false-positive measurement. Only the public
  source and generated receipts in `/private/tmp` were used; no project source
  was copied into this repository.
- **Pinned KiCad-demo applicability screen (2026-10-03):** The same four
  repeated native KiCad 10.0.5 demo netlists used for LINT-017 contain 50
  `LED`-named symbols across CM5 Minima, Jetson AGX Thor, ColdFire/Xilinx, and
  VME-WREN. All 50 use custom library identities rather than `Device:LED`; the
  exports provide no PART_IDs and no reviewed LINT-069 role map was supplied.
  LINT-063 therefore returned zero findings. This tests the custom-identity
  boundary only; it does not estimate precision or validate the LEDs' current
  paths. Native receipts remain under ignored `build/ci/`.
- **Bundled root-project applicability screen (2026-10-03):** The repeated
  KiCad 10.0.5 top-level project screen described under LINT-066 contains one
  instantiated exact `Device:LED`, `Q17ng` `D1`, and no LINT-063 findings. Its
  anode is on `vdd`; its cathode net is shared with `Q2.3` (native `input`)
  and `R2.1` (passive), so the local rule's direct output-capable-pin plus
  opposite-rail predicate does not apply. Source SHA-256 is
  `25f5da785909d7a3fb70588502f0a59e78b3d7520c42d9b1d440455c47141046`; the
  repeated normalized typed-netlist SHA-256 is
  `ccae5ebba5e74da5640401e6c341f4b6e96a8f32c73d11b332f8f7d0923adf8f`.
  This is an out-of-scope topology, not a clean control or precision result.
- **HALPI2 LED re-screen (2026-10-07):** The public KiCad 9.0, CERN-OHL-S v2 source already screened
  under LINT-074 contains eleven exact `Device:LED` instances in the root export. Its repeated KiCad
  10.0.5 typed netlist remains the complete-hierarchy evidence; LINT-063 returned zero findings.
  Four LEDs share a terminal with native output pins, but their opposite terminals are on
  intermediate resistor nets rather than recognized rails. The other exact-symbol LEDs do not
  complete the direct-output/opposite-rail predicate. A repeated standalone-sheet compatibility
  probe on installed KiCad 10.0.6 produced stable typed-netlist digests for `mcu_leds.kicad_sch`
  (`edd52347a980e921a60474a06b0b76898f50eaeb8cb6b51c4160e3371d350f2e`) and `rgb_leds.kicad_sch`
  (`72926234258a08b2780e0f22a4c832ef3678e0151cf098a74e5761f12570ff86`); the first sheet contains
  four exact `Device:LED` symbols and the second uses five custom LED identities. Neither sheet
  emitted a candidate. Because the standalone exports lack parent-sheet context and the repo
  documents KiCad 9.0, treat them only as compatibility probes. This adds no fault/control or
  reviewer-value measurement; do not repeat this source for LINT-063. The sub-sheet source SHA-256
  values are `13e8001418458d5e7cf2d75d47e6780bcccdd0b818f1add787252c96fd760119`
  (`mcu_leds.kicad_sch`) and `7f6d85930e1cc949c84ef71f8f0693d8fd3301ca69369ddc7320043cea0e3501`
  (`rgb_leds.kicad_sch`); the root source hash is recorded with the HALPI2 boundary screen above. No
  project source was copied into Tooling.
- **Applicability extension:** The LINT-069 first slice now permits an exact
  custom LED classification when the project contract binds PART_ID, symbol,
  footprint, complete native pin signature, and review basis. The mapped fault
  and series control pass on both supported native versions. This does not
  establish electrical limits, approve the component, or prove physical
  current limiting.
- **Done:** The rule is catalogued and configurable, deterministic across
  reordered netlist input, source-bound through native exports, and covered by
  fault/control and CLI/MCP parity tests. No proprietary project source or expectation
  was used or stored. The native lane validates the parser and topology prompt,
  not electrical suitability or manufacturing acceptance. The cohort analyzer
  comparison and repeated-report hashes are recorded in the synthetic fixture
  [trial notes](../tests/fixtures/design_lint/cohort-led-resistor/README.md).

#### LINT-064 — Source-bound component voltage-rating margin coverage

- **Status:** Implemented as an opt-in electrical contract and verified against
  the digest-pinned KiCad 10.0.0 and 10.0.5 fixture lanes. No project contract
  currently opts into the check. Synthetic acceptance does not approve a part
  or establish project-level adoption.
- **Cohort input:** The public
  [kicad_skills README](https://github.com/sabas0ba/kicad_skills/blob/53d1af8bc550f60415b4b8e51a6d2d5924ada03f/README.md)
  and its
  [schematic review guide](https://github.com/sabas0ba/kicad_skills/blob/53d1af8bc550f60415b4b8e51a6d2d5924ada03f/docs/guides/kicad-schematic-review.md)
  describe component-rating and voltage-derating review. The guide limits its
  voltage-derating heuristic to rail names that state a voltage. This is
  documentation review only for the rating feature; no rating runtime trial or
  source-level predicate comparison was performed. The pinned repository
  declares Apache-2.0. LINT-031 separately trials only `analog.no_dc_path`.
- **Problem:** ERC and a correct net assignment do not compare an exact fitted
  part's sourced voltage rating with the reviewed maximum stress expected
  across that part. Guessing voltage from a rail name or part description can
  misclassify custom rails, tolerances, transients, and component roles.
- **Deterministic check:** A project-owned requirement identifies
  the exact reference, symbol, footprint, part/catalog identity, native pins or
  endpoint nets, datasheet rating and source basis, a reviewed maximum operating
  stress, its source/calculation basis, and a project-chosen maximum rating
  utilization. The analyzer binds those inputs and the native netlist, verifies
  exact identity and pin/net assignments, then compares the declared stress to
  the declared rating and utilization limit. Missing or stale requirements
  remain coverage gaps. It uses no generic rail-name voltage table or universal
  derating percentage.
- **Boundary:** Project owners remain responsible for the accuracy and
  applicability of the datasheet rating and stress envelope. The analyzer does
  not derive worst-case stress, rail tolerance, ripple, surge, temperature
  derating, lifetime, or component behavior. A review hint cannot prove that a
  part is suitable or promote an unreviewed value to a release decision.
- **Acceptance evidence:** The synthetic parsed-netlist contract control at
  12 V / 16 V = 0.75 passes an 0.8 limit; equality at the limit passes; 13 V /
  16 V fails. Wrong part ID, symbol, footprint, pin inventory, pin/net
  assignment, unconnected pin, DNP state, and missing component fail closed or
  leave utilization not applicable. A CLI/MCP test produces identical
  requirements and findings, and retained evidence replay rejects omitted
  identity, pin, or utilization checks. The native fixture holds its schematic
  and netlist constant while authored stress changes from 15 V / 24 V to 20 V /
  24 V. Exact digest-pinned KiCad 10.0.0 and 10.0.5 runs both reproduced the
  canonical netlist hash
  `62445806a59516cbf1822b34cb4f7a1f020b6be559fa4bef87fba0fb3b91cf3e`. Their
  repeated normalized ERC hashes were respectively
  `8945db6cb5e10cc79180475f596dec5807ca1a246be947c84ad4a3e8c6fbd17b` and
  `b1f928b2543cac139c3067384c152844cae9e49e684e39e666b7d4c18445ab4b`.
  Each report had warnings only and no ERC errors; its signature was unchanged
  between the passing 15 V and failing 20 V authored stress cases. This shows a
  distinct contract-level result beyond the native ERC baseline. Command and
  export receipts are under ignored `build/ci` in the disposable acceptance
  checkout. Exact source hashes, native netlist evidence, and reproducible
  limits are summarized in the
  [synthetic fixture record](../tests/fixtures/design_lint/component-voltage-ratings/README.md).
  The cohort code was not installed or benchmarked, and no real
  project datasheet or design fixture was used.
- **Remaining:** Exercise the opt-in contract on a nonconfidential project with
  owner-reviewed exact-part rating and maximum-stress sources. Keep the check
  inactive where those requirements have not been authored; the tool does not
  derive ratings, worst-case stress, or suitability.

#### LINT-071 — Source-bound component power-rating margin coverage

- **Status:** Implemented as an opt-in electrical contract. Synthetic unit,
  source-bound CLI/MCP, and retained-evidence replay tests pass. Exact-version
  KiCad 10.0.0/10.0.5 native exports now pass twice on both rating fixtures;
  normalized netlist and ERC-type signatures match, with zero ERC errors.
  Controls pass and authored over-limit faults fail on both versions. No project
  requirement opts into the check.
- **Cohort input:** The pinned public kicad_skills README and schematic review
  guide describe rating and derating review, while its PCB guide discusses
  power and thermal review. Those sources do not provide a deterministic
  part-specific dissipation algorithm. This implementation adopts the review
  question only and does not import candidate code, data, threshold, or runtime.
- **Problem:** Native ERC and schematic connectivity do not compare an exact
  fitted component's rated power against a reviewed worst-case dissipation
  envelope after thermal derating.
- **Contract:** `component_power_ratings` binds the exact reference, symbol,
  footprint, `PART_ID`, two native pins and nets, datasheet rated power, a
  project-reviewed derated allowable power, maximum expected dissipation,
  source conditions and calculation bases, and a project-selected utilization
  limit. The checker verifies identity, population, pin inventory, and
  connectivity before comparing expected dissipation with the derated limit.
  A derated limit above the source rating is rejected by schema validation.
- **Boundary:** No dissipation, duty cycle, current, temperature, thermal
  resistance, layout, or derating is inferred by the tooling. Project owners
  remain responsible for sources and corner calculations. V1 covers exact
  two-pin components only; arrays and multi-pin devices need per-element loss
  models. This is not a general part-suitability or release approval.
- **Fixtures:** Exact-part control at 0.10 W / 0.25 W allowable passes a 0.8
  utilization limit; changing only the authored stress to 0.21 W fails at
  0.84. Tests cover inclusive equality, wrong identity, wrong pin inventory,
  wrong or open nets, DNP state, missing part, invalid derating, and source-map
  order. CLI/MCP reports match, and retained evidence replay rejects omitted
  check rows. The synthetic native fixture is source-hashed in
  `tests/fixtures/design_lint/component-voltage-ratings/README.md`; that record
  contains the native results for both voltage and power fixtures.
- **Remaining:** Before any project adopts it, have the electrical owner review
  exact-part rating, operating conditions, derating, and maximum-stress
  sources. No proprietary source or fixture was used.

#### LINT-072 — Likely UART endpoint missing from the serial-peer map

- **Status:** Implemented as `bus.serial_unmapped_peer`, default `REVIEW`, with
  source-hashed contract context, exact ignores, project `review`/`block`/`off`
  overrides, synthetic fault/control and metamorphic tests, native regressions
  on KiCad 10.0.0/10.0.5, and CLI/MCP parity. It extends LINT-014's explicit
  endpoint contract with deterministic discovery coverage; it is not a
  replacement for that contract.
- **Incremental-value hypothesis:** If a fitted component exposes assigned
  TX/RX pin functions, or a fitted U/IC has assigned pins on explicit UART/
  USART-labeled TX/RX nets that also reach a common fitted connector candidate,
  prompt the reviewer when that exact pin pair is absent from `serial_peers`.
  This can surface an interface the native symbol metadata does not name. A
  finding requests review and never declares that the pins should connect or
  that grounds should be joined.
- **Predicate and evidence:** Read the native KiCad 10 normalized netlist's pin
  functions, net names and assignments, fitted/DNP state, and source-hashed
  project serial-peer map. The function path recognizes bounded TX/TXD and
  RX/RXD roles, optionally with a UART/USART prefix and channel number or
  numeric suffix; pins must belong to the same component, have unique
  assignments to distinct nets, and form an unmapped exact pin pair. The
  alternate path recognizes exact UART/USART TX/RX net labels, each with one
  uniquely assigned pin on a fitted U/IC and at least one common fitted
  connector candidate across both nets. It skips MCU pins already classified by
  native serial function. A project map suppresses only its exact TX/RX pin
  pair. Evidence includes discovery basis, channel, exact pins, assigned nets,
  roster state, contract path, and contract digest. Findings use the established
  fingerprint and project-decision lifecycle.
- **Boundary:** Net labels and pin functions are discovery clues, not an
  electrical requirement. The exact label path excludes bare TX/RX names,
  arbitrary aliases, ambiguous or multiple MCU pins, missing connector
  candidates, mismatched channels, and equal TX/RX nets. Unused MCU alternate
  functions and other serial interfaces can still prompt review. It does not
  find missing power/reference assignments or prove board copper continuity,
  component behavior, or off-board wiring. An explicit serial contract remains
  responsible for endpoint perspective, voltage limits, reference policy, and
  direct/shifted path requirements.
- **Fixtures:** Synthetic direct-peer control maps J1/J2; omitted J3 and
  alternate U1 UART channels produce localized review prompts. The separate
  synthetic net-label schematic has MCU package-pin functions `PA2`/`PA3`,
  generic connector pin names, and explicit `UART_TX`/`UART_RX` labels. It
  produces one REVIEW candidate when unmapped; the source-hashed exact-map
  control passes. Negative controls cover absent or DNP connectors, unmatched
  channel labels, ambiguous MCU assignments, bare TX/RX labels, DNP exclusion,
  differential-function exclusion, pending map states, project modes, exact
  ignores, and order stability. The source-bound parity fixture compares CLI
  and MCP reports on the same native XML evidence. Native fixtures export both
  serial scenarios twice under digest-pinned KiCad 10.0.0 and 10.0.5; repeated
  typed netlists and lint reports match within each version. See the
  [native fixture record](../tests/fixtures/design_lint/serial-peer-native/README.md)
  for synthetic source digests and reproduction details.
- **Public applicability sample:** The pinned Calcumaker screen recorded under
  LINT-031 produced one label-based coverage candidate on each of two board
  roots, where native MCU pin functions and generic connector functions did not
  activate the function-only detector. This demonstrates applicability, not a
  confirmed omission, false-positive rate, or review-effort reduction. The
  public sources remained outside Tooling; no project expectation was copied.
- **Cohort input:** The rule reuses the local SPI roster-coverage pattern and
  addresses LINT-014's omitted-peer discovery gap. It does not adopt cohort
  analyzer code or add a runtime dependency.
- **Remaining:** Reviewer effort, false positives, and incremental findings on
  owner-reviewed project maps remain unmeasured. Keep the default at `REVIEW`;
  no private project source or expectation was used.

#### LINT-065 — Connector/capacitor-only net has no visible local DC anchor

- **Status:** Implemented as a default-review heuristic over the native
  KiCad 10 netlist model. The catalog, typed finding, exact ignores, project
  `review`/`block`/`off` overrides, synthetic fault/control tests, and CLI/MCP
  parity are in place. No project data was imported.
- **Cohort input:** The public
  [kicad_skills schematic review guide](https://github.com/sabas0ba/kicad_skills/blob/53d1af8bc550f60415b4b8e51a6d2d5924ada03f/docs/guides/kicad-schematic-review.md)
  documents `analog.no_dc_path`: a net whose pins are all capacitors or
  connectors. Its source and runtime were later pinned and evaluated on
  tooling-owned synthetic fixtures under LINT-031. The candidate duplicates
  the fitted fault but also warns on the DNP-capacitor control because its
  predicate does not inspect population state. No code, examples, or candidate
  installation workflow was copied.
- **Problem:** ERC may have no basis to object when a connector signal and a
  capacitor share a valid assigned net, even if the local schematic shows no
  DC-driving or bias component there. Existing power-input and reset/enable
  checks require recognized native pin roles and do not cover general
  connector-facing signal nets.
- **Predicate:** For each non-return net, require at least one fitted
  connector pin and one fitted pin from a supported capacitor symbol. Every
  other fitted pin assigned to that net must also be one of those two classes.
  Ignore DNP components. Suppress the prompt for unknown symbols, ambiguous
  assignments, return-like pin functions, or any additional fitted component
  pin. Report exact net, pin, and symbol evidence.
- **Boundary:** This pattern does not prove that a DC reference is required
  or missing. A connector may receive its level from an off-board host, a
  component may provide internal bias, and a DC path can exist elsewhere in
  the circuit. Conversely, an additional part pin suppresses the prompt even
  when that part does not establish a DC reference. The rule does not identify
  analog signals, evaluate component values or states, trace DC paths, or
  establish PCB continuity. Use a project-authored contract for any required
  endpoint or bias relationship.
- **Fixtures and value:** Synthetic faults cover a fitted connector and
  capacitor on one non-return net; controls cover DNP connector/capacitor
  cases, a component-only or return net, an additional fitted part pin, and a
  connector designator whose explicit symbol is a resistor. A metamorphic case
  checks stable fingerprints under input reordering and suppression when a
  third component pin is added. A CLI/MCP synthetic native-XML parity case
  compares the finding with a local output-driver control. The native lane now
  also verifies that a DNP capacitor remains in KiCad's exported netlist with
  its DNP state and does not trigger the fitted-part predicate. Tooling-owned
  schematic fault/control fixtures and an opt-in native lane passed with
  pinned KiCad 10.0.0 and 10.0.5; package acceptance CI now runs this lane. All
  three cases have repeatable netlist/ERC evidence and zero ERC errors; the lint
  reports only the fitted fault. This is a demonstrated synthetic detection
  gain over native ERC for this pattern, plus population-state control evidence.
  It does not establish field effectiveness, a false-positive rate, or justify
  blocking policy. Source, normalized evidence, and image receipts are recorded in the
  [native fixture record](../tests/fixtures/design_lint/net-dc-reference/README.md).
- **Remaining:** Measure useful findings and false positives on approved
  nonconfidential projects before considering broader applicability or any
  policy promotion.

#### LINT-068 — Open-output signal input without visible local bias

- **Status:** Implemented as separate `signal.open_collector_input_without_visible_bias`
  and `signal.open_emitter_input_without_visible_bias` rules, both defaulting
  to `REVIEW`, with typed evidence, independent exact ignores and project rule
  overrides, synthetic fault/control tests, and CLI/MCP parity. This adds a
  review prompt for lines outside the narrower I2C, control-input, and active-low
  SPI chip-select checks.
- **Predicate:** From the native netlist, group uniquely assigned fitted pins by
  exact net. A candidate needs one or more `open_collector` outputs with at
  least one `input`/`input_low` peer, or one or more `open_emitter` outputs with
  such a peer. Collector candidates emit the collector rule ID and emitter
  candidates emit the emitter rule ID. A direct fitted conventional two-terminal
  resistor to a recognized positive rail satisfies the visible open-collector
  pull-up; a direct resistor to a recognized return satisfies the visible
  open-emitter pull-down. Nets that are themselves recognized rails are excluded.
  Specialized I2C, recognized reset/enable/boot, and active-low SPI chip-select
  functions remain with their more specific rules. Mixed
  open-collector/open-emitter driver types and pins with ambiguous net
  assignments are outside the check.
- **Boundary:** Native pin types do not prove that a local bias is required or
  that the output is used in that mode. Internal bias, off-board bias, series
  paths, arrays, jumpers, active circuits, custom rail names, resistor values,
  receiver thresholds, runtime behavior, and PCB connectivity are not
  verified. The result remains a review question; a project contract must
  state any required local topology or operating limits.
- **Fixtures and value:** Tooling-owned netlist tests cover missing expected
  pull-up and pull-down paths, opposite-polarity resistors, DNP outputs,
  specialized-bus exclusions, missing input peers, and input-order stability.
  A synthetic native-XML report fixture asserts both distinct rule identities
  through CLI and MCP. Separate netlist tests exercise independent policy
  overrides and exact ignores. Four tooling-owned native schematic fixtures
  pair an open-
  collector or open-emitter output with a separate input peer and test fitted
  pull-up/pull-down controls against otherwise identical DNP-resistor faults.
  The digest-pinned KiCad 10.0.0/10.0.5 lane exports netlists and ERC twice,
  checks native pin types, net assignments, DNP state, expected lint evidence,
  zero ERC errors, and repeatability. A local run passed on both versions; the
  normalized netlist hashes matched across versions and repeated exports. The
  source and normalized netlist hashes and fixture boundaries are recorded in the
  [native fixture README](../tests/fixtures/design_lint/open-drain-native/README.md).
- **Remaining:** The local digest-pinned lane passed on KiCad 10.0.0 and 10.0.5
  on 2026-10-01; the source hashes and repeated normalized exports are recorded
  in the fixture README. This checkout has no hosted workflow result. Record one
  after a CI-eligible ref runs, then measure applicability and false-positive
  behavior on approved nonconfidential projects before any policy promotion.

#### LINT-073 — MOSFET operating-state terminal-stress coverage

- **Status:** Implemented as the project-authored `mosfet_stress` electrical
  contract. It binds exact fitted three-pin MOSFET identity and pin functions,
  required operating states, authored terminal-potential intervals, datasheet
  VDS/VGS maxima, and an owner-selected utilization limit. The cohort analyzer
  remains deferred; no cohort code or dependency was added. The exact
  digest-pinned KiCad 10.0.0/10.0.5 acceptance lane passed on 2026-10-02 after
  correcting its state-specific fault assertion. Repeated native exports,
  exact identity and pin maps, equality controls, and over-limit VDS/VGS faults
  pass on both versions with zero native ERC errors; normalized netlist and
  ERC-type evidence repeats within each version. This validates the synthetic
  source and calculation path, not a real device's suitability.
- **Cohort input and installation:** The upstream
  [README](https://github.com/rjwalters/kicad-tools/blob/main/README.md) documents the base
  `pip install kicad-tools` flow, but not the `component-stress` command. Its
  [project metadata](https://github.com/rjwalters/kicad-tools/blob/main/pyproject.toml) declares
  version 0.21.1, MIT, and Python 3.10+. The installed package's `kct analyze --help` exposes
  `component-stress`; the published
  [CLI reference](https://github.com/rjwalters/kicad-tools/blob/main/docs/reference/cli.md) omits
  it. The base install succeeded with pip in a disposable environment; the trial recorded 18
  installed packages and needed no optional native C++ backend. The installed `kicad_tools`
  Python-source tree digest is recorded in the fixture README and local ignored receipts.
- **Contract and calculation:** Each project requirement lists the exact
  fitted MOSFET, symbol/footprint/`PART_ID`, one native pin number and exact
  D/G/S function for each terminal, expected nets, sourced VDS/VGS limits,
  required operating states, and minimum/maximum potential for each terminal
  net in every state. For intervals D=[Dmin,Dmax] and S=[Smin,Smax], the
  checker computes `max(abs(Dmin-Smax), abs(Dmax-Smin))`; it applies the same
  rule for G-S.
  Compare those bounds with the sourced ratings and project-selected
  utilization limits. Native symbol/pin-function and netlist evidence must
  match every authored role and assignment. Missing identity, pin mapping,
  state, or potential coverage is visible as a failing check; only a stress
  metric that needs a missing terminal interval is left not applicable. A
  VGS result may still be calculated when the drain potential is missing, for
  example. Independent net intervals may be conservative when extrema are
  correlated; they do not imply a reachable waveform.
- **Boundary and policy:** The analyzer does not infer operating states,
  terminal roles from reference/value strings, net voltage from names,
  switching waveforms, gate-drive timing, safe operating area, avalanche,
  thermal behavior, or hardware suitability. Project owners supply and review
  state coverage, potential intervals, rating sources, conditions, and
  utilization limits. A generic cohort-derived heuristic remains `REVIEW`; a
  project that declares this electrical contract as required receives blocking
  missing-coverage and over-limit results.
- **Cohort trial:** The version-pinned read-only trial catches
  synthetic VDS/VGS over-limit cases, accepts equality at the rating limits,
  and reports missing required states and node potentials as unresolved. Its
  findings name the MOSFET, state, terminal nets, stress, rating, and margin.
  It also reports all checks as passing for a DNP device and after the
  synthetic MPN changes, demonstrating missing population and expected-identity
  handling. The candidate manifests supplied only scalar steady-state
  potentials, not uncertainty intervals; the candidate trial did not exercise
  duplicate states or multi-device behavior. The local contract separately
  tests exact terminal-role/net mismatches and input-order invariance, and now
  exercises two independently mapped devices through unit and CLI/MCP tests.
  A direct LINT-064 comparison is inapplicable because its exact two-pin
  inventory cannot represent the same three-pin device. The local interval
  calculation is checked against exhaustive endpoint enumeration. Two KiCad
  10.0.6 ERC runs on the
  retained schematic each report the same ten findings; raw JSON differs only
  in the generated date. The deliberately sparse fixture is not a clean
  baseline, and ERC receives no operating-state manifest. LINT-064
  requires an exact two-pin native inventory and one requirement per part, so
  it cannot model D-S and G-S checks for this three-pin device. The state-aware
  multi-terminal capability is therefore a coverage gap, although the trial
  does not measure the unique defects a local contract finds on real designs.
  Exact cohort trial inputs, report digests, installation receipts, and known
  candidate gaps are in the
  [cohort trial README](../tests/fixtures/design_lint/cohort-mosfet-stress/README.md).
- **Synthetic evidence:** Tests cover exact identity, DNP exclusion, native pin
  functions and inventory, pin/net mismatches, missing state and potential
  coverage, conservative interval bounds against an independent arithmetic
  oracle over positive, opposite-polarity, and zero-crossing intervals, equality
  and over-limit boundaries, multiple states, input-order stability, and a
  two-device case where changing Q2's drain interval affects only Q2 VDS. The
  multi-device contract also passes CLI/MCP parity while a Q1 fault leaves Q2
  results passing. Retained-evidence omission rejection remains covered. Both
  control and fault pass/fail outcomes are derived from the same exact native
  netlist. Partial-state controls confirm that one missing interval does not
  suppress the independent voltage comparison for the other terminal pair. A
  tooling-owned schematic is checked twice for repeatable native
  exports and ERC signatures in the existing pinned-image acceptance lane.
  The multi-device regression uses a synthetic typed netlist contract; it does
  not expand the exact-version native fixture beyond one MOSFET.
  Local KiCad 10.0.6 and digest-pinned KiCad 10.0.0/10.0.5 exports pass exact
  identity and pin-map checks with zero ERC errors. The 2026-10-02 pinned run
  repeats normalized netlist digest
  `7061672756bfcb228a64155279b0e637377fc75b6871b3db976729f17292c224` on
  both versions; ERC-type digests are stable within each version and may differ
  between versions. The exact image digests and reproduction command are in
  the [synthetic native fixture record](../tests/fixtures/design_lint/mosfet-stress/README.md).
- **Next evidence:** Preserve LINT-064's two-pin identity rules. Before a
  project adopts this explicit requirement, its owner must review exact-part
  ratings, operating conditions, state coverage, potential intervals, and
  calculation bases. Any broader generic heuristic remains deferred without
  approved nonconfidential examples showing its applicability and review value.
  No proprietary project source or fixture is in scope.
- **V1 native acceptance:** Complete for the exact KiCad 10.0.0 and 10.0.5
  images. Follow-up applicability evidence is still required before broadening
  beyond project-authored requirements.

#### LINT-074 — Direct UART peers use different explicit reference nets

- **Status:** Implemented as `bus.serial_peer_reference_review`, defaulting to
  `REVIEW`, with project `review`/`block`/`off` overrides, exact fingerprint
  ignores, typed evidence, synthetic fault/control and metamorphic cases, and
  CLI/MCP parity. The detector covers fitted U/IC endpoints and source-
  identified connector candidates. Its exact-version native acceptance passed
  on KiCad 10.0.0 and 10.0.5 with repeated exports.
- **Problem and incremental-value hypothesis:** A native netlist can show two
  directly linked UART endpoints, each with a populated GND-like pin, while
  their pins occupy distinct nets. One endpoint may be an MCU/IC and the other
  a connector. ERC has no independent requirement that those references be
  common. This prompt adds context when generic numbered-return naming checks
  cannot associate the split with a direct UART signal link.
- **Predicate and suppression:** Find uniquely assigned, directionally clear
  native UART TX-to-RX links among fitted U/IC components and connector
  candidates identified by the bounded connector scan or project interface
  review. Require complete native pin-number, pin-function, and electrical-type
  inventories. Each endpoint must have one unique native net across its
  explicitly named GND/AGND/DGND/PGND/VSS/0V/RTN/RETURN/GROUND pins, with
  `passive` or `power_in` types; report when the endpoint nets differ. Explicit
  SHIELD, CHASSIS, FRAME, and PE functions are excluded. Suppress only when a
  current direct `serial_peers` map exactly matches both endpoint identities,
  TX/RX pins and nets, all explicit return pins and nets, and a `common_net`,
  `separate_nets`, or `bonded` reference policy. A `bonded` map also has to
  match its exact passive component and side-pin nets. Mapping supply pins
  cannot suppress the return-domain prompt.
- **Boundary:** This is a review question. It does not decide whether references
  should be common, joined through a specified component, or intentionally
  isolated. Incomplete pin metadata, DNP endpoints, ambiguous assignments,
  mixed return domains on one endpoint, connector candidates outside the
  bounded identity scan, and unsupported return-role spellings are skipped. A
  matching schematic map records reviewed intent and exact schematic bond
  assignments, but it does not prove component conduction, PCB copper
  continuity, off-board wiring, or electrical suitability.
- **Fixtures and evidence:** Synthetic tests cover IC-to-IC and MCU-to-header
  UART peers with split and common return nets, DNP and incomplete inventories,
  multiple endpoint return nets, exact `common_net`, `separate_nets`, and
  verified `bonded` maps, stale maps, a wrong-role supply-pin map, policy
  overrides, exact ignores, and ordering stability. Multi-port typed-netlist
  tests cover two UART headers on
  one MCU: the split-reference header produces one localized finding, the
  common-reference peer stays quiet, joining the first return clears the rule,
  and reversing component/net/pin-map order preserves the finding. These are
  unit results, not new native exports. The self-contained CLI/MCP regression
  `test_dual_uart_split_reference_localizes_one_header_on_cli_and_mcp` in
  `tests/test_design_lint_i2c_parity.py` runs a digest-bound synthetic netlist
  with one MCU driving two UART headers: J1 has the split return, J2 shares the
  MCU return, and only J1 is reported; its all-common control is quiet for this
  rule. The same CLI/MCP case now also applies an exact source-matched
  `separate_nets` peer map and confirms the intentional split no longer prompts.
  This verifies shared-service and adapter parity, not another KiCad export.
  The native lane retains
  three IC-to-IC
  schematics (same-rail common-reference control, different-supply
  common-reference voltage control, and split-reference fault) plus the new
  MCU-to-header common-reference control and split-reference fault. All are
  exported twice on digest-pinned KiCad 10.0.0 and 10.0.5. The two connector
  cases have matching normalized typed-netlist digests across repeats and
  versions: `08650946c2dfeb42dda98b16e7ba9b37b934fdd310e6fb70e9801cfec08fef7d`
  for the common control and
  `62d7ca8a8fa4b8006d4a9bf38a385d2b132527b3d18edb0f4f8ea95d178f410b` for the
  split-reference fault. On the same native-derived typed netlist, turning only
  this rule off leaves generic `bus.serial_unmapped_peer` and decoupling prompts;
  no other finding identifies the `GND_A`/`GND_B` split. The regression records
  this delta. Source hashes and reproduction details are in the
  [native fixture record](../tests/fixtures/design_lint/serial-peer-connector-reference-native/README.md).
- **Coverage report improvement:** The source-bound report now retains one
  row for each discovered native-function or numbered-label link, with its
  endpoint references, signal nets/pins, and `INCOMPLETE`, `COMMON_REFERENCE`,
  `SEPARATE_REFERENCE_REVIEW`, or `MAP_COVERED_SEPARATE_REFERENCE` disposition.
  This lets reviewers locate incomplete reference evidence from the report
  instead of seeing only a count. Earlier schema-version-2 reports without
  these rows remain readable. Synthetic incomplete, common, separate, mapped,
  and label-discovered cases plus CLI/MCP parity cover the report behavior.
- **Remaining:** The checks establish repeatable tool behavior on bounded
  synthetic native exports. False-positive rate and reviewer effort have not
  been measured on approved nonconfidential designs. Keep the heuristic at
  `REVIEW`; no project should infer that similar-looking reference nets must
  be joined. The Antmicro multi-UART screen under LINT-031 identifies generic
  pin functions and channel labels outside this predicate; proposed LINT-082
  records the narrow extension and its required controls. Do not infer a
  multi-hop peer or cross an isolator from net labels alone.
- **Bundled root-project applicability screen (2026-10-03):** The same 35
  repeat-exported KiCad 10.0.5 root projects produced no direct UART TX-to-RX
  peer links for `serial_participants` and no LINT-074 separate-reference
  candidates. This leaves the public-board applicability and reviewer-value
  question open; the result is not a detector-precision measurement. Source
  mapping, complete schematic inventory, and repeatable typed-netlist digests
  are retained under ignored
  `build/ci/public-demo-lint-screen/output/lint-074-analysis.json`.
- **Public isolated-serial boundary screen (2026-10-03):** The public
  [HALPI2 hardware](https://github.com/hatlabs/HALPI2-hardware) at commit
  `43a04926cf8c5deeb93934d8cd72719e51050c87` declares a CERN-OHL-S v2 license,
  identifies its design as KiCad 9.0, and describes its RS-485 port as
  isolated. On the pinned KiCad 10.0.5 image, repeated exports of the
  source-bound top-level `HALPI2.kicad_sch` produced 659 components and 442
  nets with identical normalized typed-netlist SHA-256
  `8cdb62dd43c7a9e016ce070e8bcedddda76ead56e69d0e91cdb62bb64c1164f4`.
  The native inventory preserves distinct `GND` and `GND_RS485` nets with
  470 and 23 assigned pins respectively. `directly_linked_serial_peers` found
  no direct TX-to-RX peer, so LINT-074 emitted no finding. This is an
  out-of-scope isolated-interface control, not an applicable sample or a
  false-positive measurement; the current rule deliberately does not traverse
  isolator and transceiver paths. The root schematic SHA-256 is
  `2aced504936afebfbdadfb79b3cd0ba01eb96783b3383cb216ebf7f1cfcfefbd`; the
  `rs485.kicad_sch` SHA-256 is
  `5c6c68304f52f88660ffb65df815f3a2fda608f2e44cb0039b392d883752dc53`.
  Native output and typed analysis remain under ignored
  `build/ci/public-demo-lint-screen/output/halpi2/`; no source was copied into
  Tooling.
- **Applicability report extension (2026-10-07):** LINT-074 now returns
  source-bound coverage for discovered native-function and numbered-label
  UART links. It distinguishes no direct peers, incomplete explicit reference
  metadata, and fully evaluated links; counts common and separate reference
  links, exact-map-covered links, and emitted review groups; and records the
  native netlist and authored-map provenance. Synthetic tests cover split and
  common references, incomplete pin evidence, no discovered direct links, and
  exact-map suppression. A dual-header CLI/MCP case checks one split link and
  one common control. This closes the report gap behind quiet results for this
  rule; the bounded status is not complete interface discovery, and the added
  coverage has not yet been screened on nonconfidential public designs. The
  report field is part of design-lint schema 2; schema 1 remains readable.
- **Done when:** Complete.

#### LINT-075 — Oscillator-module output load-path review

- **Priority and status:** P3 cohort-derived candidate; not an active catalog
  rule. LINT-031 now records a repeated no-CLI runtime trial on seven
  tooling-owned schematics. It demonstrates a narrow direct-load hint, a
  fixture-relative over-prompt for an allowed direct-drive topology, and misses
  for DNP and wrong-value series components. Native and part-applicability
  evidence remain open.
- **Cohort input:** The public [`kicad_skills` schematic-review
  guide](https://github.com/sabas0ba/kicad_skills/blob/main/docs/guides/kicad-schematic-review.md)
  lists `analog.clock_no_series_resistor`: an oscillator-module output that
  drives a load directly, with resistors and test points treated differently
  from active loads. This is a documented heuristic, not a universal
  clock-design requirement. The candidate review supplied no part-specific
  datasheet basis for when a series resistor is needed. No code or fixture was
  imported.
- **Problem and incremental-value hypothesis:** Native ERC does not compare a
  project's reviewed oscillator-output topology with the source-bound
  schematic. When a specific module requires a source resistor, removing or
  bypassing it can leave a syntactically valid netlist. An exact project map
  may catch that topology regression; a review hint may also find a likely
  unmapped oscillator output. Measure the mapped check against existing
  source-bound component and connectivity contracts before adopting a second
  mechanism.
- **Candidate predicate:** The deterministic path check must use a
  project-authored map identifying exact fitted oscillator component and
  library identity, output pin, named load pins, expected direct or series
  topology, and (for series topology) exact fitted resistor identity, pin
  endpoints, and reviewed value limits with source references. Compare these
  expectations with native KiCad netlist evidence bound to the schematic and
  contract digests. Any discovery prompt must be separately bounded to
  uniquely identified oscillator-module outputs and must report that its
  classification is uncertain.
- **Boundary:** Do not infer that every clock needs damping, that an output is
  an oscillator module from a generic `CLK` net name, or that a resistor value
  is suitable. Crystal and resonator networks, MCU-generated clocks, clock
  buffers, differential clocks, multiple fanout topologies, DNP links,
  ferrites, zero-ohm links, and off-board loads need explicit applicability
  evidence before support. Matching a map proves only agreement with the
  authored schematic topology; it does not prove the selected part's
  datasheet, signal integrity, placement, PCB copper, or measured waveform.
- **Trial fixtures and open evidence:** The initial no-CLI candidate trial in
  `tests/fixtures/design_lint/cohort-clock-series/` covers X-reference and
  `Oscillator:` library-ID discovery paths, direct and series topology, a
  shunt pull, a passive crystal, DNP, wrong-value, and an authored direct-drive
  alternative. The latter is a topology control, not a claim about a real
  part. Before considering implementation, expand the study to exact
  source-reviewed module classes and fitted part identities, include permitted
  test-point, wrong-part, wrong-net, bypass, and native source/netlist/ERC
  controls, and compare first-party project-map behavior. Measure localization
  effort and installation cost. Keep findings at `REVIEW` unless a project
  later supplies an independently reviewed exact requirement.
- **Done when:** LINT-031 records a pinned cohort version/commit, license,
  installation procedure, exact synthetic source/output hashes, and a result
  for every fault and control; a first-party check is added only if it
  demonstrates unique detection or materially better localization without
  treating valid direct-drive topologies as faults. No proprietary board or
  project data is in scope.

### Cohort source inspection register

The following source observations came from current public project
documentation and selected source inspection on 2026-09-27 through 2026-10-08.
Runtime trial evidence is recorded separately under LINT-031. No cohort tool
has been run on a private board or imported into this repository.

- **Same-net plane copper opens:** Public
  [kicad-tools issue #3787](https://github.com/rjwalters/kicad-tools/issues/3787)
  describes a board whose front and back ground planes share one schematic net
  but remain separate copper islands without ground stitching vias. The issue
  reports that schematic/net assignment and its DRC run did not establish a
  physical bond; its copper-LVS comparison exposed the opens. This failure
  description informed the synthetic LINT-025 unstitched-plane fault and
  through-via control. No candidate analyzer code, board, or project fixture
  was copied, and no head-to-head analyzer trial is claimed.
- **Operating-state MOSFET stress:** The public
  [kicad-tools README](https://github.com/rjwalters/kicad-tools/blob/main/README.md)
  documents the base pip installation, but it does not list
  `kct analyze component-stress`. The public
  [`pyproject.toml`](https://github.com/rjwalters/kicad-tools/blob/main/pyproject.toml)
  declares version 0.21.1, MIT, and Python 3.10+. Its
  [CLI reference](https://github.com/rjwalters/kicad-tools/blob/main/docs/reference/cli.md)
  also omits the subcommand; installed 0.21.1 command help exposes it. A
  disposable Python 3.11.16 install of 18 packages ran the synthetic trial
  under LINT-073. The read-only trial found the seeded VDS/VGS over-stress and
  missing coverage, passed the exact-rating boundary, and exposed DNP and
  expected-MPN gaps. It highlights a multi-terminal, per-state requirement
  that LINT-064's exact two-pin schema cannot express. No local head-to-head or
  unique defect measurement has been completed. Reports and fixture hashes
  are recorded in the cohort trial README. No candidate source, project
  example, or board was copied.
- **STM32 firmware pin-map comparison:** The public
  [STM32-KiCad-Pin-Checker](https://github.com/jbmata/STM32-KiCad-Pin-Checker)
  README documents `.net`/`.ioc` comparison, aliases, ignored pins, an MIT
  declaration, and a GUI-only invocation with CLI/CI listed as future work.
  Selected [`ioc.py` source](https://github.com/jbmata/STM32-KiCad-Pin-Checker/blob/main/ioc.py)
  parses a bounded set of signal and user-label keys and strips hyphenated
  suffixes from the IOC port key. Its current main revision was not pinned;
  this is not a runtime evaluation. The source motivates LINT-050's explicit
  pin map and fail-visible parser coverage, not code reuse.
- **I2C pull-up voltage context:** The public
  [kicad-happy changelog](https://github.com/aklofas/kicad-happy/blob/main/CHANGELOG.md)
  documents I2C pull-up, rise-time, and voltage-related analysis fields. This
  is documentation review, not a repeat runtime benchmark. LINT-059 uses only
  the category as a prompt to retain pull-up rail identities in evidence.
  LINT-010 now has an opt-in source-bound resistor-window contract derived
  from the [NXP I2C specification](https://www.nxp.com/docs/en/user-guide/UM10204.pdf)
  §7.1 and [TI SLVA689](https://www.ti.com/lit/an/slva689/slva689.pdf);
  the project must author its voltage, capacitance, sink-current, and timing
  assumptions. No guessed rail values or third-party detector code were
  imported.
- **Digital voltage and rail-sequencing review:** The inspected public
  [kicad-happy `VM-001` and `PS-001` source](https://github.com/aklofas/kicad-happy/blob/a6bba1add1e18b89e3aa0824b9769ed1d9d79174/skills/kicad/scripts/validation_detectors.py)
  uses rail-name voltage estimates and generic threshold tables for domain
  crossings, and common enable-pin names plus inferred regulator outputs for
  sequence edges. These remain discovery signals only. LINT-061 implements
  exact project-authored endpoint limits; LINT-062 implements an opt-in
  project-authored dependency graph, with numeric timing checks still deferred.
  The pinned `VM-001` runtime result is recorded under LINT-031. No candidate
  code or project data was copied.
- **Component-rating and voltage-derating review:** The public
  [kicad_skills README](https://github.com/sabas0ba/kicad_skills/blob/53d1af8bc550f60415b4b8e51a6d2d5924ada03f/README.md)
  describes rating checks; its
  [schematic review guide](https://github.com/sabas0ba/kicad_skills/blob/53d1af8bc550f60415b4b8e51a6d2d5924ada03f/docs/guides/kicad-schematic-review.md)
  says the voltage heuristic uses voltage-explicit rail names. The pinned repo
  declares Apache-2.0. These docs were reviewed, but the rating check was not
  source-audited or runtime-trialed; the separate LINT-031 trial covers only
  `analog.no_dc_path`. LINT-064 implements a source-bound contract with exact
  part identity, reviewed stress, and a project-selected margin. It rejects
  generic voltage-name guesses; no candidate code or project data was copied.
  LINT-071 separately checks authored power rating, derated allowable power,
  and worst-case dissipation against the native exact-part identity. Its
  synthetic results do not validate a real thermal calculation. Its exact-
  version native acceptance passes locally on KiCad 10.0.0 and 10.0.5; a
  hosted GitHub run for the current dirty branch is not recorded.
- **Connector/capacitor-only net review:** The public
  [kicad_skills schematic review guide](https://github.com/sabas0ba/kicad_skills/blob/53d1af8bc550f60415b4b8e51a6d2d5924ada03f/docs/guides/kicad-schematic-review.md)
  lists `analog.no_dc_path` for a net whose pins are all capacitors or
  connectors. LINT-065 implements an independent, exact-pin REVIEW candidate
  and explicitly allows off-board or internal bias. The pinned runtime trial
  found no unique detection and an extra warning on a DNP control; its rule and
  data-boundary evidence are recorded under LINT-031. No cohort code, fixture,
  or project data was copied.
- **kicad_skills rule selection and installation:** The
  [README at the pinned commit](https://github.com/sabas0ba/kicad_skills/blob/53d1af8bc550f60415b4b8e51a6d2d5924ada03f/README.md)
  documents a Docker/Bash CLI, KiCad 9.0.9 and 10.0.4 image tags, and a
  first-use image build of about five minutes; the container runs without
  network access. The schematic guide lists single-pin nets,
  missing drivers, decoupling, I2C pull-ups, LED limiting, power-input
  protection, and rating/derating checks; the [PCB review guide][kicad-skills-pcb]
  also discusses power, thermal, and crosstalk review. The single-pin-net
  finding class was already trialed under LINT-031 and repeated on both fault
  and control fixtures, so it is not adopted. Other schematic topics map to
  LINT-010, LINT-046, LINT-048, LINT-056, or source-bound contract candidates
  such as LINT-064. The `analog.no_dc_path` runtime trial used a separately
  installed host-side `--no-cli` fallback and did not validate the documented
  container workflow. It showed no unique detection; no adapter or runtime
  dependency is justified. Its public schematic guide also documents
  `analog.clock_no_series_resistor` for a directly loaded oscillator-module
  output. LINT-075 records a pinned no-CLI trial: it flags direct loads,
  including a fixture-authorized direct-drive alternative, distinguishes a
  shunt pull, and misses DNP and wrong-value series components. Native
  applicability, reviewer effort, and field precision remain unmeasured.

### Curated rule concept register

This register records concepts that have a specific deterministic or
reviewable candidate. “Adopted” means an independent local implementation has
synthetic tests; it does not mean a cohort tool was benchmarked or that its
engineering advice applies to every design.

| Concept                                                | Source input                                                                                       | Local disposition and next evidence                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| ------------------------------------------------------ | -------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Multiple global or hierarchical labels on one net      | kicad-happy `LB-001`                                                                               | Deferred after a partial exact-version trial: KiCad 10.0.0/10.0.5 ERC reports both distinct labels and the canonical net name for a synthetic alias fault; a repeated-name control is quiet. The candidate runtime and reviewer-time benefit were not measured. See the detailed disposition and fixture record below.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| Repeated connector supply/return functions             | Existing native-netlist patterns and the return-disconnect scenario                                | Adopted as review candidates in LINT-001/002 and synthetic-tested. Exact common, bonded, or isolated intent still belongs in project contracts.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| Numbered positive supply rail names                    | User's similar-connector power-pin scenario                                                        | LINT-040 adds a bounded, explicitly delimited net-name grouping hint for generic or numeric connector pin functions. Intentional isolation and independent sources remain valid; the feature is review-only and not a cohort runtime benchmark.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| Connector return-contact distribution                  | kicad-happy reports a signal-to-ground contact ratio                                               | LINT-038 adopted as an optional project threshold over explicit interface pin roles; synthetic fault/control tests distinguish the ratio question from missing-return and repeated-return findings.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| I2C pull-ups and responder addresses                   | kilint and kicad-happy rule families                                                               | LINT-010/033 provide direct-resistor, authored rail-to-input voltage-limit, and address checks. LINT-042 adds a review prompt for likely U/IC responders omitted from the authored address map, based on native SDA/SCL pin functions. Array channels and collisions have synthetic controls. Optional pull-up feasibility requires project-authored voltage, capacitance, sink-current, and timing bounds; it does not model internal pulls or unreviewed off-board loading.                                                                                                                                                                                                                                                                                                                                                                                                      |
| I2C pull-up feasible resistance window                 | kicad-happy rise-time metrics; NXP UM10204 §7.1; TI SLVA689                                        | LINT-010 derives a lower resistance bound from authored rail maximum, VOL limit, and minimum sink current, plus an upper bound from authored capacitance and rise-time limit. Source-bound controls cover both sides and an empty window; exact CLI/MCP results match. This is an idealized RC calculation over reviewed inputs, not a capacitance extraction, tolerance analysis, or waveform measurement.                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| MOSFET operating-state terminal stress                 | kicad-tools 0.21.1 `component-stress`                                                              | LINT-073 uses the cohort trial as a requirements lead and defers its analyzer because the trial passed DNP and changed-part controls. The local `mosfet_stress` contract checks exact three-pin identity and role mapping, required-state potential intervals, and VDS/VGS utilization; synthetic parity, retained-receipt, and digest-pinned KiCad 10.0.0/10.0.5 acceptance passed on 2026-10-02. The native lane validates synthetic source and calculation behavior, not device suitability.                                                                                                                                                                                                                                                                                                                                                                                    |
| I2C pull-up rail families                              | kicad-happy bus voltage/pull-up summaries; NXP UM10204                                             | LINT-059 prompts when visible fitted pull-up paths use different recognized rail-name families across SDA/SCL. It does not resolve rail values, assert incompatibility, or replace project-authored endpoint voltage limits. Same-family aliases, DNP devices, custom names, and unmodeled pull-up circuits have controls or explicit boundaries.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| SPI participant and CS review                          | kicad-happy `detect_sensor_interfaces` and `validate_spi_bus`                                      | LINT-052 compares bounded SPI-like native pin functions with the source-hashed project roster; it prompts for review when a likely participant is unlisted or no roster exists. Exact-version native exports on KiCad 10.0.0/10.0.5 preserve prefixed SCLK/COPI/CIPO/NSS functions and distinguish an absent-roster prompt from a complete-roster control. Pinned source inspection found that sensor peers are listed by shared extracted nets but not compared with authored membership; its CS detector covers pull-up topology. LINT-045 separately implements the CS-bias prompt. The inventory is a clue, not proof that a device belongs on that bus.                                                                                                                                                                                                                       |
| Unmapped cross-supply digital peers                    | kicad-happy `VM-001`                                                                               | LINT-066 implements default-REVIEW prompts for recognized SPI and UART/USART TX-to-RX peers using complete native pin-type and exact voltage-explicit supply-label evidence. It does not infer incompatibility; complete exact LINT-061 maps take over covered links. Synthetic fault/control and CLI/MCP parity pass. SPI repeated native exports pass on pinned KiCad 10.0.0/10.0.5; UART repeated local KiCad 10.0.6 exports pass and the pinned-version lane is configured. Field false-positive measurements remain open. See both fixture notes.                                                                                                                                                                                                                                                                                                                             |
| CAN peer pair net asymmetry                            | kicad-happy v2.2.1 CAN protocol checks; repeated native CAN pin assignments                        | LINT-067 prompts when fitted complete CANH/CANL pairs share one exact schematic net but diverge on the other. It is a review-localization hint, not a determination that the pairs must be joined. Synthetic same-pair, one-side split, separate-bus, and DNP controls plus repeated native exports without ERC errors pass on KiCad 10.0.0/10.0.5; isolated-library warnings are recorded. The LINT-031 runtime trial emitted the same empty-net missing-termination message on control and fault and did not expose PR-003 in JSON. Reviewer effort and field false positives remain unmeasured.                                                                                                                                                                                                                                                                                 |
| USB-C port role-map coverage                           | kicad-happy USB-C CC validation                                                                    | LINT-053 prompts when a connector exports both CC1/CC2 pin functions but is absent from the authored role map. Native exports on KiCad 10.0.0/10.0.5 prove this bounded pin-function field and mapped/unmapped behavior. A pinned v2.1.0 runtime trial recognized simple 56 kΩ source and 5.1 kΩ sink controls, but for an unknown role it emitted sink-specific missing-pull-down findings while reporting the role as unknown. It adds no unique coverage over the local role-map prompt and authored role checks; details and hashes are in the synthetic fixture notes.                                                                                                                                                                                                                                                                                                        |
| LED current-limiter presence                           | kicad-happy `validate_led_resistors`, LR-001; LED audit `LA-AUD`                                   | LINT-048 keeps exact `Device:LED` direct positive-rail/return assignments as a review hint; LINT-063 prompts when a native output-capable pin directly shares an LED terminal and the other terminal is on a recognized rail. A read-only `LA-AUD` trial corroborates the simple direct-output case but misclassifies the parallel-resistor fault as `resistor_limited`; the local rule retains that finding. Native exports on KiCad 10.0.0/10.0.5 assert the parallel resistor shares both LED nets before testing. ERC, current, and electrical qualification remain open; exact cohort hashes and reports are in the synthetic fixture notes.                                                                                                                                                                                                                                  |
| USB external series-resistor topology                  | kicad-happy PR-004; ST AN4879; TI TUSB2036 datasheet                                               | LINT-049 implements an opt-in exact connector-to-PHY path map. The source-backed integrated STM32 direct-path control and TI TUSB2036 27R control both pass; removing a mapped resistor is detected. The generic cohort rule prompts on both PHY classes, so its universal resistor assumption is not adopted. Native source-to-netlist regressions now pass synthetic direct, series, and bypass cases on KiCad 10.0.0 and 10.0.5. Native ERC and electrical qualification remain open.                                                                                                                                                                                                                                                                                                                                                                                           |
| STM32CubeMX to KiCad MCU pin assignments               | jbmata/STM32-KiCad-Pin-Checker README and selected `ioc.py` source                                 | LINT-050 implements a configurable, source-hashed contract for exact package-pin, KiCad symbol-pin, schematic-net, CubeMX signal, and label comparisons. Synthetic service and CLI/MCP parity cases pass; repeated native exports pass on pinned KiCad 10.0.0 and 10.0.5. The cohort desktop tool remains unadopted and has no runtime trial.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| IC power-pin DC-source path                            | kicad-happy `audit_power_pin_dc_paths`, PP-001                                                     | LINT-031's mapped wrong-rail follow-up shows PP-001 detects the ERC-clean synthetic fault when no map exists, while the valid path control is quiet. The project-authored LINT-055 map already catches it when supplied. LINT-056 adopts a configurable fallback REVIEW using a narrower explicit passive set; it does not copy the candidate's severity or “AC-coupled” diagnosis. External source recognition, custom paths, and broader false-positive behavior remain open.                                                                                                                                                                                                                                                                                                                                                                                                    |
| Connector/capacitor-only net without visible DC anchor | kicad_skills `analog.no_dc_path`                                                                   | LINT-065 adds a default REVIEW when every fitted pin on a non-return net is a supported connector or capacitor and at least one of each is present. It does not trace DC paths and allows off-board/internal bias. Native KiCad 10.0.0/10.0.5 runs repeat the fault, output-driver control, and DNP-capacitor control; ERC is clean in all. The pinned cohort runtime duplicates the fitted fault, stays quiet on the output-driver control, and warns on the DNP control because it counts unpopulated C/J/P-prefixed symbols. No unique detection; see LINT-031. This is synthetic evidence, not field validation.                                                                                                                                                                                                                                                               |
| Unmapped decoupled power-input source path             | kicad-happy `PP-001`                                                                               | LINT-056 uses native `power_in`, fitted capacitor-to-return evidence, recognized positive rails or `power_out` pins, and a bounded fitted path graph. It recognizes bidirectional passive elements and the exact bridged solder-jumper symbol, and traverses exact supported diodes in the source-to-load direction. It prompts REVIEW when no supported path is found and suppresses the prompt for endpoints covered by an authored LINT-055 map. The synthetic assigned-wrong-rail case is missed by the mapless baseline and native ERC; the check does not infer required connectivity or prove conduction.                                                                                                                                                                                                                                                                   |
| IC decoupling-to-return coverage                       | kicad-happy `DO-DET`; kicad_skills `analog.missing_decoupling`                                     | LINT-046 emits a review prompt for a source-backed no-cap schematic whose `power_in` and `power_out` pins share `+3V3`; native KiCad 10.0.0/10.0.5 report no `power_pin_not_driven` violation. kicad-happy reports the no-cap fault and also synthetic source U2; kicad_skills duplicates the fitted fault/control result in `--no-cli` fallback mode. The kicad_skills DNP case stays quiet although native exports preserve the DNP flag and LINT-046 reports it. These trials add no unique detection; capacitor need/value, placement, and PCB return path remain open. See LINT-031 and the synthetic fixture record.                                                                                                                                                                                                                                                         |
| External connector protection coverage                 | kicad-happy and ThomsonLint `EMC_ESD_001`                                                          | LINT-034 adopted as a source-bound per-pin coverage contract. Applicability is authored; clamp suitability and PCB return geometry remain unverified.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| Crystal load network                                   | kicad-happy crystal analysis                                                                       | LINT-035 adopted for an explicitly mapped Pierce topology, nominal value ranges, and source-bound pins. Startup, tolerance, and placement are not established.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| Adjustable regulator setpoint                          | kicad-happy feedback-divider analysis                                                              | LINT-036 adopted for a project-mapped two-resistor topology and reviewed reference range. No part-name inference or general converter model is used.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| Reset/enable/boot default state                        | ThomsonLint `MS_RST_001`; kicad-happy control-signal review                                        | LINT-017 includes an exact project contract and an optional REVIEW hint for unassigned supported input pins; DNP parts are excluded. Read-only exports from public KiCad demo projects exercised recognized reset, enable, and boot aliases with native input types. These names remain clues and do not establish required polarity, bias, or successful runtime behavior.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| RC filter cutoff                                       | kicad-happy passive-network analysis                                                               | LINT-037 adopted as an explicitly mapped first-order source-bound review; a synthetic value mutation preserves connectivity and triggers a corner-range finding. Multi-stage and loaded networks need separate models.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| Decoupling placement                                   | pcb-inspector, ThomsonLint, and kicad-happy EMC `DC-003`                                           | LINT-020 now optionally checks an authored maximum distance from an exact capacitor return pad to the nearest via in that pad's native copper component. The rule reports the via identity and measured geometry; it does not estimate loop inductance or require a via when the project omits the limit. KiCad 10.0.0/10.0.5 fixtures cover a connected via at the boundary, a moved-via fault, and unconnected nearby-via control. No cohort implementation or board fixture was imported.                                                                                                                                                                                                                                                                                                                                                                                       |
| Mapped track-width screen                              | pcb-inspector power-width analysis; ThomsonLint thermal/power guidance                             | LINT-021 implements project-authored per-net minimum-width screening with native segment evidence. Zone-only nets remain incomplete; current, thermal, via, and plane analysis is deferred.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| Adjacent reference-plane coverage                      | pcb-inspector `HEUR-GND-001`; kicad-happy `GP-001`                                                 | LINT-058 maps exact signal nets/layers and measures centerline fraction over adjacent same-net filled copper. The 5 mm/0.9 cohort example is not a default. A pinned kicad-happy `GP-001` run sampled only the endpoints of a 2 mm route and missed a 0.2 mm midpoint void; a pinned pcb-inspector `HEUR-GND-001` run detects the same fault and clears the control at a fixture-only 0.65 threshold, but reports the full segment affected and adds no unique detection. LINT-058's exact native geometry distinguishes the synthetic fault from its continuous control and reports endpoint-via clearance context while keeping those intervals uncovered; merged-hole ownership remains unknown. The hosted 10.0.0/10.0.5 repeat is pending. This review rule does not prove return-current continuity.                                                                         |
| Differential-pair constraints                          | pcb-inspector and ThomsonLint `HS_DIFF_001`                                                        | LINT-022 comparison on synthetic boards showed KiCad 10.0.0/10.0.5 DRC catches configured width, gap, skew, and uncoupled-length faults; no pair finding appears without an authored rule. The tooling now audits project-authored limits against the exact source-bound active native rules. Independent geometry checking is deferred; no cohort implementation or board was imported.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| Missing differential-pair review coverage              | pcb-inspector `HEUR-DIFF-001`                                                                      | LINT-031 measured a unique 0.50 mm skew warning without native pair rules, but its default 0.15 mm limit is not universal and it misses equal-length gap/uncoupled faults. LINT-041 adopts only a deterministic name-pattern prompt for an explicit project pair requirement; native geometry limits remain project-authored under LINT-022.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| Switching-loop geometry                                | pcb-inspector and ThomsonLint buck hot-loop guidance                                               | LINT-023 reports a project-authored pad-center polygon proxy and same-island return-plane check. Native F.Cu, connected In1.Cu, and split In1.Cu synthetic fixtures pass on KiCad 10.0.0/10.0.5. LINT-039 captures why routed comparison needs explicit edge roles and unique route resolution; converter-topology coverage remains open.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| Schematic near-miss localization                       | kicad-sch-lint and KiDiff                                                                          | LINT-024 has eleven opt-in review rules. kicad-sch-lint text-overlap, text-over-wire, text-over-body, and wire-through-body trials each distinguish the synthetic graphical fault from its control while native ERC/netlist signatures remain unchanged. First-party text checks use bounded font envelopes; body checks use supported embedded symbol graphics and axis-aligned envelopes. LINT-044 scopes unsupported coverage to enabled rules. Public-template review found one unique J1 wire/body layout repeated in two examples; KiCad 10.0.6 ERC was clean, but neither project records intent, so the result is unresolved rather than a false-positive measurement. All rules remain default-off review hints; intentional overlaps, crossings, and T-shaped contacts remain possible, and no geometry auto-fix is allowed. Remaining fixture classes are listed there. |
| Analyzer execution and skipped-check coverage          | kicad-happy v2.2.1 `checks_run`, `connectivity_graph_error`, and skipped conditional DRC reporting | LINT-076 adds source-bound execution receipts for the three mapped checks that lacked dedicated coverage. Its audit found no other current service gap that justifies a global per-rule ledger; reopen when a new check can skip without observable status. No cohort code or report format is imported.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| Clock termination and driver topology                  | ThomsonLint `HS_CLK_001`; kicad_skills `analog.clock_no_series_resistor`                           | LINT-031 records the pinned no-CLI trial in LINT-075. It shows a useful direct-load hint but also an over-prompt on an authored direct-drive alternative and misses DNP/wrong-value components. Do not adopt a universal series-resistor rule. A source-bound path map remains conditional on reviewed part requirements and native evidence.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| ADC/op-amp protection and operating range              | ThomsonLint `AN_ADC_001` and analog rule families                                                  | Deferred as a generic rule. Device limits, source impedance, protection ratings, filter targets, and operating conditions need reviewed device-specific inputs; some protection coverage already belongs to LINT-034.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| Universal ESD requirement for every connector          | ThomsonLint `EMC_ESD_001` and kicad-happy protection review                                        | Rejected as a universal blocking rule. LINT-034 instead requires an explicit per-pin protection or not-required decision for scoped external interfaces.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |

**Disposition — multiple global or hierarchical labels on one net (LB-001):**
**Status (2026-10-03):** Keep the electrical lint deferred. A Tooling-owned
synthetic fault with two distinct global labels on one net and a repeated-name
control were exported twice using the exact KiCad 10.0.0 and 10.0.5 images
listed in the [fixture record](../tests/fixtures/design_lint/cohort-label-alias/README.md).
For both versions, the fault adds ERC warning `multiple_net_names`; its
diagnostic names both labels and says which one supplies the netlist name. The
duplicate-name control does not emit that warning. Normalized pin/net
assignments and ERC signatures repeat across exports and versions; raw XML
timestamps differ. Thus the documented kicad-happy [`LB-001`][happy-lb001]
predicate overlaps native ERC for this tested case, and no electrical
detection gain is demonstrated.

This is a partial native comparison, not a trial of the candidate runtime.
The candidate's additional maintainability explanation and review-time value
remain unmeasured, as do intentional aliases, power-label exclusions, and
same-name labels on separate sheets. The existing source geometry reader also
does not yet provide a complete, native-bound label-to-net inventory. Reopen
only if a candidate comparison demonstrates a repeatable review gain, such as
materially better localization or a useful case native ERC misses. Keep any
future result at `REVIEW`; multiple labels alone do not establish a wiring
fault. No cohort code or project data was imported.

### Cohort cross-analysis rule audit

The public [kicad-happy v2.2.1 changelog][happy-changelog] and
[PCB methodology][happy-pcb-methodology] document several cross-analysis
families. The changelog names CC-001 connector current capacity versus trace
width, EG-001 ESD coverage, DA-001 decoupling adequacy, and XV-001..003
schematic/PCB checks. Its [cross-verification release notes][happy-cross-verify]
also describe differential-pair length/skew, power-trace width, decoupling
placement, bus routing, and thermal-via checks. The methodology describes
per-net route length, minimum power-net track width, via dimensions, and an
approximate IPC-2221 current screen; this is documentation review, not an
implementation audit or runtime trial. The local dispositions below compare
these descriptions with existing tooling so new work targets a demonstrated
gap. This documentary re-audit was recorded on 2026-10-01; pin the exact
candidate commit and installation inputs before any new runtime comparison.

| Candidate                                          | Existing local coverage                                                                                                                                                                                                                  | Disposition and evidence required                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| -------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CC-001 connector/contact current versus PCB copper | LINT-021 measures project-mapped net track widths; LINT-071 checks authored component power dissipation. LINT-077 now checks owner-authored current against an exact per-contact rating. Neither local check calculates copper ampacity. | The contact slice is implemented in LINT-077 with exact identity/pin binding; pinned native receipts remain pending. Defer copper-capacity work until an independently reviewed model defines stack-up, temperature, vias/zones, route topology, branching, and current allocation. Do not infer ratings or current sharing from net names or a net-wide minimum width. The public candidate implementation was not installed or runtime-tested; only its documented question informed this narrower local contract. |
| EG-001 external-connector ESD coverage             | LINT-034 requires a reviewed protection disposition per scoped connector pin; LINT-060 checks mapped PCB entry and return-via geometry.                                                                                                  | No new rule yet. Compare a pinned candidate on synthetic covered, uncovered, DNP, alternate-protection, and explicitly-not-required cases. Advance only if it finds an applicable pin omitted by connector coverage or materially improves localization without treating every connector pin as ESD-sensitive.                                                                                                                                                                                                       |
| DA-001 decoupling strategy adequacy                | LINT-046 prompts on selected schematic power-input rails without a fitted capacitor; LINT-020 measures project-mapped PCB capacitor placement and optional connected return-via distance.                                                | No new rule from the changelog description alone. Inspect the exact predicate and trial it against multiple supply pins, shared capacitor banks, DNP parts, remote/plane returns, and datasheet-approved alternatives. Require a distinct confirmed finding beyond the two local checks before designing a new contract.                                                                                                                                                                                             |
| XV-001..003 schematic/PCB consistency              | Existing verification binds native schematic/netlist and PCB artifacts; selected geometry checks also bind board and netlist hashes.                                                                                                     | Keep deferred until each XV predicate and evidence source is identified. Compare one rule at a time with existing native consistency checks; a second report of the same mismatch is review duplication unless it improves actionable localization or catches a documented gap.                                                                                                                                                                                                                                      |
| CC-001 style ampacity-target net-class proposal    | LINT-021 accepts project-authored minimum widths and records exact native track measurements.                                                                                                                                            | Treat the public [kicad-tools ampacity-target proposal](https://github.com/rjwalters/kicad-tools/issues/4216) as an unimplemented research lead, not a cohort feature to import. Any future derivation needs a documented, licensed/available calculation basis, explicit copper and temperature assumptions, boundary tests, and comparison with an independent reference. Preserve authored widths as screens until that evidence exists.                                                                          |
| Mapped bundle route length and inter-signal skew   | LINT-095 audits project-authored exact endpoints, bundle membership, and active native DRC length/skew rules; LINT-022 covers differential-pair constraint coverage.                                                                     | Keep using native DRC for route measurement and LINT-095 for authored intent and rule coverage. Reconsider a separate geometry engine only if it adds independently confirmed coverage or materially clearer localization beyond those checks.                                                                                                                                                                                                                                                                       |
| Thermal-via coverage for mapped dissipating parts  | LINT-071 compares exact-part dissipated power with an authored derated power limit; it does not estimate package temperature or via benefit.                                                                                             | Keep deferred until a project-authored thermal requirement identifies the exact package, heat path, layers, connected via population, copper stack, and boundary basis. Test any narrow geometry screen against pad-connected, unconnected, wrong-plane, DNP, and datasheet-supported alternatives. Stop if via count or density is presented as thermal adequacy without an independently reviewed model.                                                                                                           |

No candidate code, installation workflow, project design, or example fixture
is adopted by this audit. Candidate runtime evidence remains under LINT-031;
documentation descriptions alone do not count as a detection gain.

### Domain-specific cohort backlog candidates

The public [kicad-happy changelog](https://github.com/aklofas/kicad-happy/blob/main/CHANGELOG.md)
lists additional domain families. This is a source inventory, not evidence of
local detection value. None of the candidates below is an active lint rule or a
runtime-trial result. Advance one only when its project-specific source data,
applicability, deterministic comparison, and valid alternatives can be tested
without importing a product design.

| Candidate family                                     | Existing overlap                                                              | First bounded work                                                                                                                                                                                                                                 | Stop or defer when                                                                                                                                                                                                 |
| ---------------------------------------------------- | ----------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Wireless module antenna and RF feed review           | Connector/pin coverage, protection maps, mapped PCB geometry                  | See proposed LINT-097: bind exact module identity and RF pad/net to a vendor-sourced module-local keepout map, then test only on synthetic schematic/board pairs.                                                                                  | Symbol/value text is the only identity evidence, antenna geometry is absent, or the check cannot distinguish module antennas from external RF connectors and intentional keepouts.                                 |
| Transformer-isolated converter feedback topology     | LINT-036 regulator feedback and LINT-034 interface/protection contracts       | Trial an authored map for exact controller feedback pins, optocoupler/secondary reference parts, and expected connectivity. Use source-bound device limits only for explicit comparisons; do not label topology matching as loop-stability proof.  | The candidate depends on generic component-name guesses, copied reference designs, or undocumented compensation assumptions; the local check duplicates a source-bound feedback contract without clearer findings. |
| Supercapacitor and energy-storage operating envelope | LINT-064 voltage ratings, LINT-071 power ratings, and power-path maps         | Inventory the distinct requirement fields needed for exact storage-part identity, working voltage, charge/discharge path, and owner-authored operating bounds. Build fault/control cases only after selecting a narrow source-backed use case.     | Safe charge current, inrush, hold-up, life, or energy behavior would be inferred from symbol connectivity without part-specific ratings, state assumptions, and reviewed calculations.                             |
| PWM LED driver-to-load topology                      | LINT-048 direct LED assignment and LINT-063 output-driven LED path review     | Compare an authored driver-output-to-string map with exact LED/current-control component pins and connectivity; test multi-channel and valid constant-current alternatives against current LED prompts.                                            | The proposed check merely rediscovers a directly driven LED, assumes PWM means a missing resistor, or needs current/brightness limits that the project has not supplied.                                           |
| Audio jack switch-contact state                      | LINT-001 connector coverage and LINT-069 project-authored custom-symbol roles | Trial a project-owned exact connector pin/state map for inserted and removed plug states, with fixtures for normal-open/normal-closed contacts and intentionally unused pins. First prove the native source contains enough identity and pin data. | KiCad schematic connectivity cannot represent the mechanical state, the library switch pins lack reviewed identities, or the tool would need to infer an audio circuit from reference/value naming.                |

#### Preliminary source audit: antenna keepout coverage (2026-10-08)

A pinned source inspection of
[kicad-happy `analyze_pcb.py` at `a6bba1a`][happy-pcb-analysis]
and its [PCB layout guidance][happy-pcb-layout]
found a useful idea but not a reusable antenna-coverage check. The guidance
calls for vendor-sourced antenna-area geometry and copper keepout coverage on
the relevant layers. Its inspected `KO-001` implementation checks component
and via center points against the bounding box of an already-present keepout;
that predicate cannot find a missing antenna keepout, verify its exact outline,
or bind the area to an RF pad and module identity. The implementation reports
those findings with error severity, so its disposition is not a suitable local
default.

LINT-097 is now implemented as an opt-in, project-authored map of exact module
identity, RF feed pad/net, antenna disposition, and module-local keepout
polygons. The shared native PCB probe supplies footprint transforms; the
analyzer compares transformed geometry and restrictions with the source-bound
rule area. Default disposition is `REVIEW`, with project policy able to select
`block` or `off` and an exact fingerprint ignore. LINT-096 continues to cover
global named rule-area signature regression. No cohort code, dependency,
project source, or proprietary fixture was copied; no kicad-happy runtime trial
is claimed here.

These candidates were transcribed from public domain-detector descriptions
reviewed on 2026-10-01. They need exact cohort revision pins and isolated
synthetic runtime comparisons under LINT-031 before implementation planning;
their presence here does not recommend adopting `kicad-happy` or adding its
runtime dependency.

The inspected public repositories identify ThomsonLint, kicad-happy, and
pcb-inspector as MIT-licensed; KiDiff v2.6.0 declares GPL-2.0; kicad_skills
declares Apache-2.0. This branch
records their ideas and source links; it does not copy their implementations,
bundled examples, project data, or installation workflows. Read-only runtime
trials for kicad-happy, kicad-sch-lint, pcb-inspector, kilint, and KiDiff are
recorded under LINT-031. The kicad_skills `analog.no_dc_path` trial also found
no unique detection and did not justify an analyzer dependency. Other candidate
runtime trials remain open.

- **[kicad-sch-lint](https://github.com/rashuky/kicad-sch-lint):** Documents
  KiCad 10 schematic geometry checks for pin-line near misses, floating
  labels, dangling wires, junctions, body/wire overlaps, and transformed pin
  tips; its workflow also includes text repair. Use its reported check classes
  to sharpen LINT-024 synthetic fixtures. Rebuild only read-only, source-bound
  checks; leave mutation out. Compare actionable localization with native ERC
  before calling it new detection.
- **[kicad-happy](https://github.com/aklofas/kicad-happy):** Documents
  deterministic schematic extraction and detector families for dividers,
  regulator feedback, oscillators, protection, buses, voltage domains, and
  sequencing, followed by a separate agent review. Its protection-coverage
  concept informed the independent LINT-034 contract and synthetic tests; its
  documented crystal detector family informed LINT-035. No source code,
  project data, skill, plugin, or runtime dependency was imported. The documented
  divider equation informed LINT-036, whose explicit map avoids the upstream
  part-name Vref lookup and fallback heuristic. Its `validate_spi_bus` PR-002
  missing-chip-select-pull-up review check informed LINT-045, which narrows
  applicability to explicitly active-low native input pins and fitted
  resistor-path evidence. The LINT-031 runtime trial matched the missing-bias
  and fitted 10 kΩ cases but accepted DNP 10 kΩ and 0 Ω anti-controls; it added
  no detection beyond the local rule. The USB `validate_usb_bus` PR-004
  series-resistor detector was also run under LINT-031 and deferred to LINT-049
  pending PHY-specific applicability. A v2.1.0 USB-C CC trial is also recorded
  under LINT-031: it matched simple source/sink controls but treated an unknown
  role as missing sink pull-downs, adding no unique value over LINT-053/LINT-012.
  LINT-037 and LINT-038 now have separate independent implementations; other
  detector families remain unverified until they have bounded predicates and
  synthetic fault/control evidence. Its v2.2.1 changelog also describes a
  `checks_run` manifest for cross-analysis, with explicit reasons for skipped
  checks and examined-item counts, plus surfaced connectivity-graph errors and
  skipped conditional DRC rules. This is the candidate input for LINT-076;
  Tooling has not installed or run that release for this feature. Its broader
  installation and review workflow is not required for these typed checks.
  Other detector families are not considered verified from documentation
  alone.
- **[pcb-inspector](https://github.com/takzen/pcb-inspector):** Documents
  configurable spatial rules for decoupling, copper width, differential pairs,
  switching loops, and return references. Selected decoupling source uses a
  nearest-pad Euclidean-distance threshold. Compare these metrics under
  LINT-020 through LINT-025. Distance is not loop inductance or copper
  continuity; preserve the measured quantity and avoid stronger claims than
  the evidence supports.
- **[kilint](https://github.com/romkey/kilint):** Documents project-level
  opt-in rule configuration, per-item disables, I2C pull-up resistor-network
  configuration, and style/documentation checks. The project describes itself
  as early alpha. A read-only README recheck on 2026-09-30 says configured
  `R`/`RN` prefixes can identify pull-ups from KiCad PCB pad-net assignments;
  the README observation is documentation review, while the separate LINT-031
  runtime trial below evaluates its direct and series-chain behavior.
  LINT-010 now supports a project-authored, exact resistor-array channel map
  and resolves the matching schematic hint only when the source-bound checks
  pass. This is an independent implementation, not adopted kilint code or a
  runtime dependency. The LINT-031 runtime trial of version 0.5.1 found a unique
  synthetic review prompt for an undeclared U-prefixed I2C responder; LINT-042
  independently implements the coverage prompt from native pin functions and
  project map entries. A separate LINT-031 v0.5.1 pad-net trial found that the
  candidate warns on an unbranched two-resistor SDA chain accepted by Tooling's
  source-bound heuristic; its rule only checks for a direct signal-to-power
  resistor pad assignment. Tooling retains series-path coverage independently.
  Metadata conventions are lower priority than electrical regression coverage.
  Do not reuse its project ignore format without checking this repository's
  fingerprinted review lifecycle.
- **[ThomsonLint](https://github.com/holla2040/ThomsonLint):** Provides
  engineering rule knowledge and applicability guidance. Keep it as curated
  source material for LINT-030. Convert a rule into a deterministic predicate
  and synthetic fault/control pair before adding it to the active catalog.
- **[KiDiff](https://github.com/INTI-CMNB/KiDiff):** Provides visual comparison
  of schematic and PCB revisions. The LINT-031 v2.6.0 trial highlighted
  synthetic common-to-split return-label edits but added no electrical
  detection; it does not infer whether the split is intentional. Treat it only
  as an optional review aid under LINT-024, with no runtime dependency or
  verification credit.

Continue cohort trials on synthetic projects with controlled faults and valid
alternatives. Record tool commit/version and install procedure, then compare
confirmed findings, duplicates, missed faults, false positives, localization
effort, and maintenance cost. Existing runtime results are fixture-specific:
they support bounded review hypotheses, not field effectiveness or approval of
a candidate implementation. Keep false-positive rate, reviewer effort, and
maintenance cost open wherever they were not measured.

## Suggested delivery order

1. Maintain the implemented rule catalog and synthetic fault/control fixtures.
   The LINT-054 baseline now covers all active rules; classify every added rule
   with an executable metamorphic case or reasoned not-applicable basis, and
   add further axes when evidence warrants. Connector discovery remains a
   candidate-generating heuristic, and project intent remains in project-owned
   contracts. LINT-083 keeps optional peer-comparison scopes source-matched and
   restores broad comparisons whenever a participating connector review is
   stale or incomplete.
2. Keep LINT-077's exact-version native lane in GitHub CI. The local KiCad
   10.0.0/10.0.5 exports now repeat with matching normalized netlist/ERC
   evidence; before a project adopts this check, its owner must source and
   review the exact contact limits and per-contact load. Keep copper-ampacity
   work deferred until its physical and current-allocation model has a reviewed
   basis.
   Keep LINT-087's serial reference-bond control and broken-bond fault in the
   exact KiCad 10.0.0/10.0.5 GitHub acceptance lane. The tagged
   `v0.5.0rc15` run (`37851810081`) passed both cases on both versions; retain
   that lane for future changes to the bond contract or native fixture.
3. Keep partial `LINT-010` through `LINT-012` aligned with their actual
   evidence boundaries. LINT-011 now checks the optional split midpoint
   capacitor map from a native schematic export as well as typed contract
   cases; physical bus-end placement and switchable or external termination
   remain outside the schematic contract. LINT-012 already tests
   controller-managed CC and an optional authored VBUS chain; debug-accessory
   behavior is unsupported, and the chain does not prove component conduction
   or PCB/contact continuity. Add coverage only when a reviewed requirement
   supplies a concrete deterministic check.
4. Keep LINT-024's eleven bounded geometry rules opt-in. The current inventory
   already covers the documented near-pin, junction, label, text, and symbol
   body classes with fault/control and native comparisons. The next LINT-024
   work is to measure false positives and reviewer effort on supported,
   non-proprietary examples; expand glyph or geometry support only when a
   concrete fault/control case demonstrates value. Use LINT-044's enabled-rule
   coverage and do not use incomplete text samples for false-positive-rate
   claims.
5. Measure review value for implemented default-REVIEW rules, beginning with
   LINT-086's USB split-reference prompt, then LINT-061/066 digital-peer
   voltage prompts and LINT-063 LED-output prompts. LINT-086 recognizes direct
   paths or one fitted `Device:R` per data line, same-net USB-C A/B contacts,
   and bounded two-pin D-designated shunts. Count only supported connector-to-IC
   pairs and record whether the review found missing, intentionally separate,
   or already bonded reference policy. The public CP2102, USB-C FUSB302/RP2040,
   and 16nx projects are common-reference non-finding screens. Synthetic split
   mutations demonstrate prompt behavior; these screens do not measure
   precision or reviewer effort.
   Use supported, nonconfidential examples and record useful findings, false
   positives, seeded misses, and reviewer effort; keep project defaults
   unchanged until that evidence is reviewed. Keep LINT-062 opt-in until
   project owners review exact sequence maps; keep numeric timing checks
   deferred until source-backed requirements and boundary fixtures exist.
   LINT-083 supplies a configurable connector comparison boundary, but does not
   count as a precision measurement for any default-REVIEW rule.
6. Run the controlled candidate trials in `LINT-031` against synthetic faults
   and valid alternatives. Record incremental findings, false positives,
   missed cases, localization effort, and maintenance cost before adopting a
   cohort implementation or adding the adapter contract in `LINT-032`. For new
   domain checks, LINT-075's no-CLI oscillator-output trial is recorded. Any
   first-party path contract still needs native netlist evidence and a
   project-authored requirement map before implementation. The additional
   domain-specific cohort families above remain conditional research items.
7. LINT-076 now covers mapped-check execution plus bounded applicability
   counts for LINT-066's direct-peer voltage heuristics, LINT-086's USB
   peer-reference heuristic, LINT-074's direct serial reference review, and
   the existing connector peer-pin comparisons. The connector coverage summary
   makes exact-symbol pin groups and open/different assignments visible even
   when the checker has no finding to emit.
   Continue it only when an audit identifies another enabled check that can
   silently skip without a matching coverage report or finding; do not add a
   global status registry that only restates the catalog.
   Add a new
   cohort-derived electrical check only after its applicability, deterministic
   predicate, fault/control fixtures, and incremental-value hypothesis are
   recorded. `LINT-033` through `LINT-067` have synthetic implementations or
   explicitly documented remaining limits. LINT-049's project-mapped
   connector-to-PHY topology comparison is implemented with integrated-PHY
   and external-resistor controls. Adoption of the cohort's generic
   resistor-presence prompt remains deferred because its trial flags both
  documented PHY classes; any future generic prompt needs part-specific
  applicability evidence and measurable value under LINT-031. LINT-064 is
  implemented and synthetically verified; project-level adoption still needs
   owner-reviewed exact-part rating and stress sources. LINT-066 is
   synthetically implemented and repeated-export validated on exact KiCad
   10.0.0/10.0.5 for SPI and UART/USART; non-proprietary reviewer-value
   measurements remain open.
   LINT-067 adds a default-review cross-peer CANH/CANL assignment prompt; native
   synthetic fault/control exports pass without ERC errors on the same pinned
   versions. The expected isolated-library warnings are documented. LINT-071
   adds a source-bound component power-rating comparison; synthetic contract,
   CLI/MCP, retained-evidence replay, and repeated native exports on KiCad
   10.0.0 and 10.0.5 pass. Project adoption still needs owner-reviewed exact-
   part rating and stress sources. LINT-072 adds serial-roster coverage; its
   omitted, partially mapped, and fully mapped synthetic native cases repeat
   on those same KiCad versions. Reviewer effort and false-positive rates
   remain open for both rules.

## Completion and release gate

A backlog item is complete only when its evidence adapter and exact version
boundary are documented, its fault and valid-control fixtures run in CI, its
limitations and false-positive cases are stated, and its report is reproducible
and source-bound. If it adds a CLI or MCP operation, the typed service,
surface map, parity test, package smoke suite, and installed-wheel test against
an external checkout are part of the change. Generated receipts remain under
ignored `build/` directories.

Passing these checks means the declared tooling conditions were met. It does
not establish electrical approval, manufacturing readiness, PCB fabrication
quality, or first-article continuity.

[thomson-kicad-review]: <https://github.com/holla2040/ThomsonLint/blob/main/docs/KiCad_Review_Guide.md>
[happy-crystal-detector]: https://github.com/aklofas/kicad-happy/blob/main/skills/kicad/scripts/signal_detectors.py#L818-L950
[happy-datasheets]: <https://github.com/aklofas/kicad-happy#-datasheets--sync-and-extract>
[happy-lb001]: https://github.com/aklofas/kicad-happy/blob/a6bba1add1e18b89e3aa0824b9769ed1d9d79174/skills/kicad/scripts/signal_detectors.py#L4367-L4440
[happy-changelog]: https://github.com/aklofas/kicad-happy/blob/main/CHANGELOG.md
[happy-uc-releases]: https://github.com/aklofas/kicad-happy/releases
[usb-c-spec-release]: https://www.usb.org/document-library/usb-type-cr-cable-and-connector-specification-release-25
[usb-cap-fixture-readme]: ../tests/fixtures/design_lint/usb-c-vbus-capacitance-native/README.md
[happy-pcb-analysis]: <https://github.com/aklofas/kicad-happy/blob/a6bba1add1e18b89e3aa0824b9769ed1d9d79174/skills/kicad/scripts/analyze_pcb.py>
[happy-pcb-layout]: <https://github.com/aklofas/kicad-happy/blob/main/skills/kicad/references/pcb-layout-analysis.md>
[happy-pcb-methodology]: https://github.com/aklofas/kicad-happy/blob/main/skills/kicad/scripts/methodology_pcb.md
[happy-cross-verify]: https://github.com/aklofas/kicad-happy/blob/main/release-notes.md
[kicad-skills-pcb]: <https://github.com/sabas0ba/kicad_skills/blob/main/docs/guides/kicad-pcb-review.md>

[calcumaker-revision]: https://github.com/calcumaker/calcumaker/commit/113a283
[calcumaker-design]: https://github.com/calcumaker/calcumaker/blob/113a283/DESIGN.md
[calcumaker-hardware]: https://github.com/calcumaker/calcumaker/tree/113a283/hardware
[calcumaker-license]: https://github.com/calcumaker/calcumaker/blob/113a283/hardware/LICENSE
[calcumaker-display-floorplan]: <https://github.com/calcumaker/calcumaker/blob/113a283/hardware/calcumaker-display/FLOORPLAN.md>
[calcumaker-wiring-review]: <https://github.com/calcumaker/calcumaker/blob/113a283/hardware/WIRING_REVIEW.md>
[antmicro-cm4]: https://github.com/antmicro/cm4-baseboard/tree/d248c2921e8e7f4c9b30c96ea5f376d9b2780f1e
[cynthion-hardware]: https://github.com/greatscottgadgets/cynthion-hardware/tree/13aa71c2fb0be3837cd2ec580ee5d2c25fc1c678
[cynthion-license]: https://github.com/greatscottgadgets/cynthion-hardware/blob/13aa71c2fb0be3837cd2ec580ee5d2c25fc1c678/LICENSE
[stickhub-schematic]: https://github.com/rbtsco/StickHub/blob/5f369a785bedc4b1d3b99222c841ac684e04f016/StickHub.kicad_sch
[stickhub-license]: https://github.com/rbtsco/StickHub/blob/5f369a785bedc4b1d3b99222c841ac684e04f016/LICENSE.md
