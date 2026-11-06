# Engine read protocol

Status: helper and fixture tests are in this branch. This is **not stable**. Do not treat it as stable until the parent routine’s own pinned reads succeed. Receipts set `stable` to false.

The helper reads three fixed repositories and nothing else:

- `farfromexact/China-Commodities-Engine`
- `farfromexact/China-Stock-Engine`
- `farfromexact/China-Options-Engine`

It does not write `reports/`, `latest/`, `status/`, or `manifests/`. Output must be a directory outside this archive repo. It does not call `gh`, does not read `~/.config/gh`, and does not invent a token. A 401 or 403 is `permission_denied` (rate-limit responses are `read_failed` / `rate_limit`). There is no second attempt with another credential.

Archive JSON still has exactly six files. Put receipts **next to** the existing `source_status` object as added fields. Do not rename `source_status` and do not add a seventh archive file.

## Which caller you are

The parent decides whether this machine may run Python.

- **Parent routine, Python allowed.** Run `python3 -m engine_read` here. Pass the unchanged evidence files and `engine_read_receipts.json` to the archive step.
- **ChatGPT scheduled task.** Do not assume `python3`, `gh`, or any subprocess exists. Use the connector calls in the next section and fill the same receipt fields yourself. `gh` on the parent box is not logged in; do not try to log it in.

`GITHUB_TOKEN` / `GH_TOKEN` are not required. The default HTTP transport is unauthenticated. `--allow-env-auth` attaches one of those variables only when the parent has already put it in the environment. The flag does not look for a token on disk.

## Parent routine commands

Resolve commits on the public API and read file bytes the same way:

```text
python3 -m engine_read \
  --cutoff 2026-11-06T07:50:00+08:00 \
  --output-dir /tmp/engine-read \
  --commits-transport api \
  --contents-transport api
```

`--as-of` is the same instant as `--cutoff`. A value with no timezone is Asia/Shanghai. `--fetched-at` freezes the receipt clock.

Connector file bytes, with commit metadata still resolved on the API:

```text
python3 -m engine_read \
  --cutoff 2026-11-06T19:50:00+08:00 \
  --output-dir /tmp/engine-read \
  --commits-transport api \
  --contents-transport handoff \
  --handoff -
```

Both halves from the connector, no network inside the helper:

```text
python3 -m engine_read \
  --cutoff 2026-11-06T19:50:00+08:00 \
  --output-dir /tmp/engine-read \
  --commits-transport handoff \
  --contents-transport handoff \
  --handoff manifest.json
```

Fixture replay, no credentials and no network:

```text
python3 -m unittest tests.test_engine_read -v
python3 -m engine_read --cutoff 2026-11-06T07:50:00+08:00 \
  --output-dir /tmp/engine-read --fixture /tmp/fixture.json
```

`--fixture` forces `fixture_mode: true` and labels both transports `fixture`. A cached connector replay passed with `"fixture_mode": true` in the handoff is also `fixture_mode: true`. It is not labeled `github_api`.

The routine contents path is a connector file from `get_file_contents` plus `write_to_file`: full raw bytes, not base64 and not a chat clip. The handoff reads that path and sets `transport` to `contents`. Size, sha256, and the git blob sha are computed from those bytes. A filename stem of 64 hex characters must equal the sha256. `declared_sha`, when the parent got it from a pinned tree, is checked and recorded as `blob_sha_source=pinned_tree`. If it is absent, the blob sha is only the computed value and `tree_metadata` is `not_supplied`. This read is `Path.read_bytes()` of the whole file. Streaming is not implemented.

`github_api` is the label only when the optional unauthenticated HTTP transport was actually selected. It is not the routine contents path. Handoff commit metadata is labeled `connector_list_commits`.

## Handoff manifest

The connector result and the commit list are separate objects. File bytes do not prove which commit was current at the cutoff.

```json
{
  "handoff_version": 1,
  "fixture_mode": false,
  "cutoff": "2026-11-06T19:50:00+08:00",
  "fetched_at": "2026-11-06T19:55:00+08:00",
  "commits": {
    "farfromexact/China-Commodities-Engine": {
      "resolved_commit": "<40 hex from list_commits>",
      "commit_time": "<committer date>"
    }
  },
  "files": [
    {
      "repo": "farfromexact/China-Commodities-Engine",
      "path": "data/night_session/latest.json",
      "commit": "<same 40 hex>",
      "asset_path": "<path to the complete tool asset>",
      "declared_size": 1612360,
      "declared_sha": "<git blob sha>",
      "tool": "get_file_contents"
    }
  ]
}
```

`asset_path` must be the complete file. If `declared_size` or `declared_sha` is present and does not match the file, the receipt is `partial_validated` and the JSON is not treated as usable, even when the short bytes happen to parse. A body cut by `--max-bytes` is `truncated` with `parse_result: not_attempted`. The helper does not split JSON by lines and call that complete.

A handoff commit whose committer time is after `--cutoff` is rejected. A file whose commit is not the resolved commit is `read_failed` / `pin_mismatch`. Paths the helper does not select are `not_attempted` with `not_selected_by_metadata`, and their legacy `source_status` stays null.

## What the helper reads

Metadata first, at the one resolved commit for that repo:

| Repo | Always | After metadata |
|---|---|---|
| Commodities | `data/last_run_status.json`, then `data/night_session/last_run_status.json` | `data/report_input_latest.json` if the day status parsed; `data/night_session/latest.json` if the night status has a session field |
| Stock | `data/last_run_status.json`, `data/latest/manifest.json` | allowlisted JSON under `data/latest/` named by `artifacts`. Parquet and research shards are not fetched |
| Options | `data/radar_latest.json` | another allowlisted path only when the radar JSON names that exact path |

Large files use the contents response only when base64 decodes to the declared size and the git blob sha. `encoding: "none"` with an empty `content` and a positive `size` is incomplete. The helper then reads `GET /repos/{repo}/git/blobs/{sha}` and decodes newline-wrapped base64. `--prefer raw` uses `https://raw.githubusercontent.com/{repo}/{commit}/{path}` and still checks the contents sha. None of these URLs use `main`.

There is no 1MB success rule. Declared size, actual size, git blob sha, sha256, and a full JSON parse have to agree. `--max-bytes` is an honest ceiling, not a completeness claim.

## Receipt fields

Each path receipt includes repo, requested ref, resolved commit, commit time, `fetched_at`, cutoff, `timezone`, path, `read_method`, `read_status`, sha, byte count and sha256 when complete, `parse_result`, `source_date`, `trade_date`, `observation_time`, `generated_at`, `published_at`, `known_at`, `research_usable`, `execution_usable`, reasons, and `module_limitations`.

Missing keys stay null. `run_date` is not copied into `trade_date`. `source_trade_date` and `quote_dates` stay on their own fields. On the stock manifest probed below, `quote_dates` is absent. `data_fresh`, `published`, `state=success_backfill`, and `usable_for_current_research` do not make a trade date current. An older trade date becomes `read_status: stale` while `last_good` is only the dedicated last-good field, not a copy of the stale date invented by the helper.

`price_semantics=vendor_latest_trade_asof_snapshot` with `official_night_close_verified=false` is a vendor snapshot. It is not an official night close. `execution_usable` stays false. `not_started` and `not_due` are `temporal_readiness`. A 404 for tonight’s night session before 21:00 Asia/Shanghai stays `read_status: not_found` but `counts_as_missing` is false and legacy `source_status` is left null so it is not reported as missing data. After a real read that does count, legacy `source_status` is `ok`, `missing`, `empty`, `truncated`, `parse_error`, `stale`, or `permission_error`.

Writes are `engine_read_receipts.json` and `engine_read_pins.json`, plus complete evidence files under the output directory. The write is a temp file in that directory replaced into place.

## ChatGPT connector calls

Do this in the task. Do not shell out.

1. Cutoff metadata, one repo at a time. Call `list_commits` with `owner`, `repo`, `sha=main`, `until` set to the cutoff in UTC (use the cutoff plus one second, then drop any committer time after the cutoff), `perPage` 20, and `fields` `["sha","commit"]`. `until` means “before”. The first row is not automatically eligible. Keep the newest row whose `commit.committer.date` is at or before the cutoff. That sha is the only pin for the rest of the run.
2. Do not call `get_commit` for this. Its default `detail` is `stats`, and the REST commit document with the file list was hundreds of kilobytes in the probe below. If a commit object is required, pass `detail=none`.
3. File bytes. Call `get_file_contents` with `owner`, `repo`, `path`, and **`sha` set to the pinned commit**. `sha` overrides `ref`. Do not pass `ref=main` or a floating branch for a file that must match the pin. `fields` is ignored for a single file.
4. If the platform hands the body back as a tool asset, validate that file’s length, git blob sha (`sha1` of `blob <size>` plus a NUL byte plus the file bytes), sha256, and a full JSON parse. A short preview is not the file.
5. One repo’s failure does not skip the other two. Record the failure on that repo and continue.
6. Nest the receipts in the archive JSON. Leave `source_status` in place.

## What this session actually observed

Unauthenticated `GET https://api.github.com/repos/{repo}/commits?sha=main&per_page=20&until=...` from this environment, with no `Authorization` header and no `gh` command. The unauthenticated core limit was 60 requests per hour.

For cutoff **2026-11-06 07:50 Asia/Shanghai** (`until=2026-11-05T23:50:01Z`), the newest eligible commit on `main` was:

| Repo | Commit | Committer time |
|---|---|---|
| China-Commodities-Engine | `8492051f3e415ae5031c3517651e103b79701d04` | 2026-11-05T22:07:36Z |
| China-Stock-Engine | `3fd9a7a6c74613cb2ff61b11014bc2d26939d773` | 2026-11-05T00:28:31Z |
| China-Options-Engine | `25f333659c4c3a4cc53aeddea3c7c19d25f5fff6` | 2026-11-05T23:18:08Z |

For cutoff **2026-11-06 19:50 Asia/Shanghai** (`until=2026-11-06T11:50:01Z`):

| Repo | Commit | Committer time |
|---|---|---|
| China-Commodities-Engine | `2dfb15b11da3854605013ce15349a43c783384f3` | 2026-11-06T11:15:39Z |
| China-Stock-Engine | `a68f3048360d03647813caa64912fec4242ea329` | 2026-11-06T00:35:33Z |
| China-Options-Engine | `25f333659c4c3a4cc53aeddea3c7c19d25f5fff6` | 2026-11-05T23:18:08Z |

The three diagnostic SHAs match this evening cutoff. They are not all the morning pins. Commodities `2dfb15b…` and stock `a68f3048…` are after 07:50 Asia/Shanghai. A later caller must resolve again; these rows are one probe, not a frozen pin.

On that evening commodities commit, `data/night_session/latest.json` contents metadata was `encoding: "none"`, `content` empty, `size` 1612360, blob sha `aa0548cb195c4a2ba8ad3c1b43c64abf2b3c5ce9`. `GET /git/blobs/aa0548cb195c4a2ba8ad3c1b43c64abf2b3c5ce9` returned newline-wrapped base64. Decoded length 1612360, git blob sha matched, sha256 `4193dc29e6f2628413d0ee4a7d1b7c6b11d55fd4b063ec3641ae2690dda25c0d`, JSON object parsed. `price_semantics` was `vendor_latest_trade_asof_snapshot`, `official_night_close_verified` was false, `ohlcv_scope` was `vendor_realtime_unverified_session_scope`, `trading_date` was `2026-11-06`, `generated_at` was `2026-11-06T05:59:29.226162+08:00`. The record list length was 806. No record body was copied into this repo.

The same probe’s small metadata files showed the live shapes the helper understands: commodities `modules[]` with `dataset`, `requested_trade_date`, and `trade_date`; stock status `state=failed_backfill`, `data_fresh=false`, `last_valid_trade_date=2026-10-30`; stock manifest `trade_date` and `source_trade_date` `2026-10-30` with `data_fresh=true` and no top-level `quote_dates`; options `date=2026-11-05`. Those values are from the morning pins above, not from the evening pins.

`get_file_contents` on the connector accepts `sha` as the commit. This session did **not** call that connector tool, so it did not re-see the parent’s tool-asset handoff. The parent reported a pinned `get_file_contents` result of about 2.27MB delivered as a tool asset. The handoff mode is how that file should be checked. It was tested here with local fixture files, including a synthetic 1612360-byte JSON blob with newline base64, not by downloading the night file again inside the tests.

`gh` 2.103.0 is installed on this agent VM and `gh auth status` reports a login. That login is not the parent box, it was not used, and the helper has no `gh` path. `GITHUB_TOKEN` and `GH_TOKEN` were unset.

## Limits still open

- No exchange holiday calendar. A weekday heuristic can mark a post-holiday file stale. The receipt shows `freshness_date_field`.
- Unauthenticated API traffic shares a 60-request hour. The helper does not raise the limit and does not switch to `gh` when it is exhausted.
- ChatGPT tasks still need the connector section. Shipping this module does not put it on that runtime.
- Morning night bytes at `8492051f…` were not re-hashed in this session. The 1612360-byte check is the evening commit `2dfb15b…`.
- Routine archive runs have not used this helper yet.
