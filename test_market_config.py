"""
test_market_config.py — L1 单元测试，get_market_config()
"""
import pytest
from unittest.mock import patch


# ── Tests: get_market_config ──────────────────────────────────────────────────

def test_get_market_config_by_county():
    """property_data 含 county='Maricopa County' → 返回 phoenix_maricopa 配置"""
    from src.market_config import get_market_config

    result = get_market_config({"county": "Maricopa County", "city": "Queen Creek", "state": "AZ"})
    assert result is not None
    assert result.get("market_name") is not None
    assert "Maricopa" in result["market_name"]


def test_get_market_config_by_city_queen_creek():
    """county 缺失，city='Queen Creek' → 返回 phoenix_maricopa"""
    from src.market_config import get_market_config

    result = get_market_config({"city": "Queen Creek", "state": "AZ"})
    assert result is not None
    assert "Maricopa" in result["market_name"]


def test_get_market_config_by_city_phoenix():
    """city='Phoenix' → 返回 phoenix_maricopa"""
    from src.market_config import get_market_config

    result = get_market_config({"city": "Phoenix", "state": "AZ"})
    assert result is not None
    assert "Maricopa" in result["market_name"]


def test_get_market_config_unknown_market():
    """city='Portland', state='OR' → 返回 None"""
    from src.market_config import get_market_config

    result = get_market_config({"city": "Portland", "state": "OR"})
    assert result is None


def test_get_market_config_none_input():
    """property_data={} → 返回 None，不崩溃"""
    from src.market_config import get_market_config

    result = get_market_config({})
    assert result is None


def test_market_config_contains_required_keys():
    """返回 dict 含 assessor/recorder/fema_flood/data_chain 字段"""
    from src.market_config import get_market_config

    result = get_market_config({"county": "Maricopa County"})
    assert result is not None
    sources = result.get("sources", {})
    assert "assessor" in sources
    assert "recorder" in sources
    assert "fema_flood" in sources
    assert "data_chain" in result
    assert len(result["data_chain"]) >= 3


# ── Tests: investigator.py market_config injection ────────────────────────────

MACRO_JSON_RESPONSE = """{
    "risk_level": "LOW",
    "key_findings": ["stable market"],
    "crime_summary": "low crime",
    "market_trend": "rising",
    "regulatory_risks": "none",
    "infrastructure_risks": "none",
    "sources": []
}"""

MICRO_JSON_RESPONSE = """{
    "verdict": {"kill_switch": false, "recommended_action": "PURSUE"},
    "phase_results": {}
}"""

SAMPLE_GOV_DATA = {
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
}


def test_investigator_macro_injects_gov_data():
    """传入 gov_data → user prompt 含 'PRE-FETCHED GOVERNMENT DATA' 和 confirmed 数据"""
    from src.investigator import investigate_macro

    captured_args = []

    def capture_call(*args, **kwargs):
        captured_args.extend(args)
        return MACRO_JSON_RESPONSE

    with patch("src.investigator.agentic_call", side_effect=capture_call):
        investigate_macro(
            "21145 E Saddle Way, Queen Creek, AZ, 85142",
            gov_data=SAMPLE_GOV_DATA,
        )

    user_arg = captured_args[3] if len(captured_args) > 3 else ""
    assert "PRE-FETCHED GOVERNMENT DATA" in user_arg
    assert "SMITH JOHN A" in user_arg or "Zone X" in user_arg or "50330033" in user_arg


def test_investigator_macro_without_gov_data():
    """gov_data=None → prompt 不含 PRE-FETCHED，行为与 v1 一致"""
    from src.investigator import investigate_macro

    captured_args = []

    def capture_call(*args, **kwargs):
        captured_args.extend(args)
        return MACRO_JSON_RESPONSE

    with patch("src.investigator.agentic_call", side_effect=capture_call):
        investigate_macro("123 Main St, Phoenix, AZ, 85001")

    user_arg = captured_args[3] if len(captured_args) > 3 else ""
    assert "PRE-FETCHED GOVERNMENT DATA" not in user_arg


def test_investigator_micro_injects_gov_data():
    """传入 gov_data → user prompt 含 PRE-FETCHED 和 confirmed 字段"""
    from src.investigator import investigate_micro

    captured_args = []

    def capture_call(*args, **kwargs):
        captured_args.extend(args)
        return MICRO_JSON_RESPONSE

    sample_property = {"zpid": "123", "address": "21145 E Saddle Way, Queen Creek, AZ, 85142"}
    macro_ctx = {"risk_level": "LOW", "key_findings": []}

    with patch("src.investigator.agentic_call", side_effect=capture_call):
        investigate_micro(sample_property, macro_ctx, gov_data=SAMPLE_GOV_DATA)

    user_arg = captured_args[3] if len(captured_args) > 3 else ""
    assert "PRE-FETCHED GOVERNMENT DATA" in user_arg
    assert "SMITH JOHN A" in user_arg
