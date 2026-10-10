"""Synthetic I2C and serial fixtures for cross-surface parity tests."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import (
    AnalysisPending,
    ElectricalAnalysisContract,
    I2cPullupAnalysis,
    I2cPullupArrayChannelRequirement,
    I2cPullupArrayRequirement,
    I2cPullupBusRequirement,
    I2cPullupLineRequirement,
    SerialDirectPeerRequirement,
    SerialEndpointRequirement,
    SerialPeerAnalysis,
    SerialPeerLinkRequirement,
    SerialPinNetRequirement,
)

PROJECT_ID = "i2c-parity-fixture"

KICAD_VERSION = "10.0.5"

TOOLCHAIN_IMAGE = "synthetic-kicad:10.0.5"

NETLIST_CONTROL = """<export>
  <components>
    <comp ref="U1"><value>Synthetic two-wire target</value>
      <libsource lib="Synthetic" part="I2cTarget"/></comp>
    <comp ref="J1"><value>Synthetic mapped endpoint A</value><footprint>Synthetic:Header</footprint>
      <libsource lib="Synthetic" part="SerialHeader"/></comp>
    <comp ref="J2"><value>Synthetic mapped endpoint B</value><footprint>Synthetic:Header</footprint>
      <libsource lib="Synthetic" part="SerialHeader"/></comp>
    <comp ref="J3"><value>Synthetic unmapped endpoint</value><footprint>Synthetic:Header</footprint>
      <libsource lib="Synthetic" part="SerialHeader"/></comp>
    <comp ref="RN1"><value>4x4.7k</value><footprint>Synthetic:RA4</footprint>
      <libsource lib="Synthetic" part="ResistorArray"/></comp>
  </components>
  <libparts>
    <libpart lib="Synthetic" part="I2cTarget"><pins>
      <pin num="1" name="SDA" type="passive"/>
      <pin num="2" name="SCL" type="passive"/>
    </pins></libpart>
    <libpart lib="Synthetic" part="SerialHeader"><pins>
      <pin num="1" name="TX" type="passive"/>
      <pin num="2" name="RX" type="passive"/>
    </pins></libpart>
    <libpart lib="Synthetic" part="ResistorArray"><pins>
      <pin num="1" name="1" type="passive"/>
      <pin num="2" name="2" type="passive"/>
      <pin num="3" name="3" type="passive"/>
      <pin num="4" name="4" type="passive"/>
    </pins></libpart>
  </libparts>
  <nets>
    <net name="I2C_SDA"><node ref="U1" pin="1"/><node ref="RN1" pin="1"/></net>
    <net name="I2C_SCL"><node ref="U1" pin="2"/><node ref="RN1" pin="3"/></net>
    <net name="+3V3"><node ref="RN1" pin="2"/><node ref="RN1" pin="4"/></net>
    <net name="SERIAL_A_TX"><node ref="J1" pin="1"/><node ref="J2" pin="2"/></net>
    <net name="SERIAL_A_RX"><node ref="J1" pin="2"/><node ref="J2" pin="1"/></net>
    <net name="SERIAL_B_TX"><node ref="J3" pin="1"/></net>
    <net name="SERIAL_B_RX"><node ref="J3" pin="2"/></net>
  </nets>
</export>
"""


def alternate_function_serial_netlist() -> str:
    """Exercise UART-labeled nets on generic MCU package-pin functions."""
    netlist = NETLIST_CONTROL.replace('name="SDA"', 'name="PA2"').replace(
        'name="SCL"', 'name="PA3"'
    )
    netlist = netlist.replace(
        '<net name="I2C_SDA"><node ref="U1" pin="1"/><node ref="RN1" pin="1"/></net>',
        '<net name="UART_TX"><node ref="U1" pin="1"/><node ref="J3" pin="1"/></net>',
    )
    netlist = netlist.replace(
        '<net name="I2C_SCL"><node ref="U1" pin="2"/><node ref="RN1" pin="3"/></net>',
        '<net name="UART_RX"><node ref="U1" pin="2"/><node ref="J3" pin="2"/></net>',
    )
    return netlist


def labelled_generic_uart_reference_netlist(*, split_reference: bool) -> str:
    """Synthetic direct UART segment with generic IC pin functions."""
    references = (
        '<net name="GND_A"><node ref="U1" pin="9"/><node ref="U2" pin="9"/></net>'
        if not split_reference
        else '<net name="GND_A"><node ref="U1" pin="9"/></net>'
        '<net name="GND_B"><node ref="U2" pin="9"/></net>'
    )
    return f"""<export>
  <components>
    <comp ref="U1"><value>Synthetic translator</value><footprint>Package:UART-TX</footprint>
      <libsource lib="Synthetic" part="UartTransmitter"/></comp>
    <comp ref="U2"><value>Synthetic serial bridge</value><footprint>Package:UART-RX</footprint>
      <libsource lib="Synthetic" part="UartReceiver"/></comp>
  </components>
  <libparts>
    <libpart lib="Synthetic" part="UartTransmitter"><pins>
      <pin num="1" name="B2" type="tri_state"/><pin num="2" name="B1" type="tri_state"/>
      <pin num="8" name="VDD" type="power_in"/><pin num="9" name="GND" type="power_in"/>
    </pins></libpart>
    <libpart lib="Synthetic" part="UartReceiver"><pins>
      <pin num="1" name="ADBUS0" type="bidirectional"/>
      <pin num="2" name="ADBUS1" type="bidirectional"/>
      <pin num="8" name="VDD" type="power_in"/><pin num="9" name="GND" type="power_in"/>
    </pins></libpart>
  </libparts>
  <nets>
    <net name="Compute module/UART.0.TX"><node ref="U1" pin="1"/><node ref="U2" pin="2"/></net>
    <net name="Compute module/UART.0.RX"><node ref="U1" pin="2"/><node ref="U2" pin="1"/></net>
    <net name="+3V3"><node ref="U1" pin="8"/><node ref="U2" pin="8"/></net>
    {references}
  </nets>
</export>
"""


NETLIST_MISSING_ARRAY = """<export>
  <components>
    <comp ref="U1"><value>Synthetic two-wire target</value>
      <libsource lib="Synthetic" part="I2cTarget"/></comp>
    <comp ref="J1"><value>Synthetic mapped endpoint A</value><footprint>Synthetic:Header</footprint>
      <libsource lib="Synthetic" part="SerialHeader"/></comp>
    <comp ref="J2"><value>Synthetic mapped endpoint B</value><footprint>Synthetic:Header</footprint>
      <libsource lib="Synthetic" part="SerialHeader"/></comp>
    <comp ref="J3"><value>Synthetic unmapped endpoint</value><footprint>Synthetic:Header</footprint>
      <libsource lib="Synthetic" part="SerialHeader"/></comp>
  </components>
  <libparts>
    <libpart lib="Synthetic" part="I2cTarget"><pins>
      <pin num="1" name="SDA" type="passive"/>
      <pin num="2" name="SCL" type="passive"/>
    </pins></libpart>
    <libpart lib="Synthetic" part="SerialHeader"><pins>
      <pin num="1" name="TX" type="passive"/>
      <pin num="2" name="RX" type="passive"/>
    </pins></libpart>
  </libparts>
  <nets>
    <net name="I2C_SDA"><node ref="U1" pin="1"/></net>
    <net name="I2C_SCL"><node ref="U1" pin="2"/></net>
    <net name="SERIAL_A_TX"><node ref="J1" pin="1"/><node ref="J2" pin="2"/></net>
    <net name="SERIAL_A_RX"><node ref="J1" pin="2"/><node ref="J2" pin="1"/></net>
    <net name="SERIAL_B_TX"><node ref="J3" pin="1"/></net>
    <net name="SERIAL_B_RX"><node ref="J3" pin="2"/></net>
  </nets>
</export>
"""


def dual_uart_reference_netlist(*, split_first_return: bool) -> str:
    """Synthetic dual-UART MCU netlist with one optional split connector return."""
    first_return = "GND_B" if split_first_return else "GND_A"
    first_return_node = "" if split_first_return else '<node ref="J1" pin="4"/>'
    split_return_net = (
        f'<net name="{first_return}"><node ref="J1" pin="4"/></net>' if split_first_return else ""
    )
    return f"""<export>
  <components>
    <comp ref="U1"><value>Synthetic two-wire target</value>
      <footprint>Synthetic:Controller</footprint>
      <libsource lib="Synthetic" part="DualUartI2cTarget"/></comp>
    <comp ref="J1"><value>Synthetic mapped endpoint A</value><footprint>Synthetic:Header</footprint>
      <libsource lib="Synthetic" part="SerialHeaderPower"/></comp>
    <comp ref="J2"><value>Synthetic mapped endpoint B</value><footprint>Synthetic:Header</footprint>
      <libsource lib="Synthetic" part="SerialHeaderPower"/></comp>
    <comp ref="J3"><value>Synthetic unmapped endpoint</value><footprint>Synthetic:Header</footprint>
      <libsource lib="Synthetic" part="SerialHeader"/></comp>
    <comp ref="RN1"><value>4x4.7k</value><footprint>Synthetic:RA4</footprint>
      <libsource lib="Synthetic" part="ResistorArray"/></comp>
  </components>
  <libparts>
    <libpart lib="Synthetic" part="DualUartI2cTarget"><pins>
      <pin num="1" name="SDA" type="passive"/>
      <pin num="2" name="SCL" type="passive"/>
      <pin num="3" name="VDD" type="power_in"/>
      <pin num="4" name="GND" type="power_in"/>
      <pin num="5" name="UART1_TX" type="output"/>
      <pin num="6" name="UART1_RX" type="input"/>
      <pin num="7" name="UART2_TX" type="output"/>
      <pin num="8" name="UART2_RX" type="input"/>
    </pins></libpart>
    <libpart lib="Synthetic" part="SerialHeaderPower"><pins>
      <pin num="1" name="TX" type="output"/>
      <pin num="2" name="RX" type="input"/>
      <pin num="3" name="VDD" type="passive"/>
      <pin num="4" name="GND" type="passive"/>
    </pins></libpart>
    <libpart lib="Synthetic" part="SerialHeader"><pins>
      <pin num="1" name="TX" type="passive"/>
      <pin num="2" name="RX" type="passive"/>
    </pins></libpart>
    <libpart lib="Synthetic" part="ResistorArray"><pins>
      <pin num="1" name="1" type="passive"/>
      <pin num="2" name="2" type="passive"/>
      <pin num="3" name="3" type="passive"/>
      <pin num="4" name="4" type="passive"/>
    </pins></libpart>
  </libparts>
  <nets>
    <net name="I2C_SDA"><node ref="U1" pin="1"/><node ref="RN1" pin="1"/></net>
    <net name="I2C_SCL"><node ref="U1" pin="2"/><node ref="RN1" pin="3"/></net>
    <net name="+3V3"><node ref="U1" pin="3"/><node ref="RN1" pin="2"/>
      <node ref="RN1" pin="4"/><node ref="J1" pin="3"/><node ref="J2" pin="3"/></net>
    <net name="UART1_TX"><node ref="U1" pin="5"/><node ref="J1" pin="2"/></net>
    <net name="UART1_RX"><node ref="U1" pin="6"/><node ref="J1" pin="1"/></net>
    <net name="UART2_TX"><node ref="U1" pin="7"/><node ref="J2" pin="2"/></net>
    <net name="UART2_RX"><node ref="U1" pin="8"/><node ref="J2" pin="1"/></net>
    <net name="GND_A"><node ref="U1" pin="4"/><node ref="J2" pin="4"/>
      {first_return_node}</net>
    {split_return_net}
    <net name="SERIAL_B_TX"><node ref="J3" pin="1"/></net>
    <net name="SERIAL_B_RX"><node ref="J3" pin="2"/></net>
  </nets>
</export>
"""


def dual_uart_separate_reference_map() -> SerialPeerAnalysis:
    """Record an intentionally separate reference for one direct UART port."""
    controller = SerialEndpointRequirement(
        id="controller-uart1",
        reference="U1",
        symbol="Synthetic:DualUartI2cTarget",
        footprint="Synthetic:Controller",
        logic_domain="3V3",
        tx=SerialPinNetRequirement(pin="U1.5", net="UART1_TX"),
        rx=SerialPinNetRequirement(pin="U1.6", net="UART1_RX"),
        reference_pins=(SerialPinNetRequirement(pin="U1.4", net="GND_A"),),
    )
    header = SerialEndpointRequirement(
        id="header-uart1",
        reference="J1",
        symbol="Synthetic:SerialHeaderPower",
        footprint="Synthetic:Header",
        logic_domain="3V3",
        tx=SerialPinNetRequirement(pin="J1.1", net="UART1_RX"),
        rx=SerialPinNetRequirement(pin="J1.2", net="UART1_TX"),
        reference_pins=(SerialPinNetRequirement(pin="J1.4", net="GND_B"),),
    )
    return SerialPeerAnalysis(
        basis="Synthetic project-reviewed isolated UART reference domains",
        links=(
            SerialPeerLinkRequirement(
                id="controller-uart1-header",
                basis="Synthetic direct UART endpoint map",
                endpoint=controller,
                peer=SerialDirectPeerRequirement(mode="direct", endpoint=header),
                reference_policy="separate_nets",
            ),
        ),
    )


def electrical_contract() -> ElectricalAnalysisContract:
    """State the intended pull-up topology independently of the netlist fixture."""
    pullups = I2cPullupAnalysis(
        basis="Synthetic I2C interface requirement authored for parity regression",
        buses=(
            I2cPullupBusRequirement(
                id="main",
                basis="Synthetic two-wire target interface",
                sda=I2cPullupLineRequirement(
                    net="I2C_SDA",
                    rail="+3V3",
                    minimum_ohms=1_000,
                    maximum_ohms=100_000,
                ),
                scl=I2cPullupLineRequirement(
                    net="I2C_SCL",
                    rail="+3V3",
                    minimum_ohms=1_000,
                    maximum_ohms=100_000,
                ),
            ),
        ),
        arrays=(
            I2cPullupArrayRequirement(
                reference="RN1",
                expected_symbol="Synthetic:ResistorArray",
                expected_footprint="Synthetic:RA4",
                expected_value="4x4.7k",
                basis="Synthetic resistor-array channel map",
                channels=(
                    I2cPullupArrayChannelRequirement(
                        id="sda",
                        signal_pin="RN1.1",
                        rail_pin="RN1.2",
                        signal_net="I2C_SDA",
                        rail_net="+3V3",
                        resistance_ohms=4_700,
                        basis="Synthetic channel 1 mapping",
                    ),
                    I2cPullupArrayChannelRequirement(
                        id="scl",
                        signal_pin="RN1.3",
                        rail_pin="RN1.4",
                        signal_net="I2C_SCL",
                        rail_net="+3V3",
                        resistance_ohms=4_700,
                        basis="Synthetic channel 2 mapping",
                    ),
                ),
            ),
        ),
    )
    endpoint_a = SerialEndpointRequirement(
        id="endpoint-a",
        reference="J1",
        symbol="Synthetic:SerialHeader",
        footprint="Synthetic:Header",
        logic_domain="3V3",
        tx=SerialPinNetRequirement(pin="J1.1", net="SERIAL_A_TX"),
        rx=SerialPinNetRequirement(pin="J1.2", net="SERIAL_A_RX"),
    )
    endpoint_b = SerialEndpointRequirement(
        id="endpoint-b",
        reference="J2",
        symbol="Synthetic:SerialHeader",
        footprint="Synthetic:Header",
        logic_domain="3V3",
        tx=SerialPinNetRequirement(pin="J2.1", net="SERIAL_A_RX"),
        rx=SerialPinNetRequirement(pin="J2.2", net="SERIAL_A_TX"),
    )
    serial_peers = SerialPeerAnalysis(
        basis="Synthetic reviewed UART peer map for parity coverage",
        links=(
            SerialPeerLinkRequirement(
                id="mapped-console",
                basis="Synthetic two-connector direct UART link",
                endpoint=endpoint_a,
                peer=SerialDirectPeerRequirement(mode="direct", endpoint=endpoint_b),
                reference_policy="not_applicable",
            ),
        ),
    )
    return ElectricalAnalysisContract(
        project_id=PROJECT_ID,
        ngspice_version="not run by synthetic parity fixture",
        grounding=AnalysisPending(reason="Grounding is outside this synthetic fixture."),
        i2c_pullups=pullups,
        serial_peers=serial_peers,
        power=AnalysisPending(reason="Power analysis is outside this synthetic fixture."),
        high_frequency=AnalysisPending(
            reason="High-frequency analysis is outside this synthetic fixture."
        ),
    )
