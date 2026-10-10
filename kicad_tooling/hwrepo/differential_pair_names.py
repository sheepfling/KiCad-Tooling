"""Recognize review candidates from complementary schematic net names."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .models import (
    NetName,
    Reference,
)
from .pcb_drc_models import PcbDifferentialPairRuleMap


@dataclass(frozen=True)
class NamedDifferentialPair:
    """A deterministic name-based pair candidate, not an asserted requirement."""

    positive_net: str
    negative_net: str
    naming_pattern: str
    positive_references: tuple[str, ...]
    negative_references: tuple[str, ...]


# Prefer the more specific suffixes first. Bare-letter forms require a longer
# base to avoid interpreting names such as VIP/VIN as a complementary pair.
_SUFFIXES: tuple[tuple[str, str, str, int], ...] = (
    ("_TXP", "_TXN", "_TXP/_TXN", 1),
    ("_RXP", "_RXN", "_RXP/_RXN", 1),
    ("_DP", "_DM", "_DP/_DM", 1),
    ("_P", "_N", "_P/_N", 1),
    ("_H", "_L", "_H/_L", 1),
    ("+", "-", "+/-", 1),
    ("DP", "DM", "DP/DM", 3),
    ("P", "N", "P/N", 3),
    ("H", "L", "H/L", 3),
)


def named_differential_pairs(
    nets: Mapping[NetName, tuple[Reference, ...]],
    reviewed_map: PcbDifferentialPairRuleMap | None = None,
) -> tuple[NamedDifferentialPair, ...]:
    """Find complementary net-name candidates not present in the reviewed pair map.

    This is intentionally a naming heuristic. It does not measure PCB geometry,
    determine whether the interface is differential, or infer acceptable limits.
    """
    normalized: dict[str, tuple[str, tuple[str, ...]] | None] = {}
    for name, references in sorted(nets.items(), key=lambda item: item[0].casefold()):
        key = name.casefold()
        if key in normalized:
            normalized[key] = None
        else:
            normalized[key] = (name, tuple(sorted(set(references))))

    reviewed: set[tuple[str, str]] = set()
    if reviewed_map is not None:
        reviewed = {
            (item.positive_net.casefold(), item.negative_net.casefold())
            for item in reviewed_map.requirements
        }

    found: dict[tuple[str, str], NamedDifferentialPair] = {}
    for net_name, references in sorted(nets.items(), key=lambda item: item[0].casefold()):
        upper_name = net_name.upper()
        for positive_suffix, negative_suffix, pattern, minimum_base in _SUFFIXES:
            if not upper_name.endswith(positive_suffix):
                continue
            base = net_name[: len(net_name) - len(positive_suffix)]
            if len(base) < minimum_base:
                continue
            negative_key = (base + negative_suffix).casefold()
            negative = normalized.get(negative_key)
            positive = normalized.get(net_name.casefold())
            if positive is None or negative is None:
                continue
            positive_name, positive_refs = positive
            negative_name, negative_refs = negative
            if not positive_refs or not negative_refs:
                continue
            if (positive_name.casefold(), negative_name.casefold()) in reviewed:
                continue
            identity = (positive_name.casefold(), negative_name.casefold())
            found.setdefault(
                identity,
                NamedDifferentialPair(
                    positive_net=positive_name,
                    negative_net=negative_name,
                    naming_pattern=pattern,
                    positive_references=positive_refs,
                    negative_references=negative_refs,
                ),
            )
            break
    return tuple(
        sorted(
            found.values(),
            key=lambda item: (item.positive_net.casefold(), item.negative_net.casefold()),
        )
    )
