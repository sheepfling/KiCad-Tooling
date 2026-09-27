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
they use differing nets. This works from the symbol pin definitions even when
one pin is unconnected. The connector-reference hint recognizes `J`, `P`, `X`,
and `CN` numbers. Different symbols, different pin function names, and unusual
reference prefixes may need direct review without a hint.

The report also flags numbered return-like net names such as `0V CTRL 1` /
`0V CTRL 2` and `USB1_GND` / `USB2_GND`. Net-name hints are deliberately
narrow and do not include shield names. Every hint is `UNREVIEWED`: similar
names or functions are reasons to compare the approved pinout with the design,
not proof that the pins should be tied.

Capture writes only under the project's ignored `build/` directory. A retained
native summary can be inspected with
`--native-summary build/<run>/<board-id>/summary.json` after its source,
toolchain, and netlist hashes are checked. Native PCB validation exports the
netlist even when the component contract is empty; it still fails that empty
contract and names any detected connector candidates in the failure.

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
`common_net` or `separate_nets`. Pin relationships can cover power, returns,
and other reviewed connector functions. The separate `grounding` section still
covers declared ground domains and component ground-pin review.

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

The checks establish schematic net membership. A specified net tie or bond
needs its own schematic and PCB review; a direct `common_net` rule does not
describe an indirect path. Review connector pads, planes, and reference points
on the PCB, then test first-article continuity according to the approved
pinout before production acceptance.

[kicad-erc]: https://docs.kicad.org/10.0/en/eeschema/eeschema.html
