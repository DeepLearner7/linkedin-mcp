"""
Unit tests for LinkedIn Job Board URL building and HTML card parsing.
"""

from bs4 import BeautifulSoup
from linkedin_mcp.actions.jobs import build_jobs_search_url, parse_job_card


def test_build_jobs_search_url():
    url = build_jobs_search_url(
        keywords="Senior Data Engineer",
        location="Pune",
        sort_by="date_posted",
        date_posted="past-week",
        workplace_type="hybrid",
        experience_level="mid-senior",
        start=25,
    )
    assert "keywords=Senior+Data+Engineer" in url
    assert "location=Pune" in url
    assert "&sortBy=DD" in url
    assert "&f_TPR=r604800" in url
    assert "&f_WT=3" in url
    assert "&f_E=4" in url
    assert "&start=25" in url


def test_build_jobs_search_url_defaults():
    url = build_jobs_search_url(keywords="Python Developer")
    assert "keywords=Python+Developer" in url
    assert "location=Pune" in url
    assert "&sortBy=DD" in url
    assert "&f_TPR=r2592000" in url
    assert "&start=" not in url


def test_parse_job_card_success():
    mock_html = """
    <div class="job-card-container" data-job-id="1234567890">
        <div class="artdeco-entity-lockup__content">
            <a class="job-card-list__title--link" href="/jobs/view/1234567890/?refId=abc">
                <span aria-hidden="true">
                    <strong>Senior Data Engineer</strong>
                </span>
                <span class="visually-hidden">Senior Data Engineer with verification</span>
            </a>
            <div class="artdeco-entity-lockup__subtitle">
                <span>Google</span>
            </div>
            <div class="artdeco-entity-lockup__caption">
                <ul class="job-card-container__metadata-wrapper">
                    <li>Pune Division, Maharashtra, India (Hybrid)</li>
                </ul>
            </div>
        </div>
        <div class="job-card-container__footer-wrapper">
            <span>2 hours ago</span>
            <span>Easy Apply</span>
        </div>
    </div>
    """
    soup = BeautifulSoup(mock_html, "html.parser")
    card = soup.select_one("div.job-card-container")
    parsed = parse_job_card(card)

    assert parsed is not None
    assert parsed["job_id"] == "1234567890"
    assert parsed["title"] == "Senior Data Engineer"
    assert parsed["company"] == "Google"
    assert "Pune" in parsed["location"]
    assert parsed["is_easy_apply"] is True
    assert parsed["job_url"] == "https://www.linkedin.com/jobs/view/1234567890/"


def test_parse_job_card_fallback_title():
    mock_html = """
    <li data-occludable-job-id="987654321">
        <a href="/jobs/view/987654321/">
            Lead Big Data Architect with verification
        </a>
        <div class="job-card-container__primary-description">Microsoft</div>
        <div class="job-card-container__metadata-wrapper">Remote, India</div>
    </li>
    """
    soup = BeautifulSoup(mock_html, "html.parser")
    card = soup.select_one("li")
    parsed = parse_job_card(card)

    assert parsed is not None
    assert parsed["job_id"] == "987654321"
    assert parsed["title"] == "Lead Big Data Architect"
    assert parsed["company"] == "Microsoft"
    assert parsed["location"] == "Remote, India"
    assert parsed["is_easy_apply"] is False
    assert parsed["job_url"] == "https://www.linkedin.com/jobs/view/987654321/"


def test_parse_job_card_invalid():
    mock_html = "<div><span>Random Banner</span></div>"
    soup = BeautifulSoup(mock_html, "html.parser")
    card = soup.select_one("div")
    parsed = parse_job_card(card)
    assert parsed is None
