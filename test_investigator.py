"""
test_investigator.py — L1 单元测试，mock agentic_call
"""
import json
import pytest
from unittest.mock import patch, MagicMock


# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_PROPERTY = {
    "zpid": "12345678",
    "address": "19533 E Timberline Rd, Queen Creek, AZ, 85142",
    "price": 550000,
    "bedrooms": 4,
    "bathrooms": 3,
    "yearBuilt": 2018,
    "rentZestimate": 2800,
    "description": "Beautiful home with new roof.",
}

MACRO_JSON_RESPONSE = json.dumps({
    "risk_level": "LOW",
    "risk_rationale": "Queen Creek is a stable suburban market with below-average crime.",
    "key_findings": [
        "Crime index 120 (national avg 300) — well below average",
        "Median home price +8% YoY in 85142 zip",
        "No rent control in Arizona statewide"
    ],
    "crime_summary": "NeighborhoodScout crime index 120; violent crime rate 1.2/1000.",
    "market_trend": "Median $520K, DOM 18 days, prices up 8% YoY, low inventory.",
    "regulatory_risks": "No rent control in AZ. No pending legislation found.",
    "infrastructure_risks": "FEMA Zone X (minimal flood risk). No EPA sites within 2mi.",
    "macro_signals": "Strong job growth in East Valley metro. Population +3% YoY.",
    "sources": ["https://www.neighborhoodscout.com", "https://www.zillow.com/research"],
    "red_flags": [],
    "green_signals": ["Below-average crime", "Strong price appreciation", "No regulatory exposure"]
})

MICRO_JSON_RESPONSE = json.dumps({
    "verdict": {
        "kill_switch": False,
        "recommended_action": "PURSUE",
        "confidence": "HIGH",
        "one_line_summary": "Clean title, permitted renovation, realistic rent — strong collateral for HML at 70% LTV."
    },
    "phase_results": {
        "phase1_ownership": {
            "owner_type": "Individual",
            "hold_duration_months": 36,
            "red_flags": [],
            "findings": "Owner John Smith since 2021. No LLC, no lis pendens, no liens found."
        },
        "phase2_permits": {
            "permits_found": True,
            "open_violations": False,
            "unpermitted_work_suspected": False,
            "findings": "Kitchen remodel permit #2023-4521 pulled and finaled. Roof permit #2022-1102 finaled."
        },
        "phase3_crime": {
            "incidents_at_address": [],
            "sex_offenders_nearby": False,
            "findings": "No incidents at address. No sex offenders within 500ft."
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
            "findings": "Comps show $2700-2900 range. Zestimate of $2800 is realistic."
        },
        "phase6_regulatory": {
            "hoa_issues": False,
            "tax_reassessment_risk": False,
            "code_violations": False,
            "findings": "No HOA violations. Tax assessment stable. No code enforcement actions."
        }
    },
    "top_risks": [
        "HOA rental restrictions not confirmed",
        "HUD FMR $400 below market rent — Section 8 upside limited"
    ],
    "top_strengths": [
        "All permits in order",
        "Clean ownership history"
    ],
    "sources": ["https://maricopa.gov/permits", "https://mft.fema.gov"],
    "data_gaps": []
})


# ── Tests: investigate_macro ──────────────────────────────────────────────────

def test_investigate_macro_returns_dict():
    """investigate_macro 返回包含 risk_level 的 dict"""
    from src.investigator import investigate_macro

    with patch("src.investigator.agentic_call", return_value=MACRO_JSON_RESPONSE):
        result = investigate_macro("19533 E Timberline Rd, Queen Creek, AZ, 85142")

    assert isinstance(result, dict)
    assert result["risk_level"] == "LOW"
    assert "key_findings" in result
    assert len(result["key_findings"]) >= 2


def test_investigate_macro_prompt_contains_address():
    """investigate_macro 的 prompt 注入了地址信息"""
    from src.investigator import investigate_macro

    captured_kwargs = {}

    def capture_call(*args, **kwargs):
        captured_kwargs.update(kwargs)
        captured_kwargs["args"] = args
        return MACRO_JSON_RESPONSE

    with patch("src.investigator.agentic_call", side_effect=capture_call):
        investigate_macro("19533 E Timberline Rd, Queen Creek, AZ, 85142")

    # user prompt 应包含地址
    user_arg = captured_kwargs.get("args", (None,) * 4)[3] if len(captured_kwargs.get("args", [])) > 3 else ""
    assert "Queen Creek" in user_arg or "85142" in user_arg


def test_investigate_macro_handles_json_in_markdown_fence():
    """investigate_macro 能解析被 markdown fence 包裹的 JSON"""
    from src.investigator import investigate_macro

    wrapped = f"```json\n{MACRO_JSON_RESPONSE}\n```"

    with patch("src.investigator.agentic_call", return_value=wrapped):
        result = investigate_macro("123 Main St, Phoenix, AZ, 85001")

    assert result["risk_level"] == "LOW"


def test_investigate_macro_invalid_json_raises():
    """agentic_call 返回无效 JSON 时抛 ValueError"""
    from src.investigator import investigate_macro

    with patch("src.investigator.agentic_call", return_value="This is not JSON at all."):
        with pytest.raises(ValueError, match="Failed to parse"):
            investigate_macro("123 Main St, Phoenix, AZ, 85001")


# ── Tests: investigate_micro ──────────────────────────────────────────────────

def test_investigate_micro_returns_dict():
    """investigate_micro 返回包含 verdict 的 dict"""
    from src.investigator import investigate_micro

    macro_ctx = json.loads(MACRO_JSON_RESPONSE)

    with patch("src.investigator.agentic_call", return_value=MICRO_JSON_RESPONSE):
        result = investigate_micro(SAMPLE_PROPERTY, macro_ctx)

    assert isinstance(result, dict)
    assert "verdict" in result
    assert result["verdict"]["recommended_action"] == "PURSUE"
    assert result["verdict"]["kill_switch"] is False


def test_investigate_micro_prompt_contains_listing_json():
    """investigate_micro 的 prompt 注入了 listing JSON"""
    from src.investigator import investigate_micro

    captured_args = []

    def capture_call(*args, **kwargs):
        captured_args.extend(args)
        return MICRO_JSON_RESPONSE

    macro_ctx = json.loads(MACRO_JSON_RESPONSE)

    with patch("src.investigator.agentic_call", side_effect=capture_call):
        investigate_micro(SAMPLE_PROPERTY, macro_ctx)

    # user 参数（index 3）应包含 property 数据
    user_arg = captured_args[3] if len(captured_args) > 3 else ""
    assert "12345678" in user_arg or "550000" in user_arg


def test_investigate_micro_handles_markdown_fence():
    """investigate_micro 能解析 markdown fence 包裹的 JSON"""
    from src.investigator import investigate_micro

    wrapped = f"```json\n{MICRO_JSON_RESPONSE}\n```"
    macro_ctx = json.loads(MACRO_JSON_RESPONSE)

    with patch("src.investigator.agentic_call", return_value=wrapped):
        result = investigate_micro(SAMPLE_PROPERTY, macro_ctx)

    assert result["verdict"]["recommended_action"] == "PURSUE"


def test_investigate_micro_invalid_json_raises():
    """agentic_call 返回无效 JSON 时抛 ValueError"""
    from src.investigator import investigate_micro

    macro_ctx = json.loads(MACRO_JSON_RESPONSE)

    with patch("src.investigator.agentic_call", return_value="not json"):
        with pytest.raises(ValueError, match="Failed to parse"):
            investigate_micro(SAMPLE_PROPERTY, macro_ctx)


# ── Tests: _parse_json_response (helper) ──────────────────────────────────────

def test_parse_json_strips_fence():
    """_parse_json_response 去掉 ```json fence"""
    from src.investigator import _parse_json_response

    raw = '```json\n{"key": "value"}\n```'
    result = _parse_json_response(raw)
    assert result == {"key": "value"}


def test_parse_json_plain():
    """_parse_json_response 处理纯 JSON"""
    from src.investigator import _parse_json_response

    raw = '{"key": "value"}'
    result = _parse_json_response(raw)
    assert result == {"key": "value"}


def test_parse_json_raises_on_invalid():
    """_parse_json_response 无效输入抛 ValueError"""
    from src.investigator import _parse_json_response

    with pytest.raises(ValueError):
        _parse_json_response("not json")
