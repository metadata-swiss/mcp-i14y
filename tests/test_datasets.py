"""Unit tests for dataset tools."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest


MOCK_DATASETS_RESPONSE = json.dumps({
    "data": [
        {
            "id": "ds-001",
            "title": {"de": "Bevölkerungsstatistik", "fr": "Statistique démographique"},
            "publisher": {"identifier": "BFS"},
        }
    ],
    "totalItems": 1,
    "page": 1,
    "pageSize": 25,
})

MOCK_DATASET_DETAIL = json.dumps({
    "id": "ds-001",
    "title": {"de": "Bevölkerungsstatistik"},
    "description": {"de": "Statistiken zur Bevölkerung der Schweiz"},
    "registrationStatus": "Standard",
    "publicationLevel": "Public",
})

MOCK_DATASET_BY_IDENTIFIER_RESPONSE = json.dumps({
    "data": [
        {
            "id": "ds-001",
            "identifier": "px-x-0602010000_109",
            "title": {"de": "Bevölkerungsstatistik"},
        }
    ]
})

MOCK_STRUCTURE = "@prefix dcat: <http://www.w3.org/ns/dcat#> ."


@pytest.mark.asyncio
async def test_list_datasets_no_filters():
    with patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MOCK_DATASETS_RESPONSE
        from tools.datasets import register
        from mcp.server.fastmcp import FastMCP
        mcp = FastMCP("test")
        register(mcp)

        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "list_datasets")
        result = await tool.fn()

    parsed = json.loads(result)
    assert parsed["totalItems"] == 1
    assert parsed["data"][0]["id"] == "ds-001"


@pytest.mark.asyncio
async def test_list_datasets_with_publisher_filter():
    with patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MOCK_DATASETS_RESPONSE
        from tools.datasets import register
        from mcp.server.fastmcp import FastMCP
        mcp = FastMCP("test")
        register(mcp)

        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "list_datasets")
        result = await tool.fn(publisher_identifier="BFS")

    mock_get.assert_called_once()
    call_kwargs = mock_get.call_args
    assert "publisherIdentifier" in str(call_kwargs) or "BFS" in str(call_kwargs)


@pytest.mark.asyncio
async def test_list_datasets_with_structure_filter():
    with patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MOCK_DATASETS_RESPONSE
        from tools.datasets import register
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        register(mcp)

        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "list_datasets")
        await tool.fn(with_structure=True)

    mock_get.assert_called_once()
    call_args, call_kwargs = mock_get.call_args
    assert call_args[0] == "/search"
    assert call_kwargs["types"] == ["Dataset"]
    assert call_kwargs["structure"] == "WithStructure"


@pytest.mark.asyncio
async def test_list_datasets_with_structure_filter_false():
    with patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MOCK_DATASETS_RESPONSE
        from tools.datasets import register
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        register(mcp)

        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "list_datasets")
        await tool.fn(with_structure=False)

    mock_get.assert_called_once()
    call_args, call_kwargs = mock_get.call_args
    assert call_args[0] == "/search"
    assert call_kwargs["structure"] == "WithoutStructure"


@pytest.mark.asyncio
async def test_get_dataset():
    with patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MOCK_DATASET_DETAIL
        from tools.datasets import register
        from mcp.server.fastmcp import FastMCP
        mcp = FastMCP("test")
        register(mcp)

        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_dataset")
        result = await tool.fn(dataset_id="ds-001")

    parsed = json.loads(result)
    assert parsed["id"] == "ds-001"
    assert parsed["registrationStatus"] == "Standard"


@pytest.mark.asyncio
async def test_get_dataset_structure_invalid_format():
    from tools.datasets import register
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("test")
    register(mcp)

    tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_dataset_structure")
    result = await tool.fn(dataset_id="ds-001", format="xml")

    # Tool returns a dict on error path, not a JSON string.
    assert isinstance(result, dict)
    assert "error" in result


@pytest.mark.asyncio
async def test_get_dataset_structure_valid():
    with patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MOCK_STRUCTURE
        from tools.datasets import register
        from mcp.server.fastmcp import FastMCP
        mcp = FastMCP("test")
        register(mcp)

        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_dataset_structure")
        result = await tool.fn(dataset_id="ds-001", format="Ttl")

    assert "dcat" in result


@pytest.mark.asyncio
async def test_get_dataset_by_identifier():
    with patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get:
        # I14YApiClient.get returns a decoded dict, not a JSON string.
        mock_get.return_value = json.loads(MOCK_DATASET_BY_IDENTIFIER_RESPONSE)
        from tools.datasets import register
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test")
        register(mcp)

        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "get_dataset_by_identifier")
        result = await tool.fn(identifier="px-x-0602010000_109")

    # Tool returns data[0] directly (a dict).
    assert isinstance(result, dict)
    assert result["identifier"] == "px-x-0602010000_109"


@pytest.mark.asyncio
async def test_check_dataset_has_structure_true():
    with patch("helpers.core_api_client.CoreApiClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = "true"
        from mcp.server.fastmcp import FastMCP
        from tools.datasets import register

        mcp = FastMCP("test")
        register(mcp)
        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "check_dataset_has_structure")
        result = await tool.fn(dataset_id="ds-001")

    assert result == "true"


@pytest.mark.asyncio
async def test_check_dataset_has_structure_false():
    with patch("helpers.core_api_client.CoreApiClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = "false"
        from mcp.server.fastmcp import FastMCP
        from tools.datasets import register

        mcp = FastMCP("test")
        register(mcp)
        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "check_dataset_has_structure")
        result = await tool.fn(dataset_id="ds-no-struct")

    assert result == "false"
