"""Unit tests for dcard_search helpers."""

import pytest
from bs4 import BeautifulSoup

from wind_vane.toolkits.crawlers.dcard_search import _build_query, _parse_google_results


# ── _build_query ──────────────────────────────────────────────────────────────

def test_no_board_uses_site_dcard():
    q = _build_query("代購", None)
    assert q.startswith("site:dcard.tw ")
    assert "代購" in q


def test_board_scope_uses_f_path():
    q = _build_query("美妝", "makeup")
    assert "site:dcard.tw/f/makeup" in q
    assert "美妝" in q


def test_site_operator_comes_first():
    q = _build_query("keyword", None)
    assert q.index("site:") < q.index("keyword")


# ── _parse_google_results ─────────────────────────────────────────────────────

_SAMPLE_HTML = """
<html><body>
  <div class="g">
    <h3>Dcard 美妝板 分享好物</h3>
    <a href="https://www.dcard.tw/f/makeup/p/12345">link</a>
    <div class="VwiC3b">日本帶回的好物推薦</div>
  </div>
  <div class="g">
    <h3>Other site article</h3>
    <a href="https://www.other.com/p/999">other</a>
  </div>
  <div class="g">
    <h3>另一個 Dcard 文</h3>
    <a href="https://www.dcard.tw/f/beauty/p/67890">link2</a>
  </div>
</body></html>
"""


def test_parse_only_dcard_urls():
    results = _parse_google_results(_SAMPLE_HTML, limit=10)
    for r in results:
        assert "dcard.tw" in r["url"]


def test_parse_extracts_title_and_snippet():
    results = _parse_google_results(_SAMPLE_HTML, limit=10)
    assert len(results) >= 1
    assert results[0]["title"] == "Dcard 美妝板 分享好物"
    assert "日本" in results[0]["content"]


def test_parse_limit_respected():
    results = _parse_google_results(_SAMPLE_HTML, limit=1)
    assert len(results) == 1


def test_parse_no_snippet_gives_empty_content():
    results = _parse_google_results(_SAMPLE_HTML, limit=10)
    # 3rd result has no snippet div
    r = next((r for r in results if "67890" in r["url"]), None)
    assert r is not None
    assert r["content"] == ""


def test_parse_empty_html_returns_empty():
    assert _parse_google_results("<html></html>", limit=10) == []
