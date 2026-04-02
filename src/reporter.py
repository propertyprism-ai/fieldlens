"""
src/reporter.py — 素材包构建（v3：build_raw_bundle 输出 raw.json）
向后兼容：generate_report() 仍返回 Markdown 字符串（委托给 report_writer）
v4 新增：verify_sources() — HTTP HEAD 验证所有 sources 的 url_alive/verified 字段
"""
import requests
from datetime import date


def verify_sources(raw_bundle: dict) -> dict:
    """
    对 raw_bundle 中所有 sources 做 HTTP HEAD 检查，更新 url_alive/verified 字段。

    四级标注逻辑：
    - CONFIRMED: gov_data status == "SUCCESS"（已在 gov_fetcher 层标注，不在此处理）
    - VERIFIED:  raw_quote >= 10 chars AND url_alive == True
    - UNVERIFIED: raw_quote 缺失/过短 OR url_alive == False
    - NOT_FOUND: AI 明确输出 "NOT FOUND"（由 AI 自行标注）

    Args:
        raw_bundle: build_raw_bundle() 返回的素材包 dict（原地修改）

    Returns:
        更新后的 raw_bundle（同一对象）
    """
    def _verify_one(source) -> dict:
        if isinstance(source, str):
            # 旧格式：纯字符串 → 升级为 dict，无法做 HEAD 检查
            return {"url": source}

        if not source.get("url"):
            return source

        url = source["url"]
        try:
            resp = requests.head(url, timeout=5, allow_redirects=True)
            url_alive = resp.status_code < 400
        except Exception:
            url_alive = False

        source["url_alive"] = url_alive
        raw_quote = source.get("raw_quote") or ""
        source["verified"] = url_alive and len(raw_quote) >= 10
        return source

    if "macro" in raw_bundle:
        raw_bundle["macro"]["sources"] = [
            _verify_one(s) for s in raw_bundle["macro"].get("sources", [])
        ]

    if "micro" in raw_bundle:
        raw_bundle["micro"]["sources"] = [
            _verify_one(s) for s in raw_bundle["micro"].get("sources", [])
        ]

    return raw_bundle


def build_raw_bundle(
    property_data: dict,
    macro: dict,
    micro: dict,
    synthesis: dict = None,
    gov_data: dict = None,
) -> dict:
    """
    构建 raw.json 素材包（pipeline 输出格式）。

    Args:
        property_data: fetcher.extract_core_fields() 输出
        macro:         investigator.investigate_macro() 输出
        micro:         investigator.investigate_micro() 输出
        synthesis:     synthesizer.synthesize() 输出（可选）
        gov_data:      gov_fetcher.fetch_gov_sources() 输出（可选）

    Returns:
        raw.json 素材包 dict
    """
    return {
        "generated_at": date.today().strftime("%Y-%m-%d"),
        "property_data": property_data,
        "gov_data": gov_data,
        "macro": macro,
        "micro": micro,
        "synthesis": synthesis,
    }


def generate_report(
    property_data: dict,
    macro: dict,
    micro: dict,
    synthesis: dict = None,
    gov_data: dict = None,
) -> str:
    """
    生成 Markdown 风险调查报告（向后兼容包装器）。

    Args:
        property_data: fetcher.extract_core_fields() 输出
        macro:         investigator.investigate_macro() 输出
        micro:         investigator.investigate_micro() 输出
        synthesis:     synthesizer.synthesize() 输出（可选，v2 新增）
        gov_data:      gov_fetcher.fetch_gov_sources() 输出（可选，v3 新增）

    Returns:
        Markdown 格式报告字符串
    """
    from src.report_writer import write_report
    bundle = build_raw_bundle(property_data, macro, micro, synthesis, gov_data)
    return write_report(bundle)
