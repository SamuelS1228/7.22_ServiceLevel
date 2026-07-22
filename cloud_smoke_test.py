"""Deployment smoke test for Streamlit Community Cloud.

Run with:
    python cloud_smoke_test.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from slo.io import INPUT_FILES, load_model_data
from slo.pipeline import run_pipeline
from slo.validation import validate_model_data


def main() -> None:
    input_dir = PROJECT_ROOT / "inputs"
    missing = [name for name in INPUT_FILES.values() if not (input_dir / name).exists()]
    if missing:
        raise FileNotFoundError(f"Missing dummy input files: {missing}")

    data = load_model_data(input_dir)
    issues = validate_model_data(data)
    errors = [issue for issue in issues if issue.severity == "ERROR"]
    if errors:
        raise RuntimeError(f"Input validation failed: {[issue.to_dict() for issue in errors]}")

    with tempfile.TemporaryDirectory() as output_dir:
        comparison, solutions = run_pipeline(
            input_dir=input_dir,
            output_dir=output_dir,
            scenario_ids=["baseline", "marginal", "significant", "structural"],
        )

    if len(solutions) != 4 or len(comparison) != 4:
        raise RuntimeError("Expected four solved scenarios")

    print("Cloud smoke test passed")
    print(comparison[["scenario_id", "total_annual_controllable_cost"]].to_string(index=False))


if __name__ == "__main__":
    main()
