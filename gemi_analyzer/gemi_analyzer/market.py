"""Μέγεθος αγοράς & μερίδιο αγοράς.

Ιεραρχία πηγών (η πρώτη διαθέσιμη υπερισχύει):
  1. Ρητή τιμή από τον χρήστη (--market-size)
  2. data/markets.json — δικές σας εκτιμήσεις ανά πρόθεμα ΚΑΔ (π.χ. από ICAP, ΕΛΣΤΑΤ, μελέτες)
  3. Eurostat SBS (sbs_ovw_act): καθαρός κύκλος εργασιών κλάδου NACE στην Ελλάδα — δωρεάν, χωρίς key
  4. Άθροισμα πωλήσεων ανταγωνιστών από ΓΕΜΗ (κατώτατο όριο αγοράς / μερίδιο μεταξύ peers)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

EUROSTAT_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/sbs_ovw_act"

# NACE Rev.2: διψήφιος κλάδος -> τομέας (γράμμα)
_SECTIONS = [
    (1, 3, "A"), (5, 9, "B"), (10, 33, "C"), (35, 35, "D"), (36, 39, "E"), (41, 43, "F"),
    (45, 47, "G"), (49, 53, "H"), (55, 56, "I"), (58, 63, "J"), (64, 66, "K"), (68, 68, "L"),
    (69, 75, "M"), (77, 82, "N"), (84, 84, "O"), (85, 85, "P"), (86, 88, "Q"), (90, 93, "R"),
    (94, 96, "S"),
]


def kad_digits(kad: str | None) -> str:
    return re.sub(r"\D", "", kad or "")


def nace_code(kad: str | None, level: int = 2) -> str | None:
    """ΚΑΔ '61.10.10.01' -> 'J61' (level=2) ή 'J611' (level=3)."""
    d = kad_digits(kad)
    if len(d) < 2:
        return None
    div = int(d[:2])
    for lo, hi, letter in _SECTIONS:
        if lo <= div <= hi:
            return letter + d[:level]
    return None


@dataclass
class MarketEstimate:
    size: float | None
    source: str
    year: int | None = None
    scope: str = ""
    note: str = ""


@dataclass
class MarketPosition:
    company_revenue: float | None
    market: MarketEstimate
    share: float | None
    peers: list[dict] = field(default_factory=list)  # [{"name", "revenue", "share"}]
    peer_share: float | None = None
    rank_among_peers: int | None = None
    hhi: float | None = None  # Herfindahl-Hirschman μεταξύ peers (0–10.000)
    concentration: str | None = None


def from_markets_file(kad: str | None, path: Path = DATA_DIR / "markets.json") -> MarketEstimate | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    d = kad_digits(kad)
    best = None
    for entry in data.get("markets", []):
        prefix = kad_digits(entry.get("kad_prefix"))
        if entry.get("size_eur") and prefix and d.startswith(prefix):
            if best is None or len(prefix) > len(kad_digits(best["kad_prefix"])):
                best = entry
    if not best:
        return None
    return MarketEstimate(
        size=float(best["size_eur"]),
        source=best.get("source", "markets.json"),
        year=best.get("year"),
        scope=best.get("name", ""),
        note=best.get("note", ""),
    )


def from_eurostat(kad: str | None, geo: str = "EL", timeout: int = 20) -> MarketEstimate | None:
    """Καθαρός κύκλος εργασιών κλάδου (εκατ. €) από Eurostat SBS. Δοκιμάζει 3ψήφιο και μετά 2ψήφιο NACE."""
    for level in (3, 2):
        code = nace_code(kad, level)
        if not code:
            continue
        try:
            r = requests.get(
                EUROSTAT_URL,
                params={"geo": geo, "nace_r2": code, "indic_sbs": "NETTUR_MEUR",
                        "size_emp": "TOTAL", "format": "JSON", "lang": "EN"},
                timeout=timeout,
            )
            if r.status_code != 200:
                continue
            val, year = _latest_jsonstat(r.json())
        except (requests.RequestException, ValueError):
            continue
        if val:
            return MarketEstimate(
                size=val * 1_000_000,
                source="Eurostat SBS (sbs_ovw_act)",
                year=year,
                scope=f"NACE {code}, {geo}",
                note="Συνολικός κύκλος εργασιών κλάδου — ευρύτερος από τη στοχευμένη αγορά της εταιρείας.",
            )
    return None


def _latest_jsonstat(js: dict) -> tuple[float | None, int | None]:
    values = js.get("value") or {}
    if not values:
        return None, None
    dims = js["id"]
    sizes = js["size"]
    time_idx = dims.index("time")
    time_cat = js["dimension"]["time"]["category"]["index"]
    pos_to_year = {v: k for k, v in time_cat.items()}
    stride = 1
    for s in sizes[time_idx + 1:]:
        stride *= s
    best = (None, None)
    for k, v in values.items():
        t = (int(k) // stride) % sizes[time_idx]
        year = int(str(pos_to_year[t])[:4])
        if v is not None and (best[1] is None or year > best[1]):
            best = (float(v), year)
    return best


def herfindahl(revenues: list[float]) -> float | None:
    tot = sum(revenues)
    if tot <= 0:
        return None
    return sum((r / tot * 100) ** 2 for r in revenues)


def position(company_name: str, company_revenue: float | None, kad: str | None,
             market_size: float | None = None, peers: list[dict] | None = None,
             use_eurostat: bool = True) -> MarketPosition:
    peers = [p for p in (peers or []) if p.get("revenue")]

    if market_size:
        est = MarketEstimate(market_size, "Δοθέν από χρήστη")
    else:
        est = from_markets_file(kad) or (from_eurostat(kad) if use_eurostat else None)
    peer_total = sum(p["revenue"] for p in peers) + (company_revenue or 0)
    if est is None:
        if peers:
            est = MarketEstimate(peer_total, "Άθροισμα εταιρείας + δηλωμένων ανταγωνιστών",
                                 note="Κατώτατο όριο: περιλαμβάνει μόνο τους δηλωμένους ανταγωνιστές.")
        else:
            est = MarketEstimate(None, "Μη διαθέσιμο",
                                 note="Δώστε --market-size, συμπληρώστε data/markets.json ή --peers.")

    pos = MarketPosition(
        company_revenue=company_revenue,
        market=est,
        share=(company_revenue / est.size) if (company_revenue and est.size) else None,
    )

    if peers and company_revenue:
        everyone = [{"name": company_name, "revenue": company_revenue, "self": True}] + peers
        everyone.sort(key=lambda p: p["revenue"], reverse=True)
        for p in everyone:
            p["share"] = p["revenue"] / peer_total
        pos.peers = everyone
        pos.peer_share = company_revenue / peer_total
        pos.rank_among_peers = next(i + 1 for i, p in enumerate(everyone) if p.get("self"))
        pos.hhi = herfindahl([p["revenue"] for p in everyone])
        pos.concentration = (
            "Χαμηλή συγκέντρωση" if pos.hhi < 1500 else
            "Μέτρια συγκέντρωση" if pos.hhi < 2500 else "Υψηλή συγκέντρωση (ολιγοπώλιο)"
        )
    return pos
