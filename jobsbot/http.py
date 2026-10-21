"""Small HTTP helper with retries and a polite User-Agent."""

from __future__ import annotations

import time

import requests

USER_AGENT = (
    "uk-compbio-jobs/0.1 (weekly job list built from public employer job boards; "
    "+https://github.com/)"
)
TIMEOUT = 30

_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json, */*"})


def _request(method: str, url: str, retries: int = 2, **kwargs) -> requests.Response:
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = _session.request(method, url, timeout=TIMEOUT, **kwargs)
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp
        except requests.RequestException as err:  # network error or 4xx/5xx
            last_err = err
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
    assert last_err is not None
    raise last_err


def get_json(url: str, **kwargs):
    return _request("GET", url, **kwargs).json()


def post_json(url: str, payload: dict, **kwargs):
    return _request("POST", url, json=payload, **kwargs).json()


def get_text(url: str, **kwargs) -> str:
    return _request("GET", url, **kwargs).text
