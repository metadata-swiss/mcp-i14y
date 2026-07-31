"""Unit tests for dataservice tools."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest


MOCK_DATASERVICES_RESPONSE = json.dumps({
    "data": [
        {
            "id": "svc-001",
            "title": {"de": "Geodaten API", "fr": "API données géographiques"},
            "endpointUrl": "https://geo.admin.ch/api/v1",
            "publisher": {"identifier": "swisstopo"},
        }
    ],
    "totalItems": 1,
    "page": 1,
    "pageSize": 25,
})

MOCK_DATASERVICE_DETAIL = json.dumps({
    "id": "svc-001",
    "title": {"de": "Geodaten API"},
    "endpointUrl": "https://geo.admin.ch/api/v1",
    "registrationStatus": "Standard",
    "publicationLevel": "Public",
})

MOCK_DATASERVICE_BY_IDENTIFIER_RESPONSE = json.dumps({
    "data": [
        {
            "id": "svc-001",
            "identifier": "geo-api",
            "title": {"de": "Geodaten API"},
        }
    ]
})


@pytest.mark.asyncio
async def test_list_dataservices():
    with patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MOCK_DATASERVICES_RESPONSE
        from tools.dataservices import register
        from mcp.server.fastmcp import FastMCP
        mcp = FastMCP("test")
        register(mcp)

        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "list_dataservices")
        result = await tool.fn()

    parsed = json.loads(result)
    assert parsed["totalItems"] == 1
    assert parsed["data"][0]["publisher"]["identifier"] == "swisstopo"


@pytest.mark.asyncio
async def test_get_dataservice():
    with patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MOCK_DATASERVICE_DETAIL
        from tools.dataservices import register
        from mcp.server.fastmcp import FastMCP
        mcp = FastMCP("test")
        register(mcp)

        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_dataservice")
        result = await tool.fn(dataservice_id="svc-001")

    parsed = json.loads(result)
    assert parsed["id"] == "svc-001"
    assert "endpointUrl" in parsed


@pytest.mark.asyncio
async def test_get_dataservice_by_identifier():
    with patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get:
        # I14YApiClient.get returns a decoded dict, not a JSON string.
        mock_get.return_value = json.loads(MOCK_DATASERVICE_BY_IDENTIFIER_RESPONSE)
        from tools.dataservices import register
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        register(mcp)

        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_dataservice_by_identifier")
        result = await tool.fn(identifier="geo-api")

    # Tool returns data[0] directly (a dict).
    assert isinstance(result, dict)
    assert result["identifier"] == "geo-api"
