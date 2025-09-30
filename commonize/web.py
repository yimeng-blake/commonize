"""FastAPI application for rendering common size financial statements."""
from __future__ import annotations

from io import BytesIO, StringIO
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Literal

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from .common_size import (
    CommonSizeLine,
    StatementNotAvailableError,
    build_balance_sheet,
    build_income_statement,
)
from .sec_client import (
    SECClientError,
    TickerInfo,
    fetch_company_facts,
    fetch_peer_company_facts,
    resolve_cik,
)


templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

StatementType = Literal["income", "balance"]
PeriodType = Literal["annual", "quarterly"]


_STATEMENT_BUILDERS: Dict[StatementType, Callable[..., List[CommonSizeLine]]] = {
    "income": build_income_statement,
    "balance": build_balance_sheet,
}


def _format_currency(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:,.0f}"


def _format_percent(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.1%}"


def _prepare_statement(
    ticker: str, statement: StatementType, period: PeriodType
) -> tuple[TickerInfo, List[CommonSizeLine], dict]:

    builder = _STATEMENT_BUILDERS.get(statement)
    if builder is None:
        raise HTTPException(status_code=400, detail="Unsupported statement type")

    info = resolve_cik(ticker)
    facts = fetch_company_facts(info.cik)
    industry_info, peer_companies, peer_facts = fetch_peer_company_facts(info.cik)
    peers_payload = {
        "industry": industry_info,
        "peers": peer_companies,
    }
    if peer_facts:
        lines = builder(facts, period=period, peers=peer_facts)
    else:
        lines = builder(facts, period=period)
    return info, lines, peers_payload



def _as_dataframe(lines: Iterable[CommonSizeLine]) -> pd.DataFrame:
    data: List[Dict[str, float | str | int | bool | None]] = []
    for line in lines:
        percent = None if line.common_size is None else line.common_size * 100
        industry_percent = (
            None if line.industry_common_size is None else line.industry_common_size * 100
        )

        data.append(
            {
                "Label": line.label,
                "Value": line.value,
                "Common Size": line.common_size,
                "Common Size (%)": percent,
                "Industry Common Size": line.industry_common_size,
                "Industry Common Size (%)": industry_percent,
                "Indent Level": line.indent,
                "Heading": line.is_header,

            }
        )
    return pd.DataFrame(data)


def _format_lines(lines: Iterable[CommonSizeLine]) -> List[Dict[str, str | int | bool]]:
    formatted: List[Dict[str, str | int | bool]] = []

    for line in lines:
        formatted.append(
            {
                "label": line.label,
                "value": _format_currency(line.value),
                "percent": _format_percent(line.common_size),
                "industry_percent": _format_percent(line.industry_common_size),
                "indent": line.indent,
                "is_heading": line.is_header,
                "is_emphasis": line.label.lower().startswith("total"),

            }
        )
    return formatted


def create_app() -> FastAPI:
    """Return an application configured to render common size statements."""

    app = FastAPI(title="Commonize", description="Common size financial statements")

    @app.get("/", response_class=HTMLResponse)
    async def index(
        request: Request,
        ticker: str = Query("", description="Ticker symbol or CIK"),
        statement: StatementType = Query("income", description="Statement to display"),
        period: PeriodType = Query("annual", description="Periodicity of filings"),
    ) -> HTMLResponse:
        context = {
            "request": request,
            "ticker": ticker,
            "statement": statement,
            "period": period,
            "company": None,
            "rows": None,
            "error": None,
            "statement_label": "Income Statement" if statement == "income" else "Balance Sheet",
            "period_label": "Annual" if period == "annual" else "Quarterly",
            "industry": None,
            "peer_count": 0,

        }

        if ticker:
            try:
                info, lines, peer_payload = _prepare_statement(ticker, statement, period)

            except KeyError:
                context["error"] = f"Unknown ticker symbol '{ticker}'."
            except StatementNotAvailableError as exc:  # pragma: no cover - error path
                context["error"] = str(exc)
            except SECClientError as exc:  # pragma: no cover - network errors
                context["error"] = str(exc)
            else:
                context["company"] = info
                context["rows"] = _format_lines(lines)
                context["industry"] = peer_payload.get("industry")
                peers = peer_payload.get("peers", [])
                context["peer_count"] = len(peers)


        return templates.TemplateResponse(request, "index.html", context)

    @app.get("/download/{file_format}")
    async def download(
        file_format: Literal["csv", "xlsx"],
        ticker: str,
        statement: StatementType = Query("income"),
        period: PeriodType = Query("annual"),
    ) -> StreamingResponse:
        try:
            info, lines, _ = _prepare_statement(ticker, statement, period)

        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except StatementNotAvailableError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        filename = f"{info.ticker.lower()}_{statement}_{period}.{file_format}"
        headers = {"Content-Disposition": f"attachment; filename=\"{filename}\""}

        dataframe = _as_dataframe(lines)

        if file_format == "csv":
            buffer = StringIO()
            dataframe.to_csv(buffer, index=False)
            buffer.seek(0)
            return StreamingResponse(
                iter([buffer.getvalue()]), media_type="text/csv", headers=headers
            )

        if file_format == "xlsx":
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                dataframe.to_excel(writer, index=False, sheet_name="Common Size")
            buffer.seek(0)
            return StreamingResponse(
                buffer,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers=headers,
            )

        raise HTTPException(status_code=404, detail="Unsupported format")

    return app


__all__ = ["create_app"]

