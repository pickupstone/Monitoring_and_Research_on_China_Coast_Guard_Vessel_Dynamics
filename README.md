# Monitoring and Research on China Coast Guard Vessel Dynamics
# 中國海警船 AIS 勤務分析

以 Global Fishing Watch（GFW）公開 AIS 資料，整理中國海警船與科研／調查船 2021-11 至 2026-11 的母港、出勤時段、重點海域（釣魚台、台灣東部、海峽中線、金門、台灣西南、東沙、南沙、黃岩島）、編隊、MMSI 切換與近期異常。

- 網頁：`index.html`（GitHub Pages）
- 資料表：`data/海警船AIS勤務分析.xlsx`
- 每日比對程式：`job/daily.py`（以 `job/baseline.json` 的各船歷史常態比對最新 AIS 事件）
- 照片：`img/`，來自 Wikimedia Commons，作者與授權標示於各船頁面

## 資料來源
- AIS 身分與事件：Global Fishing Watch API v3（港口停靠、海上滯留、AIS 中斷），約 72 小時延遲。GFW 資料僅限非商業用途，引用請註明：Global Fishing Watch, www.globalfishingwatch.org
- 舷號、艦名、單位：維基百科「中國海警艦艇」、Wikipedia "List of ships of the China Coast Guard"
- 最後回報（部分有 IMO 的船）：VesselFinder 公開船舶頁
- 編隊與事件：台灣海巡署、日本海上保安廳與防衛省、菲律賓海警、CSIS/AMTI、SeaLight 等公開報告（整理自搜尋摘要，引用前請核對原文）

## 限制
只看得到有開 AIS 的航段；位置來自事件而非逐點航跡；「共同滯留」不等於確認的編隊；每日告警與每日新聞只在 claude.ai 的報告版本即時更新。
