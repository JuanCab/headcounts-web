"""
Integration tests for Flask routes — uses the test client from conftest.py.

get_parquet() and generate_datafiles() are patched in the client fixture so
tests never touch the filesystem or require a real parquet file.
"""

import json

import pytest


# ---------------------------------------------------------------------------
# /SUBJECT (filtered_view)
# ---------------------------------------------------------------------------

class TestFilteredView:

    def test_known_subject_returns_200(self, client):
        resp = client.get("/CSIS")
        assert resp.status_code == 200

    def test_unknown_subject_returns_200_with_no_results_message(self, client):
        resp = client.get("/FAKE")
        assert resp.status_code == 200
        assert b"No Courses Found" in resp.data

    def test_response_contains_column_headers(self, client):
        resp = client.get("/CSIS")
        assert b"Enrolled" in resp.data
        assert b"Status" in resp.data


# ---------------------------------------------------------------------------
# /data/SUBJECT  (data_view — DataTables server-side endpoint)
# ---------------------------------------------------------------------------

class TestDataView:

    def _post(self, client, path, extra=None):
        """Send a minimal DataTables server-side POST request."""
        params = {"draw": "1", "start": "0", "length": "25",
                  "search[value]": "", "order[0][column]": "0",
                  "order[0][dir]": "asc"}
        if extra:
            params.update(extra)
        return client.post(path, data=params)

    def test_returns_datatables_keys(self, client):
        resp = self._post(client, "/data/CSIS")
        body = json.loads(resp.data)
        assert {"draw", "recordsTotal", "recordsFiltered", "data"} <= body.keys()

    def test_records_total_matches_filtered_subject(self, client):
        # sample_df has exactly one CSIS row.
        resp = self._post(client, "/data/CSIS")
        body = json.loads(resp.data)
        assert body["recordsTotal"] == 1

    def test_search_reduces_records_filtered(self, client):
        # Searching for "summer" should match only the ENGL Summer 2025 row.
        resp = self._post(client, "/data/all",
                          extra={"search[value]": "summer"})
        body = json.loads(resp.data)
        assert body["recordsFiltered"] == 1
        assert body["recordsTotal"] == 3

    def test_search_on_formatted_dollar_amount(self, client):
        # "$1,234.56" is a formatted value that only exists after
        # _build_display_table runs — verifies search uses display strings.
        resp = self._post(client, "/data/all",
                          extra={"search[value]": "1,234.56"})
        body = json.loads(resp.data)
        assert body["recordsFiltered"] >= 1

    def test_empty_subject_returns_empty_data(self, client):
        resp = self._post(client, "/data/FAKE")
        body = json.loads(resp.data)
        assert body["recordsTotal"] == 0
        assert body["data"] == []

    def test_draw_value_echoed_back(self, client):
        resp = self._post(client, "/data/CSIS", extra={"draw": "42"})
        body = json.loads(resp.data)
        assert body["draw"] == 42


# ---------------------------------------------------------------------------
# /csv/SUBJECT  (csv_view)
# ---------------------------------------------------------------------------

class TestCsvView:

    def test_returns_csv_content_type(self, client):
        resp = client.get("/csv/CSIS")
        assert "text/csv" in resp.content_type

    def test_csv_contains_header_row(self, client):
        resp = client.get("/csv/CSIS")
        first_line = resp.data.decode().splitlines()[0]
        assert "Subj" in first_line

    def test_q_param_filters_rows(self, client):
        # Without filter: all 3 rows; with "csis" filter: only 1 row + header.
        full = client.get("/csv/all")
        filtered = client.get("/csv/all?q=csis")
        full_lines = [l for l in full.data.decode().splitlines() if l.strip()]
        filtered_lines = [l for l in filtered.data.decode().splitlines() if l.strip()]
        assert len(filtered_lines) < len(full_lines)


# ---------------------------------------------------------------------------
# Search consistency: /data/ and /csv/?q= must agree on matching rows
# ---------------------------------------------------------------------------

class TestSearchConsistency:
    """
    This is the core regression test for Juan's code-review finding.
    Before the fix, /data/ searched formatted display strings while /csv/?q=
    searched only raw string columns — so the same query returned different
    rows from each endpoint.
    """

    def _data_subjects(self, client, search_term):
        """Return the Subj values from a /data/all search."""
        resp = client.post("/data/all", data={
            "draw": "1", "start": "0", "length": "100",
            "search[value]": search_term,
            "order[0][column]": "0", "order[0][dir]": "asc",
        })
        body = json.loads(resp.data)
        # Find the Subj column index by looking at the first row header.
        # We rely on the data being non-empty before calling this.
        return body

    def test_dollar_search_returns_same_rows_from_both_endpoints(self, client):
        search = "1,234.56"

        # Rows matched by the DataTables endpoint
        dt_resp = client.post("/data/all", data={
            "draw": "1", "start": "0", "length": "100",
            "search[value]": search,
            "order[0][column]": "0", "order[0][dir]": "asc",
        })
        dt_body = json.loads(dt_resp.data)
        dt_count = dt_body["recordsFiltered"]

        # Rows returned by the CSV endpoint
        csv_resp = client.get(f"/csv/all?q={search}")
        csv_lines = [l for l in csv_resp.data.decode().splitlines() if l.strip()]
        csv_data_rows = len(csv_lines) - 1  # subtract header

        assert dt_count == csv_data_rows, (
            f"/data/ matched {dt_count} rows but /csv/?q= returned "
            f"{csv_data_rows} rows for the same search term '{search}'"
        )


# ---------------------------------------------------------------------------
# Maintenance gate
# ---------------------------------------------------------------------------

class TestMaintenanceGate:

    def test_maintenance_file_causes_503(self, client, tmp_path, monkeypatch):
        maintenance = tmp_path / ".maintenance"
        maintenance.touch()
        monkeypatch.setattr("app.MAINTENANCE_FILE", maintenance)
        resp = client.get("/CSIS")
        assert resp.status_code == 503

    def test_no_maintenance_file_allows_request(self, client, tmp_path, monkeypatch):
        absent = tmp_path / ".maintenance"  # does not exist
        monkeypatch.setattr("app.MAINTENANCE_FILE", absent)
        resp = client.get("/CSIS")
        assert resp.status_code == 200
