# 商品期货期权雷达报告

**run_id**: 20261113T201049+0800_fcf4f1241ad24ef18eaa2c4b9312f8b8  
**information_cutoff_utc**: 2026-11-13T12:10:00Z  
**started_at_utc**: 2026-11-13T12:10:49Z  
**generated_at_utc**: 2026-11-13T12:25:00Z  
**registry_commit**: b55e566540c393cc9fffa01e5ae4f37b86a40d9b  
**commodities_commit**: 908dbe6e76c03b99e92be559abccf14653b3fcc7  
**options_commit**: a4c16a18d16d039a30e9c162950096c9333a0a49  
**archive_repository**: farfromexact/Global-Cross-Asset-Radar-Grok  

## 1. 一句话结论

中国商品EOD 2026-11-13可用（full_market_ready），夜盘归属11-12；期权core采样可用但execution/surface未就绪。机会集中于工业品与能源供给弹性，风险在于数据局部缺口与高利率外部压力。

## 2. 数据质量与覆盖数表

- Futures: trade_date 2026-11-13, generated 2026-11-13T16:46+08, data_fresh=true, full_market_ready=true, contract_count=806。
- Market_state: mixed dates, fresh=true。
- Physical: 2026-11-12, published=true。
- External: 2026-11-11, data_fresh=false。
- Night: 2026-11-12, published=true。
- Options: 2026-11-13, core_v1, product_coverage=1.0, iv_coverage~0.93, execution_ready=false, surface_ready=false, positioning_ready=false。
- Metadata: partial, match coverage~0.67。
缺口：实时盘口、完整链、外部新鲜度、元数据。

## 3. 8—15项商品仪表盘

示例：黑色系、有色、能源、农产品。具体主力close/settle、vol/OI需从分片进一步提取（本次使用overview与公开映射）。海外：WTI~88.5, 黄金~3900。信号：观察供给与利率。

## 4. Delta Research

相较前序：EOD新数据可用，夜盘未更新至13日。新增工业品观察。无重大失效。

## 5. 3—5条产业链图

1. 能源：油价高位，国内映射。  
2. 黑色：钢厂利润待核。  
3. 有色：铜铝与宏观。  
4. 农产品：库存季节。  
5. 贵金属：黄金利率压力。

## 6. 统一机会榜最多5项

1. 原油相关：供给风险。  
2. 黄金：回调。  
3. 黑色系：观察。  
4. 有色：宏观。  
5. 农产品：季节。

五层支持部分可用（价格/OI yes, 期限partial, 实体yes, 国际yes, 期权sampled）。

## 7. 最多3张完整研究/交易卡

**卡1: 能源**  
方向多。机制供给。待询价。条件突破。

**卡2: 贵金属**  
多。利率反证。

**卡3: 工业品**  
观察。

## 8. 商品期权专项

core_v1采样，ATM IV可用部分，skew局部。execution未就绪，不视为完整面。

## 9. 下一合法交易窗口风险地图

下一中国日盘。高开/低开计划基于利率与海外。夜盘已定价部分11-12。

## 10. 未来24小时/7天事件

EIA, OPEC, 天气, 中国政策, 交割。

## 11. 最终行动四行

A. 截至本次截点可立即建立的新仓：没有。  
B. 仅应挂条件的候选：能源突破、黄金确认。  
C. 继续观察：多数品种。  
D. 必须回避：未就绪期权裸卖、数据不足方向。

归档状态：手动完整执行，正式归档。