from commonize import sec_client


def test_select_fact_prefers_reference_metadata():
    facts = {
        "facts": {
            "us-gaap": {
                "Revenue": {
                    "units": {
                        "USD": [
                            {
                                "val": 100.0,
                                "end": "2023-12-31",
                                "form": "10-K",
                                "fp": "FY",
                                "accn": "0001",
                            }
                        ]
                    }
                },
                "Cost": {
                    "units": {
                        "USD": [
                            {
                                "val": 70.0,
                                "end": "2023-12-31",
                                "form": "10-K",
                                "fp": "FY",
                                "accn": "0002",
                            },
                            {
                                "val": 65.0,
                                "end": "2023-12-31",
                                "form": "10-K",
                                "fp": "FY",
                                "accn": "0001",
                            },
                        ]
                    }
                },
            }
        }
    }

    revenue_fact = sec_client.select_fact(facts, "Revenue")
    assert revenue_fact is not None
    cost_fact = sec_client.select_fact(
        facts,
        "Cost",
        reference=revenue_fact,
    )
    assert cost_fact is not None
    assert cost_fact.get("accn") == "0001"
    assert cost_fact.get("val") == 65.0


def test_select_fact_falls_back_when_no_reference_match():
    facts = {
        "facts": {
            "us-gaap": {
                "Metric": {
                    "units": {
                        "USD": [
                            {
                                "val": 10.0,
                                "end": "2022-12-31",
                                "form": "10-K",
                                "fp": "FY",
                            },
                            {
                                "val": 12.0,
                                "end": "2023-12-31",
                                "form": "10-K",
                                "fp": "FY",
                            },
                        ]
                    }
                }
            }
        }
    }

    fact = sec_client.select_fact(
        facts,
        "Metric",
        reference={"end": "2024-12-31", "form": "10-K"},
    )
    assert fact is not None
    # No match on the reference data, so the latest fact should be returned.
    assert fact.get("end") == "2023-12-31"
