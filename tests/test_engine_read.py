"""Fixture tests for the engine read helper. No live network."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from engine_read.run import (
    RunConfig,
    assert_output_dir,
    commits_url,
    contents_url,
    blob_url,
    execute,
    git_blob_sha1,
    parse_instant,
    raw_url,
    repo_root,
    sha256_hex,
    write_outputs,
)
from engine_read.transport import GithubHttpTransport, HttpResult, MapTransport

CUTOFF = "2026-11-06T07:50:00+08:00"
WHEN = "2026-11-06T06:00:00+08:00"
LATER = "2026-11-06T08:30:00+08:00"
REPOS = {
    "commodities": "farfromexact/China-Commodities-Engine",
    "stock": "farfromexact/China-Stock-Engine",
    "options": "farfromexact/China-Options-Engine",
}
SHA = {
    "commodities": "a" * 40,
    "stock": "b" * 40,
    "options": "c" * 40,
}
MOVED = "d" * 40


def _commit(sha: str, when: str) -> dict:
    return {"sha": sha, "commit": {"committer": {"date": when}, "message": "fixture"}}


def _json_bytes(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _b64_newlines(data: bytes) -> str:
    text = base64.b64encode(data).decode("ascii")
    return "\n".join(text[i : i + 60] for i in range(0, len(text), 60)) + "\n"


def _http_json(status: int, obj) -> HttpResult:
    return HttpResult(status=status, headers={}, body=_json_bytes(obj))


def _contents(data: bytes, path: str, *, encoding="base64", content=None, size=None, sha=None) -> dict:
    digest = sha if sha is not None else git_blob_sha1(data)
    if content is None:
        content = _b64_newlines(data) if encoding == "base64" else ""
    return {
        "type": "file",
        "encoding": encoding,
        "size": len(data) if size is None else size,
        "sha": digest,
        "content": content,
        "path": path,
    }


def _blob(data: bytes) -> dict:
    return {
        "encoding": "base64",
        "size": len(data),
        "sha": git_blob_sha1(data),
        "content": _b64_newlines(data),
    }


def _sized(n: int) -> bytes:
    base = {
        "fixture": "synthetic",
        "label": "size_probe",
        "official_night_close_verified": False,
        "pad": "",
        "price_semantics": "vendor_latest_trade_asof_snapshot",
    }
    skeleton = _json_bytes(base)
    extra = n - len(skeleton)
    if extra < 0:
        raise AssertionError(f"skeleton {len(skeleton)} exceeds {n}")
    base["pad"] = "x" * extra
    data = _json_bytes(base)
    if len(data) != n:
        raise AssertionError(f"sized document {len(data)} != {n}")
    return data


class ReaderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _config(self, **kwargs) -> RunConfig:
        defaults = dict(
            cutoff=parse_instant(CUTOFF),
            output_dir=self.out,
            fixture_mode=True,
            commits_transport="api",
            contents_transport="api",
            transport_label_commits="fixture",
            transport_label_contents="fixture",
            fetched_at=parse_instant("2026-11-06T07:50:05+08:00"),
            timeout=5,
        )
        defaults.update(kwargs)
        return RunConfig(**defaults)

    def _routes(self, files: dict[tuple[str, str, str], HttpResult], commits=None, extra=None) -> MapTransport:
        routes = {}
        chosen = commits or {
            role: [_commit(SHA[role], WHEN)] for role in SHA
        }
        for role, repo in REPOS.items():
            routes[commits_url(repo, "main", parse_instant(CUTOFF))] = _http_json(200, chosen[role])
        for (repo, commit, path), result in files.items():
            routes[contents_url(repo, commit, path)] = result
        if extra:
            routes.update(extra)
        return MapTransport(routes)

    def _run(self, transport, **kwargs):
        result = execute(self._config(**kwargs), transport)
        write_outputs(self.out, result)
        return result

    def _path(self, result, role, path):
        repo = next(item for item in result["repos"] if item["role"] == role)
        return next(item for item in repo["paths"] if item["path"] == path)

    def test_small_files_pin_and_do_not_follow_main(self):
        files = {}
        bodies = {}
        for role, repo in REPOS.items():
            if role == "commodities":
                spec = {
                    "data/last_run_status.json": {
                        "data_fresh": True,
                        "fixture": "synthetic",
                        "generated_at": "2026-11-06T06:05:56+08:00",
                        "modules": [
                            {
                                "dataset": "futures",
                                "is_fresh": True,
                                "records": 1,
                                "requested_trade_date": "2026-11-05",
                                "scope": "SHFE",
                                "state": "ok",
                                "trade_date": "2026-11-05",
                            }
                        ],
                        "run_date": "2026-11-05",
                    },
                    "data/night_session/last_run_status.json": {"fixture": "synthetic", "schema_version": 1},
                    "data/report_input_latest.json": {"fixture": "synthetic", "label": "report_input"},
                }
            elif role == "stock":
                spec = {
                    "data/last_run_status.json": {
                        "data_fresh": False,
                        "fixture": "synthetic",
                        "last_valid_trade_date": "2026-11-05",
                        "state": "ok",
                    },
                    "data/latest/manifest.json": {
                        "artifacts": {"daily_quotes.parquet": {"sha256": "abc"}},
                        "data_fresh": True,
                        "fixture": "synthetic",
                        "source_trade_date": "2026-11-05",
                        "trade_date": "2026-11-05",
                    },
                }
            else:
                spec = {
                    "data/radar_latest.json": {
                        "data_fresh": True,
                        "date": "2026-11-05",
                        "fixture": "synthetic",
                        "generated_at": "2026-11-06T07:17:43+08:00",
                    }
                }
            for path, obj in spec.items():
                data = _json_bytes(obj)
                bodies[(role, path)] = data
                files[(repo, SHA[role], path)] = _http_json(200, _contents(data, path))
        result = self._run(self._routes(files))
        self.assertFalse(result["stable"])
        self.assertTrue(result["fixture_mode"])
        self.assertEqual(result["commits_transport"], "fixture")
        self.assertFalse(result["authenticated"])
        for role in SHA:
            pin = next(item for item in result["repos"] if item["role"] == role)
            self.assertEqual(pin["resolved_commit"], SHA[role])
            self.assertEqual(pin["resolve_status"], "ok")
        status = self._path(result, "commodities", "data/last_run_status.json")
        self.assertEqual(status["read_status"], "ok")
        self.assertEqual(status["read_method"], "contents_at_sha")
        self.assertEqual(status["parse_result"], "json_ok")
        self.assertEqual(status["trade_date"], None)
        self.assertEqual(status["freshness_date"], "2026-11-05")
        self.assertEqual(status["freshness_date_field"], "modules.trade_date")
        self.assertEqual(status["run_date"], "2026-11-05")
        self.assertEqual(status["sha256"], sha256_hex(bodies[("commodities", "data/last_run_status.json")]))
        self.assertEqual(status["source_status"], "ok")
        self.assertTrue(status["research_usable"])
        self.assertFalse(status["execution_usable"])
        manifest = self._path(result, "stock", "data/latest/manifest.json")
        self.assertIsNone(manifest["quote_dates"])
        self.assertEqual(manifest["source_trade_date"], "2026-11-05")
        unused = self._path(result, "stock", "data/latest/opportunity_radar_latest.json")
        self.assertEqual(unused["read_status"], "not_attempted")
        self.assertEqual(unused["not_attempted_reason"], "not_selected_by_metadata")
        self.assertIsNone(unused["source_status"])

    def test_calls_stay_on_resolved_commit(self):
        repo = REPOS["commodities"]
        status = _json_bytes({"fixture": "synthetic", "trade_date": "2026-11-05"})
        night = _json_bytes({"fixture": "synthetic"})
        report = _json_bytes({"fixture": "synthetic", "label": "report_input"})
        files = {
            (repo, SHA["commodities"], "data/last_run_status.json"): _http_json(200, _contents(status, "data/last_run_status.json")),
            (repo, SHA["commodities"], "data/night_session/last_run_status.json"): _http_json(200, _contents(night, "data/night_session/last_run_status.json")),
            (repo, SHA["commodities"], "data/report_input_latest.json"): _http_json(200, _contents(report, "data/report_input_latest.json")),
            (REPOS["stock"], SHA["stock"], "data/last_run_status.json"): _http_json(200, _contents(_json_bytes({"fixture": "synthetic", "trade_date": "2026-11-05"}), "data/last_run_status.json")),
            (REPOS["stock"], SHA["stock"], "data/latest/manifest.json"): _http_json(200, _contents(_json_bytes({"fixture": "synthetic", "trade_date": "2026-11-05", "artifacts": {}}), "data/latest/manifest.json")),
            (REPOS["options"], SHA["options"], "data/radar_latest.json"): _http_json(200, _contents(_json_bytes({"fixture": "synthetic", "date": "2026-11-05"}), "data/radar_latest.json")),
        }
        transport = self._routes(files)
        self._run(transport)
        for call in transport.calls:
            url = call["url"]
            if "/contents/" in url or "raw.githubusercontent.com" in url or "/git/blobs/" in url:
                self.assertNotIn("main", url)
                self.assertNotIn("ref=main", url)
            self.assertNotIn("Authorization", call["headers"])

    def test_large_newline_base64_blob_not_clipped(self):
        data = _sized(1_612_360)
        repo = REPOS["commodities"]
        path = "data/night_session/latest.json"
        digest = git_blob_sha1(data)
        contents = _contents(data, path, encoding="none", content="", size=len(data), sha=digest)
        self.assertEqual(contents["content"], "")
        self.assertEqual(contents["encoding"], "none")
        status = _json_bytes(
            {
                "fixture": "synthetic",
                "generated_at": "2026-11-06T06:00:00+08:00",
                "modules": [{"dataset": "futures", "records": 1, "state": "ok", "trade_date": "2026-11-05"}],
            }
        )
        night_status = _json_bytes(
            {
                "fixture": "synthetic",
                "generated_at": "2026-11-06T05:59:29+08:00",
                "official_night_close_verified": False,
                "price_semantics": "vendor_latest_trade_asof_snapshot",
                "trading_date": "2026-11-06",
            }
        )
        report = _json_bytes({"fixture": "synthetic", "label": "report_input"})
        files = {
            (repo, SHA["commodities"], "data/last_run_status.json"): _http_json(200, _contents(status, "data/last_run_status.json")),
            (repo, SHA["commodities"], "data/night_session/last_run_status.json"): _http_json(200, _contents(night_status, "data/night_session/last_run_status.json")),
            (repo, SHA["commodities"], "data/report_input_latest.json"): _http_json(200, _contents(report, "data/report_input_latest.json")),
            (repo, SHA["commodities"], path): _http_json(200, contents),
            (REPOS["stock"], SHA["stock"], "data/last_run_status.json"): _http_json(200, _contents(_json_bytes({"fixture": "synthetic", "trade_date": "2026-11-05"}), "x")),
            (REPOS["stock"], SHA["stock"], "data/latest/manifest.json"): _http_json(200, _contents(_json_bytes({"artifacts": {}, "fixture": "synthetic", "trade_date": "2026-11-05"}), "m")),
            (REPOS["options"], SHA["options"], "data/radar_latest.json"): _http_json(200, _contents(_json_bytes({"date": "2026-11-05", "fixture": "synthetic"}), "r")),
        }
        extra = {blob_url(repo, digest): _http_json(200, _blob(data))}
        transport = self._routes(files, extra=extra)
        result = self._run(transport)
        receipt = self._path(result, "commodities", path)
        self.assertEqual(receipt["read_method"], "git_blob_base64")
        self.assertEqual(receipt["read_status"], "ok")
        self.assertEqual(receipt["actual_size"], 1_612_360)
        self.assertEqual(receipt["declared_size"], 1_612_360)
        self.assertEqual(receipt["sha"], digest)
        self.assertEqual(receipt["sha256"], sha256_hex(data))
        self.assertEqual(receipt["parse_result"], "json_ok")
        self.assertEqual(receipt["snapshot_class"], "vendor_latest_trade_asof_snapshot")
        self.assertFalse(receipt["execution_usable"])
        self.assertEqual(receipt["execution_usable_reason"], "vendor_snapshot_not_official_close")
        self.assertTrue(receipt["research_usable"])
        self.assertIn("\n", _blob(data)["content"])
        blob_calls = [call for call in transport.calls if call["url"] == blob_url(repo, digest)]
        self.assertEqual(len(blob_calls), 1)

    def test_empty_object_array_and_zero_bytes(self):
        empty_obj = b"{}"
        empty_arr = b"[]"
        zero = b""
        files = {
            (REPOS["commodities"], SHA["commodities"], "data/last_run_status.json"): _http_json(200, _contents(empty_obj, "data/last_run_status.json")),
            (REPOS["commodities"], SHA["commodities"], "data/night_session/last_run_status.json"): HttpResult(status=404, headers={}, body=b""),
            (REPOS["commodities"], SHA["commodities"], "data/report_input_latest.json"): HttpResult(status=404, headers={}, body=b""),
            (REPOS["stock"], SHA["stock"], "data/last_run_status.json"): _http_json(200, _contents(empty_arr, "data/last_run_status.json")),
            (REPOS["stock"], SHA["stock"], "data/latest/manifest.json"): _http_json(200, _contents(_json_bytes({"artifacts": {}, "fixture": "synthetic", "trade_date": "2026-11-05"}), "m")),
            (REPOS["options"], SHA["options"], "data/radar_latest.json"): _http_json(200, _contents(zero, "data/radar_latest.json", encoding="base64", content="", size=0, sha=git_blob_sha1(zero))),
        }
        result = self._run(self._routes(files))
        obj = self._path(result, "commodities", "data/last_run_status.json")
        arr = self._path(result, "stock", "data/last_run_status.json")
        empty = self._path(result, "options", "data/radar_latest.json")
        self.assertEqual(obj["read_status"], "valid_zero")
        self.assertEqual(obj["parse_result"], "empty_object")
        self.assertEqual(arr["read_status"], "valid_zero")
        self.assertEqual(arr["parse_result"], "empty_array")
        self.assertEqual(empty["read_status"], "actual_empty")
        self.assertEqual(empty["parse_result"], "not_attempted")
        self.assertFalse(obj["research_usable"])
        self.assertFalse(arr["research_usable"])
        self.assertFalse(empty["research_usable"])

    def test_truncated_body_is_not_parsed_as_json_lines(self):
        payload = _json_bytes({"fixture": "synthetic", "rows": [{"label": "synthetic"}, {"label": "synthetic"}]})
        wrapped = _json_bytes(_blob(payload))
        self.assertGreater(len(wrapped), 80)
        repo = REPOS["options"]
        path = "data/radar_latest.json"
        contents = _contents(payload, path, encoding="none", content="", size=len(payload), sha=git_blob_sha1(payload))
        files = {
            (REPOS["commodities"], SHA["commodities"], "data/last_run_status.json"): _http_json(200, _contents(_json_bytes({"fixture": "synthetic", "trade_date": "2026-11-05"}), "s")),
            (REPOS["commodities"], SHA["commodities"], "data/night_session/last_run_status.json"): HttpResult(status=404, headers={}, body=b""),
            (REPOS["commodities"], SHA["commodities"], "data/report_input_latest.json"): HttpResult(status=404, headers={}, body=b""),
            (REPOS["stock"], SHA["stock"], "data/last_run_status.json"): _http_json(200, _contents(_json_bytes({"fixture": "synthetic", "trade_date": "2026-11-05"}), "s")),
            (REPOS["stock"], SHA["stock"], "data/latest/manifest.json"): _http_json(200, _contents(_json_bytes({"artifacts": {}, "fixture": "synthetic", "trade_date": "2026-11-05"}), "m")),
            (repo, SHA["options"], path): _http_json(200, contents),
        }
        extra = {blob_url(repo, git_blob_sha1(payload)): HttpResult(status=200, headers={}, body=wrapped)}
        result = self._run(self._routes(files, extra=extra), max_bytes=150)
        receipt = self._path(result, "options", path)
        self.assertEqual(receipt["read_status"], "truncated")
        self.assertEqual(receipt["parse_result"], "not_attempted")
        self.assertIsNone(receipt["sha256"])
        self.assertIsNone(receipt.get("trade_date"))
        self.assertFalse(receipt["research_usable"])

    def test_bad_json_and_size_mismatch(self):
        bad = b'{"fixture":'
        repo = REPOS["options"]
        files = {
            (REPOS["commodities"], SHA["commodities"], "data/last_run_status.json"): _http_json(200, _contents(_json_bytes({"fixture": "synthetic", "trade_date": "2026-11-05"}), "s")),
            (REPOS["commodities"], SHA["commodities"], "data/night_session/last_run_status.json"): HttpResult(status=404, headers={}, body=b""),
            (REPOS["commodities"], SHA["commodities"], "data/report_input_latest.json"): HttpResult(status=404, headers={}, body=b""),
            (REPOS["stock"], SHA["stock"], "data/last_run_status.json"): _http_json(200, _contents(b'{"trade_date":"2026-11-05","fixture":"synthetic","pad":"short"}', "s", size=50, sha=git_blob_sha1(b'{"trade_date":"2026-11-05","fixture":"synthetic","pad":"short"}'))),
            (REPOS["stock"], SHA["stock"], "data/latest/manifest.json"): _http_json(200, _contents(_json_bytes({"artifacts": {}, "fixture": "synthetic", "trade_date": "2026-11-05"}), "m")),
            (repo, SHA["options"], "data/radar_latest.json"): _http_json(200, _contents(bad, "data/radar_latest.json")),
        }
        result = self._run(self._routes(files))
        parsed = self._path(result, "options", "data/radar_latest.json")
        self.assertEqual(parsed["read_status"], "parse_error")
        self.assertEqual(parsed["source_status"], "parse_error")
        self.assertFalse(parsed["research_usable"])
        # Clipped contents whose decoded size disagrees with declared size must not be accepted.
        stock = self._path(result, "stock", "data/last_run_status.json")
        self.assertNotEqual(stock["read_status"], "ok")
        self.assertIsNone(stock["trade_date"])

    def test_timeout_permission_and_not_found_do_not_block_other_repos(self):
        stock_status = _json_bytes({"fixture": "synthetic", "trade_date": "2026-11-05"})
        manifest = _json_bytes({"artifacts": {}, "fixture": "synthetic", "trade_date": "2026-11-05"})
        files = {
            (REPOS["stock"], SHA["stock"], "data/last_run_status.json"): HttpResult(status=401, headers={}, body=b'{"message":"bad credentials"}'),
            (REPOS["stock"], SHA["stock"], "data/latest/manifest.json"): _http_json(200, _contents(manifest, "m")),
            (REPOS["options"], SHA["options"], "data/radar_latest.json"): HttpResult(status=404, headers={}, body=b'{"message":"Not Found"}'),
        }
        commits = {
            "commodities": [],
            "stock": [_commit(SHA["stock"], WHEN)],
            "options": [_commit(SHA["options"], WHEN)],
        }
        # timeout is an error result, not an empty list. Override commodities after build.
        transport = self._routes(files, commits=commits)
        transport.routes[commits_url(REPOS["commodities"], "main", parse_instant(CUTOFF))] = [
            HttpResult(status=None, headers={}, body=b"", error_class="timeout", error="timed out")
        ]
        result = self._run(transport)
        roles = {item["role"]: item for item in result["repos"]}
        self.assertEqual(set(roles), {"commodities", "stock", "options"})
        self.assertEqual(roles["commodities"]["resolve_status"], "read_failed")
        self.assertEqual(roles["commodities"]["error_class"], "timeout")
        self.assertEqual(roles["commodities"]["paths"][0]["read_status"], "not_attempted")
        self.assertIsNone(roles["commodities"]["paths"][0]["source_status"])
        denied = self._path(result, "stock", "data/last_run_status.json")
        self.assertEqual(denied["read_status"], "permission_denied")
        self.assertEqual(denied["source_status"], "permission_error")
        missing = self._path(result, "options", "data/radar_latest.json")
        self.assertEqual(missing["read_status"], "not_found")
        self.assertTrue(missing["counts_as_missing"])
        self.assertEqual(missing["source_status"], "missing")
        manifest_receipt = self._path(result, "stock", "data/latest/manifest.json")
        self.assertEqual(manifest_receipt["read_status"], "ok")
        auth_calls = [call for call in transport.calls if "Authorization" in call["headers"]]
        self.assertEqual(auth_calls, [])
        status_calls = [call for call in transport.calls if call["url"] == contents_url(REPOS["stock"], SHA["stock"], "data/last_run_status.json")]
        self.assertEqual(len(status_calls), 1)

    def test_later_commit_is_not_used_and_cached_body_stays_on_pin(self):
        old = _json_bytes({"fixture": "synthetic", "label": "pinned", "trade_date": "2026-11-05"})
        new = _json_bytes({"fixture": "synthetic", "label": "moved", "trade_date": "2026-11-06"})
        repo = REPOS["commodities"]
        files = {
            (repo, SHA["commodities"], "data/last_run_status.json"): _http_json(200, _contents(old, "data/last_run_status.json")),
            (repo, MOVED, "data/last_run_status.json"): _http_json(200, _contents(new, "data/last_run_status.json")),
            (repo, SHA["commodities"], "data/night_session/last_run_status.json"): HttpResult(status=404, headers={}, body=b""),
            (repo, SHA["commodities"], "data/report_input_latest.json"): HttpResult(status=404, headers={}, body=b""),
            (REPOS["stock"], SHA["stock"], "data/last_run_status.json"): _http_json(200, _contents(_json_bytes({"fixture": "synthetic", "trade_date": "2026-11-05"}), "s")),
            (REPOS["stock"], SHA["stock"], "data/latest/manifest.json"): _http_json(200, _contents(_json_bytes({"artifacts": {}, "fixture": "synthetic", "trade_date": "2026-11-05"}), "m")),
            (REPOS["options"], SHA["options"], "data/radar_latest.json"): _http_json(200, _contents(_json_bytes({"date": "2026-11-05", "fixture": "synthetic"}), "r")),
        }
        extra = {
            raw_url(repo, "main", "data/last_run_status.json"): HttpResult(status=200, headers={}, body=new),
            raw_url(repo, MOVED, "data/last_run_status.json"): HttpResult(status=200, headers={}, body=new),
        }
        commits = {
            "commodities": [_commit(MOVED, LATER), _commit(SHA["commodities"], WHEN)],
            "stock": [_commit(SHA["stock"], WHEN)],
            "options": [_commit(SHA["options"], WHEN)],
        }
        transport = self._routes(files, commits=commits, extra=extra)
        # A second listing would show only the moved commit. It must not be requested.
        transport.routes[commits_url(repo, "main", parse_instant(CUTOFF))] = [
            _http_json(200, [_commit(MOVED, LATER), _commit(SHA["commodities"], WHEN)]),
            _http_json(200, [_commit(MOVED, LATER)]),
        ]
        result = self._run(transport)
        pin = next(item for item in result["repos"] if item["role"] == "commodities")
        self.assertEqual(pin["resolved_commit"], SHA["commodities"])
        receipt = self._path(result, "commodities", "data/last_run_status.json")
        self.assertEqual(receipt["sha256"], sha256_hex(old))
        self.assertNotEqual(receipt["sha256"], sha256_hex(new))
        urls = [call["url"] for call in transport.calls]
        self.assertNotIn(contents_url(repo, MOVED, "data/last_run_status.json"), urls)
        self.assertNotIn(raw_url(repo, "main", "data/last_run_status.json"), urls)
        self.assertEqual(urls.count(commits_url(repo, "main", parse_instant(CUTOFF))), 1)

    def test_success_backfill_old_trade_date_is_stale(self):
        status = _json_bytes(
            {
                "data_fresh": True,
                "fixture": "synthetic",
                "last_valid_trade_date": "2026-10-30",
                "state": "success_backfill",
            }
        )
        manifest = _json_bytes(
            {
                "artifacts": {},
                "data_fresh": True,
                "fixture": "synthetic",
                "source_trade_date": "2026-10-30",
                "trade_date": "2026-10-30",
            }
        )
        files = {
            (REPOS["commodities"], SHA["commodities"], "data/last_run_status.json"): _http_json(200, _contents(_json_bytes({"fixture": "synthetic", "trade_date": "2026-11-05"}), "s")),
            (REPOS["commodities"], SHA["commodities"], "data/night_session/last_run_status.json"): HttpResult(status=404, headers={}, body=b""),
            (REPOS["commodities"], SHA["commodities"], "data/report_input_latest.json"): HttpResult(status=404, headers={}, body=b""),
            (REPOS["stock"], SHA["stock"], "data/last_run_status.json"): _http_json(200, _contents(status, "data/last_run_status.json")),
            (REPOS["stock"], SHA["stock"], "data/latest/manifest.json"): _http_json(200, _contents(manifest, "data/latest/manifest.json")),
            (REPOS["options"], SHA["options"], "data/radar_latest.json"): _http_json(200, _contents(_json_bytes({"date": "2026-11-05", "fixture": "synthetic"}), "r")),
        }
        result = self._run(self._routes(files))
        status_receipt = self._path(result, "stock", "data/last_run_status.json")
        self.assertEqual(status_receipt["read_status"], "stale")
        self.assertTrue(status_receipt["success_flag"])
        self.assertTrue(status_receipt["data_fresh"])
        self.assertEqual(status_receipt["trade_date"], None)
        self.assertEqual(status_receipt["last_good"], {"field": "last_valid_trade_date", "value": "2026-10-30"})
        self.assertEqual(status_receipt["source_status"], "stale")
        self.assertEqual(status_receipt["research_usable_reason"], "stale_trade_date")
        self.assertFalse(status_receipt["execution_usable"])
        manifest_receipt = self._path(result, "stock", "data/latest/manifest.json")
        self.assertEqual(manifest_receipt["read_status"], "stale")
        self.assertIsNone(manifest_receipt["quote_dates"])
        self.assertTrue(manifest_receipt["data_fresh"])
        self.assertNotEqual(manifest_receipt["read_status"], "ok")

    def test_evening_night_not_started_is_not_a_missing_penalty(self):
        files = {
            (REPOS["commodities"], SHA["commodities"], "data/last_run_status.json"): _http_json(200, _contents(_json_bytes({"fixture": "synthetic", "trade_date": "2026-11-06"}), "s")),
            (REPOS["commodities"], SHA["commodities"], "data/night_session/last_run_status.json"): HttpResult(status=404, headers={}, body=b'{"message":"Not Found"}'),
            (REPOS["commodities"], SHA["commodities"], "data/report_input_latest.json"): HttpResult(status=404, headers={}, body=b""),
            (REPOS["stock"], SHA["stock"], "data/last_run_status.json"): _http_json(200, _contents(_json_bytes({"fixture": "synthetic", "trade_date": "2026-11-06"}), "s")),
            (REPOS["stock"], SHA["stock"], "data/latest/manifest.json"): _http_json(200, _contents(_json_bytes({"artifacts": {}, "fixture": "synthetic", "trade_date": "2026-11-06"}), "m")),
            (REPOS["options"], SHA["options"], "data/radar_latest.json"): _http_json(200, _contents(_json_bytes({"date": "2026-11-06", "fixture": "synthetic"}), "r")),
        }
        evening = parse_instant("2026-11-06T19:50:00+08:00")
        # Rebuild commit URLs for the evening cutoff.
        routes = {}
        for role, repo in REPOS.items():
            routes[commits_url(repo, "main", evening)] = _http_json(200, [_commit(SHA[role], "2026-11-06T11:00:00+08:00")])
        for (repo, commit, path), result in files.items():
            routes[contents_url(repo, commit, path)] = result
        result = self._run(MapTransport(routes), cutoff=evening, edition="evening")
        self.assertEqual(result["session_expectations"]["china_night_session_upcoming"], "not_started")
        self.assertEqual(result["session_expectations"]["china_day_session"], "completed")
        night = self._path(result, "commodities", "data/night_session/last_run_status.json")
        self.assertEqual(night["read_status"], "not_found")
        self.assertEqual(night["temporal_readiness"], "not_started")
        self.assertFalse(night["counts_as_missing"])
        self.assertIsNone(night["source_status"])
        latest = self._path(result, "commodities", "data/night_session/latest.json")
        self.assertEqual(latest["read_status"], "not_attempted")
        self.assertEqual(latest["upcoming_session"], "not_started")

    def test_weekend_not_due(self):
        saturday = parse_instant("2026-11-07T07:50:00+08:00")
        routes = {}
        for role, repo in REPOS.items():
            routes[commits_url(repo, "main", saturday)] = _http_json(200, [_commit(SHA[role], "2026-11-06T11:00:00+08:00")])
        routes[contents_url(REPOS["options"], SHA["options"], "data/radar_latest.json")] = HttpResult(status=404, headers={}, body=b"")
        routes[contents_url(REPOS["commodities"], SHA["commodities"], "data/last_run_status.json")] = _http_json(
            200, _contents(_json_bytes({"fixture": "synthetic", "trade_date": "2026-11-06"}), "s")
        )
        routes[contents_url(REPOS["commodities"], SHA["commodities"], "data/night_session/last_run_status.json")] = HttpResult(status=404, headers={}, body=b"")
        routes[contents_url(REPOS["commodities"], SHA["commodities"], "data/report_input_latest.json")] = HttpResult(status=404, headers={}, body=b"")
        routes[contents_url(REPOS["stock"], SHA["stock"], "data/last_run_status.json")] = _http_json(
            200, _contents(_json_bytes({"fixture": "synthetic", "trade_date": "2026-11-06"}), "s")
        )
        routes[contents_url(REPOS["stock"], SHA["stock"], "data/latest/manifest.json")] = _http_json(
            200, _contents(_json_bytes({"artifacts": {}, "fixture": "synthetic", "trade_date": "2026-11-06"}), "m")
        )
        result = self._run(MapTransport(routes), cutoff=saturday)
        self.assertEqual(result["edition"], "weekend")
        self.assertEqual(result["session_expectations"]["china_day_session"], "not_due")
        missing = self._path(result, "options", "data/radar_latest.json")
        self.assertEqual(missing["read_status"], "not_found")
        self.assertEqual(missing["temporal_readiness"], "not_due")
        self.assertFalse(missing["counts_as_missing"])
        self.assertIsNone(missing["source_status"])

    def test_handoff_validates_asset_and_rejects_clip_and_pin_mismatch(self):
        good = _json_bytes({"fixture": "synthetic", "trade_date": "2026-11-05"})
        clip = _json_bytes({"fixture": "synthetic", "trade_date": "2099-01-01"})
        asset = self.out / "status.json"
        clip_path = self.out / "clip.json"
        asset.write_bytes(good)
        clip_path.write_bytes(clip)
        handoff = {
            "fixture_mode": False,
            "files": [
                {
                    "repo": REPOS["commodities"],
                    "path": "data/last_run_status.json",
                    "commit": SHA["commodities"],
                    "asset_path": str(asset),
                    "declared_size": len(good),
                    "declared_sha": git_blob_sha1(good),
                    "tool": "get_file_contents",
                },
                {
                    "repo": REPOS["stock"],
                    "path": "data/last_run_status.json",
                    "commit": MOVED,
                    "asset_path": str(clip_path),
                    "declared_size": len(clip) + 32,
                    "declared_sha": git_blob_sha1(clip),
                    "tool": "get_file_contents",
                },
            ],
        }
        files = {
            (REPOS["commodities"], SHA["commodities"], "data/night_session/last_run_status.json"): HttpResult(status=404, headers={}, body=b""),
            (REPOS["options"], SHA["options"], "data/radar_latest.json"): _http_json(200, _contents(_json_bytes({"date": "2026-11-05", "fixture": "synthetic"}), "r")),
        }
        # Contents transport is handoff, so API file routes are unused except commits.
        # Stock manifest is not in the handoff.
        transport = self._routes({}, commits={role: [_commit(SHA[role], WHEN)] for role in SHA})
        result = self._run(
            transport,
            contents_transport="handoff",
            transport_label_commits="github_api",
            transport_label_contents="connector_handoff",
            fixture_mode=False,
            handoff=handoff,
        )
        self.assertFalse(result["fixture_mode"])
        self.assertEqual(result["commits_transport"], "github_api")
        self.assertEqual(result["contents_transport"], "connector_handoff")
        good_receipt = self._path(result, "commodities", "data/last_run_status.json")
        self.assertEqual(good_receipt["read_status"], "ok")
        self.assertEqual(good_receipt["read_method"], "connector_get_file_contents")
        self.assertEqual(good_receipt["sha256"], sha256_hex(good))
        self.assertEqual(good_receipt["sha"], git_blob_sha1(good))
        mismatch = self._path(result, "stock", "data/last_run_status.json")
        self.assertEqual(mismatch["read_status"], "read_failed")
        self.assertEqual(mismatch["error_class"], "pin_mismatch")
        self.assertIsNone(mismatch["trade_date"])
        # A short asset that matches the pin but not the declared size is not complete JSON.
        short = self.out / "short.json"
        short.write_bytes(clip)
        handoff["files"] = [
            {
                "repo": REPOS["options"],
                "path": "data/radar_latest.json",
                "commit": SHA["options"],
                "asset_path": str(short),
                "declared_size": len(clip) + 10,
                "declared_sha": git_blob_sha1(clip),
                "tool": "get_file_contents",
            }
        ]
        result = self._run(
            self._routes({}),
            contents_transport="handoff",
            transport_label_contents="connector_handoff",
            transport_label_commits="fixture",
            fixture_mode=False,
            handoff=handoff,
        )
        clipped = self._path(result, "options", "data/radar_latest.json")
        self.assertEqual(clipped["read_status"], "partial_validated")
        self.assertNotEqual(clipped["parse_result"], "json_ok")
        self.assertIsNone(clipped["trade_date"])
        self.assertFalse(clipped["research_usable"])

    def test_handoff_commits_are_independent_of_file_bytes(self):
        payload = _json_bytes({"fixture": "synthetic", "trade_date": "2026-11-05"})
        asset = self.out / "radar.json"
        asset.write_bytes(payload)
        handoff = {
            "fixture_mode": True,
            "fetched_at": "2026-11-06T07:50:05+08:00",
            "commits": {
                REPOS["commodities"]: {"resolved_commit": SHA["commodities"], "commit_time": WHEN},
                REPOS["stock"]: {"resolved_commit": SHA["stock"], "commit_time": LATER},
                REPOS["options"]: {"resolved_commit": SHA["options"], "commit_time": WHEN},
            },
            "files": [
                {
                    "repo": REPOS["options"],
                    "path": "data/radar_latest.json",
                    "commit": SHA["options"],
                    "asset_path": str(asset),
                    "declared_size": len(payload),
                    "declared_sha": git_blob_sha1(payload),
                }
            ],
        }
        transport = MapTransport({})
        result = self._run(
            transport,
            commits_transport="handoff",
            contents_transport="handoff",
            transport_label_commits="connector_list_commits",
            transport_label_contents="connector_handoff",
            fixture_mode=True,
            handoff=handoff,
        )
        self.assertEqual(transport.calls, [])
        self.assertTrue(result["fixture_mode"])
        self.assertEqual(result["commits_transport"], "connector_list_commits")
        self.assertNotEqual(result["commits_transport"], "github_api")
        stock = next(item for item in result["repos"] if item["role"] == "stock")
        self.assertEqual(stock["resolve_status"], "read_failed")
        self.assertEqual(stock["error_class"], "commit_after_cutoff")
        self.assertIsNone(stock["resolved_commit"])
        options = self._path(result, "options", "data/radar_latest.json")
        self.assertEqual(options["read_status"], "ok")
        self.assertEqual(options["sha256"], sha256_hex(payload))

    def test_naive_cutoff_and_output_guard_and_cli_fixture(self):
        self.assertEqual(parse_instant("2026-11-06T07:50:00").isoformat(), "2026-11-06T07:50:00+08:00")
        with self.assertRaises(SystemExit):
            assert_output_dir(repo_root() / "reports")
        repo = REPOS["options"]
        data = _json_bytes({"date": "2026-11-05", "fixture": "synthetic"})
        routes = {
            "responses": [
                {
                    "url": commits_url(REPOS["commodities"], "main", parse_instant(CUTOFF)),
                    "status": 200,
                    "json": [_commit(SHA["commodities"], WHEN)],
                },
                {
                    "url": commits_url(REPOS["stock"], "main", parse_instant(CUTOFF)),
                    "status": 200,
                    "json": [_commit(SHA["stock"], WHEN)],
                },
                {
                    "url": commits_url(repo, "main", parse_instant(CUTOFF)),
                    "status": 200,
                    "json": [_commit(SHA["options"], WHEN)],
                },
                {
                    "url": contents_url(REPOS["commodities"], SHA["commodities"], "data/last_run_status.json"),
                    "status": 200,
                    "json": _contents(_json_bytes({"fixture": "synthetic", "trade_date": "2026-11-05"}), "s"),
                },
                {
                    "url": contents_url(REPOS["commodities"], SHA["commodities"], "data/night_session/last_run_status.json"),
                    "status": 404,
                    "json": {"message": "Not Found"},
                },
                {
                    "url": contents_url(REPOS["commodities"], SHA["commodities"], "data/report_input_latest.json"),
                    "status": 404,
                    "json": {"message": "Not Found"},
                },
                {
                    "url": contents_url(REPOS["stock"], SHA["stock"], "data/last_run_status.json"),
                    "status": 200,
                    "json": _contents(_json_bytes({"fixture": "synthetic", "trade_date": "2026-11-05"}), "s"),
                },
                {
                    "url": contents_url(REPOS["stock"], SHA["stock"], "data/latest/manifest.json"),
                    "status": 200,
                    "json": _contents(_json_bytes({"artifacts": {}, "fixture": "synthetic", "trade_date": "2026-11-05"}), "m"),
                },
                {
                    "url": contents_url(repo, SHA["options"], "data/radar_latest.json"),
                    "status": 200,
                    "json": _contents(data, "data/radar_latest.json"),
                },
            ]
        }
        fixture = self.out / "fixture.json"
        fixture.write_text(json.dumps(routes), encoding="utf-8")
        out = self.out / "cli-out"
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "engine_read",
                "--as-of",
                "2026-11-06T07:50:00",
                "--output-dir",
                str(out),
                "--fixture",
                str(fixture),
                "--fetched-at",
                "2026-11-06T07:50:05+08:00",
            ],
            cwd=str(repo_root()),
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        saved = json.loads((out / "engine_read_receipts.json").read_text(encoding="utf-8"))
        self.assertTrue(saved["fixture_mode"])
        self.assertEqual(saved["commits_transport"], "fixture")
        self.assertFalse(saved["stable"])
        self.assertFalse(list(out.rglob("*.tmp")))
        denied = subprocess.run(
            [sys.executable, "-m", "engine_read", "--cutoff", CUTOFF, "--output-dir", str(repo_root() / "reports"), "--fixture", str(fixture)],
            cwd=str(repo_root()),
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(denied.returncode, 0)

    def test_env_token_is_not_attached_unless_opted_in(self):
        previous = os.environ.get("GITHUB_TOKEN")
        os.environ["GITHUB_TOKEN"] = "dummy-not-a-real-token"
        try:
            plain = GithubHttpTransport(use_env_auth=False)
            self.assertNotIn("Authorization", plain._auth_headers({}))
            opted = GithubHttpTransport(use_env_auth=True)
            self.assertEqual(opted._auth_headers({}).get("Authorization"), "Bearer dummy-not-a-real-token")
        finally:
            if previous is None:
                os.environ.pop("GITHUB_TOKEN", None)
            else:
                os.environ["GITHUB_TOKEN"] = previous

    def test_raw_commit_url_verifies_bytes(self):
        data = _json_bytes({"fixture": "synthetic", "label": "raw", "trade_date": "2026-11-05"})
        repo = REPOS["options"]
        path = "data/radar_latest.json"
        files = {
            (REPOS["commodities"], SHA["commodities"], "data/last_run_status.json"): _http_json(200, _contents(_json_bytes({"fixture": "synthetic", "trade_date": "2026-11-05"}), "s")),
            (REPOS["commodities"], SHA["commodities"], "data/night_session/last_run_status.json"): HttpResult(status=404, headers={}, body=b""),
            (REPOS["commodities"], SHA["commodities"], "data/report_input_latest.json"): HttpResult(status=404, headers={}, body=b""),
            (REPOS["stock"], SHA["stock"], "data/last_run_status.json"): _http_json(200, _contents(_json_bytes({"fixture": "synthetic", "trade_date": "2026-11-05"}), "s")),
            (REPOS["stock"], SHA["stock"], "data/latest/manifest.json"): _http_json(200, _contents(_json_bytes({"artifacts": {}, "fixture": "synthetic", "trade_date": "2026-11-05"}), "m")),
            (repo, SHA["options"], path): _http_json(200, _contents(data, path, encoding="none", content="", size=len(data), sha=git_blob_sha1(data))),
        }
        extra = {raw_url(repo, SHA["options"], path): HttpResult(status=200, headers={}, body=data)}
        result = self._run(self._routes(files, extra=extra), prefer="raw")
        receipt = self._path(result, "options", path)
        self.assertEqual(receipt["read_method"], "raw_commit_path")
        self.assertEqual(receipt["read_status"], "ok")
        self.assertEqual(receipt["sha"], git_blob_sha1(data))
        self.assertEqual(receipt["sha256"], sha256_hex(data))


if __name__ == "__main__":
    unittest.main()
