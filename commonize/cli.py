"""Command line interface for generating common size statements."""
from __future__ import annotations

import argparse
import sys
from typing import Callable, Iterable, List

from . import common_size, sec_client

try:
    from tabulate import tabulate
except ImportError:  # pragma: no cover - fallback when tabulate not installed
    tabulate = None  # type: ignore


def _statement_builder(name: str) -> Callable[[dict, str], List[common_size.CommonSizeLine]]:
    if name == "income":
        return common_size.build_income_statement
    if name == "balance":
        return common_size.build_balance_sheet
    raise ValueError(f"Unsupported statement type '{name}'.")


def _render_table(lines: Iterable[common_size.CommonSizeLine]) -> str:
    rows = [line.as_row() for line in lines]
    headers = ["Line item", "Value (USD)", "Company common size", "Industry common size"]
    if tabulate:
        return tabulate(rows, headers=headers, tablefmt="github")
    # Simple fallback rendering
    column_widths = [max(len(str(row[i])) for row in rows + [headers]) for i in range(len(headers))]
    lines_out = [
        " | ".join(h.ljust(column_widths[idx]) for idx, h in enumerate(headers)),
        "-+-".join("-" * column_widths[idx] for idx in range(len(headers))),
    ]
    for row in rows:
        lines_out.append(
            " | ".join(str(cell).ljust(column_widths[idx]) for idx, cell in enumerate(row))
        )
    return "\n".join(lines_out)


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate common size financial statements from SEC data.")
    parser.add_argument("ticker", help="Ticker symbol or CIK of the company to analyze.")
    parser.add_argument(
        "--statement",
        choices=["income", "balance"],
        default="income",
        help="Which statement to generate (default: income).",
    )
    parser.add_argument(
        "--period",
        choices=["annual", "quarterly"],
        default="annual",
        help="Which reporting period to use (default: annual).",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force refresh of cached ticker metadata.",
    )
    parser.add_argument(
        "--industry-peers",
        type=int,
        default=0,
        help="Number of peer companies (same SIC) to include when computing industry averages.",
    )

    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        ticker_info = sec_client.resolve_cik(args.ticker, force_refresh=args.force_refresh)
        facts = sec_client.fetch_company_facts(ticker_info.cik)
        peer_facts = None
        if args.industry_peers > 0:
            _, _, peer_fact_list = sec_client.fetch_peer_company_facts(
                ticker_info.cik, max_companies=args.industry_peers
            )
            if peer_fact_list:
                peer_facts = peer_fact_list
        builder = _statement_builder(args.statement)
        if peer_facts:
            lines = builder(facts, period=args.period, peers=peer_facts)
        else:
            lines = builder(facts, period=args.period)

    except Exception as exc:  # pragma: no cover - CLI entry point
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Common size {args.statement} statement for {ticker_info.ticker} (CIK {ticker_info.cik})")
    print(_render_table(lines))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
