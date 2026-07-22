"""Generate a deterministic dummy input package for the service-level optimizer."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import poisson


SEED = 20260722
WORKING_DAYS = 260
WEEKS = 52


def build_service_options() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "option_id": "CURRENT_DAILY",
                "option_name": "Current daily DDS",
                "scenario_class": "baseline",
                "deliveries_per_week": 5,
                "transport_mode": "DDS",
                "inventory_uplift_pct": 0.00,
                "transit_days": 1.0,
                "shipment_fixed_labor_minutes": 24,
                "line_labor_minutes": 2.15,
                "consolidation_line_factor": 1.00,
                "annual_implementation_cost_per_dealer": 0,
                "implementation_complexity_score": 0,
                "enabled": 1,
            },
            {
                "option_id": "DAILY_CUTOFF",
                "option_name": "Daily DDS with earlier cutoff",
                "scenario_class": "marginal",
                "deliveries_per_week": 5,
                "transport_mode": "DDS",
                "inventory_uplift_pct": 0.00,
                "transit_days": 1.0,
                "shipment_fixed_labor_minutes": 16,
                "line_labor_minutes": 2.00,
                "consolidation_line_factor": 0.98,
                "annual_implementation_cost_per_dealer": 1200,
                "implementation_complexity_score": 1,
                "enabled": 1,
            },
            {
                "option_id": "THREE_X_DDS",
                "option_name": "Three deliveries per week via DDS",
                "scenario_class": "significant",
                "deliveries_per_week": 3,
                "transport_mode": "DDS",
                "inventory_uplift_pct": 0.00,
                "transit_days": 1.2,
                "shipment_fixed_labor_minutes": 22,
                "line_labor_minutes": 1.95,
                "consolidation_line_factor": 0.94,
                "annual_implementation_cost_per_dealer": 2200,
                "implementation_complexity_score": 2,
                "enabled": 1,
            },
            {
                "option_id": "THREE_X_DDS_INV15",
                "option_name": "Three DDS deliveries with 15% inventory uplift",
                "scenario_class": "significant",
                "deliveries_per_week": 3,
                "transport_mode": "DDS",
                "inventory_uplift_pct": 0.15,
                "transit_days": 1.2,
                "shipment_fixed_labor_minutes": 22,
                "line_labor_minutes": 1.95,
                "consolidation_line_factor": 0.94,
                "annual_implementation_cost_per_dealer": 2500,
                "implementation_complexity_score": 2.5,
                "enabled": 1,
            },
            {
                "option_id": "TWO_X_LTL",
                "option_name": "Two deliveries per week via LTL",
                "scenario_class": "significant",
                "deliveries_per_week": 2,
                "transport_mode": "LTL",
                "inventory_uplift_pct": 0.00,
                "transit_days": 2.0,
                "shipment_fixed_labor_minutes": 28,
                "line_labor_minutes": 1.90,
                "consolidation_line_factor": 0.90,
                "annual_implementation_cost_per_dealer": 3500,
                "implementation_complexity_score": 3,
                "enabled": 1,
            },
            {
                "option_id": "TWO_X_LTL_INV25",
                "option_name": "Two LTL deliveries with 25% inventory uplift",
                "scenario_class": "significant",
                "deliveries_per_week": 2,
                "transport_mode": "LTL",
                "inventory_uplift_pct": 0.25,
                "transit_days": 2.0,
                "shipment_fixed_labor_minutes": 28,
                "line_labor_minutes": 1.90,
                "consolidation_line_factor": 0.90,
                "annual_implementation_cost_per_dealer": 4000,
                "implementation_complexity_score": 3,
                "enabled": 1,
            },
            {
                "option_id": "WEEKLY_CONSOLIDATED_INV50",
                "option_name": "Weekly consolidated LTL with 50% inventory uplift",
                "scenario_class": "structural",
                "deliveries_per_week": 1,
                "transport_mode": "LTL",
                "inventory_uplift_pct": 0.50,
                "transit_days": 2.5,
                "shipment_fixed_labor_minutes": 35,
                "line_labor_minutes": 1.80,
                "consolidation_line_factor": 0.82,
                "annual_implementation_cost_per_dealer": 7000,
                "implementation_complexity_score": 5,
                "enabled": 1,
            },
        ]
    )


def generate_inputs(output_dir: Path) -> None:
    rng = np.random.default_rng(SEED)
    output_dir.mkdir(parents=True, exist_ok=True)

    dealer_specs = [
        ("D001", "North Shore Truck", "PDC_EAST", "GROUP_A", 120, 3),
        ("D002", "Metro Fleet Center", "PDC_EAST", "GROUP_A", 55, 3),
        ("D003", "Granite State Commercial", "PDC_EAST", "GROUP_A", 165, 2),
        ("D004", "Pioneer Heavy Duty", "PDC_EAST", "GROUP_B", 240, 2),
        ("D005", "Hudson Valley Truck", "PDC_EAST", "GROUP_B", 310, 2),
        ("D006", "Capital District Fleet", "PDC_EAST", "GROUP_B", 390, 1),
        ("D007", "Lakeshore Commercial", "PDC_CENTRAL", "GROUP_C", 85, 3),
        ("D008", "Prairie Truck Center", "PDC_CENTRAL", "GROUP_C", 145, 2),
        ("D009", "River City Fleet", "PDC_CENTRAL", "GROUP_C", 225, 2),
        ("D010", "Heartland Heavy Duty", "PDC_CENTRAL", "GROUP_D", 315, 1),
        ("D011", "Ozark Commercial", "PDC_CENTRAL", "GROUP_D", 445, 1),
        ("D012", "Plains Equipment", "PDC_CENTRAL", "GROUP_D", 520, 1),
    ]

    dealers = []
    for idx, (dealer_id, name, pdc_id, group, distance, minimum_frequency) in enumerate(dealer_specs):
        min_fill = 0.955 if minimum_frequency >= 3 else (0.945 if minimum_frequency == 2 else 0.935)
        min_critical = 0.985 if minimum_frequency >= 2 else 0.975
        dealers.append(
            {
                "dealer_id": dealer_id,
                "dealer_name": name,
                "pdc_id": pdc_id,
                "dealer_group": group,
                "distance_miles": distance,
                "min_fill_rate": min_fill,
                "min_critical_fill_rate": min_critical,
                "min_deliveries_per_week": minimum_frequency,
                "current_option_id": "CURRENT_DAILY",
                "implementation_locked": 1 if dealer_id == "D002" else 0,
            }
        )
    dealers_df = pd.DataFrame(dealers)

    parts = []
    part_count = 30
    for dealer_idx, dealer in dealers_df.iterrows():
        demand_scale = 1.35 - 0.045 * dealer_idx
        for part_idx in range(1, part_count + 1):
            critical = 1 if part_idx <= 6 else 0
            base = rng.lognormal(mean=3.35 if critical else 2.85, sigma=0.62)
            annual_demand = max(2, int(round(base * demand_scale)))
            unit_cost = round(float(rng.lognormal(mean=4.55, sigma=0.75)), 2)
            unit_weight = round(float(rng.lognormal(mean=1.45, sigma=0.75)), 2)
            average_line_qty = float(rng.uniform(1.15, 2.7))
            annual_lines = max(1, int(math.ceil(annual_demand / average_line_qty)))

            baseline_protection_days = 2.0
            mean_demand = annual_demand / WORKING_DAYS * baseline_protection_days
            target_service = 0.995 if critical else 0.975
            target_stock = int(max(1, poisson.ppf(target_service, mean_demand)))
            if critical and annual_demand > 75:
                target_stock += 1

            parts.append(
                {
                    "dealer_id": dealer.dealer_id,
                    "part_id": f"P{part_idx:04d}",
                    "annual_demand_units": annual_demand,
                    "annual_order_lines": annual_lines,
                    "unit_weight_lb": unit_weight,
                    "unit_cost": unit_cost,
                    "target_stock_units": target_stock,
                    "critical_flag": critical,
                }
            )
    demand_df = pd.DataFrame(parts)

    options_df = build_service_options()

    transport_rows = []
    for dealer in dealers_df.itertuples(index=False):
        distance = float(dealer.distance_miles)
        volume_factor = 1.0 + 0.04 * (int(str(dealer.dealer_id)[1:]) % 4)
        transport_rows.extend(
            [
                {
                    "dealer_id": dealer.dealer_id,
                    "transport_mode": "DDS",
                    "fixed_cost_per_delivery": round((155 + 0.43 * distance) * volume_factor, 2),
                    "variable_cost_per_lb": round(0.035 + 0.000025 * distance, 5),
                },
                {
                    "dealer_id": dealer.dealer_id,
                    "transport_mode": "LTL",
                    "fixed_cost_per_delivery": round((92 + 0.16 * distance) * volume_factor, 2),
                    "variable_cost_per_lb": round(0.065 + 0.000045 * distance, 5),
                },
            ]
        )
    transport_df = pd.DataFrame(transport_rows)

    # Compute baseline workload directly from the current option to set realistic
    # regular capacity and overtime. Baseline requires moderate overtime.
    baseline_option = options_df.loc[options_df["option_id"] == "CURRENT_DAILY"].iloc[0]
    demand_summary = demand_df.groupby("dealer_id", as_index=False)["annual_order_lines"].sum()
    dealer_workload = dealers_df[["dealer_id", "pdc_id"]].merge(demand_summary, on="dealer_id")
    dealer_workload["labor_hours"] = (
        dealer_workload["annual_order_lines"] * baseline_option["line_labor_minutes"]
        + baseline_option["deliveries_per_week"]
        * WEEKS
        * baseline_option["shipment_fixed_labor_minutes"]
    ) / 60.0
    workload_by_pdc = dealer_workload.groupby("pdc_id")["labor_hours"].sum()

    pdc_rows = []
    for pdc_id, baseline_hours in workload_by_pdc.items():
        regular_capacity = round(float(baseline_hours) * 0.86, 1)
        pdc_rows.append(
            {
                "pdc_id": pdc_id,
                "regular_capacity_hours": regular_capacity,
                "max_overtime_hours": round(float(baseline_hours) * 0.35, 1),
                "regular_hourly_cost": 34.0 if pdc_id == "PDC_EAST" else 32.5,
                "overtime_hourly_cost": 51.0 if pdc_id == "PDC_EAST" else 48.75,
                "avoidable_regular_labor_pct": 0.20,
            }
        )
    pdc_df = pd.DataFrame(pdc_rows)

    dealer_groups_df = pd.DataFrame(
        [
            {
                "dealer_group": group,
                "enforce_all_or_none_structural": 1,
                "annual_group_consolidation_savings": savings,
            }
            for group, savings in {
                "GROUP_A": 18000,
                "GROUP_B": 22000,
                "GROUP_C": 19000,
                "GROUP_D": 26000,
            }.items()
        ]
    )

    scenarios_df = pd.DataFrame(
        [
            {
                "scenario_id": "baseline",
                "scenario_name": "Current policy baseline",
                "allowed_scenario_classes": "baseline",
                "network_min_fill_rate": 0.950,
                "network_min_critical_fill_rate": 0.985,
                "max_dealers_changed_pct": 0.0,
                "max_inventory_investment": 0,
                "allow_overtime": 1,
                "max_pdc_overtime_pct": 0.50,
                "max_option_complexity": 0,
                "solver_time_limit_sec": 60,
                "mip_relative_gap": 0.0001,
            },
            {
                "scenario_id": "marginal",
                "scenario_name": "Daily delivery labor optimization",
                "allowed_scenario_classes": "baseline,marginal",
                "network_min_fill_rate": 0.950,
                "network_min_critical_fill_rate": 0.985,
                "max_dealers_changed_pct": 1.0,
                "max_inventory_investment": 0,
                "allow_overtime": 1,
                "max_pdc_overtime_pct": 0.50,
                "max_option_complexity": 1,
                "solver_time_limit_sec": 60,
                "mip_relative_gap": 0.0001,
            },
            {
                "scenario_id": "significant",
                "scenario_name": "Frequency reduction with selective inventory",
                "allowed_scenario_classes": "baseline,marginal,significant",
                "network_min_fill_rate": 0.950,
                "network_min_critical_fill_rate": 0.985,
                "max_dealers_changed_pct": 1.0,
                "max_inventory_investment": 350000,
                "allow_overtime": 1,
                "max_pdc_overtime_pct": 0.50,
                "max_option_complexity": 3,
                "solver_time_limit_sec": 60,
                "mip_relative_gap": 0.0001,
            },
            {
                "scenario_id": "structural",
                "scenario_name": "Dealer-group consolidation",
                "allowed_scenario_classes": "baseline,marginal,significant,structural",
                "network_min_fill_rate": 0.945,
                "network_min_critical_fill_rate": 0.980,
                "max_dealers_changed_pct": 1.0,
                "max_inventory_investment": 750000,
                "allow_overtime": 1,
                "max_pdc_overtime_pct": 0.50,
                "max_option_complexity": 5,
                "solver_time_limit_sec": 60,
                "mip_relative_gap": 0.0001,
            },
        ]
    )

    parameters_df = pd.DataFrame(
        [
            {"parameter": "working_days_per_year", "value": WORKING_DAYS, "description": "Business days used for demand-rate conversion"},
            {"parameter": "weeks_per_year", "value": WEEKS, "description": "Weeks used for annual delivery frequency"},
            {"parameter": "inventory_carrying_rate", "value": 0.22, "description": "Annual carrying cost as a percent of incremental inventory value"},
        ]
    )

    tables = {
        "dealers.csv": dealers_df,
        "dealer_part_demand.csv": demand_df,
        "service_options.csv": options_df,
        "transport_rates.csv": transport_df,
        "pdc_capacity.csv": pdc_df,
        "dealer_groups.csv": dealer_groups_df,
        "optimization_scenarios.csv": scenarios_df,
        "model_parameters.csv": parameters_df,
    }
    for filename, frame in tables.items():
        frame.to_csv(output_dir / filename, index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="inputs", help="Destination folder")
    args = parser.parse_args()
    generate_inputs(Path(args.output_dir))
    print(f"Dummy inputs written to {Path(args.output_dir).resolve()}")
