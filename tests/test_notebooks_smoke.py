"""Smoke tests that execute the demo notebooks end-to-end.

These demo notebooks (``notebooks/demo_*.ipynb``) are zero-Azure by design:
they read only from ``data/notebook_cache/`` and do not require any cloud
credentials, so they are safe to execute in CI on a fresh clone.

The technical notebooks (``01_*`` through ``05b_*``) are intentionally NOT
included here -- they require Azure credentials (Document Intelligence,
Azure OpenAI, Azure AI Search) and are excluded from CI by design.
"""
from __future__ import annotations

from pathlib import Path

import pytest

nbformat = pytest.importorskip("nbformat")
nbclient = pytest.importorskip("nbclient")

from nbclient import NotebookClient  # noqa: E402
from nbclient.exceptions import CellExecutionError  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
NOTEBOOKS_DIR = REPO_ROOT / "notebooks"
CACHE_DIR = REPO_ROOT / "data" / "notebook_cache"

DEMO_NOTEBOOKS = [
    "demo_01_the_problem.ipynb",
    "demo_02_pipeline_tour.ipynb",
    "demo_03_metrics_that_matter.ipynb",
]

TIMEOUT_SECONDS = 120


@pytest.mark.parametrize("notebook_name", DEMO_NOTEBOOKS)
def test_demo_notebook_executes(notebook_name: str) -> None:
    """Execute a demo notebook top-to-bottom and fail if any cell errors."""
    if not CACHE_DIR.exists():
        pytest.skip(
            f"notebook cache not found at {CACHE_DIR}; "
            "run the technical notebooks (or pull cached artifacts) first."
        )

    nb_path = NOTEBOOKS_DIR / notebook_name
    if not nb_path.exists():
        pytest.skip(f"{notebook_name} not present yet; skipping.")

    nb = nbformat.read(nb_path, as_version=4)

    client = NotebookClient(
        nb,
        timeout=TIMEOUT_SECONDS,
        kernel_name="python3",
        resources={"metadata": {"path": str(NOTEBOOKS_DIR)}},
        allow_errors=False,
    )

    try:
        client.execute()
    except CellExecutionError as exc:
        pytest.fail(f"{notebook_name} failed during execution:\n{exc}")
