"""Unit tests for public service tools."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest


MOCK_PUBLICSERVICES_RESPONSE = json.dumps({
    "data": [
        {
            "id": "ps-001",
            "title": {"de": "Steuererklärung einreichen", "fr": "Déposer une déclaration fiscale"},
            "publisher": {"identifier": "EFD"},
        }
    ],
    "totalItems": 1,
    "page": 1,
    "pageSize": 25,
})

MOCK_PUBLICSERVICE_DETAIL = json.dumps({
    "id": "ps-001",
    "title": {"de": "Steuererklärung einreichen"},
    "description": {"de": "Einreichung der jährlichen Steuererklärung"},
    "registrationStatus": "Recorded",
    "publicationLevel": "Public",
})

MOCK_PUBLICSERVICE_BY_IDENTIFIER_RESPONSE = json.dumps({
    "data": [
        {
            "id": "ps-001",
            "identifier": "tax-declaration-service",
            "title": {"de": "Steuererklärung einreichen"},
        }
    ]
})


@pytest.mark.asyncio
async def test_list_publicservices():
    with patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MOCK_PUBLICSERVICES_RESPONSE
        from tools.publicservices import register
        from mcp.server.fastmcp import FastMCP
        mcp = FastMCP("test")
        register(mcp)

        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "list_publicservices")
        result = await tool.fn()

    parsed = json.loads(result)
    assert parsed["totalItems"] == 1
    assert parsed["data"][0]["id"] == "ps-001"


@pytest.mark.asyncio
async def test_get_publicservice():
    with patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MOCK_PUBLICSERVICE_DETAIL
        from tools.publicservices import register
        from mcp.server.fastmcp import FastMCP
        mcp = FastMCP("test")
        register(mcp)

        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_publicservice")
        result = await tool.fn(publicservice_id="ps-001")

    parsed = json.loads(result)
    assert parsed["id"] == "ps-001"
    assert parsed["registrationStatus"] == "Recorded"


@pytest.mark.asyncio
async def test_get_publicservice_by_identifier():
    with patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get:
        # I14YApiClient.get returns a decoded dict, not a JSON string.
        mock_get.return_value = json.loads(MOCK_PUBLICSERVICE_BY_IDENTIFIER_RESPONSE)
        from tools.publicservices import register
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        register(mcp)

        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_publicservice_by_identifier")
        result = await tool.fn(identifier="tax-declaration-service")

    # Tool returns data[0] directly (a dict).
    assert isinstance(result, dict)
    assert result["identifier"] == "tax-declaration-service"
