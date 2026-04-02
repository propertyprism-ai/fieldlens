"""
test_synthesizer.py — L1 单元测试，mock llm_call，验证 synthesizer 各步骤
"""
import json
import pytest
from unittest.mock import patch


# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_PROPERTY = {
    "zpid": "12345678",
    "address": "19533 E Timberline Rd, Queen Creek, AZ, 85142",
    "price": 550000,
    "bedrooms": 4,
    "bathrooms": 3,
    "yearBuilt": 2018,
    "rentZestimate": 2800,
}

SAMPLE_MACRO = {
    "risk_level": "LOW",
    "key_findings": ["Crime index 120", "Prices up 8% YoY"],
    "data_confidence": 80,
    "unknowns": [],
}

SAMPLE_MICRO = {
    "verdict": {"recommended_action": "PURSUE", "confidence": "HIGH"},
    "phase_results": {
        "phase1_ownership": {
            "findings": "Clean title.",
            "cross_reference_note": "No interaction with other phases yet.",
        },
        "phase2_permits": {
            "findings": "All permits OK.",
            "cross_reference_note": "",
        },
    },
}

CROSS_RESPONSE = json.dumps({
    "cross_insights": [
        {
            "title": "20-Year Owner + No Permits = Hidden Capex Risk",
            "data_points": ["Phase1: 20yr owner", "Phase2: no renovation permits"],
            "reasoning": "Long hold with no permits suggests deferred maintenance.",
            "so_what": "Budget $15K-25K for roof/HVAC replacement.",
            "estimated_impact": "$15,000-$25,000",
            "severity": "HIGH",
        }
    ],
    "revised_risk_factors": ["Hidden capex"],
    "revised_verdict": {
        "action": "CONDITIONAL_PURSUE",
        "confidence": "MEDIUM",
        "conditions": ["Inspection required"],
    },
})

BLUE_RESPONSE = json.dumps({
    "bull_arguments": [
        "Strong rental market supports $2800/mo",
        "Clean title and all permits in order",
    ],
    "recommended_ltv": "70%",
    "exit_strategy": "Hold as rental",
})

RED_RESPONSE = json.dumps({
    "bear_arguments": [
        "20-year owner + no permits = deferred maintenance risk",
        "DOM indicates liquidity risk",
    ],
    "worst_case_loss": "$45,000 if forced sale in declining market",
    "unresolved_risks": ["Hidden structural issues"],
})

JUDGE_RESPONSE = json.dumps({
    "executive_summary": (
        "This is a borderline deal. Strong rental fundamentals are offset by deferred "
        "maintenance risk. Recommend conditional pursuit with inspection contingency."
    ),
    "final_action": "CONDITIONAL_PURSUE",
    "confidence": "MEDIUM",
    "winning_side": "SPLIT",
    "unresolved_risks": ["Roof condition unknown"],
    "conditions_to_pursue": ["Full inspection required", "Reserve for $20K capex"],
})


def _llm_resp(content_str: str) -> dict:
    return {"content": content_str, "tool_calls": None, "usage": {}}


# ── Tests: cross_reference ────────────────────────────────────────────────────

def test_cross_reference_returns_insights():
    """cross_reference 返回 cross_insights 列表，每项含必要字段"""
    from src.synthesizer import cross_reference

    with patch("src.synthesizer.llm_call", return_value=_llm_resp(CROSS_RESPONSE)):
        result = cross_reference(SAMPLE_PROPERTY, SAMPLE_MACRO, SAMPLE_MICRO)

    assert "cross_insights" in result
    assert isinstance(result["cross_insights"], list)
    assert len(result["cross_insights"]) >= 1

    insight = result["cross_insights"][0]
    for field in ["title", "data_points", "reasoning", "so_what", "estimated_impact", "severity"]:
        assert field in insight, f"Missing field: {field}"


def test_cross_reference_injects_all_three_layers():
    """cross_reference prompt 包含 property/macro/micro 三层数据"""
    from src.synthesizer import cross_reference

    captured = []

    def capture_call(*args, **kwargs):
        msgs = kwargs.get("messages", args[2] if len(args) > 2 else [])
        captured.extend(msgs)
        return _llm_resp(CROSS_RESPONSE)

    with patch("src.synthesizer.llm_call", side_effect=capture_call):
        cross_reference(SAMPLE_PROPERTY, SAMPLE_MACRO, SAMPLE_MICRO)

    all_text = " ".join(str(m) for m in captured)
    assert "12345678" in all_text or "550000" in all_text  # property data
    assert "LOW" in all_text or "Crime index" in all_text  # macro data
    assert "PURSUE" in all_text or "phase" in all_text.lower()  # micro data


# ── Tests: blue_team ──────────────────────────────────────────────────────────

def test_blue_team_returns_bull_case():
    """blue_team 返回含 bull_arguments 字段的 dict"""
    from src.synthesizer import blue_team

    cross = json.loads(CROSS_RESPONSE)
    with patch("src.synthesizer.llm_call", return_value=_llm_resp(BLUE_RESPONSE)):
        result = blue_team(SAMPLE_PROPERTY, SAMPLE_MACRO, SAMPLE_MICRO, cross)

    assert "bull_arguments" in result
    assert isinstance(result["bull_arguments"], list)
    assert len(result["bull_arguments"]) >= 1


# ── Tests: red_team ───────────────────────────────────────────────────────────

def test_red_team_receives_blue_team_output():
    """red_team prompt 注入了 blue_team 的输出内容"""
    from src.synthesizer import red_team

    captured = []

    def capture_call(*args, **kwargs):
        msgs = kwargs.get("messages", args[2] if len(args) > 2 else [])
        captured.extend(msgs)
        return _llm_resp(RED_RESPONSE)

    blue_result = json.loads(BLUE_RESPONSE)
    cross = json.loads(CROSS_RESPONSE)

    with patch("src.synthesizer.llm_call", side_effect=capture_call):
        red_team(SAMPLE_PROPERTY, SAMPLE_MACRO, SAMPLE_MICRO, cross, blue_result)

    all_text = " ".join(str(m) for m in captured)
    # blue_team output must appear in the prompt
    assert "bull_arguments" in all_text or "70%" in all_text or "Hold as rental" in all_text


# ── Tests: judge ──────────────────────────────────────────────────────────────

def test_judge_returns_executive_summary():
    """judge 返回含 executive_summary 的非空字符串"""
    from src.synthesizer import judge

    blue_result = json.loads(BLUE_RESPONSE)
    red_result = json.loads(RED_RESPONSE)
    cross = json.loads(CROSS_RESPONSE)

    with patch("src.synthesizer.llm_call", return_value=_llm_resp(JUDGE_RESPONSE)):
        result = judge(blue_result, red_result, cross)

    assert "executive_summary" in result
    assert isinstance(result["executive_summary"], str)
    assert len(result["executive_summary"]) > 0


def test_judge_returns_valid_action():
    """judge final_action 是 KILL/PURSUE/CONDITIONAL_PURSUE 之一"""
    from src.synthesizer import judge

    blue_result = json.loads(BLUE_RESPONSE)
    red_result = json.loads(RED_RESPONSE)
    cross = json.loads(CROSS_RESPONSE)

    with patch("src.synthesizer.llm_call", return_value=_llm_resp(JUDGE_RESPONSE)):
        result = judge(blue_result, red_result, cross)

    assert result["final_action"] in ("KILL", "PURSUE", "CONDITIONAL_PURSUE")


# ── Tests: synthesize (full pipeline) ─────────────────────────────────────────

def test_synthesize_full_pipeline():
    """synthesize() 串联 4 次 llm_call，返回完整结构"""
    from src.synthesizer import synthesize

    responses = [
        _llm_resp(CROSS_RESPONSE),
        _llm_resp(BLUE_RESPONSE),
        _llm_resp(RED_RESPONSE),
        _llm_resp(JUDGE_RESPONSE),
    ]

    with patch("src.synthesizer.llm_call", side_effect=responses):
        result = synthesize(SAMPLE_PROPERTY, SAMPLE_MACRO, SAMPLE_MICRO)

    assert "cross_insights" in result
    assert "blue_team" in result
    assert "red_team" in result
    assert "judge_verdict" in result

    jv = result["judge_verdict"]
    for field in ["executive_summary", "final_action", "confidence", "winning_side",
                  "unresolved_risks", "conditions_to_pursue"]:
        assert field in jv, f"judge_verdict missing field: {field}"
