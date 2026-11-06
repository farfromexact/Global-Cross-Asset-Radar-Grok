"""Pin one commit per engine repo and read files without floating main.

Contents may come from the GitHub HTTP API or from a connector handoff
(stdin/manifest pointing at a complete tool-asset file). Commit metadata is
resolved independently of those bytes.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo

from engine_read import __version__
from engine_read.transport import HttpResult, MapTransport, load_fixture_routes

SHANGHAI = ZoneInfo("Asia/Shanghai")
API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"

REPOS = (
    {
        "role": "commodities",
        "repo": "farfromexact/China-Commodities-Engine",
        "metadata": ("data/last_run_status.json",),
        "status_follow": ("data/night_session/last_run_status.json",),
    },
    {
        "role": "stock",
        "repo": "farfromexact/China-Stock-Engine",
        "metadata": ("data/last_run_status.json", "data/latest/manifest.json"),
        "status_follow": (),
    },
    {
        "role": "options",
        "repo": "farfromexact/China-Options-Engine",
        "metadata": ("data/radar_latest.json",),
        "status_follow": (),
    },
)

ALLOW = {
    "commodities": (
        "data/report_input_latest.json",
        "data/night_session/latest.json",
        "data/radar_latest.json",
        "data/radar_history.json",
        "data/crosschecks/futures_latest.json",
        "data/options/quality_latest.json",
        "data/options/surface_latest.json",
        "data/options/latest.json",
        "data/latest.json",
        "data/market_state_latest.json",
        "data/physical/latest.json",
        "data/external/latest.json",
        "data/contract_meta.json",
    ),
    "stock": (
        "data/latest/data_reference_latest.json",
        "data/latest/opportunity_radar_latest.json",
        "data/latest/research_inputs_latest.json",
    ),
    "options": (
        "data/radar_history.json",
        "data/latest.json",
        "data/last_run_status.json",
    ),
}

LARGE_PATHS = frozenset(
    {
        "data/report_input_latest.json",
        "data/night_session/latest.json",
    }
)

LEGACY = {
    "ok": "ok",
    "stale": "stale",
    "permission_denied": "permission_error",
    "not_found": "missing",
    "actual_empty": "empty",
    "valid_zero": "empty",
    "parse_error": "parse_error",
    "truncated": "truncated",
    "partial_validated": "truncated",
    "read_failed": "read_failed",
}

REFUSED_PATH_MARKERS = (
    ".config/gh",
    "hosts.yml",
    "credentials.json",
    ".env",
    "id_rsa",
    "id_ed25519",
)


def parse_instant(text: str) -> datetime:
    raw = text.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    if " " in raw and "T" not in raw:
        raw = raw.replace(" ", "T", 1)
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=SHANGHAI)
    return dt


def until_param(cutoff: datetime) -> str:
    moment = cutoff.astimezone(timezone.utc) + timedelta(seconds=1)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def commits_url(repo: str, ref: str, cutoff: datetime, page: int = 1) -> str:
    query = {"per_page": "20", "sha": ref, "until": until_param(cutoff)}
    if page > 1:
        query["page"] = str(page)
    return f"{API}/repos/{repo}/commits?{urlencode(sorted(query.items()))}"


def contents_url(repo: str, commit: str, path: str) -> str:
    return f"{API}/repos/{repo}/contents/{quote(path, safe='/')}?ref={commit}"


def blob_url(repo: str, sha: str) -> str:
    return f"{API}/repos/{repo}/git/blobs/{sha}"


def raw_url(repo: str, commit: str, path: str) -> str:
    return f"{RAW}/{repo}/{commit}/{quote(path, safe='/')}"


def git_commit_url(repo: str, commit: str) -> str:
    return f"{API}/repos/{repo}/git/commits/{commit}"


def git_tree_url(repo: str, tree_sha: str) -> str:
    return f"{API}/repos/{repo}/git/trees/{tree_sha}?recursive=1"


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_b64(text: str) -> bytes:
    return base64.b64decode("".join(text.split()), validate=True)


def previous_weekday(day):
    cursor = day - timedelta(days=1)
    while cursor.weekday() >= 5:
        cursor -= timedelta(days=1)
    return cursor


def infer_edition(cutoff: datetime) -> str:
    local = cutoff.astimezone(SHANGHAI)
    if local.weekday() >= 5:
        return "weekend"
    return "morning" if local.hour < 12 else "evening"


def session_expectations(cutoff: datetime) -> dict:
    local = cutoff.astimezone(SHANGHAI)
    if local.weekday() >= 5:
        return {
            "china_day_session": "not_due",
            "china_equity_session": "not_due",
            "china_night_session_upcoming": "not_due",
        }
    minutes = local.hour * 60 + local.minute
    if minutes < 9 * 60:
        day = "not_started"
    elif minutes < 15 * 60:
        day = "in_progress"
    else:
        day = "completed"
    if minutes < 9 * 60 + 30:
        equity = "not_started"
    elif minutes < 15 * 60:
        equity = "in_progress"
    else:
        equity = "completed"
    night = "not_started" if minutes < 21 * 60 else "in_progress"
    return {
        "china_day_session": day,
        "china_equity_session": equity,
        "china_night_session_upcoming": night,
    }


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def assert_output_dir(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    root = repo_root().resolve()
    if resolved == root or root in resolved.parents:
        raise SystemExit(
            f"refusing output dir inside the archive repository: {resolved}"
        )
    return resolved


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def atomic_write_json(path: Path, obj) -> None:
    encoded = (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    atomic_write_bytes(path, encoded)


def _clip(text: str, limit: int = 300) -> str:
    text = text.replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + "..."


def http_failure_class(result: HttpResult) -> str | None:
    if result.error_class in {"timeout", "connection", "unexpected_url", "refused_host", "read_failed"}:
        return result.error_class
    status = result.status
    if status is None:
        return result.error_class or "read_failed"
    text = result.body.decode("utf-8", "replace").lower()
    remaining = (result.headers.get("X-RateLimit-Remaining") or result.headers.get("x-ratelimit-remaining") or "")
    if status == 429 or "rate limit" in text or (status == 403 and remaining == "0"):
        return "rate_limit"
    if status in (401, 403):
        if "too large" in text or "size exceeded" in text or "blobs up to 1 mb" in text:
            return "too_large"
        return "permission_denied"
    if status == 404:
        return "not_found"
    if status >= 400:
        return "read_failed"
    return None


def _json_body(result: HttpResult):
    try:
        return json.loads(result.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _parse_commit_time(item: dict) -> datetime | None:
    try:
        raw = item["commit"]["committer"]["date"]
    except (KeyError, TypeError):
        return None
    if not isinstance(raw, str):
        return None
    return parse_instant(raw)


def _refused_asset(path: str) -> bool:
    lowered = path.replace("\\", "/").lower()
    return any(marker in lowered for marker in REFUSED_PATH_MARKERS)


@dataclass
class RunConfig:
    cutoff: datetime
    output_dir: Path
    requested_ref: str = "main"
    edition: str | None = None
    fixture_mode: bool = False
    commits_transport: str = "api"
    contents_transport: str = "api"
    prefer: str = "auto"
    max_bytes: int | None = None
    timeout: float = 30.0
    fetched_at: datetime | None = None
    handoff: dict | None = None
    transport_label_commits: str = "github_api"
    transport_label_contents: str = "github_api"


@dataclass
class Ctx:
    config: RunConfig
    transport: object
    expectations: dict
    edition: str
    fetched_at: str
    evidence_dir: Path | None = None


def _base_path(ctx: Ctx, repo: str, commit: str | None, path: str, phase: str) -> dict:
    return {
        "repo": repo,
        "requested_ref": ctx.config.requested_ref,
        "resolved_commit": commit,
        "commit_time": None,
        "fetched_at": ctx.fetched_at,
        "cutoff": ctx.config.cutoff.isoformat(),
        "timezone": "Asia/Shanghai",
        "path": path,
        "phase": phase,
        "read_method": None,
        "read_status": "not_attempted",
        "not_attempted_reason": None,
        "transport": ctx.config.transport_label_contents,
        "fixture_mode": ctx.config.fixture_mode,
        "sha": None,
        "declared_size": None,
        "actual_size": None,
        "bytes": None,
        "sha256": None,
        "partial_sha256": None,
        "bytes_received": None,
        "parse_result": "not_attempted",
        "source_date": None,
        "trade_date": None,
        "source_trade_date": None,
        "quote_dates": None,
        "observation_time": None,
        "source_timestamp": None,
        "generated_at": None,
        "published_at": None,
        "known_at": None,
        "date": None,
        "run_date": None,
        "freshness_date": None,
        "freshness_date_field": None,
        "research_usable": False,
        "research_usable_reason": "not_read",
        "execution_usable": False,
        "execution_usable_reason": "read_not_complete",
        "module_limitations": [],
        "modules": None,
        "success_flag": None,
        "data_fresh": None,
        "last_good": None,
        "snapshot_class": None,
        "temporal_readiness": None,
        "upcoming_session": None,
        "counts_as_missing": False,
        "source_status": None,
        "pin_verified": False,
        "error_class": None,
        "error": None,
        "http_status": None,
        "evidence_path": None,
        "complete": False,
    }


def _legacy(receipt: dict) -> None:
    status = receipt["read_status"]
    if status == "not_attempted":
        receipt["source_status"] = None
        return
    if status == "not_found" and not receipt["counts_as_missing"]:
        receipt["source_status"] = None
        return
    receipt["source_status"] = LEGACY.get(status)


def _apply_temporal(receipt: dict, expectations: dict) -> None:
    path = receipt["path"] or ""
    weekend = expectations.get("china_day_session") == "not_due"
    if weekend and receipt["read_status"] in {"not_found", "not_attempted"}:
        receipt["temporal_readiness"] = "not_due"
        receipt["counts_as_missing"] = False
    if "night_session" in path:
        upcoming = expectations.get("china_night_session_upcoming")
        receipt["upcoming_session"] = upcoming
        if upcoming in {"not_started", "not_due"} and receipt["read_status"] in {"not_found", "not_attempted"}:
            receipt["temporal_readiness"] = upcoming
            receipt["counts_as_missing"] = False
        elif upcoming in {"not_started", "not_due"}:
            receipt["upcoming_session"] = upcoming
            receipt["counts_as_missing"] = False
    if receipt["read_status"] == "not_found" and not weekend and "night_session" not in path:
        receipt["counts_as_missing"] = True
    _legacy(receipt)


def _find_key(obj, key):
    if isinstance(obj, dict) and key in obj:
        return obj[key]
    return None


def _module_rows(doc) -> list[dict] | None:
    modules = doc.get("modules") if isinstance(doc, dict) else None
    if not isinstance(modules, list):
        return None
    rows = []
    for item in modules:
        if not isinstance(item, dict):
            continue
        row = {}
        for key in ("dataset", "scope", "state", "trade_date", "requested_trade_date", "is_fresh", "error"):
            if key in item and not isinstance(item[key], (dict, list)):
                row[key] = item[key]
        records = item.get("records")
        if isinstance(records, int):
            row["records"] = records
        elif isinstance(records, list):
            row["records_count"] = len(records)
        if row:
            rows.append(row)
    return rows


def _limitations(doc) -> list:
    if not isinstance(doc, dict):
        return []
    out = []
    quality = doc.get("quality_metrics") if isinstance(doc.get("quality_metrics"), dict) else {}
    for key in (
        "options_execution_ready",
        "options_surface_ready",
        "options_positioning_ready",
        "options_full_chain_verified",
        "full_market_ready",
    ):
        if quality.get(key) is False:
            out.append({"field": f"quality_metrics.{key}", "value": False})
    if doc.get("official_complete") is False:
        out.append({"field": "official_complete", "value": False})
    if doc.get("official_night_close_verified") is False:
        out.append({"field": "official_night_close_verified", "value": False})
    if doc.get("price_semantics") == "vendor_latest_trade_asof_snapshot":
        out.append({"field": "price_semantics", "value": "vendor_latest_trade_asof_snapshot"})
    if isinstance(doc.get("ohlcv_scope"), str) and "unverified" in doc["ohlcv_scope"]:
        out.append({"field": "ohlcv_scope", "value": doc["ohlcv_scope"]})
    limitations = doc.get("limitations")
    if isinstance(limitations, list):
        for item in limitations:
            if isinstance(item, str):
                out.append({"field": "limitations", "value": item[:200]})
    elif isinstance(limitations, dict):
        encoded = json.dumps(limitations, ensure_ascii=False, sort_keys=True)
        if len(encoded) <= 1500 and "records" not in limitations:
            out.append({"field": "limitations", "value": limitations})
        else:
            out.append({"field": "limitations", "value": sorted(limitations)})
    rows = _module_rows(doc) or []
    bad = [
        f"{row.get('dataset')}:{row.get('scope')}={row.get('state')}"
        for row in rows
        if row.get("state") not in (None, "ok")
    ]
    if bad:
        out.append({"field": "modules.state", "value": bad})
    return out


def _last_good(doc):
    if not isinstance(doc, dict):
        return None
    for key in ("last_good", "last_valid_trade_date", "last_good_trade_date", "last_good_eod"):
        if key in doc:
            return {"field": key, "value": doc[key]}
    return None


def _success_flag(doc):
    if not isinstance(doc, dict):
        return None
    state = doc.get("state")
    if isinstance(state, str):
        lowered = state.lower()
        if lowered in {"success", "success_backfill", "ok", "passed"}:
            return True
        if "fail" in lowered or lowered in {"error", "skipped"}:
            return False
    if doc.get("success") is True:
        return True
    return None


def _quote_dates(doc):
    if not isinstance(doc, dict) or "quote_dates" not in doc:
        found = _nested_quote_dates(doc)
        return found
    return doc.get("quote_dates")


def _nested_quote_dates(obj):
    if isinstance(obj, dict):
        if "quote_dates" in obj:
            return obj["quote_dates"]
        for value in obj.values():
            found = _nested_quote_dates(value)
            if found is not None:
                return found
    return None


def _as_date(value):
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _max_quote_date(value):
    if isinstance(value, str):
        return _as_date(value)
    if isinstance(value, list):
        dates = [d for d in (_as_date(item) if isinstance(item, str) else None) for item in value]
        dates = [item for item in dates if item is not None]
        return max(dates) if dates else None
    if isinstance(value, dict):
        dates = []
        for item in value.values():
            found = _max_quote_date(item)
            if found:
                dates.append(found)
        return max(dates) if dates else None
    return None


def _freshness(doc, cutoff: datetime):
    if not isinstance(doc, dict):
        return None, None
    if "trade_date" in doc:
        return doc.get("trade_date") if isinstance(doc.get("trade_date"), str) else None, "trade_date"
    if "source_trade_date" in doc:
        value = doc.get("source_trade_date")
        return value if isinstance(value, str) else None, "source_trade_date"
    quoted = _quote_dates(doc)
    if quoted is not None:
        found = _max_quote_date(quoted)
        return (found.isoformat() if found else None), "quote_dates"
    if isinstance(doc.get("date"), str):
        return doc.get("date"), "date"
    rows = _module_rows(doc) or []
    dates = sorted({row["trade_date"] for row in rows if isinstance(row.get("trade_date"), str)})
    if len(dates) == 1:
        return dates[0], "modules.trade_date"
    if "last_valid_trade_date" in doc and isinstance(doc.get("last_valid_trade_date"), str):
        return doc["last_valid_trade_date"], "last_valid_trade_date"
    return None, None


def _fill_document_fields(receipt: dict, doc, cutoff: datetime) -> None:
    if not isinstance(doc, (dict, list)):
        return
    if isinstance(doc, list):
        return
    receipt["source_date"] = doc.get("source_date") if "source_date" in doc else None
    receipt["trade_date"] = doc.get("trade_date") if isinstance(doc.get("trade_date"), str) else None
    receipt["source_trade_date"] = doc.get("source_trade_date") if "source_trade_date" in doc else None
    receipt["quote_dates"] = doc.get("quote_dates") if "quote_dates" in doc else _nested_quote_dates(doc)
    if "observation_time" in doc:
        receipt["observation_time"] = doc.get("observation_time")
    elif "source_timestamp" in doc:
        receipt["observation_time"] = doc.get("source_timestamp")
        receipt["source_timestamp"] = doc.get("source_timestamp")
    if "source_timestamp" in doc:
        receipt["source_timestamp"] = doc.get("source_timestamp")
    receipt["generated_at"] = doc.get("generated_at") if "generated_at" in doc else None
    receipt["published_at"] = doc.get("published_at") if "published_at" in doc else None
    receipt["known_at"] = doc.get("known_at") if "known_at" in doc else None
    context = doc.get("research_context") if isinstance(doc.get("research_context"), dict) else None
    if context and "known_at" in context:
        receipt["research_context_known_at"] = context.get("known_at")
    if context and "source_published_at" in context:
        receipt["source_published_at"] = context.get("source_published_at")
    receipt["date"] = doc.get("date") if "date" in doc else None
    receipt["run_date"] = doc.get("run_date") if "run_date" in doc else None
    receipt["data_fresh"] = doc.get("data_fresh") if "data_fresh" in doc else None
    receipt["success_flag"] = _success_flag(doc)
    receipt["last_good"] = _last_good(doc)
    receipt["modules"] = _module_rows(doc)
    receipt["module_limitations"] = _limitations(doc)
    if isinstance(doc.get("quality_metrics"), dict):
        kept = {}
        for key in (
            "source_date_match_pct",
            "critical_module_errors",
            "full_market_ready",
            "options_surface_ready",
            "options_positioning_ready",
            "options_execution_ready",
            "options_full_chain_verified",
        ):
            if key in doc["quality_metrics"] and not isinstance(doc["quality_metrics"][key], (dict, list)):
                kept[key] = doc["quality_metrics"][key]
        receipt["quality_metrics"] = kept
    fresh, field_name = _freshness(doc, cutoff)
    receipt["freshness_date"] = fresh
    receipt["freshness_date_field"] = field_name
    if doc.get("price_semantics") == "vendor_latest_trade_asof_snapshot" or (
        doc.get("official_night_close_verified") is False and "night" in (receipt["path"] or "")
    ):
        if doc.get("price_semantics") == "vendor_latest_trade_asof_snapshot":
            receipt["snapshot_class"] = "vendor_latest_trade_asof_snapshot"
        elif doc.get("official_night_close_verified") is False:
            receipt["snapshot_class"] = "unverified_night"
    generated = doc.get("generated_at") if isinstance(doc.get("generated_at"), str) else None
    if generated and "night_session" in (receipt["path"] or ""):
        try:
            stamp = parse_instant(generated)
            receipt["session_relation"] = (
                "completed_session_before_cutoff" if stamp <= cutoff else "generated_after_cutoff"
            )
        except ValueError:
            receipt["session_relation"] = None
    local_day = cutoff.astimezone(SHANGHAI).date()
    floor = previous_weekday(local_day) if local_day.weekday() < 5 else previous_weekday(local_day)
    # On Saturday, previous completed weekday is Friday (previous_weekday of Saturday is Friday).
    parsed_fresh = _as_date(fresh) if isinstance(fresh, str) else None
    if parsed_fresh is not None and parsed_fresh < floor and receipt["read_status"] == "ok":
        receipt["read_status"] = "stale"
        receipt["stale_vs"] = floor.isoformat()


def _usability(receipt: dict, doc) -> None:
    status = receipt["read_status"]
    if status in {"ok", "stale"} and receipt["complete"]:
        receipt["research_usable"] = True
        receipt["research_usable_reason"] = "stale_trade_date" if status == "stale" else "complete_parse"
        if receipt["snapshot_class"] == "vendor_latest_trade_asof_snapshot":
            receipt["research_usable_reason"] = "vendor_snapshot_not_official_close"
    elif status == "valid_zero":
        receipt["research_usable"] = False
        receipt["research_usable_reason"] = receipt["parse_result"]
    elif status == "actual_empty":
        receipt["research_usable"] = False
        receipt["research_usable_reason"] = "actual_empty"
    elif status == "parse_error":
        receipt["research_usable"] = False
        receipt["research_usable_reason"] = "parse_error"
    elif status == "truncated":
        receipt["research_usable"] = False
        receipt["research_usable_reason"] = "truncated"
    elif status == "partial_validated":
        receipt["research_usable"] = False
        receipt["research_usable_reason"] = "integrity_mismatch"
    elif status == "permission_denied":
        receipt["research_usable"] = False
        receipt["research_usable_reason"] = "permission_denied"
    elif status == "not_found":
        receipt["research_usable"] = False
        receipt["research_usable_reason"] = "not_found"
    elif status == "not_attempted":
        receipt["research_usable"] = False
        receipt["research_usable_reason"] = receipt["not_attempted_reason"] or "not_read"
    else:
        receipt["research_usable"] = False
        receipt["research_usable_reason"] = status

    receipt["execution_usable"] = False
    reason = "execution_ready_not_true"
    quality = doc.get("quality_metrics") if isinstance(doc, dict) else None
    ready = isinstance(quality, dict) and quality.get("options_execution_ready") is True
    if receipt["snapshot_class"] == "vendor_latest_trade_asof_snapshot" or (
        isinstance(doc, dict) and doc.get("official_night_close_verified") is False
    ):
        reason = "vendor_snapshot_not_official_close"
    elif status == "stale":
        reason = "stale_trade_date"
    elif receipt.get("upcoming_session") in {"not_started", "not_due"} or receipt.get("temporal_readiness") in {
        "not_started",
        "not_due",
    }:
        reason = "session_not_started"
    elif status not in {"ok"}:
        reason = "read_not_complete"
    elif ready and status == "ok":
        receipt["execution_usable"] = True
        reason = "explicit_execution_ready"
    receipt["execution_usable_reason"] = reason


def _finalize_bytes(ctx: Ctx, receipt: dict, data: bytes, declared_size, declared_sha, method: str) -> None:
    receipt["read_method"] = method
    receipt["actual_size"] = len(data)
    receipt["declared_size"] = declared_size
    if declared_size == 0 or (declared_size is None and data == b""):
        receipt["read_status"] = "actual_empty"
        receipt["parse_result"] = "not_attempted"
        receipt["complete"] = True
        receipt["bytes"] = 0
        receipt["sha256"] = sha256_hex(data)
        _apply_temporal(receipt, ctx.expectations)
        _usability(receipt, None)
        return
    computed = git_blob_sha1(data)
    receipt["sha"] = declared_sha or computed
    size_ok = declared_size is None or declared_size == len(data)
    sha_ok = declared_sha is None or declared_sha == computed
    if not size_ok or not sha_ok:
        receipt["read_status"] = "partial_validated"
        receipt["parse_result"] = "size_mismatch" if not size_ok else "git_blob_sha_mismatch"
        receipt["complete"] = False
        receipt["sha256"] = None
        receipt["bytes"] = None
        _apply_temporal(receipt, ctx.expectations)
        _usability(receipt, None)
        return
    receipt["sha"] = computed
    receipt["bytes"] = len(data)
    receipt["sha256"] = sha256_hex(data)
    receipt["complete"] = True
    try:
        parsed = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        receipt["read_status"] = "parse_error"
        receipt["parse_result"] = "parse_error"
        _apply_temporal(receipt, ctx.expectations)
        _usability(receipt, None)
        return
    if parsed == {}:
        receipt["read_status"] = "valid_zero"
        receipt["parse_result"] = "empty_object"
    elif parsed == []:
        receipt["read_status"] = "valid_zero"
        receipt["parse_result"] = "empty_array"
    else:
        receipt["read_status"] = "ok"
        receipt["parse_result"] = "json_ok"
    _fill_document_fields(receipt, parsed, ctx.config.cutoff)
    _apply_temporal(receipt, ctx.expectations)
    _usability(receipt, parsed if isinstance(parsed, dict) else None)
    if receipt["complete"] and ctx.evidence_dir is not None and receipt["read_status"] in {"ok", "stale", "valid_zero"}:
        rel = Path("evidence") / receipt["repo"].split("/")[-1] / (receipt["resolved_commit"] or "none") / receipt["path"]
        dest = ctx.evidence_dir / rel
        atomic_write_bytes(dest, data)
        receipt["evidence_path"] = str(dest)


def _truncated(ctx: Ctx, receipt: dict, result: HttpResult, method: str) -> dict:
    receipt["read_method"] = method
    receipt["read_status"] = "truncated"
    receipt["parse_result"] = "not_attempted"
    receipt["complete"] = False
    receipt["bytes_received"] = len(result.body)
    receipt["partial_sha256"] = sha256_hex(result.body) if result.body else None
    receipt["http_status"] = result.status
    receipt["error_class"] = "truncated"
    _apply_temporal(receipt, ctx.expectations)
    _usability(receipt, None)
    return receipt


def _fail(ctx: Ctx, receipt: dict, status: str, error_class: str | None, error: str | None, http_status=None) -> dict:
    receipt["read_status"] = status
    receipt["error_class"] = error_class
    receipt["error"] = _clip(error) if error else None
    receipt["http_status"] = http_status
    receipt["parse_result"] = "not_attempted"
    _apply_temporal(receipt, ctx.expectations)
    _usability(receipt, None)
    return receipt


def _call(ctx: Ctx, url: str) -> HttpResult:
    return ctx.transport.request(
        "GET",
        url,
        timeout=ctx.config.timeout,
        max_bytes=ctx.config.max_bytes,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "grok-engine-read"},
    )


def _resolve_api(ctx: Ctx, repo: str) -> dict:
    pin = {
        "repo": repo,
        "requested_ref": ctx.config.requested_ref,
        "resolved_commit": None,
        "commit_time": None,
        "resolve_status": "read_failed",
        "commits_transport": ctx.config.transport_label_commits,
        "fixture_mode": ctx.config.fixture_mode,
        "error_class": None,
        "error": None,
        "pages_read": 0,
    }
    for page in range(1, 6):
        result = _call(ctx, commits_url(repo, ctx.config.requested_ref, ctx.config.cutoff, page))
        pin["pages_read"] = page
        kind = http_failure_class(result)
        if result.truncated:
            pin["resolve_status"] = "truncated"
            pin["error_class"] = "truncated"
            return pin
        if kind == "timeout":
            pin["error_class"] = "timeout"
            pin["error"] = result.error
            pin["resolve_status"] = "read_failed"
            return pin
        if kind == "permission_denied":
            pin["resolve_status"] = "permission_denied"
            pin["error_class"] = "permission_denied"
            pin["error"] = result.error or f"http {result.status}"
            return pin
        if kind == "not_found":
            pin["resolve_status"] = "not_found"
            pin["error_class"] = "not_found"
            return pin
        if kind:
            pin["resolve_status"] = "read_failed"
            pin["error_class"] = kind
            pin["error"] = result.error or f"http {result.status}"
            return pin
        payload = _json_body(result)
        if not isinstance(payload, list):
            pin["error_class"] = "parse_error"
            pin["error"] = "commits response was not a list"
            pin["resolve_status"] = "read_failed"
            return pin
        if not payload:
            pin["resolve_status"] = "not_found"
            pin["error_class"] = "no_commit_at_or_before_cutoff"
            return pin
        for item in payload:
            if not isinstance(item, dict):
                continue
            moment = _parse_commit_time(item)
            sha = item.get("sha")
            if not isinstance(sha, str) or moment is None:
                continue
            if moment <= ctx.config.cutoff:
                pin["resolved_commit"] = sha
                pin["commit_time"] = moment.astimezone(SHANGHAI).isoformat()
                pin["resolve_status"] = "ok"
                pin["error_class"] = None
                return pin
        oldest = None
        for item in payload:
            moment = _parse_commit_time(item) if isinstance(item, dict) else None
            if moment is not None and (oldest is None or moment < oldest):
                oldest = moment
        if oldest is not None and oldest <= ctx.config.cutoff:
            pin["resolve_status"] = "not_found"
            pin["error_class"] = "no_commit_at_or_before_cutoff"
            return pin
    pin["resolve_status"] = "not_found"
    pin["error_class"] = "no_commit_at_or_before_cutoff"
    return pin


def _resolve_handoff(ctx: Ctx, repo: str) -> dict:
    pin = {
        "repo": repo,
        "requested_ref": ctx.config.requested_ref,
        "resolved_commit": None,
        "commit_time": None,
        "resolve_status": "not_attempted",
        "commits_transport": ctx.config.transport_label_commits,
        "fixture_mode": ctx.config.fixture_mode,
        "error_class": None,
        "error": None,
        "not_attempted_reason": "commits_metadata_not_in_handoff",
    }
    block = (ctx.config.handoff or {}).get("commits") or {}
    item = block.get(repo)
    if not isinstance(item, dict):
        return pin
    sha = item.get("resolved_commit")
    raw_time = item.get("commit_time")
    if not isinstance(sha, str) or len(sha) != 40:
        pin["resolve_status"] = "read_failed"
        pin["error_class"] = "pin_metadata_invalid"
        pin["not_attempted_reason"] = None
        return pin
    if not isinstance(raw_time, str):
        pin["resolve_status"] = "read_failed"
        pin["error_class"] = "commit_time_missing"
        pin["not_attempted_reason"] = None
        return pin
    try:
        moment = parse_instant(raw_time)
    except ValueError:
        pin["resolve_status"] = "read_failed"
        pin["error_class"] = "commit_time_invalid"
        pin["not_attempted_reason"] = None
        return pin
    pin["not_attempted_reason"] = None
    if moment > ctx.config.cutoff:
        pin["resolve_status"] = "read_failed"
        pin["error_class"] = "commit_after_cutoff"
        pin["resolved_commit"] = None
        pin["commit_time"] = moment.astimezone(SHANGHAI).isoformat()
        pin["error"] = "handoff commit_time is after cutoff"
        return pin
    pin["resolved_commit"] = sha
    pin["commit_time"] = moment.astimezone(SHANGHAI).isoformat()
    pin["resolve_status"] = "ok"
    return pin


def _handoff_file(ctx: Ctx, repo: str, commit: str, path: str) -> dict | None:
    files = (ctx.config.handoff or {}).get("files") or []
    matches = [
        item
        for item in files
        if isinstance(item, dict) and item.get("repo") == repo and item.get("path") == path
    ]
    for item in matches:
        if item.get("commit") == commit:
            return item
    return matches[0] if matches else None


def _read_asset(ctx: Ctx, receipt: dict, item: dict) -> dict:
    asset = item.get("asset_path")
    if not isinstance(asset, str) or not asset:
        return _fail(ctx, receipt, "not_attempted", "connector_asset_not_supplied", None)
    if _refused_asset(asset):
        return _fail(ctx, receipt, "read_failed", "refused_path", "asset path is not a content file")
    path = Path(asset)
    try:
        data = path.read_bytes()
    except OSError as exc:
        return _fail(ctx, receipt, "read_failed", "asset_unreadable", str(exc))
    declared_size = item.get("declared_size")
    declared_sha = item.get("declared_sha")
    if declared_size is not None and not isinstance(declared_size, int):
        return _fail(ctx, receipt, "read_failed", "declared_size_invalid", None)
    if declared_sha is not None and not isinstance(declared_sha, str):
        return _fail(ctx, receipt, "read_failed", "declared_sha_invalid", None)
    file_commit = item.get("commit")
    if file_commit != receipt["resolved_commit"]:
        return _fail(ctx, receipt, "read_failed", "pin_mismatch", "handoff commit does not match resolved commit")
    computed_sha256 = sha256_hex(data)
    computed_blob = git_blob_sha1(data)
    stem = Path(asset).stem.lower()
    name_is_sha256 = len(stem) == 64 and all(ch in "0123456789abcdef" for ch in stem)
    receipt["transport"] = "contents"
    receipt["media"] = "raw"
    receipt["streaming"] = False
    receipt["identity_source"] = "computed"
    receipt["actual_size"] = len(data)
    receipt["sha256"] = computed_sha256
    receipt["sha"] = computed_blob
    receipt["asset_name_sha256_ok"] = (stem == computed_sha256) if name_is_sha256 else None
    if name_is_sha256 and stem != computed_sha256:
        receipt["complete"] = False
        receipt["read_method"] = "contents"
        return _fail(ctx, receipt, "partial_validated", "asset_name_mismatch", "asset filename is not the sha256 of the raw bytes")
    size_arg = declared_size if isinstance(declared_size, int) else len(data)
    sha_arg = declared_sha if isinstance(declared_sha, str) else computed_blob
    _finalize_bytes(ctx, receipt, data, size_arg, sha_arg, "contents")
    receipt["transport"] = "contents"
    receipt["read_method"] = "contents"
    receipt["media"] = "raw"
    receipt["streaming"] = False
    receipt["identity_source"] = "computed"
    if isinstance(declared_sha, str):
        receipt["blob_sha_source"] = "pinned_tree" if receipt.get("complete") else "pinned_tree_mismatch"
    else:
        receipt["blob_sha_source"] = "computed"
        receipt["tree_metadata"] = "not_supplied"
    receipt["sha256"] = computed_sha256
    receipt["sha"] = computed_blob
    return receipt


def _read_blob(ctx: Ctx, repo: str, sha: str, expected_size) -> tuple[str, bytes | None, HttpResult]:
    result = _call(ctx, blob_url(repo, sha))
    if result.truncated:
        return "truncated", None, result
    kind = http_failure_class(result)
    if kind:
        return kind, None, result
    payload = _json_body(result)
    if not isinstance(payload, dict):
        return "parse_error", None, result
    content = payload.get("content")
    if not isinstance(content, str) or payload.get("encoding") not in (None, "base64"):
        return "parse_error", None, result
    try:
        data = decode_b64(content)
    except Exception:  # noqa: BLE001
        return "parse_error", None, result
    return "ok", data, result


def _tree_blob(ctx: Ctx, repo: str, commit: str, path: str) -> tuple[str | None, int | None, str | None]:
    commit_result = _call(ctx, git_commit_url(repo, commit))
    if http_failure_class(commit_result) or commit_result.truncated:
        return None, None, "tree_lookup_failed"
    commit_doc = _json_body(commit_result)
    tree_sha = None
    if isinstance(commit_doc, dict):
        tree = commit_doc.get("tree")
        if isinstance(tree, dict):
            tree_sha = tree.get("sha")
    if not isinstance(tree_sha, str):
        return None, None, "tree_lookup_failed"
    tree_result = _call(ctx, git_tree_url(repo, tree_sha))
    if http_failure_class(tree_result) or tree_result.truncated:
        return None, None, "tree_lookup_failed"
    tree_doc = _json_body(tree_result)
    entries = tree_doc.get("tree") if isinstance(tree_doc, dict) else None
    if not isinstance(entries, list):
        return None, None, "tree_lookup_failed"
    for entry in entries:
        if isinstance(entry, dict) and entry.get("path") == path and entry.get("type") == "blob":
            sha = entry.get("sha")
            size = entry.get("size")
            return (sha if isinstance(sha, str) else None, size if isinstance(size, int) else None, None)
    return None, None, "not_found"


def _read_raw(ctx: Ctx, repo: str, commit: str, path: str) -> HttpResult:
    return _call(ctx, raw_url(repo, commit, path))


def _read_api_path(ctx: Ctx, repo: str, commit: str, path: str, phase: str) -> dict:
    receipt = _base_path(ctx, repo, commit, path, phase)
    receipt["pin_verified"] = True
    prefer = ctx.config.prefer
    meta_sha = None
    meta_size = None
    result = _call(ctx, contents_url(repo, commit, path))
    if result.truncated:
        return _truncated(ctx, receipt, result, "contents_at_sha")
    kind = http_failure_class(result)
    if kind == "timeout":
        return _fail(ctx, receipt, "read_failed", "timeout", result.error, result.status)
    if kind == "permission_denied":
        return _fail(ctx, receipt, "permission_denied", "permission_denied", result.error, result.status)
    if kind == "not_found":
        return _fail(ctx, receipt, "not_found", "not_found", None, result.status)
    if kind and kind != "too_large":
        return _fail(ctx, receipt, "read_failed", kind, result.error, result.status)
    if kind != "too_large":
        meta = _json_body(result)
        if not isinstance(meta, dict):
            return _fail(ctx, receipt, "read_failed", "parse_error", "contents response was not an object", result.status)
        meta_sha = meta.get("sha") if isinstance(meta.get("sha"), str) else None
        meta_size = meta.get("size") if isinstance(meta.get("size"), int) else None
        encoding = meta.get("encoding")
        content = meta.get("content")
        content_text = content if isinstance(content, str) else ""
        if encoding == "base64" and content_text.strip() and prefer in {"auto", "contents"}:
            try:
                data = decode_b64(content_text)
            except Exception:  # noqa: BLE001
                data = None
            if data is not None and (meta_size is None or len(data) == meta_size):
                _finalize_bytes(ctx, receipt, data, meta_size, meta_sha, "contents_at_sha")
                return receipt
        if meta_size == 0 and not content_text.strip():
            _finalize_bytes(ctx, receipt, b"", 0, meta_sha, "contents_at_sha")
            return receipt
        if prefer == "contents":
            return _fail(
                ctx,
                receipt,
                "partial_validated",
                "contents_incomplete",
                "contents payload omitted bytes",
                result.status,
            )
    if prefer == "raw":
        raw = _read_raw(ctx, repo, commit, path)
        if raw.truncated:
            return _truncated(ctx, receipt, raw, "raw_commit_path")
        raw_kind = http_failure_class(raw)
        if raw_kind == "not_found":
            return _fail(ctx, receipt, "not_found", "not_found", None, raw.status)
        if raw_kind == "permission_denied":
            return _fail(ctx, receipt, "permission_denied", "permission_denied", raw.error, raw.status)
        if raw_kind:
            return _fail(ctx, receipt, "read_failed", raw_kind, raw.error, raw.status)
        _finalize_bytes(ctx, receipt, raw.body, meta_size, meta_sha, "raw_commit_path")
        return receipt
    if meta_sha is None:
        meta_sha, looked_up_size, tree_err = _tree_blob(ctx, repo, commit, path)
        if tree_err == "not_found":
            return _fail(ctx, receipt, "not_found", "not_found", None)
        if not meta_sha:
            return _fail(ctx, receipt, "read_failed", tree_err or "blob_sha_missing", None)
        if meta_size is None:
            meta_size = looked_up_size
    state, data, blob_result = _read_blob(ctx, repo, meta_sha, meta_size)
    if state == "truncated":
        return _truncated(ctx, receipt, blob_result, "git_blob_base64")
    if state == "not_found":
        return _fail(ctx, receipt, "not_found", "not_found", None, blob_result.status)
    if state == "permission_denied":
        return _fail(ctx, receipt, "permission_denied", "permission_denied", blob_result.error, blob_result.status)
    if state != "ok" or data is None:
        if ctx.config.prefer == "auto":
            raw = _read_raw(ctx, repo, commit, path)
            if raw.truncated:
                return _truncated(ctx, receipt, raw, "raw_commit_path")
            if not http_failure_class(raw):
                _finalize_bytes(ctx, receipt, raw.body, meta_size, meta_sha, "raw_commit_path")
                return receipt
        return _fail(ctx, receipt, "read_failed", state, blob_result.error, blob_result.status)
    _finalize_bytes(ctx, receipt, data, meta_size if isinstance(meta_size, int) else len(data), meta_sha, "git_blob_base64")
    return receipt


def _read_path(ctx: Ctx, repo: str, commit: str, path: str, phase: str) -> dict:
    if ctx.config.contents_transport == "handoff":
        receipt = _base_path(ctx, repo, commit, path, phase)
        item = _handoff_file(ctx, repo, commit, path)
        if item is None:
            receipt["not_attempted_reason"] = "connector_asset_not_supplied"
            receipt["read_method"] = None
            _apply_temporal(receipt, ctx.expectations)
            _usability(receipt, None)
            return receipt
        receipt["pin_verified"] = True
        return _read_asset(ctx, receipt, item)
    return _read_api_path(ctx, repo, commit, path, phase)


def _select_extras(role: str, parsed: dict[str, object]) -> list[str]:
    if role == "commodities":
        chosen = []
        status = parsed.get("data/last_run_status.json")
        if isinstance(status, dict):
            chosen.append("data/report_input_latest.json")
        night = parsed.get("data/night_session/last_run_status.json")
        if isinstance(night, dict) and any(
            key in night for key in ("trading_date", "generated_at", "records", "published")
        ):
            chosen.append("data/night_session/latest.json")
        return chosen
    if role == "stock":
        manifest = parsed.get("data/latest/manifest.json")
        if not isinstance(manifest, dict):
            return []
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, dict):
            return []
        chosen = []
        allow = set(ALLOW["stock"])
        for key in artifacts:
            if not isinstance(key, str):
                continue
            path = key if key.startswith("data/") else f"data/latest/{key}"
            if path in allow:
                chosen.append(path)
        return chosen
    radar = parsed.get("data/radar_latest.json")
    chosen = []
    if isinstance(radar, dict):
        for path in ALLOW["options"]:
            if _string_contains_path(radar, path):
                chosen.append(path)
    return chosen


def _string_contains_path(obj, path: str) -> bool:
    if isinstance(obj, str):
        return obj == path
    if isinstance(obj, dict):
        return any(_string_contains_path(value, path) for value in obj.values())
    if isinstance(obj, list):
        return any(_string_contains_path(value, path) for value in obj)
    return False


def _unused(ctx: Ctx, repo: str, commit: str | None, role: str, used: set[str]) -> list[dict]:
    rows = []
    for path in ALLOW[role]:
        if path in used:
            continue
        receipt = _base_path(ctx, repo, commit, path, "not_selected")
        receipt["not_attempted_reason"] = "not_selected_by_metadata"
        receipt["resolved_commit"] = commit
        _apply_temporal(receipt, ctx.expectations)
        _usability(receipt, None)
        rows.append(receipt)
    return rows


def execute(config: RunConfig, transport) -> dict:
    edition = config.edition or infer_edition(config.cutoff)
    expectations = session_expectations(config.cutoff)
    fetched = config.fetched_at or datetime.now(SHANGHAI)
    ctx = Ctx(
        config=config,
        transport=transport,
        expectations=expectations,
        edition=edition,
        fetched_at=fetched.astimezone(SHANGHAI).isoformat(),
        evidence_dir=config.output_dir,
    )
    repos_out = []
    for spec in REPOS:
        if config.commits_transport == "handoff":
            pin = _resolve_handoff(ctx, spec["repo"])
        else:
            pin = _resolve_api(ctx, spec["repo"])
        pin["role"] = spec["role"]
        paths = []
        commit = pin.get("resolved_commit")
        if pin["resolve_status"] != "ok" or not commit:
            for path in list(spec["metadata"]) + list(spec["status_follow"]) + list(ALLOW[spec["role"]]):
                receipt = _base_path(ctx, spec["repo"], None, path, "metadata" if path in spec["metadata"] else "not_selected")
                receipt["not_attempted_reason"] = f"repo_resolve_{pin['resolve_status']}"
                receipt["commit_time"] = pin.get("commit_time")
                _apply_temporal(receipt, expectations)
                _usability(receipt, None)
                paths.append(receipt)
            pin["paths"] = paths
            repos_out.append(pin)
            continue
        parsed: dict[str, object] = {}
        for path in spec["metadata"]:
            receipt = _read_path(ctx, spec["repo"], commit, path, "metadata")
            receipt["commit_time"] = pin.get("commit_time")
            paths.append(receipt)
            parsed[path] = _parsed_if_usable(receipt, config.output_dir)
        for path in spec["status_follow"]:
            receipt = _read_path(ctx, spec["repo"], commit, path, "metadata")
            receipt["commit_time"] = pin.get("commit_time")
            paths.append(receipt)
            parsed[path] = _parsed_if_usable(receipt, config.output_dir)
        selected = _select_extras(spec["role"], parsed)
        used = set(spec["metadata"]) | set(spec["status_follow"]) | set(selected)
        for path in selected:
            if path in spec["metadata"] or path in spec["status_follow"]:
                continue
            receipt = _read_path(ctx, spec["repo"], commit, path, "value_selected")
            receipt["commit_time"] = pin.get("commit_time")
            paths.append(receipt)
        paths.extend(_unused(ctx, spec["repo"], commit, spec["role"], used))
        for receipt in paths:
            receipt["commit_time"] = pin.get("commit_time")
        pin["paths"] = paths
        repos_out.append(pin)
    authenticated = bool(
        getattr(transport, "use_env_auth", False)
        and (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"))
    )
    return {
        "engine_read_version": __version__,
        "stable": False,
        "stability_note": "not_stable_until_routine_reads_succeed",
        "fixture_mode": config.fixture_mode,
        "cutoff": config.cutoff.isoformat(),
        "timezone": "Asia/Shanghai",
        "fetched_at": ctx.fetched_at,
        "edition": edition,
        "session_expectations": expectations,
        "commits_transport": config.transport_label_commits,
        "contents_transport": config.transport_label_contents,
        "authenticated": authenticated,
        "repos": repos_out,
    }


def _parsed_if_usable(receipt: dict, output_dir: Path):
    if receipt["read_status"] not in {"ok", "stale", "valid_zero"} or not receipt.get("evidence_path"):
        if receipt["read_status"] == "valid_zero" and receipt["parse_result"] == "empty_object":
            return {}
        if receipt["read_status"] == "valid_zero" and receipt["parse_result"] == "empty_array":
            return []
        return None
    try:
        return json.loads(Path(receipt["evidence_path"]).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def write_outputs(output_dir: Path, result: dict) -> None:
    atomic_write_json(output_dir / "engine_read_receipts.json", result)
    pins = []
    for repo in result["repos"]:
        pins.append(
            {
                "role": repo.get("role"),
                "repo": repo.get("repo"),
                "requested_ref": repo.get("requested_ref"),
                "resolved_commit": repo.get("resolved_commit"),
                "commit_time": repo.get("commit_time"),
                "resolve_status": repo.get("resolve_status"),
                "commits_transport": repo.get("commits_transport"),
                "fixture_mode": result.get("fixture_mode"),
            }
        )
    atomic_write_json(
        output_dir / "engine_read_pins.json",
        {
            "stable": False,
            "cutoff": result["cutoff"],
            "timezone": result["timezone"],
            "commits_transport": result["commits_transport"],
            "contents_transport": result["contents_transport"],
            "repos": pins,
        },
    )


def load_handoff(path: str) -> dict:
    if path == "-":
        import sys

        raw = sys.stdin.read()
    else:
        raw = Path(path).read_text(encoding="utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise SystemExit("handoff must be a JSON object")
    return payload


def config_from_args(args, handoff: dict | None) -> RunConfig:
    if args.cutoff and args.as_of:
        left = parse_instant(args.cutoff)
        right = parse_instant(args.as_of)
        if left != right:
            raise SystemExit("--cutoff and --as-of differ")
        cutoff = left
    elif args.cutoff or args.as_of:
        cutoff = parse_instant(args.cutoff or args.as_of)
    elif handoff and isinstance(handoff.get("cutoff"), str):
        cutoff = parse_instant(handoff["cutoff"])
    else:
        raise SystemExit("--cutoff or --as-of is required")
    output = assert_output_dir(Path(args.output_dir))
    fixture_mode = bool(args.fixture) or bool(handoff and handoff.get("fixture_mode") is True and not args.fixture and args.commits_transport == "handoff" and args.contents_transport == "handoff")
    if args.fixture:
        commits_transport = "fixture"
        contents_transport = "fixture"
        commits_label = "fixture"
        contents_label = "fixture"
        fixture_mode = True
    else:
        commits_transport = args.commits_transport
        contents_transport = args.contents_transport
        commits_label = "github_api" if commits_transport == "api" else "connector_list_commits"
        contents_label = "github_api" if contents_transport == "api" else "contents"
        if commits_transport == "handoff" and contents_transport == "handoff" and handoff and handoff.get("fixture_mode") is True:
            fixture_mode = True
    fetched = parse_instant(args.fetched_at) if args.fetched_at else None
    if fetched is None and handoff and isinstance(handoff.get("fetched_at"), str):
        fetched = parse_instant(handoff["fetched_at"])
    return RunConfig(
        cutoff=cutoff,
        output_dir=output,
        requested_ref=args.ref,
        edition=args.edition,
        fixture_mode=fixture_mode,
        commits_transport="handoff" if commits_transport == "handoff" else "api",
        contents_transport="handoff" if contents_transport == "handoff" else "api",
        prefer=args.prefer,
        max_bytes=args.max_bytes,
        timeout=args.timeout,
        fetched_at=fetched,
        handoff=handoff,
        transport_label_commits=commits_label,
        transport_label_contents=contents_label,
    )


def fixture_transport(path: str):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return MapTransport(load_fixture_routes(payload))
