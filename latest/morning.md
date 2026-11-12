# 全球跨资产机会雷达·晨间版 2026-11-13（周五）

- prompt_version=radar_2026-10-12_stock_v1；commodity_consumer=core_2026-10-17_v1；edition=morning
- 实际研究截点：2026-11-13 07:55 BJT（= 2026-11-12T23:55:00Z）；报告日期 2026-11-13；公开行情检索 07:52–07:53 BJT；持仓未核实；不下单；不发微信。
- 结论：worth_taking_risk=false，wechat_escalate=false。

## 一句话结论
美国周四现金盘收跌（SPX 7592.40 −0.35%、Nasdaq 25366.09 −0.39%、Dow 52297.09 −0.36%）：NVDA 因黄仁勋辞任CEO（CFO Kress任临时CEO）盘中一度跌逾13%、收166.19（−4.34%，52周新低），AMD +5.86%、AVGO +5.54%、MU −1.59%，MSFT +0.36% 再落后 GOOGL +1.79%（周二至周四连续三日落后，配对不成立）；10年美债约5.11–5.13%、Brent收95.82（+3.3%）、美联储12月加息预期近100%——风险偏好受压而非单边崩盘。中国商品引擎已补入周四Wind供应商日盘（official_complete=false）：MA2701结3163、CU2612结105140，MA/CU完整AND仍为假，铜继续backwardation；今早09:00/09:30尚未开盘，今早无新仓。

## 一、截点、日历与可比性
- 07:55 BJT 时：美国周四现金盘已收；日韩周五08:00/09:00 尚未开；中国周五09:00 商品/09:30 股指未开盘；周五21:30 BJT 美国PPI、21:00 商品夜盘均未到（not_started，不是缺失）。
- 引擎口径：商品 Wind 供应商日盘 trade_date=2026-11-12（周四，generated 21:33:42 BJT，official_complete=false，官方交易所对账 unavailable，DCE 官方页 412）；周四夜盘在引擎针内**不存在**（针内夜盘文件为 night_session_date=2026-11-11 的周三夜盘，official_night_close_verified=false）；股票引擎有效交易日 2026-11-11（周三）；期权引擎 date=2026-11-11 官方 CFFEX EOD。周四中国现金盘仅用上期晚报已记的公开源（上证3655.83 −0.67%、创业板2509.43 −2.44%、科创50 1309.84 +0.73%，恒生24008.55 −1.26%），不当引擎数据。

## 二、美国与全球（secondary：AP/CNBC/Investing/Reuters 转引 + 新浪 gb_*，官方交易所页未直取）
- 美股周四收盘：SPX 7592.40（−0.35%）、Dow 52297.09（−0.36%）、Nasdaq 25366.09（−0.39%）、NDX 约28289（−0.30%）。VIX 公开源本轮为空，缺失不补。纽交所跌/涨家数 2225/644。能源板块 +1.5% 最强。
- NVDA 事件：公司公告 Huang 辞任总裁/CEO/董事，CFO Colette Kress 临时CEO，Harvey Jones 任首位董事长；11/17 财报按期；11/18 全员会。NVDA 收166.19（−4.34%，成交量约7.4亿股，日内低148.80）；SMCI −11.3%、Nebius −16.8%、CoreWeave −6.9%。受益者：AMD 585.30（+5.86%）、AVGO 364.36（+5.54%）、ANET +5.06%；SMH −1.03%、MU 798.44（−1.59%）。
- Mag7：MSFT 523.00（+0.36%）、GOOGL 298.70（+1.79%）、AAPL 354.88（−0.14%）、AMZN 267.44（+0.48%）、META 623.61（−0.82%）、TSLA 397.45（+1.69%）。周一 MSFT 占优、周二/三/四均落后：配对触发条件不成立。
- 利率/大宗/外汇：10年美债约5.05–5.13%（盘中高于5%，创10/22以来高点）、2年约4.84–4.88%；Brent 95.82（+3.3%）、WTI 88.74（+2.6%）——特朗普称“不需要与伊朗达成协议”、沙特能源设施遭袭；美联储12月加息预期近100%、50bp约13%；今早公开源 Brent 约95.98、WTI 88.77、现货金约3880（周四晚报时约3944，连续回落）、USDCNH 6.6729、USDJPY 159.84、EURUSD 1.1049。
- 周五早盘期货（新浪，07:52，非结算）：ES 7639.8（对期货前收7620.25约+0.26%）、NQ 28527（对前收28399.25约+0.45%）、YM 52497（前收52415）；亚洲指数期货混合，日韩略强、港澳偏弱。

## 三、中国商品与股指期货（引擎周四 Wind 供应商日盘，非官方）
引擎针 China-Commodities-Engine 1db709dc（2026-11-12T14:50:28Z），report_input_latest generated 2026-11-12T21:40:33+08:00，requested_date/source_date=2026-11-12，execution snapshot sha256:6128a629…，quotes=1612，rejected=0，usage=dated_reference_only。

| 合约 | 收盘 | 结算 | 备注 |
|---|---:|---:|---|
| MA2701 | 3172 | 3163 | 1D结算 +1.57%；距门槛≥3485 仍差约10.2%；PX2701 收8448/结8384，距≥9850 差约17.5% |
| CU2612 | 104950 | 105140 | 1D −0.09%；距≥109600 差约4.2%；对CU2701结算103690为backwardation约−1.38%，对CU2611结算107740约−2.41% |
| EC2612 | 2477.5 | 2448.5 | 1D −0.83%、3D +5.65%、OI 1D −12.1%（价跌仓降）；EC2611结算2151.5 |
| BU2701 | 4330 | 4286 | 1D +1.42%、3D −3.88%；曲线对BU2612为 backwardation |
| AU2612 | 852.5 | 860.46 | 1D −1.15%（品种当前合约） |

MA完整AND（官方收盘与结算≥3485且PX≥9850）= 假；CU完整AND（≥109600且contango≥0.65%）= 假；Wind 供应商口径不能当官方结算，门槛不得因此改写为真。

公开源周四夜盘（新浪 nf_*，非引擎针内，仅作着色）：MA2701 夜盘最新3216（对周四结算约+1.7%）、PX2701 8518（约+1.6%）、BU2701 4366（约+1.9%）、CU2612 105060（约−0.08%）、AU2612 835.78（约−2.9%），均**未触及**MA/CU门槛。周四夜盘官方收盘本轮未取得。

股指期货：期权引擎官方 CFFEX 周三收盘（IH2612 2742.2 / IF2612 4043.4 / IC2612 6664.0 / IM2612 6623.0）；公开源周四收盘 IH2612 2739.4、IF2612 4002.4、IC2612 6538.4、IM2612 6480.4（对周三约 −0.10% / −1.01% / −1.89% / −2.15%）。期权质量不变：官方匹配760/760，execution_ready=false，bid/ask不足，不裸卖波动。

周四 Wind 品种扫描（77个，结算1D，研究用）：涨幅 CZCE:AP +2.90%、DCE:EG +2.34%、INE:LU +2.08%、SHFE:BR +2.04%、INE:SC +2.02%；跌幅 GFEX:PT −1.46%、DCE:JM −1.38%、DCE:I −1.32%、SHFE:AU −1.15%。

## 四、引擎读取回执（摘要）
- 截点锁定 2026-11-13 07:55 BJT（2026-11-12T23:55:00Z）。各库 list_commits 解析 main 最新 committer≤截点：
- China-Commodities-Engine **1db709dcf61a7f032747c1702673b3f78255ef8e**（2026-11-12T14:50:28Z = 22:50 BJT；“decouple commodity launcher…”）相对昨晚针 8a908946 为新针，含周四 Wind 日盘与周三夜盘（night_session_date=2026-11-11）。last_run_status / night last_run_status / report_input_latest / night_session/latest 均读到并可解析（大文件为 connector raw asset，无包装，已核UTF-8 与 git blob）。数据新鲜度：data_fresh=true，official_complete=false，contract_info/warehouse/basis/member_rankings=skipped(not_yet_mapped)。
- China-Stock-Engine **f469c846c84defd0e2a9dfa01e54bf7265bcb54d**（2026-11-12T14:04:04Z；仅启动器变更）。last_run_status=success_wind_publication、manifest verified，有效交易日 2026-11-11，不是周四。
- China-Options-Engine **a4c16a18d16d039a30e9c162950096c9333a0a49**（2026-11-11T23:16:58Z，与昨晚相同）。last_run_status/radar_latest 可读，date=2026-11-11 官方 CFFEX EOD；今日07:16 更新未在针内。
- 小文件 write_to_file 带来源包装，记 local_serialization_error，不当作 blob 证明，字段取自 inline JSON。报告仓截点尖端 0815fd3bca16e9ef77d15b12ede23fd9f790fb24（昨晚归档）。2026-11-05 晨报仍缺，不编造；周末日报按设计不存在。

## 五、Top 5
1. AI-CASHFLOW-VS-CAPEX-BETA-20261028（MSFT/GOOGL）40（较昨晨 41 −1、较昨晚 0）— observe。MSFT 连续三日落后；NVDA 治理冲击使AI链分化，不是干净配对。
2. COM-T-EC2612-TREND-CONTANGO-SHORT-20261028（EC2612）37（较昨晚 38 −1）— observe。周四结算回吐、OI降12%，近远结构仍陡但无法诚实辩护持续contango。
3. COM-M-CU2612-HVC-STRIKE-WATCH-20261025（CU2612）27（较昨晚 0）— observe。距109600约4.2%，仍backwardation。
4. COM-C-MA2701-AND-PX-RECLAIM-20261024（MA2701）25（0）— observe。周四+1.57%但距3485仍约10%、PX更远。
5. COM-C-BU2701-PULLBACK-LONG-20261022（BU2701）14（0）— avoid。周四反弹不改3D −3.9%与回避。

## 六、未来24小时/7天风险（BJT）
- 今日09:00 商品 / 09:30 股指开盘：映射美股NVDA事件冲击、AMD/AVGO受益、10年美债>5%与油价；看 IM/IC 相对 IH 的弱势是否延续、MA/CU 是否触及门槛。
- 今晚：21:00 商品夜盘（未到）、21:30 美国PPI；周末美伊局势（特朗普“不需要协议”）风险；11/17 NVDA财报、11/18 员工会；12月FOMC加息预期近100%。

## 七、局限
美股/亚洲/利率/油价为二手汇总（CNBC、AP、Investing/Reuters、Asia Business Daily 等），官方交易所/Treasury/BLS 页面未直取；VIX/DXY 公开源为空；周四夜盘不在引擎针内，仅有新浪公开源着色；商品官方结算文件仍缺，Wind 为供应商口径；股票研究分片/parquet 本轮未下钻；期权引擎今日更新未入针。

## 八、最后严格四行
A. 今天没有应立即建立的新仓位（美股周四收跌、NVDA治理冲击后分化；商品周四Wind收盘official_complete=false，MA/CU完整AND仍为假，铜backwardation；中国09:00/09:30未开盘，21:00夜盘与21:30 PPI未到；商品/股指期权未execution_ready）。
B. 今天仅应挂条件的候选：MA完整AND（官方收盘与结算≥3485且PX≥9850；Wind周四MA结3163、PX结8384，夜盘公开源MA约3216，均未达标）；CU完整AND（官方≥109600且contango≥0.65%；周四CU2612结算105140对CU2701约−1.38%为backwardation）；EC需能诚实辩护持续contango结构，默认观察；MSFT/GOOGL需NVDA事件落地、两者重新同向后才可再评。
C. 今天继续观察：中国09:00/09:30对NVDA事件、AMD/AVGO受益与美债收益率>5%的映射、日韩开盘对NVDA供应链反应、IM/IC弱于IH的延续、周四夜盘官方收盘与官方商品结算文件、今晚21:30 PPI与21:00夜盘（未到，非缺失）、周末美伊与油价。
D. 今天必须回避或若此前已建仓则有条件退出：逆门槛抄铜甲醇；把Wind供应商收盘或公开源夜盘当官方结算；把周三夜盘当周四夜盘；BU回撤多；裸卖波动；在NVDA财报(11/17)与CEO继任落地前建立半导体方向性重仓或追AMD/AVGO；复活IH/IM旧空；商品/股指期权未execution_ready。
