"""
Load the job-application tracker and check it for data-quality problems.

Safe problems are FIXED and logged; problems that need a human are WARNED;
rows that can't be used are EXCLUDED as errors. Nothing changes silently.

Quick check from the project root:
    python src/tracker.py
"""
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

import config


@dataclass
class Issue:
    level: str      # "fixed", "warning" or "error"
    app_id: str
    message: str


def load_tracker(path: Path | None = None, today: date | None = None) -> tuple[pd.DataFrame, list[Issue]]:
    """Read the tracker and return (clean DataFrame, list of issues found)."""
    path = path or config.tracker_path()
    today = pd.Timestamp(today or config.report_date())

    df = pd.read_excel(path, sheet_name="applications", dtype={"app_id": "str"})
    issues: list[Issue] = []

    _check_columns(df)
    df = _clean_text(df, issues)
    df = _normalise_categories(df, issues)
    df = _remove_duplicates(df, issues)
    df = _parse_dates(df, issues)
    df = _drop_unusable_rows(df, issues)
    _check_date_logic(df, issues, today)

    return df.reset_index(drop=True), issues


# ---------------------------------------------------------------- checks

def _check_columns(df: pd.DataFrame) -> None:
    missing = [c for c in config.REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Tracker is missing required columns: {missing}")


def _clean_text(df: pd.DataFrame, issues: list[Issue]) -> pd.DataFrame:
    """Strip leading/trailing spaces from text columns."""
    for col in config.TEXT_COLUMNS:
        original = df[col]
        stripped = original.str.strip()
        changed = original.notna() & (original != stripped)
        for idx in df.index[changed]:
            issues.append(Issue("fixed", df.at[idx, "app_id"], f"Removed extra spaces in {col}: '{original[idx]}'"))
        df[col] = stripped
    return df


def _normalise_categories(df: pd.DataFrame, issues: list[Issue]) -> pd.DataFrame:
    """Match source/work_mode to the allowed spelling, ignoring capitalisation."""
    for col, allowed in [("source", config.SOURCES), ("work_mode", config.WORK_MODES)]:
        lookup = {value.lower(): value for value in allowed}
        for idx, value in df[col].items():
            if pd.isna(value):
                continue
            canonical = lookup.get(value.lower())
            if canonical is None:
                issues.append(Issue("warning", df.at[idx, "app_id"], f"Unknown {col} '{value}'"))
            elif canonical != value:
                df.at[idx, col] = canonical
                issues.append(Issue("fixed", df.at[idx, "app_id"], f"{col} '{value}' → '{canonical}'"))
    return df


def _remove_duplicates(df: pd.DataFrame, issues: list[Issue]) -> pd.DataFrame:
    exact = df.duplicated(keep="first")
    for idx in df.index[exact]:
        issues.append(Issue("fixed", df.at[idx, "app_id"], "Duplicate row removed"))
    df = df.loc[~exact]

    same_id = df.duplicated(subset="app_id", keep=False)
    for app_id in df.loc[same_id, "app_id"].unique():
        issues.append(Issue("warning", app_id, "app_id used by more than one different row"))
    return df


def _parse_dates(df: pd.DataFrame, issues: list[Issue]) -> pd.DataFrame:
    for col in config.DATE_COLUMNS:
        parsed = pd.to_datetime(df[col], errors="coerce")
        unreadable = df[col].notna() & parsed.isna()
        for idx in df.index[unreadable]:
            issues.append(Issue("warning", df.at[idx, "app_id"], f"Unreadable date in {col}: '{df.at[idx, col]}'"))
        df[col] = parsed
    return df


def _drop_unusable_rows(df: pd.DataFrame, issues: list[Issue]) -> pd.DataFrame:
    unusable = df["date_applied"].isna() | df["company"].isna()
    for idx in df.index[unusable]:
        issues.append(Issue("error", str(df.at[idx, "app_id"]), "Missing company or date_applied: row excluded"))
    return df.loc[~unusable]


def _check_date_logic(df: pd.DataFrame, issues: list[Issue], today: pd.Timestamp) -> None:
    for col in config.STAGE_COLUMNS:
        before = df[col] < df["date_applied"]
        for idx in df.index[before]:
            issues.append(Issue("warning", df.at[idx, "app_id"], f"{col} is before date_applied: ignored in timing metrics"))

    for col in config.DATE_COLUMNS:
        future = df[col] > today
        for idx in df.index[future]:
            issues.append(Issue("warning", df.at[idx, "app_id"], f"{col} is in the future ({df.at[idx, col].date()})"))

    both = df["date_offer"].notna() & df["date_rejected"].notna()
    for idx in df.index[both]:
        issues.append(Issue("warning", df.at[idx, "app_id"], "Has both an offer and a rejection date"))


# ---------------------------------------------------------------- quick check

if __name__ == "__main__":
    df, issues = load_tracker()
    print(f"Tracker:      {config.tracker_path().relative_to(config.ROOT)}")
    print(f"Report date:  {config.report_date()}")
    print(f"Rows loaded:  {len(df)}")
    print()
    print(f"Issues found: {len(issues)}")
    for issue in issues:
        print(f"  [{issue.level.upper():7}] {issue.app_id}: {issue.message}")