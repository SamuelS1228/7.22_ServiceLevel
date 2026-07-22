"""Command-line entry point for the Service Level Optimization solver."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from slo.pipeline import run_pipeline  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Optimize dealer service policies under cost, fill-rate, and capacity constraints."
    )
    parser.add_argument("--input-dir", default="inputs", help="Folder containing input CSV files")
    parser.add_argument("--output-dir", default="outputs", help="Folder for solver results")
    parser.add_argument(
        "--scenario",
        action="append",
        dest="scenarios",
        help="Scenario ID to solve. Repeat for multiple scenarios. Omit to run all.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    comparison, _ = run_pipeline(args.input_dir, args.output_dir, args.scenarios)
    with pd_option_context():
        print("\nOptimization complete.\n")
        print(comparison.to_string(index=False))
        print(f"\nOutputs written to: {Path(args.output_dir).resolve()}")
    return 0


class pd_option_context:
    """Small context manager to keep CLI output readable without global settings."""

    def __enter__(self):
        import pandas as pd

        self._context = pd.option_context(
            "display.max_columns", 50,
            "display.width", 220,
            "display.float_format", lambda value: f"{value:,.4f}",
        )
        return self._context.__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        return self._context.__exit__(exc_type, exc_value, traceback)


if __name__ == "__main__":
    raise SystemExit(main())
