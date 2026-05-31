from evals.scorers.routing import score_routing


def test_exact_match_single_subagent():
    result = score_routing(["tavily_news_search"], ["news_macro"])
    assert result.value == 1.0


def test_exact_match_all_subagents():
    tools = ["tavily_news_search", "yfinance_get_market_data", "fetch_and_index_filing"]
    result = score_routing(tools, ["news_macro", "market_data", "filings"])
    assert result.value == 1.0


def test_no_tools_run():
    result = score_routing([], ["news_macro"])
    assert result.value == 0.0
    assert "missing" in result.comment


def test_both_empty_returns_perfect_score():
    result = score_routing([], [])
    assert result.value == 1.0


def test_over_routing_penalized():
    # detected: news_macro + market_data, expected: news_macro → Jaccard 1/2
    tools = ["tavily_news_search", "yfinance_get_market_data"]
    result = score_routing(tools, ["news_macro"])
    assert result.value == 0.5
    assert "extra" in result.comment


def test_under_routing_penalized():
    # detected: news_macro, expected: news_macro + market_data → Jaccard 1/2
    result = score_routing(["tavily_news_search"], ["news_macro", "market_data"])
    assert result.value == 0.5
    assert "missing" in result.comment


def test_tool_fingerprinting_filings():
    result = score_routing(["pageindex_get_page_content", "pageindex_get_structure"], ["filings"])
    assert result.value == 1.0


def test_unknown_tool_names_ignored():
    # Unknown tool names should not map to any subagent
    result = score_routing(["some_unknown_tool"], ["news_macro"])
    assert result.value == 0.0


def test_comment_omits_missing_extra_on_perfect_match():
    result = score_routing(["tavily_news_search"], ["news_macro"])
    assert "missing" not in result.comment
    assert "extra" not in result.comment


def test_evaluation_name():
    result = score_routing([], [])
    assert result.name == "subagent_routing"
