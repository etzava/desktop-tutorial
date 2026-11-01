"""Φόρτωση δεδομένων: SoftOne (live), αρχείο (Excel/CSV export) ή demo."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from softone_client import SoftOneClient, SoftOneConfig

COLUMNS = [
    "DOC_ID", "TRNDATE", "DOC_NO", "SERIES", "BRANCH", "CUSTOMER_CODE", "CUSTOMER", "CITY",
    "SALESMAN", "ITEM_CODE", "ITEM", "ITEM_GROUP", "BRAND", "QTY", "NET_VALUE", "COST",
]


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().upper() for c in df.columns]
    missing = {"TRNDATE", "CUSTOMER", "NET_VALUE"} - set(df.columns)
    if missing:
        raise ValueError(f"Λείπουν υποχρεωτικές στήλες: {', '.join(sorted(missing))}")
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = 0 if c in ("QTY", "COST") else "-"
    df["TRNDATE"] = pd.to_datetime(df["TRNDATE"], errors="coerce")
    for c in ("QTY", "NET_VALUE", "COST"):
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", ".", regex=False), errors="coerce").fillna(0)
    if (df["DOC_ID"] == "-").all():
        df["DOC_ID"] = df["DOC_NO"]
    df = df.dropna(subset=["TRNDATE"])
    df["GROSS_PROFIT"] = df["NET_VALUE"] - df["COST"]
    df["YEAR"] = df["TRNDATE"].dt.year
    df["MONTH"] = df["TRNDATE"].dt.to_period("M").dt.to_timestamp()
    return df[COLUMNS + ["GROSS_PROFIT", "YEAR", "MONTH"]]


def load_softone(cfg: SoftOneConfig, sql_name: str, d_from: date, d_to: date) -> pd.DataFrame:
    client = SoftOneClient(cfg)
    rows = client.sql_data(sql_name, param1=d_from.strftime("%Y%m%d"), param2=d_to.strftime("%Y%m%d"))
    if not rows:
        return normalize(pd.DataFrame(columns=COLUMNS))
    return normalize(pd.DataFrame(rows))


def load_file(uploaded) -> pd.DataFrame:
    name = uploaded.name.lower()
    if name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(uploaded)
    else:
        df = pd.read_csv(uploaded, sep=None, engine="python", encoding_errors="replace")
    return normalize(df)


# ------------------------------------------------------------------ demo data
def load_demo(seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    customers = [
        ("Ξενοδοχεία Αιγαίου ΑΕ", "Ρόδος"), ("Δήμος Αθηναίων", "Αθήνα"), ("Δήμος Πειραιά", "Πειραιάς"),
        ("Grand Resort Χαλκιδική", "Χαλκιδική"), ("ΒΙΟΜΕΤ ΑΒΕΕ", "Θεσσαλονίκη"), ("Κρήτη Hotels Group", "Ηράκλειο"),
        ("Περιφέρεια Αττικής", "Αθήνα"), ("Logistics Hellas", "Ασπρόπυργος"), ("Νοσοκομείο Αγ. Σάββας", "Αθήνα"),
        ("Santorini Suites", "Σαντορίνη"), ("ΕΛΒΙΠ ΑΕ", "Βόλος"), ("Mykonos Blue", "Μύκονος"),
        ("Πανεπιστήμιο Πατρών", "Πάτρα"), ("Δήμος Λάρισας", "Λάρισα"), ("Marina Resorts", "Κέρκυρα"),
        ("ΤΕΧΝΟΔΟΜΗ ΑΤΕ", "Αθήνα"), ("Olympic Foods", "Κόρινθος"), ("Zante Palace", "Ζάκυνθος"),
    ]
    items = [
        ("UBQ-U7PRO", "Ubiquiti U7 Pro Access Point", "Wireless", "Ubiquiti", 210, 0.27),
        ("UBQ-USW48", "Ubiquiti USW-Pro-48-PoE", "Switching", "Ubiquiti", 1150, 0.22),
        ("MKT-CCR2116", "MikroTik CCR2116 Router", "Routing", "MikroTik", 1050, 0.25),
        ("FTN-FG60F", "Fortinet FortiGate 60F", "Security", "Fortinet", 720, 0.20),
        ("FTN-FG100F", "Fortinet FortiGate 100F", "Security", "Fortinet", 3100, 0.18),
        ("HUA-S5735", "Huawei S5735 Switch 24P", "Switching", "Huawei", 890, 0.21),
        ("DAH-IPC4MP", "Dahua IP Camera 4MP", "CCTV", "Dahua", 95, 0.32),
        ("DAH-NVR32", "Dahua NVR 32ch", "CCTV", "Dahua", 680, 0.28),
        ("YEA-P550", "Yeastar P550 PBX", "Telephony", "Yeastar", 990, 0.26),
        ("FAN-X4U", "Fanvil X4U IP Phone", "Telephony", "Fanvil", 85, 0.30),
        ("MIL-AM319", "Milesight AM319 IoT Sensor", "IoT", "Milesight", 140, 0.35),
        ("SRV-INST", "Υπηρεσίες Εγκατάστασης (ώρα)", "Services", "A.I.C.", 45, 0.70),
        ("SRV-SLA", "Συμβόλαιο Υποστήριξης SLA (μήνας)", "Services", "A.I.C.", 380, 0.65),
    ]
    salesmen = ["Παπαδόπουλος Γ.", "Νικολάου Μ.", "Κωνσταντίνου Α.", "Δημητρίου Ε."]
    branches = ["Αθήνα", "Θεσσαλονίκη"]

    cust_w = rng.pareto(1.3, len(customers)) + 0.2
    cust_w /= cust_w.sum()
    rows, doc_id = [], 100000
    days = pd.date_range("2024-01-01", "2026-10-31", freq="D")
    season = 1 + 0.35 * np.sin((days.dayofyear - 60) / 365 * 2 * np.pi)
    growth = 1 + 0.18 * (days.year - 2024) + 0.015 * (days.month)
    for d, s, g in zip(days, season, growth):
        if d.weekday() >= 5:
            continue
        for _ in range(rng.poisson(1.8 * s * g)):
            doc_id += 1
            ci = rng.choice(len(customers), p=cust_w)
            sm = salesmen[ci % len(salesmen)] if rng.random() < 0.85 else rng.choice(salesmen)
            br = branches[1] if customers[ci][1] in ("Θεσσαλονίκη", "Χαλκιδική", "Λάρισα", "Βόλος") else branches[0]
            credit = rng.random() < 0.04
            for ii in rng.choice(len(items), size=rng.integers(1, 5), replace=False):
                code, name, grp, brand, price, margin = items[ii]
                qty = int(rng.integers(1, 25 if price < 300 else 6))
                val = round(qty * price * rng.uniform(0.85, 1.05), 2)
                cost = round(val * (1 - margin * rng.uniform(0.8, 1.2)), 2)
                sign = -1 if credit else 1
                rows.append({
                    "DOC_ID": doc_id, "TRNDATE": d, "DOC_NO": f"{'ΠΙΣ' if credit else 'ΤΔΑ'}-{doc_id}",
                    "SERIES": "Πιστωτικό" if credit else "Τιμολόγιο-ΔΑ", "BRANCH": br,
                    "CUSTOMER_CODE": f"Π{ci + 1:04d}", "CUSTOMER": customers[ci][0], "CITY": customers[ci][1],
                    "SALESMAN": sm, "ITEM_CODE": code, "ITEM": name, "ITEM_GROUP": grp, "BRAND": brand,
                    "QTY": qty * sign, "NET_VALUE": val * sign, "COST": cost * sign,
                })
    return normalize(pd.DataFrame(rows))
