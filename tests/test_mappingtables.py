"""Unit tests for mapping table tools."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest


MOCK_MAPPINGTABLES_RESPONSE = json.dumps({
    "data": [
        {
            "id": "mt-001",
            "name": {
                "de": "Kantone alt → neu",
                "fr": "Cantons ancien → nouveau",
            },
            "description": {"fr": "Table de correspondance des codes cantonaux."},
            "version": "1.0.0",
            "source": {"uri": "https://www.i14y.admin.ch/concepts/HGDE_KT_OLD", "name": {"fr": "Anciens codes cantonaux"}},
            "target": {"uri": "https://www.i14y.admin.ch/concepts/HGDE_KT", "name": {"fr": "Cantons suisses"}},
            "publisher": {"identifier": "CH1"},
            "registrationStatus": "Recorded",
        }
    ],
    "totalItems": 1,
    "page": 1,
    "pageSize": 25,
})

MOCK_MAPPINGTABLE_DETAIL = json.dumps({
    "data": {
        "id": "mt-001",
        "name": {"fr": "Cantons ancien → nouveau"},
        "description": {"fr": "Table de correspondance des codes cantonaux."},
        "version": "1.0.0",
        "source": {"uri": "https://www.i14y.admin.ch/concepts/HGDE_KT_OLD"},
        "target": {"uri": "https://www.i14y.admin.ch/concepts/HGDE_KT"},
        "publisher": {"identifier": "CH1"},
        "registrationStatus": "Recorded",
    }
})

MOCK_RELATIONS_JSON = json.dumps([
    {"sourceCode": "01", "targetCode": "1", "sourceLabel": {"fr": "Zurich (ancien)"}, "targetLabel": {"fr": "Zurich"}},
    {"sourceCode": "02", "targetCode": "2", "sourceLabel": {"fr": "Berne (ancien)"}, "targetLabel": {"fr": "Berne"}},
])

MOCK_RELATIONS_CSV = "sourceCode,targetCode,sourceLabel_fr,targetLabel_fr\n01,1,Zurich (ancien),Zurich\n02,2,Berne (ancien),Berne\n"


@pytest.mark.asyncio
async def test_list_mappingtables_no_filters():
    with patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MOCK_MAPPINGTABLES_RESPONSE
        from mcp.server.fastmcp import FastMCP
        from tools.mappingtables import register

        mcp = FastMCP("test")
        register(mcp)
        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "list_mappingtables")
        result = await tool.fn()

    parsed = json.loads(result)
    assert parsed["totalItems"] == 1
    assert parsed["data"][0]["id"] == "mt-001"


@pytest.mark.asyncio
async def test_list_mappingtables_with_publisher_filter():
    with patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MOCK_MAPPINGTABLES_RESPONSE
        from mcp.server.fastmcp import FastMCP
        from tools.mappingtables import register

        mcp = FastMCP("test")
        register(mcp)
        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "list_mappingtables")
        result = await tool.fn(publisher_identifier="CH1")

    mock_get.assert_called_once()
    assert "CH1" in str(mock_get.call_args)


@pytest.mark.asyncio
async def test_get_mappingtable():
    with patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MOCK_MAPPINGTABLE_DETAIL
        from mcp.server.fastmcp import FastMCP
        from tools.mappingtables import register

        mcp = FastMCP("test")
        register(mcp)
        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_mappingtable")
        result = await tool.fn(mappingtable_id="mt-001")

    parsed = json.loads(result)
    assert parsed["data"]["id"] == "mt-001"
    assert parsed["data"]["registrationStatus"] == "Recorded"


@pytest.mark.asyncio
async def test_get_mappingtable_relations_json():
    with patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MOCK_RELATIONS_JSON
        from mcp.server.fastmcp import FastMCP
        from tools.mappingtables import register

        mcp = FastMCP("test")
        register(mcp)
        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_mappingtable_relations")
        result = await tool.fn(mappingtable_id="mt-001", format="Json")

    parsed = json.loads(result)
    assert len(parsed) == 2
    assert parsed[0]["sourceCode"] == "01"
    assert parsed[0]["targetCode"] == "1"


@pytest.mark.asyncio
async def test_get_mappingtable_relations_csv():
    with patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MOCK_RELATIONS_CSV
        from mcp.server.fastmcp import FastMCP
        from tools.mappingtables import register

        mcp = FastMCP("test")
        register(mcp)
        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_mappingtable_relations")
        result = await tool.fn(mappingtable_id="mt-001", format="Csv")

    assert "sourceCode" in result
    assert "01" in result
    assert "Zurich" in result


@pytest.mark.asyncio
async def test_get_mappingtable_relations_invalid_format():
    from mcp.server.fastmcp import FastMCP
    from tools.mappingtables import register

    mcp = FastMCP("test")
    register(mcp)
    tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_mappingtable_relations")
    result = await tool.fn(mappingtable_id="mt-001", format="xml")

    # Tool returns a dict on error path, not a JSON string.
    assert isinstance(result, dict)
    assert "error" in result
