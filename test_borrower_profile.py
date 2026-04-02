"""
test_borrower_profile.py — L1 单元测试，v6 Borrower Profile
TDD: 先写测试（红灯）→ 实现（绿灯）
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
    "city": "Queen Creek",
    "state": "AZ",
}

MACRO_JSON = {
    "risk_level": "LOW",
    "risk_rationale": "Stable suburban market.",
    "key_findings": [],
    "sources": [],
}

MICRO_WITHOUT_BORROWER_PROFILE = {
    "verdict": {
        "kill_switch": False,
        "recommended_action": "PURSUE",
        "confidence": "HIGH",
    },
    "phase_results": {
        "phase1_ownership": {
            "owner_type": "Individual",
            "hold_duration_months": 36,
            "red_flags": [],
            "findings": "Owner John Smith since 2021. No LLC found.",
        },
        "phase2_permits": {"permits_found": True},
        "phase3_crime": {"incidents_at_address": []},
        "phase4_infrastructure": {"flood_zone": "X"},
        "phase5_rent": {"rent_zestimate": 2800},
        "phase6_regulatory": {},
    },
}

MICRO_WITH_BORROWER_PROFILE = {
    "verdict": {
        "kill_switch": False,
        "recommended_action": "PURSUE",
        "confidence": "HIGH",
    },
    "phase_results": {
        "phase1_ownership": {
            "owner_type": "Individual",
            "hold_duration_months": 36,
            "red_flags": [],
            "findings": "Owner John Smith since 2021.",
            "borrower_risk_profile": {
                "is_professional_investor": True,
                "evidence": "Active BiggerPockets member with 12 current flips.",
                "estimated_properties_held": 8,
                "properties_found": [
                    "19533 E Timberline Rd",
                    "20144 E Via de Parque",
                ],
                "llc_found": True,
                "llc_names": ["JS Investment Holdings LLC"],
                "litigation_signals": [],
                "cross_lender_exposure": "ESTIMATED($1.2M)",
                "cross_lender_note": "Based on social media posts.",
                "borrower_risk_level": "MEDIUM",
                "borrower_risk_summary": "Active flipper with multiple concurrent HML loans.",
            },
        },
        "phase2_permits": {"permits_found": True},
        "phase3_crime": {"incidents_at_address": []},
        "phase4_infrastructure": {"flood_zone": "X"},
        "phase5_rent": {"rent_zestimate": 2800},
        "phase6_regulatory": {},
    },
}


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_borrower_profile_fields_present():
    """mock investigate_micro 返回无 borrower_risk_profile 的 dict，验证 investigator.py 补充了默认结构"""
    from src.investigator import investigate_micro

    mock_agentic = MagicMock(return_value=json.dumps(MICRO_WITHOUT_BORROWER_PROFILE))

    with patch("src.investigator.agentic_call", mock_agentic):
        result = investigate_micro(SAMPLE_PROPERTY, MACRO_JSON, gov_data=None)

    phase1 = result.get("phase_results", {}).get("phase1_ownership", {})
    assert "borrower_risk_profile" in phase1, \
        "investigate_micro must add borrower_risk_profile if missing"


def test_borrower_profile_not_null():
    """验证 is_professional_investor/estimated_properties_held/borrower_risk_level 不为 None"""
    from src.investigator import investigate_micro

    mock_agentic = MagicMock(return_value=json.dumps(MICRO_WITHOUT_BORROWER_PROFILE))

    with patch("src.investigator.agentic_call", mock_agentic):
        result = investigate_micro(SAMPLE_PROPERTY, MACRO_JSON, gov_data=None)

    brp = result["phase_results"]["phase1_ownership"]["borrower_risk_profile"]
    assert brp.get("is_professional_investor") is not None
    assert brp.get("estimated_properties_held") is not None
    assert brp.get("borrower_risk_level") is not None


def test_borrower_profile_default_values():
    """缺失时默认：is_professional_investor=False, estimated_properties_held=0, borrower_risk_level='UNKNOWN'"""
    from src.investigator import investigate_micro

    mock_agentic = MagicMock(return_value=json.dumps(MICRO_WITHOUT_BORROWER_PROFILE))

    with patch("src.investigator.agentic_call", mock_agentic):
        result = investigate_micro(SAMPLE_PROPERTY, MACRO_JSON, gov_data=None)

    brp = result["phase_results"]["phase1_ownership"]["borrower_risk_profile"]
    assert brp["is_professional_investor"] is False
    assert brp["estimated_properties_held"] == 0
    assert brp["borrower_risk_level"] == "UNKNOWN"


def test_gov_data_inject_contains_borrower_steps():
    """验证 gov_data_inject.txt 含 'BORROWER PORTFOLIO RISK' 和 'AZCourts' 关键字"""
    from src.investigator import _build_gov_data_inject

    gov_data = {
        "fema": {"status": "SUCCESS", "flood_zone": "X", "in_sfha": False},
        "assessor": {"status": "SUCCESS", "owner": "John Smith", "parcel_number": "12345"},
    }
    inject = _build_gov_data_inject(gov_data, "19533 E Timberline Rd")

    assert "BORROWER PORTFOLIO RISK" in inject, \
        "gov_data_inject must contain BORROWER PORTFOLIO RISK section"
    assert "AZCourts" in inject, \
        "gov_data_inject must contain AZCourts search instruction"


def test_recorder_explicitly_forbidden():
    """验证 prompt 含 'Maricopa Recorder inaccessible (Cloudflare)' 字样"""
    from src.investigator import _build_gov_data_inject

    gov_data = {
        "fema": {"status": "SUCCESS", "flood_zone": "X", "in_sfha": False},
        "assessor": {"status": "SUCCESS", "owner": "John Smith", "parcel_number": "12345"},
    }
    inject = _build_gov_data_inject(gov_data, "19533 E Timberline Rd")

    assert "Maricopa Recorder inaccessible (Cloudflare)" in inject, \
        "gov_data_inject must explicitly state Recorder is inaccessible due to Cloudflare"
