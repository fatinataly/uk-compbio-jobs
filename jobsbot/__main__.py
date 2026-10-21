"""Command line entry point.

    python -m jobsbot build    fetch every employer, filter, write README/lists/csv
    python -m jobsbot check    fetch every employer and report which sources work
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import yaml

from . import filters, render, sources, sponsors

ROOT = Path(__file__).resolve().parent.parent


def load_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def all_keywords(cfg: dict) -> list[str]:
    return cfg.get("workday_search_terms") or []


def fetch_all(cfg: dict) -> tuple[list[sources.Job], list[tuple[str, str, int]]]:
    """Returns (jobs, report) where report rows are (employer, status, raw count)."""
    employers = [e for e in cfg["employers"] if not e.get("disabled")]
    keywords = all_keywords(cfg)

    def run(emp):
        try:
            got = sources.fetch(emp, keywords)
            return emp, got, "ok"
        except Exception as err:
            return emp, [], f"ERROR {err.__class__.__name__}: {str(err)[:120]}"

    jobs, report = [], []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for emp, got, status in pool.map(run, employers):
            jobs.extend(got)
            report.append((emp["name"], status, len(got)))
    return jobs, report


def apply_first_seen(jobs: list[sources.Job], state_path: Path, today: date) -> None:
    """Remember when each URL was first seen; use it when a board gives no date."""
    state = {}
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    live = {}
    for j in jobs:
        first = state.get(j.key, today.isoformat())
        live[j.key] = first
        if j.posted is None:
            j.posted = date.fromisoformat(first)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(live, indent=1, sort_keys=True), encoding="utf-8")


def cmd_build(cfg: dict, root: Path, today: date) -> int:
    raw, report = fetch_all(cfg)
    jobs = filters.apply(raw, cfg, today)

    reg_path, note = sponsors.download(root / "data" / "sponsor_register.csv")
    register = sponsors.Register.from_csv(reg_path)
    aliases = {e["name"]: e.get("sponsor_names", []) for e in cfg["employers"]}
    for j in jobs:
        j.sponsor = register.matches(j.company, aliases.get(j.company))

    apply_first_seen(jobs, root / "data" / "first_seen.json", today)
    render.build(root, jobs, cfg, today, f"register checked {today:%-d %b %Y}")

    failed = [r for r in report if r[1] != "ok"]
    print(f"{len(raw)} postings fetched, {len(jobs)} kept, "
          f"{sum(j.sponsor for j in jobs)} at licensed sponsors; register: {note} "
          f"({len(register)} Skilled Worker sponsors)")
    for name, status, _ in failed:
        print(f"  ! {name}: {status}")
    # Fail the run only if nothing at all could be fetched.
    return 1 if len(failed) == len(report) else 0


def cmd_check(cfg: dict) -> int:
    raw, report = fetch_all(cfg)
    kept = {j.key for j in filters.apply(list(raw), cfg)}
    by_company: dict[str, int] = {}
    uk: dict[str, int] = {}
    for j in raw:
        if j.key in kept:
            by_company[j.company] = by_company.get(j.company, 0) + 1
        if filters.is_uk(j.location):
            uk[j.company] = uk.get(j.company, 0) + 1
    print(f"{'Employer':40} {'Status':10} {'Fetched':>8} {'UK':>5} {'Kept':>5}")
    for name, status, n in sorted(report):
        short = "ok" if status == "ok" else "ERROR"
        print(f"{name[:40]:40} {short:10} {n:>8} {uk.get(name, 0):>5} {by_company.get(name, 0):>5}")
        if status != "ok":
            print(f"    {status}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jobsbot")
    parser.add_argument("command", choices=["build", "check"])
    parser.add_argument("--config", default=str(ROOT / "config" / "config.yaml"))
    args = parser.parse_args(argv)
    cfg = load_config(Path(args.config))
    if args.command == "check":
        return cmd_check(cfg)
    return cmd_build(cfg, ROOT, date.today())


if __name__ == "__main__":
    sys.exit(main())
