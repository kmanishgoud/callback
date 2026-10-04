"""
Generate a realistic SAMPLE job-application tracker for Callback.

The sample lets the project be built, tested and published without
exposing anyone's real job search. Company names are fictional.

Run from the project root:
    python src/generate_sample.py
"""
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT_FILE = ROOT / "data" / "sample" / "applications_sample.xlsx"

rng = np.random.default_rng(3)          # fixed seed = same sample every run

N_APPS = 140
START = date(2026, 6, 15)
TODAY = date(2026, 10, 2)                # the sample's "today"

# source: (share of applications, chance of a screening call)
SOURCES = {
    "LinkedIn Easy Apply":   (0.30, 0.06),
    "LinkedIn":              (0.20, 0.14),
    "Company website":       (0.18, 0.18),
    "Welcome to the Jungle": (0.12, 0.16),
    "Indeed":                (0.10, 0.05),
    "Recruiter":             (0.05, 0.45),
    "Referral":              (0.05, 0.55),
}
ROLES = {
    "Data Analyst": 0.35, "Junior Data Analyst": 0.15, "Business Analyst": 0.15,
    "BI Analyst": 0.12, "Analytics Engineer": 0.08, "Reporting Analyst": 0.08,
    "Junior Data Engineer": 0.07,
}
LOCATIONS = {"Paris": 0.45, "Remote": 0.20, "Lyon": 0.10, "London": 0.10,
             "Amsterdam": 0.10, "Lille": 0.05}
WORK_MODES = {"Hybrid": 0.60, "On-site": 0.40}

PREFIXES = ["North", "Blue", "Silver", "Bright", "Atlas", "Nova", "Cedar",
            "Harbor", "Summit", "Quantum", "Vertex", "Lumen"]
SUFFIXES = ["Analytics", "Retail", "Bank", "Logistics", "Health", "Energy",
            "Labs", "Insurance", "Media", "Mobility"]


def pick(options: dict, size: int) -> np.ndarray:
    """Weighted random choice from {option: weight}."""
    keys = list(options)
    weights = np.array(list(options.values()), dtype=float)
    return rng.choice(keys, size=size, p=weights / weights.sum())


def after(d: date, lo: int, hi: int) -> date:
    """A date between lo and hi days after d."""
    return d + timedelta(days=int(rng.integers(lo, hi + 1)))


def simulate_outcome(applied: date, p_screen: float) -> dict:
    """Simulate what happens to one application, stage by stage."""
    screen = interview = offer = rejected = None

    if rng.random() < p_screen:                       # got a screening call
        screen = after(applied, 2, 14)
        if rng.random() < 0.55:                       # moved to interview
            interview = after(screen, 4, 12)
            if rng.random() < 0.12:                   # offer
                offer = after(interview, 7, 21)
            elif rng.random() < 0.80:                 # rejected after interview
                rejected = after(interview, 3, 14)
        elif rng.random() < 0.60:                     # rejected after screening
            rejected = after(screen, 2, 10)
    elif rng.random() < 0.35:                         # rejected without a call
        rejected = after(applied, 3, 40)
    # otherwise: never hear back (ghosted)

    def happened(d):                                  # future events haven't happened yet
        return d if d is not None and d <= TODAY else None

    return {
        "date_screen": happened(screen),
        "date_interview": happened(interview),
        "date_offer": happened(offer),
        "date_rejected": happened(rejected),
    }


def add_typos(df: pd.DataFrame) -> pd.DataFrame:
    """Real trackers are filled in by hand and contain mistakes.
    Step 3's validator must catch every one of these."""
    df.loc[5, "source"] = "linkedin"                          # wrong capitalisation
    df.loc[17, "source"] = "Referral "                        # trailing space
    df.loc[33, "company"] = "  " + df.loc[33, "company"]      # leading spaces
    df.loc[48, "date_screen"] = df.loc[48, "date_applied"] - timedelta(days=3)  # screen BEFORE applying
    df.loc[60, "work_mode"] = "hybrid"                        # wrong capitalisation
    df = pd.concat([df, df.loc[[72]]], ignore_index=True)     # duplicate row
    return df


def main() -> None:
    span = (TODAY - START).days
    # Triangular distribution: the job search ramps up over time
    offsets = rng.triangular(0, span, span, size=N_APPS).astype(int)
    applied_dates = sorted(START + timedelta(days=int(o)) for o in offsets)
    # Move weekend applications to the following Monday (capped at TODAY)
    applied_dates = [
        min(d + timedelta(days=(7 - d.weekday()) % 7) if d.weekday() >= 5 else d, TODAY)
        for d in applied_dates
    ]

    sources = pick({k: v[0] for k, v in SOURCES.items()}, N_APPS)
    locations = pick(LOCATIONS, N_APPS)
    work_modes = pick(WORK_MODES, N_APPS)
    companies = [f"{rng.choice(PREFIXES)} {rng.choice(SUFFIXES)}" for _ in range(N_APPS)]

    rows = []
    for i in range(N_APPS):
        rows.append({
            "app_id": f"A{i + 1:03d}",
            "company": companies[i],
            "role": pick(ROLES, 1)[0],
            "location": locations[i],
            "work_mode": "Remote" if locations[i] == "Remote" else work_modes[i],
            "source": sources[i],
            "date_applied": applied_dates[i],
            **simulate_outcome(applied_dates[i], SOURCES[sources[i]][1]),
            "notes": "",
            "job_url": "",
        })

    df = pd.DataFrame(rows)
    df = add_typos(df)

    date_cols = ["date_applied", "date_screen", "date_interview", "date_offer", "date_rejected"]
    for col in date_cols:
        df[col] = pd.to_datetime(df[col])

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(OUT_FILE, index=False, sheet_name="applications")

    # ---- Summary ----
    print(f"Applications:  {len(df)} (includes 1 deliberate duplicate)")
    print(f"Date range:    {df['date_applied'].min().date()} to {df['date_applied'].max().date()}")
    print(f"Screen calls:  {df['date_screen'].notna().sum()}")
    print(f"Interviews:    {df['date_interview'].notna().sum()}")
    print(f"Offers:        {df['date_offer'].notna().sum()}")
    print(f"Rejections:    {df['date_rejected'].notna().sum()}")
    print()
    print(df["source"].value_counts().to_string())
    print()
    print(f"Saved: {OUT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()