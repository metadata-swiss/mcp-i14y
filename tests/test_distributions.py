"""Unit tests for distribution content tools."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _as_dict(result):
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"text": result}
    return {"value": result}


def _make_stream_response(content: bytes, content_type: str, status_code: int = 200):
    """Build a mock httpx streaming response."""
    mock_response = AsyncMock()
    mock_response.status_code = status_code
    mock_response.headers = {"content-type": content_type}

    def mock_raise_for_status():
        if status_code >= 400:
            import httpx
            request = MagicMock()
            raise httpx.HTTPStatusError(
                f"HTTP {status_code}",
                request=request,
                response=mock_response,
            )

    mock_response.raise_for_status = mock_raise_for_status

    async def aiter_bytes(chunk_size=4096):
        for i in range(0, len(content), chunk_size):
            yield content[i : i + chunk_size]

    mock_response.aiter_bytes = aiter_bytes
    return mock_response


@pytest.mark.asyncio
async def test_get_dataset_distribution_content_json():
    payload = {"records": [{"id": 1, "value": "test"}]}
    content = json.dumps(payload).encode()
    dataset_response = {
        "data": {
            "id": "ds-1",
            "distributions": [
                {"id": "dist-1", "downloadUrl": {"uri": "https://example.com/data.json"}}
            ],
        }
    }

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=_make_stream_response(content, "application/json"))
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get,
        patch("httpx.AsyncClient.stream", return_value=mock_cm),
    ):
        mock_get.return_value = dataset_response
        from mcp.server.fastmcp import FastMCP
        from tools.distributions import register

        mcp = FastMCP("test")
        register(mcp)
        tool = next(
            t
            for t in mcp._tool_manager.list_tools()
            if t.name == "get_dataset_distribution_content"
        )
        result = await tool.fn(dataset_id="ds-1")

    parsed = _as_dict(result)
    assert parsed["data"]["records"][0]["id"] == 1
    assert parsed["dataset_id"] == "ds-1"


@pytest.mark.asyncio
async def test_get_dataset_distribution_content_csv_by_id():
    csv_content = b"id,name,value\n1,Zurich,42\n2,Berne,17\n"
    dataset_response = {
        "data": {
            "id": "ds-1",
            "distributions": [
                {"id": "a", "downloadUrl": {"uri": "https://example.com/a.csv"}},
                {"id": "b", "downloadUrl": {"uri": "https://example.com/b.csv"}},
            ],
        }
    }

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=_make_stream_response(csv_content, "text/csv"))
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get,
        patch("httpx.AsyncClient.stream", return_value=mock_cm),
    ):
        mock_get.return_value = dataset_response
        from mcp.server.fastmcp import FastMCP
        from tools.distributions import register

        mcp = FastMCP("test")
        register(mcp)
        tool = next(
            t
            for t in mcp._tool_manager.list_tools()
            if t.name == "get_dataset_distribution_content"
        )
        result = await tool.fn(dataset_id="ds-1", distribution_id="b")

    parsed = _as_dict(result)
    assert "Zurich" in parsed["text"]
    assert parsed["distribution_id"] == "b"


@pytest.mark.asyncio
async def test_get_dataset_distribution_content_truncated():
    # 300 KB content, limit 200 KB
    large_content = b"x" * (300 * 1024)
    dataset_response = {
        "data": {
            "id": "ds-1",
            "distributions": [
                {"id": "dist-1", "downloadUrl": {"uri": "https://example.com/big.txt"}}
            ],
        }
    }

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=_make_stream_response(large_content, "text/plain"))
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get,
        patch("httpx.AsyncClient.stream", return_value=mock_cm),
    ):
        mock_get.return_value = dataset_response
        from mcp.server.fastmcp import FastMCP
        from tools.distributions import register

        mcp = FastMCP("test")
        register(mcp)
        tool = next(
            t
            for t in mcp._tool_manager.list_tools()
            if t.name == "get_dataset_distribution_content"
        )
        result = await tool.fn(dataset_id="ds-1", max_kb=200)

    parsed = _as_dict(result)
    assert parsed["truncated"] is True
    assert "warning" in parsed
    assert len(parsed.get("text", "").encode()) <= 200 * 1024 + 500


@pytest.mark.asyncio
async def test_get_dataset_distribution_content_binary_rejected():
    dataset_response = {
        "data": {
            "id": "ds-1",
            "distributions": [
                {"id": "dist-1", "downloadUrl": {"uri": "https://example.com/doc.pdf"}}
            ],
        }
    }

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(
        return_value=_make_stream_response(b"%PDF-1.4...", "application/pdf")
    )
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("helpers.i14y_api_client.I14YApiClient.get", new_callable=AsyncMock) as mock_get,
        patch("httpx.AsyncClient.stream", return_value=mock_cm),
    ):
        mock_get.return_value = dataset_response
        from mcp.server.fastmcp import FastMCP
        from tools.distributions import register

        mcp = FastMCP("test")
        register(mcp)
        tool = next(
            t
            for t in mcp._tool_manager.list_tools()
            if t.name == "get_dataset_distribution_content"
        )
        result = await tool.fn(dataset_id="ds-1")

    parsed = _as_dict(result)
    assert "error" in parsed
    assert "binary" in parsed["error"].lower() or "pdf" in parsed["error"].lower()


@pytest.mark.asyncio
async def test_get_distribution_content_tool_not_exposed():
    from mcp.server.fastmcp import FastMCP
    from tools.distributions import register

    mcp = FastMCP("test")
    register(mcp)
    tool_names = [t.name for t in mcp._tool_manager.list_tools()]
    assert "get_distribution_content" not in tool_names
    assert "get_dataset_distribution_content" in tool_names


