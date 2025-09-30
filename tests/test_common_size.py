import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from commonize import common_size


def _build_facts(tag_values):
    return {
        "facts": {
            "us-gaap": {
                tag: {
                    "units": {
                        "USD": [
                            {
                                "val": value,
                                "end": "2023-12-31",
                                "form": form,
                                "fp": fp,
                            }
                            for value, form, fp in values
                        ]
                    }
                }
                for tag, values in tag_values.items()
            }
        }
    }


def test_build_income_statement_computes_percentages():
    facts = _build_facts(
        {
            "Revenues": [(100.0, "10-K", "FY")],
            "CostOfRevenue": [(40.0, "10-K", "FY")],
            "GrossProfit": [(60.0, "10-K", "FY")],
            "ResearchAndDevelopmentExpense": [(10.0, "10-K", "FY")],
            "SellingGeneralAndAdministrativeExpense": [(20.0, "10-K", "FY")],
            "OperatingIncomeLoss": [(30.0, "10-K", "FY")],
            "NetIncomeLoss": [(25.0, "10-K", "FY")],
        }
    )

    lines = common_size.build_income_statement(facts)

    assert lines[0].common_size == 1
    assert lines[-1].common_size == 0.25
    cost_of_revenue = next(line for line in lines if line.label == "Cost of revenue")
    assert cost_of_revenue.indent == 1
    operating_expenses = next(line for line in lines if line.label == "Operating expenses")
    assert operating_expenses.is_header is True


def test_build_income_statement_includes_industry_average():
    company_facts = _build_facts(
        {
            "Revenues": [(200.0, "10-K", "FY")],
            "CostOfRevenue": [(80.0, "10-K", "FY")],
            "GrossProfit": [(120.0, "10-K", "FY")],
        }
    )
    peer_one = _build_facts(
        {
            "Revenues": [(150.0, "10-K", "FY")],
            "CostOfRevenue": [(60.0, "10-K", "FY")],
            "GrossProfit": [(90.0, "10-K", "FY")],
        }
    )
    peer_two = _build_facts(
        {
            "Revenues": [(250.0, "10-K", "FY")],
            "CostOfRevenue": [(125.0, "10-K", "FY")],
            "GrossProfit": [(125.0, "10-K", "FY")],
        }
    )

    lines = common_size.build_income_statement(company_facts, peers=[peer_one, peer_two])

    revenue_line = lines[0]
    assert revenue_line.industry_common_size == 1
    cost_of_revenue = next(line for line in lines if line.label == "Cost of revenue")
    # peer percentages: 0.4 and 0.5 -> average 0.45
    assert round(cost_of_revenue.industry_common_size or 0, 4) == 0.45


def test_missing_denominator_raises():
    facts = _build_facts({"Revenues": [(0.0, "10-K", "FY")]})
    try:
        common_size.build_income_statement(facts)
    except common_size.StatementNotAvailableError:
        pass
    else:
        raise AssertionError("Expected StatementNotAvailableError")


def test_balance_sheet_includes_hierarchical_items():
    facts = _build_facts(
        {
            "Assets": [(200.0, "10-K", "FY")],
            "Liabilities": [(120.0, "10-K", "FY")],
            "StockholdersEquity": [(80.0, "10-K", "FY")],
            "LiabilitiesAndStockholdersEquity": [(200.0, "10-K", "FY")],
        }
    )

    lines = common_size.build_balance_sheet(facts)

    assert lines[0].label == "Total assets"
    assert lines[0].common_size == 1
    current_assets_header = next(line for line in lines if line.label == "Current assets")
    assert current_assets_header.is_header is True
    accounts_payable = next(line for line in lines if line.label == "Accounts payable")
    assert accounts_payable.indent == 1
    assert lines[-1].label == "Total liabilities and equity"
