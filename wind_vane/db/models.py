from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, VARCHAR
from sqlalchemy.dialects.postgresql import TIMESTAMP as _PGTIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# TIMESTAMPTZ: PostgreSQL TIMESTAMP WITH TIME ZONE
# Defined here so the test conftest can patch it with sqlalchemy.DateTime for SQLite


class TIMESTAMPTZ(_PGTIMESTAMP):
    """TIMESTAMP WITH TIME ZONE — subclass so SQLite conftest can monkey-patch."""

    def __init__(self, *args, **kwargs):
        super().__init__(timezone=True)


class Base(DeclarativeBase):
    pass


class Forum(Base):
    __tablename__ = "forums"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(VARCHAR(20), unique=True, nullable=False)
    name_zh: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)
    base_url: Mapped[str] = mapped_column(VARCHAR(255), nullable=False)
    requires_js: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rate_limit_per_min: Mapped[int] = mapped_column(Integer, nullable=False)
    search_url_template: Mapped[str | None] = mapped_column(VARCHAR(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    boards: Mapped[list["ForumBoard"]] = relationship(back_populates="forum")
    operators: Mapped[list["ForumSearchOperator"]] = relationship(back_populates="forum")
    posts: Mapped[list["Post"]] = relationship(back_populates="forum")
    crawl_logs: Mapped[list["CrawlLog"]] = relationship(back_populates="forum")


class ForumBoard(Base):
    __tablename__ = "forum_boards"
    __table_args__ = (UniqueConstraint("forum_id", "board_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    forum_id: Mapped[int] = mapped_column(ForeignKey("forums.id"), nullable=False)
    board_code: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)
    name_zh: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    native_id: Mapped[str | None] = mapped_column(VARCHAR(50))
    url_path: Mapped[str | None] = mapped_column(VARCHAR(255))
    value_score: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    forum: Mapped["Forum"] = relationship(back_populates="boards")
    posts: Mapped[list["Post"]] = relationship(back_populates="board")
    affinities: Mapped[list["BoardKeywordAffinity"]] = relationship(back_populates="board")


class Keyword(Base):
    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    tier: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)
    aliases: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    weight: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    affinities: Mapped[list["BoardKeywordAffinity"]] = relationship(back_populates="keyword")


class ForumSearchOperator(Base):
    __tablename__ = "forum_search_operators"
    __table_args__ = (UniqueConstraint("forum_id", "operator"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    forum_id: Mapped[int] = mapped_column(ForeignKey("forums.id"), nullable=False)
    operator: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    syntax_template: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    value_type: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    forum: Mapped["Forum"] = relationship(back_populates="operators")


class BoardKeywordAffinity(Base):
    __tablename__ = "board_keyword_affinity"
    __table_args__ = (UniqueConstraint("board_id", "keyword_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    board_id: Mapped[int] = mapped_column(ForeignKey("forum_boards.id"), nullable=False)
    keyword_id: Mapped[int] = mapped_column(ForeignKey("keywords.id"), nullable=False)
    affinity_score: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    board: Mapped["ForumBoard"] = relationship(back_populates="affinities")
    keyword: Mapped["Keyword"] = relationship(back_populates="affinities")


class BlacklistPattern(Base):
    __tablename__ = "blacklist_patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pattern: Mapped[str] = mapped_column(VARCHAR(200), nullable=False)
    pattern_type: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    applies_to: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CommercialSignal(Base):
    __tablename__ = "commercial_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_text: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    forum_id: Mapped[int] = mapped_column(ForeignKey("forums.id"), nullable=False)
    board_id: Mapped[int | None] = mapped_column(ForeignKey("forum_boards.id"))
    native_post_id: Mapped[str | None] = mapped_column(VARCHAR(100))
    url: Mapped[str] = mapped_column(VARCHAR(500), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(VARCHAR(500), nullable=False)
    author: Mapped[str | None] = mapped_column(VARCHAR(100))
    content: Mapped[str | None] = mapped_column(Text)
    posted_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    pushes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    boos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comment_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pushes_history: Mapped[str | None] = mapped_column(Text)
    pushes_history_dt: Mapped[str | None] = mapped_column(Text)
    latest_score: Mapped[int | None] = mapped_column(Integer)
    matched_keywords: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    first_crawled_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=func.now(), nullable=False
    )
    last_crawled_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=func.now(), nullable=False
    )
    crawl_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    forum: Mapped["Forum"] = relationship(back_populates="posts")
    board: Mapped["ForumBoard | None"] = relationship(back_populates="posts")


class SearchQuery(Base):
    __tablename__ = "search_queries"
    __table_args__ = (UniqueConstraint("keyword", "forum_code", "board_code"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(VARCHAR(200), nullable=False)
    forum_code: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    board_code: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)
    operators: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=func.now(), nullable=False
    )
    last_used_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=func.now(), nullable=False
    )
    use_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_posts_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passed_posts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hit_rate: Mapped[float | None] = mapped_column(Numeric(5, 2))
    avg_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    peak_post_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_priority: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    needs_optimization: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(VARCHAR(20), default="active", nullable=False)
    manual_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    override_reason: Mapped[str | None] = mapped_column(Text)
    override_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    override_by: Mapped[str | None] = mapped_column(VARCHAR(50))
    parent_query_id: Mapped[int | None] = mapped_column(BigInteger)
    optimization_note: Mapped[str | None] = mapped_column(Text)


class CrawlLog(Base):
    __tablename__ = "crawl_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    forum_id: Mapped[int | None] = mapped_column(ForeignKey("forums.id"))
    tool_name: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)
    query_keyword: Mapped[str | None] = mapped_column(VARCHAR(255))
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    posts_fetched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    posts_new: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_msg: Mapped[str | None] = mapped_column(Text)

    forum: Mapped["Forum | None"] = relationship(back_populates="crawl_logs")


class SystemNotification(Base):
    __tablename__ = "system_notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    notification_type: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=func.now(), nullable=False
    )
    scope: Mapped[dict | None] = mapped_column(JSONB)
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_sent_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    email_to: Mapped[str | None] = mapped_column(VARCHAR(200))
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    next_review_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
