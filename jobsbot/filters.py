"""Title and location filters: UK only, entry level, in scope."""

from __future__ import annotations

import re
from datetime import date, timedelta

from .sources import Job

# Strong UK signals: any of these means the role has a UK location.
_UK_STRONG = re.compile(
    r"\b(united kingdom|u\.k\.|uk|great britain|gb|england|scotland|wales|"
    r"northern ireland)\b",
    re.I,
)

# UK places. Cambridge and a few others also exist in the US, so a place name
# only counts when no US signal appears in the same location string.
_UK_PLACES = re.compile(
    r"\b(london|cambridge|oxford|edinburgh|glasgow|manchester|birmingham|leeds|"
    r"bristol|sheffield|nottingham|newcastle|liverpool|cardiff|belfast|dundee|"
    r"aberdeen|st andrews|york|leicester|southampton|exeter|norwich|reading|"
    r"brighton|coventry|warwick|bath|durham|lancaster|swansea|hinxton|"
    r"stevenage|macclesfield|alderley|harwell|didcot|abingdon|milton park|"
    r"slough|uxbridge|sandwich|ware|harlow|guildford|surrey|hertfordshire|"
    r"cambridgeshire|oxfordshire|kent|cheshire|babraham|granta park|"
    r"chesterford|porton down|wellcome genome campus|stevenage bioscience)\b",
    re.I,
)

_US_SIGNAL = re.compile(
    r"\b(usa|united states|u\.s\.|us|ma|massachusetts|ny|nj|ca|california|"
    r"ohio|oh|pa|pennsylvania|ontario|canada)\b",
    re.I,
)


def is_uk(location: str) -> bool:
    if not location:
        return False
    for part in re.split(r"[;|/]| or ", location):
        if _UK_STRONG.search(part):
            return True
        if _UK_PLACES.search(part) and not _US_SIGNAL.search(part):
            return True
    return False


def _compile(words: list[str]) -> re.Pattern:
    return re.compile(r"\b(" + "|".join(words) + r")\b", re.I)


class TitleFilter:
    def __init__(self, cfg: dict):
        self.exclude = _compile(cfg["exclude_titles"])
        self.categories = [
            (c["slug"], c.get("needs_bio_context", False), _compile(c["keywords"]))
            for c in cfg["categories"]
        ]
        self.bio = _compile(cfg["bio_context_keywords"])
        self.early = _compile(cfg["early_career_keywords"])
        self.early_slug = cfg["early_career_list"]["slug"]

    def classify(self, title: str, life_sciences: bool = True) -> list[str]:
        """Return the list slugs a title belongs to, or [] if out of scope."""
        if self.exclude.search(title):
            return []
        slugs = []
        for slug, needs_bio, pattern in self.categories:
            if needs_bio and not life_sciences and not self.bio.search(title):
                continue  # e.g. a generic ML role at a non-bio company
            if pattern.search(title):
                slugs.append(slug)
                break  # one subject list per role, first match wins
        if slugs and self.early.search(title):
            slugs.append(self.early_slug)
        return slugs


def apply(jobs: list[Job], cfg: dict, today: date | None = None) -> list[Job]:
    today = today or date.today()
    tf = TitleFilter(cfg)
    max_age = cfg.get("max_age_days", 120)
    cutoff = today - timedelta(days=max_age)
    keep, seen = [], set()
    for job in jobs:
        if not job.title or not job.url or job.key in seen:
            continue
        if not is_uk(job.location):
            continue
        if job.posted and job.posted < cutoff:
            continue
        cats = tf.classify(job.title, job.life_sciences)
        if not cats:
            continue
        job.categories = cats
        seen.add(job.key)
        keep.append(job)
    return keep
