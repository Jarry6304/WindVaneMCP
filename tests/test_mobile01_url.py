"""Unit tests for mobile01_search URL construction and result parsing."""

import pytest
from bs4 import BeautifulSoup

from wind_vane.toolkits.crawlers.mobile01_search import _build_search_url, _parse_result

MOBILE01_BASE = "https://www.mobile01.com"


# ── _build_search_url ─────────────────────────────────────────────────────────

def test_no_board_plain_keyword():
    url = _build_search_url("日本代購")
    assert url.startswith(MOBILE01_BASE + "/googlesearch.php?q=")
    assert "site:mobile01" not in url
    assert " " not in url  # encoded


def test_board_scoped_includes_site_operator():
    url = _build_search_url("彩妝", fid="371")
    assert "f%3D371" in url or "f=371" in url or "371" in url
    assert "site%3Amobile01" in url or "site:mobile01" in url


def test_keyword_with_spaces_encoded():
    url = _build_search_url("日本 化妝品")
    assert " " not in url


def test_keyword_with_special_chars_encoded():
    url = _build_search_url("Switch 2 代購")
    assert " " not in url


# ── _parse_result ─────────────────────────────────────────────────────────────

def _soup(html: str):
    s = BeautifulSoup(html, "html.parser")
    return s.select_one("div")


def test_parse_h3_a_structure():
    html = """<div class="search-result-item">
      <h3><a href="/topiclist.php?f=371&t=1">彩妝好物分享</a></h3>
      <p class="snippet">日本帶回的彩妝</p>
    </div>"""
    result = _parse_result(_soup(html))
    assert result is not None
    assert result["title"] == "彩妝好物分享"
    assert "mobile01" in result["url"]
    assert "日本" in result["content"]


def test_parse_absolute_url_unchanged():
    html = """<div><h3><a href="https://www.mobile01.com/topicdetail.php?f=1&t=99">Title</a></h3></div>"""
    result = _parse_result(_soup(html))
    assert result is not None
    assert result["url"].startswith("https://www.mobile01.com")


def test_parse_no_anchor_returns_none():
    html = """<div class="search-result-item"><p>No link here</p></div>"""
    result = _parse_result(_soup(html))
    assert result is None


def test_parse_hash_href_returns_none():
    html = """<div><h3><a href="#">Skip nav</a></h3></div>"""
    result = _parse_result(_soup(html))
    assert result is None


def test_parse_no_snippet_gives_empty_content():
    html = """<div><h3><a href="/topiclist.php?t=5">Title Only</a></h3></div>"""
    result = _parse_result(_soup(html))
    assert result is not None
    assert result["content"] == ""
