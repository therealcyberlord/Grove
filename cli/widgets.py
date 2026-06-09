"""Activity sidebar widgets for the Grove TUI - track subagent/tool progress lines."""
from textual.containers import VerticalScroll
from textual.widgets import Static


class ActivityItem(Static):
    """A single activity line with a label."""

    def __init__(self, label: str, classes: str = "") -> None:
        super().__init__(label, classes=classes)

    def mark_done(self, label: str) -> None:
        self.update(label)


class ActivityLog(VerticalScroll):
    """Scrolling list of activity lines for the current run."""

    def clear_items(self) -> None:
        self.remove_children()

    def add_note(self, text: str) -> None:
        self.mount(Static(text))

    def start_item(self, label: str) -> ActivityItem:
        item = ActivityItem(label)
        self.mount(item)
        item.scroll_visible()
        return item

    def start_nested_item(self, label: str) -> ActivityItem:
        item = ActivityItem(f"  {label}", classes="nested")
        self.mount(item)
        return item
