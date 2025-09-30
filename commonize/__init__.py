"""Commonize package for generating common size financial statements."""
from typing import TYPE_CHECKING, Any
from .common_size import (
    CommonSizeLine,
    StatementNotAvailableError,
    build_balance_sheet,
    build_income_statement,
)
from .cli import main as cli_main
from .industry_cache import IndustryBenchmark, load_benchmark, store_benchmark
from .sec_client import (
    SECClientError,
    IndustryInfo,
    fetch_company_facts,
    fetch_peer_company_facts,
    fetch_ticker_map,
    find_industry_peers,
    get_company_industry,
    resolve_cik,
)

if TYPE_CHECKING:  # pragma: no cover - import for type hints only
    from .web import create_app as _create_app
    from .worker import main as _worker_main


def create_app(*args: Any, **kwargs: Any):  # pragma: no cover - thin wrapper
    from .web import create_app as _create_app

    return _create_app(*args, **kwargs)


def worker_main(*args: Any, **kwargs: Any) -> None:  # pragma: no cover - thin wrapper
    from .worker import main as _worker_main

    _worker_main(*args, **kwargs)

__all__ = [
    "CommonSizeLine",
    "StatementNotAvailableError",
    "SECClientError",
    "build_balance_sheet",
    "build_income_statement",
    "cli_main",
    "create_app",
    "worker_main",
    "IndustryBenchmark",
    "load_benchmark",
    "store_benchmark",
    "fetch_company_facts",
    "fetch_peer_company_facts",
    "fetch_ticker_map",
    "find_industry_peers",
    "get_company_industry",
    "IndustryInfo",
    "resolve_cik",
]
