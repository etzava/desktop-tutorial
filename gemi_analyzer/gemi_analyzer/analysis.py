"""Χρηματοοικονομική ανάλυση: δείκτες, ανάπτυξη, μεταβολές ισολογισμού, Altman Z'', συνολική βαθμολογία."""

from __future__ import annotations

from dataclasses import dataclass, field

from .financials import FIELD_NAMES, YearFinancials

FIELD_LABELS = {
    "revenue": "Κύκλος εργασιών",
    "cost_of_sales": "Κόστος πωλήσεων",
    "gross_profit": "Μικτό κέρδος",
    "depreciation": "Αποσβέσεις",
    "ebit": "EBIT (λειτουργικό αποτέλεσμα)",
    "interest_expense": "Χρεωστικοί τόκοι",
    "ebt": "Κέρδη προ φόρων",
    "net_income": "Καθαρά κέρδη",
    "total_assets": "Σύνολο ενεργητικού",
    "fixed_assets": "Μη κυκλοφορούν ενεργητικό",
    "current_assets": "Κυκλοφορούν ενεργητικό",
    "inventory": "Αποθέματα",
    "receivables": "Εμπορικές απαιτήσεις",
    "cash": "Ταμειακά διαθέσιμα",
    "equity": "Ίδια κεφάλαια",
    "retained_earnings": "Αποτελέσματα εις νέο",
    "total_liabilities": "Σύνολο υποχρεώσεων",
    "long_term_liabilities": "Μακροπρόθεσμες υποχρεώσεις",
    "current_liabilities": "Βραχυπρόθεσμες υποχρεώσεις",
    "bank_debt": "Τραπεζικός δανεισμός",
    "employees": "Εργαζόμενοι",
}


def _div(a, b):
    if a is None or b in (None, 0):
        return None
    return a / b


def _growth(cur, prev):
    if cur is None or prev in (None, 0):
        return None
    return (cur - prev) / abs(prev)


@dataclass
class YearRatios:
    year: int
    gross_margin: float | None = None
    ebitda_margin: float | None = None
    ebit_margin: float | None = None
    net_margin: float | None = None
    roe: float | None = None
    roa: float | None = None
    current_ratio: float | None = None
    quick_ratio: float | None = None
    cash_ratio: float | None = None
    debt_to_equity: float | None = None
    equity_ratio: float | None = None
    interest_coverage: float | None = None
    net_debt_to_ebitda: float | None = None
    asset_turnover: float | None = None
    dso_days: float | None = None
    dio_days: float | None = None
    revenue_per_employee: float | None = None
    working_capital: float | None = None
    revenue_growth: float | None = None
    net_income_growth: float | None = None
    equity_growth: float | None = None
    altman_z: float | None = None
    altman_zone: str | None = None


RATIO_LABELS = {
    "revenue_growth": ("Ανάπτυξη πωλήσεων", "pct"),
    "net_income_growth": ("Μεταβολή καθαρών κερδών", "pct"),
    "gross_margin": ("Μικτό περιθώριο", "pct"),
    "ebitda_margin": ("Περιθώριο EBITDA", "pct"),
    "ebit_margin": ("Περιθώριο EBIT", "pct"),
    "net_margin": ("Καθαρό περιθώριο", "pct"),
    "roe": ("ROE (απόδοση ιδίων κεφαλαίων)", "pct"),
    "roa": ("ROA (απόδοση ενεργητικού)", "pct"),
    "current_ratio": ("Γενική ρευστότητα", "x"),
    "quick_ratio": ("Άμεση ρευστότητα", "x"),
    "cash_ratio": ("Ταμειακή ρευστότητα", "x"),
    "working_capital": ("Κεφάλαιο κίνησης", "eur"),
    "debt_to_equity": ("Ξένα / Ίδια κεφάλαια", "x"),
    "equity_ratio": ("Ίδια / Σύνολο ενεργητικού", "pct"),
    "interest_coverage": ("Κάλυψη τόκων (EBIT/τόκοι)", "x"),
    "net_debt_to_ebitda": ("Καθαρός δανεισμός / EBITDA", "x"),
    "asset_turnover": ("Κυκλοφοριακή ταχύτητα ενεργητικού", "x"),
    "dso_days": ("Μέση είσπραξη απαιτήσεων (ημέρες)", "days"),
    "dio_days": ("Μέση διάρκεια αποθεμάτων (ημέρες)", "days"),
    "revenue_per_employee": ("Πωλήσεις ανά εργαζόμενο", "eur"),
    "altman_z": ("Altman Z'' (πιστοληπτικός κίνδυνος)", "num"),
}


def compute_ratios(cur: YearFinancials, prev: YearFinancials | None) -> YearRatios:
    r = YearRatios(year=cur.year)
    rev = cur.revenue
    r.gross_margin = _div(cur.gross_profit, rev)
    r.ebitda_margin = _div(cur.ebitda, rev)
    r.ebit_margin = _div(cur.ebit, rev)
    r.net_margin = _div(cur.net_income, rev)

    avg_eq = cur.equity
    avg_ta = cur.total_assets
    if prev is not None:
        if prev.equity is not None and cur.equity is not None:
            avg_eq = (prev.equity + cur.equity) / 2
        if prev.total_assets is not None and cur.total_assets is not None:
            avg_ta = (prev.total_assets + cur.total_assets) / 2
    r.roe = _div(cur.net_income, avg_eq) if (avg_eq or 0) > 0 else None
    r.roa = _div(cur.net_income, avg_ta)

    r.current_ratio = _div(cur.current_assets, cur.current_liabilities)
    if cur.current_assets is not None:
        r.quick_ratio = _div(cur.current_assets - (cur.inventory or 0), cur.current_liabilities)
    r.cash_ratio = _div(cur.cash, cur.current_liabilities)
    if cur.current_assets is not None and cur.current_liabilities is not None:
        r.working_capital = cur.current_assets - cur.current_liabilities

    r.debt_to_equity = _div(cur.total_liabilities, cur.equity) if (cur.equity or 0) > 0 else None
    r.equity_ratio = _div(cur.equity, cur.total_assets)
    if cur.interest_expense:
        r.interest_coverage = _div(cur.ebit, abs(cur.interest_expense))
    ebitda = cur.ebitda
    if cur.bank_debt is not None and ebitda and ebitda > 0:
        r.net_debt_to_ebitda = (cur.bank_debt - (cur.cash or 0)) / ebitda

    r.asset_turnover = _div(rev, avg_ta)
    if cur.receivables is not None and rev:
        r.dso_days = cur.receivables / rev * 365
    if cur.inventory is not None and cur.cost_of_sales:
        r.dio_days = cur.inventory / abs(cur.cost_of_sales) * 365
    r.revenue_per_employee = _div(rev, cur.employees)

    if prev is not None:
        r.revenue_growth = _growth(cur.revenue, prev.revenue)
        r.net_income_growth = _growth(cur.net_income, prev.net_income)
        r.equity_growth = _growth(cur.equity, prev.equity)

    r.altman_z, r.altman_zone = altman_z_double_prime(cur)
    return r


def altman_z_double_prime(y: YearFinancials) -> tuple[float | None, str | None]:
    """Altman Z'' (1995) για μη εισηγμένες / μη μεταποιητικές εταιρείες.
    Z'' = 6.56·X1 + 3.26·X2 + 6.72·X3 + 1.05·X4
    Ζώνες: >2.60 ασφαλής, 1.10–2.60 γκρίζα, <1.10 κίνδυνος."""
    ta = y.total_assets
    if not ta or y.current_assets is None or y.current_liabilities is None or y.ebit is None:
        return None, None
    if y.equity is None or not y.total_liabilities:
        return None, None
    x1 = (y.current_assets - y.current_liabilities) / ta
    x2 = (y.retained_earnings if y.retained_earnings is not None else 0) / ta
    x3 = y.ebit / ta
    x4 = y.equity / y.total_liabilities
    z = 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4
    zone = "Ασφαλής" if z > 2.6 else ("Γκρίζα ζώνη" if z >= 1.1 else "Κίνδυνος")
    return z, zone


def cagr(first: float | None, last: float | None, years: int) -> float | None:
    if first is None or last is None or years <= 0 or first <= 0 or last <= 0:
        return None
    return (last / first) ** (1 / years) - 1


@dataclass
class Change:
    field: str
    label: str
    year: int
    prev: float
    cur: float
    abs_change: float
    pct_change: float | None


def balance_changes(years: list[YearFinancials], top: int = 8) -> list[Change]:
    """Οι σημαντικότερες μεταβολές κονδυλίων της τελευταίας χρήσης σε σχέση με την προηγούμενη."""
    if len(years) < 2:
        return []
    prev, cur = years[-2], years[-1]
    out = []
    for name in FIELD_NAMES:
        a, b = getattr(prev, name), getattr(cur, name)
        if a is None or b is None or a == b:
            continue
        out.append(Change(name, FIELD_LABELS.get(name, name), cur.year, a, b, b - a, _growth(b, a)))
    # Ταξινόμηση με βάση το μέγεθος της μεταβολής ως % του ενεργητικού (ουσιαστικότητα)
    base = cur.total_assets or max((abs(c.cur) for c in out), default=1) or 1
    out.sort(key=lambda c: abs(c.abs_change) / base, reverse=True)
    return out[:top]


# --- Βαθμολόγηση ----------------------------------------------------------------------


def _band(v, bands: list[tuple[float, float]]) -> float | None:
    """bands: [(όριο, βαθμός)] αύξουσα σειρά ορίων. Επιστρέφει τον βαθμό του υψηλότερου ορίου που ξεπερνά."""
    if v is None:
        return None
    score = 0.0
    for limit, s in bands:
        if v >= limit:
            score = s
    return score


@dataclass
class Assessment:
    score: float
    grade: str
    pillars: dict[str, float | None]
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    summary: str = ""


PILLAR_WEIGHTS = {
    "Ανάπτυξη": 0.20,
    "Κερδοφορία": 0.25,
    "Ρευστότητα": 0.15,
    "Φερεγγυότητα": 0.25,
    "Αποδοτικότητα": 0.15,
}


def assess(years: list[YearFinancials], ratios: list[YearRatios], revenue_cagr: float | None) -> Assessment:
    r = ratios[-1]
    growth = revenue_cagr if revenue_cagr is not None else r.revenue_growth
    pillars: dict[str, float | None] = {}

    pillars["Ανάπτυξη"] = _avg(
        _band(growth, [(-1, 10), (-0.05, 30), (0, 50), (0.05, 65), (0.10, 80), (0.20, 95)]),
        _band(r.net_income_growth, [(-10, 20), (-0.2, 35), (0, 60), (0.1, 80), (0.25, 95)]),
    )
    pillars["Κερδοφορία"] = _avg(
        _band(r.ebitda_margin, [(-10, 0), (0, 25), (0.05, 50), (0.10, 70), (0.15, 85), (0.25, 100)]),
        _band(r.net_margin, [(-10, 0), (0, 30), (0.03, 55), (0.07, 75), (0.12, 90), (0.20, 100)]),
        _band(r.roe, [(-10, 0), (0, 30), (0.05, 50), (0.10, 70), (0.15, 85), (0.25, 100)]),
    )
    pillars["Ρευστότητα"] = _avg(
        _band(r.current_ratio, [(0, 10), (0.8, 35), (1.0, 55), (1.2, 70), (1.5, 85), (2.0, 100)]),
        _band(r.quick_ratio, [(0, 10), (0.5, 35), (0.8, 60), (1.0, 80), (1.5, 100)]),
    )
    pillars["Φερεγγυότητα"] = _avg(
        _band(r.equity_ratio, [(-10, 0), (0, 15), (0.15, 40), (0.30, 65), (0.45, 85), (0.60, 100)]),
        _band(r.altman_z, [(-100, 5), (1.1, 45), (1.8, 60), (2.6, 80), (4.0, 100)]),
        _band(r.interest_coverage, [(-1000, 0), (1, 30), (2, 50), (4, 75), (8, 100)]),
    )
    pillars["Αποδοτικότητα"] = _avg(
        _band(r.asset_turnover, [(0, 20), (0.5, 45), (1.0, 65), (1.5, 80), (2.0, 95)]),
        _band(-(r.dso_days) if r.dso_days is not None else None,
              [(-10000, 15), (-180, 35), (-120, 55), (-90, 70), (-60, 85), (-30, 100)]),
    )

    total_w = sum(PILLAR_WEIGHTS[k] for k, v in pillars.items() if v is not None)
    score = (
        sum(v * PILLAR_WEIGHTS[k] for k, v in pillars.items() if v is not None) / total_w if total_w else 0
    )
    grade = (
        "AAA" if score >= 85 else "AA" if score >= 75 else "A" if score >= 65 else
        "BBB" if score >= 55 else "BB" if score >= 45 else "B" if score >= 35 else "CCC"
    )

    a = Assessment(score=round(score, 1), grade=grade, pillars=pillars)
    _commentary(a, years, r, growth)
    return a


def _avg(*vals):
    v = [x for x in vals if x is not None]
    return sum(v) / len(v) if v else None


def _pct(v):
    return f"{v * 100:.1f}%"


def _commentary(a: Assessment, years: list[YearFinancials], r: YearRatios, growth) -> None:
    s, w = a.strengths, a.weaknesses
    if growth is not None:
        if growth >= 0.10:
            s.append(f"Ισχυρή ανάπτυξη πωλήσεων {_pct(growth)} ετησίως")
        elif growth >= 0.03:
            s.append(f"Σταθερή ανάπτυξη πωλήσεων {_pct(growth)} ετησίως")
        elif growth >= 0:
            w.append(f"Στασιμότητα πωλήσεων ({_pct(growth)} ετησίως)")
        else:
            w.append(f"Συρρίκνωση πωλήσεων ({_pct(growth)} ετησίως)")
    if r.ebitda_margin is not None:
        if r.ebitda_margin >= 0.12:
            s.append(f"Υψηλό περιθώριο EBITDA {_pct(r.ebitda_margin)}")
        elif r.ebitda_margin < 0.05:
            w.append(f"Χαμηλό περιθώριο EBITDA {_pct(r.ebitda_margin)} — πίεση τιμών/κόστους")
    if r.net_margin is not None and r.net_margin < 0:
        w.append(f"Ζημιογόνος χρήση (καθαρό περιθώριο {_pct(r.net_margin)})")
    if r.roe is not None:
        if r.roe >= 0.15:
            s.append(f"Υψηλή απόδοση ιδίων κεφαλαίων (ROE {_pct(r.roe)})")
        elif r.roe < 0.05:
            w.append(f"Χαμηλή απόδοση ιδίων κεφαλαίων (ROE {_pct(r.roe)})")
    if r.current_ratio is not None:
        if r.current_ratio < 1:
            w.append(f"Γενική ρευστότητα {r.current_ratio:.2f} < 1 — αρνητικό κεφάλαιο κίνησης")
        elif r.current_ratio >= 1.5:
            s.append(f"Άνετη ρευστότητα ({r.current_ratio:.2f})")
    if r.equity_ratio is not None:
        if r.equity_ratio < 0:
            w.append("Αρνητικά ίδια κεφάλαια — εφαρμογή άρθρου 119 ν.4548/2018")
        elif r.equity_ratio < 0.2:
            w.append(f"Υψηλή μόχλευση (ίδια κεφάλαια {_pct(r.equity_ratio)} του ενεργητικού)")
        elif r.equity_ratio >= 0.45:
            s.append(f"Ισχυρή κεφαλαιακή διάρθρωση (ίδια κεφάλαια {_pct(r.equity_ratio)})")
    if r.interest_coverage is not None and r.interest_coverage < 2:
        w.append(f"Χαμηλή κάλυψη τόκων ({r.interest_coverage:.1f}x)")
    if r.dso_days is not None and r.dso_days > 120:
        w.append(f"Αργή είσπραξη απαιτήσεων ({r.dso_days:.0f} ημέρες)")
    if r.altman_zone:
        (s if r.altman_zone == "Ασφαλής" else w).append(
            f"Altman Z'' = {r.altman_z:.2f} ({r.altman_zone})"
        )

    if len(years) >= 2 and years[-1].revenue and years[-2].revenue:
        trend = "αυξάνεται" if years[-1].revenue > years[-2].revenue else "μειώνεται"
    else:
        trend = "—"
    a.summary = (
        f"Συνολική βαθμολογία {a.score:.0f}/100 (διαβάθμιση {a.grade}). "
        f"Ο τζίρος {trend} την τελευταία χρήση. "
        + ("Η εταιρεία εμφανίζει υγιή εικόνα με περιθώρια ανάπτυξης."
           if a.score >= 65 else
           "Η εικόνα είναι μέτρια· απαιτείται προσοχή στα αδύναμα σημεία."
           if a.score >= 45 else
           "Η εταιρεία εμφανίζει σημαντικές αδυναμίες — αυξημένος πιστωτικός/επιχειρηματικός κίνδυνος.")
    )


@dataclass
class AnalysisResult:
    years: list[YearFinancials]
    ratios: list[YearRatios]
    revenue_cagr: float | None
    net_income_cagr: float | None
    changes: list[Change]
    assessment: Assessment


def analyze(years: list[YearFinancials]) -> AnalysisResult:
    if not years:
        raise ValueError("Δεν υπάρχουν οικονομικά στοιχεία για ανάλυση.")
    years = sorted(years, key=lambda y: y.year)
    ratios = [compute_ratios(y, years[i - 1] if i else None) for i, y in enumerate(years)]
    span = years[-1].year - years[0].year
    rc = cagr(years[0].revenue, years[-1].revenue, span)
    nc = cagr(years[0].net_income, years[-1].net_income, span)
    return AnalysisResult(
        years=years,
        ratios=ratios,
        revenue_cagr=rc,
        net_income_cagr=nc,
        changes=balance_changes(years),
        assessment=assess(years, ratios, rc),
    )
