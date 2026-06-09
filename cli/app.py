"""Grove TUI - a Claude Code-style terminal client for the Grove research backend."""
import httpx
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, Markdown

from cli.client import GroveClient
from cli.commands import SUBAGENT_NAMES, parse_input
from cli.widgets import ActivityItem, ActivityLog


class GroveApp(App):
    """Split-panel terminal client: activity sidebar + streaming report pane + input bar."""

    CSS_PATH = "styles.tcss"
    TITLE = "Grove"

    def __init__(self) -> None:
        super().__init__()
        self._client = GroveClient()
        self._items_by_id: dict[str, ActivityItem] = {}

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="body"):
            yield ActivityLog(id="activity")
            with Vertical(id="main"):
                yield Markdown(id="report")
        yield Input(placeholder="Ask a question, or /filings NVDA, /market_data NVDA, /news_macro NVDA", id="prompt")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#prompt", Input).focus()

    def on_input_submitted(self, message: Input.Submitted) -> None:
        text = message.value.strip()
        if not text:
            return
        prompt = self.query_one("#prompt", Input)
        prompt.value = ""
        self.run_query(text)

    @work(exclusive=True)
    async def run_query(self, text: str) -> None:
        prompt = self.query_one("#prompt", Input)
        activity = self.query_one(ActivityLog)
        report = self.query_one("#report", Markdown)

        prompt.disabled = True
        activity.reset()
        await report.update("")
        self._items_by_id = {}

        subagent_name, query = parse_input(text)
        try:
            if subagent_name is None:
                activity.add_note("routing query...")
                stream = self._client.stream_run(query)
            elif subagent_name in SUBAGENT_NAMES:
                stream = self._client.stream_subagent_run(subagent_name, query)
            else:
                activity.add_note(f"✗ Unknown command: /{subagent_name}")
                return

            async for event in stream:
                await self._apply_event(event, activity, report)
        except httpx.HTTPError as exc:
            activity.add_note(f"✗ Connection error: {exc}")
        finally:
            prompt.disabled = False
            prompt.focus()

    async def _apply_event(self, event: dict, activity: ActivityLog, report: Markdown) -> None:
        kind = event.get("event")
        data = event.get("data", {})

        if kind in ("subagent_started", "tool_started"):
            label = data.get("name") or data.get("tool")
            self._items_by_id[data["id"]] = activity.start_item(label)
        elif kind in ("subagent_completed", "tool_completed"):
            item = self._items_by_id.get(data["id"])
            if item is not None:
                item.mark_done(data["duration_s"])
        elif kind == "report_chunk":
            await report.append(data["text"])
        elif kind == "error":
            activity.add_note(f"✗ {data['message']}")
            for item in self._items_by_id.values():
                item.mark_interrupted()


def main() -> None:
    GroveApp().run()


if __name__ == "__main__":
    main()
