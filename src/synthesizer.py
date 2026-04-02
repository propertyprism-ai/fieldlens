"""
src/synthesizer.py — Layer 3: Cross-Reference Synthesis + Adversarial Debate
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "/Users/lobster/.openclaw/workspace/skills/reflexion-ensemble")
from reflexion.providers import llm_call

from src.investigator import _parse_json_response

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")


def cross_reference(property_data: dict, macro: dict, micro: dict) -> dict:
    """
    Step 4a — Cross-Reference Engine.
    Finds causal connections across all 3 layers.

    Returns dict with cross_insights, revised_risk_factors, revised_verdict.
    """
    template = _load_prompt("layer3_cross_reference.txt")
    user_content = (
        template
        .replace("{{property_json}}", json.dumps(property_data, indent=2, ensure_ascii=False))
        .replace("{{macro_json}}", json.dumps(macro, indent=2, ensure_ascii=False))
        .replace("{{micro_json}}", json.dumps(micro, indent=2, ensure_ascii=False))
    )

    messages = [{"role": "user", "content": user_content}]
    response = llm_call(
        provider="openclaw",
        model="reflexion-sonnet",
        messages=messages,
        max_tokens=8000,
        timeout=600,
    )
    return _parse_json_response(response["content"])


def blue_team(property_data: dict, macro: dict, micro: dict, cross: dict) -> dict:
    """
    Step 4b — Blue Team (Bull Case).
    Builds the strongest case FOR the deal.

    Returns dict with bull_arguments, recommended_ltv, exit_strategy, etc.
    """
    template = _load_prompt("layer3_blue_team.txt")
    user_content = (
        template
        .replace("{{property_json}}", json.dumps(property_data, indent=2, ensure_ascii=False))
        .replace("{{macro_json}}", json.dumps(macro, indent=2, ensure_ascii=False))
        .replace("{{micro_json}}", json.dumps(micro, indent=2, ensure_ascii=False))
        .replace("{{cross_insights}}", json.dumps(cross, indent=2, ensure_ascii=False))
    )

    messages = [{"role": "user", "content": user_content}]
    response = llm_call(
        provider="moonshot",
        model="kimi-k2.5",
        messages=messages,
        max_tokens=8000,
        timeout=600,
    )
    return _parse_json_response(response["content"])


def red_team(property_data: dict, macro: dict, micro: dict, cross: dict, blue: dict) -> dict:
    """
    Step 4c — Red Team (Bear Case).
    Attacks Blue Team arguments and finds hidden risks.

    Returns dict with bear_arguments, worst_case_scenario, unresolved_risks, etc.
    """
    template = _load_prompt("layer3_red_team.txt")
    user_content = (
        template
        .replace("{{property_json}}", json.dumps(property_data, indent=2, ensure_ascii=False))
        .replace("{{macro_json}}", json.dumps(macro, indent=2, ensure_ascii=False))
        .replace("{{micro_json}}", json.dumps(micro, indent=2, ensure_ascii=False))
        .replace("{{cross_insights}}", json.dumps(cross, indent=2, ensure_ascii=False))
        .replace("{{blue_team}}", json.dumps(blue, indent=2, ensure_ascii=False))
    )

    messages = [{"role": "user", "content": user_content}]
    response = llm_call(
        provider="deepinfra",
        model="Qwen/Qwen3.5-122B-A10B",
        messages=messages,
        max_tokens=8000,
        timeout=600,
    )
    return _parse_json_response(response["content"])


def judge(blue: dict, red: dict, cross: dict) -> dict:
    """
    Step 4d — Judge (Investment Committee Chair).
    Evaluates the debate and renders final verdict.

    Returns dict with executive_summary, final_action, confidence, winning_side,
    unresolved_risks, conditions_to_pursue.
    """
    template = _load_prompt("layer3_judge.txt")
    user_content = (
        template
        .replace("{{cross_insights}}", json.dumps(cross, indent=2, ensure_ascii=False))
        .replace("{{blue_team}}", json.dumps(blue, indent=2, ensure_ascii=False))
        .replace("{{red_team}}", json.dumps(red, indent=2, ensure_ascii=False))
    )

    messages = [{"role": "user", "content": user_content}]
    response = llm_call(
        provider="openclaw",
        model="reflexion-opus",
        messages=messages,
        max_tokens=8000,
        timeout=600,
    )
    return _parse_json_response(response["content"])


def synthesize(property_data: dict, macro: dict, micro: dict, gov_data: dict | None = None) -> dict:
    """
    Layer 3 — Full synthesis pipeline (4 sequential llm_call steps).

    Returns:
        {
            "cross_insights": [...],
            "blue_team": {...},
            "red_team": {...},
            "judge_verdict": {
                "executive_summary": str,
                "final_action": "KILL|PURSUE|CONDITIONAL_PURSUE",
                "confidence": "HIGH|MEDIUM|LOW",
                "winning_side": "BLUE|RED|SPLIT",
                "unresolved_risks": [...],
                "conditions_to_pursue": [...]
            }
        }
    """
    # Step 1: Cross-reference synthesis
    cross_result = cross_reference(property_data, macro, micro)

    # Step 2: Blue Team (bull case)
    blue_result = blue_team(property_data, macro, micro, cross_result)

    # Step 3: Red Team (bear case) — receives blue team output
    red_result = red_team(property_data, macro, micro, cross_result, blue_result)

    # Step 4: Judge — renders final verdict
    judge_result = judge(blue_result, red_result, cross_result)

    return {
        "cross_insights": cross_result.get("cross_insights", []),
        "blue_team": blue_result,
        "red_team": red_result,
        "judge_verdict": {
            "executive_summary": judge_result.get("executive_summary", ""),
            "final_action": judge_result.get("final_action", "CONDITIONAL_PURSUE"),
            "confidence": judge_result.get("confidence", "LOW"),
            "winning_side": judge_result.get("winning_side", "SPLIT"),
            "unresolved_risks": judge_result.get("unresolved_risks", []),
            "conditions_to_pursue": judge_result.get("conditions_to_pursue", []),
        },
    }
