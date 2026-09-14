"""
Tests for API dependency helpers.
"""

from starlette.requests import Request

from llm_inference_service.api.dependencies import _get_client_ip


def _build_request(
    headers: list[tuple[bytes, bytes]] | None = None,
    client: tuple[str, int] | None = ("127.0.0.1", 12345),
) -> Request:
    scope = {
        "type": "http",
        "headers": headers or [],
        "client": client,
    }

    return Request(scope)


def test_get_client_ip_prefers_forwarded_for_header() -> None:
    request = _build_request(
        headers=[
            (
                b"x-forwarded-for",
                b"203.0.113.10, 10.0.0.1",
            )
        ]
    )

    assert _get_client_ip(request) == "203.0.113.10"


def test_get_client_ip_uses_direct_client_when_header_is_missing() -> None:
    request = _build_request(
        client=("198.51.100.20", 12345),
    )

    assert _get_client_ip(request) == "198.51.100.20"


def test_get_client_ip_returns_none_when_client_cannot_be_identified() -> None:
    request = _build_request(
        client=None,
    )

    assert _get_client_ip(request) is None
