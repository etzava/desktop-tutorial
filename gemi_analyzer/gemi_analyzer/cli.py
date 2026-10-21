"""Γραμμή εντολών.

  python -m gemi_analyzer search "ΕΠΩΝΥΜΙΑ"            αναζήτηση εταιρείας
  python -m gemi_analyzer info 123456789000             στοιχεία ΓΕΜΗ
  python -m gemi_analyzer fetch 123456789000            λήψη ισολογισμών & εξαγωγή σε JSON
  python -m gemi_analyzer analyze 123456789000 [...]    πλήρης ανάλυση & HTML αναφορά
  python -m gemi_analyzer template                      κενό πρότυπο CSV για χειροκίνητη καταχώρηση
  python -m gemi_analyzer demo                          δοκιμή με δείγμα δεδομένων (χωρίς API)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import webbrowser
from datetime import date
from pathlib import Path

from .analysis import analyze
from .financials import (
    FIELD_NAMES, YearFinancials, extract_from_pdf, load_financials, merge_years, save_financials,
)
from .gemi_client import Company, GemiClient, GemiError, normalize_company
from .market import position
from .report import eur, pct, render_html, to_json

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"


def _doc_year(doc: dict) -> int:
    text = " ".join(str(v) for v in doc.values() if isinstance(v, (str, int)))
    years = [int(y) for y in re.findall(r"\b(20\d{2})\b", text)]
    # Οι ισολογισμοί δημοσιεύονται την επόμενη χρονιά από τη χρήση
    return min(years) if years else date.today().year - 1


def _doc_url(doc: dict) -> str | None:
    for k in ("url", "downloadUrl", "fileUrl", "assetUrl"):
        if doc.get(k):
            return doc[k]
    return None


def fetch_financials(client: GemiClient, ar_gemi: str, max_docs: int = 5) -> tuple[list[YearFinancials], list[dict]]:
    docs = client.financial_statement_docs(ar_gemi)
    docs.sort(key=_doc_year, reverse=True)
    groups = []
    with tempfile.TemporaryDirectory() as tmp:
        for d in docs[:max_docs]:
            url = _doc_url(d)
            if not url:
                continue
            year = _doc_year(d)
            dest = Path(tmp) / f"{ar_gemi}_{year}.pdf"
            try:
                client.download(url, str(dest))
                groups.append(extract_from_pdf(dest, year))
                print(f"  ✓ Χρήση {year}: εξήχθησαν στοιχεία", file=sys.stderr)
            except Exception as ex:  # ένα χαλασμένο PDF δεν σταματά τη διαδικασία
                print(f"  ✗ Χρήση {year}: {ex}", file=sys.stderr)
    return merge_years(*groups), docs


def _peers(args, client: GemiClient | None) -> list[dict]:
    peers: list[dict] = []
    if args.peers:
        data = json.loads(Path(args.peers).read_text(encoding="utf-8"))
        peers += data.get("peers", data) if isinstance(data, dict) else data
    for g in (args.peer_gemi or "").split(","):
        g = g.strip()
        if not g or client is None:
            continue
        try:
            c = client.company(g)
            yrs, _ = fetch_financials(client, g, max_docs=1)
            rev = next((y.revenue for y in reversed(yrs) if y.revenue), None)
            peers.append({"name": c.name, "ar_gemi": g, "revenue": rev})
        except Exception as ex:
            print(f"  ✗ Ανταγωνιστής {g}: {ex}", file=sys.stderr)
    return peers


def run_analysis(company: Company, years: list[YearFinancials], args, docs=None, client=None) -> Path:
    result = analyze(years)
    peers = _peers(args, client)
    mkt = position(company.name, result.years[-1].revenue, args.kad or company.main_kad,
                   market_size=args.market_size, peers=peers, use_eurostat=not args.no_eurostat)

    REPORTS.mkdir(exist_ok=True)
    slug = re.sub(r"[^\w]+", "_", company.name or company.ar_gemi).strip("_")[:50] or "company"
    out = Path(args.out) if args.out else REPORTS / f"{slug}_{date.today():%Y%m%d}.html"
    out.write_text(render_html(company, result, mkt, docs), encoding="utf-8")
    out.with_suffix(".json").write_text(to_json(company, result, mkt), encoding="utf-8")

    a = result.assessment
    last, lr = result.years[-1], result.ratios[-1]
    print(f"\n{company.name}  —  Βαθμολογία {a.score:.0f}/100 ({a.grade})")
    print(f"  Πωλήσεις {last.year}: {eur(last.revenue)}  ({pct(lr.revenue_growth)} y/y, CAGR {pct(result.revenue_cagr)})")
    print(f"  EBITDA: {eur(last.ebitda)} ({pct(lr.ebitda_margin)})   Καθαρά: {eur(last.net_income)} ({pct(lr.net_margin)})")
    print(f"  Μερίδιο αγοράς: {pct(mkt.share)}  [αγορά {eur(mkt.market.size)} — {mkt.market.source}]")
    for s in a.strengths:
        print(f"  + {s}")
    for w in a.weaknesses:
        print(f"  - {w}")
    print(f"\nΑναφορά: {out}\nJSON:    {out.with_suffix('.json')}")
    if args.open:
        webbrowser.open(out.resolve().as_uri())
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="gemi_analyzer", description="Ανάλυση εταιρειών από ΓΕΜΗ")
    p.add_argument("--api-key", help="GEMI API key (αλλιώς από GEMI_API_KEY)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="Αναζήτηση με επωνυμία ή ΑΦΜ")
    s.add_argument("name", nargs="?")
    s.add_argument("--afm")

    i = sub.add_parser("info", help="Στοιχεία εταιρείας")
    i.add_argument("ar_gemi")

    f = sub.add_parser("fetch", help="Λήψη ισολογισμών και εξαγωγή σε JSON για έλεγχο")
    f.add_argument("ar_gemi")
    f.add_argument("--out")
    f.add_argument("--max-docs", type=int, default=5)

    an = sub.add_parser("analyze", help="Πλήρης ανάλυση")
    an.add_argument("ar_gemi", nargs="?", help="Αρ. ΓΕΜΗ (ή χρησιμοποιήστε --afm / --name)")
    an.add_argument("--afm", help="Εύρεση εταιρείας με ΑΦΜ")
    an.add_argument("--name", help="Εύρεση με επωνυμία (πρώτο αποτέλεσμα)")
    an.add_argument("--financials", action="append", default=[], help="JSON/CSV με οικονομικά (πολλαπλά επιτρέπονται)")
    an.add_argument("--pdf", action="append", default=[], help="Τοπικό PDF ισολογισμού ως ΑΡΧΕΙΟ:ΕΤΟΣ")
    an.add_argument("--no-fetch", action="store_true", help="Χωρίς αυτόματη λήψη ισολογισμών από ΓΕΜΗ")
    an.add_argument("--market-size", type=float, help="Μέγεθος αγοράς σε € (υπερισχύει)")
    an.add_argument("--kad", help="ΚΑΔ για εκτίμηση αγοράς (αλλιώς ο κύριος ΚΑΔ από ΓΕΜΗ)")
    an.add_argument("--peers", help="JSON με ανταγωνιστές [{name, revenue}]")
    an.add_argument("--peer-gemi", help="Αρ. ΓΕΜΗ ανταγωνιστών χωρισμένοι με κόμμα (αυτόματη λήψη)")
    an.add_argument("--no-eurostat", action="store_true")
    an.add_argument("--company-json", help="Offline: JSON απάντηση ΓΕΜΗ για την εταιρεία")
    an.add_argument("--out", help="Αρχείο HTML εξόδου")
    an.add_argument("--open", action="store_true", help="Άνοιγμα αναφοράς στον browser")

    t = sub.add_parser("template", help="Κενό CSV για χειροκίνητη καταχώρηση")
    t.add_argument("--out", default="financials_template.csv")

    d = sub.add_parser("demo", help="Δείγμα ανάλυσης χωρίς API")
    d.add_argument("--open", action="store_true")

    args = p.parse_args(argv)
    try:
        return _dispatch(args)
    except GemiError as ex:
        print(f"Σφάλμα ΓΕΜΗ: {ex}", file=sys.stderr)
        return 2


def _dispatch(args) -> int:
    if args.cmd == "template":
        cols = ["year"] + FIELD_NAMES
        Path(args.out).write_text(",".join(cols) + "\n" + "\n".join(
            str(date.today().year - k) + "," * len(FIELD_NAMES) for k in (3, 2, 1)) + "\n", encoding="utf-8")
        print(f"Δημιουργήθηκε {args.out} — συμπληρώστε τα ποσά σε € (μία γραμμή ανά χρήση).")
        return 0

    if args.cmd == "demo":
        ex = ROOT / "examples"
        company = normalize_company(json.loads((ex / "demo_company.json").read_text(encoding="utf-8")))
        years = load_financials(ex / "demo_financials.json")
        ns = argparse.Namespace(market_size=None, kad=None, peers=str(ex / "demo_peers.json"), peer_gemi=None,
                                no_eurostat=True, out=str(REPORTS / "demo_report.html"), open=args.open)
        run_analysis(company, years, ns)
        return 0

    if args.cmd == "analyze" and args.company_json:
        client = None
        company = normalize_company(json.loads(Path(args.company_json).read_text(encoding="utf-8")))
    else:
        client = GemiClient(args.api_key)

    if args.cmd == "search":
        res = client.search(name=args.name, afm=args.afm)
        if not res:
            print("Δεν βρέθηκαν αποτελέσματα.")
        for c in res:
            print(f"{c.ar_gemi:>14}  {c.afm or '':>10}  {c.status or '':<12} {c.name}")
        return 0

    if args.cmd == "info":
        c = client.company(args.ar_gemi)
        print(json.dumps({k: v for k, v in c.__dict__.items() if k != "raw"}, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "fetch":
        years, docs = fetch_financials(client, args.ar_gemi, args.max_docs)
        if not docs:
            print("Δεν βρέθηκαν δημοσιευμένοι ισολογισμοί στο ΓΕΜΗ.", file=sys.stderr)
        out = args.out or f"financials_{args.ar_gemi}.json"
        save_financials(years, out)
        print(f"Αποθηκεύτηκε {out} ({len(years)} χρήσεις). Ελέγξτε/διορθώστε και τρέξτε analyze --financials {out}")
        return 0

    # analyze
    docs = None
    if client is not None:
        if args.ar_gemi:
            company = client.company(args.ar_gemi)
        else:
            found = client.search(name=args.name, afm=args.afm, size=1)
            if not found:
                print("Η εταιρεία δεν βρέθηκε.", file=sys.stderr)
                return 1
            company = client.company(found[0].ar_gemi) if found[0].ar_gemi else found[0]
        print(f"Εταιρεία: {company.name} (ΓΕΜΗ {company.ar_gemi})", file=sys.stderr)

    groups = [load_financials(fp) for fp in args.financials]  # τα χειροκίνητα υπερισχύουν
    for spec in args.pdf:
        path, _, yr = spec.rpartition(":")
        groups.append(extract_from_pdf(path, int(yr)))
    if client is not None and not args.no_fetch:
        print("Λήψη ισολογισμών από ΓΕΜΗ…", file=sys.stderr)
        fetched, docs = fetch_financials(client, company.ar_gemi)
        groups.append(fetched)
    years = merge_years(*groups)
    if not years:
        print("Δεν βρέθηκαν οικονομικά στοιχεία. Χρησιμοποιήστε --financials ή --pdf "
              "(πρότυπο: python -m gemi_analyzer template).", file=sys.stderr)
        return 1
    run_analysis(company, years, args, docs, client)
    return 0
