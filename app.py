"""Streamlit upload interface for the Service Level Optimization solver."""

from __future__ import annotations

import io
import sys
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from slo.io import INPUT_FILES, load_model_data  # noqa: E402
from slo.pipeline import run_pipeline  # noqa: E402
from slo.validation import validate_model_data  # noqa: E402


st.set_page_config(page_title="Service Level Optimizer", layout="wide")
st.title("Service Level Optimization Solver")
st.caption(
    "Upload the eight standardized CSV inputs, validate them, and solve one or more policy scenarios."
)

uploaded_files = st.file_uploader(
    "Input files",
    type=["csv"],
    accept_multiple_files=True,
    help="Use the exact filenames shown below.",
)

with st.expander("Required filenames", expanded=False):
    st.code("\n".join(INPUT_FILES.values()))

if uploaded_files:
    uploads = {uploaded.name: uploaded.getvalue() for uploaded in uploaded_files}
    missing = sorted(set(INPUT_FILES.values()) - set(uploads))
    unexpected = sorted(set(uploads) - set(INPUT_FILES.values()))

    if missing:
        st.error(f"Missing files: {', '.join(missing)}")
    if unexpected:
        st.warning(f"Unexpected files will be ignored: {', '.join(unexpected)}")

    if not missing:
        with tempfile.TemporaryDirectory() as input_tmp, tempfile.TemporaryDirectory() as output_tmp:
            input_dir = Path(input_tmp)
            output_dir = Path(output_tmp)
            for filename, payload in uploads.items():
                if filename in INPUT_FILES.values():
                    (input_dir / filename).write_bytes(payload)

            try:
                model_data = load_model_data(input_dir)
                issues = validate_model_data(model_data)
                error_issues = [issue for issue in issues if issue.severity == "ERROR"]
                if error_issues:
                    st.error("Input validation failed.")
                    st.dataframe(pd.DataFrame([issue.to_dict() for issue in issues]), use_container_width=True)
                else:
                    st.success("All input files passed validation.")
                    scenario_options = model_data.optimization_scenarios.set_index("scenario_id")[
                        "scenario_name"
                    ].to_dict()
                    selected_scenarios = st.multiselect(
                        "Scenarios to solve",
                        options=list(scenario_options),
                        default=list(scenario_options),
                        format_func=lambda scenario_id: f"{scenario_id} — {scenario_options[scenario_id]}",
                    )

                    if st.button("Run optimization", type="primary", disabled=not selected_scenarios):
                        comparison, _ = run_pipeline(input_dir, output_dir, selected_scenarios)
                        st.subheader("Scenario comparison")
                        display_columns = [
                            "scenario_id",
                            "scenario_name",
                            "total_annual_controllable_cost",
                            "annual_savings_vs_baseline",
                            "savings_pct_vs_baseline",
                            "network_fill_rate",
                            "network_critical_fill_rate",
                            "incremental_inventory_investment",
                            "changed_dealers",
                            "total_overtime_hours",
                        ]
                        st.dataframe(comparison[display_columns], use_container_width=True)

                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                            for path in output_dir.rglob("*"):
                                if path.is_file():
                                    archive.write(path, path.relative_to(output_dir))
                        st.download_button(
                            "Download results ZIP",
                            data=zip_buffer.getvalue(),
                            file_name="service_level_optimization_results.zip",
                            mime="application/zip",
                        )
            except Exception as exc:  # Streamlit should surface readable input/solver errors.
                st.exception(exc)
