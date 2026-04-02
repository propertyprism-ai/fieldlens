"""test_anti_hallucination.py — v4 Anti-Hallucination 测试（9个L1 + 1个Smoke）"""
import pytest
from unittest.mock import patch, MagicMock
import requests


# ── 辅助函数 ────────────────────────────────────────────────────────────────

def _make_bundle(macro_sources=None, micro_sources=None):
    """构建最小 bundle 用于 verify_sources 测试。"""
    return {
        "macro": {"sources": macro_sources or []},
        "micro": {"sources": micro_sources or []},
    }


def _make_full_bundle(exec_summary="Property looks stable.", macro_sources=None, micro_sources=None):
    """构建完整 bundle 用于 report_writer 测试。"""
    return {
        "property_data": {
            "address": "123 Test St, Phoenix, AZ 85001",
            "price": 500000,
        },
        "macro": {
            "risk_level": "LOW",
            "key_findings": ["Market is stable"],
            "sources": macro_sources or [],
        },
        "micro": {
            "verdict": {
                "recommended_action": "PURSUE",
                "confidence": "HIGH",
                "kill_switch": False,
                "one_line_summary": exec_summary,
            },
            "sources": micro_sources or [],
        },
        "synthesis": None,
        "gov_data": None,
    }


# ── verify_sources — L1 单元测试 ────────────────────────────────────────────

def test_verify_sources_marks_alive_urls():
    """HTTP 200 → url_alive=True, verified=True（raw_quote 足够长）。"""
    from src.reporter import verify_sources

    bundle = _make_bundle(
        macro_sources=[{
            "url": "https://example.com",
            "raw_quote": "Sold for $500,000 on December 1 2025",
            "data_type": "sale_price",
        }]
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("requests.head", return_value=mock_resp):
        result = verify_sources(bundle)

    source = result["macro"]["sources"][0]
    assert source["url_alive"] is True
    assert source["verified"] is True


def test_verify_sources_marks_dead_urls():
    """HTTP 404 → url_alive=False, verified=False。"""
    from src.reporter import verify_sources

    bundle = _make_bundle(
        macro_sources=[{
            "url": "https://dead.example.com/404",
            "raw_quote": "Some valid quote from this page",
            "data_type": "crime_rate",
        }]
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    with patch("requests.head", return_value=mock_resp):
        result = verify_sources(bundle)

    source = result["macro"]["sources"][0]
    assert source["url_alive"] is False
    assert source["verified"] is False


def test_verify_sources_handles_timeout():
    """requests.Timeout → url_alive=False, 不崩溃。"""
    from src.reporter import verify_sources

    bundle = _make_bundle(
        macro_sources=[{
            "url": "https://slow.example.com",
            "raw_quote": "Valid quote text from this source",
            "data_type": "permit_status",
        }]
    )
    with patch("requests.head", side_effect=requests.Timeout):
        result = verify_sources(bundle)

    source = result["macro"]["sources"][0]
    assert source["url_alive"] is False
    assert source["verified"] is False


def test_verify_sources_skips_no_url():
    """source 无 url 字段 → 跳过，不崩溃，不调用 requests.head。"""
    from src.reporter import verify_sources

    bundle = _make_bundle(
        macro_sources=[{"note": "no url here", "raw_quote": "Some quote"}]
    )
    with patch("requests.head") as mock_head:
        result = verify_sources(bundle)

    mock_head.assert_not_called()
    # source 原样保留，不崩溃
    assert result["macro"]["sources"][0]["note"] == "no url here"


def test_source_verified_requires_raw_quote():
    """url_alive=True 但 raw_quote 为空 → verified=False。"""
    from src.reporter import verify_sources

    bundle = _make_bundle(
        macro_sources=[{"url": "https://example.com", "raw_quote": ""}]
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("requests.head", return_value=mock_resp):
        result = verify_sources(bundle)

    source = result["macro"]["sources"][0]
    assert source["url_alive"] is True
    assert source["verified"] is False  # raw_quote 为空，不能 verified


def test_source_verified_requires_min_length():
    """raw_quote 只有 3 个字符 → verified=False（要求 ≥10 字符）。"""
    from src.reporter import verify_sources

    bundle = _make_bundle(
        macro_sources=[{"url": "https://example.com", "raw_quote": "abc"}]
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("requests.head", return_value=mock_resp):
        result = verify_sources(bundle)

    source = result["macro"]["sources"][0]
    assert source["url_alive"] is True
    assert source["verified"] is False  # raw_quote < 10 字符


# ── report_writer — L1 单元测试 ─────────────────────────────────────────────

def test_report_writer_exec_summary_no_unverified():
    """Executive Summary 段落中不出现 ⚠️ UNVERIFIED 标注。"""
    from src.report_writer import write_report

    unverified_source = {
        "url": "https://dead.example.com",
        "raw_quote": "Price was $999,999 on record",
        "data_type": "sale_price",
        "url_alive": False,
        "verified": False,
    }
    bundle = _make_full_bundle(macro_sources=[unverified_source])
    report = write_report(bundle)

    # 找到 Executive Summary 段落
    lines = report.split("\n")
    in_exec = False
    exec_lines = []
    for line in lines:
        if line.startswith("## Executive Summary"):
            in_exec = True
        elif line.startswith("## ") and in_exec:
            break
        elif in_exec:
            exec_lines.append(line)

    exec_section = "\n".join(exec_lines)
    assert "⚠️ UNVERIFIED" not in exec_section


def test_report_writer_supporting_evidence_has_unverified_label():
    """verified=False 的 source 在 Supporting Evidence 中有 ⚠️ UNVERIFIED 标注。"""
    from src.report_writer import write_report

    unverified_source = {
        "url": "https://dead.example.com",
        "raw_quote": "Price was $999,999 on record",
        "data_type": "sale_price",
        "url_alive": False,
        "verified": False,
    }
    bundle = _make_full_bundle(macro_sources=[unverified_source])
    report = write_report(bundle)

    assert "⚠️ UNVERIFIED" in report


# ── investigator — L1 单元测试 ──────────────────────────────────────────────

def test_investigator_does_not_inject_anti_hallucination_rules():
    """
    v5 规范：investigator.py 不注入 anti_hallucination_rules
    （Prompt 分级：investigator 走短 prompt，anti_hallucination_rules 仅在 report_writer post-processing 阶段注入）
    """
    captured_prompts = []

    def mock_agentic(*args, **kwargs):
        captured_prompts.append(args[3])
        return '{"risk_level": "LOW", "key_findings": [], "sources": []}'

    with patch("src.investigator.agentic_call", side_effect=mock_agentic):
        from src.investigator import investigate_macro
        investigate_macro("123 Test St, Phoenix, AZ, 85001")

    assert len(captured_prompts) == 1
    # v5: investigator 不注入 anti_hallucination_rules
    assert "FACTUAL INTEGRITY RULES" not in captured_prompts[0]


# ── Smoke 测试（需 --run-smoke 显式启用）──────────────────────────────────────

@pytest.mark.smoke
def test_raw_json_sources_have_url_alive():
    """
    Smoke: verify_sources 对所有包含 url 的 source 设置 url_alive 字段（真实 HTTP HEAD）。
    使用稳定公开 URL 验证机制正确性。
    """
    from src.reporter import verify_sources

    bundle = {
        "macro": {
            "sources": [
                {
                    "url": "https://www.google.com",
                    "raw_quote": "Google search result page content",
                    "data_type": "general",
                },
            ]
        },
        "micro": {
            "sources": [
                {
                    "url": "https://hazards.fema.gov",
                    "raw_quote": "FEMA National Flood Hazard Layer portal",
                    "data_type": "fema_flood",
                },
            ]
        },
    }

    result = verify_sources(bundle)

    all_sources = (
        result["macro"].get("sources", [])
        + result["micro"].get("sources", [])
    )

    for source in all_sources:
        if isinstance(source, dict) and source.get("url"):
            assert "url_alive" in source, f"url_alive 字段缺失: {source}"
            assert "verified" in source, f"verified 字段缺失: {source}"
