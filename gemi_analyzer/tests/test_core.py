from gemi_analyzer.analysis import altman_z_double_prime, analyze
from gemi_analyzer.financials import YearFinancials, extract_from_text, parse_greek_number
from gemi_analyzer.gemi_client import normalize_company
from gemi_analyzer.market import _latest_jsonstat, nace_code, position


def test_parse_greek_number():
    assert parse_greek_number("1.234.567,89") == 1234567.89
    assert parse_greek_number("(12.345)") == -12345
    assert parse_greek_number("-") is None
    assert parse_greek_number("1.250.000") == 1250000


def test_extract_from_text_two_columns():
    text = """Κύκλος εργασιών (καθαρός) 5.650.000,00 5.200.000,00
Κόστος πωλήσεων (4.180.000,00) (3.800.000,00)
Αποτέλεσμα προ φόρων 7.1 505.000,00 470.000,00
Σύνολο ενεργητικού 4.750.000,00 4.300.000,00
Σύνολο καθαρής θέσης 2.050.000,00 1.660.000,00"""
    prev, cur = extract_from_text(text, 2024)
    assert cur.year == 2024 and cur.revenue == 5650000 and cur.ebt == 505000
    assert prev.revenue == 5200000 and cur.gross_profit == 1470000
    assert cur.total_liabilities == 2700000


def test_normalize_company():
    c = normalize_company({"arGemi": 123, "coNameEl": "ΤΕΣΤ ΑΕ",
                           "activities": [{"activity": {"id": "62.01", "descr": "Προγραμματισμός"},
                                           "type": {"descr": "Κύρια"}}]})
    assert c.ar_gemi == "123" and c.main_kad == "62.01"


def test_nace_code():
    assert nace_code("61.10.10.01") == "J61"
    assert nace_code("43.21.10.01", 3) == "F432"


def test_altman_and_analysis():
    y1 = YearFinancials(2023, revenue=100, ebt=10, interest_expense=2, net_income=8, total_assets=200,
                        current_assets=120, equity=100, current_liabilities=60, long_term_liabilities=40).complete()
    y2 = YearFinancials(2024, revenue=120, ebt=14, interest_expense=2, net_income=11, total_assets=220,
                        current_assets=130, equity=111, current_liabilities=69, long_term_liabilities=40).complete()
    z, zone = altman_z_double_prime(y2)
    assert z is not None and zone
    res = analyze([y2, y1])
    assert abs(res.ratios[-1].revenue_growth - 0.2) < 1e-9
    assert 0 <= res.assessment.score <= 100


def test_market_position_with_peers():
    m = position("Εμείς", 50, None, peers=[{"name": "Α", "revenue": 150}], use_eurostat=False)
    assert m.share == 0.25 and m.rank_among_peers == 2 and m.hhi == 6250


def test_jsonstat_latest():
    js = {"id": ["geo", "time"], "size": [1, 3],
          "dimension": {"time": {"category": {"index": {"2021": 0, "2022": 1, "2023": 2}}}},
          "value": {"0": 10.0, "1": 11.0}}
    assert _latest_jsonstat(js) == (11.0, 2022)
