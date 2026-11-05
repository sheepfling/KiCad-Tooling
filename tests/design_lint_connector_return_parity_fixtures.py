"""Catalog references for connector-return CLI/MCP fault and control cases."""

from types import MappingProxyType

_PARITY_TEST = (
    "tests.test_design_lint_mcp_parity_connector_all_open_returns."
    "test_mixed_usb_serial_return_review_matches_between_cli_and_mcp"
)

CONNECTOR_RETURN_PARITY_FIXTURES = MappingProxyType(
    {
        "connector.repeated_pin_function": MappingProxyType(
            {
                "fault_fixtures": (_PARITY_TEST,),
                "valid_control_fixtures": (_PARITY_TEST,),
                "metamorphic_fixtures": (_PARITY_TEST,),
            }
        ),
    }
)
