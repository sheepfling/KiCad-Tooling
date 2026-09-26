"""Small no-key DigiKey myLists adapter, invoked only by an explicit handoff.

The wire contract follows Digi-Key/KiCad-Push-to-DigiKey's public source.
This creates a review list, not a purchase, and never retries a POST automatically.
"""
from __future__ import annotations

import http.client
import re
import ssl
import time
from urllib.parse import urlencode

from .contracts import parse_model
from .models import (
    DigiKeyHandoffPart,
    DigiKeyHandoffPayload,
    DigiKeyHandoffQuantity,
    DigiKeyHandoffReply,
    DigiKeyHandoffUrl,
    PurchasingPlan,
)

_HOST = "www.digikey.com"
_ENDPOINT = "/mylists/api/thirdparty"
_TIMEOUT_SECONDS = 15.0
_MAX_REQUEST_BYTES = 1_048_576
_MAX_RESPONSE_BYTES = 8192
_SHORT_URL = re.compile(r"https://www\.digikey\.com/short/[a-z0-9]{7,8}")


class DigiKeyHandoffError(ValueError):
    """A handoff failed or its external outcome could not be confirmed."""


def build_payload(plan: PurchasingPlan) -> DigiKeyHandoffPayload:
    """Build a supplier request only from a complete, reviewed order projection."""
    if plan.status != "READY_FOR_ORDER_REVIEW" or plan.findings or not plan.lines:
        raise DigiKeyHandoffError("Complete the parts review before sending a DigiKey list.")
    identities: dict[str, tuple[str, str]] = {}
    rows: list[DigiKeyHandoffPart] = []
    for line in plan.lines:
        identity = (line.manufacturer, line.mpn)
        previous = identities.get(line.order_number)
        if previous is not None and previous != identity:
            raise DigiKeyHandoffError(
                f"{line.order_number}: different manufacturers share this order number; "
                "select an exact DigiKey SKU for each part before sending."
            )
        identities[line.order_number] = identity
        rows.append(DigiKeyHandoffPart(
            requestedPartNumber=line.order_number,
            quantities=(DigiKeyHandoffQuantity(quantity=line.quantity),),
            customerReference=line.part_id,
            notes=(f"Manufacturer: {line.manufacturer}; MPN: {line.mpn}; "
                   f"References: {', '.join(line.references)}"),
        ))
    return DigiKeyHandoffPayload(root=tuple(rows))


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("DigiKey handoff timed out")
    return remaining


def _post(path: str, body: bytes) -> bytes:
    """One bounded HTTPS exchange; redirects are rejected without following them."""
    deadline = time.monotonic() + _TIMEOUT_SECONDS
    connection = http.client.HTTPSConnection(
        _HOST, timeout=_TIMEOUT_SECONDS, context=ssl.create_default_context(),
    )
    try:
        connection.request("POST", path, body=body, headers={
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "KiCad-Parts-Assistant/1",
        })
        if connection.sock is not None:
            connection.sock.settimeout(_remaining(deadline))
        transport_socket = connection.sock
        response = connection.getresponse()
        if response.status != 200:
            raise DigiKeyHandoffError(
                f"DigiKey returned HTTP {response.status} without confirming a list. "
                "No automatic retry was made; check DigiKey before trying again."
            )
        length = response.getheader("Content-Length")
        if length is not None:
            try:
                content_length = int(length)
            except ValueError as exc:
                raise DigiKeyHandoffError("DigiKey returned an invalid response length.") from exc
            if content_length < 0 or content_length > _MAX_RESPONSE_BYTES:
                raise DigiKeyHandoffError("DigiKey returned an oversized response.")
        document = bytearray()
        while True:
            remaining = _remaining(deadline)
            if transport_socket is not None:
                transport_socket.settimeout(remaining)
            # read1 performs at most one buffered transport read. Recompute the
            # deadline between chunks so a trickle cannot reset the whole timeout.
            chunk = response.read1(_MAX_RESPONSE_BYTES + 1 - len(document))
            _remaining(deadline)
            if not chunk:
                return bytes(document)
            document.extend(chunk)
            if len(document) > _MAX_RESPONSE_BYTES:
                raise DigiKeyHandoffError("DigiKey returned an oversized response.")
    except (OSError, http.client.HTTPException) as exc:
        raise DigiKeyHandoffError(
            "DigiKey did not confirm whether the list was received. No automatic retry "
            "was made; check DigiKey before trying again."
        ) from exc
    finally:
        connection.close()


def send(payload: DigiKeyHandoffPayload, *, list_name: str) -> DigiKeyHandoffReply:
    """Send once after the user selects the button; return only a checked review URL."""
    if not list_name.strip() or len(list_name) > 200 or any(ord(char) < 32 for char in list_name):
        raise DigiKeyHandoffError("Use a nonempty list name of at most 200 characters.")
    if not payload.root:
        raise DigiKeyHandoffError("There are no parts to send to DigiKey.")
    body = payload.model_dump_json(by_alias=True).encode("utf-8")
    if len(body) > _MAX_REQUEST_BYTES:
        raise DigiKeyHandoffError("This list exceeds the assistant's 1 MiB handoff limit.")
    query = urlencode({"listName": list_name, "tags": "KiCad-Parts-Assistant"})
    document = _post(f"{_ENDPOINT}?{query}", body)
    try:
        result = parse_model(document.decode("utf-8"), DigiKeyHandoffUrl)
    except (UnicodeError, ValueError) as exc:
        raise DigiKeyHandoffError(
            "DigiKey returned an unsupported response instead of a review link. "
            "No automatic retry was made; check DigiKey before trying again."
        ) from exc
    if not _SHORT_URL.fullmatch(result.root):
        raise DigiKeyHandoffError("DigiKey returned an unexpected review URL; it was not opened.")
    return DigiKeyHandoffReply(single_use_url=result.root)
