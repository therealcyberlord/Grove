"""Activity sidebar widgets for the Grove TUI - track subagent/tool progress lines."""
from textual.containers import VerticalScroll
from textual.widgets import Static

_ICONS = {"running": "◐", "done": "✓", "error": "✗"}


class ActivityItem(Static):
    """A single activity line: a label with a status icon and elapsed time once known."""

    def __init__(self, label: str) -> None:
        super().__init__()
        self._label = label
        self._status = "running"
        self._elapsed: float | None = None
        self._refresh_content()

    def mark_done(self, elapsed: float) -> None:
        self._status = "done"
        self._elapsed = elapsed
        self._refresh_content()

    def mark_interrupted(self) -> None:
        if self._status == "running":
            self._status = "error"
            self._refresh_content()

    def _refresh_content(self) -> None:
        icon = _ICONS[self._status]
        suffix = f" ({self._elapsed:.1f}s)" if self._elapsed is not None else "..."
        self.update(f"{icon} {self._label}{suffix}")


class ActivityLog(VerticalScroll):
    """Scrolling list of activity lines for the current run."""

    def reset(self) -> None:
        self.remove_children()

    def add_note(self, text: str) -> None:
        self.mount(Static(text))

    def start_item(self, label: str) -> ActivityItem:
        item = ActivityItem(label)
        self.mount(item)
        item.scroll_visible()
        return item
