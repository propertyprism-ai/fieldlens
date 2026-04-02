"""
test_regression.py — 回归测试，验证已知输入产生正确输出格式
"""
import json
import pytest
from unittest.mock import patch


# ── Fixtures ──────────────────────────────────────────────────────────────────

KNOWN_PROPERTY = {
    "zpid": "99887766",
    "address": "123 Oak St, Indianapolis, IN, 46201",
    "price": 185000,
    "bedrooms": 3,
    "bathrooms": 2,
    "yearBuilt": 1978,
    "livingArea": 1450,
    "lotSize": 6000,
    "homeType": "SINGLE_FAMILY",
    "rentZestimate": 1400,
    "taxAnnualAmount": 2100,
    "hoaFee": 0,
    "daysOnZillow": 45,
    "homeStatus": "FOR_SALE",
    "schoolRating": ["IPS School 55: 3.0/10"],
    "priceHistory": [
        {"date": "2024-03-01", "price": 195000, "event": "Listed for sale"},
        {"date": "2024-04-15", "price": 185000, "event": "Price change"},
    ],
    "description": "Solid rental property, tenant occupied, income producing.",
    "url": "https://www.zillow.com/homedetails/123-Oak-St/99887766_zpid/",
}

KNOWN_MACRO = {
    "risk_level": "MODERATE",
    "risk_rationale": "Indianapolis has moderate crime and stable rental demand.",
    "key_findings": [
        "Crime index 450 — above national average",
        "Rental vacancy rate 6.5%",
        "No rent control in Indiana"
    ],
    "crime_summary": "Crime index 450, moderate violent crime.",
    "market_trend": "Flat prices, investor-driven market.",
    "regulatory_risks": "No rent control. Stable landlord laws.",
    "infrastructure_risks": "FEMA Zone X. No EPA superfund sites within 2mi.",
    "macro_signals": "Moderate employment, stable population.",
    "sources": ["https://neighborhoodscout.com"],
    "red_flags": ["Above-average crime index"],
    "green_signals": ["No rent control", "Stable rental demand"],
}

KNOWN_MICRO = {
    "verdict": {
        "kill_switch": False,
        "recommended_action": "CONDITIONAL_PURSUE",
        "confidence": "MEDIUM",
        "one_line_summary": "Viable cash flow play with moderate crime risk — verify tenant status."
    },
    "phase_results": {
        "phase1_ownership": {
            "owner_type": "Individual",
            "hold_duration_months": 24,
            "red_flags": [],
            "findings": "Individual owner, clean record."
        },
        "phase2_permits": {
            "permits_found": False,
            "open_violations": False,
            "unpermitted_work_suspected": False,
            "findings": "No permits found — property appears original condition."
        },
        "phase3_crime": {
            "incidents_at_address": [],
            "sex_offenders_nearby": False,
            "findings": "No incidents at address. Block-level crime moderate."
        },
        "phase4_infrastructure": {
            "flood_zone": "X",
            "environmental_concerns": [],
            "findings": "FEMA Zone X. No environmental concerns."
        },
        "phase5_rent": {
            "rent_zestimate": 1400,
            "market_comparable_range": "1250-1500",
            "hud_fmr": 1100,
            "assessment": "REALISTIC",
            "findings": "Market comps support $1350-1450 range."
        },
        "phase6_regulatory": {
            "hoa_issues": False,
            "tax_reassessment_risk": False,
            "code_violations": False,
            "findings": "No issues found."
        }
    },
    "top_risks": ["Moderate crime area", "School rating 3/10"],
    "top_strengths": ["Tenant occupied", "No HOA", "Realistic rent"],
    "sources": ["https://marion.gov/permits"],
    "data_gaps": ["Owner's permit history pre-2015 not available online"]
}


# ── Regression Tests ──────────────────────────────────────────────────────────

class TestEndToEndPipeline:
    """端到端回归：已知输入 → 检查输出格式和关键内容"""

    def test_reporter_output_structure(self):
        """generate_report 输出包含所有必要段落"""
        from src.reporter import generate_report

        report = generate_report(KNOWN_PROPERTY, KNOWN_MACRO, KNOWN_MICRO)

        # 封面
        assert "123 Oak St" in report
        assert "Indianapolis" in report

        # 宏观区域
        assert "MODERATE" in report

        # 微观判决
        assert "CONDITIONAL_PURSUE" in report

        # 免责声明
        assert "informational purposes only" in report

    def test_macro_risk_levels_covered(self):
        """所有 risk_level 值都能正确渲染"""
        from src.reporter import generate_report

        for level in ["LOW", "MODERATE", "HIGH", "CRITICAL"]:
            macro = dict(KNOWN_MACRO)
            macro["risk_level"] = level
            report = generate_report(KNOWN_PROPERTY, macro, KNOWN_MICRO)
            assert level in report

    def test_kill_vs_pursue_verdict(self):
        """KILL 和 PURSUE 判决渲染不同"""
        from src.reporter import generate_report

        # PURSUE
        pursue_report = generate_report(KNOWN_PROPERTY, KNOWN_MACRO, KNOWN_MICRO)

        # KILL
        kill_micro = dict(KNOWN_MICRO)
        kill_micro["verdict"] = {
            "kill_switch": True,
            "recommended_action": "KILL",
            "confidence": "HIGH",
            "one_line_summary": "Active lis pendens — do not lend."
        }
        kill_report = generate_report(KNOWN_PROPERTY, KNOWN_MACRO, kill_micro)

        assert "CONDITIONAL_PURSUE" in pursue_report
        assert "KILL" in kill_report
        assert pursue_report != kill_report

    def test_extract_core_fields_regression(self):
        """extract_core_fields 对已知输入产生已知输出"""
        from src.fetcher import extract_core_fields

        raw = {
            "zpid": "REG001",
            "address": {
                "streetAddress": "999 Regression Ave",
                "city": "Testville",
                "state": "TX",
                "zipcode": "77001"
            },
            "price": 300000,
            "bedrooms": 3,
            "bathrooms": 2,
            "yearBuilt": 2000,
            "taxHistory": [{"taxPaid": 6000, "year": 2023}],
            "rentZestimate": 2000,
            "restimateLowPercent": 10,
            "restimateHighPercent": 10,
            "resoFacts": {"hoaFee": None},
            "schools": [{"name": "Test School", "rating": 8}],
            "priceHistory": [{"date": "2024-01-01", "price": 300000, "event": "Listed"}],
            "description": "Test property.",
        }

        result = extract_core_fields(raw)

        assert result["zpid"] == "REG001"
        assert result["address"] == "999 Regression Ave, Testville, TX, 77001"
        assert result["price"] == 300000
        assert result["taxAnnualAmount"] == 6000.0
        assert result["rentZestimate"] == 2000
        assert result["rentMin"] == pytest.approx(1800.0, abs=1)
        assert result["rentMax"] == pytest.approx(2200.0, abs=1)
        assert result["hoaFee"] == 0
        assert result["schoolRating"] == ["Test School: 8.0/10"]


class TestInvestigatorParsing:
    """investigator JSON 解析回归测试"""

    def test_parse_json_response_various_formats(self):
        """_parse_json_response 处理多种 JSON 格式"""
        from src.investigator import _parse_json_response

        # 纯 JSON
        assert _parse_json_response('{"a": 1}') == {"a": 1}

        # json fence
        assert _parse_json_response('```json\n{"a": 1}\n```') == {"a": 1}

        # 普通 fence
        assert _parse_json_response('```\n{"a": 1}\n```') == {"a": 1}

        # 带前导文本
        result = _parse_json_response('Here is the result:\n{"a": 1}')
        assert result == {"a": 1}

    def test_investigate_macro_injects_address_parts(self):
        """investigate_macro 将地址拆分注入 prompt"""
        from src.investigator import investigate_macro

        macro_response = json.dumps({
            "risk_level": "LOW", "risk_rationale": "OK",
            "key_findings": ["F1", "F2", "F3"],
            "crime_summary": "Low", "market_trend": "Stable",
            "regulatory_risks": "None", "infrastructure_risks": "None",
            "macro_signals": "Good", "sources": [], "red_flags": [], "green_signals": []
        })

        captured = {}

        def capture(*args, **kwargs):
            captured["user"] = args[3] if len(args) > 3 else kwargs.get("user", "")
            return macro_response

        with patch("src.investigator.agentic_call", side_effect=capture):
            investigate_macro("456 Elm St, Dallas, TX, 75201")

        assert "Dallas" in captured["user"]
        assert "75201" in captured["user"]
