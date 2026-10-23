# Design lint and project review decisions

Design lint finds patterns that merit review in a source-bound KiCad netlist. It
cannot infer whether matching connector pins should share a net. The project
repository owns the pinout, electrical requirements, and decisions about each
finding. Tooling owns the rules and report format.

## Reconcile findings against a source-bound baseline

Use the [source-bound finding reconciliation guide](DESIGN_LINT_RECONCILIATION.md)
to compare current design-lint findings with a reviewed source baseline,
reconcile dispositions, and refresh evidence. It keeps heuristic candidates,
contract mismatches, coverage gaps, and native diagnostics distinct.

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

## Review direct MOSFET gate drive

`component.mosfet_gate_direct_drive` can flag a supported fitted MOSFET whose
gate shares one native net with another fitted output-capable pin. It defaults
to `off`: an external gate resistor is not always needed, and this schematic
pattern cannot show driver impedance, switching performance, or PCB continuity.
Enable `review` in the project's `design_lint.rules` only when the prompt is
useful for that project. The
[native fixture note](../tests/fixtures/design_lint/mosfet-gate-native/README.md)
documents the tooling-owned direct-drive and series-resistor cases.

## Review project-mapped stateful connector contacts

`connector.stateful_contact_topology_mismatch` checks a mechanical connector
contact only when the project supplies its exact identity and source-backed
contact map. Without the map, the tool does not infer switch contacts from
audio-jack names, symbol text, or pin numbers. For each mapped fitted part, it
checks the native symbol, value, footprint, PART_ID, and complete pin inventory.
Each mapped stateful pair must have two distinct, unambiguous schematic net
assignments; a single net permanently bypasses the physical contact.

Add an entry under `design_lint` in the project's `tests/contract.json` after
reviewing its exact part datasheet and symbol pin mapping:

```json
{
  "design_lint": {
    "connector_stateful_contact_map": {
      "schema_version": "1",
      "basis": "Reviewed synthetic audio-jack contact table, revision 1",
      "requirements": [
        {
          "id": "headphone-jack-contact-state",
          "reference": "J1",
          "expected_symbol": "Synthetic:AudioJack_2Contact",
          "expected_value": "Synthetic Audio Jack",
          "expected_footprint": "Synthetic:AudioJack_2Contact",
          "expected_part_id": "SYNTH-AUDIO-JACK-001",
          "native_pin_numbers": ["1", "2"],
          "contact_pairs": [
            {
              "id": "tip-normal-contact",
              "first_pin": "1",
              "second_pin": "2",
              "closed_when": "plug_removed",
              "source_basis": "Reviewed contact table, row 1"
            }
          ]
        }
      ]
    }
  }
}
```

With this map, tying J1.1 and J1.2 to one native net produces a review finding;
separate assigned nets are the valid control. A missing or ambiguous pin
assignment and a stale identity map are also review findings. The rule defaults
to `review` when mapped and supports project `block`, `off`, and exact-ignore
decisions. `off` findings remain visible with `RULE_OFF` disposition. Omit a
contact pair from the map when the project intentionally leaves it unused.
This schematic check does not prove the contact's mechanical behavior, PCB
copper continuity, or first-article continuity. The
[synthetic fault/control fixtures](../tests/fixtures/design_lint/stateful-connector-contacts/README.md)
show the bounded topology check.

## Review serial TX/RX pins on one net

`bus.serial_tx_rx_same_net` can find a fitted component whose uniquely assigned
native TX and RX pins for one recognized UART/USART channel share one
schematic net. The rule defaults to `off` because single-wire, half-duplex,
loopback, and other project-specific serial topologies can be intentional.
Enable `review` only when the prompt helps your project; an exact finding can
also be ignored with a reason.

The check skips DNP components, open or multiply assigned pins, ambiguous
multiple TX/RX functions, and differently indexed channels. It uses native
exported pin functions and net assignments. It cannot establish the intended
serial topology, physical continuity, external wiring, transceiver behavior,
or firmware configuration. Tooling-owned fault and full-duplex control
schematics are exported repeatedly on digest-pinned KiCad 10.0.0 and 10.0.5
images; see the
[fixture note](../tests/fixtures/design_lint/serial-tx-rx-same-net/README.md).

### Serial TX/RX pin and net-label direction review

`bus.serial_tx_rx_label_mismatch` compares fitted U/IC TX/TXD and RX/RXD
functions with explicit UART/USART labels on matching channel names. An
opposite role produces a configurable `review` finding; projects can promote
it to `block`, turn it `off`, or ignore one exact finding. Generic TX/RX
labels, cross-prefix or different-channel aliases, connectors, DNP parts, and
open, multiply assigned, or inventory-inconsistent pins remain unclassified.
Endpoint labels can use different naming conventions, so this finding asks
for review and does not establish the authoritative pin map or required
topology. The synthetic fault/control exports repeat with clean ERC on
digest-pinned KiCad 10.0.0 and 10.0.5 images; see the
[fixture note](../tests/fixtures/design_lint/serial-tx-rx-label-mismatch/README.md).

```sh
.venv/bin/python -I -m pytest tests/test_serial_tx_rx_label_mismatch.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.serial_tx_rx_label_mismatch")'

KICAD_RUN_NATIVE_SERIAL_TX_RX_LABEL_MISMATCH_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_serial_tx_rx_label_mismatch_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.serial_tx_rx_label_mismatch")'
```

`bus.serial_tx_outputs_share_net` adds a separate opt-in review when TX/TXD
functions on two fitted ICs share one net but native pin types do not already
show two output drivers for ERC to report. It skips incomplete or ambiguous
assignments and excludes connector pins. A single transmitter feeding several
receivers is a valid control. Shared tri-state, half-duplex, or other
project-specific nets can still be intentional, so this rule defaults to
`off`. It does not infer driver behavior or protocol requirements. Its
synthetic fault and one-to-two receiver control both pass native ERC without
errors on the digest-pinned KiCad 10.0.0 and 10.0.5 lanes; see the
[fixture note](../tests/fixtures/design_lint/serial-tx-output-sharing/README.md).

`bus.spi_chip_select_inputs_share_net` adds an opt-in review when input-typed
SPI chip-select pins on multiple fitted ICs share one assigned schematic net.
It uses bounded native function aliases, fitted state, pin inventory, unique
net assignments, and native pin types; a single controller output driving one
device stays quiet. Broadcast selection can be intentional, so the rule
defaults to `off`. It does not infer device behavior, SPI role, active polarity,
or required topology. Its synthetic shared-select fault and separate-select
control both pass native ERC without errors on the digest-pinned KiCad 10.0.0
and 10.0.5 lanes; see the
[fixture note](../tests/fixtures/design_lint/spi-shared-chip-select/README.md).

`bus.spi_data_outputs_share_net` adds a separate opt-in review when MISO/SDO/CIPO
function pins on multiple fitted ICs share one exact schematic net and native
types do not already show two output drivers for ERC to report. Native input
pins are receivers and do not count; ambiguous assignments and incomplete pin
inventories are skipped. Tri-state shared MISO buses can be intentional, so
the rule defaults to `off`. It does not infer bus membership, device role, or
select coordination. Its synthetic fault and one-device control pass native
ERC without errors on the digest-pinned KiCad 10.0.0 and 10.0.5 lanes; see the
[fixture note](../tests/fixtures/design_lint/spi-shared-data-outputs/README.md).

`bus.spi_clock_control_data_same_net` adds an opt-in review when a fitted
device's bounded SCK/SCLK or chip-select function pin shares one exact native
net with a MOSI/SDI/COPI or MISO/SDO/CIPO data pin on the same indexed SPI
channel. It requires each pin in the native component inventory with one
unambiguous net assignment. The rule skips DNP, connector, duplicate-role,
open, cross-channel, and inventory-inconsistent cases. Two explicit native
output types are left to ERC; missing type evidence stays `unknown`. A device
can intentionally multiplex these signals, so the rule defaults to `off` and
does not infer its configured mode or required topology. It covers clock or
select to data combinations; MOSI/MISO shorts remain with the more specific
`bus.spi_data_input_output_same_net` rule. The synthetic fault and separate-net
control pass native ERC without errors on KiCad 10.0.0 and 10.0.5; see the
[fixture note](../tests/fixtures/design_lint/spi-clock-control-same-net/README.md).

`bus.spi_clock_chip_select_same_net` separately reviews one fitted IC whose
bounded SCK/SCLK and chip-select function pins share one exact native net on
the same optional SPI channel. It requires both pins in the native component
inventory with one unambiguous net assignment. DNP, connector, duplicate-role,
open, cross-channel, and inventory-inconsistent cases are skipped; two
explicit native output types are left to ERC, while missing type evidence
remains `unknown`. The default is `off` because these function names cannot
establish device configuration and the signals may be intentionally
multiplexed. The source-hashed synthetic fault and separate-net control both
pass native ERC on KiCad 10.0.0 and 10.0.5; see the
[fixture note](../tests/fixtures/design_lint/spi-clock-control-same-net/README.md).

Select the SPI clock/chip-select check with:

```sh
.venv/bin/python -I -m pytest tests/test_spi_clock_chip_select_same_net.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.spi_clock_chip_select_same_net")'

KICAD_RUN_NATIVE_SPI_CLOCK_CONTROL_SAME_NET_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_spi_clock_control_same_net_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.spi_clock_chip_select_same_net")'
```

Select this rule's fast and exact-native checks with:

```sh
.venv/bin/python -I -m pytest tests/test_spi_clock_control_same_net.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.spi_clock_control_data_same_net")'

KICAD_RUN_NATIVE_SPI_CLOCK_CONTROL_SAME_NET_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_spi_clock_control_same_net_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.spi_clock_control_data_same_net")'
```

## Explore the rule catalog

List all packaged rules, their implementation theme and source owner, default
mode, predicate, supported evidence, and limitations without selecting a
project or native run:

```sh
kicad-team design-lint --catalog --format text
kicad-team design-lint --catalog --format json
```

The read-only MCP tool `list_design_lint_rules` returns the same typed catalog.
Use this view before adding project overrides; `review`, `block`, and `off`
are explicit project decisions, and the rule metadata states what each check
can and cannot establish.
The catalog currently contains 192 active rules.

### Review project-authored courtyard-to-edge DRC coverage

`pcb.mechanical_edge_clearance_rule_coverage` audits a project-owned
`pcb_mechanical_edge_clearance_map`. For each requirement, it checks that the
source-bound `.kicad_dru` has the named `physical_clearance` rule for the exact
front or back courtyard layer, the `Edge.Cuts` condition, the exact minimum,
and blocking severity. It also prompts when another native rule declares the
same exact scope. The rule is opt-in: projects that have no reviewed
courtyard-to-edge minimum do not receive a prompt.

```json
{
  "design_lint": {
    "pcb_mechanical_edge_clearance_map": {
      "schema_version": "1",
      "basis": "Reviewed enclosure drawing, revision 2",
      "requirements": [
        {
          "id": "front-connector-edge",
          "basis": "Connector body clearance on reviewed enclosure drawing",
          "courtyard_layer": "F.Courtyard",
          "rule_name": "front-connector-board-edge",
          "minimum_clearance_nm": 1500000
        }
      ]
    }
  }
}
```

The `.kicad_dru` rule must compare `B.Layer == 'Edge.Cuts'` with the exact
courtyard layer and minimum. This lint checks authored rule coverage; native
KiCad DRC measures board geometry. Neither check establishes enclosure fit,
manufacturing tolerance, or mechanical approval. For details, see
[LINT-209](DESIGN_LINT_BACKLOG.md#lint-209--courtyard-to-edge-drc-rule-coverage)
and the [fixture note](../tests/fixtures/design_lint/pcb-mechanical-edge-clearance/README.md).

### Distinct mapped connector supply domains sharing a net

`connector.mapped_supply_domains_share_net` prompts when complete,
source-matched project interface entries classify fitted connector contacts as
supplies in distinct `voltage_domain` groups and the native netlist assigns
them to one exact schematic net. It emits one `review` finding per shared net
with the affected pins, map classifications, and interface-catalog digest.

Treat this as a request to check the pinout and map. Distinct domain names do
not prove different voltages or incompatibility, and an intentional common node
is a valid control. Incomplete, stale, open, ambiguous, and DNP pin evidence is
excluded. The rule can be promoted, disabled, or ignored per project using the
normal `design_lint` policy.

Select the synthetic regression slice with:

```sh
python -I -m pytest tests/test_connector_supply_domain_net_sharing.py \
  -m 'design_lint and connector_lint and design_lint_rule(rule_id="connector.mapped_supply_domains_share_net")'
```

### Mapped connector return/supply scopes with isolated peers

`connector.return_supply_scope_singleton` reviews a source-matched generic
return or same-domain generic supply comparison scope when one connector
reference has no peer inside that scope. It reports that the scoped peer checks
cannot compare those contacts with the other mapped connectors. A singleton
scope can be intentional for a separate or isolated interface; the finding does
not require common nets or prove isolation. Stale or incomplete scope evidence
keeps the existing broad comparison and does not create this finding.

Select the synthetic regression slice with:

```sh
python -I -m pytest tests/test_connector_peer_comparison_scope_singleton.py \
  -m 'design_lint and connector_lint and design_lint_rule(rule_id="connector.return_supply_scope_singleton")'
```

### USB data pin/name polarity review

`bus.usb_data_polarity_label_mismatch` compares bounded native USB D+/D− pin
functions with an explicitly polarity-named assigned net. A same-port
contradiction produces a configurable `review` finding; projects can promote it
to `block`, turn it `off`, or ignore one exact finding. Neutral net names,
unrecognized aliases, differently indexed ports, DNP pins, and open or
ambiguous assignments remain unclassified. This clue does not prove connector
intent, device pinout, physical polarity, or PCB routing. Its focused checks are
selectable with:

```sh
python -I -m pytest tests/test_usb_data_polarity.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.usb_data_polarity_label_mismatch")'

KICAD_RUN_NATIVE_USB_DATA_POLARITY_FIXTURES=1 python -I -m pytest \
  tests/test_usb_data_polarity_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.usb_data_polarity_label_mismatch")'
```

### USB connector-to-PHY data-pair crossing review

`bus.usb_peer_data_pair_crossed` compares complete native USB 2.0 D+/D−
endpoint assignments between a fitted connector and fitted U/IC PHY. It reports
a configurable `review` finding when neutral-named connector D+ and PHY D−
share one direct net, and connector D− and PHY D+ share the other. It requires
unique role assignments and matching port-group identities, and only permits
bounded D-designated protection branches. Explicit USB-polarity labels remain
with the label-polarity rule; authored endpoint maps remain with the exact USB
path-contract check. This heuristic does not establish authoritative pinout,
physical routing, or device
behavior. Incomplete or ambiguous inventories, mismatched or partly indexed
port groups, DNP endpoints, series resistors, inline parts, and SuperSpeed
pairs remain outside its scope. Its focused checks are selectable with:

```sh
.venv/bin/python -I -m pytest tests/test_usb_peer_data_pair_crossing.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.usb_peer_data_pair_crossed")'
```

### CAN line pin/name polarity review

`bus.can_line_polarity_label_mismatch` compares bounded CANH/CANL pin
functions with explicitly CANH/CANL-named assigned nets. A contradiction
produces a configurable `review` finding; projects can promote it to `block`,
turn it `off`, or ignore one exact finding. Neutral, numbered, or unrecognized
names and DNP, open, or ambiguous pin assignments remain unclassified. This
review clue does not establish project pinout intent, bus membership, PCB
routing, or physical connectivity. Its focused checks are selectable with:

```sh
python -I -m pytest tests/test_can_line_polarity.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.can_line_polarity_label_mismatch")'

KICAD_RUN_NATIVE_CAN_LINE_POLARITY_FIXTURES=1 python -I -m pytest \
  tests/test_can_line_polarity_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.can_line_polarity_label_mismatch")'
```

### CAN TX/RX pin and net-label direction review

`bus.can_tx_rx_label_mismatch` compares explicit CAN/FDCAN TX/TXD and RX/RXD
pin functions with assigned net labels that name the opposite direction. It
requires a fitted U/IC reference, complete native pin inventory, and exactly
one net assignment for each examined pin. Generic UART names, connectors,
neutral labels, DNP parts, and incomplete assignments remain unclassified.
The finding is a review cue because projects may use different endpoint
naming conventions; the rule defaults off and supports project policy and
exact finding ignores. It does not establish the correct pin map, transceiver
behavior, PCB copper, or off-board wiring. Its focused checks are selectable
with:

```sh
.venv/bin/python -I -m pytest tests/test_can_tx_rx_label_mismatch.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.can_tx_rx_label_mismatch")'

KICAD_RUN_NATIVE_CAN_TX_RX_LABEL_MISMATCH_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_can_tx_rx_label_mismatch_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.can_tx_rx_label_mismatch")'
```

The [synthetic fixture record](../tests/fixtures/design_lint/can-tx-rx-label-mismatch/README.md)
contains the source hashes and native-lane boundaries.

### CAN controller TX/RX same-net review

`bus.can_tx_rx_same_net` reviews one fitted IC when its explicit CAN/FDCAN
transmit and receive function pins share the same exact net on the same
optional channel. It requires both pins in the native inventory with one
unambiguous assignment each. The rule skips generic UART `TXD`/`RXD` names,
connectors, DNP parts, duplicate roles, incomplete inventory, and open or
multiply assigned pins; two explicit native outputs remain with ERC, and
missing type data stays `unknown`. It defaults to `off` because loopback and
project-specific topologies can be intentional. The source-hashed synthetic
fault and separate-net control pass native ERC on KiCad 10.0.0 and 10.0.5.
See the [synthetic fixture record](../tests/fixtures/design_lint/can-tx-rx-same-net/README.md)
for source hashes and the fixture's limits.

Select the CAN TX/RX check with:

```sh
.venv/bin/python -I -m pytest tests/test_can_tx_rx_same_net.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.can_tx_rx_same_net")'

KICAD_RUN_NATIVE_CAN_TX_RX_SAME_NET_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_can_tx_rx_same_net_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.can_tx_rx_same_net")'
```

### Multiple CAN TX outputs sharing one net

`bus.can_tx_outputs_share_net` reviews a fitted group of two or more CAN/FDCAN
transmit-function pins on one exact net. It requires one unambiguous TX pin
per fitted U/IC reference, a complete native pin inventory, one net assignment,
and supported electrical types. Two explicit native outputs are left to ERC;
unknown pin types are skipped. Different channel numbers are grouped when the
net itself is shared. The default is `off` because shared transmit paths can be
intentional; the review does not infer device mode, driver behavior, or required
bus topology. The synthetic fault and one-TX-to-RX control have clean ERC on
KiCad 10.0.0 and 10.0.5. See the
[fixture record](../tests/fixtures/design_lint/can-tx-output-sharing/README.md)
for source hashes and fixture limits.

Select the CAN TX output-sharing check with:

```sh
.venv/bin/python -I -m pytest tests/test_can_tx_output_sharing.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.can_tx_outputs_share_net")'

KICAD_RUN_NATIVE_CAN_TX_OUTPUT_SHARING_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_can_tx_output_sharing_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.can_tx_outputs_share_net")'
```

### SPI data pin/name role review

`bus.spi_data_polarity_label_mismatch` compares supported MOSI/MISO pin
functions with unindexed `MOSI`, `MISO`, `SPI_MOSI`, and `SPI_MISO` net names.
A contradiction produces a configurable `review` finding; projects can
promote it to `block`, turn it `off`, or ignore one exact finding. Neutral,
indexed, and vendor-specific labels, DNP pins, and open or ambiguous
assignments remain unclassified. Endpoint naming can depend on part
convention, so this clue does not establish bus intent, routing, or physical
continuity. Its focused checks are selectable with:

```sh
python -I -m pytest tests/test_spi_data_label_polarity.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.spi_data_polarity_label_mismatch")'

KICAD_RUN_NATIVE_SPI_DATA_POLARITY_FIXTURES=1 python -I -m pytest \
  tests/test_spi_data_polarity_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.spi_data_polarity_label_mismatch")'
```

### SPI clock/select pin/name role review

`bus.spi_clock_select_label_mismatch` compares fitted SPI clock and chip-select
pin functions with bounded SPI clock/select net names. Opposite roles produce
a configurable `review` finding; projects can promote it to `block`, turn it
`off`, or ignore one exact finding. The rule requires each compared pin to
appear in the component pin inventory and have one native net assignment.
DNP, connector, open, multiply assigned, inventory-inconsistent, generic, and
vendor-specific cases remain unclassified. This naming clue does not establish
the device pin map, required topology, protocol behavior, PCB copper, or
off-board wiring. The synthetic crossed-label fault and matching control pass
native ERC on digest-pinned KiCad 10.0.0 and 10.0.5 images; see the
[fixture note](../tests/fixtures/design_lint/spi-clock-select-label-mismatch/README.md).

```sh
python -I -m pytest tests/test_spi_clock_select_label_mismatch.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.spi_clock_select_label_mismatch")'

KICAD_RUN_NATIVE_SPI_CLOCK_SELECT_LABEL_FIXTURES=1 python -I -m pytest \
  tests/test_spi_clock_select_label_mismatch_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.spi_clock_select_label_mismatch")'
```

### I2C signal pin/name role review

`bus.i2c_signal_label_role_mismatch` compares bounded SDA/SCL pin functions
with recognized SDA/SCL net names. Opposite roles produce a configurable
`review` finding; projects can promote it to `block`, turn it `off`, or ignore
one exact finding. Indexed or vendor-specific names, DNP pins, and open or
ambiguous assignments remain unclassified. This is a naming clue, not proof of
bus intent, routing, or physical continuity. Its focused checks are selectable
with:

```sh
python -I -m pytest tests/test_i2c_signal_label_roles.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.i2c_signal_label_role_mismatch")'

KICAD_RUN_NATIVE_I2C_SIGNAL_LABEL_FIXTURES=1 python -I -m pytest \
  tests/test_i2c_signal_label_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.i2c_signal_label_role_mismatch")'
```

### I2C SDA/SCL same-net review

`bus.i2c_sda_scl_same_net` prompts when one fitted U/IC has exactly one
recognized SDA pin and one recognized SCL pin, both present in its native pin
inventory and assigned to the same exact net. The rule defaults off because
pin-function names do not prove that a part implements standard I2C or that
its pins must be separate. If both pins are native `output` types, the rule
leaves the conflict to ERC. DNP, open, multiply assigned, multi-port, indexed,
vendor-specific, and inventory-inconsistent cases remain unclassified. A
project can enable review, promote the finding to `block`, turn it `off`, or
ignore one exact fingerprint. The schematic netlist does not prove PCB
continuity or external wiring.
Source hashes and fixture details are in the
[tooling-owned fixture README](../tests/fixtures/design_lint/i2c-sda-scl-same-net/README.md).

```sh
.venv/bin/python -I -m pytest tests/test_i2c_signal_same_net.py \
  -m 'design_lint and interface_lint and design_lint_rule(rule_id="bus.i2c_sda_scl_same_net")'

KICAD_RUN_NATIVE_I2C_SDA_SCL_SAME_NET_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_i2c_sda_scl_same_net_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.i2c_sda_scl_same_net")'
```

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
In the shipped catalog, `pcb.required_fitted_reference` is the only rule that
defaults to `block`; it compares a project-authored population requirement
against source-bound native evidence. Heuristic rules default to `review` or
`off`; a project may promote a reviewed heuristic to `block` under its own
policy.
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
connected and open controls. It also checks same-net front/back return planes
with matching pad/net assignments: the unstitched fault has separate copper
groups, and its paired control adds one plated through via. This synthetic
topology is based on the failure class in the public
[cohort copper-LVS issue](https://github.com/rjwalters/kicad-tools/issues/3787);
no source board or candidate code was copied. The lane also checks a connected copper plane and
same-net split planes, including a connected return plane with an additional filled island that has
no pad anchor. That index is review evidence; the tool does not infer that the island is
electrically isolated or defective. The lane checks a fitted net tie between two distinct return
nets and the same bond marked DNP. The net-tie controls retain the exact footprint, pad group,
population state, and the two separate native copper groups at its pads. KiCad reports the zone
identity for each pad, while pad connectivity groups show whether the returns actually share copper.
The synthetic same-net plane fault/control boards and their digests are listed in the
[plane-stitching fixture notes](../tests/fixtures/design_lint/pcb-return-plane-stitching/README.md).
The zone controls include SMD and plated through-hole pads on split planes; the probe preserves
polygon holes and maps each pad to the island indexes its copper shape touches. Two additional
controls declare separate return domains: one keeps both domains disconnected, and one adds a fitted
net tie that must make the isolation check fail. If KiCad says a pad connects to a zone but no
filled island intersects its effective copper shape, evidence capture fails instead of emitting an
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

For a reviewed direct USB SuperSpeed pair, add a `superspeed_interfaces`
entry to the same map. It names one complementary connector/PHY signal-family
pair, the exact positive and negative endpoint pins and nets, every return pin
on both endpoints, and the project-approved relationship. A full-duplex link
uses one entry for each direction. Example:

```json
{
  "superspeed_interfaces": [
    {
      "id": "usb-ss-tx-to-rx",
      "basis": "Reviewed connector and PHY pin tables, revisions 2 and C",
      "connector_reference": "J1",
      "expected_connector_symbol": "Connector:USB_A",
      "expected_connector_footprint": "Synthetic:USB-A",
      "phy_reference": "U1",
      "expected_phy_symbol": "Vendor:UsbPhy",
      "expected_phy_footprint": "Synthetic:QFN",
      "connector_signal_family": "USB SuperSpeed TX",
      "phy_signal_family": "USB SuperSpeed RX",
      "connector_positive_pin": "J1.1",
      "phy_positive_pin": "U1.1",
      "positive_net": "SS_TX_P",
      "connector_negative_pin": "J1.2",
      "phy_negative_pin": "U1.2",
      "negative_net": "SS_TX_N",
      "connector_reference_pins": [
        {"pin": "J1.3", "net": "USB_GND"}
      ],
      "phy_reference_pins": [
        {"pin": "U1.3", "net": "BOARD_GND"}
      ],
      "reference_policy": "separate_nets"
    }
  ]
}
```

`reference_policy` accepts `common_net`, `separate_nets`, or `bonded`. A
`bonded` entry also includes the exact two-pin component identity and both
side-pin net assignments, using the same `reference_bond` shape documented
below. A matching entry resolves only the named direct pair and reference-pin
decision. Stale identities, data pin/net assignments, reference inventories,
or a required bond produce `bus.usb_data_path_mismatch`; a split-reference
review remains visible when the policy map does not match. This schematic
comparison does not prove bond conduction, PCB copper continuity, external
grounding, lane routing, or signal integrity.

A reviewed path through one multi-pin component can use
`topology: "inline_component"` on both data lines and an `inline_component`
map on the interface. Name the exact component symbol and footprint, the four
component pins that carry connector-side and PHY-side D+/D−, and every native
component pin's expected net or explicit unconnected state. For example:

```json
{
  "inline_component": {
    "reference": "U2",
    "expected_symbol": "Synthetic:UsbProtection",
    "expected_footprint": "Synthetic:QFN",
    "positive_connector_pin": "U2.1",
    "positive_phy_pin": "U2.2",
    "negative_connector_pin": "U2.3",
    "negative_phy_pin": "U2.4",
    "pins": [
      {"pin": "U2.1", "disposition": "net", "net": "USB_DP_PORT"},
      {"pin": "U2.2", "disposition": "net", "net": "USB_DP_PHY"},
      {"pin": "U2.3", "disposition": "net", "net": "USB_DM_PORT"},
      {"pin": "U2.4", "disposition": "net", "net": "USB_DM_PHY"},
      {"pin": "U2.5", "disposition": "net", "net": "BOARD_GND"},
      {"pin": "U2.6", "disposition": "unconnected"}
    ]
  }
}
```

This is a project-authored netlist contract, not automatic recognition of
protection parts. The map must account for the complete symbol pin inventory;
the tooling compares every declared assignment with native netlist evidence.
It cannot establish that the selected symbol pins match the device datasheet,
that the component conducts or protects as intended, or that board copper
completes the route. Multiple inline devices and multi-hop paths remain outside
this contract.

A multi-pin part that shunts D+/D− while leaving the connector-to-PHY path
direct can be declared under `protection_shunts` instead of
`inline_component`:

```json
{
  "protection_shunts": [
    {
      "reference": "U6",
      "expected_symbol": "Synthetic:UsbProtectionArray",
      "expected_footprint": "Synthetic:DFN-6",
      "data_pins": [
        {"pin": "U6.1", "line": "D+", "net": "USB_DP"},
        {"pin": "U6.3", "line": "D-", "net": "USB_DM"}
      ],
      "pins": [
        {"pin": "U6.1", "disposition": "net", "net": "USB_DP"},
        {"pin": "U6.2", "disposition": "net", "net": "BOARD_GND"},
        {"pin": "U6.3", "disposition": "net", "net": "USB_DM"},
        {"pin": "U6.4", "disposition": "net", "net": "BOARD_GND"},
        {"pin": "U6.5", "disposition": "net", "net": "BOARD_GND"},
        {"pin": "U6.6", "disposition": "unconnected"}
      ]
    }
  ]
}
```

This map makes the multi-pin part eligible for the USB peer-reference review
only when its exact identity, full native pin inventory, every assignment, and
data-net membership match. A changed or incomplete map fails closed. It can
make a split-reference data path reviewable when no reference policy is
authored; adding common_net, separate_nets, or bonded requires the separately
reviewed endpoint reference-pin decision above. The lint does not decide that
the protection ground must join either endpoint, and the schematic map does not
prove the device's datasheet pinout, protection performance, or PCB copper
continuity. This initial mapping supports direct paths only and cannot be
combined with an inline-component path.

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

## Review a mapped oscillator-module output path

`oscillator.output_load_path_mismatch` checks only output paths named in the
project's `design_lint.oscillator_output_path_map`. The project records the
reviewed module identity and output pin, every fitted load pin, and whether the
required topology is direct or uses one series resistor. A series map also
records the exact resistor identity, pin sides, and inclusive nominal
resistance range.

```json
{
  "design_lint": {
    "oscillator_output_path_map": {
      "basis": "Reviewed synthetic clock-module output requirements",
      "paths": [
        {
          "id": "clock-to-receivers",
          "basis": "Synthetic module datasheet requirement, revision A",
          "oscillator_reference": "X1",
          "expected_oscillator_value": "Synthetic clock module",
          "expected_oscillator_symbol": "Synthetic:ClockModule",
          "expected_oscillator_footprint": "Synthetic:ClockModule_4",
          "output_pin": "X1.1",
          "topology": "series",
          "load_pins": [
            {
              "reference": "U2",
              "pin": "U2.2",
              "expected_symbol": "Synthetic:Receiver",
              "expected_footprint": "Synthetic:SOIC8"
            }
          ],
          "series_resistor": {
            "reference": "R1",
            "expected_symbol": "Device:R",
            "expected_footprint": "Synthetic:R_0603",
            "output_side_pin": "R1.1",
            "load_side_pin": "R1.2",
            "minimum_nominal_resistance_ohms": 22.0,
            "maximum_nominal_resistance_ohms": 47.0
          }
        }
      ]
    }
  }
}
```

Use `topology: "direct"` and omit `series_resistor` when that is the reviewed
requirement. Unmapped outputs are not guessed, and this rule never states that
every clock output needs a resistor. A mismatch creates a default-`REVIEW`
finding that project policy can set to `block`, `off`, or ignore by its exact
fingerprint. The comparison covers schematic netlist membership, fitted state,
mapped identities, and the authored nominal resistor range. For a series path,
it also reviews another recognized fitted two-terminal resistor across the same
output and load nets, including a zero-ohm bridge. It does not enumerate
non-resistor or multi-component parallel branches, resistor arrays, or hidden
electrical paths; nor does it check the PCB route, resistor tolerance, signal
integrity, waveform behavior, or whether the project-authored requirement is
electrically correct. Its test projects are synthetic; no product or
proprietary project is used. A focused, source-hashed native lane
also exports a 47R inclusive-boundary control and a 1 kOhm fault with
digest-pinned KiCad 10.0.0 and 10.0.5 images. It repeats both exports and
evaluates the native XML through the same typed rule service; its hosted result
is attached to the annotated lint tag. See the
[native fixture record](../tests/fixtures/design_lint/oscillator-output-native/README.md).

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
that setpoint coverage. The exact-version native fixture lane exports a valid
divider, an out-of-range upper-resistor value, and a split feedback node twice
on KiCad 10.0.0 and 10.0.5. It verifies the mapped pin functions and nets,
component identities and values, repeatability, and ERC error absence against
the explicit synthetic map, including the target rule's fault/control finding.
The simplified control schematic may still receive unrelated advisory
findings, so this gate does not require the aggregate design-lint report to be
PASS. The fixtures do not validate an actual regulator, datasheet, or analog
performance. See the native fixture README and its case table:
[README](../tests/fixtures/design_lint/regulator-feedback-native/README.md).

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

## Review an unassigned mapped shield contact

`connector.mapped_interface_shield_unassigned` uses the `shield` role from a
complete, source-matched connector interface map. If that fitted pin has no
schematic net and no `unconnected_pin_reasons` entry, the default result is a
`REVIEW` finding. It prompts the project reviewer to decide whether to add a
board bond or document that the shield is intentionally isolated.

Record an intentional open on the project-owned connector review:

```json
{
  "reference": "J1",
  "disposition": "interface",
  "basis": "Reviewed connector pinout and chassis strategy",
  "interface_id": "service-link",
  "pin_map": {"4": "4"},
  "unconnected_pin_reasons": {
    "4": "Shield intentionally isolated for this interface revision"
  }
}
```

The shield classification does not determine a bond point, require a common
signal return, prove PCB copper continuity, or establish external or chassis
grounding. Incomplete or stale maps and DNP connectors are excluded. Project
policy can set the rule to `block` or `off`, or ignore a finding by its exact
fingerprint. Synthetic fault/control tests and exact KiCad 10.0.0/10.0.5 native
fixtures verify that an unassigned mapped shield prompts and a connected or
reasoned-open shield stays quiet.

## Review an unassigned mapped supply or return contact

`connector.mapped_interface_power_contact_unassigned` fills the single-
connector gap for generic or unnamed native pins. When a complete, current
connector interface map assigns a fitted contact the role `supply` or `return`
and the native netlist leaves it open without a reasoned disposition, the
default result is a `REVIEW` finding. Named native functions stay with their
specific open-pin checks.

Record an intentional open on the project-owned connector review:

```json
{
  "reference": "J1",
  "disposition": "interface",
  "basis": "Reviewed connector pinout and interface operating modes",
  "interface_id": "serial-port",
  "pin_map": {"7": "7"},
  "unconnected_pin_reasons": {
    "7": "Return contact is intentionally unused in this isolated mode"
  }
}
```

The map tells the lint which contact role to review; it does not require that
the contact be connected, choose a target net, or require returns on similar
connectors to be common. The lint cannot establish PCB copper or off-board
continuity. Incomplete or stale maps and DNP connectors are excluded. Project
policy can set the rule to `block` or `off`, or ignore a finding by its exact
fingerprint. Synthetic supply/return faults and assigned/reasoned-open controls
are paired with exact KiCad 10.0.0/10.0.5 native exports of tooling-owned
connector schematics.

Run its focused slice with:

```sh
.venv/bin/python -I -m pytest tests/test_connector_mapped_interface_power_contact_unassigned.py \
  -m 'design_lint and connector_lint and interface_lint and design_lint_rule(rule_id="connector.mapped_interface_power_contact_unassigned")'
```

## Review an open mapped connector contact with role `other`

`connector.mapped_interface_other_unassigned` prompts when a complete,
source-matched interface map classifies a fitted generic or unnamed connector
contact as `other`, but the native netlist leaves it open without an
`unconnected_pin_reasons` entry. This asks the reviewer to confirm the
classification or document an intentional open; `other` does not prove that
the contact is electrical or that it needs a connection. Connected contacts,
DNP connectors, named native functions, stale or incomplete maps, and contacts
with a reasoned-open disposition are controls.

Record an intentional open in the project-owned connector review:

```json
{
  "reference": "J1",
  "disposition": "interface",
  "basis": "Reviewed connector pinout and interface operating modes",
  "interface_id": "service-link",
  "pin_map": {"8": "8"},
  "unconnected_pin_reasons": {
    "8": "Reviewed as intentionally unused in this interface revision"
  }
}
```

The lint does not infer the contact's electrical function, choose a target
net, or establish PCB copper continuity or off-board wiring. Project policy
can set the rule to `block` or `off`, or ignore a finding by its exact
fingerprint. Synthetic fault/control tests are paired with exact KiCad
10.0.0/10.0.5 native exports of tooling-owned connector schematics.

Run its focused slice with:

```sh
.venv/bin/python -I -m pytest tests/test_connector_mapped_interface_other_unassigned.py \
  -m 'design_lint and connector_lint and interface_lint and design_lint_rule(rule_id="connector.mapped_interface_other_unassigned")'
```

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
probe observations. Schema 11 adds rule-area evidence; schema 12 adds source-
bound footprint identity, fitted state, board origin, canonical orientation,
and board side; schema 13 adds native footprint value fields. Schema 14 adds
exact touch-pad-to-filled-copper clearance observations and the digest of the
explicit requests supplied to the native probe. Current source-bound KiCad 10
geometry captures use schema 14. These additions retain the earlier aperture
and zone-contour evidence.
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

## Review mapped capacitive touch-pad clearance

Use `design_lint.pcb_touch_pad_clearance_map` only when an independent
controller or layout requirement identifies the exact touch pad, its expected
schematic net, a reference copper net, the copper layer, and a positive
minimum clearance. The following example is synthetic and its distance is not
a recommended design value:

```json
{
  "design_lint": {
    "pcb_touch_pad_clearance_map": {
      "schema_version": "1",
      "basis": "Synthetic controller layout requirement, revision 1",
      "requirements": [
        {
          "id": "synthetic-touch-pad-gap",
          "pad": "J1.1",
          "expected_pad_net": "TOUCH_A",
          "reference_net": "GND",
          "layer": "F.Cu",
          "minimum_clearance_nm": 1500000
        }
      ]
    }
  }
}
```

The check verifies the schematic and native PCB pad assignments against the
authored net, then measures the exact effective pad shape to matching filled
zones on the authored net and layer. It uses the nearest such zone. A complete
measurement below the authored minimum, or any missing or inconsistent
evidence, produces a review candidate. The default is `review`; project
policy can select `block` or `off`, and exact fingerprint ignores remain
available.

The native measurement is carried by source-bound PCB snapshot schema 14.
The snapshot records the exact pad, requested nets and layer, matching-zone
count, closest zone UUID, measured integer-nanometer distance, and a digest of
the canonical probe request set. The request set is generated from the
project map, so editing its requirement invalidates prior evidence.

The synthetic round- and oval-pad regression is documented in its
[fixture README](../tests/fixtures/design_lint/pcb-touch-pad-clearance/README.md).

This check does not infer touch-pad identity from reference/value text, decide
that connector grounds or other nets should be joined, or establish a required
ground bond. It checks only the mapped geometric relationship. It does not
validate controller sensitivity, sensing performance, native DRC settings,
fabricated copper, or physical assembly; use the independently reviewed
requirement and native design review for those decisions.

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
antipad and its native track-endpoint contact, on pinned KiCad versions. A
second native fault/control pair places a 0.2 mm void between the 2 mm-spaced
samples used by a cohort analyzer; the first-party exact centerline geometry
must review the fault while keeping the intact control quiet. This fixture
tests geometric coverage only and does not imply a universal threshold.

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
does not count as active. It also reads each matching rule's optional
`(severity ...)` clause: an explicit `(severity ignore)` does not count as
coverage, while an unrecognized or repeated severity clause remains
unsupported. Supported lengths are `mm` and `mil`; supported net suffixes are
`_P`/`_N` and `+`/`-`. Missing rules, changed limits, duplicate matches,
ignored checks, unsupported syntax or units, and unrecognized pair names
remain incomplete review findings. A missing `.kicad_dru` file is reported as
missing coverage.

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

## Verify that custom PCB rules load in native DRC

During exact-version native validation, a PCB project that contains a
`.kicad_dru` file receives an additional `drc_rule_compilation` check. The
tooling copies the rule file and optional `.kicad_pro` settings into a temporary
directory, appends a uniquely named terminal clearance rule that must flag the
synthetic board's track pair, then runs KiCad DRC using the project's pinned
image. The retained receipt records source hashes, the observed KiCad version,
the sentinel violation count, and the native report; the temporary source
copies are removed after the command. This adapts the terminal-rule probe idea
from [kicad-druid](https://github.com/Cimos/kicad-druid) without importing its
implementation or project data.

The check fails if the exact native version cannot be confirmed or the final
sentinel is not reported. This catches malformed custom-rule files that stop
DRC from running. KiCad documents that custom-rule syntax errors prevent DRC
from running and recommends checking rule syntax in the editor; the automated
probe supplies a source-bound native execution check for the same failure
class ([KiCad 10 PCB Editor documentation](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html)).

This is a compilation/load check, not a semantic audit of every project rule.
A syntactically valid condition or layer typo can load while failing to match
the intended board objects; the terminal sentinel still passes in that case.
Use the mapped DRC-coverage checks for independently authored limits and the
normal board DRC run for board geometry. Neither result establishes electrical
approval or fabrication readiness. The tooling-owned synthetic control and
fault, plus the exact-version native lane, are documented in
[`tests/fixtures/design_lint/pcb-dru-rule-compilation/`](../tests/fixtures/design_lint/pcb-dru-rule-compilation/README.md).

## Review explicitly ignored custom PCB rules

`pcb.custom_drc_rule_ignored` prompts for review when a PCB project's
source-bound `.kicad_dru` contains a named top-level rule with an explicit
`(severity ignore)` clause. The finding identifies the rule file, SHA-256,
declaration ordinal and name, and the project's exact configured KiCad version.
Its default mode is `review`; a project may use the usual `block`, `off`, or
exact-fingerprint ignore policy.

This is an intent check. Some rules are intentionally ignored, so the finding
does not claim the board is defective or that the rule should be enabled. It
does not inspect global `.kicad_pro` ignored checks, evaluate custom-rule
conditions or limits, or create requirements for other rules. Mapped DRC rule
coverage and the native compilation probe remain separate checks. The
tooling-owned parser inputs are documented in
[`tests/fixtures/design_lint/pcb-dru-ignored-rules/`](../tests/fixtures/design_lint/pcb-dru-ignored-rules/README.md).

## Review custom PCB rules that assign exclusion severity

`pcb.custom_drc_rule_excluded` prompts when a PCB project's source-bound
`.kicad_dru` contains a named top-level rule with an explicit
`(severity exclusion)` clause. The finding identifies the rule file, SHA-256,
declaration ordinal and name, the exclusion severity, and the project's exact
configured KiCad version. Its default mode is `review`; projects may choose
`block`, `off`, or an exact-fingerprint ignore.

KiCad treats `exclusion` as a distinct severity from `ignore`: excluded
violations remain available in the DRC results when the matching filter is
selected. The finding therefore asks whether excluding violations matching
that rule is intentional. It does not claim a matching violation exists, that
the rule is too broad, or that it should use another severity. The check does
not evaluate conditions, limits, board geometry, or DRC output. See the
[KiCad 10 PCB Editor DRC documentation](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html)
and the tooling-owned synthetic fixtures in
[`tests/fixtures/design_lint/pcb-dru-severity-exclusions/`](../tests/fixtures/design_lint/pcb-dru-severity-exclusions/README.md).

## Review suppressed core native PCB DRC checks

`pcb.core_drc_check_ignored` prompts when a KiCad 10.x PCB project's
source-hashed `.kicad_pro` sets one of five core checks to `ignore`:
`unconnected_items`, `shorting_items`, `tracks_crossing`, `clearance`, or
`copper_edge_clearance`. KiCad stores these settings under
`board.design_settings.rule_severities`; the exact project-configured patch
version is recorded in the finding. The supported checks have Error defaults
in the [KiCad 10 DRC reference][kicad-10-drc].

The finding asks an engineer to confirm the suppression. It does not claim the
board is defective or that every project must enable every check. The rule
leaves KiCad's documented default-ignore footprint and presentation checks
quiet, and it does not inspect per-violation exclusions, Warning settings,
custom rules, or PCB geometry. The separate `pcb.drc_exclusion_present` rule
reviews saved per-violation exclusions. Projects can use the usual `review`, `block`,
`off`, or exact-fingerprint ignore policy. Tooling-owned fault and control
settings are in
[`tests/fixtures/design_lint/pcb-core-drc-disabled/`](../tests/fixtures/design_lint/pcb-core-drc-disabled/README.md).

[kicad-10-drc]: https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html#drc-configuration

## Review Error-default core DRC checks downgraded to Warning

`pcb.core_drc_check_warning` prompts when a KiCad 10.x PCB project's
source-hashed `.kicad_pro` sets one of five Error-default core DRC checks to
`warning`: `unconnected_items`, `shorting_items`, `tracks_crossing`,
`clearance`, or `copper_edge_clearance`. The finding records the exact settings
file hash, check ID, configured severity, and project KiCad version. Its
default mode is `review`; projects may use `block`, `off`, or exact-fingerprint
ignore.

Warning findings remain visible in DRC. The prompt asks whether lowering the
severity of an Error-default check was intentional; it does not claim the
board is defective or that Warning is unacceptable for every project. Other
core DRC checks and custom-rule severities remain outside this bounded rule.
KiCad's [DRC reference](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html)
lists the covered checks and their Error defaults. The source-bound synthetic
fixtures are documented in
[`tests/fixtures/design_lint/pcb-core-drc-warning/`](../tests/fixtures/design_lint/pcb-core-drc-warning/README.md).

## Review documented DFM Error-default DRC checks downgraded to Warning

`pcb.dfm_drc_check_warning` prompts when a KiCad 10.0.x PCB project's
source-hashed `.kicad_pro` sets one of thirteen documented Error-default DFM
checks to `warning`: `hole_clearance`, `hole_to_hole`, `track_width`,
`track_angle`, `track_segment_length`, `annular_width`, `drill_out_of_range`,
`microvia_drill_out_of_range`, `courtyards_overlap`, `malformed_courtyard`,
`invalid_outline`, `solder_mask_bridge`, or `track_on_post_machined_layer`.
The finding records the settings hash, check ID, configured severity, and exact
project KiCad version. Its default mode is `review`; projects may use `block`,
`off`, or exact-fingerprint ignore.

The warning remains visible in DRC. This prompt asks whether lowering the
documented default severity was intentional; it does not claim a violation
exists or that a project must retain KiCad's default. The core copper-edge
check is covered separately by `pcb.core_drc_check_warning`. KiCad's
[DRC reference](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html) lists the
DFM defaults; tooling-owned synthetic settings are in
[`tests/fixtures/design_lint/pcb-dfm-drc-warning/`](../tests/fixtures/design_lint/pcb-dfm-drc-warning/README.md).

## Review documented DFM Error-default DRC checks set to Ignore

`pcb.dfm_drc_check_ignored` prompts when a KiCad 10.0.x PCB project's
source-hashed `.kicad_pro` sets one of the same thirteen documented
Error-default DFM checks to `ignore`. KiCad disables the selected check at this
severity. The finding records the settings hash, check ID, configured
severity, and exact project KiCad version. Its default mode is `review`; a
project can choose `block`, `off`, or exact-fingerprint ignore.

The prompt asks whether suppressing the check was intentional; it does not
claim a violation exists or require every check to remain enabled. It reads
project settings and does not run DRC or determine whether a check applies to a
particular board. KiCad's [DRC reference](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html)
describes Ignore behavior. Tooling-owned synthetic settings are in
[`tests/fixtures/design_lint/pcb-dfm-drc-ignored/`](../tests/fixtures/design_lint/pcb-dfm-drc-ignored/README.md).

## Review downgraded signal-integrity DRC checks

`pcb.signal_integrity_drc_check_downgraded` prompts when a KiCad 10.0.x PCB
project's source-hashed `.kicad_pro` sets one of five Error-default
signal-integrity checks to `warning` or `ignore`: `length_out_of_range`,
`skew_out_of_range`, `too_many_vias`, `diff_pair_gap_out_of_range`, or
`diff_pair_uncoupled_length_too_long`. The finding records the exact project
version, settings hash, check ID, and configured severity. The rule defaults
to `review`; project policy may set `block`, `off`, or an exact-fingerprint
ignore.

KiCad documents these checks and their Error defaults in the
[KiCad 10 DRC reference][kicad-10-drc]. Ignore disables the selected check.
The exact settings keys are confirmed against the versioned
[KiCad 10.0.0](https://gitlab.com/kicad/code/kicad/-/blob/10.0.0/pcbnew/drc/drc_item.cpp)
and [10.0.5](https://gitlab.com/kicad/code/kicad/-/blob/10.0.5/pcbnew/drc/drc_item.cpp)
sources. In particular, KiCad 10 uses the key `too_many_vias` for its via-count
check. The prompt does not determine whether matching custom constraints are
present or applicable, measure a route, or qualify signal integrity. Existing
project-authored differential-pair and signal-path coverage checks remain
separate. Synthetic settings are in
[`tests/fixtures/design_lint/pcb-signal-integrity-drc-severity/`](../tests/fixtures/design_lint/pcb-signal-integrity-drc-severity/README.md).

## Review downgraded electrical DRC checks

`pcb.electrical_drc_check_downgraded` prompts when a KiCad 10.0.x PCB
project's source-hashed `.kicad_pro` sets `creepage` or `starved_thermal` to
`warning` or `ignore`, despite their documented Error defaults. The finding
records the exact project version, settings hash, check ID, and configured
severity. The rule defaults to `review`; project policy may set `block`, `off`,
or an exact-fingerprint ignore.

The prompt asks whether the explicit severity change was intentional. It does
not prove that a creepage constraint applies, that a pad uses thermal relief,
or that a violation exists. It does not run DRC, inspect board copper, or
establish electrical or manufacturing approval. Tooling-owned synthetic
settings are in
[`tests/fixtures/design_lint/pcb-electrical-drc-severity/`](../tests/fixtures/design_lint/pcb-electrical-drc-severity/README.md).

The [KiCad 10 DRC reference](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html#drc-configuration)
documents both checks with Error defaults. The
versioned [10.0.0 DRC item source][electrical-drc-items-100] and
[10.0.5 DRC item source][electrical-drc-items-105] confirm the serialized
keys. Their corresponding [10.0.0 settings source][electrical-drc-settings-100]
and [10.0.5 settings source][electrical-drc-settings-105] initialize all DRC
severities to Error before applying explicit default exceptions.

## Review lowered miscellaneous DRC checks

`pcb.miscellaneous_drc_check_downgraded` prompts when a KiCad 10.0.x PCB
project's source-hashed `.kicad_pro` sets one of nine Error-default
miscellaneous checks to `warning` or `ignore`: `footprint`,
`item_on_disabled_layer`, `items_not_allowed`, `npth_inside_courtyard`,
`pth_inside_courtyard`, `text_on_edge_cuts`, `through_hole_pad_without_hole`,
`unresolved_variable`, or `zones_intersect`. It records the exact project
version, settings hash, check ID, and severity, and defaults to `review`.

The KiCad 10 [DRC reference][kicad-10-drc] documents eight of these checks and
their Error defaults. Versioned [10.0.0][misc-drc-items-100] and
[10.0.5][misc-drc-items-105] DRC item sources list all nine editable keys,
including `text_on_edge_cuts`, which the manual omits from its table. Their
[10.0.0][misc-drc-settings-100] and [10.0.5][misc-drc-settings-105] settings
sources initialize DRC severities to Error before applying explicit
exceptions. The prompt asks whether lowering the severity was intentional. It
does not claim a violation exists, determine whether the check applies, run
DRC, inspect board geometry, or establish electrical or manufacturing
approval. Tooling-owned settings fixtures are in
[`tests/fixtures/design_lint/pcb-miscellaneous-drc-severity/`](../tests/fixtures/design_lint/pcb-miscellaneous-drc-severity/README.md).

## Review persisted per-violation PCB DRC exclusions

`pcb.drc_exclusion_present` prompts when a KiCad 10.0.x PCB project's
source-hashed `.kicad_pro` contains an individual saved DRC exclusion. The
finding includes the serialized marker, a stable marker hash, any saved comment,
and the exact project-configured KiCad patch version. The check reads the
`board.design_settings.drc_exclusions` list and accepts the KiCad 10.0 schema 2
string or marker/comment-pair forms.

The prompt asks an engineer to confirm that the exception is still intentional.
It does not assert that the excluded violation still exists or that the
exception is wrong. KiCad hides excluded violations unless the Exclusions view
is enabled; an absent comment is identified in the prompt. This check does not
run DRC, resolve the marker against current board objects, or inspect copper
geometry. Project policy can select `review`, `block`, `off`, or an
exact-fingerprint ignore. Tooling-owned synthetic settings are in
[`tests/fixtures/design_lint/pcb-drc-exclusions/`](../tests/fixtures/design_lint/pcb-drc-exclusions/README.md).

KiCad documents individual exclusions and their optional comments in the
[PCB Editor DRC reference][kicad-10-drc-exclusions]. Its tagged 10.0.7 source
stores marker/comment records under the project settings path
[`board.design_settings.drc_exclusions`][kicad-10-project-drc-exclusions].

[kicad-10-drc-exclusions]: https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html#design-rule-checking
[kicad-10-project-drc-exclusions]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.7/pcbnew/board_design_settings.cpp

## Review mapped PCB signal-path length and bundle skew

Use `design_lint.pcb_signal_path_rule_map` when a reviewed interface or timing
requirement defines exact PCB endpoint pads and a route-length or bundle-skew
limit. The values below are synthetic examples only:

```json
{
  "design_lint": {
    "pcb_signal_path_rule_map": {
      "schema_version": "1",
      "basis": "Reviewed synthetic serial-interface timing requirement",
      "paths": [
        {
          "id": "clock",
          "basis": "Synthetic clock path",
          "net": "SYNTH_CLK",
          "from_pad": "J1.1",
          "to_pad": "U1.1",
          "length": {"max_nm": 20000000}
        },
        {
          "id": "data",
          "basis": "Synthetic data path",
          "net": "SYNTH_DATA",
          "from_pad": "J1.2",
          "to_pad": "U1.2",
          "length": {"max_nm": 20000000}
        }
      ],
      "bundles": [
        {
          "id": "serial-bundle",
          "basis": "Synthetic inter-signal skew requirement",
          "path_ids": ["clock", "data"],
          "from_pad_pattern": "J1-*",
          "to_pad_pattern": "U1-*",
          "max_skew": {"max_nm": 100000}
        }
      ]
    },
    "rules": [
      {
        "rule_id": "pcb.signal_path_rule_coverage",
        "mode": "review",
        "reason": "Review native route rules against approved interface limits"
      }
    ]
  }
}
```

The audit requires every exact endpoint to appear on the mapped net in both the
source-bound schematic netlist and native PCB inventory. Endpoint pads must be
fitted, assigned to that net, and present in the same native copper component.
For a bundle, each KiCad `fromTo()` wildcard must resolve to exactly the mapped
endpoint set; an additional matching board pad makes coverage incomplete. The
project's `.kicad_dru` must contain exactly one matching `A.fromTo()` rule with
the authored integer-nanometer length or skew bounds. Ignored native DRC
severities and a matching custom rule with `(severity ignore)` do not count as
coverage. Absent or duplicate rules, changed bounds, unsupported syntax, stale
endpoints, and disconnected pads remain review findings.

The report binds the project and board, optional rule file, native DRC receipt,
native PCB snapshot and command, KiCad version, and source inventory. Projects
can select `review`, `block`, `off`, or an exact fingerprint ignore. Missing
maps stay `NOT_REQUESTED`; net-name patterns do not create endpoint or timing
requirements. KiCad native DRC measures actual route length and skew. This
audit checks that the reviewed requirements are represented by active native
rules and that mapped endpoints agree with source and copper evidence; it does
not establish that a chosen limit is electrically appropriate, nor prove
off-board wiring or physical continuity.

## Review schematic and PCB component-inventory differences

`pcb.schematic_component_inventory` compares fitted, footprint-assigned
schematic components with the source-bound native PCB footprint inventory. It
prompts when a reference has no board placement, or when the exact assigned
footprint identity differs from the placed footprint identity. Component
references are compared case-insensitively; footprint identities are compared
exactly. DNP and empty-footprint schematic components are controls, and
board-only mechanical footprints are outside this check.

The rule defaults to `review`. A project can select `block`, `off`, or suppress
an exact finding through the existing fingerprint-ignore lifecycle. An
assigned footprint does not prove the part belongs on the board, and different
footprint IDs do not prove that the land patterns differ. Prompts ask the
reviewer to confirm whether a component is intentionally off-board or whether
the placed footprint is an approved alternate. Each finding binds the native
netlist digest, board digest, native footprint snapshot digest and schema,
KiCad version, image, and probe. Missing, stale, or unsupported evidence is
reported as a coverage gap, not as a clean comparison.

This is a placement and exact-name consistency screen. It does not compare
CAD values, DNP agreement, board-only parts, pad geometry, assembly state, or
electrical connectivity. Schematic/PCB value text has a separate review rule
described below. A matching footprint ID does not prove the fabricated board
matches the source.

## Review PCB footprints with no schematic reference

`pcb.board_only_footprint` compares every nonempty native PCB footprint
reference with references in the source-bound schematic netlist, ignoring case.
It prompts when a PCB reference has no schematic counterpart. This can surface
an accidental extra connector or component, while also prompting on intentional
mechanical, fiducial, fabrication, logo, or other board-only footprints.

The rule defaults to `off` because boards commonly contain intentional extras.
Projects can opt in with `review` or `block`, then suppress a reviewed exact
reference through the fingerprint-ignore lifecycle. The comparison uses the
native footprint inventory snapshot schema 12, 13, or 14 and binds each finding to
the netlist, board, snapshot, KiCad version, image, and probe digests. Missing,
stale, or unsupported evidence blocks coverage when the rule is enabled.

This is a reference-identity heuristic. It cannot determine the item's
electrical role, assembly state, or manufacturing intent. A project may decide
that one unmatched reference is an error and another is intentional; the
checker only supplies the review prompt.

## Require selected base-assembly references to be fitted

`pcb.required_fitted_reference` checks a project-authored list of exact
references that must be fitted in the base assembly. The map is a requirement;
component similarity, a repeated design pattern, or a matching DNP state does
not create one.

```json
{
  "design_lint": {
    "pcb_required_fitted_reference_map": {
      "schema_version": "1",
      "basis": "Reviewed base-assembly requirements",
      "requirements": [
        {
          "reference": "U1",
          "footprint": "Package_QFP:TQFP-48",
          "basis": "Required interface controller"
        }
      ]
    }
  }
}
```

For every listed reference, the checker requires a non-DNP source schematic
component and a non-DNP native PCB footprint with the exact footprint ID. A
map entry may also require exact symbol and PART_ID identity. This catches a
required part omitted from both sources or marked DNP in both, while the
schematic-to-PCB DNP consistency check correctly sees no disagreement.

A configured map activates the rule in `block` mode by default. A project can
select `review` or `off` with the normal rule override; an explicitly enabled
rule without a map blocks coverage. Findings bind the canonical requirement
map, netlist, board, native snapshot, KiCad version, image, and probe. The rule
supports the base assembly only; it does not resolve named variants, validate
the requirement against an external BOM or approval record, or establish
physical population. Exact ignores follow the standard fingerprint lifecycle.

## Review schematic and PCB component-value differences

`pcb.schematic_pcb_value_mismatch` compares the schematic netlist value with
the native PCB footprint value for each case-insensitive reference that has a
schematic footprint assignment and is fitted in both sources. It trims
surrounding whitespace and then compares case-sensitive text exactly. A
difference is a review prompt, since a board may intentionally show a shorter
label or another approved value string.

This check defaults to `review`; project policy can select `block`, `off`, or
an exact fingerprint ignore. It requires source-bound footprint value fields
from PCB snapshot schema 13 or later. Schema 12 remains usable for footprint
placement, identity, and population checks, while value coverage stays blocked
until a schema 13-or-later capture is available. Findings bind the netlist,
board, snapshot,
KiCad version, image, and probe digests.

The comparison excludes DNP components, references missing from either file,
components without a schematic footprint assignment, population mismatches,
board-only footprints, and named variant values. It compares CAD text only; it
does not identify a part, establish electrical equivalence, or determine
assembly intent. The exact-version synthetic native lane exercises a matching
control and one stale-board-value fault on KiCad 10.0.0 and 10.0.5.

## Review mapped PCB keepout intent

Use `design_lint.pcb_keepout_map` when an independently reviewed requirement
identifies a named copper keepout whose exact shape, copper layers, and
restrictions must remain stable. The signature is SHA-256 over the canonical
native polygon outlines and holes in nanometers. The example is synthetic and
its digest is only a valid-format placeholder; do not copy it as a design
requirement.

```json
{
  "design_lint": {
    "pcb_keepout_map": {
      "schema_version": "1",
      "basis": "Synthetic approved module keepout drawing, revision 1",
      "requirements": [
        {
          "id": "synthetic-module-keepout",
          "basis": "Synthetic keepout drawing and layer note",
          "name": "ANTENNA_NO_COPPER",
          "geometry_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
          "layers": ["F.Cu", "B.Cu"],
          "forbids_tracks": true,
          "forbids_vias": true,
          "forbids_pads": true,
          "forbids_zone_fills": true,
          "forbids_footprints": false
        }
      ]
    },
    "rules": [
      {
        "rule_id": "pcb.keepout_intent_coverage",
        "mode": "review",
        "reason": "Review the native keepout against the approved source geometry"
      }
    ]
  }
}
```

The checker requires exactly one native rule area with the mapped name, exact
geometry digest, exact copper-layer set, and exact track, via, pad, zone-fill,
and footprint restrictions. A missing or duplicate name, changed geometry,
changed layer, changed restriction, or native snapshot older than schema 11 is
incomplete. Snapshot schema 12 and later retain that keepout evidence and add
source-bound footprint placement identity, origin, orientation, and board side.
Snapshot schema 13 adds the native footprint value; schema 14 retains that
evidence. The project
owner must author the digest, layers, flags, and basis
from an independent approved source; do not generate the requirement by
accepting whatever shape happens to be on the board.

The default is `review`; project policy can choose `block`, `off`, or an exact
fingerprint ignore. With no map, coverage is `NOT_REQUESTED`. This is a
regression check for the authored KiCad rule area only. It does not establish
that the chosen region is large enough or in the correct location for an
antenna, RF module, connector, or other engineering requirement, and it does
not prove fabricated copper or physical assembly matches the board source.

## Review mapped RF module antenna coverage

Use design_lint.pcb_rf_module_antenna_map when an independently reviewed
requirement identifies an RF module, its fitted disposition, feed pin/net, and
an onboard antenna keepout drawn in footprint-local coordinates. This check
binds the map to the exact schematic symbol, footprint, optional PART_ID,
native schematic net assignment, fitted/DNP state, and native PCB footprint
placement. For an onboard antenna it transforms each local outline and hole
through the observed placement position, orientation, and front/back side, then
compares the result with exactly one named native rule area. The synthetic
example below is not a design requirement.

```json
{
      "design_lint": {
        "pcb_rf_module_antenna_map": {
          "schema_version": "1",
          "basis": "Synthetic approved module drawing, revision 1",
          "requirements": [
            {
              "id": "radio-module",
              "basis": "Synthetic module pinout and antenna drawing",
              "reference": "U1",
              "expected_symbol": "RF_Module:Radio",
              "expected_footprint": "RF_Module:Radio_Module",
              "expected_part_id": "RADIO-1",
              "disposition": "onboard_antenna",
              "rf_feed_pad": "U1.1",
              "rf_feed_net": "RF_IN",
              "keepout": {
                "name": "radio-antenna-clearance",
                "local_polygons": [
                  {
                    "outline_nm": [
                      [0, 0],
                      [1000000, 0],
                      [1000000, 500000],
                      [0, 500000]
                    ],
                    "holes_nm": []
                  }
                ],
                "layers": ["F.Cu", "B.Cu"],
                "forbids_tracks": true,
                "forbids_vias": true,
                "forbids_pads": true,
                "forbids_zone_fills": true,
                "forbids_footprints": false
              }
            }
          ]
        },
        "rules": [
          {
            "rule_id": "pcb.rf_module_antenna_keepout_coverage",
            "mode": "review",
            "reason": "Review the mapped module and transformed antenna keepout"
          }
        ]
      }
}
```

Use the external_antenna disposition when the reviewed module uses an external
antenna: the feed pin/net remain required, and the onboard keepout is omitted.
Use dnp only when both schematic and PCB evidence identify the mapped module
as unpopulated; a DNP requirement cannot name a fitted feed or keepout. These
dispositions are explicit project decisions, not name-based guesses.

The map is opt-in and defaults to review; project policy can select block, off,
or an exact fingerprint ignore. An absent map is NOT_REQUESTED.
Placement-relative coverage requires source-bound native PCB snapshot schema
12, including explicit footprint identity, fitted state, origin, orientation,
and board side. Missing, duplicate, mismatched, or unsupported evidence remains
incomplete. The check verifies agreement with the authored requirement; it
cannot validate the vendor drawing interpretation, antenna performance,
fabricated copper, or physical assembly. Keep vendor documents and project
expectations in the project repository; the shared tooling retains only
synthetic fixtures.

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
Symbol-body geometry supports rectangles, polylines, Bezier curves, circles,
and non-degenerate three-point arcs. The arc bounds derive from its start,
midpoint, and endpoint; only cardinal extrema on the selected sweep enter the
envelope. Collinear or degenerate point triples leave body-dependent rules
partial.
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
single-unit, single-conversion symbols with rectangle, polyline, Bezier,
circle, or non-degenerate three-point arc graphics, plus orthogonal rotations
and x/y mirrors. It reports only after the centerline stays 0.2 mm inside the
envelope and overlaps it for at least 0.3 mm. Envelopes around disjoint,
curved, or non-rectangular graphics can include empty space, so intentional
crossings can be candidates. Text graphics, collinear or degenerate arcs,
multi-unit symbols, and other unsupported primitives leave this rule's
coverage partial when enabled. The finding identifies the symbol, wire,
source hash, sheet instance, body box, and clipped segment; it does not
establish pin connectivity or intent. The synthetic KiCad 10.0.6 fault and
clear control retain identical net assignments and ERC signatures, so this
rule adds a localized drawing review prompt rather than electrical detection.
The arc fault/control pair is also registered in the exact-version native
suite, which checks native SVG rendering and unchanged netlist/ERC evidence.
It is off by default, supports project review, block, off, and exact ignores,
and never changes the schematic.

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
        "expected_part_id": "SYNTHETIC-ARRAY-47K",
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
  "rise_time_basis": "Synthetic interface timing requirement",
  "maximum_per_resistor_tolerance_percent": 5.0,
  "resistor_tolerance_basis": "Synthetic worst-case datasheet tolerance for every pull-up element"
}
```

The authored `minimum_ohms` and `maximum_ohms` are checked against those
derived bounds. Equality passes. When both optional global tolerance fields
are present, the check applies the per-resistor bound to the nominal equivalent
range, then verifies that its worst-case minimum and maximum remain inside the
derived physical window. For more precise source coverage, use
`resistor_tolerances` instead of the global percentage and basis:

```json
"resistor_tolerances": [
  {
    "element_id": "R10",
    "maximum_tolerance_percent": 1.0,
    "basis": "Synthetic R10 manufacturer tolerance specification"
  },
  {
    "element_id": "RN1.sda",
    "maximum_tolerance_percent": 5.0,
    "basis": "Synthetic resistor-array SDA channel tolerance specification"
  }
]
```

Use a discrete resistor's exact reference or a mapped array channel ID formed
as `ARRAY_REFERENCE.CHANNEL_ID`. Scoped IDs must exactly match every mapped
pull-up element on that line; omitted or stale entries fail the scope check
and keep the `bus.i2c_missing_pullup` prompt open. The largest scoped
percentage is applied conservatively to the full nominal range. Global and
scoped tolerance modes cannot be combined. Omit both modes for the existing
nominal-only check. Neither mode verifies the cited datasheets or that their
contents support the authored bounds. Configured sink-current and rise-time
window checks must also pass before an authored requirement resolves the
heuristic prompt. The window values and source notes remain project inputs;
this is not a waveform simulation.

An optional `capacitance_scope` inventories fitted C-prefixed components and
components with recognized capacitor-symbol identities whose native pin
assignments connect directly to the bus line. A contributor with another
reference prefix can be counted either through that symbol-based discovery or
by an explicit map when its symbol identity is opaque. Each listed contributor
binds the exact symbol, footprint, optional `PART_ID`, two-pin inventory,
signal and return pins/nets, and nominal capacitance range. It also records a
reviewed maximum effective capacitance for that component, which can include
tolerance and DC-bias derating. A separate residual bound covers bus loading
not represented by those local schematic capacitors. The sum of contributor
maxima and residual must not exceed
`maximum_bus_capacitance_pf`:

```json
"capacitance_scope": {
  "inventory_basis": "Synthetic inventory of fitted capacitors on SDA",
  "maximum_residual_capacitance_pf": 25.0,
  "residual_capacitance_basis": "Synthetic pin, route, and endpoint load bound",
  "contributors": [
    {
      "reference": "C10",
      "expected_symbol": "Device:C",
      "expected_footprint": "Synthetic:0603",
      "expected_part_id": "SYNTHETIC-C10",
      "signal_pin": "C10.1",
      "return_pin": "C10.2",
      "return_net": "GND",
      "minimum_nominal_capacitance_pf": 8.0,
      "maximum_nominal_capacitance_pf": 12.0,
      "nominal_capacitance_basis": "Synthetic component value review",
      "maximum_effective_capacitance_pf": 10.0,
      "effective_capacitance_basis": "Synthetic tolerance and DC-bias bound"
    }
  ]
}
```

Every fitted C-prefixed device and recognized capacitor-symbol component
attached to the line must be mapped. A non-C reference with an opaque symbol is
not discovered automatically; explicitly map it as a contributor or account
for its loading in the residual bound. Stale, missing, DNP, identity, pin,
net, or nominal-range mismatches fail the scope.
The residual must account for endpoint pin loads, board parasitics, and any
off-board loading included in the requirement. Configured sink-current,
rise-time, tolerance, and capacitance checks must all pass before an authored
requirement resolves the heuristic prompt. These maps and source notes remain
project inputs: the tool does not validate cited documents, derive
capacitance from PCB copper, or simulate a waveform. The authored
`maximum_low_level_voltage_v` and `minimum_sink_current_ma` must describe the
same guaranteed operating point for the weakest applicable bus device.
The model does not verify resistor tolerance sources, nonlinear/active
pull-ups, buffers, off-board loading beyond the authored capacitance, or
device-to-device dynamic behavior. The optional tolerance bound does not
account for temperature drift or aging unless the project includes those in
its authored bound. NXP [UM10204 §7.1](https://www.nxp.com/docs/en/user-guide/UM10204.pdf)
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
value, channel pins, signal and rail nets, and nominal channel resistance. An
optional `expected_part_id` binds the map to the schematic's exact `PART_ID`
property; a mismatch or missing native `PART_ID` fails the array check. This
can catch a part substitution that keeps the same symbol, footprint, and value.
Every native array pin must appear in a channel map or have an explicit
`unmapped_pin_reasons` entry. The netlist can verify these identities and
assignments; it cannot establish the array's internal pin topology or channel
resistance. Those values must come from an independently reviewed datasheet
pin map. `expected_part_id` binds project identity but does not verify catalog
contents or cited datasheet claims. A direct pull-up to another recognized
positive rail also fails the check. DNP components do not satisfy a required
path or channel. The project contract must be reviewed independently; unless
an optional voltage map is provided, the rule does not determine rail voltage
or pin limits. It does not check bus capacitance, rise time, transient
behavior, sink-current margin, or suitability of an external/internal pull-up.

Set `i2c_pullups` to `{"mode":"not_applicable","reason":"..."}` when the
project has no board-local discrete pull-up requirement, including a reviewed
internal or off-board topology. Set it to `{"mode":"pending","reason":"..."}`
to keep the question visible and prevent the electrical lane from passing.
Older contracts without this section remain readable and make no I2C
pull-up-range claim. Direct paths, exact series paths, and mapped resistor
arrays are only evaluated when the contract declares them.

The deterministic I2C resistor-path checks also recognize an exact native
`Device:R` symbol under a non-R reference when KiCad exports the complete
two-pin inventory (`1` and `2`) and both pins have unique net assignments.
This covers library-identified generic resistors without guessing from a
component value or custom symbol name. Other resistor symbol IDs, custom
symbols, incomplete pin inventories, DNP parts, and ambiguous assignments are
not inferred; use an exact project-authored map when those parts are required.
See the [synthetic fixture README][i2c-device-r-fixture] for the source-bound
native checks and evidence boundary.

[i2c-device-r-fixture]: ../tests/fixtures/design_lint/i2c-device-r-symbol-native/README.md

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
pins, an explicit VBUS capacitance disposition, and whether exact protection
components are required, pending, or not applicable. The example's capacitance
range is synthetic and is not a USB-C default; each project must cite its own
approved source for an applicable limit. For example, a source port with
discrete Rp resistors can declare:

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
        "vbus_capacitance": {
          "mode": "required",
          "basis": "Synthetic reviewed port-side capacitance requirement",
          "minimum_nf": 4500,
          "maximum_nf": 5000,
          "capacitors": [
            {
              "reference": "C1",
              "symbol": "Device:C",
              "footprint": "Capacitor_SMD:C_0603_1608Metric",
              "pins": [
                {"pin": "C1.1", "net": "VBUS_PORT"},
                {"pin": "C1.2", "net": "GND"}
              ]
            }
          ]
        },
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
ranges, controller/protection identity, footprints, declared protection
pin nets, and the required nominal VBUS capacitance inventory with the current
source-bound native netlist. The capacitance check sums explicitly mapped
fitted capacitor nominal values, verifies each symbol, footprint, pin inventory
and pin-to-net assignment, and rejects additional fitted capacitor candidates
touching the port-side VBUS net. It compares the sum to the project's inclusive
minimum and maximum; the tooling supplies no universal threshold. A controller
mapping proves only the symbol/footprint identity and that its named pins map
to CC1 and CC2; it does not inspect firmware, straps, registers, or internal
Rp/Rd behavior. VBUS entries verify the named pins' net assignments separately on
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
capacitance disposition visible and prevent the electrical lane from passing.
Use `{"mode":"not_applicable","reason":"..."}` only when the project has
reviewed why this port has no applicable capacitance requirement. Each
configured USB-C port must state one of `required`, `pending`, or
`not_applicable`; there is no inferred value or default disposition. A
capacitance mismatch is a source-bound contract failure, not a USB compliance
verdict. The check does not account for capacitor tolerance, DC-bias derating,
temperature, frequency, transients, placement, PCB copper, or dynamic source
states. Older contracts without `usb_c` remain readable and make no USB-C role
claim.

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

## Review I2C and CAN peer reference domains

`bus.i2c_peer_reference_review` compares fitted ICs that expose one exact
shared native SDA/SCL net pair. `bus.can_peer_reference_review` compares fitted
ICs that expose one exact native CANH/CANL pair. Both are default-`review`
prompts when supported endpoints show explicit return pins on different native
nets. A return pin with native type `passive` or `power_in` is eligible; type
`unspecified` is eligible only when its pin function explicitly identifies a
return role such as `GND` or `VSS`. Shield, chassis, frame, and protective-earth
functions are excluded. These rules ask whether the difference is intentional;
they do not require common grounding, resolve isolated or translated buses, or
prove a physical return path. Projects can use the normal `review`, `block`, or
`off` policy and exact-fingerprint ignores. The I2C and CAN synthetic and
digest-pinned fixture suites are under
[`tests/test_i2c_peer_reference_review.py`](../tests/test_i2c_peer_reference_review.py),
[`tests/test_can_peer_reference_review.py`](../tests/test_can_peer_reference_review.py),
and their native fixture notes.

## Review SPI peer reference domains

`bus.spi_peer_reference_review` is a default-`review` prompt for fitted ICs
with one unambiguous native SCK/SCLK pin each on the exact same exported clock
net, at least one output-capable clock endpoint and one input-capable endpoint,
and explicit return-like pin assignments spanning multiple schematic nets.
Passive/`power_in` types are eligible; native type `unspecified` is eligible
only when the pin function explicitly identifies a return role. It reports
one finding for the direct clock group. A documented
control keeps both endpoints on `+3V3` and uses a common return; the fault
changes only the return pins to `GND_A` and `GND_B`. The separate
`bus.spi_peer_voltage_review` rule remains quiet on that equal-supply case,
showing the additional coverage is reference-domain review rather than a
duplicate voltage prompt.

The rule stays quiet for common references, separate clocks, DNP endpoints,
shield-only pins, incomplete reference metadata without a known split, and
clocks without a clear input/output relationship. A known split remains
reviewable when another peer's reference evidence is incomplete. Existing
component-peer return findings suppress this prompt only when they cover every
explicit return-pin assignment in a complete group. The heuristic does not
require a common return, identify every SPI endpoint from data or chip-select
pins, interpret translated or isolated clock paths, establish electrical
compatibility, or prove a PCB copper or physical return path. Project policy
can set `block`, `off`, or an exact ignore. Synthetic fault, control, boundary,
policy, duplicate-suppression, coverage, ordering, and CLI/MCP parity cases are
under `tests/test_spi_peer_reference_review.py` and
`tests/test_design_lint_mcp_parity_spi_reference.py`. Exact native fixture
exports repeat on digest-pinned KiCad 10.0.0 and 10.0.5 images; see the
[SPI reference fixture notes](../tests/fixtures/design_lint/spi-peer-reference-native/README.md).

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
return net across explicit return-like functions such as GND, AGND, DGND, PGND,
VSS/VSSA/VSSD/VSSP, 0V, RTN, RETURN, or GROUND. Passive/`power_in` types are
eligible; native type `unspecified` is eligible only when the pin function
explicitly identifies a return role. Pin functions marked SHIELD, CHASSIS,
FRAME, or PE are excluded.
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
do not receive the direct voltage comparison. The authored `serial_peers`
contract covers logic-level UART mapping. A separate configurable
`bus.rs485_data_direction_label_mismatch` heuristic reviews bounded D/DI and
R/RO transceiver functions against explicit same-channel UART/USART TX/RX net
labels; it does not replace a reviewed RS-485 topology map. RS-232 needs
separate rules and requirements.

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

## Review BJT bases directly connected to output pins

The catalog rule `component.bjt_base_direct_drive` defaults to
`REVIEW` when a supported basic BJT's native base net also contains a fitted
pin whose native electrical type is output-capable (`output`, `power_out`,
`bidirectional`, `tri_state`, `open_collector`, or `open_emitter`). Because
both pins occupy the same native net, the schematic has no series resistor
between those two pins. Review the intended driver and base-current limit.

The rule recognizes only the twelve basic KiCad NPN and PNP pin-order symbols
with complete, unique B/C/E pin functions. It skips DNP devices, custom and
compound symbols, incomplete or ambiguous assignments, and pins without
native output-type metadata. It does not prove that a resistor is required or
missing elsewhere, that the driver lacks internal current limiting, or that
the transistor's operating point is safe. It does not evaluate footprint
mapping, PCB copper, or physical behavior. Projects can override the rule to
`block` or `off`, or ignore an exact reviewed finding.

The exact-version native fixture lane exports a tooling-owned direct-drive
fault and a series-resistor control twice on KiCad 10.0.0 and 10.0.5. It
confirms native B/C/E functions, output pin types, net membership, and repeatable
findings for both NPN and PNP examples. The control remains a schematic
connectivity example; it does not establish resistor sizing or physical
performance.

## Review BJT bases without a visible base-emitter bias resistor

The opt-in catalog rule `component.bjt_base_without_visible_emitter_bias`
defaults to `off`. When enabled, it prompts if an exact supported basic BJT
has complete native base, collector, and emitter roles; the base and emitter
have distinct unambiguous nets; another fitted pin shares the base net; and no
recognized fitted nonzero two-terminal resistor directly spans the base and
emitter nets. A direct output-capable peer is left to
`component.bjt_base_direct_drive`.

This is a review question about a possible off-state path. Push-pull drive,
internal bias, or another topology can make an external resistor unnecessary.
The rule does not determine whether a resistor is required or adequate and
does not evaluate indirect paths, unparsed values, PCB routing, or physical
behavior. It skips unsupported and compound symbols, DNP devices, incomplete
or ambiguous pin data, open bases, and same-net base/emitter assignments.
Projects can set the rule to `review`, promote it to `block`, leave it `off`,
or ignore an exact reviewed finding. Same-net base/emitter assignments have
their own separate review rule.

The synthetic fixtures cover NPN and PNP faults, direct base-emitter resistor
controls, output-drive delegation, DNP and unsupported cases, policy behavior,
and ordering. Digest-pinned native schematic fixtures repeat netlist and ERC
exports on KiCad 10.0.0 and 10.0.5; their source hashes are recorded in the
[fixture README](../tests/fixtures/design_lint/bjt-base-bias-native/README.md).

## Review BJT base and emitter assigned to one net

The opt-in catalog rule `component.bjt_base_emitter_same_net` defaults to
`off`. It prompts when an exact supported basic NPN or PNP symbol has complete
native B/C/E pin roles and its base and emitter pins have one unambiguous
assignment to the same schematic net. Pin functions determine terminal roles;
pin numbers are not assumed.

A shared base/emitter net may intentionally hold the transistor off. This is a
review clue, not a required connection or proof of a defect. The rule skips DNP,
custom or compound devices, incomplete pin evidence, duplicate role metadata,
open pins, and ambiguous assignments. It does not establish PCB continuity,
footprint pin mapping, external circuitry, or physical behavior. Project
policy can enable review, promote it to block, leave it off, or ignore an exact
finding.

Tooling-owned NPN and PNP fault fixtures and a distinct-net control repeat
native netlist and ERC exports on digest-pinned KiCad 10.0.0 and 10.0.5. Source
hashes are recorded in the
[fixture README](../tests/fixtures/design_lint/bjt-be-same-net-native/README.md).

## Review BJT base and collector assigned to one net

The opt-in catalog rule `component.bjt_base_collector_same_net` defaults to
`off`. It prompts when an exact supported basic NPN or PNP symbol has complete
native B/C/E pin roles and its base and collector pins have one unambiguous
assignment to the same schematic net. Pin functions determine terminal roles;
pin numbers are not assumed.

A base/collector tie can be an intentional diode-connected transistor, such as
a current-reference element. This prompt asks for review; it does not label the
topology defective or infer intended behavior. It skips DNP, custom or
compound devices, incomplete pin evidence, duplicate role metadata, open pins,
and ambiguous assignments. It does not establish PCB continuity, footprint pin
mapping, external circuitry, or physical behavior. Project policy can enable
review, promote it to block, leave it off, or ignore an exact finding.

Tooling-owned NPN and PNP fault fixtures and a distinct-net control repeat
native netlist and ERC exports on digest-pinned KiCad 10.0.0 and 10.0.5. Source
hashes are recorded in the
[fixture README](../tests/fixtures/design_lint/bjt-bc-same-net-native/README.md).

## Require an authored RS-485 topology

The `bus.rs485_data_direction_label_mismatch` review heuristic checks a fitted
transceiver with one native D/DI driver-data input and one R/RO receiver-data
output against explicit UART/USART TX/RX labels on the same channel. It can
prompt when those directions disagree, but does not determine which UART
endpoint is intended or verify the differential bus topology. The default is
`review`; projects may use `block`, `off`, or exact finding ignores through the
design-lint policy.

See the [synthetic fault/control fixture record][rs485-data-fixture] for
source hashes and reproduction details.

The configurable `bus.rs485_data_input_output_same_net` heuristic separately
reviews a fitted RS-485 transceiver whose native D/DI driver input and R/RO
receiver output are assigned to one exact schematic net. It requires an
explicitly RS-485-specific component identity, complete pin inventory, and
unique assignments, so generic D/R functions on unrelated ICs are outside its
scope. A shared net may be intentional for echo or single-wire operation; the
default is `review`, and the rule does not infer the required transceiver mode
or PCB continuity. See the
[fixture README](../tests/fixtures/design_lint/rs485-data-same-net/README.md).

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

## Require a project-authored IC decoupling minimum

Use `design_lint.ic_decoupling_map` when a reviewed electrical requirement sets
a minimum total nominal capacitance for one exact IC power pin. The map names
the IC identity, supply and return nets, every capacitor counted toward the
minimum, and the source basis. No required IC, rail, capacitor, or threshold is
inferred from a design:

```json
{
  "design_lint": {
    "ic_decoupling_map": {
      "schema_version": "1",
      "requirements": [
        {
          "id": "controller-vdd-decoupling",
          "basis": "Example only; replace with the reviewed source and requirement",
          "ic_reference": "U1",
          "expected_ic_value": "Synthetic controller",
          "expected_ic_symbol": "Synthetic:Controller",
          "expected_ic_footprint": "Synthetic:QFN",
          "power_pin": "U1.1",
          "power_net": "+3V3",
          "return_net": "GND",
          "minimum_total_capacitance_pf": 100000.0,
          "capacitors": [
            {
              "reference": "C1",
              "expected_symbol": "Device:C",
              "expected_footprint": "Synthetic:0603",
              "power_pin": "C1.1",
              "return_pin": "C1.2"
            }
          ]
        }
      ]
    }
  }
}
```

For each mapped requirement, the check verifies exact component identity,
IC fitted state, power-pin type and assignment, capacitor identity and fitted
state, exact two-pin inventory, passive pin types, and supply/return
assignments. A mapped DNP IC is a stale requirement: it produces `REVIEW` and
does not evaluate the capacitor total. The check parses explicit capacitance
units, sums mapped nominal values in pF, and reviews a total below the authored
inclusive minimum. Stale identity or topology also produces a review before a
capacitance comparison can be relied on. Findings default to `REVIEW`; the
normal rule override and exact-fingerprint ignore lifecycle applies.

The example values are synthetic and are not design guidance. The check does
not choose a universal capacitor value, discover missing map entries, validate
the source requirement, apply tolerance or DC-bias derating, evaluate voltage
rating or transient response, check PCB placement, or prove copper/return-path
continuity. Pair it with the separate PCB decoupling and return-path checks
where those requirements apply.

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

[electrical-drc-items-100]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.0/pcbnew/drc/drc_item.cpp
[electrical-drc-items-105]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.5/pcbnew/drc/drc_item.cpp
[electrical-drc-settings-100]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.0/pcbnew/board_design_settings.cpp
[electrical-drc-settings-105]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.5/pcbnew/board_design_settings.cpp
[misc-drc-items-100]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.0/pcbnew/drc/drc_item.cpp
[misc-drc-items-105]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.5/pcbnew/drc/drc_item.cpp
[misc-drc-settings-100]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.0/pcbnew/board_design_settings.cpp
[misc-drc-settings-105]: https://gitlab.com/kicad/code/kicad/-/blob/10.0.5/pcbnew/board_design_settings.cpp
[rs485-data-fixture]: ../tests/fixtures/design_lint/rs485-data-direction-label-mismatch/README.md
