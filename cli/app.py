from textual import events, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Footer, Input, Markdown, Static

from cli.client import GroveClient
from cli.commands import SUBAGENT_NAMES, parse_input
from cli.labels import subagent_label, tool_label
from cli.widgets import ActivityItem, ActivityLog, CommandInput, CommandSuggestions


_WELCOME_MD = """\
**Ready — 3 subagents available**

orchestrator → news\\_macro · market\\_data · filings

---

**Model:** DeepSeek V4 Pro (via OpenRouter) &nbsp;&nbsp; **Date:** {date}

---

**Try asking:**

- What is the sentiment for CELH?
- Give me a deep dive on NVDA
- Compare AAPL vs MSFT

Or target a subagent directly: `/news_macro` `/market_data` `/filings`
"""


class GroveApp(App):
    CSS_PATH = "styles.tcss"

    _items_by_id: dict[str, ActivityItem]
    _auto_scroll: bool
    _programmatic_scroll: bool
    _subagent_last_child: dict[str, ActivityItem]
    _thinking_item: ActivityItem | None

    def compose(self) -> ComposeResult:
        yield Static("[bold #81c784]⬡ Grove[/]  [#6a9f6a]Analyst's CLI[/]", id="app-header")
        with Horizontal(id="body"):
            yield ActivityLog(id="sidebar")
            with VerticalScroll(id="report-scroll"):
                yield Markdown(id="report")
        yield CommandSuggestions(id="command-suggestions")
        yield CommandInput(placeholder="Ask a question, or call a subagent with a ticker: /filings NVDA", id="prompt")
        yield Footer()

    async def on_mount(self) -> None:
        self._items_by_id = {}
        self._subagent_last_child = {}
        self._auto_scroll = True
        self._programmatic_scroll = False
        self._thinking_item = None
        await self._show_welcome()

    async def _show_welcome(self) -> None:
        from datetime import date
        activity = self.query_one("#sidebar", ActivityLog)
        activity.mount(Static("Subagents ready", classes="ready-heading"))
        for name in ("news_macro", "market_data", "filings"):
            activity.mount(Static(f"● {name}", classes="ready-item"))
        report = self.query_one("#report", Markdown)
        await report.update(_WELCOME_MD.format(date=date.today().isoformat()))

    def _dismiss_thinking(self) -> None:
        if self._thinking_item is not None:
            self._thinking_item.remove()
            self._thinking_item = None

    def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        if self._programmatic_scroll:
            return
        self._auto_scroll = False

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "prompt":
            return
        value = event.value
        suggestions = self.query_one("#command-suggestions", CommandSuggestions)
        if value.startswith("/") and " " not in value:
            suggestions.show_for(value)
        else:
            suggestions.hide()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        if not query:
            return
        event.input.clear()
        self.run_query(query)

    @work(exclusive=True)
    async def run_query(self, text: str) -> None:
        self._items_by_id = {}
        self._subagent_last_child = {}
        self._thinking_item = None
        self._auto_scroll = True
        report_scroll = self.query_one("#report-scroll", VerticalScroll)
        self._programmatic_scroll = True
        report_scroll.scroll_home(animate=False)
        self._programmatic_scroll = False

        subagent_name, query = parse_input(text)
        client = GroveClient()
        if subagent_name in SUBAGENT_NAMES:
            stream = client.stream_subagent_run(subagent_name, query)
        else:
            stream = client.stream_run(query)

        async for event in stream:
            await self._apply_event(event)

    async def _apply_event(self, event: dict) -> None:
        activity = self.query_one("#sidebar", ActivityLog)
        event_type = event["event"]

        if event_type == "run_started":
            activity.clear_items()
            report = self.query_one("#report", Markdown)
            await report.update("")
            self._thinking_item = activity.start_item("Thinking...")

        elif event_type == "subagent_started":
            self._dismiss_thinking()
            data = event["data"]
            label = subagent_label(data["name"])
            item = activity.start_item(f"{label}...")
            self._items_by_id[data["id"]] = item
            self._subagent_last_child[data["name"]] = item

        elif event_type == "tool_started":
            self._dismiss_thinking()
            data = event["data"]
            label = tool_label(data["tool"])
            display = f"{label}..."
            if "subagent" in data:
                last = self._subagent_last_child.get(data["subagent"])
                if last:
                    item = activity.insert_nested_after(display, after=last)
                else:
                    item = activity.start_nested_item(display)
                self._subagent_last_child[data["subagent"]] = item
            else:
                item = activity.start_item(display)
            self._items_by_id[data["id"]] = item

        elif event_type in ("subagent_completed", "tool_completed"):
            data = event["data"]
            item = self._items_by_id.pop(data["id"], None)
            if item:
                if "name" in data:
                    friendly = subagent_label(data["name"])
                else:
                    friendly = tool_label(data.get("tool", ""))
                item.mark_done(f"✓ {friendly} ({data['duration_s']}s)")

        elif event_type == "report_chunk":
            report = self.query_one("#report", Markdown)
            await report.append(event["data"]["text"])
            if self._auto_scroll:
                report_scroll = self.query_one("#report-scroll", VerticalScroll)
                self._programmatic_scroll = True
                report_scroll.scroll_end(animate=False)
                self._programmatic_scroll = False

        elif event_type == "error":
            self._dismiss_thinking()
            for item in self._items_by_id.values():
                item.mark_done("✗ interrupted")
            self._items_by_id = {}

        elif event_type == "run_completed":
            pass


def main() -> None:
    GroveApp().run()


if __name__ == "__main__":
    main()
