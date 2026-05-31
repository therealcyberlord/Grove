from evals.scorers.structure import score_structure


def test_no_checks_defined():
    result = score_structure("anything", [], [])
    assert result.value == 1.0
    assert "no checks" in result.comment


def test_required_section_present():
    response = "## Summary\nSome content here."
    result = score_structure(response, ["Summary"], [])
    assert result.value == 1.0


def test_required_section_missing():
    response = "## Summary\nSome content."
    result = score_structure(response, ["Risks"], [])
    assert result.value == 0.0
    assert "fail" in result.comment


def test_forbidden_section_absent():
    response = "## Financials\nNumbers here."
    result = score_structure(response, [], ["Disclaimer"])
    assert result.value == 1.0


def test_forbidden_section_present():
    response = "## Disclaimer\nNot financial advice."
    result = score_structure(response, [], ["Disclaimer"])
    assert result.value == 0.0
    assert "fail" in result.comment


def test_mixed_partial_score():
    # 2 required: one found, one missing → 1/2 = 0.5
    response = "## Summary\nContent."
    result = score_structure(response, ["Summary", "Risks"], [])
    assert result.value == 0.5


def test_case_insensitive_match():
    response = "## SUMMARY\nContent."
    result = score_structure(response, ["summary"], [])
    assert result.value == 1.0


def test_raw_text_does_not_match_required():
    # "Summary" appearing in body text should not count as a header
    response = "This is a summary of the company's performance."
    result = score_structure(response, ["Summary"], [])
    assert result.value == 0.0


def test_evaluation_name():
    result = score_structure("", [], [])
    assert result.name == "report_structure"
