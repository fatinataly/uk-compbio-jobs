"""Match employers against the Home Office Register of Licensed Sponsors.

The register is published on GOV.UK as a CSV whose file name changes with
every update, so the publication page is read first to find the current link.
A cached copy in data/ is used if GOV.UK cannot be reached.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from . import http

PAGE = "https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers"
_CSV_LINK = re.compile(r'https://assets\.publishing\.service\.gov\.uk/[^"\']+\.csv')

_SUFFIXES = re.compile(
    r"\b(the|limited|ltd|plc|llp|lp|inc|incorporated|llc|co|company|group|"
    r"holdings|uk|u k|gb|europe|international|services|operations|trading as.*)\b"
)


def normalise(name: str) -> str:
    text = name.lower().replace("&", " and ")
    text = re.sub(r"\(.*?\)", " ", text)
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = _SUFFIXES.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def download(cache: Path) -> tuple[Path, str]:
    """Fetch the latest register CSV into `cache`. Returns (path, status)."""
    try:
        html = http.get_text(PAGE)
        links = _CSV_LINK.findall(html)
        if not links:
            raise RuntimeError("no CSV link on the GOV.UK page")
        text = http.get_text(links[0])
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(text, encoding="utf-8")
        return cache, f"downloaded {links[0].rsplit('/', 1)[-1]}"
    except Exception as err:  # keep going with the cached copy
        if cache.exists():
            return cache, f"using cached register ({err.__class__.__name__})"
        return cache, f"register unavailable ({err})"


class Register:
    def __init__(self, names: set[str]):
        self.names = names
        self._by_first: dict[str, list[str]] = {}
        for n in names:
            if n:
                self._by_first.setdefault(n.split()[0], []).append(n)

    @classmethod
    def from_csv(cls, path: Path, routes: tuple[str, ...] = ("Skilled Worker",)) -> "Register":
        if not path.exists():
            return cls(set())
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        names = set()
        for row in csv.DictReader(io.StringIO(text)):
            route = (row.get("Route") or "").strip()
            if routes and not any(r.lower() in route.lower() for r in routes):
                continue
            names.add(normalise(row.get("Organisation Name") or ""))
        return cls(names)

    def __len__(self) -> int:
        return len(self.names)

    def matches(self, company: str, aliases: list[str] | None = None) -> bool:
        for candidate in [company, *(aliases or [])]:
            n = normalise(candidate)
            if not n:
                continue
            if n in self.names:
                return True
            # "astrazeneca" vs "astrazeneca pharmaceuticals" style variants
            for reg in self._by_first.get(n.split()[0], []):
                if reg.startswith(n + " ") and len(n) >= 6:
                    return True
        return False
