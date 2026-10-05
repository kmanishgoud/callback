from datetime import date

import pandas as pd
import pytest

from helpers import app, make_tracker
from metrics import add_derived_columns, funnel, headline, report_week

TODAY = date(2026, 10, 5)       # a Monday


def days_ago(n: int) -> pd.Timestamp:
    return pd.Timestamp(TODAY) - pd.Timedelta(days=n)


# ---------------------------------------------------------------- report week

@pytest.mark.parametrize("run_day", [date(2026, 10, 5), date(2026, 10, 7), date(2026, 10, 11)])
def test_report_week_is_last_complete_monday_to_sunday(run_day):
    assert report_week(run_day) == (pd.Timestamp("2026-09-28"), pd.Timestamp("2026-10-04"))


# ---------------------------------------------------------------- status logic

@pytest.mark.parametrize("stages, age, expected", [
    ({}, 5, "Waiting"),
    ({}, 30, "Ghosted"),
    ({"date_screen": "2026-09-10"}, 30, "Screening"),
    ({"date_screen": "2026-09-10", "date_interview": "2026-09-15"}, 30, "Interviewing"),
    ({"date_screen": "2026-09-10", "date_rejected": "2026-09-20"}, 30, "Rejected"),
    ({"date_interview": "2026-09-15", "date_offer": "2026-09-25"}, 30, "Offer"),
])
def test_status_is_derived_from_stage_dates(stages, age, expected):
    df = make_tracker([app("A1", days_ago(age), **stages)])
    assert add_derived_columns(df, TODAY).loc[0, "status"] == expected


def test_days_to_reply_uses_first_reply_of_any_kind():
    df = make_tracker([app("A1", "2026-09-01", date_rejected="2026-09-11")])
    assert add_derived_columns(df, TODAY).loc[0, "days_to_reply"] == 10


def test_stage_date_before_application_is_ignored():
    df = make_tracker([app("A1", "2026-09-10", date_screen="2026-09-01")])
    out = add_derived_columns(df, TODAY)
    assert not out.loc[0, "reached_screen"]
    assert pd.isna(out.loc[0, "days_to_reply"])


# ---------------------------------------------------------------- rates

def test_rates_only_count_mature_applications():
    df = make_tracker([
        app("OLD", days_ago(30), date_screen=days_ago(25)),   # mature, replied
        app("NEW", days_ago(3)),                               # too young to judge
    ])
    k = headline(add_derived_columns(df, TODAY), TODAY)
    assert k["mature_apps"] == 1
    assert k["reply_rate"] == 1.0


def test_funnel_counts_never_increase():
    df = make_tracker([
        app("A1", days_ago(40), date_screen=days_ago(35), date_interview=days_ago(30), date_offer=days_ago(20)),
        app("A2", days_ago(40), date_screen=days_ago(35)),
        app("A3", days_ago(40)),
    ])
    counts = funnel(add_derived_columns(df, TODAY))["count"].tolist()
    assert counts == [3, 2, 1, 1]
    assert counts == sorted(counts, reverse=True)