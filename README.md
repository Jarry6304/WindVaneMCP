# 風向計 MCP — 台灣論壇代購情報系統

FastMCP + Crawlee + PostgreSQL 17 的論壇爬蟲與情報彙整系統。  
透過 MCP 協議暴露 13 個工具給 Claude，涵蓋 PTT、巴哈姆特、Mobile01、Dcard、Komica 五大論壇。

---

## 系統需求

| 項目 | 版本 |
|---|---|
| Python | 3.12+ |
| PostgreSQL | 17（本機） |
| uv | 最新版 |
| Playwright Chromium | 透過 `uv run playwright install chromium` 安裝 |

---

## 一、安裝

```powershell
# 1. clone 專案
git clone https://github.com/Jarry6304/WindVaneMCP.git
cd WindVaneMCP

# 2. 安裝所有相依套件（含 dev 工具）
uv sync --extra dev

# 3. 安裝 Playwright Chromium（巴哈姆特爬蟲需要）
uv run playwright install chromium
```

---

## 二、資料庫設定

### 2.1 建立 PostgreSQL 資料庫

```sql
-- 以 postgres 超級使用者執行
CREATE DATABASE wind_vane;
CREATE USER windvane WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE wind_vane TO windvane;
```

### 2.2 環境變數

複製 `.env.example`（或直接建立 `.env`）：

```dotenv
DATABASE_URL=postgresql+asyncpg://windvane:your_password@localhost:5432/wind_vane
SMTP_PASSWORD=your_gmail_app_password
```

### 2.3 執行 Alembic migration

```powershell
uv run alembic upgrade head
```

### 2.4 匯入 Seed Data

```powershell
uv run python -c "
import asyncio
from wind_vane.db.connection import AsyncSessionLocal
from wind_vane.db.seed import seed_all

async def main():
    async with AsyncSessionLocal() as session:
        await seed_all(session)
        await session.commit()
        print('seed OK')

asyncio.run(main())
"
```

---

## 三、Claude Desktop 設定

複製 `claude_desktop_config.example.json` 的 `wind-vane` 區塊到  
`%APPDATA%\Claude\claude_desktop_config.json` 的 `mcpServers` 下：

```json
{
  "mcpServers": {
    "wind-vane": {
      "command": "C:\\Users\\jarry\\.local\\bin\\uv.exe",
      "args": [
        "--directory", "D:\\projects\\WindVaneMCP",
        "run", "python", "-m", "wind_vane.server"
      ],
      "env": {
        "DATABASE_URL": "postgresql+asyncpg://windvane:password@localhost:5432/wind_vane",
        "PLAYWRIGHT_BROWSERS_PATH": "C:\\Users\\jarry\\AppData\\Local\\ms-playwright",
        "SMTP_PASSWORD": "your-gmail-app-password"
      }
    }
  }
}
```

> **注意**：`command` 需填寫 `uv.exe` 的完整路徑（`where uv` 可查詢）。  
> Playwright 路徑若不符，巴哈姆特工具會無法啟動瀏覽器。

重新啟動 Claude Desktop，左下角 MCP 圖示應顯示 `wind-vane` 已連線。

---

## 四、Email 通知設定

### 4.1 Gmail App Password

1. Google 帳號 → 安全性 → 兩步驟驗證（需開啟）
2. 搜尋「應用程式密碼」→ 新增 → 選「其他」→ 輸入 `WindVane`
3. 複製產生的 16 位密碼，填入 `SMTP_PASSWORD`

### 4.2 通知設定（`config/settings.toml`）

```toml
[notifier]
enabled = true
email_to   = "you@gmail.com"
email_from = "wind-vane-notifier@localhost"

[notifier.smtp]
host     = "smtp.gmail.com"
port     = 587
username = "your-gmail@gmail.com"
password = "${SMTP_PASSWORD}"
use_tls  = true
```

### 4.3 Windows Task Scheduler — 每日自動檢查

```powershell
schtasks /create /tn "WindVane Notifier" `
  /tr "C:\Users\jarry\.local\bin\uv.exe --directory D:\projects\WindVaneMCP run python -m wind_vane.notifier" `
  /sc daily /st 09:00 /ru SYSTEM
```

三種通知觸發條件：

| 類型 | 條件 |
|---|---|
| `quarterly_review` | 首筆查詢距今 ≥ 90 天，且近 90 天未發過 |
| `rule_drift` | `needs_optimization` 查詢累積 ≥ 20 筆，且近 30 天未發過 |
| `rigidity_warning` | `manual_override=true` 且近 30 天命中率 < 20% 的查詢 |

---

## 五、Log 位置

| 作業系統 | 路徑 |
|---|---|
| Windows | `%LOCALAPPDATA%\wind-vane-mcp\logs\server.log` |
| macOS / Linux | `~/.local/share/wind-vane-mcp/logs/server.log` |

- **stdlib logging** → 寫入上述 log 檔（file only）  
- **structlog** → 輸出至 stderr（IDE console 可見）  
- **stdout** → 永不使用（保留給 MCP stdio 協議）

---

## 六、MCP 工具一覽

### 爬蟲類（7 支）

| 工具 | 說明 |
|---|---|
| `tool_ptt_search` | PTT 板搜尋，支援 `min_recommend`、`title_only`、`author` 進階運算子 |
| `tool_bahamut_search` | 巴哈姆特搜尋，`scope="board"` 或 `scope="global"` |
| `tool_mobile01_search` | Mobile01 搜尋，可指定子板 `board_code` |
| `tool_dcard_search` | Dcard 透過 Google 搜尋，回傳 title + snippet |
| `tool_komica_search` | Komica 爬最新頁後關鍵字過濾 |
| `tool_exchange_rate` | 即時 JPY/TWD 匯率（台銀 CSV，不入庫） |
| `tool_post_filter` | 對一篇 post dict 評分（關鍵字 tier × weight + 商業訊號 + 推文數） |

### 查詢類（6 支）

| 工具 | 說明 |
|---|---|
| `tool_posts_query` | 多條件查詢已入庫文章（關鍵字、論壇、時間、推文數、評分） |
| `tool_keyword_trend` | 關鍵字週期趨勢（day / week 粒度） |
| `tool_top_posts` | 依推文數或評分排行榜 |
| `tool_query_recommendations` | 查詢歷史高效搜尋組合（topic 模糊比對 is_priority 列） |
| `tool_query_review` | 列出待優化 / deprecated / 全部查詢 |
| `tool_query_review_update` | LLM 寫回 `manual_override`、`status`、`reason` |

---

## 七、典型使用流程

```
User → Claude：「給我本週戰鬥陀螺的代購情報」

1. tool_query_recommendations(topic="戰鬥陀螺")
   → 取得歷史高效查詢組合

2. tool_bahamut_search(keyword="戰鬥陀螺", board_code="beyblade")
   tool_ptt_search(keyword="戰鬥陀螺", board_code="Toy_Hobby", min_recommend=10)
   → 爬取、UPSERT posts、觸發規則引擎 R1-R4

3. tool_post_filter(post=每篇)
   → 過濾低品質文章

4. Claude 整理高分文章回應
```

---

## 八、開發測試

```powershell
# 執行全部測試（163 個，使用 SQLite in-memory）
uv run --extra dev pytest tests/ -v

# 只跑特定類別
uv run --extra dev pytest tests/test_notifier_triggers.py -v
uv run --extra dev pytest tests/test_post_filter_full.py -v
```

> 爬蟲類測試（`test_ptt_parse`、`test_bahamut_scope` 等）只測純邏輯函式，不發網路請求。  
> DB 整合測試使用 SQLite in-memory，不需要 PostgreSQL。

---

## 九、規則引擎

每次爬蟲 UPSERT `search_queries` 後，**只對當筆**觸發 R1-R4：

| 規則 | 動作 | 條件 |
|---|---|---|
| R1 | `is_priority = true` | avg_score ≥ 7 且 use_count ≥ 3，或 hit_rate ≥ 50% 且 use_count ≥ 5，或 peak_post_count ≥ 3 |
| R2 | `needs_optimization = true` | hit_rate < 10% 且 use_count ≥ 5，或 avg_score < 3 且 use_count ≥ 5，或 passed=0 且 use_count ≥ 3 |
| R3 | `status = "deprecated"` | 90 天未使用 |
| R4 | 跳過 R1-R3 | `manual_override = true`（人工或 LLM 鎖定） |

---

## 十、專案結構

```
WindVaneMCP/
├── alembic/                    # DB migration
│   └── versions/0001_initial_schema.py
├── config/
│   └── settings.toml           # SMTP / 通知設定
├── tests/                      # 163 個測試
├── wind_vane/
│   ├── config.py               # pydantic-settings
│   ├── log.py                  # 集中式 logging（stdlib→file, structlog→stderr）
│   ├── server.py               # FastMCP 入口（python -m wind_vane.server）
│   ├── db/
│   │   ├── models.py           # 11 張 SQLAlchemy 2.0 ORM 模型
│   │   ├── connection.py       # AsyncSessionLocal
│   │   └── seed.py             # 初始對照資料
│   ├── notifier/
│   │   └── main.py             # Email 通知排程（python -m wind_vane.notifier）
│   ├── rules/
│   │   └── engine.py           # R1-R4 自動規則
│   └── toolkits/
│       ├── crawlers/           # 7 支爬蟲工具
│       │   ├── upsert.py       # UPSERT 共用 helpers
│       │   └── ...
│       └── queries/            # 5 支查詢工具
└── claude_desktop_config.example.json
```
