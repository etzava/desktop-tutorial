"""Client για το GEMI Open Data API (opendata-api.businessportal.gr).

Απαιτεί δωρεάν API key από https://opendata.businessportal.gr (εγγραφή developer).
Το key διαβάζεται από τη μεταβλητή περιβάλλοντος GEMI_API_KEY ή δίνεται ρητά.

Η δομή των απαντήσεων του API έχει αλλάξει στο παρελθόν, γι' αυτό η κανονικοποίηση
(normalize_company) είναι αμυντική: δοκιμάζει πολλαπλά ονόματα πεδίων και κρατά
πάντα και το raw JSON.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

import requests

BASE_URL = os.environ.get(
    "GEMI_BASE_URL", "https://opendata-api.businessportal.gr/api/opendata/v1"
)


class GemiError(RuntimeError):
    pass


@dataclass
class Company:
    ar_gemi: str
    name: str
    afm: str | None = None
    legal_type: str | None = None
    status: str | None = None
    incorporation_date: str | None = None
    address: str | None = None
    main_kad: str | None = None
    main_kad_descr: str | None = None
    activities: list[dict[str, str]] = field(default_factory=list)
    capital: float | None = None
    persons: list[dict[str, str]] = field(default_factory=list)
    website: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def _first(d: dict, *keys, default=None):
    for k in keys:
        v = d.get(k)
        if v not in (None, "", [], {}):
            return v
    return default


def _descr(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, dict):
        return _first(v, "descr", "description", "descrEl", "name", "title")
    return str(v)


def normalize_company(raw: dict[str, Any]) -> Company:
    name = _first(raw, "coNameEl", "coName", "name", "companyName", default="")
    titles = _first(raw, "coTitlesEl", "coTitles", "titles")
    if not name and titles:
        name = titles[0] if isinstance(titles, list) else str(titles)

    address_parts = [
        _first(raw, "street"),
        _first(raw, "streetNumber"),
        _first(raw, "zipCode", "postalCode"),
        _descr(_first(raw, "city", "municipality")),
    ]
    address = ", ".join(str(p) for p in address_parts if p) or None

    activities = []
    for a in _first(raw, "activities", "kad", "kads", default=[]) or []:
        act = a.get("activity", a) if isinstance(a, dict) else {}
        activities.append(
            {
                "kad": str(_first(act, "id", "code", "kad", default="")),
                "descr": _descr(act) or "",
                "type": _descr(_first(a, "type", "activityType")) or "",
            }
        )
    main = next((a for a in activities if "κύρια" in a["type"].lower()), None)
    main = main or (activities[0] if activities else None)

    capital = None
    cap = _first(raw, "capital", "capitalStock")
    if isinstance(cap, list) and cap:
        cap = cap[0]
    if isinstance(cap, dict):
        cap = _first(cap, "capitalStock", "amount", "value")
    try:
        capital = float(cap) if cap is not None else None
    except (TypeError, ValueError):
        capital = None

    persons = []
    for p in _first(raw, "persons", "managers", "boardMembers", default=[]) or []:
        if isinstance(p, dict):
            persons.append(
                {
                    "name": str(_first(p, "name", "fullName", "personName", default="")),
                    "role": _descr(_first(p, "role", "capacity", "position")) or "",
                }
            )

    return Company(
        ar_gemi=str(_first(raw, "arGemi", "gemiNumber", "ar_gemi", default="")),
        name=str(name),
        afm=_first(raw, "afm", "vatNumber"),
        legal_type=_descr(_first(raw, "legalType", "legalForm")),
        status=_descr(_first(raw, "status", "companyStatus")),
        incorporation_date=_first(raw, "incorporationDate", "registrationDate"),
        address=address,
        main_kad=main["kad"] if main else None,
        main_kad_descr=main["descr"] if main else None,
        activities=activities,
        capital=capital,
        persons=persons,
        website=_first(raw, "url", "website", "webSite"),
        raw=raw,
    )


class GemiClient:
    def __init__(self, api_key: str | None = None, base_url: str = BASE_URL, timeout: int = 30):
        self.api_key = api_key or os.environ.get("GEMI_API_KEY")
        if not self.api_key:
            raise GemiError(
                "Λείπει API key. Ορίστε GEMI_API_KEY (δωρεάν από https://opendata.businessportal.gr)."
            )
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"api_key": self.api_key, "Accept": "application/json"})

    def _get(self, path: str, params: dict | None = None, retries: int = 3) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        for attempt in range(retries):
            r = self.session.get(url, params=params, timeout=self.timeout)
            if r.status_code == 429:  # rate limit του API — αναμονή και επανάληψη
                time.sleep(2 ** attempt * 2)
                continue
            if r.status_code == 401 or r.status_code == 403:
                raise GemiError("Μη έγκυρο API key ή μη εξουσιοδοτημένη πρόσβαση.")
            if r.status_code == 404:
                raise GemiError(f"Δεν βρέθηκε: {path}")
            r.raise_for_status()
            return r.json()
        raise GemiError("Υπέρβαση ορίου κλήσεων (429). Δοκιμάστε ξανά σε λίγο.")

    def search(self, name: str | None = None, afm: str | None = None, size: int = 10) -> list[Company]:
        params: dict[str, Any] = {"resultsOffset": 0, "resultsSize": size}
        if name:
            params["name"] = name
        if afm:
            params["afm"] = afm
        data = self._get("companies", params)
        items = data.get("searchResults", data) if isinstance(data, dict) else data
        return [normalize_company(i) for i in (items or [])]

    def company(self, ar_gemi: str) -> Company:
        data = self._get(f"companies/{ar_gemi}")
        if isinstance(data, list):
            data = data[0] if data else {}
        return normalize_company(data)

    def documents(self, ar_gemi: str) -> list[dict[str, Any]]:
        """Λίστα δημοσιευμένων εγγράφων (ισολογισμοί, ανακοινώσεις κ.λπ.)."""
        data = self._get(f"companies/{ar_gemi}/documents")
        docs: list[dict] = []

        def walk(node):
            if isinstance(node, dict):
                if any(k in node for k in ("url", "downloadUrl", "fileUrl", "assetUrl")):
                    docs.append(node)
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(data)
        return docs

    def financial_statement_docs(self, ar_gemi: str) -> list[dict[str, Any]]:
        keys = ("οικονομικ", "ισολογισμ", "financial", "balance")
        out = []
        for d in self.documents(ar_gemi):
            text = " ".join(str(v) for v in d.values() if isinstance(v, str)).lower()
            if any(k in text for k in keys):
                out.append(d)
        return out

    def download(self, url: str, dest: str) -> str:
        r = self.session.get(url, timeout=self.timeout * 2)
        r.raise_for_status()
        with open(dest, "wb") as f:
            f.write(r.content)
        return dest
