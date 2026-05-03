#!/usr/bin/env python3
"""
Orchestrate all article GIF renders.

Renders each chart in up to two variants:
  desktop  — 1200×400, wide, for web/desktop articles
  mobile   — 800×800,  square, for mobile / social cards

Usage:
    python article_gifs/render_all.py                                  # today, both variants
    python article_gifs/render_all.py --date 2026-04-14
    python article_gifs/render_all.py --format desktop                 # desktop only
    python article_gifs/render_all.py --format mobile                  # square only
    python article_gifs/render_all.py --charts price-chart,trade-levels
    python article_gifs/render_all.py --date 2026-04-14 --format all --charts price-chart

Writes: article_gifs/out/manifest_<date>.json
Manifest structure:
  {
    "date": "2026-04-14",
    "format": "all",
    "gifs": {
      "price-chart": {
        "desktop": "article_gifs/price-chart/out/price_chart_2026-04-14_desktop.gif",
        "mobile":  "article_gifs/price-chart/out/price_chart_2026-04-14_mobile.gif"
      },
      ...
    }
  }
"""

import json
import os
import subprocess
import sys
from datetime import date as date_type
from pathlib import Path

# ─── Config ───────────────────────────────────────────────────────────────────
THIS_DIR     = Path(__file__).parent
PROJECT_ROOT = THIS_DIR.parent

CHARTS = [
    {
        "name":  "price-chart",
        "fetch": THIS_DIR / "price-chart" / "fetch_price_chart.py",
        "cwd":   THIS_DIR / "price-chart",
        "variants": {
            "desktop": {"comp": "PriceChart",       "out": "out/price_chart_{date}_desktop.gif"},
            "mobile":  {"comp": "PriceChartSquare", "out": "out/price_chart_{date}_mobile.gif"},
        },
    },
    {
        "name":  "technical-dashboard",
        "fetch": THIS_DIR / "technical-dashboard" / "fetch_technical_dashboard.py",
        "cwd":   THIS_DIR / "technical-dashboard",
        "variants": {
            "desktop": {"comp": "TechnicalDashboard",       "out": "out/technical_dashboard_{date}_desktop.gif"},
            "mobile":  {"comp": "TechnicalDashboardSquare", "out": "out/technical_dashboard_{date}_mobile.gif"},
        },
    },
    {
        "name":  "correlated-heatmap",
        "fetch": THIS_DIR / "correlated-heatmap" / "fetch_correlated_heatmap.py",
        "cwd":   THIS_DIR / "correlated-heatmap",
        "variants": {
            "desktop": {"comp": "CorrelatedHeatmap",       "out": "out/correlated_heatmap_{date}_desktop.gif"},
            "mobile":  {"comp": "CorrelatedHeatmapSquare", "out": "out/correlated_heatmap_{date}_mobile.gif"},
        },
    },
]

VALID_FORMATS = ("desktop", "mobile", "all")


# ─── Argument parsing ─────────────────────────────────────────────────────────
def parse_args():
    args = sys.argv[1:]
    target_date   = str(date_type.today())
    fmt           = "mobile"
    charts_filter = None

    i = 0
    while i < len(args):
        if args[i] == "--date" and i + 1 < len(args):
            target_date = args[i + 1]; i += 2
        elif args[i] == "--format" and i + 1 < len(args):
            fmt = args[i + 1]; i += 2
        elif args[i] == "--charts" and i + 1 < len(args):
            charts_filter = set(args[i + 1].split(",")); i += 2
        else:
            i += 1

    if fmt not in VALID_FORMATS:
        print(f"Error: --format must be one of {VALID_FORMATS}, got '{fmt}'")
        sys.exit(1)

    return target_date, fmt, charts_filter


# ─── Helpers ──────────────────────────────────────────────────────────────────
def run(cmd, cwd=None, env=None, timeout=300, shell=False):
    result = subprocess.run(
        cmd, cwd=cwd, env=env,
        capture_output=True, text=True, timeout=timeout, shell=shell,
    )
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode != 0:
        print(f"STDERR: {result.stderr[:500]}")
    return result.returncode == 0


def ensure_npm_deps(cwd: Path):
    """Run npm install only when node_modules is absent."""
    if (cwd / "node_modules").exists():
        return
    print(f"  npm install in {cwd.name}...")
    run("npm install", cwd=cwd, timeout=120, shell=True)


def render_variant(comp: str, out_path: Path, cwd: Path) -> bool:
    out_posix = str(out_path).replace("\\", "/")
    cmd = (
        f"npx remotion render {comp} {out_posix} "
        "--codec=gif --fps=15 --number-of-gif-loops=3 --scale=2"
    )
    return run(cmd, cwd=cwd, timeout=300, shell=True)


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    target_date, fmt, charts_filter = parse_args()

    # Which variant keys to render
    active_variants = ["desktop", "mobile"] if fmt == "all" else [fmt]

    print(f"Rendering article GIFs for {target_date}  [format: {fmt}]")

    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}
    manifest_gifs: dict[str, dict] = {}
    (THIS_DIR / "out").mkdir(exist_ok=True)

    for chart in CHARTS:
        name = chart["name"]
        if charts_filter and name not in charts_filter:
            continue

        print(f"\n--- {name} ---")
        cwd = chart["cwd"]

        # ── 1. Fetch data (once per chart) ─────────────────────────────────
        print("  Fetching data...")
        ok = run(
            [sys.executable, str(chart["fetch"]), "--date", target_date],
            cwd=PROJECT_ROOT, env=env, timeout=60,
        )
        if not ok:
            print(f"  WARN: fetch failed for {name}, skipping render.")
            continue

        # ── 2. npm install (first run only) ────────────────────────────────
        ensure_npm_deps(cwd)

        # ── 3. Render each requested variant ───────────────────────────────
        chart_paths: dict[str, str] = {}
        for variant_key in active_variants:
            v = chart["variants"][variant_key]
            out_name = v["out"].format(date=target_date)
            out_path = cwd / out_name
            out_path.parent.mkdir(exist_ok=True)

            print(f"  Rendering [{variant_key}] {v['comp']} -> {out_name}...")
            ok = render_variant(v["comp"], out_path, cwd)
            if not ok:
                print(f"  ERROR: render failed for {name} [{variant_key}]")
                continue

            size_kb = out_path.stat().st_size // 1024
            print(f"  OK  {out_path.name}  ({size_kb} kB)")
            chart_paths[variant_key] = out_path.relative_to(PROJECT_ROOT).as_posix()

        if chart_paths:
            manifest_gifs[name] = chart_paths

    # ── Write manifest (remove stale ones first) ─────────────────────────────
    manifest = {"date": target_date, "format": fmt, "gifs": manifest_gifs}
    manifest_path = THIS_DIR / "out" / f"manifest_{target_date}.json"
    for old in (THIS_DIR / "out").glob("manifest_*.json"):
        if old != manifest_path:
            old.unlink()
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nManifest: {manifest_path}")
    for chart_name, paths in manifest_gifs.items():
        for variant_key, path in paths.items():
            print(f"  {chart_name} [{variant_key}]: {path}")


if __name__ == "__main__":
    main()
