from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RawMetricSpec:
    name: str
    dtype: str
    nullable: bool
    description: str
    expected_range: str | None = None
    formula_note: str | None = None
    directional_note: str | None = None


REQUIRED_ANNUAL_VALIDATED_COLUMNS: dict[str, RawMetricSpec] = {
    "ExitCap": RawMetricSpec(
        name="ExitCap",
        dtype="float",
        nullable=False,
        description="Exit cap rate actually used for the run after override and correlation logic.",
        expected_range="> 0",
        formula_note="Per-run exit_cap value used in terminal pricing.",
        directional_note="Higher exit cap should reduce terminal value and generally reduce IRR.",
    ),
    "GRM": RawMetricSpec(
        name="GRM",
        dtype="float",
        nullable=True,
        description="Gross rent multiplier based on Year 1 cash rent.",
        formula_note="purchase_price / y1_cash_rent",
        directional_note="Higher Year 1 cash rent lowers GRM; higher purchase price raises GRM.",
    ),
    "OperatingExpenseRatio": RawMetricSpec(
        name="OperatingExpenseRatio",
        dtype="float",
        nullable=True,
        description="Year 1 operating expense ratio on an NOI basis.",
        expected_range="[0, 1] in normal runs",
        formula_note="y1_opex_noi / y1_income",
        directional_note="Higher OPEX raises OER; higher rent and recoveries lower OER.",
    ),
    "EquityToValue": RawMetricSpec(
        name="EquityToValue",
        dtype="float",
        nullable=False,
        description="Transaction-basis equity-to-value proxy for the annual validated model.",
        formula_note="equity / total_cost",
        directional_note="Higher debt ratio lowers it; higher equity-funded fees and reserves raise it.",
    ),
    "Capex_Total": RawMetricSpec(
        name="Capex_Total",
        dtype="float",
        nullable=False,
        description="Total below-NOI capital cash outflow across the hold.",
        expected_range=">= 0",
        formula_note="sum(capex_series)",
        directional_note="Higher TI/LC, reserves, or scheduled capex should raise it.",
    ),
    "PhysicalOccupancyRate": RawMetricSpec(
        name="PhysicalOccupancyRate",
        dtype="float",
        nullable=False,
        description="Per-run hold-average physical occupancy on an RSF-month basis.",
        expected_range="[0, 1]",
        formula_note="mean over years of occupied_rsf_months / (total_rsf * months_in_year)",
        directional_note="Higher initial occupancy and renewal retention should raise it.",
    ),
    "EconomicOccupancyRate": RawMetricSpec(
        name="EconomicOccupancyRate",
        dtype="float",
        nullable=True,
        description="Per-run hold-average economic occupancy using contract rent potential.",
        expected_range="[0, 1] in normal runs",
        formula_note="mean over years of cash_rent / scheduled_contract_rent",
        directional_note="More free rent or downtime lowers it; stronger renewal retention raises it.",
    ),
    "LeaseRenewalRate": RawMetricSpec(
        name="LeaseRenewalRate",
        dtype="float",
        nullable=True,
        description="Lease renewal rate measured from actual expiry events in the run.",
        expected_range="[0, 1]",
        formula_note="renewal_event_count / lease_event_count",
        directional_note="Higher renew_prob should raise it.",
    ),
}


OPTIONAL_GATED_COLUMNS = {
    "_ExplainMode",
    "_ScheduleData",
    "_TerminalData",
    "_CashFlowSeries",
    "equity_cf",
    "InterestCoverage",
    "ROI",
    "TenantTurnoverRate",
    "OccupancyRate",
    "AvgRentPricePSF",
    "GOI",
    "RevenueGrowth_YoY",
    "FFO",
    "AFFO",
    "NAV",
    "PI",
    "ReturnOnCost",
    "InvestmentRating",
    "RiskAssessmentScore",
}
