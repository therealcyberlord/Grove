"""Slash-command parsing for the Grove TUI - mirrors Claude Code's /command syntax."""
from cli.labels import _SUBAGENT_LABELS

SUBAGENT_NAMES = tuple(_SUBAGENT_LABELS.keys())


def parse_input(text: str) -> tuple[str | None, str]:
    """Split user input into (subagent_name, query).

    Plain text -> (None, text), routed through the orchestrator.
    "/name rest" -> (name, rest), routed directly to that subagent.

    The returned name is not validated against SUBAGENT_NAMES here - the
    caller checks membership and surfaces unknown commands to the user.
    """
    if not text.startswith("/"):
        return None, text
    name, _, rest = text[1:].partition(" ")
    return name, rest.strip()
