"""Small builders for hand-made test trackers."""
import pandas as pd

import config


def app(app_id: str, applied, **fields) -> dict:
    """One application row with sensible defaults; override any field by keyword."""
    row = {
        "app_id": app_id, "company": "Test Co", "role": "Data Analyst",
        "location": "Paris", "work_mode": "Hybrid", "source": "LinkedIn",
        "date_applied": applied,
    }
    row.update(fields)
    return row


def make_tracker(rows: list[dict]) -> pd.DataFrame:
    """Build a tracker DataFrame with every required column and proper date types."""
    df = pd.DataFrame(rows)
    for col in config.REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = None
    for col in config.DATE_COLUMNS:
        df[col] = pd.to_datetime(df[col])
    return df[config.REQUIRED_COLUMNS]