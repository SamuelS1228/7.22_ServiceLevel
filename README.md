# Service Level Optimization Solver

A complete mixed-integer optimization package for evaluating dealer stock-order service policies. The model selects one policy per dealer to minimize controllable annual cost while protecting dealer-level and network-level service, PDC labor capacity, overtime limits, inventory investment, implementation complexity, and dealer-group consolidation rules.

The package includes:

- Eight dummy upload files with realistic dealer, part-demand, transport, labor, and scenario structures
- A transparent candidate-generation engine
- A SciPy/HiGHS mixed-integer linear program
- Four example scenarios: baseline, marginal, significant, and structural
- Dealer-, PDC-, group-, and scenario-level outputs
- A Streamlit upload interface
- Automated unit and integration tests
- Windows PowerShell and batch launchers

## 1. Decision the solver makes

For each dealer `d`, the solver selects exactly one policy option `o`:

- Delivery frequency
- Transportation mode
- Inventory uplift
- Warehouse processing method
- Implementation complexity

The candidate options included in the dummy files are:

1. Current daily dedicated delivery service
2. Daily delivery with an earlier order cutoff and lower warehouse labor
3. Three deliveries per week using dedicated delivery
4. Three deliveries per week with a 15% inventory uplift
5. Two deliveries per week using LTL
6. Two deliveries per week with a 25% inventory uplift
7. Weekly dealer-group consolidation using LTL and a 50% inventory uplift

Real options can be added by inserting rows in `service_options.csv`; no solver-code change is required.

## 2. Objective function

The solver minimizes:

`transport cost + inventory carrying cost + implementation cost + controllable regular labor cost + overtime labor cost - dealer-group consolidation savings`

Only the avoidable portion of regular warehouse labor is included in the controllable cost objective. Overtime is fully variable. This distinction is controlled by `avoidable_regular_labor_pct` in `pdc_capacity.csv`.

## 3. Constraints

The MILP enforces:

- Exactly one policy per dealer
- Dealer-level minimum off-the-shelf fill
- Dealer-level minimum critical-part fill
- Network weighted-average fill target
- Network weighted-average critical-part fill target
- Dealer-specific minimum delivery frequency
- PDC regular labor capacity
- PDC overtime capacity
- Maximum percent of dealers changed
- Maximum incremental dealer inventory investment
- Maximum option implementation complexity
- Locked dealers remain on their current policy
- Structural group policies are all-or-none when requested

## 4. Service calculation

For each dealer-part-policy candidate:

1. Convert annual demand to average business-day demand.
2. Calculate the protection period:

   `review period + transportation transit time`

3. Apply the option's inventory uplift to the current target stock.
4. Assume demand during the protection period follows a Poisson distribution.
5. Calculate expected shortage:

   `E[(D-S)+] = λ × P(D ≥ S) - S × P(D > S)`

6. Calculate unit fill rate:

   `fill rate = 1 - expected shortage / expected demand`

Dealer fill is annual-demand-weighted across parts. Critical fill is weighted only across parts flagged as critical.

### Important modeling limitation

The Poisson formulation is appropriate as a first-pass model for independent, relatively low-frequency parts demand. It should be replaced or extended where demand is highly intermittent, overdispersed, seasonal, supersession-driven, or dependent on fleet campaigns. The candidate architecture is unchanged if a negative-binomial, empirical-bootstrap, or Monte Carlo service engine is substituted.

## 5. Input files

Place all eight CSV files in one directory using the exact names below:

| File | Purpose |
|---|---|
| `dealers.csv` | Dealer-to-PDC mapping, service floors, current policy, and implementation locks |
| `dealer_part_demand.csv` | Dealer-part demand, order lines, weight, cost, stock, and criticality |
| `service_options.csv` | Candidate service policies and operational assumptions |
| `transport_rates.csv` | Dealer-mode fixed and variable transportation rates |
| `pdc_capacity.csv` | PDC labor capacity, labor rates, and avoidability |
| `dealer_groups.csv` | Structural consolidation rules and group savings |
| `optimization_scenarios.csv` | Scenario-specific option scope and guardrails |
| `model_parameters.csv` | Global calendar and carrying-cost assumptions |

See `DATA_DICTIONARY.md` for field definitions and validation rules.

## 6. Run from the command line

### Standard setup

```powershell
cd service_level_optimizer
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run_solver.py --input-dir inputs --output-dir outputs
```

Run only selected scenarios:

```powershell
python run_solver.py --input-dir inputs --output-dir outputs --scenario baseline --scenario significant
```

Regenerate the deterministic dummy inputs:

```powershell
python generate_dummy_inputs.py --output-dir inputs
```

### One-command Windows launchers

PowerShell:

```powershell
.\run_solver.ps1
```

Command Prompt:

```bat
run_solver.bat
```

## 7. Run the upload application

```powershell
streamlit run app.py
```

Upload the eight CSVs. The app validates the package, lets the user select scenarios, solves the model, displays the scenario comparison, and produces a downloadable results ZIP.

## 8. Outputs

Top-level outputs:

- `scenario_comparison.csv`: executive comparison across scenarios
- `all_candidate_options.csv`: every evaluated dealer-policy candidate
- `validation_report.json`: validation warnings and errors

Each scenario folder contains:

- `dealer_recommendations.csv`: current versus recommended policy by dealer
- `selected_candidates.csv`: solver-selected candidate rows
- `pdc_summary.csv`: capacity, regular hours, overtime, and labor cost
- `dealer_group_summary.csv`: structural-policy activation and group savings
- `scenario_summary.csv`
- `scenario_summary.json`

## 9. Recommended real-data mapping

The dummy files are deliberately normalized. The cleaned EasyMorph outputs should map to the following minimum grain:

- Dealer master: one row per dealer
- Dealer-part demand: one row per dealer-part for the modeling period
- Transportation rates: one row per dealer-mode
- PDC capacity: one row per PDC
- Service options: one row per policy design
- Scenario controls: one row per scenario

The part-demand input should use trailing annualized demand and order-line volume. If the project uses trailing 2026 data for a partial year, annualize only after correcting for working days, dealer openings/closures, and known demand discontinuities.

## 10. Validation checks before client use

Required checks:

1. Reconcile dealer-part annual units and sales dollars to source-system totals.
2. Reconcile modeled current-policy transportation cost to 2026 actual spend by PDC and mode.
3. Reconcile current-policy labor hours to actual paid regular and overtime hours.
4. Compare modeled baseline fill to reported dealer off-the-shelf fill.
5. Back-test policy changes on historical weekly demand.
6. Stress-test service under demand at the 75th, 90th, and 95th percentiles.
7. Test transportation rates for minimum charges, weight breaks, route fixed costs, fuel, and accessorials.
8. Separate operationally avoidable cost from accounting cost.
9. Review recommendations with dealer operations before interpreting modeled savings as realizable.
10. Run sensitivity cases for carrying rate, service floors, transit time, labor avoidability, and demand volatility.

## 11. Model extensions

The current structure can scale to:

- Dealer-day delivery calendars
- Route activation and stop sequencing
- Parcel/LTL/DDS mode splits by part or shipment
- Order-type differentiation
- PDC shift and day-of-week capacity
- Parts supersession chains
- Dealer inventory budget by group
- Repair-order completion constraints
- Demand scenarios and robust optimization
- Piecewise labor and transportation rates
- Multi-period implementation sequencing

The strongest next extension for this assessment is a Monte Carlo service engine using dealer-part weekly demand history. It would produce candidate fill distributions and downside percentiles, which can be passed into the same MILP as deterministic candidate coefficients.
