"""Unit tests for CORE API concept tools."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest


MOCK_CONCEPT_BY_ID = json.dumps([
    {
        "id": "concept-uuid-001",
        "identifier": "HGDE_KT",
        "version": "1.0.0",
        "name": {"de": "Schweizer Kantone", "fr": "Cantons suisses", "en": "Swiss cantons"},
        "conceptType": "CodeList",
        "registrationStatus": "Recorded",
    }
])

MOCK_CODELIST_ENTRIES = json.dumps({
    "data": [
        {"code": "1", "label": {"de": "Zürich", "fr": "Zurich"}, "id": "entry-001"},
        {"code": "2", "label": {"de": "Bern", "fr": "Berne"}, "id": "entry-002"},
    ],
    "totalItems": 26,
    "page": 1,
    "pageSize": 100,
})

MOCK_ENTRY_BY_CODE = json.dumps({
    "code": "1",
    "label": {"de": "Zürich", "fr": "Zurich"},
    "id": "entry-001",
})

MOCK_CHILDREN = json.dumps({
    "data": [
        {"code": "101", "label": {"de": "Bezirk Zürich"}, "parentCode": "1"},
    ],
    "totalItems": 1,
    "page": 1,
    "pageSize": 100,
})

MOCK_SEARCH_ENTRIES = json.dumps({
    "data": [
        {"code": "1", "label": {"fr": "Zurich"}, "id": "entry-001"},
    ],
    "totalItems": 1,
})


@pytest.mark.asyncio
async def test_get_concept_by_identifier():
    with patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get:
        # I14YApiClient.get returns a decoded dict, not a JSON string.
        mock_get.return_value = {"data": json.loads(MOCK_CONCEPT_BY_ID)}
        from mcp.server.fastmcp import FastMCP
        from tools.concepts import register

        mcp = FastMCP("test")
        register(mcp)
        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_concept_by_identifier")
        result = await tool.fn(identifier="HGDE_KT")

    # Tool returns the unwrapped "data" list directly.
    assert isinstance(result, list)
    assert result[0]["identifier"] == "HGDE_KT"
    assert result[0]["conceptType"] == "CodeList"


@pytest.mark.asyncio
async def test_get_codelist_entries():
    with patch("helpers.core_api_client.CoreApiClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MOCK_CODELIST_ENTRIES
        from mcp.server.fastmcp import FastMCP
        from tools.concepts import register

        mcp = FastMCP("test")
        register(mcp)
        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_codelist_entries")
        result = await tool.fn(concept_id="concept-uuid-001")

    parsed = json.loads(result)
    assert parsed["totalItems"] == 26
    assert parsed["data"][0]["code"] == "1"


@pytest.mark.asyncio
async def test_get_codelist_entry_by_code():
    with patch("helpers.core_api_client.CoreApiClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MOCK_ENTRY_BY_CODE
        from mcp.server.fastmcp import FastMCP
        from tools.concepts import register

        mcp = FastMCP("test")
        register(mcp)
        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_codelist_entry_by_code")
        result = await tool.fn(concept_id="concept-uuid-001", code="1")

    parsed = json.loads(result)
    assert parsed["code"] == "1"
    assert parsed["label"]["fr"] == "Zurich"


@pytest.mark.asyncio
async def test_get_codelist_entries_children():
    with patch("helpers.core_api_client.CoreApiClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MOCK_CHILDREN
        from mcp.server.fastmcp import FastMCP
        from tools.concepts import register

        mcp = FastMCP("test")
        register(mcp)
        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_codelist_entries_children")
        result = await tool.fn(concept_id="concept-uuid-001", parent_code="1")

    mock_get.assert_called_once()
    assert "parentCode" in str(mock_get.call_args)
    parsed = json.loads(result)
    assert parsed["data"][0]["parentCode"] == "1"


@pytest.mark.asyncio
async def test_search_codelist_entries():
    with patch("helpers.core_api_client.CoreApiClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MOCK_SEARCH_ENTRIES
        from mcp.server.fastmcp import FastMCP
        from tools.concepts import register

        mcp = FastMCP("test")
        register(mcp)
        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "search_codelist_entries")
        result = await tool.fn(concept_id="concept-uuid-001", query="Zurich", language="fr")

    parsed = json.loads(result)
    assert parsed["data"][0]["label"]["fr"] == "Zurich"
