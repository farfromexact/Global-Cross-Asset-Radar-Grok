# Grok 按需双报告归档

当前人工入口见[Registry START_HERE](https://github.com/farfromexact/AI-prompt-repository/blob/main/START_HERE.md#grok)。Grok完成全球、商品两份完整正文，一次提交到`inbox/grok/<唯一英文或数字文件名>.md`，以`<!-- radar:global -->`和`<!-- radar:commodities -->`按顺序分隔。模型只做研究与交付，JSON、哈希、工程校验、回读、时间批次和索引由后台工具完成。

`Archive Grok Inbox`只处理人工收件或手动重试，不定时生成研究，不采集，不下单。归档结果见`receipts/grok/<同名文件>.json`；仅`archived`表示完整批次已写入。工具保存原文，不虚构数据版本、研究截点或研究复核。

新报告仍在`reports/YYYY/MM/DD/{run_id}/`；`manifests/runs.json`与`latest/run.json`在实际收到新报告时转为v2，旧记录和旧报告原样保留。撤回台账继续有效，旧结构化报告继续按原证据/Schema校验，新文本批次按字节、正文一致性、回执及索引校验。工程存档成功不认证投资判断。

维护者可手动运行收件工作流的`check`模式：只在临时本地Git仓库测试合成正文，再只读审计已有档案，不把测试报告写入本仓。`publish`模式只重试已有人工提交。校验包固定Registry提交及文件哈希，见`config/grok-publication.json`。

下方为历史晨晚流程说明，保留原自动化及报告入口；它不是当前按需启动步骤。

---


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

- `prompts/` — morning and evening are Cong's `radar_2026-10-12_stock_v1`, split from one upload. See `prompts/PROMPT_SOURCE.md`.
- `reports/YYYY/MM/` — historical reports. Placeholder for `2026/10` only. No market reports are included.
- `latest/` — latest successful morning/evening pair, once a real run exists.
- `status/` — per-edition archive status.
- `manifests/` — report index.
- `config/` — archive policy (repo name retargeted to this repository).
- `docs/` — schedule/archive instructions and `docs/GROK_BOT_RUNBOOK.md`.
- `schemas/` — report and manifest JSON Schema.
- `templates/` — empty report templates, not published reports.

## Weekly reviews (Mission Control)

`reports/2026/11/` — Mission Control 周复盘 markdown (week 6, 2026-11-01). Outside the morning/evening six-file protocol; not indexed in `manifests/reports.json`.

## Privacy / 可见性

This repository was intended to be **private**. It is currently **public** on GitHub. Do not put secrets, account data, or credentials here.

## Source / 来源

Schemas, templates, and archive instructions were copied from the public sibling `farfromexact/Global-Cross-Asset-Radar` and retargeted to `farfromexact/Global-Cross-Asset-Radar-Grok`. Both prompts are Cong's 2026-10-29 upload of `radar_2026-10-12_stock_v1`. Historical `reports/` from the sibling were not copied. Market content belongs only in files a real run writes later.

