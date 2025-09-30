"""Utilities to build common size financial statements."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from . import sec_client


@dataclass
class CommonSizeLine:
    label: str
    value: Optional[float]
    common_size: Optional[float]

    def as_row(self) -> List[str]:
        if self.value is None:
            value_text = "-"
        else:
            value_text = f"{self.value:,.0f}"
        if self.common_size is None:
            percent_text = "-"
        else:
            percent_text = f"{self.common_size:.1%}"
        return [self.label, value_text, percent_text]


class StatementNotAvailableError(RuntimeError):
    """Raised when the requested statement cannot be prepared."""


def _build_lines(facts: dict, layout: Iterable[tuple], *, period: str) -> List[CommonSizeLine]:
    lines: List[CommonSizeLine] = []
    for label, tag in layout:
        fact = sec_client.select_fact(facts, tag, period=period)
        value = sec_client.extract_value(fact)
        lines.append(CommonSizeLine(label=label, value=value, common_size=None))
    return lines


def _compute_common_size(lines: List[CommonSizeLine], *, denominator_index: int) -> None:
    denominator = lines[denominator_index].value
    if denominator in (0, None):
        raise StatementNotAvailableError("Denominator for common size statement is missing or zero.")
    for line in lines:
        if line.value is None:
            continue
        line.common_size = line.value / denominator


_INCOME_LAYOUT = [
    ("Revenue", "Revenues"),
    ("Cost of revenue", "CostOfRevenue"),
    ("Gross profit", "GrossProfit"),
    ("Research & development", "ResearchAndDevelopmentExpense"),
    ("Selling, general & administrative", "SellingGeneralAndAdministrativeExpense"),
    ("Operating income", "OperatingIncomeLoss"),
    ("Net income", "NetIncomeLoss"),
]

_BALANCE_LAYOUT = [
    ("Total assets", "Assets"),
    ("Cash and cash equivalents", "CashAndCashEquivalentsAtCarryingValue"),
    ("Accounts receivable", "AccountsReceivableNetCurrent"),
    ("Inventory", "InventoryNet"),
    ("Total liabilities", "Liabilities"),
    ("Total equity", "StockholdersEquity"),
]


def build_income_statement(facts: dict, *, period: str = "annual") -> List[CommonSizeLine]:
    lines = _build_lines(facts, _INCOME_LAYOUT, period=period)
    if lines[0].value is None or lines[0].value == 0:
        raise StatementNotAvailableError("Revenue not available for common size computation.")
    _compute_common_size(lines, denominator_index=0)
    return lines


def build_balance_sheet(facts: dict, *, period: str = "annual") -> List[CommonSizeLine]:
    lines = _build_lines(facts, _BALANCE_LAYOUT, period=period)
    if lines[0].value is None or lines[0].value == 0:
        raise StatementNotAvailableError("Total assets not available for common size computation.")
    _compute_common_size(lines, denominator_index=0)
    return lines
