"""
Metrics specification tests - verify correctness of ui_metrics.py functions.

Each test independently recomputes metrics using direct pandas operations
and compares with ui_metrics.py function outputs using assert math.isclose().

Tests include:
- IRR statistics verification
- Return value metrics verification  
- Risk operations metrics verification
- Covenant minima verification
- Prepay/defeasance verification
- Operational risk metrics verification
- Advanced financial metrics verification
- Financial ratios metrics verification
- 50% Rule metrics verification
- REIT investment metrics verification
- Additional KPIs verification

Tests that require columns not available will be skipped with clear messages.
"""

import pytest
import math
import numpy as np
import pandas as pd
import ui_metrics


class TestIRRStats:
    """Test IRR statistics calculations."""
    
    def test_irr_stats_basic_calculation(self, df_base):
        """Test IRR stats calculation against independent computation."""
        if 'IRR' not in df_base.columns:
            pytest.skip("IRR column missing")
            
        # Independent calculation
        irr_series = pd.to_numeric(df_base['IRR'], errors='coerce').dropna()
        expected_mean = float(irr_series.mean())
        expected_median = float(irr_series.median())
        expected_p5 = float(np.percentile(irr_series, 5))
        expected_p50 = float(np.percentile(irr_series, 50))
        expected_p95 = float(np.percentile(irr_series, 95))
        expected_prob_ge_15 = float((irr_series >= 0.15).mean())
        
        # Function result
        result = ui_metrics.irr_stats(df_base)
        
        # Assertions
        assert math.isclose(result['mean'], expected_mean, rel_tol=1e-6)
        assert math.isclose(result['median'], expected_median, rel_tol=1e-6)
        assert math.isclose(result['p5'], expected_p5, rel_tol=1e-6)
        assert math.isclose(result['p50'], expected_p50, rel_tol=1e-6)
        assert math.isclose(result['p95'], expected_p95, rel_tol=1e-6)
        assert math.isclose(result['prob_ge_15'], expected_prob_ge_15, rel_tol=1e-6)
    
    def test_irr_stats_missing_column(self, df_base):
        """Test IRR stats with missing IRR column."""
        df_no_irr = df_base.drop(columns=['IRR'], errors='ignore')
        result = ui_metrics.irr_stats(df_no_irr)
        
        # All values should be NaN
        assert math.isnan(result['mean'])
        assert math.isnan(result['median'])
        assert math.isnan(result['p5'])
        assert math.isnan(result['p50'])
        assert math.isnan(result['p95'])
        assert math.isnan(result['prob_ge_15'])


class TestCapexAdjIRR:
    """Test CapEx-adjusted IRR calculations."""
    
    def test_capex_adj_irr_calculation(self, df_base):
        """Test CapEx-adjusted IRR calculation."""
        if 'IRR_CapexAdj' not in df_base.columns:
            pytest.skip("IRR_CapexAdj column missing")
            
        # Independent calculation
        capex_adj_series = pd.to_numeric(df_base['IRR_CapexAdj'], errors='coerce').dropna()
        expected_mean = float(capex_adj_series.mean())
        
        # Function result
        result = ui_metrics.capex_adj_irr_mean(df_base)
        
        # Assertion
        assert math.isclose(result, expected_mean, rel_tol=1e-6)
    
    def test_capex_adj_irr_missing_column(self, df_base):
        """Test CapEx-adjusted IRR with missing column."""
        df_no_capex = df_base.drop(columns=['IRR_CapexAdj'], errors='ignore')
        result = ui_metrics.capex_adj_irr_mean(df_no_capex)
        
        assert math.isnan(result)


class TestReturnValueMetrics:
    """Test return and value metrics calculations."""
    
    def test_return_value_metrics_basic(self, df_base):
        """Test return value metrics against independent computation."""
        required_cols = ['CoC', 'EquityMultiple', 'NPV']
        missing_cols = [col for col in required_cols if col not in df_base.columns]
        if missing_cols:
            pytest.skip(f"Missing columns: {missing_cols}")
        
        # Independent calculations
        coc_series = pd.to_numeric(df_base['CoC'], errors='coerce').dropna()
        em_series = pd.to_numeric(df_base['EquityMultiple'], errors='coerce').dropna()
        npv_series = pd.to_numeric(df_base['NPV'], errors='coerce').dropna()
        
        expected_coc_mean = float(coc_series.mean())
        expected_coc_p5 = float(np.percentile(coc_series, 5))
        expected_coc_p50 = float(np.percentile(coc_series, 50))
        expected_coc_p95 = float(np.percentile(coc_series, 95))
        
        expected_em_mean = float(em_series.mean())
        expected_npv_mean = float(npv_series.mean())
        
        # Function result
        result = ui_metrics.return_value_metrics(df_base)
        
        # Assertions
        assert math.isclose(result['coc_mean'], expected_coc_mean, rel_tol=1e-6)
        assert math.isclose(result['coc_p5'], expected_coc_p5, rel_tol=1e-6)
        assert math.isclose(result['coc_p50'], expected_coc_p50, rel_tol=1e-6)
        assert math.isclose(result['coc_p95'], expected_coc_p95, rel_tol=1e-6)
        assert math.isclose(result['equity_multiple_mean'], expected_em_mean, rel_tol=1e-6)
        assert math.isclose(result['npv_mean'], expected_npv_mean, rel_tol=1e-6)
    
    def test_pi_fallback_calculation(self, df_base):
        """Test PI fallback calculation when PI column missing but NPV and Equity available."""
        required_cols = ['NPV', 'Equity']
        missing_cols = [col for col in required_cols if col not in df_base.columns]
        if missing_cols:
            pytest.skip(f"Missing columns for PI fallback: {missing_cols}")
        
        # Create DataFrame without PI column
        df_no_pi = df_base.drop(columns=['PI'], errors='ignore')
        
        # Independent PI calculation: PI = (NPV + Equity) / Equity
        npv_series = pd.to_numeric(df_no_pi['NPV'], errors='coerce')
        equity_series = pd.to_numeric(df_no_pi['Equity'], errors='coerce')
        
        # Calculate PI manually
        pi_manual = (npv_series + equity_series) / equity_series
        pi_manual = pi_manual.replace([np.inf, -np.inf], np.nan).dropna()
        expected_pi_mean = float(pi_manual.mean())
        
        # Function result
        result = ui_metrics.return_value_metrics(df_no_pi)
        
        # Assertion
        assert math.isclose(result['pi_mean'], expected_pi_mean, rel_tol=1e-6)


class TestRiskOpsMetrics:
    """Test risk and operations metrics calculations."""
    
    def test_risk_ops_basic_metrics(self, df_base):
        """Test basic risk operations metrics."""
        if 'YieldOnCost' not in df_base.columns:
            pytest.skip("YieldOnCost column missing")
        
        # Independent calculation
        yoc_series = pd.to_numeric(df_base['YieldOnCost'], errors='coerce').dropna()
        expected_yoc_mean = float(yoc_series.mean())
        
        # Function result
        result = ui_metrics.risk_ops_metrics(df_base)
        
        # Assertion
        assert math.isclose(result['yoc_mean'], expected_yoc_mean, rel_tol=1e-6)
    
    def test_dscr_fallback(self, df_base):
        """Test DSCR fallback from DSCR_Y1 to DSCR when Y1 not available."""
        if 'DSCR' not in df_base.columns:
            pytest.skip("DSCR column missing")
        
        # Create DataFrame without DSCR_Y1
        df_no_y1 = df_base.drop(columns=['DSCR_Y1'], errors='ignore')
        
        # Independent calculation using DSCR fallback
        dscr_series = pd.to_numeric(df_no_y1['DSCR'], errors='coerce').dropna()
        expected_dscr_mean = float(dscr_series.mean())
        
        # Function result
        result = ui_metrics.risk_ops_metrics(df_no_y1)
        
        # Assertion
        assert math.isclose(result['dscr_y1_mean'], expected_dscr_mean, rel_tol=1e-6)
    
    def test_stable_all_years_percentage(self, df_base):
        """Test RunStableAllYears percentage calculation."""
        if 'RunStableAllYears' not in df_base.columns:
            pytest.skip("RunStableAllYears column missing")
        
        # Independent calculation
        stable_series = pd.to_numeric(df_base['RunStableAllYears'], errors='coerce').dropna()
        expected_pct = float((stable_series == True).mean() * 100.0)
        
        # Function result
        result = ui_metrics.risk_ops_metrics(df_base)
        
        # Assertion
        assert math.isclose(result['run_stable_all_years_pct'], expected_pct, rel_tol=1e-6)


class TestCovenantMinima:
    """Test covenant minima calculations."""
    
    def test_min_dscr_fallback_priority(self, df_base):
        """Test MinDSCR fallback priority."""
        # Test that function tries MinDSCR first, then falls back to DSCR
        priority_cols = ["MinDSCR", "DSCR_Min", "min_dscr", "mindscr", "DSCR"]
        
        available_col = None
        for col in priority_cols:
            if col in df_base.columns:
                available_col = col
                break
        
        if available_col is None:
            pytest.skip("No DSCR columns available")
        
        # Independent calculation using the first available column
        dscr_series = pd.to_numeric(df_base[available_col], errors='coerce').dropna()
        expected_mean = float(dscr_series.mean())
        
        # Function result
        result = ui_metrics.covenant_minima(df_base)
        
        # Assertion
        assert math.isclose(result['min_dscr_mean'], expected_mean, rel_tol=1e-6)
    
    def test_debt_yield_percentage_conversion(self, df_base):
        """Test debt yield percentage conversion."""
        # Find available debt yield column
        dy_cols = ["MinDebtYield", "DebtYield_Min", "min_dy", "mindebtyield", "DebtYield_Y1"]
        
        available_col = None
        for col in dy_cols:
            if col in df_base.columns:
                available_col = col
                break
        
        if available_col is None:
            pytest.skip("No debt yield columns available")
        
        # Independent calculation (convert to percentage)
        dy_series = pd.to_numeric(df_base[available_col], errors='coerce').dropna()
        expected_pct = float(dy_series.mean() * 100.0)
        
        # Function result
        result = ui_metrics.covenant_minima(df_base)
        
        # Assertion
        assert math.isclose(result['min_dy_mean_pct'], expected_pct, rel_tol=1e-6)


class TestPrepayDefeasance:
    """Test prepayment and defeasance metrics."""
    
    def test_defeasance_usage_percentage(self, df_base):
        """Test defeasance usage percentage calculation."""
        if 'Defeasance_Used' not in df_base.columns:
            pytest.skip("Defeasance_Used column missing")
        
        # Independent calculation
        def_series = pd.to_numeric(df_base['Defeasance_Used'], errors='coerce').dropna()
        expected_pct = float((def_series == True).mean() * 100.0)
        
        # Function result
        result = ui_metrics.prepay_defeasance(df_base)
        
        # Assertion
        assert math.isclose(result['defeasance_used_pct'], expected_pct, rel_tol=1e-6)
    
    def test_defeasance_cost_when_used(self, df_base):
        """Test average defeasance cost when used."""
        required_cols = ['Defeasance_Used', 'Defeasance_Cost_Refi']
        missing_cols = [col for col in required_cols if col not in df_base.columns]
        if missing_cols:
            pytest.skip(f"Missing columns: {missing_cols}")
        
        # Independent calculation
        used_mask = (pd.to_numeric(df_base['Defeasance_Used'], errors='coerce') == True)
        if used_mask.sum() == 0:
            pytest.skip("No defeasance usage in data")
        
        cost_when_used = pd.to_numeric(df_base.loc[used_mask, 'Defeasance_Cost_Refi'], errors='coerce')
        expected_cost = float(cost_when_used.mean())
        
        # Function result
        result = ui_metrics.prepay_defeasance(df_base)
        
        # Assertion
        assert math.isclose(result['avg_def_cost_when_used'], expected_cost, rel_tol=1e-6)
    
    def test_prepay_sale_usage_cost_method(self, df_base):
        """Test prepay at sale usage using cost > 0 method."""
        if 'Prepay_Cost_Sale' not in df_base.columns:
            pytest.skip("Prepay_Cost_Sale column missing")
        
        # Independent calculation
        cost_series = pd.to_numeric(df_base['Prepay_Cost_Sale'], errors='coerce')
        expected_pct = float((cost_series > 1e-6).mean() * 100.0)
        
        # Function result
        result = ui_metrics.prepay_defeasance(df_base)
        
        # Assertion
        assert math.isclose(result['prepay_sale_used_pct'], expected_pct, rel_tol=1e-6)


class TestOperationalRiskMetrics:
    """Test operational and risk metrics calculations."""
    
    def test_goi_percentiles(self, df_base):
        """Test GOI percentile calculations."""
        if 'GOI' not in df_base.columns:
            pytest.skip("GOI column missing")
        
        # Independent calculation
        goi_series = pd.to_numeric(df_base['GOI'], errors='coerce').dropna()
        expected_p5 = float(np.percentile(goi_series, 5))
        expected_p50 = float(np.percentile(goi_series, 50))
        expected_p95 = float(np.percentile(goi_series, 95))
        
        # Function result
        result = ui_metrics.operational_risk_metrics(df_base)
        
        # Assertions
        assert math.isclose(result['goi_p5'], expected_p5, rel_tol=1e-6)
        assert math.isclose(result['goi_p50'], expected_p50, rel_tol=1e-6)
        assert math.isclose(result['goi_p95'], expected_p95, rel_tol=1e-6)
    
    def test_revenue_growth_percentiles(self, df_base):
        """Test revenue growth percentile calculations."""
        if 'RevenueGrowth_YoY' not in df_base.columns:
            pytest.skip("RevenueGrowth_YoY column missing")
        
        # Independent calculation
        rev_series = pd.to_numeric(df_base['RevenueGrowth_YoY'], errors='coerce').dropna()
        expected_p50 = float(np.percentile(rev_series, 50))
        
        # Function result
        result = ui_metrics.operational_risk_metrics(df_base)
        
        # Assertion
        assert math.isclose(result['revenue_growth_p50'], expected_p50, rel_tol=1e-6)


class TestAdvancedFinancialMetrics:
    """Test advanced financial metrics calculations."""
    
    def test_ffo_percentiles(self, df_base):
        """Test FFO percentile calculations."""
        if 'FFO' not in df_base.columns:
            pytest.skip("FFO column missing")
        
        # Independent calculation
        ffo_series = pd.to_numeric(df_base['FFO'], errors='coerce').dropna()
        expected_p5 = float(np.percentile(ffo_series, 5))
        expected_p50 = float(np.percentile(ffo_series, 50))
        expected_p95 = float(np.percentile(ffo_series, 95))
        
        # Function result
        result = ui_metrics.advanced_financial_metrics(df_base)
        
        # Assertions
        assert math.isclose(result['ffo_p5'], expected_p5, rel_tol=1e-6)
        assert math.isclose(result['ffo_p50'], expected_p50, rel_tol=1e-6)
        assert math.isclose(result['ffo_p95'], expected_p95, rel_tol=1e-6)
    
    def test_affo_nav_percentiles(self, df_base):
        """Test AFFO and NAV percentile calculations."""
        missing_cols = []
        if 'AFFO' not in df_base.columns:
            missing_cols.append('AFFO')
        if 'NAV' not in df_base.columns:
            missing_cols.append('NAV')
        
        if missing_cols:
            pytest.skip(f"Missing columns: {missing_cols}")
        
        # Independent calculations
        affo_series = pd.to_numeric(df_base['AFFO'], errors='coerce').dropna()
        nav_series = pd.to_numeric(df_base['NAV'], errors='coerce').dropna()
        
        expected_affo_p50 = float(np.percentile(affo_series, 50))
        expected_nav_p50 = float(np.percentile(nav_series, 50))
        
        # Function result
        result = ui_metrics.advanced_financial_metrics(df_base)
        
        # Assertions
        assert math.isclose(result['affo_p50'], expected_affo_p50, rel_tol=1e-6)
        assert math.isclose(result['nav_p50'], expected_nav_p50, rel_tol=1e-6)


class TestFinancialRatiosMetrics:
    """Test financial ratios metrics calculations."""
    
    def test_core_ratios_percentiles(self, df_base):
        """Test core financial ratios percentile calculations."""
        available_cols = []
        test_cols = ['PI', 'NetCashFlow', 'PriceToRentRatio', 'GrossRentalYield', 'DebtToEquityRatio']
        
        for col in test_cols:
            if col in df_base.columns:
                available_cols.append(col)
        
        if not available_cols:
            pytest.skip(f"None of the core ratio columns available: {test_cols}")
        
        # Function result
        result = ui_metrics.financial_ratios_metrics(df_base)
        
        # Test each available column
        for col in available_cols:
            series = pd.to_numeric(df_base[col], errors='coerce').dropna()
            expected_p50 = float(np.percentile(series, 50))
            
            # Map column name to result key
            if col == 'PI':
                assert math.isclose(result['pi_p50'], expected_p50, rel_tol=1e-6)
            elif col == 'NetCashFlow':
                assert math.isclose(result['net_cash_flow_p50'], expected_p50, rel_tol=1e-6)
            elif col == 'PriceToRentRatio':
                assert math.isclose(result['price_to_rent_p50'], expected_p50, rel_tol=1e-6)
            elif col == 'GrossRentalYield':
                assert math.isclose(result['gross_rental_yield_p50'], expected_p50, rel_tol=1e-6)
            elif col == 'DebtToEquityRatio':
                assert math.isclose(result['debt_to_equity_p50'], expected_p50, rel_tol=1e-6)


class TestFiftyPercentRuleMetrics:
    """Test 50% Rule metrics calculations."""
    
    def test_fifty_percent_ratio_percentiles(self, df_base):
        """Test 50% Rule ratio percentile calculations."""
        if 'FiftyPercentRule_Ratio' not in df_base.columns:
            pytest.skip("FiftyPercentRule_Ratio column missing")
        
        # Independent calculation
        ratio_series = pd.to_numeric(df_base['FiftyPercentRule_Ratio'], errors='coerce').dropna()
        expected_p5 = float(np.percentile(ratio_series, 5))
        expected_p50 = float(np.percentile(ratio_series, 50))
        expected_p95 = float(np.percentile(ratio_series, 95))
        
        # Function result
        result = ui_metrics.fifty_percent_rule_metrics(df_base)
        
        # Assertions
        assert math.isclose(result['fifty_percent_ratio_p5'], expected_p5, rel_tol=1e-6)
        assert math.isclose(result['fifty_percent_ratio_p50'], expected_p50, rel_tol=1e-6)
        assert math.isclose(result['fifty_percent_ratio_p95'], expected_p95, rel_tol=1e-6)
    
    def test_fifty_percent_pass_percentage(self, df_base):
        """Test 50% Rule pass percentage calculation."""
        if 'FiftyPercentRule_Pass' not in df_base.columns:
            pytest.skip("FiftyPercentRule_Pass column missing")
        
        # Independent calculation
        pass_series = pd.to_numeric(df_base['FiftyPercentRule_Pass'], errors='coerce').dropna()
        expected_pct = float((pass_series == True).mean() * 100.0)
        
        # Function result
        result = ui_metrics.fifty_percent_rule_metrics(df_base)
        
        # Assertion
        assert math.isclose(result['fifty_percent_pass_pct'], expected_pct, rel_tol=1e-6)


class TestREITInvestmentMetrics:
    """Test REIT and investment analysis metrics."""
    
    def test_ffo_payout_percentiles(self, df_base):
        """Test FFO Payout Ratio percentile calculations."""
        if 'FFO_PayoutRatio' not in df_base.columns:
            pytest.skip("FFO_PayoutRatio column missing")
        
        # Independent calculation
        ffo_payout_series = pd.to_numeric(df_base['FFO_PayoutRatio'], errors='coerce').dropna()
        expected_p5 = float(np.percentile(ffo_payout_series, 5))
        expected_p50 = float(np.percentile(ffo_payout_series, 50))
        expected_p95 = float(np.percentile(ffo_payout_series, 95))
        
        # Function result
        result = ui_metrics.reit_investment_metrics(df_base)
        
        # Assertions
        assert math.isclose(result['ffo_payout_p5'], expected_p5, rel_tol=1e-6)
        assert math.isclose(result['ffo_payout_p50'], expected_p50, rel_tol=1e-6)
        assert math.isclose(result['ffo_payout_p95'], expected_p95, rel_tol=1e-6)
    
    def test_return_on_cost_percentiles(self, df_base):
        """Test Return on Cost percentile calculations."""
        if 'ReturnOnCost' not in df_base.columns:
            pytest.skip("ReturnOnCost column missing")
        
        # Independent calculation
        roc_series = pd.to_numeric(df_base['ReturnOnCost'], errors='coerce').dropna()
        expected_p50 = float(np.percentile(roc_series, 50))
        
        # Function result
        result = ui_metrics.reit_investment_metrics(df_base)
        
        # Assertion
        assert math.isclose(result['return_on_cost_p50'], expected_p50, rel_tol=1e-6)
    
    def test_investment_rating_percentiles(self, df_base):
        """Test Investment Rating percentile calculations."""
        if 'InvestmentRating' not in df_base.columns:
            pytest.skip("InvestmentRating column missing")
        
        # Independent calculation
        rating_series = pd.to_numeric(df_base['InvestmentRating'], errors='coerce').dropna()
        expected_p50 = float(np.percentile(rating_series, 50))
        
        # Function result
        result = ui_metrics.reit_investment_metrics(df_base)
        
        # Assertion
        assert math.isclose(result['investment_rating_p50'], expected_p50, rel_tol=1e-6)
    
    def test_validity_percentages(self, df_base):
        """Test validity percentage calculations for REIT metrics."""
        if 'FFO_PayoutRatio' not in df_base.columns:
            pytest.skip("FFO_PayoutRatio column missing")
        
        # Independent calculation
        ffo_series = pd.to_numeric(df_base['FFO_PayoutRatio'], errors='coerce')
        expected_valid_pct = float((~ffo_series.isna()).mean() * 100.0)
        
        # Function result
        result = ui_metrics.reit_investment_metrics(df_base)
        
        # Assertion
        assert math.isclose(result['ffo_payout_valid_pct'], expected_valid_pct, rel_tol=1e-6)


class TestAdditionalKPIs:
    """Test additional KPI metrics calculations."""
    
    def test_grm_percentiles(self, df_base):
        """Test GRM percentile calculations."""
        if 'GRM' not in df_base.columns:
            pytest.skip("GRM column missing")
        
        # Independent calculation
        grm_series = pd.to_numeric(df_base['GRM'], errors='coerce').dropna()
        expected_p5 = float(np.percentile(grm_series, 5))
        expected_p50 = float(np.percentile(grm_series, 50))
        expected_p95 = float(np.percentile(grm_series, 95))
        
        # Function result
        result = ui_metrics.additional_kpis(df_base)
        
        # Assertions
        assert math.isclose(result['grm_p5'], expected_p5, rel_tol=1e-6)
        assert math.isclose(result['grm_p50'], expected_p50, rel_tol=1e-6)
        assert math.isclose(result['grm_p95'], expected_p95, rel_tol=1e-6)
    
    def test_oer_equity_to_value_percentiles(self, df_base):
        """Test OER and Equity-to-Value percentile calculations."""
        available_cols = []
        for col in ['OperatingExpenseRatio', 'EquityToValue']:
            if col in df_base.columns:
                available_cols.append(col)
        
        if not available_cols:
            pytest.skip("OperatingExpenseRatio and EquityToValue columns missing")
        
        # Function result
        result = ui_metrics.additional_kpis(df_base)
        
        # Test each available column
        for col in available_cols:
            series = pd.to_numeric(df_base[col], errors='coerce').dropna()
            expected_p50 = float(np.percentile(series, 50))
            
            if col == 'OperatingExpenseRatio':
                assert math.isclose(result['oer_p50'], expected_p50, rel_tol=1e-6)
            elif col == 'EquityToValue':
                assert math.isclose(result['equity_to_value_p50'], expected_p50, rel_tol=1e-6)
