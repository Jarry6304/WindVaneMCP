# 風向計 MCP 系統 — 完整規格 v1.2

> **製表日期**:2026-05-05
> **版本**:v1.2(取代 v1.0)
> **架構**:MCP Server(FastMCP)+ Crawlee 統一爬蟲基底 + PostgreSQL 入庫 + 獨立 Email 通知
> **環境**:Windows 11 / PostgreSQL 17 / Python 3.12
> **核心設計**:對照碼與爬取結果皆入 DB,搜尋查詢累積學習,自動規則 + 人工覆寫雙軌

---

## 一、設計核心

### 1.1 五個關鍵原則

| 原則 | 說明 |
|---|---|
| **DB 為唯一真相來源** | 對照碼、爬取結果、查詢學習資料皆入庫 |
| **爬取結果同 URL 覆蓋** | 不保留歷史快照,僅以 `pushes_history` 字串欄位記錄推文增長 |
| **MCP 統一接口** | 所有 toolkit 透過 MCP 暴露給 LLM |
| **搜尋查詢累積學習** | 系統使用越久,優先查詢越穩定 |
| **通知不依賴 LLM** | 獨立 email 排程,不在對話中打斷 |

### 1.2 v1.2 對 v1.0 的關鍵改變

| 項目 | v1.0 | v1.2 |
|---|---|---|
| 爬蟲基底 | httpx + selectolax + 自管 Playwright | Crawlee Python 1.3.x |
| 爬取結果 | 不入庫 | 入庫(同 URL 覆蓋) |
| 推文數歷史 | 無 | `pushes_history` 字串欄位 |
| 搜尋查詢學習 | 無 | `search_queries` 表 + 自動規則 |
| 通知機制 | 無 | 獨立 Email 排程 |
| Toolkit 數量 | 6 | 12(7 爬蟲類 + 5 查詢類) |
| Komica 支援 | 無 | 有 |
| PTT 進階運算子 | 無 | 支援 `recommend:` 等 |
| 巴哈跨板搜尋 | 無 | 支援 `scope=global` |

---

## 二、整體架構

```
LLM (Claude Code / Claude Desktop)
        ↓ MCP Protocol
┌──────────────────────────────────────┐
│  MCP Server (FastMCP)                 │
│                                       │
│  爬蟲類 toolkit (7):                   │
│  ├─ ptt_search       (Crawlee BS4)    │
│  ├─ bahamut_search   (Crawlee Pwt)    │
│  ├─ mobile01_search  (Crawlee BS4)    │
│  ├─ dcard_search     (Crawlee BS4)    │
│  ├─ komica_search    (Crawlee BS4)    │
│  ├─ exchange_rate    (httpx)          │
│  └─ post_filter      (純邏輯)          │
│                                       │
│  查詢類 toolkit (5):                   │
│  ├─ posts_query                       │
│  ├─ keyword_trend                     │
│  ├─ top_posts                         │
│  ├─ query_recommendations             │
│  └─ query_review                      │
└────┬─────────────────────────────────┘
     ↓ 讀寫
┌──────────────────────────────────────┐
│  PostgreSQL 17                       │
│  ├─ 對照表 (forums/boards/keywords)   │
│  ├─ 進階運算子 (forum_search_operators)│
│  ├─ 過濾輔助 (affinity/blacklist/     │
│              commercial_signals)     │
│  ├─ 主資料 (posts)                    │
│  ├─ 學習表 (search_queries)           │
│  ├─ 觀測 (crawl_log)                  │
│  └─ 通知 (system_notifications)       │
└────┬─────────────────────────────────┘
     ↑ 讀
┌──────────────────────────────────────┐
│  Notifier(獨立排程模組)               │
│  Windows Task Scheduler 每日 09:00    │
│  ├─ 檢查季度檢視/規則漂移/僵化警示      │
│  └─ SMTP 寄 email                    │
└────┬─────────────────────────────────┘
     ↓ SMTP
  📧 Gmail → Jarry 信箱
```

---

## 三、PostgreSQL Schema

### 3.1 對照表(4 張)

#### `forums`(平台主檔)

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | SERIAL PK | |
| `code` | VARCHAR(20) UNIQUE | `ptt` / `bahamut` / `mobile01` / `dcard` / `komica` |
| `name_zh` | VARCHAR(50) | 平台中文名 |
| `base_url` | VARCHAR(255) | |
| `requires_js` | BOOLEAN | 是否需 Playwright |
| `rate_limit_per_min` | INTEGER | 每分鐘最多請求數 |
| `search_url_template` | VARCHAR(500) | 搜尋 URL 模板 |
| `is_active` | BOOLEAN | |

#### `forum_boards`(板別主檔)

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | SERIAL PK | |
| `forum_id` | FK → forums | |
| `board_code` | VARCHAR(50) | 平台內代碼 |
| `name_zh` | VARCHAR(100) | 板中文名 |
| `native_id` | VARCHAR(50) | bsn(巴哈)/ fid(Mobile01)/ 板名(PTT/Dcard) |
| `url_path` | VARCHAR(255) | 該板首頁路徑 |
| `value_score` | INTEGER | 1-10 該板代購情報價值 |
| `notes` | TEXT | |
| `is_active` | BOOLEAN | |
| UNIQUE | (forum_id, board_code) | |

#### `keywords`(關鍵字主檔)

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | SERIAL PK | |
| `keyword` | VARCHAR(100) | 主關鍵字 |
| `tier` | INTEGER | 1=商品 / 2=類別 / 3=行為 |
| `category` | VARCHAR(50) | toy / drugstore / cosmetic / generic |
| `aliases` | TEXT[] | 別名陣列 |
| `weight` | INTEGER | 評分權重 |
| `is_active` | BOOLEAN | |

#### `forum_search_operators`(進階運算子對照)

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | SERIAL PK | |
| `forum_id` | FK → forums | |
| `operator` | VARCHAR(20) | `title` / `author` / `recommend` / `site` |
| `syntax_template` | VARCHAR(100) | 例:`recommend:{value}` |
| `value_type` | VARCHAR(20) | `int` / `string` / `regex` |
| `notes` | TEXT | |
| UNIQUE | (forum_id, operator) | |

### 3.2 過濾輔助表(3 張)

#### `board_keyword_affinity`(板別×關鍵字 親和度)

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | SERIAL PK | |
| `board_id` | FK → forum_boards | |
| `keyword_id` | FK → keywords | |
| `affinity_score` | INTEGER | 0-10,0=禁止組合,10=高度相關 |
| `notes` | TEXT | |
| UNIQUE | (board_id, keyword_id) | |

#### `blacklist_patterns`(內容黑名單)

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | SERIAL PK | |
| `pattern` | VARCHAR(200) | 字串或 regex |
| `pattern_type` | VARCHAR(20) | `keyword` / `regex` |
| `applies_to` | VARCHAR(20) | `title` / `content` / `both` |
| `notes` | TEXT | 例:「徵求文」、「私訊文」 |
| `is_active` | BOOLEAN | |

#### `commercial_signals`(商業訊號加權)

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | SERIAL PK | |
| `signal_text` | VARCHAR(100) | 例:`現貨`、`+P+運`、`下標` |
| `weight` | INTEGER | 加分權重 |
| `category` | VARCHAR(50) | `pricing` / `availability` / `transaction` |
| `is_active` | BOOLEAN | |

### 3.3 主資料表 — `posts`(爬取結果,UPSERT by URL)

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `forum_id` | FK → forums | |
| `board_id` | FK → forum_boards | |
| `native_post_id` | VARCHAR(100) | 平台原生 ID |
| `url` | VARCHAR(500) UNIQUE | **去重鍵** |
| `title` | VARCHAR(500) | |
| `author` | VARCHAR(100) | |
| `content` | TEXT | 內文 |
| `posted_at` | TIMESTAMPTZ | 平台顯示的發文時間 |
| `pushes` | INTEGER | 當前推文數 |
| `boos` | INTEGER | 當前噓文數 |
| `comment_count` | INTEGER | 留言總數 |
| `pushes_history` | TEXT | 推文數歷史,分號分隔,例:`"10;25;47;89;120"` |
| `pushes_history_dt` | TEXT | 對應日期,分號分隔,例:`"2026-04-25;2026-04-28;..."` |
| `latest_score` | INTEGER | post_filter 最新評分 |
| `matched_keywords` | TEXT[] | 最新命中關鍵字 |
| `first_crawled_at` | TIMESTAMPTZ | 首次入庫(不變) |
| `last_crawled_at` | TIMESTAMPTZ | 最近一次更新 |
| `crawl_count` | INTEGER | 被爬次數 |

**索引**:
```sql
CREATE INDEX idx_posts_forum_board_posted ON posts(forum_id, board_id, posted_at DESC);
CREATE INDEX idx_posts_last_crawled ON posts(last_crawled_at);
CREATE INDEX idx_posts_pushes ON posts(pushes DESC);
CREATE INDEX idx_posts_score ON posts(latest_score DESC);
CREATE INDEX idx_posts_fts ON posts USING GIN (to_tsvector('simple', title || ' ' || COALESCE(content, '')));
```

#### `pushes_history` 寫入規則

| 情境 | 行為 |
|---|---|
| 新貼文首次入庫 | 初始化 `pushes_history = "{pushes}"`、`pushes_history_dt = "{今日}"` |
| 同一日重爬 | 覆蓋當天那筆(陣列最後一筆換值,不 append) |
| 跨日重爬,推文數有變 | append 新值與新日期 |
| 跨日重爬,推文數沒變 | 不寫 |
| 陣列已達 10 筆 | append 新值前先砍掉最舊那筆(FIFO) |

**寫入虛擬碼**:
```python
def update_pushes_history(post_row, new_pushes, today_str):
    history = post_row.pushes_history.split(';') if post_row.pushes_history else []
    dates = post_row.pushes_history_dt.split(';') if post_row.pushes_history_dt else []
    
    if not history:  # 首次
        return [str(new_pushes)], [today_str]
    
    if dates[-1] == today_str:  # 同日,覆蓋
        history[-1] = str(new_pushes)
        return history, dates
    
    if int(history[-1]) == new_pushes:  # 跨日但無變化,不寫
        return history, dates
    
    # 跨日且有變,append
    history.append(str(new_pushes))
    dates.append(today_str)
    
    if len(history) > 10:  # 砍最舊
        history = history[-10:]
        dates = dates[-10:]
    
    return history, dates
```

### 3.4 學習表 — `search_queries`(查詢累積學習)

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `keyword` | VARCHAR(200) | 實際使用的搜尋字串 |
| `forum_code` | VARCHAR(20) | 在哪個平台搜 |
| `board_code` | VARCHAR(50) | 在哪個板搜 |
| `operators` | JSONB | 進階運算子,如 `{"recommend": 10}` |
| `created_at` | TIMESTAMPTZ | 第一次使用 |
| `last_used_at` | TIMESTAMPTZ | 最近一次使用 |
| `use_count` | INTEGER DEFAULT 0 | 總使用次數 |
| `total_posts_found` | INTEGER DEFAULT 0 | 累積爬到的貼文數 |
| `passed_posts` | INTEGER DEFAULT 0 | 通過 post_filter 的數量 |
| `hit_rate` | NUMERIC(5,2) | 命中率 = passed/found |
| `avg_score` | NUMERIC(5,2) | 平均評分 |
| `peak_post_count` | INTEGER DEFAULT 0 | 該查詢爬到的爆紅文數量 |
| `is_priority` | BOOLEAN DEFAULT false | 優先使用 |
| `needs_optimization` | BOOLEAN DEFAULT false | 需要優化 |
| `status` | VARCHAR(20) DEFAULT 'active' | active / deprecated / archived |
| `manual_override` | BOOLEAN DEFAULT false | **鎖定:自動規則跳過** |
| `override_reason` | TEXT | 鎖定理由 |
| `override_at` | TIMESTAMPTZ | |
| `override_by` | VARCHAR(50) | `human` / `llm` |
| `parent_query_id` | BIGINT | 從哪個查詢衍生 |
| `optimization_note` | TEXT | LLM 寫入的優化建議 |
| UNIQUE | (keyword, forum_code, board_code) | |

### 3.5 觀測表 — `crawl_log`

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `forum_id` | FK | |
| `tool_name` | VARCHAR(50) | 哪支 toolkit |
| `query_keyword` | VARCHAR(255) | |
| `started_at` | TIMESTAMPTZ | |
| `finished_at` | TIMESTAMPTZ | |
| `posts_fetched` | INTEGER | 本次爬到幾篇 |
| `posts_new` | INTEGER | 其中幾篇是新的 |
| `error_msg` | TEXT | 失敗時的錯誤訊息 |

### 3.6 通知表 — `system_notifications`

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `notification_type` | VARCHAR(50) | `quarterly_review` / `rule_drift` / `rigidity_warning` |
| `triggered_at` | TIMESTAMPTZ | |
| `scope` | JSONB | 詳細內容 |
| `email_sent` | BOOLEAN DEFAULT false | |
| `email_sent_at` | TIMESTAMPTZ | |
| `email_to` | VARCHAR(200) | |
| `acknowledged` | BOOLEAN DEFAULT false | |
| `acknowledged_at` | TIMESTAMPTZ | |
| `next_review_at` | TIMESTAMPTZ | 下次再提醒 |

---

## 四、Seed Data

### 4.1 `forums` 啟動資料

| code | name_zh | base_url | requires_js | rate/min | 搜尋模板 |
|---|---|---|---|---|---|
| `ptt` | PTT | `https://www.ptt.cc` | false | 60 | `/bbs/{board}/search?q={kw}` |
| `bahamut` | 巴哈姆特 | `https://forum.gamer.com.tw` | true | 30 | `/B.php?bsn={bsn}&qt=2&q={kw}` |
| `mobile01` | Mobile01 | `https://www.mobile01.com` | false | 30 | `/googlesearch.php?q={kw}` |
| `dcard` | Dcard | `https://www.google.com` | false | 6 | `/search?q=site:dcard.tw+{kw}` |
| `komica` | Komica | `https://www.komica.org` | false | 30 | (無原生搜尋,爬最新 N 頁過濾) |

### 4.2 `forum_search_operators`(PTT 進階運算子)

| forum | operator | syntax_template | value_type | notes |
|---|---|---|---|---|
| ptt | title | `title:{value}` | string | 標題包含 |
| ptt | author | `author:{value}` | string | 限定作者 |
| ptt | recommend | `recommend:{value}` | int | 推文數 ≥ value(可負) |

### 4.3 巴哈姆特板別 bsn 對照

| board_code | name_zh | bsn | value_score |
|---|---|---|---|
| `beyblade` | 戰鬥陀螺系列 | 2696 | 10 |
| `pokemon_main` | 神奇寶貝(精靈寶可夢)系列 | 1647 | 8 |
| `pokemon_master` | 寶可夢大師 | 36673 | 6 |
| `pokemon_unite` | 寶可夢大集結 | 38783 | 5 |
| `pokemon_sleep` | Pokémon Sleep | 36685 | 5 |
| `pokemon_live` | 寶可夢戰鬥卡 Live | 21259 | 9 |
| `pokemon_pocket` | 寶可夢集換式卡牌遊戲口袋版 | 79688 | 9 |
| `pokemon_champion` | 寶可夢 冠軍 | 85164 | 7 |
| `toy_general` | 綜合公仔玩具討論區 | 60036 | 10 |
| `model_girls` | 模型少女:限定特典 | 39003 | 4 |
| `model_tech` | 模型技術與資訊 | 60053 | 7 |
| `western_anime` | 歐美動畫綜合討論 | 60605 | 5 |

### 4.4 Mobile01 子板 fid 對照

| board_code | name_zh | fid | value_score |
|---|---|---|---|
| `home_appliance` | 生活家電 | 168 | 9 |
| `kitchen_appliance` | 廚房家電 | 729 | 7 |
| `cosmetics` | 彩妝保養 | 371 | 8 |
| `travel_food_other` | 旅遊美食其他討論 | 345 | 7 |
| `style_grooming` | 造型與保養 | 301 | 6 |
| `fashion` | 時尚流行 | 373 | 6 |
| `intl_news` | 國際新聞 | 780 | 4 |
| `chitchat` | 閒聊與趣味 | 37 | 3 |
| `health` | 健康與養生 | 330 | 7 |
| `entrepreneur` | 創業夢想家 | 747 | 8 |
| `northeast_asia` | 東北亞 | 405 | 9 |
| `accommodation` | 住宿訂房 | 703 | 6 |
| `roaming` | 電信漫遊 | 702 | 5 |

### 4.5 PTT 板別

| board_code | name_zh | value_score |
|---|---|---|
| `e-shopping` | 線上購物板 | 10 |
| `HelpBuy` | 代購代買板 | 10 |
| `Japan_Travel` | 日本旅遊板 | 9 |
| `Beauty` | 美妝板 | 8 |
| `MakeUp` | 化妝板 | 8 |
| `Lifeismoney` | 省錢板 | 7 |
| `BabyMother` | 媽寶板 | 6 |
| `Toy_Hobby` | 玩具收藏板 | 9 |

### 4.6 Dcard 板別

| board_code | name_zh | value_score |
|---|---|---|
| `makeup` | 美妝板 | 8 |
| `buyonline` | 網路購物板 | 9 |
| `fashion` | 穿搭板 | 6 |
| `mood` | 心情板 | 3 |

### 4.7 Komica 板別(W3 開工前再驗證)

| board_code | name_zh | url_path | value_score |
|---|---|---|---|
| `figure` | 模型公仔板 | `/00/?title=模型公仔` | 7 |
| `toy` | 玩具版 | `/00/?title=玩具` | 6 |
| `cosp` | 收藏品板 | `/00/?title=收藏品` | 5 |

### 4.8 關鍵字 45 個

**Tier 1 商品具體名(20)**
```
戰鬥陀螺、UX-15、UX-03、BX-23、Beyblade
合利他命、EVE 止痛藥、安耐曬、ANESSA
KATE 唇膏、Quality 1st、Melano CC
LeTAO、Royce、東京芭娜娜
Switch 2、Panasonic、Dyson
Pokemon 卡、一番賞
```

**Tier 2 類別+地域(10)**
```
日本藥妝、日本美妝、日本零食、日本伴手禮、日本必買
日本電器、日本玩具、日本動漫、日本必敗、日本戰利品
```

**Tier 3 代購行為訊號(15)**
```
代購、團購、開團、揪團、預購
戰利品、開箱、實測、退稅、免稅
唐吉訶德、松本清、Yodobashi、樂天、Amazon JP
```

### 4.9 商業訊號 seed

| signal_text | weight | category |
|---|---|---|
| 現貨 | 5 | availability |
| 預購 | 4 | availability |
| 現+1 | 5 | availability |
| 售價 | 4 | pricing |
| 含運 | 3 | pricing |
| +P+運 | 4 | pricing |
| 下標 | 3 | transaction |
| 私訊報價 | 2 | transaction |
| 收單 | 4 | transaction |
| 開團 | 5 | transaction |

### 4.10 黑名單 seed

| pattern | applies_to | notes |
|---|---|---|
| 徵 | title | 求購文,過濾 |
| 收 | title | 求購文 |
| 詢問 | title | 純諮詢,無情報 |
| 廣告 | title | 純廣告 |

---

## 五、自動規則(規則引擎)

### 5.1 規則 R1 — 標記 `is_priority = true`

任一條件成立即標記:

| 條件代碼 | 條件 | 理由 |
|---|---|---|
| R1-a | `avg_score >= 7 AND use_count >= 3` | 用過 3 次以上、平均分高 |
| R1-b | `hit_rate >= 50 AND use_count >= 5` | 命中率高 |
| R1-c | `peak_post_count >= 3` | 找得到爆紅文 |

### 5.2 規則 R2 — 標記 `needs_optimization = true`

| 條件代碼 | 條件 |
|---|---|
| R2-a | `hit_rate < 10 AND use_count >= 5` |
| R2-b | `avg_score < 3 AND use_count >= 5` |
| R2-c | `passed_posts = 0 AND use_count >= 3` |

### 5.3 規則 R3 — 標記 `status = 'deprecated'`

- `last_used_at < now() - interval '90 days'` AND `manual_override = false`

### 5.4 規則 R4 — `manual_override` 鎖定保護

- `manual_override = true` 的列,**自動規則一律跳過**,僅更新客觀指標(`use_count`、`hit_rate`、`avg_score`、`peak_post_count`、`last_used_at`)

### 5.5 執行時機

- **觸發式**:每次爬蟲 toolkit 執行完,UPSERT `search_queries` 後**只重算這一筆**
- 不掃全表,效能佳
- 實作:Application 層 hook(SQLAlchemy event 或 service 方法)

---

## 六、MCP Toolkit 規格(12 支)

### 6.1 共用設計

- 執行流程:LLM 呼叫 → MCP 查 DB 取對照碼 → Crawlee 爬取 → UPSERT posts → 寫 search_queries → 跑規則 → 回 LLM
- 回傳格式:統一 JSON,含 `posts` array、`meta` 物件
- 錯誤處理:拋出明確 exception 給 LLM
- log 寫 file/stderr,**禁寫 stdout**(MCP stdio 通訊)

### 6.2 爬蟲類 toolkit(7)

#### `ptt_search`

| 屬性 | 規格 |
|---|---|
| **輸入** | `keyword: str`<br>`board_code: str`<br>`limit: int=20`<br>`min_recommend: int \| None`(進階)<br>`title_only: bool=False`(進階)<br>`author: str \| None`(進階) |
| **DB 查詢** | `forums` 取 search_url_template;`forum_boards` 確認 board 啟用;`forum_search_operators` 取運算子模板 |
| **執行步驟** | 1. 構造搜尋 URL(含進階運算子)<br>2. Crawlee BeautifulSoupCrawler,帶 `over18=1` cookie,驗證非中介頁<br>3. 解析 `div.r-ent`<br>4. 對每筆抓內文 + 推文/噓文計數(不存內文)<br>5. UPSERT 進 posts,更新 pushes_history<br>6. UPSERT search_queries,觸發規則<br>7. 回傳 list[Post] |
| **輸出** | `[{title, author, content, pushes, boos, comment_count, posted_at, url, latest_score?}]` |

#### `bahamut_search`

| 屬性 | 規格 |
|---|---|
| **輸入** | `keyword: str`<br>`scope: "board" \| "global" = "board"`<br>`board_code: str \| None`(scope=board 時必填)<br>`limit: int=20` |
| **DB 查詢** | scope=board 時讀 `forum_boards.native_id`(bsn) |
| **執行步驟** | 1. 構造 URL:scope=board 用 `B.php?bsn={bsn}&qt=2&q={kw}`,scope=global 用 `G2.php?qt=2&q={kw}`<br>2. Crawlee PlaywrightCrawler,等 networkidle<br>3. 解析結果列表<br>4. **sequential** 對每筆開頁取內文(避免記憶體爆),寫死 `max_concurrency=3`<br>5. UPSERT posts<br>6. UPSERT search_queries<br>7. 回傳 list[Post] |
| **輸出** | 同 ptt_search |

#### `mobile01_search`

| 屬性 | 規格 |
|---|---|
| **輸入** | `keyword: str`<br>`board_code: str \| None`<br>`limit: int=20` |
| **DB 查詢** | 若指定 board,從 `forum_boards.native_id` 取 fid |
| **執行步驟** | 1. 若 board 有指定,組 query=`{kw} site:mobile01.com/topiclist.php?f={fid}`<br>2. 呼叫 `mobile01.com/googlesearch.php`<br>3. Crawlee BS4 解析<br>4. 對每筆抓內文(只第一頁留言計數,不存留言)<br>5. UPSERT posts<br>6. UPSERT search_queries<br>7. 回傳 list[Post] |
| **輸出** | 同 ptt_search |

#### `dcard_search`

| 屬性 | 規格 |
|---|---|
| **輸入** | `keyword: str`<br>`board_code: str \| None`<br>`limit: int=10` |
| **DB 查詢** | 若指定 board,組 `site:dcard.tw/f/{board_code}` |
| **執行步驟** | 1. 構造 Google 查詢<br>2. 呼叫 Google Custom Search API(免費 100 次/日)<br>3. **只回搜尋摘要,不抓內文**<br>4. UPSERT posts(content 為 snippet)<br>5. UPSERT search_queries |
| **輸出** | `[{title, snippet, url, posted_at?}]`(無 content、無 comments) |

#### `komica_search`

| 屬性 | 規格 |
|---|---|
| **輸入** | `keyword: str`<br>`board_code: str`<br>`limit: int=10`(預設小,因需先爬再過濾) |
| **DB 查詢** | `forum_boards.url_path` |
| **執行步驟** | 1. Crawlee BeautifulSoupCrawler 爬指定板最新 N 頁<br>2. 對標題+內文做關鍵字過濾<br>3. UPSERT posts<br>4. UPSERT search_queries |
| **輸出** | 同 ptt_search |

#### `exchange_rate`

| 屬性 | 規格 |
|---|---|
| **輸入** | 無 |
| **執行步驟** | 1. httpx GET 台銀 CSV<br>2. 解析 JPY 列<br>3. **不入庫**(匯率即時值,不需歷史)<br>4. 回傳當前匯率 |
| **輸出** | `{rate: 0.21, captured_at: "2026-05-04T14:00:00"}` |

#### `post_filter`

| 屬性 | 規格 |
|---|---|
| **輸入** | `post: dict`<br>`keywords: list[str] \| None`(預設讀 DB) |
| **DB 查詢** | `keywords`、`blacklist_patterns`、`commercial_signals`、`board_keyword_affinity` |
| **執行步驟** | 1. 算 Tier 1/2/3 命中分<br>2. 加分:商業訊號、互動、板別 affinity<br>3. 硬性條件:長度、黑名單<br>4. 回傳 score、passed |
| **輸出** | `{passed: bool, score: int, matched_keywords: [...], reason: str}` |

### 6.3 查詢類 toolkit(5)— 不爬蟲,純查 DB

#### `posts_query`

| 屬性 | 規格 |
|---|---|
| **輸入** | `keywords: list[str] \| None`<br>`forum_codes: list[str] \| None`<br>`board_codes: list[str] \| None`<br>`posted_after: datetime \| None`<br>`min_pushes: int \| None`<br>`min_score: int \| None`<br>`limit: int=50` |
| **執行** | 純 SQL 查 posts,套全文檢索(GIN index) |
| **用途** | LLM 問「上週推文 50 以上的代購文」即時回應 |

#### `keyword_trend`

| 屬性 | 規格 |
|---|---|
| **輸入** | `keyword: str`<br>`granularity: "day" \| "week" = "week"`<br>`weeks: int=4` |
| **執行** | 用 `posted_at` 分組統計命中文章數、平均推文、板別分布 |
| **輸出** | `[{period, post_count, avg_pushes, board_distribution}]` |

#### `top_posts`

| 屬性 | 規格 |
|---|---|
| **輸入** | `forum_code: str \| None`<br>`board_code: str \| None`<br>`posted_after: datetime`<br>`order_by: "pushes" \| "score" = "pushes"`<br>`limit: int=20` |
| **執行** | 純 SQL ORDER BY |
| **用途** | 「最近一週最熱代購文」 |

#### `query_recommendations`

| 屬性 | 規格 |
|---|---|
| **輸入** | `topic: str`<br>`limit: int=10` |
| **執行** | 查 `search_queries WHERE is_priority=true AND keyword ILIKE '%{topic}%'` ORDER BY avg_score DESC |
| **用途** | LLM 編排前先問:「我要查戰鬥陀螺,有什麼歷史上效果好的查詢?」 |

#### `query_review`

| 屬性 | 規格 |
|---|---|
| **輸入** | `filter: "needs_optimization" \| "deprecated" \| "all" = "needs_optimization"`<br>`limit: int=20` |
| **執行** | 查對應 flag 的 search_queries |
| **用途** | LLM 主動分析待優化查詢,可呼叫 `query_review_update` 寫回 manual_override |

#### `query_review_update`(輔助寫回)

| 屬性 | 規格 |
|---|---|
| **輸入** | `query_id: int`<br>`is_priority: bool \| None`<br>`needs_optimization: bool \| None`<br>`status: str \| None`<br>`reason: str` |
| **執行** | UPDATE search_queries SET 對應欄位、`manual_override=true`、`override_reason=reason`、`override_at=now()`、`override_by='llm'` |

---

## 七、Notifier 模組(獨立排程,不走 MCP)

### 7.1 部署方式

Windows Task Scheduler:
```
schtasks /create /tn "WindVane Notifier" \
         /tr "C:\path\to\uv.exe --directory C:\path\to\wind-vane-mcp run python -m wind_vane.notifier" \
         /sc daily /st 09:00
```

### 7.2 程式邏輯

```python
# wind_vane/notifier/main.py
async def run_notification_check():
    if is_quarterly_review_due():
        notif = create_notification('quarterly_review', scope=...)
        await send_email(notif)
    
    if count_needs_optimization() >= 20 and not_recently_warned('rule_drift', 30):
        notif = create_notification('rule_drift', scope=...)
        await send_email(notif)
    
    rigid_queries = find_rigid_queries(days=30)
    if rigid_queries:
        notif = create_notification('rigidity_warning', scope=...)
        await send_email(notif)
```

### 7.3 三種通知

| 類型 | 觸發條件 | 內容 |
|---|---|---|
| `quarterly_review` | 系統首筆 search_queries.created_at 距今 ≥ 90 天,且最近 90 天未發過此類通知 | 季度檢視大盤摘要 |
| `rule_drift` | `needs_optimization=true` 累積 ≥ 20 筆,且最近 30 天未發過 | 待優化清單 |
| `rigidity_warning` | `manual_override=true` 的查詢,最近 30 天 hit_rate 連續下滑 | 標註可能過時 |

### 7.4 SMTP 設定(`config/settings.toml`)

```toml
[notifier]
enabled = true
email_to = "jarry@example.com"
email_from = "wind-vane-notifier@localhost"

[notifier.smtp]
host = "smtp.gmail.com"
port = 587
username = "your-gmail@gmail.com"
password = "${SMTP_PASSWORD}"
use_tls = true
```

### 7.5 Email 範本(摘要)

```
主旨:[風向計] 季度檢視提醒 - 47 組查詢累積待檢視

▌ 查詢統計
  - 累積查詢組合:47
  - 已標記為 priority:8
  - 需要優化:23  ← 建議檢視
  - 已棄用:4

▌ 表現最佳的查詢(top 5)
  1. 戰鬥陀螺 @ bahamut/beyblade   命中率 78%, 平均分 8.2
  ...

▌ 建議優化的查詢(top 5)
  1. 日本玩具 @ ptt/Lifeismoney    命中率 4%, 雜訊太多
  ...
```

---

## 八、執行流程範例

### 8.1 範例 A:LLM 編排,先查歷史最佳查詢

```
User → LLM:「給我這週戰鬥陀螺的代購情報」

LLM 編排:
1. mcp.query_recommendations(topic="戰鬥陀螺", limit=5)
   ↓ 回傳歷史 priority 查詢

2. 對 top 3 priority 查詢分別呼叫對應 tool
   mcp.bahamut_search(keyword="戰鬥陀螺", scope="board", board_code="beyblade")
   mcp.ptt_search(keyword="戰鬥陀螺", board_code="Toy_Hobby", min_recommend=10)
   ...
   
   每次呼叫:
   - 查 forum_boards 取 native_id
   - Crawlee 爬取
   - UPSERT posts(更新 pushes_history)
   - UPSERT search_queries(累積指標 + 觸發規則 R1-R4)

3. mcp.post_filter(post=每篇)

4. LLM 整理高分文章回應 User
```

### 8.2 範例 B:純 DB 查詢,瞬間回應

```
User → LLM:「過去 4 週日本代購討論的熱度趨勢」

LLM 編排:
1. mcp.keyword_trend(keyword="日本+代購", granularity="week", weeks=4)
   ↓ 純 SQL,毫秒級回應

2. LLM 直接回應(不打爬蟲)
```

### 8.3 範例 C:LLM 主動優化

```
User → LLM:「順便檢查一下哪些搜尋查詢效果差」

LLM 編排:
1. mcp.query_review(filter="needs_optimization", limit=10)
2. 對每筆分析:可能是板別不對、或關鍵字過廣
3. mcp.query_review_update(query_id=X, is_priority=false, status="deprecated", reason="...")
   ↑ 自動規則從此跳過此筆(manual_override=true)
```

---

## 九、開發優先順序與時程(Phase 1,6 週)

| 週次 | 任務 | 產出 |
|---|---|---|
| **W1** | PostgreSQL 17 + 完整 schema(10 張表)+ seed data | DB 可查、可寫測試資料 |
| **W2** | Crawlee + FastMCP 骨架 + ptt_search(含進階運算子) + posts UPSERT 邏輯 | 第一支 toolkit 從 LLM 可用,入庫正確 |
| **W3** | bahamut_search(雙 scope)+ komica_search + 規則引擎 R1-R4 | 主戰場可用,規則自動觸發 |
| **W4** | mobile01_search + post_filter(含黑名單/商業訊號) | 過濾管線可用 |
| **W5** | dcard_search + exchange_rate + 5 支查詢類 toolkit | 全 12 支 toolkit 完成 |
| **W6** | Notifier 模組 + 整合測試 + Claude Desktop 設定 + log 規範 | 可在 Claude 中對話、Email 通知運作 |

---

## 十、技術選型(確定)

| 項目 | 選用 |
|---|---|
| 語言 | Python 3.12 |
| 套件管理 | uv |
| 爬蟲框架 | **Crawlee Python 1.3.x** |
| MCP 框架 | FastMCP |
| HTML 解析 | BeautifulSoup4(Crawlee 內附) |
| 瀏覽器 | Playwright Chromium(Crawlee 管理) |
| HTTP(非 Crawlee 用,如匯率) | httpx |
| 資料庫 | PostgreSQL 17(本機 Windows) |
| ORM | SQLAlchemy 2.0(async)+ Alembic |
| 設定 | pydantic-settings |
| 日誌 | structlog(寫 file/stderr,**禁寫 stdout**) |
| 程式風格 | ruff + mypy |
| 排程 | Windows Task Scheduler(Notifier 用) |
| Email | aiosmtplib |

---

## 十一、Phase 1 不做的事

| 項目 | 原因 |
|---|---|
| 完整 comments 全文入庫 | 體積爆炸,只存推文/噓文/留言計數 |
| 推文增長時序圖(同篇文連續多日記錄) | 已用 `pushes_history` 字串欄位解決,不另立表 |
| 排程自動爬 | LLM 觸發即可,Phase 1 不主動爬 |
| Workflow 業務封裝 | toolkit 夠用,LLM 自己編排 |
| 商家爬蟲(蝦皮等) | 反爬重、法律灰色 |
| 日本論壇(2ch、Reddit) | Phase 2 |
| LINE Bot 推播 | Phase 2(已用 Email 替代) |
| 商品 SKU 主檔 | 等實際資料反推 |
| Rust 加速 | 規模太小不需要 |
| 推文增長**完整時序**圖 | 字串欄位最多 10 筆,完整時序待 Phase 2 |

---

## 十二、Phase 2 候選

1. 加日本論壇:2ch、5ch、Reddit
2. 加商家爬蟲(評估反爬可行性)
3. 推文增長獨立 history 表(若 10 筆字串不夠)
4. SKU 主檔(從爬取結果反推)
5. 排程自動爬(熱門關鍵字定期更新)
6. LINE Bot 推播(取代或補充 Email)
7. 全文檢索升級(pg_bigm 或 zhparser)

---

## 十三、Windows 環境注意事項

### 13.1 Playwright 路徑

Crawlee 使用 Playwright 的 Chromium。安裝:
```powershell
uv run playwright install chromium
```

預設裝在 `%USERPROFILE%\AppData\Local\ms-playwright\`。Claude Desktop 啟動 MCP Server 時環境變數可能不一致,於 `claude_desktop_config.json` 顯式設定:

```json
{
  "env": {
    "PLAYWRIGHT_BROWSERS_PATH": "C:\\Users\\jarry\\AppData\\Local\\ms-playwright"
  }
}
```

### 13.2 Log 寫入位置

```python
# 強制寫 file,不寫 stdout
import logging
import structlog
from pathlib import Path

LOG_DIR = Path.home() / "AppData" / "Local" / "wind-vane-mcp" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(LOG_DIR / "server.log"),
    level=logging.INFO,
)
```

### 13.3 Claude Desktop 設定範本

`%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "wind-vane": {
      "command": "C:\\Users\\jarry\\.local\\bin\\uv.exe",
      "args": [
        "--directory", "D:\\projects\\wind-vane-mcp",
        "run", "python", "-m", "wind_vane.server"
      ],
      "env": {
        "DATABASE_URL": "postgresql+asyncpg://postgres:xxx@localhost:5432/wind_vane",
        "PLAYWRIGHT_BROWSERS_PATH": "C:\\Users\\jarry\\AppData\\Local\\ms-playwright",
        "SMTP_PASSWORD": "your-gmail-app-password"
      }
    }
  }
}
```

---

## 十四、立即可開始的下一步交付物

1. **A**:完整 DDL SQL(10 張表 + 索引 + seed insert)
2. **B**:`pyproject.toml` + Alembic 初始 migration
3. **C**:FastMCP Server 骨架 + 12 toolkit 介面定義
4. **D**:Notifier 模組骨架 + Email 範本

任選或全部,直接交付。

---

**版本歷史**

- v1.0(2026-04 初稿):不入庫,6 toolkit
- v1.1(討論中):導入 Crawlee + 進階運算子 + Komica + 巴哈跨板
- **v1.2(本版,2026-05-05)**:全面入庫 + 搜尋查詢學習 + Email 通知 + 12 toolkit
