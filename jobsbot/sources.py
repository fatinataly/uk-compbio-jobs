"""Adapters for public applicant-tracking-system (ATS) job board APIs.

Every adapter takes one employer entry from config.yaml and returns a list of
Job objects. Nothing here scrapes LinkedIn or Indeed: each source is the
employer's own careers board.

Supported `ats` values:
  greenhouse       slug                       boards-api.greenhouse.io
  lever            slug, [region: eu]         api.lever.co / api.eu.lever.co
  ashby            slug                       api.ashbyhq.com
  workday          host, tenant, site         {host}/wday/cxs/{tenant}/{site}/jobs
  smartrecruiters  slug                       api.smartrecruiters.com
  rss              url, [company_from_title]  any RSS 2.0 feed (e.g. jobs.ac.uk)
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from . import http


@dataclass
class Job:
    company: str
    title: str
    location: str
    url: str
    posted: date | None
    source: str
    categories: list[str] = field(default_factory=list)
    sponsor: bool = False
    life_sciences: bool = True  # employer is a biotech/pharma/research org

    @property
    def key(self) -> str:
        return self.url.split("?")[0].rstrip("/")


# ---------------------------------------------------------------- helpers

def _iso_date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, (int, float)):  # epoch milliseconds (Lever)
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date()
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(text).date()  # RFC 822 (RSS)
    except (TypeError, ValueError):
        return None


_WD_DAYS = re.compile(r"(\d+)\+?\s+days?\s+ago", re.I)


def workday_posted(text: str | None, today: date | None = None) -> date | None:
    """Turn Workday's 'Posted 3 Days Ago' style strings into a date."""
    if not text:
        return None
    today = today or date.today()
    low = text.lower()
    if "today" in low:
        return today
    if "yesterday" in low:
        return today - timedelta(days=1)
    m = _WD_DAYS.search(low)
    if m:
        return today - timedelta(days=int(m.group(1)))
    return None


# ---------------------------------------------------------------- adapters

def greenhouse(emp: dict, keywords: list[str]) -> list[Job]:
    data = http.get_json(f"https://boards-api.greenhouse.io/v1/boards/{emp['slug']}/jobs")
    jobs = []
    for j in data.get("jobs", []):
        jobs.append(Job(
            company=emp["name"],
            title=j.get("title", "").strip(),
            location=(j.get("location") or {}).get("name", ""),
            url=j.get("absolute_url", ""),
            posted=_iso_date(j.get("first_published") or j.get("updated_at")),
            source="greenhouse",
        ))
    return jobs


def lever(emp: dict, keywords: list[str]) -> list[Job]:
    base = "https://api.eu.lever.co" if emp.get("region") == "eu" else "https://api.lever.co"
    data = http.get_json(f"{base}/v0/postings/{emp['slug']}?mode=json")
    jobs = []
    for j in data:
        cats = j.get("categories") or {}
        locs = cats.get("allLocations") or [cats.get("location", "")]
        jobs.append(Job(
            company=emp["name"],
            title=j.get("text", "").strip(),
            location="; ".join(l for l in locs if l),
            url=j.get("hostedUrl", ""),
            posted=_iso_date(j.get("createdAt")),
            source="lever",
        ))
    return jobs


def ashby(emp: dict, keywords: list[str]) -> list[Job]:
    data = http.get_json(f"https://api.ashbyhq.com/posting-api/job-board/{emp['slug']}")
    jobs = []
    for j in data.get("jobs", []):
        if j.get("isListed") is False:
            continue
        locs = [j.get("location", "")]
        for sec in j.get("secondaryLocations") or []:
            locs.append(sec.get("location", "") if isinstance(sec, dict) else str(sec))
        addr = ((j.get("address") or {}).get("postalAddress") or {}).get("addressCountry")
        if addr:
            locs.append(addr)
        jobs.append(Job(
            company=emp["name"],
            title=j.get("title", "").strip(),
            location="; ".join(dict.fromkeys(l for l in locs if l)),
            url=j.get("jobUrl", ""),
            posted=_iso_date(j.get("publishedAt")),
            source="ashby",
        ))
    return jobs


def workday(emp: dict, keywords: list[str]) -> list[Job]:
    """Workday boards are large, so search them once per keyword."""
    host, tenant, site = emp["host"], emp["tenant"], emp["site"]
    endpoint = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    seen: dict[str, Job] = {}
    for kw in emp.get("search_terms") or keywords:
        offset = 0
        while offset < 200:  # 10 pages max per keyword
            payload = {"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": kw}
            data = http.post_json(endpoint, payload)
            postings = data.get("jobPostings", [])
            for j in postings:
                path = j.get("externalPath", "")
                url = f"https://{host}/{site}{path}"
                if url in seen:
                    continue
                seen[url] = Job(
                    company=emp["name"],
                    title=j.get("title", "").strip(),
                    location=j.get("locationsText", ""),
                    url=url,
                    posted=workday_posted(j.get("postedOn")),
                    source="workday",
                )
            if len(postings) < 20:
                break
            offset += 20
    return list(seen.values())


def smartrecruiters(emp: dict, keywords: list[str]) -> list[Job]:
    jobs, offset = [], 0
    while True:
        url = (f"https://api.smartrecruiters.com/v1/companies/{emp['slug']}/postings"
               f"?country=gb&limit=100&offset={offset}")
        data = http.get_json(url)
        for j in data.get("content", []):
            loc = j.get("location") or {}
            jobs.append(Job(
                company=emp["name"],
                title=j.get("name", "").strip(),
                location=", ".join(x for x in (loc.get("city"), "United Kingdom") if x),
                url=f"https://jobs.smartrecruiters.com/{emp['slug']}/{j.get('id')}",
                posted=_iso_date(j.get("releasedDate")),
                source="smartrecruiters",
            ))
        offset += 100
        if offset >= data.get("totalFound", 0) or offset > 1000:
            break
    return jobs


def rss(emp: dict, keywords: list[str]) -> list[Job]:
    """Generic RSS 2.0 feed. Feeds are assumed to be UK-only (e.g. jobs.ac.uk)."""
    root = ET.fromstring(http.get_text(emp["url"]).encode("utf-8"))
    jobs = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        company = emp.get("name", "")
        if emp.get("company_from_title"):
            # e.g. "Bioinformatician - University of Leeds"  -> split on last " - "
            if " - " in title:
                title, company = title.rsplit(" - ", 1)
        location = emp.get("location", "United Kingdom")
        jobs.append(Job(
            company=company.strip() or "Unknown",
            title=title.strip(),
            location=location,
            url=(item.findtext("link") or "").strip(),
            posted=_iso_date(item.findtext("pubDate")),
            source="rss",
        ))
    return jobs


ADAPTERS = {
    "greenhouse": greenhouse,
    "lever": lever,
    "ashby": ashby,
    "workday": workday,
    "smartrecruiters": smartrecruiters,
    "rss": rss,
}


def fetch(emp: dict, keywords: list[str]) -> list[Job]:
    adapter = ADAPTERS.get(emp.get("ats", ""))
    if adapter is None:
        raise ValueError(f"unknown ats '{emp.get('ats')}' for {emp.get('name')}")
    jobs = adapter(emp, keywords)
    for job in jobs:
        job.life_sciences = emp.get("life_sciences", True)
    return jobs
