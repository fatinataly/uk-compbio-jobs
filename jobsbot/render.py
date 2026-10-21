"""Write README.md, lists/*.md and csv/*.csv from the filtered jobs."""

from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from pathlib import Path

from .sources import Job

VISA_TEXT = "✅ Licensed sponsor"


def _cell(text: str, limit: int = 60) -> str:
    text = " ".join((text or "").split()).replace("|", "/")
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _posted(d: date | None) -> str:
    return d.strftime("%-d %b") if d else ""


def _sort(jobs: list[Job]) -> list[Job]:
    return sorted(jobs, key=lambda j: (j.posted or date.min, j.company), reverse=True)


def table(jobs: list[Job]) -> str:
    rows = [
        "| Company | Role | Location | Posted | Visa signal |",
        "| --- | --- | --- | --- | --- |",
    ]
    for j in _sort(jobs):
        rows.append(
            f"| **{_cell(j.company, 40)}** | [{_cell(j.title, 90)}]({j.url}) | "
            f"{_cell(j.location, 45)} | {_posted(j.posted)} | {VISA_TEXT if j.sponsor else ''} |"
        )
    return "\n".join(rows)


def write_csv(path: Path, jobs: list[Job]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["company", "title", "location", "posted", "url", "lists", "sponsor_register", "source"])
        for j in _sort(jobs):
            w.writerow([j.company, j.title, j.location, j.posted.isoformat() if j.posted else "",
                        j.url, ";".join(j.categories), "yes" if j.sponsor else "", j.source])


def build(root: Path, jobs: list[Job], cfg: dict, today: date, register_note: str) -> None:
    site = cfg["site"]
    lists = [(c["slug"], c["name"]) for c in cfg["categories"]]
    lists.append((cfg["early_career_list"]["slug"], cfg["early_career_list"]["name"]))

    (root / "lists").mkdir(exist_ok=True)
    summary_rows = ["| List | Roles | Employers |", "| --- | --- | --- |"]
    for slug, name in lists:
        sub = [j for j in jobs if slug in j.categories]
        write_csv(root / "csv" / f"{slug}.csv", sub)
        employers = len({j.company for j in sub})
        summary_rows.append(f"| [{name}](lists/{slug}.md) | {len(sub)} | {employers} |")
        body = (
            f"# 🧬 {name}\n\n"
            f"{len(sub)} open roles at {employers} UK employers. Checked {today:%-d %b %Y}.\n\n"
            f"[⬅️ Back to all lists](../README.md)\n\n---\n\n"
            + (table(sub) if sub else "_No open roles this week._")
            + "\n"
        )
        (root / "lists" / f"{slug}.md").write_text(body, encoding="utf-8")
    write_csv(root / "csv" / "all.csv", jobs)

    write_json(root / "json" / "jobs.json", jobs, today, lists)

    week_ago = today - timedelta(days=7)
    new = sum(1 for j in jobs if j.posted and j.posted >= week_ago)
    sponsors = sum(1 for j in jobs if j.sponsor)
    employers = len({j.company for j in jobs})
    n_sources = len([e for e in cfg["employers"] if not e.get("disabled")])

    author = site.get("author", "")
    blog, blog_url = site.get("blog_name", ""), site.get("blog_url", "")
    credit = []
    if author:
        credit.append(f"[{author}](https://github.com/{author})")
    if blog:
        credit.append(f"[{blog}]({blog_url})" if blog_url else blog)
    footer = f"*Maintained by {' · '.join(credit)}.*" if credit else ""

    readme = f"""# 🧬 {site['title']}

---

## 📌 Overview

This repository contains a **weekly updated list of {site['tagline']}** in the United Kingdom.

> **{len(jobs)} open roles at {employers} UK employers** · {new} posted in the last 7 days · {sponsors} at licensed visa sponsors
> Last checked: **{today:%-d %B %Y}**

{site['intro']}

Every role comes straight from the employer's own careers site. Nothing is copied from LinkedIn or Indeed. The list is rebuilt every Monday, so closed roles drop off and new ones come in.

---

## 🎯 Objectives

- Collect entry level roles directly from employers' own job boards.
- Keep only UK-based, early career positions in computational life sciences.
- Flag employers licensed by the Home Office to sponsor Skilled Worker visas.
- Publish the results as Markdown, CSV and JSON, refreshed automatically every week.

---

## 📋 Job Lists

{chr(10).join(summary_rows)}

Spreadsheet versions: [`csv/`](csv/) · JSON for websites: [`json/jobs.json`](json/jobs.json)

## 🧑‍🔬 All Roles

{table(jobs) if jobs else '_No open roles this week._'}

## 🛂 Visa Sponsorship Signal

A ✅ in the **Visa signal** column marks employers that appear on the Home Office [Register of Licensed Sponsors](https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers) for the **Skilled Worker** route ({register_note}).

A licence means the employer *can* sponsor, not that a given role will. Always confirm with the employer and check that the salary meets the Skilled Worker threshold.

---

## 🔬 Workflow Overview

The pipeline follows these stages:

1. **Fetch postings** — query the public job board APIs of {n_sources} employers (Greenhouse, Lever, Ashby, Workday, SmartRecruiters, RSS).
2. **Filter by location** — keep roles based in the United Kingdom.
3. **Filter by title** — keep in-scope subjects and drop senior, lead, manager and director titles.
4. **Classify** — assign each role to a subject list and, where relevant, the early career list.
5. **Match visa sponsors** — check each employer against the Home Office register.
6. **Publish** — write this README, the per-list pages, CSV and JSON files.

A GitHub Action ([`.github/workflows/weekly.yml`](.github/workflows/weekly.yml)) runs the tests and the pipeline every Monday and commits the results.

## 📂 Repository Structure

```
uk-compbio-jobs/
├── .github/workflows/
│   └── weekly.yml           # Weekly rebuild (GitHub Actions)
├── config/
│   └── config.yaml          # Employers, keywords and filters
├── environment/
│   └── environment.yml      # Conda environment definition
├── jobsbot/
│   ├── sources.py           # Job board adapters
│   ├── filters.py           # UK location and title filters
│   ├── sponsors.py          # Home Office sponsor register matching
│   ├── render.py            # README, lists, CSV and JSON output
│   └── __main__.py          # Command line entry point
├── lists/                   # Generated Markdown page per list
├── csv/                     # Generated CSV files
├── json/                    # Generated JSON for websites
├── data/                    # Sponsor register cache and first-seen dates
├── docs/
│   └── GUIA.md              # Setup guide (Spanish)
├── tests/
│   └── test_jobsbot.py      # Offline tests
├── requirements.txt         # pip dependencies (used by GitHub Actions)
└── README.md                # Generated every week
```

## 🔁 Reproducibility

- Configuration-based execution (`config/config.yaml`)
- Conda environment management
- Automated weekly runs with GitHub Actions
- Offline test suite run before every build

### Installation

```bash
git clone https://github.com/{author or '<user>'}/<this-repository>.git
cd <this-repository>
```

### Conda setup

```bash
conda env create -f environment/environment.yml
conda activate uk-compbio-jobs
```

### How to run

```bash
python -m jobsbot check    # test every employer's job board
python -m jobsbot build    # rebuild README, lists, CSV and JSON
python -m pytest -q        # run the tests
```

## ➕ Adding an Employer

Employers are listed in [`config/config.yaml`](config/config.yaml). Open a pull request adding one, or an issue with a link to its careers page.

---

## ⚠️ Limitations

- Only employers listed in the configuration are covered; this is not an exhaustive search of the UK job market.
- Seniority is inferred from job titles, so some roles may be misclassified.
- Some job boards do not give a posting date; the date first seen by this repository is used instead.
- The sponsor register shows which employers *can* sponsor, not which roles do.

---

{footer}
"""
    (root / "README.md").write_text(readme, encoding="utf-8")


def write_json(path: Path, jobs: list[Job], today: date, lists: list[tuple[str, str]]) -> None:
    """Machine-readable copy for websites (e.g. an Astro page)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated": today.isoformat(),
        "lists": [{"slug": s, "name": n} for s, n in lists],
        "jobs": [
            {
                "company": j.company,
                "title": j.title,
                "location": j.location,
                "posted": j.posted.isoformat() if j.posted else None,
                "url": j.url,
                "lists": j.categories,
                "sponsor": j.sponsor,
            }
            for j in _sort(jobs)
        ],
    }
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
