"""Unit tests for bahamut_search scope validation and URL construction."""

import pytest

from wind_vane.toolkits.crawlers.bahamut_search import _build_search_url

BAHAMUT_BASE = "https://forum.gamer.com.tw"


def test_board_scope_url_uses_bsn():
    url = _build_search_url("board", "2696", "戰鬥陀螺")
    assert "B.php" in url
    assert "bsn=2696" in url
    assert "qt=2" in url


def test_global_scope_url_uses_g2():
    url = _build_search_url("global", None, "代購")
    assert "G2.php" in url
    assert "qt=2" in url
    assert "bsn" not in url


def test_keyword_is_url_encoded():
    url = _build_search_url("board", "1647", "神奇寶貝 Switch")
    # spaces must be encoded
    assert " " not in url


def test_global_scope_encodes_keyword():
    url = _build_search_url("global", None, "Pokemon カード")
    assert " " not in url
    assert "%" in url  # URL-encoded


@pytest.mark.asyncio
async def test_board_scope_without_board_code_raises():
    """scope='board' with no board_code must raise immediately (no DB needed)."""
    from unittest.mock import AsyncMock
    from wind_vane.toolkits.crawlers.bahamut_search import bahamut_search

    mock_session = AsyncMock()
    with pytest.raises(ValueError, match="board_code is required"):
        await bahamut_search(mock_session, keyword="test", scope="board", board_code=None)
