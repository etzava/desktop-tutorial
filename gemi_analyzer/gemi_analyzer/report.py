"""Δημιουργία αυτόνομης HTML αναφοράς (χωρίς εξωτερικές εξαρτήσεις, inline SVG γραφήματα)."""

from __future__ import annotations

import html
import json
from dataclasses import asdict
from datetime import date

from .analysis import FIELD_LABELS, RATIO_LABELS, AnalysisResult
from .gemi_client import Company
from .market import MarketPosition

e = html.escape


def eur(v, short: bool = True) -> str:
    if v is None:
        return "—"
    if short and abs(v) >= 1_000_000:
        return f"€{v / 1_000_000:,.2f}M".replace(",", "X").replace(".", ",").replace("X", ".")
    if short and abs(v) >= 10_000:
        return f"€{v / 1_000:,.0f}K".replace(",", ".")
    return f"€{v:,.0f}".replace(",", ".")


def pct(v) -> str:
    return "—" if v is None else f"{v * 100:.1f}%".replace(".", ",")


def fmt_ratio(v, kind: str) -> str:
    if v is None:
        return "—"
    if kind == "pct":
        return pct(v)
    if kind == "eur":
        return eur(v)
    if kind == "days":
        return f"{v:.0f}"
    return f"{v:.2f}".replace(".", ",")


def _bar_chart(title: str, series: list[tuple[str, list[float | None]]], labels: list[str]) -> str:
    """Ομαδοποιημένο ραβδόγραμμα σε SVG."""
    W, H, PAD_L, PAD_B, PAD_T = 640, 240, 70, 28, 16
    vals = [v for _, s in series for v in s if v is not None]
    if not vals:
        return ""
    vmax, vmin = max(max(vals), 0), min(min(vals), 0)
    rng = (vmax - vmin) or 1
    plot_h = H - PAD_B - PAD_T
    y0 = PAD_T + plot_h * vmax / rng
    group_w = (W - PAD_L - 10) / len(labels)
    bar_w = min(36, group_w * 0.7 / len(series))
    colors = ["var(--c1)", "var(--c2)", "var(--c3)"]
    parts = [f'<line x1="{PAD_L}" x2="{W - 10}" y1="{y0:.1f}" y2="{y0:.1f}" class="axis"/>']
    for i in range(5):
        v = vmin + rng * i / 4
        y = PAD_T + plot_h * (vmax - v) / rng
        parts.append(f'<line x1="{PAD_L}" x2="{W - 10}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>')
        parts.append(f'<text x="{PAD_L - 6}" y="{y + 4:.1f}" class="tick" text-anchor="end">{e(eur(v))}</text>')
    for gi, lab in enumerate(labels):
        gx = PAD_L + gi * group_w + (group_w - bar_w * len(series)) / 2
        for si, (name, s) in enumerate(series):
            v = s[gi]
            if v is None:
                continue
            h = plot_h * abs(v) / rng
            y = y0 - h if v >= 0 else y0
            parts.append(
                f'<rect x="{gx + si * bar_w:.1f}" y="{y:.1f}" width="{bar_w - 3:.1f}" height="{max(h, 1):.1f}" '
                f'rx="2" fill="{colors[si % 3]}"><title>{e(name)} {lab}: {e(eur(v, False))}</title></rect>'
            )
        parts.append(f'<text x="{PAD_L + gi * group_w + group_w / 2:.1f}" y="{H - 8}" class="tick" '
                     f'text-anchor="middle">{e(lab)}</text>')
    legend = "".join(
        f'<span><i style="background:{colors[i % 3]}"></i>{e(n)}</span>' for i, (n, _) in enumerate(series)
    )
    return (f'<figure><figcaption>{e(title)}</figcaption><div class="legend">{legend}</div>'
            f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{e(title)}">{"".join(parts)}</svg></figure>')


def _gauge(score: float, grade: str) -> str:
    color = "var(--good)" if score >= 65 else "var(--warn)" if score >= 45 else "var(--bad)"
    return (f'<div class="gauge"><div class="gauge-num" style="color:{color}">{score:.0f}</div>'
            f'<div class="gauge-sub">/100 · {e(grade)}</div>'
            f'<div class="meter"><div style="width:{score:.0f}%;background:{color}"></div></div></div>')


def render_html(company: Company, result: AnalysisResult, market: MarketPosition | None,
                docs: list[dict] | None = None) -> str:
    years = result.years
    labels = [str(y.year) for y in years]
    last = years[-1]
    lr = result.ratios[-1]
    a = result.assessment

    kpis = [
        ("Κύκλος εργασιών " + str(last.year), eur(last.revenue), pct(lr.revenue_growth) + " ετήσια μεταβολή"),
        ("EBITDA", eur(last.ebitda), "περιθώριο " + pct(lr.ebitda_margin)),
        ("Καθαρά κέρδη", eur(last.net_income), "περιθώριο " + pct(lr.net_margin)),
        ("CAGR πωλήσεων", pct(result.revenue_cagr), f"{years[0].year}–{last.year}"),
        ("Ίδια κεφάλαια", eur(last.equity), "ROE " + pct(lr.roe)),
        ("Μερίδιο αγοράς", pct(market.share) if market else "—",
         (market.market.source if market else "δεν υπολογίστηκε")),
    ]
    kpi_html = "".join(
        f'<div class="kpi"><div class="kpi-l">{e(l)}</div><div class="kpi-v">{e(v)}</div>'
        f'<div class="kpi-s">{e(s)}</div></div>' for l, v, s in kpis
    )

    info_rows = [
        ("Επωνυμία", company.name), ("Αρ. ΓΕΜΗ", company.ar_gemi), ("ΑΦΜ", company.afm),
        ("Νομική μορφή", company.legal_type), ("Κατάσταση", company.status),
        ("Ημ. σύστασης", company.incorporation_date), ("Έδρα", company.address),
        ("Κύριος ΚΑΔ", f"{company.main_kad or '—'} {company.main_kad_descr or ''}"),
        ("Κεφάλαιο", eur(company.capital, False) if company.capital else None),
        ("Website", company.website),
    ]
    info_html = "".join(f"<tr><th>{e(k)}</th><td>{e(str(v))}</td></tr>" for k, v in info_rows if v)
    persons_html = "".join(f"<li>{e(p['name'])} — {e(p['role'])}</li>" for p in company.persons[:12])

    # Πίνακας οικονομικών
    fin_fields = ["revenue", "gross_profit", "ebit", "net_income", "total_assets", "current_assets",
                  "cash", "equity", "total_liabilities", "current_liabilities", "bank_debt", "employees"]
    fin_rows = ""
    for f in fin_fields:
        vals = [getattr(y, f) for y in years]
        if all(v is None for v in vals):
            continue
        cells = "".join(
            f"<td>{(f'{v:.0f}' if f == 'employees' else eur(v, False)) if v is not None else '—'}</td>"
            for v in vals)
        fin_rows += f"<tr><th>{e(FIELD_LABELS[f])}</th>{cells}</tr>"

    ratio_rows = ""
    for key, (label, kind) in RATIO_LABELS.items():
        vals = [getattr(r, key) for r in result.ratios]
        if all(v is None for v in vals):
            continue
        ratio_rows += f"<tr><th>{e(label)}</th>" + "".join(f"<td>{fmt_ratio(v, kind)}</td>" for v in vals) + "</tr>"

    change_rows = "".join(
        f"<tr><th>{e(c.label)}</th><td>{eur(c.prev, False)}</td><td>{eur(c.cur, False)}</td>"
        f"<td class=\"{'pos' if c.abs_change > 0 else 'neg'}\">{eur(c.abs_change, False)}</td>"
        f"<td>{pct(c.pct_change)}</td></tr>" for c in result.changes
    )

    pillars_html = "".join(
        f'<div class="pillar"><span>{e(k)}</span><div class="meter"><div style="width:{v or 0:.0f}%"></div></div>'
        f'<b>{"—" if v is None else f"{v:.0f}"}</b></div>' for k, v in a.pillars.items()
    )

    market_html = ""
    if market:
        m = market.market
        market_html = f"""
<section><h2>Αγορά & ανταγωνιστική θέση</h2>
<table class="kv"><tr><th>Μέγεθος αγοράς</th><td>{eur(m.size, False)}{f' ({m.year})' if m.year else ''}</td></tr>
<tr><th>Πηγή</th><td>{e(m.source)} {e(m.scope)}</td></tr>
<tr><th>Μερίδιο εταιρείας</th><td><b>{pct(market.share)}</b></td></tr>
{f'<tr><th>Σημείωση</th><td>{e(m.note)}</td></tr>' if m.note else ''}</table>"""
        if market.peers:
            peer_rows = "".join(
                f"<tr class=\"{'self' if p.get('self') else ''}\"><td>{i + 1}</td><td>{e(p['name'])}</td>"
                f"<td>{eur(p['revenue'], False)}</td><td>{pct(p['share'])}</td></tr>"
                for i, p in enumerate(market.peers))
            market_html += f"""
<h3>Σύγκριση με ανταγωνιστές</h3>
<p>Θέση <b>#{market.rank_among_peers}</b> από {len(market.peers)} · μερίδιο μεταξύ peers <b>{pct(market.peer_share)}</b>
· HHI {market.hhi:.0f} ({e(market.concentration or '')})</p>
<table><thead><tr><th>#</th><th>Εταιρεία</th><th>Πωλήσεις</th><th>Μερίδιο</th></tr></thead><tbody>{peer_rows}</tbody></table>"""
        market_html += "</section>"

    docs_html = ""
    if docs:
        items = "".join(
            f'<li><a href="{e(str(d.get("url") or d.get("downloadUrl") or d.get("fileUrl") or "#"))}">'
            f'{e(str(d.get("title") or d.get("descr") or d.get("name") or d.get("dateAnnounced") or "Έγγραφο"))}</a></li>'
            for d in docs[:20])
        docs_html = f"<section><h2>Δημοσιευμένοι ισολογισμοί (ΓΕΜΗ)</h2><ul>{items}</ul></section>"

    th_years = "".join(f"<th>{y}</th>" for y in labels)
    charts = (
        _bar_chart("Πωλήσεις & κερδοφορία", [
            ("Πωλήσεις", [y.revenue for y in years]),
            ("EBITDA", [y.ebitda for y in years]),
            ("Καθαρά κέρδη", [y.net_income for y in years]),
        ], labels)
        + _bar_chart("Κεφαλαιακή διάρθρωση", [
            ("Ενεργητικό", [y.total_assets for y in years]),
            ("Ίδια κεφάλαια", [y.equity for y in years]),
            ("Υποχρεώσεις", [y.total_liabilities for y in years]),
        ], labels)
    )

    return f"""<!doctype html>
<html lang="el"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(company.name)} — Αξιολόγηση</title>
<style>
:root{{--bg:#f6f7f9;--card:#fff;--fg:#1b1f24;--mut:#5d6672;--line:#e3e6ea;--c1:#2563eb;--c2:#0d9488;--c3:#d97706;
--good:#15803d;--warn:#b45309;--bad:#b91c1c}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0f1216;--card:#171b21;--fg:#e6e9ee;--mut:#9aa4b1;--line:#2a3039;
--c1:#60a5fa;--c2:#2dd4bf;--c3:#fbbf24;--good:#4ade80;--warn:#fbbf24;--bad:#f87171}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
main{{max-width:1080px;margin:0 auto;padding:24px 16px 64px}}
header h1{{margin:0;font-size:26px}}header p{{margin:4px 0 0;color:var(--mut)}}
section{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin-top:16px;overflow-x:auto}}
h2{{font-size:17px;margin:0 0 12px}}h3{{font-size:15px;margin:16px 0 8px}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}@media(max-width:720px){{.grid2{{grid-template-columns:1fr}}}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-top:16px}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}}
.kpi-l{{color:var(--mut);font-size:12px}}.kpi-v{{font-size:22px;font-weight:650;font-variant-numeric:tabular-nums}}.kpi-s{{color:var(--mut);font-size:12px}}
table{{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}}th,td{{padding:6px 8px;border-bottom:1px solid var(--line);text-align:right}}
th:first-child,td:first-child{{text-align:left}}thead th{{color:var(--mut);font-weight:600}}
table.kv th{{width:38%;color:var(--mut);font-weight:500}}table.kv td{{text-align:left}}
tr.self{{font-weight:700;color:var(--c1)}}.pos{{color:var(--good)}}.neg{{color:var(--bad)}}
.gauge-num{{font-size:56px;font-weight:700;line-height:1}}.gauge-sub{{color:var(--mut)}}
.meter{{height:8px;background:var(--line);border-radius:4px;overflow:hidden;margin-top:8px}}.meter>div{{height:100%;background:var(--c1)}}
.pillar{{display:grid;grid-template-columns:120px 1fr 36px;gap:10px;align-items:center;margin:6px 0}}.pillar .meter{{margin:0}}.pillar b{{text-align:right}}
ul.s li::marker{{content:"＋ ";color:var(--good)}}ul.w li::marker{{content:"－ ";color:var(--bad)}}
figure{{margin:0 0 12px}}figcaption{{font-weight:600;margin-bottom:4px}}svg{{width:100%;height:auto}}
.axis{{stroke:var(--mut)}}.grid{{stroke:var(--line)}}.tick{{fill:var(--mut);font-size:11px}}
.legend{{display:flex;gap:14px;font-size:12px;color:var(--mut)}}.legend i{{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px}}
footer{{color:var(--mut);font-size:12px;margin-top:20px}}a{{color:var(--c1)}}
</style></head><body><main>
<header><h1>{e(company.name)}</h1><p>Αρ. ΓΕΜΗ {e(company.ar_gemi)} · ΑΦΜ {e(company.afm or '—')} · Αναφορά {date.today():%d/%m/%Y}</p></header>
<div class="kpis">{kpi_html}</div>
<section><h2>Συνολική αξιολόγηση</h2><div class="grid2"><div>{_gauge(a.score, a.grade)}<p>{e(a.summary)}</p></div>
<div>{pillars_html}</div></div>
<div class="grid2"><div><h3>Δυνατά σημεία</h3><ul class="s">{''.join(f'<li>{e(x)}</li>' for x in a.strengths) or '<li>—</li>'}</ul></div>
<div><h3>Αδυναμίες / κίνδυνοι</h3><ul class="w">{''.join(f'<li>{e(x)}</li>' for x in a.weaknesses) or '<li>—</li>'}</ul></div></div></section>
<section><h2>Εξέλιξη</h2>{charts}</section>
<section><h2>Οικονομικά στοιχεία</h2><table><thead><tr><th></th>{th_years}</tr></thead><tbody>{fin_rows}</tbody></table></section>
<section><h2>Χρηματοοικονομικοί δείκτες</h2><table><thead><tr><th></th>{th_years}</tr></thead><tbody>{ratio_rows}</tbody></table></section>
<section><h2>Ανάλυση ισολογισμού — σημαντικότερες μεταβολές {years[-2].year if len(years) > 1 else ''}→{last.year}</h2>
<table><thead><tr><th>Κονδύλι</th><th>Προηγ.</th><th>Τρέχουσα</th><th>Μεταβολή</th><th>%</th></tr></thead><tbody>{change_rows or '<tr><td colspan=5>Απαιτούνται ≥2 χρήσεις</td></tr>'}</tbody></table></section>
{market_html}
<section class="grid2"><div><h2>Στοιχεία ΓΕΜΗ</h2><table class="kv">{info_html}</table></div>
<div><h2>Διοίκηση / Εκπρόσωποι</h2><ul>{persons_html or '<li>—</li>'}</ul></div></section>
{docs_html}
<footer>Πηγές: ΓΕΜΗ Open Data API, δημοσιευμένες οικονομικές καταστάσεις{', ' + e(market.market.source) if market else ''}.
Η βαθμολογία είναι ποσοτικό εργαλείο screening και δεν υποκαθιστά due diligence.</footer>
</main></body></html>"""


def to_json(company: Company, result: AnalysisResult, market: MarketPosition | None) -> str:
    payload = {
        "company": {k: v for k, v in asdict(company).items() if k != "raw"},
        "years": [asdict(y) | {"ebitda": y.ebitda} for y in result.years],
        "ratios": [asdict(r) for r in result.ratios],
        "revenue_cagr": result.revenue_cagr,
        "changes": [asdict(c) for c in result.changes],
        "assessment": asdict(result.assessment),
        "market": asdict(market) if market else None,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)
