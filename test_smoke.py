"""
test_smoke.py — 集成测试，真实 API 调用
标注 @pytest.mark.smoke，默认不运行（需 pytest -m smoke）
"""
import pytest
import os

pytestmark = pytest.mark.smoke

SMOKE_URL = "https://www.zillow.com/homedetails/19533-E-Timberline-Rd-Queen-Creek-AZ-85142/2071932938_zpid/"


@pytest.mark.smoke
def test_smoke_fetch_property():
    """smoke: fetch_property 真实调用 Apify，返回有效数据"""
    from src.fetcher import fetch_property

    api_token = os.environ.get("APIFY_API_TOKEN")
    if not api_token:
        pytest.skip("APIFY_API_TOKEN not set")

    result = fetch_property(SMOKE_URL)

    assert result is not None
    assert result.get("address") is not None
    assert result.get("price") is not None
    assert isinstance(result.get("price"), (int, float))
    print(f"\n[smoke] Fetched: {result['address']}, price=${result['price']:,}")


@pytest.mark.smoke
def test_smoke_investigate_macro():
    """smoke: investigate_macro 真实调用 Reflexion，含强制数据源注入，返回有效 JSON"""
    from src.investigator import investigate_macro
    from src.market_config import get_market_config

    address = "19533 E Timberline Rd, Queen Creek, AZ, 85142"
    market_config = get_market_config({"city": "Queen Creek", "state": "AZ"})

    assert market_config is not None, "market_config should resolve for Queen Creek, AZ"
    print(f"\n[smoke] Market: {market_config.get('market_name')}")

    result = investigate_macro(address, market_config=market_config, smoke_mode=True)

    assert isinstance(result, dict)
    assert result.get("risk_level") in ("LOW", "MODERATE", "HIGH", "CRITICAL")
    assert "key_findings" in result
    assert len(result["key_findings"]) >= 2
    print(f"[smoke] Macro risk_level: {result['risk_level']}")
    print(f"[smoke] Findings: {result['key_findings'][:2]}")


@pytest.mark.smoke
def test_smoke_investigate_micro():
    """smoke: investigate_micro 真实调用 Reflexion，返回有效 JSON"""
    from src.fetcher import fetch_property
    from src.investigator import investigate_macro, investigate_micro

    api_token = os.environ.get("APIFY_API_TOKEN")
    if not api_token:
        pytest.skip("APIFY_API_TOKEN not set")

    property_data = fetch_property(SMOKE_URL)
    macro = investigate_macro(property_data["address"], smoke_mode=True)
    micro = investigate_micro(property_data, macro, smoke_mode=True)

    assert isinstance(micro, dict)
    assert "verdict" in micro
    assert micro["verdict"]["recommended_action"] in ("KILL", "PURSUE", "CONDITIONAL_PURSUE")
    print(f"\n[smoke] Verdict: {micro['verdict']['recommended_action']}")
    print(f"[smoke] Summary: {micro['verdict']['one_line_summary']}")


@pytest.mark.smoke
def test_smoke_full_pipeline():
    """smoke: 全流程 — fetch → macro → micro → report，输出到 results/"""
    import os
    from pathlib import Path
    from src.fetcher import fetch_property
    from src.investigator import investigate_macro, investigate_micro
    from src.reporter import generate_report

    api_token = os.environ.get("APIFY_API_TOKEN")
    if not api_token:
        pytest.skip("APIFY_API_TOKEN not set")

    # Full pipeline
    property_data = fetch_property(SMOKE_URL)
    macro = investigate_macro(property_data["address"], smoke_mode=True)
    micro = investigate_micro(property_data, macro, smoke_mode=True)
    report = generate_report(property_data, macro, micro)

    # Validate report
    assert isinstance(report, str)
    assert len(report) > 200
    assert "informational purposes only" in report

    # Save report
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    from datetime import date
    zpid = property_data.get("zpid", "unknown")
    report_path = results_dir / f"{zpid}_{date.today().isoformat()}_smoke.md"
    report_path.write_text(report, encoding="utf-8")

    print(f"\n[smoke] Report saved: {report_path}")
    assert report_path.exists()
