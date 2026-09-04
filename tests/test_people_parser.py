"""
Unit tests for LinkedIn people search parsing and extraction.
"""

from bs4 import BeautifulSoup


def test_legacy_people_card_parsing():
    mock_html = """
    <div role="listitem">
        <div class="entity-result">
            <span class="entity-result__title-text">
                <a class="app-aware-link" href="https://www.linkedin.com/in/jane-doe?miniProfile=1">
                    Jane Doe
                </a>
            </span>
            <div class="entity-result__primary-subtitle">
                Senior Data Engineer @ Citi | PySpark | Databricks
            </div>
            <div class="entity-result__secondary-subtitle">
                Pune, Maharashtra, India
            </div>
        </div>
    </div>
    """
    soup = BeautifulSoup(mock_html, "html.parser")
    cards = soup.select("div[role='listitem'], div.entity-result")
    assert len(cards) >= 1
    card = cards[0]

    name_elem = card.select_one("span.entity-result__title-text a")
    headline_elem = card.select_one(".entity-result__primary-subtitle")
    loc_elem = card.select_one(".entity-result__secondary-subtitle")

    assert name_elem.get_text(strip=True) == "Jane Doe"
    assert "Senior Data Engineer" in headline_elem.get_text(strip=True)
    assert "Pune" in loc_elem.get_text(strip=True)


def test_modern_people_card_parsing():
    mock_html = """
    <div role="listitem" data-view-name="search-entity-result-universal-template">
        <a href="https://www.linkedin.com/in/john-smith"></a>
        <div>John Smith</div>
        <div>• 2nd</div>
        <div>Lead Cloud Architect @ Barclays</div>
        <div>Pune District, Maharashtra, India</div>
        <button>Connect</button>
    </div>
    """
    soup = BeautifulSoup(mock_html, "html.parser")
    card = soup.select_one("div[data-view-name='search-entity-result-universal-template']")
    assert card is not None

    ignore_tokens = {"is open to work", "status is offline", "status is online", "• 1st", "• 2nd", "• 3rd+"}
    raw_strings = [s.strip() for s in card.stripped_strings if s.strip()]
    deduped = [s for s in raw_strings if s.lower() not in ignore_tokens]

    assert deduped[0] == "John Smith"
    assert deduped[1] == "Lead Cloud Architect @ Barclays"
    assert "Pune" in deduped[2]
