"""Synthetic fitted I2S data-output sharing fault and controls."""

from __future__ import annotations

from kicad_tooling.hwrepo.netlist_contract_models import (
    ComponentContract,
    NetlistContract,
)


def i2s_data_output_netlist(
    *,
    shared: bool = True,
    dnp_references: tuple[str, ...] = (),
    output_functions: tuple[str, str] = ("SDOUT", "SDOUT"),
) -> NetlistContract:
    """Return two fully inventoried audio ICs with peer or isolated outputs."""
    references = ("U1", "U2")
    nets: dict[str, tuple[str, ...]] = {
        "I2S_BCLK": ("U1.1", "U2.1"),
        "I2S_LRCLK": ("U1.2", "U2.2"),
        "U1_MCLK": ("U1.4",),
        "U2_MCLK": ("U2.4",),
    }
    if shared:
        nets["I2S_DATA_SHARED"] = ("U1.3", "U2.3")
    else:
        nets["U1_I2S_DATA"] = ("U1.3",)
        nets["U2_I2S_DATA"] = ("U2.3",)
    return NetlistContract(
        components={
            reference: ComponentContract(value="Synthetic I2S codec", footprint="Synthetic:Codec")
            for reference in references
        },
        nets=nets,
        dnp_components=dnp_references,
        component_symbols={reference: "Synthetic:I2SAudioCodec" for reference in references},
        component_pin_numbers={reference: ("1", "2", "3", "4") for reference in references},
        pin_functions={
            "U1.1": "I2S_BCLK",
            "U1.2": "I2S_LRCLK",
            "U1.3": output_functions[0],
            "U1.4": "MCLK",
            "U2.1": "I2S_BCLK",
            "U2.2": "I2S_LRCLK",
            "U2.3": output_functions[1],
            "U2.4": "MCLK",
        },
        pin_electrical_types={
            **{f"{reference}.1": "passive" for reference in references},
            **{f"{reference}.2": "passive" for reference in references},
            **{f"{reference}.3": "passive" for reference in references},
            **{f"{reference}.4": "passive" for reference in references},
        },
    )
