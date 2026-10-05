"""
Callback: build the weekly job-search report and email it.

Usage (from the project root):
    python src/main.py              build and send
    python src/main.py --dry-run    build only, don't send
    python src/main.py --preview    also open the report in your browser
"""
import argparse
import logging
import sys
import webbrowser

import config
from charts import make_charts
from metrics import build_metrics
from report import build_context, render_html, summary_line
from send_email import build_message, load_settings, send_message
from tracker import load_tracker

config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    handlers=[
        logging.FileHandler(config.OUTPUT_DIR / "callback.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logging.getLogger("matplotlib").setLevel(logging.WARNING)   # hide matplotlib's info chatter
log = logging.getLogger("callback")


def run(send: bool = True, preview: bool = False) -> None:
    today = config.report_date()
    log.info("Run started. Tracker: %s | report date: %s",
             config.tracker_path().relative_to(config.ROOT), today)

    df, issues = load_tracker(today=today)
    log.info("Loaded %d applications, %d tracker issues", len(df), len(issues))

    metrics = build_metrics(df, today)
    chart_paths = make_charts(metrics)

    # Browser preview: charts load from files next to the HTML
    preview_html = render_html(build_context(metrics, issues, {n: f"charts/{p.name}" for n, p in chart_paths.items()}))
    preview_path = config.OUTPUT_DIR / "report_preview.html"
    preview_path.write_text(preview_html, encoding="utf-8")
    log.info("Preview saved: %s", preview_path.relative_to(config.ROOT))
    if preview:
        webbrowser.open(preview_path.as_uri())

    if not send:
        log.info("Dry run: email not sent")
        return

    # Email version: charts referenced as embedded attachments (cid:)
    context = build_context(metrics, issues, {n: f"cid:{n}" for n in chart_paths})
    html = render_html(context)
    text = summary_line(metrics["kpis"], metrics["events"]) + "\n\nOpen this email in an HTML-capable app to see the full report."
    k = metrics["kpis"]
    subject = f"Callback · {context['week_label']} · {k['apps_this_week']} applications, {len(metrics['events'])} updates"

    settings = load_settings()
    msg = build_message(subject, html, text, chart_paths, settings["sender"], settings["recipient"])
    send_message(msg, settings)
    log.info("Email sent to %s", settings["recipient"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build and email the weekly Callback report.")
    parser.add_argument("--dry-run", action="store_true", help="build the report but don't send it")
    parser.add_argument("--preview", action="store_true", help="open the report in your browser")
    args = parser.parse_args()

    try:
        run(send=not args.dry_run, preview=args.preview)
    except Exception:
        log.exception("Callback failed")
        sys.exit(1)