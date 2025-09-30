"""Caching helpers for industry benchmark data."""
from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

_CACHE_DIR = Path(os.environ.get("COMMONIZE_CACHE", "./.commonize-cache"))
_CACHE_DIR.mkdir(parents=True, exist_ok=True)
_DB_PATH = _CACHE_DIR / "industry_benchmarks.sqlite3"

# Expose the database path so other modules (such as background workers) can
# coordinate on the same persistent store without duplicating configuration.
DB_PATH = _DB_PATH

_DEFAULT_TTL_SECONDS = int(os.environ.get("COMMONIZE_INDUSTRY_CACHE_TTL", 60 * 60 * 24 * 7))


@dataclass
class IndustryBenchmark:
    """Representation of cached industry benchmark ratios."""

    ratios: List[Optional[float]]
    peer_count: int
    line_count: int
    updated_at: float


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS industry_benchmarks (
            sic TEXT NOT NULL,
            statement TEXT NOT NULL,
            period TEXT NOT NULL,
            ratios TEXT NOT NULL,
            peer_count INTEGER NOT NULL,
            line_count INTEGER NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY (sic, statement, period)
        )
        """
    )


def ensure_cache_schema(conn: sqlite3.Connection) -> None:
    """Public wrapper so other modules can ensure the cache table exists."""

    _ensure_schema(conn)

def load_benchmark(
    sic: Optional[str],
    statement: str,
    period: str,
    *,
    expected_line_count: Optional[int] = None,
    max_age_seconds: Optional[int] = None,
) -> Optional[IndustryBenchmark]:
    """Return a cached benchmark for ``sic`` if it is still valid."""

    if not sic:
        return None
    if max_age_seconds is None:
        max_age_seconds = _DEFAULT_TTL_SECONDS

    with sqlite3.connect(_DB_PATH) as conn:
        _ensure_schema(conn)
        row = conn.execute(
            """
            SELECT ratios, peer_count, line_count, updated_at
            FROM industry_benchmarks
            WHERE sic = ? AND statement = ? AND period = ?
            """,
            (sic, statement, period),
        ).fetchone()

    if not row:
        return None

    ratios_json, peer_count, line_count, updated_at = row
    if expected_line_count is not None and line_count != expected_line_count:
        return None
    if max_age_seconds and max_age_seconds > 0:
        if time.time() - updated_at > max_age_seconds:
            return None

    ratios = json.loads(ratios_json)
    # Ensure ratios length matches expected when provided
    if expected_line_count is not None and len(ratios) != expected_line_count:
        return None

    return IndustryBenchmark(
        ratios=list(ratios),
        peer_count=int(peer_count),
        line_count=int(line_count),
        updated_at=float(updated_at),
    )


def store_benchmark(
    sic: Optional[str],
    statement: str,
    period: str,
    ratios: Iterable[Optional[float]],
    peer_count: int,
    *,
    line_count: int,
) -> None:
    """Persist ``ratios`` for the given industry if possible."""

    if not sic:
        return

    ratios_list = list(ratios)
    if not ratios_list:
        return
    if len(ratios_list) != line_count:
        raise ValueError("Line count mismatch when storing industry benchmark")

    timestamp = time.time()
    payload = json.dumps(ratios_list)

    with sqlite3.connect(_DB_PATH) as conn:
        _ensure_schema(conn)
        conn.execute(
            """
            INSERT INTO industry_benchmarks (
                sic, statement, period, ratios, peer_count, line_count, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sic, statement, period)
            DO UPDATE SET
                ratios = excluded.ratios,
                peer_count = excluded.peer_count,
                line_count = excluded.line_count,
                updated_at = excluded.updated_at
            """,
            (sic, statement, period, payload, int(peer_count), int(line_count), timestamp),
        )
        conn.commit()
