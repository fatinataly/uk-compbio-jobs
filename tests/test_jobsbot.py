"""Offline tests: every network call is replaced with canned responses."""

from datetime import date
from pathlib import Path

import pytest
import yaml

from jobsbot import __main__ as cli
from jobsbot import filters, http, sources, sponsors

ROOT = Path(__file__).resolve().parent.parent
CFG = yaml.safe_load((ROOT / "config" / "config.yaml").read_text())
TODAY = date(2026, 10, 19)


# ------------------------------------------------------------ location

@pytest.mark.parametrize("loc", [
    "London, UK", "Cambridge, United Kingdom", "Cambridge", "Hinxton",
    "Macclesfield", "Boston, MA; London", "Stevenage, Hertfordshire",
    "GB - Ware", "Oxford, England",
])
def test_uk_locations(loc):
    assert filters.is_uk(loc)


@pytest.mark.parametrize("loc", [
    "Cambridge, MA", "Cambridge, Massachusetts, United States", "Boston, MA",
    "New York, NY", "Remote - US", "Toronto, Ontario", "London, Ontario, Canada", "",
])
def test_non_uk_locations(loc):
    assert not filters.is_uk(loc)


# ------------------------------------------------------------ titles

@pytest.fixture(scope="module")
def tf():
    return filters.TitleFilter(CFG)


@pytest.mark.parametrize("title,expected", [
    ("Bioinformatician", ["bioinformatics-genomics"]),
    ("Graduate Bioinformatics Scientist", ["bioinformatics-genomics", "graduate-placements-internships"]),
    ("Computational Chemist", ["computational-biology-chemistry"]),
    ("Statistician I", ["biostatistics"]),
    ("Industrial Placement - Data Science 2027", ["data-science-ml", "graduate-placements-internships"]),
    ("PhD Studentship in Single-Cell Genomics", ["bioinformatics-genomics", "graduate-placements-internships"]),
])
def test_classify_in_scope(tf, title, expected):
    assert tf.classify(title) == expected


@pytest.mark.parametrize("title", [
    "Senior Bioinformatician", "Principal Data Scientist", "Lead Computational Biologist",
    "Associate Director, Biostatistics", "Bioinformatics Manager", "Scientist III, Genomics",
    "Lab Technician", "Professor of Genomics", "Genetic Counsellor",
])
def test_classify_out_of_scope(tf, title):
    assert tf.classify(title) == []


def test_generic_ml_role_needs_bio_context(tf):
    assert tf.classify("Machine Learning Engineer, Ads", life_sciences=False) == []
    assert tf.classify("Machine Learning Engineer, Drug Discovery", life_sciences=False) == ["data-science-ml"]
    assert tf.classify("Machine Learning Engineer", life_sciences=True) == ["data-science-ml"]


# ------------------------------------------------------------ adapters

GREENHOUSE = {"jobs": [
    {"title": "Bioinformatics Scientist", "location": {"name": "London, UK"},
     "absolute_url": "https://job-boards.greenhouse.io/x/jobs/1", "first_published": "2026-10-15T09:00:00-04:00"},
    {"title": "Senior Bioinformatics Scientist", "location": {"name": "London, UK"},
     "absolute_url": "https://job-boards.greenhouse.io/x/jobs/2", "updated_at": "2026-10-10T09:00:00Z"},
]}
LEVER = [{"text": "Computational Biologist", "categories": {"location": "Cambridge, UK"},
          "hostedUrl": "https://jobs.lever.co/x/abc", "createdAt": 1760000000000}]
ASHBY = {"jobs": [{"title": "Machine Learning Scientist", "location": "London",
                   "secondaryLocations": [{"location": "Remote (UK)"}], "jobUrl": "https://jobs.ashbyhq.com/x/1",
                   "publishedAt": "2026-10-01T00:00:00Z", "isListed": True}]}
WORKDAY = {"jobPostings": [{"title": "Graduate Data Scientist", "locationsText": "UK - Cambridge",
                            "externalPath": "/job/Cambridge/Graduate-Data-Scientist_R1", "postedOn": "Posted 3 Days Ago"}]}
RSS = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Bioinformatician - University of Leeds</title><link>https://www.jobs.ac.uk/job/ABC123</link>
<pubDate>Wed, 14 Oct 2026 10:00:00 GMT</pubDate></item></channel></rss>"""


@pytest.fixture
def fake_http(monkeypatch):
    def get_json(url, **kw):
        if "greenhouse" in url:
            return GREENHOUSE
        if "lever" in url:
            return LEVER
        if "ashby" in url:
            return ASHBY
        raise AssertionError(url)

    monkeypatch.setattr(http, "get_json", get_json)
    monkeypatch.setattr(http, "post_json", lambda url, payload, **kw: WORKDAY)
    monkeypatch.setattr(http, "get_text", lambda url, **kw: RSS)


def test_greenhouse(fake_http):
    jobs = sources.fetch({"name": "X", "ats": "greenhouse", "slug": "x"}, [])
    assert [j.title for j in jobs] == ["Bioinformatics Scientist", "Senior Bioinformatics Scientist"]
    assert jobs[0].posted == date(2026, 10, 15)


def test_lever_ashby(fake_http):
    lj = sources.fetch({"name": "L", "ats": "lever", "slug": "x"}, [])[0]
    assert lj.location == "Cambridge, UK" and lj.posted is not None
    aj = sources.fetch({"name": "A", "ats": "ashby", "slug": "x"}, [])[0]
    assert "Remote (UK)" in aj.location


def test_workday_dedupes_across_terms(fake_http):
    jobs = sources.fetch({"name": "W", "ats": "workday", "host": "w.wd3.myworkdayjobs.com",
                          "tenant": "w", "site": "Careers"}, ["a", "b", "c"])
    assert len(jobs) == 1
    assert jobs[0].url == "https://w.wd3.myworkdayjobs.com/Careers/job/Cambridge/Graduate-Data-Scientist_R1"


def test_rss_company_from_title(fake_http):
    j = sources.fetch({"name": "", "ats": "rss", "url": "u", "company_from_title": True}, [])[0]
    assert (j.title, j.company, j.posted) == ("Bioinformatician", "University of Leeds", date(2026, 10, 14))


def test_life_sciences_flag(fake_http):
    j = sources.fetch({"name": "X", "ats": "greenhouse", "slug": "x", "life_sciences": False}, [])[0]
    assert j.life_sciences is False


def test_workday_posted():
    assert sources.workday_posted("Posted Today", TODAY) == TODAY
    assert sources.workday_posted("Posted Yesterday", TODAY) == date(2026, 10, 18)
    assert sources.workday_posted("Posted 30+ Days Ago", TODAY) == date(2026, 9, 19)
    assert sources.workday_posted(None, TODAY) is None


# ------------------------------------------------------------ sponsors

REGISTER_CSV = '''"Organisation Name","Town/City","County","Type & Rating","Route"
"AstraZeneca UK Limited","Cambridge","","Worker (A rating)","Skilled Worker"
"GlaxoSmithKline Services Unlimited","Brentford","","Worker (A rating)","Skilled Worker"
"Isomorphic Labs Limited","London","","Worker (A rating)","Skilled Worker"
"University of Leeds","Leeds","","Worker (A rating)","Global Business Mobility: Senior or Specialist Worker"
"University of Leeds","Leeds","","Worker (A rating)","Skilled Worker"
"Seasonal Farm Ltd","Kent","","Temporary Worker (A rating)","Seasonal Worker"
'''


def test_register_matching(tmp_path):
    p = tmp_path / "reg.csv"
    p.write_text(REGISTER_CSV)
    reg = sponsors.Register.from_csv(p)
    assert reg.matches("AstraZeneca")
    assert reg.matches("Isomorphic Labs")
    assert reg.matches("University of Leeds")
    assert reg.matches("GSK", ["GlaxoSmithKline Services Unlimited"])
    assert not reg.matches("GSK")
    assert not reg.matches("Seasonal Farm")  # not a Skilled Worker route
    assert not reg.matches("Unknown Biotech")


# ------------------------------------------------------------ end to end

def test_build_end_to_end(tmp_path, fake_http, monkeypatch):
    cfg = dict(CFG)
    cfg["employers"] = [
        {"name": "Isomorphic Labs", "ats": "greenhouse", "slug": "x"},
        {"name": "AstraZeneca", "ats": "workday", "host": "w.wd3.myworkdayjobs.com", "tenant": "w", "site": "Careers"},
        {"name": "", "ats": "rss", "url": "u", "company_from_title": True},
        {"name": "Broken", "ats": "nope"},
    ]
    reg = tmp_path / "data" / "sponsor_register.csv"
    reg.parent.mkdir()
    reg.write_text(REGISTER_CSV)
    monkeypatch.setattr(sponsors, "download", lambda cache: (reg, "test"))

    assert cli.cmd_build(cfg, tmp_path, TODAY) == 0

    readme = (tmp_path / "README.md").read_text()
    assert "**3 open roles at 3 UK employers**" in readme
    assert "Senior Bioinformatics" not in readme
    assert "Graduate Data Scientist" in readme
    assert readme.count("✅ Licensed sponsor") == 3
    assert (tmp_path / "lists" / "graduate-placements-internships.md").exists()
    rows = (tmp_path / "csv" / "all.csv").read_text().strip().splitlines()
    assert len(rows) == 4  # header + 3 roles
    assert (tmp_path / "data" / "first_seen.json").exists()
    import json
    data = json.loads((tmp_path / "json" / "jobs.json").read_text())
    assert len(data["jobs"]) == 3 and data["jobs"][0]["sponsor"] is True
