"""Utilities for communicating with the SEC data APIs."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Optional

try:
    import requests
except ImportError:  # pragma: no cover - allows unit tests without requests
    requests = None  # type: ignore

_DEFAULT_USER_AGENT = os.environ.get(
    "COMMONIZE_USER_AGENT",
    "Commonize/0.1 (your_email@example.com)",
)

_TICKER_CACHE = Path(os.environ.get("COMMONIZE_CACHE", "./.commonize-cache"))
_TICKER_CACHE.mkdir(parents=True, exist_ok=True)
_TICKER_CACHE_FILE = _TICKER_CACHE / "ticker_cik_map.json"


class SECClientError(RuntimeError):
    """Raised when a request to the SEC API fails."""


@dataclass
class TickerInfo:
    ticker: str
    cik_str: str
    title: str

    @property
    def cik(self) -> str:
        return self.cik_str.zfill(10)


def _request_json(url: str, *, sleep: float = 0.2) -> dict:
    if requests is None:  # pragma: no cover - exercised when dependency missing
        raise ImportError("The 'requests' package is required to call the SEC API.")
    headers = {"User-Agent": _DEFAULT_USER_AGENT, "Accept-Encoding": "gzip, deflate"}
    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code != 200:
        raise SECClientError(f"SEC request failed with status {response.status_code}: {url}")
    if sleep:
        time.sleep(sleep)  # be kind to SEC infrastructure
    return response.json()


def _load_ticker_cache() -> Dict[str, TickerInfo]:
    if not _TICKER_CACHE_FILE.exists():
        return {}
    with _TICKER_CACHE_FILE.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return {k: TickerInfo(**v) for k, v in data.items()}


def _save_ticker_cache(data: Dict[str, TickerInfo]) -> None:
    serializable = {k: v.__dict__ for k, v in data.items()}
    with _TICKER_CACHE_FILE.open("w", encoding="utf-8") as fh:
        json.dump(serializable, fh)


def fetch_ticker_map(force_refresh: bool = False) -> Dict[str, TickerInfo]:
    """Return a mapping of ticker -> ticker information from the SEC."""
    cache = _load_ticker_cache()
    if cache and not force_refresh:
        return cache

    url = "https://www.sec.gov/files/company_tickers.json"
    data = _request_json(url)
    mapping: Dict[str, TickerInfo] = {}
    for value in data.values():
        ticker = value["ticker"].upper()
        mapping[ticker] = TickerInfo(
            ticker=ticker,
            cik_str=str(value["cik_str"]),
            title=value["title"],
        )
    _save_ticker_cache(mapping)
    return mapping


def resolve_cik(ticker_or_cik: str, *, force_refresh: bool = False) -> TickerInfo:
    candidate = ticker_or_cik.strip().upper()
    if candidate.isdigit() and len(candidate) <= 10:
        return TickerInfo(ticker=candidate, cik_str=candidate, title="")

    mapping = fetch_ticker_map(force_refresh=force_refresh)
    if candidate not in mapping:
        raise KeyError(f"Unknown ticker symbol '{candidate}'.")
    return mapping[candidate]


def fetch_company_facts(cik: str) -> dict:
    info = resolve_cik(cik)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{info.cik}.json"
    return _request_json(url, sleep=0.4)


def _iter_facts_for_tag(facts: dict, tag: str) -> Iterable[dict]:
    taxonomy = facts.get("facts", {}).get("us-gaap", {})
    if tag not in taxonomy:
        return []
    tag_info = taxonomy[tag]
    for units in tag_info.get("units", {}).values():
        for item in units:
            yield item


def select_fact(
    facts: dict,
    tag: str,
    *,
    period: str = "annual",
    forms: Optional[Iterable[str]] = None,
) -> Optional[dict]:
    """Select the most recent fact for ``tag`` matching ``period``."""
    period = period.lower()
    if forms is None:
        forms = ("10-K",) if period == "annual" else ("10-Q", "10-K")

    candidates = []
    for item in _iter_facts_for_tag(facts, tag):
        form = item.get("form")
        if form not in forms:
            continue
        if period == "annual" and item.get("fp") not in {"FY", "Q4", "12M"}:
            continue
        if period == "quarterly" and item.get("fp") not in {"Q1", "Q2", "Q3", "Q4"}:
            continue
        end = item.get("end")
        try:
            end_date = datetime.fromisoformat(end)
        except (TypeError, ValueError):
            continue
        candidates.append((end_date, item))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def extract_value(fact: Optional[dict]) -> Optional[float]:
    if not fact:
        return None
    return float(fact.get("val"))
