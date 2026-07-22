"""Input loading and shared data structures for the service-level optimizer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


INPUT_FILES = {
    "dealers": "dealers.csv",
    "dealer_part_demand": "dealer_part_demand.csv",
    "service_options": "service_options.csv",
    "transport_rates": "transport_rates.csv",
    "pdc_capacity": "pdc_capacity.csv",
    "dealer_groups": "dealer_groups.csv",
    "optimization_scenarios": "optimization_scenarios.csv",
    "model_parameters": "model_parameters.csv",
}


@dataclass(frozen=True)
class ModelData:
    """Container for all normalized model inputs."""

    dealers: pd.DataFrame
    dealer_part_demand: pd.DataFrame
    service_options: pd.DataFrame
    transport_rates: pd.DataFrame
    pdc_capacity: pd.DataFrame
    dealer_groups: pd.DataFrame
    optimization_scenarios: pd.DataFrame
    model_parameters: dict[str, Any]


def _parse_scalar(value: Any) -> Any:
    """Convert a CSV parameter value to bool, int, float, None, or string."""
    if pd.isna(value):
        return None
    if isinstance(value, (bool, int, float)):
        return value

    text = str(value).strip()
    lower = text.lower()
    if lower in {"true", "yes", "y"}:
        return True
    if lower in {"false", "no", "n"}:
        return False
    if lower in {"none", "null", "na", "n/a", ""}:
        return None

    try:
        if any(token in text.lower() for token in (".", "e")):
            return float(text)
        return int(text)
    except ValueError:
        return text


def load_model_data(input_dir: str | Path) -> ModelData:
    """Load the standard CSV input package from ``input_dir``.

    Parameters
    ----------
    input_dir:
        Directory containing all files listed in :data:`INPUT_FILES`.

    Raises
    ------
    FileNotFoundError
        If one or more required input files are missing.
    ValueError
        If ``model_parameters.csv`` has duplicate parameter names.
    """
    input_path = Path(input_dir)
    missing = [filename for filename in INPUT_FILES.values() if not (input_path / filename).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing required input files in {input_path}: {', '.join(sorted(missing))}"
        )

    frames = {
        key: pd.read_csv(input_path / filename)
        for key, filename in INPUT_FILES.items()
        if key != "model_parameters"
    }
    parameter_df = pd.read_csv(input_path / INPUT_FILES["model_parameters"])
    if parameter_df["parameter"].duplicated().any():
        duplicates = parameter_df.loc[
            parameter_df["parameter"].duplicated(keep=False), "parameter"
        ].tolist()
        raise ValueError(f"Duplicate model parameters: {sorted(set(duplicates))}")

    parameters = {
        str(row.parameter).strip(): _parse_scalar(row.value)
        for row in parameter_df.itertuples(index=False)
    }

    return ModelData(
        dealers=frames["dealers"],
        dealer_part_demand=frames["dealer_part_demand"],
        service_options=frames["service_options"],
        transport_rates=frames["transport_rates"],
        pdc_capacity=frames["pdc_capacity"],
        dealer_groups=frames["dealer_groups"],
        optimization_scenarios=frames["optimization_scenarios"],
        model_parameters=parameters,
    )


def get_scenario(data: ModelData, scenario_id: str) -> pd.Series:
    """Return one scenario row by ID."""
    matches = data.optimization_scenarios.loc[
        data.optimization_scenarios["scenario_id"].astype(str) == str(scenario_id)
    ]
    if matches.empty:
        valid = sorted(data.optimization_scenarios["scenario_id"].astype(str).tolist())
        raise KeyError(f"Unknown scenario_id '{scenario_id}'. Valid values: {valid}")
    if len(matches) > 1:
        raise ValueError(f"Duplicate scenario_id '{scenario_id}'")
    return matches.iloc[0]
