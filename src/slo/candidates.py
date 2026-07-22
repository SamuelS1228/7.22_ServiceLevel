"""Candidate generation for dealer-by-policy optimization choices."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .io import ModelData
from .service_model import adjusted_stock_units, poisson_fill_rate


def _weighted_average(values: np.ndarray, weights: np.ndarray) -> float:
    total_weight = float(np.sum(weights))
    if total_weight <= 0:
        return 1.0
    return float(np.average(values, weights=weights))


def build_candidates(data: ModelData) -> pd.DataFrame:
    """Build every enabled dealer-policy candidate and calculate its economics.

    Candidate metrics are intentionally precomputed before optimization so the
    solver remains a transparent mixed-integer linear program.
    """
    working_days = float(data.model_parameters["working_days_per_year"])
    weeks = float(data.model_parameters["weeks_per_year"])
    carrying_rate = float(data.model_parameters["inventory_carrying_rate"])

    options = data.service_options.copy()
    options = options.loc[pd.to_numeric(options["enabled"]).astype(int) == 1].copy()
    rates = data.transport_rates.copy()
    rate_lookup = rates.set_index(["dealer_id", "transport_mode"])

    demand = data.dealer_part_demand.copy()
    demand["dealer_id"] = demand["dealer_id"].astype(str)
    demand["critical_flag"] = pd.to_numeric(demand["critical_flag"]).astype(int)

    rows: list[dict[str, float | str | int]] = []
    for dealer in data.dealers.itertuples(index=False):
        dealer_id = str(dealer.dealer_id)
        dealer_demand = demand.loc[demand["dealer_id"] == dealer_id].copy()
        annual_demand_units = float(dealer_demand["annual_demand_units"].sum())
        annual_weight_lb = float(
            (dealer_demand["annual_demand_units"] * dealer_demand["unit_weight_lb"]).sum()
        )
        baseline_inventory_value = float(
            (dealer_demand["target_stock_units"] * dealer_demand["unit_cost"]).sum()
        )
        critical_demand_units = float(
            dealer_demand.loc[dealer_demand["critical_flag"] == 1, "annual_demand_units"].sum()
        )

        for option in options.itertuples(index=False):
            mode = str(option.transport_mode)
            rate = rate_lookup.loc[(dealer_id, mode)]
            deliveries_per_year = float(option.deliveries_per_week) * weeks
            review_period_days = (
                working_days / deliveries_per_year if deliveries_per_year > 0 else working_days
            )
            protection_period_days = review_period_days + float(option.transit_days)

            part_fill_rates: list[float] = []
            part_weights: list[float] = []
            critical_fill_rates: list[float] = []
            critical_weights: list[float] = []
            incremental_inventory = 0.0
            recommended_inventory_value = 0.0

            for part in dealer_demand.itertuples(index=False):
                daily_demand = float(part.annual_demand_units) / working_days
                mean_protection_demand = daily_demand * protection_period_days
                stock_units = adjusted_stock_units(
                    part.target_stock_units, option.inventory_uplift_pct
                )
                fill_rate = poisson_fill_rate(mean_protection_demand, stock_units)
                weight = float(part.annual_demand_units)
                part_fill_rates.append(fill_rate)
                part_weights.append(weight)
                recommended_inventory_value += stock_units * float(part.unit_cost)
                incremental_inventory += max(
                    stock_units - float(part.target_stock_units), 0.0
                ) * float(part.unit_cost)
                if int(part.critical_flag) == 1:
                    critical_fill_rates.append(fill_rate)
                    critical_weights.append(weight)

            dealer_fill_rate = _weighted_average(
                np.asarray(part_fill_rates), np.asarray(part_weights)
            )
            critical_fill_rate = _weighted_average(
                np.asarray(critical_fill_rates), np.asarray(critical_weights)
            )

            annual_transport_cost = (
                deliveries_per_year * float(rate["fixed_cost_per_delivery"])
                + annual_weight_lb * float(rate["variable_cost_per_lb"])
            )
            annual_order_lines = float(dealer_demand["annual_order_lines"].sum()) * float(
                option.consolidation_line_factor
            )
            annual_labor_hours = (
                annual_order_lines * float(option.line_labor_minutes)
                + deliveries_per_year * float(option.shipment_fixed_labor_minutes)
            ) / 60.0
            annual_inventory_carrying_cost = incremental_inventory * carrying_rate
            annual_implementation_cost = float(option.annual_implementation_cost_per_dealer)

            rows.append(
                {
                    "dealer_id": dealer_id,
                    "dealer_name": str(dealer.dealer_name),
                    "pdc_id": str(dealer.pdc_id),
                    "dealer_group": str(dealer.dealer_group),
                    "current_option_id": str(dealer.current_option_id),
                    "implementation_locked": int(dealer.implementation_locked),
                    "dealer_min_fill_rate": float(dealer.min_fill_rate),
                    "dealer_min_critical_fill_rate": float(dealer.min_critical_fill_rate),
                    "dealer_min_deliveries_per_week": float(dealer.min_deliveries_per_week),
                    "option_id": str(option.option_id),
                    "option_name": str(option.option_name),
                    "scenario_class": str(option.scenario_class),
                    "deliveries_per_week": float(option.deliveries_per_week),
                    "deliveries_per_year": deliveries_per_year,
                    "transport_mode": mode,
                    "inventory_uplift_pct": float(option.inventory_uplift_pct),
                    "implementation_complexity_score": float(
                        option.implementation_complexity_score
                    ),
                    "protection_period_days": protection_period_days,
                    "modeled_fill_rate": dealer_fill_rate,
                    "modeled_critical_fill_rate": critical_fill_rate,
                    "annual_demand_units": annual_demand_units,
                    "annual_critical_demand_units": critical_demand_units,
                    "annual_weight_lb": annual_weight_lb,
                    "annual_transport_cost": annual_transport_cost,
                    "annual_labor_hours": annual_labor_hours,
                    "baseline_inventory_value": baseline_inventory_value,
                    "recommended_inventory_value": recommended_inventory_value,
                    "incremental_inventory_investment": incremental_inventory,
                    "annual_inventory_carrying_cost": annual_inventory_carrying_cost,
                    "annual_implementation_cost": annual_implementation_cost,
                    "annual_nonlabor_cost": annual_transport_cost
                    + annual_inventory_carrying_cost
                    + annual_implementation_cost,
                    "is_current_option": int(str(option.option_id) == str(dealer.current_option_id)),
                    "is_structural_option": int(str(option.scenario_class).lower() == "structural"),
                }
            )

    candidates = pd.DataFrame(rows)
    candidates.sort_values(["dealer_id", "option_id"], inplace=True, ignore_index=True)
    return candidates
