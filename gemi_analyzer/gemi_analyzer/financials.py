"""Οικονομικά στοιχεία: μοντέλο, φόρτωση από JSON/CSV και εξαγωγή από PDF ισολογισμών ΓΕΜΗ."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass, fields
from pathlib import Path


@dataclass
class YearFinancials:
    year: int
    # Κατάσταση αποτελεσμάτων
    revenue: float | None = None
    cost_of_sales: float | None = None
    gross_profit: float | None = None
    depreciation: float | None = None
    ebit: float | None = None
    interest_expense: float | None = None
    ebt: float | None = None
    net_income: float | None = None
    # Ισολογισμός
    total_assets: float | None = None
    fixed_assets: float | None = None
    current_assets: float | None = None
    inventory: float | None = None
    receivables: float | None = None
    cash: float | None = None
    equity: float | None = None
    retained_earnings: float | None = None
    total_liabilities: float | None = None
    long_term_liabilities: float | None = None
    current_liabilities: float | None = None
    bank_debt: float | None = None
    employees: float | None = None

    def complete(self) -> "YearFinancials":
        """Συμπληρώνει παράγωγα πεδία όπου λείπουν."""
        if self.gross_profit is None and self.revenue is not None and self.cost_of_sales is not None:
            self.gross_profit = self.revenue - abs(self.cost_of_sales)
        if self.ebit is None and self.ebt is not None and self.interest_expense is not None:
            self.ebit = self.ebt + abs(self.interest_expense)
        if self.total_liabilities is None and self.total_assets is not None and self.equity is not None:
            self.total_liabilities = self.total_assets - self.equity
        if (
            self.current_liabilities is None
            and self.total_liabilities is not None
            and self.long_term_liabilities is not None
        ):
            self.current_liabilities = self.total_liabilities - self.long_term_liabilities
        if self.fixed_assets is None and self.total_assets is not None and self.current_assets is not None:
            self.fixed_assets = self.total_assets - self.current_assets
        return self

    @property
    def ebitda(self) -> float | None:
        if self.ebit is None:
            return None
        return self.ebit + abs(self.depreciation or 0)


FIELD_NAMES = [f.name for f in fields(YearFinancials) if f.name != "year"]


def _to_float(v) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return parse_greek_number(str(v))


def parse_greek_number(s: str) -> float | None:
    """'1.234.567,89' -> 1234567.89, '(12.345)' -> -12345, '-' -> None."""
    s = s.strip().replace("€", "").replace("\xa0", "").replace(" ", "")
    if not s or s in {"-", "—", "–"}:
        return None
    neg = s.startswith("(") and s.endswith(")") or s.startswith("-")
    s = s.strip("()-")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1 or re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    try:
        val = float(s)
    except ValueError:
        return None
    return -val if neg else val


def load_financials(path: str | Path) -> list[YearFinancials]:
    """JSON: {"years": [{"year": 2023, "revenue": ...}, ...]} ή λίστα.
    CSV: στήλες year,revenue,... (μία γραμμή ανά χρήση)."""
    path = Path(path)
    rows: list[dict]
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
    else:
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data.get("years", data.get("financials", [])) if isinstance(data, dict) else data
    out = []
    for r in rows:
        yf = YearFinancials(year=int(r["year"]))
        for name in FIELD_NAMES:
            if name in r:
                setattr(yf, name, _to_float(r[name]))
        out.append(yf.complete())
    return sorted(out, key=lambda y: y.year)


def save_financials(years: list[YearFinancials], path: str | Path) -> None:
    data = {"years": [{k: v for k, v in asdict(y).items() if v is not None} for y in years]}
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def merge_years(*groups: list[YearFinancials]) -> list[YearFinancials]:
    """Ενώνει χρήσεις από πολλές πηγές· οι πιο πρόσφατες πηγές υπερισχύουν σε κενά πεδία."""
    by_year: dict[int, YearFinancials] = {}
    for group in groups:
        for y in group:
            cur = by_year.setdefault(y.year, YearFinancials(year=y.year))
            for name in FIELD_NAMES:
                v = getattr(y, name)
                if v is not None and getattr(cur, name) is None:
                    setattr(cur, name, v)
    return sorted((y.complete() for y in by_year.values()), key=lambda y: y.year)


# --- Εξαγωγή από PDF (υποδείγματα ΕΛΠ ν.4308/2014) -------------------------------------

# Η σειρά μετράει: πιο συγκεκριμένες φράσεις πρώτα.
PDF_LABELS: list[tuple[str, str]] = [
    ("revenue", r"κύκλος\s+εργασιών"),
    ("cost_of_sales", r"κόστος\s+πωλήσεων"),
    ("gross_profit", r"μικτό\s+(αποτέλεσμα|κέρδος)"),
    ("depreciation", r"αποσβέσεις"),
    ("interest_expense", r"(χρεωστικοί\s+τόκοι|τόκοι\s+και\s+συναφή\s+έξοδα)"),
    ("ebt", r"(αποτέλεσμα|κέρδη|ζημίες).{0,20}προ\s+φόρων"),
    ("net_income", r"(αποτέλεσμα\s+περιόδου\s+μετά\s+(από\s+)?φόρους|καθαρά\s+κέρδη)"),
    ("total_assets", r"σύνολο\s+ενεργητικού"),
    ("current_assets", r"σύνολο\s+κυκλοφορούντων"),
    ("fixed_assets", r"σύνολο\s+μη\s+κυκλοφορούντων"),
    ("inventory", r"σύνολο\s+αποθεμάτων"),
    ("receivables", r"εμπορικές\s+απαιτήσεις"),
    ("cash", r"ταμειακά\s+διαθέσιμα"),
    ("equity", r"σύνολο\s+καθαρής\s+θέσης"),
    ("retained_earnings", r"αποτελέσματα\s+εις\s+νέο"),
    ("long_term_liabilities", r"σύνολο\s+μακροπρόθεσμων\s+υποχρεώσεων"),
    ("current_liabilities", r"σύνολο\s+βραχυπρόθεσμων\s+υποχρεώσεων"),
    ("total_liabilities", r"σύνολο\s+υποχρεώσεων"),
    ("bank_debt", r"τραπεζικά\s+δάνεια"),
]

_NUM = r"\(?-?\d{1,3}(?:\.\d{3})*(?:,\d+)?\)?|\(?-?\d+(?:,\d+)?\)?"


def extract_from_text(text: str, year: int) -> list[YearFinancials]:
    """Οι οικονομικές καταστάσεις έχουν 2 στήλες (τρέχουσα & προηγούμενη χρήση).
    Επιστρέφει έως δύο YearFinancials."""
    cur, prev = YearFinancials(year=year), YearFinancials(year=year - 1)
    for line in text.splitlines():
        low = line.lower()
        for name, pattern in PDF_LABELS:
            if getattr(cur, name) is not None:
                continue
            m = re.search(pattern, low)
            if not m:
                continue
            tail = line[m.end():]
            nums = [parse_greek_number(n) for n in re.findall(_NUM, tail)]
            # Αγνοούμε αριθμούς σημειώσεων (π.χ. "7.1") και μικρούς ακέραιους πριν τα ποσά
            nums = [n for n in nums if n is not None and (abs(n) >= 100 or n == 0)]
            if nums:
                setattr(cur, name, nums[-2] if len(nums) >= 2 else nums[0])
                if len(nums) >= 2:
                    setattr(prev, name, nums[-1])
            break
    result = [y.complete() for y in (prev, cur) if any(getattr(y, f) is not None for f in FIELD_NAMES)]
    return result


def extract_from_pdf(path: str | Path, year: int) -> list[YearFinancials]:
    try:
        import pdfplumber
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("Χρειάζεται: pip install pdfplumber") from e
    with pdfplumber.open(str(path)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    if not text.strip():
        raise RuntimeError(
            f"{path}: το PDF είναι σκαναρισμένο (χωρίς κείμενο). Χρειάζεται OCR ή χειροκίνητη καταχώρηση."
        )
    return extract_from_text(text, year)
