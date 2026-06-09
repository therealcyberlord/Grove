from textual.containers import VerticalScroll
from textual.timer import Timer
from textual.widgets import Static

_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class ActivityItem(Static):
    def __init__(self, label: str, classes: str = "") -> None:
        super().__init__(classes=classes)
        self._label = label
        self._frame = 0
        self._timer: Timer | None = None

    def on_mount(self) -> None:
        self._timer = self.set_interval(0.1, self._tick)
        self._tick()

    def _tick(self) -> None:
        self.update(f"{_SPINNER_FRAMES[self._frame % 10]} {self._label}")
        self._frame += 1

    def mark_done(self, label: str) -> None:
        if self._timer:
            self._timer.stop()
            self._timer = None
        self.update(label)


class ActivityLog(VerticalScroll):
    def clear_items(self) -> None:
        self.remove_children()

    def start_item(self, label: str) -> ActivityItem:
        item = ActivityItem(label)
        self.mount(item)
        item.scroll_visible()
        return item

    def start_nested_item(self, label: str) -> ActivityItem:
        item = ActivityItem(label, classes="nested")
        self.mount(item)
        return item

    def insert_nested_after(self, label: str, after: ActivityItem) -> ActivityItem:
        item = ActivityItem(label, classes="nested")
        self.mount(item, after=after)
        return item
