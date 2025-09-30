"""Background job orchestration for computing industry benchmarks."""
from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional

from .common_size import (
    CommonSizeLine,
    StatementNotAvailableError,
    build_balance_sheet,
    build_income_statement,
)
from .industry_cache import DB_PATH, ensure_cache_schema, load_benchmark, store_benchmark
from .sec_client import (
    SECClientError,
    IndustryInfo,
    TickerInfo,
    fetch_company_facts,
    fetch_peer_company_facts,
)


_JOB_STATEMENTS: Dict[str, Callable[..., list[CommonSizeLine]]] = {
    "income": build_income_statement,
    "balance": build_balance_sheet,
}


@dataclass
class BenchmarkJob:
    """Representation of a queued benchmark computation."""

    sic: Optional[str]
    statement: str
    period: str
    max_companies: int
    subject_cik: str
    subject_ticker: str
    subject_title: str
    status: str
    queued_at: float
    started_at: Optional[float]
    finished_at: Optional[float]
    attempts: int
    error: Optional[str]


def _ensure_job_schema(conn: sqlite3.Connection) -> None:
    ensure_cache_schema(conn)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS benchmark_jobs (
            sic TEXT,
            statement TEXT NOT NULL,
            period TEXT NOT NULL,
            max_companies INTEGER NOT NULL,
            subject_cik TEXT NOT NULL,
            subject_ticker TEXT NOT NULL,
            subject_title TEXT NOT NULL,
            status TEXT NOT NULL,
            queued_at REAL NOT NULL,
            started_at REAL,
            finished_at REAL,
            attempts INTEGER NOT NULL DEFAULT 0,
            error TEXT,
            PRIMARY KEY (sic, statement, period)
        )
        """
    )


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    _ensure_job_schema(conn)
    return conn


def enqueue_benchmark_job(
    subject: TickerInfo,
    industry: IndustryInfo,
    statement: str,
    period: str,
    *,
    max_companies: int,
    force: bool = False,
) -> None:
    """Persist a benchmark job if one is not already queued."""

    if not industry.sic:
        return

    now = time.time()
    payload = (
        industry.sic,
        statement,
        period,
        int(max_companies),
        subject.cik,
        subject.ticker,
        subject.title,
    )

    with _connect() as conn:
        row = conn.execute(
            """
            SELECT status FROM benchmark_jobs
            WHERE sic = ? AND statement = ? AND period = ?
            """,
            (industry.sic, statement, period),
        ).fetchone()

        if row:
            if force and row[0] != "running":
                conn.execute(
                    """
                    UPDATE benchmark_jobs
                    SET status = 'pending', queued_at = ?, started_at = NULL,
                        finished_at = NULL, attempts = 0, error = NULL,
                        max_companies = ?, subject_cik = ?,
                        subject_ticker = ?, subject_title = ?
                    WHERE sic = ? AND statement = ? AND period = ?
                    """,
                    (
                        now,
                        int(max_companies),
                        subject.cik,
                        subject.ticker,
                        subject.title,
                        industry.sic,
                        statement,
                        period,
                    ),
                )
                conn.commit()
            return

        conn.execute(
            """
            INSERT INTO benchmark_jobs (
                sic, statement, period, max_companies,
                subject_cik, subject_ticker, subject_title,
                status, queued_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            payload + (now,),
        )
        conn.commit()


def get_job_status(sic: Optional[str], statement: str, period: str) -> Optional[BenchmarkJob]:
    if not sic:
        return None
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT sic, statement, period, max_companies, subject_cik,
                   subject_ticker, subject_title, status, queued_at,
                   started_at, finished_at, attempts, error
            FROM benchmark_jobs
            WHERE sic = ? AND statement = ? AND period = ?
            """,
            (sic, statement, period),
        ).fetchone()
    if not row:
        return None
    return BenchmarkJob(*row)


def _row_to_job(row: tuple) -> BenchmarkJob:
    return BenchmarkJob(*row)


def claim_next_job() -> Optional[BenchmarkJob]:
    with _connect() as conn:
        conn.isolation_level = None
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT sic, statement, period, max_companies, subject_cik,
                   subject_ticker, subject_title, status, queued_at,
                   started_at, finished_at, attempts, error
            FROM benchmark_jobs
            WHERE status = 'pending'
            ORDER BY queued_at ASC
            LIMIT 1
            """,
        ).fetchone()
        if not row:
            conn.execute("COMMIT")
            return None

        job = _row_to_job(row)
        conn.execute(
            """
            UPDATE benchmark_jobs
            SET status = 'running', started_at = ?, attempts = attempts + 1
            WHERE sic = ? AND statement = ? AND period = ?
            """,
            (time.time(), job.sic, job.statement, job.period),
        )
        conn.execute("COMMIT")
        job.status = "running"
    return job


def _complete_job(job: BenchmarkJob, status: str, error: Optional[str] = None) -> None:
    with _connect() as conn:
        conn.execute(
            """
            UPDATE benchmark_jobs
            SET status = ?, finished_at = ?, error = ?
            WHERE sic = ? AND statement = ? AND period = ?
            """,
            (status, time.time(), error, job.sic, job.statement, job.period),
        )
        conn.commit()


def process_job(job: BenchmarkJob) -> None:
    builder = _JOB_STATEMENTS.get(job.statement)
    if builder is None:
        _complete_job(job, "failed", f"Unknown statement '{job.statement}'")
        return

    try:
        facts = fetch_company_facts(job.subject_cik)
        industry_info, peers, peer_facts = fetch_peer_company_facts(
            job.subject_cik, max_companies=job.max_companies
        )
    except (SECClientError, KeyError) as exc:
        _complete_job(job, "failed", str(exc))
        return

    if not peer_facts:
        _complete_job(job, "failed", "No peer filings available")
        return

    try:
        lines = builder(facts, period=job.period, peers=peer_facts)
    except StatementNotAvailableError as exc:
        _complete_job(job, "failed", str(exc))
        return

    ratios = [line.industry_common_size for line in lines]
    try:
        store_benchmark(
            industry_info.sic,
            job.statement,
            job.period,
            ratios,
            len(peers),
            line_count=len(lines),
        )
    except ValueError as exc:
        _complete_job(job, "failed", str(exc))
        return

    _complete_job(job, "succeeded", None)


def worker_loop(stop_event: threading.Event, poll_interval: float = 2.0) -> None:
    """Run a worker loop until ``stop_event`` is set."""

    while not stop_event.is_set():
        job = claim_next_job()
        if job is None:
            stop_event.wait(poll_interval)
            continue
        process_job(job)


def ensure_benchmark_ready(
    subject: TickerInfo,
    industry: IndustryInfo,
    statement: str,
    period: str,
    *,
    max_companies: int,
) -> Optional[BenchmarkJob]:
    """Ensure a benchmark exists, queueing work when missing."""

    benchmark = load_benchmark(industry.sic, statement, period)
    if benchmark is not None:
        return None

    enqueue_benchmark_job(
        subject,
        industry,
        statement,
        period,
        max_companies=max_companies,
    )
    return get_job_status(industry.sic, statement, period)


__all__ = [
    "BenchmarkJob",
    "enqueue_benchmark_job",
    "get_job_status",
    "claim_next_job",
    "process_job",
    "worker_loop",
    "ensure_benchmark_ready",
]

