"""Input validation for the service-level optimizer."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

import pandas as pd

from .io import ModelData


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    table: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


REQUIRED_COLUMNS: dict[str, set[str]] = {
    "dealers": {
        "dealer_id",
        "dealer_name",
        "pdc_id",
        "dealer_group",
        "min_fill_rate",
        "min_critical_fill_rate",
        "min_deliveries_per_week",
        "current_option_id",
        "implementation_locked",
    },
    "dealer_part_demand": {
        "dealer_id",
        "part_id",
        "annual_demand_units",
        "annual_order_lines",
        "unit_weight_lb",
        "unit_cost",
        "target_stock_units",
        "critical_flag",
    },
    "service_options": {
        "option_id",
        "option_name",
        "scenario_class",
        "deliveries_per_week",
        "transport_mode",
        "inventory_uplift_pct",
        "transit_days",
        "shipment_fixed_labor_minutes",
        "line_labor_minutes",
        "consolidation_line_factor",
        "annual_implementation_cost_per_dealer",
        "implementation_complexity_score",
        "enabled",
    },
    "transport_rates": {
        "dealer_id",
        "transport_mode",
        "fixed_cost_per_delivery",
        "variable_cost_per_lb",
    },
    "pdc_capacity": {
        "pdc_id",
        "regular_capacity_hours",
        "max_overtime_hours",
        "regular_hourly_cost",
        "overtime_hourly_cost",
        "avoidable_regular_labor_pct",
    },
    "dealer_groups": {
        "dealer_group",
        "enforce_all_or_none_structural",
        "annual_group_consolidation_savings",
    },
    "optimization_scenarios": {
        "scenario_id",
        "scenario_name",
        "allowed_scenario_classes",
        "network_min_fill_rate",
        "network_min_critical_fill_rate",
        "max_dealers_changed_pct",
        "max_inventory_investment",
        "allow_overtime",
        "max_pdc_overtime_pct",
        "max_option_complexity",
        "solver_time_limit_sec",
        "mip_relative_gap",
    },
}


def _check_required_columns(table_name: str, frame: pd.DataFrame) -> list[ValidationIssue]:
    missing = sorted(REQUIRED_COLUMNS[table_name] - set(frame.columns))
    if not missing:
        return []
    return [
        ValidationIssue(
            "ERROR",
            table_name,
            f"Missing required columns: {', '.join(missing)}",
        )
    ]


def _check_unique(frame: pd.DataFrame, columns: Iterable[str], table: str) -> list[ValidationIssue]:
    columns = list(columns)
    if not set(columns).issubset(frame.columns):
        return []
    duplicate_mask = frame.duplicated(columns, keep=False)
    if not duplicate_mask.any():
        return []
    sample = frame.loc[duplicate_mask, columns].head(5).to_dict("records")
    return [ValidationIssue("ERROR", table, f"Duplicate keys on {columns}. Sample: {sample}")]


def validate_model_data(data: ModelData) -> list[ValidationIssue]:
    """Return all structural, referential, and range validation issues."""
    issues: list[ValidationIssue] = []
    frames = {
        "dealers": data.dealers,
        "dealer_part_demand": data.dealer_part_demand,
        "service_options": data.service_options,
        "transport_rates": data.transport_rates,
        "pdc_capacity": data.pdc_capacity,
        "dealer_groups": data.dealer_groups,
        "optimization_scenarios": data.optimization_scenarios,
    }

    for name, frame in frames.items():
        issues.extend(_check_required_columns(name, frame))

    if any(issue.severity == "ERROR" for issue in issues):
        return issues

    issues.extend(_check_unique(data.dealers, ["dealer_id"], "dealers"))
    issues.extend(_check_unique(data.dealer_part_demand, ["dealer_id", "part_id"], "dealer_part_demand"))
    issues.extend(_check_unique(data.service_options, ["option_id"], "service_options"))
    issues.extend(_check_unique(data.transport_rates, ["dealer_id", "transport_mode"], "transport_rates"))
    issues.extend(_check_unique(data.pdc_capacity, ["pdc_id"], "pdc_capacity"))
    issues.extend(_check_unique(data.dealer_groups, ["dealer_group"], "dealer_groups"))
    issues.extend(_check_unique(data.optimization_scenarios, ["scenario_id"], "optimization_scenarios"))

    dealer_ids = set(data.dealers["dealer_id"].astype(str))
    demand_dealers = set(data.dealer_part_demand["dealer_id"].astype(str))
    missing_dealers = sorted(demand_dealers - dealer_ids)
    if missing_dealers:
        issues.append(
            ValidationIssue(
                "ERROR",
                "dealer_part_demand",
                f"Demand references unknown dealers: {missing_dealers[:10]}",
            )
        )

    dealers_without_demand = sorted(dealer_ids - demand_dealers)
    if dealers_without_demand:
        issues.append(
            ValidationIssue(
                "ERROR",
                "dealers",
                f"Dealers have no demand rows: {dealers_without_demand[:10]}",
            )
        )

    pdc_ids = set(data.pdc_capacity["pdc_id"].astype(str))
    unknown_pdcs = sorted(set(data.dealers["pdc_id"].astype(str)) - pdc_ids)
    if unknown_pdcs:
        issues.append(ValidationIssue("ERROR", "dealers", f"Unknown PDC IDs: {unknown_pdcs}"))

    option_ids = set(data.service_options["option_id"].astype(str))
    unknown_current = sorted(set(data.dealers["current_option_id"].astype(str)) - option_ids)
    if unknown_current:
        issues.append(
            ValidationIssue("ERROR", "dealers", f"Unknown current_option_id values: {unknown_current}")
        )

    group_ids = set(data.dealer_groups["dealer_group"].astype(str))
    unknown_groups = sorted(set(data.dealers["dealer_group"].astype(str)) - group_ids)
    if unknown_groups:
        issues.append(ValidationIssue("ERROR", "dealers", f"Unknown dealer groups: {unknown_groups}"))

    numeric_nonnegative = {
        "dealer_part_demand": [
            "annual_demand_units",
            "annual_order_lines",
            "unit_weight_lb",
            "unit_cost",
            "target_stock_units",
        ],
        "transport_rates": ["fixed_cost_per_delivery", "variable_cost_per_lb"],
        "pdc_capacity": [
            "regular_capacity_hours",
            "max_overtime_hours",
            "regular_hourly_cost",
            "overtime_hourly_cost",
            "avoidable_regular_labor_pct",
        ],
        "service_options": [
            "deliveries_per_week",
            "inventory_uplift_pct",
            "transit_days",
            "shipment_fixed_labor_minutes",
            "line_labor_minutes",
            "consolidation_line_factor",
            "annual_implementation_cost_per_dealer",
            "implementation_complexity_score",
        ],
    }
    for table, columns in numeric_nonnegative.items():
        frame = frames[table]
        for column in columns:
            values = pd.to_numeric(frame[column], errors="coerce")
            if values.isna().any():
                issues.append(ValidationIssue("ERROR", table, f"Column {column} contains non-numeric values"))
            elif (values < 0).any():
                issues.append(ValidationIssue("ERROR", table, f"Column {column} contains negative values"))

    rate_columns = {
        "dealers": ["min_fill_rate", "min_critical_fill_rate"],
        "pdc_capacity": ["avoidable_regular_labor_pct"],
        "optimization_scenarios": [
            "network_min_fill_rate",
            "network_min_critical_fill_rate",
            "max_dealers_changed_pct",
            "max_pdc_overtime_pct",
            "mip_relative_gap",
        ],
    }
    for table, columns in rate_columns.items():
        for column in columns:
            values = pd.to_numeric(frames[table][column], errors="coerce")
            if ((values < 0) | (values > 1)).any():
                issues.append(ValidationIssue("ERROR", table, f"Column {column} must be between 0 and 1"))

    enabled_options = data.service_options.loc[
        pd.to_numeric(data.service_options["enabled"], errors="coerce").fillna(0).astype(int) == 1
    ]
    rate_keys = set(
        zip(data.transport_rates["dealer_id"].astype(str), data.transport_rates["transport_mode"].astype(str))
    )
    missing_rate_pairs: list[tuple[str, str]] = []
    for dealer in data.dealers.itertuples(index=False):
        for mode in enabled_options["transport_mode"].astype(str).unique():
            if (str(dealer.dealer_id), mode) not in rate_keys:
                missing_rate_pairs.append((str(dealer.dealer_id), mode))
    if missing_rate_pairs:
        issues.append(
            ValidationIssue(
                "ERROR",
                "transport_rates",
                f"Missing dealer/mode rates. Sample: {missing_rate_pairs[:10]}",
            )
        )

    if not data.model_parameters.get("working_days_per_year"):
        issues.append(ValidationIssue("ERROR", "model_parameters", "working_days_per_year is required"))
    if not data.model_parameters.get("weeks_per_year"):
        issues.append(ValidationIssue("ERROR", "model_parameters", "weeks_per_year is required"))
    if data.model_parameters.get("inventory_carrying_rate") is None:
        issues.append(ValidationIssue("ERROR", "model_parameters", "inventory_carrying_rate is required"))

    return issues


def raise_for_errors(issues: list[ValidationIssue]) -> None:
    """Raise one readable exception if validation returned any errors."""
    errors = [issue for issue in issues if issue.severity == "ERROR"]
    if not errors:
        return
    details = "\n".join(f"- [{issue.table}] {issue.message}" for issue in errors)
    raise ValueError(f"Input validation failed with {len(errors)} error(s):\n{details}")
