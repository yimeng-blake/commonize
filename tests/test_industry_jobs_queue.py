import importlib

from commonize.common_size import CommonSizeLine
from commonize.sec_client import IndustryInfo, TickerInfo


def test_enqueue_and_process_job(tmp_path, monkeypatch):
    monkeypatch.setenv("COMMONIZE_CACHE", str(tmp_path))

    cache_module = importlib.import_module("commonize.industry_cache")
    jobs_module = importlib.import_module("commonize.industry_jobs")
    importlib.reload(cache_module)
    jobs_module = importlib.reload(jobs_module)

    info = TickerInfo(ticker="DEMO", cik_str="1234", title="Demo Corp")
    industry = IndustryInfo(sic="5678", description="Demo Industry")

    def fake_builder(facts, *, period="annual", peers=None):
        line = CommonSizeLine(
            label="Revenue",
            value=100.0,
            common_size=1.0,
            industry_common_size=None,
        )
        if peers:
            line.industry_common_size = 0.5
        return [line]

    monkeypatch.setattr(jobs_module, "build_income_statement", fake_builder)
    jobs_module._JOB_STATEMENTS["income"] = fake_builder
    monkeypatch.setattr(jobs_module, "fetch_company_facts", lambda cik: {"facts": {}})
    monkeypatch.setattr(
        jobs_module,
        "fetch_peer_company_facts",
        lambda cik, max_companies=5: (industry, [info], [{"facts": {}}]),
    )

    jobs_module.enqueue_benchmark_job(
        info,
        industry,
        "income",
        "annual",
        max_companies=3,
    )

    job = jobs_module.claim_next_job()
    assert job is not None
    assert job.status == "running"

    jobs_module.process_job(job)

    stored = cache_module.load_benchmark(industry.sic, "income", "annual", expected_line_count=1)
    assert stored is not None
    assert stored.peer_count == 1
    assert stored.ratios[0] == 0.5

    refreshed_job = jobs_module.get_job_status(industry.sic, "income", "annual")
    assert refreshed_job is not None
    assert refreshed_job.status == "succeeded"
