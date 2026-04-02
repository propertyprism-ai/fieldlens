"""
test_gov_fetcher.py — L1 单元测试 + Smoke 测试，gov_fetcher.py
"""
import pytest
from unittest.mock import patch, MagicMock


# ── L1 Unit Tests (mock requests) ─────────────────────────────────────────────

def test_fema_returns_flood_zone_on_success():
    """mock requests.get → status=SUCCESS, flood_zone 非空"""
    from src.gov_fetcher import fetch_fema_flood_zone

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "features": [{"attributes": {"FLD_ZONE": "X", "ZONE_SUBTY": "OUTSIDE SFHA", "SFHA_TF": "F"}}]
    }

    with patch("src.gov_fetcher.requests.get", return_value=mock_response):
        result = fetch_fema_flood_zone(33.2148, -111.6340)

    assert result["status"] == "SUCCESS"
    assert result["flood_zone"] == "X"
    assert result["in_sfha"] is False


def test_fema_returns_failed_on_no_features():
    """mock 返回空 features → status=FAILED"""
    from src.gov_fetcher import fetch_fema_flood_zone

    mock_response = MagicMock()
    mock_response.json.return_value = {"features": []}

    with patch("src.gov_fetcher.requests.get", return_value=mock_response):
        result = fetch_fema_flood_zone(33.2148, -111.6340)

    assert result["status"] == "FAILED"


def test_fema_returns_failed_on_request_error():
    """requests 抛 Exception → status=FAILED，不崩溃"""
    from src.gov_fetcher import fetch_fema_flood_zone

    with patch("src.gov_fetcher.requests.get", side_effect=Exception("timeout")):
        result = fetch_fema_flood_zone(33.2148, -111.6340)

    assert result["status"] == "FAILED"
    assert "error" in result


def test_maricopa_parcel_returns_owner_on_success():
    """mock 返回 parcel features → owner/parcel_number 非空"""
    from src.gov_fetcher import fetch_maricopa_parcel

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "features": [{"attributes": {
            "APN": "50330033",
            "OWNER": "SMITH JOHN A",
            "OWNER2": None,
            "SITUS": "21145 E SADDLE WAY",
            "LEGAL": "LOT 123",
            "ASSESSED_FULL_CASH": 385000
        }}]
    }

    with patch("src.gov_fetcher.requests.get", return_value=mock_response):
        result = fetch_maricopa_parcel(33.2148, -111.6340)

    assert result["status"] == "SUCCESS"
    assert result["owner"] == "SMITH JOHN A"
    assert result["parcel_number"] == "50330033"


def test_maricopa_parcel_skips_if_market_none():
    """fetch_gov_sources(market_key=None) → assessor status=NOT_CONFIGURED"""
    from src.gov_fetcher import fetch_gov_sources

    mock_response = MagicMock()
    mock_response.json.return_value = {"features": []}

    prop = {"latitude": 33.2148, "longitude": -111.6340}

    with patch("src.gov_fetcher.requests.get", return_value=mock_response):
        result = fetch_gov_sources(prop, market_key=None)

    assert result["assessor"]["status"] == "NOT_CONFIGURED"


def test_fetch_gov_sources_fema_always_runs():
    """market_key=None → fema 仍尝试；assessor=NOT_CONFIGURED"""
    from src.gov_fetcher import fetch_gov_sources

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "features": [{"attributes": {"FLD_ZONE": "X", "ZONE_SUBTY": "OUTSIDE SFHA", "SFHA_TF": "F"}}]
    }

    prop = {"latitude": 33.2148, "longitude": -111.6340}

    with patch("src.gov_fetcher.requests.get", return_value=mock_response):
        result = fetch_gov_sources(prop, market_key=None)

    assert result["fema"]["status"] in ("SUCCESS", "FAILED")
    assert result["assessor"]["status"] == "NOT_CONFIGURED"


def test_treasurer_skipped_if_assessor_failed():
    """assessor status=FAILED → treasurer status=SKIPPED_DEPENDENCY"""
    from src.gov_fetcher import fetch_gov_sources

    def mock_requests_get(url, **kwargs):
        resp = MagicMock()
        if "hazards.fema.gov" in url:
            resp.json.return_value = {
                "features": [{"attributes": {"FLD_ZONE": "X", "ZONE_SUBTY": "", "SFHA_TF": "F"}}]
            }
        else:
            # Assessor returns no features → FAILED
            resp.json.return_value = {"features": []}
        return resp

    prop = {"latitude": 33.2148, "longitude": -111.6340}

    with patch("src.gov_fetcher.requests.get", side_effect=mock_requests_get):
        result = fetch_gov_sources(prop, market_key="phoenix_maricopa")

    assert result["assessor"]["status"] == "FAILED"
    assert result["treasurer"]["status"] == "SKIPPED_DEPENDENCY"


# ── Smoke Tests (real API calls) ──────────────────────────────────────────────

@pytest.mark.smoke
def test_fema_flood_zone_smoke():
    """Queen Creek 坐标 → FEMA status=SUCCESS, flood_zone 有效"""
    from src.gov_fetcher import fetch_fema_flood_zone

    result = fetch_fema_flood_zone(lat=33.2148, lon=-111.6340)
    assert result["status"] == "SUCCESS", f"FEMA failed: {result}"
    assert result["flood_zone"] in ("X", "AE", "AH", "VE", "A", "D"), \
        f"Unexpected zone: {result.get('flood_zone')}"


@pytest.mark.smoke
def test_maricopa_assessor_smoke():
    """Maricopa Assessor GIS endpoint — NOT_AVAILABLE (JS redirect).
    A1 decision: verify call does not crash and returns valid status."""
    from src.gov_fetcher import fetch_maricopa_parcel

    result = fetch_maricopa_parcel(lat=33.2148, lon=-111.6340)
    # A1: accept FAILED/NOT_AVAILABLE — GIS endpoint returns JS redirect
    assert result["status"] in ("SUCCESS", "FAILED", "NOT_AVAILABLE"),         f"Unexpected status: {result}"
    print(f"\n[smoke] Assessor status: {result['status']} — {result.get('error', 'ok')}")


@pytest.mark.smoke
def test_fetch_gov_sources_integration():
    """完整串联 fetch_gov_sources — FEMA must succeed, Assessor may be PARTIAL"""
    from src.gov_fetcher import fetch_gov_sources

    prop = {"latitude": 33.2148, "longitude": -111.6340}
    result = fetch_gov_sources(prop, market_key="phoenix_maricopa")

    # FEMA is mandatory
    assert result["fema"]["status"] == "SUCCESS", f"FEMA: {result['fema']}"
    # Assessor A1: does not crash, returns valid status
    assert result["assessor"]["status"] in ("SUCCESS", "FAILED", "NOT_AVAILABLE"),         f"Assessor unexpected: {result['assessor']}"
    print(f"\n[smoke] FEMA Zone: {result['fema'].get('flood_zone')}")
    print(f"[smoke] Assessor: {result['assessor']['status']}")
