"""
test_reporter_v2.py — v2 报告模板渲染测试（Executive Summary 前置结构）
"""
import pytest


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
    "schoolRating": [],
    "priceHistory": [],
    "description": "Beautiful home.",
    "url": "https://www.zillow.com/homedetails/12345678_zpid/",
}

SAMPLE_MACRO = {
    "risk_level": "LOW",
    "risk_rationale": "Queen Creek is stable.",
    "key_findings": ["Crime index 120", "Prices up 8% YoY"],
    "crime_summary": "Crime index 120.",
    "market_trend": "Prices up 8% YoY.",
    "regulatory_risks": "No rent control.",
    "infrastructure_risks": "FEMA Zone X.",
    "macro_signals": "Strong job growth.",
    "sources": ["https://neighborhoodscout.com"],
    "red_flags": [],
    "green_signals": ["Low crime"],
    "data_confidence": 85,
    "unknowns": [],
}

SAMPLE_MICRO = {
    "verdict": {
        "kill_switch": False,
        "recommended_action": "PURSUE",
        "confidence": "HIGH",
        "one_line_summary": "Clean title, permitted reno, realistic rent.",
    },
    "phase_results": {
        "phase1_ownership": {
            "owner_type": "Individual",
            "hold_duration_months": 36,
            "red_flags": [],
            "findings": "Clean ownership.",
            "cross_reference_note": "",
        },
        "phase2_permits": {
            "permits_found": True,
            "open_violations": False,
            "unpermitted_work_suspected": False,
            "findings": "Permits OK.",
            "cross_reference_note": "",
        },
        "phase3_crime": {
            "incidents_at_address": [],
            "sex_offenders_nearby": False,
            "findings": "Clear.",
            "cross_reference_note": "",
        },
        "phase4_infrastructure": {
            "flood_zone": "X",
            "environmental_concerns": [],
            "findings": "Zone X.",
            "cross_reference_note": "",
        },
        "phase5_rent": {
            "rent_zestimate": 2800,
            "market_comparable_range": "2650-2950",
            "hud_fmr": 2400,
            "assessment": "REALISTIC",
            "findings": "Realistic.",
            "cross_reference_note": "",
        },
        "phase6_regulatory": {
            "hoa_issues": False,
            "tax_reassessment_risk": False,
            "code_violations": False,
            "findings": "Clean.",
            "cross_reference_note": "",
        },
    },
    "top_risks": ["HOA restrictions unconfirmed"],
    "top_strengths": ["All permits in order"],
    "sources": ["https://maricopa.gov"],
    "data_gaps": [],
}

SAMPLE_SYNTHESIS = {
    "cross_insights": [
        {
            "title": "Strong Rental Fundamentals",
            "data_points": ["Layer1: LOW risk", "Phase5: REALISTIC rent"],
            "reasoning": "Low crime + realistic rent = solid hold strategy.",
            "so_what": "Rental exit strategy is viable at current pricing.",
            "estimated_impact": "+$200/mo above HUD FMR",
            "severity": "LOW",
        },
        {
            "title": "Deferred Maintenance Exposure",
            "data_points": ["Phase1: 36mo hold", "Phase2: no recent permits"],
            "reasoning": "No permits suggest no major upgrades in 3 years.",
            "so_what": "Reserve $10K for deferred maintenance.",
            "estimated_impact": "$10,000",
            "severity": "MEDIUM",
        },
    ],
    "blue_team": {
        "bull_arguments": ["Strong rental demand", "Clean title"],
        "recommended_ltv": "70%",
        "exit_strategy": "Hold as rental",
    },
    "red_team": {
        "bear_arguments": ["Deferred maintenance", "HOA uncertainty"],
        "worst_case_loss": "$30,000",
        "unresolved_risks": ["HOA rental caps"],
    },
    "judge_verdict": {
        "executive_summary": (
            "This deal shows strong rental fundamentals with manageable risk. "
            "HOA restrictions must be confirmed before closing. "
            "Recommend conditional pursuit at 68% LTV with inspection contingency."
        ),
        "final_action": "CONDITIONAL_PURSUE",
        "confidence": "MEDIUM",
        "winning_side": "BLUE",
        "unresolved_risks": ["HOA rental caps"],
        "conditions_to_pursue": ["Confirm HOA allows rentals", "Full inspection"],
    },
}


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_report_v2_starts_with_executive_summary():
    """v2 报告第一个主 section 是 Executive Summary（早于 Key Insights）"""
    from src.reporter import generate_report

    report = generate_report(SAMPLE_PROPERTY, SAMPLE_MACRO, SAMPLE_MICRO, SAMPLE_SYNTHESIS)

    exec_pos = report.find("Executive Summary")
    insights_pos = report.find("Key Insights")
    assert exec_pos != -1, "Report must contain 'Executive Summary'"
    assert insights_pos != -1, "Report must contain 'Key Insights'"
    assert exec_pos < insights_pos, "Executive Summary must appear before Key Insights"


def test_report_v2_contains_key_insights():
    """v2 报告含 Key Insights section，含 ≥1 个洞察标题"""
    from src.reporter import generate_report

    report = generate_report(SAMPLE_PROPERTY, SAMPLE_MACRO, SAMPLE_MICRO, SAMPLE_SYNTHESIS)

    assert "Key Insights" in report
    # At least one insight title from SAMPLE_SYNTHESIS should appear
    assert "Strong Rental Fundamentals" in report or "Deferred Maintenance" in report


def test_report_v2_contains_bull_bear_debate():
    """v2 报告含 Bull Case 和 Bear Case"""
    from src.reporter import generate_report

    report = generate_report(SAMPLE_PROPERTY, SAMPLE_MACRO, SAMPLE_MICRO, SAMPLE_SYNTHESIS)

    assert "Bull Case" in report
    assert "Bear Case" in report


def test_report_v2_contains_judge_verdict():
    """v2 报告含 Committee Verdict section"""
    from src.reporter import generate_report

    report = generate_report(SAMPLE_PROPERTY, SAMPLE_MACRO, SAMPLE_MICRO, SAMPLE_SYNTHESIS)

    assert "Committee Verdict" in report


def test_report_v2_layer1_in_supporting_evidence():
    """v2 报告 Layer 1 Area Analysis 在 Supporting Evidence section 之后"""
    from src.reporter import generate_report

    report = generate_report(SAMPLE_PROPERTY, SAMPLE_MACRO, SAMPLE_MICRO, SAMPLE_SYNTHESIS)

    assert "Supporting Evidence" in report
    supporting_pos = report.find("Supporting Evidence")
    area_pos = report.find("Area Analysis")
    assert area_pos != -1, "Report must contain 'Area Analysis'"
    assert area_pos > supporting_pos, "Area Analysis must be inside Supporting Evidence section"


def test_report_v2_contains_disclaimer():
    """v2 报告底部有免责声明"""
    from src.reporter import generate_report

    report = generate_report(SAMPLE_PROPERTY, SAMPLE_MACRO, SAMPLE_MICRO, SAMPLE_SYNTHESIS)

    assert "informational purposes only" in report
    assert "PropertyPrism" in report
