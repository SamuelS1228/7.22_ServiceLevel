"""Streamlit interface for the Service Level Optimization solver."""

from __future__ import annotations

import io
import platform
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

# Import package modules directly. The package initializer is intentionally
# lightweight to avoid import-lock deadlocks on Streamlit Community Cloud.
from slo.io import INPUT_FILES, load_model_data  # noqa: E402
from slo.pipeline import run_pipeline  # noqa: E402
from slo.validation import validate_model_data  # noqa: E402


def _write_uploads(uploaded_files: list[object], target_dir: Path) -> None:
    """Write recognized uploaded CSVs to a temporary input directory."""
    for uploaded in uploaded_files:
        filename = str(uploaded.name)
        if filename in INPUT_FILES.values():
            (target_dir / filename).write_bytes(uploaded.getvalue())


def _zip_directory(directory: Path) -> bytes:
    """Return every file under ``directory`` as an in-memory ZIP archive."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(directory))
    return buffer.getvalue()


def _display_results() -> None:
    """Render the most recent solved comparison and download button."""
    comparison = st.session_state.get("comparison")
    results_zip = st.session_state.get("results_zip")
    if comparison is None or results_zip is None:
        return

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
    st.dataframe(comparison[display_columns], use_container_width=True, hide_index=True)
    st.download_button(
        "Download results ZIP",
        data=results_zip,
        file_name="service_level_optimization_results.zip",
        mime="application/zip",
    )


st.set_page_config(page_title="Service Level Optimizer", layout="wide")
st.title("Service Level Optimization Solver")
st.caption(
    "Validate standardized inputs and optimize dealer service policies across baseline, "
    "marginal, significant, and structural scenarios."
)

with st.sidebar:
    st.header("Run configuration")
    input_source = st.radio(
        "Input source",
        options=["Bundled dummy data", "Upload CSV files"],
        index=0,
        help="Use the bundled data to verify the deployment before uploading replacement files.",
    )
    with st.expander("Deployment diagnostics", expanded=False):
        st.write(f"Python: {platform.python_version()}")
        st.write(f"Project root: {PROJECT_ROOT}")
        st.write(f"Source directory found: {SRC_DIR.exists()}")

with st.expander("Required input filenames", expanded=False):
    st.code("\n".join(INPUT_FILES.values()))

uploaded_files: list[object] = []
if input_source == "Upload CSV files":
    uploaded_files = st.file_uploader(
        "Upload all eight input files",
        type=["csv"],
        accept_multiple_files=True,
        help="Filenames must match the required list exactly.",
    ) or []

# Every Streamlit run gets isolated temporary input/output folders. Bundled
# dummy data is copied into the temporary input folder so both input paths use
# the same pipeline.
with tempfile.TemporaryDirectory() as input_tmp, tempfile.TemporaryDirectory() as output_tmp:
    input_dir = Path(input_tmp)
    output_dir = Path(output_tmp)

    if input_source == "Bundled dummy data":
        bundled_dir = PROJECT_ROOT / "inputs"
        for filename in INPUT_FILES.values():
            source = bundled_dir / filename
            if source.exists():
                (input_dir / filename).write_bytes(source.read_bytes())
    else:
        _write_uploads(uploaded_files, input_dir)

    present = {path.name for path in input_dir.glob("*.csv")}
    missing = sorted(set(INPUT_FILES.values()) - present)
    unexpected = sorted(
        {str(uploaded.name) for uploaded in uploaded_files} - set(INPUT_FILES.values())
    )

    if unexpected:
        st.warning(f"Unexpected files ignored: {', '.join(unexpected)}")

    if missing:
        if input_source == "Bundled dummy data":
            st.error(f"Deployment package is missing bundled inputs: {', '.join(missing)}")
        else:
            st.info(f"Upload the remaining files: {', '.join(missing)}")
    else:
        try:
            model_data = load_model_data(input_dir)
            issues = validate_model_data(model_data)
            issue_frame = pd.DataFrame([issue.to_dict() for issue in issues])
            error_issues = [issue for issue in issues if issue.severity == "ERROR"]

            if error_issues:
                st.error("Input validation failed.")
                st.dataframe(issue_frame, use_container_width=True, hide_index=True)
            else:
                st.success("Input package passed validation.")
                if not issue_frame.empty:
                    with st.expander("Validation warnings", expanded=False):
                        st.dataframe(issue_frame, use_container_width=True, hide_index=True)

                scenario_options = model_data.optimization_scenarios.set_index("scenario_id")[
                    "scenario_name"
                ].to_dict()
                selected_scenarios = st.multiselect(
                    "Scenarios to solve",
                    options=list(scenario_options),
                    default=list(scenario_options),
                    format_func=lambda scenario_id: (
                        f"{scenario_id} — {scenario_options[scenario_id]}"
                    ),
                )

                if st.button(
                    "Run optimization",
                    type="primary",
                    disabled=not selected_scenarios,
                ):
                    with st.spinner("Solving scenarios..."):
                        comparison, _ = run_pipeline(
                            input_dir=input_dir,
                            output_dir=output_dir,
                            scenario_ids=selected_scenarios,
                        )
                        st.session_state["comparison"] = comparison
                        st.session_state["results_zip"] = _zip_directory(output_dir)

        except Exception as exc:
            st.error("The model could not complete. Review the error and the uploaded inputs.")
            st.exception(exc)

_display_results()
