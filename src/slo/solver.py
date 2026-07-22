"""Mixed-integer optimization model for dealer service policies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix

from .io import ModelData


class SolverInfeasibleError(RuntimeError):
    """Raised when no feasible policy portfolio satisfies the constraints."""


@dataclass
class Solution:
    scenario_id: str
    scenario_name: str
    selected_candidates: pd.DataFrame
    pdc_results: pd.DataFrame
    group_results: pd.DataFrame
    summary: dict[str, Any]
    solver_message: str
    solver_status: int
    mip_gap: float | None


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "y"}
    return bool(value)


def _allowed_classes(value: Any) -> set[str]:
    return {item.strip().lower() for item in str(value).split(",") if item.strip()}


def _filter_candidates(candidates: pd.DataFrame, scenario: pd.Series) -> pd.DataFrame:
    allowed = _allowed_classes(scenario["allowed_scenario_classes"])
    max_complexity = float(scenario["max_option_complexity"])

    eligible = candidates.loc[
        candidates["scenario_class"].str.lower().isin(allowed)
        & (candidates["implementation_complexity_score"] <= max_complexity + 1e-12)
        & (
            candidates["deliveries_per_week"]
            >= candidates["dealer_min_deliveries_per_week"] - 1e-12
        )
    ].copy()

    locked = eligible["implementation_locked"] == 1
    eligible = eligible.loc[(~locked) | (eligible["is_current_option"] == 1)].copy()
    eligible.reset_index(drop=True, inplace=True)
    return eligible


def _precheck_feasibility(candidates: pd.DataFrame, scenario: pd.Series) -> list[str]:
    reasons: list[str] = []
    for dealer_id, group in candidates.groupby("dealer_id"):
        if group.empty:
            reasons.append(f"Dealer {dealer_id} has no eligible options")
            continue
        min_fill = float(group["dealer_min_fill_rate"].iloc[0])
        if float(group["modeled_fill_rate"].max()) + 1e-9 < min_fill:
            reasons.append(
                f"Dealer {dealer_id}: best fill {group['modeled_fill_rate'].max():.4f} "
                f"is below required {min_fill:.4f}"
            )
        min_critical = float(group["dealer_min_critical_fill_rate"].iloc[0])
        if float(group["modeled_critical_fill_rate"].max()) + 1e-9 < min_critical:
            reasons.append(
                f"Dealer {dealer_id}: best critical fill "
                f"{group['modeled_critical_fill_rate'].max():.4f} is below required {min_critical:.4f}"
            )

    if candidates.empty:
        return reasons or ["No eligible candidates remain after scenario filters"]

    best = candidates.loc[candidates.groupby("dealer_id")["modeled_fill_rate"].idxmax()]
    weighted_fill = np.average(best["modeled_fill_rate"], weights=best["annual_demand_units"])
    if weighted_fill + 1e-9 < float(scenario["network_min_fill_rate"]):
        reasons.append(
            f"Maximum approximate network fill {weighted_fill:.4f} is below target "
            f"{float(scenario['network_min_fill_rate']):.4f}"
        )
    return reasons


def solve_scenario(
    data: ModelData,
    all_candidates: pd.DataFrame,
    scenario: pd.Series,
) -> Solution:
    """Solve one optimization scenario using SciPy/HiGHS MILP."""
    candidates = _filter_candidates(all_candidates, scenario)
    expected_dealers = set(data.dealers["dealer_id"].astype(str))
    candidate_dealers = set(candidates["dealer_id"].astype(str))
    missing = sorted(expected_dealers - candidate_dealers)
    if missing:
        raise SolverInfeasibleError(f"Dealers with no eligible candidates: {missing}")

    precheck = _precheck_feasibility(candidates, scenario)
    if precheck:
        raise SolverInfeasibleError("Scenario failed feasibility precheck:\n- " + "\n- ".join(precheck))

    candidates = candidates.copy().reset_index(drop=True)
    pdc = data.pdc_capacity.copy().reset_index(drop=True)
    pdc["pdc_id"] = pdc["pdc_id"].astype(str)

    enforced_groups = data.dealer_groups.loc[
        pd.to_numeric(data.dealer_groups["enforce_all_or_none_structural"]).astype(int) == 1
    ].copy()
    enforced_groups["dealer_group"] = enforced_groups["dealer_group"].astype(str)
    enforced_groups.reset_index(drop=True, inplace=True)

    n_x = len(candidates)
    n_pdc = len(pdc)
    n_group = len(enforced_groups)
    reg_start = n_x
    ot_start = reg_start + n_pdc
    group_start = ot_start + n_pdc
    n_vars = n_x + 2 * n_pdc + n_group

    objective = np.zeros(n_vars, dtype=float)
    objective[:n_x] = (
        candidates["annual_nonlabor_cost"].to_numpy(float)
        + 1e-6 * candidates["implementation_complexity_score"].to_numpy(float)
    )
    objective[reg_start:ot_start] = (
        pdc["regular_hourly_cost"].to_numpy(float)
        * pdc["avoidable_regular_labor_pct"].to_numpy(float)
    )
    objective[ot_start:group_start] = pdc["overtime_hourly_cost"].to_numpy(float)
    if n_group:
        objective[group_start:] = -enforced_groups[
            "annual_group_consolidation_savings"
        ].to_numpy(float)

    lower_bounds = np.zeros(n_vars, dtype=float)
    upper_bounds = np.full(n_vars, np.inf, dtype=float)
    upper_bounds[:n_x] = 1.0
    upper_bounds[reg_start:ot_start] = pdc["regular_capacity_hours"].to_numpy(float)

    allow_overtime = _as_bool(scenario["allow_overtime"])
    max_ot_pct = float(scenario["max_pdc_overtime_pct"])
    scenario_ot_cap = pdc["regular_capacity_hours"].to_numpy(float) * max_ot_pct
    input_ot_cap = pdc["max_overtime_hours"].to_numpy(float)
    upper_bounds[ot_start:group_start] = (
        np.minimum(scenario_ot_cap, input_ot_cap) if allow_overtime else 0.0
    )
    if n_group:
        upper_bounds[group_start:] = 1.0

    integrality = np.zeros(n_vars, dtype=int)
    integrality[:n_x] = 1
    if n_group:
        integrality[group_start:] = 1

    rows: list[dict[int, float]] = []
    lower: list[float] = []
    upper: list[float] = []

    def add_constraint(coefficients: dict[int, float], lb: float, ub: float) -> None:
        rows.append(coefficients)
        lower.append(lb)
        upper.append(ub)

    # One option per dealer, plus dealer-level service floors.
    for dealer_id, group in candidates.groupby("dealer_id", sort=False):
        indices = group.index.to_list()
        add_constraint({idx: 1.0 for idx in indices}, 1.0, 1.0)
        add_constraint(
            {idx: float(candidates.at[idx, "modeled_fill_rate"]) for idx in indices},
            float(group["dealer_min_fill_rate"].iloc[0]),
            np.inf,
        )
        add_constraint(
            {
                idx: float(candidates.at[idx, "modeled_critical_fill_rate"])
                for idx in indices
            },
            float(group["dealer_min_critical_fill_rate"].iloc[0]),
            np.inf,
        )

    # PDC workload balance: regular + overtime = selected policy hours.
    for pdc_idx, pdc_row in pdc.iterrows():
        pdc_id = str(pdc_row["pdc_id"])
        coefficients = {
            reg_start + pdc_idx: 1.0,
            ot_start + pdc_idx: 1.0,
        }
        for idx in candidates.index[candidates["pdc_id"] == pdc_id]:
            coefficients[int(idx)] = -float(candidates.at[idx, "annual_labor_hours"])
        add_constraint(coefficients, 0.0, 0.0)

    # Network weighted fill constraints.
    demand_coefficients = {
        idx: float(row.annual_demand_units * row.modeled_fill_rate)
        for idx, row in candidates.iterrows()
    }
    total_demand = float(
        candidates.groupby("dealer_id", as_index=False)["annual_demand_units"].first()[
            "annual_demand_units"
        ].sum()
    )
    add_constraint(
        demand_coefficients,
        float(scenario["network_min_fill_rate"]) * total_demand,
        np.inf,
    )

    critical_coefficients = {
        idx: float(row.annual_critical_demand_units * row.modeled_critical_fill_rate)
        for idx, row in candidates.iterrows()
    }
    total_critical_demand = float(
        candidates.groupby("dealer_id", as_index=False)["annual_critical_demand_units"].first()[
            "annual_critical_demand_units"
        ].sum()
    )
    if total_critical_demand > 0:
        add_constraint(
            critical_coefficients,
            float(scenario["network_min_critical_fill_rate"]) * total_critical_demand,
            np.inf,
        )

    # Change and inventory investment guardrails.
    max_changed = float(scenario["max_dealers_changed_pct"]) * len(expected_dealers)
    add_constraint(
        {
            idx: 1.0
            for idx in candidates.index[candidates["is_current_option"] == 0]
        },
        -np.inf,
        max_changed,
    )
    add_constraint(
        {
            idx: float(candidates.at[idx, "incremental_inventory_investment"])
            for idx in candidates.index
        },
        -np.inf,
        float(scenario["max_inventory_investment"]),
    )

    # Structural dealer-group policies are all-or-none where requested.
    for group_idx, group_row in enforced_groups.iterrows():
        group_name = str(group_row["dealer_group"])
        y_idx = group_start + group_idx
        dealer_ids = data.dealers.loc[
            data.dealers["dealer_group"].astype(str) == group_name, "dealer_id"
        ].astype(str)
        for dealer_id in dealer_ids:
            structural_indices = candidates.index[
                (candidates["dealer_id"] == dealer_id)
                & (candidates["is_structural_option"] == 1)
            ].to_list()
            coefficients = {int(idx): 1.0 for idx in structural_indices}
            coefficients[y_idx] = -1.0
            add_constraint(coefficients, 0.0, 0.0)

    matrix = lil_matrix((len(rows), n_vars), dtype=float)
    for row_idx, coefficients in enumerate(rows):
        for col_idx, coefficient in coefficients.items():
            matrix[row_idx, col_idx] = coefficient

    options = {
        "disp": False,
        "presolve": True,
        "time_limit": float(scenario["solver_time_limit_sec"]),
        "mip_rel_gap": float(scenario["mip_relative_gap"]),
    }
    result = milp(
        c=objective,
        integrality=integrality,
        bounds=Bounds(lower_bounds, upper_bounds),
        constraints=LinearConstraint(matrix.tocsr(), np.asarray(lower), np.asarray(upper)),
        options=options,
    )

    if result.x is None or result.status not in {0, 1}:
        raise SolverInfeasibleError(
            f"MILP did not produce a feasible solution. Status={result.status}; message={result.message}"
        )

    selected = candidates.loc[result.x[:n_x] > 0.5].copy().reset_index(drop=True)
    if len(selected) != len(expected_dealers):
        raise RuntimeError(
            f"Solver selected {len(selected)} rows for {len(expected_dealers)} dealers"
        )

    pdc_results = pdc.copy()
    pdc_results["selected_labor_hours"] = pdc_results["pdc_id"].map(
        selected.groupby("pdc_id")["annual_labor_hours"].sum()
    ).fillna(0.0)
    pdc_results["regular_hours_used"] = result.x[reg_start:ot_start]
    pdc_results["overtime_hours_used"] = result.x[ot_start:group_start]
    pdc_results["regular_capacity_utilization"] = (
        pdc_results["regular_hours_used"] / pdc_results["regular_capacity_hours"]
    )
    pdc_results["modeled_regular_labor_cost"] = (
        pdc_results["regular_hours_used"]
        * pdc_results["regular_hourly_cost"]
        * pdc_results["avoidable_regular_labor_pct"]
    )
    pdc_results["modeled_overtime_cost"] = (
        pdc_results["overtime_hours_used"] * pdc_results["overtime_hourly_cost"]
    )

    group_results = enforced_groups.copy()
    if n_group:
        group_results["structural_policy_selected"] = (
            result.x[group_start:] > 0.5
        ).astype(int)
        group_results["realized_group_savings"] = (
            group_results["annual_group_consolidation_savings"]
            * group_results["structural_policy_selected"]
        )
    else:
        group_results["structural_policy_selected"] = pd.Series(dtype=int)
        group_results["realized_group_savings"] = pd.Series(dtype=float)

    total_demand_selected = float(selected["annual_demand_units"].sum())
    network_fill = float(
        (selected["modeled_fill_rate"] * selected["annual_demand_units"]).sum()
        / total_demand_selected
    )
    total_critical_selected = float(selected["annual_critical_demand_units"].sum())
    network_critical_fill = (
        float(
            (
                selected["modeled_critical_fill_rate"]
                * selected["annual_critical_demand_units"]
            ).sum()
            / total_critical_selected
        )
        if total_critical_selected > 0
        else 1.0
    )

    transport_cost = float(selected["annual_transport_cost"].sum())
    carrying_cost = float(selected["annual_inventory_carrying_cost"].sum())
    implementation_cost = float(selected["annual_implementation_cost"].sum())
    regular_labor_cost = float(pdc_results["modeled_regular_labor_cost"].sum())
    overtime_cost = float(pdc_results["modeled_overtime_cost"].sum())
    group_savings = float(group_results["realized_group_savings"].sum()) if n_group else 0.0
    total_cost = (
        transport_cost
        + carrying_cost
        + implementation_cost
        + regular_labor_cost
        + overtime_cost
        - group_savings
    )

    summary = {
        "scenario_id": str(scenario["scenario_id"]),
        "scenario_name": str(scenario["scenario_name"]),
        "solver_status": int(result.status),
        "solver_message": str(result.message),
        "total_annual_controllable_cost": total_cost,
        "annual_transport_cost": transport_cost,
        "annual_inventory_carrying_cost": carrying_cost,
        "annual_implementation_cost": implementation_cost,
        "annual_regular_labor_cost": regular_labor_cost,
        "annual_overtime_cost": overtime_cost,
        "annual_group_consolidation_savings": group_savings,
        "network_fill_rate": network_fill,
        "network_critical_fill_rate": network_critical_fill,
        "incremental_inventory_investment": float(
            selected["incremental_inventory_investment"].sum()
        ),
        "changed_dealers": int((selected["is_current_option"] == 0).sum()),
        "changed_dealers_pct": float((selected["is_current_option"] == 0).mean()),
        "total_annual_labor_hours": float(selected["annual_labor_hours"].sum()),
        "total_overtime_hours": float(pdc_results["overtime_hours_used"].sum()),
        "mip_gap": float(getattr(result, "mip_gap", np.nan))
        if getattr(result, "mip_gap", None) is not None
        else None,
    }

    return Solution(
        scenario_id=str(scenario["scenario_id"]),
        scenario_name=str(scenario["scenario_name"]),
        selected_candidates=selected,
        pdc_results=pdc_results,
        group_results=group_results,
        summary=summary,
        solver_message=str(result.message),
        solver_status=int(result.status),
        mip_gap=summary["mip_gap"],
    )
