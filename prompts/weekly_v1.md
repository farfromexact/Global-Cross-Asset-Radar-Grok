# 全球跨资产高风险机会雷达｜周报版（weekly_v1）

**版本**: weekly_v1 · **时区**: Asia/Shanghai · **节奏**: 周日约 20:00（跳过周末晨报/晚报）  
**仓库**: `farfromexact/Global-Cross-Asset-Radar-Grok` · **只研究、不下单、不给仓位规模**  
**微信**: 仅当正文明确写出「机会」且 abnormality≥70 + 跨资产确认 + 清晰失效条件时才 escalate；否则 `wechat_escalate=false`。

## 覆盖窗口
- ISO 周 `YYYY-Www`：周一至周日（含当日周报截点）。
- 输入：本周已归档的晨报/晚报 `reports/YYYY/MM/YYYY-MM-DD_{morning|evening}.{md,json}`；`latest/` 仅作对照。
- 若周内缺失交易日档案（例：雷达中途启动），必须写 `coverage_note`，禁止用外部周报冒充本雷达日度结论。
- Mission Control / 其他 bot 的 `weekly-*` 文件仅可作 **OTHER_BOT_CLAIM** 日历/事件交叉核对，**不得**作为价格主证据，也不得覆盖。

## 必写五段（中文正文）
1. **本周复盘**  
   - 列出本周 Top5（及退休/暂停 id）每个候选的触发门槛与结果：`triggered` / `invalidated` / `still_waiting`。  
   - 价格证据优先来自本周日报；周末可补可核验的公开收盘，标注来源+时间戳。  
   - 给出简单命中率：在「本周可检验触发」的想法中，触发 / 失效 / 仍等待各多少；样本量不足要诚实说明。
2. **跨资产周度格局**  
   - 美股、A股/港股、利率、USD/CNH、黄金、原油、工业金属：周涨跌%、关键位、资金/风格线索。  
   - 每条市场数据必须有来源+as-of；缺数标 `PARTIAL_COVERAGE`，禁止编造。
3. **框架体检**  
   - 永久归档（不复活）的 idea_id；强化主题；需调整的门槛；证据层不足处。
4. **下周日历**  
   - 央行、关键数据、财报、期货交割/换月（下一自然周）；标注受影响候选。  
   - 外部日历主张须 Web 核验；未核验标未核实。
5. **下周作战清单**（与日报同构，供周一晨报直接接力）  
   - **A** 今天/下周开盘前不应立即建立的新仓（默认无）  
   - **B** 条件触发才可讨论的探针（门槛原文）  
   - **C** 继续观察  
   - **D** 明确回避 / 不复活

## 硬规则
- 事实 / 主张 / 推断三者分开写。  
- `worth_taking_risk` 默认 `false`，除非门槛清晰且证据充分。  
- 不写订单、不写手数/金额、不声称已调仓；持仓未核实则写「未核实」。  
- 不把盘前/二级行情写成已确认现金收盘。

## 归档路径（写满后由推送流程上 main）
- `reports/{YYYY}/{MM}/{YYYY-Www}_weekly.md`
- `reports/{YYYY}/{MM}/{YYYY-Www}_weekly.json`
- `latest/weekly.md` / `latest/weekly.json`
- `status/weekly_latest.json`
- `manifests/reports.json`（**UPSERT** `report_week`+`edition=weekly` 或 `report_date`+`edition=weekly`；不得丢弃既有 morning/evening）
- 首次安装本提示词：`prompts/weekly_v1.md`

## 对话交付
- 聊天只发 ≤600 汉字摘要 + 仓库文件路径链接。  
- 摘要含：命中率、主线主题、下周 A/B/C/D 要点、是否微信 escalate。  
- 完整周报以仓库文件为准。

## JSON 精神字段（schema_version 1.0, edition=weekly）
`report_week, week_start, week_end, generated_at_bjt, regime, worth_taking_risk, wechat_escalate, hit_rate, candidates_outcomes[], cross_asset_weekly[], framework_review, next_week_calendar[], action_list, sources[], archive, coverage_note`
