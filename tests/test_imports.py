from __future__ import annotations

import importlib
import sys


def test_package_initializer_is_lightweight() -> None:
    for module_name in list(sys.modules):
        if module_name == "slo" or module_name.startswith("slo."):
            del sys.modules[module_name]

    package = importlib.import_module("slo")
    assert package.__version__ == "1.1.0"
    assert "slo.pipeline" not in sys.modules
    assert "slo.solver" not in sys.modules


def test_cloud_entrypoint_imports_without_deadlock() -> None:
    io_module = importlib.import_module("slo.io")
    pipeline_module = importlib.import_module("slo.pipeline")
    validation_module = importlib.import_module("slo.validation")

    assert io_module.INPUT_FILES
    assert callable(pipeline_module.run_pipeline)
    assert callable(validation_module.validate_model_data)
