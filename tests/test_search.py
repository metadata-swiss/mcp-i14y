"""Unit tests for full_text_search_resources tool."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest


MOCK_SEARCH_RESULTS = json.dumps([
    {
        "id": "ds-001",
        "identifier": "px-x-0602010000_109",
        "type": "Dataset",
        "title": {
            "de": "Arbeitsstätten und Beschäftigte nach Kanton",
            "fr": "Etablissements et emplois selon le canton",
        },
        "description": {"fr": "Statistiques des établissements selon le canton."},
        "publisher": {"identifier": "CH1", "name": {"fr": "OFS"}},
        "registrationStatus": "Recorded",
    },
    {
        "id": "concept-001",
        "identifier": "HGDE_KT",
        "type": "Concept",
        "title": {"de": "Schweizer Kantone", "fr": "Cantons suisses"},
        "registrationStatus": "Recorded",
    },
])


@pytest.mark.asyncio
async def test_full_text_search_returns_results():
    with patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MOCK_SEARCH_RESULTS
        from mcp.server.fastmcp import FastMCP
        from tools.search import register

        mcp = FastMCP("test")
        register(mcp)
        tool = next(
            t for t in mcp._tool_manager.list_tools() if t.name == "full_text_search_resources"
        )
        result = await tool.fn(query="canton")

    parsed = json.loads(result)
    assert len(parsed) == 2
    assert parsed[0]["id"] == "ds-001"
    assert parsed[1]["identifier"] == "HGDE_KT"


@pytest.mark.asyncio
async def test_full_text_search_with_type_filter():
    with patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MOCK_SEARCH_RESULTS
        from mcp.server.fastmcp import FastMCP
        from tools.search import register

        mcp = FastMCP("test")
        register(mcp)
        tool = next(
            t for t in mcp._tool_manager.list_tools() if t.name == "full_text_search_resources"
        )
        result = await tool.fn(query="canton", types=["Concept"])

    mock_get.assert_called_once()
    call_kwargs = mock_get.call_args
    assert "Concept" in str(call_kwargs)


@pytest.mark.asyncio
async def test_full_text_search_invalid_type():
    from mcp.server.fastmcp import FastMCP
    from tools.search import register

    mcp = FastMCP("test")
    register(mcp)
    tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "full_text_search_resources")
    result = await tool.fn(query="canton", types=["InvalidType"])

    # Tool returns a dict on error path, not a JSON string.
    assert isinstance(result, dict)
    assert "error" in result
