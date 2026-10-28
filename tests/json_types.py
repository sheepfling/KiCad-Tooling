"""Shared types for JSON values exchanged by test fixtures and reports."""

from typing import TypeAlias

from pydantic import JsonValue

JsonObject: TypeAlias = dict[str, JsonValue]
