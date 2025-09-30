"""Utilities to build common size financial statements."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple, Union


from . import sec_client


@dataclass
class CommonSizeLine:
    label: str
    value: Optional[float]
    common_size: Optional[float]
    indent: int = 0
    is_header: bool = False
    industry_common_size: Optional[float] = None

    def value_in_millions(self) -> Optional[float]:
        if self.value is None:
            return None
        return self.value / 1_000_000

    def as_row(self) -> List[str]:
        value_millions = self.value_in_millions()
        if value_millions is None:
            value_text = "-"
        else:
            value_text = f"{value_millions:,.1f}"

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


TagSpec = Optional[Union[str, Sequence[str]]]


def _normalize_tag_spec(tag: TagSpec) -> Tuple[str, ...]:
    if tag is None:
        return tuple()
    if isinstance(tag, str):
        return (tag,)
    return tuple(tag)


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
        for candidate_tag in _normalize_tag_spec(tag):
            fact = sec_client.select_fact(facts, candidate_tag, period=period)
            value = sec_client.extract_value(fact)
            if value is not None:
                break


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
    (
        "Revenue",
        (
            "Revenues",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "SalesRevenueNet",
            "SalesRevenueGoodsNet",
        ),
        0,
    ),
    (
        "Cost of revenue",
        (
            "CostOfRevenue",
            "CostOfGoodsAndServicesSold",
            "CostOfSales",
            "CostOfGoodsSold",
        ),
        1,
    ),
    ("Gross profit", ("GrossProfit", "GrossProfitLoss"), 0),
    ("Operating expenses", None, 0, True),
    (
        "Research & development",
        ("ResearchAndDevelopmentExpense", "ResearchAndDevelopment"),
        1,
    ),
    (
        "Selling, general & administrative",
        ("SellingGeneralAndAdministrativeExpense", "SellingGeneralAndAdministrativeExpenses"),
        1,
    ),
    (
        "Other operating expenses",
        ("OtherOperatingExpenses", "OtherOperatingIncomeExpense"),
        1,
    ),
    ("Total operating expenses", ("OperatingExpenses", "OperatingCostsAndExpenses"), 0),
    ("Operating income", ("OperatingIncomeLoss", "OperatingProfitLoss"), 0),
    ("Interest expense", ("InterestExpense", "InterestExpenseDebt"), 1),
    (
        "Other income (expense)",
        ("OtherNonoperatingIncomeExpense", "NonoperatingIncomeExpense"),
        1,
    ),
    (
        "Income before taxes",
        (
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxes",
            "IncomeBeforeIncomeTaxes",
        ),
        0,
    ),
    (
        "Income tax expense (benefit)",
        ("IncomeTaxExpenseBenefit", "IncomeTaxExpenseBenefitContinuingOperations"),
        1,
    ),
    ("Net income", ("NetIncomeLoss", "ProfitLoss"), 0),
]

_BALANCE_LAYOUT = [
    ("Total assets", "Assets", 0),
    ("Current assets", None, 0, True),
    (
        "Cash and cash equivalents",
        ("CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsAndShortTermInvestments"),
        1,
    ),
    (
        "Short-term investments",
        ("MarketableSecuritiesCurrent", "AvailableForSaleSecuritiesCurrent"),
        1,
    ),
    (
        "Accounts receivable",
        ("AccountsReceivableNetCurrent", "AccountsReceivableTradeNetCurrent"),
        1,
    ),
    ("Inventory", ("InventoryNet", "InventoryFinishedGoods"), 1),
    ("Other current assets", ("OtherAssetsCurrent", "PrepaidExpenseAndOtherAssetsCurrent"), 1),
    ("Total current assets", ("AssetsCurrent", "CurrentAssets"), 0),
    ("Non-current assets", None, 0, True),
    (
        "Property, plant and equipment, net",
        ("PropertyPlantAndEquipmentNet", "PropertyPlantAndEquipmentIncludingConstructionInProgress"),
        1,
    ),
    (
        "Operating lease right-of-use assets",
        ("OperatingLeaseRightOfUseAsset", "OperatingLeaseRightOfUseAssetNoncurrent"),
        1,
    ),
    ("Goodwill", "Goodwill", 1),
    (
        "Intangible assets, net",
        ("IntangibleAssetsNetExcludingGoodwill", "IntangibleAssetsNet"),
        1,
    ),
    ("Other non-current assets", ("OtherAssetsNoncurrent", "OtherAssets"), 1),
    ("Total non-current assets", ("AssetsNoncurrent", "NoncurrentAssets"), 0),
    ("Liabilities and equity", None, 0, True),
    ("Current liabilities", None, 0, True),
    (
        "Accounts payable",
        ("AccountsPayableCurrent", "AccountsPayableTradeCurrent"),
        1,
    ),
    (
        "Accrued liabilities",
        ("AccruedLiabilitiesCurrent", "AccruedExpensesAndOtherCurrentLiabilities"),
        1,
    ),
    (
        "Short-term debt",
        ("ShortTermBorrowings", "ShortTermDebtAndCurrentPortionOfLongTermDebt"),
        1,
    ),
    ("Other current liabilities", ("OtherLiabilitiesCurrent", "OtherLiabilities"), 1),
    ("Total current liabilities", ("LiabilitiesCurrent", "CurrentLiabilities"), 0),
    ("Non-current liabilities", None, 0, True),
    (
        "Long-term debt",
        ("LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations"),
        1,
    ),
    (
        "Operating lease liabilities",
        (
            "OperatingLeaseLiabilityNoncurrent",
            "OperatingLeaseLiability",
        ),
        1,
    ),
    ("Other non-current liabilities", ("OtherLiabilitiesNoncurrent", "OtherNoncurrentLiabilities"), 1),
    ("Total non-current liabilities", ("LiabilitiesNoncurrent", "NoncurrentLiabilities"), 0),
    ("Total liabilities", ("Liabilities", "LiabilitiesAndStockholdersEquityAttributableToParent"), 0),
    ("Stockholders' equity", None, 0, True),
    ("Common stock", ("CommonStockValue", "CommonStockCapital"), 1),
    ("Additional paid-in capital", ("AdditionalPaidInCapital", "AdditionalPaidInCapitalCommonStock"), 1),
    (
        "Retained earnings",
        ("RetainedEarningsAccumulatedDeficit", "RetainedEarnings"),
        1,
    ),
    (
        "Accumulated other comprehensive income (loss)",
        (
            "AccumulatedOtherComprehensiveIncomeLossNetOfTax",
            "AccumulatedOtherComprehensiveIncomeLoss",
        ),
        1,
    ),
    ("Treasury stock", ("TreasuryStockValue", "TreasuryStockCommon"), 1),
    (
        "Total stockholders' equity",
        (
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        ),
        0,
    ),
    (
        "Total liabilities and equity",
        ("LiabilitiesAndStockholdersEquity", "LiabilitiesAndShareholdersEquity"),
        0,
    ),
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
