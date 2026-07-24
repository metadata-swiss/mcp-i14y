"""MCP tool for reading the content of a DCAT distribution."""

from __future__ import annotations

import json
from typing import Any

import httpx

from helpers.i14y_api_client import I14YApiClient
from mcp.server.fastmcp import FastMCP

__all__ = ["register"]

VERSION = "0.1.0"
USER_AGENT = f"mcp-i14y/{VERSION} (https://github.com/I14Y-ch/mcp-i14y)"

# Content types that are safe to read as text
_TEXT_TYPES = {
    "application/json",
    "application/ld+json",
    "application/geo+json",
    "text/csv",
    "text/plain",
    "text/xml",
    "application/xml",
    "application/rdf+xml",
    "text/turtle",
    "application/sparql-results+json",
    "application/sparql-results+xml",
}

# Content types that are binary and cannot be meaningfully returned to an LLM
_BINARY_TYPES = {
    "application/pdf",
    "application/zip",
    "application/gzip",
    "application/x-tar",
    "application/octet-stream",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument",
    "image/",
    "audio/",
    "video/",
}


def _is_binary(content_type: str) -> bool:
    ct = content_type.split(";")[0].strip().lower()
    return any(ct.startswith(bt) for bt in _BINARY_TYPES)


def _is_text(content_type: str) -> bool:
    ct = content_type.split(";")[0].strip().lower()
    return ct.startswith("text/") or any(ct == t for t in _TEXT_TYPES)


def _extract_download_url(distribution: dict[str, Any]) -> str | None:
    download_url = distribution.get("downloadUrl")
    if isinstance(download_url, dict):
        uri = download_url.get("uri")
        return uri if isinstance(uri, str) and uri else None
    if isinstance(download_url, str) and download_url:
        return download_url
    return None


async def _fetch_distribution_from_url(download_url: str, max_kb: int) -> dict[str, Any]:
    max_bytes = max_kb * 1024

    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=30.0,
        ) as client:
            async with client.stream("GET", download_url) as response:
                response.raise_for_status()

                content_type = response.headers.get("content-type", "")
                ct_base = content_type.split(";")[0].strip().lower()

                if _is_binary(content_type):
                    return {
                        "error": (
                            f"Binary content type '{ct_base}' cannot be returned as text."
                        ),
                        "url": download_url,
                        "content_type": content_type,
                    }

                if not _is_text(content_type):
                    return {
                        "error": (
                            f"Unsupported content type '{ct_base}'. "
                            "Only text-like distributions can be returned."
                        ),
                        "url": download_url,
                        "content_type": content_type,
                    }

                chunks: list[bytes] = []
                total = 0
                truncated = False

                async for chunk in response.aiter_bytes(chunk_size=4096):
                    if total + len(chunk) > max_bytes:
                        remaining = max_bytes - total
                        chunks.append(chunk[:remaining])
                        truncated = True
                        break
                    chunks.append(chunk)
                    total += len(chunk)

                text = b"".join(chunks).decode("utf-8", errors="replace")

                result: dict[str, Any] = {
                    "url": download_url,
                    "content_type": content_type,
                    "truncated": truncated,
                    "max_kb": max_kb,
                }

                if "json" in ct_base:
                    try:
                        result["data"] = json.loads(text)
                    except Exception:
                        result["text"] = text
                else:
                    result["text"] = text

                if truncated:
                    result["warning"] = (
                        f"Content exceeds {max_kb} KB. Only the first {max_kb} KB "
                        "are shown."
                    )

                return result

    except httpx.HTTPStatusError as exc:
        return {
            "error": f"HTTP {exc.response.status_code} fetching distribution",
            "url": download_url,
        }
    except httpx.RequestError as exc:
        return {
            "error": f"Network error fetching distribution: {exc}",
            "url": download_url,
        }


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def get_dataset_distribution_content(
        dataset_id: str,
        distribution_index: int = 0,
        distribution_id: str | None = None,
        max_kb: int = 200,
    ) -> dict[str, Any]:
        """Fetch distribution content from a dataset using a safe selector.

        This tool resolves the distribution URL from I14Y dataset metadata
        (`get_dataset`) instead of accepting an arbitrary user-provided URL.

        Args:
            dataset_id: UUID of the dataset on I14Y.
            distribution_index: Zero-based index in dataset.distributions.
            distribution_id: Optional distribution ID to select explicitly.
            max_kb: Maximum content size to return in kilobytes.

        Returns:
            Structured object containing content metadata and either parsed JSON
            or text content.
        """
        if distribution_index < 0:
            return {
                "error": "distribution_index must be >= 0",
                "distribution_index": distribution_index,
            }

        async with I14YApiClient() as client:
            dataset_response = await client.get(
                f"/datasets/{dataset_id}",
                resource_type="dataset",
            )

        if not isinstance(dataset_response, dict):
            return {"error": "Unexpected dataset response format."}

        if "error" in dataset_response:
            return dataset_response

        dataset_data: Any
        if isinstance(dataset_response.get("distributions"), list):
            dataset_data = dataset_response
        else:
            dataset_data = dataset_response.get("data")
            if isinstance(dataset_data, dict) and isinstance(dataset_data.get("data"), dict):
                dataset_data = dataset_data["data"]

        if not isinstance(dataset_data, dict):
            return {
                "error": "Dataset payload missing or invalid for dataset-by-id response.",
                "dataset_id": dataset_id,
            }

        distributions = dataset_data.get("distributions")
        if not isinstance(distributions, list) or not distributions:
            return {
                "error": "Dataset has no distributions.",
                "dataset_id": dataset_id,
            }

        selected_distribution: dict[str, Any] | None = None
        selected_index: int | None = None

        if distribution_id:
            for i, distribution in enumerate(distributions):
                if isinstance(distribution, dict) and distribution.get("id") == distribution_id:
                    selected_distribution = distribution
                    selected_index = i
                    break
            if selected_distribution is None:
                return {
                    "error": "distribution_id not found in dataset distributions.",
                    "dataset_id": dataset_id,
                    "distribution_id": distribution_id,
                }
        else:
            if distribution_index >= len(distributions):
                return {
                    "error": "distribution_index out of range.",
                    "dataset_id": dataset_id,
                    "distribution_index": distribution_index,
                    "distribution_count": len(distributions),
                }
            distribution = distributions[distribution_index]
            if not isinstance(distribution, dict):
                return {
                    "error": "Invalid distribution entry format.",
                    "dataset_id": dataset_id,
                    "distribution_index": distribution_index,
                }
            selected_distribution = distribution
            selected_index = distribution_index

        download_url = _extract_download_url(selected_distribution)
        if not download_url:
            return {
                "error": "Selected distribution has no valid downloadUrl.",
                "dataset_id": dataset_id,
                "distribution_index": selected_index,
                "distribution_id": selected_distribution.get("id"),
            }

        result = await _fetch_distribution_from_url(download_url, max_kb)
        if isinstance(result, dict):
            result.setdefault("dataset_id", dataset_id)
            result.setdefault("distribution_index", selected_index)
            result.setdefault("distribution_id", selected_distribution.get("id"))
        return result
