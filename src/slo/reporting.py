"""Output reporting for service-level optimization runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import pandas as pd

from .solver import Solution
from .validation import ValidationIssue


def build_dealer_recommendations(
    selected: pd.DataFrame, all_candidates: pd.DataFrame
) -> pd.DataFrame:
    """Create a dealer-level current-versus-recommended comparison."""
    current = all_candidates.loc[all_candidates["is_current_option"] == 1].copy()
    current_columns = [
        "dealer_id",
        "option_id",
        "option_name",
        "deliveries_per_week",
        "transport_mode",
        "inventory_uplift_pct",
        "modeled_fill_rate",
        "modeled_critical_fill_rate",
        "annual_transport_cost",
        "annual_labor_hours",
        "incremental_inventory_investment",
        "annual_nonlabor_cost",
    ]
    selected_columns = [
        "dealer_id",
        "dealer_name",
        "pdc_id",
        "dealer_group",
        "option_id",
        "option_name",
        "scenario_class",
        "deliveries_per_week",
        "transport_mode",
        "inventory_uplift_pct",
        "modeled_fill_rate",
        "modeled_critical_fill_rate",
        "dealer_min_fill_rate",
        "dealer_min_critical_fill_rate",
        "annual_transport_cost",
        "annual_labor_hours",
        "incremental_inventory_investment",
        "annual_inventory_carrying_cost",
        "annual_implementation_cost",
        "annual_nonlabor_cost",
        "implementation_complexity_score",
        "is_current_option",
    ]
    comparison = selected[selected_columns].merge(
        current[current_columns], on="dealer_id", how="left", suffixes=("_recommended", "_current")
    )
    comparison["annual_transport_savings"] = (
        comparison["annual_transport_cost_current"]
        - comparison["annual_transport_cost_recommended"]
    )
    comparison["annual_labor_hours_reduction"] = (
        comparison["annual_labor_hours_current"] - comparison["annual_labor_hours_recommended"]
    )
    comparison["modeled_fill_rate_change"] = (
        comparison["modeled_fill_rate_recommended"] - comparison["modeled_fill_rate_current"]
    )
    comparison["modeled_critical_fill_rate_change"] = (
        comparison["modeled_critical_fill_rate_recommended"]
        - comparison["modeled_critical_fill_rate_current"]
    )
    comparison["policy_changed"] = (comparison["is_current_option"] == 0).astype(int)
    comparison.sort_values(
        ["policy_changed", "annual_transport_savings"], ascending=[False, False], inplace=True
    )
    return comparison


def write_solution_outputs(
    output_dir: str | Path,
    solution: Solution,
    all_candidates: pd.DataFrame,
) -> None:
    """Write detailed outputs for one scenario."""
    scenario_dir = Path(output_dir) / solution.scenario_id
    scenario_dir.mkdir(parents=True, exist_ok=True)

    recommendations = build_dealer_recommendations(
        solution.selected_candidates, all_candidates
    )
    recommendations.to_csv(scenario_dir / "dealer_recommendations.csv", index=False)
    solution.selected_candidates.to_csv(scenario_dir / "selected_candidates.csv", index=False)
    solution.pdc_results.to_csv(scenario_dir / "pdc_summary.csv", index=False)
    solution.group_results.to_csv(scenario_dir / "dealer_group_summary.csv", index=False)
    pd.DataFrame([solution.summary]).to_csv(scenario_dir / "scenario_summary.csv", index=False)
    with (scenario_dir / "scenario_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(solution.summary, handle, indent=2)


def write_run_outputs(
    output_dir: str | Path,
    solutions: Iterable[Solution],
    all_candidates: pd.DataFrame,
    validation_issues: list[ValidationIssue],
) -> pd.DataFrame:
    """Write all scenario outputs and return the comparison table."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    all_candidates.to_csv(output_path / "all_candidate_options.csv", index=False)

    issues_payload = [issue.to_dict() for issue in validation_issues]
    with (output_path / "validation_report.json").open("w", encoding="utf-8") as handle:
        json.dump(issues_payload, handle, indent=2)

    solution_list = list(solutions)
    for solution in solution_list:
        write_solution_outputs(output_path, solution, all_candidates)

    comparison = pd.DataFrame([solution.summary for solution in solution_list])
    if not comparison.empty:
        baseline_rows = comparison.loc[comparison["scenario_id"] == "baseline"]
        baseline_cost = (
            float(baseline_rows.iloc[0]["total_annual_controllable_cost"])
            if not baseline_rows.empty
            else float(comparison.iloc[0]["total_annual_controllable_cost"])
        )
        comparison["annual_savings_vs_baseline"] = (
            baseline_cost - comparison["total_annual_controllable_cost"]
        )
        comparison["savings_pct_vs_baseline"] = (
            comparison["annual_savings_vs_baseline"] / baseline_cost
            if baseline_cost != 0
            else 0.0
        )
    comparison.to_csv(output_path / "scenario_comparison.csv", index=False)
    return comparison
