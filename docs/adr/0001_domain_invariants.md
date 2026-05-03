# ADR-0001: Domain Invariants and API Stability

## Status
Accepted

## Context
The Monte Carlo real estate model requires strict mathematical and financial invariants to ensure correct calculations and reliable results. These invariants form the foundation of the system's correctness and must be preserved across all changes.

## Decision
We establish the following domain invariants and API stability guarantees for the Monte Carlo real estate model:

### Financial Calculation Invariants

#### 1. Debt Service Coverage Ratio (DSCR)
- **Formula**: `DSCR = NOI / Debt Service`
- **Invariant**: DSCR must be calculated using fresh NOI and debt service values
- **Sensitivity**: DSCR decreases when OpEx increases, tax increases, or debt service increases
- **Bounds**: DSCR > 0 when debt service exists

#### 2. Debt Yield
- **Formula**: `Debt Yield = NOI / Loan Amount`
- **Types**: Year-1 DY uses NOI_Y1/Loan_Origination, Min DY uses min(NOI_t/Loan_Balance_t)
- **Sensitivity**: Debt Yield decreases when OpEx or taxes increase (NOI decreases)
- **Bounds**: Debt Yield > 0 for performing assets

#### 3. Cash-on-Cash Return (CoC)
- **Formula**: `CoC = Year-1 Cash Flow to Equity / Initial Equity`
- **Invariant**: Must use fresh Year-1 cash flow calculation
- **Sensitivity**: CoC decreases when OpEx, taxes, or debt service increase
- **Bounds**: CoC can be negative for poor-performing investments

#### 4. Net Present Value (NPV)
- **Formula**: `NPV = ∑(Cash Flows / (1 + discount_rate)^t) - Initial Investment`
- **Sensitivity**: NPV increases with higher rents, decreases with higher costs
- **Type**: Can be positive or negative

#### 5. Profitability Index (PI)
- **Formula**: `PI = (NPV + Equity) / Equity = NPV/Equity + 1`
- **Invariant**: PI = 1 when NPV = 0
- **Bounds**: PI > 1 indicates positive NPV investment

### Lease Roll System Invariants

#### 1. Renewal Probability
- **Invariant**: `renew_prob` parameter must flow into renewal Bernoulli draws
- **Sensitivity**: Higher `renew_prob` → higher renewal rates, lower turnover rates
- **Bounds**: 0 ≤ renew_prob ≤ 1

#### 2. Recovery Type Consistency
- **GROSS**: Landlord pays all expenses, tenant pays base rent only
- **NNN**: Tenant pays pro-rata share of operating expenses and taxes
- **Invariant**: Recovery calculations must respect the specified recovery type

### Statistical Invariants

#### 1. Percentile Ordering
- **Invariant**: For all metrics, P5 ≤ P50 ≤ P95
- **Consistency**: P50 = median for all metrics

#### 2. Probability Bounds
- **Invariant**: All probability metrics ∈ [0, 1]
- **Examples**: prob_ge_15 for IRR, covenant breach probabilities

#### 3. Variance Requirements
- **Invariant**: Metrics should show variance across Monte Carlo runs
- **Threshold**: Variance > 1e-12 for non-constant scenarios
- **Detection**: Use variance_report() to identify constant metrics

### Data Type Invariants

#### 1. Numeric Outputs
- **Type**: All metric outputs must be Python floats or math.nan
- **Bounds**: No infinite values except in documented edge cases (e.g., division by zero)
- **Handling**: NaN for missing/invalid data, never raise exceptions

#### 2. DataFrame Structure
- **Input**: All metrics functions accept pandas DataFrame
- **Output**: Structured dictionaries with percentile statistics
- **Graceful Degradation**: Handle missing columns by returning NaN

### Performance Invariants

#### 1. Memory Usage
- **Constraint**: O(1) memory beyond input DataFrame
- **No Copying**: Avoid unnecessary data duplication
- **Large Datasets**: Handle 10,000+ rows efficiently

#### 2. Deterministic Results
- **Seeds**: All tests use fixed seeds from seed_registry
- **Reproducibility**: Same inputs + same seed = same outputs

## Public API Stability Guarantees

### Function Signatures (IMMUTABLE)
```python
# ui_metrics.py - These signatures cannot change without explicit approval
def irr_stats(df: pd.DataFrame) -> Dict[str, Any]
def return_value_metrics(df: pd.DataFrame) -> Dict[str, Any]
def risk_ops_metrics(df: pd.DataFrame) -> Dict[str, Any]
def covenant_minima(df: pd.DataFrame) -> Dict[str, Any]
# ... (all other public functions)

# rmc_model.py - Core functions are stable
def run_simulation(n: int = 1000, seed: int = None, params: dict = None, parallel: bool = False) -> pd.DataFrame
def default_params() -> dict
```

### Output Structure (STABLE)
- All metrics return dictionaries with percentile statistics: 'p5', 'p50', 'p95', 'mean'
- Key names are stable and cannot be changed without deprecation period
- New metrics can be added, existing ones cannot be removed

### Backward Compatibility
- New optional parameters allowed in `default_params()`
- New columns in simulation DataFrame allowed
- New metrics in ui_metrics.py allowed
- Breaking changes require ADR and version increment

## Testing Requirements

### Mandatory Tests
1. **Invariant Tests**: All mathematical invariants must have assertion-based tests
2. **Sensitivity Tests**: Input shocks must produce expected directional changes
3. **Property Tests**: Hypothesis tests for monotonicity, bounds, ordering
4. **Assertion Counting**: Tests with zero assertions are prohibited

### Test Coverage Requirements
- ui_metrics.py: ≥90% line coverage
- metrics_registry.py: ≥90% line coverage
- seed_registry.py: ≥90% line coverage

### Mutation Testing
- Target: ui_metrics.py and core financial helpers
- Threshold: ≥70% mutation score
- Tool: mutmut with pytest runner

## Consequences

### Benefits
1. **Correctness**: Mathematical invariants ensure accurate financial calculations
2. **Reliability**: API stability prevents breaking changes in dependent systems
3. **Maintainability**: Clear invariants guide development and testing
4. **Trust**: Rigorous testing framework prevents regression bugs

### Risks
1. **Flexibility**: Strict invariants may limit some implementation choices
2. **Performance**: Comprehensive testing may slow development
3. **Complexity**: Property-based testing adds complexity

### Mitigation
1. Use ADRs for any proposed changes to core invariants
2. Maintain comprehensive test suite with assertion counting
3. Regular mutation testing to verify test quality
4. Clear documentation of all invariants and their rationale

## Compliance Monitoring

### Automated Checks
- CI/CD pipeline enforces all invariants
- Pre-commit hooks prevent large undocumented changes
- Mutation testing runs on every merge to main

### Manual Reviews
- All changes to ui_metrics.py require code review
- Changes to rmc_model.py business logic require domain expert review
- ADR required for any changes to core invariants

## Related Documents
- [Contributing Guidelines](../CONTRIBUTING.md)
- [Testing Framework](../TESTING_FRAMEWORK_README.md)
- [API Documentation](../specs/)

---

**Authors**: Development Team  
**Date**: 2024-01-XX  
**Reviewers**: Domain Experts, QA Team
