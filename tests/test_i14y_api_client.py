"""Unit tests for the I14Y API client."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from helpers.i14y_api_client import I14YApiClient, _build_params


# ── _build_params ──────────────────────────────────────────────────────────────

def test_build_params_strips_none():
    result = _build_params(a=1, b=None, c="hello")
    assert result == {"a": "1", "c": "hello"}


def test_build_params_all_none():
    result = _build_params(a=None, b=None)
    assert result == {}


def test_build_params_converts_to_str():
    result = _build_params(page=2, pageSize=25)
    assert result == {"page": "2", "pageSize": "25"}


def test_build_params_preserves_lists():
    result = _build_params(types=["Dataset", "Concept"], statuses=["Recorded"])
    assert result == {
        "types": ["Dataset", "Concept"],
        "statuses": ["Recorded"],
    }


# ── Context manager ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_client_raises_outside_context():
    client = I14YApiClient()
    with pytest.raises(RuntimeError, match="async context manager"):
        await client.get("/datasets")


# ── JSON response ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_returns_json_object():
    mock_response = MagicMock()
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = {"data": [{"id": "abc"}], "totalItems": 1}
    mock_response.raise_for_status = MagicMock()

    with patch("helpers.i14y_api_client.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_response)
        mock_http.aclose = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        async with I14YApiClient() as client:
            client._client = mock_http
            result = await client.get("/datasets", page=1, pageSize=5)

    assert result["totalItems"] == 1
    assert result["data"][0]["id"] == "abc"


# ── Plain-text response (TTL) ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_returns_plain_text_for_turtle():
    turtle_content = "@prefix dcat: <http://www.w3.org/ns/dcat#> ."
    mock_response = MagicMock()
    mock_response.headers = {"content-type": "text/turtle; charset=utf-8"}
    mock_response.text = turtle_content
    mock_response.raise_for_status = MagicMock()

    with patch("helpers.i14y_api_client.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_response)
        mock_http.aclose = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        async with I14YApiClient() as client:
            client._client = mock_http
            result = await client.get("/catalogs/123/dcat/exports/ttl")

    assert result["text"] == turtle_content


# ── HTTP error handling ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_handles_http_404():
    mock_response = MagicMock()
    mock_response.status_code = 404
    request = httpx.Request("GET", "https://api.i14y.admin.ch/api/public/v1/datasets/bad-id")
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError("Not found", request=request, response=mock_response)
    )

    with patch("helpers.i14y_api_client.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_response)
        mock_http.aclose = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        async with I14YApiClient() as client:
            client._client = mock_http
            result = await client.get("/datasets/bad-id")

    assert "error" in result
    assert "404" in result["error"]
