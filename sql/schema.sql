-- WindVane MCP — Reference DDL (PostgreSQL 17)
-- Authoritative schema is managed by Alembic migrations.
-- Run: uv run alembic upgrade head

CREATE TABLE IF NOT EXISTS forums (
    id SERIAL PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,
    name_zh VARCHAR(50) NOT NULL,
    base_url VARCHAR(255) NOT NULL,
    requires_js BOOLEAN NOT NULL DEFAULT false,
    rate_limit_per_min INTEGER NOT NULL,
    search_url_template VARCHAR(500),
    is_active BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS forum_boards (
    id SERIAL PRIMARY KEY,
    forum_id INTEGER NOT NULL REFERENCES forums(id),
    board_code VARCHAR(50) NOT NULL,
    name_zh VARCHAR(100) NOT NULL,
    native_id VARCHAR(50),
    url_path VARCHAR(255),
    value_score INTEGER NOT NULL DEFAULT 5,
    notes TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    UNIQUE (forum_id, board_code)
);

CREATE TABLE IF NOT EXISTS keywords (
    id SERIAL PRIMARY KEY,
    keyword VARCHAR(100) NOT NULL,
    tier INTEGER NOT NULL,          -- 1=商品 / 2=類別 / 3=行為
    category VARCHAR(50) NOT NULL,  -- toy / drugstore / cosmetic / generic
    aliases TEXT[],
    weight INTEGER NOT NULL DEFAULT 5,
    is_active BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS forum_search_operators (
    id SERIAL PRIMARY KEY,
    forum_id INTEGER NOT NULL REFERENCES forums(id),
    operator VARCHAR(20) NOT NULL,
    syntax_template VARCHAR(100) NOT NULL,
    value_type VARCHAR(20) NOT NULL,
    notes TEXT,
    UNIQUE (forum_id, operator)
);

CREATE TABLE IF NOT EXISTS board_keyword_affinity (
    id SERIAL PRIMARY KEY,
    board_id INTEGER NOT NULL REFERENCES forum_boards(id),
    keyword_id INTEGER NOT NULL REFERENCES keywords(id),
    affinity_score INTEGER NOT NULL DEFAULT 5, -- 0=禁止組合, 10=高度相關
    notes TEXT,
    UNIQUE (board_id, keyword_id)
);

CREATE TABLE IF NOT EXISTS blacklist_patterns (
    id SERIAL PRIMARY KEY,
    pattern VARCHAR(200) NOT NULL,
    pattern_type VARCHAR(20) NOT NULL, -- keyword / regex
    applies_to VARCHAR(20) NOT NULL,   -- title / content / both
    notes TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS commercial_signals (
    id SERIAL PRIMARY KEY,
    signal_text VARCHAR(100) NOT NULL,
    weight INTEGER NOT NULL,
    category VARCHAR(50) NOT NULL, -- pricing / availability / transaction
    is_active BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS posts (
    id BIGSERIAL PRIMARY KEY,
    forum_id INTEGER NOT NULL REFERENCES forums(id),
    board_id INTEGER REFERENCES forum_boards(id),
    native_post_id VARCHAR(100),
    url VARCHAR(500) UNIQUE NOT NULL,
    title VARCHAR(500) NOT NULL,
    author VARCHAR(100),
    content TEXT,
    posted_at TIMESTAMPTZ,
    pushes INTEGER NOT NULL DEFAULT 0,
    boos INTEGER NOT NULL DEFAULT 0,
    comment_count INTEGER NOT NULL DEFAULT 0,
    pushes_history TEXT,
    pushes_history_dt TEXT,
    latest_score INTEGER,
    matched_keywords TEXT[],
    first_crawled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_crawled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    crawl_count INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_posts_forum_board_posted ON posts(forum_id, board_id, posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_posts_last_crawled ON posts(last_crawled_at);
CREATE INDEX IF NOT EXISTS idx_posts_pushes ON posts(pushes DESC);
CREATE INDEX IF NOT EXISTS idx_posts_score ON posts(latest_score DESC);
CREATE INDEX IF NOT EXISTS idx_posts_fts ON posts
    USING GIN (to_tsvector('simple', title || ' ' || COALESCE(content, '')));

CREATE TABLE IF NOT EXISTS search_queries (
    id BIGSERIAL PRIMARY KEY,
    keyword VARCHAR(200) NOT NULL,
    forum_code VARCHAR(20) NOT NULL,
    board_code VARCHAR(50) NOT NULL,
    operators JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    use_count INTEGER NOT NULL DEFAULT 0,
    total_posts_found INTEGER NOT NULL DEFAULT 0,
    passed_posts INTEGER NOT NULL DEFAULT 0,
    hit_rate NUMERIC(5,2),
    avg_score NUMERIC(5,2),
    peak_post_count INTEGER NOT NULL DEFAULT 0,
    is_priority BOOLEAN NOT NULL DEFAULT false,
    needs_optimization BOOLEAN NOT NULL DEFAULT false,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    manual_override BOOLEAN NOT NULL DEFAULT false,
    override_reason TEXT,
    override_at TIMESTAMPTZ,
    override_by VARCHAR(50),
    parent_query_id BIGINT,
    optimization_note TEXT,
    UNIQUE (keyword, forum_code, board_code)
);

CREATE TABLE IF NOT EXISTS crawl_log (
    id BIGSERIAL PRIMARY KEY,
    forum_id INTEGER REFERENCES forums(id),
    tool_name VARCHAR(50) NOT NULL,
    query_keyword VARCHAR(255),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    posts_fetched INTEGER NOT NULL DEFAULT 0,
    posts_new INTEGER NOT NULL DEFAULT 0,
    error_msg TEXT
);

CREATE TABLE IF NOT EXISTS system_notifications (
    id BIGSERIAL PRIMARY KEY,
    notification_type VARCHAR(50) NOT NULL,
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    scope JSONB,
    email_sent BOOLEAN NOT NULL DEFAULT false,
    email_sent_at TIMESTAMPTZ,
    email_to VARCHAR(200),
    acknowledged BOOLEAN NOT NULL DEFAULT false,
    acknowledged_at TIMESTAMPTZ,
    next_review_at TIMESTAMPTZ
);
