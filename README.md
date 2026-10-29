# Global-Cross-Asset-Radar-Grok

Grok Bot archive for the weekday morning and evening **全球跨资产机会雷达** (Global Cross-Asset Opportunity Radar).

这是 Grok Bot 的晨间 / 晚间「全球跨资产机会雷达」归档仓库。本仓库只保存研究归档，不执行下单，也不在脚手架里预写任何行情、价格或交易结论。

## Schedule / 时刻

| Edition | Clock | Timezone | Days |
|---|---|---|---|
| morning 晨间 | 07:50 | Asia/Shanghai | weekdays |
| evening 晚间 | 19:50 | Asia/Shanghai | weekdays |

## Six-file archive protocol / 六文件归档

Each run writes these six paths on `main`, then re-reads them before claiming success:

1. `reports/YYYY/MM/YYYY-MM-DD_{edition}.md`
2. `reports/YYYY/MM/YYYY-MM-DD_{edition}.json`
3. `latest/{edition}.md`
4. `latest/{edition}.json`
5. `status/{edition}_latest.json`
6. `manifests/reports.json`

`{edition}` is `morning` or `evening`. `latest/` currently holds only a placeholder. `manifests/reports.json` is an empty index. Status files are stubs with `archive_status` set to `empty`.

## Layout / 目录

- `prompts/` — evening is Cong's `radar_2026-10-12_stock_v1`. Morning is a stub until he uploads that edition. See `prompts/PROMPT_SOURCE.md`.
- `reports/YYYY/MM/` — historical reports. Placeholder for `2026/10` only. No market reports are included.
- `latest/` — latest successful morning/evening pair, once a real run exists.
- `status/` — per-edition archive status.
- `manifests/` — report index.
- `config/` — archive policy (repo name retargeted to this repository).
- `docs/` — schedule/archive instructions and `docs/GROK_BOT_RUNBOOK.md`.
- `schemas/` — report and manifest JSON Schema.
- `templates/` — empty report templates, not published reports.

## Privacy / 可见性

This repository was intended to be **private**. It is currently **public** on GitHub. Do not put secrets, account data, or credentials here.

## Source / 来源

Schemas, templates, and archive instructions were copied from the public sibling `farfromexact/Global-Cross-Asset-Radar` and retargeted to `farfromexact/Global-Cross-Asset-Radar-Grok`. The evening prompt is Cong's 2026-10-29 upload. Historical `reports/` from the sibling were not copied. Market content belongs only in files a real run writes later.
