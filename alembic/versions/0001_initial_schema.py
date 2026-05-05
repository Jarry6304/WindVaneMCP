"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-05 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "forums",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.VARCHAR(20), unique=True, nullable=False),
        sa.Column("name_zh", sa.VARCHAR(50), nullable=False),
        sa.Column("base_url", sa.VARCHAR(255), nullable=False),
        sa.Column("requires_js", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("rate_limit_per_min", sa.Integer(), nullable=False),
        sa.Column("search_url_template", sa.VARCHAR(500)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )

    op.create_table(
        "forum_boards",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("forum_id", sa.Integer(), sa.ForeignKey("forums.id"), nullable=False),
        sa.Column("board_code", sa.VARCHAR(50), nullable=False),
        sa.Column("name_zh", sa.VARCHAR(100), nullable=False),
        sa.Column("native_id", sa.VARCHAR(50)),
        sa.Column("url_path", sa.VARCHAR(255)),
        sa.Column("value_score", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("notes", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.UniqueConstraint("forum_id", "board_code"),
    )

    op.create_table(
        "keywords",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("keyword", sa.VARCHAR(100), nullable=False),
        sa.Column("tier", sa.Integer(), nullable=False),
        sa.Column("category", sa.VARCHAR(50), nullable=False),
        sa.Column("aliases", postgresql.ARRAY(sa.Text())),
        sa.Column("weight", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )

    op.create_table(
        "forum_search_operators",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("forum_id", sa.Integer(), sa.ForeignKey("forums.id"), nullable=False),
        sa.Column("operator", sa.VARCHAR(20), nullable=False),
        sa.Column("syntax_template", sa.VARCHAR(100), nullable=False),
        sa.Column("value_type", sa.VARCHAR(20), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.UniqueConstraint("forum_id", "operator"),
    )

    op.create_table(
        "board_keyword_affinity",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("board_id", sa.Integer(), sa.ForeignKey("forum_boards.id"), nullable=False),
        sa.Column("keyword_id", sa.Integer(), sa.ForeignKey("keywords.id"), nullable=False),
        sa.Column("affinity_score", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("notes", sa.Text()),
        sa.UniqueConstraint("board_id", "keyword_id"),
    )

    op.create_table(
        "blacklist_patterns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("pattern", sa.VARCHAR(200), nullable=False),
        sa.Column("pattern_type", sa.VARCHAR(20), nullable=False),
        sa.Column("applies_to", sa.VARCHAR(20), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )

    op.create_table(
        "commercial_signals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("signal_text", sa.VARCHAR(100), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False),
        sa.Column("category", sa.VARCHAR(50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )

    op.create_table(
        "posts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("forum_id", sa.Integer(), sa.ForeignKey("forums.id"), nullable=False),
        sa.Column("board_id", sa.Integer(), sa.ForeignKey("forum_boards.id")),
        sa.Column("native_post_id", sa.VARCHAR(100)),
        sa.Column("url", sa.VARCHAR(500), unique=True, nullable=False),
        sa.Column("title", sa.VARCHAR(500), nullable=False),
        sa.Column("author", sa.VARCHAR(100)),
        sa.Column("content", sa.Text()),
        sa.Column("posted_at", postgresql.TIMESTAMPTZ()),
        sa.Column("pushes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("boos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("comment_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pushes_history", sa.Text()),
        sa.Column("pushes_history_dt", sa.Text()),
        sa.Column("latest_score", sa.Integer()),
        sa.Column("matched_keywords", postgresql.ARRAY(sa.Text())),
        sa.Column("first_crawled_at", postgresql.TIMESTAMPTZ(), server_default=sa.func.now(), nullable=False),
        sa.Column("last_crawled_at", postgresql.TIMESTAMPTZ(), server_default=sa.func.now(), nullable=False),
        sa.Column("crawl_count", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("idx_posts_forum_board_posted", "posts", ["forum_id", "board_id", sa.text("posted_at DESC")])
    op.create_index("idx_posts_last_crawled", "posts", ["last_crawled_at"])
    op.create_index("idx_posts_pushes", "posts", [sa.text("pushes DESC")])
    op.create_index("idx_posts_score", "posts", [sa.text("latest_score DESC")])
    op.execute(
        "CREATE INDEX idx_posts_fts ON posts USING GIN "
        "(to_tsvector('simple', title || ' ' || COALESCE(content, '')))"
    )

    op.create_table(
        "search_queries",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("keyword", sa.VARCHAR(200), nullable=False),
        sa.Column("forum_code", sa.VARCHAR(20), nullable=False),
        sa.Column("board_code", sa.VARCHAR(50), nullable=False),
        sa.Column("operators", postgresql.JSONB()),
        sa.Column("created_at", postgresql.TIMESTAMPTZ(), server_default=sa.func.now(), nullable=False),
        sa.Column("last_used_at", postgresql.TIMESTAMPTZ(), server_default=sa.func.now(), nullable=False),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_posts_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("passed_posts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hit_rate", sa.Numeric(5, 2)),
        sa.Column("avg_score", sa.Numeric(5, 2)),
        sa.Column("peak_post_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_priority", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("needs_optimization", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("status", sa.VARCHAR(20), nullable=False, server_default="active"),
        sa.Column("manual_override", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("override_reason", sa.Text()),
        sa.Column("override_at", postgresql.TIMESTAMPTZ()),
        sa.Column("override_by", sa.VARCHAR(50)),
        sa.Column("parent_query_id", sa.BigInteger()),
        sa.Column("optimization_note", sa.Text()),
        sa.UniqueConstraint("keyword", "forum_code", "board_code"),
    )

    op.create_table(
        "crawl_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("forum_id", sa.Integer(), sa.ForeignKey("forums.id")),
        sa.Column("tool_name", sa.VARCHAR(50), nullable=False),
        sa.Column("query_keyword", sa.VARCHAR(255)),
        sa.Column("started_at", postgresql.TIMESTAMPTZ(), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", postgresql.TIMESTAMPTZ()),
        sa.Column("posts_fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("posts_new", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_msg", sa.Text()),
    )

    op.create_table(
        "system_notifications",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("notification_type", sa.VARCHAR(50), nullable=False),
        sa.Column("triggered_at", postgresql.TIMESTAMPTZ(), server_default=sa.func.now(), nullable=False),
        sa.Column("scope", postgresql.JSONB()),
        sa.Column("email_sent", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("email_sent_at", postgresql.TIMESTAMPTZ()),
        sa.Column("email_to", sa.VARCHAR(200)),
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("acknowledged_at", postgresql.TIMESTAMPTZ()),
        sa.Column("next_review_at", postgresql.TIMESTAMPTZ()),
    )


def downgrade() -> None:
    op.drop_table("system_notifications")
    op.drop_table("crawl_log")
    op.drop_table("search_queries")
    op.execute("DROP INDEX IF EXISTS idx_posts_fts")
    op.drop_index("idx_posts_score", table_name="posts")
    op.drop_index("idx_posts_pushes", table_name="posts")
    op.drop_index("idx_posts_last_crawled", table_name="posts")
    op.drop_index("idx_posts_forum_board_posted", table_name="posts")
    op.drop_table("posts")
    op.drop_table("commercial_signals")
    op.drop_table("blacklist_patterns")
    op.drop_table("board_keyword_affinity")
    op.drop_table("forum_search_operators")
    op.drop_table("keywords")
    op.drop_table("forum_boards")
    op.drop_table("forums")
