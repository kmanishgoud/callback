"""
Build the weekly report HTML from the metrics, using templates/report.html.j2.

Preview in your browser from the project root:
    python src/report.py
"""
import math
import webbrowser
from datetime import date

from jinja2 import Environment, FileSystemLoader

import config

TEMPLATE_DIR = config.ROOT / "templates"
TEMPLATE_NAME = "report.html.j2"


# ---------------------------------------------------------------- formatting helpers

def _pct(x) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "–"
    return f"{x:.0%}"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


# ---------------------------------------------------------------- report pieces

def summary_line(k: dict, events) -> str:
    """One sentence that sums up the week."""
    diff = k["apps_this_week"] - k["apps_last_week"]
    text = f"You sent {_plural(k['apps_this_week'], 'application')} ({diff:+d} vs last week). "
    if len(events):
        counts = events["event"].value_counts()
        parts = [_plural(int(n), label.lower()) for label, n in counts.items()]
        text += "This week: " + ", ".join(parts) + "."
    else:
        text += "No replies this week."
    return text


def kpi_rows(k: dict) -> list[list[dict]]:
    diff = k["apps_this_week"] - k["apps_last_week"]
    days = k["median_days_to_reply"]
    tiles = [
        {"label": "Applications this week", "value": k["apps_this_week"], "note": f"{diff:+d} vs last week"},
        {"label": "Reply rate", "value": _pct(k["reply_rate"]), "note": "any response"},
        {"label": "Screening rate", "value": _pct(k["screen_rate"]), "note": "led to a call"},
        {"label": "Interview rate", "value": _pct(k["interview_rate"]), "note": _plural(k["offers"], "offer") + " so far"},
        {"label": "Median days to reply", "value": "–" if days is None else f"{days:.0f}", "note": "when they do reply"},
        {"label": "Active pipeline", "value": k["active"], "note": "screening + interviewing"},
    ]
    return [tiles[:3], tiles[3:]]


def source_note(sources) -> str | None:
    """Name the best source, with a warning if the sample is small."""
    if sources.empty:
        return None
    best = sources["screen_rate"].idxmax()
    row = sources.loc[best]
    n = int(row["applications"])
    note = f"{best} leads to a screening call most often ({row['screen_rate']:.0%} of {n} applications)."
    if n < 10:
        note += " Small sample, so treat it as a hint rather than a rule."
    return note


def build_context(metrics: dict, issues: list, image_src: dict[str, str]) -> dict:
    """Everything the template needs, already formatted."""
    k = metrics["kpis"]

    events = [
        {"date": r.date.strftime("%a %d %b"), "event": r.event, "company": r.company, "role": r.role}
        for r in metrics["events"].itertuples()
    ]
    follow_ups = [
        {"company": r.company, "role": r.role, "source": r.source, "days": int(r.days_since_applied)}
        for r in metrics["follow_ups"].head(10).itertuples()
    ]
    ghosted = [f"{r.company} ({r.role})" for r in metrics["newly_ghosted"].itertuples()]

    charts = [
        {"title": "Your funnel", "note": "Every application so far, and how far each one got.", "src": image_src["funnel"]},
        {"title": "Applications per week", "note": "The last 8 weeks, with this week highlighted.", "src": image_src["trend"]},
        {"title": "Which sources work", "note": source_note(metrics["sources"]), "src": image_src["sources"]},
    ]

    return {
        "week_label": f"{k['week_start']:%d %b} – {k['week_end']:%d %b %Y}",
        "summary": summary_line(k, metrics["events"]),
        "kpi_rows": kpi_rows(k),
        "events": events,
        "follow_ups": follow_ups,
        "follow_up_total": len(metrics["follow_ups"]),
        "ghosted": ghosted,
        "charts": charts,
        "status": [{"label": s, "count": int(n)} for s, n in metrics["status_counts"].items()],
        "issues_total": len(issues),
        "issues_fixed": sum(i.level == "fixed" for i in issues),
        "attention": [i for i in issues if i.level != "fixed"],
        "follow_up_days": config.FOLLOW_UP_AFTER_DAYS,
        "ghost_days": config.GHOST_AFTER_DAYS,
        "mature_days": config.MATURE_AFTER_DAYS,
        "mature_apps": k["mature_apps"],
        "total_apps": k["total_apps"],
        "generated_on": date.today().strftime("%d %b %Y"),
        "using_sample": config.tracker_path() == config.SAMPLE_TRACKER,
    }


def render_html(context: dict) -> str:
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)
    return env.get_template(TEMPLATE_NAME).render(**context)


# ---------------------------------------------------------------- preview

if __name__ == "__main__":
    from charts import make_charts
    from metrics import build_metrics
    from tracker import load_tracker

    today = config.report_date()
    df, issues = load_tracker(today=today)
    metrics = build_metrics(df, today)
    chart_paths = make_charts(metrics)

    # In the preview, charts load from files next to the HTML (the email will use cid: links instead)
    image_src = {name: f"charts/{path.name}" for name, path in chart_paths.items()}
    html = render_html(build_context(metrics, issues, image_src))

    out = config.OUTPUT_DIR / "report_preview.html"
    out.write_text(html, encoding="utf-8")
    print(f"Saved: {out.relative_to(config.ROOT)}")
    webbrowser.open(out.as_uri())