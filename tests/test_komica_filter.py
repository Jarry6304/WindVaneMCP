"""Unit tests for Komica keyword filtering helpers."""

import pytest
from bs4 import BeautifulSoup

from wind_vane.toolkits.crawlers.komica_search import _extract_thread, _matches_keyword


# ── _matches_keyword ──────────────────────────────────────────────────────────

def test_matches_in_title():
    assert _matches_keyword("模型公仔特賣", "", "模型") is True


def test_matches_in_content():
    assert _matches_keyword("今日新貨", "收到一批模型公仔", "模型") is True


def test_no_match():
    assert _matches_keyword("今天吃什麼", "炒飯很好吃", "模型") is False


def test_case_insensitive():
    assert _matches_keyword("beyblade burst", "", "Beyblade") is True


def test_empty_strings():
    assert _matches_keyword("", "", "模型") is False


# ── _extract_thread ───────────────────────────────────────────────────────────

def _parse_thread(html: str):
    soup = BeautifulSoup(html, "html.parser")
    return _extract_thread(soup.select_one("div.thread"))


def test_extract_standard_thread():
    html = """
    <div class="thread">
      <div class="title"><a href="/00/res/123.html">模型公仔開箱</a></div>
      <blockquote>超讚的模型</blockquote>
    </div>
    """
    result = _parse_thread(html)
    assert result is not None
    assert result["title"] == "模型公仔開箱"
    assert "komica.org" in result["url"]
    assert "超讚" in result["content"]


def test_extract_absolute_url_kept():
    html = """
    <div class="thread">
      <div class="title"><a href="https://www.komica.org/00/res/456.html">Title</a></div>
    </div>
    """
    result = _parse_thread(html)
    assert result is not None
    assert result["url"].startswith("https://www.komica.org")


def test_extract_no_link_returns_none():
    html = """
    <div class="thread">
      <div class="title">No link here</div>
    </div>
    """
    result = _parse_thread(html)
    assert result is None


def test_extract_empty_href_returns_none():
    html = """
    <div class="thread">
      <div class="title"><a href="">Empty href</a></div>
    </div>
    """
    result = _parse_thread(html)
    assert result is None


def test_extract_no_content_gives_empty_string():
    html = """
    <div class="thread">
      <div class="title"><a href="/00/res/789.html">Title Only</a></div>
    </div>
    """
    result = _parse_thread(html)
    assert result is not None
    assert result["content"] == ""
