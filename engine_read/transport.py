"""HTTP and in-memory transports.

The live transport speaks to api.github.com and raw.githubusercontent.com.
It does not call `gh`, does not read GitHub CLI config, and does not attach
an ambient token unless the caller sets use_env_auth.
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from dataclasses import dataclass


ALLOWED_HOSTS = frozenset({"api.github.com", "raw.githubusercontent.com"})


@dataclass
class HttpResult:
    status: int | None
    headers: dict[str, str]
    body: bytes
    truncated: bool = False
    error_class: str | None = None
    error: str | None = None
    url: str = ""


def _clip(text: str, limit: int = 300) -> str:
    text = text.replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + "..."


class MapTransport:
    """Exact-URL fixture transport. Queues allow one URL to answer differently per call."""

    def __init__(self, routes: dict[str, list[HttpResult] | HttpResult]):
        self.routes: dict[str, list[HttpResult]] = {}
        for url, item in routes.items():
            self.routes[url] = list(item) if isinstance(item, list) else [item]
        self.calls: list[dict] = []

    def request(self, method: str, url: str, *, timeout: float, max_bytes: int | None, headers: dict | None):
        self.calls.append(
            {"method": method, "url": url, "timeout": timeout, "max_bytes": max_bytes, "headers": dict(headers or {})}
        )
        queue = self.routes.get(url)
        if not queue:
            return HttpResult(
                status=None,
                headers={},
                body=b"",
                error_class="unexpected_url",
                error=_clip(url),
                url=url,
            )
        result = queue.pop(0) if len(queue) > 1 else queue[0]
        body = result.body
        truncated = result.truncated
        if max_bytes is not None and len(body) > max_bytes:
            body = body[:max_bytes]
            truncated = True
        return HttpResult(
            status=result.status,
            headers=dict(result.headers),
            body=body,
            truncated=truncated,
            error_class=result.error_class,
            error=result.error,
            url=url,
        )


class GithubHttpTransport:
    """Unauthenticated GitHub HTTP by default. Optional env token is opt-in."""

    def __init__(self, *, use_env_auth: bool = False, opener=None):
        self.use_env_auth = use_env_auth
        self.opener = opener or urllib.request.urlopen

    def _auth_headers(self, base: dict | None) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "grok-engine-read",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if base:
            headers.update(base)
        if self.use_env_auth:
            token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
            if token:
                headers["Authorization"] = "Bearer " + token
        return headers

    def request(self, method: str, url: str, *, timeout: float, max_bytes: int | None, headers: dict | None):
        from urllib.parse import urlparse

        host = urlparse(url).hostname
        if host not in ALLOWED_HOSTS:
            return HttpResult(
                status=None,
                headers={},
                body=b"",
                error_class="refused_host",
                error=host or "",
                url=url,
            )
        req = urllib.request.Request(url, method=method, headers=self._auth_headers(headers))
        try:
            with self.opener(req, timeout=timeout) as resp:
                status = getattr(resp, "status", None) or resp.getcode()
                hdrs = {k: v for k, v in resp.headers.items()}
                body, truncated = _read_bounded(resp, max_bytes)
                return HttpResult(status=status, headers=hdrs, body=body, truncated=truncated, url=url)
        except urllib.error.HTTPError as exc:
            hdrs = {k: v for k, v in exc.headers.items()} if exc.headers else {}
            try:
                body = exc.read(max_bytes + 1) if max_bytes is not None else exc.read()
            except Exception as read_exc:  # noqa: BLE001 — surface as transport failure
                return HttpResult(
                    status=exc.code,
                    headers=hdrs,
                    body=b"",
                    error_class="read_failed",
                    error=_clip(str(read_exc)),
                    url=url,
                )
            truncated = max_bytes is not None and len(body) > max_bytes
            if truncated:
                body = body[:max_bytes]
            return HttpResult(status=exc.code, headers=hdrs, body=body, truncated=truncated, url=url)
        except TimeoutError as exc:
            return HttpResult(status=None, headers={}, body=b"", error_class="timeout", error=_clip(str(exc)), url=url)
        except urllib.error.URLError as exc:
            reason = exc.reason
            timed_out = isinstance(reason, TimeoutError) or "timed out" in str(reason).lower()
            return HttpResult(
                status=None,
                headers={},
                body=b"",
                error_class="timeout" if timed_out else "connection",
                error=_clip(str(reason)),
                url=url,
            )
        except Exception as exc:  # noqa: BLE001
            return HttpResult(
                status=None,
                headers={},
                body=b"",
                error_class="connection",
                error=_clip(repr(exc)),
                url=url,
            )


def _read_bounded(resp, max_bytes: int | None) -> tuple[bytes, bool]:
    if max_bytes is None:
        return resp.read(), False
    chunks = []
    remaining = max_bytes + 1
    while remaining > 0:
        block = resp.read(min(65536, remaining))
        if not block:
            break
        chunks.append(block)
        remaining -= len(block)
    body = b"".join(chunks)
    truncated = len(body) > max_bytes
    if truncated:
        body = body[:max_bytes]
    return body, truncated


def load_fixture_routes(payload: dict) -> dict[str, HttpResult]:
    routes: dict[str, HttpResult] = {}
    for item in payload.get("responses") or []:
        url = item["url"]
        if "json" in item:
            import json

            body = json.dumps(item["json"]).encode("utf-8")
        elif "body_b64" in item:
            import base64

            body = base64.b64decode(item["body_b64"])
        else:
            body = str(item.get("body") or "").encode("utf-8")
        routes[url] = HttpResult(
            status=int(item.get("status") or 200),
            headers={str(k): str(v) for k, v in (item.get("headers") or {}).items()},
            body=body,
            truncated=bool(item.get("truncated")),
            error_class=item.get("error_class"),
            error=item.get("error"),
            url=url,
        )
    return routes
