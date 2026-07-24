"""Async HTTP client for the Swiss I14Y CORE API."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from helpers.iri_links import (
    enrich_catalog_search_result_with_iris,
    enrich_response_with_iris,
)

__all__ = ["CoreApiClient"]

logger = logging.getLogger(__name__)

_CORE_BASE_URL = "https://core.i14y.c.bfs.admin.ch/api"
VERSION = "0.1.0"
USER_AGENT = f"mcp-i14y/{VERSION} (https://github.com/I14Y-ch/mcp-i14y)"

# Content types returned as plain text (not parsed as JSON)
_PLAIN_TEXT_TYPES = {"text/turtle", "application/rdf+xml", "text/csv", "text/plain"}


def _build_params(**kwargs: object) -> dict[str, str | list[str]]:
    """Build a query-parameter dict, dropping any None values.

    List values are sent as repeated query parameters by httpx.
    """
    result: dict[str, str | list[str]] = {}

    for k, v in kwargs.items():
        if v is None:
            continue

        if isinstance(v, list):
            result[k] = [str(i) for i in v if i is not None]
        else:
            result[k] = str(v)

    return result


def _int_header(headers: httpx.Headers, name: str) -> int | None:
    value = headers.get(name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _pagination_from_headers(headers: httpx.Headers) -> dict[str, Any] | None:
    """Extract I14Y pagination metadata from x-paging-* response headers."""
    page = _int_header(headers, "x-paging-page")
    page_size = _int_header(headers, "x-paging-pagesize")
    total_pages = _int_header(headers, "x-paging-totalpages")
    total_rows = _int_header(headers, "x-paging-totalrows")

    if page is None and page_size is None and total_pages is None and total_rows is None:
        return None

    has_more = page is not None and total_pages is not None and page < total_pages

    return {
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "total_rows": total_rows,
        "has_more": has_more,
        "next_page": page + 1 if has_more and page is not None else None,
    }


def _extract_items(payload: Any) -> list[Any]:
    """Extract list items from common I14Y response shapes."""
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in ("data", "items", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return value

    return []


def _wrap_json_with_pagination(data: Any, headers: httpx.Headers, path: str) -> dict[str, Any]:
    """Wrap JSON API responses with pagination metadata when available."""
    pagination = _pagination_from_headers(headers)

    if pagination is None:
        return data

    next_page = pagination["next_page"]
    items = _extract_items(data)

    return {
        "pagination": pagination,
        "pagination_instruction": (
            f"More pages are available for {path}. Call the same tool again "
            f"with page={next_page} unless enough relevant results have been collected."
            if pagination["has_more"]
            else "No more pages available."
        ),
        "data": items if items else data,
    }


class CoreApiClient:
    """Reusable async HTTP client for the I14Y CORE API.

    The CORE API (https://core.i14y.c.bfs.admin.ch/api) provides richer endpoints
    than the public API, including full-text search, identifier-based lookups,
    and hierarchical codelist navigation.

    Usage::
        async with CoreApiClient() as client:
            data = await client.get("/Catalog/search", query="canton")
    """

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "CoreApiClient":
        self._client = httpx.AsyncClient(
            base_url=_CORE_BASE_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=30.0,
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client:
            await self._client.aclose()
        self._client = None

    async def _get_response(self, path: str, **params: object) -> httpx.Response:
        """Perform a raw GET request and return the httpx response."""
        if self._client is None:
            raise RuntimeError("CoreApiClient must be used as an async context manager.")

        query = _build_params(**params)
        logger.debug("CORE GET %s params=%s", path, query)

        response = await self._client.get(path, params=query)
        response.raise_for_status()
        return response

    async def get(
        self,
        path: str,
        resource_type: str | None = None,
        catalog_search: bool = False,
        **params: object,
    ) -> dict[str, Any]:
        """Perform a GET request and return a structured object.

        Args:
            path: API path relative to the base URL, e.g. "/Catalog/search".
            **params: Query parameters; None values are stripped automatically.
                List values are sent as repeated query parameters.

        Returns:
            A dict. Non-paginated JSON responses are returned as-is.
            Paginated endpoints return ``{"pagination": ..., "data": ...}``
            where ``data`` is the extracted item list when available.
            Text/RDF/CSV responses are returned as
            ``{"content_type": ..., "text": ...}``.
        """
        try:
            response = await self._get_response(path, **params)
        except httpx.HTTPStatusError as exc:
            return {
                "error": f"I14Y CORE API returned HTTP {exc.response.status_code}",
                "url": str(exc.request.url),
            }
        except httpx.RequestError as exc:
            return {"error": f"Network error while contacting I14Y CORE API: {exc}"}

        content_type = response.headers.get("content-type", "")

        if any(ct in content_type for ct in _PLAIN_TEXT_TYPES):
            return {"content_type": content_type, "text": response.text}

        try:
            data = response.json()

            if catalog_search:
                data = enrich_catalog_search_result_with_iris(data)
            elif resource_type:
                data = enrich_response_with_iris(data, resource_type)

            return _wrap_json_with_pagination(data, response.headers, path)
        except Exception:
            return {"content_type": content_type, "text": response.text}

    async def get_all_pages(
        self,
        path: str,
        page_size: int = 100,
        max_pages: int | None = None,
        resource_type: str | None = None,
        catalog_search: bool = False,
        **params: object,
    ) -> dict[str, Any]:
        """Fetch all pages of a list endpoint unless max_pages is provided.

        Args:
            path: API path relative to the base URL, e.g. "/Catalog/search".
            page_size: Number of results per page.
            max_pages: Optional safety limit. If None, fetches until the API says
                there are no more pages.
            **params: Additional query parameters; None values are stripped.

        Returns:
            A dict containing all collected items and pagination summary.
        """
        results: list[Any] = []
        page = 1
        pages_fetched = 0
        total_pages: int | None = None
        total_rows: int | None = None

        while True:
            try:
                response = await self._get_response(
                    path,
                    page=page,
                    pageSize=page_size,
                    **params,
                )
            except httpx.HTTPStatusError as exc:
                return {
                    "error": f"I14Y CORE API returned HTTP {exc.response.status_code}",
                    "url": str(exc.request.url),
                    "pages_fetched": pages_fetched,
                    "results_so_far": results,
                }
            except httpx.RequestError as exc:
                return {
                    "error": f"Network error while contacting I14Y CORE API: {exc}",
                    "pages_fetched": pages_fetched,
                    "results_so_far": results,
                }

            try:
                payload = response.json()
            except Exception:
                return {
                    "error": "Expected JSON response while fetching all pages.",
                    "pages_fetched": pages_fetched,
                    "results_so_far": results,
                }

            pagination = _pagination_from_headers(response.headers) or {}
            total_pages = pagination.get("total_pages", total_pages)
            total_rows = pagination.get("total_rows", total_rows)

            items = _extract_items(payload)
            if not items:
                break

            if catalog_search:
                items = enrich_catalog_search_result_with_iris(items)
            elif resource_type:
                items = enrich_response_with_iris(items, resource_type)

            results.extend(items)
            pages_fetched += 1

            has_more = bool(pagination.get("has_more"))
            if not has_more:
                break

            if max_pages is not None and pages_fetched >= max_pages:
                break

            page = int(pagination.get("next_page") or page + 1)

        is_complete = total_pages is None or pages_fetched >= total_pages

        return {
            "pagination": {
                "page_size": page_size,
                "pages_fetched": pages_fetched,
                "total_pages": total_pages,
                "total_rows": total_rows,
                "is_complete": is_complete,
                "truncated": not is_complete,
                "max_pages": max_pages,
            },
            "data": results,
        }
