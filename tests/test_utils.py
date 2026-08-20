"""
Unit tests for utils.py — pure functions only, no Flask context needed.
"""

import polars as pl
import pytest

from utils import (
    _build_display_table,
    _display_text,
    _search_rows,
    filter_data,
)


# ---------------------------------------------------------------------------
# filter_data
# ---------------------------------------------------------------------------

class TestFilterData:
    """filter_data wraps a LazyFrame, so each test must call .collect()."""

    def test_filter_by_subject_returns_only_matching_rows(self, sample_df):
        lf, _ = filter_data(sample_df.lazy(), "CSIS")
        result = lf.collect()
        assert list(result["Subj"]) == ["CSIS"]

    def test_filter_all_returns_every_row(self, sample_df):
        lf, _ = filter_data(sample_df.lazy(), "all")
        result = lf.collect()
        assert len(result) == len(sample_df)

    def test_filter_by_college_returns_matching_college(self, sample_df):
        lf, _ = filter_data(sample_df.lazy(), "COAH")
        result = lf.collect()
        assert all(r == "COAH" for r in result["College"])

    def test_filter_by_term_narrows_rows(self, sample_df):
        # Only the ENGL row is from term 20261 (Summer 2025).
        lf, _ = filter_data(sample_df.lazy(), "CSIS", "20261")
        result = lf.collect()
        # CSIS only exists in term 20275, so this should be empty.
        assert result.is_empty()

    def test_filter_lasc_excludes_courses_without_lasc(self, sample_df):
        lf, _ = filter_data(sample_df.lazy(), "lasc")
        result = lf.collect()
        # CSIS 101 has LASC/WI = None, so it must not appear.
        assert "CSIS" not in list(result["Subj"])

    def test_filter_wi_returns_only_wi_courses(self, sample_df):
        # None of the sample rows have "WI" in LASC/WI, so result is empty.
        lf, _ = filter_data(sample_df.lazy(), "wi")
        result = lf.collect()
        assert result.is_empty()

    def test_filter_18online_returns_only_online_courses(self, sample_df):
        lf, _ = filter_data(sample_df.lazy(), "18online")
        result = lf.collect()
        assert all(r is True for r in result["18online"])

    def test_unknown_subject_returns_empty(self, sample_df):
        lf, _ = filter_data(sample_df.lazy(), "FAKE")
        result = lf.collect()
        assert result.is_empty()


# ---------------------------------------------------------------------------
# _display_text
# ---------------------------------------------------------------------------

class TestDisplayText:
    """_display_text is the building block for all display-layer search."""

    def test_strips_html_tags(self):
        assert _display_text("<a href='/course/123'>123456</a>") == "123456"

    def test_lowercases_output(self):
        assert _display_text("Introduction to CS") == "introduction to cs"

    def test_none_returns_empty_string(self):
        assert _display_text(None) == ""

    def test_plain_string_passes_through_lowercased(self):
        assert _display_text("Open") == "open"

    def test_strips_nested_tags(self):
        assert _display_text("<b><i>text</i></b>") == "text"


# ---------------------------------------------------------------------------
# _search_rows
# ---------------------------------------------------------------------------

class TestSearchRows:
    """
    _search_rows is the fix for Juan's code-review finding: the CSV download
    must search the same formatted strings that appear on screen, not the raw
    parquet values. The critical case is a dollar amount — the parquet stores
    tuition as a float, but the table displays it as "$1,234.56".
    """

    def _make_display_rows(self, sample_df):
        _, rows = _build_display_table(sample_df)
        return rows

    def test_matches_formatted_dollar_amount(self, sample_df):
        # "$1,234.56" only exists after _build_display_table formats the float.
        # If _search_rows searched raw parquet data this would return no rows.
        rows = self._make_display_rows(sample_df)
        mask = _search_rows(rows, "1,234.56")
        assert any(mask), "dollar-formatted tuition amount must be findable"

    def test_search_is_case_insensitive(self, sample_df):
        rows = self._make_display_rows(sample_df)
        mask_lower = _search_rows(rows, "intro to cs")
        mask_upper = _search_rows(rows, "INTRO TO CS")
        assert mask_lower == mask_upper

    def test_empty_search_term_returns_all_true(self, sample_df):
        rows = self._make_display_rows(sample_df)
        mask = _search_rows(rows, "")
        assert all(mask)

    def test_no_match_returns_all_false(self, sample_df):
        rows = self._make_display_rows(sample_df)
        mask = _search_rows(rows, "zzz-no-match-zzz")
        assert not any(mask)

    def test_html_in_id_column_not_matched_as_text(self, sample_df):
        # The href URL contains "campusid" — searching for it should not match
        # because _display_text strips HTML before comparing.
        rows = self._make_display_rows(sample_df)
        mask = _search_rows(rows, "campusid")
        assert not any(mask)

    def test_returns_correct_count(self, sample_df):
        # Only the ENGL row is from Summer 2025 — its term name is unique.
        rows = self._make_display_rows(sample_df)
        mask = _search_rows(rows, "summer 2025")
        assert sum(mask) == 1


# ---------------------------------------------------------------------------
# _build_display_table
# ---------------------------------------------------------------------------

class TestBuildDisplayTable:

    def test_money_columns_are_formatted_as_dollar_strings(self, sample_df):
        _, rows = _build_display_table(sample_df)
        col_names, _ = _build_display_table(sample_df)
        tuition_idx = col_names.index("Tuition Resident")
        # All three rows should look like "$X,XXX.XX"
        for row in rows:
            assert row[tuition_idx].startswith("$")

    def test_fiscal_year_term_excluded_from_display_columns(self, sample_df):
        columns, _ = _build_display_table(sample_df)
        assert "Fiscal yrtr" not in columns
        assert "year_term" not in columns

    def test_row_count_matches_input(self, sample_df):
        _, rows = _build_display_table(sample_df)
        assert len(rows) == len(sample_df)

    def test_course_id_column_contains_html_link(self, sample_df):
        columns, rows = _build_display_table(sample_df)
        id_idx = columns.index("ID #")
        for row in rows:
            assert "<a href=" in row[id_idx]
