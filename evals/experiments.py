"""Eval runner using Langfuse native experiment API."""
import logging
from datetime import datetime

from langchain_core.callbacks import BaseCallbackHandler
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler

from agents.orchestrator import orchestrator
from clients.config import settings
from evals.dataset import eval_dataset, subagent_eval_dataset
from evals.scorers.llm_judge import score_helpfulness, score_subagent_quality
from evals.scorers.routing import score_routing
from evals.scorers.urls import URL_RE, score_no_fabricated_urls

logger = logging.getLogger(__name__)

dataset_name = "grove-orchestrator-v1"
subagent_dataset_name = "grove-subagent-v1"

_lf = Langfuse(
    public_key=settings.langfuse_public_key,
    secret_key=settings.langfuse_secret_key,
    host=settings.langfuse_base_url,
)


class ToolCapture(BaseCallbackHandler):
    def __init__(self) -> None:
        self.tool_names = set()
        self.tool_urls = set()

    def on_tool_start(self, serialized: dict, input_str: str, **_) -> None:
        if name := serialized.get("name"):
            self.tool_names.add(name)

    def on_tool_end(self, output: str, **_) -> None:
        text = output if isinstance(output, str) else str(output)
        for url in URL_RE.findall(text):
            self.tool_urls.add(url)


def sync_dataset() -> None:
    try:
        _lf.create_dataset(name=dataset_name, description="Grove orchestrator end-to-end eval suite")
    except Exception:
        pass

    for case in eval_dataset:
        _lf.create_dataset_item(
            id=f"orch_{case.name}",
            dataset_name=dataset_name,
            input={"query": case.query},
            metadata={"routing_type": case.routing_type, "expected_subagents": case.expected_subagents},
        )


async def _task(*, item, **_):
    query = item.input["query"]
    capture = ToolCapture()
    lf_handler = LangfuseCallbackHandler()

    result = await orchestrator.with_config({"callbacks": [lf_handler, capture]}).ainvoke(
        {"messages": [{"role": "user", "content": query}]}
    )
    messages = result.get("messages", [])
    return {
        "report": messages[-1].content if messages else "",
        "tool_names": sorted(capture.tool_names),
        "tool_urls": sorted(capture.tool_urls),
    }


def _routing_evaluator(*, output, metadata, **_):
    return score_routing(output.get("tool_names", []), metadata["expected_subagents"])


def _urls_evaluator(*, output, **_):
    return score_no_fabricated_urls(output.get("report", ""), output.get("tool_urls", []))


def run_experiment(routing_types: list[str] | None = None) -> None:
    sync_dataset()

    items = _lf.get_dataset(dataset_name).items
    if routing_types:
        items = [i for i in items if i.metadata.get("routing_type") in routing_types]

    run_name = f"orchestrator-{datetime.now().strftime('%Y%m%d-%H%M')}"
    logger.info("Run: %s  |  %d case(s)", run_name, len(items))

    result = _lf.run_experiment(
        name="grove-orchestrator",
        run_name=run_name,
        data=items,
        task=_task,
        evaluators=[_routing_evaluator, _urls_evaluator, score_helpfulness],
        max_concurrency=2,
    )
    logger.info(result.format())


def sync_subagent_dataset() -> None:
    try:
        _lf.create_dataset(name=subagent_dataset_name, description="Grove subagent isolation eval suite - one subagent at a time")
    except Exception:
        pass

    for case in subagent_eval_dataset:
        _lf.create_dataset_item(
            id=f"sub_{case.name}",
            dataset_name=subagent_dataset_name,
            input={"subagent": case.subagent, "ticker": case.ticker, "query": case.query},
        )


async def _subagent_task(*, item, **_):
    from agents.subagents.news_macro.agent import news_macro
    from agents.subagents.market_data.agent import market_data
    from agents.subagents.filings.agent import filings

    runnables = {
        "news_macro": news_macro["runnable"],
        "market_data": market_data["runnable"],
        "filings": filings["runnable"],
    }

    subagent_name = item.input["subagent"]
    ticker = item.input["ticker"]
    query = item.input["query"]
    capture = ToolCapture()

    result = await runnables[subagent_name].with_config({"callbacks": [capture]}).ainvoke(
        {"messages": [{"role": "user", "content": f"Ticker: {ticker}\n{query}"}]}
    )
    messages = result.get("messages", [])
    return {
        "report": messages[-1].content if messages else "",
        "tool_urls": sorted(capture.tool_urls),
    }


def run_subagent_experiment(subagents: list[str] | None = None) -> None:
    sync_subagent_dataset()

    items = _lf.get_dataset(subagent_dataset_name).items
    if subagents:
        items = [i for i in items if i.input.get("subagent") in subagents]

    run_name = f"subagent-{datetime.now().strftime('%Y%m%d-%H%M')}"
    logger.info("Run: %s  |  %d case(s)", run_name, len(items))

    result = _lf.run_experiment(
        name="grove-subagent",
        run_name=run_name,
        data=items,
        task=_subagent_task,
        evaluators=[_urls_evaluator, score_subagent_quality],
        max_concurrency=2,
    )
    logger.info(result.format())


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if sys.argv[1:] and sys.argv[1] == "subagent":
        run_subagent_experiment(subagents=sys.argv[2:] or None)
    else:
        run_experiment(routing_types=sys.argv[1:] or None)
