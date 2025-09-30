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
    indent: int = 0
    is_header: bool = False
    industry_common_size: Optional[float] = None

    def as_row(self) -> List[str]:
        if self.value is None:
            value_text = "-"
        else:
            value_text = f"{self.value:,.0f}"
        if self.common_size is None:
            percent_text = "-"
        else:
            percent_text = f"{self.common_size:.1%}"
        if self.industry_common_size is None:
            industry_text = "-"
        else:
            industry_text = f"{self.industry_common_size:.1%}"
        return [self.label, value_text, percent_text, industry_text]



class StatementNotAvailableError(RuntimeError):
    """Raised when the requested statement cannot be prepared."""


def _build_lines(facts: dict, layout: Iterable[tuple], *, period: str) -> List[CommonSizeLine]:
    lines: List[CommonSizeLine] = []
    for item in layout:
        if len(item) == 2:
            label, tag = item
            indent = 0
            is_header = tag is None
        elif len(item) == 3:
            label, tag, indent = item
            is_header = tag is None
        elif len(item) == 4:
            label, tag, indent, is_header = item
        else:  # pragma: no cover - defensive guard
            raise ValueError("Layout entries must have 2 to 4 elements")

        value = None
        if tag:
            fact = sec_client.select_fact(facts, tag, period=period)
            value = sec_client.extract_value(fact)

        lines.append(
            CommonSizeLine(
                label=label,
                value=value,
                common_size=None,
                indent=indent,
                is_header=is_header,
            )
        )
    return lines


def _compute_common_size(lines: List[CommonSizeLine], *, denominator_index: int) -> None:
    denominator = lines[denominator_index].value
    if denominator in (0, None):
        raise StatementNotAvailableError("Denominator for common size statement is missing or zero.")
    for line in lines:
        if line.value is None:
            continue
        line.common_size = line.value / denominator


def _apply_industry_average(
    lines: List[CommonSizeLine],
    peer_facts: Iterable[dict],
    *,
    layout: Iterable[tuple],
    denominator_index: int,
    period: str,
) -> None:
    peer_ratios: List[List[Optional[float]]] = []
    for facts in peer_facts:
        peer_lines = _build_lines(facts, layout, period=period)
        try:
            _compute_common_size(peer_lines, denominator_index=denominator_index)
        except StatementNotAvailableError:
            continue
        peer_ratios.append([line.common_size for line in peer_lines])

    if not peer_ratios:
        return

    for index, line in enumerate(lines):
        values = [row[index] for row in peer_ratios if row[index] is not None]
        if not values:
            continue
        line.industry_common_size = sum(values) / len(values)

_INCOME_LAYOUT = [
    ("Revenue", "Revenues", 0),
    ("Cost of revenue", "CostOfRevenue", 1),
    ("Gross profit", "GrossProfit", 0),
    ("Operating expenses", None, 0, True),
    ("Research & development", "ResearchAndDevelopmentExpense", 1),
    (
        "Selling, general & administrative",
        "SellingGeneralAndAdministrativeExpense",
        1,
    ),
    ("Other operating expenses", "OtherOperatingExpenses", 1),
    ("Total operating expenses", "OperatingExpenses", 0),
    ("Operating income", "OperatingIncomeLoss", 0),
    ("Interest expense", "InterestExpense", 1),
    ("Other income (expense)", "OtherNonoperatingIncomeExpense", 1),
    (
        "Income before taxes",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxes",
        0,
    ),
    ("Income tax expense (benefit)", "IncomeTaxExpenseBenefit", 1),
    ("Net income", "NetIncomeLoss", 0),
]

_BALANCE_LAYOUT = [
    ("Total assets", "Assets", 0),
    ("Current assets", None, 0, True),
    (
        "Cash and cash equivalents",
        "CashAndCashEquivalentsAtCarryingValue",
        1,
    ),
    ("Short-term investments", "MarketableSecuritiesCurrent", 1),
    ("Accounts receivable", "AccountsReceivableNetCurrent", 1),
    ("Inventory", "InventoryNet", 1),
    ("Other current assets", "OtherAssetsCurrent", 1),
    ("Total current assets", "AssetsCurrent", 0),
    ("Non-current assets", None, 0, True),
    (
        "Property, plant and equipment, net",
        "PropertyPlantAndEquipmentNet",
        1,
    ),
    (
        "Operating lease right-of-use assets",
        "OperatingLeaseRightOfUseAsset",
        1,
    ),
    ("Goodwill", "Goodwill", 1),
    ("Intangible assets, net", "IntangibleAssetsNetExcludingGoodwill", 1),
    ("Other non-current assets", "OtherAssetsNoncurrent", 1),
    ("Total non-current assets", "AssetsNoncurrent", 0),
    ("Liabilities and equity", None, 0, True),
    ("Current liabilities", None, 0, True),
    ("Accounts payable", "AccountsPayableCurrent", 1),
    ("Accrued liabilities", "AccruedLiabilitiesCurrent", 1),
    ("Short-term debt", "ShortTermBorrowings", 1),
    ("Other current liabilities", "OtherLiabilitiesCurrent", 1),
    ("Total current liabilities", "LiabilitiesCurrent", 0),
    ("Non-current liabilities", None, 0, True),
    ("Long-term debt", "LongTermDebtNoncurrent", 1),
    ("Operating lease liabilities", "OperatingLeaseLiabilityNoncurrent", 1),
    ("Other non-current liabilities", "OtherLiabilitiesNoncurrent", 1),
    ("Total non-current liabilities", "LiabilitiesNoncurrent", 0),
    ("Total liabilities", "Liabilities", 0),
    ("Stockholders' equity", None, 0, True),
    ("Common stock", "CommonStockValue", 1),
    ("Additional paid-in capital", "AdditionalPaidInCapital", 1),
    (
        "Retained earnings",
        "RetainedEarningsAccumulatedDeficit",
        1,
    ),
    (
        "Accumulated other comprehensive income (loss)",
        "AccumulatedOtherComprehensiveIncomeLossNetOfTax",
        1,
    ),
    ("Treasury stock", "TreasuryStockValue", 1),
    ("Total stockholders' equity", "StockholdersEquity", 0),
    ("Total liabilities and equity", "LiabilitiesAndStockholdersEquity", 0),
]


def build_income_statement(
    facts: dict,
    *,
    period: str = "annual",
    peers: Optional[Iterable[dict]] = None,
) -> List[CommonSizeLine]:

    lines = _build_lines(facts, _INCOME_LAYOUT, period=period)
    if lines[0].value is None or lines[0].value == 0:
        raise StatementNotAvailableError("Revenue not available for common size computation.")
    _compute_common_size(lines, denominator_index=0)
    if peers:
        _apply_industry_average(
            lines,
            peers,
            layout=_INCOME_LAYOUT,
            denominator_index=0,
            period=period,
        )
    return lines


def build_balance_sheet(
    facts: dict,
    *,
    period: str = "annual",
    peers: Optional[Iterable[dict]] = None,
) -> List[CommonSizeLine]:

    lines = _build_lines(facts, _BALANCE_LAYOUT, period=period)
    if lines[0].value is None or lines[0].value == 0:
        raise StatementNotAvailableError("Total assets not available for common size computation.")
    _compute_common_size(lines, denominator_index=0)
    if peers:
        _apply_industry_average(
            lines,
            peers,
            layout=_BALANCE_LAYOUT,
            denominator_index=0,
            period=period,
        )

    return lines
