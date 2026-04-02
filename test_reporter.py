"""
test_reporter.py — L1 单元测试，测试 Markdown 报告生成
"""
import pytest
from datetime import date


# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_PROPERTY = {
    "zpid": "12345678",
    "address": "19533 E Timberline Rd, Queen Creek, AZ, 85142",
    "price": 550000,
    "bedrooms": 4,
    "bathrooms": 3,
    "yearBuilt": 2018,
    "livingArea": 2800,
    "lotSize": 8500,
    "homeType": "SINGLE_FAMILY",
    "rentZestimate": 2800,
    "taxAnnualAmount": 4200,
    "hoaFee": 150,
    "daysOnZillow": 12,
    "homeStatus": "FOR_SALE",
    "schoolRating": ["Queen Creek Elementary: 7.0/10", "Queen Creek High School: 6.0/10"],
    "priceHistory": [
        {"date": "2024-01-15", "price": 550000, "event": "Listed for sale"},
        {"date": "2022-05-20", "price": 480000, "event": "Sold"},
    ],
    "description": "Beautiful home with new roof and updated kitchen.",
    "url": "https://www.zillow.com/homedetails/19533-E-Timberline-Rd/12345678_zpid/",
}

SAMPLE_MACRO = {
    "risk_level": "LOW",
    "risk_rationale": "Queen Creek is a stable suburban market.",
    "key_findings": [
        "Crime index 120 (national avg 300)",
        "Median home price +8% YoY",
        "No rent control in Arizona"
    ],
    "crime_summary": "Crime index 120, well below national average.",
    "market_trend": "Prices up 8% YoY, strong demand.",
    "regulatory_risks": "No rent control. No pending legislation.",
    "infrastructure_risks": "FEMA Zone X. No EPA sites nearby.",
    "macro_signals": "Strong job growth, population +3% YoY.",
    "sources": ["https://neighborhoodscout.com", "https://zillow.com/research"],
    "red_flags": [],
    "green_signals": ["Below-average crime", "Strong price appreciation"],
}

SAMPLE_MICRO = {
    "verdict": {
        "kill_switch": False,
        "recommended_action": "PURSUE",
        "confidence": "HIGH",
        "one_line_summary": "Clean title, permitted reno, realistic rent — strong collateral."
    },
    "phase_results": {
        "phase1_ownership": {
            "owner_type": "Individual",
            "hold_duration_months": 36,
            "red_flags": [],
            "findings": "Owner John Smith since 2021. No liens found."
        },
        "phase2_permits": {
            "permits_found": True,
            "open_violations": False,
            "unpermitted_work_suspected": False,
            "findings": "Kitchen and roof permits pulled and finaled."
        },
        "phase3_crime": {
            "incidents_at_address": [],
            "sex_offenders_nearby": False,
            "findings": "No incidents at address."
        },
        "phase4_infrastructure": {
            "flood_zone": "X",
            "environmental_concerns": [],
            "findings": "FEMA Zone X. No EPA sites within 1mi."
        },
        "phase5_rent": {
            "rent_zestimate": 2800,
            "market_comparable_range": "2650-2950",
            "hud_fmr": 2400,
            "assessment": "REALISTIC",
            "findings": "Comps show $2700-2900 range. Zestimate realistic."
        },
        "phase6_regulatory": {
            "hoa_issues": False,
            "tax_reassessment_risk": False,
            "code_violations": False,
            "findings": "No HOA violations. No code enforcement actions."
        }
    },
    "top_risks": ["HOA rental restrictions not confirmed"],
    "top_strengths": ["All permits in order", "Clean ownership history"],
    "sources": ["https://maricopa.gov/permits", "https://mft.fema.gov"],
    "data_gaps": []
}

SAMPLE_MICRO_KILL = dict(SAMPLE_MICRO)
SAMPLE_MICRO_KILL["verdict"] = {
    "kill_switch": True,
    "recommended_action": "KILL",
    "confidence": "HIGH",
    "one_line_summary": "Active lis pendens and open code violations — do not lend."
}


# ── Tests: generate_report structure ─────────────────────────────────────────

def test_generate_report_returns_string():
    """generate_report 返回非空字符串"""
    from src.reporter import generate_report

    report = generate_report(SAMPLE_PROPERTY, SAMPLE_MACRO, SAMPLE_MICRO)
    assert isinstance(report, str)
    assert len(report) > 100


def test_report_contains_address():
    """报告包含房产地址"""
    from src.reporter import generate_report

    report = generate_report(SAMPLE_PROPERTY, SAMPLE_MACRO, SAMPLE_MICRO)
    assert "19533 E Timberline Rd" in report
    assert "Queen Creek" in report


def test_report_contains_risk_level():
    """报告包含宏观风险评级"""
    from src.reporter import generate_report

    report = generate_report(SAMPLE_PROPERTY, SAMPLE_MACRO, SAMPLE_MICRO)
    assert "LOW" in report


def test_report_contains_verdict():
    """报告包含 PURSUE 判决"""
    from src.reporter import generate_report

    report = generate_report(SAMPLE_PROPERTY, SAMPLE_MACRO, SAMPLE_MICRO)
    assert "PURSUE" in report


def test_report_kill_verdict():
    """KILL 判决正确显示"""
    from src.reporter import generate_report

    report = generate_report(SAMPLE_PROPERTY, SAMPLE_MACRO, SAMPLE_MICRO_KILL)
    assert "KILL" in report


def test_report_contains_all_6_phases():
    """报告包含 6 个调查阶段"""
    from src.reporter import generate_report

    report = generate_report(SAMPLE_PROPERTY, SAMPLE_MACRO, SAMPLE_MICRO)
    # 检查 Phase 1-6 都存在
    for i in range(1, 7):
        assert f"Phase {i}" in report or f"PHASE {i}" in report or f"phase{i}" in report.lower()


def test_report_contains_key_findings():
    """报告包含 Layer 1 的关键发现"""
    from src.reporter import generate_report

    report = generate_report(SAMPLE_PROPERTY, SAMPLE_MACRO, SAMPLE_MICRO)
    assert "Crime index 120" in report


def test_report_contains_disclaimer():
    """报告底部包含免责声明"""
    from src.reporter import generate_report

    report = generate_report(SAMPLE_PROPERTY, SAMPLE_MACRO, SAMPLE_MICRO)
    assert "informational purposes only" in report
    assert "PropertyPrism" in report


def test_report_is_markdown():
    """报告是有效的 Markdown（包含标题标记）"""
    from src.reporter import generate_report

    report = generate_report(SAMPLE_PROPERTY, SAMPLE_MACRO, SAMPLE_MICRO)
    assert "#" in report  # 至少有一个标题


def test_report_contains_financial_data():
    """报告包含价格和租金数据"""
    from src.reporter import generate_report

    report = generate_report(SAMPLE_PROPERTY, SAMPLE_MACRO, SAMPLE_MICRO)
    assert "550,000" in report or "550000" in report
    assert "2,800" in report or "2800" in report


def test_report_contains_top_risks():
    """报告包含 Top 风险列表"""
    from src.reporter import generate_report

    report = generate_report(SAMPLE_PROPERTY, SAMPLE_MACRO, SAMPLE_MICRO)
    assert "HOA rental restrictions" in report


def test_report_date_present():
    """报告包含生成日期"""
    from src.reporter import generate_report

    report = generate_report(SAMPLE_PROPERTY, SAMPLE_MACRO, SAMPLE_MICRO)
    today = date.today().strftime("%Y-%m-%d")
    assert today in report
