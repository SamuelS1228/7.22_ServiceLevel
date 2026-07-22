"""End-to-end orchestration for validation, candidate generation, and solving."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .candidates import build_candidates
from .io import get_scenario, load_model_data
from .reporting import write_run_outputs
from .solver import Solution, solve_scenario
from .validation import raise_for_errors, validate_model_data


def run_pipeline(
    input_dir: str | Path,
    output_dir: str | Path,
    scenario_ids: list[str] | None = None,
) -> tuple[pd.DataFrame, list[Solution]]:
    """Run selected scenarios and write all output files."""
    data = load_model_data(input_dir)
    issues = validate_model_data(data)
    raise_for_errors(issues)
    candidates = build_candidates(data)

    if scenario_ids is None:
        scenario_ids = data.optimization_scenarios["scenario_id"].astype(str).tolist()

    solutions: list[Solution] = []
    for scenario_id in scenario_ids:
        scenario = get_scenario(data, scenario_id)
        solutions.append(solve_scenario(data, candidates, scenario))

    comparison = write_run_outputs(output_dir, solutions, candidates, issues)
    return comparison, solutions
