"""Commonize package for generating common size financial statements."""
from .common_size import (
    CommonSizeLine,
    StatementNotAvailableError,
    build_balance_sheet,
    build_income_statement,
)
from .cli import main as cli_main
from .sec_client import (
    SECClientError,
    fetch_company_facts,
    fetch_ticker_map,
    resolve_cik,
)

__all__ = [
    "CommonSizeLine",
    "StatementNotAvailableError",
    "SECClientError",
    "build_balance_sheet",
    "build_income_statement",
    "cli_main",
    "fetch_company_facts",
    "fetch_ticker_map",
    "resolve_cik",
]
