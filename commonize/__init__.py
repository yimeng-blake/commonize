"""Commonize package for generating common size financial statements."""
from .common_size import (
    CommonSizeLine,
    StatementNotAvailableError,
    build_balance_sheet,
    build_income_statement,
)
from .cli import main as cli_main
from .web import create_app
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

__all__ = [
    "CommonSizeLine",
    "StatementNotAvailableError",
    "SECClientError",
    "build_balance_sheet",
    "build_income_statement",
    "cli_main",
    "create_app",
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
