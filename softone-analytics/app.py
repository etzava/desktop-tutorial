"""SoftOne Analytics – στατιστικά πωλήσεων από SoftOne ERP.
Εκτέλεση:  streamlit run app.py
"""
from __future__ import annotations

import io
import os
from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data import load_demo, load_file, load_softone
from softone_client import SoftOneConfig, SoftOneError

st.set_page_config(page_title="SoftOne Analytics", page_icon="📊", layout="wide")


# ------------------------------------------------------------------ helpers
def eur(x: float) -> str:
    if abs(x) >= 1_000_000:
        return f"€ {x / 1_000_000:.2f}".replace(".", ",") + " εκ."
    return f"€ {x:,.0f}".replace(",", ".")


def pct(x: float | None) -> str:
    return "–" if x is None or pd.isna(x) else f"{x:+.1%}".replace(".", ",")


def growth(cur: float, prev: float) -> float | None:
    return None if not prev else (cur - prev) / abs(prev)


def secret(key: str, default: str = "") -> str:
    try:
        return str(st.secrets["softone"][key])
    except Exception:
        return os.getenv(f"SOFTONE_{key.upper()}", default)


def kpis(df: pd.DataFrame) -> dict[str, float]:
    sales = df["NET_VALUE"].sum()
    gp = df["GROSS_PROFIT"].sum()
    docs = df["DOC_ID"].nunique()
    return {
        "sales": sales, "gp": gp, "gp_pct": gp / sales if sales else 0,
        "docs": docs, "customers": df["CUSTOMER"].nunique(), "avg_doc": sales / docs if docs else 0,
    }


def summary(df: pd.DataFrame, prev: pd.DataFrame, by: str) -> pd.DataFrame:
    cur = df.groupby(by).agg(Τζίρος=("NET_VALUE", "sum"), Μικτό_Κέρδος=("GROSS_PROFIT", "sum"),
                             Παραστατικά=("DOC_ID", "nunique"), Πελάτες=("CUSTOMER", "nunique"))
    cur["Περιθώριο_%"] = cur["Μικτό_Κέρδος"] / cur["Τζίρος"].where(cur["Τζίρος"] != 0)
    cur["Τζίρος_ΠΕ"] = prev.groupby(by)["NET_VALUE"].sum().reindex(cur.index).fillna(0)
    cur["Μεταβολή_%"] = (cur["Τζίρος"] - cur["Τζίρος_ΠΕ"]) / cur["Τζίρος_ΠΕ"].where(cur["Τζίρος_ΠΕ"] != 0)
    cur["Μερίδιο_%"] = cur["Τζίρος"] / cur["Τζίρος"].sum()
    return cur.sort_values("Τζίρος", ascending=False)


MONEY = {"Τζίρος": "€ {:,.0f}", "Μικτό_Κέρδος": "€ {:,.0f}", "Τζίρος_ΠΕ": "€ {:,.0f}",
         "Περιθώριο_%": "{:.1%}", "Μεταβολή_%": "{:+.1%}", "Μερίδιο_%": "{:.1%}"}


def show_table(df: pd.DataFrame, height: int | str = "auto"):
    st.dataframe(df.style.format(MONEY, na_rep="–"), width="stretch", height=height)


# ------------------------------------------------------------------ sidebar: πηγή
st.sidebar.title("📊 SoftOne Analytics")
source = st.sidebar.radio("Πηγή δεδομένων", ["SoftOne (live)", "Αρχείο Excel/CSV", "Demo δεδομένα"], index=2)

today = date.today()
c1, c2 = st.sidebar.columns(2)
d_from = c1.date_input("Από", date(today.year, 1, 1), format="DD/MM/YYYY")
d_to = c2.date_input("Έως", today, format="DD/MM/YYYY")
prev_from = d_from.replace(year=d_from.year - 1)

raw: pd.DataFrame | None = None

if source == "SoftOne (live)":
    with st.sidebar.expander("Σύνδεση SoftOne", expanded=not secret("url")):
        url = st.text_input("URL Web Services", secret("url"), placeholder="https://XXXXXXXX.oncloud.gr/s1services")
        user = st.text_input("Χρήστης", secret("username"))
        pwd = st.text_input("Κωδικός", secret("password"), type="password")
        app_id = st.text_input("App ID", secret("app_id"))
        company = st.text_input("Εταιρεία (κενό = 1η)", secret("company"))
        sql_name = st.text_input("Όνομα SQL script", secret("sql_name", "AIC_SALES_STATS"))

    @st.cache_data(ttl=900, show_spinner="Λήψη δεδομένων από SoftOne…")
    def _fetch(url, user, pwd, app_id, company, sql_name, f, t):
        cfg = SoftOneConfig(url=url, username=user, password=pwd, app_id=app_id, company=company or None)
        return load_softone(cfg, sql_name, f, t)

    if st.sidebar.button("🔄 Ανανέωση", width="stretch"):
        _fetch.clear()
    if url and user and app_id:
        try:
            raw = _fetch(url, user, pwd, app_id, company, sql_name, prev_from, d_to)
        except SoftOneError as e:
            st.error(f"SoftOne: {e}")
        except Exception as e:  # δίκτυο, SSL κ.λπ.
            st.error(f"Σφάλμα σύνδεσης: {e}")
    else:
        st.info("Συμπληρώστε τα στοιχεία σύνδεσης SoftOne στο αριστερό μενού.")

elif source == "Αρχείο Excel/CSV":
    up = st.sidebar.file_uploader("Export από SoftOne (xlsx/csv)", type=["xlsx", "xls", "csv"])
    st.sidebar.caption("Απαιτούμενες στήλες: TRNDATE, CUSTOMER, NET_VALUE. Προαιρετικές: βλ. README.")
    if up:
        try:
            raw = load_file(up)
        except Exception as e:
            st.error(str(e))
else:
    raw = st.cache_data(load_demo)()
    st.sidebar.success("Demo δεδομένα (ICT integrator, 2024–2026)")

if raw is None or raw.empty:
    st.title("SoftOne Analytics")
    st.write("Επιλέξτε πηγή δεδομένων για να ξεκινήσετε.")
    st.stop()

# ------------------------------------------------------------------ sidebar: φίλτρα
st.sidebar.divider()
st.sidebar.subheader("Φίλτρα")


def multi(label: str, col: str) -> list[str]:
    opts = sorted(raw[col].dropna().astype(str).unique())
    return st.sidebar.multiselect(label, opts) if len(opts) > 1 else []


f_branch = multi("Υποκατάστημα", "BRANCH")
f_sm = multi("Πωλητής", "SALESMAN")
f_grp = multi("Ομάδα ειδών", "ITEM_GROUP")
f_brand = multi("Brand", "BRAND")
f_cust = multi("Πελάτης", "CUSTOMER")

mask = pd.Series(True, index=raw.index)
for vals, col in [(f_branch, "BRANCH"), (f_sm, "SALESMAN"), (f_grp, "ITEM_GROUP"), (f_brand, "BRAND"), (f_cust, "CUSTOMER")]:
    if vals:
        mask &= raw[col].astype(str).isin(vals)
base = raw[mask]

ts_from, ts_to = pd.Timestamp(d_from), pd.Timestamp(d_to) + pd.Timedelta(days=1)
df = base[(base["TRNDATE"] >= ts_from) & (base["TRNDATE"] < ts_to)]
prev = base[(base["TRNDATE"] >= ts_from - pd.DateOffset(years=1)) & (base["TRNDATE"] < ts_to - pd.DateOffset(years=1))]

# ------------------------------------------------------------------ header + KPIs
st.title("Στατιστικά Πωλήσεων")
st.caption(f"Περίοδος {d_from:%d/%m/%Y} – {d_to:%d/%m/%Y} · σύγκριση με ίδια περίοδο προηγ. έτους")

k, kp = kpis(df), kpis(prev)
cols = st.columns(6)
cols[0].metric("Τζίρος", eur(k["sales"]), pct(growth(k["sales"], kp["sales"])))
cols[1].metric("Μικτό κέρδος", eur(k["gp"]), pct(growth(k["gp"], kp["gp"])))
cols[2].metric("Περιθώριο", f"{k['gp_pct']:.1%}", f"{(k['gp_pct'] - kp['gp_pct']) * 100:+.1f} μον.")
cols[3].metric("Παραστατικά", f"{k['docs']:,}".replace(",", "."), pct(growth(k["docs"], kp["docs"])))
cols[4].metric("Ενεργοί πελάτες", k["customers"], pct(growth(k["customers"], kp["customers"])))
cols[5].metric("Μέση αξία παραστ.", eur(k["avg_doc"]), pct(growth(k["avg_doc"], kp["avg_doc"])))

tab_over, tab_cust, tab_item, tab_team, tab_data = st.tabs(
    ["📈 Επισκόπηση", "👥 Πελάτες", "📦 Είδη & Brands", "🧑‍💼 Πωλητές & Καταστήματα", "📄 Δεδομένα & Export"])

# ------------------------------------------------------------------ Επισκόπηση
with tab_over:
    m = base.groupby("MONTH")["NET_VALUE"].sum().reset_index()
    m["Έτος"] = m["MONTH"].dt.year.astype(str)
    m["Μήνας"] = m["MONTH"].dt.month
    fig = px.line(m, x="Μήνας", y="NET_VALUE", color="Έτος", markers=True,
                  labels={"NET_VALUE": "Τζίρος (€)"}, title="Μηνιαίος τζίρος ανά έτος")
    fig.update_xaxes(dtick=1)
    st.plotly_chart(fig, width="stretch")

    c1, c2 = st.columns(2)
    cm = df.groupby("MONTH").agg(Τζίρος=("NET_VALUE", "sum"), ΜΚ=("GROSS_PROFIT", "sum")).reset_index()
    cm["Περιθώριο %"] = cm["ΜΚ"] / cm["Τζίρος"] * 100
    fig = go.Figure()
    fig.add_bar(x=cm["MONTH"], y=cm["Τζίρος"], name="Τζίρος")
    fig.add_bar(x=cm["MONTH"], y=cm["ΜΚ"], name="Μικτό κέρδος")
    fig.add_scatter(x=cm["MONTH"], y=cm["Περιθώριο %"], name="Περιθώριο %", yaxis="y2", mode="lines+markers")
    fig.update_layout(title="Τζίρος, κέρδος & περιθώριο", barmode="group",
                      yaxis2=dict(overlaying="y", side="right", ticksuffix="%", showgrid=False),
                      legend=dict(orientation="h", y=-0.2))
    c1.plotly_chart(fig, width="stretch")

    cum = df.set_index("TRNDATE")["NET_VALUE"].resample("D").sum().cumsum().reset_index()
    cump = prev.set_index("TRNDATE")["NET_VALUE"].resample("D").sum().cumsum().reset_index()
    cump["TRNDATE"] = cump["TRNDATE"] + pd.DateOffset(years=1)
    fig = go.Figure()
    fig.add_scatter(x=cum["TRNDATE"], y=cum["NET_VALUE"], name="Τρέχουσα περίοδος", fill="tozeroy")
    fig.add_scatter(x=cump["TRNDATE"], y=cump["NET_VALUE"], name="Προηγ. έτος", line=dict(dash="dot"))
    fig.update_layout(title="Σωρευτικός τζίρος (YTD) vs προηγ. έτος", legend=dict(orientation="h", y=-0.2))
    c2.plotly_chart(fig, width="stretch")

# ------------------------------------------------------------------ Πελάτες
with tab_cust:
    cs = summary(df, prev, "CUSTOMER")
    c1, c2 = st.columns([3, 2])
    top_n = c1.slider("Top N πελάτες", 5, 50, 15)
    fig = px.bar(cs.head(top_n).reset_index(), x="Τζίρος", y="CUSTOMER", orientation="h",
                 color="Περιθώριο_%", color_continuous_scale="RdYlGn", title=f"Top {top_n} πελάτες")
    fig.update_layout(yaxis=dict(autorange="reversed", title=None), coloraxis_colorbar=dict(tickformat=".0%"))
    c1.plotly_chart(fig, width="stretch")

    # ABC / Pareto
    abc = cs[["Τζίρος"]].copy()
    abc["Σωρευτικό_%"] = abc["Τζίρος"].cumsum() / abc["Τζίρος"].sum()
    abc["Κατηγορία"] = pd.cut(abc["Σωρευτικό_%"], [-1, 0.8, 0.95, 2], labels=["A", "B", "C"])
    counts = abc["Κατηγορία"].value_counts().reindex(["A", "B", "C"]).fillna(0)
    c2.markdown("**Ανάλυση ABC (Pareto)**")
    for cat, label in [("A", "80% του τζίρου"), ("B", "επόμενο 15%"), ("C", "τελευταίο 5%")]:
        c2.write(f"**{cat}** · {int(counts[cat])} πελάτες → {label}")
    conc = cs["Μερίδιο_%"].head(5).sum()
    c2.metric("Συγκέντρωση top-5 πελατών", f"{conc:.1%}")
    if conc > 0.5:
        c2.warning("Υψηλή εξάρτηση από λίγους πελάτες (>50% στους top-5).")

    st.subheader("Κίνηση πελατολογίου")
    cur_c, prev_c = set(df["CUSTOMER"]), set(prev["CUSTOMER"])
    hist_c = set(base[base["TRNDATE"] < ts_from]["CUSTOMER"])
    new_c = sorted(cur_c - hist_c)
    lost_c = sorted(prev_c - cur_c)
    a, b, c = st.columns(3)
    a.metric("Νέοι πελάτες", len(new_c))
    b.metric("Χαμένοι (αγόρασαν πέρσι, όχι φέτος)", len(lost_c))
    c.metric("Retention", f"{len(cur_c & prev_c) / len(prev_c):.0%}" if prev_c else "–")
    if lost_c:
        lost = prev[prev["CUSTOMER"].isin(lost_c)].groupby("CUSTOMER")["NET_VALUE"].sum().sort_values(ascending=False)
        st.markdown("**Χαμένοι πελάτες – τζίρος προηγ. έτους (λίστα για επανενεργοποίηση):**")
        st.dataframe(lost.rename("Τζίρος ΠΕ").to_frame().style.format("€ {:,.0f}"), width="stretch")
    with st.expander("Πλήρης πίνακας πελατών"):
        show_table(cs)

# ------------------------------------------------------------------ Είδη
with tab_item:
    c1, c2 = st.columns(2)
    tm = df.groupby(["ITEM_GROUP", "BRAND"])["NET_VALUE"].sum().reset_index()
    tm = tm[tm["NET_VALUE"] > 0]
    c1.plotly_chart(px.treemap(tm, path=["ITEM_GROUP", "BRAND"], values="NET_VALUE",
                               title="Τζίρος ανά ομάδα & brand"), width="stretch")
    gs = summary(df, prev, "ITEM_GROUP").reset_index()
    fig = px.scatter(gs, x="Τζίρος", y="Περιθώριο_%", size=gs["Μικτό_Κέρδος"].clip(lower=0) + 1,
                     text="ITEM_GROUP", title="Ομάδες: τζίρος vs περιθώριο (μέγεθος = μικτό κέρδος)")
    fig.update_traces(textposition="top center")
    fig.update_yaxes(tickformat=".0%")
    c2.plotly_chart(fig, width="stretch")

    st.subheader("Brands")
    show_table(summary(df, prev, "BRAND"))
    st.subheader("Top είδη")
    it = summary(df, prev, "ITEM")
    it.insert(0, "Ποσότητα", df.groupby("ITEM")["QTY"].sum())
    show_table(it.head(50), height=400)

# ------------------------------------------------------------------ Πωλητές
with tab_team:
    ss = summary(df, prev, "SALESMAN")
    c1, c2 = st.columns(2)
    sm = df.groupby(["MONTH", "SALESMAN"])["NET_VALUE"].sum().reset_index()
    c1.plotly_chart(px.bar(sm, x="MONTH", y="NET_VALUE", color="SALESMAN", title="Τζίρος ανά πωλητή / μήνα",
                           labels={"NET_VALUE": "€", "MONTH": ""}), width="stretch")
    bs = df.groupby("BRANCH")["NET_VALUE"].sum().reset_index()
    c2.plotly_chart(px.pie(bs, names="BRANCH", values="NET_VALUE", hole=0.5, title="Μερίδιο υποκαταστημάτων"),
                    width="stretch")
    st.subheader("Απόδοση πωλητών")
    show_table(ss)
    st.subheader("Υποκαταστήματα")
    show_table(summary(df, prev, "BRANCH"))

# ------------------------------------------------------------------ Data/export
with tab_data:
    st.write(f"{len(df):,} γραμμές στην επιλεγμένη περίοδο.".replace(",", "."))
    st.dataframe(df.drop(columns=["YEAR", "MONTH"]), width="stretch", height=420)

    def to_excel() -> bytes:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as xw:
            pd.DataFrame([
                ["Περίοδος", f"{d_from:%d/%m/%Y} – {d_to:%d/%m/%Y}"],
                ["Τζίρος", k["sales"]], ["Τζίρος ΠΕ", kp["sales"]], ["Μικτό κέρδος", k["gp"]],
                ["Περιθώριο %", k["gp_pct"]], ["Παραστατικά", k["docs"]], ["Πελάτες", k["customers"]],
            ], columns=["Δείκτης", "Τιμή"]).to_excel(xw, sheet_name="KPIs", index=False)
            summary(df, prev, "CUSTOMER").to_excel(xw, sheet_name="Πελάτες")
            summary(df, prev, "ITEM").to_excel(xw, sheet_name="Είδη")
            summary(df, prev, "BRAND").to_excel(xw, sheet_name="Brands")
            summary(df, prev, "SALESMAN").to_excel(xw, sheet_name="Πωλητές")
            df.groupby("MONTH")[["NET_VALUE", "GROSS_PROFIT"]].sum().to_excel(xw, sheet_name="Ανά μήνα")
            df.drop(columns=["YEAR", "MONTH"]).to_excel(xw, sheet_name="Γραμμές", index=False)
        return buf.getvalue()

    st.download_button("⬇️ Λήψη αναφοράς Excel", to_excel(), f"softone_stats_{d_from:%Y%m%d}_{d_to:%Y%m%d}.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
