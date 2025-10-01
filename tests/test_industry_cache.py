import importlib


def test_store_and_load(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    monkeypatch.setenv("COMMONIZE_CACHE", str(cache_dir))

    module = importlib.import_module("commonize.industry_cache")
    importlib.reload(module)

    module.store_benchmark("1234", "income", "annual", [0.1, None], 3, line_count=2)
    result = module.load_benchmark("1234", "income", "annual", expected_line_count=2)

    assert result is not None
    assert result.peer_count == 3
    assert result.ratios == [0.1, None]
    assert result.line_count == 2
