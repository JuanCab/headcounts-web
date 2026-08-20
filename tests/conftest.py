"""
Shared fixtures for the headcounts-web test suite.

The app reads SECRET_KEY at import time, so we inject a test value into the
environment before the module is loaded. The sample_df fixture builds a
minimal in-memory DataFrame that matches the parquet schema well enough for
all unit and integration tests.
"""

import os
from datetime import datetime

import polars as pl
import pytest

# Must be set before importing app so get_secret_key() doesn't raise.
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")


@pytest.fixture
def sample_df():
    """
    Three-row DataFrame covering CBAC and COAH subjects across two terms.
    CSIS and MATH are in the DEFAULT_TERM (20273, Fall 2026) so that
    filter_data's implicit term guard doesn't blank them out in route tests.
    ENGL is in a past term (20261, Summer 2025) for multi-term assertions.
    """
    return pl.DataFrame({
        "Fiscal yrtr": [20273, 20273, 20261],
        "Term": ["Fall 2026", "Fall 2026", "Summer 2025"],
        "ID #": [12345, 12346, 12347],
        "Subj": ["CSIS", "MATH", "ENGL"],
        "#": ["101", "261", "101"],
        "Sec": ["01", "01", "01"],
        "Title": ["Intro to CS", "Calculus I", "Composition I"],
        "Credits": ["3", "4", "3"],
        "Enrolled": [20, 25, 15],
        "Size": [30, 35, 25],
        "Status": ["Open", "Open", "Open"],
        "College": ["CBAC", "CBAC", "COAH"],
        "LASC/WI": [None, "4", "1B"],
        "18online": [False, False, True],
        "Tuition Resident": [1234.56, 1646.08, 1234.56],
        "Tuition Non-Resident": [2500.00, 3000.00, 2500.00],
        "Approximate Course Fees": [0.0, 0.0, 0.0],
        "Book Cost": [150.0, 200.0, 80.0],
        "Tuition unit": ["credit", "credit", "credit"],
        "Delivery Method": ["On Campus", "On Campus", "100% Online"],
        "Loc": ["BR101", "MH201", ""],
        "Dates": ["08/25-12/15", "08/25-12/15", "06/01-07/15"],
        "Days": ["MWF", "MTWHF", "Online"],
        "Time": ["10:00-10:50", "09:00-09:50", ""],
        "Instructor": ["Smith", "Jones", "Brown"],
        "Last Updated": [
            datetime(2026, 8, 1, 12, 0, 0),
            datetime(2026, 8, 1, 12, 0, 0),
            datetime(2026, 8, 1, 12, 0, 0),
        ],
    })


@pytest.fixture
def client(monkeypatch, sample_df, tmp_path):
    """Flask test client with parquet and file-write side-effects mocked out."""
    import app as flask_app

    # Redirect the cache dir so no real files are written during tests.
    monkeypatch.setattr("app.CACHE_DIR", str(tmp_path))

    # Replace the parquet loader so tests don't need the actual data file.
    monkeypatch.setattr(flask_app, "get_parquet", lambda: sample_df)

    # generate_datafiles writes CSV/Excel; return dummy names instead.
    monkeypatch.setattr("utils.generate_datafiles",
                        lambda *a, **kw: ("test.csv", "test.xlsx"))

    flask_app.app.config["TESTING"] = True
    flask_app.app.config["WTF_CSRF_ENABLED"] = False

    with flask_app.app.test_client() as c:
        yield c
