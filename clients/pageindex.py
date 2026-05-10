from functools import lru_cache
from pathlib import Path

from lib.PageIndex.pageindex import PageIndexClient

_WORKSPACE = Path(__file__).parent.parent / "workspace"


@lru_cache(maxsize=1)
def get_pageindex_client() -> PageIndexClient:
    _WORKSPACE.mkdir(exist_ok=True)
    return PageIndexClient(workspace=_WORKSPACE)
