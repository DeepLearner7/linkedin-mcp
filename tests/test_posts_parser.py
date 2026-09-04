"""
Unit tests for LinkedIn post search parsing and count extraction.
"""

import urllib.parse
from bs4 import BeautifulSoup
from linkedin_mcp.actions.posts import _parse_count


def test_parse_count():
    assert _parse_count("1,245 reactions") == 1245
    assert _parse_count("45 comments") == 45
    assert _parse_count("1 reaction") == 1
    assert _parse_count("0 comments") == 0
    assert _parse_count("") == 0
    assert _parse_count(None) == 0
    assert _parse_count("350") == 350


def test_url_encoding_for_search():
    keywords = "Senior Data Engineer Pune"
    encoded_query = urllib.parse.quote_plus(keywords)
    url = f"https://www.linkedin.com/search/results/content/?keywords={encoded_query}"
    
    sort_by = "date_posted"
    if sort_by == "date_posted":
        url += "&sortBy=%22date_posted%22"
        
    date_posted = "past-month"
    if date_posted in ["past-24h", "past-week", "past-month"]:
        url += f"&datePosted=%22{date_posted}%22"

    assert "sortBy=%22date_posted%22" in url
    assert "datePosted=%22past-month%22" in url
    assert '"' not in url  # Raw quotes must NOT be present in URL


def test_card_structure_parsing():
    mock_html = """
    <div componentkey="update-card-test123" role="listitem">
        <div class="header">
            <h2><span>Feed post</span></h2>
            <a href="https://www.linkedin.com/in/sample-author?tracking=1">
                Sample Author • 1st
            </a>
            <p>Principal Data Architect @ Global Tech</p>
            <p>2d •</p>
            <button>Follow</button>
        </div>
        <div class="feed-shared-update-v2__description">
            We are actively hiring a Senior Data Engineer in Pune!
            Requirements: PySpark, AWS Glue, Snowflake, and SQL.
        </div>
        <div class="social-counts">
            <a class="social-details-social-counts__reactions-count">120 reactions</a>
            <button class="social-details-social-counts__comments">15 comments</button>
        </div>
    </div>
    """
    soup = BeautifulSoup(mock_html, "html.parser")
    cards = soup.select(
        "div[componentkey*='update-card'], "
        "div[role='listitem'][componentkey*='update'], "
        "div.feed-shared-update-v2"
    )
    assert len(cards) == 1
    card = cards[0]

    # Author
    author_a = card.find("a", href=lambda h: h and "/in/" in h)
    assert author_a is not None
    assert "https://www.linkedin.com/in/sample-author" in author_a["href"]

    # Text
    desc = card.select_one(".feed-shared-update-v2__description")
    assert desc is not None
    assert "Senior Data Engineer in Pune" in desc.get_text()

    # Reactions
    r_tag = card.select_one(".social-details-social-counts__reactions-count")
    assert _parse_count(r_tag.get_text()) == 120

    # Comments
    c_tag = card.select_one(".social-details-social-counts__comments")
    assert _parse_count(c_tag.get_text()) == 15
