# Data Dictionary

All percentages are expressed as decimals. For example, 97.5% is entered as `0.975`.

## `dealers.csv`

| Field | Type | Required | Definition |
|---|---:|---:|---|
| `dealer_id` | text | Yes | Unique dealer identifier |
| `dealer_name` | text | Yes | Dealer display name |
| `pdc_id` | text | Yes | Supplying PDC identifier; must exist in `pdc_capacity.csv` |
| `dealer_group` | text | Yes | Dealer ownership or consolidation group; must exist in `dealer_groups.csv` |
| `distance_miles` | numeric | No | Reference distance; not directly used when rates are already supplied |
| `min_fill_rate` | decimal | Yes | Minimum dealer modeled unit fill rate |
| `min_critical_fill_rate` | decimal | Yes | Minimum dealer modeled critical-part unit fill rate |
| `min_deliveries_per_week` | numeric | Yes | Hard minimum stock-order delivery frequency |
| `current_option_id` | text | Yes | Current service option; must exist in `service_options.csv` |
| `implementation_locked` | 0/1 | Yes | `1` prevents the solver from changing the dealer |

Primary key: `dealer_id`

## `dealer_part_demand.csv`

| Field | Type | Required | Definition |
|---|---:|---:|---|
| `dealer_id` | text | Yes | Dealer identifier |
| `part_id` | text | Yes | Part identifier |
| `annual_demand_units` | numeric | Yes | Annualized dealer demand units |
| `annual_order_lines` | numeric | Yes | Annualized stock-order lines |
| `unit_weight_lb` | numeric | Yes | Shipping weight per unit |
| `unit_cost` | numeric | Yes | Inventory value per unit |
| `target_stock_units` | numeric | Yes | Current target stock or modeled base-stock level |
| `critical_flag` | 0/1 | Yes | `1` identifies uptime-critical parts |

Primary key: `dealer_id + part_id`

Data-quality requirements:

- Demand and order lines must be nonnegative.
- Returns should not remain as negative demand rows.
- Superseded parts should be mapped to the active chain where practical.
- Part weight and cost should be populated or explicitly imputed.

## `service_options.csv`

| Field | Type | Required | Definition |
|---|---:|---:|---|
| `option_id` | text | Yes | Unique policy identifier |
| `option_name` | text | Yes | Policy description |
| `scenario_class` | text | Yes | `baseline`, `marginal`, `significant`, or `structural` |
| `deliveries_per_week` | numeric | Yes | Planned weekly stock-order delivery count |
| `transport_mode` | text | Yes | Must match a mode in `transport_rates.csv` |
| `inventory_uplift_pct` | decimal | Yes | Increase applied to current target stock |
| `transit_days` | numeric | Yes | Expected business-day transit time |
| `shipment_fixed_labor_minutes` | numeric | Yes | PDC labor per dispatched shipment |
| `line_labor_minutes` | numeric | Yes | PDC labor per order line |
| `consolidation_line_factor` | decimal | Yes | Multiplier applied to annual lines after consolidation |
| `annual_implementation_cost_per_dealer` | numeric | Yes | Annualized change-management or systems cost |
| `implementation_complexity_score` | numeric | Yes | Relative complexity used as a scenario eligibility guardrail |
| `enabled` | 0/1 | Yes | `1` makes the option available for candidate generation |

Primary key: `option_id`

## `transport_rates.csv`

| Field | Type | Required | Definition |
|---|---:|---:|---|
| `dealer_id` | text | Yes | Dealer identifier |
| `transport_mode` | text | Yes | Transportation mode |
| `fixed_cost_per_delivery` | numeric | Yes | Cost incurred for each delivery |
| `variable_cost_per_lb` | numeric | Yes | Cost applied to annual shipment weight |

Primary key: `dealer_id + transport_mode`

Current formula:

`annual transport cost = deliveries per year × fixed cost per delivery + annual weight × variable cost per lb`

For actual DDS route economics, replace or extend this input with route-level fixed costs and route-activation variables.

## `pdc_capacity.csv`

| Field | Type | Required | Definition |
|---|---:|---:|---|
| `pdc_id` | text | Yes | Unique PDC identifier |
| `regular_capacity_hours` | numeric | Yes | Annual regular labor hours available to the modeled activity |
| `max_overtime_hours` | numeric | Yes | Absolute annual overtime limit |
| `regular_hourly_cost` | numeric | Yes | Loaded regular labor rate |
| `overtime_hourly_cost` | numeric | Yes | Loaded overtime labor rate |
| `avoidable_regular_labor_pct` | decimal | Yes | Share of regular labor cost considered economically avoidable |

Primary key: `pdc_id`

## `dealer_groups.csv`

| Field | Type | Required | Definition |
|---|---:|---:|---|
| `dealer_group` | text | Yes | Group identifier |
| `enforce_all_or_none_structural` | 0/1 | Yes | `1` requires all dealers in the group to adopt or reject structural options together |
| `annual_group_consolidation_savings` | numeric | Yes | Fixed annual savings if the structural group policy is activated |

Primary key: `dealer_group`

## `optimization_scenarios.csv`

| Field | Type | Required | Definition |
|---|---:|---:|---|
| `scenario_id` | text | Yes | Unique scenario identifier |
| `scenario_name` | text | Yes | Scenario description |
| `allowed_scenario_classes` | text | Yes | Comma-separated eligible option classes |
| `network_min_fill_rate` | decimal | Yes | Demand-weighted network fill floor |
| `network_min_critical_fill_rate` | decimal | Yes | Critical-demand-weighted network fill floor |
| `max_dealers_changed_pct` | decimal | Yes | Maximum share of dealers that may change policy |
| `max_inventory_investment` | numeric | Yes | Maximum incremental inventory value |
| `allow_overtime` | 0/1 | Yes | Whether overtime variables may be positive |
| `max_pdc_overtime_pct` | decimal | Yes | Scenario OT cap as a share of regular capacity |
| `max_option_complexity` | numeric | Yes | Maximum eligible option complexity score |
| `solver_time_limit_sec` | numeric | Yes | HiGHS time limit |
| `mip_relative_gap` | decimal | Yes | Accepted relative optimality gap |

Primary key: `scenario_id`

## `model_parameters.csv`

| Parameter | Definition |
|---|---|
| `working_days_per_year` | Business days used to convert annual demand to daily demand |
| `weeks_per_year` | Weeks used to annualize delivery frequency |
| `inventory_carrying_rate` | Annual carrying cost applied to incremental inventory value |

Primary key: `parameter`
