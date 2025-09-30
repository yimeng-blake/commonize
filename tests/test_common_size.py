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


def test_missing_denominator_raises():
    facts = _build_facts({"Revenues": [(0.0, "10-K", "FY")]})
    try:
        common_size.build_income_statement(facts)
    except common_size.StatementNotAvailableError:
        pass
    else:
        raise AssertionError("Expected StatementNotAvailableError")
