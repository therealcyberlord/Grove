from textual import events
from textual.containers import VerticalScroll
from textual.timer import Timer
from textual.widgets import Input, Static

_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

_COMMANDS = [
    ("/news_macro", "news & sentiment"),
    ("/market_data", "financials & metrics"),
    ("/filings", "10-K SEC analysis"),
]


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


class CommandSuggestions(Static):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._selected = 0
        self._filtered: list[tuple[str, str]] = []
        self.display = False

    def _render_list(self) -> str:
        lines = []
        for i, (cmd, desc) in enumerate(self._filtered):
            if i == self._selected:
                lines.append(f"[bold #81c784 on #2a3d26] {cmd}  [#6a9f6a on #2a3d26]{desc}[/]")
            else:
                lines.append(f"[bold #81c784] {cmd}[/]  [#6a9f6a]{desc}[/]")
        return "\n".join(lines)

    def show_for(self, prefix: str) -> None:
        self._filtered = [(c, d) for c, d in _COMMANDS if c.startswith(prefix)]
        if not self._filtered:
            self.display = False
            return
        self._selected = 0
        self.update(self._render_list())
        self.display = True

    def hide(self) -> None:
        self.display = False

    def move_up(self) -> None:
        if not self._filtered:
            return
        self._selected = max(0, self._selected - 1)
        self.update(self._render_list())

    def move_down(self) -> None:
        if not self._filtered:
            return
        self._selected = min(len(self._filtered) - 1, self._selected + 1)
        self.update(self._render_list())

    def selected_command(self) -> str:
        if self._filtered and 0 <= self._selected < len(self._filtered):
            return self._filtered[self._selected][0]
        return ""


class CommandInput(Input):
    def _on_key(self, event: events.Key) -> None:
        suggestions = self.app.query_one("#command-suggestions", CommandSuggestions)
        if suggestions.display:
            if event.key == "up":
                suggestions.move_up()
                event.stop()
                return
            elif event.key == "down":
                suggestions.move_down()
                event.stop()
                return
            elif event.key in ("enter", "tab"):
                cmd = suggestions.selected_command()
                if cmd:
                    self.value = cmd + " "
                    self.cursor_position = len(self.value)
                suggestions.hide()
                event.prevent_default()
                event.stop()
                return
            elif event.key == "escape":
                suggestions.hide()
                event.stop()
                return
        super()._on_key(event)
