# 全球跨资产机会雷达·晨间版 2026-11-12（周四）

- prompt_version=radar_2026-10-12_stock_v1；commodity_consumer=core_2026-10-17_v1；edition=morning
- 实际研究截点：2026-11-12 07:55 BJT（= 2026-11-11T23:55Z）；报告日期 2026-11-12；持仓未核实；不下单。
- 结论：worth_taking_risk=false，wechat_escalate=false。

## 一句话结论
美国周三现金盘收涨（SPX +1.31% 7619.38、Nasdaq +1.60%、NDX +2.28%、VIX 17.58），AI/半导体全面反弹（MU +11.9%、AMD +7.3%、CoreWeave +24.7%），但MSFT −2.26% 与 GOOGL +2.11% 分化——周一MSFT占优、周二MSFT落后、周三再次MSFT落后，配对信号反复，不成立；收盘后NYT/WSJ报道英伟达董事会拟罢免黄仁勋，NVDA盘后约−8%、NDX期货约−0.8%至−1%，11/17财报前事件风险极高；中国商品供应商（Wind）周三收盘显示MA/CU门槛仍灭、CU仍backwardation；中国周四09:00/09:30尚未开盘，今早无新仓。

## 一、截点、日历与可比性
- 07:55 BJT 时：美国周三（11-11）现金盘已收（退伍军人节，股市开市、债市休市，故无新的美债收益率官方收盘）；欧洲周三已收（DAX约+1.2%、FTSE约+0.8%、Stoxx600约+0.7%，来源为二手行情摘要）；日韩周四08:00尚未开；中国周四09:00商品/09:30股指尚未开盘；中国周三夜盘（11-11 21:00→11-12 02:30）引擎在pin时刻无该数据，不能用周二夜盘代替。
- 今夜重要事件：美国初请/成屋销售（周四20:30/22:00 BJT）；11/17 NVDA财报；美联储12月加息预期约90%（周二CPI +0.4%、核心+0.3%，来源为二手引用，官方BLS数据在上期已读）。

## 二、美国与全球 EOD（来源：AP/Investing/Sharecast/Yahoo等二手汇总，价格以收盘为准；官方交易所页面未直接取到，标secondary）
- SPX 7619.38 (+1.31%)；Dow 52486.49 (+0.49%)；Nasdaq 25466.19 (+1.60%)；NDX 约28374 (+2.28%)；Russell 2000 2846.26 (+0.88%)；VIX 17.58（−9.66%）。
- Mag7：NVDA 173.73 (+2.87%)、TSLA +2.91%、GOOGL 293.45 (+2.11%)、AAPL 355.63 (+2.04%)、AMZN 266.17 (−1.74%)、META 628.77 (−1.97%)、MSFT 521.13 (−2.26%)。
- 半导体/AI硬件：MU 811.30 (+11.89%)、AMD 552.90 (+7.32%)、AVGO +3.99%、AMAT +6.05%、LRCX +6.07%、ORCL +8.8%；CRWV +24.7%（Q3营收36.6亿美元，全年指引上调至130–133亿美元）。
- 盘后：NVDA约−4.5%至−8.4%（不同来源不同时点，写区间）；SMCI、ORCL、CRWV、INTC同步走弱，AMD +3.8%。
- 日本Nikkei周三收 61248.59（+1.31%）、Taiex +3.62%、Kospi +2.60%、HSI 24315.92（−0.98%）、上证3680.64（+0.46%）。
- 大宗/外汇（周四早盘二手快照，非结算）：Brent约92.6–93.0、WTI约86.9、黄金约3989–4063（不同来源差异大，标冲突）、DXY约102.48、USDJPY约158.97、EURUSD 1.1138。美国10年期约5.00%（二手，债市周三休市）。

## 三、前序报告与想法台账
上期晨报（2026-11-11 morning，commit 1becf5b0…）与晚报（ca906bc0…，status tip b8af56c7…）已读：Top5 AI40/EC40/CU29/MA25/BU14，均为observe/avoid，worth_taking_risk=false。本期变更只因新事实：AI因周三MSFT/GOOGL相对表现再度反向与NVDA盘后事件重估；商品因周三Wind收盘更新。

## 四、三个引擎（pin与读取，详见JSON的engine_read_receipts）
- China-Commodities-Engine pin 7f596fae…（2026-11-11T15:34:19Z，Cong提交“add local Wind daily collection”）；data/last_run_status.json 与 night_session/last_run_status.json、report_input_latest.json 读取成功并解析：run_date=2026-11-11，generated_at 22:07:47+08:00，provider=wind，五所futures源日期=2026-11-11，source_date_match 100%，data_fresh=true，但official_complete=false、core_futures_official_complete=false（Wind供应商口径，不是交易所官方结算文件）；contract_meta/warehouse/basis/member_rankings 均 skipped（unavailable）；options=core_available（466合约，execution_ready=false，bid_ask_coverage=0）。夜盘status：night_session_date=2026-11-10（周二夜盘），coverage 63.77%，official_night_close_verified=false；周三夜盘不在此pin内（不是缺失，是尚未被引擎采集）。night_session/latest.json 仅取得显示截断版本，未做完整字节验证（标 read_success_partial_display_truncated）。
- China-Stock-Engine pin 8b496efb…（2026-11-11T16:06:35Z，PR #11合并）；data/last_run_status.json 状态 success_wind_publication，last_valid_trade_date=2026-11-11；data/latest/manifest.json 读取成功：5580只，行情/参考覆盖100%，opportunity_radar_latest 36行；opportunity_radar等大文件本轮未下钻（不影响六文件归档，标 not_deep_read，非读取失败）。
- China-Options-Engine pin a4c16a18…（2026-11-11T23:16:58Z）；data/radar_latest.json 读取成功：date=2026-11-11，CFFEX官方EOD CSV 760条，匹配100%，无错误。head_changed_after_pin=false（仅在pin解析时点核验）。

## 五、中国商品（周三 Wind 供应商收盘，非官方结算；MA/CU 门槛按官方口径需官方文件确认）
- MA2701 收3159/结3114，PX2701 收8410/结8324——距离MA门槛（官方收盘与结算≥3485且PX≥9850）仍远，门槛为假。
- CU2612 收105820/结105230；CU2611结107370，近远backwardation约−2.0%；CU门槛（≥109600且contango≥0.65%）为假。
- EC2612 收2485.5/结2469.0（EC观察，不具执行条件，期权未execution_ready）；BU2701 收4282/结4226，BU2612 4495/4442，曲线仍陡；SC2612 604.0/598.1；AU2612 873.3/870.5；TA2701 6016/5952。
- 由于周三官方期货文件缺失（iFinD配额问题此前持续，本轮Wind供应商替代），门槛判断仅为供应商口径，保持保守为假。

## 六、中国股指与期权（官方CFFEX周三EOD）
- 现货：上证50 2765.54（−0.27%）、沪深300 4075.71（+0.41%）、中证500 6713.18（+1.01%）、中证1000 6669.55（+1.37%）。
- 期货主力：IH2612 2742.2（−0.45%，OI 63192）、IF2612 4043.4（+0.35%）、IC2612 6664.0（+1.04%，OI +4705）、IM2612 6623.0（+1.37%，OI +9945）。风格：小盘强于大盘。
- 期权：HO ATM IV约14.7%、IF约17.8%、MO2611 ATM约29.2%、MO2612约27.9%（RR25约−2.4%、PCR_OI 0.65）；本引擎质量边界内，非execution_ready，不裸卖波动。

## 七、AI 专题
周三AI硬件强反弹，但软件/超大规模云（MSFT、META、AMZN）下跌，GOOGL上涨——“现金流龙头多/Capex Beta空”的MSFT/GOOGL配对三日分别为+2.75/+1.18、−2.20/−0.27、−2.26/+2.11，方向不稳，不是干净信号。NVDA盘后事件使11/17财报前不确定性飙升，Asian open（台韩日）先交易此事；无可核验结构化合约/权重，不称Beta-neutral，仅观察/条件挂单研究。

## 八、Top5（均observe；无任何项通过执行条件）
1. AI-CASHFLOW-VS-CAPEX-BETA-20261028（MSFT/GOOGL）41 — observe，条件：NVDA事件落地后配对重新同向+隔夜成交确认。
2. COM-T-EC2612-TREND-CONTANGO-SHORT-20261028（EC2612）39 — observe。
3. COM-M-CU2612-HVC-STRIKE-WATCH-20261025（CU2612）28 — observe。
4. COM-C-MA2701-AND-PX-RECLAIM-20261024（MA2701）25 — observe。
5. COM-C-BU2701-PULLBACK-LONG-20261022（BU2701）14 — avoid。

## 九、未来24小时/7天风险（BJT）
- 今日09:00商品/09:30股指日盘开盘：映射周三美股AI反弹与NVDA盘后下挫；开盘后15/30/45分钟看IM/IC相对IH强度是否延续、CU/MA是否触及门槛。
- 今晚：美国初请20:30、成屋销售22:00、商品夜盘21:00（未到，不是缺失）；11/17 NVDA财报；12月FOMC加息预期约90%。

## 十、最后严格四行
A. 今天没有应立即建立的新仓位。
B. 今天仅应挂条件的候选：MA完整AND（官方收盘与结算≥3485且PX≥9850）；CU完整AND（≥109600且contango≥0.65%）；EC需可辩护的持续contango结构；MSFT/GOOGL需NVDA事件落地后重新同向。
C. 今天继续观察：中国09:00/09:30开盘对美股AI反弹及NVDA盘后消息的映射、台韩日开盘对NVDA供应链的反应、周三夜盘官方收盘、IM/IC强于IH的持续性、油价约92–93与黄金的二手价差冲突。
D. 今天必须回避或若此前已建仓则有条件退出：逆门槛抄铜甲醇；把Wind供应商收盘当官方结算；把周二夜盘当周三夜盘；BU回撤多；裸卖波动；在NVDA事件落地前建立半导体方向性重仓；复活IH/IM旧空；商品/股指期权未execution_ready。

## 附：局限
美国/亚洲行情为二手汇总（AP、Investing.com、Sharecast、Yahoo、ABC、Reuters转引），官方交易所/Treasury/BLS页面本轮未逐个直取；黄金多源价格冲突；中国周三夜盘缺失于pin；商品官方期货文件未取得；本期正文约1,300汉字，深度低于完整万字版，缺口已披露，非省略研究结论。
