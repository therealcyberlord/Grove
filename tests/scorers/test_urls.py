from evals.scorers.urls import score_no_fabricated_urls


def test_no_urls_in_report():
    result = score_no_fabricated_urls("No links here.", [])
    assert result.value == 1.0
    assert "no URLs" in result.comment


def test_all_urls_verified():
    report = "See https://example.com for details."
    result = score_no_fabricated_urls(report, ["https://example.com"])
    assert result.value == 1.0
    assert "verified" in result.comment


def test_fabricated_url_fails():
    report = "See https://made-up.com for details."
    result = score_no_fabricated_urls(report, ["https://example.com"])
    assert result.value == 0.0
    assert "fabricated" in result.comment


def test_all_fabricated_fails():
    report = "https://a.com and https://b.com"
    result = score_no_fabricated_urls(report, [])
    assert result.value == 0.0


def test_subset_of_tool_urls_used_passes():
    # Report only cites one of several tool URLs - still valid
    report = "See https://a.com"
    result = score_no_fabricated_urls(report, ["https://a.com", "https://b.com"])
    assert result.value == 1.0


def test_markdown_link_url_extracted():
    report = "Details [here](https://reuters.com/article/123)"
    result = score_no_fabricated_urls(report, ["https://reuters.com/article/123"])
    assert result.value == 1.0


def test_multiple_urls_one_fabricated():
    report = "https://real.com and https://fake.com"
    result = score_no_fabricated_urls(report, ["https://real.com"])
    assert result.value == 0.0
    assert "https://fake.com" in result.comment


def test_evaluation_name():
    result = score_no_fabricated_urls("no links", [])
    assert result.name == "no_fabricated_urls"
