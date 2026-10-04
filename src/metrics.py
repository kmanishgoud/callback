"""
Turn the clean tracker into the numbers the weekly report needs.

All functions are pure: data in, numbers out, no file access.
That makes them easy to test (see tests/).

Quick check from the project root:
    python src/metrics.py
"""
from datetime import date, timedelta

import numpy as np
import pandas as pd

import config

STATUS_ORDER = ["Offer", "Interviewing", "Screening", "Waiting", "Ghosted", "Rejected"]
EVENT_LABELS = {
    "date_screen": "Screening call",
    "date_interview": "Interview",
    "date_offer": "Offer",
    "date_rejected": "Rejection",
}


# ---------------------------------------------------------------- helpers

def report_week(today: date) -> tuple[pd.Timestamp, pd.Timestamp]:
    """The last complete Monday–Sunday week before `today`."""
    this_monday = today - timedelta(days=today.weekday())
    start = this_monday - timedelta(days=7)
    end = this_monday - timedelta(days=1)
    return pd.Timestamp(start), pd.Timestamp(end)


def add_derived_columns(df: pd.DataFrame, today: date) -> pd.DataFrame:
    """Work out status, reply timing and stage flags from the stage dates."""
    df = df.copy()
    today = pd.Timestamp(today)

    # Stage dates that come before the application date are invalid: ignore them for timing
    stages = df[config.STAGE_COLUMNS]
    valid = stages.where(stages.ge(df["date_applied"], axis=0))

    df["date_first_reply"] = valid.min(axis=1)
    df["replied"] = df["date_first_reply"].notna()
    df["days_to_reply"] = (df["date_first_reply"] - df["date_applied"]).dt.days
    df["days_since_applied"] = (today - df["date_applied"]).dt.days
    df["mature"] = df["days_since_applied"] >= config.MATURE_AFTER_DAYS

    df["reached_screen"] = valid[["date_screen", "date_interview", "date_offer"]].notna().any(axis=1)
    df["reached_interview"] = valid[["date_interview", "date_offer"]].notna().any(axis=1)
    df["reached_offer"] = valid["date_offer"].notna()
    rejected = valid["date_rejected"].notna()

    # Status: the furthest point each application has reached (checked in priority order)
    df["status"] = np.select(
        [
            df["reached_offer"],
            rejected,
            df["reached_interview"],
            df["reached_screen"],
            df["days_since_applied"] > config.GHOST_AFTER_DAYS,
        ],
        ["Offer", "Rejected", "Interviewing", "Screening", "Ghosted"],
        default="Waiting",
    )
    return df


# ---------------------------------------------------------------- report sections

def headline(df: pd.DataFrame, today: date) -> dict:
    start, end = report_week(today)
    prev_start, prev_end = start - pd.Timedelta(days=7), end - pd.Timedelta(days=7)
    mature = df[df["mature"]]
    replied = df[df["replied"]]

    return {
        "week_start": start.date(),
        "week_end": end.date(),
        "apps_this_week": int(df["date_applied"].between(start, end).sum()),
        "apps_last_week": int(df["date_applied"].between(prev_start, prev_end).sum()),
        "total_apps": len(df),
        "mature_apps": len(mature),
        "reply_rate": mature["replied"].mean(),
        "screen_rate": mature["reached_screen"].mean(),
        "interview_rate": mature["reached_interview"].mean(),
        "offers": int(df["reached_offer"].sum()),
        "active": int(df["status"].isin(["Screening", "Interviewing"]).sum()),
        "median_days_to_reply": float(replied["days_to_reply"].median()) if len(replied) else None,
    }


def funnel(df: pd.DataFrame) -> pd.DataFrame:
    stages = [
        ("Applied", len(df)),
        ("Screening call", int(df["reached_screen"].sum())),
        ("Interview", int(df["reached_interview"].sum())),
        ("Offer", int(df["reached_offer"].sum())),
    ]
    f = pd.DataFrame(stages, columns=["stage", "count"])
    f["pct_of_applied"] = f["count"] / len(df)
    f["pct_of_previous"] = f["count"] / f["count"].shift(1)
    return f


def by_source(df: pd.DataFrame) -> pd.DataFrame:
    """Which channels get replies? Mature applications only."""
    mature = df[df["mature"]]
    table = mature.groupby("source").agg(
        applications=("app_id", "size"),
        reply_rate=("replied", "mean"),
        screen_rate=("reached_screen", "mean"),
        median_days_to_reply=("days_to_reply", "median"),
    )
    return table.sort_values(["screen_rate", "applications"], ascending=False)


def weekly_trend(df: pd.DataFrame, today: date, weeks: int = 8) -> pd.DataFrame:
    """Applications and screening calls per week, for the last `weeks` weeks."""
    start, _ = report_week(today)
    week_starts = pd.date_range(start - pd.Timedelta(weeks=weeks - 1), start, freq="7D")

    def monday_of(dates: pd.Series) -> pd.Series:
        return dates - pd.to_timedelta(dates.dt.weekday, unit="D")

    apps = monday_of(df["date_applied"]).value_counts()
    screen_dates = df.loc[df["reached_screen"] & df["date_screen"].notna(), "date_screen"]
    screens = monday_of(screen_dates).value_counts()

    return pd.DataFrame({
        "applications": apps.reindex(week_starts, fill_value=0),
        "screens": screens.reindex(week_starts, fill_value=0),
    }).rename_axis("week_start")


def week_events(df: pd.DataFrame, today: date) -> pd.DataFrame:
    """Everything that happened during the report week, in date order."""
    start, end = report_week(today)
    rows = []
    for col, label in EVENT_LABELS.items():
        for _, r in df[df[col].between(start, end)].iterrows():
            rows.append({"date": r[col], "event": label, "company": r["company"], "role": r["role"]})
    return pd.DataFrame(rows, columns=["date", "event", "company", "role"]).sort_values("date")


def follow_ups(df: pd.DataFrame) -> pd.DataFrame:
    """No reply yet, but old enough that a polite follow-up makes sense."""
    mask = (df["status"] == "Waiting") & (df["days_since_applied"] >= config.FOLLOW_UP_AFTER_DAYS)
    cols = ["app_id", "company", "role", "source", "date_applied", "days_since_applied"]
    return df.loc[mask, cols].sort_values("days_since_applied", ascending=False)


def newly_ghosted(df: pd.DataFrame) -> pd.DataFrame:
    """Crossed the ghosting threshold during the last 7 days."""
    days = df["days_since_applied"]
    mask = (df["status"] == "Ghosted") & (days > config.GHOST_AFTER_DAYS) & (days <= config.GHOST_AFTER_DAYS + 7)
    cols = ["app_id", "company", "role", "source", "date_applied", "days_since_applied"]
    return df.loc[mask, cols].sort_values("days_since_applied", ascending=False)


# ---------------------------------------------------------------- everything together

def build_metrics(df: pd.DataFrame, today: date) -> dict:
    df = add_derived_columns(df, today)
    return {
        "kpis": headline(df, today),
        "status_counts": df["status"].value_counts().reindex(STATUS_ORDER, fill_value=0),
        "funnel": funnel(df),
        "sources": by_source(df),
        "trend": weekly_trend(df, today),
        "events": week_events(df, today),
        "follow_ups": follow_ups(df),
        "newly_ghosted": newly_ghosted(df),
        "applications": df,
    }


# ---------------------------------------------------------------- quick check

if __name__ == "__main__":
    from tracker import load_tracker

    pd.set_option("display.width", 120)
    today = config.report_date()
    df, _ = load_tracker(today=today)
    m = build_metrics(df, today)

    k = m["kpis"]
    print(f"REPORT WEEK: {k['week_start']} to {k['week_end']}\n")
    print(f"Applications this week:  {k['apps_this_week']}  (last week: {k['apps_last_week']})")
    print(f"Total applications:      {k['total_apps']}  ({k['mature_apps']} older than {config.MATURE_AFTER_DAYS} days)")
    print(f"Reply rate:              {k['reply_rate']:.0%}")
    print(f"Screening rate:          {k['screen_rate']:.0%}")
    print(f"Interview rate:          {k['interview_rate']:.0%}")
    print(f"Offers:                  {k['offers']}")
    print(f"Active (screen/interview): {k['active']}")
    print(f"Median days to reply:    {k['median_days_to_reply']}")

    print("\nSTATUS\n" + m["status_counts"].to_string())
    print("\nFUNNEL\n" + m["funnel"].round(2).to_string(index=False))
    print("\nBY SOURCE\n" + m["sources"].round(2).to_string())
    print("\nWEEKLY TREND\n" + m["trend"].to_string())
    print("\nTHIS WEEK'S EVENTS\n" + (m["events"].to_string(index=False) if len(m["events"]) else "None"))
    print(f"\nFOLLOW UP ({len(m['follow_ups'])})\n" + m["follow_ups"].head(10).to_string(index=False))
    print(f"\nNEWLY GHOSTED ({len(m['newly_ghosted'])})\n" + m["newly_ghosted"].to_string(index=False))