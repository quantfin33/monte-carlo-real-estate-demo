# Metric-to-Inputs Mapping

This document maps every available metric to the inputs that should logically influence it and the expected direction of change.

## Metric Categories

### Core Return Metrics
| Metric | Related Inputs | Expected Direction | Formula/Logic |
|--------|---------------|-------------------|---------------|
| **IRR** | `purchase_price`, `rent levels`, `rent_growth`, `opex_start`, `opex_growth`, `debt_ratio`, `interest_rate`, `exit_cap_range` | Purchase price ↓→ IRR ↑, Rent ↑→ IRR ↑, OpEx ↑→ IRR ↓, Interest ↑→ IRR ↓, Exit cap ↓→ IRR ↑ | Present value calculation |
| **NPV** | `discount_rate`, `purchase_price`, `rent levels`, `cash flows`, `exit_cap_range` | Discount rate ↑→ NPV ↓, Rent ↑→ NPV ↑, Purchase price ↑→ NPV ↓ | PV of cash flows minus initial investment |
| **CoC** | `in_place_rent_psf`, `market_rent_psf`, `initial_occupancy`, `opex_start`, `debt_ratio`, `interest_rate` | Rent ↑→ CoC ↑, OpEx ↑→ CoC ↓, Interest ↑→ CoC ↓ | (NOI - Debt Service) / Equity |
| **EquityMultiple** | All cash flow drivers, `exit_cap_range`, hold period | Cash flow ↑→ EM ↑, Exit cap ↓→ EM ↑ | Total cash returned / Equity invested |

### Risk & Operations Metrics  
| Metric | Related Inputs | Expected Direction | Formula/Logic |
|--------|---------------|-------------------|---------------|
| **DSCR** | `opex_start`, `opex_growth`, `property_tax_rate`, `debt_ratio`, `interest_rate` | OpEx ↑→ DSCR ↓, Tax ↑→ DSCR ↓, Interest ↑→ DSCR ↓ | NOI / Debt Service |
| **LTV** | `debt_ratio`, `purchase_price`, property appreciation | Debt ratio ↑→ LTV ↑, Property value ↑→ LTV ↓ | Loan Balance / Property Value |
| **DebtYield_Y1** | `opex_start`, `property_tax_rate`, `debt_ratio` | NOI drivers ↑→ Debt Yield ↑, Debt ↑→ Debt Yield ↓ | NOI / Loan Balance |
| **BreakEvenOcc** | `opex_start`, `property_tax_rate`, `debt_ratio`, `interest_rate`, `market_rent_psf` | OpEx ↑→ Breakeven ↑, Rent ↑→ Breakeven ↓ | (OpEx + Tax + Debt Service) / Gross Rent |
| **YieldOnCost** | `purchase_price`, `acq_cost_rate`, `financing_fee_rate`, NOI | Total cost ↑→ YoC ↓, NOI ↑→ YoC ↑ | NOI / Total Investment |

### Occupancy & Leasing Metrics
| Metric | Related Inputs | Expected Direction | Formula/Logic |
|--------|---------------|-------------------|---------------|
| **OccupancyRate** | `initial_occupancy`, `vacancy_auto_lease`, `downtime_months`, `renew_prob` | Initial occ ↑→ Avg occ ↑, Auto-lease=true→ Occ ↑ | Weighted average occupancy |
| **TenantTurnoverRate** | `renew_prob`, `walt_years`, `downtime_months` | Renewal prob ↑→ Turnover ↓, WALT ↑→ Turnover ↓ | (1 - Renewal Rate) adjusted for lease terms |
| **LeaseRenewalRate** | `renew_prob`, lease spread attractiveness | Renewal prob ↑→ Renewal rate ↑ | Renewals / Total lease events |
| **AvgRentPricePSF** | `in_place_rent_psf`, `market_rent_psf`, `market_rent_growth_min/max` | Market rent ↑→ Avg rent ↑, Growth ↑→ Avg rent ↑ | Weighted average rent across portfolio |

### Financial Structure Metrics
| Metric | Related Inputs | Expected Direction | Formula/Logic |
|--------|---------------|-------------------|---------------|
| **DebtToEquityRatio** | `debt_ratio` | Debt ratio ↑→ D/E ↑ | Debt / (Total Value - Debt) |
| **PriceToRentRatio** | `purchase_price`, current rent levels | Purchase price ↑→ P/R ↑, Rent ↑→ P/R ↓ | Purchase Price / Annual Rent |
| **GrossRentalYield** | `purchase_price`, rent levels | Purchase price ↑→ Yield ↓, Rent ↑→ Yield ↑ | Annual Rent / Purchase Price |
| **RentToCostRatio** | Total investment cost, rent levels | Cost ↑→ Ratio ↓, Rent ↑→ Ratio ↑ | Annual Rent / Total Cost |

### REIT & Investment Metrics
| Metric | Related Inputs | Expected Direction | Formula/Logic |
|--------|---------------|-------------------|---------------|
| **FFO** | NOI, depreciation, gains on sales | NOI ↑→ FFO ↑ | NOI + Depreciation - Gains |
| **AFFO** | FFO, `capex_schedule`, maintenance capex | FFO ↑→ AFFO ↑, CapEx ↑→ AFFO ↓ | FFO - Recurring CapEx |
| **NAV** | Property value, debt balance | Property value ↑→ NAV ↑, Debt ↑→ NAV ↓ | Assets - Liabilities |
| **FFO_PayoutRatio** | FFO, cash distributions | FFO ↑→ Payout ratio ↓ (if distributions fixed) | Distributions / FFO |
| **ReturnOnCost** | Total development/acquisition cost, NOI | Cost ↑→ ROC ↓, NOI ↑→ ROC ↑ | NOI / Total Cost |

### Cost & Construction Metrics
| Metric | Related Inputs | Expected Direction | Formula/Logic |
|--------|---------------|-------------------|---------------|
| **ConstructionCostPSF** | `ti_psf_new`, `ti_psf_renew`, `capex_schedule`, `total_rsf` | TI costs ↑→ Construction cost ↑ | Total construction costs / RSF |
| **AvgCommissionPerSale** | `sale_cost_rate`, exit value | Sale cost rate ↑→ Commission ↑, Exit value ↑→ Commission ↑ | Sale Cost Rate × Sale Price |

### 50% Rule Metrics
| Metric | Related Inputs | Expected Direction | Formula/Logic |
|--------|---------------|-------------------|---------------|
| **FiftyPercentRule_Ratio** | `opex_start`, `property_tax_rate`, `capex_schedule`, gross income | OpEx ↑→ Ratio ↑, Income ↑→ Ratio ↓ | (OpEx + Tax + CapEx) / Gross Income |
| **FiftyPercentRule_Pass** | Same as ratio | Ratio <50% → Pass=True, Ratio ≥50% → Pass=False | Boolean: Ratio < 0.50 |

### Prepayment & Defeasance Metrics
| Metric | Related Inputs | Expected Direction | Formula/Logic |
|--------|---------------|-------------------|---------------|
| **Prepay_Cost_Total** | `prepay.model`, `prepay.stepdown`, `prepay.fees_bps` | Model=stepdown→ Lower cost, Higher fees→ Higher cost | Based on prepayment model selected |
| **Defeasance_Cost_Refi** | `prepay.rf_flat_rate`, `prepay.ym_spread`, remaining term | RF rate ↑→ Cost varies, Spread ↑→ Cost ↑ | Defeasance calculation |

## Input Categories

### Property Fundamentals
- `purchase_price`: Affects all return metrics, ratios, leverage metrics
- `total_rsf`: Affects per-SF calculations, construction costs
- `in_place_rent_psf`, `market_rent_psf`: Primary revenue drivers
- `initial_occupancy`: Affects initial cash flows, occupancy metrics

### Operating Parameters  
- `opex_start`, `opex_growth_rate`: Affects NOI, DSCR, cash flows
- `property_tax_rate`, `tax_growth_rate`: Affects NOI, breakeven calculations
- `controllable_opex_pct`: Affects recovery calculations

### Financing Structure
- `debt_ratio`: Affects leverage, DSCR, LTV, cash-on-cash
- `interest_rate`: Affects debt service, DSCR, cash flows
- `amort_years`: Affects debt service calculation

### Leasing Assumptions
- `renew_prob`: Affects turnover, renewal rates
- `walt_years`: Affects lease rollover timing
- `downtime_months`: Affects vacancy costs, occupancy
- `ti_psf_new`, `ti_psf_renew`: Affects leasing costs

### Exit Assumptions
- `exit_cap_left`, `exit_cap_right`, `exit_cap_mode`: Affects terminal value, IRR
- `sale_cost_rate`: Affects net sale proceeds
- `transfer_tax_sell_rate`: Affects transaction costs

### Growth Parameters
- `market_rent_growth_min`, `market_rent_growth_max`: Affects rent escalation
- `rent_spread_std`: Affects rent variability
- `renewal_spread_std`: Affects renewal rent spreads

## Expected Cross-Correlations

**Positively Correlated Metrics:**
- IRR ↔ NPV ↔ CoC (all benefit from higher NOI)
- DSCR ↔ DebtYield (both measure debt coverage)
- OccupancyRate ↔ LeaseRenewalRate (good leasing performance)

**Negatively Correlated Metrics:**
- BreakEvenOcc ↔ DSCR (higher breakeven = lower coverage)
- TenantTurnoverRate ↔ LeaseRenewalRate (inverse relationship)
- LTV ↔ DSCR (higher leverage = lower coverage)

**Should Be Relatively Independent:**
- ConstructionCostPSF ↔ Market performance metrics
- WALT ↔ Financial returns (timing vs performance)
