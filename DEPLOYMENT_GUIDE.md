# Streamlit Community Cloud deployment

## What changed in version 1.1.0

The previous package imported multiple solver modules from `src/slo/__init__.py`.
When Streamlit Community Cloud loaded `slo.io`, Python first executed that
initializer, which then tried to import `slo.pipeline` and the rest of the
package. Under Streamlit's threaded runtime, the overlapping package imports
could trigger `_frozen_importlib._DeadlockError`.

Version 1.1.0 keeps `src/slo/__init__.py` lightweight and imports each module
directly from `app.py`. The bundled dummy data can now be selected from the app
without uploading files.

## Deploy a clean copy

1. Extract the ZIP.
2. Open the extracted folder. Its top level must contain:
   - `app.py`
   - `requirements.txt`
   - `src/`
   - `inputs/`
   - `.streamlit/`
3. Replace the contents of the GitHub repository with the contents of the
   extracted folder. Do not upload the ZIP file itself as the application.
4. Commit the changes to the branch used by Streamlit Community Cloud.
5. In Streamlit Community Cloud, set the entrypoint to `app.py`.
6. Select Python 3.12 in Advanced settings when creating or redeploying the app.
7. Deploy or reboot the app.

## Verify the deployment

The app opens with **Bundled dummy data** selected. Click **Run optimization**.
A four-row scenario comparison should appear, followed by a results ZIP download.

## Repository layout

```text
app.py
requirements.txt
requirements-dev.txt
cloud_smoke_test.py
pytest.ini
src/
  slo/
inputs/
tests/
.streamlit/
  config.toml
```

## Optional remote checks

In GitHub Codespaces or another remote terminal:

```bash
pip install -r requirements-dev.txt
python cloud_smoke_test.py
python -m pytest -q
streamlit run app.py
```

## If the old deadlock still appears

Confirm the deployed commit contains this lightweight initializer:

```python
# src/slo/__init__.py
__version__ = "1.1.0"
__all__ = ["__version__"]
```

Then use **Manage app → Reboot app**. If the app was created with a different
Python version, delete and redeploy it with Python 3.12.
