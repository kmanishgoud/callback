"""
Central settings for Callback. Every other module imports from here,
so there is one place to change paths, categories and thresholds.
"""
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ---- Files ----
REAL_TRACKER = ROOT / "data" / "applications.xlsx"              # private, git-ignored
SAMPLE_TRACKER = ROOT / "data" / "sample" / "applications_sample.xlsx"
OUTPUT_DIR = ROOT / "output"

# The sample data's "today" (the Monday after its last application)
SAMPLE_REPORT_DATE = date(2026, 10, 5)


def tracker_path() -> Path:
    """Use the real tracker if it exists, otherwise fall back to the sample."""
    return REAL_TRACKER if REAL_TRACKER.exists() else SAMPLE_TRACKER


def report_date() -> date:
    """Today's date for real data; a fixed date for the sample, so its report never changes."""
    return date.today() if REAL_TRACKER.exists() else SAMPLE_REPORT_DATE


# ---- Tracker structure ----
REQUIRED_COLUMNS = [
    "app_id", "company", "role", "location", "work_mode", "source",
    "date_applied", "date_screen", "date_interview", "date_offer", "date_rejected",
]
TEXT_COLUMNS = ["app_id", "company", "role", "location", "work_mode", "source"]
DATE_COLUMNS = ["date_applied", "date_screen", "date_interview", "date_offer", "date_rejected"]
STAGE_COLUMNS = ["date_screen", "date_interview", "date_offer", "date_rejected"]  # must come after applying

# ---- Allowed values (exact spelling) ----
SOURCES = [
    "LinkedIn Easy Apply", "LinkedIn", "Company website", "Welcome to the Jungle",
    "Indeed", "Recruiter", "Referral",
]
WORK_MODES = ["On-site", "Hybrid", "Remote"]

# ---- Thresholds ----
GHOST_AFTER_DAYS = 21       # no reply after this many days = ghosted
FOLLOW_UP_AFTER_DAYS = 7    # no reply after this many days = time to follow up