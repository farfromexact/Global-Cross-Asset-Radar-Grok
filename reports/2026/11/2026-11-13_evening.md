# 全球跨资产高风险机会雷达｜晚间版

- 报告日期：2026-11-13（周五）｜edition=evening｜prompt_version=unified_2026-11-12_v2｜archive_edition=evening
- 实际研究截点：2026-11-13T17:13:00+08:00（=2026-11-13T09:13:00Z）；公开资料检索约17:15–17:20 BJT；归档生成约17:30 BJT。
- 持仓未核实；不下单；不发微信。worth_taking_risk=false。
- 仓库：farfromexact/Global-Cross-Asset-Radar-Grok。Prompt SHA-256：363290ca884b5a397cbf2c3c2e7000d72fcf448a53ef941f017875387d77fc51（Manifest声明值与独立计算一致）。
- China-Commodities-Engine Commit：fc490f67d45bcd0fd969b16a808ce88155c33739（2026-11-13T08:51:51Z）。
- China-Options-Engine Commit：a4c16a18d16d039a30e9c162950096c9333a0a49（2026-11-11T23:16:58Z）。

## 1. 一句话结论

中国周五A股已完成（公开源Xinhua：上证3634.35−0.59%、创业板2426.08−3.32%），成长/小盘继续承压。商品引擎已更新至2026-11-13供应商数据（official_complete=false）：MA等有正收益但证据层有限，MA/CU完整AND门槛仍未证实达标。美股周四现金盘收低（SPX约7592−0.4%），NVDA CEO辞职报道引发波动，周五现金盘未开。21:00夜盘尚未开始。今晚不建仓。

## 2. 全市场仪表盘

截点17:13时：中国周五日盘已完成；香港已收；日韩已收；欧洲大致已收；美国周五现金盘22:30 BJT尚未开盘；中国周五21:00夜盘尚未开始（不是缺失）。

### 2.1 美国利率、美元、美股

- 美国周四现金盘（公开源）：SPX约7592.40（−0.4%）、Nasdaq约25366（−0.4%）、Dow约52297（−0.4%）。NVDA因CEO辞职报道大幅波动后收低。周五盘前期货小幅偏低。
- 10年国债收益率公开源约5.10–5.13%。
- 外汇、黄金、原油公开源有延迟，不作精确执行价。

### 2.2 中国股票

公开源周五收盘（Xinhua 2026-11-13 16:11）：上证3634.35（−0.59%）、深证10968.79（−2.05%）、创业板2426.08（−3.32%）、科创相关承压。成长风格继续弱于主板。

### 2.3 中国商品

**引擎（供应商，trade_date=2026-11-13，generated_at 16:46+08，official_complete=false，options_surface not_ready，execution_ready=false）：**

热力图显示FG、MA等有正close_return（MA约+3.26%），但evidence_count多为1（curve），basis/warehouse/options缺失。完整AND门槛（MA收/结≥3485且PX≥9850；CU≥109600且contango）从公开与引擎摘要看仍未满足。

期权引擎仍为2026-11-11 CFFEX官方，execution_ready=false。

## 3. Top 5

1. AI-CASHFLOW-VS-CAPEX-BETA-20261028 38 — observe。美股未开，NVDA事件增加不确定性。
2. COM-C-MA2701-AND-PX-RECLAIM-20261024 26 — observe。引擎有正收益但门槛未证实，official_complete=false。
3. COM-M-CU2612-HVC-STRIKE-WATCH-20261025 25 — observe。曲线与门槛仍不足。
4. COM-T-EC2612-TREND-CONTANGO-SHORT-20261028 35 — observe。需持续结构辩护。
5. COM-C-BU2701-PULLBACK-LONG-20261022 12 — avoid。

## 4. 引擎读取回执

- Commodities：fc490f67... radar_latest trade_date=2026-11-13，official_complete=false，full_market_ready=true，options_full_chain_verified=false。
- Options：a4c16a18... date=2026-11-11，official 760/760，execution_ready=false。
- 未访问China-Stock-Engine。

## 5–9. 研究要点与局限

前序晚报（2026-11-12）worth_taking_risk=false，门槛未达。本轮新事实：周五中国成长继续下跌，商品引擎刷新至当日但官方未完成，美股NVDA事件。数据不足处标明，不虚构。

局限：商品官方结算文件缺失；期权曲面未就绪；夜盘未开始；部分公开源有延迟或冲突。

## 10. 最后严格四行

A. 今天没有应立即建立的新仓位（中国周五A股成长继续下跌；商品引擎official_complete=false且AND门槛未证实达标；美股未开且NVDA事件；21:00夜盘未开始；期权未execution_ready）。
B. 今天仅应挂条件的候选：MA完整AND官方达标且PX同步；CU官方≥109600且contango达标；AI配对需美股开盘后新证据。
C. 今天继续观察：美国22:30现金盘对NVDA事件与亚洲风险的映射、今夜21:00商品夜盘、官方商品结算是否补上。
D. 今天必须回避或若此前已建仓则有条件退出：逆门槛抄底；把供应商数据当官方结算；裸卖波动；在事件证据落地前重仓半导体方向。