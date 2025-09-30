import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from commonize.common_size import CommonSizeLine, StatementNotAvailableError
from commonize.industry_cache import IndustryBenchmark
from commonize.sec_client import IndustryInfo, TickerInfo
from commonize import web


def _build_lines():
    return [
        CommonSizeLine(label="Revenue", value=100.0, common_size=1.0),
        CommonSizeLine(label="Net income", value=25.0, common_size=0.25),
    ]


def _setup_common_mocks(monkeypatch):
    info = TickerInfo(ticker="DEMO", cik_str="1234", title="Demo Corporation")
    monkeypatch.setattr(web, "resolve_cik", lambda ticker: info)
    monkeypatch.setattr(web, "fetch_company_facts", lambda cik: {"facts": {}})
    industry = IndustryInfo(sic="1234", description="Demo Industry")
    monkeypatch.setattr(web, "get_company_industry", lambda cik: industry)
    monkeypatch.setattr(
        web,
        "load_benchmark",
        lambda sic, statement, period, expected_line_count=None: None,
    )
    monkeypatch.setattr(web, "store_benchmark", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        web,
        "fetch_peer_company_facts",
        lambda cik: (industry, [info], [{"facts": {}}]),
    )
    monkeypatch.setitem(
        web._STATEMENT_BUILDERS,
        "income",
        lambda facts, *, period="annual", peers=None: _build_lines(),
    )
    monkeypatch.setitem(
        web._STATEMENT_BUILDERS,
        "balance",
        lambda facts, *, period="annual", peers=None: _build_lines(),
    )
    return info


def test_cached_industry_skips_peer_fetch(monkeypatch):
    info = TickerInfo(ticker="DEMO", cik_str="1234", title="Demo Corporation")
    industry = IndustryInfo(sic="1234", description="Demo Industry")

    monkeypatch.setattr(web, "resolve_cik", lambda ticker: info)
    monkeypatch.setattr(web, "fetch_company_facts", lambda cik: {"facts": {}})
    monkeypatch.setattr(web, "get_company_industry", lambda cik: industry)

    benchmark = IndustryBenchmark(ratios=[1.0, 0.25], peer_count=3, line_count=2, updated_at=0.0)
    monkeypatch.setattr(
        web,
        "load_benchmark",
        lambda sic, statement, period, expected_line_count=None: benchmark,
    )
    def fail_store(*args, **kwargs):
        raise AssertionError("should not store when cache hit")

    monkeypatch.setattr(web, "store_benchmark", fail_store)

    def fail_fetch(*args, **kwargs):
        raise AssertionError("should not fetch peers when cache is warm")

    monkeypatch.setattr(web, "fetch_peer_company_facts", fail_fetch)
    monkeypatch.setitem(
        web._STATEMENT_BUILDERS,
        "income",
        lambda facts, *, period="annual", peers=None: _build_lines(),
    )

    client = TestClient(web.create_app())
    response = client.get("/", params={"ticker": "demo", "statement": "income", "period": "annual"})

    assert response.status_code == 200
    assert "derived from 3 peers" in response.text


def test_index_renders_statement(monkeypatch):
    _setup_common_mocks(monkeypatch)
    client = TestClient(web.create_app())

    response = client.get("/", params={"ticker": "demo", "statement": "income", "period": "annual"})

    assert response.status_code == 200
    assert "Demo Corporation" in response.text
    assert "Net income" in response.text
    assert "25" in response.text
    assert "Industry Common Size" in response.text


def test_download_csv(monkeypatch):
    _setup_common_mocks(monkeypatch)
    client = TestClient(web.create_app())

    response = client.get("/download/csv", params={"ticker": "demo", "statement": "income", "period": "annual"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "Industry Common Size" in response.text


def test_download_excel(monkeypatch):
    _setup_common_mocks(monkeypatch)
    client = TestClient(web.create_app())

    response = client.get("/download/xlsx", params={"ticker": "demo", "statement": "income", "period": "annual"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert response.content[:2] == b"PK"


def test_index_handles_statement_errors(monkeypatch):
    _setup_common_mocks(monkeypatch)

    def raise_error(*args, **kwargs):
        raise StatementNotAvailableError("Data unavailable")

    monkeypatch.setitem(
        web._STATEMENT_BUILDERS,
        "income",
        lambda facts, *, period="annual", peers=None: raise_error(),
    )

    client = TestClient(web.create_app())
    response = client.get("/", params={"ticker": "demo", "statement": "income", "period": "annual"})

    assert response.status_code == 200
    assert "Data unavailable" in response.text
