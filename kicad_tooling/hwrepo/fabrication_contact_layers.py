"""Bind IPC-D-356 access layers to source PCB component-pad layers."""

from __future__ import annotations

from .fabrication_artwork import Contact, UnsupportedFabricationFormat
from .fabrication_contact_geometry import match_ipc356_source_pad_centers
from .fabrication_contact_source import SourceComponentPad


def require_ipc356_source_pad_layers(
    source_pads: tuple[SourceComponentPad, ...], contacts: tuple[Contact, ...]
) -> None:
    """Require each IPC-D-356 component access class to match its source center."""
    pairs = match_ipc356_source_pad_centers(source_pads, contacts)
    for source, contact in pairs:
        if source.contact_layer is None:
            raise UnsupportedFabricationFormat(
                "source PCB pad "
                f"{source.reference}.{source.number} has unsupported or ambiguous "
                "copper-layer classification"
            )
        if source.contact_layer != contact.layer:
            raise UnsupportedFabricationFormat(
                "IPC-D-356 layer classification differs from source PCB pad "
                f"{source.reference}.{source.number} at "
                f"({source.x_nm}, {-source.y_nm}) nm "
                f"(expected {source.contact_layer}; observed {contact.layer})"
            )


def require_ipc356_source_pad_access_codes(
    source_pads: tuple[SourceComponentPad, ...],
    contacts: tuple[Contact, ...],
    copper_layer_count: int,
) -> None:
    """Require each IPC-D-356 access code to match its source pad and copper stack."""
    if copper_layer_count < 2:
        raise UnsupportedFabricationFormat(
            "IPC-D-356 access-code comparison requires a supported copper stack"
        )
    for source, contact in match_ipc356_source_pad_centers(source_pads, contacts):
        if source.contact_layer is None:
            raise UnsupportedFabricationFormat(
                "source PCB pad "
                f"{source.reference}.{source.number} has unsupported or ambiguous "
                "copper-layer classification"
            )
        if contact.access_code is None:
            raise UnsupportedFabricationFormat(
                f"IPC-D-356 access code is unavailable for {source.reference}.{source.number}"
            )
        expected = {
            "through": 0,
            "top": 1,
            "bottom": copper_layer_count,
        }[source.contact_layer]
        if contact.access_code != expected:
            raise UnsupportedFabricationFormat(
                "IPC-D-356 access code differs from source PCB pad "
                f"{source.reference}.{source.number} at "
                f"({source.x_nm}, {-source.y_nm}) nm "
                f"(expected A{expected:02d}; observed A{contact.access_code:02d})"
            )
