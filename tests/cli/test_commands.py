"""Unit tests for slash-command parsing."""
from cli.commands import parse_input


def test_parse_input_returns_plain_query_for_text_without_slash():
    assert parse_input("What is the sentiment for CELH?") == (None, "What is the sentiment for CELH?")


def test_parse_input_splits_slash_command_into_name_and_query():
    assert parse_input("/filings NVDA") == ("filings", "NVDA")


def test_parse_input_handles_slash_command_with_multi_word_query():
    assert parse_input("/market_data compare NVDA and AMD") == ("market_data", "compare NVDA and AMD")


def test_parse_input_handles_slash_command_with_no_query():
    assert parse_input("/filings") == ("filings", "")


def test_parse_input_preserves_unknown_command_name_for_caller_to_validate():
    assert parse_input("/nonsense NVDA") == ("nonsense", "NVDA")
