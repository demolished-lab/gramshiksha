#!/usr/bin/env python3
"""Validate and summarize a Lighthouse JSON report for scheduled monitoring."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--min-performance", type=int, default=90)
    parser.add_argument("--min-seo", type=int, default=90)
    args = parser.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    scores = {
        name: round(category["score"] * 100)
        for name, category in report["categories"].items()
        if category.get("score") is not None
    }
    audits = report.get("audits", {})
    metrics = {
        key: audits[key].get("displayValue", "n/a")
        for key in ("first-contentful-paint", "largest-contentful-paint", "total-blocking-time", "cumulative-layout-shift")
        if key in audits
    }
    print(json.dumps({"scores": scores, "metrics": metrics}, indent=2))

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("## Weekly Lighthouse monitoring\n\n")
            handle.write("| Category | Score |\n|---|---:|\n")
            for name, score in scores.items():
                handle.write(f"| {name.title()} | {score}/100 |\n")
            handle.write("\n| Core metric | Value |\n|---|---|\n")
            for name, value in metrics.items():
                handle.write(f"| {name} | {value} |\n")

    failures = []
    if scores.get("performance", 0) < args.min_performance:
        failures.append(f"performance below {args.min_performance}")
    if scores.get("seo", 0) < args.min_seo:
        failures.append(f"SEO below {args.min_seo}")
    if failures:
        raise SystemExit("Lighthouse monitoring threshold failed: " + ", ".join(failures))


if __name__ == "__main__":
    main()
