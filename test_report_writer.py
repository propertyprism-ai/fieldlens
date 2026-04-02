"""
test_report_writer.py — L1 单元测试，report_writer.py
"""
import json
import tempfile
import os
from unittest.mock import patch


SAMPLE_RAW_BUNDLE = {
    "generated_at": "2026-04-01",
    "property_data": {
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
    },
    "gov_data": {
        "fema": {
            "status": "SUCCESS",
            "flood_zone": "X",
            "in_sfha": False,
            "source": "FEMA NFHL ArcGIS REST API",
        },
        "assessor": {
            "status": "SUCCESS",
            "owner": "SMITH JOHN A",
            "parcel_number": "50330033",
            "assessed_value": 385000,
            "source": "Maricopa County Assessor GIS API",
        },
        "treasurer": {"status": "SKIPPED_DEPENDENCY"},
        "recorder": {"status": "NOT_CONFIGURED"},
    },
    "macro": {
        "risk_level": "LOW",
        "risk_rationale": "Stable suburban market.",
        "key_findings": ["Crime index 120", "Prices up 8% YoY"],
        "crime_summary": "Low crime.",
        "market_trend": "Rising.",
        "regulatory_risks": "No rent control.",
        "infrastructure_risks": "FEMA Zone X.",
        "macro_signals": "Strong growth.",
        "sources": ["https://neighborhoodscout.com"],
        "red_flags": [],
        "green_signals": ["Low crime"],
        "data_confidence": 90,
        "unknowns": [],
    },
    "micro": {
        "verdict": {
            "kill_switch": False,
            "recommended_action": "PURSUE",
            "confidence": "HIGH",
            "one_line_summary": "Clean title, permitted reno, realistic rent.",
        },
        "phase_results": {
            "phase1_ownership": {"findings": "Clean ownership.", "red_flags": [], "cross_reference_note": ""},
            "phase2_permits": {"findings": "Permits OK.", "red_flags": [], "cross_reference_note": ""},
            "phase3_crime": {"findings": "Clear.", "red_flags": [], "cross_reference_note": ""},
            "phase4_infrastructure": {"findings": "Zone X.", "red_flags": [], "cross_reference_note": ""},
            "phase5_rent": {"findings": "Realistic.", "red_flags": [], "cross_reference_note": ""},
            "phase6_regulatory": {"findings": "Clean.", "red_flags": [], "cross_reference_note": ""},
        },
        "top_risks": [],
        "top_strengths": [],
        "sources": [],
        "data_gaps": [],
    },
    "synthesis": {
        "cross_insights": [{
            "title": "Strong Rental Fundamentals",
            "data_points": ["Low risk", "Realistic rent"],
            "reasoning": "Good hold strategy.",
            "so_what": "Viable rental exit.",
            "estimated_impact": "+$200/mo",
            "severity": "LOW",
        }],
        "blue_team": {
            "bull_arguments": ["Clean title", "Good location"],
            "recommended_ltv": "70%",
            "exit_strategy": "Hold as rental",
        },
        "red_team": {
            "bear_arguments": ["Market uncertainty"],
            "worst_case_scenario": "$20K loss",
        },
        "judge_verdict": {
            "executive_summary": "Strong deal with clean fundamentals. Recommend pursuing at 70% LTV.",
            "final_action": "PURSUE",
            "confidence": "HIGH",
            "winning_side": "BLUE",
            "unresolved_risks": [],
            "conditions_to_pursue": [],
        },
    },
}


def test_write_report_contains_executive_summary():
    """write_report 输出含 Executive Summary section"""
    from src.report_writer import write_report

    report = write_report(SAMPLE_RAW_BUNDLE)
    assert isinstance(report, str)
    assert "Executive Summary" in report


def test_write_report_confirmed_data_labeled():
    """报告中 gov_data CONFIRMED 数据有 CONFIRMED 标注"""
    from src.report_writer import write_report

    report = write_report(SAMPLE_RAW_BUNDLE)
    assert "CONFIRMED" in report


def test_write_report_contains_disclaimer_legal():
    """报告底部有完整法律 disclaimer，含 PropertyPrism 和 informational purposes"""
    from src.report_writer import write_report

    report = write_report(SAMPLE_RAW_BUNDLE)
    assert "informational purposes only" in report
    assert "PropertyPrism" in report


def test_write_report_from_raw_json():
    """write_report_from_file 从 raw.json 路径读取并生成报告"""
    from src.report_writer import write_report_from_file

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(SAMPLE_RAW_BUNDLE, f)
        tmp_path = f.name

    try:
        report = write_report_from_file(tmp_path)
        assert "Executive Summary" in report
        assert isinstance(report, str)
    finally:
        os.unlink(tmp_path)


def test_write_report_zh_returns_chinese():
    """write_report_zh mock llm_call → 返回含中文字符的字符串"""
    from src.report_writer import write_report_zh

    mock_response = {
        "content": "执行摘要：这是一份中文速览版报告。风险：低。建议：追求。",
        "tool_calls": None,
        "usage": {},
    }

    with patch("src.report_writer.llm_call", return_value=mock_response):
        result = write_report_zh(SAMPLE_RAW_BUNDLE)

    assert isinstance(result, str)
    has_chinese = any("\u4e00" <= ch <= "\u9fff" for ch in result)
    assert has_chinese, f"Expected Chinese characters in: {result[:100]}"
