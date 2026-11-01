# SoftOne Analytics

Web εφαρμογή (Python / Streamlit) που συνδέεται στο **SoftOne ERP μέσω Web Services**, τραβάει τις πωλήσεις και παράγει στατιστικά & dashboards.

## Τι δείχνει
| Ενότητα | Περιεχόμενο |
|---|---|
| **KPIs** | Τζίρος, μικτό κέρδος, περιθώριο %, παραστατικά, ενεργοί πελάτες, μέση αξία – όλα σε σύγκριση με την ίδια περίοδο πέρσι |
| **Επισκόπηση** | Μηνιαίος τζίρος ανά έτος, τζίρος/κέρδος/περιθώριο ανά μήνα, σωρευτικός YTD vs προηγ. έτος |
| **Πελάτες** | Top N, ανάλυση ABC (Pareto), συγκέντρωση top-5, νέοι / χαμένοι πελάτες, retention, λίστα επανενεργοποίησης |
| **Είδη & Brands** | Treemap ομάδα→brand, τζίρος vs περιθώριο ανά ομάδα, πίνακες brands & top ειδών |
| **Πωλητές & Καταστήματα** | Τζίρος ανά πωλητή/μήνα, μερίδιο υποκαταστημάτων, πίνακες απόδοσης με YoY |
| **Export** | Αναφορά Excel με φύλλα KPIs / Πελάτες / Είδη / Brands / Πωλητές / Ανά μήνα / Γραμμές |

Φίλτρα: περίοδος, υποκατάστημα, πωλητής, ομάδα ειδών, brand, πελάτης.

## Πηγές δεδομένων
1. **SoftOne (live)** – Web Services: `login → authenticate → SqlData`
2. **Αρχείο Excel/CSV** – export από SoftOne (στήλες όπως στο SQL παρακάτω, ελάχιστες: `TRNDATE, CUSTOMER, NET_VALUE`)
3. **Demo** – συνθετικά δεδομένα για παρουσίαση

## Εγκατάσταση
```bash
cd softone-analytics
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # και συμπληρώστε
streamlit run app.py
```
Ανοίγει στο http://localhost:8501

## Ρύθμιση στο SoftOne (μία φορά, με τον SoftOne partner)
1. **Χρήστης Web Services** με δικαιώματα μόνο ανάγνωσης.
2. **appId** – ενεργοποίηση Web Services στο serial (για Cloud: `https://<serial>.oncloud.gr/s1services`).
3. **SQL script** με όνομα `AIC_SALES_STATS` και περιεχόμενο από το [`sql/AIC_SALES_STATS.sql`](sql/AIC_SALES_STATS.sql).
   Παράμετροι: `param1` = από (YYYYMMDD), `param2` = έως (YYYYMMDD).
   ⚠️ Επιβεβαιώστε σειρές παραστατικών, πρόσημο πιστωτικών και πεδίο κόστους για τη δική σας εγκατάσταση.

## Αρχιτεκτονική
```
softone_client.py   Client Web Services (login/authenticate, SqlData, getTable, getBrowserData,
                    αυτόματο re-login, αποκωδικοποίηση windows-1253)
data.py             Φόρτωση & κανονικοποίηση (SoftOne / αρχείο / demo)
app.py              Dashboard (Streamlit + Plotly), cache 15'
sql/                SQL scripts για το SoftOne
```

## Επόμενα βήματα (roadmap)
- Εγκατάσταση σε server/VM της εταιρείας ή σε Streamlit Cloud, πίσω από SSO.
- Επιπλέον scripts: ανοιχτά υπόλοιπα πελατών (aging), αγορές/προμηθευτές, αποθέματα, εκκρεμείς παραγγελίες.
- Νυχτερινό sync σε βάση (PostgreSQL) για ιστορικότητα & ταχύτητα → Power BI / Metabase.
- Ημερήσιο email με KPIs και ειδοποιήσεις (π.χ. πελάτης κατηγορίας A χωρίς αγορά για 60 ημέρες).
