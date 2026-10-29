# Grok Bot runbook

Grok Bot (gemini monitor) runs on weekdays only:

- morning, about **07:50** Asia/Shanghai
- evening, about **19:50** Asia/Shanghai

`config/archive-policy.json` uses those two clocks for `morning` and `evening`. Commodity edition blocks in that file were copied from the sibling radar so the schema stays compatible. This bot does not run them.

## What a run does

1. Research from the prompt in `prompts/` for that edition, plus `docs/SCHEDULE_ARCHIVE_INSTRUCTIONS.md` and the schema/template/policy files.
2. Write the six archive files **directly to this repo's `main`** (no staging branch, no pull request for a formal archive):
   - `reports/YYYY/MM/YYYY-MM-DD_{edition}.md`
   - `reports/YYYY/MM/YYYY-MM-DD_{edition}.json`
   - `latest/{edition}.md`
   - `latest/{edition}.json`
   - `status/{edition}_latest.json`
   - `manifests/reports.json`
3. Re-read those six paths from `main` before setting `archive_status` to `success`.
4. In chat, send only a summary of **at most 600 Chinese characters**, with the commit link and links to the six files.

## Hard limits

- No orders. Research and decision support only. Do not place, route, or simulate a fill as if it were an account instruction.
- Do not invent prices, quotes, fills, or data dates. If a figure is missing, say so.
- Do not copy historical reports from `farfromexact/Global-Cross-Asset-Radar` into this repo to fill `reports/` or `latest/`.
- Morning and evening both use Cong's `radar_2026-10-12_stock_v1` prompts (`commodity_consumer=core_2026-10-17_v1`) and write this repo's `main`. See `prompts/PROMPT_SOURCE.md`.
- This repository was intended to be private. It may still be public. Do not write secrets.
