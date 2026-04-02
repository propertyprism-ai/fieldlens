"""
src/investigator.py — Reflexion agentic_call 封装，Layer 1 & Layer 2 调查
"""
import json
import logging
import re
import sys
import time as _time
from pathlib import Path

sys.path.insert(0, "/Users/lobster/.openclaw/workspace/skills/reflexion-ensemble")
from reflexion.agentic import agentic_call

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
logger = logging.getLogger(__name__)


def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _parse_json_response(raw: str) -> dict:
    """
    解析 agentic_call 返回的 JSON 字符串。
    支持 markdown fence 包裹（```json ... ```）。
    支持多层嵌套 JSON，自动找最外层完整对象。
    失败时抛 ValueError。
    """
    text = raw.strip()

    # 策略1：去掉 markdown fence（支持单层和多层嵌套）
    fence = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()

    # 策略2：直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 策略3：从文本中提取第一个 "{" 到最后一个 "}" 的完整 JSON
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate = text[first_brace:last_brace + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # 策略4：找所有 markdown fence 中的内容，优先用最后一个（有时代理最后输出）
    fences = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", raw, re.DOTALL)
    for fence_content in reversed(fences):
        fence_content = fence_content.strip()
        try:
            return json.loads(fence_content)
        except json.JSONDecodeError:
            continue

    # 策略5：尝试修复截断的 JSON（在末尾补 "}" 直到解析成功）
    if first_brace != -1:
        candidate = text[first_brace:]
        for _ in range(100):  # 最多补100个 }
            candidate += "}"
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

    raise ValueError(f"Failed to parse JSON from agentic_call response: {raw[:300]}")


def _build_gov_data_inject(gov_data: dict, address: str = "") -> str:
    """从 gov_data dict 构建 PRE-FETCHED GOVERNMENT DATA 注入段。"""
    lines = []

    fema = gov_data.get("fema", {})
    if fema.get("status") == "SUCCESS":
        sfha_str = "YES ⚠️ MANDATORY FLOOD INSURANCE" if fema.get("in_sfha") else "NO ✅"
        lines.append(
            f"FEMA FLOOD ZONE: {fema.get('flood_zone', 'UNKNOWN')} "
            f"| In SFHA: {sfha_str} ✅ CONFIRMED"
        )
    elif fema.get("status") == "FAILED":
        lines.append(f"FEMA FLOOD ZONE: UNAVAILABLE — {fema.get('error', 'query failed')}")

    assessor = gov_data.get("assessor", {})
    if assessor.get("status") == "SUCCESS":
        owner = assessor.get("owner", "UNKNOWN")
        parcel = assessor.get("parcel_number", "UNKNOWN")
        assessed = assessor.get("assessed_value")
        assessed_str = f"${assessed:,}" if isinstance(assessed, (int, float)) else "N/A"
        lines.append(
            f"COUNTY ASSESSOR: Owner={owner}, Parcel={parcel}, "
            f"Assessed={assessed_str} ✅ CONFIRMED"
        )
    elif assessor.get("status") == "NOT_CONFIGURED":
        lines.append("COUNTY ASSESSOR: NOT CONFIGURED for this market")

    treasurer = gov_data.get("treasurer", {})
    if treasurer.get("status") == "SUCCESS":
        tax_status = treasurer.get("tax_status", "UNKNOWN")
        lines.append(f"COUNTY TREASURER: Tax Status={tax_status} ✅ CONFIRMED")
    elif treasurer.get("status") in ("SKIPPED_DEPENDENCY", "NEEDS_TESTING"):
        lines.append("COUNTY TREASURER: NOT AVAILABLE (depends on Assessor parcel number)")

    recorder = gov_data.get("recorder", {})
    if recorder.get("status") in ("NOT_CONFIGURED", None):
        lines.append(
            "COUNTY RECORDER: NOT CONFIGURED via API — "
            "use search tools / jina_read for deed/lien data ⚠️ PARTIAL"
        )

    gov_data_section = "\n".join(lines) if lines else "No government data pre-fetched."

    owner_for_search = (
        assessor.get("owner", "the property owner")
        if assessor.get("status") == "SUCCESS"
        else "the property owner"
    )

    template = _load_prompt("gov_data_inject.txt")
    return (
        template
        .replace("{{gov_data_section}}", gov_data_section)
        .replace("{{owner_for_search}}", owner_for_search)
    )


def _call_agentic_with_retry(
    system_prompt: str,
    user_prompt: str,
    max_rounds: int,
    timeout: int,
    layer_name: str,
) -> dict:
    """
    调用 agentic_call + _parse_json_response，失败自动重试最多3次，间隔10s。
    每次失败打 WARNING log。
    3次全失败才 raise ValueError。
    """
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            raw = agentic_call(
                "openclaw",
                "reflexion-sonnet",
                system_prompt,
                user_prompt,
                max_rounds=max_rounds,
                timeout=timeout,
            )
            return _parse_json_response(raw)
        except ValueError as e:
            if attempt == max_retries:
                logger.error("[%s] All %d attempts failed", layer_name, max_retries)
                raise
            logger.warning(
                "%s 失败（attempt %d/%d），10s 后重试...",
                layer_name,
                attempt,
                max_retries,
            )
            _time.sleep(10)


def investigate_macro(
    address: str,
    gov_data: dict | None = None,
    market_config: dict | None = None,  # deprecated, ignored in v3
    smoke_mode: bool = False,
) -> dict:
    """
    Layer 1 — 宏观区域扫描。

    Args:
        address:       完整地址字符串（如 "19533 E Timberline Rd, Queen Creek, AZ, 85142"）
        gov_data:      gov_fetcher.fetch_gov_sources() 结果，None 时不注入政府数据
        market_config: 已废弃（v3 用 gov_data 替代），保留参数避免调用方 TypeError
        smoke_mode:    True 时 max_rounds=3（快速验证结构）

    Returns:
        解析后的区域风险 dict（含 risk_level 字段）

    Raises:
        ValueError: agentic_call 返回无效 JSON
    """
    parts = [p.strip() for p in address.split(",")]
    street = parts[0] if len(parts) > 0 else address
    city = parts[1] if len(parts) > 1 else ""
    state = parts[2] if len(parts) > 2 else ""
    zipcode = parts[3] if len(parts) > 3 else ""

    template = _load_prompt("layer1_macro.txt")
    user_prompt = (
        template
        .replace("{{address}}", address)
        .replace("{{city}}", city)
        .replace("{{zip}}", zipcode)
        .replace("{{state}}", state)
    )

    if gov_data is not None:
        inject_section = _build_gov_data_inject(gov_data, address)
        user_prompt = user_prompt + "\n\n" + inject_section
        logger.info("Layer 1: gov_data injected (FEMA=%s, Assessor=%s)",
                    gov_data.get("fema", {}).get("status"),
                    gov_data.get("assessor", {}).get("status"))

    # anti_hallucination rules NOT injected here — too long for agentic_call

    system_prompt = (
        "You are a senior real estate risk analyst for a hard money lender. "
        "Execute the investigation mandate and return only valid JSON."
    )

    if smoke_mode:
        max_rounds = 3
    elif gov_data is not None:
        max_rounds = 6
    else:
        max_rounds = 6

    result = _call_agentic_with_retry(
        system_prompt, user_prompt, max_rounds, 600, "Layer 1"
    )

    result.setdefault("data_confidence", None)
    result.setdefault("unknowns", [])
    return result


def investigate_micro(
    property_data: dict,
    macro_context: dict,
    gov_data: dict | None = None,
    market_config: dict | None = None,  # deprecated, ignored in v3
    smoke_mode: bool = False,
) -> dict:
    """
    Layer 2 — 微观房产法证。

    Args:
        property_data: extract_core_fields() 返回的清洗后房源 dict
        macro_context: investigate_macro() 返回的区域风险 dict
        gov_data:      gov_fetcher.fetch_gov_sources() 结果，None 时不注入政府数据
        market_config: 已废弃（v3 用 gov_data 替代），保留参数避免调用方 TypeError
        smoke_mode:    True 时 max_rounds=3（快速验证结构）

    Returns:
        解析后的房产法证 dict（含 verdict 字段）

    Raises:
        ValueError: agentic_call 返回无效 JSON
    """
    listing_json = json.dumps(property_data, indent=2, ensure_ascii=False)
    macro_summary = json.dumps(macro_context, indent=2, ensure_ascii=False)

    template = _load_prompt("layer2_micro.txt")
    user_prompt = (
        template
        .replace("{{listing_json}}", listing_json)
        .replace("{{macro_context}}", macro_summary)
    )

    if gov_data is not None:
        address = property_data.get("address", "")
        inject_section = _build_gov_data_inject(gov_data, address)
        user_prompt = user_prompt + "\n\n" + inject_section
        logger.info("Layer 2: gov_data injected (FEMA=%s, Assessor=%s)",
                    gov_data.get("fema", {}).get("status"),
                    gov_data.get("assessor", {}).get("status"))

    # anti_hallucination rules NOT injected here — too long for agentic_call

    system_prompt = (
        "You are a senior forensic analyst for a hard money lender. "
        "Execute all 6 investigation phases and return only valid JSON."
    )

    if smoke_mode:
        max_rounds = 3
    elif gov_data is not None:
        max_rounds = 6
    else:
        max_rounds = 6

    result = _call_agentic_with_retry(
        system_prompt, user_prompt, max_rounds, 600, "Layer 2"
    )
    phase_results = result.get("phase_results", {})
    for phase_key in phase_results:
        phase_results[phase_key].setdefault("cross_reference_note", "")

    # v6: ensure borrower_risk_profile is present in phase1_ownership
    phase1 = phase_results.get("phase1_ownership", {})
    if "borrower_risk_profile" not in phase1:
        phase1["borrower_risk_profile"] = {
            "is_professional_investor": False,
            "evidence": "No social/professional profile found",
            "estimated_properties_held": 0,
            "properties_found": [],
            "llc_found": False,
            "llc_names": [],
            "litigation_signals": [],
            "cross_lender_exposure": "UNKNOWN",
            "cross_lender_note": "Maricopa Recorder inaccessible (Cloudflare); cross-lender debt unknown.",
            "borrower_risk_level": "UNKNOWN",
            "borrower_risk_summary": "Insufficient data to assess borrower risk.",
        }
        phase_results["phase1_ownership"] = phase1

    return result
