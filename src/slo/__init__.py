"""Service Level Optimization package.

The package initializer is intentionally lightweight. Importing submodules from
``__init__`` caused Streamlit Community Cloud to acquire overlapping import
locks while loading ``slo.io`` and ``slo.pipeline``, which could raise
``_frozen_importlib._DeadlockError``. Import the required functions from their
own modules instead, for example ``from slo.pipeline import run_pipeline``.
"""

__version__ = "1.1.0"

__all__ = ["__version__"]
