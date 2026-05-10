import json
import logging
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

logger = logging.getLogger(__name__)

_SUMMARIZE_PROMPT = """Summarize this web article for financial research.

Preserve exactly:
- All financial figures (revenue, earnings, price targets, ratings, dates)
- Business events (earnings beats/misses, M&A, guidance changes, regulatory actions)
- Analyst opinions and their stated sources
- Macro signals

Remove: navigation menus, ads, boilerplate, author bios, related-article links.

Keep under {word_limit} words. Never fabricate data or URLs.

Article:
{content}"""


class TavilyExtractSummarizer(AgentMiddleware):
    def __init__(self, model, char_threshold: int = 1000, word_limit: int = 500):
        super().__init__()
        self.model = model
        self.char_threshold = char_threshold
        self.word_limit = word_limit

    async def awrap_tool_call(self, request, handler):
        result = await handler(request)

        if request.tool_call.get("name") != "tavily_extract":
            return result

        if not isinstance(result, ToolMessage):
            return result

        try:
            data = json.loads(result.content)
        except (json.JSONDecodeError, TypeError):
            return result

        for article in data.get("results", []):
            raw = article.get("raw_content") or ""
            if len(raw) <= self.char_threshold:
                continue
            try:
                article["raw_content"] = await self._summarize(raw)
            except Exception:
                logger.warning(
                    "TavilyExtractSummarizer: failed to summarize %s",
                    article.get("url"),
                    exc_info=True,
                )

        return ToolMessage(
            content=json.dumps(data),
            tool_call_id=result.tool_call_id,
            name=result.name,
        )

    async def _summarize(self, content: str) -> str:
        response = await self.model.ainvoke(_SUMMARIZE_PROMPT.format(content=content, word_limit=self.word_limit))
        return response.content
