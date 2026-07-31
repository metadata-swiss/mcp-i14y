"""Unit tests for concept tools."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest


MOCK_CONCEPTS_RESPONSE = json.dumps({
    "data": [
        {
            "id": "con-001",
            "identifier": "CH-canton-codes",
            "title": {"de": "Kantonscodes", "fr": "Codes cantonaux"},
        }
    ],
    "totalItems": 1,
    "page": 1,
    "pageSize": 25,
})

MOCK_CONCEPT_DETAIL = json.dumps({
    "id": "con-001",
    "identifier": "CH-canton-codes",
    "title": {"de": "Kantonscodes"},
    "type": "CodeList",
    "registrationStatus": "Standard",
})

MOCK_CODELIST_JSON = json.dumps([
    {"code": "ZH", "label": {"de": "Zürich", "fr": "Zurich"}},
    {"code": "BE", "label": {"de": "Bern", "fr": "Berne"}},
])

MOCK_CODELIST_CSV = "code,label_de,label_fr\nZH,Zürich,Zurich\nBE,Bern,Berne\n"


@pytest.mark.asyncio
async def test_list_concepts():
    with patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MOCK_CONCEPTS_RESPONSE
        from tools.concepts import register
        from mcp.server.fastmcp import FastMCP
        mcp = FastMCP("test")
        register(mcp)

        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "list_concepts")
        result = await tool.fn()

    parsed = json.loads(result)
    assert parsed["totalItems"] == 1
    assert parsed["data"][0]["identifier"] == "CH-canton-codes"


@pytest.mark.asyncio
async def test_get_concept_without_entries():
    with patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MOCK_CONCEPT_DETAIL
        from tools.concepts import register
        from mcp.server.fastmcp import FastMCP
        mcp = FastMCP("test")
        register(mcp)

        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_concept")
        result = await tool.fn(concept_id="con-001", include_codelist_entries=False)

    parsed = json.loads(result)
    assert parsed["type"] == "CodeList"


@pytest.mark.asyncio
async def test_get_concept_codelist_json():
    with patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MOCK_CODELIST_JSON
        from tools.concepts import register
        from mcp.server.fastmcp import FastMCP
        mcp = FastMCP("test")
        register(mcp)

        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_concept_codelist")
        result = await tool.fn(concept_id="con-001", format="json")

    parsed = json.loads(result)
    assert len(parsed) == 2
    assert parsed[0]["code"] == "ZH"


@pytest.mark.asyncio
async def test_get_concept_codelist_csv():
    with patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MOCK_CODELIST_CSV
        from tools.concepts import register
        from mcp.server.fastmcp import FastMCP
        mcp = FastMCP("test")
        register(mcp)

        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_concept_codelist")
        result = await tool.fn(concept_id="con-001", format="csv")

    assert "ZH" in result
    assert "Zürich" in result


@pytest.mark.asyncio
async def test_get_concept_codelist_invalid_format():
    from tools.concepts import register
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("test")
    register(mcp)

    tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_concept_codelist")
    result = await tool.fn(concept_id="con-001", format="xml")

    # Tool returns a dict on error path, not a JSON string.
    assert isinstance(result, dict)
    assert "error" in result
