# 当前 Grok 按需报告与验收

Grok当前人工入口为 [Registry按需双报告](https://github.com/farfromexact/AI-prompt-repository/blob/main/compiled/grok_on_demand/radar_run.md)，一次生成全球跨资产与商品期货期权两份完整报告。按 [研究验收与发布合同](https://github.com/farfromexact/AI-prompt-repository/blob/main/docs/GROK_RESEARCH_ACCEPTANCE.md)执行，正式发布由grok_publish.py完成；下方晨晚政策作为旧入口兼容说明。

**2026-11-13按需批次已撤回验收。** 19:42、20:10及并发新增的20:20三批原文保留，分别需要研究复核与补全；它们已移出成功索引，不能作为当前合格前序。暂时没有已验证的按需latest，不自动恢复早一版。见[撤回台账](manifests/withdrawn_runs.json)、[当前状态](status/on_demand_latest.json)。新的合格批次发布后由程序重新建立latest。

发布先校验研究包，再写partial并实际回读，最后提交成功索引和一致latest。新增档案校验CI仅做事后复核，不触发研究/采集，不改变原有自动化。原始十二份报告、晨晚/周报latest和旧索引保留。校验配置固定Registry Commit，见config/grok-publication.json。

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

