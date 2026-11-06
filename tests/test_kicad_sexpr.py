from __future__ import annotations

from collections.abc import Mapping

import pytest

from kicad_tooling.hwrepo.kicad_sexpr import (
    quote_sexpr_atom,
    sexpr_atoms,
    sexpr_nodes,
    sexpr_properties,
    sexpr_property_value,
    sexpr_root,
    sexpr_tokens,
)


def test_root_and_children_ignore_delimiters_inside_strings_and_comments() -> None:
    source = '(root "close ) and open (" # ignored )\n (item value))'

    root = sexpr_root(source, "root")
    items = sexpr_nodes(source, root, "item")

    assert sexpr_atoms(source, root) == ("root", "close ) and open (")
    assert len(items) == 1
    assert sexpr_atoms(source, items[0]) == ("item", "value")


def test_property_index_is_a_named_mapping_contract_and_rejects_duplicates() -> None:
    source = '(symbol (property "Reference" "J1") (property "Value" "Header"))'
    root = sexpr_root(source, "symbol")

    properties = sexpr_properties(source, root)

    assert isinstance(properties, Mapping)
    assert tuple(properties) == ("Reference", "Value")
    assert sexpr_property_value(source, properties, "Reference", required=True) == "J1"
    assert sexpr_property_value(source, properties, "missing") == ""
    with pytest.raises(TypeError):
        properties["Other"] = properties["Reference"]
    duplicate = '(symbol (property "Reference" "J1") (property "Reference" "J2"))'
    with pytest.raises(ValueError, match="duplicate CAD property"):
        sexpr_properties(duplicate, sexpr_root(duplicate, "symbol"))


def test_token_spans_support_lossless_replacement_and_quoted_output() -> None:
    source = '(property "Value" "old")'
    root = sexpr_root(source, "property")
    tokens = sexpr_tokens(source, root)

    assert len(tokens) == 3
    assert tokens[1].quoted and tokens[2].quoted
    replacement = quote_sexpr_atom('new "value"')
    updated = source[: tokens[2].start] + replacement + source[tokens[2].end :]
    assert updated == '(property "Value" "new \\"value\\"")'
    with pytest.raises(ValueError, match="control character"):
        quote_sexpr_atom("bad\nvalue")


def test_root_rejects_non_comment_text_outside_the_expression() -> None:
    with pytest.raises(ValueError, match="Unexpected text outside root"):
        sexpr_root("prefix (root)", "root")
