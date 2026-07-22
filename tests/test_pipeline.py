from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from slo.candidates import build_candidates
from slo.io import get_scenario, load_model_data
from slo.pipeline import run_pipeline
from slo.solver import solve_scenario
from slo.validation import validate_model_data


@pytest.fixture(scope="module")
def input_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "inputs"


def test_dummy_inputs_validate(input_dir: Path) -> None:
    data = load_model_data(input_dir)
    issues = validate_model_data(data)
    errors = [issue for issue in issues if issue.severity == "ERROR"]
    assert errors == []


def test_candidate_generation_is_complete(input_dir: Path) -> None:
    data = load_model_data(input_dir)
    candidates = build_candidates(data)
    assert not candidates.empty
    assert set(data.dealers["dealer_id"].astype(str)) == set(candidates["dealer_id"])
    assert candidates.groupby("dealer_id")["is_current_option"].sum().eq(1).all()
    assert candidates["modeled_fill_rate"].between(0, 1).all()
    assert candidates["modeled_critical_fill_rate"].between(0, 1).all()


def test_significant_scenario_respects_constraints(input_dir: Path) -> None:
    data = load_model_data(input_dir)
    candidates = build_candidates(data)
    scenario = get_scenario(data, "significant")
    solution = solve_scenario(data, candidates, scenario)
    selected = solution.selected_candidates

    assert len(selected) == len(data.dealers)
    assert selected["dealer_id"].nunique() == len(data.dealers)
    assert (selected["modeled_fill_rate"] + 1e-9 >= selected["dealer_min_fill_rate"]).all()
    assert (
        selected["modeled_critical_fill_rate"] + 1e-9
        >= selected["dealer_min_critical_fill_rate"]
    ).all()
    assert solution.summary["network_fill_rate"] + 1e-9 >= float(
        scenario["network_min_fill_rate"]
    )
    assert solution.summary["incremental_inventory_investment"] <= float(
        scenario["max_inventory_investment"]
    ) + 1e-6


def test_full_pipeline_writes_expected_outputs(input_dir: Path, tmp_path: Path) -> None:
    comparison, solutions = run_pipeline(
        input_dir=input_dir,
        output_dir=tmp_path,
        scenario_ids=["baseline", "marginal", "significant", "structural"],
    )
    assert len(solutions) == 4
    assert set(comparison["scenario_id"]) == {
        "baseline",
        "marginal",
        "significant",
        "structural",
    }
    assert (tmp_path / "scenario_comparison.csv").exists()
    assert (tmp_path / "all_candidate_options.csv").exists()
    assert (tmp_path / "structural" / "dealer_recommendations.csv").exists()

    loaded = pd.read_csv(tmp_path / "scenario_comparison.csv")
    baseline_cost = loaded.loc[
        loaded["scenario_id"] == "baseline", "total_annual_controllable_cost"
    ].iloc[0]
    structural_cost = loaded.loc[
        loaded["scenario_id"] == "structural", "total_annual_controllable_cost"
    ].iloc[0]
    assert structural_cost < baseline_cost
