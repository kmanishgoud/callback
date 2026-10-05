import config
from helpers import app, make_tracker
from metrics import build_metrics
from tracker import load_tracker


def test_validator_fixes_warns_and_excludes(tmp_path):
    messy = make_tracker([
        app("A1", "2026-09-01", source=" linkedin "),     # spaces + wrong case
        app("A1", "2026-09-01", source=" linkedin "),     # exact duplicate
        app("A2", None),                                   # missing date_applied
        app("A3", "2026-09-01", source="Carrier pigeon"),  # unknown source
    ])
    path = tmp_path / "tracker.xlsx"
    messy.to_excel(path, index=False, sheet_name="applications")

    df, issues = load_tracker(path, today=config.SAMPLE_REPORT_DATE)

    assert sorted(df["app_id"]) == ["A1", "A3"]                        # duplicate + broken row gone
    assert df.loc[df["app_id"] == "A1", "source"].item() == "LinkedIn"  # cleaned
    assert any(i.level == "error" and i.app_id == "A2" for i in issues)
    assert any(i.level == "warning" and "Carrier pigeon" in i.message for i in issues)
    assert any(i.message == "Duplicate row removed" for i in issues)


def test_sample_tracker_catches_every_planted_issue():
    df, issues = load_tracker(config.SAMPLE_TRACKER, today=config.SAMPLE_REPORT_DATE)
    assert len(df) == 140
    assert sum(i.level == "fixed" for i in issues) == 5
    assert sum(i.level == "warning" for i in issues) == 1
    assert set(df["source"]) <= set(config.SOURCES)


def test_sample_report_end_to_end():
    df, _ = load_tracker(config.SAMPLE_TRACKER, today=config.SAMPLE_REPORT_DATE)
    m = build_metrics(df, config.SAMPLE_REPORT_DATE)
    counts = m["funnel"]["count"].tolist()
    assert counts == sorted(counts, reverse=True)
    assert m["status_counts"].sum() == len(df)